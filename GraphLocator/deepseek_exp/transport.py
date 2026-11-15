"""Official API adapter with shared, balance-based CNY budget reservations.

Qwen inference files are never edited. Local Qwen tokenization remains only a
batch-size heuristic in B2; official usage is the token/cost evidence here.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import fcntl
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import time
import uuid

from openai import OpenAI
from llms import ContextBudgetExceeded, record

ENDPOINT = 'https://api.deepseek.com'
MODEL = 'deepseek-flash'
MODEL_NAME = 'DeepSeek-V4.1-Flash'
_client = None
_key = None
_sequence = 0


class BudgetLimitReached(RuntimeError):
    pass


class OutputBudgetExceeded(RuntimeError):
    pass


def root():
    return Path(os.environ['GRAPHLOCATOR_DEEPSEEK_WORK'])


def settings():
    return json.loads((root()/'config.json').read_text())


def credential():
    global _key
    if _key is None:
        path = Path(settings()['credential_file'])
        if path.stat().st_uid != os.getuid() or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise PermissionError('Credential file must belong to this user and have mode 600')
        values = {}
        for line in path.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                name,value = line.split('=',1)
                values[name.strip()] = value.strip().strip('\"\'')
        _key = values.get('DEEPSEEK_API_KEY')
        if not _key:
            raise ValueError('DEEPSEEK_API_KEY is missing')
    return _key


def api_get(route):
    if route not in ('models','user/balance'):
        raise ValueError('Unexpected official API route')
    # Use the same HTTP/TLS implementation as paid calls; retry only these free,
    # read-only endpoints when a connection handshake fails transiently.
    import httpx
    for attempt in range(4):
        try:
            response = httpx.get(ENDPOINT+'/'+route,
                headers={'Authorization':'Bearer '+credential()},timeout=40,trust_env=False)
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError,httpx.HTTPStatusError) as exc:
            status = getattr(getattr(exc,'response',None),'status_code',None)
            if attempt==3 or status in (400,401,402,403,404,422):
                raise RuntimeError('Official read-only endpoint failed: '+type(exc).__name__) from None
            time.sleep(attempt+1)


def balance():
    value = api_get('user/balance')
    entries = [v for v in value['balance_infos'] if v['currency']=='CNY']
    if len(entries)!=1:
        raise ValueError('A CNY balance is required for the authorized CNY budget')
    return float(entries[0]['total_balance'])


def atomic(path,value):
    target = Path(path)
    temporary = target.with_suffix(target.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(target)


@contextmanager
def locked_budget():
    with (root()/'budget.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path = root()/'budget.json'
        state = json.loads(path.read_text())
        try:
            yield state
        finally:
            atomic(path,state)


def usage_upper_usd(usage):
    """Peak prices; no assumption of off-peak availability or cache savings."""
    hit = usage.get('prompt_cache_hit_tokens',0) or 0
    total = usage.get('prompt_tokens',0) or 0
    miss = usage.get('prompt_cache_miss_tokens',max(0,total-hit)) or 0
    output = usage.get('completion_tokens',0) or 0
    return (hit*0.006+miss*0.3+output*1.2)/1_000_000


def reserve(input_upper,output_limit,request_id):
    # 10 CNY/USD is a deliberately conservative reservation conversion, not a
    # claimed exchange rate. Actual budget spending uses official CNY balances.
    hold = (input_upper*0.3+output_limit*1.2)/1_000_000*10
    identity = str(uuid.uuid4())
    with locked_budget() as state:
        current = balance()
        used = max(0,state['initial_balance_cny']-current)
        # Official balance reads can lag token receipts. Enforce the greater of
        # actual deductions and an independent conservative token charge bound.
        used_upper = max(used,state.get('probe_charge_upper_cny',0.01)+state['peak_usd_upper']*10)
        in_flight = sum(v['reserved_cny'] for v in state['reservations'].values())
        remaining = min(current,state['limit_cny']-used_upper)-in_flight
        state.update(last_balance_cny=current,observed_spend_cny=used,
                     token_spend_upper_cny=used_upper,
                     updated_at=datetime.now().astimezone().isoformat())
        if remaining < hold:
            state['stop_reason'] = 'budget_reservation_limit'
            raise BudgetLimitReached(f'Remaining CNY budget {remaining:.4f} is below safe request reservation {hold:.4f}')
        if state.get('stop_reason'):
            raise BudgetLimitReached('Experiment budget guard is stopped: '+state['stop_reason'])
        state['reservations'][identity] = dict(reserved_cny=hold,
            instance_id=os.environ.get('GRAPHLOCATOR_INSTANCE_ID'),pid=os.getpid(),
            request_id=request_id,started_at=datetime.now().astimezone().isoformat())
    return identity


def settle(identity,usage=None,uncertain=False):
    with locked_budget() as state:
        current = balance()
        state.update(last_balance_cny=current,
            observed_spend_cny=max(0,state['initial_balance_cny']-current),
            updated_at=datetime.now().astimezone().isoformat())
        reservation = state['reservations'].pop(identity)
        if usage:
            state['returned_calls'] += 1
            for k in ('prompt_tokens','completion_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens'):
                state['usage'][k] = state['usage'].get(k,0)+(usage.get(k,0) or 0)
            state['peak_usd_upper'] += usage_upper_usd(usage)
        if uncertain:
            # A timed-out paid request can still be billed. Keep its reservation
            # rather than releasing money for unverified subsequent requests.
            state['reservations'][identity] = dict(**reservation,uncertain=True)


def messages_for_api(messages,schema=None):
    active = deepcopy(messages)
    if schema:
        text = ('Return exactly one JSON object satisfying this JSON Schema. '
            'The schema is an output-format constraint, not repository evidence.\n'+
            json.dumps(schema,ensure_ascii=False,separators=(',',':')))
        if active and active[0]['role']=='system':
            active[0]['content'] += '\n'+text
        else:
            active.insert(0,dict(role='system',content=text))
    return active


def request(messages,tools=None,schema=None,role='model',limit=4096,required=False):
    global _client,_sequence
    if tools or required:
        raise ValueError('Frozen B2 uses validated JSON actions, not native tool calls')
    cfg = settings()
    thinking = cfg['thinking']=='enabled'
    active = messages_for_api(messages,schema)
    output_limit = max(limit,cfg['causal_output_tokens'] if role.startswith('generate') or role.startswith('update') else cfg['json_output_tokens']) if thinking else limit
    # Byte count plus message framing conservatively bounds unknown-tokenizer
    # input, and never pretends Qwen tokenizer counts are DeepSeek exact counts.
    input_upper = len(json.dumps(active,ensure_ascii=False).encode())+256*len(active)
    if input_upper+output_limit+512 > cfg['context_limit']:
        raise ContextBudgetExceeded('Conservative UTF-8 input bound exceeds official DeepSeek context window')
    _sequence += 1
    number = _sequence
    trace = Path(os.environ['GRAPHLOCATOR_TRACE_FILE'])
    folder = trace.parent/'prompts'/trace.stem
    folder.mkdir(parents=True,exist_ok=True)
    prompt = folder/f'{number:05d}.json.gz'
    with gzip.open(prompt,'wt',encoding='utf8') as stream:
        json.dump(dict(messages=active,tools=None,response_schema=schema),stream,ensure_ascii=False)
    record('request_preflight',request_id=number,caller=role,prompt_file=str(prompt))
    reservation = reserve(input_upper,output_limit,number)
    if _client is None:
        import httpx
        _client = OpenAI(base_url=ENDPOINT,api_key=credential(),timeout=600,max_retries=0,
                        http_client=httpx.Client(trust_env=False,timeout=600))
    kwargs = dict(model=MODEL,messages=active,max_tokens=output_limit,
                  extra_body={'thinking':{'type':cfg['thinking']}})
    if thinking:
        kwargs['reasoning_effort'] = cfg['reasoning_effort']
    else:
        kwargs['temperature'] = 0
    if schema:
        kwargs['response_format'] = {'type':'json_object'}
    record('model_request',request_id=number,caller=role,endpoint=ENDPOINT,model=MODEL_NAME,
        input_tokens=None,input_byte_upper=input_upper,max_output_tokens=output_limit,
        thinking=cfg['thinking'],reasoning_effort=cfg['reasoning_effort'] if thinking else None,
        structured=bool(schema),structured_protocol='json_object+schema_prompt+client_validation' if schema else None,
        prompt_file=str(prompt),prompt_sha256=hashlib.sha256(json.dumps(active,sort_keys=True).encode()).hexdigest())
    started = time.monotonic()
    try:
        response = _client.chat.completions.create(**kwargs)
    except Exception as exc:
        safe = str(exc).replace(credential(),'[REDACTED]')
        status = getattr(exc,'status_code',None)
        uncertain = status not in (400,401,402,403,404,422,429)
        record('model_error',request_id=number,caller=role,error=type(exc).__name__,
               status=status,message=safe[:1000],uncertain_billing=uncertain)
        settle(reservation,uncertain=uncertain)
        raise RuntimeError(f'Official API {type(exc).__name__}: {safe[:1000]}') from None
    usage = response.usage.model_dump(exclude_none=True)
    decoded = [choice.message.model_dump(exclude_none=True) for choice in response.choices]
    reasons = [choice.finish_reason for choice in response.choices]
    record('model_response',request_id=number,caller=role,attempt=0,responses=decoded,
        finish_reasons=reasons,usage=usage,model=response.model,system_fingerprint=response.system_fingerprint,
        seconds=time.monotonic()-started,peak_usd_upper=usage_upper_usd(usage))
    settle(reservation,usage)
    if any(reason=='length' for reason in reasons):
        raise OutputBudgetExceeded('Thinking and answer reached the configured total output token cap; raw response retained')
    if any(reason not in ('stop','tool_calls') for reason in reasons):
        raise RuntimeError('Unexpected official API finish reason: '+str(reasons))
    return decoded,reasons,usage


def get_llm_response(model_name,messages,with_tool=False,tools=None,
                     temperature=0,n=1,max_completion_tokens=8192):
    if with_tool or n!=1:
        raise ValueError('Unexpected legacy B2 transport parameters')
    role = inspect.currentframe().f_back.f_code.co_name
    return request(messages,role=role,limit=4096)
