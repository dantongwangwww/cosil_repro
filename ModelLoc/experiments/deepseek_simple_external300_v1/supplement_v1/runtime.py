"""Independent USD5, zero-GPU additional200 controller; execution is opt-in."""
import argparse
import collections
import copy
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from . import common as C

CONFIG=C.ROOT/'configs/resolved_config.json'
FREEZE=C.RUN/'online_freeze.json'
PYTHON=C.COSIL/'.venv-v5/bin/python'
SOURCE_NAMES=['__init__.py','common.py','code_index.py','simple_pipeline.py','providers.py','execution.py','token_counter.py']
CONTROLLER_NAMES=['__init__.py','common.py','bootstrap.py','runtime.py','worker.py']
PROMPTS=['file_selection','query_planning','function_localization']
TOKENIZER_REL='resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json'


def once(path,obj):
    existing=C.load(path)
    if existing is not None:
        if existing!=obj:raise RuntimeError('Immutable freeze drift: '+str(path))
    else:C.write(path,obj)


def config_guard(config):
    if config['methods']!=['D-SIMPLE'] or config['run_id']!=C.RUN_ID or config['cohort']!=C.COHORT:raise PermissionError('Method/run/cohort mismatch')
    if config['budget_usd']!=C.BUDGET_USD or config['api_concurrency']!=4 or config['transport_retries']!=3 or config['semantic_retries']!=0:raise PermissionError('Budget/concurrency/retry mismatch')
    if config['deepseek']['thinking']!='disabled' or config['deepseek'].get('reasoning_effort') is not None or config['deepseek']['model']!='deepseek-flash':raise PermissionError('Frozen non-thinking model mismatch')
    if config['budget']['per_case_soft_cny']!=.5 or config['budget']['per_case_hard_cny']!=1.5 or config['budget']['cumulative_tokens_per_case']!=400000:raise PermissionError('Per-issue limits changed')
    if config.get('gpu_used') is not False or 'pruner' in config or 'qwen' in config:raise PermissionError('This extension has no GPU methods')


def install_assets():
    previous=C.load(C.PREVIOUS/'configs/resolved_config.json')
    expected=previous['source_sha256'];checks={}
    paths=[C.FROZEN/'src'/n for n in SOURCE_NAMES]
    paths += [C.FROZEN/'prompts'/(n+'.txt') for n in PROMPTS]+[C.FROZEN/TOKENIZER_REL]
    for path in paths:
        actual=C.sha(path)
        if expected.get(str(path))!=actual:raise RuntimeError('P1/previous100 source compatibility failed: '+str(path))
        checks[str(path)]=actual
    copies=[(C.FROZEN/'prompts'/(n+'.txt'),C.ROOT/'prompts'/(n+'.txt')) for n in PROMPTS]
    copies.append((C.FROZEN/TOKENIZER_REL,C.ROOT/TOKENIZER_REL))
    # Copy the exact o200k encoding cache, so a hidden /tmp cannot cause a download.
    url='https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken'
    key=hashlib.sha1(url.encode()).hexdigest()
    cache_candidates=[C.FROZEN/'runs/20261021_nonthinking_v3/shared_cache/tiktoken'/key,C.FROZEN/'runs/20261021_context_tool_diagnostic/shared_cache/tiktoken'/key,
        C.PREVIOUS/'runs/20261021_external_nonthinking_v1/shared_cache/tiktoken'/key,Path('/tmp/data-gym-cache')/key]
    cache=next((p for p in cache_candidates if p.is_file()),None)
    if cache is None:raise RuntimeError('Existing offline o200k cache is required; no online tokenizer fallback')
    copies.append((cache,C.ROOT/'resources/offline_tiktoken'/key))
    for source,dest in copies:
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            if C.sha(dest)!=C.sha(source):raise RuntimeError('Copied asset drift: '+str(dest))
        else:shutil.copyfile(source,dest)
        checks[str(dest)]=C.sha(dest)
    config={k:copy.deepcopy(previous[k]) for k in ['deepseek','price_snapshot','simple','api_concurrency','transport_retries','semantic_retries']}
    config.update(run_id=C.RUN_ID,cohort=C.COHORT,root=str(C.ROOT),methods=['D-SIMPLE'],budget_usd=C.BUDGET_USD,gpu_used=False,
        budget={'per_case_soft_cny':.5,'per_case_hard_cny':1.5,'fx':7,'cumulative_tokens_per_case':400000,
                'reservation':'Original UTF8-byte peak upper; official offline tokenizer token cap; unknown billing remains reserved'},
        tokenizer={'path':str(C.ROOT/TOKENIZER_REL),'sha256':C.sha(C.ROOT/TOKENIZER_REL),'o200k_cache_path':str(copies[-1][1])},
        pre_change_github_commit=C.PRE_CHANGE_GITHUB_COMMIT,baseline_source='Frozen P1 D-SIMPLE + previous100 exact compatibility',
        scope='Only additional200 localization; previous100 reused without requests; no repair/test/train/GPU')
    config_guard(config);once(CONFIG,config)
    once(C.RUN/'baseline_asset_compatibility.json',{'sha256':checks,'all_exact':True,'sealed_inputs_read_or_stat':False})
    return config,checks


