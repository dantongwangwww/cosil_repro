"""Isolated new-run workers and an explicitly owned Qwen service lifecycle."""
import concurrent.futures,contextlib,json,os,signal,subprocess,time,traceback
from pathlib import Path
from .common import *

def run_one(task):
    job=read(task['job']);variant=task['variant'];out=RUN/'lite_pilot'/variant/job['instance_id']
    out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():return read(out/'result.json')['status']
    started=utc();began=time.perf_counter()
    from .provider import Provider,BudgetExceeded
    provider=Provider(task.get('base_method',variant),job['instance_id'],out)
    try:
        if variant.startswith('A-'):
            from .ablation import build_messages,parse_final
            frozen=read(RUN/'frozen'/job['instance_id']/'frozen_context.json')
            item=build_messages(job,frozen)[variant]
            if item['status']!='ready':result={'status':item['status'],'predicted_functions':[],'reason':'common context cap without truncation'}
            else:
                response=provider.ask(item['messages'],'function_localization',max_tokens=4096,json_mode=True,temperature=0.)
                result=parse_final(response['content'],frozen);result.update(raw_output=response['content'],usage=response['usage'])
            result.update(candidate_sha256=frozen['manifest']['candidate_sha256'],context_stats={k:v for k,v in item.items() if k!='messages'})
        else:
            from .structured import run
            base=task['base_method'];upstream=RUN/'upstream'/base/job['instance_id']
            job['frozen_upstream']=str(upstream)
            status=read(upstream/'upstream_status.json')
            if status['status']!='ready':result={'status':'upstream_failure','reason':status['reason'],'predicted_functions':[],'predicted_files':status['files']}
            else:
                config=read(RUN/'resolved_config.json')
                result=run(job,provider,out,config['pruner'])
    except Exception as e:
        result={'status':'budget_exceeded' if isinstance(e,BudgetExceeded) else 'failed','error_type':type(e).__name__,'error_message':str(e)[:700],
                'traceback':traceback.format_exc(),'predicted_functions':[]}
    result.update(instance_id=job['instance_id'],repo=job['repo'],base_commit=job['base_commit'],method=variant,
                  processing_started_utc=started,processing_ended_utc=utc(),elapsed_seconds=time.perf_counter()-began,run_id=RUN_ID)
    write(out/'result.json',result)
    print(json.dumps({'method':variant,'instance_id':job['instance_id'],'status':result['status']}),flush=True)
    return result['status']

def worker(batch):
    
    for hidden in ['evaluator_private','manifests','reports','analysis','configs']:
        if list((ROOT/hidden).iterdir()):raise RuntimeError('Worker namespace exposes hidden '+hidden)
    tasks=read(batch)['tasks'];methods={t['variant'] for t in tasks}
    local=any(t.startswith('Q-') for t in methods)
    os.environ.update(CUDA_VISIBLE_DEVICES='2' if 'Q-PRUNER-STRUCTURED' in methods else '',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    # Pure API batches may run concurrently; Qwen/pruner follows serial original state.
    if all(v.startswith('A-') for v in methods):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run_one,tasks))
    else:
        for task in tasks:run_one(task)

