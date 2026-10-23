"""Offline report: old-correct172 plus unconditional paper-parameter retest93.

No inference/provider/pipeline is imported. Original gold/results/reports and
financial entries are read only. All output is confined to reports/paper_retest93.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import json
import re
from pathlib import Path
from unittest.mock import patch

from filtered265 import report as B
from . import common as C

REPORT = 'paper_retest93'
MASK = '[BENCHMARK_METADATA]'
_OLD_DELIVERY = B.H.final_delivery
CAUSES = dict(B.H.CAUSE_ZH, **{
    'selected_file_60k_prefix_truncation': '已选主文件的60K原文前缀未完整覆盖目标',
    'evidence_span_12k_prefix_truncation': '12K证据前缀未完整覆盖目标',
    'selected_context_80k_skip': '已选源码块因总80K上下文装箱限制被跳过',
    'file_rank_cutoff_at_5': '目标文件排第6至10位，未进入文件Top5',
    'file_selection_miss': '目标文件未出现在最终文件Top10',
    'file_only_miss': '函数已命中或为NA，但文件Top5未命中',
    'hit5_with_recall_gap': '函数Top5命中，但尚未覆盖全部既有函数目标',
    'retained_old_hit5_recall_gap': '旧保留结果Hit5已中但召回不全，非本轮重测失败',
    'NOT_RUN': '尚未运行，不判作模型定位错误',
    'engineering_failure': '工程、预算或最终输出阶段未完成',
})
IDENTITY_SUBTYPES = {
    'metadata_alias_identity_boundary': '合法JSON；元数据遮罩进入路径/限定名，属于可逆身份边界，不直接称虚构位置',
    'existing_test_scope_identity': '合法JSON；返回真实测试路径，超出既有业务Python评价范围',
    'existing_documentation_scope_identity': '合法JSON；返回文档路径，超出既有业务Python评价范围',
    'wrong_class_qualified_name': '合法JSON；同文件同叶名存在，但类限定名前缀不匹配',
    'qualified_name_identity_mismatch': '合法JSON；精确限定名无效，同叶名仅作诊断不追分',
    'unknown_or_malformed_identity': '合法JSON中路径/函数身份无效，现有证据不足以细分',
    'malformed_final_json': '最终响应不是合法JSON',
    'ranked_functions_not_list': '最终JSON中的ranked_functions不是列表',
}


def classify_output_identity(row, job, index, context):
    """Diagnostic-only subtypes. Never unmask or repair the scored prediction."""
    audit = row.get('output_audit', {}); records = []
    if audit.get('raw_final_json_valid') is False:
        records.append({'subtype': 'malformed_final_json'})
    elif audit.get('raw_final_json_valid') is True and audit.get('raw_ranked_functions_list') is False:
        records.append({'subtype': 'ranked_functions_not_list'})
    safe_blocks = [dict(b, end_line=b.get('truncation', {}).get('last_complete_line', b['end_line']))
                   for b in context.get('blocks', [])]
    delivered = row.get('final_http_context_delivered', False)
    for rank, item in enumerate(row.get('raw_predicted_functions', [])[:10], 1):
        slots = row.get('normalized_function_slots', [])
        if rank <= len(slots) and slots[rank - 1] is not None:
            continue
        record = {'rank': rank, 'json_valid': audit.get('raw_final_json_valid'),
                  'diagnostic_only_scoring_unchanged': True}
        if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not isinstance(item.get('qualified_name'), str):
            records.append(dict(record, subtype='unknown_or_malformed_identity')); continue
        path = item['path'].replace('\\', '/')
        while path.startswith('./'):
            path = path[2:]
        qn = item['qualified_name']
        record.update(raw_path=item['path'], raw_qualified_name=qn, path_exists_in_clean_job=path in job.get('paths', []))
        if MASK in path or MASK in qn:
            candidates = []
            for field in ('instance_id', 'base_commit', 'repo'):
                literal = job.get(field)
                if not literal:
                    continue
                candidate_path, candidate_qn = path.replace(MASK, literal), qn.replace(MASK, literal)
                definitions = [d for d in index.get(candidate_path, {}).get('definitions', [])
                               if d.get('kind') == 'function' and d.get('qualified_name') == candidate_qn]
                if candidate_path in job.get('paths', []):
                    candidates.append({'metadata_literal_field': field, 'path': candidate_path,
                                       'qualified_name': candidate_qn, 'canonical_identity_in_base': bool(definitions)})
            canonical = {(c['path'], c['qualified_name']) for c in candidates if c['canonical_identity_in_base']}
            record.update(subtype='metadata_alias_identity_boundary', diagnostic_unmask_candidates=candidates,
                          diagnostic_canonical_identity_count=len(canonical),
                          canonical_path_in_actual_model_context=any(p in context.get('model_context_text', '') for p, _ in canonical),
                          alias_marker_in_actual_model_context=MASK in context.get('model_context_text', ''),
                          explanation='仅离线枚举本题元数据字面量的逆替换；不改原输出、固定槽位或分数。源码SHA有效不证明模型可恢复规范路径。')
        elif path in job.get('paths', []) and set(Path(path).parts) & {'test', 'tests', 'testing', 'doc', 'docs'}:
            is_test = bool(set(Path(path).parts) & {'test', 'tests', 'testing'})
            record.update(subtype='existing_test_scope_identity' if is_test else 'existing_documentation_scope_identity',
                          explanation='路径在本题真实base清单中，但既有评价范围排除此路径；不称不存在或JSON格式错误。')
        else:
            candidates = [d for d in index.get(path, {}).get('definitions', [])
                          if d.get('kind') == 'function' and d.get('qualified_name', '').split('.')[-1] == qn.split('.')[-1]
                          and d.get('qualified_name') != qn]
            evidence = []
            for candidate in candidates:
                parent = candidate['qualified_name'].rsplit('.', 1)[0] if '.' in candidate['qualified_name'] else None
                declarations = [d for d in index.get(path, {}).get('definitions', [])
                                if d.get('kind') == 'class' and d.get('qualified_name') == parent]
                blocks = [b for b in safe_blocks if b.get('path') == path]
                evidence.append({'base_identity': path + '::' + candidate['qualified_name'],
                                 'function_start_line': candidate.get('start_line'), 'function_end_line': candidate.get('end_line'),
                                 'function_full_in_final_context': bool(delivered and B.H.intervals_cover(blocks, candidate['start_line'], candidate['end_line'])),
                                 'class_header_lines': [d.get('def_line', d['start_line']) for d in declarations],
                                 'class_header_in_final_context': (bool(delivered and any(B.H.intervals_cover(blocks, d.get('def_line', d['start_line']), d.get('def_line', d['start_line'])) for d in declarations))
                                                                   if declarations else None)})
            subtype = ('wrong_class_qualified_name' if any(e['class_header_lines'] for e in evidence)
                       else 'qualified_name_identity_mismatch' if evidence else 'unknown_or_malformed_identity')
            record.update(subtype=subtype, same_leaf_base_evidence=evidence,
                          explanation='同叶名候选与所属class声明是否实际送达只作观察证据；不据此重命名、追分或推断模型心理。')
        records.append(record)
    subtypes = sorted({r['subtype'] for r in records})
    aliases = [r for r in records if r['subtype'] == 'metadata_alias_identity_boundary']
    return {'output_identity_subtypes': subtypes, 'output_identity_diagnostics': records,
            'identity_diagnostic_json_valid': audit.get('raw_final_json_valid'),
            'metadata_alias_identity_boundary': bool(aliases),
            'diagnostic_unmask_unique_base_identity': bool(aliases) and all(r['diagnostic_canonical_identity_count'] == 1 for r in aliases),
            'source_sha_proves_canonical_paths_recoverable': False if aliases else None}


def path_alias_and_planner_audit(row, job, folder, context, selection):
    """Observe path aliases in upstream draws as well as final identities."""
    literals = {k: job.get(k) for k in ('instance_id', 'base_commit', 'repo') if job.get(k)}
    paths = set(job.get('paths', []))
    collisions = sorted(p for p in paths if any(v in p for v in literals.values()))
    aliases = []
    for number, draw in enumerate(selection.get('draws', [])):
        for rank, path in enumerate(draw, 1):
            if not isinstance(path, str) or MASK not in path:
                continue
            candidates = sorted({path.replace(MASK, value) for value in literals.values()
                                 if path.replace(MASK, value) in paths})
            aliases.append({'file_draw_index': number, 'rank': rank, 'returned_path': path,
                            'returned_path_in_canonical_allowlist': path in paths,
                            'diagnostic_inverse_base_paths': candidates})
    requested_inventory_alias = False
    for p in sorted((Path(folder) / 'calls').glob('*_file_draw_*/request.json')):
        request = C.load(p, {}).get('request', {})
        message = '\n'.join(m.get('content', '') for m in request.get('messages', []))
        if any(masked(path, job) != path and masked(path, job) in message for path in collisions):
            requested_inventory_alias = True; break
    final_alias = any(MASK in json.dumps(item, ensure_ascii=False) for item in
                      row.get('raw_predicted_functions', []) + row.get('raw_predicted_files', []))
    boundary = bool(collisions and (aliases or final_alias))
    result = {'metadata_path_alias_boundary': boundary, 'metadata_literal_path_collision_count': len(collisions),
              'metadata_literal_path_collision_examples': collisions[:20],
              'metadata_alias_in_file_draws': bool(aliases), 'metadata_alias_in_final_identity': final_alias,
              'metadata_alias_inventory_delivery_verified': requested_inventory_alias,
              'metadata_path_alias_evidence': aliases,
              'diagnostic_draw_aliases_uniquely_reversible': bool(aliases) and all(len(a['diagnostic_inverse_base_paths']) == 1 for a in aliases),
              'source_sha_proves_canonical_paths_recoverable': False if boundary else row.get('source_sha_proves_canonical_paths_recoverable'),
              'canonical_selected_file_count': len(selection.get('ranked_edit_files', [])),
              'planner_errors': context.get('planner_errors', []), 'planner_json_syntax_valid': None,
              'planner_error_subtype': None, 'collected_query_count': len(context.get('queries', [])),
              'collected_evidence_file_count': len(context.get('collected_evidence_files', []))}
    files = sorted((Path(folder) / 'calls').glob('*_query_planning/result.json'))
    if len(files) == 1:
        content = C.load(files[0], {}).get('content', '')
        try:
            value = json.loads(content); result['planner_json_syntax_valid'] = True
            if not isinstance(value, dict) or 'queries' not in value:
                result['planner_error_subtype'] = 'queries_field_missing'
            elif not isinstance(value['queries'], list):
                result['planner_error_subtype'] = 'queries_field_not_list'
            elif result['planner_errors']:
                result['planner_error_subtype'] = 'query_schema_or_fixed_string_error'
        except (ValueError, TypeError):
            result.update(planner_json_syntax_valid=False, planner_error_subtype='json_syntax_invalid')
    return result


def owner_context_audit(row, targets, index, context):
    evidence = []
    blocks = [dict(b, end_line=b.get('truncation', {}).get('last_complete_line', b['end_line']))
              for b in context.get('blocks', [])]
    for target in targets:
        wrong_owner = [p for p in target.get('same_leaf_different_identity_top10', []) if p.get('same_path')]
        path, name = target['gold_identity'].split('::', 1)
        if not wrong_owner or '.' not in name:
            continue
        owner = name.rsplit('.', 1)[0]
        declarations = [d for d in index.get(path, {}).get('definitions', [])
                        if d.get('qualified_name') == owner and d.get('kind') in ('function', 'class')]
        same_file = [b for b in blocks if b.get('path') == path]
        for definition in declarations:
            line = definition.get('def_line', definition['start_line'])
            visible = bool(row['final_http_context_delivered'] and B.H.intervals_cover(same_file, line, line))
            evidence.append({'gold_identity': target['gold_identity'], 'owner_identity': path + '::' + owner,
                             'owner_kind': definition['kind'], 'owner_header_line': line,
                             'owner_header_in_final_context': visible,
                             'target_body_full_in_final_context': target['final_delivered_any_definition_full'],
                             'same_leaf_different_owner_predictions': wrong_owner,
                             'identity_context_gap_observed': target['final_delivered_any_definition_full'] and not visible})
    return {'owner_identity_context_gap': any(e['identity_context_gap_observed'] for e in evidence),
            'owner_identity_context_diagnostics': evidence}


def output(name, value):
    root = C.ROOT / 'reports' / REPORT
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise PermissionError('Report output escaped its new directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.json':
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    elif path.suffix == '.csv':
        fields = list(dict.fromkeys(k for row in value for k in row)) or ['status']
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()} for row in value)
    else:
        path.write_text(value)
    return path


def masked(text, job):
    literals = sorted({job[k] for k in ('instance_id', 'base_commit', 'repo') if job.get(k)}, key=lambda v: (-len(v), v))
    return re.sub('|'.join(re.escape(v) for v in literals), MASK, text) if literals else text


def full_line_prefix(source, prefix, start):
    """Last fully represented original line; a token-cut half-line is excluded."""
    cursor = 0; last = start - 1
    for line in source.splitlines(keepends=True):
        if cursor + len(line) > len(prefix):
            break
        cursor += len(line); last += 1
    return last


def verify_prefix_context(job, index, context, qualification=None):
    """Verify exact raw base prefixes, then expose only full lines to old helpers.

    Mutation is in memory only. The saved JSON/request remains untouched, and
    delivery is checked against raw rendered blocks before this function runs.
    """
    root = Path(job['snapshot']).resolve(); errors = []; audit = []; selected = []
    selected_paths = context.get('ranked_edit_files', [])
    raw_hashes = (qualification or {}).get('snapshot_sha256', {})
    for pos, block in enumerate(context.get('blocks', [])):
        row = {'block_index': pos, 'path': block.get('path'), 'source_valid': False}
        try:
            path = block['path']; relative = Path(path)
            if relative.is_absolute() or '..' in relative.parts or '\\' in path:
                raise ValueError('unsafe_source_path')
            actual = (root / relative).resolve()
            if not actual.is_relative_to(root):
                raise ValueError('source_outside_snapshot')
            raw = actual.read_bytes()
            pinned_raw = raw_hashes.get(str(Path(job['snapshot']) / path), raw_hashes.get(str(actual)))
            if pinned_raw is not None and B.H.digest(raw) != pinned_raw:
                raise ValueError('materialized_base_raw_sha_mismatch')
            if path.endswith('.py'):
                text = B.H.decoded(raw)
                if path not in index or index[path].get('sha256') != B.H.digest(text):
                    raise ValueError('base_text_index_sha_mismatch')
            else:
                if pinned_raw is None:
                    raise ValueError('non_python_materialized_raw_sha_unavailable')
                text = raw.decode('utf-16') if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else raw.decode('utf-8-sig')
            lines = text.splitlines(keepends=True); start = block['start_line']
            if not 1 <= start <= max(1, len(lines)):
                raise ValueError('invalid_prefix_start_line')
            tail = ''.join(lines[start - 1:]); retained = block.get('text', '')
            if not tail.startswith(retained) or B.H.digest(retained) != block.get('sha256'):
                raise ValueError('context_not_exact_base_prefix')
            if block.get('complete_file') and not (start == 1 and retained == text):
                raise ValueError('complete_file_flag_does_not_cover_base_file')
            last = full_line_prefix(tail, retained, start)
            truncation = block.get('truncation', {})
            claimed_last = block.get('last_complete_line', truncation.get('last_complete_line'))
            if claimed_last is not None and claimed_last != last:
                raise ValueError('last_complete_line_mismatch')
            for key, actual_value in [('retained_characters', len(retained)), ('retained_utf8_bytes', len(retained.encode())),
                                      ('prefix_sha256', B.H.digest(retained))]:
                if key in truncation and truncation[key] != actual_value:
                    raise ValueError('truncation_' + key + '_mismatch')
            original_end = block['end_line']
            row.update(source_valid=True, base_raw_sha256=B.H.digest(raw), base_text_sha256=B.H.digest(text),
                       block_sha256=block['sha256'], start_line=start, reported_end_line=original_end,
                       last_complete_line=last, retained_characters=len(retained),
                       partial_last_line=last < original_end)
            block['_reported_end_line'] = original_end
            block['_raw_complete_file'] = bool(block.get('complete_file'))
            block['end_line'] = last
            if path in selected_paths:
                selected.append(path)
        except (ValueError, OSError, UnicodeError, SyntaxError, KeyError, TypeError) as error:
            row['error'] = str(error); errors.append(str(block.get('path')) + ':' + str(error))
        audit.append(row)
    # The legacy diagnostic partitions by origin position. Here this prefix list
    # is only an internal partition, not a claim that a truncated file is whole.
    context['loaded_whole_files'] = selected
    return {'base_context_verified': not errors, 'context_integrity_errors': errors,
            'verified_block_count': sum(a['source_valid'] for a in audit), 'blocks': audit}


def final_delivery(folder, context, receipts, *, iid, expected_run_id, job):
    raw = '\n\n'.join(b.get('header', '') + b.get('text', '') for b in context.get('blocks', []))
    rendered = masked(raw, job)
    invalid = (context.get('model_context_text') != rendered or
               context.get('model_context_sha256') != B.H.digest(rendered))
    paths = sorted((Path(folder) / 'calls').glob('*_function_localization/request.json'))
    proof = {'final_request_count': len(paths), 'source_block_count': len(context.get('blocks', [])),
             'nonempty_source_block_count': sum(bool(b.get('text')) for b in context.get('blocks', [])),
             'final_request_path': str(paths[0]) if len(paths) == 1 else None,
             'request_sha256': None, 'context_body_sha256': B.H.digest(rendered),
             'raw_context_body_sha256': B.H.digest(raw), 'metadata_mask_transform_verified': not invalid,
             'final_http_context_delivered': False, 'successful_request_ids': [], 'delivery_error': None}
    if invalid or any(B.H.digest(b.get('text', '')) != b.get('sha256') for b in context.get('blocks', [])):
        proof['delivery_error'] = 'raw_prefix_or_metadata_mask_sha_mismatch'; return proof
    if len(paths) != 1:
        proof['delivery_error'] = 'missing_or_multiple_final_requests'; return proof
    saved = B.C.load(paths[0]); request = saved.get('request', {})
    if B.H.digest(json.dumps(request, sort_keys=True, ensure_ascii=False)) != saved.get('sha256'):
        proof['delivery_error'] = 'final_request_sha_mismatch'; return proof
    wanted = '\n<context>\n' + rendered + '\n</context>'
    if not any(wanted in m.get('content', '') for m in request.get('messages', [])):
        proof['delivery_error'] = 'final_payload_not_exact_masked_context'; return proof
    sequence = int(paths[0].parent.name.split('_', 1)[0])
    good = [r for r in receipts if r.get('stage') == 'function_localization' and r.get('sequence') == sequence
            and r.get('http_status') == 200 and r.get('usage') and r.get('instance_id') == iid
            and r.get('method') == 'D-SIMPLE' and r.get('run_id') == expected_run_id
            and r.get('request_sha256') == saved['sha256'] and r.get('finish_reason') == 'stop']
    proof.update(request_sha256=saved['sha256'], successful_request_ids=sorted(r['request_id'] for r in good),
                 final_http_context_delivered=bool(good), delivery_error=None if good else 'no_successful_matching_http_receipt')
    return proof


def correct_prefix_diagnostics(rows, targets, contexts):
    """Replace only mechanism labels; scores/slots remain the frozen evaluator's."""
    for target in targets:
        context = contexts[target['instance_id']]
        blocks = [b for b in context.get('blocks', []) if b.get('path') == target['gold_path']]
        selected = target['gold_path'] in context.get('ranked_edit_files', [])
        target['selected_file_prefix_loaded'] = bool(selected and blocks)
        target['loaded_whole_file'] = any(b.get('_raw_complete_file', b.get('complete_file')) for b in blocks) and selected
        target['five_file_limit'] = False
        target['labels'] = [x for x in target['labels'] if x not in ('selected_five_file_limit', 'gold_file_loaded_whole')]
        if target['loaded_whole_file']:
            target['labels'].append('gold_file_loaded_whole')
        target['raw_prefix_then_metadata_mask_delivery'] = next(
            bool(r['base_context_verified'] and r['final_http_context_delivered'])
            for r in rows if r['instance_id'] == target['instance_id'])
        truncated = any(b.get('truncation', {}).get('original_body_tokens', 0) >
                        b.get('truncation', {}).get('retained_body_tokens', 0) for b in blocks)
        cause = target['target_primary_cause']
        if truncated and not target['hit_at_5'] and target['final_delivered_any_definition_partial'] and not target['final_delivered_any_definition_full']:
            cause = 'selected_file_60k_prefix_truncation' if selected else 'evidence_span_12k_prefix_truncation'
        elif truncated and not target['hit_at_5'] and not target['final_delivered_any_definition_full'] and selected and blocks:
            if cause not in ('source_or_truth_integrity_unproven', 'source_not_delivered_to_final', 'invalid_final_output'):
                cause = 'selected_file_60k_prefix_truncation'
        elif not target['hit_at_5'] and selected and not blocks and target.get('overflow_record'):
            cause = 'selected_context_80k_skip'
        target['target_primary_cause'] = cause
        target['target_primary_cause_zh'] = CAUSES.get(cause, cause)
    by = collections.defaultdict(list)
    for target in targets:
        by[target['instance_id']].append(target)
    for row in rows:
        if row['status_family'] == 'complete' and row['function_scorable'] and row['function_hit_5'] == 0:
            row['failure_category'] = ';'.join(sorted({t['target_primary_cause'] for t in by[row['instance_id']] if not t['hit_at_5']}))


