"""One isolated serial API worker; probe performs no provider/model imports."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from . import common as C

FORBIDDEN={'gold','patch','test_patch','FAIL_TO_PASS','PASS_TO_PASS','hints_text'}


def probe(batch):
    # Prove both tokenizers work with network creation blocked, not just that
    # cache paths happen to exist in the isolated filesystem.
    from unittest.mock import patch
    with patch('socket.create_connection',side_effect=RuntimeError('Probe network is forbidden')),patch('socket.socket',side_effect=RuntimeError('Probe network is forbidden')):
        import tiktoken
        from tokenizers import Tokenizer
        cache_ok=bool(tiktoken.get_encoding('o200k_base').encode('Offline CPU probe.'))
        tokenizer_ok=bool(Tokenizer.from_file(str(C.ROOT/'resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json')).encode('Offline CPU probe.').ids)
    jobs=[C.load(t['job']) for t in batch['tasks']]
    selected={j['instance_id'] for j in jobs}
    checks={
        'current_code_visible':(C.ROOT/'supplement_v1/worker.py').is_file(),
        'frozen_src_visible':(C.FROZEN/'src/simple_pipeline.py').is_file(),
        'old_runs_hidden':not (C.FROZEN/'runs').exists() and not C.PREVIOUS.exists(),
        'old_evaluator_hidden':not (C.FROZEN/'evaluator_private').exists(),
        'new_private_hidden':not any((C.ROOT/'evaluator_private').iterdir()),
        'manifests_hidden':not any((C.ROOT/'manifests').iterdir()),
        'reports_hidden':not any((C.ROOT/'reports').iterdir()),
        'configs_hidden':not any((C.ROOT/'configs').iterdir()),
        'native_git_results_models_hidden':not (C.COSIL/'.git').exists() and not (C.COSIL/'results').exists() and not (C.COSIL/'models_v6').exists(),
        'external_model_weights_hidden':not any(Path('/home/wdt/models').iterdir()),
        'archives_hidden':not Path('/tmp/modelloc_swerebench300_20261022/archives').exists(),
        'only_selected_jobs_mounted':{p.name for p in (C.ROOT/'jobs').iterdir()}==selected,
        'only_selected_logical_snapshots_mounted':{p.name for p in (C.ROOT/'snapshots').iterdir()}==selected,
        'clean_job_schema':all(not FORBIDDEN.intersection(j) and j['cohort']==C.COHORT for j in jobs),
        'selected_sources_visible':all(Path(j['snapshot']).is_dir() and Path(j['code_index']).is_file() and Path(j['structure']).is_file() for j in jobs),
        'no_provider_or_gpu_import':not any(v in sys.modules for v in ['src.providers','openai','torch','transformers']),
        'gpu_disabled':os.environ.get('CUDA_VISIBLE_DEVICES')=='',
        'o200k_cache_works_without_network':cache_ok,
        'official_tokenizer_works_without_network':tokenizer_ok,
    }
    result={'passed':all(checks.values()),'checks':checks,'paid_requests':0,'model_forwards':0,'time':C.utc(),'selected_jobs':len(jobs)}
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if not result['passed']:raise RuntimeError('Isolation probe failed: '+','.join(k for k,v in checks.items() if not v))
    return result


def verify_batch(batch):
    if batch.get('run_id')!=C.RUN_ID or batch.get('cohort')!=C.COHORT:raise PermissionError('Wrong batch namespace')
    if batch.get('methods')!=['D-SIMPLE'] or batch.get('budget_usd')!=C.BUDGET_USD:raise PermissionError('Wrong method or budget')
    for path,expected in batch['online_sha256'].items():
        if Path(path)==C.ROOT/'configs/resolved_config.json':
            actual=hashlib.sha256((json.dumps(batch['config'],ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()).hexdigest()
        else:actual=C.sha(path)
        if actual!=expected:raise RuntimeError('Mounted online source drift: '+path)
    for task in batch['tasks']:
        job=C.load(task['job'])
        if job['cohort']!=C.COHORT or FORBIDDEN.intersection(job):raise PermissionError('Invalid clean job')
        for path,expected in task['data_sha256'].items():
            if C.sha(path)!=expected:raise RuntimeError('Mounted clean data drift: '+path)
        for path,expected in task['snapshot_sha256'].items():
            if C.sha(path)!=expected:raise RuntimeError('Mounted base snapshot drift: '+path)
    return True


def work(batch_file,execute=False,probe_only=False):
    batch=C.load(batch_file)
    if batch is None:raise RuntimeError('Batch file missing')
    try:result=probe(batch)
    except Exception as error:
        if execute:
            from .bootstrap import stop
            stop('worker_isolation_failure',error_type=type(error).__name__,error_message=str(error)[:500])
        raise
    if probe_only:return result
    if not execute:raise PermissionError('Worker paid execution requires --execute')
    from .bootstrap import install,stop
    try:
        verify_batch(batch)
        execution,provider=install()
        for task in batch['tasks']:
            if any((C.RUN/name).exists() for name in ['emergency_stop.json','budget_stop.json','resource_pause.json']):break
            output_volume=C.RUN.resolve()
            free=shutil.disk_usage(output_volume).free
            if free<2*1024**3:
                C.write(C.RUN/'resource_pause.json',{'time':C.utc(),'reason':'actual new RUN output disk free below 2GiB','checked_path':str(output_volume),'free_bytes':free});break
            # Recheck each task at its point of use; method inputs are immutable.
            for path,expected in {**task['data_sha256'],**task['snapshot_sha256']}.items():
                if C.sha(path)!=expected:raise RuntimeError('Input changed before case: '+path)
            began=time.process_time()
            answer=execution.run_one((task['job'],'D-SIMPLE',batch['config'],task.get('enqueued_utc')))
            cpu=time.process_time()-began
            output=C.RUN/C.COHORT/'D-SIMPLE'/task['instance_id']/'result.json'
            saved=C.load(output)
            if saved and not answer.get('cached'):
                saved.update(process_cpu_seconds=cpu,process_cpu_scope='frozen run_one worker CPU; excludes pre-case integrity verification',gpu_used=False)
                C.write(output,saved)
            print(json.dumps(answer,ensure_ascii=False),flush=True)
            # Ordinary per-case model/data failures remain in their denominator;
            # global contract markers, if any, stop the next queued case.
    except Exception as error:
        stop('worker_integrity_or_runtime_failure',error_type=type(error).__name__,error_message=str(error)[:500]);raise
    finally:
        C.write(Path(batch_file).with_suffix('.finished.json'),{'time':C.utc(),'worker_pid':os.getpid(),'finished':True})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch');p.add_argument('--probe',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
    work(a.batch,execute=a.execute,probe_only=a.probe)

if __name__=='__main__':main()
