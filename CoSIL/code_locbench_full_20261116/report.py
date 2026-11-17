"""Lossless CPU aggregation of completed, frozen LocBench batches.

Every input report must pass its terminal/output provenance gate before any
gold-bearing evaluation or CSV is parsed.  Only the fixed hash-order prefix is
accepted.  This module never calls a model, alters predictions or opens an
uncompleted batch's private targets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

from code_locbench_sfpruner_20261116 import report as original
from code_locbench_sfpruner_20261116.pilot import key as sampling_key

c, e, f = original.c, original.e, original.f
ARMS = original.ARMS
CUTS = (100, 200, 300, 400, 500, 560)
METRICS = tuple(metric + str(k) for k in (1, 3, 5)
                for metric in ('hit', 'precision', 'recall', 'f1', 'all_coverage')) + ('mrr10',)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report_batch(work):
    """The root freezes inputs before GPU startup; evaluation never freezes late."""
    work = Path(work).resolve(strict=True)
    frozen = work / 'controller/report_freeze.json'
    if not frozen.is_file():
        raise ValueError('A report freeze written before inference is required')
    return original.execute(frozen, work / 'reports/final')


def verified_outputs(directory):
    directory = Path(directory).resolve(strict=True)
    files = read(directory / 'output_sha256.json')
    if not isinstance(files, dict) or not files:
        raise ValueError('Missing nonempty report output manifest')
    actual = {p.name for p in directory.iterdir() if p.is_file()}
    if actual != set(files) | {'output_sha256.json'}:
        raise ValueError('Report output manifest is incomplete or has extra files')
    for name, wanted in files.items():
        path = directory / name
        if (Path(name).name != name or path.is_symlink() or not path.is_file()
                or sha(path) != wanted):
            raise ValueError('Report output hash/shape drift: ' + str(path))
    return directory, {str(directory / name): value for name, value in files.items()}


def method_signature(controller):
    required = ('controller_sha256', 'execution', 'arms', 'replay_policy',
                'arm_timeout_seconds', 'scheduling')
    if controller.get('simulation') is not False or any(k not in controller for k in required):
        raise ValueError('Real frozen execution and scheduling contracts are required')
    if controller['execution'] != c.FrozenBackend().protocol():
        raise ValueError('Underlying frozen model/renderer/execution changed')
    return {key: controller[key] for key in required}


def report_gate(directory):
    """Read only provenance and terminal metadata until all batches pass."""
    directory, hashes = verified_outputs(directory)
    summary = read(directory / 'summary.json')
    frozen = read(directory / 'report_freeze.json')
    gate = read(directory / 'terminal_gate.json')
    allocated = read(directory / 'allocation.json')
    count, runnable = summary.get('allocated'), summary.get('runnable')
    if (summary.get('status') != 'FINAL' or summary.get('dataset') != 'czlll/Loc-Bench_V1'
            or summary.get('revision') != original.SOURCE_REVISION
            or summary.get('official_scorer_sha256') != original.OFFICIAL_SCORER_SHA
            or summary.get('evaluator_sha256') != c.sha(e.__file__)
            or summary.get('gold_read_after_all_runnable_terminal') is not True
            or summary.get('test_unsealed') is not False
            or summary.get('new_model_calls_by_evaluator') != 0
            or not isinstance(count, int) or count not in (60, 100)
            or not isinstance(runnable, int) or not 0 <= runnable <= count):
        raise ValueError('Wrong/nonfinal batch dataset or evaluation contract')
    if (frozen.get('allocated') != count or frozen.get('runnable') != runnable
            or frozen.get('status') != 'FROZEN_BEFORE_SCORING'
            or frozen.get('protocol_sha256') != summary.get('protocol_sha256')
            or sha(directory / 'report_freeze.json') != summary.get('report_freeze_sha256')):
        raise ValueError('Batch report/input freeze drift')
    records = allocated.get('records', [])
    if (allocated.get('n') != count or len(records) != count
            or len({row['instance_id'] for row in records}) != count):
        raise ValueError('Incomplete or duplicate allocation')
    if (gate.get('passed') is not True or gate.get('issues') != runnable
            or gate.get('terminal_pairs') != runnable or gate.get('terminal_arms') != 2 * runnable
            or gate.get('gold_opened_during_gate') is not False):
        raise ValueError('All runnable arm and pair terminals must precede scoring')
    terminals = gate.get('terminal_sha256', {})
    if len(terminals) != 3 * runnable:
        raise ValueError('Terminal gate omits runnable arm or pair receipts')
    for path, wanted in terminals.items():
        if not Path(path).is_file() or sha(path) != wanted:
            raise ValueError('Original terminal receipt drift: ' + path)
    controller = None
    if runnable:
        path = Path(frozen['run_root']) / 'freeze.json'
        expected = frozen['source_sha256'].get(str(path.resolve(strict=True)))
        if not expected or sha(path) != expected:
            raise ValueError('Controller freeze lost its original source binding')
        controller = read(path)
        if controller.get('protocol_sha256') != gate.get('protocol_sha256'):
            raise ValueError('Controller and terminal protocol mismatch')
        method_signature(controller)
        hashes[str(path.resolve())] = expected
    return {'directory': directory, 'summary': summary, 'frozen': frozen, 'gate': gate,
            'allocation': records, 'controller': controller, 'hashes': hashes}


def official_order(frozen):
    """Only the three public identity columns, never target/patch columns."""
    path = Path(frozen['parquet'])
    if sha(path) != original.PARQUET_SHA:
        raise ValueError('Official LocBench source snapshot changed')
    import pyarrow.parquet as pq
    rows = pq.read_table(path, columns=['instance_id', 'repo', 'base_commit']).to_pylist()
    if len(rows) != 560 or len({row['instance_id'] for row in rows}) != 560:
        raise ValueError('Expected the exact official560 identity pool')
    return sorted(rows, key=sampling_key)


def validate_prefix(batches, ordered):
    flat = [row for batch in batches for row in batch['allocation']]
    if len(flat) not in CUTS or len({r['instance_id'] for r in flat}) != len(flat):
        raise ValueError('Cumulative scope must be a unique fixed checkpoint prefix')
    identity = ('instance_id', 'repo', 'base_commit')
    got = [{key: row[key] for key in identity} for row in flat]
    if got != ordered[:len(flat)]:
        raise ValueError('A batch was skipped, replaced or reordered from the frozen hash prefix')
    offset = 0
    for batch in batches:
        count = len(batch['allocation'])
        if count != min(100, 560 - offset):
            raise ValueError('Only final fixed batch may contain60 issues')
        offset += count
    return flat


def same_number(a, b):
    return (isinstance(a, (int, float)) and not isinstance(a, bool)
            and isinstance(b, (int, float)) and not isinstance(b, bool)
            and math.isfinite(a) and math.isfinite(b)
            and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12))


def validate_record(row):
    """Check accepted slots and scores losslessly; no raw identity repair."""
    for arm in ARMS:
        if not isinstance(row.get(arm + '_status'), str):
            raise ValueError('Execution status must remain separate from correctness')
        for unit in ('file', 'function'):
            target = row['gold_files'] if unit == 'file' else row['gold_functions']
            eligible = bool(target) if unit == 'file' else row['function_scorable']
            value = row[arm + '_' + unit]
            if not eligible:
                if value is not None:
                    raise ValueError('NA target group carries numeric metrics')
                continue
            if not isinstance(value, dict) or not isinstance(value.get('slots'), list):
                raise ValueError('Eligible issue omitted metrics or original rank slots')
            slots = value['slots']
            for k in (1, 3, 5):
                for metric, expected in e.scores(slots, target, k).items():
                    if not same_number(value[metric + str(k)], expected):
                        raise ValueError('Stored per-issue score differs from its accepted rank slots')
            expected_mrr = next((1 / (rank + 1) for rank, name in enumerate(slots[:10])
                                 if name in set(target)), 0)
            if not same_number(value['mrr10'], expected_mrr):
                raise ValueError('Stored per-issue MRR differs from accepted slots')


def load_scores(batch):
    directory, summary = batch['directory'], batch['summary']
    name = summary['main_group']
    evaluated = read(directory / (name + '_evaluation.json'))
    if evaluated['summary'] != summary['groups'][name]:
        raise ValueError('Batch evaluation/summary metrics disagree')
    ids = [row['instance_id'] for row in batch['allocation']]
    if [row['instance_id'] for row in evaluated['records']] != ids:
        raise ValueError('Batch evaluation silently changed allocation membership/order')
    score_summary = evaluated['summary']
    for unit in ('file', 'function'):
        for arm in ARMS:
            entries = [row[arm + '_' + unit] for row in evaluated['records']
                       if row[arm + '_' + unit] is not None]
            reported = score_summary['metrics'][arm][unit]
            if reported['n'] != len(entries):
                raise ValueError('Batch summary silently changed eligible denominator')
            for k in (1, 3, 5):
                if reported['hit' + str(k) + '_numerator'] != sum(row['hit' + str(k)] for row in entries):
                    raise ValueError('Batch summary hit count differs from retained issue scores')
            for metric in ('precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
                expected = statistics.mean(row[metric] for row in entries) if entries else None
                if not (expected is None and reported[metric] is None) and not same_number(reported[metric], expected):
                    raise ValueError('Batch macro metric differs from its retained issue scores')
    with (directory / (name + '_逐题定位与资源.csv')).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream); csv_rows = list(reader); fields = reader.fieldnames
    if [row['instance_id'] for row in csv_rows] != ids:
        raise ValueError('CSV omits, duplicates or reorders an allocated issue')
    for row, flat in zip(evaluated['records'], csv_rows):
        validate_record(row)
        for key in ('repo', 'base_commit', 'gold_status'):
            if row[key] != flat[key]:
                raise ValueError('CSV/evaluation identity or Gold status mismatch')
        for key in ('gold_files', 'gold_functions'):
            if row[key] != json.loads(flat[key]):
                raise ValueError('CSV/evaluation target mismatch')
        for arm in ARMS:
            if row[arm + '_status'] != flat[arm + '_status']:
                raise ValueError('CSV/evaluation execution status mismatch')
            for unit in ('file', 'function'):
                value = row[arm + '_' + unit]
                if value is None:
                    continue
                for metric in METRICS:
                    column = arm + '_' + unit + '_' + metric
                    if column in flat and not same_number(float(flat[column]), value[metric]):
                        raise ValueError('CSV/evaluation per-issue metric mismatch')
        flat['source_report'] = str(directory)
    return evaluated['records'], csv_rows, fields


def summarize(rows, *, draws=5000):
    summary = {'allocated': len(rows), 'function_denominator': sum(r['function_scorable'] for r in rows),
        'file_denominator': sum(bool(r['gold_files']) for r in rows),
        'gold_statuses': dict(Counter(r['gold_status'] for r in rows)),
        'complete_pairs': sum(all(r[a + '_status'] == 'complete' for a in ARMS) for r in rows),
        'denominator_policy': 'fixed hash-order prefix; eligible failures retained; NA separate by unit',
        'bootstrap_seed': e.DEFAULT_SEED, 'bootstrap_draws': draws, 'metrics': {}, 'statuses': {}}
    for arm in ARMS:
        summary['metrics'][arm] = {}
        summary['statuses'][arm] = dict(Counter(r[arm + '_status'] for r in rows))
        for unit in ('file', 'function'):
            values = [r[arm + '_' + unit] for r in rows if r[arm + '_' + unit] is not None]
            metric = e.aggregate(values, seed=e.DEFAULT_SEED, draws=draws)
            for k in (1, 3):
                for kind in ('precision', 'recall', 'f1'):
                    key = kind + str(k)
                    data = [value[key] for value in values]
                    metric[key] = statistics.mean(data) if data else None
                    metric[key + '_ci95'] = e.mean_ci(data, seed=e.DEFAULT_SEED, draws=draws)
            summary['metrics'][arm][unit] = metric
    eligible = [r for r in rows if r['function_scorable']]
    paired = {'hit' + str(k): e.paired([r['baseline_function']['hit' + str(k)] for r in eligible],
              [r['hybrid_safe_function']['hit' + str(k)] for r in eligible],
              seed=e.DEFAULT_SEED, draws=draws) for k in (1, 3, 5)}
    return {'summary': summary, 'records': rows, 'paired_function': paired}


def resources(csv_rows):
    details = {}
    for row in csv_rows:
        for arm in ARMS:
            resource = json.loads(row[arm + '_resource'])
            details[(row['instance_id'], arm)] = {'resource': resource}
    values = original.prior.resource_summary({'records': csv_rows, 'details': details})
    shared_known, shared_unknown = 0, 0
    local = {'input_tokens': 0, 'decisions': 0, 'forward_seconds': 0., 'routes': Counter()}
    for row in csv_rows:
        baseline = details[(row['instance_id'], 'baseline')]['resource']
        stage = baseline.get('file_main_usage')
        if stage is not None and all(type(stage.get(k)) is int and stage[k] >= 0 for k in ('prompt', 'completion', 'unknown')):
            shared_known += stage['prompt'] + stage['completion']
            shared_unknown += bool(stage['unknown'])
        elif baseline.get('usage_source') != 'verified_preparation_block_no_worker':
            shared_unknown += 1
        judge = details[(row['instance_id'], 'hybrid_safe')]['resource']
        local['input_tokens'] += judge.get('local_input_tokens', 0)
        local['decisions'] += judge.get('local_decisions', 0)
        local['forward_seconds'] += judge.get('local_forward_seconds', 0.)
        local['routes'].update(judge.get('routes', {}))
    a, b = (values[arm]['main_tokens_total'] for arm in ARMS)
    fair = b + shared_known if b is not None and not shared_unknown else None
    return {'physical_main_by_arm': values, 'shared_file_stage_known_tokens': shared_known,
        'shared_file_stage_unknown_tasks': shared_unknown,
        'sfpruner_main_tokens_including_shared_file_stage': fair,
        'fair_main_token_relative_reduction': 1 - fair / a if fair is not None and a else None,
        'actual_both_arms_main_tokens': a + b if a is not None and b is not None else None,
        'local_4B_judge': {**local, 'routes': dict(local['routes'])},
        'latency_note': 'worker seconds include main-service queue wait; shared-file reuse prevents interpreting raw worker ratio as independent end-to-end speedup',
        'external_API_USD': 0, 'GPU_energy_and_depreciation': 'not measured'}


def compatible(batches, ids):
    records, contract = [], None
    for batch in batches:
        value = read(batch['directory'] / 'official_compatible.json')
        semantics = {key: item for key, item in value.items() if key not in ('n', 'records', 'metrics')}
        if contract is not None and contract != semantics:
            raise ValueError('Official compatibility scoring semantics changed')
        contract = semantics
        if value['n'] != len(batch['allocation']) or [r['instance_id'] for r in value['records']] != [r['instance_id'] for r in batch['allocation']]:
            raise ValueError('Official compatibility view changed roster')
        records.extend(value['records'])
    if [row['instance_id'] for row in records] != ids:
        raise ValueError('Official compatibility record order changed')
    metrics = {arm: {unit: {key: statistics.mean(row[arm][unit][key] for row in records)
                  for key in records[0][arm][unit]} for unit in ('file', 'function')} for arm in ARMS}
    return {**contract, 'n': len(records), 'records': records, 'metrics': metrics}


def markdown(summary, evaluated, batch_summaries):
    s, n = evaluated['summary'], summary['allocated']
    lines = [f'# LocBench累计{n}题：CoSIL与SFPruner', '',
        f'这是固定560题哈希顺序前缀的已完成{n}题；未按结果删题、换题或调参。原100题保持原字节复用，各批结果来自同一冻结模型和执行契约。', '',
        '函数主表（P/R/F1为逐题宏平均，失败留在原可评价分母）：', '']
    rows = []
    for arm in ARMS:
        m = s['metrics'][arm]['function']
        rows.append([arm, *[f.fraction(m['hit' + str(k) + '_numerator'], m['n']) for k in (1, 3, 5)],
                     *[f.percent(m[key]) for key in ('precision5', 'recall5', 'f15')]])
    lines += [f.table(['条件', '函数Hit@1', 'Hit@3', 'Hit@5', 'Macro-P@5', 'Macro-R@5', 'Macro-F1@5'], rows), '',
        f'固定任务{n}；文件可评价{s["file_denominator"]}；函数可评价{s["function_denominator"]}；两臂均执行完成{s["complete_pairs"]}。状态分布：`{json.dumps(s["statuses"], ensure_ascii=False)}`。', '',
        '文件主表使用实际文件智能体排名，两臂共享同题文件阶段：', '']
    rows = []
    for arm in ARMS:
        m = s['metrics'][arm]['file']
        rows.append([arm, *[f.fraction(m['hit' + str(k) + '_numerator'], m['n']) for k in (1, 3, 5)],
                     *[f.percent(m[key]) for key in ('precision5', 'recall5', 'f15')]])
    lines += [f.table(['条件', '文件Hit@1', 'Hit@3', 'Hit@5', 'Macro-P@5', 'Macro-R@5', 'Macro-F1@5'], rows), '',
        '同题配对：', '']
    rows = []
    for metric, p in evaluated['paired_function'].items():
        rows.append([metric, p['n'], p['both_success'], p['only_a'], p['only_b'], p['both_failure'],
                     f.percent(p['b_minus_a']), str(p['b_minus_a_ci95']), p['exact_mcnemar_p']])
    lines += [f.table(['指标', 'n', '均命中', '仅CoSIL', '仅SFPruner', '均未中', 'SF−CoSIL', '配对95%CI', '精确McNemar p'], rows), '',
        '单组Hit使用Wilson95%区间；宏平均与配对差使用冻结seed的issue bootstrap。各指标完整区间保存在evaluation.json。未校正仓库内相关；每100题查看属于持续描述性监控，不构成重复显著性检验后的确认性结论，也不用于挑选最终版本。', '',
        '各批固定范围及累计检查均保留：', '']
    rows = []
    for batch in batch_summaries:
        rows.append([batch['start_rank'], batch['end_rank'], batch['allocated'], batch['directory'],
            *[str(batch['function_hit_counts'][arm]) for arm in ARMS]])
    lines += [f.table(['起始秩', '结束秩', '分配题数', '原报告目录', 'CoSIL函数Hit1/3/5', 'SFPruner函数Hit1/3/5'], rows), '',
        '资源账（本地主模型，API费用0；未知usage不计零）：', '',
        '```json', json.dumps(summary['resources'], ensure_ascii=False, indent=2), '```', '',
        'SFPruner物理账未重复计共享文件阶段；比较主模型总token时使用补计共享文件阶段后的值。4B判决token另计，启动探针不属于任务内token。worker耗时包含服务排队且复用文件阶段，不据此声称独立端到端加速比。', '',
        '主指标严格使用已有函数path::qualified_name，初始化器不折叠，无效/重复排名不压缩。聚合只使用原报告已校验的每题槽位和指标，未重建无效原预测，也未重跑原100题。官方兼容口径独立保存在official_compatible.json，Acc不能改称主表Hit，函数docs投影文件排名不能替代实际文件候选。', '',
        '输入报告输出哈希与全部终态回执先通过核验，随后才解析已完成批次的金标承载评价文件。未打开本项目封存test，未读取未来批次私有目标，未训练、修复、修改论文或历史矩阵。', '']
    return '\n'.join(lines)


def combine(report_dirs, out, *, draws=5000):
    out = Path(out)
    if out.exists():
        raise FileExistsError('Never overwrite a cumulative checkpoint')
    if draws < 40:
        raise ValueError('At least40 bootstrap draws required')
    if not report_dirs:
        raise ValueError('At least the frozen original100 report is required')
    # This entire loop is provenance-only; evaluations/CSVs are opened below.
    batches = [report_gate(path) for path in report_dirs]
    signatures = [method_signature(batch['controller']) for batch in batches if batch['controller'] is not None]
    if not signatures or any(signature != signatures[0] for signature in signatures):
        raise ValueError('Cannot combine different model, prompt, renderer or scheduling methods')
    order = official_order(batches[0]['frozen'])
    allocation = validate_prefix(batches, order)
    records, flat, headers, batch_summaries, inputs = [], [], [], [], {}
    offset = 0
    for batch in batches:
        rows, csv_rows, fields = load_scores(batch)
        for key in fields + ['source_report']:
            if key not in headers:
                headers.append(key)
        records.extend(rows); flat.extend(csv_rows); inputs.update(batch['hashes'])
        metric = batch['summary']['groups'][batch['summary']['main_group']]['metrics']
        batch_summaries.append({'directory': str(batch['directory']), 'allocated': len(rows),
            'start_rank': offset + 1, 'end_rank': offset + len(rows),
            'function_hit_counts': {arm: [metric[arm]['function']['hit' + str(k) + '_numerator']
                                        for k in (1, 3, 5)] for arm in ARMS}})
        offset += len(rows)
    evaluated = summarize(records, draws=draws)
    official = compatible(batches, [row['instance_id'] for row in records])
    n = len(records)
    summary = {'schema': 1, 'status': 'FINAL_CUMULATIVE_CHECKPOINT', 'allocated': n,
        'dataset': 'czlll/Loc-Bench_V1', 'revision': original.SOURCE_REVISION,
        'parent_official_dataset_tasks': 560, 'selection_seed': 20261116,
        'scope': 'fixed stable-hash-order prefix, all eligible failures retained',
        'main_group': 'all' + str(n), 'groups': {'all' + str(n): evaluated['summary']},
        'coverage_and_status': {key: evaluated['summary'][key] for key in ('allocated', 'function_denominator',
            'file_denominator', 'gold_statuses', 'complete_pairs', 'statuses')},
        'batches': batch_summaries, 'resources': resources(flat),
        'train_repo_overlap_tasks': sum(row['train_repo_seen'] for row in allocation),
        'train_repo_overlap_repos': len({row['repo'].casefold() for row in allocation if row['train_repo_seen']}),
        'gold_bearing_reports_parsed_after_all_included_batch_terminal_gates': True,
        'future_batch_gold_opened': False, 'historical_predictions_reexecuted': False,
        'accepted_original_slots_and_per_issue_scores_preserved': True,
        'external_paid_API_usd': 0, 'test_unsealed': False, 'paper_modified': False,
        'official_scorer_sha256': original.OFFICIAL_SCORER_SHA,
        'evaluator_sha256': c.sha(e.__file__), 'aggregator_sha256': sha(__file__)}
    # Detect mutation during CPU statistics, without rewriting any inputs.
    for path, wanted in inputs.items():
        if sha(path) != wanted:
            raise ValueError('An immutable input changed during cumulative scoring: ' + path)
    out.mkdir(parents=True)
    for name, value in [('summary', summary), ('evaluation', evaluated), ('official_compatible', official),
                        ('allocation', {'n': n, 'records': allocation}), ('input_sha256', inputs),
                        ('execution_method', signatures[0])]:
        c.write(out / (name + '.json'), value, immutable=True)
    with (out / '逐题定位与资源.csv').open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, headers); writer.writeheader(); writer.writerows(flat)
    (out / 'LocBench_累计定位结果.md').write_text(markdown(summary, evaluated, batch_summaries), encoding='utf-8')
    c.write(out / 'output_sha256.json', {p.name: sha(p) for p in out.iterdir() if p.is_file()}, immutable=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    batch = sub.add_parser('batch'); batch.add_argument('--work', type=Path, required=True)
    merged = sub.add_parser('combine'); merged.add_argument('--reports', type=Path, nargs='+', required=True)
    merged.add_argument('--out', type=Path, required=True); merged.add_argument('--bootstrap-draws', type=int, default=5000)
    args = parser.parse_args()
    result = report_batch(args.work) if args.action == 'batch' else combine(args.reports, args.out, draws=args.bootstrap_draws)
    print(json.dumps({'status': result['status'], 'allocated': result['allocated']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
