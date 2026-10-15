"""Resume unstarted cases across identical Qwen replicas, draining original tasks."""
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime
from pathlib import Path
import fcntl
import hashlib
import json
import os
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT))
import run_full_audit as run


def init_worker(gpu,endpoint):
    os.environ['OPENAI_API_BASE']=endpoint
    os.environ['COSIL_AUDIT_GPU']=str(gpu)
    import CoSIL.util.model as module
    completion=module.completion
    def routed(**config):
        config['api_base']=endpoint
        config['api_key']='empty'
        return completion(**config)
    module.completion=routed
    emit=run.Audit.event
    def event(self,kind,**fields):
        fields.setdefault('gpu_index',gpu)
        fields.setdefault('api_base',endpoint)
        return emit(self,kind,**fields)
    run.Audit.event=event


def original_done(transition):
    pending=[]
    for iid in transition['reserved_original_cases']:
        if not (run.WORK/'func/cases'/f'{iid}.json').exists() and not (run.WORK/'func/failures'/f'{iid}.json').exists():
            pending.append(iid)
    return not pending


def stop_original(transition):
    parent=transition['original_coordinator_pid']
    for pid in transition['original_workers']:
        p=Path('/proc')/str(pid)
        if p.exists():
            assert 'run_full_audit.py' in (p/'cmdline').read_bytes().decode().replace('\x00',' ')
            os.kill(pid,signal.SIGTERM)
    p=Path('/proc')/str(parent)
    if p.exists():
        assert 'run_full_audit.py' in (p/'cmdline').read_bytes().decode().replace('\x00',' ')
        os.kill(parent,signal.SIGTERM)
        os.kill(parent,signal.SIGCONT)
    transition['original_drained_at']=run.now()
    transition['status']='running_four_replicas'
    run.atomic(run.WORK/'parallelism_transition.json',transition)


def main():
    from datasets import load_from_disk
    import subprocess
    lock=(run.WORK/'parallel_runner.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    transition=json.loads((run.WORK/'parallelism_transition.json').read_text())
    verification=json.loads((run.WORK/'replica_verification.json').read_text())
    assert verification['all_new_replicas_match']
    frozen=json.loads((run.WORK/'audit_manifest.json').read_text())
    for name,sha in frozen['source_sha256'].items():assert run.digest(ROOT/name)==sha,name
    for iid,sha in transition['preserved_completed_function_cases'].items():
        assert run.digest(run.WORK/'func/cases'/f'{iid}.json')==sha,iid
    parent=Path('/proc')/str(transition['original_coordinator_pid'])
    if parent.exists():
        assert '\nState:\tT' in (parent/'status').read_text(),'Original coordinator must be paused'
    reserved=[]
    for p in (run.WORK/'func/events').glob('*.jsonl'):
        if not (run.WORK/'func/cases'/f'{p.stem}.json').exists() and not (run.WORK/'func/failures'/f'{p.stem}.json').exists():
            reserved.append(p.stem)
    transition['reserved_original_cases']=reserved
    transition['parallel_driver_started_at']=run.now()
    transition['driver_sha256']=run.digest(Path(__file__))
    run.atomic(run.WORK/'parallelism_transition.json',transition)
    bugs=list(load_from_disk(os.environ['COSIL_DATASET']))
    ids=frozen['instances']
    assert len(ids)==300 and {b['instance_id'] for b in bugs}==set(ids)
    tasks=[('func',b) for b in bugs if b['instance_id'] not in reserved
           and not (run.WORK/'func/cases'/f"{b['instance_id']}.json").exists()
           and not (run.WORK/'func/failures'/f"{b['instance_id']}.json").exists()]
    iterator=iter(tasks)
    pending={}
    pools={gpu:ProcessPoolExecutor(max_workers=2,initializer=init_worker,
            initargs=(gpu,url)) for gpu,url in enumerate(transition['new_endpoints'].values())}
    original_stopped=False
    exhausted=False
    runner_lock=None
    try:
        while pending or not exhausted or not original_stopped:
            if not original_stopped and original_done(transition):
                stop_original(transition)
                original_stopped=True
                runner_lock=(run.WORK/'audit_runner.lock').open('a')
                fcntl.flock(runner_lock,fcntl.LOCK_EX)
            for gpu,pool in pools.items():
                if gpu==0 and not original_stopped:continue
                active=sum(value==gpu for value in pending.values())
                while active<2 and not exhausted:
                    task=next(iterator,None)
                    if task is None:
                        exhausted=True
                        break
                    future=pool.submit(run.case,task)
                    pending[future]=gpu
                    active+=1
            if pending:
                done,_=wait(pending,timeout=15,return_when=FIRST_COMPLETED)
                for future in done:
                    gpu=pending.pop(future)
                    result=future.result()
                    for name,sha in frozen['source_sha256'].items():assert run.digest(ROOT/name)==sha,name
                    print(json.dumps({'gpu':gpu,**{k:result[k] for k in ('phase','instance_id','status')}},ensure_ascii=False),flush=True)
                    run.aggregate('func',ids)
            else:
                time.sleep(5)
            run.status('四卡运行函数级',gpus=[0,1,2,3],workers_per_gpu=2,
                       original_tasks_drained=original_stopped)
        run.aggregate('func',ids)
        for iid in ids:
            assert (run.WORK/'func/cases'/f'{iid}.json').exists() or (run.WORK/'func/failures'/f'{iid}.json').exists(),iid
        for iid,sha in transition['preserved_completed_function_cases'].items():
            assert run.digest(run.WORK/'func/cases'/f'{iid}.json')==sha,iid
        transition['finished_at']=run.now();transition['status']='complete'
        run.atomic(run.WORK/'parallelism_transition.json',transition)
        run.status('分析问题与生成报告',gpus=[0,1,2,3],workers_per_gpu=2)
        subprocess.run([sys.executable,str(ROOT/'scripts/analyze_full_audit.py')],cwd=ROOT,check=True)
        run.status('完成',gpus=[0,1,2,3],workers_per_gpu=2)
    except Exception as exc:
        run.status('停止并保留证据',error=type(exc).__name__,message=str(exc))
        raise
    finally:
        for pool in pools.values():pool.shutdown(wait=True)


if __name__=='__main__':main()
