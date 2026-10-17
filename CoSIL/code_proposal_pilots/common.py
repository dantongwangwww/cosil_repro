"""Read-only inputs, exclusive outputs, and sealed-test guards for proposal pilots."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import csv
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/proposal_pilots/20261017'
DOCS = ROOT / 'docs/proposal-pilots'
PRE_COMMIT = 'f3dbc8f1c05c90993f0ef50eafe37bfe52b2de5a'


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def allowed(path):
    p = Path(path).resolve()
    if 'pruner_test' in p.name:
        raise PermissionError('Sealed pruner test content is forbidden, even for hashing')
    return p


def sha(path):
    h = hashlib.sha256()
    with allowed(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(allowed(path).read_text())


def write(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def textfile(path, content):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        f.write(content)


def csvfile(path, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def leaf(name):
    return name.strip().strip('`').split('(', 1)[0].split('#', 1)[0].strip().rsplit('.', 1)[-1]


def mentions(issue):
    calls = re.findall(r'\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(', issue)
    ids = [s for s in re.findall(r'`([^`\n]+)`', issue)
           if re.fullmatch(r'\w+(?:\.\w+)*', s.strip())]
    return {leaf(s) for s in calls + ids}


def function_key(fid):
    file, name = fid.rsplit('::', 1)
    name, line = name.rsplit('@', 1)
    assert int(line) > 0
    return file, 'function', leaf(name)


def targets(gold):
    return {(file, 'function', leaf(name))
            for file, names in gold['gold_functions_by_file'].items() for name in names}


def ratio(n, d):
    return n / d if d else None


def pct(v):
    return 'NA' if v is None else f'{v:.2%}'


def inputs():
    gold = read(ROOT / 'ground_truth_300.json')
    metrics = read(ROOT / 'results/qwen_300/metrics.json')
    baseline_path = ROOT / 'results/full/loc_out_full.jsonl'
    baseline_rows = [json.loads(s) for s in baseline_path.read_text().splitlines() if s.strip()]
    baseline = {r['instance_id']: r['found_files'] for r in baseline_rows}
    issue_path = ROOT.parent / 'GraphLocator/datasets/swe_bench_lite.jsonl'
    issues = {r['instance_id']: r for r in
              (json.loads(s) for s in issue_path.read_text().splitlines() if s.strip())}
    assert len(gold) == len(baseline_rows) == len(baseline) == len(issues) == 300
    assert set(gold) == set(issues) == set(baseline)
    for arm, cases in metrics['cases'].items():
        assert len(cases) == 300 and {c['instance_id'] for c in cases} == set(gold)
    return gold, metrics, baseline, issues, issue_path


def protected():
    from code_v6.common import test_stats
    files = [ROOT / 'ground_truth_300.json', ROOT / 'results/qwen_300/metrics.json',
             ROOT / 'results/full/loc_out_full.jsonl',
             ROOT / 'results/comparison/逐题定位对照数据.json']
    files += sorted((ROOT / 'docs/qwen-300').glob('跨实验逐题*'))
    for d in ['code_v6', 'code_v6_round2']:
        files += sorted((ROOT / d).glob('*.py'))
    return {'test_stat_only': test_stats(), 'source_hashes': {str(p): sha(p) for p in files}}


def initialize():
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / 'frozen_protocol.json'
    if not p.exists():
        write(p, {'created_at': now(), 'pre_change_github_commit': PRE_COMMIT,
                  'protocol_path': str(DOCS / '执行协议与预研一提示词_2026-10-17.md'),
                  'protocol_sha256': sha(DOCS / '执行协议与预研一提示词_2026-10-17.md'),
                  'protected': protected(), 'cpu_experiments_gpu_allowed': False,
                  'new_test_execution_allowed': False, 'pruner_test_open_allowed': False})
    r = read(p)
    assert r['protocol_sha256'] == sha(r['protocol_path'])
    assert r['protected'] == protected(), 'Protected historical inputs or sealed test stat changed'
    return r


def provenance():
    _, _, _, _, issue_path = inputs()
    files = [ROOT / 'ground_truth_300.json', ROOT / 'results/qwen_300/metrics.json',
             ROOT / 'results/full/loc_out_full.jsonl', issue_path]
    return {str(p): sha(p) for p in files}


def production(path):
    parts = Path(path).parts
    return path.endswith('.py') and not any(
        x.lower() in {'test', 'tests', 'testing', 'benchmarks', 'benchmark', 'docs',
                      'doc', 'examples', 'example', 'tools', 'scripts', 'build', 'setup.py',
                      'conftest.py'} or x.lower().startswith('test_')
        or x.lower().endswith('_test.py') for x in parts)
