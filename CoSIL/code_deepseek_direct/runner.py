"""One neutral issue+repository conversation, native tools, model-chosen finish."""
import argparse
import fcntl
import json
import time
import traceback
from . import common as C
from .transport import Transport,PRICES,PRICE_SOURCE

SYSTEM='''You are a software issue localization agent. You are given an issue and read-only access to its base repository. Identify the source files and existing functions responsible for the issue. Choose your own repository browsing steps and decide when you have sufficient evidence. Use the available tools directly; there is no preselected file menu or separate relevance judge. Do not modify files, generate a patch, or access the internet. Cite only repository evidence you actually inspected; label uncertainties. You may give concise factual progress notes, but do not provide private internal reasoning. When finished, return a JSON object with: files (ranked objects with path and evidence), functions (ranked objects with path, qualified_name, start_line, end_line, evidence), summary, and uncertainties. List as many candidates as the evidence justifies, strongest first. A class alone is not an existing function; list an exact method if that is your function candidate.'''


def initial_messages(job):
    if set(job)!={'instance_id','repo','base_commit','problem_statement'}:
        raise ValueError('Only the four clean issue/base metadata fields are permitted')
    return [{'role':'system','content':SYSTEM},
            {'role':'user','content':f"Repository: {job['repo']}\nBase commit: {job['base_commit']}\nRepository root through tools: .\n\nIssue:\n{job['problem_statement']}"}]


def protocol():
    return dict(run_id='20261024_deepseek_direct_astropy12907_v1',instance_id=C.IID,
        model=C.MODEL,documented_version='DeepSeek-V4.1-Flash-1017',thinking='disabled',
        temperature=0,max_tokens=C.MAX_OUTPUT,provider_context_documented='1M',
        cumulative_tokens_cap=None,wall_time_cap=None,turn_cap=None,cost_cap_usd=None,
        transport_attempts_max=3,semantic_retries=0,
        single_response_limit='Official platform maximum 393216; no experimental total-token cap',
        method='Native-tool autonomous issue+full-base-repository localization',
        prechange_checkpoint=C.CHECKPOINT,price_source=PRICE_SOURCE,prices=PRICES,
        repository_payload='full base tracked tree, no .git/history/gold/old predictions',
        initial_inputs='issue text and repo/base identity only; no upstream localization results')


def verify_repo():
    receipt=C.read(C.RUN/'inputs/input_receipt.json')
    expected={m['path']:m for m in receipt['members']}
    actual={p.relative_to(C.REPO).as_posix():p for p in C.REPO.rglob('*') if not p.is_dir()}
    if set(actual)!=set(expected):raise RuntimeError('Base repository file list changed')
    for name,path in actual.items():
        if path.is_symlink() or '.git' in path.parts or C.sha(path)!=expected[name]['sha256']:
            raise RuntimeError('Base repository content changed')
    return dict(passed=True,utc=C.utc(),files=len(actual),base_commit=receipt['base_commit'],
                base_tree=receipt['base_tree'],manifest_sha256=C.sha(C.RUN/'inputs/input_receipt.json'))


