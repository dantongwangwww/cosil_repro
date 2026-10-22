"""Frozen D-SIMPLE Lite continuation; one pre-existing shared USD5 budget."""
import argparse
import collections
import copy
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from . import common as C
from .lite_bootstrap import financial_contract

CONFIG=C.ROOT/'configs/lite_resolved_config.json'
FREEZE=C.RUN/'lite_online_freeze.json'
OLD_NAMES=['__init__.py','common.py','code_index.py','simple_pipeline.py','providers.py','execution.py','token_counter.py']
VISIBLE_NEW=['__init__.py','common.py','lite_bootstrap.py','lite_worker.py']
ALL_NEW=VISIBLE_NEW+['lite_runtime.py','lite_prepare.py']
FINANCE_ALLOWED={'budget.json','budget.lock','budget_stop.json','dsimple_v2_safety_stop.json'}|{'dsimple_v2_api_slot_'+str(i)+'.lock' for i in range(4)}


def once(path,value):
    previous=C.load(path)
    if previous is not None:
        if previous!=value:raise RuntimeError('Immutable Lite runtime artifact drift: '+str(path))
    else:C.write(path,value)


def assets():
    parent=C.load(C.FROZEN/'configs/resolved_config.json');expected=parent['source_sha256'];mapping={}
    names=['prompts/'+n+'.txt' for n in ['file_selection','query_planning','function_localization']]+['resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json']
    for name in names:
        source=C.FROZEN/name;dest=C.ROOT/name
        if expected.get(str(source))!=C.sha(source):raise RuntimeError('Frozen P1 prompt/tokenizer changed')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and C.sha(dest)!=C.sha(source):raise RuntimeError('New Lite asset differs')
        if not dest.exists():shutil.copyfile(source,dest)
        mapping[str(dest)]=C.sha(dest)
    cache=C.ADDITIONAL/'resources/offline_tiktoken/fb374d419588a4632f3f557e76b4b70aebbca790';dest=C.ROOT/'resources/offline_tiktoken'/cache.name
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():shutil.copyfile(cache,dest)
    if C.sha(dest)!=C.sha(cache):raise RuntimeError('Offline o200k cache differs from frozen resource')
    mapping[str(dest)]=C.sha(dest)
    contract=financial_contract()
    config={k:copy.deepcopy(parent[k]) for k in ['deepseek','simple','price_snapshot','api_concurrency','transport_retries','semantic_retries']}
    config.update(run_id=C.RUN_ID,cohort=C.COHORT,methods=['D-SIMPLE'],root=str(C.ROOT),gpu_used=False,
        shared_budget_contract=contract,budget_usd=5.,new_independent_budget_created=False,
        budget={'per_case_soft_cny':.5,'per_case_hard_cny':1.5,'fx':7,'cumulative_tokens_per_case':400000,'case_key':'D-SIMPLE|instance_id'},
        tokenizer={'path':str(C.ROOT/names[-1]),'sha256':mapping[str(C.ROOT/names[-1])],'o200k_cache':str(dest)},
        pre_change_github_commit=C.PRE_CHANGE_GITHUB_COMMIT,
        inference_ast='unchanged P1 Python3.11 code_index; independent Python3.12 evaluator never enters inference')
    if config['deepseek']['thinking']!='disabled' or config['semantic_retries']!=0 or config['transport_retries']!=3 or config['api_concurrency']!=4:raise RuntimeError('Frozen inference contract differs')
    once(CONFIG,config)
    once(C.ROOT/'configs/shared_budget_registration.json',{'shared_ledger':str(C.SHARED_BUDGET),'shared_cap_usd':5.,'original_ledger_scope_label_preserved':True,
        'new_authorization':'All new Lite and independently eligible screened-dataset requests share this pre-existing cap; no per-run reset.',
        'old200_remains_paused':True,'legacy100_and_Lite55_reuse_no_new_charge':True,'global_concurrent_api_operations':4})
    return config,mapping


def assert_old200_sources():
    frozen=C.load(C.ADDITIONAL_RUN/'online_freeze.json')
    for path,expected in frozen['online_sha256'].items():
        if C.sha(path)!=expected:raise RuntimeError('Old200 online source changed: '+path)
    return frozen['online_sha256']