def manifests():
    additional=C.load(C.ROOT/'manifests/additional200.json');combined=C.load(C.ROOT/'manifests/combined300.json')
    if not additional or not combined:raise RuntimeError('Additional200 and combined300 must be fully prepared')
    new=additional['records'];allrows=combined['records']
    if additional['n']!=200 or len(new)!=200 or combined['n']!=300 or len(allrows)!=300:raise RuntimeError('Expected exact prepared200 + combined300')
    if len({r['instance_id'] for r in new})!=200 or len({r['instance_id'] for r in allrows})!=300:raise RuntimeError('Issue IDs must be unique')
    old=[r for r in allrows if r['origin']=='previous100'];extended=[r for r in allrows if r['origin']=='additional200']
    if len(old)!=100 or {r['instance_id'] for r in extended}!={r['instance_id'] for r in new}:raise RuntimeError('Origin allocation mismatch')
    return new,old


def history_inventory(old):
    previous=C.load(C.PREVIOUS/'configs/resolved_config.json');run=C.PREVIOUS/'runs'/previous['run_id']/'external/D-SIMPLE'
    inventory={str(C.PREVIOUS/'configs/resolved_config.json'):C.sha(C.PREVIOUS/'configs/resolved_config.json')}
    for row in old:
        directory=run/row['instance_id']
        if not (directory/'result.json').is_file():raise RuntimeError('Previous100 D-SIMPLE result missing')
        for name in ['result.json','started.json','stdout.log','inventory.json','file_selection.json','context.json']:
            path=directory/name
            if path.is_file():inventory[str(path)]=C.sha(path)
        for path in (directory/'calls').glob('*/*.json'):inventory[str(path)]=C.sha(path)
    return inventory


