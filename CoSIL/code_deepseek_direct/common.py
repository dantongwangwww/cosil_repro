import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = Path('/tmp/deepseek_direct_astropy12907_20261024')
RUN = ROOT/'results/deepseek_direct_astropy12907_20261024'
DOCS = ROOT/'docs/deepseek-direct/astropy__astropy-12907'
REPO = WORK/'repo'
JOB = WORK/'job.json'
IID = 'astropy__astropy-12907'
MODEL = 'deepseek-flash'
API = 'https://api.deepseek.com'
MAX_OUTPUT = 393216
CHECKPOINT = 'b44366622bd234896ea77bf844034943e4806bc3'


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
                                    separators=(',',':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, default=None):
    path=Path(path)
    return json.loads(path.read_text()) if path.is_file() else default


def write(path,value,*,replace=False):
    path=Path(path)
    if not any(path.resolve().is_relative_to(p.resolve()) for p in (WORK,RUN,DOCS)):
        raise PermissionError('New direct experiment output only')
    data=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and not replace:
        if path.read_text()==data:return
        raise FileExistsError(str(path))
    temporary=path.with_name(path.name+'.pending-'+str(os.getpid()))
    with os.fdopen(os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:
        stream.write(data)
    temporary.replace(path)