def collect_new(manifest, budget):
    adapted = copy.deepcopy(manifest); contexts = {}; jobs = {}; qualifications = {}; indexes = {}
    for rec in adapted['records']:
        rec['origin'] = B.NEW_ORIGIN
        jobs[rec['instance_id']] = B.C.load(rec['job'])
        qualifications[rec['instance_id']] = C.load(rec.get('preparation_receipt', C.PRIVATE / 'preparation' / (rec['instance_id'] + '.json')), {})
    def verify(job, index, context, qualification=None):
        indexes[job['instance_id']] = index
        result = verify_prefix_context(job, index, context, qualifications[job['instance_id']])
        contexts[job['instance_id']] = context
        return result
    def delivery(folder, context, receipts, *, iid, expected_run_id):
        return final_delivery(folder, context, receipts, iid=iid, expected_run_id=expected_run_id, job=jobs[iid] or {})
    with patch.object(B.H, 'verify_base_context', verify), patch.object(B.H, 'final_delivery', delivery):
        rows, targets, attempts = B.collect(adapted, budget=budget)
    for row in rows:
        contexts.setdefault(row['instance_id'], C.load(Path(row['context_path']), {'blocks': []}))
    correct_prefix_diagnostics(rows, targets, contexts)
    for row in rows:
        job = jobs[row['instance_id']] or {}; context = contexts[row['instance_id']]
        row.update(classify_output_identity(row, job, indexes.get(row['instance_id'], {}), context))
        row['file_prediction_scope_notes'] = []
        for rank, value in enumerate(row['raw_predicted_files'][:10], 1):
            path = value.replace('\\', '/') if isinstance(value, str) else None
            while path and path.startswith('./'):
                path = path[2:]
            label = ('strict_scored_identity' if rank <= len(row['normalized_file_slots']) and row['normalized_file_slots'][rank - 1]
                     else 'existing_path_outside_business_python_evaluation_scope' if path in job.get('paths', [])
                     else 'unknown_or_malformed_path')
            row['file_prediction_scope_notes'].append({'rank': rank, 'raw_path': value, 'scope_status': label})
        selection = C.load(Path(row['result_path']).parent / 'file_selection.json', {})
        inventory = C.load(Path(row['result_path']).parent / 'inventory.json', {})
        row.update(path_alias_and_planner_audit(row, job, Path(row['result_path']).parent, context, selection))
        row.update(owner_context_audit(row, [t for t in targets if t['instance_id'] == row['instance_id']],
                                       indexes.get(row['instance_id'], {}), context))
        selected = selection.get('ranked_edit_files', context.get('ranked_edit_files', []))
        row['file_gold_source_facts'] = []
        for path in row['gold_files']:
            blocks = [b for b in context.get('blocks', []) if b.get('path') == path]
            row['file_gold_source_facts'].append({'path': path, 'in_displayed_inventory': path in inventory.get('paths', []),
                'selected_rank': selected.index(path) + 1 if path in selected else None,
                'actual_context_block_count': len(blocks), 'raw_complete_file_in_context': any(b.get('_raw_complete_file') for b in blocks),
                'block_ranges_complete_lines': [[b['start_line'], b['end_line']] for b in blocks],
                'skip_records': [v for v in context.get('skipped_files', []) if v.get('path') == path],
                'final_http_context_delivered': row['final_http_context_delivered']})
    return rows, targets, attempts


