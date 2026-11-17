"""Offline R2 target evaluation and comparable shared-file resource accounting."""
from collections import Counter
from functools import lru_cache
import csv
import json
import math
import statistics
from . import config as P
from code_qwen3_rr4.report import paired, usage
from code_rebench_qwen.reporting import norm, source_file, scores, mrr

@lru_cache(maxsize=1)
def private():
    return P.read(P.OUT / 'evaluation_private.json'), P.read(P.OUT / 'evaluation_inventory.json')

def slots(raw, identities, *, functions):
    """Strict R2 identity; invalid entries retain their raw rank slots."""
    valid = set(identities); result = []
    for item in (raw if isinstance(raw, list) else [])[:10]:
        path = norm(item.get('path')) if functions and isinstance(item, dict) else norm(item) if not functions else None
        qn = item.get('qualified_name') if functions and isinstance(item, dict) else None
        identity = path + '::' + qn if functions and path and isinstance(qn, str) else path if not functions else None
        result.append(identity if source_file(path) and identity in valid else None)
    return result

def metrics(raw, targets, inventory, *, functions):
    if not targets: return None
    ss = slots(raw, inventory, functions=functions)
    return {**{f'{metric}{k}': value for k in (1, 3, 5) for metric, value in scores(ss, targets, k).items()},
            'mrr10': mrr(ss, targets), 'slots': ss}

def wilson(hits, n):
    if not n: return [None, None]
    z = 1.959963984540054; p = hits / n; den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    h = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return [c-h, c+h]

def mean_ci(values):
    if not values: return [None, None]
    import random
    rng = random.Random(P.SEED)
    vals = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(5000))
    return [vals[124], vals[4874]]

