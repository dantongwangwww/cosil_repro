"""Minimal isolated filtered265 worker. No screen, gold evaluator, or historical rows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from . import common as C

FORBIDDEN={'gold','patch','test_patch','FAIL_TO_PASS','PASS_TO_PASS','hints_text'}
CLEAN_KEYS={'instance_id','repo','base_commit','problem_statement','cohort','snapshot','paths','code_index','structure'}


def probe(batch):
    from unittest.mock import patch
    with patch('socket.socket',side_effect=RuntimeError('Probe network forbidden')),patch('socket.create_connection',side_effect=RuntimeError('Probe network forbidden')):
        import tiktoken
        from tokenizers import Tokenizer
        encoding=bool(tiktoken.get_encoding('o200k_base').encode('Offline filtered265 probe.'))
        official=bool(Tokenizer.from_file(str(C.ROOT/'resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json')).encode('Offline filtered265 probe.').ids)
    jobs=[C.load(t['job']) for t in batch['tasks']];ids={j['instance_id'] for j in jobs}
    allowed_finance={'budget.json','budget.lock','budget_stop.json','dsimple_v2_safety_stop.json'}|{'dsimple_v2_api_slot_'+str(i)+'.lock' for i in range(4)}
    finance_metadata_hidden=True
    for path in C.SHARED_BUDGET.parent.iterdir():
        if path.name in allowed_finance or '.v2tmp.' in path.name:continue
        if path.is_dir():finance_metadata_hidden=finance_metadata_hidden and not any(path.iterdir())
        else:
            try:hidden=path.read_bytes()==b''
            except PermissionError:hidden=True  # A masked device may be denied by host device policy.
            finance_metadata_hidden=finance_metadata_hidden and hidden
    checks={
        'new_online_code_visible':(C.ROOT/'filtered265/worker.py').is_file(),
        'screen_and_gold_code_hidden':not (C.ROOT/'filtered265/screen.py').exists() and not (C.ROOT/'filtered265/gold.py').exists() and not (C.ROOT/'filtered265/prepare.py').exists() and not (C.ROOT/'filtered265/runtime.py').exists(),
        'frozen_inference_only':(C.FROZEN/'src/simple_pipeline.py').is_file() and not (C.FROZEN/'src/dataset_adapter.py').exists() and not (C.FROZEN/'src/gold_mapping.py').exists(),
        'new_private_hidden':not any((C.ROOT/'evaluator_private').iterdir()),
        'manifests_hidden':not any((C.ROOT/'manifests').iterdir()),
        'reports_hidden':not any((C.ROOT/'reports').iterdir()),
        'configs_hidden':not any((C.ROOT/'configs').iterdir()),
        'old_p1_runs_private_hidden':not (C.FROZEN/'runs').exists() and not (C.FROZEN/'evaluator_private').exists(),
        'old100_project_hidden':not C.PREVIOUS.exists(),
        'prior_v2_project_hidden':not C.PRIOR_V2.exists(),
        'old200_code_config_hidden':not (C.ADDITIONAL/'supplement_v1').exists() and not (C.ADDITIONAL/'configs').exists(),
        'old200_finance_only_metadata_masked':finance_metadata_hidden,
        'no_model_weights':not (C.COSIL/'models_v6').exists() and not any(Path('/home/wdt/models').iterdir()),
        'home_cache_empty':not any((Path.home()/'.cache').iterdir()),
        'native_git_results_hidden':not (C.COSIL/'.git').exists() and not (C.COSIL/'results').exists(),
        'only_batch_jobs':{p.name for p in (C.ROOT/'jobs').iterdir()}==ids,
        'only_batch_snapshots':{p.name for p in (C.ROOT/'snapshots').iterdir()}==ids,
        'clean_new_jobs':all(set(j)==CLEAN_KEYS and j['cohort']==C.COHORT for j in jobs),
        'selected_base_visible':all(Path(j['snapshot']).is_dir() and Path(j['structure']).is_file() and Path(j['code_index']).is_file() for j in jobs),
        'global_manifest_not_visible':not (C.RUN/'online_freeze.json').exists() and not (C.RUN/'preparation_progress.json').exists(),
        'shared_existing_ledger_visible':C.SHARED_BUDGET.is_file() and C.load(C.SHARED_BUDGET)['stage_cap_usd']==5.,
        'no_provider_or_gpu_module':not any(n in sys.modules for n in ['openai','src.providers','torch','transformers']),
        'cuda_disabled':os.environ.get('CUDA_VISIBLE_DEVICES')=='',
        'o200k_offline':encoding,'official_tokenizer_offline':official,
    }
    value={'passed':all(checks.values()),'checks':checks,'time':C.utc(),'paid_requests':0,'gpu_used':False,'selected_jobs':len(jobs)}
    print(json.dumps(value,ensure_ascii=False),flush=True)
    if not value['passed']:raise RuntimeError('filtered265 isolation probe failed: '+','.join(k for k,v in checks.items() if not v))
    return value


def verify_batch(batch):
    if batch.get('run_id')!=C.RUN_ID or batch.get('cohort')!=C.COHORT or batch.get('methods')!=['D-SIMPLE']:raise PermissionError('Wrong filtered265 worker namespace')
    if batch['shared_budget_contract']['logical_budget']!=str(C.SHARED_BUDGET):raise PermissionError('Worker attempted another budget')
    for path,expected in batch['worker_online_sha256'].items():
        if C.sha(path)!=expected:raise RuntimeError('Mounted inference source changed: '+path)
    for task in batch['tasks']:
        job=C.load(task['job'])
        if set(job)!=CLEAN_KEYS or job['cohort']!=C.COHORT or job['instance_id']!=task['instance_id']:raise RuntimeError('Unsafe filtered265 job')
        output=Path(task['result_dir'])
        if output!=C.RUN/C.COHORT/'D-SIMPLE'/task['instance_id']:raise PermissionError('filtered265 result path escaped allocated case')
        expected_inputs={str(Path(task['job'])),job['code_index'],job['structure']}
        if set(task['data_sha256'])!=expected_inputs:raise RuntimeError('Unexpected input mapping')
        for path,expected in {**task['data_sha256'],**task['snapshot_sha256']}.items():
            if C.sha(path)!=expected:raise RuntimeError('Frozen filtered265 inference input changed: '+path)


def work(batch_path,execute=False,probe_only=False):
    batch=C.load(batch_path)
    try:observed=probe(batch)
    except Exception as error:
        if execute:
            from .bootstrap import stop
            stop('worker_isolation_failure',error_type=type(error).__name__,error_message=str(error)[:500])
        raise
    if probe_only:return observed
    if not execute:raise PermissionError('Paid filtered265 worker requires explicit --execute')
    from .bootstrap import install,stop,stopped
    try:
        verify_batch(batch);execution,provider=install(batch['shared_budget_contract'])
        for task in batch['tasks']:
            if stopped() or (C.SHARED_BUDGET.parent/'budget_stop.json').exists():break
            if shutil.disk_usage(Path(task['result_dir']).resolve()).free<2*1024**3:
                C.write(Path(batch['worker_receipt_dir'])/'resource_pause.json',{'time':C.utc(),'reason':'actual output volume below 2GiB'});break
            for path,expected in {**task['data_sha256'],**task['snapshot_sha256']}.items():
                if C.sha(path)!=expected:raise RuntimeError('filtered265 input drift before execution: '+path)
            began=time.process_time();result=execution.run_one((task['job'],'D-SIMPLE',batch['config'],task.get('enqueued_utc')));cpu=time.process_time()-began
            output=Path(task['result_dir'])/'result.json';saved=C.load(output)
            if saved is not None and not result.get('cached'):
                saved.update(process_cpu_seconds=cpu,process_cpu_scope='frozen P1 run_one only; input verification excluded',gpu_used=False,shared_budget_path=str(C.SHARED_BUDGET))
                C.write(output,saved)
            print(json.dumps(result,ensure_ascii=False),flush=True)
    except Exception as error:
        stop('worker_integrity_failure',error_type=type(error).__name__,error_message=str(error)[:500]);raise
    finally:C.write(Path(batch['worker_receipt_dir'])/'finished.json',{'time':C.utc(),'worker_pid':os.getpid(),'finished':True})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch');p.add_argument('--probe',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args();work(a.batch,a.execute,a.probe)

if __name__=='__main__':main()
