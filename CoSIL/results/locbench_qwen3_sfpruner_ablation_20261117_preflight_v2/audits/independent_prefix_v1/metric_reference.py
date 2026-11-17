"""Exact pure metric functions copied from the immutable first100 auditor.
No I/O, private data, production evaluator or model imports.
"""
from collections import Counter
import math
import random
import statistics
import datetime as dt

def equal(a, b, label=''):
    if isinstance(a, dict) and isinstance(b, dict):
        assert set(a) == set(b), (label, set(a) ^ set(b))
        for k in a:
            equal(a[k], b[k], label + '/' + k)
    elif isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), label
        for i, (x, y) in enumerate(zip(a, b)):
            equal(x, y, label + '/' + str(i))
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        assert math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-12), (label, a, b)
    else:
        assert a == b, (label, a, b)


def slots(raw, inventory, functions):
    result = []
    for item in (raw if isinstance(raw, list) else [])[:10]:
        path = item.get('path') if functions and isinstance(item, dict) else item if not functions else None
        qn = item.get('qualified_name') if functions and isinstance(item, dict) else None
        if not isinstance(path, str):
            result.append(None)
            continue
        path = path.replace('\\', '/')
        while path.startswith('./'):
            path = path[2:]
        parts = path.lower().split('/')
        valid = (not path.startswith('/') and '..' not in path.split('/') and path.endswith('.py')
                 and not set(parts[:-1]) & {'test', 'tests', 'testing', 'doc', 'docs', 'documentation'}
                 and not parts[-1].startswith('test_') and not parts[-1].endswith('_test.py'))
        name = path + '::' + qn if functions and isinstance(qn, str) else path if not functions else None
        result.append(name if valid and name in inventory else None)
    return result


def score(ranked, targets):
    if not targets:
        return None
    targets = set(targets)
    out = {'slots': ranked}
    for k in (1, 3, 5):
        count = len(set(ranked[:k]) & targets)
        p, r = count / k, count / len(targets)
        out.update({f'hit{k}': int(count > 0), f'precision{k}': p, f'recall{k}': r,
                    f'f1{k}': 2 * p * r / (p + r) if p + r else 0,
                    f'all_coverage{k}': int(count == len(targets))})
    out['mrr10'] = next((1 / (i + 1) for i, item in enumerate(ranked) if item in targets), 0.0)
    return out


def interval(values, seed, draws):
    if not values:
        return [None, None]
    rng = random.Random(seed)
    samples = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(draws))
    return [samples[math.ceil(.025 * draws) - 1], samples[math.ceil(.975 * draws) - 1]]


def aggregate(entries, seed, draws):
    n = len(entries)
    out = {'n': n}
    for k in (1, 3, 5):
        hit = sum(x[f'hit{k}'] for x in entries)
        p = hit / n if n else None
        if n:
            z = 1.959963984540054
            center = (p + z * z / (2 * n)) / (1 + z * z / n)
            radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
            ci = [center - radius, center + radius]
        else:
            ci = [None, None]
        out.update({f'hit{k}_numerator': hit, f'hit{k}': p, f'hit{k}_ci95': ci})
    for key in ('precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
        values = [x[key] for x in entries]
        out[key] = statistics.mean(values) if values else None
        out[key + '_ci95'] = interval(values, seed, draws)
    return out


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
