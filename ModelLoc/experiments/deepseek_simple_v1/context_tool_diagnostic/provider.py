"""Explicit non-thinking transport and cross-process, pessimistic budget reservations."""
import fcntl, json, math, os, stat, time, uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import httpx
from openai import OpenAI
from .common import RUN,write,read,digest,utc

_CLIENTS={}

class BudgetExceeded(RuntimeError):pass
class UnexpectedThinking(RuntimeError):pass
class ModelMismatch(RuntimeError):pass
class AmbiguousPriorRequest(RuntimeError):pass

def credential():
    if os.environ.get('DEEPSEEK_API_KEY'):return os.environ['DEEPSEEK_API_KEY']
    p=Path('/home/wdt/.config/graphlocator/deepseek.env');s=p.stat()
    if s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)&0o077:raise PermissionError('Credential permissions')
    for line in p.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1)
            if k.strip()=='DEEPSEEK_API_KEY':return v.strip().strip('\"\'')
    raise RuntimeError('Missing DeepSeek credential')

def free_get(route):
    if route not in ('models','user/balance'):raise ValueError(route)
    for attempt in range(4):
        try:
            r=httpx.get('https://api.deepseek.com/'+route,headers={'Authorization':'Bearer '+credential()},
                        trust_env=False,timeout=45)
            r.raise_for_status();return r.json()
        except (httpx.TransportError,httpx.HTTPStatusError):
            if attempt==3:raise RuntimeError('Read-only API failed') from None
            time.sleep(2**attempt)

def price_tier(start,end):
    def peak(t):
        d=datetime.fromisoformat(t)
        # Frozen experiment dates Oct21 onward: no Chinese statutory holiday
        # until Jan1. Refuse extrapolation rather than invent a holiday table.
        if not '2026-10-21'<=d.date().isoformat()<='2026-12-31':return None
        hour=d.hour+d.minute/60+d.second/3600
        return d.weekday()<5 and (1<=hour<4 or 6<=hour<10)
    a,b=peak(start),peak(end)
    return 'peak' if a is True and b is True else 'off_peak' if a is False and b is False else 'boundary_or_unknown_upper_peak'

