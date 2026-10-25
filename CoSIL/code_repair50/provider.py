"""Nonthinking DeepSeek transport, exact persisted requests, shared5USD ledger."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import time

from .budget import BudgetExceeded, BudgetLedger, timestamp, usage_charge, worst_charge
from .locator import ALIASES, digest, qualification_member
from .prepare import durable, json_bytes

MODEL = "deepseek-flash"
API = "https://api.deepseek.com/chat/completions"
ROOT = Path(__file__).resolve().parents[1]
TOKENIZER = ROOT.parent / "ModelLoc/experiments/deepseek_simple_v1/resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json"
TOKENIZER_SHA = "89085f12ef79460ac5f66d1119325ddfc694b4ab209d80bbd81d35f081dc9614"
MAX_CONTEXT = 1_000_000
MAX_ATTEMPTS = 3


class TransportExhausted(RuntimeError):
    pass


class UnknownBilling(RuntimeError):
    pass


class ResponseContractError(RuntimeError):
    pass


def load_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        path = Path('/home/wdt/.config/graphlocator/deepseek.env')
        if not path.is_file() or path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
            raise RuntimeError("DeepSeek credential file missing or permissions unsuitable")
        for line in path.read_text().splitlines():
            line = line.strip().removeprefix("export ").strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                values = shlex.split(line.split("=",1)[1],comments=True)
                if len(values)==1:key=values[0]
    if not isinstance(key,str) or not key.startswith('sk-') or any(c.isspace() for c in key):
        raise RuntimeError("DeepSeek credential is unavailable")
    return key


class PromptCounter:
    def __init__(self, path=TOKENIZER):
        from tokenizers import Tokenizer
        self.path = Path(path)
        self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        if self.sha256!=TOKENIZER_SHA:raise ValueError('Pinned tokenizer artifact differs')
        self.tokenizer = Tokenizer.from_file(str(self.path))

    def prompt_upper(self, messages):
        if not isinstance(messages,list) or any(set(m)!={'role','content'} or not isinstance(m['content'],str) for m in messages):
            raise ValueError("Text-only role/content messages required")
        content=sum(len(self.tokenizer.encode(m['content'],add_special_tokens=False).ids) for m in messages)
        return content+128*len(messages)+1024

    def budget_prompt_upper(self,messages):
        return max(self.prompt_upper(messages),sum(len(m['content'].encode('utf-8')) for m in messages)+128*len(messages)+1024)


class DeepSeekProvider:
    def __init__(self, ledger: BudgetLedger, out, qualified_manifest, instance_id,
                 pre_reserved=None, *, client=None, api_key_loader=load_api_key, counter=None, sleeper=time.sleep):
        self.manifest = json.loads(Path(qualified_manifest).read_text()) if isinstance(qualified_manifest,(str,Path)) else qualified_manifest
        tasks=self.manifest.get('tasks',[]) if isinstance(self.manifest,dict) else []
        matches=[row for row in tasks if row.get('instance_id')==instance_id]
        if len(matches)!=1:raise ValueError('Task missing from officially frozen roster')
        qualification_member(matches[0],self.manifest)
        if any(row.get('qualification_passed') is not True for row in tasks):
            raise ValueError('Every formal task must explicitly pass official gold/base qualification')
        self.ledger,self.out,self.instance_id=ledger,Path(out),instance_id
        self.out.mkdir(parents=True,exist_ok=True)
        self.pre_reserved=pre_reserved
        self._stage_reservations={}
        self.counter=counter or PromptCounter()
        self._client=client;self._key_loader=api_key_loader;self._sleep=sleeper;self._api_key=None

    def prompt_upper(self,messages):return self.counter.prompt_upper(messages)
    def budget_prompt_upper(self,messages):return self.counter.budget_prompt_upper(messages)

    def _post(self,request):
        import httpx
        if self._client is None:
            self._client=httpx.Client(timeout=httpx.Timeout(1200,connect=30),trust_env=True,follow_redirects=False)
        return self._client.post(API,json=request,headers={'Authorization':'Bearer '+self._api_key,
                                                          'Content-Type':'application/json'})

    def _stage_request(self,messages,stage,max_tokens,json_mode,temperature):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',stage):raise ValueError('Safe fixed stage identity required')
        if type(max_tokens) is not int or not 1<=max_tokens<=393216:raise ValueError('Invalid output limit')
        request={'model':MODEL,'messages':messages,'max_tokens':max_tokens,'thinking':{'type':'disabled'}}
        if json_mode:request['response_format']={'type':'json_object'}
        if temperature is not None:request['temperature']=temperature
        prompt=self.prompt_upper(messages);upper=self.budget_prompt_upper(messages)
        if prompt+max_tokens>MAX_CONTEXT:raise ValueError('Context overflow: no evidence may be silently truncated')
        reqsha=digest(request)
        if stage not in self._stage_reservations:
            self._stage_reservations[stage]=self.pre_reserved
        context={'request':request,'sha256':reqsha,'instance_id':self.instance_id,'stage':stage,
            'provider_scope':str(self.out.resolve()),'initial_reservation_id':self._stage_reservations[stage],
            'prompt_token_upper':prompt,'budget_prompt_upper':upper,
            'tokenizer_sha256':getattr(self.counter,'sha256','synthetic-test-counter')}
        return request,reqsha,prompt,upper,context

    def restore_completed(self,messages,stage,*,max_tokens,json_mode=True,temperature=None):
        """Recover only a fully evidenced local stage; this never sends a request.

        Equal message bytes are insufficient provenance: task, stage, absolute
        provider scope and the arm's original pair reservation must also match.
        Legacy/unbound or copied results stop here rather than buying a rescue.
        """
        request,reqsha,_,_,context=self._stage_request(messages,stage,max_tokens,json_mode,temperature)
        folder=self.out/'calls'/stage
        def read(name):
            path=folder/name
            if not path.is_file() or path.is_symlink():
                raise ValueError('Canonical completed provider evidence is missing or linked')
            return json.loads(path.read_text())
        saved,result=read('request.json'),read('result.json')
        if saved!=context:raise ValueError('Canonical request task/stage/scope/reservation differs')
        final=result.get('receipt',{});number=final.get('attempt')
        if type(number) is not int or not 1<=number<=MAX_ATTEMPTS:
            raise ValueError('Canonical completed attempt identity differs')
        attempts=[];payload=None
        scope=digest(str(self.out.resolve()))[:20]
        for attempt in range(1,number+1):
            sent=read(f'attempt_{attempt}_sent.json');receipt=read(f'attempt_{attempt}_receipt.json')
            expected=(context['initial_reservation_id'] if attempt==1 and context['initial_reservation_id']
                      else f'{self.instance_id}:{scope}:{stage}:{reqsha}:attempt{attempt}')
            if (sent.get('reservation_id')!=expected or sent.get('request_sha256')!=reqsha
                    or receipt.get('reservation_id')!=expected or receipt.get('request_sha256')!=reqsha
                    or receipt.get('attempt')!=attempt):
                raise ValueError('Canonical attempt does not belong to this task/arm/scope')
            row=self.ledger.reservation(expected)
            response_path=folder/f'attempt_{attempt}_response.json'
            payload=read(response_path.name) if response_path.exists() else None
            actual_sha=digest(json.dumps(payload,sort_keys=True)) if payload is not None else None
            if receipt.get('response_sha256')!=actual_sha:
                raise ValueError('Canonical raw HTTP response hash differs')
            charge=usage_charge(payload.get('usage'),payload.get('created')) if isinstance(payload,dict) else None
            if charge is None:
                if row.get('status')!='UNKNOWN_COST' or receipt.get('cost_usd') is not None:
                    raise ValueError('Canonical unknown billing evidence differs')
            elif (row.get('status')!='SETTLED' or row.get('charge_nano_usd')!=charge['nano_usd']
                    or row.get('evidence',{}).get('request_sha256')!=reqsha
                    or row['evidence'].get('response_path')!=str(response_path)
                    or row['evidence'].get('usage_cost')!=charge
                    or receipt.get('usage_cost')!=charge or receipt.get('cost_usd')!=charge['cost_usd']):
                raise ValueError('Canonical result lacks its own settled response/usage evidence')
            attempts.append(receipt)
        last=attempts[-1]
        choices=payload.get('choices') if isinstance(payload,dict) else None
        choice=choices[0] if isinstance(choices,list) and len(choices)==1 and isinstance(choices[0],dict) else {}
        message=choice.get('message')
        if (last.get('http_status')!=200 or not isinstance(message,dict)
                or message.get('reasoning_content') or not isinstance(message.get('content'),str)
                or payload.get('model') not in ALIASES or last.get('thinking_mode')!='disabled'
                or last.get('transport_error_type') is not None or last.get('cost_usd') is None
                or last.get('finish_reason')!=choice.get('finish_reason')
                or last.get('reasoning_content_present') is not False
                or result.get('content')!=message['content'] or result.get('usage')!=payload.get('usage')):
            raise ValueError('Canonical result differs from its normal nonthinking HTTP response')
        seconds=final.get('generation_seconds')
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0:
            raise ValueError('Canonical generation duration unavailable')
        known=sum(x['cost_usd'] for x in attempts if x['cost_usd'] is not None)
        unknown=sum(x['cost_usd'] is None for x in attempts)
        expected_final={**last,'cost_usd':None if unknown else known,'known_attempt_cost_usd':known,
                        'unknown_cost_attempts':unknown,'attempts':attempts,'generation_seconds':seconds}
        if final!=expected_final or set(result)!={'content','usage','receipt'}:
            raise ValueError('Canonical aggregate receipt differs from original attempts')
        return result

    def ask(self,messages,stage,*,max_tokens,json_mode=True,temperature=None):
        request,reqsha,prompt,upper,context=self._stage_request(messages,stage,max_tokens,json_mode,temperature)
        folder=self.out/'calls'/stage
        folder.mkdir(parents=True,exist_ok=True)
        request_path=folder/'request.json';result_path=folder/'result.json'
        if result_path.exists():
            return self.restore_completed(messages,stage,max_tokens=max_tokens,json_mode=json_mode,temperature=temperature)
        durable(request_path,json_bytes(context))
        existing=list(folder.glob('attempt_*_receipt.json'))+list(folder.glob('attempt_*_sent.json'))
        if existing:
            # A process crash after send is not permission to silently send another candidate.
            raise UnknownBilling('Interrupted stage: reconcile existing attempts before any further API request')
        # Resolve credentials before any SENT receipt: a missing local key is not a billable attempt.
        self._api_key=self._key_loader()
        began=time.monotonic();reserved=self.pre_reserved;self.pre_reserved=None;attempt_receipts=[]
        if reserved is not None:self.ledger.assert_sendable(reserved,upper,max_tokens)
        for attempt in range(1,MAX_ATTEMPTS+1):
            scope=digest(str(self.out.resolve()))[:20]
            rid=reserved if attempt==1 and reserved else f'{self.instance_id}:{scope}:{stage}:{reqsha}:attempt{attempt}'
            if not (attempt==1 and reserved):self.ledger.reserve(rid,upper,max_tokens)
            self.ledger.assert_sendable(rid,upper,max_tokens)
            start=timestamp();t0=time.monotonic()
            # The SENT receipt is persisted before sending; crashes retain reservation.
            durable(folder/f'attempt_{attempt}_sent.json',json_bytes({'reservation_id':rid,'request_sha256':reqsha,'sent_at':start}))
            response=None;payload=None;error_type=None
            try:
                response=self._post(request)
                try:payload=response.json()
                except (ValueError,UnicodeError):error_type='INVALID_RESPONSE_JSON'
            except Exception as exc:
                # Never persist exception text: it can contain URLs or authorization data.
                error_type=type(exc).__name__
            status=getattr(response,'status_code',None)
            if payload is not None:
                serialized=json.dumps(payload,ensure_ascii=False)
                if self._api_key in serialized:
                    payload=json.loads(serialized.replace(self._api_key,'[REDACTED_API_KEY]'))
                    error_type='SECRET_REDACTED_FROM_RESPONSE'
                durable(folder/f'attempt_{attempt}_response.json',json_bytes(payload))
            charge=usage_charge(payload.get('usage'),payload.get('created')) if isinstance(payload,dict) else None
            receipt={'reservation_id':rid,'request_sha256':reqsha,'request_model':MODEL,
                'returned_model':payload.get('model') if isinstance(payload,dict) else None,
                'response_created':payload.get('created') if isinstance(payload,dict) else None,
                'thinking_mode':'disabled','started_at':start,'finished_at':timestamp(),
                'http_status':status,'transport_error_type':error_type,'attempt':attempt,
                'duration_seconds':time.monotonic()-t0,'cost_usd':charge['cost_usd'] if charge else None,
                'usage_cost':charge,'response_sha256':digest(json.dumps(payload,sort_keys=True)) if payload is not None else None}
            if charge:
                self.ledger.settle(rid,charge['nano_usd'],{'request_sha256':reqsha,'response_path':str(folder/f'attempt_{attempt}_response.json'),
                                                       'usage_cost':charge})
            else:self.ledger.unknown(rid,'No authoritative valid usage/cache split returned')
            if status==200 and isinstance(payload,dict):
                choices=payload.get('choices')
                valid_choice=(isinstance(choices,list) and len(choices)==1
                              and isinstance(choices[0],dict))
                choice=choices[0] if valid_choice else {}
                raw_message=choice.get('message')
                message=raw_message if isinstance(raw_message,dict) else {}
                receipt.update(finish_reason=choice.get('finish_reason'),reasoning_content_present=bool(message.get('reasoning_content')))
                durable(folder/f'attempt_{attempt}_receipt.json',json_bytes(receipt))
                if charge is None:raise UnknownBilling('Successful response missing billable usage; retained full upper reserve')
                if self.ledger.summary()['bound_violation']:raise BudgetExceeded('Returned usage exceeded reserved bound; stopped')
                if (not valid_choice or not isinstance(raw_message,dict)
                        or message.get('reasoning_content') or not isinstance(message.get('content'),str)
                        or payload.get('model') not in ALIASES or error_type=='SECRET_REDACTED_FROM_RESPONSE'):
                    raise ResponseContractError('Nonthinking text response contract violated; no semantic retry')
                attempt_receipts.append(dict(receipt))
                known=sum(x['cost_usd'] for x in attempt_receipts if x['cost_usd'] is not None)
                unknown=sum(x['cost_usd'] is None for x in attempt_receipts)
                receipt.update(cost_usd=None if unknown else known,known_attempt_cost_usd=known,
                               unknown_cost_attempts=unknown,attempts=attempt_receipts)
                receipt['generation_seconds']=time.monotonic()-began
                result={'content':message['content'],'usage':payload['usage'],'receipt':receipt}
                durable(result_path,json_bytes(result));return result
            durable(folder/f'attempt_{attempt}_receipt.json',json_bytes(receipt))
            attempt_receipts.append(dict(receipt))
            retryable=status is None or status in (408,409,429) or isinstance(status,int) and status>=500
            if not retryable or attempt==MAX_ATTEMPTS:
                raise TransportExhausted('Transport failed; receipts and conservative billing retained')
            self._sleep(min(2**attempt,8))
        raise TransportExhausted('No completed response')
