"""Read-only CPU evaluation and evidence reports for the frozen filtered265 pool.

No provider or inference module is imported. Shared financial artifacts and all
historical predictions are read only; outputs are confined to this ROOT/reports.
"""
from __future__ import annotations
import argparse
import collections
import csv
import importlib
import json
import statistics
import sys
from pathlib import Path
from . import common as C

COHORT = 'filtered265'
NEW_ORIGIN = 'new221'
REUSE_ORIGIN = 'old100_reuse44'
KS = (1, 3, 5, 10)
EXPECTED_COUNTS = {'total': 265, NEW_ORIGIN: 221, REUSE_ORIGIN: 44}
sys.path.insert(0, str(C.ADDITIONAL))
H = importlib.import_module('supplement_v1.report')


def output(name, value):
    path = C.ROOT / 'reports' / name
    if not path.resolve().is_relative_to((C.ROOT / 'reports').resolve()):
        raise PermissionError('Reports may only write the new reports directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.json':
        C.write(path, value)
    elif path.suffix == '.csv':
        fields = list(dict.fromkeys(k for row in value for k in row)) or ['status']
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in value:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                 for k, v in row.items()})
    else:
        path.write_text(value)
    return path


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def describe(values):
    import numpy as np
    values = [v for v in values if v is not None]
    return {'n': len(values), 'sum': sum(values) if values else None,
            'mean': mean(values), 'median': statistics.median(values) if values else None,
            'p90': float(np.quantile(values, .9)) if values else None,
            'p95': float(np.quantile(values, .95)) if values else None}


def score(pred, gold, k):
    if not gold:
        return dict.fromkeys(('hit', 'precision', 'recall', 'f1', 'all_coverage'))
    n = len(set(x for x in pred[:k] if x is not None) & set(gold))
    p, r = n / k, n / len(set(gold))
    return {'hit': int(n > 0), 'precision': p, 'recall': r,
            'f1': 2 * p * r / (p + r) if n else 0,
            'all_coverage': int(n == len(set(gold)))}


def ci(values, repos, repeats=10000):
    return H.confidence(values, repos, repeats=repeats, seed=C.SEED)


def fix_valid_empty_causes(targets, slots, info):
    if slots or not info.get('raw_final_json_valid') or not info.get('raw_ranked_functions_list'):
        return targets
    for target in targets:
        if target['target_primary_cause'] != 'invalid_final_output':
            continue
        if target['final_delivered_any_definition_full']:
            cause = 'valid_empty_prediction_with_visible_source'
        elif target['final_delivered_any_definition_partial']:
            cause = 'grep_only_partial_gold_context'
        elif target['overflow_record']:
            cause = 'selected_whole_file_overflow'
        elif target['five_file_limit']:
            cause = 'selected_five_file_limit'
        elif not target['selected_file_rank']:
            cause = ('inventory_filter_and_grep_no_recovery' if target.get('in_displayed_inventory') is False
                     else 'file_selection_and_grep_no_recovery')
        else:
            cause = 'selected_not_loaded_unknown'
        target['target_primary_cause'] = cause
        target['target_primary_cause_zh'] = ('合法空列表，目标源码可见但未输出函数'
                                            if cause.startswith('valid_empty') else H.CAUSE_ZH[cause])
    return targets


def resource_totals(attempts):
    unknown_usage = sum(bool(a['billing_unknown']) for a in attempts)
    unknown_cost = sum(a['api_cost_usd_usage_estimate'] is None for a in attempts)
    return {'input_tokens': None if unknown_usage else sum(a['input_tokens'] for a in attempts),
            'output_tokens': None if unknown_usage else sum(a['output_tokens'] for a in attempts),
            'request_attempts': len(attempts), 'billing_unknown_attempts': unknown_usage,
            'cost_unknown_attempts': unknown_cost,
            'usage_cost_usd': None if unknown_cost else sum(a['api_cost_usd_usage_estimate'] for a in attempts),
            'known_usage_cost_usd': sum(a['api_cost_usd_usage_estimate'] or 0 for a in attempts),
            'peak_no_cache_cost_usd': None if any(a['api_cost_usd_peak_no_cache'] is None for a in attempts)
            else sum(a['api_cost_usd_peak_no_cache'] for a in attempts)}


def total_known_or_none(rows, field):
    return None if any(row[field] is None for row in rows) else sum(row[field] for row in rows)