def scope_sets(old_rows):
    wrong = {r['instance_id'] for r in old_rows if r['status_family'] == 'complete' and
             ((r['function_scorable'] and r['function_hit_5'] == 0) or (r['file_scorable'] and r['file_hit_5'] == 0))}
    unfinished = {r['instance_id'] for r in old_rows if r['status_family'] != 'complete'}
    return wrong, unfinished


def merge_rows(old_rows, new_rows, selected_ids):
    old = {r['instance_id']: r for r in old_rows}; new = {r['instance_id']: r for r in new_rows}
    if len(old) != len(old_rows) or len(new) != len(new_rows) or set(new) != set(selected_ids) or not set(new) <= set(old):
        raise RuntimeError('IID overlay set mismatch/duplicate')
    merged = []
    for prior in old_rows:
        iid = prior['instance_id']; row = copy.deepcopy(new[iid] if iid in new else prior)
        row['original_origin'] = prior['origin']
        row['protocol_group'] = 'paper_params_retest93' if iid in new else 'old_correct_reuse172'
        row['old_result_path'] = prior['result_path']
        row['old_status'] = prior['status']
        merged.append(row)
    return merged


def finance_summary(new_attempts, ledger, baseline):
    unique = B.deduplicate_receipts(new_attempts)
    before = baseline.get('ledger', baseline).get('attempts', {})
    entries = ledger.get('attempts', {})
    if any(entries.get(rid) != value for rid, value in before.items()):
        raise RuntimeError('The immutable pre-run ledger baseline changed')
    ids = {a['request_id'] for a in unique}
    if ids & set(before):
        raise RuntimeError('New protocol replayed a baseline paid request')
    for a in unique:
        entry = entries.get(a['request_id'])
        if not entry or entry.get('key') != 'D-SIMPLE|' + a['instance_id'] or (a.get('usage') and entry.get('usage') != a['usage']):
            raise RuntimeError('New receipt/shared-ledger identity or usage mismatch')
    unlinked = set(entries) - set(before) - ids
    unknown = sum(a['api_cost_usd_usage_estimate'] is None for a in unique)
    return {'baseline_attempts': len(before), 'baseline_entries_preserved': True, 'current_shared_attempts': len(entries),
            'new_unique_http_attempts': len(unique), 'duplicate_request_ids_removed': len(new_attempts) - len(unique),
            'usage_cost_usd': None if unknown or unlinked else sum(a['api_cost_usd_usage_estimate'] for a in unique),
            'known_usage_cost_usd': sum(a['api_cost_usd_usage_estimate'] or 0 for a in unique),
            'unknown_cost_attempts': unknown, 'unlinked_new_ledger_request_ids': sorted(unlinked),
            'new_charged_upper_usd': sum(entries[rid]['charged_upper_usd'] for rid in set(entries) - set(before)),
            'no_active_total_or_per_case_or_cumulative_token_cap': True,
            'historical_stage_cap_usd_metadata': ledger.get('stage_cap_usd'),
            'usage_estimate_is_account_invoice': False, 'report_created_ledger': False}


