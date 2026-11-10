"""Versioned artifact boundaries; identical pinned inference weights and thresholds."""
import json
from pathlib import Path
from code_qwen3_rr4.config import MODEL, JUDGE_MODEL, LEGACY_TOKENIZER, CHECKPOINT, SAMPLE, ISSUES, route, sha

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'results/qwen3_reranker4b_canary_20261110'
OUT = ROOT / 'results/qwen3_rr4_engineering_v2_20261110'
DOCS = ROOT / 'docs/qwen3-reranker4b-engineering-v2'
PACKAGE = ROOT / 'code_qwen3_rr4_v2'
TRANSPORT = Path('/tmp/rr4v2_1110')
SOCKET = TRANSPORT / 'score.sock'
ARMS = ('baseline', 'hybrid_safe')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value, *, immutable=False):
    path = Path(path)
    if path.is_symlink() or not any(path.resolve().is_relative_to(p.resolve()) for p in (OUT, DOCS)):
        raise PermissionError('New v2 artifacts only')
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        if path.read_text() != text:
            raise FileExistsError('Immutable v2 artifact differs: ' + str(path))
        return
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)


def configure():
    from code_rebench_qwen import common as c
    c.WORK, c.INPUTS, c.RUN, c.REPORTS = OUT, OUT / 'inputs', OUT / 'run', DOCS
    c.MODEL_DIR = MODEL
    c.RUN_ID = '20261110_qwen3_rr4_identity_resident_v2'
    c.COHORT = 'frozen_Lite20_engineering_development_canary'
    return c
