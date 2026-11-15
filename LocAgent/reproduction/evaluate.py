"""Offline CPU evaluation of LocAgent's official MRR-fused final predictions.

No model/tool runner is imported. Gold is read only here, never by inference.
The frozen SpecPrune evaluator owns metric semantics. This adapter translates
only explicit path:name identities; it never guesses a leaf name, uses gold to
resolve ambiguity, expands classes, or removes invalid final ranking slots.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics

EVALUATOR_SHA256 = '22b6c4c8c24da8b88bc09c0191ffe830d5ba375183e1d98c00577007adffe5aa'
ARMS = ('baseline', 'hybrid_safe', 'locagent')
LABELS = {'baseline': 'CoSIL-Qwen3', 'hybrid_safe': 'CoSIL-SFPruner', 'locagent': 'LocAgent-Qwen3'}
RANKING_NOTE = ('评价官方多样本MRR融合后的最终排名。官方在融合前已过滤不支持的图实体并归并重复；'
                '本评价器只保持融合后排名的无效/重复槽位，不声称原始模型输出全过程保留原槽。'
                '不以金标消歧，不将类扩展为其方法，不补入缺失构造函数。')
SCOPE_NOTE = ('100题从已观察结果后构成的280题父池按固定哈希取出。父池排除了18道基线占优题和2道共同未命中题，'
              '因此不是独立盲测；不能用该同题比较推断未筛选总体上的方法优势。')
ADAPTATION_NOTE = ('LocAgent按原生工具调用方式适配本地Qwen3：逻辑别名openai/locagent-native用于选择上游原生分支，'
                   '实际请求模型仍为qwen3-8b；上游以qwen命名的默认分支会走文本/XML转换，因此不能声称工具协议逐项未变。'
                   '官方README要求Python3.12，本地推理环境为Python3.12.3；LiteLLM从官方1.52.1兼容固定为1.53.1。'
                   'LocAgent每题两个独立样本、temperature=1.0/top_p=0.8/repetition_penalty=1.05，'
                   '历史CoSIL两条件各运行一次、temperature=0/seed=0。底座、任务与评分对齐不代表采样预算完全一致。')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def frozen_evaluator(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[2] / 'CoSIL/papers/SFPruner/specprune/evaluation.py'
    if sha(path) != EVALUATOR_SHA256:
        raise ValueError('Frozen evaluation.py SHA differs; do not silently change scoring rules')
    spec = importlib.util.spec_from_file_location('_locagent_frozen_evaluation', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def number(value):
    if isinstance(value, bool) or value is None or value == '':
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def identity_item(item):
    """Lossless syntactic conversion; base-inventory validation is separate."""
    if isinstance(item, dict):
        return {'path': item.get('path'), 'qualified_name': item.get('qualified_name')}
    if not isinstance(item, str):
        return None
    if '::' in item:
        path, name = item.split('::', 1)
    elif ':' in item:
        path, name = item.split(':', 1)
    else:
        return None
    return {'path': path, 'qualified_name': name}


def official_predictions(result):
    """Use the native final fused order, including unsupported/invalid entries."""
    files = result.get('found_files', [])
    entities = result.get('found_entities', [])
    diagnostics = []
    if not isinstance(files, list):
        diagnostics.append('found_files_is_not_a_list')
        files = []
    if not isinstance(entities, list):
        diagnostics.append('found_entities_is_not_a_list')
        entities = []
    return {'status': result['status'], 'predicted_files': files,
            'predicted_functions': [identity_item(x) for x in entities]}, diagnostics


def historical_prediction(row, arm):
    files = json.loads(row[arm + '_file_slots'])
    functions = json.loads(row[arm + '_function_slots'])
    if not isinstance(files, list) or not isinstance(functions, list):
        raise ValueError('Historical slots must be JSON lists')
    return {'status': row[arm + '_status'], 'predicted_files': files,
            'predicted_functions': [identity_item(x) for x in functions]}


def resource_from_worker(result):
    usage = result.get('usage') or {}
    if not isinstance(usage, dict):
        raise ValueError('Worker usage must be an object')
    out = {k: number(usage.get(k)) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens',
           'unknown_usage_requests', 'http_attempts', 'completion_requests', 'api_cost_usd')}
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        known = number(usage.get('known_' + key))
        out['known_' + key] = known if known is not None else out[key]
    if out['unknown_usage_requests'] is not None and out['unknown_usage_requests'] > 0:
        # A worker must not conceal missing attempt usage in an apparently exact total.
        if any(out[k] is not None for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
            raise ValueError('Unknown HTTP usage cannot carry exact token totals')
    for key in ('elapsed_seconds', 'generation_seconds', 'tool_elapsed_seconds', 'graph_elapsed_seconds'):
        out[key] = number(result.get(key))
    out['origin'] = 'new_locagent_worker_receipt'
    return out


def resource_from_history(row, arm):
    out = {
        'prompt_tokens': None, 'completion_tokens': None,
        'total_tokens': number(row.get(arm + '_main_tokens')),
        'known_prompt_tokens': number(row.get(arm + '_known_prompt_tokens')),
        'known_completion_tokens': number(row.get(arm + '_known_completion_tokens')),
        'unknown_usage_requests': number(row.get(arm + '_unknown_usage_attempts')),
        'http_attempts': number(row.get(arm + '_http_attempts_recorded')),
        'completion_requests': None, 'api_cost_usd': None,
        'elapsed_seconds': number(row.get(arm + '_worker_elapsed_seconds')),
        'generation_seconds': None, 'tool_elapsed_seconds': None, 'graph_elapsed_seconds': None,
        'local_input_tokens': number(row.get(arm + '_local_input_tokens')),
        'origin': 'reused_historical_result_not_new_compute',
    }
    known = [out[k] for k in ('known_prompt_tokens', 'known_completion_tokens')]
    out['known_total_tokens'] = sum(known) if all(x is not None for x in known) else None
    file_seconds = number(row.get('baseline_file_stage_wall_seconds'))
    out['comparable_elapsed_seconds'] = (out['elapsed_seconds'] + file_seconds
        if arm == 'hybrid_safe' and out['elapsed_seconds'] is not None and file_seconds is not None
        else out['elapsed_seconds'] if arm == 'baseline' else None)
    return out


def aggregate_resources(rows, arm):
    values = [r['resources'][arm] for r in rows if r['resources'].get(arm) is not None]
    out = {'recorded_tasks': len(values), 'historical_reuse_not_rebilled': arm != 'locagent'}
    fields = ('prompt_tokens', 'completion_tokens', 'total_tokens', 'known_prompt_tokens',
              'known_completion_tokens', 'known_total_tokens', 'unknown_usage_requests',
              'http_attempts', 'completion_requests', 'api_cost_usd', 'elapsed_seconds',
              'comparable_elapsed_seconds', 'generation_seconds', 'tool_elapsed_seconds',
              'graph_elapsed_seconds', 'local_input_tokens')
    for key in fields:
        observed = [r[key] for r in values if r.get(key) is not None]
        out[key] = {'records': len(observed), 'sum': sum(observed) if observed else None,
                    'mean': statistics.mean(observed) if observed else None,
                    'median': statistics.median(observed) if observed else None,
                    'all_recorded_tasks_known': bool(values) and len(observed) == len(values)}
    out['accounting_note'] = ('历史hybrid实际token不含共享文件阶段；CSV没有逐题文件token，不能直接与其他臂作全流程token比较。'
        '历史hybrid的comparable_elapsed_seconds补计同题文件时间。LocAgent独立完成文件与函数检索；'
        '各资源值保留实际记录数，不用未知值补零，不把历史复用计为本轮新增用量。')
    return out


def context_audits(run_dir, ids):
    """Read offline provenance only; it never changes a prediction or metric."""
    out = {'adaptation_note': ADAPTATION_NOTE, 'graph_coverage': {'status': 'NOT_AVAILABLE'},
           'model_identity': {'status': 'NOT_AVAILABLE'}, 'source_sha256': {}}
    graph_audit = run_dir / 'private/graph_coverage.json'
    if graph_audit.is_file():
        data = read(graph_audit)
        records = data['records']
        if len(records) != len(ids) or {r['instance_id'] for r in records} != set(ids):
            raise ValueError('Offline graph coverage roster differs from evaluation roster')
        constructor_nodes, bom_tasks, other_missing = 0, [], 0
        for row in records:
            missing = row.get('missing_function_nodes', [])
            constructor_nodes += sum(x['reason'] == 'upstream_omits_independent_constructor_node' for x in missing)
            remaining = [x for x in missing if x['reason'] != 'upstream_omits_independent_constructor_node']
            if not remaining:
                continue
            receipt_path = run_dir / 'public/graph_index' / (row['instance_id'] + '.receipt.json')
            skips = read(receipt_path).get('syntax_skips', []) if receipt_path.is_file() else []
            bom_files = {x['path'] for x in skips if 'U+FEFF' in str(x.get('message')) or '\ufeff' in str(x.get('message'))}
            n_bom = sum(x['identity'].split('::', 1)[0] in bom_files for x in remaining)
            if n_bom:
                bom_tasks.append(row['instance_id'])
            other_missing += len(remaining) - n_bom
            if receipt_path.is_file():
                out['source_sha256'][str(receipt_path.relative_to(run_dir))] = sha(receipt_path)
        out['graph_coverage'] = {
            'status': 'READ_ONLY_OFFLINE_AUDIT', 'allocated': len(records),
            'successful_graphs': sum(r['graph_ready'] for r in records),
            'tasks_all_target_function_nodes_present': sum(r.get('all_target_function_nodes_present') is True for r in records),
            'tasks_missing_target_function_nodes': sum(bool(r.get('missing_function_nodes')) for r in records),
            'targets_missing_function_nodes': sum(len(r.get('missing_function_nodes', [])) for r in records),
            'missing_constructor_function_nodes': constructor_nodes, 'bom_affected_issue_ids': bom_tasks,
            'other_missing_function_nodes': other_missing, 'tasks_removed': 0, 'graph_modified': False,
            'note': '官方图缺少独立函数节点不等于源码不可见；类/文件工具可能包含源码。全部任务仍保留严格评价分母，不用金标补图。'}
        out['source_sha256'][str(graph_audit.relative_to(run_dir))] = sha(graph_audit)
    identity_path = run_dir / 'service/model_identity_audit.json'
    if identity_path.is_file():
        data = read(identity_path)
        out['model_identity'] = {key: data.get(key) for key in ('status', 'model_id', 'revision',
            'files_verified', 'verified_bytes', 'pin_manifest_sha256', 'runtime_versions')}
        out['source_sha256'][str(identity_path.relative_to(run_dir))] = sha(identity_path)
    launch_path = run_dir / 'service/launch.json'
    out['hardware'] = {'status': 'NOT_AVAILABLE'}
    if launch_path.is_file():
        launch = read(launch_path)
        gpus = launch.get('gpus')
        out['hardware'] = {'status': 'SERVICE_LAUNCH_RECEIPT', 'gpus': launch.get('gpus'),
            'note': ('本次服务GPU1和GPU3为跨NUMA的SYS链路；' if gpus in ([1, 3], [3, 1]) else '此部署拓扑需查阅自己的实际回执；')
                    + '与历史CoSIL部署及共卡评分配置不同，耗时只能按各自环境描述。'}
        out['source_sha256'][str(launch_path.relative_to(run_dir))] = sha(launch_path)
    return out


def load_inputs(run_dir):
    paths = {'manifest': run_dir / 'selection/manifest.json', 'gold': run_dir / 'private/gold.json',
             'inventory': run_dir / 'private/inventory.json',
             'comparison': run_dir / 'private/comparison_original.csv'}
    manifest, gold, inventory = (read(paths[k]) for k in ('manifest', 'gold', 'inventory'))
    tasks = manifest['records']
    ids = [r['instance_id'] for r in tasks]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Frozen roster is empty or contains duplicate issue IDs')
    with paths['comparison'].open(encoding='utf-8-sig') as f:
        historical = list(csv.DictReader(f))
    by_id = {r['instance_id']: r for r in historical}
    if len(by_id) != len(historical) or any(set(ids) != set(v) for v in (gold, inventory, by_id)):
        raise ValueError('Manifest, gold, inventory and historical comparison rosters must match exactly')
    for task in tasks:
        iid = task['instance_id']
        if not isinstance(iid, str) or Path(iid).name != iid or iid in ('.', '..'):
            raise ValueError('Issue ID must be a single safe path component')
        if any(by_id[iid][key] != task[key] for key in ('repo', 'base_commit')):
            raise ValueError('Historical source identity or base commit differs: ' + iid)
        g = gold[iid]
        if not (g['status'] == 'COMPLETE_NONEMPTY' and g['set_complete'] is True and g['targets']):
            raise ValueError('This frozen cohort requires complete nonempty existing-function targets: ' + iid)
        if not g['gold_files']:
            raise ValueError('A function-eligible task must also have nonempty file targets: ' + iid)
    return manifest, tasks, gold, inventory, by_id, paths


def build_evaluation(run_dir, *, evaluator_path=None, seed=20261110, draws=5000):
    """Read current receipts once; pending tasks are never relabelled model failures."""
    run_dir = Path(run_dir).resolve(strict=True)
    frozen, frozen_path = frozen_evaluator(evaluator_path)
    manifest, tasks, gold, inventory, historical, source_paths = load_inputs(run_dir)
    predictions, metadata, result_hashes = [], {}, {}
    for task in tasks:
        iid = task['instance_id']
        arms = {a: historical_prediction(historical[iid], a) for a in ARMS[:2]}
        resource = {a: resource_from_history(historical[iid], a) for a in ARMS[:2]}
        result_path = run_dir / 'outputs' / iid / 'result.json'
        receipt_bytes = result_path.read_bytes() if result_path.is_file() else None
        receipt = json.loads(receipt_bytes) if receipt_bytes is not None else None
        terminal = bool(receipt and receipt.get('terminal') is True)
        diagnostics = []
        execution_status = 'NOT_RUN'
        if receipt is not None:
            if any(receipt.get(k) != task[k] for k in ('instance_id', 'repo', 'base_commit')):
                raise ValueError('Worker receipt identity mismatch: ' + iid)
            result_hashes[str(result_path.relative_to(run_dir))] = hashlib.sha256(receipt_bytes).hexdigest()
            execution_status = receipt.get('execution_status', receipt.get('status', 'UNKNOWN'))
        if terminal:
            if receipt['status'] not in ('complete', 'partial', 'failed'):
                raise ValueError('Unrecognized terminal worker status: ' + str(receipt['status']))
            arms['locagent'], diagnostics = official_predictions(receipt)
            if receipt['status'] == 'failed' and (arms['locagent']['predicted_files'] or arms['locagent']['predicted_functions']):
                raise ValueError('Failed worker carries predictions; use terminal partial when a sample is usable')
            resource['locagent'] = resource_from_worker(receipt)
        else:
            arms['locagent'] = {'status': 'NOT_RUN', 'predicted_files': [], 'predicted_functions': []}
            resource['locagent'] = None
        predictions.append({'instance_id': iid, 'repo': task['repo'], 'base_commit': task['base_commit'], 'arms': arms})
        metadata[iid] = {'terminal': terminal, 'execution_status': execution_status,
                         'diagnostics': diagnostics, 'resources': resource,
                         'receipt': str(result_path.relative_to(run_dir)) if receipt else None}
    scored = frozen.evaluate(predictions, gold, inventory, arms=ARMS, seed=seed, draws=draws)
    for row in scored['records']:
        iid = row['instance_id']
        row.update(metadata[iid])
        # Guard against silently evaluating a different gold mapping or source-slot convention.
        for arm in ARMS[:2]:
            for unit in ('file', 'function'):
                metric = row[arm + '_' + unit]
                for key in ('hit1', 'hit3', 'hit5', 'precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
                    original = number(historical[iid].get(arm + '_' + unit + '_' + key))
                    if metric is not None and (original is None or not math.isclose(metric[key], original, rel_tol=0, abs_tol=1e-12)):
                        raise ValueError('Historical scoring changed: ' + iid + '/' + arm + '/' + unit + '/' + key)
        if not row['terminal']:
            diagnostic = '尚未终态，不归为模型失败'
        elif row['locagent_status'] == 'failed':
            diagnostic = '执行终态无有效输出：' + str(row['execution_status'])
        elif not row['locagent_file']['hit5']:
            diagnostic = '最终文件Top-5未命中；原因仍需工具轨迹证据'
        elif not row['locagent_function']['hit5']:
            diagnostic = '文件Top-5命中但函数Top-5未命中；不能仅据排名断言源码缺失'
        elif not row['locagent_function']['all_coverage5']:
            diagnostic = '函数Top-5部分目标命中，未覆盖全部既有目标'
        else:
            diagnostic = '函数Top-5覆盖全部既有目标'
        row['locagent_diagnostic'] = diagnostic
    rows = scored['records']
    terminal_rows = [r for r in rows if r['terminal']]
    pending = [r['instance_id'] for r in rows if not r['terminal']]
    summary = scored['summary']
    if pending:
        # Pending placeholders permit delivery accounting, not inference about accuracy.
        for unit in ('file', 'function'):
            for key in list(summary['metrics']['locagent'][unit]):
                if key.endswith('_ci95'):
                    summary['metrics']['locagent'][unit][key] = [None, None]
    summary.update(schema=1, status='PARTIAL' if pending else 'FINAL',
        result_scope='未完成时固定名册指标仅为暂时交付下界，pending不等于模型失败' if pending else '固定名册已全终态；失败保留分母',
        pending_issue_ids=pending, terminal_tasks=len(terminal_rows), pending_tasks=len(pending),
        cohort_provenance=SCOPE_NOTE, ranking_protocol=RANKING_NOTE,
        locagent_terminal_statuses=dict(Counter(r['locagent_status'] for r in terminal_rows)),
        locagent_terminal_execution_statuses=dict(Counter(str(r['execution_status']) for r in terminal_rows)),
        locagent_terminal_subset_metrics={unit: frozen.aggregate([r['locagent_' + unit] for r in terminal_rows], seed=seed, draws=draws)
                                          for unit in ('file', 'function')},
        resources={a: aggregate_resources(rows, a) for a in ARMS},
        paired_comparisons={},
        source_sha256={key: sha(path) for key, path in source_paths.items()},
        worker_result_sha256=result_hashes, frozen_evaluator_sha256=sha(frozen_path),
        adapter_sha256=sha(__file__), new_evaluation_model_calls=0, sealed_test_opened=False,
        inference_predictions_repaired_with_gold=False,
        statistical_note='探索性同题配对区间与精确检验未作多重比较校正；未显著不表示等效或非劣。')
    summary['context_audits'] = context_audits(run_dir, [r['instance_id'] for r in rows])
    for a, b in (('baseline', 'hybrid_safe'), ('baseline', 'locagent'), ('hybrid_safe', 'locagent')):
        if pending and 'locagent' in (a, b):
            summary['paired_comparisons'][a + '__' + b] = {'status': 'PENDING_FULL_ROSTER', 'n': None}
            continue
        unit_results = {}
        for unit in ('file', 'function'):
            unit_results[unit] = {str(k): frozen.paired([r[a + '_' + unit]['hit' + str(k)] for r in rows],
                  [r[b + '_' + unit]['hit' + str(k)] for r in rows], seed=seed, draws=draws) for k in (1, 3, 5)}
        summary['paired_comparisons'][a + '__' + b] = {'status': 'ANALYZED', 'arms': [a, b], **unit_results}
    return {'summary': summary, 'records': rows, 'manifest_metadata': {k: v for k, v in manifest.items() if k != 'records'}}


def percent(value):
    return 'NA' if value is None else f'{100 * value:.2f}%'


def ci_text(value):
    return 'NA' if not value or value[0] is None else f'[{100*value[0]:.2f}, {100*value[1]:.2f}]%'


def report_text(result, run_dir):
    s = result['summary']
    n = s['allocated']
    lines = ['# LocAgent同题定位比较：中文结果报告', '',
        f'状态：**{s["status"]}**。固定{n}题，已终态{s["terminal_tasks"]}题，待完成{s["pending_tasks"]}题。', '',
        SCOPE_NOTE, '', RANKING_NOTE, '',
        '## 范围与状态', '',
        '文件与函数分母均按同一冻结名册；失败保留分母，尚未终态不归为模型失败。LocAgent单题partial表示两个样本中有至少一个可用结果，仍是终态，并按真实融合输出计分。',
        f'LocAgent终态状态：`{json.dumps(s["locagent_terminal_statuses"], ensure_ascii=False)}`。', '']
    audits = s['context_audits']
    lines += ['## 运行适配与代码图可见性', '', audits['adaptation_note'], '']
    hardware = audits['hardware']
    if hardware['status'] != 'NOT_AVAILABLE':
        lines += [f'服务回执GPU：`{hardware["gpus"]}`。' + hardware['note'], '']
    graph = audits['graph_coverage']
    if graph['status'] != 'NOT_AVAILABLE':
        lines += [f'官方图构建成功{graph["successful_graphs"]}/{graph["allocated"]}题；'
                  f'{graph["tasks_all_target_function_nodes_present"]}题的全部既有目标均有独立函数节点，'
                  f'{graph["tasks_missing_target_function_nodes"]}题缺少至少一个独立目标函数节点。'
                  f'其中{graph["missing_constructor_function_nodes"]}个为上游省略的同步__init__；'
                  f'{len(graph["bom_affected_issue_ids"])}题受源码BOM（U+FEFF）导致的官方AST解析跳过影响；'
                  f'其余未解释节点数为{graph["other_missing_function_nodes"]}。', graph['note'], '']
    identity = audits['model_identity']
    if identity['status'] != 'NOT_AVAILABLE':
        lines += [f'主模型文件核验：{identity["status"]}，{identity["files_verified"]}个核心文件／'
                  f'{identity["verified_bytes"]}字节匹配既有SHA清单；'
                  f'固定模型{identity["model_id"]}@{identity["revision"]}。API别名本身不作为权重身份依据。', '']
    if s['pending_tasks']:
        lines += ['**实验尚未完成。以下固定名册LocAgent比例只是暂时交付下界，不是最终模型准确率；涉及LocAgent的配对显著性检验尚不进行。**', '',
                  f'已终态子集（n={s["terminal_tasks"]}）的函数Hit@5：'
                  f'{s["locagent_terminal_subset_metrics"]["function"]["hit5_numerator"]}/{s["terminal_tasks"]}；该子集同样不能替代最终固定名册。', '']
    lines += ['## 文件级与函数级定位', '', '| 范围 | 指标 | CoSIL-Qwen3 | CoSIL-SFPruner | LocAgent-Qwen3 |', '|---|---|---:|---:|---:|']
    for unit, label in (('file', '文件'), ('function', '函数')):
        for k in (1, 3, 5):
            values = []
            for a in ARMS:
                m = s['metrics'][a][unit]
                values.append(f'{m["hit"+str(k)+"_numerator"]}/{m["n"]}（{percent(m["hit"+str(k)])}；95%CI {ci_text(m["hit"+str(k)+"_ci95"])})')
            lines.append('| ' + ' | '.join([label, f'Hit@{k}', *values]) + ' |')
        for metric, name in (('precision5', 'Macro-Precision@5'), ('recall5', 'Macro-Recall@5'),
                             ('f15', 'Macro-F1@5'), ('all_coverage5', 'AllCoverage@5'), ('mrr10', 'MRR@10')):
            lines.append('| ' + ' | '.join([label, name, *[percent(s['metrics'][a][unit][metric]) for a in ARMS]]) + ' |')
    lines += ['', 'Hit采用Wilson区间；宏指标的issue bootstrap区间保存在summary.json。P@5固定除以5；无效/重复排名不补位；函数采用严格path::qualified_name。', '',
              '## 同题配对比较', '', '| 比较（后者−前者） | 函数指标 | 均中 / 仅前者 / 仅后者 / 均未中 | 差值 | 配对95%CI | 精确McNemar p |', '|---|---|---|---:|---|---:|']
    for value in s['paired_comparisons'].values():
        if value['status'] != 'ANALYZED':
            continue
        a, b = value['arms']
        for k in (1, 3, 5):
            m = value['function'][str(k)]
            four = ' / '.join(str(m[key]) for key in ('both_success', 'only_a', 'only_b', 'both_failure'))
            lines.append(f'| {LABELS[a]} → {LABELS[b]} | Hit@{k} | {four} | {100*m["b_minus_a"]:+.2f}pp | {ci_text(m["b_minus_a_ci95"])} | {m["exact_mcnemar_p"]:.6g} |')
    lines += ['', s['statistical_note'], '', '## Token、耗时与执行状态', '',
              '| 记录 | 条件 | 有值题数 | 总量 | 均值 |', '|---|---|---:|---:|---:|']
    for a in ARMS:
        resource = s['resources'][a]
        for field, label in (('known_prompt_tokens', '已知输入token下界'), ('known_completion_tokens', '已知输出token下界'),
                             ('known_total_tokens', '已知总token下界'), ('unknown_usage_requests', 'usage未知HTTP尝试'),
                             ('elapsed_seconds', 'worker秒数（不含启动/构图）'), ('generation_seconds', 'HTTP生成秒数'),
                             ('graph_elapsed_seconds', '构图秒数'), ('api_cost_usd', '记录的API美元费用')):
            m = resource[field]
            total = 'NA' if m['sum'] is None else f'{m["sum"]:.4f}'
            mean = 'NA' if m['mean'] is None else f'{m["mean"]:.4f}'
            lines.append(f'| {label} | {LABELS[a]} | {m["records"]} | {total} | {mean} |')
    lines += ['', s['resources']['hybrid_safe']['accounting_note'],
              '各方法的历史/当前硬件、共享文件阶段和构图范围不同；上述记录不能直接等同受控加速或系统总计算减少。电费、折旧与模型预训练成本未测量。', '',
              '## 未命中与异常', '', '| issue | 状态 | 可观察诊断 |', '|---|---|---|']
    for row in result['records']:
        if not row['terminal'] or not row['locagent_function']['hit5']:
            lines.append(f'| {row["instance_id"]} | {row["locagent_status"]} / {row["execution_status"]} | {row["locagent_diagnostic"]} |')
    lines += ['', '以上分类是由终态、文件排名及函数排名得到的可观察描述，不将测试环境故障当成模型推理失败，也不据最终排名推断未观察的源码读取或因果原因。', '',
              '## 复现与证据', '', f'运行目录：`{run_dir}`。',
              '```bash', f'python -m reproduction.evaluate --run {run_dir} --output NEW_EVALUATION_DIRECTORY', '```',
              'per_issue.csv保留全部冻结issue及状态；summary.json含原始分子分母、区间、配对检验、资源记录数、输入与终态SHA。离线评价不调用模型，不读取封存训练test，不改写历史预测。', '']
    return '\n'.join(lines)


def evaluate_run(run_dir, output_dir=None, *, evaluator_path=None, seed=20261110, draws=5000):
    """Evaluate current receipts into a NEW report directory and return the result."""
    if draws < 40:
        raise ValueError('bootstrap draws must be >=40')
    run_dir = Path(run_dir).resolve(strict=True)
    result = build_evaluation(run_dir, evaluator_path=evaluator_path, seed=seed, draws=draws)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output = Path(output_dir) if output_dir else run_dir / 'reports' / ('evaluation_' + stamp)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'summary.json').write_text(json.dumps(result['summary'], ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (output / 'evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    flat_rows = []
    for row in result['records']:
        flat = {key: row[key] for key in ('instance_id', 'repo', 'base_commit', 'function_scorable', 'gold_status',
                 'gold_functions', 'gold_files', 'terminal', 'execution_status', 'receipt', 'diagnostics', 'locagent_diagnostic')}
        for a in ARMS:
            flat[a + '_status'] = row[a + '_status']
            for unit in ('file', 'function'):
                m = row[a + '_' + unit]
                for key, value in m.items():
                    flat[a + '_' + unit + '_' + key] = '' if a == 'locagent' and not row['terminal'] else value
            flat[a + '_resources'] = row['resources'][a]
        flat_rows.append(flat)
    with (output / 'per_issue.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_rows[0])); writer.writeheader()
        for row in flat_rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    (output / 'final_report.md').write_text(report_text(result, run_dir), encoding='utf-8')
    result['output_directory'] = str(output.resolve())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--evaluator', type=Path)
    parser.add_argument('--seed', type=int, default=20261110)
    parser.add_argument('--bootstrap-draws', type=int, default=5000)
    args = parser.parse_args()
    result = evaluate_run(args.run, args.output, evaluator_path=args.evaluator, seed=args.seed, draws=args.bootstrap_draws)
    print(json.dumps({'status': result['summary']['status'], 'terminal_tasks': result['summary']['terminal_tasks'],
                      'pending_tasks': result['summary']['pending_tasks'], 'output_directory': result['output_directory']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