def group_summaries(merged, new, wrong, unfinished, repeats=10000):
    groups = [('合并265_旧正确复用加定向重测补全', merged), ('本轮93', new),
              ('旧失败28_新结果', [r for r in new if r['instance_id'] in wrong]),
              ('未完成65_新结果', [r for r in new if r['instance_id'] in unfinished]),
              ('旧正确172_原结果', [r for r in merged if r['protocol_group'] == 'old_correct_reuse172'])]
    return [B.summarize(rows, name + '/' + population, population=population, ci_repeats=repeats)
            for name, rows in groups for population in ('allocation', 'executed')]


def paired_table(old, new, ids):
    oldby = {r['instance_id']: r for r in old}; newby = {r['instance_id']: r for r in new}
    out = []
    for iid in sorted(ids):
        a, b = oldby[iid], newby[iid]
        row = {'instance_id': iid, 'repo': a['repo'], 'old_status': a['status'], 'new_status': b['status'],
               'function_scorable': a['function_scorable'], 'old_result_path': a['result_path'], 'new_result_path': b['result_path']}
        for prefix in ('file', 'function'):
            for metric in ('hit_1', 'hit_3', 'hit_5', 'precision_5', 'recall_5', 'f1_5', 'all_coverage_5', 'mrr_10'):
                key = prefix + '_' + metric; x, y = a[key], b[key]
                row['old_' + key], row['new_' + key] = x, y
                row['delta_' + key] = y - x if x is not None and y is not None else None
        out.append(row)
    return out


