"""Prepare/freeze/probe explicit independent paper93 run; never auto-activates API."""
import argparse,collections,copy,fcntl,json,os,subprocess,time
from pathlib import Path
from . import common as C
from .bootstrap import digest
CONFIG=C.RUN/'config.json';FREEZE=C.RUN/'online_freeze.json';BASELINE=C.RUN/'financial_baseline.json'
OLD_NAMES=['__init__.py','common.py','code_index.py','providers.py','execution.py','token_counter.py']
VISIBLE=['__init__.py','common.py','bootstrap.py','transport.py','worker.py','pipeline.py']
ALL=VISIBLE+['runtime.py','prepare.py']
ALLOWED={'budget.json','budget.lock','budget_stop.json','user_pause.json','emergency_stop.json','dsimple_v2_safety_stop.json'}|{'dsimple_v2_api_slot_'+str(i)+'.lock' for i in range(4)}

def source_signature():return {str(C.PACKAGE_ROOT/n):C.sha(C.PACKAGE_ROOT/n) for n in ALL}
def financial_contract():
 st=C.SHARED_BUDGET.parent.stat()
 return {'logical_budget':str(C.SHARED_BUDGET),'resolved_budget':str(C.SHARED_BUDGET.resolve()),'parent_device':st.st_dev,'parent_inode':st.st_ino,'cap_usd':5.}
def once(p,value):C.write(p,value,replace=False)

def freeze():
 if FREEZE.exists():return verify()
 manifest=C.load(C.MANIFEST);roster=C.load(C.ROSTER)
 if not manifest or manifest['n']!=93 or any(r.get('preparation_status')!='complete' for r in manifest['records']):raise RuntimeError('All fixed93 CPU preparations must succeed before freeze; no reselection')
 if [r['instance_id'] for r in manifest['records']]!=[r['instance_id'] for r in roster['records']]:raise RuntimeError('Fixed93 roster drift')
 ledger=C.load(C.SHARED_BUDGET)
 if not ledger or len(ledger['attempts'])!=2613 or C.sha(C.SHARED_BUDGET)!='a39db00fc6bdfc7a3dcc31ff473b92a69ce9a7c9ca7b94e8698f138d410db5a1' or any(a['status']!='usage_received' for a in ledger['attempts'].values()):raise RuntimeError('Exact2613 settled historical finance baseline required')
 old=C.load(C.OLD_RUN/'online_freeze.json');independent=C.ROOT/'configs/paper_retest93/independent_baseline.json';protected=dict(C.load(independent)['historical_file_sha256']);protected[str(independent)]=C.sha(independent)
 for field in ['online_sha256','data_sha256','snapshot_sha256','preparation_receipt_sha256','reuse_history_sha256','protected_history_sha256','selection_sha256','test_sha256','financial_baseline_sha256']:
  protected.update(old[field])
 for p,h in protected.items():
  if C.sha(p)!=h:raise RuntimeError('Protected old experiment changed: '+p)
 for p,h in roster['source_sha256'].items():
  if C.sha(p)!=h:raise RuntimeError('Selection source changed')
 ids=[r['instance_id'] for r in manifest['records']];keys={'D-SIMPLE|'+i for i in ids};finance=C.SHARED_BUDGET.parent
 policy={'allowed_ids':ids,'no_total_cap':True,'no_per_case_cap':True,'no_token_cap':True,'shared_budget_contract':financial_contract(),'baseline_attempt_sha256':{k:digest(v) for k,v in ledger['attempts'].items()},'protected_case_sha256':{k:digest(v) for k,v in ledger['cases'].items() if k not in keys},'ignored_historic_budget_stop_sha256':C.sha(finance/'budget_stop.json'),'protected_old200_pause_sha256':C.sha(finance/'user_pause.json'),'reservation_input_bound':'utf8_byte_upper_unchanged'}
 original=C.load(C.ROOT/'configs/resolved_config.json');config={k:copy.deepcopy(original[k]) for k in ['deepseek','price_snapshot','api_concurrency','transport_retries','semantic_retries']}
 config.update(run_id=C.RUN_ID,cohort=C.COHORT,methods=['D-SIMPLE'],budget_caps={'total_usd':None,'per_case_usd':None,'cumulative_case_tokens':None},sampling={'temperature':'omitted; vendor default1.0','top_p':'omitted; vendor default1.0','official_doc':'https://api-docs.deepseek.com/api/create-chat-completion/'},stage_max_tokens={'file_draws':6144,'query_planning':4096,'function_localization':4096},function_stage='Independent Top10 diagnostic extension; paper32768 patch cap is not applied',fresh_all_seven_calls=True,api_concurrency=4,gpu_used=False,checkpoint=C.CHECKPOINT,policy=policy)
 once(CONFIG,config)
 # Byte-identical baseline, never rewrite source ledger.
 if BASELINE.exists():raise RuntimeError('Unexpected preexisting continuation baseline')
 BASELINE.parent.mkdir(parents=True,exist_ok=True);BASELINE.write_bytes(C.SHARED_BUDGET.read_bytes());BASELINE.chmod(0o600)
 policy=dict(policy,configuration_sha256=C.sha(CONFIG))
 data={};snapshots={}
 for r in manifest['records']:
  receipt=C.load(r['preparation_receipt']);data.update(receipt['data_sha256']);snapshots.update(receipt['snapshot_sha256'])
 online={str(C.FROZEN/'src'/n):C.sha(C.FROZEN/'src'/n) for n in OLD_NAMES};online.update(source_signature())
 for p in C.PROMPTS.glob('*.txt'):online[str(p)]=C.sha(p)
 for p in [C.ROOT/'resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json',C.ROOT/'resources/offline_tiktoken/fb374d419588a4632f3f557e76b4b70aebbca790']:online[str(p)]=C.sha(p)
 once(FREEZE,{'run_id':C.RUN_ID,'cohort':C.COHORT,'records':manifest['records'],'allocated':93,'smoke_ids':ids[:5],'config':config,'policy':policy,'online_sha256':online,'worker_online_sha256':{p:h for p,h in online.items() if p not in {str(C.PACKAGE_ROOT/'runtime.py'),str(C.PACKAGE_ROOT/'prepare.py')}},'data_sha256':data,'snapshot_sha256':snapshots,'protected_old_sha256':protected,'selection_sha256':{str(p):C.sha(p) for p in [C.MANIFEST,C.ROSTER,C.ROOT/'reports/filtered265/per_issue.csv']},'test_sha256':{str(p):C.sha(p) for p in (C.PACKAGE_ROOT/'tests').glob('test_*.py')},'baseline_sha256':{str(BASELINE):C.sha(BASELINE)},'new_budget_created':False,'fresh_no_prior_replay':True})
 return verify()

