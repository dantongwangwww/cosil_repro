"""Independent CPU scoring of frozen ranked predictions against offline R2 targets.

Adapted from code_qwen3_rr4_rebench100/report.py and
code_rebench_qwen/reporting.py. This module never imports a model or tool runner.
Invalid identities retain their original ranking positions. Missing/failed tasks
remain in the fixed eligible denominator; status counts are reported separately.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

DEFAULT_ARMS = ('baseline', 'hybrid_safe')
DEFAULT_SEED = 20261110

def norm(value):
    if not isinstance(value, str):
        return None
    value = value.replace('\\', '/')
    while value.startswith('./'):
        value = value[2:]
    return None if value.startswith('/') or '..' in value.split('/') else value

def source_file(path):
    if not path or not path.endswith('.py'):
        return False
    parts = path.lower().split('/')
    return (not any(p in ('test', 'tests', 'testing', 'doc', 'docs', 'documentation') for p in parts[:-1])
            and not parts[-1].startswith('test_') and not parts[-1].endswith('_test.py'))

def slots(raw, identities, *, functions):
    """Validate exact identities against the base snapshot; never repair a rank."""
    valid, result = set(identities), []
    for item in (raw if isinstance(raw, list) else [])[:10]:
        path = norm(item.get('path')) if functions and isinstance(item, dict) else norm(item) if not functions else None
        qn = item.get('qualified_name') if functions and isinstance(item, dict) else None
        identity = path + '::' + qn if functions and path and isinstance(qn, str) else path if not functions else None
        result.append(identity if source_file(path) and identity in valid else None)
    return result

def scores(predictions, targets, k):
    if not targets:
        return dict.fromkeys(('hit', 'precision', 'recall', 'f1', 'all_coverage'))
    targets = set(targets)
    found = len(set(p for p in predictions[:k] if p is not None) & targets)
    precision, recall = found / k, found / len(targets)
    return {'hit': int(found > 0), 'precision': precision, 'recall': recall,
            'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0,
            'all_coverage': int(found == len(targets))}

def metrics(raw, targets, inventory, *, functions):
    if not targets:
        return None
    ranked = slots(raw, inventory, functions=functions)
    targets = set(targets)
    return {**{f'{metric}{k}': value for k in (1, 3, 5) for metric, value in scores(ranked, targets, k).items()},
            'mrr10': next((1 / (rank + 1) for rank, identity in enumerate(ranked[:10]) if identity in targets), 0.0),
            'slots': ranked}

def wilson(hits, n):
    if not n:
        return [None, None]
    z, p = 1.959963984540054, hits / n
    den = 1 + z*z/n
    center = (p + z*z/(2*n)) / den
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return [center-half, center+half]

def mean_ci(values, *, seed=DEFAULT_SEED, draws=5000):
    """Issue bootstrap, preserving the original paper's percentile convention."""
    if not values:
        return [None, None]
    rng = random.Random(seed)
    vals = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(draws))
    return [vals[max(0, math.ceil(.025 * draws) - 1)], vals[max(0, math.ceil(.975 * draws) - 1)]]

def paired(a, b, *, seed=DEFAULT_SEED, draws=5000):
    if len(a) != len(b):
        raise ValueError('Paired observations must have the same length')
    both = sum(bool(x) and bool(y) for x, y in zip(a, b))
    only_a = sum(bool(x) and not bool(y) for x, y in zip(a, b))
    only_b = sum(bool(y) and not bool(x) for x, y in zip(a, b))
    discordant = only_a + only_b
    p = min(1., 2 * sum(math.comb(discordant, k) for k in range(min(only_a, only_b) + 1)) / 2**discordant) if discordant else 1.
    delta = [int(bool(y)) - int(bool(x)) for x, y in zip(a, b)]
    return {'n': len(a), 'both_success': both, 'only_a': only_a, 'only_b': only_b,
            'both_failure': len(a)-both-only_a-only_b, 'b_minus_a': statistics.mean(delta) if delta else None,
            'b_minus_a_ci95': mean_ci(delta, seed=seed, draws=draws),
            'exact_mcnemar_p': p, 'noninferiority_certified': False}