def paired_summary(paired, repeats=10000):
    out = []
    for prefix in ('file', 'function'):
        for metric in ('hit_1', 'hit_3', 'hit_5', 'precision_5', 'recall_5', 'f1_5', 'all_coverage_5', 'mrr_10'):
            key = prefix + '_' + metric
            part = [r for r in paired if r['old_' + key] is not None and r['new_' + key] is not None]
            delta = [r['delta_' + key] for r in part]
            out.append({'metric': key, 'paired_n': len(part),
                        'old_mean': B.mean([r['old_' + key] for r in part]),
                        'new_mean': B.mean([r['new_' + key] for r in part]), 'new_minus_old': B.mean(delta),
                        'delta_ci95': B.ci(delta, [r['repo'] for r in part], repeats=repeats),
                        'new_better_n': sum(v > 0 for v in delta), 'new_worse_n': sum(v < 0 for v in delta),
                        'tie_n': sum(v == 0 for v in delta), 'selected_on_old_failure': True})
    return out


def failure_kind(row):
    if row['status_family'] != 'complete':
        return 'NOT_RUN' if row['status_family'] == 'NOT_RUN' else 'engineering_failure'
    if row['function_scorable'] and row['function_hit_5'] == 0:
        return row['failure_category']
    if row['file_scorable'] and row['file_hit_5'] == 0:
        slots = row['normalized_file_slots']; targets = row['gold_files']
        return 'file_rank_cutoff_at_5' if any(x in targets for x in slots[5:10] if x) else 'file_selection_miss'
    if row['function_scorable'] and row['function_hit_5'] == 1 and row['function_recall_5'] < 1:
        return ('retained_old_hit5_recall_gap' if row.get('protocol_group') == 'old_correct_reuse172'
                else 'hit5_with_recall_gap')
    return None


