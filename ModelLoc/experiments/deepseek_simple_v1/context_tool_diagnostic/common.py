"""Run-local storage; private evaluation has a separate entry point."""
import hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
COSIL=ROOT.parents[2]/'CoSIL'
RUN_ID='20261021_context_tool_diagnostic'
RUN=ROOT/'runs'/RUN_ID
OLD=ROOT/'runs/20261021_nonthinking_v3'
PRIVATE=ROOT/'evaluator_private'/RUN_ID
BACKUP='06ad7173a455f5102d383d11ec7d6e91701e5505'

def utc():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(value.encode() if isinstance(value,str) else value).hexdigest()
def allowed_read(path):
    p=Path(path)
    if any(v in str(p).lower() for v in ('pruner_test','holdout','test_chain')):raise PermissionError('Sealed input forbidden')
    return p

def read(path):return json.loads(allowed_read(path).read_text())
def sha(path):return digest(allowed_read(path).read_bytes())
def write(path,obj,replace=False):
    p=Path(path).absolute()
    if not (p.is_relative_to(RUN) or p.is_relative_to(PRIVATE)):raise PermissionError('New run/private output only: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if replace:
        tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(text);tmp.replace(p)
    elif p.exists():
        if p.read_text()!=text:raise FileExistsError('Immutable output drift: '+str(p))
    else:
        with p.open('x') as f:f.write(text)

def records():
    return read(RUN/'run_manifest.json')['records']

def selected(scope):
    m=read(RUN/'run_manifest.json')
    return m['smoke_ids'] if scope=='smoke' else m['b2_ids'] if scope=='b2' else [r['instance_id'] for r in m['records']]

def redact(text,job):
    for s in (job['instance_id'],job['repo'],job['base_commit']):text=text.replace(s,'[BENCHMARK_METADATA]')
    return text