def freeze():
    config,asset_sha=assets();old200=assert_old200_sources()
    manifest=C.load(C.ROOT/'manifests/lite270.json');new=C.load(C.ROOT/'manifests/lite215.json')
    if not manifest or not manifest.get('complete') or manifest['n']!=270 or new['n']!=215:raise RuntimeError('Complete Lite270/215 preparation is required')
    if len({r['instance_id'] for r in manifest['records']})!=270 or len({r['instance_id'] for r in new['records']})!=215:raise RuntimeError('Lite cohort uniqueness changed')
    data={};snapshots={};reuse_hashes={};preparation={}
    for record in new['records']:
        if record.get('preparation_status')=='failed':
            C.write(Path(record['result_dir'])/'result.json',{'status':'input_preparation_failed','instance_id':record['instance_id'],'method':'D-SIMPLE',
                'cohort':C.COHORT,'run_id':C.RUN_ID,'repo':record['repo'],'base_commit':record['base_commit'],'predicted_files':[],'predicted_functions':[],
                'error_type':record['preparation_error_type'],'error_message':record['preparation_error_message'],'api_calls':0})
            continue
        receipt_path=C.ROOT/'evaluator_private/lite/preparation'/(record['instance_id']+'.json');receipt=C.load(receipt_path)
        if not receipt or receipt['status']!='complete' or not receipt['online_ast_python'].startswith('3.11'):raise RuntimeError('Missing unchanged Python3.11 inference preparation')
        data.update(receipt['data_sha256']);snapshots.update(receipt['snapshot_sha256']);preparation[str(receipt_path)]=C.sha(receipt_path)
    for record in manifest['records']:
        if record['origin']=='new215':continue
        path=C.ROOT/'evaluator_private/lite/reuse_contracts'/(record['instance_id']+'.json');receipt=C.load(path)
        if not receipt or not receipt['validated'] or receipt['requests']!=7:raise RuntimeError('Prior55 reuse contract missing')
        preparation[str(path)]=C.sha(path);reuse_hashes.update(receipt['historical_artifact_sha256'])
    online={str(C.FROZEN/'src'/n):C.sha(C.FROZEN/'src'/n) for n in OLD_NAMES}
    online.update({str(C.ROOT/'dsimple_v2'/n):C.sha(C.ROOT/'dsimple_v2'/n) for n in ALL_NEW});online.update(asset_sha);online[str(CONFIG)]=C.sha(CONFIG)
    worker_online={p:h for p,h in online.items() if not p.endswith(('lite_runtime.py','lite_prepare.py')) and p!=str(CONFIG)}
    frozen={'run_id':C.RUN_ID,'cohort':C.COHORT,'config':config,'records':new['records'],'allocated_new':215,'eligible_total':270,'reused55':55,
        'smoke_ids':[r['instance_id'] for r in new['records'][:5]],'online_sha256':online,'worker_online_sha256':worker_online,
        'data_sha256':data,'snapshot_sha256':snapshots,'preparation_receipt_sha256':preparation,'reuse_history_sha256':reuse_hashes,
        'old200_online_sha256':old200,'manifest_sha256':{str(C.ROOT/'manifests'/n):C.sha(C.ROOT/'manifests'/n) for n in ['lite270.json','lite215.json']},
        'shared_budget_contract':config['shared_budget_contract'],'new_ledger_created':False,'gpu_used':False}
    once(FREEZE,frozen);return verify()


def verify():
    frozen=C.load(FREEZE)
    if not frozen or frozen['run_id']!=C.RUN_ID or frozen['cohort']!=C.COHORT:raise RuntimeError('Lite source freeze missing/wrong')
    for field in ['online_sha256','data_sha256','snapshot_sha256','preparation_receipt_sha256','reuse_history_sha256','old200_online_sha256','manifest_sha256']:
        for path,expected in frozen[field].items():
            if C.sha(path)!=expected:raise RuntimeError('Frozen Lite artifact drift in '+field+': '+path)
    contract=financial_contract()
    if contract!=frozen['shared_budget_contract']:raise RuntimeError('Shared ledger path/directory contract changed')
    ledger=C.load(C.SHARED_BUDGET)
    if not ledger or ledger.get('stage_cap_usd')!=5. or sum(a['charged_upper_usd'] for a in ledger['attempts'].values())>5.+1e-10:raise RuntimeError('Existing shared USD5 ledger invalid')
    if (C.RUN/'budget.json').exists():raise RuntimeError('A separate Lite budget ledger is forbidden')
    return frozen