def failure_report(rows, targets, jobs):
    """Categories first, then every affected IID; observable automatic analysis."""
    by = collections.defaultdict(list)
    for target in targets:
        by[target['instance_id']].append(target)
    affected = [(failure_kind(row), row) for row in rows if failure_kind(row)]
    counts = collections.Counter(kind for kind, _ in affected)
    lines = ['# 定位失败分析报告：先分类，再逐题', '',
             '本报告覆盖合并265题中所有函数Top5未命中、文件Top5未命中、已命中但函数召回不足，以及未完成/工程失败。函数NA不硬判函数错误；文件仍可独立评价。每题只进入一个主分类，多个目标的原因保留组合类与逐目标明细。以下说明为自动证据归纳，不是模型内部思维解释，也不替代人工语义复核。', '',
             '| 主分类（互斥按题） | 中文含义 | 题数 |', '|---|---|---:|']
    for kind in sorted(counts):
        label = '；'.join(CAUSES.get(x, x) for x in kind.split(';'))
        lines.append(f'| {kind} | {label} | {counts[kind]} |')
    strict_or_file = [r for _, r in affected if r['status_family'] == 'complete' and
                      ((r['function_scorable'] and r['function_hit_5'] == 0) or (r['file_scorable'] and r['file_hit_5'] == 0))]
    invalid_rows = [r for kind, r in affected if 'invalid_final_output' in kind.split(';')]
    subtype_counts = collections.Counter(subtype for r in invalid_rows for subtype in set(r.get('output_identity_subtypes', [])))
    lines += ['', f'完全函数未命中或文件独有未命中并集为{len(strict_or_file)}题。文件与函数同时未命中时只计一题；已Hit5但Recall5不足的题单列，不混称完全没定位到。来源为旧正确172或本轮93，均按最终采用结果列示。', '',
              f'其中invalid_final_output主类共{len(invalid_rows)}题，以下仅为同一批题的子类型，不额外加入上述总数。JSON语法有效与精确函数身份有效是不同检查；以下不因诊断逆替换而改变严格分数。', '',
              '| 输出身份子类型（仅主类invalid_final_output，按题） | 解释 | 题数 |', '|---|---|---:|']
    for subtype in sorted(subtype_counts):
        lines.append(f'| {subtype} | {IDENTITY_SUBTYPES.get(subtype, subtype)} | {subtype_counts[subtype]} |')
    lines += ['', '**源码真实性与身份可恢复性分开。** 93题base SHA、脱敏转换和成功HTTP送达验证只证明已发送文本可追溯，不证明遮罩后的规范文件路径一定可被模型恢复。若`[BENCHMARK_METADATA]`进入路径，原输出仍按严格path::QN记分；离线只用本题已知元数据枚举逆替换，记录能否恢复真实base身份，不把这类输入/输出身份边界直接称作模型虚构位置。错误class前缀与真实测试路径范围外也分别说明。', '']
    alias_rows = [r for r in rows if r.get('metadata_path_alias_boundary')]
    owner_rows = [r for r in rows if r.get('owner_identity_context_gap')]
    planner_rows = [r for r in rows if r.get('planner_errors')]
    lines += ['| 额外阶段诊断（可重叠，不增加主类题数） | 题数 | issue |', '|---|---:|---|',
              '| 元数据字面量与真实源码路径相撞 | ' + str(len(alias_rows)) + ' | ' + ', '.join(r['instance_id'] for r in alias_rows) + ' |',
              '| 同名目标体可见但外层owner声明未送达，输出另一owner | ' + str(len(owner_rows)) + ' | ' + ', '.join(r['instance_id'] for r in owner_rows) + ' |',
              '| 检索规划解析错误 | ' + str(len(planner_rows)) + ' | ' + ', '.join(r['instance_id'] for r in planner_rows) + ' |', '',
              '路径遮罩也可发生在上游文件选择：模型返回遮罩路径后，原canonical路径allowlist会拒绝它。这证明存在身份校验边界，不证明模型已找到实际gold，也不能把同题的inventory遗漏等联合缺口全部归因于遮罩。检索规划错误按真实响应区分JSON语法与schema错误，保存错误不自动修复或重试；规划失败不等同于最终函数未命中。规划是JSON请求加程序字符串检索，不是API原生function-calling。', '']
    index = []
    for kind in sorted(counts):
        lines += ['## ' + '；'.join(CAUSES.get(x, x) for x in kind.split(';')), '']
        for _, row in sorted((x for x in affected if x[0] == kind), key=lambda x: x[1]['instance_id']):
            iid = row['instance_id']; job = jobs.get(iid) or {}; issue = ' '.join(job.get('problem_statement', '').split())[:420]
            index.append({'instance_id': iid, 'primary_category': kind, 'protocol_group': row['protocol_group'],
                          'status': row['status'], 'function_hit_5': row['function_hit_5'], 'file_hit_5': row['file_hit_5'],
                          'function_recall_5': row['function_recall_5'], 'issue_excerpt': issue,
                          'result_path': row['result_path'], 'context_path': row['context_path'],
                          'output_identity_subtypes': row.get('output_identity_subtypes', []),
                          'identity_diagnostic_json_valid': row.get('identity_diagnostic_json_valid'),
                          'metadata_alias_identity_boundary': row.get('metadata_alias_identity_boundary', False),
                          'diagnostic_unmask_unique_base_identity': row.get('diagnostic_unmask_unique_base_identity', False),
                          'metadata_path_alias_boundary': row.get('metadata_path_alias_boundary', False),
                          'owner_identity_context_gap': row.get('owner_identity_context_gap', False),
                          'planner_errors': row.get('planner_errors', []),
                          'planner_error_subtype': row.get('planner_error_subtype')})
            lines += ['### ' + iid, '', '**Issue原文摘要（自动截取）**：' + (issue or '缺失，见job证据。'), '',
                      f"采用来源={row['protocol_group']}；状态={row['status']}；函数评价={row['function_evaluation_status']}。文件Hit5={row['file_hit_5']}；函数Hit5={row['function_hit_5']}；函数Recall5={row['function_recall_5']}。", '',
                      '**自动中文证据分析**：' + '；'.join(CAUSES.get(x, x) for x in kind.split(';')) + '。',
                      '输出身份子类型=' + '；'.join(IDENTITY_SUBTYPES.get(x, x) for x in row.get('output_identity_subtypes', [])),
                      '输出身份附证（仅诊断，不改评分）=' + json.dumps(row.get('output_identity_diagnostics', []), ensure_ascii=False),
                      '上游/最终路径遮罩边界=' + json.dumps({'observed': row.get('metadata_path_alias_boundary', False),
                          'inventory_delivery_verified': row.get('metadata_alias_inventory_delivery_verified'),
                          'canonical_selected_files': row.get('canonical_selected_file_count'),
                          'file_draw_alias_evidence': row.get('metadata_path_alias_evidence', [])}, ensure_ascii=False),
                      '外层owner上下文附证=' + json.dumps(row.get('owner_identity_context_diagnostics', []), ensure_ascii=False),
                      '规划解析与真实检索=' + json.dumps({'planner_errors': row.get('planner_errors', []),
                          'json_syntax_valid': row.get('planner_json_syntax_valid'), 'error_subtype': row.get('planner_error_subtype'),
                          'collected_queries': row.get('collected_query_count'),
                          'collected_evidence_files': row.get('collected_evidence_file_count')}, ensure_ascii=False),
                      '最终文件原排名=' + json.dumps(row['raw_predicted_files'], ensure_ascii=False),
                      '最终函数原排名=' + json.dumps(row['raw_predicted_functions'][:10], ensure_ascii=False),
                      '严格函数槽位=' + json.dumps(row['normalized_function_slots'], ensure_ascii=False),
                      f"base源码核验={row['base_context_verified']}；最终成功HTTP上下文送达={row['final_http_context_delivered']}。", '',
                      '| 既有函数目标 | Top10原rank | inventory/选择rank | 整定义完整/部分送达 | 实际修改base体完整覆盖已核 | 证据原因 |',
                      '|---|---:|---|---|---|---|']
            for target in by[iid]:
                lines.append(f"| {target['gold_identity']} | {target['gold_rank_top10']} | {target['in_displayed_inventory']}/{target['selected_file_rank']} | {target['final_delivered_any_definition_full']}/{target['final_delivered_any_definition_partial']} | {target['actual_modified_implementation_verified']} | {target['target_primary_cause_zh']} |")
                if target.get('same_leaf_different_identity_top10'):
                    lines += ['', '同叶名不同path/QN附证=' + json.dumps(target['same_leaf_different_identity_top10'], ensure_ascii=False)]
            lines += ['', '文件真值=' + json.dumps(row['gold_files'], ensure_ascii=False),
                      '文件获取证据=' + json.dumps(row.get('file_gold_source_facts', []), ensure_ascii=False),
                      '文件预测范围审计=' + json.dumps(row.get('file_prediction_scope_notes', []), ensure_ascii=False),
                      '最终HTTP证据=' + json.dumps(row['source_delivery_proof'], ensure_ascii=False),
                      '来源错误=' + json.dumps(row['source_integrity_errors'], ensure_ascii=False),
                      '证据：' + '；'.join(f'[{label}]({row[field]})' for label, field in [('结果', 'result_path'), ('context', 'context_path'), ('R2金标', 'gold_v2_path')]), '']
    lines += ['## NA及解释边界', '',
              '函数COMPLETE_EMPTY题数=' + str(sum(r['function_evaluation_status'] == 'COMPLETE_EMPTY' for r in rows)) + '；其文件指标继续保留，NA原因见原30题独立核验。',
              '同QN多span共享身份；同名任一span可见不等于真实修改实现已送达。新源码前缀按基准元数据脱敏后交付；最后半行不算完整覆盖。严格JSON合法空列表、错误QN、排名截断与源码获取缺口分别解释，不做叶名/祖先追分。',
              '本轮同时改变文件/规划输出限额、提示词/默认采样、可读取文本与证据范围、装箱规则，并重新抽样。因此旧题恢复不能只归因于60K截断或取消五文件限制；剩余未命中描述排除已知旧上下文偏差后的可观测失败，不足以证明模型本身无法完成该题。']
    return '\n'.join(lines) + '\n', [{'category': k, 'count': counts[k]} for k in sorted(counts)], index