def freeze():
    config,assets=install_assets();new,old=manifests();data={};snapshots={};qualifications={}
    forbidden={'gold','patch','test_patch','FAIL_TO_PASS','PASS_TO_PASS','hints_text'}
    for row in new:
        job=C.load(row['job'])
        if job is None or job['cohort']!=C.COHORT or forbidden.intersection(job):raise RuntimeError('Unsafe/missing additional job')
        if any(job[k]!=row[k] for k in ['instance_id','repo','base_commit']):raise RuntimeError('Manifest/job identity mismatch')
        if not Path(row['job']).resolve().is_relative_to((C.ROOT/'jobs').resolve()):raise RuntimeError('Job escaped new ROOT')
        root=Path(job['snapshot']).resolve();allowed=(C.ROOT/'snapshots').resolve()
        if not root.is_relative_to(allowed):raise RuntimeError('Snapshot escaped selected clean snapshots')
        receipt_path=C.ROOT/'evaluator_private/preparation/qualification'/(row['instance_id']+'.json')
        qualification=C.load(receipt_path)
        if not qualification or qualification.get('qualified') is not True:raise RuntimeError('Missing successful qualification receipt')
        qualifications[str(receipt_path)]=C.sha(receipt_path)
        paths=qualification['snapshot_python_sha256']
        if not {p for p in job['paths'] if p.endswith('.py')}.issubset(paths):raise RuntimeError('Job path missing from base snapshot receipt')
        for rel,expected in paths.items():
            path=root/rel
            if not path.resolve().is_relative_to(root) or not rel.endswith('.py'):raise RuntimeError('Snapshot receipt escaped base Python source')
            if C.sha(path)!=expected:raise RuntimeError('Qualified base snapshot drift: '+rel)
            snapshots[str(Path(job['snapshot'])/rel)]=expected
        for path in [row['job'],job['code_index'],job['structure']]:data[str(path)]=C.sha(path)
    online={str(C.FROZEN/'src'/n):C.sha(C.FROZEN/'src'/n) for n in SOURCE_NAMES}
    online.update({str(C.ROOT/'supplement_v1'/n):C.sha(C.ROOT/'supplement_v1'/n) for n in CONTROLLER_NAMES})
    online.update({p:h for p,h in assets.items() if Path(p).is_relative_to(C.ROOT)})
    online[str(CONFIG)]=C.sha(CONFIG)
    manifest_hashes={str(C.ROOT/'manifests'/n):C.sha(C.ROOT/'manifests'/n) for n in ['additional200.json','combined300.json']}
    payload={'run_id':C.RUN_ID,'cohort':C.COHORT,'config':config,'online_sha256':online,'data_sha256':data,'snapshot_sha256':snapshots,
        'qualification_receipt_sha256':qualifications,'manifest_sha256':manifest_hashes,'history_sha256':history_inventory(old),
        'records':new,'smoke_ids':[r['instance_id'] for r in new[:5]],'allocated_new':200,'previous_reused':100,
        'methods':['D-SIMPLE'],'budget_usd':C.BUDGET_USD,'max_api_workers':4,'gpu_used':False}
    once(FREEZE,payload)
    C.RUN.mkdir(parents=True,exist_ok=True)
    with (C.RUN/'budget.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);ledger=C.load(C.RUN/'budget.json')
        if ledger is None:C.write(C.RUN/'budget.json',{'stage_cap_usd':C.BUDGET_USD,'cases':{},'attempts':{},'created_at':C.utc(),'scope':'additional200 only'})
        elif ledger.get('stage_cap_usd')!=C.BUDGET_USD:raise RuntimeError('Existing independent budget is not USD5')
    return verify()


def verify():
    frozen=C.load(FREEZE)
    if frozen is None:raise RuntimeError('Run freeze is missing')
    config_guard(frozen['config'])
    if frozen['run_id']!=C.RUN_ID or frozen['cohort']!=C.COHORT:raise RuntimeError('Freeze namespace changed')
    for field in ['online_sha256','data_sha256','snapshot_sha256','qualification_receipt_sha256','manifest_sha256','history_sha256']:
        for path,expected in frozen[field].items():
            if C.sha(path)!=expected:raise RuntimeError('Frozen '+field+' drift: '+path)
    ledger=C.load(C.RUN/'budget.json')
    if not ledger or ledger.get('stage_cap_usd')!=C.BUDGET_USD:raise RuntimeError('Independent USD5 budget must exist')
    if sum(v['charged_upper_usd'] for v in ledger['attempts'].values())>C.BUDGET_USD+1e-10:raise RuntimeError('Independent budget exceeded')
    return frozen


def tasks_for_scope(frozen,scope):
    selected=set(frozen['smoke_ids']) if scope=='smoke' else {r['instance_id'] for r in frozen['records']}
    return [r for r in frozen['records'] if r['instance_id'] in selected and not (C.RUN/C.COHORT/'D-SIMPLE'/r['instance_id']/'result.json').exists()]


def make_batch(frozen,rows,scope,index):
    tasks=[]
    for row in rows:
        job=C.load(row['job']);prefix=str(Path(job['snapshot']))+'/'
        tasks.append({'job':row['job'],'instance_id':row['instance_id'],'enqueued_utc':C.utc(),
            'data_sha256':{p:frozen['data_sha256'][p] for p in [row['job'],job['code_index'],job['structure']]},
            'snapshot_sha256':{p:h for p,h in frozen['snapshot_sha256'].items() if p.startswith(prefix)}})
    return {'run_id':C.RUN_ID,'cohort':C.COHORT,'methods':['D-SIMPLE'],'budget_usd':C.BUDGET_USD,'config':frozen['config'],
            'online_sha256':frozen['online_sha256'],'tasks':tasks,'scope':scope,'worker_index':index}


def sandbox_argv(batch_file,batch,probe=False):
    # Nothing under the experiment parent is inherited. Mount only this code,
    # immutable prompts/tokenizers and this batch's clean selected base sources.
    argv=['bwrap','--die-with-parent','--new-session','--unshare-pid','--ro-bind','/','/',
        '--proc','/proc','--dev-bind','/dev','/dev','--tmpfs','/tmp','--tmpfs',str(C.COSIL.parent),
        '--tmpfs',str(Path('/home/wdt/models').resolve()),'--dir',str(C.ROOT)]
    for source in [C.ROOT/'supplement_v1',C.FROZEN/'src',C.ROOT/'prompts',C.ROOT/'resources/deepseek_v4_tokenizer',C.ROOT/'resources/offline_tiktoken',C.COSIL/'.venv-v5']:
        argv+=['--ro-bind',str(source),str(source)]
    for name in ['evaluator_private','manifests','reports','configs','jobs','snapshots','runs']:
        argv+=['--dir',str(C.ROOT/name)]
    argv+=['--bind',str(C.RUN),str(C.RUN)]
    seen=set()
    for task in batch['tasks']:
        job=C.load(task['job'])
        job_logical=Path(task['job']).parent
        job_actual=job_logical.resolve()
        sources=[(job_actual,job_logical),(job_actual,job_actual)]
        logical=C.ROOT/'snapshots'/job['instance_id'];actual=Path(job['snapshot']).resolve()
        sources.extend([(actual,logical),(actual,actual)])
        for source,dest in sources:
            if str(dest) not in seen:argv+=['--ro-bind',str(source),str(dest)];seen.add(str(dest))
    argv+=['--chdir',str(C.ROOT),'--',str(PYTHON),'-m','supplement_v1.worker',str(batch_file)]
    argv+=['--probe'] if probe else ['--execute']
    return argv


def worker_env():
    return dict(os.environ,PYTHONPATH=str(C.ROOT),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',
        OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',TIKTOKEN_CACHE_DIR=str(C.ROOT/'resources/offline_tiktoken'))


def probe():
    frozen=verify();rows=frozen['records'][:5];batch=make_batch(frozen,rows,'probe',0)
    path=C.RUN/'batches/isolation_probe.json';C.write(path,batch)
    proc=subprocess.run(sandbox_argv(path,batch,probe=True),env=worker_env(),stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
    receipt={'time':C.utc(),'passed':proc.returncode==0,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,
             'paid_requests':0,'model_forwards':0,'selected_jobs':len(rows)}
    C.write(C.RUN/'isolation_probe.json',receipt)
    if proc.returncode:raise RuntimeError('Isolation probe failed: '+proc.stderr[-1500:])
    return receipt


def coordinate(scope,execute=False):
    if not execute:raise PermissionError('Coordinator requires explicit --execute')
    C.RUN.mkdir(parents=True,exist_ok=True)
    with (C.RUN/'coordinator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        frozen=verify()
        if not C.load(C.RUN/'isolation_probe.json',{}).get('passed'):raise RuntimeError('Isolation probe must pass')
        if not C.load(C.RUN/'cpu_tests.json',{}).get('passed'):raise RuntimeError('CPU synthetic tests must pass')
        if scope=='full' and not C.load(C.RUN/'smoke_engineering_gate.json',{}).get('passed'):raise RuntimeError('Fixed first5 smoke gate must pass')
        if any((C.RUN/p).exists() for p in ['emergency_stop.json','budget_stop.json','resource_pause.json']):raise RuntimeError('Run has a durable stop/pause marker')
        pending=tasks_for_scope(frozen,scope);groups=[pending[i::4] for i in range(4)];children=[]
        try:
            for index,rows in enumerate(groups):
                if not rows:continue
                batch=make_batch(frozen,rows,scope,index);path=C.RUN/'batches'/(scope+'_'+str(index)+'.json');C.write(path,batch)
                log=path.with_suffix('.log').open('a')
                child=subprocess.Popen(sandbox_argv(path,batch),env=worker_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                log.close();children.append(child)
            C.write(C.RUN/(scope+'_workers.json'),{'time':C.utc(),'coordinator_pid':os.getpid(),'worker_pids':[p.pid for p in children],'pending':len(pending),'gpu_used':False})
            while any(p.poll() is None for p in children):
                if any(p.poll() is not None and p.returncode for p in children):
                    from .bootstrap import stop
                    stop('isolated_worker_exit',reason_detail='A worker failed; stop new reservations while in-flight receipts settle')
                time.sleep(3)
            if any(p.returncode for p in children):raise RuntimeError('Isolated worker exited unsuccessfully; preserve all receipts')
            verify()
            statuses=collections.Counter();smoke=[]
            for row in frozen['records']:
                result=C.load(C.RUN/C.COHORT/'D-SIMPLE'/row['instance_id']/'result.json')
                statuses[result['status'] if result else 'NOT_RUN']+=1
                if row['instance_id'] in frozen['smoke_ids']:smoke.append(result)
            if scope=='smoke':
                ok=len(smoke)==5 and all(r and r['status'] in ('complete','parse_error','budget_exceeded') for r in smoke) and not (C.RUN/'emergency_stop.json').exists()
                C.write(C.RUN/'smoke_engineering_gate.json',{'passed':ok,'time':C.utc(),'fixed_smoke_ids':frozen['smoke_ids'],
                    'statuses':[r['status'] if r else 'NOT_RUN' for r in smoke],'accuracy_threshold_used':False})
            C.write(C.RUN/(scope+'_complete.json'),{'time':C.utc(),'phase_finished':True,'allocated_new':200,'previous_reused':100,
                'statuses':dict(statuses),'history_hashes_verified':True,'source_and_input_hashes_verified':True,'gpu_used':False})
        except Exception as error:
            from .bootstrap import stop
            stop('coordinator_failure',error_type=type(error).__name__,error_message=str(error)[:500]);raise


def launch(scope,execute=False):
    frozen=verify();pending=tasks_for_scope(frozen,scope)
    if not execute:return {'dry_run':True,'scope':scope,'pending':len(pending),'maximum_semantic_requests':len(pending)*7,'gpu_used':False,'budget_usd':C.BUDGET_USD}
    logpath=C.RUN/(scope+'_launcher.log');log=logpath.open('a')
    child=subprocess.Popen([str(PYTHON),'-m','supplement_v1.runtime','--phase','coordinate','--scope',scope,'--execute'],
        cwd=C.ROOT,env=worker_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    log.close();record={'time':C.utc(),'pid':child.pid,'new_session':True,'scope':scope,'log':str(logpath),'pending':len(pending)}
    C.write(C.RUN/(scope+'_launcher.json'),record);return record


def cpu_tests():
    command=[str(PYTHON),'-m','unittest','discover','-s','tests','-p','test_runtime.py','-t','.','-v']
    proc=subprocess.run(command,cwd=C.ROOT,env=worker_env(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    receipt={'passed':proc.returncode==0,'time':C.utc(),'returncode':proc.returncode,'output':proc.stdout}
    C.write(C.RUN/'cpu_tests.json',receipt)
    if proc.returncode:raise RuntimeError('CPU runtime tests failed: '+proc.stdout[-3000:])
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',required=True,choices=['assets','freeze','verify','probe','tests','run','coordinate'])
    p.add_argument('--scope',choices=['smoke','full'],default='smoke');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.phase=='assets':result=install_assets()[0]
    elif a.phase=='freeze':result=freeze();result={'frozen':True,'new':len(result['records']),'budget_usd':C.BUDGET_USD}
    elif a.phase=='verify':result=verify();result={'verified':True,'new':len(result['records'])}
    elif a.phase=='probe':result=probe()
    elif a.phase=='tests':result=cpu_tests()
    elif a.phase=='coordinate':return coordinate(a.scope,a.execute)
    else:result=launch(a.scope,a.execute)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
