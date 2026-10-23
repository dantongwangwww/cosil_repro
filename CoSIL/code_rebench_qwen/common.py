"""Shared paths and safe artifact helpers; no model or evaluation imports."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELLOC = ROOT.parent / 'ModelLoc/experiments'
FROZEN = MODELLOC / 'dsimple_rebench_lite_filtered265_v1'
SOURCE_MANIFEST = FROZEN / 'manifests/filtered265.json'
WORK = Path('/tmp/cosil_rebench_qwen3_8b_20261023')
INPUTS = WORK / 'inputs'
RUN = WORK / 'run'
REPORTS = ROOT / 'docs/rebench-qwen3-8b'
MODEL_DIR = WORK / 'model'
MODEL_ID = 'Qwen/Qwen3-8B'
SERVED_MODEL = 'qwen3-8b'
BASE_URL = 'http://127.0.0.1:7343/v1'
CHECKPOINT = '9b77d56bc82f0c443ebb7693e3a526bee47af5f6'
COHORT = 'rebench_lite_filtered265'
RUN_ID = '20261023_cosil_qwen3_8b_off_rebench265_v1'
CONTEXT_LIMIT = 65536
MAX_TOKENS = 2048
MAX_RETRY = 10
SEED = 0
CLEAN_KEYS = {'instance_id', 'repo', 'base_commit', 'problem_statement',
              'cohort', 'snapshot', 'paths', 'code_index', 'structure'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


load = read


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    if not isinstance(value, (str, bytes)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def write(path, value, replace=True):
    path = Path(path)
    if path.is_symlink():
        raise PermissionError('Artifact must not be a symlink')
    allowed = (WORK.resolve(), REPORTS.resolve())
    if not any(path.resolve().is_relative_to(root) for root in allowed):
        raise PermissionError('New experiment output only: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        if read(path) != value:
            raise RuntimeError('Immutable artifact differs: ' + str(path))
        return path
    temporary = path.with_name(path.name + '.tmp.' + str(os.getpid()))
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    return path


atomic_json = write
