from pathlib import Path
import hashlib, json, os
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
COSIL=Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL')
RUN_ID='20261021_nonthinking_v3'
RUN=ROOT/'runs'/RUN_ID

def digest(data):
    if isinstance(data,str): data=data.encode()
    return hashlib.sha256(data).hexdigest()

def sha(path):
    if 'pruner_test' in Path(path).name: raise PermissionError('Sealed test is forbidden')
    return digest(Path(path).read_bytes())

def read(path):
    if 'pruner_test' in Path(path).name: raise PermissionError('Sealed test is forbidden')
    return json.loads(Path(path).read_text())

def write(path,obj,replace=False):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if replace:
        tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(text); tmp.replace(p)
    else:
        with p.open('x') as f: f.write(text)

def stable(namespace,iid):
    return digest(f'deepseek-simple-v1|20261021|{namespace}|{iid}')

def utc(): return datetime.now(timezone.utc).isoformat()

def norm(path):
    p=str(path).replace('\\','/')
    while p.startswith('./'): p=p[2:]
    if p.startswith('/') or '..' in p.split('/'): return None
    return p

def is_test(path):
    p=path.lower().split('/')
    return any(v in ('test','tests','testing','doc','docs','documentation') for v in p[:-1]) or p[-1].startswith('test_') or p[-1].endswith('_test.py')

def source_file(path):
    return path.endswith('.py') and not is_test(path)

def redact(text,job):
    for s in [job['instance_id'],job['base_commit'],job['repo']]:
        text=text.replace(s,'[BENCHMARK_METADATA]')
    return text
