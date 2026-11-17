"""Independent, terminal-gated evaluation of the frozen Java128 roster.

No inference is performed. Gold is opened only after every selected arm has a
terminal artifact. Output directories are new and immutable. Ranking slots are
never compressed to remove malformed, nonexistent or duplicate predictions.
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

from .common import ARMS, RUN, read, sha

TERMINAL = {'complete', 'partial', 'worker_failed', 'timed_out', 'dependency_blocked',
            'preparation_failed', 'failed', 'error'}
KS = (1, 3, 5)
BOOTSTRAP_SEED = 20261117
BOOTSTRAP_DRAWS = 2000


def count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def wilson(success: int, n: int):
    if not n:
        return None
    z = 1.959963984540054
    center = (success/n + z*z/(2*n)) / (1+z*z/n)
    half = z * math.sqrt((success/n)*(1-success/n)/n + z*z/(4*n*n)) / (1+z*z/n)
    return [max(0., center-half), min(1., center+half)]


def bootstrap_mean(values: list[float], *, draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED):
    if not values:
        return None
    if len(set(values)) == 1:
        return [values[0], values[0]]
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(draws))
    # Explicit percentile convention avoids dependency/version differences.
    return [means[int((draws-1)*.025)], means[int((draws-1)*.975)]]


def ranking_slots(result: dict, index: dict, arm: str) -> dict:
    """Validate actual exported ranking fields without repairing identities."""
    file_fields = ('ranked_files',) if arm == 'locagent' else ('ranked_edit_files', 'file_rank_after_reflection', 'predicted_files')
    function_fields = ('ranked_functions', 'predicted_functions')
    file_key = next((k for k in file_fields if k in result), None)
    function_key = next((k for k in function_fields if k in result), None)
    canonical_counts = Counter(d.get('canonical_id', path+'::'+d.get('qualified_name', ''))
        for path, entry in index.items() for d in entry.get('definitions', []) if d.get('kind') == 'function')

    def slots(raw, level):
        if not isinstance(raw, list):
            return [], ['ranking_field_not_list']
        out, seen = [], set()
        for rank, value in enumerate(raw, 1):
            cid = None
            reason = None
            if level == 'file':
                cid = value if isinstance(value, str) else value.get('path') if isinstance(value, dict) else None
                if not isinstance(cid, str):
                    reason = 'invalid_file_slot'
                elif cid not in index:
                    reason = 'file_not_in_base_java_inventory'
            else:
                if isinstance(value, str):
                    cid = value
                elif isinstance(value, dict):
                    path, qn = value.get('path'), value.get('qualified_name')
                    supplied = value.get('canonical_id')
                    if isinstance(path, str) and isinstance(qn, str):
                        cid = path+'::'+qn
                        if supplied is not None and supplied != cid:
                            reason = 'canonical_id_disagrees_with_fields'
                    elif isinstance(supplied, str) and 'path' not in value and 'qualified_name' not in value:
                        cid = supplied
                    else:
                        reason = 'invalid_function_slot'
                else:
                    reason = 'invalid_function_slot'
                if reason is None and canonical_counts[cid] != 1:
                    reason = 'ambiguous_or_nonexistent_method_identity'
            duplicate = reason is None and isinstance(cid, str) and cid in seen
            if reason is None and isinstance(cid, str):
                seen.add(cid)
            if duplicate and reason is None:
                reason = 'duplicate_rank_slot'
            out.append({'rank': rank, 'raw': value, 'canonical_id': cid,
                        'valid': reason is None, 'reason': reason})
        return out, []

    files, file_errors = slots(result.get(file_key, []) if file_key else [], 'file')
    funcs, function_errors = slots(result.get(function_key, []) if function_key else [], 'function')
    return {'file': files, 'function': funcs, 'file_field': file_key, 'function_field': function_key,
            'field_errors': file_errors+function_errors}


def score_slots(slots: list[dict], target: set[str]):
    if not target:
        raise ValueError('An evaluable target set must be nonempty')
    def hits(k):
        return {s['canonical_id'] for s in slots[:k] if s['valid']} & target
    result = {f'hit{k}': bool(hits(k)) for k in KS}
    tp = len(hits(5))
    denominator = min(5, len(slots))
    precision = tp/denominator if denominator else 0.
    recall = tp/len(target)
    result.update(tp5=tp, prediction_slots5=denominator, target_count=len(target),
        precision5=precision, recall5=recall,
        f1_5=2*precision*recall/(precision+recall) if precision+recall else 0.,
        allcoverage5=(tp == len(target)),
        mrr10=next((1/s['rank'] for s in slots[:10] if s['valid'] and s['canonical_id'] in target), 0.))
    return result


def summarize_metrics(rows: list[dict], *, draws=BOOTSTRAP_DRAWS):
    n = len(rows)
    result = {'denominator': n}
    for key in ['hit1', 'hit3', 'hit5', 'allcoverage5']:
        num = sum(bool(r[key]) for r in rows)
        result[key] = {'numerator': num, 'denominator': n, 'value': num/n if n else None,
                       'ci95': wilson(num, n), 'ci_method': 'Wilson_score'}
    for key in ['precision5', 'recall5', 'f1_5', 'mrr10']:
        values = [r[key] for r in rows]
        result[key] = {'numerator_sum': sum(values), 'denominator': n,
                       'value': statistics.fmean(values) if values else None,
                       'ci95': bootstrap_mean(values, draws=draws),
                       'ci_method': 'task_percentile_bootstrap', 'draws': draws, 'seed': BOOTSTRAP_SEED}
    return result


def resource_record(directory: Path, result: dict, terminal: dict):
    """Use real receipts where available, with unknown usage retained as NA."""
    attempts = sorted((directory/'calls').glob('*/attempt_*_receipt.json'))
    starts = sorted((directory/'calls').glob('*/attempt_*_start.json'))
    known_prompt = known_completion = 0
    unknown = 0
    source = 'missing'
    if attempts or starts:
        source = 'raw_provider_attempt_receipts'
        finished = set()
        for p in attempts:
            row = read(p)
            finished.add((str(p.parent), p.name.replace('_receipt.json', '')))
            usage = row.get('usage') if isinstance(row.get('usage'), dict) else {}
            a, b = count(usage.get('prompt_tokens')), count(usage.get('completion_tokens'))
            if a is not None: known_prompt += a
            if b is not None: known_completion += b
            if a is None or b is None: unknown += 1
        unknown += sum((str(p.parent), p.name.replace('_start.json', '')) not in finished for p in starts)
    else:
        usage = result.get('usage') if isinstance(result.get('usage'), dict) else result
        a = count(usage.get('known_prompt_tokens', usage.get('prompt_tokens')))
        b = count(usage.get('known_completion_tokens', usage.get('completion_tokens')))
        u = count(usage.get('unknown_usage_requests', usage.get('usage_unknown_attempts')))
        if a is not None and b is not None and u is not None:
            known_prompt, known_completion, unknown = a, b, u
            source = 'actual_worker_usage'
        elif terminal.get('model_called') is False:
            source = 'terminal_explicit_no_model_call'
        else:
            known_prompt = known_completion = unknown = None
    total = known_prompt+known_completion if unknown == 0 and known_prompt is not None else None
    stages = result.get('stage_resources')
    file_usage = None
    if isinstance(stages, dict):
        values = [v for k, v in stages.items() if k.startswith('file_')]
        if values and all(isinstance(v, dict) and all(count(v.get(k)) is not None for k in
                    ['known_prompt_tokens', 'known_completion_tokens', 'usage_unknown_attempts']) for v in values):
            u = sum(v['usage_unknown_attempts'] for v in values)
            p = sum(v['known_prompt_tokens'] for v in values)
            c = sum(v['known_completion_tokens'] for v in values)
            file_usage = {'known_prompt_tokens': p, 'known_completion_tokens': c,
                          'unknown_usage_attempts': u, 'tokens': p+c if u == 0 else None}
    returned_usage = result.get('usage') if isinstance(result.get('usage'), dict) else {}
    return {'usage_source': source, 'known_prompt_tokens': known_prompt,
            'known_completion_tokens': known_completion, 'unknown_usage_attempts': unknown,
            'physical_main_tokens': total, 'shared_file_stage_usage': file_usage,
            'worker_elapsed_seconds': result.get('elapsed_seconds'),
            'controller_elapsed_seconds': terminal.get('elapsed_seconds'),
            'generation_seconds': result.get('generation_seconds'),
            'tool_elapsed_seconds': result.get('tool_elapsed_seconds'),
            'api_cost_usd': result.get('billed_api_usd', returned_usage.get('api_cost_usd')),
            'local_judge_usage': 'not_summed_here; distinct judge ledger required'}


def evaluate_run(root: str | Path, *, prefix3=False, draws=BOOTSTRAP_DRAWS):
    root = Path(root)
    allocation = read(root/'allocation.json')
    roster = allocation['records']
    if allocation.get('n') != 128 or len(roster) != 128 or len({r['instance_id'] for r in roster}) != 128:
        raise ValueError('Evaluation requires the complete frozen Java128 allocation')
    selected = {r['instance_id'] for r in roster[:3]} if prefix3 else {r['instance_id'] for r in roster}
    states, provenance, incomplete = {}, {}, []
    provenance[str(root/'allocation.json')] = sha(root/'allocation.json')
    # Complete this pass before opening any Gold or inventory file.
    for row in roster:
        iid = row['instance_id']
        states[iid] = {}
        for arm in ARMS:
            directory = root/'run'/iid/arm
            tp, rp = directory/'terminal.json', directory/'result.json'
            terminal, result, errors = {}, {}, []
            for p, kind in [(tp, 'terminal'), (rp, 'result')]:
                if p.exists():
                    provenance[str(p)] = sha(p)
                    try:
                        value = read(p)
                        if not isinstance(value, dict): raise ValueError('not a JSON object')
                        if kind == 'terminal': terminal = value
                        else: result = value
                    except Exception as error:
                        errors.append(f'{kind}_read_error:{type(error).__name__}:{error}')
            status = terminal.get('status', 'unrun' if not tp.exists() else 'terminal_error')
            is_terminal = status in TERMINAL
            if iid in selected and not is_terminal:
                incomplete.append({'instance_id': iid, 'arm': arm, 'status': status})
            states[iid][arm] = {'directory': directory, 'terminal': terminal, 'result': result,
                                'status': status, 'errors': errors}
    opened = not incomplete
    records = []
    gold_states = Counter()
    for row in roster:
        iid = row['instance_id']
        gold = None
        gold_error = None
        index = {}
        gold_status = 'NOT_SELECTED_PREFIX3' if iid not in selected else 'NOT_OPENED_WAITING_TERMINAL'
        if opened and iid in selected:
            gp, ip = root/'evaluator_private'/iid/'gold.json', root/'public'/iid/'code_index.json'
            try:
                if not gp.is_file(): raise FileNotFoundError('Gold missing; never interpreted as empty targets')
                gold = read(gp); index = read(ip)
                provenance[str(gp)], provenance[str(ip)] = sha(gp), sha(ip)
                if any(gold.get(k) != row[k] for k in ('instance_id', 'repo', 'base_commit')):
                    raise ValueError('Gold identity differs from the allocation')
                if gold.get('base_index_sha256') is not None and gold['base_index_sha256'] != provenance[str(ip)]:
                    raise ValueError('Gold/index SHA mismatch')
                for level, key in [('file', 'file_targets'), ('function', 'function_targets')]:
                    values = gold.get(key)
                    if not isinstance(values, list) or any(not isinstance(v, str) for v in values) or len(values) != len(set(values)):
                        raise ValueError(f'Invalid {key}')
                    if gold.get(level+'_evaluable') is True and not values:
                        raise ValueError(f'Evaluable {level} Gold cannot be empty')
                if gold.get('function_evaluable') is True and gold.get('existing_target_set_complete') is not True:
                    raise ValueError('Incomplete existing-function Gold marked evaluable')
                if any(path not in index for path in gold['file_targets']):
                    raise ValueError('Existing-file Gold absent from the bound base inventory')
                inventory_methods = Counter(d.get('canonical_id', path+'::'+d.get('qualified_name', ''))
                    for path, entry in index.items() for d in entry.get('definitions', []) if d.get('kind') == 'function')
                if gold.get('function_evaluable') is True and any(inventory_methods[cid] != 1 for cid in gold['function_targets']):
                    raise ValueError('Evaluable method Gold absent or ambiguous in the bound base inventory')
                gold_status = gold.get('function_status', 'ERROR_MISSING_STATUS')
            except Exception as error:
                gold, index = None, {}
                gold_status = 'ERROR_MISSING_OR_INVALID_GOLD'
                gold_error = f'{type(error).__name__}:{error}'
        gold_states[gold_status] += 1
        arms = {}
        baseline_resource = None
        for arm in ARMS:
            state = states[iid][arm]
            result = state['result']
            simulation = result.get('simulation') is True or result.get('not_benchmark_result') is True
            slots = ranking_slots({} if simulation else result, index, arm) if gold is not None else None
            resource = resource_record(state['directory'], result, state['terminal'])
            if arm == 'cosil': baseline_resource = resource
            reattributed = None
            if arm == 'sfpruner' and (root/'run'/iid/'shared.json').is_file() and baseline_resource:
                shared = baseline_resource.get('shared_file_stage_usage')
                reattributed = shared['tokens'] if shared is not None else None
            resource['shared_file_stage_reattributed_tokens'] = reattributed
            resource['fair_attributed_main_tokens'] = (
                resource['physical_main_tokens']+reattributed if arm == 'sfpruner' and resource['physical_main_tokens'] is not None and reattributed is not None
                else resource['physical_main_tokens'] if arm != 'sfpruner' else None)
            scores = {}
            for level, key in [('file', 'file_targets'), ('function', 'function_targets')]:
                eligible = gold is not None and gold.get(level+'_evaluable') is True
                scores[level] = score_slots(slots[level], set(gold[key])) if eligible else None
            arms[arm] = {'status': 'invalid_simulation' if simulation else state['status'],
                         'result_status': result.get('status'), 'errors': state['errors'],
                         'ranking': slots, 'metrics': scores, 'resource': resource}
        records.append({'instance_id': iid, 'repo': row['repo'], 'base_commit': row['base_commit'],
                        'selected_for_evaluation': iid in selected, 'gold_status': gold_status, 'gold_error': gold_error,
                        'file_evaluable': gold.get('file_evaluable') if gold is not None else None,
                        'function_evaluable': gold.get('function_evaluable') if gold is not None else None,
                        'gold_files': gold['file_targets'] if gold is not None else None,
                        'gold_functions': gold['function_targets'] if gold is not None else None,
                        'gold_limitations': gold.get('limitations') if gold is not None else None, 'arms': arms})
    metrics = {arm: {level: summarize_metrics([r['arms'][arm]['metrics'][level] for r in records
        if r['selected_for_evaluation'] and r['arms'][arm]['metrics'][level] is not None], draws=draws)
        for level in ['file', 'function']} for arm in ARMS} if opened else None
    selected_rows = [r for r in records if r['selected_for_evaluation']]
    summary = {'schema': 'multiswe_java128_strict_terminal_evaluation_v1', 'allocated': 128,
        'selected': len(selected), 'scope': 'prefix3_engineering_description_only' if prefix3 else 'full128',
        'status': 'WAITING_TERMINAL_NO_GOLD_OPENED' if not opened else
                  'INCOMPLETE_GOLD' if any(r['gold_error'] for r in selected_rows) else 'EVALUATED',
        'gold_opened': opened, 'incomplete_arms': incomplete,
        'gold_status_counts': dict(gold_states),
        'file_denominator': sum(r['file_evaluable'] is True for r in selected_rows) if opened else None,
        'function_denominator': sum(r['function_evaluable'] is True for r in selected_rows) if opened else None,
        'arm_status_counts': {arm: dict(Counter(r['arms'][arm]['status'] for r in selected_rows)) for arm in ARMS},
        'metrics': metrics,
        'definitions': {'file_scope': 'existing production Java files; new/non-Java targets disclosed by Gold',
            'function_scope': 'complete nonempty set of existing production Java methods/explicit constructors',
            'identity': 'exact path::qualified_name including parameter signature; no alias expansion',
            'slots': 'invalid and duplicate predictions retain original ranks; duplicate identities count once',
            'precision5': 'unique true targets in first 5 original slots / min(5, number of original slots); empty output gives 0',
            'recall5': 'unique true targets in first 5 original slots / all existing targets',
            'macro': 'mean per-task precision, recall and F1; F1 is not computed from aggregate macro P/R',
            'mrr10': 'mean reciprocal rank of first correct original slot within first 10',
            'failure_policy': 'all terminal model/timeout/dependency failures remain in evaluable denominators; available partial ranks retained',
            'missing_gold': 'ERROR, never an empty target set or a model miss',
            'ci': f'Wilson 95% for binary metrics; {draws} task bootstrap draws, seed {BOOTSTRAP_SEED}, for means',
            'resources': 'unknown token usage is NA; shared file-stage physical execution and fair attribution are separate; judge usage requires its own ledger'},
        'provenance_sha256': provenance}
    return {'summary': summary, 'records': records}


def metric_cell(metric):
    if metric['value'] is None:
        return 'NA'
    num = metric.get('numerator', metric.get('numerator_sum'))
    ntext = str(num) if isinstance(num, int) else f'{num:.4f}'
    ci = metric['ci95']
    return f"{ntext}/{metric['denominator']} = {metric['value']*100:.2f}% [{ci[0]*100:.2f}, {ci[1]*100:.2f}]"


def report_markdown(evaluated):
    s, rows = evaluated['summary'], evaluated['records']
    text = ['# Multi-SWE-bench Java128：CoSIL、SFPruner与LocAgent定位评价', '',
        f"状态：`{s['status']}`；冻结任务128题，本报告指定评价{s['selected']}题。", '']
    if s['scope'].startswith('prefix3'):
        text += ['本报告仅描述预先固定的3题金丝雀工程链路；不用于按准确率选方法、调参数或替换题目。其余125题不打开Gold。', '']
    if not s['gold_opened']:
        text += [f"尚有{len(s['incomplete_arms'])}个指定题臂未终态，因此未打开任何Gold；定位指标暂为NA。", '']
    else:
        text += [f"文件可评价分母：{s['file_denominator']}/{s['selected']}；既有方法可评价分母：{s['function_denominator']}/{s['selected']}。",
                 '每个运行失败仍保留在对应可评价分母中；缺失/错误Gold、不可映射NA和集合不完整partial单独列出。', '']
        if s['status'] == 'INCOMPLETE_GOLD':
            text += ['存在缺失或异常Gold，下表仅为已核定目标范围的临时统计，不能称为完整Java128最终成绩。', '']
        keys = ['hit1', 'hit3', 'hit5', 'precision5', 'recall5', 'f1_5', 'allcoverage5', 'mrr10']
        for level, label in [('file', '文件级（既有生产Java文件）'), ('function', '方法级（含显式构造函数）')]:
            text += [f'## {label}', '', '| 方法 | Hit@1 | Hit@3 | Hit@5 | Macro-P@5 | Macro-R@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |',
                     '|---|---|---|---|---|---|---|---|---|']
            for arm in ARMS:
                text.append('| '+arm+' | '+' | '.join(metric_cell(s['metrics'][arm][level][key]) for key in keys)+' |')
            text += ['']
        text += ['方括号为95%置信区间。Hit和AllCoverage分子为命中题数；宏指标及MRR分子为逐题指标之和、分母为可评价题数。', '']
    text += ['## 状态与评价口径', '', f"Gold状态：`{json.dumps(s['gold_status_counts'], ensure_ascii=False)}`。", '']
    for arm in ARMS:
        text.append(f"- {arm}：`{json.dumps(s['arm_status_counts'][arm], ensure_ascii=False)}`。")
    text += ['', '方法身份严格匹配完整相对路径、限定名与参数类型签名；裸方法名不展开。非法和重复输出保留原始槽位，不能通过清除错误输出提升Hit@k。',
        'Macro-P@5的分母为实际前五个原始预测槽数（最多5）；无输出为0。Macro-R@5覆盖全部既有目标，Macro-F1@5先逐题计算再平均。',
        '新建方法/文件、方法外修改和非Java部分按Gold范围单列；本表不等同于补丁修复成功率。', '',
        '## 资源记录', '', '| 方法 | usage可完整核实题数 | 物理主模型token合计 | 公平归属token合计 | 控制器时延有记录题数 |',
        '|---|---:|---:|---:|---:|']
    selected = [r for r in rows if r['selected_for_evaluation']]
    for arm in ARMS:
        resources = [r['arms'][arm]['resource'] for r in selected]
        physical = [r['physical_main_tokens'] for r in resources if r['physical_main_tokens'] is not None]
        fair = [r['fair_attributed_main_tokens'] for r in resources if r['fair_attributed_main_tokens'] is not None]
        text.append(f"| {arm} | {len(physical)}/{len(resources)} | {sum(physical) if physical else 'NA'}（已知部分） | {sum(fair) if fair else 'NA'}（{len(fair)}/{len(resources)}题已知） | {sum(r['controller_elapsed_seconds'] is not None for r in resources)}/{len(resources)} |")
    text += ['', '共享文件选择阶段只由CoSIL物理运行一次；SFPruner的公平归属另加相同文件阶段的实际token。未知usage保留NA，不补0。剪枝器token、GPU能耗和硬件费用需独立账本，本表不把主模型token等同系统总资源。', '',
             '完整逐题状态、原始排名槽、严格评价、usage来源和输入SHA见同目录JSON/CSV。', '']
    return '\n'.join(text)


def write_report(evaluated: dict, output: str | Path):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Use a new report directory; existing reports are immutable')
    output.mkdir(parents=True)
    (output/'summary.json').write_text(json.dumps(evaluated['summary'], ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    (output/'per_issue.json').write_text(json.dumps(evaluated['records'], ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    flat = []
    for row in evaluated['records']:
        base = {k: row[k] for k in ['instance_id', 'repo', 'base_commit', 'selected_for_evaluation',
                                  'gold_status', 'gold_error', 'file_evaluable', 'function_evaluable']}
        base.update(gold_files=json.dumps(row['gold_files'], ensure_ascii=False),
                    gold_functions=json.dumps(row['gold_functions'], ensure_ascii=False))
        for arm in ARMS:
            a = row['arms'][arm]
            base[arm+'_status'], base[arm+'_result_status'] = a['status'], a['result_status']
            for level in ['file', 'function']:
                base[f'{arm}_{level}_original_slots'] = json.dumps(a['ranking'][level] if a['ranking'] else None, ensure_ascii=False)
                for key in ['hit1', 'hit3', 'hit5', 'precision5', 'recall5', 'f1_5', 'allcoverage5', 'mrr10']:
                    base[f'{arm}_{level}_{key}'] = a['metrics'][level][key] if a['metrics'][level] is not None else None
            for key in ['physical_main_tokens', 'fair_attributed_main_tokens', 'shared_file_stage_reattributed_tokens',
                        'known_prompt_tokens', 'known_completion_tokens', 'unknown_usage_attempts', 'usage_source',
                        'controller_elapsed_seconds', 'worker_elapsed_seconds', 'generation_seconds', 'tool_elapsed_seconds', 'api_cost_usd']:
                base[arm+'_'+key] = a['resource'][key]
        flat.append(base)
    with (output/'per_issue.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader(); writer.writerows(flat)
    (output/'总览.md').write_text(report_markdown(evaluated), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=RUN)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--prefix3', action='store_true')
    args = p.parse_args()
    evaluated = evaluate_run(args.root, prefix3=args.prefix3)
    write_report(evaluated, args.out)
    print(json.dumps({k: evaluated['summary'][k] for k in ['status', 'allocated', 'selected', 'gold_opened',
                                                         'file_denominator', 'function_denominator']}, ensure_ascii=False))
    return 0 if evaluated['summary']['status'] == 'EVALUATED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
