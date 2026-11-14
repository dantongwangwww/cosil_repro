"""Independent outputs, unchanged weights, thresholds and inference contracts."""
import hashlib
import json
from pathlib import Path
from code_qwen3_rr4.config import MODEL, JUDGE_MODEL, LEGACY_TOKENIZER, CHECKPOINT, route, sha

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'results/qwen3_rr4_engineering_v2_20261110'
OUT = ROOT / 'results/qwen3_rr4_rebench100_20261110'
DOCS = ROOT / 'docs/qwen3-reranker4b-rebench100'
PACKAGE = ROOT / 'code_qwen3_rr4_rebench100'
TRANSPORT = Path('/tmp/rr4rb100_1110')
SOCKET = TRANSPORT / 'score.sock'
ARMS = ('baseline', 'hybrid_safe')
SEED = 20261110
REVISION = '34d5a58864acf91613740a09ec5d205228dcfa39'
SOURCE = Path('/tmp/cosil_rebench_qwen3_8b_20261023/inputs/prepare_manifest.json')
FROZEN = ROOT.parent / 'ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1'

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value, *, immutable=False):
    path = Path(path)
    if path.is_symlink() or not any(path.resolve().is_relative_to(p.resolve()) for p in (OUT, DOCS)):
        raise PermissionError('Independent Rebench100 artifacts only')
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        if path.read_text() != data:
            raise FileExistsError('Immutable artifact differs: ' + str(path))
        return
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(data)
    temp.replace(path)

def select(records, n=100):
    """Outcome/gold-free stable order, case-insensitive repository deduplication."""
    if len({r['instance_id'] for r in records}) != len(records):
        raise ValueError('Duplicate instance IDs')
    ordered = sorted(records, key=lambda r: (hashlib.sha256(
        f'{SEED}:{r["instance_id"]}'.encode()).hexdigest(), r['instance_id']))
    seen, selected, audit = set(), [], []
    for rank, r in enumerate(ordered, 1):
        repo = r['repo'].casefold()
        reason = 'duplicate_repository' if repo in seen else 'quota_after100' if len(selected) >= n else 'selected'
        if reason == 'selected':
            seen.add(repo); selected.append(r)
        audit.append({'rank': rank, 'instance_id': r['instance_id'], 'repo': r['repo'],
                      'base_commit': r['base_commit'], 'decision': reason,
                      'sampling_hash': hashlib.sha256(f'{SEED}:{r["instance_id"]}'.encode()).hexdigest()})
    if len(selected) != n:
        raise ValueError(f'Only {len(selected)} unique eligible repositories')
    return selected, audit

def configure():
    from code_rebench_qwen import common as c
    c.WORK, c.INPUTS, c.RUN, c.REPORTS = OUT, OUT / 'inputs', OUT / 'run', DOCS
    c.MODEL_DIR = MODEL
    c.RUN_ID = '20261110_cosil_qwen3_rr4_rebench100_v1'
    c.COHORT = 'frozen_filtered265_unique_repo100'
    return c
