"""Outcome-free deterministic sampling, adapted from the frozen 20261110 run.

Source: CoSIL/code_qwen3_rr4_rebench100/config.py:select.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SEED = 20261110
REVISION = '34d5a58864acf91613740a09ec5d205228dcfa39'
ALGORITHM = 'SHA256(utf8(str(seed)+":"+instance_id)), then instance_id; first per repo.casefold()'

def select(records, n=100, seed=SEED):
    """Return selected records and every candidate's decision, without reading gold."""
    if n < 1:
        raise ValueError('n must be positive')
    if len({r['instance_id'] for r in records}) != len(records):
        raise ValueError('Duplicate instance IDs')
    key = lambda r: (hashlib.sha256(f'{seed}:{r["instance_id"]}'.encode()).hexdigest(), r['instance_id'])
    ordered = sorted(records, key=key)
    selected, audit, seen = [], [], set()
    for rank, r in enumerate(ordered, 1):
        repo = r['repo'].casefold()
        decision = 'duplicate_repository' if repo in seen else f'quota_after{n}' if len(selected) >= n else 'selected'
        if decision == 'selected':
            selected.append(r)
            seen.add(repo)
        audit.append({'rank': rank, 'instance_id': r['instance_id'], 'repo': r['repo'],
                      'base_commit': r['base_commit'], 'decision': decision, 'sampling_hash': key(r)[0]})
    if len(selected) != n:
        raise ValueError(f'Only {len(selected)} unique eligible repositories; requested {n}')
    return selected, audit

def manifest(records, n=100, seed=SEED, revision=REVISION):
    selected, audit = select(records, n=n, seed=seed)
    return {'seed': seed, 'dataset_revision': revision, 'algorithm': ALGORITHM,
            'pool_n': len(records), 'unique_pool_repositories': len({r['repo'].casefold() for r in records}),
            'selected_n': len(selected), 'rows': audit,
            'selected_issue_ids': [r['instance_id'] for r in selected],
            'selection_reads_gold_or_outcomes': False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, type=Path, help='JSON list, records, or prior sampling_manifest rows')
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--seed', type=int, default=SEED)
    p.add_argument('--count', type=int, default=100)
    p.add_argument('--revision', default=REVISION)
    args = p.parse_args()
    d = json.loads(args.input.read_text())
    rows = d if isinstance(d, list) else d.get('records', d.get('rows'))
    if rows is None:
        p.error('Input must contain records or rows')
    out = manifest(rows, args.count, args.seed, args.revision)
    out['source_manifest_sha256'] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    if args.output.exists():
        p.error('Refusing to overwrite an existing manifest')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: out[k] for k in ('pool_n', 'unique_pool_repositories', 'selected_n')}))

if __name__ == '__main__':
    main()