def worker_env():
    return dict(os.environ,PYTHONPATH=str(C.ROOT),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',TIKTOKEN_CACHE_DIR=str(C.ROOT/'resources/offline_tiktoken'))


def make_batch(frozen,records,scope,index):
    tasks=[]
    for record in records:
        if record.get('preparation_status')=='failed':continue
        job=C.load(record['job']);prefix=str(Path(job['snapshot']))+'/'
        Path(record['result_dir']).mkdir(parents=True,exist_ok=True)
        tasks.append({'job':record['job'],'instance_id':record['instance_id'],'result_dir':record['result_dir'],'enqueued_utc':C.utc(),
            'data_sha256':{p:frozen['data_sha256'][p] for p in [record['job'],job['code_index'],job['structure']]},
            'snapshot_sha256':{p:h for p,h in frozen['snapshot_sha256'].items() if p.startswith(prefix)}})
    receipt_dir=C.RUN/'worker_receipts'/(scope+'_'+str(index));receipt_dir.mkdir(parents=True,exist_ok=True)
    return {'run_id':C.RUN_ID,'cohort':C.COHORT,'methods':['D-SIMPLE'],'config':frozen['config'],'tasks':tasks,
        'worker_online_sha256':frozen['worker_online_sha256'],'shared_budget_contract':frozen['shared_budget_contract'],'worker_receipt_dir':str(receipt_dir)}


def sandbox_argv(batch_file,batch,probe_only=False):
    argv=['bwrap','--die-with-parent','--new-session','--unshare-pid','--ro-bind','/','/','--proc','/proc','--dev-bind','/dev','/dev',
        '--tmpfs','/tmp','--tmpfs',str(C.COSIL.parent),'--tmpfs',str(Path('/home/wdt/models').resolve()),
        '--tmpfs',str((Path.home()/'.cache').resolve())]
    for name in ['dsimple_v2','jobs','snapshots','manifests','reports','configs','evaluator_private','runs']:argv+=['--dir',str(C.ROOT/name)]
    for name in VISIBLE_NEW:argv+=['--ro-bind',str(C.ROOT/'dsimple_v2'/name),str(C.ROOT/'dsimple_v2'/name)]
    argv+=['--dir',str(C.FROZEN/'src')]
    for name in OLD_NAMES:argv+=['--ro-bind',str(C.FROZEN/'src'/name),str(C.FROZEN/'src'/name)]
    for path in [C.ROOT/'prompts',C.ROOT/'resources/deepseek_v4_tokenizer',C.ROOT/'resources/offline_tiktoken',C.COSIL/'.venv-v5']:
        argv+=['--ro-bind',str(path),str(path)]
    # Finance is the existing canonical ledger directory. Mask every non-finance
    # entry, so atomic rename remains safe without exposing old run metadata.
    finance=C.SHARED_BUDGET.parent
    argv+=['--bind',str(finance.resolve()),str(finance)]
    for path in finance.iterdir():
        if path.name in FINANCE_ALLOWED or '.v2tmp.' in path.name:continue
        if path.is_dir():argv+=['--tmpfs',str(path)]
        else:argv+=['--ro-bind','/dev/null',str(path)]
    seen=set()
    for task in batch['tasks']:
        job=C.load(task['job']);logical=Path(task['job']).parent;actual=logical.resolve();snapshot=Path(job['snapshot'])
        mounts=[(actual,logical),(actual,actual),(snapshot.resolve(),C.ROOT/'snapshots'/job['instance_id']),(snapshot.resolve(),snapshot.resolve())]
        for source,target in mounts:
            if str(target) not in seen:argv+=['--ro-bind',str(source),str(target)];seen.add(str(target))
        argv+=['--bind',str(Path(task['result_dir']).resolve()),str(task['result_dir'])]
    argv+=['--bind',str(Path(batch['worker_receipt_dir']).resolve()),str(batch['worker_receipt_dir'])]
    argv+=['--ro-bind',str(Path(batch_file).resolve()),str(batch_file),'--chdir',str(C.ROOT),'--',str(C.PYTHON),'-m','dsimple_v2.lite_worker',str(batch_file)]
    argv+=['--probe'] if probe_only else ['--execute']
    return argv


def probe():
    frozen=verify();records=[r for r in frozen['records'] if r.get('preparation_status')!='failed'][:5]
    batch=make_batch(frozen,records,'probe',0);path=C.RUN/'batches/lite_probe.json';C.write(path,batch)
    result=subprocess.run(sandbox_argv(path,batch,True),env=worker_env(),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
    receipt={'time':C.utc(),'passed':result.returncode==0,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'paid_requests':0,'gpu_used':False}
    C.write(C.RUN/'lite_isolation_probe.json',receipt)
    if result.returncode:raise RuntimeError('Actual Lite isolation probe failed: '+result.stderr[-2000:])
    return receipt


def pending(frozen,scope):
    ids=set(frozen['smoke_ids']) if scope=='smoke' else {r['instance_id'] for r in frozen['records']}
    return [r for r in frozen['records'] if r['instance_id'] in ids and not (Path(r['result_dir'])/'result.json').exists()]


def coordinate(scope,execute=False):
    if not execute:raise PermissionError('Lite coordinator needs explicit --execute')
    with (C.RUN/'lite_coordinator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);frozen=verify()
        if not C.load(C.RUN/'lite_cpu_tests.json',{}).get('passed') or not C.load(C.RUN/'lite_isolation_probe.json',{}).get('passed'):raise RuntimeError('CPU tests and actual isolation probe must pass before paid calls')
        if scope=='full' and not C.load(C.RUN/'lite_smoke_gate.json',{}).get('passed'):raise RuntimeError('Fixed first5 smoke engineering gate required')
        from .lite_bootstrap import stopped,stop
        if stopped() or (C.SHARED_BUDGET.parent/'budget_stop.json').exists():raise RuntimeError('Shared financial safety/budget stop active')
        rows=pending(frozen,scope);children=[]
        try:
            for index in range(4):
                group=rows[index::4]
                if not group:continue
                batch=make_batch(frozen,group,scope,index);path=C.RUN/'batches'/('lite_'+scope+'_'+str(index)+'.json');C.write(path,batch)
                log=path.with_suffix('.log').open('a');process=subprocess.Popen(sandbox_argv(path,batch),env=worker_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                log.close();children.append(process)
            C.write(C.RUN/('lite_'+scope+'_workers.json'),{'time':C.utc(),'coordinator_pid':os.getpid(),'worker_pids':[p.pid for p in children],'pending':len(rows),'gpu_used':False})
            while any(p.poll() is None for p in children):
                if any(p.poll() is not None and p.returncode for p in children):stop('isolated_Lite_worker_exit')
                time.sleep(3)
            if any(p.returncode for p in children):raise RuntimeError('Lite worker exit; receipts preserved')
            verify();statuses=collections.Counter();smoke=[]
            for record in frozen['records']:
                result=C.load(Path(record['result_dir'])/'result.json');statuses[result['status'] if result else 'NOT_RUN']+=1
                if record['instance_id'] in frozen['smoke_ids']:smoke.append(result)
            if scope=='smoke':C.write(C.RUN/'lite_smoke_gate.json',{'passed':len(smoke)==5 and all(r is not None for r in smoke) and not stopped(),
                'time':C.utc(),'fixed_smoke_ids':frozen['smoke_ids'],'statuses':[r['status'] if r else 'NOT_RUN' for r in smoke],'accuracy_threshold_used':False})
            C.write(C.RUN/('lite_'+scope+'_complete.json'),{'time':C.utc(),'phase_finished':True,'allocated_new':215,'reused55':55,'statuses':dict(statuses),
                'shared_budget':str(C.SHARED_BUDGET),'history_and_source_sha_verified':True,'gpu_used':False})
        except Exception as error:stop('Lite_coordinator_failure',error_type=type(error).__name__,error_message=str(error)[:500]);raise


def launch(scope,execute=False):
    frozen=verify();rows=pending(frozen,scope)
    if not execute:return {'dry_run':True,'scope':scope,'new_cases':len(rows),'max_semantic_requests':len(rows)*7,'shared_budget':str(C.SHARED_BUDGET),'new_budget_created':False}
    logpath=C.RUN/('lite_'+scope+'_launcher.log');log=logpath.open('a')
    process=subprocess.Popen([str(C.PYTHON),'-m','dsimple_v2.lite_runtime','--phase','coordinate','--scope',scope,'--execute'],cwd=C.ROOT,
        env=worker_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    log.close();value={'time':C.utc(),'pid':process.pid,'new_session':True,'scope':scope,'pending':len(rows),'log':str(logpath)}
    C.write(C.RUN/('lite_'+scope+'_launcher.json'),value);return value


def tests():
    command=[str(C.PYTHON),'-m','unittest','discover','-s','tests','-p','test_lite_*.py','-t','.','-v']
    process=subprocess.run(command,cwd=C.ROOT,env=worker_env(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    value={'time':C.utc(),'passed':process.returncode==0,'output':process.stdout};C.write(C.RUN/'lite_cpu_tests.json',value)
    if process.returncode:raise RuntimeError('Lite CPU tests failed: '+process.stdout[-3000:])
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',required=True,choices=['assets','tests','freeze','verify','probe','run','coordinate']);p.add_argument('--scope',choices=['smoke','full'],default='smoke');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.phase=='assets':result=assets()[0]
    elif a.phase=='tests':result=tests()
    elif a.phase=='freeze':frozen=freeze();result={'frozen':True,'allocated_new':len(frozen['records']),'reused55':55,'new_budget_created':False}
    elif a.phase=='verify':verify();result={'verified':True,'new_budget_created':False}
    elif a.phase=='probe':result=probe()
    elif a.phase=='coordinate':return coordinate(a.scope,a.execute)
    else:result=launch(a.scope,a.execute)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