def classify_missing_result(raw, attempts, *, started=False):
    if raw['status'] != 'NOT_RUN':
        return raw
    if attempts:
        return dict(raw, status='attempted_without_terminal_result', error_type='MissingTerminalResultAfterHTTPRequest')
    if started:
        return dict(raw, status='execution_started_without_terminal_result', error_type='MissingTerminalResultAfterLocalStart')
    return raw


def status_family(status, *, executed):
    lower = status.lower()
    if status == 'complete':
        return 'complete'
    if 'preparation' in lower or lower in ('input_failed', 'missing_input'):
        return 'input_preparation_failure'
    if 'budget' in lower:
        return 'budget_stop' if executed else 'NOT_RUN'
    if lower in ('not_run', 'not_started', 'paused', 'user_paused') or lower.startswith('not_run'):
        return 'NOT_RUN'
    return 'execution_or_output_failure'


def validate_manifest(manifest, expected_counts=None):
    if not isinstance(manifest, dict) or manifest.get('n') != len(manifest.get('records', [])):
        raise ValueError('Manifest count is inconsistent')
    ids = [H.safe_issue_id(r['instance_id']) for r in manifest['records']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate issue in fixed allocation')
    origins = collections.Counter(r.get('origin') for r in manifest['records'])
    if set(origins) - {NEW_ORIGIN, REUSE_ORIGIN}:
        raise ValueError('Unexpected origin in filtered allocation')
    if expected_counts is not None:
        if manifest['n'] != expected_counts['total'] or any(origins[k] != expected_counts[k] for k in (NEW_ORIGIN, REUSE_ORIGIN)):
            raise ValueError('Frozen total/new/reuse allocation changed')
    return manifest


def observed_repository_metadata(manifest):
    previous = C.load(C.PREVIOUS / 'manifests/external.json', {})
    observed = {r['repo'] for r in previous.get('records', [])}
    observed |= {r['repo'] for r in manifest['records'] if r.get('repository_observed_in_old100') is True
                 or r['origin'] == REUSE_ORIGIN}
    return observed


def collect(manifest, cohort=COHORT, *, budget=None):
    if cohort != COHORT:
        raise ValueError('This report only accepts the filtered265 evaluation scope')
    validate_manifest(manifest)
    budget = C.load(C.SHARED_BUDGET, {}) if budget is None else budget
    observed_repos = observed_repository_metadata(manifest)
    records, alltargets, attempts_all = [], [], []
    for rec in manifest['records']:
        iid = rec['instance_id']; folder = Path(rec['result_dir'])
        job = C.load(rec['job']) if rec.get('job') else None
        goldpath = C.ROOT / 'evaluator_private/eval_v2' / cohort / iid / 'gold_v2.json'
        gold = C.load(goldpath)
        unavailable = []
        if job is None:
            unavailable.append('clean_job_unavailable')
        else:
            if job['instance_id'] != iid or any(k in rec and rec[k] != job[k] for k in ('repo', 'base_commit')):
                raise RuntimeError('Descriptor/job identity mismatch: ' + iid)
        if gold is None:
            unavailable.append('gold_unavailable')
        elif gold['instance_id'] != iid or any(k in rec and rec[k] != gold[k] for k in ('repo', 'base_commit')):
            raise RuntimeError('Descriptor/gold identity mismatch: ' + iid)
        index = C.load(gold['code_index_v2_path']) if gold and gold.get('code_index_v2_path') else None
        if gold is not None and index is None:
            unavailable.append('evaluation_index_unavailable')
        index = index or {}
        saved = C.load(folder / 'result.json')
        started = (folder / 'started.json').is_file()
        raw = saved or {'status': 'NOT_RUN', 'predicted_files': [], 'predicted_functions': []}
        if saved is not None:
            if any(k in saved and saved[k] != rec[k] for k in ('instance_id', 'repo', 'base_commit')):
                raise RuntimeError('Result/descriptor identity mismatch: ' + iid)
            if saved.get('method', 'D-SIMPLE') != 'D-SIMPLE':
                raise RuntimeError('Unexpected method result: ' + iid)
        selection = C.load(folder / 'file_selection.json', {})
        context = C.load(folder / 'context.json', {'blocks': []})
        inventory = C.load(folder / 'inventory.json', {})
        attempts = H.request_receipts(folder, rec['origin'], budget=budget)
        if any(a['instance_id'] != iid or a['method'] != 'D-SIMPLE' for a in attempts):
            raise RuntimeError('Receipt/descriptor identity mismatch: ' + iid)
        raw = classify_missing_result(raw, attempts, started=started)
        if raw['status'] == 'NOT_RUN' and rec.get('preparation_status') == 'failed':
            raw = dict(raw, status='input_preparation_failed', error_type=rec.get('preparation_error_type'))
        terminal_is_execution = saved is not None and raw['status'].lower() not in (
            'not_run', 'not_started', 'paused', 'user_paused', 'input_preparation_failed', 'budget_not_run', 'budget_skipped')
        executed = bool(attempts or started or terminal_is_execution)
        family = status_family(raw['status'], executed=executed)
        attempts_all.extend(attempts)
        qraw = raw.get('predicted_functions', [])
        fraw = raw.get('predicted_files') or selection.get('ranked_edit_files', [])
        if not isinstance(qraw, list) or not isinstance(fraw, list):
            raise RuntimeError('Result ranking container must be a list: ' + iid)
        slots, invalid = H.normalize_functions(qraw, index)
        fslots, finvalid = H.normalize_files(fraw, job.get('paths', []) if job else [])
        proof = H.final_delivery(folder, context, attempts, iid=iid, expected_run_id=raw.get('run_id', ''))
        integrity = H.verify_base_context(job, index, context) if job and index else {
            'base_context_verified': False, 'context_integrity_errors': ['clean_job_or_evaluation_index_unavailable'], 'blocks': [], 'verified_block_count': 0}
        state = 'evaluation_unavailable' if unavailable else gold['status']
        targets_known = gold.get('existing_function_targets', []) if gold else []
        files_known = gold.get('gold_files', []) if gold else []
        function_scorable = state == 'COMPLETE_NONEMPTY'
        # File targets retain the original existing non-test Python-file scope.
        # A missing job/gold/index is never promoted to verified file truth.
        file_scorable = bool(files_known) and not unavailable
        legacy = {'gold_files': files_known, 'gold_functions': targets_known,
                  'mapping_status': 'fully_mappable' if function_scorable else 'unmappable',
                  'changed_line_evidence': [dict(e, function_id=e.get('base_function_id'), line=e.get('old_line'))
                                           for e in (gold or {}).get('changed_line_evidence', [])
                                           if e.get('change') == '-' and e.get('old_line') is not None]}
        info = H.raw_output_audit(raw, slots)
        targets = H.target_diagnostics(iid, legacy, index, context, inventory, selection, proof, integrity, slots, info) if not unavailable else []
        targets = fix_valid_empty_causes(targets, slots, info)
        alltargets.extend(targets)
        row = {'cohort': cohort, 'instance_id': iid, 'repo': rec.get('repo', (job or {}).get('repo')),
               'base_commit': rec.get('base_commit', (job or {}).get('base_commit')), 'origin': rec['origin'],
               'repository_observed_in_old100': rec.get('repo') in observed_repos,
               'status': raw['status'], 'status_family': family, 'execution_attempted': executed,
               'http_attempted': bool(attempts), 'terminal_result_present': saved is not None,
               'not_run_reason': rec.get('not_run_reason') or ('shared_budget_stop' if family == 'NOT_RUN' and
                    (C.SHARED_BUDGET.parent / 'budget_stop.json').exists() else None),
               'function_evaluation_status': state, 'declared_gold_status': (gold or {}).get('status'),
               'evaluation_unavailable_reasons': unavailable, 'function_scorable': function_scorable,
               'file_scorable': file_scorable, 'file_truth_source_verified': file_scorable,
               'function_eligibility_unknown': state in ('INCOMPLETE', 'evaluation_unavailable'),
               'file_eligibility_unknown': bool(unavailable) or (not files_known and state == 'INCOMPLETE'),
               'gold_function_count': len(targets_known), 'gold_functions': targets_known,
               'gold_file_count': len(files_known), 'gold_files': files_known,
               'v1_mapping_status': (gold or {}).get('v1_mapping_status'),
               'normalized_function_slots': slots, 'normalized_file_slots': fslots,
               'raw_predicted_functions': qraw, 'raw_predicted_files': fraw,
               'invalid_function_slots': invalid, 'invalid_file_slots': finvalid, 'output_audit': info,
               **resource_totals(attempts), 'is_new_inference': rec['origin'] == NEW_ORIGIN,
               'elapsed_seconds': raw.get('elapsed_seconds'), 'process_cpu_seconds': raw.get('process_cpu_seconds'),
               'base_context_verified': integrity['base_context_verified'],
               'final_http_context_delivered': proof['final_http_context_delivered'], 'source_delivery_proof': proof,
               'source_integrity_errors': integrity['context_integrity_errors'], 'model_error_type': raw.get('error_type'),
               'evaluator_errors': (gold or {}).get('errors', []),
               'scope_exempt_change_count': len((gold or {}).get('scope_exempt_changes', [])),
               'scope_exempt_reason_counts': dict(collections.Counter(e.get('reason', 'unspecified') for e in (gold or {}).get('scope_exempt_changes', []))),
               'gold_v2_path': str(goldpath), 'result_path': str(folder / 'result.json'), 'context_path': str(folder / 'context.json'),
               'gold_patch_pass': 'NOT_CHECKED', 'empty_patch_fail': 'NOT_CHECKED',
               'test_qualification_note': 'No per-case official harness execution is performed or inferred by this report.'}
        for prefix, predictions, truth, eligible in [('file', fslots, files_known, file_scorable),
                                                     ('function', slots, targets_known, function_scorable)]:
            for k in KS:
                for metric, value in score(predictions, truth, k).items():
                    row[f'{prefix}_{metric}_{k}'] = value if eligible and family != 'NOT_RUN' else None
            row[prefix + '_mrr_10'] = (next((1 / (n + 1) for n, x in enumerate(predictions[:10]) if x in truth), 0)
                                       if eligible and family != 'NOT_RUN' else None)
        if family == 'NOT_RUN':
            row['failure_category'] = 'NOT_RUN'
        elif unavailable:
            row['failure_category'] = 'EVALUATION_UNAVAILABLE'
        elif not function_scorable:
            row['failure_category'] = 'EVALUATOR_INCOMPLETE' if state == 'INCOMPLETE' else 'NO_EXISTING_FUNCTION_TARGET'
        elif row['function_hit_5'] == 1:
            row['failure_category'] = 'HIT_WITH_RECALL_GAP' if row['function_recall_5'] < 1 else 'HIT_ALL_EXISTING_TARGETS'
        elif family != 'complete':
            row['failure_category'] = family.upper()
        else:
            row['failure_category'] = ';'.join(sorted({t['target_primary_cause'] for t in targets if not t['hit_at_5']}))
        records.append(row)
    return records, alltargets, attempts_all


def summarize(rows, name, *, population='allocation', ci_repeats=10000):
    if population not in ('allocation', 'executed', 'http_attempted'):
        raise ValueError('Unknown reporting population')
    included = rows if population == 'allocation' else [r for r in rows if r['execution_attempted' if population == 'executed' else 'http_attempted']]
    executed = [r for r in rows if r['execution_attempted']]
    resources = [r for r in included if r['execution_attempted'] or r['http_attempted']]
    counts = collections.Counter(r['status_family'] for r in rows)
    s = {'scope': name, 'population': population, 'allocated_n': len(rows), 'population_n': len(included),
         'executed_n': len(executed), 'http_attempted_n': sum(r['http_attempted'] for r in rows),
         'not_run_n': counts['NOT_RUN'], 'complete_n': counts['complete'],
         'model_or_output_failure_n': counts['execution_or_output_failure'], 'budget_stopped_n': counts['budget_stop'],
         'input_preparation_failure_n': counts['input_preparation_failure'],
         'status_counts': dict(collections.Counter(r['status'] for r in rows)), 'status_family_counts': dict(counts),
         'origins': dict(collections.Counter(r['origin'] for r in rows)), 'repository_n': len({r['repo'] for r in rows}),
         'previously_observed_repository_n': len({r['repo'] for r in rows if r['repository_observed_in_old100']}),
         'function_evaluation_status_counts': dict(collections.Counter(r['function_evaluation_status'] for r in rows)),
         'evaluation_unavailable_n': sum(r['function_evaluation_status'] == 'evaluation_unavailable' for r in rows),
         'incomplete_n': sum(r['function_evaluation_status'] == 'INCOMPLETE' for r in rows),
         'function_empty_n': sum(r['function_evaluation_status'] == 'COMPLETE_EMPTY' for r in rows),
         'allocation_function_eligibility_unknown_n': sum(r['function_eligibility_unknown'] for r in rows),
         'allocation_file_eligibility_unknown_n': sum(r['file_eligibility_unknown'] for r in rows),
         'allocation_pending': any(r['status_family'] == 'NOT_RUN' or r['function_eligibility_unknown'] for r in rows),
         'score_semantics': 'allocation_completion_credit_lower_bound' if population == 'allocation' and counts['NOT_RUN'] else 'executed_results_with_failures' if population != 'allocation' else 'allocation_results_with_failures'}
    for prefix in ('file', 'function'):
        eligible = [r for r in included if r[prefix + '_scorable']]
        s[prefix + '_denominator'] = len(eligible)
        s[prefix + '_not_run_in_denominator'] = sum(r['status_family'] == 'NOT_RUN' for r in eligible)
        names = [f'{prefix}_{m}_{k}' for k in KS for m in ('hit', 'precision', 'recall', 'f1', 'all_coverage')] + [prefix + '_mrr_10']
        for metric in names:
            values = [r[metric] if r[metric] is not None else 0 for r in eligible]
            s[metric] = mean(values)
            s[metric + '_ci95'] = ci(values, [r['repo'] for r in eligible], repeats=ci_repeats)
        hits = sum(r[prefix + '_hit_5'] or 0 for r in eligible)
        s[prefix + '_hit_5_count'] = hits
        s[prefix + '_hit_5_allocation_uncertainty_bounds'] = ([hits / len(eligible), (hits + s[prefix + '_not_run_in_denominator']) / len(eligible)] if eligible else [None, None])
    qs = [r for r in included if r['function_scorable']]
    s['function_more_than5_targets_n'] = sum(r['gold_function_count'] > 5 for r in qs)
    s['function_allcoverage5_maximum'] = mean([int(r['gold_function_count'] <= 5) for r in qs])
    for field in ('input_tokens', 'output_tokens', 'usage_cost_usd', 'peak_no_cache_cost_usd', 'elapsed_seconds', 'process_cpu_seconds'):
        s[field] = describe([r[field] for r in resources])
    s['resource_population_n'] = len(resources)
    s['new_api_usage_cost_usd'] = total_known_or_none([r for r in included if r['is_new_inference']], 'usage_cost_usd')
    s['historical_reuse_usage_cost_usd'] = total_known_or_none([r for r in included if not r['is_new_inference']], 'usage_cost_usd')
    s['usage_unknown_attempts'] = sum(r['billing_unknown_attempts'] for r in included)
    s['cost_unknown_attempts'] = sum(r['cost_unknown_attempts'] for r in included)
    s['known_usage_cost_usd'] = sum(r['known_usage_cost_usd'] for r in included)
    return s


def deduplicate_receipts(attempts):
    unique = {}
    fields = ('instance_id', 'method', 'run_id', 'stage', 'sequence', 'attempt', 'usage', 'request_sha256', 'response_sha256')
    for item in attempts:
        rid = item['request_id']
        if rid in unique and any(unique[rid].get(k) != item.get(k) for k in fields):
            raise RuntimeError('Contradictory duplicate request ID: ' + rid)
        unique.setdefault(rid, item)
    return list(unique.values())


def financial_summary(attempts, budget, baseline=None):
    if budget.get('stage_cap_usd') != C.BUDGET_USD or C.BUDGET_USD != 5.:
        raise RuntimeError('The original shared USD5 cap must remain unchanged')
    unique = deduplicate_receipts(attempts)
    new = [a for a in unique if a['origin'] == NEW_ORIGIN]
    reuse = [a for a in unique if a['origin'] == REUSE_ORIGIN]
    entries = budget.get('attempts', {})
    before = (baseline or {}).get('ledger', baseline or {})
    baseline_entries = before.get('attempts', {})
    if baseline is not None:
        if before.get('stage_cap_usd') != 5. or any(entries.get(k) != v for k, v in baseline_entries.items()):
            raise RuntimeError('The pre-existing financial baseline drifted')
    new_ids = {a['request_id'] for a in new}; reuse_ids = {a['request_id'] for a in reuse}
    missing_new = new_ids - set(entries)
    if missing_new:
        raise RuntimeError('New transmitted request missing from shared ledger: ' + ','.join(sorted(missing_new)))
    for item in new:
        entry = entries[item['request_id']]
        if entry.get('key') != 'D-SIMPLE|' + item['instance_id'] or (item['usage'] and entry.get('usage') != item['usage']):
            raise RuntimeError('Receipt/shared-ledger identity or usage mismatch')
    if new_ids & set(baseline_entries):
        raise RuntimeError('A new request was already in the prior financial baseline')
    if reuse_ids & set(entries):
        raise RuntimeError('Historical reuse was charged to this shared ledger')
    current_ids = set(entries) - set(baseline_entries) if baseline is not None else new_ids
    unlinked = current_ids - new_ids
    unknown = sum(a['api_cost_usd_usage_estimate'] is None for a in new)
    total = sum(a['charged_upper_usd'] for a in entries.values())
    if total > 5. + 1e-10:
        raise RuntimeError('Shared ledger exceeds the authorized USD5 cap')
    return {'path': str(C.SHARED_BUDGET), 'cap_usd': 5., 'shared_charged_upper_usd': total,
            'shared_attempts': len(entries), 'shared_status_counts': dict(collections.Counter(a['status'] for a in entries.values())),
            'financial_baseline_available': baseline is not None,
            'baseline_attempts': len(baseline_entries) if baseline is not None else None,
            'baseline_charged_upper_usd': sum(a['charged_upper_usd'] for a in baseline_entries.values()) if baseline is not None else None,
            'filtered_new_request_receipts': len(new), 'historical_reuse_request_receipts': len(reuse),
            'filtered_new_ledger_upper_usd': sum(entries[rid]['charged_upper_usd'] for rid in current_ids),
            'unlinked_current_ledger_request_ids': sorted(unlinked), 'new_cost_unknown_attempts': unknown,
            'new_usage_cost_usd': None if unknown or unlinked else sum(a['api_cost_usd_usage_estimate'] for a in new),
            'known_new_usage_cost_usd': sum(a['api_cost_usd_usage_estimate'] or 0 for a in new),
            'historical_reuse_usage_cost_usd': None if any(a['api_cost_usd_usage_estimate'] is None for a in reuse)
            else sum(a['api_cost_usd_usage_estimate'] for a in reuse),
            'new_independent_budget_created': False if baseline is not None else None, 'report_created_budget': False, 'usage_estimate_is_account_invoice': False}


def pct(value):
    return 'NA' if value is None else f'{100 * value:.2f}%'


def num(value):
    return 'NA' if value is None else f'{value:.8g}'


def markdown_summary(summaries, rows, finance):
    text = ['# 四规则筛选265题：D-SIMPLE独立结果', '',
            f'生成时间：{C.utc()}。本表只属于filtered265，旧Lite与原external100分别保留独立报告。', '',
            '业务patch≤1文件、≤3hunks、无文件新增/删除，problem_statement用word.split计数≥40；历史隔离保持，用户取消每仓一题。固定265题/173仓，旧100中44题复用、新推理分配221题。该数据集不是CQ2-CARE论文原生300题，不保证与SWE-bench Lite难度相同。', '',
            '| 分配范围/统计人口 | 分配/启动/HTTP | 未运行/预算停/模型或输出失败/输入失败 | 文件/函数分母 | 函数Hit1/3/5 | Recall@5/AllCoverage@5 |',
            '|---|---:|---|---:|---|---|']
    for s in summaries:
        text.append(f"| {s['scope']} | {s['allocated_n']}/{s['executed_n']}/{s['http_attempted_n']} | "
                    + '/'.join(str(s[k]) for k in ('not_run_n', 'budget_stopped_n', 'model_or_output_failure_n', 'input_preparation_failure_n'))
                    + f" | {s['file_denominator']}/{s['function_denominator']} | "
                    + '/'.join(pct(s['function_hit_' + str(k)]) for k in (1, 3, 5)) + ' | '
                    + pct(s['function_recall_5']) + '/' + pct(s['function_all_coverage_5']) + ' |')
    text += ['', 'allocation行把已冻结且已知可评的未运行题记为“尚无完成信用”，只给完成信用下界，不能称作这些题的真实模型成绩；逐题NOT_RUN指标仍为NA。executed行仅包括真实启动/HTTP/执行终态的题，已执行失败及预算中止仍留在该行分母。新组另列http_attempted子组。缺gold/index/job记evaluation_unavailable，不记COMPLETE_EMPTY，不从未知函数资格推测分母。', '',
             '| 范围/人口 | 函数Hit5计数/分母 | 95% issue / repo-cluster CI | 未运行所致Hit5上下界 | Precision@5/F1@5/MRR10 | 完整/空/不完整/不可用 |',
             '|---|---|---|---|---|---|']
    for s in summaries:
        interval = s['function_hit_5_ci95']; bounds = s['function_hit_5_allocation_uncertainty_bounds']
        text.append(f"| {s['scope']} | {s['function_hit_5_count']}/{s['function_denominator']} | "
                    + ' / '.join('[' + ','.join(pct(v) for v in interval[k]) + ']' for k in ('issue_bootstrap95', 'repo_cluster_bootstrap95'))
                    + ' | [' + ','.join(pct(v) for v in bounds) + '] | '
                    + '/'.join(pct(s['function_' + k]) for k in ('precision_5', 'f1_5', 'mrr_10')) + ' | '
                    + json.dumps(s['function_evaluation_status_counts'], ensure_ascii=False) + ' |')
    text += ['', '所有k=1/3/5/10的文件与函数Hit、precision、recall、F1、AllCoverage及MRR10见CSV。沿用冻结path::qualified_name身份、共享同QN span、原槽位和固定k分母；不按叶名/父子函数或模型所报行号补名。合法空列表与无效身份/JSON错误分开。10,000次issue及repo-cluster bootstrap使用固定seed20261022；重复仓库按仓整体重采样。allocation下界的CI只描述完成信用统计，不补偿未运行的不确定性。', '',
             'COMPLETE_EMPTY表示所声明范围内没有补丁修改的既有具名Python函数，不是模型失败；INCOMPLETE与evaluation_unavailable单列。非测试既有Python文件作为文件真值，不能把未知文件真值推断为已核验；函数与文件各用其独立分母。源码/函数数超过Top5覆盖能力的题保留，并报告AllCoverage理论上限。', '',
             '## 请求、费用和资源', '',
             f"共享原账本cap=${finance['cap_usd']}；基线保守占用=${num(finance['baseline_charged_upper_usd'])}，当前共享占用=${num(finance['shared_charged_upper_usd'])}。新增run不重置额度，历史复用不重扣。当前新请求回执{finance['filtered_new_request_receipts']}、历史复用回执{finance['historical_reuse_request_receipts']}；本池新增usage费用估算=${num(finance['new_usage_cost_usd'])}，已知subtotal=${num(finance['known_new_usage_cost_usd'])}。费用未知attempt={finance['new_cost_unknown_attempts']}，无法关联的新账本条目={len(finance['unlinked_current_ledger_request_ids'])}。", '',
             '| 范围/人口 | 新增/历史usage费用USD | 单题输入mean/median/P90 | 单题输出mean/median/P90 | 单题墙钟mean/median/P90秒 |',
             '|---|---|---|---|---|']
    for s in summaries:
        text.append('| ' + s['scope'] + ' | ' + num(s['new_api_usage_cost_usd']) + '/' + num(s['historical_reuse_usage_cost_usd']) + ' | '
                    + ' | '.join('/'.join(num(s[field][k]) for k in ('mean', 'median', 'p90'))
                                 for field in ('input_tokens', 'output_tokens', 'elapsed_seconds')) + ' |')
    text += ['', '资源分布仅用实际执行/HTTP尝试的题，排除未运行占位零；记录缺失统计n，未知费用或usage不当0。存在未知时仅能称已知subtotal，不能称总费用。费用来自真实usage/缓存/冻结峰闲价格推算，并非账户账单。墙钟包含run_one内API等待、源码/grep及输出处理，不含队列、全量准备/SHA或离线评价；进程CPU秒另列，不能当GPU秒。', '',
             '## 来源、资格和解释限制', '',
             '已观察44题与新221题不能混称265题全新外部验证；重复仓库中的已观察repo数由旧100元数据与固定名单单列，见CSV。模型结果与旧gold/报告不改，模型输入没有离线v2金标；推理仍用原非思考D-SIMPLE和原在线3.11工具，Python3.12只在离线评价。gold_patch_pass与empty_patch_fail均NOT_CHECKED，不冒充官方harness或完全CQ2资格。原未筛选追加200仍保持暂停。',
             '逐题未命中和召回缺口依实际最终HTTP请求中的源码块、base SHA和定义区间诊断；有效输入hash本身不能证明目标源码已送达。源码可见也不推断模型注意或心理原因，人工语义复核另行标注。见[未命中分析.md](未命中分析.md)、gold_source_evidence.csv和逐请求cost_ledger.csv。',
             '工作目录实际位于/tmp；最终永久副本及GitHub代码文档以主线程delivery receipt为准，不依赖临时盘重启后存续。']
    return '\n'.join(text) + '\n'


def failure_md(rows, targets):
    text = ['# filtered265逐题结果与未命中证据', '',
            '已执行失败、预算停止、未运行、空函数目标和评价不可用分别列示。原因仅解释实际输入/输出与源码获取证据，不推断心理，也不反馈重跑。', '']
    for row in rows:
        if row['function_scorable'] and row['status_family'] != 'NOT_RUN' and row['function_hit_5'] == 1 and row['function_recall_5'] == 1:
            continue
        text += ['## ' + row['instance_id'], '',
                 f"来源={row['origin']}；状态={row['status']}；评价={row['function_evaluation_status']}；分类={row['failure_category']}。",
                 '目标=' + json.dumps(row['gold_functions'], ensure_ascii=False),
                 '原始函数Top10=' + json.dumps(row['raw_predicted_functions'][:10], ensure_ascii=False),
                 '固定槽Top10=' + json.dumps(row['normalized_function_slots'], ensure_ascii=False),
                 f"最终HTTP上下文送达={row['final_http_context_delivered']}；base源码核验={row['base_context_verified']}。",
                 '评价未解决证据=' + json.dumps(row['evaluator_errors'] + row['evaluation_unavailable_reasons'], ensure_ascii=False),
                 '范围外改动=' + json.dumps(row['scope_exempt_reason_counts'], ensure_ascii=False), '',
                 '| 既有函数目标 | 原rank≤10 | 完整/部分定义实际送达 | 证据支持的原因 |', '|---|---:|---|---|']
        for target in targets:
            if target['instance_id'] == row['instance_id']:
                text.append(f"| {target['gold_identity']} | {target['gold_rank_top10']} | {target['final_delivered_any_definition_full']}/{target['final_delivered_any_definition_partial']} | {target['target_primary_cause_zh']} |")
        proof = row['source_delivery_proof']
        text += ['', '证据：' + '；'.join(f'[{label}]({row[key]})' for label, key in (
            ('原结果', 'result_path'), ('保存上下文', 'context_path'), ('独立评价', 'gold_v2_path'))),
                 '最终HTTP证据=' + json.dumps(proof, ensure_ascii=False), '']
    return '\n'.join(text) + '\n'


def run_report(manifest_path=None, *, allow_incomplete=False, expected_counts=EXPECTED_COUNTS, ci_repeats=10000):
    path = Path(manifest_path) if manifest_path else C.ROOT / 'manifests/filtered265.json'
    manifest = validate_manifest(C.load(path), expected_counts)
    budget = C.load(C.SHARED_BUDGET)
    if budget is None:
        raise RuntimeError('The pre-existing shared ledger is required; report never creates one')
    rows, targets, attempts = collect(manifest, budget=budget)
    if not allow_incomplete and any(r['status_family'] == 'NOT_RUN' or r['function_evaluation_status'] == 'evaluation_unavailable' for r in rows):
        raise RuntimeError('Allocation/evaluation not finished; checkpoints need --allow-incomplete')
    groups = [('all', rows), ('reused', [r for r in rows if not r['is_new_inference']]), ('new', [r for r in rows if r['is_new_inference']])]
    summaries = [summarize(group, COHORT + '/' + label + '/' + population, population=population, ci_repeats=ci_repeats)
                 for label, group in groups for population in ('allocation', 'executed')]
    summaries.append(summarize(groups[-1][1], COHORT + '/new/http_attempted', population='http_attempted', ci_repeats=ci_repeats))
    unique = deduplicate_receipts(attempts)
    baseline = C.load(C.RUN / 'financial_baseline.json')
    if baseline is None and not allow_incomplete:
        raise RuntimeError('The frozen pre-stage financial baseline is required for a final report')
    finance = financial_summary(unique, budget, baseline)
    for name, value in [('per_issue.csv', rows), ('method_summary.csv', summaries), ('gold_source_evidence.csv', targets), ('cost_ledger.csv', unique)]:
        output(COHORT + '/' + name, value)
    result = {'generated_at': C.utc(), 'cohort': COHORT, 'manifest_path': str(path), 'manifest_sha256': C.sha(path),
              'allocation': {'n': len(rows), 'origins': dict(collections.Counter(r['origin'] for r in rows)),
                             'repositories': len({r['repo'] for r in rows}),
                             'previously_observed_repositories': len({r['repo'] for r in rows if r['repository_observed_in_old100']})},
              'summaries': summaries, 'records': rows, 'shared_finance': finance,
              'ci_repeats': ci_repeats, 'seed': C.SEED, 'new_model_requests_by_report': 0}
    output(COHORT + '/evaluation_summary.json', result)
    output(COHORT + '/shared_budget_summary.json', finance)
    output(COHORT + '/总览.md', markdown_summary(summaries, rows, finance))
    output(COHORT + '/未命中分析.md', failure_md(rows, targets))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--cohort', choices=[COHORT], default=COHORT)
    parser.add_argument('--allow-incomplete', action='store_true')
    args = parser.parse_args(argv)
    result = run_report(args.manifest, allow_incomplete=args.allow_incomplete)
    print(json.dumps({'reports': str(C.ROOT / 'reports' / COHORT), 'allocation': result['allocation'],
                      'new_receipts': result['shared_finance']['filtered_new_request_receipts'],
                      'shared_cap_usd': result['shared_finance']['cap_usd']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
