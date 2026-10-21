"""Explicitly budgeted CPU preparation, paired ablation, audit and interface runs."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from .common import *

def freeze_code():
    paths=[ROOT/'context_tool_diagnostic'/name for name in ['__init__.py','common.py','prepare.py','provider.py','runtime.py','cli.py','ablation.py','protocol.py','structured.py']]
    paths += [ROOT/'src/token_counter.py',ROOT/'src/cosil_adapter.py',ROOT/'src/code_index.py',ROOT/'src/judge.py',ROOT/'scripts/start_qwen.sh']
    paths += [COSIL/p for p in ['code_v3b/fixed_search.py','code_v3b/tool_dispatch.py','code_v3b/AFL_插桩版.py','code_v6_canary_v2/pipeline.py']]
    mapping={str(p):sha(p) for p in paths}
    write(RUN/'online_source_sha256.json',mapping)

def verify_code():
    for path,expected in read(RUN/'online_source_sha256.json').items():
        if sha(path)!=expected:raise RuntimeError('Frozen online code drift '+path)

def prepare_all():
    from .prepare import prepare
    prepare()
    from .ablation import prepare as freeze,build_messages
    from src.token_counter import prompt_upper
    lines=[];estimates=[]
    for rec in records():
        job=read(rec['job']);frozen=freeze(job,RUN/'frozen'/job['instance_id'])
        lines.append(json.dumps(frozen['manifest'],ensure_ascii=False))
        plans=build_messages(job,frozen)
        assert plans['A-SIGNATURE']['candidate_id_order']==plans['A-FULL']['candidate_id_order']
        assert plans['A-SIGNATURE']['common_prefix_sha256']==plans['A-FULL']['common_prefix_sha256']
        for arm,plan in plans.items():
            upper=prompt_upper(plan['messages'])
            byte_upper=len(json.dumps(plan['messages'],ensure_ascii=False).encode())+128*len(plan['messages'])+1024
            entry={k:v for k,v in plan.items() if k not in ('messages','candidate_id_order')}
            entry.update(instance_id=job['instance_id'],method=arm,input_token_upper=upper,input_byte_upper=byte_upper,
                maximum_output_tokens=4096,peak_token_estimated_max_usd=(upper*.3+4096*1.2)/1e6,
                peak_byte_reserved_max_usd=(byte_upper*.3+4096*1.2)/1e6)
            write(RUN/'frozen'/job['instance_id']/(arm+'_prompt_plan.json'),entry)
            estimates.append(entry)
    dest=RUN/'frozen_context_manifest.jsonl';text='\n'.join(lines)+'\n'
    if dest.exists() and dest.read_text()!=text:raise RuntimeError('Frozen context manifest drift')
    if not dest.exists():dest.write_text(text)
    write(RUN/'ablation_request_estimates.json',estimates)
    print(json.dumps({'allocated_calls':100,'eligible_calls':sum(e['status']=='ready' for e in estimates),
         'max_token_peak_usd':sum(e['peak_token_estimated_max_usd'] for e in estimates if e['status']=='ready'),
         'max_byte_peak_usd':sum(e['peak_byte_reserved_max_usd'] for e in estimates if e['status']=='ready'),
         'overflow':[e['instance_id'] for e in estimates if e['status']=='context_overflow'],'budget_usd':3.},ensure_ascii=False))

def tests():
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='')
    proc=subprocess.run([str(COSIL/'.venv-v5/bin/python'),'-m','unittest','discover','-s','context_tool_diagnostic','-p','test_*.py','-t','.','-v'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    print(proc.stdout)
    write(RUN/'cpu_tests.json',{'passed':proc.returncode==0,'time':utc(),'output':proc.stdout},replace=True)
    if proc.returncode:raise RuntimeError('CPU tests failed')

def online_preflight():
    if not read(RUN/'cpu_tests.json')['passed']:raise RuntimeError('CPU tests required')
    if not (RUN/'online_source_sha256.json').exists():freeze_code()
    verify_code()
    if not (RUN/'api_readonly_preflight.json').exists():
        from .provider import free_get
        models=free_get('models');balance=free_get('user/balance')
        if not any(d['id']=='deepseek-flash' for d in models['data']):raise RuntimeError('Frozen DeepSeek model unavailable')
        write(RUN/'api_readonly_preflight.json',{'time':utc(),'models':models,'balance':balance,'price_source':'https://api-docs.deepseek.com/quick_start/pricing/','price_verified_date':'2026-10-21'})

def run_phase(phase,scope,execute):
    if phase=='adapter':raise RuntimeError('B1 STOPPED: strict DSL/prose historical compatibility confounds parser-only comparison')
    if phase=='ablation':
        ids=selected(scope);variants=['A-SIGNATURE','A-FULL']
        tasks=[]
        for rec in records():
            if rec['instance_id'] not in ids:continue
            order=variants if int(digest(rec['instance_id'])[-1],16)%2==0 else variants[::-1]
            for variant in order:tasks.append({'job':rec['job'],'variant':variant})
    else:
        ids=selected('smoke' if scope=='smoke' else 'b2');tasks=[]
        for method in ['D-COSIL','Q-COSIL','Q-PRUNER']:
            for rec in records():
                if rec['instance_id'] in ids:tasks.append({'job':rec['job'],'variant':method+'-STRUCTURED','base_method':method})
    done=lambda t:(RUN/'lite_pilot'/t['variant']/read(t['job'])['instance_id']/'result.json').exists()
    tasks=[t for t in tasks if not done(t)]
    print(json.dumps({'phase':phase,'scope':scope,'new_allocated':len(tasks),'execute':execute,'budget_usd':3.}))
    if not execute or not tasks:return
    online_preflight()
    from .runtime import sandbox_batch,wait_batches,start_qwen,stop_owned
    if scope!='smoke' and not read(RUN/(phase+'_smoke_gate.json'))['passed']:raise RuntimeError('Smoke engineering gate required')
    owned=None
    try:
        if phase=='ablation':wait_batches([sandbox_batch(tasks,phase+'_'+scope)])
        else:
            # Never reselect the upstream files; each base method owns its start.
            owned=start_qwen()
            groups=[[t for t in tasks if t['base_method']==method] for method in ['D-COSIL','Q-COSIL','Q-PRUNER']]
            wait_batches([sandbox_batch(group,phase+'_'+scope+'_'+str(i)) for i,group in enumerate(groups) if group])
    finally:stop_owned(owned)
    verify_code()
    if scope=='smoke':
        results=[read(RUN/'lite_pilot'/t['variant']/read(t['job'])['instance_id']/'result.json') for t in tasks]
        accepted={'complete','parse_error','context_overflow','upstream_failure','budget_exceeded'}
        # Model contract failures are genuine outcomes; unexpected engineering errors stop the expansion.
        passed=all(r['status'] in accepted or (r.get('error_type')=='ValueError' and 'semantic' in r.get('error_message','').lower()) for r in results)
        write(RUN/(phase+'_smoke_gate.json'),{'passed':passed,'time':utc(),'results':[{k:r.get(k) for k in ['instance_id','method','status','error_type','error_message']} for r in results]},replace=True)
        if not passed:raise RuntimeError('Smoke engineering failed; preserve calls before repair')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',choices=['lite_pilot'],default='lite_pilot')
    parser.add_argument('--phase',choices=['prepare','tests','audit','ablation','adapter','structured','verify','report'],required=True)
    group=parser.add_mutually_exclusive_group();group.add_argument('--smoke',action='store_true');group.add_argument('--full',action='store_true')
    parser.add_argument('--execute',action='store_true',help='Explicit authorization for paid/model requests; otherwise dry run')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if args.execute and args.dry_run:parser.error('Choose dry run or execute')
    if args.phase=='prepare':prepare_all()
    elif args.phase=='tests':tests()
    elif args.phase=='verify':
        verify_code()
        for path,expected in read(RUN/'history_preservation_sha256.json').items():
            if sha(path)!=expected:raise RuntimeError('Historical file drift '+path)
        print('Frozen code and authorized historical files unchanged; no sealed test opened.')
    elif args.phase=='audit':
        from .audit import audit
        result=read(RUN/'audit/summary.json') if (RUN/'audit/summary.json').exists() else audit(OLD,ROOT/'manifests/lite_pilot.json',ROOT/'reports/lite_pilot_tool_io_per_call.csv',RUN/'audit')
        print(json.dumps(result,ensure_ascii=False))
    elif args.phase=='report':
        from .evaluate import main as report_main
        report_main()
    else:run_phase(args.phase,'smoke' if args.smoke else 'full',args.execute)

if __name__=='__main__':main()
