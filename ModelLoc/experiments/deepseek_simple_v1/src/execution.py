"""Persistent cohort controller. No stage after P1 can start implicitly."""
import concurrent.futures,contextlib,json,multiprocessing,os,signal,subprocess,time,traceback
from pathlib import Path
from .common import *

def run_one(task):
    job_path,method,config=task;job=read(job_path)
    folder=RUN/job['cohort']/method/job['instance_id'];folder.mkdir(parents=True,exist_ok=True)
    result_path=folder/'result.json'
    if result_path.exists():return {'method':method,'instance_id':job['instance_id'],'status':read(result_path)['status'],'cached':True}
    if (folder/'started.json').exists():
        # Replayed provider calls are allowed only on exact request hash; the
        # full trajectory remains deterministic until the last durable receipt.
        resume=True
    else:write(folder/'started.json',{'created_at':utc(),'job_sha256':sha(job_path),'method':method});resume=False
    began=time.perf_counter()
    os.environ.update(CUDA_VISIBLE_DEVICES='2' if method=='Q-PRUNER' else '',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',
        OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    from .providers import Provider
    provider=Provider(method,job['instance_id'],folder)
    try:
        with (folder/'stdout.log').open('a') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            if method=='D-SIMPLE':
                from .simple_pipeline import run
                result=run(job,provider,folder)
            else:
                from .cosil_adapter import run
                result=run(job,provider,folder,config['pruner'])
    except Exception as e:
        result={'status':'budget_exceeded' if type(e).__name__=='BudgetExceeded' else 'failed',
            'error_type':type(e).__name__,'error_message':str(e)[:600],
            'traceback':traceback.format_exc(),'predicted_files':[],'predicted_functions':[]}
        # Export any partial context from durable trace for honest failure audit.
    result.update(instance_id=job['instance_id'],method=method,cohort=job['cohort'],
        run_id=RUN_ID,repo=job['repo'],base_commit=job['base_commit'],
        elapsed_seconds=time.perf_counter()-began,resumed_exact_receipts=resume,raw_artifact_path=str(folder))
    write(result_path,result)
    return {k:result[k] for k in ['instance_id','method','status']}

def start_qwen():
    import httpx
    try:
        r=httpx.get('http://127.0.0.1:7333/v1/models',timeout=3,trust_env=False)
        if r.status_code==200:
            if not any(m['id']=='llama3' for m in r.json()['data']):raise RuntimeError('Unexpected existing service')
            return None
    except httpx.TransportError:pass
    status=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used','--format=csv,noheader,nounits'],text=True)
    gpu0=next(int(line.split(',')[1]) for line in status.splitlines() if line.split(',')[0].strip()=='0')
    if gpu0>1000:raise RuntimeError('GPU0 occupied; will not evict another task')
    service=RUN/'service';service.mkdir(exist_ok=True)
    log=(service/'qwen7333.log').open('a')
    proc=subprocess.Popen(['bash',str(ROOT/'scripts/start_qwen.sh')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    write(service/'owned_process.json',{'pid':proc.pid,'started_at':utc(),'script':str(ROOT/'scripts/start_qwen.sh')},replace=True)
    for _ in range(300):
        if proc.poll() is not None:raise RuntimeError('Qwen service exited; inspect service log')
        try:
            r=httpx.get('http://127.0.0.1:7333/v1/models',timeout=2,trust_env=False)
            if r.status_code==200:return proc
        except httpx.TransportError:pass
        time.sleep(2)
    os.killpg(proc.pid,signal.SIGTERM);raise RuntimeError('Qwen service startup timeout')

def stop_owned(proc):
    if proc is None:return
    if proc.poll() is None:
        os.killpg(proc.pid,signal.SIGTERM)
        try:proc.wait(timeout=45)
        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
    write(RUN/'service/shutdown.json',{'stopped_at':utc(),'pid':proc.pid,'returncode':proc.returncode,'owned_only':True},replace=True)

def sandbox_batch(batch_file,name):
    # Hide the entire experiment-parent tree, then re-expose only source code,
    # base snapshots, clean jobs, model files, and this run's writable receipts.
    argv=['bwrap','--die-with-parent','--new-session','--unshare-pid','--ro-bind','/','/',
          '--proc','/proc','--dev-bind','/dev','/dev','--tmpfs',str(COSIL.parent),
          '--ro-bind',str(ROOT),str(ROOT),'--bind',str(RUN),str(RUN),
          '--tmpfs',str(ROOT/'evaluator_private'),'--tmpfs',str(ROOT/'manifests'),
          '--tmpfs',str(ROOT/'reports')]
    for name_ in ['afl','code_v3b','code_v5','code_v6','code_v6_canary_v2','code_v6_round2',
                  '.venv-v5','models_v5/Qwen3-Reranker-0.6B','models_v6/SweRankLLM-Small']:
        p=COSIL/name_;argv+=['--ro-bind',str(p),str(p)]
    config=read(ROOT/'configs/resolved_config.json')
    adapter=config['pruner']['adapter_dir'];argv+=['--ro-bind',adapter,adapter]
    if (RUN/'test_chain').exists():argv+=['--tmpfs',str(RUN/'test_chain')]
    env=dict(os.environ,PYTHONPATH=str(ROOT)+':'+str(COSIL),PYTHONDONTWRITEBYTECODE='1',
             HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',
             OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false')
    argv+=['--chdir',str(ROOT),'--',str(COSIL/'.venv-v5/bin/python'),'-m','src.worker_batch',str(batch_file)]
    log=(RUN/'batches'/(name+'.log')).open('a')
    return subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)

def run(cohort):
    if cohort not in ('smoke','lite_pilot'):raise PermissionError('Only P0/P1 authorized')
    from .preflight import verify
    config=verify()
    if cohort=='lite_pilot':
        gate=read(RUN/'smoke_gate.json')
        if not gate['passed']:raise RuntimeError('P0 gate failed: fix before P1')
    rows_=read(ROOT/'manifests'/f'{cohort}.json')['records']
    service=None
    try:
        service=start_qwen()
        batches=[[] for _ in range(6)]
        paid=0
        for rec in rows_:
            for method in config['methods']:
                item={'job':rec['job'],'method':method}
                if method.startswith('D-'):batches[paid%4].append(item);paid+=1
                elif method=='Q-COSIL':batches[4].append(item)
                else:batches[5].append(item)
        processes=[]
        try:
            for i,tasks in enumerate(batches):
                path=RUN/'batches'/f'{cohort}_{i}.json';write(path,{'config':config,'tasks':tasks},replace=True)
                processes.append(sandbox_batch(path,f'{cohort}_{i}'))
            last=-1
            while any(p.poll() is None for p in processes):
                counts={}
                for rec in rows_:
                    for method in config['methods']:
                        p=RUN/cohort/method/rec['instance_id']/'result.json'
                        if p.exists():
                            r=read(p);key=r['method']+'/'+r['status'];counts[key]=counts.get(key,0)+1
                if sum(counts.values())!=last:
                    last=sum(counts.values());print(json.dumps({'cohort':cohort,'completed':last,'counts':counts}),flush=True)
                    write(RUN/f'{cohort}_progress.json',{'updated_at':utc(),'completed':last,'allocated':len(rows_)*4,'counts':counts},replace=True)
                time.sleep(5)
            if any(p.returncode for p in processes):raise RuntimeError('Isolated worker batch failed; inspect batches logs')
        finally:
            for p in processes:
                if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
            for p in processes:
                try:p.wait(timeout=20)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL)
    finally:stop_owned(service)
    verify()
    if cohort=='smoke':
        statuses=[read(RUN/cohort/m/r['instance_id']/'result.json') for r in rows_ for m in config['methods']]
        passed=all(r['status']=='complete' for r in statuses)
        chain=read(RUN/'test_chain/receipt.json') if (RUN/'test_chain/receipt.json').exists() else {}
        passed=passed and chain.get('execution_chain_passed',False)
        write(RUN/'smoke_gate.json',{'passed':passed,'completed_at':utc(),'statuses':[
            {k:r[k] for k in ['instance_id','method','status']} for r in statuses],
            'test_chain_passed':chain.get('execution_chain_passed',False),'no_accuracy_threshold_used':True},replace=True)
