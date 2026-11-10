"""Public paths and policy. Importing this module performs no inference."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/qwen3_reranker4b_canary_20261110'
DOCS = ROOT / 'docs/qwen3-reranker4b-canary'
MODEL = Path('/tmp/cosil_rebench_qwen3_8b_20261023/model')
JUDGE_MODEL = ROOT / 'models_v6/Qwen3-Reranker-4B'
CHECKPOINT = ROOT / 'results/v6_pruner/20261016/T3_round1_exploratory/reranker4B/epoch_1'
SAMPLE = ROOT / 'results/v6_pruner/20261016/T1_canary_preparation/sampling_manifest.json'
ISSUES = ROOT / 'results/v6_pruner/20261019/T1_canary_v2/inference_issues.json'
VAL = CHECKPOINT.parent / 'val_epoch_1.jsonl'
DATA = ROOT / 'results/v6_pruner/20261016/T2_dataset_v6'
ARMS = ('baseline', 'hybrid_safe')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def write(path, value, *, immutable=False):
    path = Path(path)
    if not any(path.resolve().is_relative_to(p.resolve()) for p in (OUT, DOCS)):
        raise PermissionError('Independent run/docs paths only')
    if path.is_symlink():
        raise PermissionError('No symlink outputs')
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        if path.read_text() != data:
            raise FileExistsError('Immutable artifact differs: ' + str(path))
        return
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(data)
    tmp.replace(path)


def configure():
    # Redirect only the current process's configuration; old source/results stay intact.
    from code_rebench_qwen import common as c
    c.WORK, c.INPUTS, c.RUN, c.REPORTS = OUT, OUT/'inputs', OUT/'run', DOCS
    c.MODEL_DIR = MODEL
    c.RUN_ID = '20261110_qwen3_8b_reranker4b_lite20_v1'
    c.COHORT = 'frozen_Lite20_development_canary'
    return c


def route(p, low, high=.9):
    if not all(math.isfinite(x) for x in (p, low, high)) or not 0 <= p <= 1 or not 0 <= low < high <= 1:
        raise ValueError('Invalid calibrated probability or thresholds')
    return 'reject' if p <= low else 'retain' if p >= high else 'qwen'
