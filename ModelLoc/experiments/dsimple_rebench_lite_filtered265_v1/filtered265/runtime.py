"""Independent filtered265 controller; frozen D-SIMPLE and existing shared USD5."""
import argparse
import collections
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from . import common as C
from .bootstrap import financial_contract

CONFIG=C.ROOT/'configs/resolved_config.json'
FREEZE=C.RUN/'online_freeze.json'
BASELINE=C.RUN/'financial_baseline.json'
PACKAGE='filtered265'
OLD_NAMES=['__init__.py','common.py','code_index.py','simple_pipeline.py','providers.py','execution.py','token_counter.py']
VISIBLE_NEW=['__init__.py','common.py','bootstrap.py','worker.py']
ALL_NEW=VISIBLE_NEW+['runtime.py']
FINANCE_ALLOWED={'budget.json','budget.lock','budget_stop.json','dsimple_v2_safety_stop.json'}|{'dsimple_v2_api_slot_'+str(i)+'.lock' for i in range(4)}
CLEAN_KEYS={'instance_id','repo','base_commit','problem_statement','cohort','snapshot','paths','code_index','structure'}
IDENTITY=('instance_id','repo','base_commit','sampling_hash')


def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def once(path,value):
    prior=C.load(path)
    if prior is not None:
        if prior!=value:raise RuntimeError('Immutable filtered265 artifact drift: '+str(path))
    else:C.write(path,value)


def source_signature():
    return {str(C.ROOT/PACKAGE/n):C.sha(C.ROOT/PACKAGE/n) for n in ALL_NEW}


def validate_ledger(ledger):
    if not ledger or ledger.get('stage_cap_usd')!=5. or C.BUDGET_USD!=5.:raise RuntimeError('Original shared USD5 ledger required')
    if not isinstance(ledger.get('attempts'),dict) or not isinstance(ledger.get('cases'),dict):raise RuntimeError('Malformed shared ledger')
    costs=[a['charged_upper_usd'] for a in ledger['attempts'].values()]
    if any(not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 for v in costs) or sum(costs)>5.+1e-10:raise RuntimeError('Shared financial bounds invalid')
    return ledger


def prior_contracts():
    prior=C.load(C.PRIOR_V2/'runs/20261022_lite_eval_v2_nonthinking/lite_online_freeze.json')
    old=C.load(C.ADDITIONAL_RUN/'online_freeze.json')
    if not prior or not old:raise RuntimeError('Prior immutable source/finance contracts missing')
    expected=prior['shared_budget_contract']
    if financial_contract()!=expected:raise RuntimeError('Original shared financial directory/path/inode contract changed')
    protected={**prior['online_sha256'],**old['online_sha256']}
    pause=C.ADDITIONAL_RUN/'user_pause.json'
    if not C.load(pause,{}).get('resume_requires_user_instruction'):raise RuntimeError('Original additional200 pause must remain preserved')
    protected[str(pause)]=C.sha(pause)
    for p,h in protected.items():
        if C.sha(p)!=h:raise RuntimeError('Protected historical source drift: '+p)
    return expected,protected


def assets():
    contract,protected=prior_contracts();parent=C.load(C.FROZEN/'configs/resolved_config.json');mapping={}
    names=['prompts/'+n+'.txt' for n in ['file_selection','query_planning','function_localization']]+['resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json']
    for name in names:
        source=C.FROZEN/name;dest=C.ROOT/name;h=C.sha(source)
        if parent['source_sha256'].get(str(source))!=h:raise RuntimeError('Frozen prompt/tokenizer source drift')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and C.sha(dest)!=h:raise RuntimeError('New prompt/tokenizer differs')
        if not dest.exists():shutil.copyfile(source,dest)
        mapping[str(dest)]=h
    cache=C.PRIOR_V2/'resources/offline_tiktoken/fb374d419588a4632f3f557e76b4b70aebbca790';dest=C.ROOT/'resources/offline_tiktoken'/cache.name
    if protected.get(str(cache))!=C.sha(cache):raise RuntimeError('Pinned offline tokenizer cache changed')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():shutil.copyfile(cache,dest)
    if C.sha(dest)!=C.sha(cache):raise RuntimeError('Offline tokenizer cache differs')
    mapping[str(dest)]=C.sha(dest)
    config={k:copy.deepcopy(parent[k]) for k in ['deepseek','simple','price_snapshot','api_concurrency','transport_retries','semantic_retries']}
    config.update(run_id=C.RUN_ID,cohort=C.COHORT,methods=['D-SIMPLE'],root=str(C.ROOT),gpu_used=False,
        shared_budget_contract=contract,budget_usd=5.,new_independent_budget_created=False,
        budget={'per_case_soft_cny':.5,'per_case_hard_cny':1.5,'fx':7,'cumulative_tokens_per_case':400000,'case_key':'D-SIMPLE|instance_id'},
        tokenizer={'path':str(C.ROOT/names[-1]),'sha256':mapping[str(C.ROOT/names[-1])],'o200k_cache':str(dest)},
        pre_change_github_commit=C.PRE_CHANGE_GITHUB_COMMIT,inference_ast='unchanged P1 Python3.11; independent R2 Python3.12 evaluator excluded')
    if config['deepseek']['thinking']!='disabled' or config['semantic_retries']!=0 or config['transport_retries']!=3 or config['api_concurrency']!=4:raise RuntimeError('Frozen generation configuration differs')
    once(CONFIG,config)
    return config,mapping,protected


