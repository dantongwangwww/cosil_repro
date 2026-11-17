from pathlib import Path
import json,hashlib,os
from datetime import datetime,timezone
ROOT=Path('/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_evaluation_v2')
FROZEN=ROOT.with_name('deepseek_simple_v1')
PREVIOUS=ROOT.with_name('deepseek_simple_external_v1')
ADDITIONAL=ROOT.with_name('deepseek_simple_external300_v1')
ADDITIONAL_RUN=ADDITIONAL/'runs/20261022_external_add200_nonthinking_v1'
SHARED_BUDGET=ADDITIONAL_RUN/'budget.json'
COSIL=Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL')
RUN_ID='20261022_lite_eval_v2_nonthinking'
RUN=ROOT/'runs'/RUN_ID
COHORT='lite_remaining_v2'
PRE_CHANGE_GITHUB_COMMIT='dfab02c2d7cf595807c9cfed735174dbaca91e71'
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
 if not p.resolve().is_relative_to(ROOT.resolve()):raise PermissionError('new evaluation project writes only')
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp.'+str(os.getpid()))
 t.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
