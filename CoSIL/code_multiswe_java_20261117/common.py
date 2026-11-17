"""Small CPU-only artifact primitives; importing this module starts no models."""
from pathlib import Path
import hashlib
import json
import os
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parent
RUN = ROOT / 'results/multiswe_java_qwen3_20261117'
REVISION = '56ff018c04a38e27ada1e9d0a6d5839a51f88f0d'
SOURCE = ROOT.parent / 'GraphLocator/datasets/multi_swe_bench_java.jsonl'
ARMS = ('cosil', 'sfpruner', 'locagent')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value, *, immutable=True):
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    if path.exists() and immutable:
        if path.read_bytes() != data: raise ValueError('Frozen artifact drift: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    with temp.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    if immutable:
        try: os.link(temp, path)
        finally: temp.unlink(missing_ok=True)
    else: os.replace(temp, path)


def event(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': time.time(), **value}, ensure_ascii=False) + '\n')
        stream.flush(); os.fsync(stream.fileno())


def safe_path(path):
    p = Path(path)
    if not isinstance(path, str) or not path or p.is_absolute() or '..' in p.parts or '\\' in path:
        raise ValueError('Unsafe relative path')
    return path


def ordered_rows(source=SOURCE):
    rows = [json.loads(line) for line in Path(source).read_text().splitlines() if line.strip()]
    if len(rows) != 128 or len({r['instance_id'] for r in rows}) != 128:
        raise ValueError('Require the complete frozen Java128 roster')
    return sorted(rows, key=lambda r: (hashlib.sha256(('20261117:' + r['instance_id']).encode()).hexdigest(), r['instance_id']))