def verify():
 f=C.load(FREEZE)
 if not f or f['run_id']!=C.RUN_ID:raise RuntimeError('New paper93 freeze required')
 for field in ['online_sha256','data_sha256','snapshot_sha256','protected_old_sha256','selection_sha256','test_sha256','baseline_sha256']:
  for p,h in f[field].items():
   if C.sha(p)!=h:raise RuntimeError('Frozen artifact changed: '+p)
 if financial_contract()!=f['policy']['shared_budget_contract']:raise RuntimeError('Financial path/inode changed')
 ledger=C.load(C.SHARED_BUDGET)
 for k,h in f['policy']['baseline_attempt_sha256'].items():
  if k not in ledger['attempts'] or digest(ledger['attempts'][k])!=h:raise RuntimeError('Historical2613attempt changed')
 if ledger['stage_cap_usd']!=5:raise RuntimeError('Historical cap metadata changed')
 return f

def worker_env():return dict(os.environ,PYTHONPATH=str(C.ROOT),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',TIKTOKEN_CACHE_DIR=str(C.ROOT/'resources/offline_tiktoken'))

def make_batch(f,records,scope,index):
 tasks=[]
 for r in records:
  receipt=C.load(r['preparation_receipt']);Path(r['result_dir']).mkdir(parents=True,exist_ok=True)
  tasks.append({'job':r['job'],'instance_id':r['instance_id'],'result_dir':r['result_dir'],'data_sha256':receipt['data_sha256'],'snapshot_sha256':receipt['snapshot_sha256'],'enqueued_utc':C.utc()})
 directory=C.RUN/'worker_receipts'/str(scope+'_'+str(index));directory.mkdir(parents=True,exist_ok=True)
 return {'run_id':C.RUN_ID,'cohort':C.COHORT,'tasks':tasks,'config':f['config'],'policy':f['policy'],'worker_online_sha256':f['worker_online_sha256'],'worker_receipt_dir':str(directory)}

def sandbox_argv(path,batch,probe_only=False):
 args=['bwrap','--die-with-parent','--new-session','--unshare-pid','--ro-bind','/','/','--proc','/proc','--dev-bind','/dev','/dev','--tmpfs','/tmp','--tmpfs',str(C.COSIL.parent),'--tmpfs',str(Path('/home/wdt/models').resolve()),'--tmpfs',str((Path.home()/'.cache').resolve())]
 for n in ['paper_retest93','jobs','snapshots','manifests','reports','configs','evaluator_private','runs']:args+=['--dir',str(C.ROOT/n)]
 for n in VISIBLE:args+=['--ro-bind',str(C.PACKAGE_ROOT/n),str(C.PACKAGE_ROOT/n)]
 args+=['--ro-bind',str(C.PROMPTS),str(C.PROMPTS),'--dir',str(C.FROZEN/'src')]
 for n in OLD_NAMES:args+=['--ro-bind',str(C.FROZEN/'src'/n),str(C.FROZEN/'src'/n)]
 for p in [C.ROOT/'resources/deepseek_v4_tokenizer',C.ROOT/'resources/offline_tiktoken',C.COSIL/'.venv-v5']:args+=['--ro-bind',str(p),str(p)]
 finance=C.SHARED_BUDGET.parent;args+=['--bind',str(finance.resolve()),str(finance)]
 for p in finance.iterdir():
  if p.name in ALLOWED or '.v2tmp.' in p.name:continue
  args+=['--tmpfs',str(p)] if p.is_dir() else ['--ro-bind','/dev/null',str(p)]
 seen=set()
 for task in batch['tasks']:
  job=C.load(task['job']);p=Path(task['job']).parent;snapshot=Path(job['snapshot'])
  for source,target in [(p.resolve(),p),(p.resolve(),p.resolve()),(snapshot.resolve(),snapshot),(snapshot.resolve(),snapshot.resolve())]:
   if str(target) not in seen:args+=['--ro-bind',str(source),str(target)];seen.add(str(target))
  args+=['--bind',str(Path(task['result_dir']).resolve()),str(task['result_dir'])]
 if not probe_only:args+=['--ro-bind',str((C.RUN/'activation.json').resolve()),str(C.RUN/'activation.json')]
 args+=['--bind',str(Path(batch['worker_receipt_dir']).resolve()),str(batch['worker_receipt_dir']),'--ro-bind',str(Path(path).resolve()),str(path),'--chdir',str(C.ROOT),'--',str(C.PYTHON),'-m','paper_retest93.worker',str(path)]
 return args+(['--probe'] if probe_only else ['--execute'])

def probe():
 f=verify();batch=make_batch(f,f['records'][:5],'probe',0);path=C.RUN/'batches/probe.json';C.write(path,batch)
 p=subprocess.run(sandbox_argv(path,batch,True),env=worker_env(),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
 receipt={'time':C.utc(),'passed':p.returncode==0,'stdout':p.stdout,'stderr':p.stderr,'returncode':p.returncode,'online_freeze_sha256':C.sha(FREEZE),'model_calls':0};C.write(C.RUN/'isolation_probe.json',receipt)
 if p.returncode:raise RuntimeError('Actual isolation failed: '+p.stderr[-2000:])
 return receipt

def pending(f,scope):
 allowed=set(f['smoke_ids']) if scope=='smoke' else set(r['instance_id'] for r in f['records'])
 return [r for r in f['records'] if r['instance_id'] in allowed and not (Path(r['result_dir'])/'result.json').exists()]

def paid_gates(f,scope):
 from .bootstrap import set_policy,activation,stopped
 set_policy(f['policy']);activation()
 test=C.load(C.RUN/'cpu_tests.json',{});proof=C.load(C.RUN/'isolation_probe.json',{})
 if not test.get('passed') or test.get('source_sha256')!=source_signature() or not proof.get('passed') or proof['online_freeze_sha256']!=C.sha(FREEZE):raise RuntimeError('Current-source CPU tests and actual probe required')
 if scope=='full':
  gate=C.load(C.RUN/'smoke_gate.json',{})
  if not gate.get('passed') or gate.get('online_freeze_sha256')!=C.sha(FREEZE):raise RuntimeError('Current-freeze fixedfirst5 engineering gate required')
 if stopped():raise RuntimeError('Active safety/pause stop')

def coordinate(scope):
 with (C.RUN/'coordinator.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);f=verify();paid_gates(f,scope);rows=pending(f,scope);children=[]
  for i in range(4):
   group=rows[i::4]
   if not group:continue
   batch=make_batch(f,group,scope,i);path=C.RUN/'batches'/str(scope+'_'+str(i)+'.json');C.write(path,batch);log=path.with_suffix('.log').open('a')
   p=subprocess.Popen(sandbox_argv(path,batch),env=worker_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);log.close();children.append(p)
  C.write(C.RUN/(scope+'_workers.json'),{'time':C.utc(),'pid':os.getpid(),'workers':[p.pid for p in children]})
  while any(p.poll() is None for p in children):
   if any(p.poll() is not None and p.returncode for p in children):
    from .bootstrap import stop
    stop('paper93_isolated_worker_exit')
   time.sleep(2)
  if any(p.returncode for p in children):raise RuntimeError('Isolated worker failure; preserve all receipts')
  verify();values=[C.load(Path(r['result_dir'])/'result.json') for r in f['records']];counts=collections.Counter(v['status'] if v else 'NOT_RUN' for v in values)
  if scope=='smoke':
   smoke=[C.load(Path(r['result_dir'])/'result.json') for r in f['records'][:5]];C.write(C.RUN/'smoke_gate.json',{'passed':all(v is not None for v in smoke) and not __import__('paper_retest93.bootstrap',fromlist=['stopped']).stopped(),'accuracy_threshold_used':False,'online_freeze_sha256':C.sha(FREEZE),'statuses':[v['status'] if v else 'NOT_RUN' for v in smoke]})
  C.write(C.RUN/(scope+'_complete.json'),{'time':C.utc(),'phase_finished':True,'allocated':93,'statuses':dict(counts),'history_and_source_sha_verified':True})

def launch(scope,execute=False):
 f=verify();rows=pending(f,scope)
 if not execute:return {'dry_run':True,'pending':len(rows),'new_semantic_requests_upper':len(rows)*7,'no_new_budget':True}
 paid_gates(f,scope);log=(C.RUN/(scope+'_launcher.log')).open('a');p=subprocess.Popen([str(C.PYTHON),'-m','paper_retest93.runtime','--phase','run','--scope',scope,'--execute','--coordinate'],cwd=C.ROOT,env=worker_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);log.close();value={'pid':p.pid,'time':C.utc(),'scope':scope};C.write(C.RUN/(scope+'_launcher.json'),value);return value

def tests():
 p=subprocess.run([str(C.PYTHON),'-m','unittest','discover','-s','paper_retest93/tests','-p','test_*.py','-v'],cwd=C.ROOT,env=worker_env(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 v={'passed':p.returncode==0,'output':p.stdout,'source_sha256':source_signature(),'model_calls':0};C.write(C.RUN/'cpu_tests.json',v)
 if p.returncode:raise RuntimeError(p.stdout[-4000:])
 return v

def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['tests','freeze','probe','run']);p.add_argument('--scope',default='smoke',choices=['smoke','full']);p.add_argument('--execute',action='store_true');p.add_argument('--coordinate',action='store_true');a=p.parse_args()
 if a.coordinate:
  if a.phase!='run' or not a.execute:raise PermissionError('Internal coordinator explicit execute only')
  return coordinate(a.scope)
 v=tests() if a.phase=='tests' else freeze() if a.phase=='freeze' else probe() if a.phase=='probe' else launch(a.scope,a.execute)
 print(json.dumps({'phase':a.phase,'result':v if a.phase!='freeze' else {'frozen':True,'n':v['allocated']}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
