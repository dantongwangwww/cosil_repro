"""CPU-only provenance and test-denial helpers for the v6 audit stages."""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/v5_pruner'
OUT = ROOT / 'results/v6_pruner/20261016'
DOCS = ROOT / 'docs/v6-pruner'
INSTRUCTION = ROOT.parent / '指令_v6执行序列_2026-10-16.md'
COHORTS = {'legacy_v1': BASE / 'data', 'B': BASE / 'data_v3_runtime_filtered_reviewed',
           'C': BASE / 'data_verified_plus_B_runtime_reviewed'}


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def allowed(path):
    path = Path(path).resolve()
    if 'pruner_test' in path.name:
        raise PermissionError('v6 refuses test contents, including binary hashing')
    return path


def sha(path):
    p = allowed(path)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def read(path):
    return json.loads(allowed(path).read_text())


def rows(path):
    p = allowed(path)
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def write(path, data):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def status(path, data):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    temporary = p.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(p)


def test_stats():
    result = {}
    for d in [BASE / n for n in ['data', 'data_v3', 'data_v3_runtime_filtered_reviewed',
                                'data_verified_plus_B_runtime_reviewed', 'data_verified_plus_B_runtime']]:
        p = d / 'pruner_test.jsonl'
        s = p.stat()
        opened = p.with_name(p.name + '.v5_opened_once.json').exists()
        if opened:
            raise PermissionError('Test once-open marker exists: ' + str(p))
        result[str(p)] = {'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns, 'inode': s.st_ino,
                          'opened_marker_exists': opened}
    return result


def historical_files():
    paths = list((ROOT / 'docs/v5-pruner').glob('*.md'))
    paths += [ROOT / 'results/comparison/逐题定位对照数据.json',
              ROOT.parent / '跨实验对照表/跨实验逐题定位对照表.xlsx']
    return {str(p): sha(p) for p in paths}


def verify_files(files):
    for p, expected in files.items():
        if sha(p) != expected:
            raise RuntimeError('Source/input/history drift: ' + str(p))


def pair(row):
    return row['instance_id'], row['function_id']
