"""Official API only; actual wire JSON/usage, no hidden or budget retries."""
import json
import os
from pathlib import Path
import stat
import time
from datetime import datetime
import httpx
from . import common as C

PRICE_SOURCE='https://api-docs.deepseek.com/quick_start/pricing/'
PRICES={'peak':{'cache_hit':0.006,'cache_miss':0.3,'output':1.2},
        'off_peak':{'cache_hit':0.003,'cache_miss':0.15,'output':0.6}}


def credential():
    if os.environ.get('DEEPSEEK_API_KEY'):
        return os.environ['DEEPSEEK_API_KEY']
    path=Path('/home/wdt/.config/graphlocator/deepseek.env')
    metadata=path.stat()
    if metadata.st_uid!=os.getuid() or stat.S_IMODE(metadata.st_mode)&0o077:
        raise PermissionError('DeepSeek credential must be privately owned')
    for line in path.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            name,value=line.split('=',1)
            if name.strip()=='DEEPSEEK_API_KEY':return value.strip().strip('\"\'')
    raise RuntimeError('DeepSeek credential not configured')


def estimated_cost(usage,started,ended):
    if not isinstance(usage,dict):return {'usd':None,'usage_unknown':True}
    p,o=usage.get('prompt_tokens'),usage.get('completion_tokens')
    hit=usage.get('prompt_cache_hit_tokens',(usage.get('prompt_tokens_details') or {}).get('cached_tokens'))
    if not all(isinstance(v,int) and not isinstance(v,bool) and v>=0 for v in (p,o)):
        return {'usd':None,'usage_unknown':True}
    def tier(when):
        d=datetime.fromisoformat(when)
        if d.weekday()>=5:return 'off_peak'
        # Current experiment week contains no Chinese public holiday. Outside
        # this frozen week use an explicitly labelled peak upper estimate.
        if not '2026-10-21'<=d.date().isoformat()<='2026-10-31':return 'upper_peak_unknown_holiday'
        hour=d.hour+d.minute/60+d.second/3600
        return 'peak' if 1<=hour<4 or 6<=hour<10 else 'off_peak'
    a,b=tier(started),tier(ended)
    label=a if a==b else 'upper_peak_boundary'
    rates=PRICES['off_peak' if label=='off_peak' else 'peak']
    known_hit=isinstance(hit,int) and not isinstance(hit,bool) and 0<=hit<=p
    amount=((hit*rates['cache_hit']+(p-hit)*rates['cache_miss']) if known_hit else p*rates['cache_miss'])+o*rates['output']
    return dict(usd=amount/1e6,price_tier=label,cache_hits_known=known_hit,
                estimate_or_upper='estimate' if known_hit and not label.startswith('upper') else 'upper',
                source=PRICE_SOURCE,not_provider_invoice=True,usage_unknown=False)


class Transport:
    def __init__(self,run=C.RUN,client=None):
        self.run=Path(run)
        self.key=None if client is not None else credential()
        self.client=client or httpx.Client(base_url=C.API,
            headers={'Authorization':'Bearer '+self.key},trust_env=False,
            follow_redirects=False,timeout=httpx.Timeout(connect=45,read=None,write=45,pool=45))
        self.owned=client is None

    def free_get(self,route,name):
        if route not in ('/models','/user/balance'):raise ValueError('Unapproved API route')
        response=self.client.get(route)
        if response.status_code!=200:raise RuntimeError('Read-only API HTTP '+str(response.status_code))
        value=response.json()
        C.write(self.run/'preflight'/name,dict(utc=C.utc(),response=value))
        return value

    def ask(self,request,turn):
        if request.get('model')!=C.MODEL or request.get('thinking')!={'type':'disabled'}:
            raise ValueError('Require the frozen nonthinking DeepSeek Flash model')
        folder=self.run/'calls'/f'{turn:04d}'
        if folder.exists():raise FileExistsError('No implicit replay of an existing paid turn')
        C.write(folder/'request.json',request)
        for attempt in range(3):
            started=C.utc();began=time.perf_counter()
            C.write(folder/f'attempt_{attempt}_started.json',dict(utc=started,request_sha256=C.digest(request)))
            try:
                response=self.client.post('/chat/completions',json=request)
            except httpx.TransportError as error:
                C.write(folder/f'attempt_{attempt}_receipt.json',dict(started_utc=started,ended_utc=C.utc(),
                    elapsed_seconds=time.perf_counter()-began,status='transport_error',
                    error_type=type(error).__name__,usage=None,billing_unknown=True))
                if attempt==2:raise RuntimeError('Transport failure; billing may be unknown') from None
                time.sleep(2**attempt);continue
            ended=C.utc()
            try:raw=response.json()
            except ValueError:raw={'non_json_response_status':response.status_code}
            if response.status_code!=200:
                # Errors may echo input, but never write an authentication key.
                safe=json.loads(json.dumps(raw).replace(self.key,'[REDACTED]')) if self.key else raw
                C.write(folder/f'attempt_{attempt}_error.json',safe)
                C.write(folder/f'attempt_{attempt}_receipt.json',dict(started_utc=started,ended_utc=ended,
                    elapsed_seconds=time.perf_counter()-began,http_status=response.status_code,
                    usage=None,billing_unknown=response.status_code>=500))
                if response.status_code in (408,429) or response.status_code>=500:
                    if attempt<2:time.sleep(2**attempt);continue
                raise RuntimeError('DeepSeek API HTTP '+str(response.status_code))
            C.write(folder/f'attempt_{attempt}_response.json',raw)
            receipt=dict(started_utc=started,ended_utc=ended,elapsed_seconds=time.perf_counter()-began,
                http_status=200,request_sha256=C.digest(request),response_sha256=C.digest(raw),
                request_id=raw.get('id'),model=raw.get('model'),usage=raw.get('usage'),
                cost=estimated_cost(raw.get('usage'),started,ended),
                system_fingerprint=raw.get('system_fingerprint'))
            C.write(folder/f'attempt_{attempt}_receipt.json',receipt)
            C.write(folder/'result.json',dict(response=raw,receipt=receipt))
            if raw.get('model') not in (C.MODEL,'deepseek-v4.1-flash','DeepSeek-V4.1-Flash-1017'):
                raise RuntimeError('Unexpected API model alias; preserve response')
            if raw['choices'][0]['message'].get('reasoning_content'):
                raise RuntimeError('Unexpected reasoning content with thinking disabled')
            return raw,receipt
        raise AssertionError('unreachable')

    def close(self):
        if self.owned:self.client.close()