def validate_roster(roster,source,manifest,new):
    selected=sorted((r for r in source['records'] if r.get('qualified') is True),key=lambda r:(r['sampling_hash'],r['instance_id']))
    if len(selected)!=265 or len({r['instance_id'] for r in selected})!=265 or len({r['repo'].lower() for r in selected})!=173:raise RuntimeError('Authoritative qualified265 population changed')
    if roster.get('n')!=265 or roster.get('allow_repeated_repository') is not True or roster.get('rules_relaxed') is not False:raise RuntimeError('Formal roster scope differs')
    for r in selected:
        b=r['business_patch']
        if not r['four_filter_pass'] or not r['history_pass'] or r['four_filter_reasons'] or r['history_reasons']:raise RuntimeError('Nonqualified issue entered roster')
        if b['files']>1 or b['hunks']>3 or r['problem_words']<40 or any(b.get(k) for k in ['added_files','removed_files','new_file_mode','deleted_file_mode','dev_null','copy_metadata_files']):raise RuntimeError('Four original screening constraints relaxed')
    expected=[tuple(r[k] for k in IDENTITY) for r in selected]
    for label,value in [('roster',roster),('manifest',manifest)]:
        if value.get('n')!=265 or [tuple(r[k] for k in IDENTITY) for r in value['records']]!=expected:raise RuntimeError(label+' identity/order differs from all qualified265')
    if manifest.get('complete') is False or new.get('n')!=221:raise RuntimeError('Final preparation manifest incomplete')
    reused=[r for r in manifest['records'] if r['origin']=='old100_reuse44'];fresh=[r for r in manifest['records'] if r['origin']=='new221']
    if len(reused)!=44 or len(fresh)!=221 or fresh!=new['records']:raise RuntimeError('44 reused/221 new allocation or order changed')
    groups=collections.Counter(r['observation_group'] for r in selected)
    if groups!={'old100_observed':44,'old200_prepared_not_run':58,'unseen':163}:raise RuntimeError('Frozen observation groups changed')
    for r,s in zip(manifest['records'],selected):
        if (r['origin']=='old100_reuse44')!=(s['observation_group']=='old100_observed'):raise RuntimeError('Historical prediction reuse identity changed')
    return fresh,reused


def authorization():
    path=C.ROOT/'configs/authorization.json';value=C.load(path)
    required={'n_tasks':265,'n_repositories':173,'planned_reuse':44,'planned_new':221,'shared_cap_usd':5,'thinking':'disabled','no_new_budget':True}
    if not value or any(value.get(k)!=v for k,v in required.items()) or Path(value['shared_ledger']).resolve()!=C.SHARED_BUDGET.resolve():raise RuntimeError('User scope/shared financial authorization differs')
    if value['code_checkpoint']!=C.PRE_CHANGE_GITHUB_COMMIT:raise RuntimeError('Pre-change checkpoint differs')
    return path,value


