#!/usr/bin/env python
"""Method-level derived metrics over ALL 128 issues (offline view v2).

Per user request 2026-11-17: function-level metrics recomputed with
denominator fixed at 128 (all allocated issues). Issues with method-gold NA
(11) and arms that failed / produced no usable ranking are counted as NOT
correct (contribute 0). No model calls; does not modify frozen outputs.

Hit@k: count(first gold method within top-k) / 128.
MAP@5: AP@5 = sum_{k<=5} P@k*rel(k)/min(|G|,5), 0 when no gold/failed.
MRR@5: 1/rank of first gold method within top-5, else 0.
Macro-P/R/F1@5: per-issue P@5,R@5,F1@5 (0 when failed/no gold), mean over 128.
"""
import json, hashlib, time
from pathlib import Path

R = Path('results/multiswe_java_qwen3_20261117_v2')
OUT = Path('results/multiswe_java128_map5_derived_20261117')
SRC = R / 'reports/final128/per_issue.json'
ARMS = ('cosil', 'sfpruner', 'locagent')

def ranked(arm, level='function'):
    rk = arm.get('ranking', {}).get(level, []) or []
    out = []
    for e in rk:
        cid = e.get('canonical_id')
        if e.get('valid') and cid:
            out.append(cid)
        else:
            out.append(None)
    return out

def prf_at5(ids, gold):
    if not gold:
        return 0.0, 0.0, 0.0
    seen = set(); hits = 0
    for cid in ids[:5]:
        if cid in gold and cid not in seen:
            seen.add(cid); hits += 1
    p = hits / 5.0
    r = hits / len(gold)
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1

def main():
    data = json.loads(SRC.read_text())
    assert len(data) == 128
    per_issue = []
    acc = {a: dict(hit={1: 0, 3: 0, 5: 0}, ap=0.0, rr=0.0, p=0.0, r=0.0, f1=0.0) for a in ARMS}
    for issue in data:
        gold = set(issue.get('gold_functions') or [])
        row = {'instance_id': issue['instance_id'], 'gold_method_count': len(gold), 'arms': {}}
        for a in ARMS:
            arm = issue['arms'].get(a, {})
            ids = ranked(arm)
            h = {k: 1 if any(c in gold for c in ids[:k]) else 0 for k in (1, 3, 5)}
            p, r, f1 = prf_at5(ids, gold)
            seen = set(); hits = 0; ap = 0.0; rr = 0.0
            if gold:
                cap = min(len(gold), 5)
                for k, cid in enumerate(ids[:5], 1):
                    if cid in gold and cid not in seen:
                        seen.add(cid); hits += 1
                        ap += hits / k
                        if rr == 0.0:
                            rr = 1.0 / k
                        if hits == cap:
                            break
                ap /= cap
            for k in (1, 3, 5):
                acc[a]['hit'][k] += h[k]
            acc[a]['ap'] += ap; acc[a]['rr'] += rr
            acc[a]['p'] += p; acc[a]['r'] += r; acc[a]['f1'] += f1
            row['arms'][a] = {'hit1': h[1], 'hit3': h[3], 'hit5': h[5],
                              'ap5': ap, 'rr5': rr, 'p5': p, 'r5': r, 'f15': f1}
        per_issue.append(row)
    N = 128
    summary = {
        'schema': 'multiswe_java128_function_denom128_derived_view_v1',
        'derived_from': str(SRC),
        'source_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(),
        'denominator': N,
        'policy': '11 method-NA issues and all failed/partial arms count as NOT correct (0). No model calls.',
        'generated_epoch': time.time(),
        'metrics': {},
    }
    for a in ARMS:
        x = acc[a]
        summary['metrics'][a] = {
            'hit1': {'numerator': x['hit'][1], 'denominator': N, 'value': x['hit'][1] / N},
            'hit3': {'numerator': x['hit'][3], 'denominator': N, 'value': x['hit'][3] / N},
            'hit5': {'numerator': x['hit'][5], 'denominator': N, 'value': x['hit'][5] / N},
            'macro_p5': x['p'] / N, 'macro_r5': x['r'] / N, 'macro_f15': x['f1'] / N,
            'map5': x['ap'] / N, 'mrr5': x['rr'] / N,
        }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'function_denom128_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    (OUT / 'function_denom128_per_issue.json').write_text(json.dumps(per_issue, ensure_ascii=False, indent=1))
    print(f"{'指标':16}" + ''.join(f'{a:>22}' for a in ARMS))
    def pct(k):
        return ''.join(f"{acc[a]['hit'][k]}/128 ({acc[a]['hit'][k]/N*100:.2f}%)".rjust(22) for a in ARMS)
    print('Hit@1  '.ljust(16) + pct(1))
    print('Hit@3  '.ljust(16) + pct(3))
    print('Hit@5  '.ljust(16) + pct(5))
    for key, name in (('p', 'Macro-P@5'), ('r', 'Macro-R@5'), ('f1', 'Macro-F1@5'), ('ap', 'MAP@5'), ('rr', 'MRR@5')):
        print(f'{name:16}' + ''.join(f"{acc[a][key]/N:.4f}".rjust(22) for a in ARMS))

if __name__ == '__main__':
    main()
