from pathlib import Path
import datetime,hashlib,json,os
ROOT=Path('/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1')
PACKAGE_ROOT=ROOT/'paper_retest93';PROMPTS=PACKAGE_ROOT/'prompts'
FROZEN=ROOT.with_name('deepseek_simple_v1');PREVIOUS=ROOT.with_name('deepseek_simple_external_v1');ADDITIONAL=ROOT.with_name('deepseek_simple_external300_v1');PRIOR_V2=ROOT.with_name('dsimple_evaluation_v2')
COSIL=Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL');PYTHON=COSIL/'.venv-v5/bin/python'
OLD_RUN=ROOT/'runs/20261022_rebench_lite_filtered265_nonthinking_v1'
RUN_ID='20261023_paper_params_retest93_nonthinking_v1';COHORT='paper_params_retest93';RUN=ROOT/'runs'/RUN_ID
SHARED_BUDGET=ADDITIONAL/'runs/20261022_external_add200_nonthinking_v1/budget.json'
PRIVATE=ROOT/'evaluator_private/paper_retest93';JOBS=ROOT/'jobs/paper_retest93';SNAPSHOTS=ROOT/'snapshots/paper_retest93';MANIFEST=ROOT/'manifests/paper_retest93/manifest.json';ROSTER=ROOT/'manifests/paper_retest93/roster.json'
CHECKPOINT='df2244a7a2330b537746007db0f7368cdfa916f4'
CLEAN_KEYS={'instance_id','repo','base_commit','problem_statement','cohort','snapshot','paths','code_index','structure'}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(path,default=None):
 p=Path(path)
 if 'pruner_test' in p.name:raise PermissionError('Sealed content forbidden')
 return json.loads(p.read_text()) if p.exists() else default
def sha(path):
 p=Path(path)
 if 'pruner_test' in p.name:raise PermissionError('Sealed content forbidden')
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def permitted(path):
 p=Path(path);targets=[RUN,PACKAGE_ROOT,PRIVATE,JOBS,SNAPSHOTS,MANIFEST.parent,ROOT/'reports/paper_retest93',ROOT/'configs/paper_retest93']
 if not any(p.resolve().is_relative_to(t.resolve()) for t in targets):raise PermissionError('Only new paper_retest93 output may be written')
 return p
def write(path,value,replace=True):
 p=permitted(path);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and not replace:
  if load(p)!=value:raise RuntimeError('Immutable output differs: '+str(p))
  return
 tmp=p.with_name(p.name+'.tmp.'+str(os.getpid()))
 fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 tmp.replace(p)