def freeze():
    if FREEZE.exists():return verify()
    config,asset_sha,protected=assets();auth_path,auth=authorization()
    roster_path=C.ROOT/'manifests/filtered265_roster.json';manifest_path=C.ROOT/'manifests/filtered265.json';new_path=C.ROOT/'manifests/new221.json'
    roster=C.load(roster_path);manifest=C.load(manifest_path);new=C.load(new_path)
    if not roster or not manifest or not new:raise RuntimeError('Final265/221 preparation and formal roster required')
    screen=C.PRIOR_V2/'evaluator_private/rebench_lite_filtered_v1/screening_all860.json';public=C.PRIOR_V2/'reports/rebench_lite_filtered_v1/screening_all860.json'
    if C.sha(screen)!=roster['source_screen_sha256'] or C.sha(public)!=roster['source_screen_sha256']:raise RuntimeError('Private/public authority screening source SHA differs')
    source=C.load(screen);fresh,reused=validate_roster(roster,source,manifest,new)
    ledger=validate_ledger(C.load(C.SHARED_BUDGET))
    if C.sha(C.SHARED_BUDGET)!=auth['pre_batch_budget_sha256'] or set(ledger['attempts'])!=set(auth['pre_batch_attempt_ids']):raise RuntimeError('Pre-stage budget snapshot differs from authorized1505 baseline')
    if not math.isclose(sum(a['charged_upper_usd'] for a in ledger['attempts'].values()),auth['pre_batch_charged_upper_usd'],abs_tol=1e-10):raise RuntimeError('Pre-stage financial total differs')
    if any(a['key'] in {'D-SIMPLE|'+r['instance_id'] for r in fresh} for a in ledger['attempts'].values()):raise RuntimeError('New221 already has historical paid attempts; preserve and investigate')
    data={};snapshots={};receipts={};history={};private=C.ROOT/'evaluator_private/filtered265'
    for r in manifest['records']:
        if r.get('preparation_status')=='failed' and r['origin']=='new221':continue
        job=C.load(r['job']);row=C.load(r['private_row'])
        if not job or not row or any(job[k]!=r[k] or row[k]!=r[k] for k in ['instance_id','repo','base_commit']) or job['problem_statement']!=row['problem_statement']:raise RuntimeError('Roster/job/private issue identity differs')
        if r['origin']=='old100_reuse44':
            receipt_path=private/'reuse_contracts'/(r['instance_id']+'.json');receipt=C.load(receipt_path)
            if not receipt or receipt.get('validated') is not True or receipt.get('requests')!=7:raise RuntimeError('Historical44 contract incomplete')
            history.update(receipt['historical_artifact_sha256']);receipts[str(receipt_path)]=C.sha(receipt_path)
            continue
        if set(job)!=CLEAN_KEYS or job['cohort']!=C.COHORT:raise RuntimeError('Unsafe new inference job fields/cohort')
        if Path(r['result_dir'])!=C.RUN/C.COHORT/'D-SIMPLE'/r['instance_id']:raise RuntimeError('New result directory escaped independent run')
        receipt_path=private/'preparation'/(r['instance_id']+'.json');receipt=C.load(receipt_path)
        if not receipt or receipt.get('status')!='complete' or not receipt.get('online_ast_python','').startswith('3.11'):raise RuntimeError('Frozen Python3.11 preparation missing')
        if set(receipt['data_sha256'])!={r['job'],job['code_index'],job['structure']}:raise RuntimeError('Preparation input hash coverage differs')
        if any(not p.startswith(str(Path(job['snapshot']))+'/') for p in receipt['snapshot_sha256']):raise RuntimeError('Snapshot receipt path escaped selected base')
        data.update(receipt['data_sha256']);snapshots.update(receipt['snapshot_sha256']);receipts[str(receipt_path)]=C.sha(receipt_path)
    for r in fresh:
        if r.get('preparation_status')=='failed':
            once(Path(r['result_dir'])/'result.json',{'status':'input_preparation_failed','instance_id':r['instance_id'],'method':'D-SIMPLE','cohort':C.COHORT,'run_id':C.RUN_ID,'repo':r['repo'],'base_commit':r['base_commit'],'predicted_files':[],'predicted_functions':[],'error_type':r.get('preparation_error_type','PreparationFailure'),'error_message':r.get('preparation_error_message',r.get('preparation_error','')),'api_calls':0,'gpu_used':False})
    once(BASELINE,ledger)
    online={str(C.FROZEN/'src'/n):C.sha(C.FROZEN/'src'/n) for n in OLD_NAMES};online.update(source_signature());online.update(asset_sha);online[str(CONFIG)]=C.sha(CONFIG)
    selection={str(p):C.sha(p) for p in [roster_path,manifest_path,new_path,screen,public,auth_path]}
    tests_path=C.ROOT/'tests/test_runtime.py'
    frozen={'run_id':C.RUN_ID,'cohort':C.COHORT,'config':config,'records':fresh,'allocated_new':len(fresh),'eligible_total':len(manifest['records']),'reused':len(reused),'smoke_ids':[r['instance_id'] for r in fresh[:5]],
        'online_sha256':online,'worker_online_sha256':{p:h for p,h in online.items() if p!=str(CONFIG) and p!=str(C.ROOT/PACKAGE/'runtime.py')},'data_sha256':data,'snapshot_sha256':snapshots,'preparation_receipt_sha256':receipts,'reuse_history_sha256':history,'protected_history_sha256':protected,'selection_sha256':selection,
        'test_sha256':{str(tests_path):C.sha(tests_path)},'shared_budget_contract':config['shared_budget_contract'],'financial_baseline_sha256':{str(BASELINE):C.sha(BASELINE)},'baseline_attempt_sha256':{rid:digest(a) for rid,a in ledger['attempts'].items()},'new_ledger_created':False,'gpu_used':False}
    once(FREEZE,frozen);return verify()


