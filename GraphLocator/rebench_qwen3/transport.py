"""Recorded localhost HTTP boundary for the unchanged GraphLocator agents."""
from __future__ import annotations
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class ContextBudgetExceeded(RuntimeError): pass
class ProtocolError(RuntimeError): pass
class ModelHTTPError(RuntimeError): pass

_state = None
# The non-thinking recommendation on the exact deployed Qwen3-8B revision.
# seed=0 is the experiment's fixed request seed, not a model-card guarantee.
FIXED_SAMPLING = {'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'seed':0}
SAMPLING_PROFILE_SOURCE = 'https://huggingface.co/Qwen/Qwen3-8B/blob/b968826d9c46dd6066d109eabc6255188de91218/README.md'


def _atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as f:
        f.write(payload); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, path)


def _json(path, value):
    _atomic(path, (json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n').encode())


def _gzip(path, value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, default=str).encode()
    _atomic(path, gzip.compress(raw, mtime=0))


def record(event, **fields):
    if _state is None: return
    value = {'time':time.time(), 'event':event, **fields}
    with (_state['output']/'events.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, default=str)+'\n'); f.flush(); os.fsync(f.fileno())


def configure(output_dir, endpoint='http://127.0.0.1:7353/v1', model='qwen3-8b', *, opener=None):
    global _state
    parsed = urlsplit(endpoint)
    if (parsed.scheme != 'http' or parsed.hostname not in {'localhost','127.0.0.1','::1'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path.rstrip('/') != '/v1' or model != 'qwen3-8b'):
        raise ValueError('Only the fixed local Qwen3 model and /v1 endpoint are permitted')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if list(output.glob('*_request.json.gz')):
        raise FileExistsError('Refusing to append new inference to an existing HTTP attempt directory')
    _state = {'output':output, 'endpoint':endpoint.rstrip('/'), 'model':model,
              'opener':opener or urlopen, 'sequence':0, 'attempts':0}
    receipt = {'endpoint':_state['endpoint'],'model':model,**FIXED_SAMPLING,'n':1,
        'actual_sampling':dict(FIXED_SAMPLING),'sampling_profile_source':SAMPLING_PROFILE_SOURCE,
        'seed_policy':'Experiment-fixed request seed 0; not a claim of bitwise determinism',
        'max_completion_tokens':8192,'service_context_limit':65536,'thinking':False,
        'semantic_retries':0,'transport_retries':1,'tokenize_timeout':120,'http_timeout':600,
        'relevance_serialization':'One same-order JSON boolean array; exact candidate length via JSON schema',
        'context_policy':'Keep input unchanged; output=min(8192,capacity-input-64); fail if available<1'}
    _json(output/'transport_config.json', receipt)
    return receipt


def _exchange(path, payload, stem, phase):
    raw = json.dumps(payload, ensure_ascii=False).encode()
    _gzip(_state['output']/(stem+'_request.json.gz'), raw)
    request = Request(_state['endpoint'].removesuffix('/v1')+path, data=raw,
                      headers={'Content-Type':'application/json'})
    started = time.monotonic()
    record('http_started',phase=phase,stem=stem,request_sha256=hashlib.sha256(raw).hexdigest())
    status, response_raw, error = None, b'', None
    try:
        with _state['opener'](request, timeout=120 if phase=='tokenize' else 600) as response:
            status = int(response.status); response_raw = response.read()
    except HTTPError as exc:
        status = exc.code; response_raw = exc.read(); error = str(exc)
    except (URLError, TimeoutError, ConnectionError, OSError) as exc:
        error = f'{type(exc).__name__}: {exc}'
    # Raw response and accounting are durable before decoding by the agents.
    _gzip(_state['output']/(stem+'_response.json.gz'), response_raw)
    decoded = None
    try:
        decoded = json.loads(response_raw)
    except (ValueError, UnicodeDecodeError): pass
    usage = decoded.get('usage') if isinstance(decoded,dict) else None
    known = isinstance(usage,dict) and all(isinstance(usage.get(k),int) and not isinstance(usage[k],bool)
              and usage[k]>=0 for k in ('prompt_tokens','completion_tokens'))
    record('http_finished',phase=phase,stem=stem,status=status,usage=usage,usage_known=known,
           response_model=decoded.get('model') if isinstance(decoded,dict) else None,
           response_sha256=hashlib.sha256(response_raw).hexdigest(),elapsed_seconds=time.monotonic()-started,error=error)
    return status, decoded, error


def get_llm_response(model_name, messages, with_tool=False, tools=None,
                     temperature=0.0, n=1, max_completion_tokens=8192, *, relevance_count=None):
    if _state is None: raise RuntimeError('configure() must run before any model request')
    if n != 1: raise ProtocolError('This frozen run permits one completion per agent request')
    if relevance_count is not None and (type(relevance_count) is not int or relevance_count<0 or with_tool):
        raise ProtocolError('A relevance schema requires a nonnegative exact candidate count and no tools')
    _state['sequence'] += 1
    number = _state['sequence']
    role = inspect.currentframe().f_back.f_code.co_name
    params = {'model':_state['model'],'messages':messages,
              'chat_template_kwargs':{'enable_thinking':False}}
    if with_tool: params['tools'] = tools
    token_payload = {**params, 'add_generation_prompt':True}
    status, counted, error = _exchange('/tokenize',token_payload,f'{number:05d}_tokenize','tokenize')
    if status != 200 or not isinstance(counted,dict):
        raise ModelHTTPError(f'Tokenizer HTTP {status}: {error or counted}')
    prompt_tokens, capacity = counted.get('count'), counted.get('max_model_len')
    if (not isinstance(prompt_tokens,int) or isinstance(prompt_tokens,bool) or prompt_tokens<0
            or capacity != 65536):
        raise ProtocolError('Unexpected precise tokenizer count/context capacity')
    available = capacity - prompt_tokens - 64
    if available < 1:
        record('context_error',caller=role,input_tokens=prompt_tokens,capacity=capacity,output_reserved=8192)
        raise ContextBudgetExceeded(f'Input {prompt_tokens}+64 leaves no output within {capacity}; no generation sent')
    output_limit = min(8192,available)
    payload = {**params,**FIXED_SAMPLING,'n':1,'max_completion_tokens':output_limit,'stream':False}
    if with_tool: payload.update(tool_choice='auto',parallel_tool_calls=False)
    if relevance_count is not None:
        schema={'type':'array','items':{'type':'boolean'},'minItems':relevance_count,'maxItems':relevance_count}
        payload['response_format']={'type':'json_schema','json_schema':{
            'name':'relevance_flags','strict':True,'schema':schema}}
    record('model_request',request_id=number,caller=role,input_tokens=prompt_tokens,
           model=_state['model'],thinking=False,max_output_tokens=output_limit,requested_output_tokens=8192,
           caller_requested_temperature=temperature,actual_sampling=dict(FIXED_SAMPLING),
           sampling_profile_source=SAMPLING_PROFILE_SOURCE,
           relevance_count=relevance_count,response_format=payload.get('response_format'))
    for retry in range(2):
        _state['attempts'] += 1
        stem=f'{number:05d}_attempt_{retry+1}'
        status, response, error = _exchange('/v1/chat/completions',payload,stem,'generation')
        if status == 200:
            if not isinstance(response,dict) or not isinstance(response.get('choices'),list) or len(response['choices']) != 1:
                raise ProtocolError('Successful HTTP did not contain exactly one choice; no semantic redraw')
            choices=response['choices']; decoded=[choice.get('message') for choice in choices]
            if any(not isinstance(message,dict) for message in decoded):
                raise ProtocolError('Invalid message object; no semantic redraw')
            record('model_response',request_id=number,caller=role,usage=response.get('usage'),
                   actual_model=response.get('model'),finish_reasons=[c.get('finish_reason') for c in choices])
            return decoded,[c.get('finish_reason') for c in choices],response.get('usage')
        retryable = status is None or status in {500,502,503,504}
        if not retryable or retry:
            raise ModelHTTPError(f'Model HTTP {status}: {error or response}')
        record('transport_retry',request_id=number,attempt=retry+1,status=status)
    raise AssertionError('unreachable')


def summary_usage(workdir=None):
    """Reconstruct model usage from durable events, including interrupted HTTP.

    Accepts the /work/http directory or its /work parent. Tokenize requests are
    recorded for evidence but are not counted as completion/model attempts.
    """
    if workdir is None:
        if _state is None: raise RuntimeError('No configured transport')
        directory = _state['output']
    else:
        directory = Path(workdir)
        if not (directory/'events.jsonl').exists() and (directory/'http').is_dir():
            directory = directory/'http'
    path=directory/'events.jsonl'; attempts={}; malformed=0
    if path.exists():
        for line in path.read_text().splitlines():
            try: row=json.loads(line)
            except ValueError:
                malformed+=1; continue
            if row.get('phase')!='generation' or row.get('event') not in {'http_started','http_finished'}: continue
            stem=row.get('stem')
            if not isinstance(stem,str): malformed+=1; continue
            entry=attempts.setdefault(stem,{})
            if row['event']=='http_finished' and 'http_finished' in entry and entry['http_finished']!=row:
                entry['conflicting_receipts']=True
            entry[row['event']]=row
    pp=cc=unknown=0; statuses={}
    for entry in attempts.values():
        receipt=entry.get('http_finished',{}); usage=receipt.get('usage')
        known=(receipt.get('usage_known') is True and isinstance(usage,dict)
               and all(isinstance(usage.get(k),int) and not isinstance(usage[k],bool) and usage[k]>=0
                       for k in ('prompt_tokens','completion_tokens')) and not entry.get('conflicting_receipts'))
        if known: pp+=usage['prompt_tokens'];cc+=usage['completion_tokens']
        else: unknown+=1
        key=str(receipt.get('status','unfinished'));statuses[key]=statuses.get(key,0)+1
    unknown=max(unknown,malformed)
    return {'prompt_tokens':None if unknown else pp,'completion_tokens':None if unknown else cc,
        'total_tokens':None if unknown else pp+cc,'known_prompt_tokens':pp,'known_completion_tokens':cc,
        'known_total_tokens':pp+cc,'unknown_usage_requests':unknown,'http_attempts':len(attempts),
        'completion_requests':len({s.split('_attempt_')[0] for s in attempts}),
        'unparsed_ledger_records':malformed,'http_statuses':statuses,'api_cost_usd':0.0,
        'accounting_source':str(path)}


usage_snapshot = summary_usage
summarize_usage = summary_usage
