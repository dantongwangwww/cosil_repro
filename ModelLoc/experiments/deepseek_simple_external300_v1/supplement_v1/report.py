"""Independent CPU evaluator for the frozen previous100 + additional200.

Never import this module in an inference worker. Only this offline process reads
per-issue gold.json. It does not read benchmark rows/tests, execute tools, call a
provider, change old files, or repair predictions. All outputs stay in reports/.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import sys
import tokenize

from .common import ROOT, FROZEN, PREVIOUS, RUN, COHORT, BUDGET_USD, utc

if str(FROZEN) not in sys.path:
    sys.path.insert(0, str(FROZEN))
from analysis.evaluation_extension import normalize_functions, normalize_files
from src.metrics import scores, mrr

PREVIOUS_RUN_ID = '20261021_external_nonthinking_v1'
COHORTS = ('previous100', 'additional200', 'combined300')
KS = (1, 3, 5, 10)
SEED = 20261021
PENDING = 'NOT_RUN'
CAUSE_ZH = {
    'hit_all_mappable_gold': 'Top5覆盖全部可映射gold身份',
    'hit_with_recall_gap': 'Top5已命中，但未覆盖全部可映射目标',
    'truth_unmappable': '无既有函数可映射真值，函数指标NA',
    'partial_auxiliary_miss': '部分可映射辅助目标未命中，不作严格主榜模型失败',
    'not_run': '尚未运行，不冒充模型答错',
    'execution_or_output_failure': '运行/预算/最终输出阶段未完成',
    'source_or_truth_integrity_unproven': '源码、请求或真值身份一致性未获证实',
    'invalid_final_output': '最终JSON或函数身份无效',
    'inventory_filter_and_grep_no_recovery': '目标路径未展示于文件inventory，grep亦未恢复目标源码',
    'file_selection_and_grep_no_recovery': '目标文件未入最终选择，grep亦未恢复目标源码',
    'selected_whole_file_overflow': '已选目标文件因80K上下文限制跳过，grep排除已选文件',
    'selected_five_file_limit': '已选目标文件位于最多5个整文件加载范围之外',
    'selected_not_loaded_unknown': '已选目标文件未加载，保存证据不足以确定具体子因',
    'grep_only_partial_gold_context': 'grep仅提供目标定义的部分源码',
    'source_not_delivered_to_final': '保存的context尚不足以证明最终模型成功收到源码',
    'rank_cutoff_at_5': 'gold身份排第6至10位，属于Top5截断',
    'ranking_omission_with_visible_source': 'gold同名定义span可见，但最终Top10未包含该精确身份',
    'mixed_visibility_and_ranking': '不同gold目标分别存在信息缺口与排序遗漏',
    'multiple_source_acquisition_gaps': '不同gold目标存在多种源码获取缺口',
    'gold_identity_missing_from_base_index': '既有gold身份不在当前冻结base AST索引中',
}


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def read_json(path, default=None):
    path = Path(path)
    if any(word in str(path).lower() for word in ('pruner_test', 'holdout', 'test_chain')):
        raise PermissionError('Sealed input is forbidden')
    return json.loads(path.read_text()) if path.is_file() else default


def decoded(raw):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def safe_issue_id(iid):
    if not isinstance(iid, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', iid) or iid in ('.', '..'):
        raise ValueError('Unsafe explicit issue ID')
    return iid


def relative_source(path):
    p = Path(path)
    if not isinstance(path, str) or not path.endswith('.py') or p.is_absolute() or '..' in p.parts or '\\' in path:
        raise ValueError('Unsafe repository source path')
    return path


def average(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def describe(values):
    import numpy as np
    values = [v for v in values if v is not None]
    return {'observed_n': len(values), 'mean': average(values),
            'p50': statistics.median(values) if values else None,
            'p90': float(np.quantile(values, .9)) if values else None,
            'sum': sum(values) if values else None}


def intervals_cover(blocks, start, end):
    cursor = start
    for a, b in sorted((max(start, x['start_line']), min(end, x['end_line'])) for x in blocks
                       if x['end_line'] >= start and x['start_line'] <= end):
        if a > cursor:
            return False
        cursor = max(cursor, b + 1)
    return cursor > end


def request_receipts(folder, origin, *, budget=None):
    """Saved attempts only; request IDs deduplicate financial accounting."""
    result, seen = [], set()
    for call in sorted((Path(folder) / 'calls').glob('*')):
        paths = sorted(call.glob('attempt_*_receipt.json')) + sorted(call.glob('attempt_*_error.json'))
        terminal = {p.name.rsplit('_', 1)[0] for p in paths}
        paths += [p for p in sorted(call.glob('attempt_*_started.json')) if p.name.rsplit('_', 1)[0] not in terminal]
        for path in paths:
            item = read_json(path); rid = item.get('request_id')
            if not rid or rid in seen:
                continue
            seen.add(rid)
            usage = item.get('usage') or {}
            reserved = (budget or {}).get('attempts', {}).get(rid, {})
            result.append({'origin': origin, 'request_id': rid, 'instance_id': item.get('instance_id'),
                'method': item.get('method', 'D-SIMPLE'), 'run_id': item.get('run_id'),
                'stage': item.get('stage'), 'sequence': item.get('sequence'), 'attempt': item.get('attempt'),
                'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0),
                'cache_hit_tokens': usage.get('prompt_cache_hit_tokens'), 'usage': usage,
                'api_cost_usd_usage_estimate': item.get('api_cost_usd_actual'),
                'api_cost_usd_peak_no_cache': item.get('api_cost_usd_normalized'),
                'charged_or_reserved_upper_usd': reserved.get('charged_upper_usd'),
                'billing_unknown': not bool(usage), 'http_status': item.get('http_status'),
                'finish_reason': item.get('finish_reason'), 'thinking_mode': item.get('thinking_mode'),
                'request_sha256': item.get('request_sha256'), 'response_sha256': item.get('response_sha256'),
                'start_utc': item.get('start_utc'), 'end_utc': item.get('end_utc'),
                'wall_seconds': item.get('attempt_elapsed_seconds'), 'evidence_path': str(path)})
    return result


def final_delivery(folder, context, receipts, *, iid, expected_run_id):
    """Exact saved context in successful final HTTP input, independent of tools."""
    paths = sorted((Path(folder) / 'calls').glob('*_function_localization/request.json'))
    proof = {'final_request_count': len(paths), 'final_http_context_delivered': False,
             'request_sha256': None, 'context_body_sha256': None, 'successful_request_ids': [],
             'source_block_count': len(context.get('blocks', [])),
             'nonempty_source_block_count': sum(bool(b.get('text')) for b in context.get('blocks', [])),
             'final_request_path': str(paths[0]) if len(paths) == 1 else None,
             'delivery_error': None}
    if len(paths) != 1:
        proof['delivery_error'] = 'missing_final_request' if not paths else 'multiple_final_semantic_requests'
        return proof
    saved = read_json(paths[0]); request = saved.get('request', {})
    if saved.get('sha256') != digest(json.dumps(request, sort_keys=True, ensure_ascii=False)):
        proof['delivery_error'] = 'final_request_sha_mismatch'; return proof
    blocks = context.get('blocks', [])
    if any(digest(b.get('text', '')) != b.get('sha256') for b in blocks):
        proof['delivery_error'] = 'context_block_sha_mismatch'; return proof
    joined = '\n\n'.join(b.get('header', '') + b.get('text', '') for b in blocks)
    wanted = '\n<context>\n' + joined + '\n</context>'
    if not any(wanted in m.get('content', '') for m in request.get('messages', [])):
        proof['delivery_error'] = 'final_payload_not_exact_saved_context'; return proof
    final_sequence = int(paths[0].parent.name.split('_', 1)[0])
    good = [r for r in receipts if r['stage'] == 'function_localization'
            and r.get('sequence') == final_sequence and r.get('http_status') == 200 and r.get('usage')
            and r.get('instance_id') == iid and r.get('method') == 'D-SIMPLE'
            and r.get('run_id') == expected_run_id and r.get('request_sha256') == saved['sha256']]
    proof.update(request_sha256=saved['sha256'], context_body_sha256=digest(joined),
                 successful_request_ids=sorted(r['request_id'] for r in good),
                 final_http_context_delivered=bool(good),
                 delivery_error=None if good else 'no_successful_matching_http_receipt')
    return proof


def verify_base_context(job, index, context, qualification=None):
    """Only explicit context files are read; compare base text and original spans."""
    snapshot = Path(job['snapshot']).resolve()
    raw_hashes = (qualification or {}).get('snapshot_python_sha256', {})
    loaded = context.get('loaded_whole_files', [])
    blocks = context.get('blocks', [])
    errors, verified = [], []
    if [b.get('path') for b in blocks[:len(loaded)]] != loaded:
        errors.append('loaded_whole_file_order_mismatch')
    cache = {}
    for position, block in enumerate(blocks):
        path = block.get('path')
        row = {'block_index': position, 'path': path,
               'origin': 'selected_whole_file' if position < len(loaded) else 'grep_evidence',
               'start_line': block.get('start_line'), 'end_line': block.get('end_line'),
               'original_complete_file_flag': bool(block.get('complete_file')), 'source_valid': False,
               'base_text_sha256': None, 'base_raw_sha256': None, 'block_sha256': block.get('sha256')}
        try:
            relative_source(path)
            source_path = snapshot / path
            if not source_path.resolve().is_relative_to(snapshot):
                raise ValueError('source_outside_snapshot')
            if path not in cache:
                raw = source_path.read_bytes(); text = decoded(raw)
                cache[path] = (raw, text)
            raw, text = cache[path]
            row.update(base_raw_sha256=digest(raw), base_text_sha256=digest(text),
                       qualification_raw_sha_available=path in raw_hashes)
            if path not in index or digest(text) != index[path].get('sha256'):
                raise ValueError('base_text_index_sha_mismatch')
            if path in raw_hashes and digest(raw) != raw_hashes[path]:
                raise ValueError('base_raw_qualification_sha_mismatch')
            start, end = block['start_line'], block['end_line']
            lines = text.splitlines(keepends=True)
            if not (1 <= start <= end <= len(lines) or (not lines and start == 1 and end == 0 and row['origin'] == 'selected_whole_file')):
                raise ValueError('invalid_source_span')
            expected = text if row['origin'] == 'selected_whole_file' else ''.join(lines[start - 1:end])
            if row['origin'] == 'selected_whole_file' and (start != 1 or end != len(lines)):
                raise ValueError('whole_file_span_not_complete')
            if expected != block.get('text') or digest(expected) != block.get('sha256'):
                raise ValueError('context_not_exact_base_span')
            row['source_valid'] = True
        except (ValueError, OSError, UnicodeError, SyntaxError, TypeError) as error:
            row['error'] = str(error)
            errors.append(str(path) + ':' + str(error))
        verified.append(row)
    return {'base_context_verified': not errors, 'context_integrity_errors': errors,
            'verified_block_count': sum(b['source_valid'] for b in verified), 'blocks': verified}


def raw_output_audit(result, slots):
    raw = result.get('raw_output')
    info = {'raw_final_json_valid': None, 'raw_ranked_functions_list': None, 'raw_ranked_function_count': None,
            'raw_excess_entries': None, 'invalid_slots_top5': [i + 1 for i, v in enumerate(slots[:5]) if v is None],
            'duplicate_valid_slots': len([v for v in slots if v is not None]) - len(set(v for v in slots if v is not None))}
    if isinstance(raw, str):
        try:
            obj = json.loads(raw); info['raw_final_json_valid'] = True
            values = obj.get('ranked_functions') if isinstance(obj, dict) else None
            info['raw_ranked_functions_list'] = isinstance(values, list)
            if isinstance(values, list):
                info.update(raw_ranked_function_count=len(values), raw_excess_entries=max(0, len(values) - 10))
        except (ValueError, TypeError):
            info['raw_final_json_valid'] = False; info['raw_ranked_functions_list'] = False
    return info


def target_diagnostics(iid, gold, index, context, inventory, selection, proof, integrity, slots, output_info):
    targets = []
    selected = selection.get('ranked_edit_files', context.get('ranked_edit_files', []))
    loaded = context.get('loaded_whole_files', [])
    skipped = {x['path']: x for x in context.get('skipped_files', [])}
    valid_blocks = [b for b, audit in zip(context.get('blocks', []), integrity['blocks']) if audit['source_valid']]
    full_origin = context.get('blocks', [])[:len(loaded)]
    for identity in gold['gold_functions']:
        path, qn = identity.split('::', 1)
        definitions = [d for d in index.get(path, {}).get('definitions', [])
                       if d['kind'] == 'function' and d['qualified_name'] == qn]
        spans = [b for b in valid_blocks if b['path'] == path]
        full_visible = any(intervals_cover(spans, d['start_line'], d['end_line']) for d in definitions)
        partial_visible = any(b['end_line'] >= d['start_line'] and b['start_line'] <= d['end_line'] for b in spans for d in definitions)
        rank = next((i + 1 for i, value in enumerate(slots[:10]) if value == identity), None)
        ancestor, descendant = [], []
        for position, predicted in enumerate(slots[:5], 1):
            if predicted is None:
                continue
            p, name = predicted.split('::', 1)
            if p == path and qn.startswith(name + '.'):
                ancestor.append({'rank': position, 'identity': predicted})
            if p == path and name.startswith(qn + '.'):
                descendant.append({'rank': position, 'identity': predicted})
        in_inventory = path in inventory.get('paths', []) if inventory else None
        is_selected = path in selected
        overflow = path in skipped and skipped[path].get('reason') == 'whole_file_overflow'
        five_limit = bool(is_selected and path not in loaded and path not in skipped and len(loaded) == 5
                          and all(p in selected for p in loaded) and selected.index(path) > max(selected.index(p) for p in loaded))
        delivered_full = bool(proof['final_http_context_delivered'] and full_visible)
        delivered_partial = bool(proof['final_http_context_delivered'] and partial_visible)
        labels = []
        if in_inventory is False:
            labels.append('gold_path_not_in_displayed_inventory')
        if not is_selected:
            labels.append('gold_path_not_selected')
        if overflow:
            labels.append('selected_whole_file_overflow')
        if five_limit:
            labels.append('selected_five_file_limit')
        if path in loaded:
            labels.append('gold_file_loaded_whole')
        grep_blocks = [b for b in context.get('blocks', [])[len(loaded):] if b['path'] == path]
        if grep_blocks:
            labels.append('gold_path_in_grep_evidence')
        if full_visible and not is_selected:
            labels.append('grep_recovered_unselected_gold_identity')
        if ancestor:
            labels.append('predicted_outer_instead_of_nested_gold')
        if descendant:
            labels.append('predicted_nested_instead_of_outer_gold')
        if len(definitions) > 1:
            labels.append('shared_qualified_name_multiple_definition_spans')
        if output_info['invalid_slots_top5']:
            labels.append('invalid_output_slots_occupy_ranks')
        if rank is not None and rank <= 5:
            cause = 'hit_all_mappable_gold'
            if not delivered_partial:
                labels.append('correct_identity_without_proven_gold_source')
        elif not definitions:
            cause = 'gold_identity_missing_from_base_index'
        elif not integrity['base_context_verified']:
            cause = 'source_or_truth_integrity_unproven'
        elif not proof['final_http_context_delivered']:
            cause = 'source_not_delivered_to_final'
        elif output_info['raw_final_json_valid'] is False or output_info['raw_ranked_functions_list'] is False or not any(v is not None for v in slots):
            cause = 'invalid_final_output'
        elif delivered_full:
            cause = 'rank_cutoff_at_5' if rank is not None else 'ranking_omission_with_visible_source'
        elif delivered_partial:
            cause = 'grep_only_partial_gold_context'
        elif overflow:
            cause = 'selected_whole_file_overflow'
        elif five_limit:
            cause = 'selected_five_file_limit'
        elif not is_selected:
            cause = 'inventory_filter_and_grep_no_recovery' if in_inventory is False else 'file_selection_and_grep_no_recovery'
        else:
            cause = 'selected_not_loaded_unknown'
        old_lines = sorted({e['line'] for e in gold.get('changed_line_evidence', [])
                            if e.get('function_id') == identity and e.get('change') == '-'})
        covered_old_lines = [line for line in old_lines if any(b['start_line'] <= line <= b['end_line'] for b in spans)]
        targets.append({'instance_id': iid, 'gold_identity': identity, 'gold_path': path,
            'gold_mapping_status': gold['mapping_status'], 'gold_rank_top10': rank,
            'hit_at_5': rank is not None and rank <= 5, 'target_primary_cause': cause,
            'target_primary_cause_zh': CAUSE_ZH[cause], 'labels': sorted(set(labels)),
            'in_displayed_inventory': in_inventory, 'selected_file_rank': selected.index(path) + 1 if is_selected else None,
            'loaded_whole_file': path in loaded, 'overflow_record': skipped.get(path), 'five_file_limit': five_limit,
            'context_any_definition_full': full_visible, 'context_any_definition_partial': partial_visible,
            'final_delivered_any_definition_full': delivered_full, 'final_delivered_any_definition_partial': delivered_partial,
            'definition_span_count': len(definitions), 'definition_spans': definitions,
            'actual_modified_implementation_verified': False,
            'changed_base_deleted_lines': old_lines, 'changed_base_deleted_lines_covered': covered_old_lines,
            'changed_base_deleted_line_coverage': len(covered_old_lines) / len(old_lines) if old_lines else None,
            'predicted_ancestor_symbols_top5': ancestor, 'predicted_descendant_symbols_top5': descendant,
            'source_span_evidence': [{k: b[k] for k in ('path', 'start_line', 'end_line', 'sha256')} for b in spans]})
    return targets


def issue_primary(result, gold, metrics, targets, integrity):
    if gold['mapping_status'] == 'unmappable' or not gold['gold_functions']:
        return 'truth_unmappable'
    if result['status'] == PENDING:
        return 'not_run'
    if result['status'] != 'complete':
        return 'execution_or_output_failure'
    if metrics['function_hit_5'] == 1:
        return 'hit_with_recall_gap' if metrics['function_recall_5'] < 1 else 'hit_all_mappable_gold'
    if gold['mapping_status'] == 'partially_mappable':
        return 'partial_auxiliary_miss'
    causes = {t['target_primary_cause'] for t in targets if not t['hit_at_5']}
    if not integrity['base_context_verified'] or 'gold_identity_missing_from_base_index' in causes:
        return 'source_or_truth_integrity_unproven'
    if len(causes) == 1:
        return next(iter(causes))
    ranking = {'rank_cutoff_at_5', 'ranking_omission_with_visible_source'}
    return 'mixed_visibility_and_ranking' if causes & ranking else 'multiple_source_acquisition_gaps'


def score_result(result, gold, job, index, selection):
    files_raw = result.get('predicted_files') or selection.get('ranked_edit_files', [])
    function_raw = result.get('predicted_functions', [])
    functions, bad_functions = normalize_functions(function_raw, index)
    files, bad_files = normalize_files(files_raw, job['paths'])
    out = {'normalized_function_slots': functions, 'normalized_file_slots': files,
           'invalid_function_slots': bad_functions, 'invalid_file_slots': bad_files,
           'raw_predicted_functions': function_raw, 'raw_predicted_files': files_raw}
    for prefix, predictions, targets in (('function', functions, gold['gold_functions']), ('file', files, gold['gold_files'])):
        for k in KS:
            for metric, value in scores(predictions, targets, k).items():
                out[f'{prefix}_{metric}_{k}'] = None if result['status'] == PENDING else value
        out[f'{prefix}_mrr_10'] = None if result['status'] == PENDING else mrr(predictions, targets)
    return out


def issue_chinese_summary(job, primary, targets):
    text = job['problem_statement']
    excerpt = re.sub(r'\s+', ' ', text).strip()[:280]
    topics = []
    for pattern, topic in ((r'\b(type|typing|annotation|hint)\b', '类型/标注'),
            (r'\b(memory|performance|slow)\b', '性能/资源'), (r'\b(parse|parser|parsing|serialize|serialization)\b', '解析/序列化'),
            (r'\b(read|write|reader|writer|file|stream)\b', '读写/文件处理'),
            (r'\b(error|exception|raise|crash)\b', '异常/报错'), (r'\b(support|feature)\b', '功能支持')):
        if re.search(pattern, text, flags=re.I):
            topics.append(topic)
    subject = '、'.join(topics[:3]) if topics else '仓库行为与预期'
    missing = [t['gold_identity'] for t in targets if not t['hit_at_5']]
    summary = f"{job['repo']} 的问题文本涉及{subject}；本次证据分类：{CAUSE_ZH[primary]}。"
    if missing:
        summary += '未进入Top5的可映射身份：' + '、'.join(missing[:5]) + '。'
    return summary, excerpt


def confidence(values, repos, *, repeats=10000, seed=SEED):
    import numpy as np
    if not values:
        return {'issue_bootstrap95': [None, None], 'repo_cluster_bootstrap95': [None, None]}
    array = np.array(values, float); rng = np.random.default_rng(seed)
    boot = array[rng.integers(0, len(array), size=(repeats, len(array)))].mean(axis=1)
    grouped = defaultdict(list)
    for repo, value in zip(repos, values):
        grouped[repo].append(value)
    names = sorted(grouped)
    sums = np.array([sum(grouped[r]) for r in names]); sizes = np.array([len(grouped[r]) for r in names])
    picked = rng.integers(0, len(names), size=(repeats, len(names)))
    cluster = sums[picked].sum(axis=1) / sizes[picked].sum(axis=1)
    return {'issue_bootstrap95': [float(v) for v in np.quantile(boot, [.025, .975])],
            'repo_cluster_bootstrap95': [float(v) for v in np.quantile(cluster, [.025, .975])]}


def summarize(rows, cohort):
    allocated = [r for r in rows if cohort == 'combined300' or r['origin'] == cohort]
    observed = [r for r in allocated if r['status'] != PENDING]
    strict = [r for r in allocated if r['gold_mapping_status'] == 'fully_mappable']
    partial = [r for r in allocated if r['gold_mapping_status'] == 'partially_mappable']
    summary = {'cohort': cohort, 'allocated_n': len(allocated), 'observed_n': len(observed),
               'complete_n': sum(r['status'] == 'complete' for r in allocated),
               'strict_n': len(strict), 'strict_observed_n': sum(r['status'] != PENDING for r in strict),
               'strict_observed_hit5': average([r['function_hit_5'] for r in strict if r['status'] != PENDING]),
               'partial_n': len(partial),
               'unmapped_n': sum(r['gold_mapping_status'] == 'unmappable' for r in allocated),
               'file_gold_n': sum(bool(r['gold_file_count']) for r in allocated),
               'pending_n': sum(r['status'] == PENDING for r in allocated),
               'statuses': dict(Counter(r['status'] for r in allocated)),
               'metric_status': 'COMPLETE' if len(observed) == len(allocated) else 'INCOMPLETE_ALLOCATION_LOWER_BOUND',
               'strict_hit5_count': sum(r['function_hit_5'] or 0 for r in strict),
               'strict_hit5_misses_observed': sum(r['function_hit_5'] == 0 and r['status'] != PENDING for r in strict),
               'strict_hit5_with_recall_gap': sum(r['function_hit_5'] == 1 and r['function_recall_5'] < 1 for r in strict),
               'failure_primary_counts': dict(Counter(r['primary_cause'] for r in allocated)),
               'partial_auxiliary_hit5': average([r['function_hit_5'] for r in partial]),
               'partial_auxiliary_recall5': average([r['function_recall_5'] for r in partial])}
    for prefix, subset in (('function', strict), ('file', [r for r in allocated if r['gold_file_count']])):
        names = [f'{prefix}_{metric}_{k}' for k in KS for metric in ('hit', 'precision', 'recall', 'f1', 'all_coverage')] + [f'{prefix}_mrr_10']
        for name in names:
            values = [r[name] if r[name] is not None else 0 for r in subset]
            summary[name] = average(values) if observed else None
            summary[name + '_ci95'] = confidence(values, [r['repo'] for r in subset]) if observed else confidence([], [])
    for field in ('input_tokens', 'output_tokens', 'elapsed_seconds', 'process_cpu_seconds',
                  'api_cost_usd_usage_estimate', 'api_cost_usd_peak_no_cache'):
        summary[field] = describe([r[field] for r in observed])
    summary['gold_patch_pass_statuses'] = dict(Counter(r['gold_patch_pass'] for r in allocated))
    summary['empty_patch_fail_statuses'] = dict(Counter(r['empty_patch_fail'] for r in allocated))
    summary['execution_qualification_reasons'] = dict(Counter(r['execution_qualification_reason'] for r in allocated))
    summary['request_attempt_count'] = sum(r['request_attempt_count'] for r in observed)
    summary['billing_unknown_attempts'] = sum(r['billing_unknown_attempts'] for r in observed)
    summary['final_context_delivery_verified_n'] = sum(r['final_http_context_delivered'] and r['base_context_verified'] for r in observed)
    return summary


def report_write(root, name, value, *, json_value=False, csv_rows=False):
    directory = Path(root) / 'reports'; directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    if not path.resolve().is_relative_to(directory.resolve()):
        raise PermissionError('Offline outputs must stay in new ROOT/reports')
    if json_value:
        text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    elif csv_rows:
        fields = list(dict.fromkeys(k for row in value for k in row)) or ['status']
        stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in value:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()})
        text = stream.getvalue()
    else:
        text = value
    temp = path.with_suffix(path.suffix + '.tmp'); temp.write_text(text); temp.replace(path)


def build_report(root=ROOT, previous=PREVIOUS, run=RUN, *, expected_counts=(100, 200), verify_previous=True):
    """Standalone offline entry. Synthetic tests provide temporary roots only."""
    root, previous, run = Path(root), Path(previous), Path(run)
    combined = read_json(root / 'manifests/combined300.json')
    added = read_json(root / 'manifests/additional200.json')
    if combined is None or added is None:
        raise RuntimeError('Wait for frozen additional200/combined300 manifests')
    records = combined['records']
    ids = [safe_issue_id(r['instance_id']) for r in records]
    if len(set(ids)) != len(ids):
        raise RuntimeError('Combined issue IDs are not unique')
    if set(r['origin'] for r in records) != {'previous100', 'additional200'}:
        raise RuntimeError('Expected explicit previous100/additional200 provenance')
    new_ids = {r['instance_id'] for r in records if r['origin'] == 'additional200'}
    if new_ids != {r['instance_id'] for r in added['records']}:
        raise RuntimeError('Additional/combined manifests disagree by issue ID')
    if expected_counts is not None:
        old_n, new_n = expected_counts
        if sum(r['origin'] == 'previous100' for r in records) != old_n or len(new_ids) != new_n:
            raise RuntimeError('Frozen cohort allocation mismatch')
    budget = read_json(run / 'budget.json', {'stage_cap_usd': BUDGET_USD, 'attempts': {}})
    if budget.get('stage_cap_usd') != BUDGET_USD:
        raise RuntimeError(f'Additional200 budget must remain independent USD{BUDGET_USD:g}')
    rows, targets, ledger, block_audits = [], [], [], []
    for rec in records:
        iid, origin = rec['instance_id'], rec['origin']
        base_root = previous if origin == 'previous100' else root
        folder = (previous / 'runs' / PREVIOUS_RUN_ID / 'external/D-SIMPLE' / iid) if origin == 'previous100' else run / COHORT / 'D-SIMPLE' / iid
        job = read_json(rec['job'])
        if job is None or any(job.get(key) != rec[key] for key in ('instance_id', 'repo', 'base_commit')):
            raise RuntimeError('Manifest/clean-job identity disagreement: ' + iid)
        index = read_json(job['code_index'])
        # Only exact per-issue gold mappings are read: no raw benchmark/test rows.
        gold = read_json(base_root / 'evaluator_private' / iid / 'gold.json')
        if gold is None:
            raise RuntimeError('Missing existing offline gold mapping: ' + iid)
        result = read_json(folder / 'result.json', {'status': PENDING, 'predicted_functions': [], 'predicted_files': []})
        selection = read_json(folder / 'file_selection.json', {})
        context = read_json(folder / 'context.json', {'blocks': [], 'loaded_whole_files': []})
        inventory = read_json(folder / 'inventory.json', {})
        qualification = read_json(base_root / 'evaluator_private/preparation/qualification' / (iid + '.json'), {})
        case_ledger = request_receipts(folder, origin, budget=budget if origin == 'additional200' else None)
        ledger.extend(case_ledger)
        integrity = verify_base_context(job, index, context, qualification)
        proof = final_delivery(folder, context, case_ledger, iid=iid,
                               expected_run_id=PREVIOUS_RUN_ID if origin == 'previous100' else run.name)
        metrics = score_result(result, gold, job, index, selection)
        output = raw_output_audit(result, metrics['normalized_function_slots'])
        case_targets = target_diagnostics(iid, gold, index, context, inventory, selection, proof, integrity,
                                          metrics['normalized_function_slots'], output)
        primary = issue_primary(result, gold, metrics, case_targets, integrity)
        summary_zh, excerpt = issue_chinese_summary(job, primary, case_targets)
        cpu = result.get('process_cpu_seconds')
        if cpu is None and result.get('cpu_user_seconds') is not None and result.get('cpu_system_seconds') is not None:
            cpu = result['cpu_user_seconds'] + result['cpu_system_seconds']
        evidence = [str(folder / p) for p in ('result.json', 'inventory.json', 'file_selection.json', 'context.json')]
        if proof['final_request_path']:
            evidence.append(proof['final_request_path'])
        evidence.extend(r['evidence_path'] for r in case_ledger if r['stage'] == 'function_localization')
        labels = sorted({label for t in case_targets for label in t['labels']})
        row = {'origin': origin, 'instance_id': iid, 'repo': rec['repo'], 'base_commit': rec['base_commit'],
            'status': result['status'], 'gold_mapping_status': gold['mapping_status'],
            'gold_file_count': len(set(gold['gold_files'])), 'gold_function_count': len(set(gold['gold_functions'])),
            'gold_functions_offline_only': gold['gold_functions'], 'gold_files_offline_only': gold['gold_files'],
            'primary_cause': primary, 'primary_cause_zh': CAUSE_ZH[primary], 'labels': labels,
            'strict_hit5_failure': gold['mapping_status'] == 'fully_mappable' and result['status'] != PENDING and metrics['function_hit_5'] == 0,
            'strict_recall5_gap_after_hit': gold['mapping_status'] == 'fully_mappable' and metrics['function_hit_5'] == 1 and metrics['function_recall_5'] < 1,
            'partial_auxiliary_miss': gold['mapping_status'] == 'partially_mappable' and result['status'] != PENDING and metrics['function_hit_5'] == 0,
            'partial_auxiliary_recall_gap': gold['mapping_status'] == 'partially_mappable' and metrics['function_hit_5'] == 1 and metrics['function_recall_5'] < 1,
            'selected_files': selection.get('ranked_edit_files', []), 'loaded_whole_files': context.get('loaded_whole_files', []),
            'whole_file_overflow_records': context.get('skipped_files', []),
            'context_gold_identity_full_count': sum(t['context_any_definition_full'] for t in case_targets),
            'final_delivered_gold_identity_full_count': sum(t['final_delivered_any_definition_full'] for t in case_targets),
            'input_tokens': sum(r['input_tokens'] for r in case_ledger), 'output_tokens': sum(r['output_tokens'] for r in case_ledger),
            'api_cost_usd_usage_estimate': sum(r['api_cost_usd_usage_estimate'] or 0 for r in case_ledger),
            'api_cost_usd_peak_no_cache': sum(r['api_cost_usd_peak_no_cache'] or 0 for r in case_ledger),
            'request_attempt_count': len(case_ledger), 'billing_unknown_attempts': sum(r['billing_unknown'] for r in case_ledger),
            'elapsed_seconds': result.get('elapsed_seconds'), 'process_cpu_seconds': cpu, 'gpu_compute_seconds': 0,
            'resource_scope': 'D-SIMPLE_full_localization_pipeline; elapsed_includes_API_wait; CPU_separately_measured',
            'error_type': result.get('error_type'), 'error_message': result.get('error_message'),
            'gold_patch_pass': qualification.get('gold_patch_pass', 'NOT_CHECKED'),
            'empty_patch_fail': qualification.get('empty_patch_fail', 'NOT_CHECKED'),
            'execution_qualification_reason': qualification.get('execution_qualification_reason', 'previous_or_current_case_has_no_recorded_gold_empty_execution_qualification'),
            'qualification_environment': qualification.get('qualification_environment'),
            'test_execution_qualification': qualification.get('test_execution', 'NOT_RUN'),
            'issue_summary_zh': summary_zh, 'issue_excerpt_original': excerpt,
            'raw_result_path': str(folder / 'result.json'), 'evidence_paths': evidence,
            **metrics, **output, **{k: v for k, v in proof.items() if k != 'final_request_path'},
            'base_context_verified': integrity['base_context_verified'], 'context_integrity_errors': integrity['context_integrity_errors']}
        rows.append(row)
        targets.extend({'origin': origin, 'repo': rec['repo'], 'context_path': str(folder / 'context.json'),
                        'final_request_path': proof['final_request_path'], **t} for t in case_targets)
        block_audits.extend({'origin': origin, 'instance_id': iid, **b} for b in integrity['blocks'])
    unique = {}
    for item in ledger:
        rid = item['request_id']
        if rid in unique:
            if any(unique[rid].get(k) != item.get(k) for k in ('instance_id', 'usage', 'api_cost_usd_usage_estimate', 'api_cost_usd_peak_no_cache', 'request_sha256')):
                raise RuntimeError('Contradictory copied request_id: ' + rid)
        else:
            unique[rid] = item
    ledger = list(unique.values())
    summaries = [summarize(rows, cohort) for cohort in COHORTS]
    previous_summary = summaries[0]
    if verify_previous and {k: previous_summary[k] for k in ('allocated_n', 'strict_n', 'partial_n', 'unmapped_n', 'strict_hit5_count', 'file_gold_n')} != {
            'allocated_n': 100, 'strict_n': 46, 'partial_n': 38, 'unmapped_n': 16, 'strict_hit5_count': 37, 'file_gold_n': 99}:
        raise RuntimeError('Previous100 final strict evaluator reproduction failed')
    new_ledger = [r for r in ledger if r['origin'] == 'additional200']
    cost = {'new_budget_cap_usd': budget.get('stage_cap_usd'),
            'new_charged_or_reserved_upper_usd': sum(a.get('charged_upper_usd', 0) for a in budget.get('attempts', {}).values()),
            'new_usage_estimated_usd': sum(r['api_cost_usd_usage_estimate'] or 0 for r in new_ledger),
            'previous_usage_estimated_usd': sum(r['api_cost_usd_usage_estimate'] or 0 for r in ledger if r['origin'] == 'previous100'),
            'new_request_attempts': len(new_ledger),
            'new_billing_unknown_attempts': len({r['request_id'] for r in new_ledger if r['billing_unknown']} | {rid for rid, a in budget.get('attempts', {}).items() if a.get('status') != 'usage_received'}),
            'estimation_not_itemized_billing': True, 'previous100_charged_to_new_budget': False,
            'local_gpu_used_by_this_D_SIMPLE_extension': False}
    summary_json = {'generated_at': utc(), 'summaries': summaries, 'cost_accounting': cost,
                    'records': rows, 'diagnostic_target_count': len(targets),
                    'gold_reads_confined_to_offline_evaluator': True, 'sealed_test_read_or_stat': False}
    for name, value in (('per_issue.csv', rows), ('method_summary.csv', summaries), ('failure_targets.csv', targets),
                        ('source_delivery_audit.csv', block_audits), ('cost_ledger.csv', ledger),
                        ('strict_hit5_failures.csv', [r for r in rows if r['strict_hit5_failure']]),
                        ('strict_recall5_gaps.csv', [r for r in rows if r['strict_recall5_gap_after_hit']]),
                        ('partial_auxiliary_misses.csv', [r for r in rows if r['partial_auxiliary_miss']])):
        report_write(root, name, value, csv_rows=True)
    report_write(root, 'results.json', summary_json, json_value=True)
    report_write(root, 'cost_accounting.json', cost, json_value=True)
    render_markdown(root, summary_json, targets)
    return summary_json


def pct(value):
    return 'NA' if value is None else f'{100 * value:.2f}%'


def num(value):
    return 'NA' if value is None else f'{value:.6g}'


def render_markdown(root, data, targets):
    summaries, rows = data['summaries'], data['records']
    text = ['# D-SIMPLE外部300题扩展与失败归因', '', '生成：' + data['generated_at'], '',
            '旧100结果只读复用；新增200与合并300单独报告。方法仍是原D-SIMPLE：五次文件选择、交集/回退、整文件+grep、一次最终排序；没有加入签名候选、结构化工具增强或gold反馈重跑。', '',
            '| 集合 | 分配/完成 | 严格/partial/NA | Hit@1 | Hit@3 | Hit@5 | Recall@5 | P@5 | F1@5 | AllCoverage@5 | MRR@10 |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        text.append(f"| {s['cohort']} | {s['allocated_n']}/{s['complete_n']} | {s['strict_n']}/{s['partial_n']}/{s['unmapped_n']} | " + ' | '.join(pct(s[k]) for k in ('function_hit_1', 'function_hit_3', 'function_hit_5', 'function_recall_5', 'function_precision_5', 'function_f1_5', 'function_all_coverage_5', 'function_mrr_10')) + ' |')
    text += ['', '严格主分母仅fully_mappable，实际运行失败保留为未命中；NOT_RUN单列，尚未执行时all_allocated仅是累计下界。partial辅助只对可映射函数子集评分，不代表整题完整gold召回；unmappable函数指标NA，不硬判模型失败。文件主分母只含文件gold有效题，旧100为99。k=1/3/5/10全部指标及10,000次issue/repo cluster bootstrap95%CI见method_summary.csv，seed20261021。', '',
             '## 执行资格与抽样边界', '',
             '| 集合 | gold补丁通过状态 | empty补丁失败状态 | 未检查/环境原因 |', '|---|---|---|---|',
             *[f"| {s['cohort']} | {json.dumps(s['gold_patch_pass_statuses'], ensure_ascii=False)} | {json.dumps(s['empty_patch_fail_statuses'], ensure_ascii=False)} | {json.dumps(s['execution_qualification_reasons'], ensure_ascii=False)} |" for s in summaries], '',
             '这里只引用独立准备阶段资格记录，报告本身不执行任何补丁/测试。NOT_CHECKED不等于通过；环境限制不得包装为已验证gold-pass/empty-fail，亦不因此按gold可映射程度删选样本。本扩展不是完整CQ2论文300题抽样。临时clean job/base缓存若缺失，需按固定revision/base恢复并核SHA；不承诺/tmp在重启后保留，不重抽历史预测。', '',
             '## 失败归因口径', '',
             '归因是日志可核的证据分类，不是补做反事实实验。主因互斥，多标签及逐gold目标明细保留；一题多个目标分别有文件缺口和排序缺口时明确为混合，不强行归于单一模型能力。文件未选若被grep救回，不归为“最终缺源码”。已选但80K溢出的文件按原实现也被grep排除。最多5整文件与80K溢出分开。grep块即使complete_file=true，也保留其grep来源，不误算整文件选择。', '',
             '函数身份严格path::qualified_name，nested/property/overload同名定义不因span多而无效；任何同名定义span可见不等于真实修复实现完整可见。只对gold中已有删除行的base坐标额外报告覆盖；无法绑定实际修改span时保持未知。返回外层函数/嵌套粒度差异仅作诊断标签，不叶名放宽追回分数。第6–10位gold单列Top5截断。', '',
             '| 集合 | 严格Hit@5未命中 | 命中但Recall@5不足 | partial辅助未命中 |', '|---|---:|---:|---:|']
    for s in summaries:
        subset = [r for r in rows if s['cohort'] == 'combined300' or r['origin'] == s['cohort']]
        text.append(f"| {s['cohort']} | {s['strict_hit5_misses_observed']} | {s['strict_hit5_with_recall_gap']} | {sum(r['partial_auxiliary_miss'] for r in subset)} |")
    text += ['', '最终源码送达要求保存context的每个源码块SHA与base实际span相符，并在成功HTTP回执绑定的最终请求中逐字出现；没有HTTP成功证据不把“磁盘有源码”当模型收到。源码不可见与函数排序遗漏分开。模型见到同名span仍未排中，只能说观察到排序漏检，不能单凭该结果推断深层理解或实际修复能力。', '',
             '## 资源与费用', '', '| 集合 | 输入/输出token累计 | USD费率推算 | 处理墙钟mean/p50/p90秒 | CPU进程秒累计 |', '|---|---:|---:|---:|---:|']
    for s in summaries:
        text.append(f"| {s['cohort']} | {num(s['input_tokens']['sum'])}/{num(s['output_tokens']['sum'])} | {num(s['api_cost_usd_usage_estimate']['sum'])} | " + '/'.join(num(s['elapsed_seconds'][k]) for k in ('mean', 'p50', 'p90')) + f" | {num(s['process_cpu_seconds']['sum'])} |")
    cost = data['cost_accounting']
    text += ['', f"新增200独立硬限USD{num(cost['new_budget_cap_usd'])}；新增usage费率推算USD{num(cost['new_usage_estimated_usd'])}，保守已记/预约上界USD{num(cost['new_charged_or_reserved_upper_usd'])}，未知计费attempt {cost['new_billing_unknown_attempts']}。旧100费用不记入新增预算。", '',
             '费用来自usage、缓存和对应时段费率推算，不是逐笔账单。cost_ledger按request_id去重，不按文件行号累计。D-SIMPLE本轮不使用本地GPU；CPU不是免费，进程CPU秒与含API等待的处理墙钟分别列，旧100未实测CPU时为NA，不用墙钟替代。', '',
             '## 限制与交付', '',
             '这是SWE-rebench独立外部抽样扩展，不是论文原始300题；D-SIMPLE是CQ2-inspired函数级诊断扩展，不是论文官方函数定位方法，也未验证修复率。DeepSeek保持原非思考设置和模型别名/文档版本；服务端权重快照和随机种子未独立锁定。不训练、不做修复/测试、不碰封存test，不把gold用于选择文件或提示词。', '',
             '逐题严格未命中详见[未命中逐题归因.md](未命中逐题归因.md)，命中但召回不全与partial辅助单列。所有标签只在独立离线进程进入本reports目录，推理worker不可见。']
    report_write(root, 'final_report.md', '\n'.join(text) + '\n')
    details = ['# 未命中逐题归因', '', '中文概述按原Issue关键词与日志证据生成，原问题摘录供核对；不声称完成自动语义根因裁决。每题保留原始精确评分，不重试或修补预测。', '']
    for title, flag in (('严格Hit@5未命中', 'strict_hit5_failure'), ('严格命中但Recall@5不足', 'strict_recall5_gap_after_hit'), ('partial辅助未命中（非严格模型失败）', 'partial_auxiliary_miss')):
        details += ['## ' + title, '']
        chosen = [r for r in rows if r[flag]]
        if not chosen:
            details += ['当前无此类已观察结果。', '']
        for row in chosen:
            details += [f"### {row['instance_id']}（{row['origin']}）", '', row['issue_summary_zh'], '',
                        '原Issue摘录：' + row['issue_excerpt_original'].replace('\n', ' '), '',
                        f"状态={row['status']}；主因={row['primary_cause_zh']}；精确Top10=" + json.dumps(row['normalized_function_slots'], ensure_ascii=False),
                        '文件选择=' + json.dumps(row['selected_files'], ensure_ascii=False) + '；实际整文件=' + json.dumps(row['loaded_whole_files'], ensure_ascii=False),
                        '多标签=' + json.dumps(row['labels'], ensure_ascii=False), '',
                        '| 可映射目标 | 原rank≤10 | 最终同名span完整/部分可见 | 证据分类 |', '|---|---:|---|---|']
            for target in [t for t in targets if t['instance_id'] == row['instance_id']]:
                details.append(f"| {target['gold_identity']} | {target['gold_rank_top10']} | {target['final_delivered_any_definition_full']}/{target['final_delivered_any_definition_partial']} | {target['target_primary_cause_zh']} |")
            details += ['', '证据：' + '；'.join('`' + p + '`' for p in row['evidence_paths']), '']
    report_write(root, '未命中逐题归因.md', '\n'.join(details) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-incomplete', action='store_true', help='Report a checkpoint; pending items stay separate')
    args = parser.parse_args()
    manifest = read_json(ROOT / 'manifests/additional200.json')
    if manifest is None:
        raise RuntimeError('Additional200 manifest is not prepared')
    missing = [r['instance_id'] for r in manifest['records'] if not (RUN / COHORT / 'D-SIMPLE' / r['instance_id'] / 'result.json').is_file()]
    if missing and not args.allow_incomplete:
        raise RuntimeError('Wait for all allocated outcomes or explicitly request --allow-incomplete')
    result = build_report()
    print(json.dumps({'report': str(ROOT / 'reports/final_report.md'),
                      'cohorts': [{k: s[k] for k in ('cohort', 'allocated_n', 'strict_n', 'strict_hit5_count')} for s in result['summaries']],
                      'new_cost_usage_estimate_usd': result['cost_accounting']['new_usage_estimated_usd']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