def metric_overview(summaries, finance, paired_stats=()):
    pct = B.pct
    lines = ['# 合并265题：旧正确复用＋论文参数定向重测/补全', '',
             '主表无条件采用新93题结果（旧失败28＋未完成65），其余旧正确172题保留原结果，即使新结果变差也不回选旧结果。此表混合两种协议，并且重测队列由旧结果筛选；不是265题全量论文参数成绩，不代表独立泛化验证，不能将改善全部归因为参数变动。', '',
             '新条件共同调整文件/规划输出限额、提示词/默认采样、文本与证据范围、装箱及新抽样；28题配对反映这整套条件的结果变化，无法单独归因于60K前缀或取消五文件上限。剩余未命中只按实际来源与输出证据解释，不等同于模型能力不可能。', '',
             '保留函数Top10扩展与非思考DeepSeek，未运行补丁生成/官方harness；不是论文修复率。主表函数分母完整非空R2目标、文件分母独立；严格path::QN、无效槽不压缩、P@k除k。', '',
             '| 范围/人口 | 完成/分配 | 文件/函数分母 | 文件Hit1/3/5 | 函数Hit1/3/5 | P5/R5/F1/AllCoverage5/MRR10 |', '|---|---:|---:|---|---|---|']
    for s in summaries:
        lines.append(f"| {s['scope']} | {s['complete_n']}/{s['allocated_n']} | {s['file_denominator']}/{s['function_denominator']} | "
                     + '/'.join(pct(s['file_hit_' + str(k)]) for k in (1, 3, 5)) + ' | '
                     + '/'.join(pct(s['function_hit_' + str(k)]) for k in (1, 3, 5)) + ' | '
                     + '/'.join(pct(s['function_' + k]) for k in ('precision_5', 'recall_5', 'f1_5', 'all_coverage_5', 'mrr_10')) + ' |')
    lines += ['', '| 固定分配组 | 函数Hit5 count/N | 95% issue CI | 95% repo-cluster CI |', '|---|---:|---|---|']
    for s in summaries:
        if s['population'] != 'allocation':
            continue
        interval = s['function_hit_5_ci95']; fmt = lambda k: '[' + ', '.join(pct(x) for x in interval[k]) + ']'
        lines.append(f"| {s['scope']} | {s['function_hit_5_count']}/{s['function_denominator']} | " + fmt('issue_bootstrap95') + ' | ' + fmt('repo_cluster_bootstrap95') + ' |')
    lines += ['', '所有k=1/3/5/10文件与函数指标和两种95%CI见method_summary.csv，bootstrap重复10,000次、seed=20261022。未运行指标逐题为NA；allocation有未运行时仅是完成信用下界，executed保留真实执行失败。', '',
              '| 旧失败28题中的同题配对 | N | 旧值 | 新值 | 新减旧（pp） | 95% issue / repo-cluster 差值CI（pp） |',
              '|---|---:|---:|---:|---:|---|']
    for item in paired_stats:
        if item['metric'] not in ('file_hit_5', 'function_hit_5', 'function_recall_5', 'function_mrr_10'):
            continue
        interval = item['delta_ci95']
        fmt = lambda key: '[' + ', '.join('NA' if x is None else f'{100*x:.2f}' for x in interval[key]) + ']'
        lines.append(f"| {item['metric']} | {item['paired_n']} | {pct(item['old_mean'])} | {pct(item['new_mean'])} | "
                     + ('NA' if item['new_minus_old'] is None else f"{100*item['new_minus_old']:.2f}")
                     + ' | ' + fmt('issue_bootstrap95') + ' / ' + fmt('repo_cluster_bootstrap95') + ' |')
    lines += ['',
              f"新93题唯一HTTP attempts={finance['new_unique_http_attempts']}；usage美元估算=${B.num(finance['usage_cost_usd'])}。旧2613基线逐条保留，新费用单列，非账户逐笔账单。", '',
              '旧28配对只描述原失败题的变化，存在按旧结果选样本的偏倚；old-correct172、原21个Hit5已中但召回不足题继续保留原预测。完整逐题失败分类见定位失败分析报告.md。']
    lines += ['', '源码prefix/SHA、脱敏转换及HTTP送达核验不等于规范路径可恢复性核验。本轮instructlab与Spack出现基准元数据字面量恰好嵌入真实路径的边界，分别影响最终身份输出或上游文件选择；只作诊断逆替换，不改变严格分数，也不直接称模型虚构路径。错误class前缀、测试路径范围外及外层owner声明缺口另列。']
    return '\n'.join(lines) + '\n'


def resource_report(rows, finance):
    parts = [('all_allocated', rows), ('complete', [r for r in rows if r['status_family'] == 'complete']),
             ('failed_executed', [r for r in rows if r['execution_attempted'] and r['status_family'] != 'complete'])]
    stats = []
    lines = ['# 本轮93题资源消耗', '',
             '只统计新协议93题，原172复用不计新增请求；旧16个成功partial也不重放，本轮所有模型步骤重新请求。tokens按usage、费用按缓存及逐请求峰闲价格估算美元，非账户账单。wall为run_one内实际测量，含网络等待、不含队列/CPU准备/离线评价；进程CPU另列，无GPU。', '',
             '| 人口 | 分配题数 | 资源 | 已观测N | 总量 | 均值 | 中位 | P90 |', '|---|---:|---|---:|---:|---:|---:|---:|']
    for name, part in parts:
        for field in ('input_tokens', 'output_tokens', 'usage_cost_usd', 'elapsed_seconds', 'process_cpu_seconds'):
            observed = [r[field] for r in part if r['execution_attempted'] or r['http_attempted']]
            d = B.describe(observed); record = {'population': name, 'allocated_n': len(part), 'resource': field, **d}; stats.append(record)
            lines.append(f"| {name} | {len(part)} | {field} | {d['n']} | " + ' | '.join(B.num(d[k]) for k in ('sum', 'mean', 'median', 'p90')) + ' |')
    lines += ['', '未运行占位零不参与执行资源分布；未知usage/费用保持NA。合并账本按request_id去重，不按相同prompt哈希去重；五次选文件仍是五个独立请求。', '',
              '财务核验=' + json.dumps(finance, ensure_ascii=False)]
    return '\n'.join(lines) + '\n', stats


