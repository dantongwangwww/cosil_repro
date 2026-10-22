"""Independent extension paths; historical projects are read-only inputs."""
from pathlib import Path
import hashlib,json,os
from datetime import datetime,timezone
ROOT=Path('/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external300_v1')
FROZEN=ROOT.with_name('deepseek_simple_v1')
PREVIOUS=ROOT.with_name('deepseek_simple_external_v1')
COSIL=Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL')
RUN_ID='20261022_external_add200_nonthinking_v1'
RUN=ROOT/'runs'/RUN_ID
COHORT='external_add200'
BUDGET_USD=5.0
PRE_CHANGE_GITHUB_COMMIT='36145c8a05719057c3ab0de0e98aad8ab3aad1c0'
def utc():return datetime.now(timezone.utc).isoformat()
def sha(p):
 p=Path(p)
 if 'pruner_test' in p.name:raise PermissionError('sealed test must not be read')
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def load(p,default=None):
 p=Path(p)
 if 'pruner_test' in p.name:raise PermissionError('sealed test must not be read')
 return json.loads(p.read_text()) if p.exists() else default
def write(p,obj):
 p=Path(p)
 if not p.resolve().is_relative_to(ROOT.resolve()):raise PermissionError('new-project writes only')
 p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_name(p.name+'.tmp.'+str(os.getpid()))
 tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)