def verify():
    frozen=C.load(FREEZE)
    if not frozen or frozen['run_id']!=C.RUN_ID or frozen['cohort']!=C.COHORT:raise RuntimeError('Independent filtered265 source freeze missing/wrong')
    for field in ['online_sha256','data_sha256','snapshot_sha256','preparation_receipt_sha256','reuse_history_sha256','protected_history_sha256','selection_sha256','test_sha256','financial_baseline_sha256']:
        for p,h in frozen[field].items():
            if C.sha(p)!=h:raise RuntimeError('Frozen artifact drift in '+field+': '+p)
    if financial_contract()!=frozen['shared_budget_contract']:raise RuntimeError('Original financial directory contract changed')
    ledger=validate_ledger(C.load(C.SHARED_BUDGET))
    if any(rid not in ledger['attempts'] or digest(ledger['attempts'][rid])!=h for rid,h in frozen['baseline_attempt_sha256'].items()):raise RuntimeError('Pre-stage historical billing receipt changed')
    if (C.RUN/'budget.json').exists():raise RuntimeError('Independent budget reset forbidden')
    return frozen


def worker_env():
    return dict(os.environ,PYTHONPATH=str(C.ROOT),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',TIKTOKEN_CACHE_DIR=str(C.ROOT/'resources/offline_tiktoken'))


def make_batch(frozen,records,scope,index):
    tasks=[]
    for r in records:
        if r.get('preparation_status')=='failed':continue
        job=C.load(r['job']);prefix=str(Path(job['snapshot']))+'/'
        Path(r['result_dir']).mkdir(parents=True,exist_ok=True)
        tasks.append({'job':r['job'],'instance_id':r['instance_id'],'result_dir':r['result_dir'],'enqueued_utc':C.utc(),'data_sha256':{p:frozen['data_sha256'][p] for p in [r['job'],job['code_index'],job['structure']]},'snapshot_sha256':{p:h for p,h in frozen['snapshot_sha256'].items() if p.startswith(prefix)}})
    receipt_dir=C.RUN/'worker_receipts'/(scope+'_'+str(index));receipt_dir.mkdir(parents=True,exist_ok=True)
    return {'run_id':C.RUN_ID,'cohort':C.COHORT,'methods':['D-SIMPLE'],'config':frozen['config'],'tasks':tasks,'worker_online_sha256':frozen['worker_online_sha256'],'shared_budget_contract':frozen['shared_budget_contract'],'worker_receipt_dir':str(receipt_dir)}


def sandbox_argv(batch_file,batch,probe_only=False):
    argv=['bwrap','--die-with-parent','--new-session','--unshare-pid','--ro-bind','/','/','--proc','/proc','--dev-bind','/dev','/dev','--tmpfs','/tmp','--tmpfs',str(C.COSIL.parent),'--tmpfs',str(Path('/home/wdt/models').resolve()),'--tmpfs',str((Path.home()/'.cache').resolve())]
    for name in [PACKAGE,'jobs','snapshots','manifests','reports','configs','evaluator_private','runs']:argv+=['--dir',str(C.ROOT/name)]
    for name in VISIBLE_NEW:argv+=['--ro-bind',str(C.ROOT/PACKAGE/name),str(C.ROOT/PACKAGE/name)]
    argv+=['--dir',str(C.FROZEN/'src')]
    for name in OLD_NAMES:argv+=['--ro-bind',str(C.FROZEN/'src'/name),str(C.FROZEN/'src'/name)]
    for p in [C.ROOT/'prompts',C.ROOT/'resources/deepseek_v4_tokenizer',C.ROOT/'resources/offline_tiktoken',C.COSIL/'.venv-v5']:argv+=['--ro-bind',str(p),str(p)]
    finance=C.SHARED_BUDGET.parent;argv+=['--bind',str(finance.resolve()),str(finance)]
    for p in finance.iterdir():
        if p.name in FINANCE_ALLOWED or '.v2tmp.' in p.name:continue
        argv+=['--tmpfs',str(p)] if p.is_dir() else ['--ro-bind','/dev/null',str(p)]
    seen=set()
    for task in batch['tasks']:
        job=C.load(task['job']);logical=Path(task['job']).parent;actual=logical.resolve();snapshot=Path(job['snapshot'])
        for source,target in [(actual,logical),(actual,actual),(snapshot.resolve(),C.ROOT/'snapshots'/job['instance_id']),(snapshot.resolve(),snapshot.resolve())]:
            if str(target) not in seen:argv+=['--ro-bind',str(source),str(target)];seen.add(str(target))
        argv+=['--bind',str(Path(task['result_dir']).resolve()),str(task['result_dir'])]
    argv+=['--bind',str(Path(batch['worker_receipt_dir']).resolve()),str(batch['worker_receipt_dir']),'--ro-bind',str(Path(batch_file).resolve()),str(batch_file),'--chdir',str(C.ROOT),'--',str(C.PYTHON),'-m',PACKAGE+'.worker',str(batch_file)]
    return argv+(['--probe'] if probe_only else ['--execute'])


def probe():
    frozen=verify();records=[r for r in frozen['records'] if r.get('preparation_status')!='failed'][:5]
    if len(records)!=5:raise RuntimeError('Five prepared cases needed for actual isolation probe')
    batch=make_batch(frozen,records,'probe',0);path=C.RUN/'batches/probe.json';C.write(path,batch)
    result=subprocess.run(sandbox_argv(path,batch,True),env=worker_env(),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
    receipt={'time':C.utc(),'passed':result.returncode==0,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'paid_requests':0,'gpu_used':False,'online_freeze_sha256':C.sha(FREEZE)}
    C.write(C.RUN/'isolation_probe.json',receipt)
    if result.returncode:raise RuntimeError('Actual filtered265 isolation probe failed: '+result.stderr[-2000:])
    return receipt


def pending(frozen,scope):
    ids=set(frozen['smoke_ids']) if scope=='smoke' else {r['instance_id'] for r in frozen['records']}
    return [r for r in frozen['records'] if r['instance_id'] in ids and not (Path(r['result_dir'])/'result.json').exists()]


def paid_gates(frozen,scope):
    tests=C.load(C.RUN/'cpu_tests.json',{});proof=C.load(C.RUN/'isolation_probe.json',{})
    if not tests.get('passed') or tests.get('source_sha256')!=source_signature() or not proof.get('passed') or proof.get('online_freeze_sha256')!=C.sha(FREEZE):raise RuntimeError('Current-source CPU tests and actual isolation probe required')
    if scope=='full':
        gate=C.load(C.RUN/'smoke_gate.json',{})
        if not gate.get('passed') or gate.get('online_freeze_sha256')!=C.sha(FREEZE):raise RuntimeError('Current-freeze fixed first5 smoke engineering gate required')
    from .bootstrap import stopped
    if stopped() or (C.SHARED_BUDGET.parent/'budget_stop.json').exists():raise RuntimeError('Existing shared financial stop forbids new calls')


def coordinate(scope,execute=False):
    if not execute:raise PermissionError('Paid coordinator requires explicit --execute')
    with (C.RUN/'coordinator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);frozen=verify();paid_gates(frozen,scope)
        from .bootstrap import stopped,stop
        rows=pending(frozen,scope);children=[]
        try:
            for index in range(4):
                group=rows[index::4]
                if not group:continue
                batch=make_batch(frozen,group,scope,index);path=C.RUN/'batches'/(scope+'_'+str(index)+'.json');C.write(path,batch)
                log=path.with_suffix('.log').open('a');process=subprocess.Popen(sandbox_argv(path,batch),env=worker_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);log.close();children.append(process)
            C.write(C.RUN/(scope+'_workers.json'),{'time':C.utc(),'coordinator_pid':os.getpid(),'worker_pids':[p.pid for p in children],'pending':len(rows),'gpu_used':False})
            while any(p.poll() is None for p in children):
                if any(p.poll() is not None and p.returncode for p in children):stop('isolated_filtered265_worker_exit')
                time.sleep(3)
            if any(p.returncode for p in children):raise RuntimeError('Isolated worker exit; evidence preserved')
            verify();statuses=collections.Counter();smoke=[]
            for r in frozen['records']:
                value=C.load(Path(r['result_dir'])/'result.json');statuses[value['status'] if value else 'NOT_RUN']+=1
                if r['instance_id'] in frozen['smoke_ids']:smoke.append(value)
            budget_stop=(C.SHARED_BUDGET.parent/'budget_stop.json').exists()
            if scope=='smoke':C.write(C.RUN/'smoke_gate.json',{'passed':len(smoke)==5 and all(r is not None for r in smoke) and not stopped() and not budget_stop,'time':C.utc(),'fixed_smoke_ids':frozen['smoke_ids'],'statuses':[r['status'] if r else 'NOT_RUN' for r in smoke],'accuracy_threshold_used':False,'online_freeze_sha256':C.sha(FREEZE)})
            C.write(C.RUN/(scope+'_complete.json'),{'time':C.utc(),'phase_finished':True,'allocated_total':frozen['eligible_total'],'allocated_new':frozen['allocated_new'],'reused':frozen['reused'],'statuses':dict(statuses),'shared_budget':str(C.SHARED_BUDGET),'shared_budget_stop':budget_stop,'history_and_source_sha_verified':True,'gpu_used':False})
        except Exception as error:stop('filtered265_coordinator_failure',error_type=type(error).__name__,error_message=str(error)[:500]);raise


def launch(scope,execute=False):
    frozen=verify();rows=pending(frozen,scope)
    if not execute:return {'dry_run':True,'scope':scope,'new_cases':len(rows),'max_semantic_requests':len(rows)*7,'shared_budget':str(C.SHARED_BUDGET),'new_budget_created':False}
    paid_gates(frozen,scope)
    logpath=C.RUN/(scope+'_launcher.log');log=logpath.open('a');process=subprocess.Popen([str(C.PYTHON),'-m',PACKAGE+'.runtime','--phase','run','--scope',scope,'--execute','--coordinate'],cwd=C.ROOT,env=worker_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);log.close()
    value={'time':C.utc(),'pid':process.pid,'new_session':True,'scope':scope,'pending':len(rows),'log':str(logpath)};C.write(C.RUN/(scope+'_launcher.json'),value);return value


def tests():
    command=[str(C.PYTHON),'-m','unittest','discover','-s','tests','-p','test_runtime.py','-v'];process=subprocess.run(command,cwd=C.ROOT,env=worker_env(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    value={'time':C.utc(),'passed':process.returncode==0,'output':process.stdout,'source_sha256':source_signature(),'paid_requests':0};C.write(C.RUN/'cpu_tests.json',value)
    if process.returncode:raise RuntimeError('Runtime CPU tests failed: '+process.stdout[-3000:])
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',required=True,choices=['tests','freeze','probe','run']);p.add_argument('--scope',choices=['smoke','full'],default='smoke');p.add_argument('--execute',action='store_true');p.add_argument('--coordinate',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    if a.coordinate and a.phase!='run':raise PermissionError('Internal coordinator is a run phase only')
    if a.phase=='tests':value=tests()
    elif a.phase=='freeze':frozen=freeze();value={'frozen':True,'allocated_total':frozen['eligible_total'],'allocated_new':frozen['allocated_new'],'reused':frozen['reused'],'new_budget_created':False}
    elif a.phase=='probe':value=probe()
    elif a.coordinate:return coordinate(a.scope,a.execute)
    else:value=launch(a.scope,a.execute)
    print(json.dumps(value,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