def run_loop(job,tools,transport,*,schemas):
    messages=initial_messages(job);turn=0;tool_count=0;receipts=[]
    C.write(C.RUN/'initial_messages.json',messages)
    C.write(C.RUN/'resolved_config.json',protocol())
    C.write(C.RUN/'tool_schemas.json',schemas)
    began=time.perf_counter();started=C.utc()
    while True:
        turn+=1
        request=dict(model=C.MODEL,messages=messages,thinking={'type':'disabled'},
                     temperature=0,max_tokens=C.MAX_OUTPUT,tools=schemas,tool_choice='auto',stream=False)
        C.write(C.RUN/'progress.json',dict(utc=C.utc(),turn=turn,tools_executed=tool_count,
                                        phase='waiting_for_model'),replace=True)
        raw,receipt=transport.ask(request,turn);receipts.append(receipt)
        choice=raw['choices'][0];message=choice['message']
        calls=message.get('tool_calls') or []
        assistant={'role':'assistant','content':message.get('content')}
        if calls:assistant['tool_calls']=calls
        messages.append(assistant)
        C.write(C.RUN/'conversation.json',messages,replace=True)
        if not calls:
            if choice.get('finish_reason')=='length':
                messages.append({'role':'user','content':"Your previous completion reached the API's single-response maximum. Continue from where it ended without repeating it, and finish the localization when ready."})
                continue
            if choice.get('finish_reason')!='stop' or not message.get('content'):
                raise RuntimeError('No complete final response; preserve the actual provider outcome')
            result=dict(status='complete',started_utc=started,ended_utc=C.utc(),
                elapsed_seconds=time.perf_counter()-began,model_turns=turn,tool_calls=tool_count,
                model=C.MODEL,thinking='disabled',final_response=message['content'],
                usage=[r.get('usage') for r in receipts],estimated_costs=[r.get('cost') for r in receipts],
                finish_reason=choice['finish_reason'])
            C.write(C.RUN/'result.json',result)
            C.write(C.RUN/'progress.json',dict(utc=C.utc(),phase='complete',turn=turn,
                                            tools_executed=tool_count),replace=True)
            return result
        for position,call in enumerate(calls):
            tool_count+=1;name=call.get('function',{}).get('name')
            raw_args=call.get('function',{}).get('arguments','')
            tool_started=time.perf_counter()
            try:
                args=json.loads(raw_args)
                output=tools.execute(name,args)
            except (ValueError,TypeError) as error:
                args=None;output=dict(ok=False,tool=name,arguments=raw_args,
                    data=None,error=dict(code='invalid_arguments',type=type(error).__name__,
                                        message='Invalid tool argument JSON'))
            wire=json.dumps(output,ensure_ascii=False)
            record=dict(turn=turn,position=position,tool_call_id=call['id'],name=name,
                arguments=args,raw_arguments=raw_args,output=output,
                output_sha256=C.digest(output),output_utf8_bytes=len(wire.encode()),
                elapsed_seconds=time.perf_counter()-tool_started,
                wire_content=wire)
            C.write(C.RUN/'tools'/f'{tool_count:04d}.json',record)
            messages.append({'role':'tool','tool_call_id':call['id'],'content':wire})
        C.write(C.RUN/'conversation.json',messages,replace=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.preflight==args.execute:raise ValueError('Choose exactly --preflight or --execute')
    transport=Transport()
    try:
        if args.preflight:
            models=transport.free_get('/models','models.json')
            assert C.MODEL in {m['id'] for m in models['data']}
            transport.free_get('/user/balance','balance_before.json')
            print(json.dumps(dict(passed=True,model_available=C.MODEL,paid_model_calls=0)))
            return
        from .tools import RepoTools,TOOLS
        C.RUN.mkdir(parents=True,exist_ok=True)
        with (C.RUN/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (C.RUN/'result.json').exists() or (C.RUN/'calls').exists():
                raise FileExistsError('This paid run already has artifacts; never replay silently')
            tested=C.read(C.RUN/'cpu_tests.json',{})
            if not tested.get('passed'):raise RuntimeError('Passing CPU tests required')
            for name,expected in tested['source_sha256'].items():
                if C.sha(name)!=expected:raise RuntimeError('Code changed after tests')
            job=C.read(C.JOB)
            if job['instance_id']!=C.IID:raise ValueError('Different issue')
            if C.sha(C.JOB)!=C.sha(C.RUN/'inputs/job.json'):
                raise RuntimeError('Clean input job changed')
            C.write(C.RUN/'repo_before.json',verify_repo())
            with RepoTools(C.REPO) as repository_tools:
                result=run_loop(job,repository_tools,transport,schemas=TOOLS)
            C.write(C.RUN/'repo_after.json',verify_repo())
            try:transport.free_get('/user/balance','balance_after.json')
            except Exception:C.write(C.RUN/'balance_after_unavailable.json',{'utc':C.utc()})
            print(json.dumps({k:result[k] for k in ('status','model_turns','tool_calls','elapsed_seconds')}))
    except BaseException as error:
        C.write(C.RUN/'error.json',dict(utc=C.utc(),type=type(error).__name__,
                error=str(error),traceback=traceback.format_exc()),replace=True)
        raise
    finally:transport.close()


if __name__=='__main__':main()
