"""Portable bindings for the unchanged, vendored experimental implementation."""
from pathlib import Path
import hashlib
import json
import os
import re
import sys

BUNDLE = Path(__file__).resolve().parents[1]
VENDOR = BUNDLE / 'vendor'
CLEAN_KEYS = {'instance_id', 'repo', 'base_commit', 'problem_statement', 'cohort',
              'snapshot', 'paths', 'code_index', 'structure'}


def activate_vendor():
    for path in (VENDOR, VENDOR / 'afl/fl'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, *, immutable=True):
    path = Path(path)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if path.is_symlink():
        raise ValueError('Refuse symlink output')
    if immutable and path.exists():
        if path.read_text() != data:
            raise FileExistsError(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp.' + str(os.getpid()))
    with tmp.open('x', encoding='utf-8') as f:
        f.write(data)
    tmp.replace(path)


def configure(output, model_dir):
    activate_vendor()
    from code_rebench_qwen import common as c
    c.ROOT = VENDOR
    c.WORK = c.RUN = c.REPORTS = Path(output).resolve()
    c.MODEL_DIR = Path(model_dir).resolve()
    c.RUN_ID = 'SpecPrune_portable_rebench100_protocol'
    c.COHORT = 'frozen_filtered265_unique_repo100'
    return c


def validate_clean_job(job):
    if not isinstance(job, dict) or set(job) != CLEAN_KEYS:
        raise ValueError('Only the nine clean public/base job fields are accepted')
    if any(not isinstance(job[k], str) for k in CLEAN_KEYS - {'paths'}):
        raise ValueError('Clean job scalar fields must be strings')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', job['instance_id']) or job['instance_id'] in ('.', '..'):
        raise ValueError('Unsafe task ID')
    if not re.fullmatch(r'[0-9a-f]{40}', job['base_commit']):
        raise ValueError('Require a full base commit SHA')
    if not isinstance(job['paths'], list) or len(job['paths']) != len(set(job['paths'])):
        raise ValueError('Invalid inventory')
    for value in job['paths']:
        if not isinstance(value, str) or Path(value).is_absolute() or '..' in Path(value).parts:
            raise ValueError('Unsafe source path')
    return job


def load_job(path):
    """Resolve the three relocatable asset paths, keeping the nine-field schema."""
    path = Path(path).resolve(strict=True)
    job = validate_clean_job(read(path))
    for key in ('snapshot', 'code_index', 'structure'):
        value = Path(job[key])
        job[key] = str((path.parent / value).resolve() if not value.is_absolute() else value.resolve())
    return job