def aggregate(entries, *, seed, draws):
    out = {'n': len(entries)}
    for k in (1, 3, 5):
        hits = sum(v[f'hit{k}'] for v in entries)
        out.update({f'hit{k}_numerator': hits, f'hit{k}': hits / len(entries) if entries else None,
                    f'hit{k}_ci95': wilson(hits, len(entries))})
    for metric in ('precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
        values = [v[metric] for v in entries]
        out[metric] = statistics.mean(values) if values else None
        out[metric + '_ci95'] = mean_ci(values, seed=seed, draws=draws)
    return out

def evaluate(predictions, gold, inventory, *, arms=DEFAULT_ARMS, seed=DEFAULT_SEED, draws=5000):
    """Score a fixed roster; gold/inventory must have exactly that roster's IDs."""
    records = predictions['records'] if isinstance(predictions, dict) else predictions
    ids = [r['instance_id'] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate issue IDs')
    if set(ids) != set(gold) or set(ids) != set(inventory):
        raise ValueError('Predictions, gold, and inventory rosters differ; do not silently drop issues')
    rows = []
    for record in records:
        iid = record['instance_id']
        g, inv = gold[iid], inventory[iid]
        eligible = g['status'] == 'COMPLETE_NONEMPTY' and g['set_complete'] and bool(g['targets'])
        if eligible and not set(g['targets']).issubset(inv['function_identities']):
            raise ValueError(f'Gold identity absent from base inventory: {iid}')
        row = {k: record[k] for k in ('instance_id', 'repo', 'base_commit') if k in record}
        row.update(function_scorable=eligible, gold_status=g['status'], gold_functions=g['targets'], gold_files=g['gold_files'])
        for arm in arms:
            pred = record.get('arms', {}).get(arm, {})
            status = pred.get('status', 'NOT_RUN')
            raw_fn, raw_files = pred.get('predicted_functions', []), pred.get('predicted_files', [])
            if status in ('NOT_RUN', 'EXECUTION_INCOMPLETE') and (raw_fn or raw_files):
                raise ValueError(f'Unfinished result carries predictions: {iid}/{arm}')
            row[arm + '_status'] = status
            row[arm + '_function'] = metrics(raw_fn, g['targets'] if eligible else [], inv['function_identities'], functions=True)
            row[arm + '_file'] = metrics(raw_files, g['gold_files'], inv['paths'], functions=False)
        rows.append(row)
    summary = {'allocated': len(rows), 'function_denominator': sum(r['function_scorable'] for r in rows),
               'file_denominator': sum(bool(r['gold_files']) for r in rows), 'gold_statuses': dict(Counter(r['gold_status'] for r in rows)),
               'complete_pairs': sum(all(r[a + '_status'] == 'complete' for a in arms) for r in rows),
               'denominator_policy': 'fixed roster; failed/unrun eligible issues stay as misses; NA gold excluded only at that unit',
               'bootstrap_seed': seed, 'bootstrap_draws': draws, 'metrics': {}, 'statuses': {}, 'completed_only_secondary': {}}
    for arm in arms:
        summary['statuses'][arm] = dict(Counter(r[arm + '_status'] for r in rows))
        summary['metrics'][arm] = {}
        summary['completed_only_secondary'][arm] = {}
        for unit in ('file', 'function'):
            entries = [r[arm + '_' + unit] for r in rows if r[arm + '_' + unit] is not None]
            summary['metrics'][arm][unit] = aggregate(entries, seed=seed, draws=draws)
            complete = [r[arm + '_' + unit] for r in rows if r[arm + '_status'] == 'complete' and r[arm + '_' + unit] is not None]
            summary['completed_only_secondary'][arm][unit] = aggregate(complete, seed=seed, draws=draws)
    if len(arms) == 2:
        pairs = [r for r in rows if r['function_scorable']]
        summary['paired_function_hit5'] = paired([r[arms[0] + '_function']['hit5'] for r in pairs],
                                                 [r[arms[1] + '_function']['hit5'] for r in pairs], seed=seed, draws=draws)
        summary['paired_function_hit5']['arms'] = list(arms)
        summary['paired_function_hit5']['scope'] = 'fixed function-eligible roster; includes unavailable output as miss'
    return {'summary': summary, 'records': rows}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--predictions', type=Path, required=True)
    p.add_argument('--gold', type=Path, required=True, help='Offline evaluation assets; never pass to inference')
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True, help='New directory; existing evaluation is never overwritten')
    p.add_argument('--arms', nargs='+', default=list(DEFAULT_ARMS))
    p.add_argument('--seed', type=int, default=DEFAULT_SEED)
    p.add_argument('--bootstrap-draws', type=int, default=5000)
    a = p.parse_args()
    if a.bootstrap_draws < 40:
        p.error('--bootstrap-draws must be >= 40')
    if a.output.exists():
        p.error('Output directory already exists')
    inputs = {key: json.loads(getattr(a, key).read_text()) for key in ('predictions', 'gold', 'inventory')}
    result = evaluate(**inputs, arms=a.arms, seed=a.seed, draws=a.bootstrap_draws)
    result['input_sha256'] = {key: hashlib.sha256(getattr(a, key).read_bytes()).hexdigest() for key in inputs}
    a.output.mkdir(parents=True)
    (a.output / 'evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    with (a.output / 'per_issue.csv').open('w', encoding='utf-8-sig', newline='') as f:
        fields = list(dict.fromkeys(k for r in result['records'] for k in r))
        writer = csv.DictWriter(f, fields); writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in result['records'])
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
