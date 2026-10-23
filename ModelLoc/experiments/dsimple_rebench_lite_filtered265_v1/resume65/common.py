from pathlib import Path
import json,hashlib,os
from datetime import datetime,timezone
ROOT=Path('/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1')
FROZEN=ROOT.with_name('deepseek_simple_v1')
PREVIOUS=ROOT.with_name('deepseek_simple_external_v1')
PRIOR_V2=ROOT.with_name('dsimple_evaluation_v2')
ADDITIONAL=ROOT.with_name('deepseek_simple_external300_v1')
ADDITIONAL_RUN=ADDITIONAL/'runs/20261022_external_add200_nonthinking_v1'
SHARED_BUDGET=ADDITIONAL_RUN/'budget.json'
COSIL=Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL')
OLD_RUN=ROOT/'runs/20261022_rebench_lite_filtered265_nonthinking_v1'
RUN_ID='20261022_filtered265_resume65_nonthinking_v1'
RUN=ROOT/'runs'/RUN_ID
COHORT='rebench_lite_filtered265_v1'
PRE_CHANGE_GITHUB_COMMIT='bb0fd82bf8374a62f8ec550c611941e76cdcbf52'
BUDGET_USD=5.0
SEED=20261022
PYTHON=COSIL/'.venv-v5/bin/python'
PYTHON_AST=Path('/usr/bin/python3.12')
def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):
 p=Path(path)
 if 'pruner_test' in p.name:raise PermissionError('sealed test content forbidden')
 h=hashlib.sha256()
 with p.open('rb') as f:
  for v in iter(lambda:f.read(1048576),b''):h.update(v)
 return h.hexdigest()
def load(path,default=None):
 p=Path(path)
 if 'pruner_test' in p.name:raise PermissionError('sealed test content forbidden')
 return json.loads(p.read_text()) if p.exists() else default
def write(path,data):
 p=Path(path)
 if not p.resolve().is_relative_to(ROOT.resolve()):raise PermissionError('new filtered project writes only')
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp.'+str(os.getpid()))
 t.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