def create(*, final=False):
    manifest = P.read(P.OUT / 'inputs/manifest.json'); gold, inventory = private()
    state = P.read(P.OUT / 'controller_status.json') if (P.OUT / 'controller_status.json').exists() else {'stage': 'PREPARED'}
    rows = []; arm_rows = {a: [] for a in P.ARMS}; raw = {}
    for record in manifest['records']:
        iid = record['instance_id']; g = gold[iid]; inv = inventory[iid]
        eligible = g['status'] == 'COMPLETE_NONEMPTY' and g['set_complete'] and bool(g['targets'])
        row = {'instance_id': iid, 'repo': record['repo'], 'base_commit': record['base_commit'],
               'function_scorable': eligible, 'gold_status': g['status'], 'gold_functions': g['targets'], 'gold_files': g['gold_files']}
        for arm in P.ARMS:
            folder = P.OUT / 'run' / arm / iid; path = folder / 'result.json'
            result = P.read(path) if path.exists() else {}
            status = result.get('status', 'EXECUTION_INCOMPLETE' if (folder / 'started.json').exists() else 'NOT_RUN')
            events = [json.loads(s) for s in (folder / 'events.jsonl').read_text().splitlines()] if (folder / 'events.jsonl').exists() else []
            local = [e for e in events if e['event'] == 'local_judge']
            u, fu, pu = usage(result), usage(result, 'file_'), usage(result, 'pruner')
            fn = metrics(result.get('predicted_functions', []), g['targets'] if eligible else [], inv['function_identities'], functions=True)
            file = metrics(result.get('predicted_files', []), g['gold_files'], inv['paths'], functions=False)
            entry = {'instance_id': iid, 'repo': record['repo'], 'status': status, 'function': fn, 'file': file,
                'raw_functions': result.get('predicted_functions', []), 'raw_files': result.get('predicted_files', []),
                'main_tokens': None if u['unknown'] else u['prompt'] + u['completion'],
                'main_prompt_tokens': u['prompt'], 'main_completion_tokens': u['completion'],
                'file_tokens': fu['prompt'] + fu['completion'], 'pruner_tokens': pu['prompt'] + pu['completion'],
                'seconds': result.get('elapsed_seconds'), 'file_seconds': result.get('file_stage_wall_seconds', 0),
                'local_input_tokens': sum(e['input_tokens'] for e in local), 'routes': dict(Counter(e['route'] for e in local)),
                'local_decisions': len(local), 'local_seconds': sum(e['wall_seconds'] for e in local),
                'source_reads': sum(e['event'] == 'source_returned' for e in events),
                'source_deliveries': sum(e['event'] == 'agent_seen' for e in events),
                'local_gold_reject_events': [dict(step=e['step'], function_id=e['function_id'], p_yes=e['p_yes']) for e in local
                    if e['route'] == 'reject' and e['function_id'].rsplit('@', 1)[0] in g['targets']],
                'local_gold_visits': [dict(step=e['step'], function_id=e['function_id'], route=e['route'], p_yes=e['p_yes']) for e in local
                    if e['function_id'].rsplit('@', 1)[0] in g['targets']]}
            arm_rows[arm].append(entry); raw[(iid, arm)] = entry
            row.update({arm + '_' + k: v for k, v in entry.items() if k not in ('instance_id', 'repo')})
        b, h = raw[(iid, 'baseline')], raw[(iid, 'hybrid_safe')]
        row['hybrid_comparable_tokens'] = h['main_tokens'] + b['file_tokens'] if h['main_tokens'] is not None else None
        row['hybrid_comparable_seconds'] = h['seconds'] + b['file_seconds'] if h['seconds'] is not None else None
        rows.append(row)
    attempted = [r for r in rows if all(r[a + '_status'] not in ('NOT_RUN', 'EXECUTION_INCOMPLETE') for a in P.ARMS)]
    summary = {'state': state['stage'], 'allocated': 100, 'attempted_pairs': len(attempted),
               'complete_pairs': sum(all(r[a + '_status'] == 'complete' for a in P.ARMS) for r in rows),
               'file_denominator': sum(bool(g['gold_files']) for g in gold.values()),
               'function_denominator': sum(g['status'] == 'COMPLETE_NONEMPTY' and g['set_complete'] and bool(g['targets']) for g in gold.values()),
               'metrics': {}, 'resources': {}, 'api_calls': 0, 'gpu_limit': 2, 'final': final}
    for arm, entries in arm_rows.items():
        groups = {}
        for unit in ('file', 'function'):
            vals = [r[unit] for r in entries if r[unit] is not None]
            groups[unit] = {'n': len(vals)}
            for k in (1, 3, 5):
                hits = sum(v[f'hit{k}'] for v in vals)
                groups[unit].update({f'hit{k}_numerator': hits, f'hit{k}': hits/len(vals) if vals else None,
                                    f'hit{k}_ci95': wilson(hits, len(vals))})
            for m in ('precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
                values = [v[m] for v in vals]
                groups[unit][m] = statistics.mean(values) if values else None
                if final: groups[unit][m + '_ci95'] = mean_ci(values)
        summary['metrics'][arm] = groups
        executed = [r for r in entries if r['status'] != 'NOT_RUN']
        summary['resources'][arm] = {'statuses': dict(Counter(r['status'] for r in entries)),
            'actual_main_tokens': sum(r['main_tokens'] for r in executed if r['main_tokens'] is not None),
            'main_prompt_tokens': sum(r['main_prompt_tokens'] for r in executed),
            'main_completion_tokens': sum(r['main_completion_tokens'] for r in executed),
            'main_pruner_tokens': sum(r['pruner_tokens'] for r in executed),
            'local_input_tokens': sum(r['local_input_tokens'] for r in executed),
            'local_decisions': sum(r['local_decisions'] for r in executed),
            'routes': dict(sum((Counter(r['routes']) for r in executed), Counter())),
            'local_gold_reject_events': sum(len(r['local_gold_reject_events']) for r in executed)}
    for arm in P.ARMS:
        vals = [r[arm + '_main_tokens'] + (r['baseline_file_tokens'] if arm == 'hybrid_safe' else 0) for r in attempted
                if r[arm + '_main_tokens'] is not None]
        seconds = [r[arm + '_seconds'] + (r['baseline_file_seconds'] if arm == 'hybrid_safe' else 0) for r in attempted if r[arm + '_seconds'] is not None]
        summary['resources'][arm].update(comparable_tokens=sum(vals), comparable_mean_tokens=statistics.mean(vals) if vals else None,
            comparable_mean_seconds=statistics.mean(seconds) if seconds else None, comparable_median_seconds=statistics.median(seconds) if seconds else None)
    pair = [r for r in attempted if r['function_scorable']]
    summary['paired_function_hit5'] = paired([bool(r['baseline_function']['hit5']) for r in pair], [bool(r['hybrid_safe_function']['hit5']) for r in pair])
    P.write(P.OUT / 'paired_results.json', {'summary': summary, 'records': rows})
    P.DOCS.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (P.DOCS / '逐题对照.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        w = csv.DictWriter(stream, fields); w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in rows)
    text = '# SWE-rebench100：Qwen3基线与4B剪枝对照\n\n'
    text += f"状态：{state['stage']}；已配对执行{len(attempted)}/100、完整成功{summary['complete_pairs']}/100。文件分母{summary['file_denominator']}，完整非空既有函数分母{summary['function_denominator']}；未运行不冒充模型失败，最终按固定名单计分。\n\n"
    text += '| 条件 | 文件Hit@1 | 文件Hit@3 | 文件Hit@5 | 函数Hit@1 | 函数Hit@3 | 函数Hit@5 | 函数Recall@5 | 全目标覆盖@5 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
    for arm in P.ARMS:
        f, fn = summary['metrics'][arm]['file'], summary['metrics'][arm]['function']
        text += '| ' + arm + ' | ' + ' | '.join([f"{v[f'hit{k}_numerator']}/{v['n']}" for v in (f, fn) for k in (1,3,5)] + [f"{fn['recall5']:.2%}", f"{fn['all_coverage5']:.2%}"]) + ' |\n'
    text += '\n主模型token与时间按同题补计共享文件阶段；4B自身计算、初始化与CPU缓存准备另外披露。基线固定先跑，缓存／共享GPU负载影响时间，token少不等于整体成本更低。\n\n'
    text += '冻结265池已被历史实验观察过；本轮不按历史表现选题，不调阈值；每仓最多一道，不能代表全部SWE-rebench或视为完全未见测试集。正式test保持封存。\n\n'
    text += '```json\n' + json.dumps(summary, ensure_ascii=False, indent=2) + '\n```\n'
    (P.DOCS / '实验报告_Rebench100_自动总览.md').write_text(text)
    return summary

if __name__ == '__main__': print(json.dumps(create(final=True), ensure_ascii=False))