def sandbox_batch(tasks,name):
    path=RUN/'batches'/(name+'.json');write(path,{'tasks':tasks},replace=True)
    (RUN/'shared_cache/tiktoken').mkdir(parents=True,exist_ok=True)
    argv=['bwrap','--die-with-parent','--new-session','--unshare-pid','--ro-bind','/','/','--proc','/proc',
          '--dev-bind','/dev','/dev','--tmpfs','/tmp','--tmpfs',str(COSIL.parent),
          '--ro-bind',str(ROOT),str(ROOT),'--tmpfs',str(ROOT/'runs'),'--bind',str(RUN),str(RUN),
          '--tmpfs',str(ROOT/'evaluator_private'),'--tmpfs',str(ROOT/'manifests'),'--tmpfs',str(ROOT/'reports'),
          '--tmpfs',str(ROOT/'analysis'),'--tmpfs',str(ROOT/'configs'),'--tmpfs',str(ROOT/'jobs'),'--tmpfs',str(ROOT/'snapshots')]
    # Only the authorized 50 clean jobs and base snapshots are visible. No gold/report/test mounts.
    for rec in records():
        job=read(rec['job'])
        for p in [Path(rec['job']).parent,Path(job['snapshot'])]:argv+=['--ro-bind',str(p),str(p)]
    # New outputs which contain evaluator labels are always hidden from workers.
    for hidden in ['reports','audit']:
        (RUN/hidden).mkdir(exist_ok=True);argv+=['--tmpfs',str(RUN/hidden)]
    for rel in ['afl','get_repo_structure','code_v3b','code_v5','code_v6','code_v6_canary_v2','code_v6_round2',
                '.venv-v5','models_v5/Qwen3-Reranker-0.6B','models_v6/SweRankLLM-Small']:
        p=COSIL/rel;argv+=['--ro-bind',str(p),str(p)]
    adapter=read(RUN/'resolved_config.json')['pruner']['adapter_dir'];argv+=['--ro-bind',adapter,adapter]
    env=dict(os.environ,PYTHONPATH=str(ROOT)+':'+str(COSIL),PYTHONDONTWRITEBYTECODE='1',
        TIKTOKEN_CACHE_DIR=str(RUN/'shared_cache/tiktoken'),TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
    argv+=['--chdir',str(ROOT),'--',str(COSIL/'.venv-v5/bin/python'),'-m','context_tool_diagnostic.runtime',str(path)]
    log=(RUN/'batches'/(name+'.log')).open('a')
    return subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)

def wait_batches(procs):
    try:
        while any(p.poll() is None for p in procs):time.sleep(2)
        if any(p.returncode for p in procs):raise RuntimeError('Isolated worker exit; inspect batches logs before any retry')
    finally:
        for p in procs:
            if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)

def check_gpu_free(index):
    import csv,io
    txt=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True)
    devices=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used','--format=csv,noheader,nounits'],text=True)
    dev=next(row for row in csv.reader(io.StringIO(devices)) if int(row[0])==index)
    peers=[r for r in csv.reader(io.StringIO(txt)) if r and r[0].strip()==dev[1].strip()]
    if peers or int(dev[2])>1000:raise RuntimeError('GPU'+str(index)+' occupied; no eviction')
    return {'gpu':index,'memory_used_mib':int(dev[2]),'compute_processes':peers}

def start_qwen():
    import httpx
    try:
        r=httpx.get('http://127.0.0.1:7333/v1/models',timeout=3,trust_env=False)
        if r.status_code==200:raise RuntimeError('Existing service requires owner/config verification; refuse silent reuse')
    except httpx.TransportError:pass
    checks=[check_gpu_free(0),check_gpu_free(2)]
    service=RUN/'service';service.mkdir(exist_ok=True);began=time.perf_counter()
    log=(service/'qwen7333.log').open('a')
    proc=subprocess.Popen(['bash',str(ROOT/'scripts/start_qwen.sh')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    write(service/'owned_process.json',{'pid':proc.pid,'started_at':utc(),'script':str(ROOT/'scripts/start_qwen.sh'),'gpu_checks':checks},replace=True)
    for _ in range(300):
        if proc.poll() is not None:raise RuntimeError('Owned service exited')
        try:
            r=httpx.get('http://127.0.0.1:7333/v1/models',timeout=2,trust_env=False)
            if r.status_code==200:
                if not any(m['id']=='llama3' for m in r.json()['data']):raise RuntimeError('Qwen alias mismatch')
                write(service/'startup_timing.json',{'ready_at':utc(),'seconds':time.perf_counter()-began},replace=True);return proc
        except httpx.TransportError:pass
        time.sleep(2)
    stop_owned(proc);raise RuntimeError('Owned service timeout')

def stop_owned(proc):
    if proc and proc.poll() is None:
        os.killpg(proc.pid,signal.SIGTERM)
        try:proc.wait(timeout=45)
        except subprocess.TimeoutExpired:raise RuntimeError('Owned service slow shutdown; not escalating to unrelated process')
    if proc:write(RUN/'service/shutdown.json',{'pid':proc.pid,'time':utc(),'returncode':proc.returncode,'owned_only':True},replace=True)

if __name__=='__main__':
    import sys
    worker(sys.argv[1])
