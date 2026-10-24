"""Resume unchanged history using the provider's remaining output allowance.

No history trimming, new semantic hint, answer retry, or new total budget. Every
HTTP request has a fresh immutable directory, including rejected reservations.
"""
import fcntl
import json
import re
import time
import traceback
from datetime import datetime
from . import common as C
from .runner import verify_repo
from .tools import RepoTools, TOOLS
from .transport import Transport

CONTEXT=1048576


def remaining(error):
    message=(error.get('error') or {}).get('message','')
    match=re.search(r'maximum context length is (\d+).*?\((\d+) in the messages, (\d+) in the completion\)',message)
    if not match:raise RuntimeError('Not a provider context-reservation error')
    limit,prompt,output=map(int,match.groups())
    if limit!=CONTEXT:raise RuntimeError('Unexpected provider context limit')
    return limit-prompt,prompt,output


def next_budget(receipt,new_messages):
    # A conservative byte bound avoids repeatedly reserving output that no
    # longer fits. Provider errors, if any, supply the exact remaining count.
    prompt=receipt['usage']['prompt_tokens']
    added=sum(len(json.dumps(m,ensure_ascii=False).encode()) for m in new_messages)
    return max(1,min(C.MAX_OUTPUT,CONTEXT-prompt-added-4096))


def continue_loop(transport,tools,messages,turn,tool_count,budget):
    new_successes=[]
    while True:
        turn+=1
        C.write(C.RUN/'progress.json',dict(utc=C.utc(),turn=turn,tools_executed=tool_count,
                phase='waiting_for_model',continuation=True,max_tokens=budget),replace=True)
        request=dict(model=C.MODEL,messages=messages,thinking={'type':'disabled'},temperature=0,
                     max_tokens=budget,tools=TOOLS,tool_choice='auto',stream=False)
        try:raw,receipt=transport.ask(request,turn)
        except RuntimeError:
            error=C.read(C.RUN/'calls'/f'{turn:04d}'/'attempt_0_error.json',{})
            allowed,_,previous=remaining(error)
            C.write(C.RUN/'context_adjustments'/f'{turn:04d}.json',dict(utc=C.utc(),
                    allowed_output_tokens=allowed,previous_output_tokens=previous,
                    messages_sha256=C.digest(messages),semantic_input_change=False))
            if allowed<1:raise RuntimeError('Provider input context exhausted; no final localization') from None
            if allowed>=budget:raise RuntimeError('Reservation error did not reduce output allowance') from None
            budget=allowed
            continue
        new_successes.append(receipt)
        choice=raw['choices'][0];message=choice['message'];calls=message.get('tool_calls') or []
        assistant=dict(role='assistant',content=message.get('content'))
        if calls:assistant['tool_calls']=calls
        messages.append(assistant);added=[assistant]
        C.write(C.RUN/'conversation.json',messages,replace=True)
        if not calls:
            if choice.get('finish_reason')=='length':
                continuation=dict(role='user',content="Your previous completion reached the API's single-response maximum. Continue from where it ended without repeating it, and finish the localization when ready.")
                messages.append(continuation);added.append(continuation)
            elif choice.get('finish_reason')=='stop' and message.get('content'):
                return dict(final_response=message['content'],finish_reason='stop',
                            last_http_turn=turn,tool_calls=tool_count,new_receipts=new_successes)
            else:raise RuntimeError('No complete final response; preserve actual provider outcome')
        for position,call in enumerate(calls):
            tool_count+=1;began=time.perf_counter();name=call.get('function',{}).get('name')
            raw_args=call.get('function',{}).get('arguments','')
            try:
                args=json.loads(raw_args);output=tools.execute(name,args)
            except (ValueError,TypeError) as error:
                args=None;output=dict(ok=False,tool=name,arguments=raw_args,data=None,
                    error=dict(code='invalid_arguments',type=type(error).__name__,message='Invalid tool argument JSON'))
            wire=json.dumps(output,ensure_ascii=False)
            C.write(C.RUN/'tools'/f'{tool_count:04d}.json',dict(turn=turn,position=position,
                tool_call_id=call['id'],name=name,arguments=args,raw_arguments=raw_args,output=output,
                output_sha256=C.digest(output),output_utf8_bytes=len(wire.encode()),
                elapsed_seconds=time.perf_counter()-began,wire_content=wire))
            tool_message=dict(role='tool',tool_call_id=call['id'],content=wire)
            messages.append(tool_message);added.append(tool_message)
        C.write(C.RUN/'conversation.json',messages,replace=True)
        budget=next_budget(receipt,added)


def main():
    transport=Transport()
    try:
        with (C.RUN/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (C.RUN/'result.json').exists() or (C.RUN/'continuation.json').exists():
                raise FileExistsError('Never implicitly replay a completed/continued run')
            original=C.read(C.RUN/'calls/0608/request.json')
            available,prompt,_=remaining(C.read(C.RUN/'calls/0608/attempt_0_error.json'))
            if available<1:raise RuntimeError('No remaining provider context')
            tested=C.read(C.RUN/'cpu_tests.json')
            for name,expected in tested['source_sha256'].items():
                if C.sha(name)!=expected:raise RuntimeError('Original executor changed')
            C.write(C.RUN/'repo_before_continuation.json',verify_repo())
            C.write(C.RUN/'continuation.json',dict(utc=C.utc(),resume_after_http_turn=608,
                unchanged_messages_sha256=C.digest(original['messages']),provider_prompt_tokens=prompt,
                initial_remaining_output_tokens=available,history_truncation=False,
                added_semantic_hints=False,thinking='disabled',
                source_sha256={str(p):C.sha(p) for p in sorted((C.ROOT/'code_deepseek_direct').rglob('*.py'))}))
            with RepoTools(C.REPO) as repository_tools:
                end=continue_loop(transport,repository_tools,original['messages'],608,615,available)
            receipts=[C.read(p)['receipt'] for p in sorted((C.RUN/'calls').glob('*/result.json'))]
            first=C.read(C.RUN/'calls/0001/attempt_0_started.json')['utc'];last=C.utc()
            result=dict(status='complete',started_utc=first,ended_utc=last,
                elapsed_seconds=(datetime.fromisoformat(last)-datetime.fromisoformat(first)).total_seconds(),
                model_turns=end['last_http_turn'],successful_model_responses=len(receipts),
                http_requests=end['last_http_turn'],tool_calls=end['tool_calls'],
                model=C.MODEL,thinking='disabled',final_response=end['final_response'],finish_reason='stop',
                usage=[r.get('usage') for r in receipts],estimated_costs=[r.get('cost') for r in receipts],
                reservation_continuation=True)
            C.write(C.RUN/'result.json',result)
            C.write(C.RUN/'progress.json',dict(utc=C.utc(),phase='complete',turn=end['last_http_turn'],
                tools_executed=end['tool_calls']),replace=True)
            print(json.dumps({k:result[k] for k in ('status','model_turns','tool_calls','elapsed_seconds')}))
    except BaseException as error:
        C.write(C.RUN/'continuation_error.json',dict(utc=C.utc(),type=type(error).__name__,
            error=str(error),traceback=traceback.format_exc()),replace=True)
        raise
    finally:
        C.write(C.RUN/'repo_after_continuation.json',verify_repo(),replace=True)
        try:transport.free_get('/user/balance','balance_after_continuation.json')
        except Exception:pass
        transport.close()


if __name__=='__main__':main()