@contextmanager
def budget():
    RUN.mkdir(parents=True,exist_ok=True)
    with (RUN/'budget.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        p=RUN/'budget.json'
        x=read(p) if p.exists() else {'stage_cap_usd':3.,'cases':{},'attempts':{}}
        if x['stage_cap_usd']!=3.:raise RuntimeError('Diagnostic budget must remain exactly USD3')
        try:yield x
        finally:write(p,x,replace=True)

def total_budget(x):return sum(v['charged_upper_usd'] for v in x['attempts'].values())

def reserve(key,request_id,input_upper,output_limit,*,token_upper=None):
    amount=(input_upper*.3+output_limit*1.2)/1e6
    tokens=(input_upper if token_upper is None else token_upper)+output_limit
    with budget() as x:
        case=x['cases'].setdefault(key,{'charged_upper_usd':0.,'total_tokens_upper':0,'soft_triggered':False})
        if total_budget(x)+amount>x['stage_cap_usd']:raise BudgetExceeded('independent diagnostic USD3 cap')
        if (case['charged_upper_usd']+amount)*7>1.5:raise BudgetExceeded('per-method issue CNY1.50 cap')
        if case['total_tokens_upper']+tokens>400000:raise BudgetExceeded('400000 token cap')
        x['attempts'][request_id]={'key':key,'status':'reserved','charged_upper_usd':amount,
            'total_tokens_upper':tokens,'reserved_at':utc()}
        case['charged_upper_usd']+=amount;case['total_tokens_upper']+=tokens
        case['soft_triggered']=case['charged_upper_usd']*7>.5
    return amount

def settle(request_id,usage=None,status='billing_unknown'):
    with budget() as x:
        a=x['attempts'][request_id];c=x['cases'][a['key']]
        if usage:
            prompt=usage['prompt_tokens'];output=usage['completion_tokens']
            hit=usage.get('prompt_cache_hit_tokens')
            charge=((hit*.006+(prompt-hit)*.3) if hit is not None else prompt*.3)+output*1.2
            charge/=1e6
            if charge>a['charged_upper_usd']+1e-9:raise RuntimeError('Reservation underestimated actual charge')
            c['charged_upper_usd']+=charge-a['charged_upper_usd']
            c['total_tokens_upper']+=prompt+output-a['total_tokens_upper']
            a.update(charged_upper_usd=charge,total_tokens_upper=prompt+output,usage=usage)
        a.update(status=status,settled_at=utc())

def usage_cost(usage,tier):
    p,o=usage['prompt_tokens'],usage['completion_tokens'];hit=usage.get('prompt_cache_hit_tokens')
    normalized=(p*.3+o*1.2)/1e6
    if hit is None:return None,normalized
    cost=(hit*.006+(p-hit)*.3+o*1.2)/1e6
    return cost*(.5 if tier=='off_peak' else 1),normalized

class Provider:
    def __init__(self,method,iid,out):
        self.method,self.iid,self.out=method,iid,Path(out);self.seq=0
        self.deepseek=method.startswith(('D-','A-'));self.client=_CLIENTS.get(self.deepseek)

    def ask(self,messages,stage,*,max_tokens=2048,json_mode=False,temperature=0.):
        if (RUN/'emergency_stop.json').exists():raise UnexpectedThinking('Global API safety stop is active')
        self.seq+=1;folder=self.out/'calls'/f'{self.seq:04d}_{stage}';folder.mkdir(parents=True,exist_ok=True)
        req={'model':'deepseek-flash' if self.deepseek else 'llama3','messages':messages,
             'max_tokens':max_tokens,'temperature':temperature}
        if self.deepseek:req['thinking']={'type':'disabled'}
        else:req['seed']=0
        if json_mode:req['response_format']={'type':'json_object'}
        fingerprint=digest(json.dumps(req,sort_keys=True,ensure_ascii=False))
        if (folder/'request.json').exists():
            if read(folder/'request.json')['sha256']!=fingerprint:raise AmbiguousPriorRequest('Replay request drift')
            if (folder/'result.json').exists():return read(folder/'result.json')
            if list(folder.glob('attempt_*_started.json')):
                raise AmbiguousPriorRequest('Incomplete prior transmitted call: preserve; do not resample')
            # No attempt-start receipt means reservation stopped this request
            # before any wire transmission. Resume that same unsent request.
        else:write(folder/'request.json',{'sha256':fingerprint,'request':req,'thinking_mode':'disabled' if self.deepseek else None})
        cold_client=self.client is None
        if self.client is None:
            self.client=OpenAI(base_url='https://api.deepseek.com' if self.deepseek else 'http://127.0.0.1:7333/v1',
                api_key=credential() if self.deepseek else 'token-abc123',max_retries=0,timeout=240,
                http_client=httpx.Client(trust_env=False,timeout=240))
            _CLIENTS[self.deepseek]=self.client
        # UTF8 byte upper bound covers all visible tokens plus role wrappers.
        upper=len(json.dumps(messages,ensure_ascii=False).encode())+128*len(messages)+1024
        if self.deepseek:
            from src.token_counter import prompt_upper
            token_upper=prompt_upper(messages)
        else:token_upper=None
        key=self.method+'|'+self.iid
        began_all=time.perf_counter()
        for attempt in range(4):
            request_id=str(uuid.uuid4());began=utc();attempt_began=time.perf_counter()
            if self.deepseek:reserve(key,request_id,upper,max_tokens,token_upper=token_upper)
            receipt={'run_id':RUN.name,'instance_id':self.iid,'method':self.method,'stage':stage,
                'sequence':self.seq,'attempt':attempt,'request_id':request_id,'request_sha256':fingerprint,
                'model_requested':req['model'],'documented_version':'DeepSeek-V4.1-Flash-1017' if self.deepseek else 'Qwen2.5-Coder-7B-Instruct',
                'start_utc':began,'thinking_mode':'disabled' if self.deepseek else None,'reasoning_effort':None,
                'max_output_tokens':max_tokens,'input_upper_bound':upper,'input_cost_byte_upper':upper,
                'input_token_upper_estimate':token_upper,'cold_http_client':cold_client}
            write(folder/f'attempt_{attempt}_started.json',receipt)
            try:
                wire={k:v for k,v in req.items() if k!='thinking'}
                if self.deepseek:wire['extra_body']={'thinking':{'type':'disabled'}}
                response=self.client.chat.completions.create(**wire)
            except Exception as e:
                status=getattr(e,'status_code',None)
                receipt.update(end_utc=utc(),error_type=type(e).__name__,http_status=status,
                    billing_status='billing_unknown',attempt_elapsed_seconds=time.perf_counter()-attempt_began)
                if self.deepseek:settle(request_id)
                write(folder/f'attempt_{attempt}_error.json',receipt)
                # Only transport/transient server failures, no semantic retries.
                retryable=status in (408,409,429,500,502,503,504) or type(e).__name__ in ('APIConnectionError','APITimeoutError')
                if not retryable or attempt==3:raise RuntimeError(f'API request failed: {type(e).__name__}; HTTP {status}') from None
                time.sleep(2**attempt);continue
            raw=response.model_dump(exclude_none=True);write(folder/f'attempt_{attempt}_response.json',raw)
            usage=response.usage.model_dump(exclude_none=True) if response.usage else None
            if self.deepseek:settle(request_id,usage,status='usage_received' if usage else 'billing_unknown')
            msg=response.choices[0].message;reasoning=getattr(msg,'reasoning_content',None)
            receipt.update(end_utc=utc(),model_reported=response.model,usage=usage,
                reasoning_content_present=bool(reasoning),finish_reason=response.choices[0].finish_reason,
                response_sha256=digest(json.dumps(raw,sort_keys=True)),http_status=200,
                elapsed_seconds=time.perf_counter()-began_all,price_snapshot_id='deepseek_20261021_official',
                attempt_elapsed_seconds=time.perf_counter()-attempt_began,
                price_tier=price_tier(began,utc()) if self.deepseek else None)
            if usage and self.deepseek:
                actual,normalized=usage_cost(usage,receipt['price_tier'])
                receipt.update(api_cost_usd_actual=actual,api_cost_usd_normalized=normalized,
                    api_cost_cny_budget=actual*7 if actual is not None else None)
            write(folder/f'attempt_{attempt}_receipt.json',receipt)
            if self.deepseek and usage and usage['prompt_tokens']>token_upper:
                write(RUN/'emergency_stop.json',{'reason':'Offline tokenizer wrapper upper estimate violated',
                    'request_id':request_id,'upper_estimate':token_upper,'actual':usage['prompt_tokens'],'time':utc()},replace=True)
                raise RuntimeError('Offline tokenizer drift; stop before more paid requests')
            if reasoning and self.deepseek:
                write(RUN/'emergency_stop.json',{'reason':'Unexpected thinking','request_id':request_id,'time':utc()},replace=True)
                raise UnexpectedThinking('Non-empty reasoning_content with disabled thinking')
            if self.deepseek and response.model not in ('deepseek-flash','deepseek-v4.1-flash','DeepSeek-V4.1-Flash-1017'):
                write(RUN/'emergency_stop.json',{'reason':'Response model mismatch','model':response.model,'time':utc()},replace=True)
                raise ModelMismatch('Unexpected response model '+response.model)
            if not usage:raise RuntimeError('Missing API usage')
            if response.choices[0].finish_reason!='stop':raise RuntimeError('Truncated or rejected model response')
            result={'content':msg.content or '', 'usage':usage,'receipt':receipt}
            write(folder/'result.json',result);return result
