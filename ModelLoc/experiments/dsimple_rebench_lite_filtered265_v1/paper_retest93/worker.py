"""Isolated D-SIMPLE paper-parameter worker; no evaluator or historical results mounted."""
import argparse,json,os,shutil,sys,time
from pathlib import Path
from . import common as C

def probe(batch):
 from unittest.mock import patch
 with patch('socket.socket',side_effect=RuntimeError('Probe network forbidden')),patch('socket.create_connection',side_effect=RuntimeError('Probe network forbidden')):
  import tiktoken
  from tokenizers import Tokenizer
  tok=bool(tiktoken.get_encoding('o200k_base').encode('Paper93 offline probe'))
  official=bool(Tokenizer.from_file(str(C.ROOT/'resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json')).encode('Paper93 offline probe').ids)
 from .bootstrap import set_policy,stopped
 set_policy(batch['policy']);finance_contract_ok=not stopped()
 jobs=[C.load(t['job']) for t in batch['tasks']];ids={j['instance_id'] for j in jobs}
 checks={'original_financial_inode_and_stop_contracts':finance_contract_ok,'new_pipeline_visible':(C.PACKAGE_ROOT/'pipeline.py').is_file(),'offline_coordinator_hidden':not (C.PACKAGE_ROOT/'prepare.py').exists() and not (C.PACKAGE_ROOT/'runtime.py').exists() and not (C.PACKAGE_ROOT/'reporting.py').exists(),'gold_private_hidden':not any((C.ROOT/'evaluator_private').iterdir()),'reports_manifests_configs_hidden':all(not any((C.ROOT/n).iterdir()) for n in ['reports','manifests','configs']),'old_results_hidden':not C.OLD_RUN.exists() and not C.PREVIOUS.exists() and not C.PRIOR_V2.exists(),'old_additional_code_hidden':not (C.ADDITIONAL/'supplement_v1').exists(),'old_filtered_resume_code_hidden':not (C.ROOT/'filtered265').exists() and not (C.ROOT/'resume65').exists(),'frozen_inference_only':(C.FROZEN/'src/execution.py').is_file() and not (C.FROZEN/'src/dataset_adapter.py').exists(),'only_batch_jobs':{p.name for p in C.JOBS.iterdir()}==ids,'only_batch_snapshots':{p.name for p in C.SNAPSHOTS.iterdir()}==ids,'clean_jobs':all(set(j)==C.CLEAN_KEYS and j['cohort']==C.COHORT for j in jobs),'source_index_visible':all(Path(j['snapshot']).is_dir() and Path(j['code_index']).is_file() and Path(j['structure']).is_file() for j in jobs),'home_cache_empty':not any((Path.home()/'.cache').iterdir()),'model_cache_hidden':not any(Path('/home/wdt/models').iterdir()) and not (C.COSIL/'models_v6').exists(),'native_git_hidden':not (C.COSIL/'.git').exists(),'finance_original_visible':C.SHARED_BUDGET.is_file() and C.load(C.SHARED_BUDGET)['stage_cap_usd']==5,'no_provider_gpu_imports':not any(n in sys.modules for n in ['openai','src.providers','torch','transformers']),'cuda_disabled':os.environ.get('CUDA_VISIBLE_DEVICES')=='','offline_o200k':tok,'offline_official_tokenizer':official}
 value={'time':C.utc(),'passed':all(checks.values()),'checks':checks,'model_calls':0,'gpu_used':False};print(json.dumps(value),flush=True)
 if not value['passed']:raise RuntimeError('Paper93 isolation probe failed: '+','.join(k for k,v in checks.items() if not v))
 return value

def verify_batch(batch):
 if batch['run_id']!=C.RUN_ID or batch['cohort']!=C.COHORT or len(batch['policy']['allowed_ids'])!=93:raise PermissionError('Wrong fixed93 namespace')
 for p,h in batch['worker_online_sha256'].items():
  if C.sha(p)!=h:raise RuntimeError('Worker source drift: '+p)
 for task in batch['tasks']:
  job=C.load(task['job'])
  if set(job)!=C.CLEAN_KEYS or job['cohort']!=C.COHORT or job['instance_id']!=task['instance_id'] or job['instance_id'] not in batch['policy']['allowed_ids']:raise PermissionError('Job outside fixed93')
  if Path(task['result_dir'])!=C.RUN/C.COHORT/'D-SIMPLE'/job['instance_id']:raise PermissionError('Case output escaped')
  for p,h in {**task['data_sha256'],**task['snapshot_sha256']}.items():
   if C.sha(p)!=h:raise RuntimeError('New frozen input drift: '+p)

def work(path,execute=False,probe_only=False):
 batch=C.load(path)
 try:observed=probe(batch)
 except Exception as error:
  if execute:
   from .bootstrap import stop
   stop('paper93_isolation_failure',error_type=type(error).__name__,error_message=str(error)[:500])
  raise
 if probe_only:return observed
 if not execute:raise PermissionError('Explicit --execute and root activation required')
 from .bootstrap import install,stop,stopped
 try:
  verify_batch(batch);execution,provider=install(batch['policy'])
  for task in batch['tasks']:
   if stopped():break
   if shutil.disk_usage(Path(task['result_dir']).resolve()).free<2*1024**3:
    C.write(Path(batch['worker_receipt_dir'])/'resource_pause.json',{'time':C.utc(),'reason':'actual output volume below2GiB'});break
   for p,h in {**task['data_sha256'],**task['snapshot_sha256']}.items():
    if C.sha(p)!=h:raise RuntimeError('Input drift before case')
   began=time.process_time();result=execution.run_one((task['job'],'D-SIMPLE',batch['config'],task['enqueued_utc']));cpu=time.process_time()-began
   out=Path(task['result_dir'])/'result.json';saved=C.load(out)
   if saved and not result.get('cached'):
    saved.update(process_cpu_seconds=cpu,gpu_used=False,paper_parameter_retest=True,fresh_retest_no_old_partial_replay=True,shared_budget_path=str(C.SHARED_BUDGET));C.write(out,saved)
   print(json.dumps(result),flush=True)
 except Exception as e:
  stop('paper93_worker_integrity_failure',error_type=type(e).__name__,error_message=str(e)[:500]);raise
 finally:C.write(Path(batch['worker_receipt_dir'])/'finished.json',{'time':C.utc(),'pid':os.getpid(),'finished':True})

def main():
 p=argparse.ArgumentParser();p.add_argument('batch');p.add_argument('--probe',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args();work(a.batch,a.execute,a.probe)
if __name__=='__main__':main()