def run_report(*, allow_incomplete=False, ci_repeats=10000, expected_counts=(265, 93, 28, 65)):
    original = C.load(C.ROOT / 'manifests/filtered265.json'); manifest = C.load(C.MANIFEST)
    ledger = C.load(C.SHARED_BUDGET); baseline = C.load(C.RUN / 'financial_baseline.json')
    if any(x is None for x in (original, manifest, ledger, baseline)):
        raise RuntimeError('Frozen original/new manifests, baseline and existing ledger required')
    B.validate_manifest(original)
    old_rows, old_targets, old_attempts = B.collect(original, budget=ledger)
    wrong, unfinished = scope_sets(old_rows); selected = wrong | unfinished
    records = manifest.get('records', [])
    if expected_counts is not None and (len(old_rows), len(records), len(wrong), len(unfinished)) != expected_counts:
        raise RuntimeError('Fixed265/93/28/65 scope changed')
    original_by = {r['instance_id']: r for r in original['records']}
    if manifest.get('n') != len(records) or len({r['instance_id'] for r in records}) != len(records) or {r['instance_id'] for r in records} != selected:
        raise RuntimeError('New manifest must equal old-wrong OR unfinished by IID')
    for rec in records:
        prior = original_by[rec['instance_id']]
        if any(rec[k] != prior[k] for k in ('instance_id', 'repo', 'base_commit')):
            raise RuntimeError('New case identity differs from old allocation')
        if Path(rec['result_dir']) != C.RUN / C.COHORT / 'D-SIMPLE' / rec['instance_id']:
            raise RuntimeError('New output path escaped independent run')
    new_rows, new_targets, new_attempts = collect_new(manifest, ledger)
    merged = merge_rows(old_rows, new_rows, selected)
    new_by = {r['instance_id']: r for r in merged if r['instance_id'] in selected}
    new_rows = [new_by[r['instance_id']] for r in new_rows]
    targets = [t for t in old_targets if t['instance_id'] not in selected] + new_targets
    if not allow_incomplete and any(r['status_family'] == 'NOT_RUN' or r['function_evaluation_status'] in ('INCOMPLETE', 'evaluation_unavailable') for r in merged):
        raise RuntimeError('Final allocation/evaluation unfinished; use --allow-incomplete for progress')
    finance = finance_summary(new_attempts, ledger, baseline)
    if not allow_incomplete and finance['unlinked_new_ledger_request_ids']:
        raise RuntimeError('Final finance has unlinked new requests')
    summaries = group_summaries(merged, new_rows, wrong, unfinished, ci_repeats)
    paired = paired_table(old_rows, new_rows, wrong)
    paired_stats = paired_summary(paired, ci_repeats)
    jobs = {rec['instance_id']: C.load(rec['job']) for rec in original['records']}
    jobs.update({rec['instance_id']: C.load(rec['job']) for rec in records})
    failure_md, categories, failure_index = failure_report(merged, targets, jobs)
    resource_md, resources = resource_report(new_rows, finance)
    unique = B.deduplicate_receipts(new_attempts)
    result = {'generated_at': C.utc(), 'report_protocol': '旧正确复用＋论文参数定向重测/补全',
              'allocation': {'merged': len(merged), 'new': len(new_rows), 'old_correct_reused': len(merged) - len(new_rows),
                             'old_wrong_retested': len(wrong), 'unfinished_completed_or_attempted': len(unfinished)},
              'forced_new_override': True, 'best_of_old_new': False, 'outcome_selected_retest_bias': True,
              'full265_paper_parameter_accuracy_claimed': False, 'seed': B.C.SEED, 'ci_repeats': ci_repeats,
              'summaries': summaries, 'paired28_summary': paired_stats, 'records': merged, 'new_records': new_rows, 'finance': finance,
              'new_model_requests_by_report': 0, 'source_manifest_sha256': C.sha(C.MANIFEST)}
    result['diagnostic_clarification_revision'] = '20261023_identity_boundary_v2'
    result['diagnostic_overlay_counts'] = {
        'metadata_path_alias_boundary': sum(bool(r.get('metadata_path_alias_boundary')) for r in new_rows),
        'owner_identity_context_gap': sum(bool(r.get('owner_identity_context_gap')) for r in new_rows),
        'planner_error_cases': sum(bool(r.get('planner_errors')) for r in new_rows),
        'planner_json_syntax_invalid': sum(r.get('planner_json_syntax_valid') is False for r in new_rows)}
    percase_resources = [{key: row[key] for key in ('instance_id', 'repo', 'status', 'status_family', 'original_origin',
                         'request_attempts', 'input_tokens', 'output_tokens', 'usage_cost_usd', 'known_usage_cost_usd',
                         'billing_unknown_attempts', 'cost_unknown_attempts', 'elapsed_seconds', 'process_cpu_seconds', 'result_path')}
                        for row in new_rows]
    retained_gaps = [r for r in merged if failure_kind(r) == 'retained_old_hit5_recall_gap']
    for name, data in [('merged265_per_issue.csv', merged), ('new93_per_issue.csv', new_rows), ('paired28.csv', paired),
                       ('paired28_summary.csv', paired_stats), ('retained_old_recall_gaps.csv', retained_gaps),
                       ('method_summary.csv', summaries), ('gold_source_evidence.csv', targets), ('cost_ledger.csv', unique),
                       ('本轮93题_资源消耗.csv', resources), ('本轮93题_逐题资源.csv', percase_resources),
                       ('failure_categories.csv', categories), ('failure_issue_index.csv', failure_index)]:
        output(name, data)
    output('evaluation_summary.json', result); output('shared_finance.json', finance)
    output('合并265题_总览.md', metric_overview(summaries, finance, paired_stats))
    output('本轮93题_资源消耗.md', resource_md); output('定位失败分析报告.md', failure_md)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-incomplete', action='store_true')
    args = parser.parse_args(argv)
    result = run_report(allow_incomplete=args.allow_incomplete)
    print(json.dumps({'reports': str(C.ROOT / 'reports' / REPORT), 'allocation': result['allocation'],
                      'new_http_attempts': result['finance']['new_unique_http_attempts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
