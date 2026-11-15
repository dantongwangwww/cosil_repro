"""CPU-only evaluation of one fixed, unified LocAgent280 prediction protocol.

The first completed inference batch is reused by identity and content hash.
Every task uses the same format-compatible, requested-file-scoped parser rule.
No original native ranking, per-batch accuracy, model, or search is evaluated
here. Historical files and predictions are never overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from reproduction import evaluate as common

ARMS = ('baseline', 'hybrid_safe', 'locagent')
LABELS = {'baseline': 'CoSIL-Qwen3', 'hybrid_safe': 'CoSIL-SFPruner',
          'locagent': 'LocAgent-Qwen3（统一解析修正版）'}
RULE_ID = 'normalized_requested_file_v1'
SOURCE_PATCH_SHA256 = '7984406d757f4d5fb9cda6fd5d4b2e47f033890eda9f37d7e019a20c92a8446f'
OLD_VIEW = 'offline_format_plus_requested_file_scope_diagnostic_v1'
RULE_FILES = {
    'reproduction/postprocess_requested_file.py': '7fb38794351cd962615de2206bb285b981404684a61a30a4c5a4069ff59597fa',
    'reproduction/postprocess_compat.py': '1df7718e46a4f6b09d5d31afa22741612af4a07e01b6c9f0bdb51eccafabcc44',
    'util/process_output.py': 'a5bbbdd7dff4215f6408abd5b345bde650cfe54c4167fa5e58289ad74ce37355',
}
ORIGINS = ('existing100_reuse', 'new180')
EXPECTED_HISTORICAL_FUNCTION_HITS = {'baseline': (128, 161, 171), 'hybrid_safe': (139, 167, 174)}
SCOPE_NOTE = ('固定280题来自观察既有实验结果后构成的父池：完整300题中排除了18道基线占优题和2道双方未命中题。'
              '因此属于有结果选择偏差的开发比较，不是独立盲测，不能推断未筛选总体优势。')
METHOD_NOTE = ('所有任务统一使用格式兼容及requested_file行号约束：只归一化图中严格存在的身份，'
               '行号仅在模型指定文件内映射，逐sample执行原生实体过滤及MRR融合；不按金标修身份、'
               '不按题择优、不扩展类、不新增推理。它不是完整AST/parser修复。')


def reference_path(run, value):
    if not isinstance(value, str) or not value:
        raise ValueError('An explicit provenance path is required')
    path = Path(value)
    return (path if path.is_absolute() else run / path).resolve()


def raw_path(run, task):
    origin, iid = task.get('execution_origin'), task['instance_id']
    if origin == 'new180':
        return run / 'outputs' / iid / 'result.json'
    if origin != 'existing100_reuse':
        raise ValueError('Unknown execution_origin: ' + str(origin))
    path = reference_path(run, task.get('original_result'))
    original_run = reference_path(run, task.get('original_run'))
    if path != (original_run / 'outputs' / iid / 'result.json').resolve():
        raise ValueError('Reused raw result is not the declared issue/run: ' + iid)
    return path


def _identity(value, task, label):
    if any(value.get(k) != task[k] for k in ('instance_id', 'repo', 'base_commit')):
        raise ValueError(label + ' identity mismatch: ' + task['instance_id'])


def _check_raw(raw, task):
    _identity(raw, task, 'Raw result')
    if raw.get('terminal') is True and raw.get('status') not in ('complete', 'partial', 'failed'):
        raise ValueError('Unknown terminal status: ' + task['instance_id'])
    expected = {'thinking_enabled': False, 'actual_request_model': 'qwen3-8b',
                'num_samples': 2, 'ranking_method': 'mrr'}
    # Controller-level failures with no model requests need not invent model metadata.
    attempts = common.number((raw.get('usage') or {}).get('http_attempts'))
    if attempts is None or attempts > 0:
        for key, value in expected.items():
            if raw.get(key) != value or (key == 'thinking_enabled' and raw.get(key) is not False):
                raise ValueError('Raw model/protocol differs: ' + key + '/' + task['instance_id'])


def _normalized(run, task, raw, source, directory):
    """A result becomes scoreable only after its atomic hash receipt is ready."""
    iid = task['instance_id']
    path = directory / 'outputs' / iid / 'result.json'
    receipt_path = path.parent / 'normalization_receipt.json'
    if not receipt_path.is_file():
        return None, 'WAITING_NORMALIZATION', {}, path
    receipt = common.read(receipt_path)
    if receipt.get('status') != 'ready':
        return None, 'NORMALIZATION_' + str(receipt.get('status', 'UNKNOWN')), receipt, path
    if not path.is_file():
        raise ValueError('Ready normalization has no result: ' + iid)
    if receipt.get('instance_id') != iid:
        raise ValueError('Normalization receipt identity mismatch: ' + iid)
    if receipt.get('rule_id') != OLD_VIEW or receipt.get('source_patch_sha256') != SOURCE_PATCH_SHA256:
        raise ValueError('Unified normalization rule differs: ' + iid)
    if reference_path(run, receipt.get('source_result_path')) != source.resolve():
        raise ValueError('Normalization raw-source path differs: ' + iid)
    if receipt.get('source_result_sha256') != common.sha(source):
        raise ValueError('Normalization raw-source SHA differs: ' + iid)
    if receipt.get('normalized_result_sha256') != common.sha(path):
        raise ValueError('Normalized result SHA differs: ' + iid)
    normalized = common.read(path)
    _identity(normalized, task, 'Normalized result')
    for key in ('terminal', 'status', 'execution_status', 'usage', 'samples', 'raw_output_loc',
                'elapsed_seconds', 'generation_seconds', 'tool_elapsed_seconds', 'graph_elapsed_seconds'):
        if normalized.get(key) != raw.get(key):
            raise ValueError('Normalization changed non-prediction field: ' + key + '/' + iid)
    if normalized.get('source_inference_result_sha256') != common.sha(source):
        raise ValueError('Normalized inference provenance differs: ' + iid)
    if normalized.get('postprocess_view') != OLD_VIEW:
        raise ValueError('Normalized view is not the frozen requested_file rule: ' + iid)
    if normalized.get('postprocess_diagnostic_error'):
        raise ValueError('Normalization diagnostic error: ' + iid)
    if task['execution_origin'] == 'existing100_reuse':
        old = reference_path(run, task.get('requested_file_result'))
        if common.sha(old) != common.sha(path):
            raise ValueError('Reused normalized result is not a byte-identical copy: ' + iid)
    return normalized, 'READY', receipt, path


def _raw_resource(raw, source, origin):
    resource = common.resource_from_worker(raw)
    resource['origin'] = 'reused_completed_inference' if origin == 'existing100_reuse' else 'new_extension_inference'
    resource['runner_wall_seconds'] = None
    runner = source.parent / 'runner_receipt.json'
    if runner.is_file():
        data = common.read(runner)
        resource.update(runner_wall_seconds=common.number(data.get('wall_seconds')),
                        runner_receipt_sha256=common.sha(runner), runner_returncode=data.get('returncode'),
                        runner_timed_out=data.get('timed_out'))
    return resource


def _timing(run, rows):
    launcher = run / 'controller/full_launcher.json'
    start = common.number(common.read(launcher).get('started')) if launcher.is_file() else None
    new_rows = [r for r in rows if r['execution_origin'] == 'new180']
    done = bool(new_rows) and all(r['inference_terminal'] for r in new_rows)
    end = max(Path(r['raw_result_path']).stat().st_mtime for r in new_rows) if done else None
    return {'status': 'FINAL_EXTENSION_TIMESTAMPS' if done else 'PENDING_EXTENSION',
            'extension_launcher_started_epoch': start, 'extension_last_raw_terminal_epoch': end,
            'extension_launcher_to_last_raw_terminal_seconds': max(0., end-start)
                if start is not None and end is not None else None,
            'not_a_continuous_280_task_wall_clock': True,
            'note': 'Tasks span reused and new execution batches. Only the actual extension launcher and raw '
                    'terminal mtimes determine this wall clock; normalization/copy mtimes and task sums do not.'}


def inspect_progress(run, directory, *, expected_n, expected_reused):
    """Public/provenance-only gate: do not open private gold while inference runs."""
    manifest_path, extension_path = run/'selection/manifest.json', run/'selection/extension_manifest.json'
    manifest, extension = common.read(manifest_path), common.read(extension_path)
    tasks=manifest['records'];ids=[t['instance_id'] for t in tasks]
    if len(tasks)!=expected_n or manifest.get('n')!=expected_n or len(set(ids))!=len(ids):
        raise ValueError('Full frozen cohort size differs or duplicate issue IDs')
    for iid in ids:
        if not isinstance(iid,str) or Path(iid).name!=iid or iid in ('.','..'):
            raise ValueError('Unsafe issue ID')
    origins=Counter(t.get('execution_origin') for t in tasks)
    if set(origins)!=set(ORIGINS) or origins['existing100_reuse']!=expected_reused:
        raise ValueError('Execution-batch partition differs')
    new=[t for t in tasks if t['execution_origin']=='new180']
    if extension.get('n')!=len(new) or [t['instance_id'] for t in extension['records']]!=[t['instance_id'] for t in new]:
        raise ValueError('Extension manifest is not the fixed-order new-task complement')
    for ext,task in zip(extension['records'],new):
        _identity(ext,task,'Extension manifest')
    extra={p.parent.name for p in (directory/'outputs').glob('*/result.json')}-set(ids)
    if extra:
        raise ValueError('Unexpected task in normalized outputs')
    rows=[];sources=set();hashes={}
    for task in tasks:
        iid=task['instance_id'];source=raw_path(run,task)
        if source.resolve() in sources:
            raise ValueError('Raw inference source counted more than once')
        sources.add(source.resolve());raw=common.read(source) if source.is_file() else None
        if raw is not None:
            _check_raw(raw,task);hashes[str(source)]=common.sha(source)
            if task['execution_origin']=='existing100_reuse' and (expected_n==280 or 'original_result_sha256' in task):
                if task.get('original_result_sha256')!=hashes[str(source)]:
                    raise ValueError('Frozen original-result SHA differs: '+iid)
                if task.get('requested_file_result_sha256')!=common.sha(reference_path(run,task.get('requested_file_result'))):
                    raise ValueError('Frozen reused-normalization SHA differs: '+iid)
        inference_terminal=bool(raw and raw.get('terminal') is True)
        normalized=None;state='WAITING_INFERENCE'
        if inference_terminal:
            normalized,state,_,path=_normalized(run,task,raw,source,directory)
            if normalized is not None:
                hashes[str(path)]=common.sha(path)
        elif (directory/'outputs'/iid/'normalization_receipt.json').exists():
            raise ValueError('Normalized receipt has no terminal raw inference: '+iid)
        rows.append({k:task[k] for k in ('instance_id','repo','base_commit')}|dict(
            terminal=normalized is not None,inference_terminal=inference_terminal,
            execution_origin=task['execution_origin'],normalization_state=state,
            execution_status=raw.get('execution_status',raw.get('status')) if raw else 'NOT_RUN',
            raw_result_path=str(source),normalized_result_path=str(path) if normalized is not None else None,
            raw_result_sha256=common.sha(source) if raw else None,
            normalized_result_sha256=common.sha(path) if normalized is not None else None,
            locagent_status=normalized['status'] if normalized is not None else 'NOT_RUN',
            resources={'locagent':_raw_resource(raw,source,task['execution_origin']) if inference_terminal else None}))
    pending=[r['instance_id'] for r in rows if not r['terminal']]
    if not pending:
        return None
    summary=dict(schema='locagent_unified280_progress_v1',status='PARTIAL',allocated=len(rows),
        terminal_tasks=len(rows)-len(pending),pending_tasks=len(pending),pending_issue_ids=pending,
        inference_terminal_tasks=sum(r['inference_terminal'] for r in rows),
        normalization_states=dict(Counter(r['normalization_state'] for r in rows)),
        locagent_terminal_statuses=dict(Counter(r['locagent_status'] for r in rows if r['terminal'])),
        function_denominator=None,file_denominator=None,metrics={},paired_comparisons={},
        scoring_performed=False,gold_read=False,private_inventory_read=False,
        primary_prediction_protocol=RULE_ID,source_patch_sha256=SOURCE_PATCH_SHA256,
        parsing_rule_source_sha256=RULE_FILES,execution_batches=dict(origins),
        per_batch_accuracy_reported=False,previous_native_rankings_compared=False,
        additional_model_calls_by_evaluator=0,inference_predictions_repaired_with_gold=False,
        sealed_training_test_opened=False,cohort_provenance=SCOPE_NOTE,ranking_protocol=METHOD_NOTE,
        resources={'locagent':common.aggregate_resources(rows,'locagent')},wall_clock=_timing(run,rows),
        source_sha256={'manifest':common.sha(manifest_path),'extension_manifest':common.sha(extension_path)},
        prediction_source_sha256=hashes,adapter_sha256=common.sha(__file__),
        result_scope='运行中仅报告状态与真实资源；不读private gold、不输出暂时准确率；最终统一全部任务评分')
    return {'summary':summary,'records':rows,
        'manifest_metadata':{k:v for k,v in manifest.items() if k!='records'},
        'incremental_accounting':{'scope':'new180 actual inference only; no per-batch accuracy',
            'declared_tasks':len(new),'terminal_raw_tasks':sum(r['inference_terminal'] for r in rows if r['execution_origin']=='new180'),
            'resources':common.aggregate_resources([r for r in rows if r['execution_origin']=='new180'],'locagent'),
            'no_per_batch_accuracy':True,'no_reused_usage_rebilled':True}}


def build_evaluation(run_dir, *, unified_dir=None, evaluator_path=None, seed=20261110,
                     draws=5000, expected_n=280, expected_reused=100):
    run = Path(run_dir).resolve(strict=True)
    source_root = Path(__file__).resolve().parent.parent
    for name, digest in RULE_FILES.items():
        if common.sha(source_root / name) != digest:
            raise ValueError('Frozen parsing-rule source changed: ' + name)
    directory = Path(unified_dir).resolve() if unified_dir else run / 'audits/unified_requested_file'
    progress=inspect_progress(run,directory,expected_n=expected_n,expected_reused=expected_reused)
    if progress is not None:
        return progress
    frozen, frozen_path = common.frozen_evaluator(evaluator_path)
    manifest, tasks, gold, inventory, historical, paths = common.load_inputs(run)
    if len(tasks) != expected_n or manifest.get('n') != expected_n:
        raise ValueError('Full frozen cohort size differs')
    origins = Counter(t.get('execution_origin') for t in tasks)
    if set(origins) != set(ORIGINS) or origins['existing100_reuse'] != expected_reused:
        raise ValueError('Execution-batch partition differs')
    extension_path = run / 'selection/extension_manifest.json'
    extension = common.read(extension_path)
    wanted_new = [t['instance_id'] for t in tasks if t['execution_origin'] == 'new180']
    if extension.get('n') != len(wanted_new) or [t['instance_id'] for t in extension['records']] != wanted_new:
        raise ValueError('Extension manifest is not the fixed-order new-task complement')
    for ext, task in zip(extension['records'], (t for t in tasks if t['execution_origin'] == 'new180')):
        _identity(ext, task, 'Extension manifest')
    all_ids = {t['instance_id'] for t in tasks}
    extra = {p.parent.name for p in (directory / 'outputs').glob('*/result.json')} - all_ids
    if extra:
        raise ValueError('Unexpected task in normalized outputs')
    predictions, metadata, source_hashes, used_sources = [], {}, {}, set()
    for task in tasks:
        iid, origin = task['instance_id'], task['execution_origin']
        source = raw_path(run, task)
        if source.resolve() in used_sources:
            raise ValueError('Raw inference source counted more than once')
        used_sources.add(source.resolve())
        raw = common.read(source) if source.is_file() else None
        if raw is not None:
            _check_raw(raw, task)
            source_hashes[str(source)] = common.sha(source)
            if origin == 'existing100_reuse' and (expected_n == 280 or 'original_result_sha256' in task):
                if task.get('original_result_sha256') != source_hashes[str(source)]:
                    raise ValueError('Frozen original-result SHA differs: ' + iid)
                old_normalized = reference_path(run, task.get('requested_file_result'))
                if task.get('requested_file_result_sha256') != common.sha(old_normalized):
                    raise ValueError('Frozen reused-normalization SHA differs: ' + iid)
        inference_terminal = bool(raw and raw.get('terminal') is True)
        resources = {a: common.resource_from_history(historical[iid], a) for a in ARMS[:2]}
        resources['locagent'] = _raw_resource(raw, source, origin) if inference_terminal else None
        if inference_terminal:
            normalized, state, receipt, normalized_path = _normalized(run, task, raw, source, directory)
        else:
            normalized, state, receipt = None, 'WAITING_INFERENCE', {}
            normalized_path = directory / 'outputs' / iid / 'result.json'
            if (normalized_path.parent / 'normalization_receipt.json').is_file():
                raise ValueError('Normalized receipt has no terminal raw inference: ' + iid)
        ready = normalized is not None
        arms = {a: common.historical_prediction(historical[iid], a) for a in ARMS[:2]}
        if ready:
            pred, problems = common.official_predictions(normalized)
            if problems:
                raise ValueError('Malformed normalized ranking: ' + iid)
            if pred['status'] == 'failed' and (pred['predicted_files'] or pred['predicted_functions']):
                raise ValueError('Failed inference carries a prediction: ' + iid)
            arms['locagent'] = pred
            source_hashes[str(normalized_path)] = common.sha(normalized_path)
            source_hashes[str(normalized_path.parent / 'normalization_receipt.json')] = common.sha(
                normalized_path.parent / 'normalization_receipt.json')
        else:
            arms['locagent'] = {'status': 'NOT_RUN', 'predicted_files': [], 'predicted_functions': []}
        predictions.append({k: task[k] for k in ('instance_id', 'repo', 'base_commit')} | {'arms': arms})
        metadata[iid] = dict(terminal=ready, inference_terminal=inference_terminal,
            execution_origin=origin, normalization_state=state,
            execution_status=raw.get('execution_status', raw.get('status')) if raw else 'NOT_RUN',
            raw_result_path=str(source), normalized_result_path=str(normalized_path) if ready else None,
            raw_result_sha256=common.sha(source) if raw else None,
            normalized_result_sha256=common.sha(normalized_path) if ready else None,
            normalization_receipt=receipt, resources=resources)
    result = frozen.evaluate(predictions, gold, inventory, arms=ARMS, seed=seed, draws=draws)
    for row in result['records']:
        iid = row['instance_id']
        row.update(metadata[iid])
        for arm in ARMS[:2]:
            for unit in ('file', 'function'):
                for key in ('hit1', 'hit3', 'hit5', 'precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
                    original = common.number(historical[iid].get(arm + '_' + unit + '_' + key))
                    if original is None or not math.isclose(row[arm+'_'+unit][key], original, abs_tol=1e-12, rel_tol=0):
                        raise ValueError('Historical scoring changed: ' + iid + '/' + arm + '/' + unit + '/' + key)
    rows, s = result['records'], result['summary']
    if expected_n == 280:
        for arm, wanted in EXPECTED_HISTORICAL_FUNCTION_HITS.items():
            if tuple(s['metrics'][arm]['function'][f'hit{k}_numerator'] for k in (1, 3, 5)) != wanted:
                raise ValueError('Historical280 aggregate differs: ' + arm)
    pending = [r['instance_id'] for r in rows if not r['terminal']]
    if pending:
        for unit in ('file', 'function'):
            for key in s['metrics']['locagent'][unit]:
                if key.endswith('_ci95'):
                    s['metrics']['locagent'][unit][key] = [None, None]
    s.pop('completed_only_secondary', None)
    s.update(schema='locagent_unified280_evaluation_v1', status='PARTIAL' if pending else 'FINAL',
        scoring_performed=True,gold_read=True,private_inventory_read=True,
        terminal_tasks=len(rows)-len(pending), pending_tasks=len(pending), pending_issue_ids=pending,
        inference_terminal_tasks=sum(r['inference_terminal'] for r in rows),
        normalization_states=dict(Counter(r['normalization_state'] for r in rows)),
        locagent_terminal_statuses=dict(Counter(r['locagent_status'] for r in rows if r['terminal'])),
        primary_prediction_protocol=RULE_ID, source_patch_sha256=SOURCE_PATCH_SHA256,
        parsing_rule_source_sha256=RULE_FILES,
        result_scope='固定全部任务的统一口径；待完成只作交付下界，不视为模型失败' if pending else '固定全部任务已终态，失败留分母',
        cohort_provenance=SCOPE_NOTE, ranking_protocol=METHOD_NOTE,
        per_batch_accuracy_reported=False, previous_native_rankings_compared=False,
        execution_batches=dict(origins), additional_model_calls_by_evaluator=0,
        inference_predictions_repaired_with_gold=False, sealed_training_test_opened=False,
        resources={a: common.aggregate_resources(rows, a) for a in ARMS},
        source_sha256={k: common.sha(p) for k, p in paths.items()} | {'extension_manifest': common.sha(extension_path)},
        prediction_source_sha256=source_hashes, frozen_evaluator_sha256=common.sha(frozen_path),
        adapter_sha256=common.sha(__file__), paired_comparisons={}, wall_clock=_timing(run, rows),
        resource_attribution='Each actual inference source counted once, reused or new; normalized copies add no usage. '
            'Unified totals are not all newly incurred. Incremental accounting is separate, with no per-batch accuracy.')
    for a, b in (('baseline', 'hybrid_safe'), ('baseline', 'locagent'), ('hybrid_safe', 'locagent')):
        if pending and 'locagent' in (a, b):
            s['paired_comparisons'][a+'__'+b] = {'status': 'PENDING_FULL_ROSTER'}
            continue
        s['paired_comparisons'][a+'__'+b] = {'status': 'ANALYZED', 'arms': [a, b], **{
            unit: {str(k): frozen.paired([r[a+'_'+unit][f'hit{k}'] for r in rows],
                [r[b+'_'+unit][f'hit{k}'] for r in rows], seed=seed, draws=draws) for k in (1, 3, 5)}
            for unit in ('file', 'function')}}
    result['manifest_metadata'] = {k: v for k, v in manifest.items() if k != 'records'}
    result['incremental_accounting'] = {'scope': 'new180 inference only, not an additional experiment arm',
        'declared_tasks': len(wanted_new), 'terminal_raw_tasks': sum(r['inference_terminal'] for r in rows if r['execution_origin']=='new180'),
        'resources': common.aggregate_resources([r for r in rows if r['execution_origin']=='new180'], 'locagent'),
        'no_per_batch_accuracy': True, 'no_reused_usage_rebilled': True}
    return result


def report_text(result, run):
    s = result['summary']
    if not s.get('scoring_performed',True):
        lines=['# LocAgent＋Qwen3-8B：统一280题执行进度','',
            f"状态：**PARTIAL**；固定{s['allocated']}题，推理终态{s['inference_terminal_tasks']}题，"
            f"统一解析就绪{s['terminal_tasks']}题，待完成{s['pending_tasks']}题。",'',
            '当前只报告执行、规范化状态与实际资源；没有读取private gold或库存，没有计算或展示暂时准确率。'
            '待全部任务就绪后，统一输出280题主表和同题配对统计。待推理、待解析均不归为模型失败。','',
            SCOPE_NOTE,'',METHOD_NOTE,'',
            '已有推理跨批次复用，新增任务使用相同统一规则，不伪称全部任务一次连续运行。'
            '原始输出和历史报告保留；规范化不新增模型调用。','',
            '## 执行与资源','',
            '就绪任务执行状态：`'+json.dumps(s['locagent_terminal_statuses'],ensure_ascii=False)+'`。','',
            '| 记录 | 有记录题数 | 已知总量 |','|---|---:|---:|']
        for key,label in [('known_prompt_tokens','输入token下界'),('known_completion_tokens','输出token下界'),
            ('known_total_tokens','总token下界'),('unknown_usage_requests','usage未知尝试'),
            ('runner_wall_seconds','隔离进程墙钟/秒')]:
            v=s['resources']['locagent'][key]
            lines.append(f"| {label} | {v['records']} | "+('NA' if v['sum'] is None else f"{v['sum']:.2f}")+' |')
        lines+=['','每个真实raw源只计一次；新增执行账单另存incremental_accounting.json，'
                '规范化复制与已有推理不形成新费用。未知usage不补零，单题累计耗时不当作并行墙钟。','',
                f'运行目录：`{run}`。文件和函数指标在全体就绪前留空。']
        return '\n'.join(lines)+'\n'
    lines = ['# LocAgent＋Qwen3-8B：统一280题定位报告', '',
        f"状态：**{s['status']}**；固定{s['allocated']}题，推理终态{s['inference_terminal_tasks']}题，"
        f"统一解析就绪{s['terminal_tasks']}题，待完成{s['pending_tasks']}题。", '', SCOPE_NOTE, '',
        '## 统一方法与执行记录', '', METHOD_NOTE, '',
        '主表只使用同一统一解析规则的全部任务结果，不混用其他后处理版本。已有完成推理复用，'
        '余题在后续批次执行；这是可追溯的多批次实验，不声称全部任务同一次连续运行。'
        '已有批次的原始输出和历史报告完整保留。旧输出的解析修正不涉及新增模型调用，'
        '统一规则在新增批次推理前固定，推理模型不读取金标。', '',
        '实际模型为通用Qwen3-8B，未使用作者LocAgent专用微调权重；每题两样本MRR融合，'
        '与历史CoSIL每条件一次轨迹的采样/搜索预算不同。同底座、同题与同评分器不等于完整复现论文配置。', '',
        '## 全部任务的文件级与函数级定位', '']
    if s['pending_tasks']:
        lines += ['**尚未完成：当前LocAgent数值仅是固定名册上的暂时交付下界，不是最终准确率。'
                  '待推理或待规范化任务在CSV中留空，不计入模型失败；最终配对推断暂不进行。**', '']
    lines += ['| 范围 | 指标 | CoSIL-Qwen3 | CoSIL-SFPruner | LocAgent-Qwen3统一解析修正版 |',
              '|---|---|---:|---:|---:|']
    for unit, zh in (('file', '文件'), ('function', '函数')):
        for k in (1, 3, 5):
            cells = []
            for arm in ARMS:
                m = s['metrics'][arm][unit]
                cells.append(f"{m[f'hit{k}_numerator']}/{m['n']}（{common.percent(m[f'hit{k}'])}；"
                             f"CI {common.ci_text(m[f'hit{k}_ci95'])}）")
            lines.append('| '+zh+f' | Hit@{k} | '+' | '.join(cells)+' |')
        for key, label in (('precision5','Macro-P@5'),('recall5','Macro-R@5'),('f15','Macro-F1@5'),
                           ('all_coverage5','AllCoverage@5'),('mrr10','MRR@10')):
            lines.append('| '+zh+' | '+label+' | '+' | '.join(common.percent(s['metrics'][a][unit][key]) for a in ARMS)+' |')
    lines += ['', '严格使用path::qualified_name和修复前库存；不以金标修预测，不压缩最终无效/重复槽位，'
              'P@5固定除以5。全部失败留分母。Hit采用Wilson95%CI，宏指标CI及完整配对统计见JSON；'
              f"bootstrap为{s['bootstrap_draws']}次、seed{s['bootstrap_seed']}，未显著不表示等效。", '', '## 同题配对', '']
    lines += ['| 比较（后者−前者） | 函数Hit | 均中/仅前者/仅后者/均未中 | 差值 | 配对95%CI | 精确McNemar p |',
              '|---|---|---|---:|---:|---:|']
    for pair in s['paired_comparisons'].values():
        if pair['status'] != 'ANALYZED':
            continue
        a,b = pair['arms']
        for k in (1,3,5):
            m=pair['function'][str(k)]
            four='/'.join(str(m[x]) for x in ('both_success','only_a','only_b','both_failure'))
            lines.append(f"| {LABELS[a]} → {LABELS[b]} | @{k} | {four} | {100*m['b_minus_a']:+.2f}pp | "
                         f"{common.ci_text(m['b_minus_a_ci95'])} | {m['exact_mcnemar_p']:.6g} |")
    lines += ['', '探索性比较未作多重校正；父池选择偏差及框架配置差异限制总体结论。', '',
              '## 统一资源账与时间边界', '',
              '下表每道题只读取一次真实raw推理回执；规范化复制和历史结果复用不形成新调用。'
              '主表是全部任务已有实际执行记录的合计，不表示这些用量都是本轮新增。'
              '新增执行的增量账单独保存在incremental_accounting.json，不拆成按批次的成绩表。', '',
              '| 单题记录 | 有记录题数 | 总量 | 均值 | 中位数 | P90 |', '|---|---:|---:|---:|---:|---:|']
    for key,label in (('known_prompt_tokens','已知输入token下界'),('known_completion_tokens','已知输出token下界'),
        ('known_total_tokens','已知总token下界'),('unknown_usage_requests','usage未知HTTP尝试'),
        ('runner_wall_seconds','隔离进程墙钟/秒'),('elapsed_seconds','worker内部/秒'),
        ('generation_seconds','HTTP生成/秒'),('tool_elapsed_seconds','工具执行/秒'),('graph_elapsed_seconds','构图/秒')):
        v=s['resources']['locagent'][key]
        display=lambda x:'NA' if x is None else f'{x:.2f}'
        lines.append('| '+label+f" | {v['records']} | "+' | '.join(display(v[k]) for k in ('sum','mean','median','p90'))+' |')
    wall=s['wall_clock']['extension_launcher_to_last_raw_terminal_seconds']
    lines += ['', '未知usage不填零；本地付费API为0不等于电费或硬件成本为0。worker内部时间不含导入；'
              'runner墙钟含隔离进程导入与执行，仍不含此前probe、模型启动和构图；各项可能嵌套，不能简单相加。', '',
              ('新增批次真实launcher至最后raw终态墙钟：'+f'{wall:.2f}秒。' if wall is not None else
               '新增批次尚未取得完整的最终墙钟。')+'该时间只描述本次推进阶段，不能称为全部280题连续运行时间；'
              '不使用规范化拷贝mtime或累计单题时间冒充并行墙钟。历史CoSIL硬件与共享文件阶段记账不同，'
              '不据该表宣称严格速度或总计算优势。', '', '## 状态、限制与复现', '',
              '统一解析已就绪的执行状态：`'+json.dumps(s['locagent_terminal_statuses'],ensure_ascii=False)+'`。'
              'complete只表示两次loop返回文本，partial表示部分sample有输出，均不表示定位命中。', '',
              '本轮只定位，不训练、修补issue或运行修复测试；不改历史结果、矩阵或论文。'
              '图缺少构造函数节点、其他名称截断及类表示等问题仍可能存在；统一规则不是完整AST修复。'
              '更好的解析交付不能直接解释为模型推理能力提升。', '',
              f'运行目录：`{run}`。', '', '```bash', 'source .venv/bin/activate',
              'python -m reproduction.evaluate_extension \\', f'  --run {run} \\',
              '  --output NEW_UNIFIED_EVALUATION_DIRECTORY', '```', '',
              '输出为全部任务逐题CSV、summary.json、evaluation.json和增量账；已有目录禁止覆盖。'
              '离线评分不启动模型、不调用工具，金标只在隔离评价程序使用。']
    return '\n'.join(lines)+'\n'


def evaluate_run(run_dir, output_dir=None, **kwargs):
    if kwargs.get('draws',5000)<40:
        raise ValueError('bootstrap draws must be >=40')
    run=Path(run_dir).resolve(strict=True)
    result=build_evaluation(run,**kwargs)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out=Path(output_dir) if output_dir else run/'reports'/('unified_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    for name,value in [('summary.json',result['summary']),('evaluation.json',result),
                       ('incremental_accounting.json',result['incremental_accounting'])]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    flattened=[]
    for row in result['records']:
        flat={k:row.get(k,'') for k in ('instance_id','repo','base_commit','function_scorable','gold_status','gold_functions',
            'gold_files','terminal','inference_terminal','execution_origin','normalization_state','execution_status',
            'raw_result_path','normalized_result_path','raw_result_sha256','normalized_result_sha256')}
        for arm in ARMS:
            flat[arm+'_status']=row.get(arm+'_status','')
            for unit in ('file','function'):
                metric=row.get(arm+'_'+unit) or dict.fromkeys(
                    ('hit1','hit3','hit5','precision5','recall5','f15','all_coverage5','mrr10','slots'),'')
                for key,value in metric.items():
                    flat[arm+'_'+unit+'_'+key]='' if arm=='locagent' and not row['terminal'] else value
            flat[arm+'_resources']=row['resources'].get(arm)
        flattened.append(flat)
    with (out/'per_issue.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flattened[0]));writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()}
                         for row in flattened)
    (out/'final_report.md').write_text(report_text(result,run),encoding='utf-8')
    result['output_directory']=str(out.resolve())
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--unified-dir',type=Path)
    parser.add_argument('--evaluator',type=Path)
    parser.add_argument('--seed',type=int,default=20261110)
    parser.add_argument('--bootstrap-draws',type=int,default=5000)
    args=parser.parse_args()
    result=evaluate_run(args.run,args.output,unified_dir=args.unified_dir,evaluator_path=args.evaluator,
                        seed=args.seed,draws=args.bootstrap_draws)
    print(json.dumps({'status':result['summary']['status'],'terminal_tasks':result['summary']['terminal_tasks'],
                      'pending_tasks':result['summary']['pending_tasks'],'output':result['output_directory']}))


if __name__=='__main__':
    main()
