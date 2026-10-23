"""Offline strict R2 evaluation. Never import this module in a model worker.

Importing is inert. Only --execute-frozen reads the explicitly allocated265 gold
files. No patch/test row, provider, model or evaluation main is imported.
"""
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import tokenize

from . import common as C

KS = (1, 3, 5, 10)
CI_SEED = 20261021
CAUSE_ZH = {
    'not_run': '尚未运行；不冒充模型答错',
    'execution_failure': '执行或最终输出未完成；在已执行分母中保留',
    'function_truth_empty': '完整既有函数目标为空；函数指标NA',
    'evaluation_unavailable': '金标不可用或不完整；不当作空金标',
    'hit_all_targets': 'Top5覆盖全部既有函数目标',
    'hit_with_recall_gap': 'Top5命中但未覆盖全部目标',
    'rank_cutoff_at5': '精确身份排第6至10位',
    'directory_target_absent': '实际文件阶段目录展示中没有目标路径',
    'file_selection_miss': '目标文件未入候选文件，未检索到目标源码',
    'selected_target_not_retrieved': '已选文件中的目标源码未被检索',
    'target_unretrieved_with_parse_errors': '目标未检索，且存在工具解析错误；只报告共现',
    'target_unretrieved_with_target_errors': '目标未检索，且存在工具目标错误；只报告共现',
    'prune_false_without_agent_delivery': '目标源码已检索且judge判False，未送达搜索agent',
    'judge_only_no_agent_delivery': '目标源码送达judge，但未证明送达搜索agent',
    'target_source_partial': '搜索agent只收到目标定义的部分源码',
    'visible_identity_mismatch': '目标源码已送达，但输出同leaf的不同path/QN身份',
    'visible_ranking_omission': '目标源码已送达，最终Top10未列出精确身份',
    'retrieved_not_delivered': '保存了目标源码，但缺少有效因果送达证据',
    'mixed_target_gaps': '多个目标分别存在不同可观测缺口',
}


def digest(value):
    if not isinstance(value, (str, bytes)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def read_json(path, default=None):
    path = Path(path)
    if any(word in str(path).lower() for word in ('pruner_test', 'sealedtest', 'sealed_test', 'holdout', 'test_chain')):
        raise PermissionError('Sealed/holdout data may not be read by this reporter')
    return json.loads(path.read_text()) if path.is_file() else default


def norm(value):
    if not isinstance(value, str):
        return None
    value = value.replace('\\', '/')
    while value.startswith('./'):
        value = value[2:]
    return None if value.startswith('/') or '..' in value.split('/') else value


def source_file(path):
    if not path or not path.endswith('.py'):
        return False
    parts = path.lower().split('/')
    return not (any(p in ('test', 'tests', 'testing', 'doc', 'docs', 'documentation') for p in parts[:-1])
                or parts[-1].startswith('test_') or parts[-1].endswith('_test.py'))


def normalize_functions(raw, index):
    slots, invalid = [], 0
    for item in (raw if isinstance(raw, list) else [])[:10]:
        path = norm(item.get('path')) if isinstance(item, dict) else None
        qn = item.get('qualified_name') if isinstance(item, dict) else None
        matches = [d for d in index.get(path, {}).get('definitions', [])
                   if d['kind'] == 'function' and d['qualified_name'] == qn]
        valid = source_file(path) and bool(matches)
        slots.append(path + '::' + qn if valid else None)
        invalid += not valid
    return slots, invalid


def normalize_files(raw, paths):
    slots, invalid = [], 0
    for item in (raw if isinstance(raw, list) else [])[:10]:
        path = norm(item)
        valid = source_file(path) and path in paths
        slots.append(path if valid else None)
        invalid += not valid
    return slots, invalid


def scores(predictions, targets, k):
    if not targets:
        return dict.fromkeys(('hit', 'precision', 'recall', 'f1', 'all_coverage'))
    found = len(set(v for v in predictions[:k] if v is not None) & set(targets))
    precision, recall = found / k, found / len(set(targets))
    return {'hit': int(found > 0), 'precision': precision, 'recall': recall,
            'f1': 2 * precision * recall / (precision + recall) if found else 0.,
            'all_coverage': int(found == len(set(targets)))}


def mrr(predictions, targets):
    if not targets:
        return None
    return next((1 / (i + 1) for i, value in enumerate(predictions[:10]) if value in targets), 0.)


def events_at(folder):
    path = Path(folder) / 'events.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def call_audit(folder):
    """Count saved attempts once; missing usage remains unknown, never zero."""
    attempts, calls = [], []
    for directory in sorted((Path(folder) / 'calls').glob('*')):
        request = read_json(directory / 'request.json', {})
        if not request:
            continue
        call = {'path': str(directory), 'request': request, 'stage': directory.name.split('_', 1)[-1]}
        calls.append(call)
        receipts = {p.name.removesuffix('_receipt.json'): p for p in directory.glob('attempt_*_receipt.json')}
        starts = {p.name.removesuffix('_start.json'): p for p in directory.glob('attempt_*_start.json')}
        for key in sorted(set(receipts) | set(starts)):
            receipt = read_json(receipts.get(key, starts.get(key)), {})
            response_path = directory / (key + '_response.json')
            response = read_json(response_path, {})
            valid = bool(receipt.get('http_status') == 200 and receipt.get('request_id')
                         and receipt.get('request_sha256') == digest(request)
                         and receipt.get('response_sha256') == digest(response)
                         and response.get('id') == receipt.get('request_id'))
            attempt = {**receipt, 'path': str(receipts.get(key, starts.get(key))),
                       'request_path': str(directory / 'request.json'), 'response_path': str(response_path),
                       'request': request, 'response': response, 'effective_response': valid,
                       'stage': receipt.get('stage', call['stage']), 'terminal_receipt': key in receipts}
            attempts.append(attempt)
        result = read_json(directory / 'result.json', {})
        call['content'] = result.get('content', '')
    ids = Counter(a.get('request_id') for a in attempts if a.get('request_id'))
    for attempt in attempts:
        if ids.get(attempt.get('request_id'), 0) != 1:
            attempt['effective_response'] = False
    return attempts, calls


def resource_values(attempts, calls, result):
    known_input = known_output = unknown = 0
    for attempt in attempts:
        usage = attempt.get('usage') or {}
        a, b = usage.get('prompt_tokens'), usage.get('completion_tokens')
        valid_a, valid_b = number(a), number(b)
        known_input += a if valid_a else 0
        known_output += b if valid_b else 0
        unknown += not (valid_a and valid_b)
    walls = [a.get('attempt_elapsed_seconds') for a in attempts]
    return {'semantic_calls': len(calls), 'http_attempts': len(attempts),
            'http200_responses': sum(a.get('http_status') == 200 for a in attempts),
            'usage_unknown_attempts': unknown, 'known_prompt_tokens': known_input,
            'known_completion_tokens': known_output,
            'prompt_tokens': None if unknown else known_input,
            'completion_tokens': None if unknown else known_output,
            'http_attempt_wall_seconds': sum(walls) if all(number(v) for v in walls) else None,
            'elapsed_seconds': result.get('elapsed_seconds'), 'process_cpu_seconds': result.get('process_cpu_seconds'),
            'file_stage_wall_seconds': result.get('file_stage_wall_seconds'),
            'function_stage_wall_seconds': result.get('function_stage_wall_seconds'),
            'reasoning_responses': sum(bool(a.get('reasoning_content_present')) for a in attempts),
            'model_response_mismatches': sum(a.get('http_status') == 200 and a.get('response', {}).get('model') != C.SERVED_MODEL for a in attempts),
            'nonthinking_request_violations': sum(a['request'].get('chat_template_kwargs', {}).get('enable_thinking') is not False for a in attempts),
            'finish_reason_not_stop': sum(a.get('http_status') == 200 and a.get('finish_reason') != 'stop' for a in attempts),
            'local_api_billed_usd': 0., 'gpu_kernel_seconds': None}


def lf_lines(text):
    pieces = text.split('\n')
    return [part + '\n' for part in pieces[:-1]] + ([pieces[-1]] if pieces[-1] else [])


def decoded(raw):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def covers(intervals, start, end):
    cursor = start
    for a, b in sorted((max(start, a), min(end, b)) for a, b in intervals if b >= start and a <= end):
        if a > cursor:
            return False
        cursor = max(cursor, b + 1)
    return cursor > end


def source_valid(source, job, index):
    try:
        path = norm(source['path']);root = Path(job['snapshot']).resolve()
        full = (root / path).resolve()
        if not full.is_relative_to(root) or path not in index:
            return False
        raw = full.read_bytes();text = decoded(raw);lines = lf_lines(text)
        if digest(raw) != source['base_raw_sha256']:
            return False
        if index[path].get('raw_sha256') and index[path]['raw_sha256'] != digest(raw):
            return False
        expected = [(d['start_line'], d['end_line']) for d in index[path]['definitions']
                    if d['kind'] == source['kind'] and d['qualified_name'] == source['qualified_name']]
        if [(s['start_line'], s['end_line']) for s in source['spans']] != expected or not expected:
            return False
        for span in source['spans']:
            if not 1 <= span['start_line'] <= span['end_line'] <= len(lines):
                return False
            body = ''.join(lines[span['start_line'] - 1:span['end_line']])
            if span['text'] != body or span['sha256'] != digest(body):
                return False
        joined = '\n'.join(s['text'] for s in source['spans'])
        return source['text'] == joined and source['sha256'] == digest(joined)
    except (KeyError, ValueError, TypeError, OSError, UnicodeError, SyntaxError):
        return False


def source_delivery(folder, job, index, events, attempts):
    """Require origin round, successful wire proof and causal context acceptance."""
    by_id = {a['request_id']: a for a in attempts if a['effective_response']}
    node_sequences=sorted({a['sequence'] for a in attempts if a['stage']=='node_selection' and isinstance(a.get('sequence'),int)})
    context = read_json(Path(folder) / 'context.json', {})
    sources = {s['source_id']: s for s in context.get('retrieved_blocks', [])}
    for path in sorted((Path(folder) / 'sources').glob('source-*.json')):
        source = read_json(path)
        if source['source_id'] in sources and source != sources[source['source_id']]:
            raise ValueError('Source file/context copy differs: ' + str(path))
        sources[source['source_id']] = source
    rows = []
    for sid, source in sources.items():
        valid = source_valid(source, job, index)
        returned = [i for i, e in enumerate(events) if e['event'] == 'source_returned'
                    and e.get('source_id') == sid and e.get('step') == source['step']
                    and e.get('source_sha256') == source['sha256']]
        origin = min(returned) if returned else None
        origin_sequence=node_sequences[source['step']] if isinstance(source.get('step'),int) and 0<=source['step']<len(node_sequences) else None
        gate_sequences=[a['sequence'] for a in attempts if a['stage'] in ('pruner','pruner_format_retry')
                        and a.get('metadata',{}).get('navigation_step')==source['step'] and isinstance(a.get('sequence'),int)]
        accepted = [i for i, e in enumerate(events) if origin is not None and i > origin
                    and e['event'] == 'context_accept' and e.get('step') == source['step']
                    and e.get('tool') == source['tool'] and e.get('arguments') == source['arguments']]
        decisions = [e.get('decision') for i, e in enumerate(events) if origin is not None and i > origin
                     and e['event'] == 'prune' and e.get('step') == source['step']
                     and e.get('tool') == source['tool'] and e.get('arguments') == source['arguments']]
        judge, agent, final, proofs = False, False, False, []
        for i, event in enumerate(events):
            if origin is None or i <= origin or event.get('source_id') != sid or event.get('step') != source['step']:
                continue
            attempt = by_id.get(event.get('request_id'))
            if not attempt or event.get('request_sha256') != attempt.get('request_sha256'):
                continue
            if origin_sequence is None or not isinstance(attempt.get('sequence'),int) or attempt['sequence']<=origin_sequence:
                continue
            if not valid or not event.get('full_source_in_request') or not source['text']:
                continue
            if not any(source['text'] in m.get('content', '') for m in attempt['request'].get('messages', [])):
                continue
            stage = attempt['stage']
            if event['event'] == 'judge_seen' and stage in ('pruner', 'pruner_format_retry'):
                if attempt.get('metadata', {}).get('navigation_step') != source['step']:
                    continue
                judge = True
            elif event['event'] == 'agent_seen' and stage in ('node_selection', 'final_summary'):
                if not any(accept < i for accept in accepted) or (gate_sequences and attempt['sequence']<=max(gate_sequences)):
                    continue
                agent = True;final |= stage == 'final_summary'
            else:
                continue
            proofs.append({'recipient': 'judge' if event['event'] == 'judge_seen' else 'agent',
                           'stage': stage, 'request_id': attempt['request_id'],
                           'request_sha256': attempt['request_sha256'], 'request_path': attempt['request_path']})
        rows.append({'source_id': sid, 'path': source['path'], 'qualified_name': source['qualified_name'],
                     'kind': source['kind'], 'step': source['step'], 'base_source_valid': valid,
                     'source_returned_origin_proved': origin is not None,
                     'origin_node_sequence':origin_sequence,
                     'context_accepted_same_origin': bool(accepted), 'judge_seen': judge,
                     'agent_seen': agent, 'final_seen': final,
                     'prune_false': any(str(v).lower() == 'false' for v in decisions),
                     'prune_true': any(str(v).lower() == 'true' for v in decisions),
                     'spans': [(s['start_line'], s['end_line']) for s in source['spans']],
                     'source_sha256': source['sha256'], 'proofs': proofs})
    return rows


def tree_display(structure, prefix='', spacing=0):
    text, paths = '', set()
    for key, value in structure.items():
        if '.' in key and '.py' not in key:
            continue
        text += ' ' * spacing + key + ('\n' if '.' in key else '/\n')
        path = prefix + key
        if 'classes' in value:
            paths.add(path)
        else:
            child, names = tree_display(value, path + '/', spacing + 4)
            text += child;paths.update(names)
    return text, paths


def target_diagnostics(gold, index, slots, raw, selected, directory_paths, directory_proved, source_rows, events):
    targets = []
    parse_n = sum(e['event'] == 'parse_error' for e in events)
    errors_n = sum(e['event'] == 'tool_io_audit' and e.get('success') is False for e in events)
    for identity in gold.get('existing_function_targets', []):
        path, qn = identity.split('::', 1)
        definitions = [d for d in index.get(path, {}).get('definitions', [])
                       if d['kind'] == 'function' and d['qualified_name'] == qn]
        modified = {tuple((e['matched_base_span']['start_line'], e['matched_base_span']['end_line']))
                    for e in gold.get('changed_line_evidence', [])
                    if e.get('base_function_id', e.get('function_id')) == identity and e.get('matched_base_span')}
        required = sorted(modified or {(d['start_line'], d['end_line']) for d in definitions})
        related = [s for s in source_rows if s['path'] == path and s['base_source_valid']]

        def visible(flag):
            intervals = [span for s in related if flag is None or s[flag] for span in s['spans']]
            full = bool(required) and all(covers(intervals, a, b) for a, b in required)
            partial = any(x <= b and y >= a for a, b in required for x, y in intervals)
            return full, partial

        retrieved, _ = visible(None);judge, _ = visible('judge_seen')
        seen, partial = visible('agent_seen');final, _ = visible('final_seen')
        rank = next((i + 1 for i, item in enumerate(slots) if item == identity), None)
        mismatches = [{'rank': i + 1, 'path': p.get('path'), 'qualified_name': p.get('qualified_name')}
                      for i, p in enumerate(raw[:10]) if isinstance(p, dict)
                      and isinstance(p.get('qualified_name'), str) and p['qualified_name'].split('.')[-1] == qn.split('.')[-1]
                      and (norm(p.get('path')) != path or p['qualified_name'] != qn)]
        prune_false = any(s['prune_false'] for s in related if any(
            x <= b and y >= a for a, b in required for x, y in s['spans']))
        if rank and rank <= 5:
            cause = 'hit_all_targets'
        elif rank:
            cause = 'rank_cutoff_at5'
        elif seen:
            cause = 'visible_identity_mismatch' if mismatches else 'visible_ranking_omission'
        elif partial:
            cause = 'target_source_partial'
        elif retrieved and prune_false:
            cause = 'prune_false_without_agent_delivery'
        elif judge:
            cause = 'judge_only_no_agent_delivery'
        elif retrieved:
            cause = 'retrieved_not_delivered'
        elif directory_proved and path not in directory_paths:
            cause = 'directory_target_absent'
        elif path not in selected:
            cause = 'file_selection_miss'
        elif parse_n:
            cause = 'target_unretrieved_with_parse_errors'
        elif errors_n:
            cause = 'target_unretrieved_with_target_errors'
        else:
            cause = 'selected_target_not_retrieved'
        targets.append({'gold_identity': identity, 'path': path, 'qualified_name': qn,
                        'required_spans': required, 'span_scope': 'actual_modified_base_spans' if modified else 'all_base_identity_spans',
                        'normalized_raw_rank': rank, 'hit_at5': bool(rank and rank <= 5),
                        'in_selected_files': path in selected, 'directory_path_display_proved': directory_proved,
                        'in_displayed_directory': path in directory_paths if directory_proved else None,
                        'target_source_retrieved_full': retrieved, 'judge_seen_target_full': judge,
                        'agent_seen_target_full': seen, 'final_seen_target_full': final,
                        'agent_seen_target_partial': partial, 'prune_false_recorded': prune_false,
                        'same_leaf_different_identity': mismatches, 'cause': cause, 'cause_zh': CAUSE_ZH[cause]})
    return targets


def status_of(folder, result):
    if result:
        return result.get('status', 'failed')
    attempted = any((Path(folder) / name).exists() for name in ('started.json', 'events.jsonl', 'calls'))
    return 'attempted_without_terminal_result' if attempted else 'NOT_RUN'


def evaluate_case(record, gold, index, folder):
    """Purely offline per-case collection; synthetic fixtures use this same API."""
    folder = Path(folder);job = read_json(record['job']);result = read_json(folder / 'result.json', {})
    status = status_of(folder, result);events = events_at(folder);attempts, calls = call_audit(folder)
    for key in ('instance_id', 'repo', 'base_commit'):
        if record[key] != job[key] or (gold and gold.get(key, job[key]) != job[key]) or (result and result.get(key, job[key]) != job[key]):
            raise ValueError('Issue/base identity mismatch: ' + record['instance_id'])
    fn_raw = result.get('predicted_functions', [])
    file_raw = result.get('predicted_files', [])
    fn_slots, bad_fn = normalize_functions(fn_raw, index)
    file_slots, bad_file = normalize_files(file_raw, job['paths'])
    fn_gold = gold.get('existing_function_targets', []) if gold else []
    gold_status = gold.get('status', 'EVALUATION_UNAVAILABLE') if gold else 'EVALUATION_UNAVAILABLE'
    fn_scorable = gold_status == 'COMPLETE_NONEMPTY' and bool(fn_gold)
    file_gold = gold.get('gold_files', []) if gold else []
    file_scorable = bool(file_gold) and gold_status in ('COMPLETE_NONEMPTY', 'COMPLETE_EMPTY')
    sources = source_delivery(folder, job, index, events, attempts)
    tree, paths = tree_display(read_json(job['structure'])['structure'])
    directory_proved = bool(tree) and any(a['effective_response'] and a['stage'] in ('file_initial', 'file_reflection')
        and any(tree.strip() in message.get('content', '') for message in a['request'].get('messages', [])) for a in attempts)
    selected = result.get('ranked_edit_files', [])
    if not selected:
        selected = next((e.get('found_files', [])[:5] for e in events if e['event'] == 'file_stage_end'), [])
    targets = target_diagnostics(gold or {}, index, fn_slots, fn_raw, selected, paths, directory_proved, sources, events)
    row = {k: job[k] for k in ('instance_id', 'repo', 'base_commit')}
    row.update(status=status, status_family='complete' if status == 'complete' else 'NOT_RUN' if status == 'NOT_RUN' else 'failed',
               origin=record.get('origin'), gold_status=gold_status, function_scorable=fn_scorable,
               file_scorable=file_scorable, gold_function_count=len(fn_gold), gold_file_count=len(file_gold),
               gold_functions=fn_gold, gold_files=file_gold,
               function_gold_over5=len(fn_gold) > 5, allcoverage5_capacity_upper=int(len(fn_gold) <= 5) if fn_gold else None,
               recall5_capacity_upper=min(5, len(fn_gold)) / len(fn_gold) if fn_gold else None,
               normalized_function_slots=fn_slots, normalized_file_slots=file_slots,
               invalid_function_slots=bad_fn, invalid_file_slots=bad_file,
               raw_predicted_functions=fn_raw, raw_predicted_files=file_raw, selected_files=selected,
               file_endpoint_prediction_present='predicted_files' in result,
               function_endpoint_prediction_present='predicted_functions' in result,
               source_retrievals=len(sources), valid_source_retrievals=sum(s['base_source_valid'] for s in sources),
               source_judge_seen=sum(s['judge_seen'] for s in sources), source_agent_seen=sum(s['agent_seen'] for s in sources),
               source_final_seen=sum(s['final_seen'] for s in sources),
               predictions_without_agent_source=bool(any(fn_slots) and not any(s['agent_seen'] for s in sources)),
               raw_locations_without_agent_source=bool(fn_raw and not any(s['agent_seen'] for s in sources)),
               node_selection_proposals=sum(c['stage'] == 'node_selection' for c in calls),
               tool_parse_errors=sum(e['event'] == 'parse_error' for e in events),
               tool_executions=sum(e['event'] == 'tool_io_audit' and bool(e.get('executed')) for e in events),
               tool_successes=sum(e['event'] == 'tool_io_audit' and e.get('success') is True for e in events),
               tool_target_errors=sum(e['event'] == 'tool_io_audit' and e.get('success') is False for e in events),
               directory_display_proved=directory_proved, **resource_values(attempts, calls, result))
    for prefix, slots, truth, available in (('function', fn_slots, fn_gold, fn_scorable), ('file', file_slots, file_gold, file_scorable)):
        # Keep completed endpoint predictions even if a later stage failed.
        # No raw-text repair/fallback can bypass a provider contract failure.
        effective = slots
        for k in KS:
            for metric, value in scores(effective, truth if available else [], k).items():
                row[f'{prefix}_{metric}_{k}'] = None if status == 'NOT_RUN' else value
        row[f'{prefix}_mrr_10'] = None if status == 'NOT_RUN' else mrr(effective, truth if available else [])
    if status=='NOT_RUN' or (status!='complete' and 'predicted_functions' not in result):
        for target in targets:
            target.update(cause='not_run' if status=='NOT_RUN' else 'execution_failure',
                          cause_zh=CAUSE_ZH['not_run' if status=='NOT_RUN' else 'execution_failure'],
                          hit_at5=None if status=='NOT_RUN' else False)
    file_targets=[]
    for path in file_gold:
        rank=next((i+1 for i,value in enumerate(file_slots) if value==path),None)
        file_targets.append({'path':path,'normalized_raw_rank':rank,
            'cause':'not_run' if status=='NOT_RUN' else 'execution_failure' if status!='complete' and 'predicted_files' not in result else
                    'hit' if rank and rank<=5 else 'rank_cutoff_at5' if rank else
                    'directory_target_absent' if directory_proved and path not in paths else 'file_selection_miss',
            'directory_display_proved':directory_proved,'in_displayed_directory':path in paths if directory_proved else None,
            'retrieved_source_in_file':any(s['path']==path and s['base_source_valid'] for s in sources),
            'agent_received_source_in_file':any(s['path']==path and s['agent_seen'] for s in sources)})
    row['file_target_diagnostics']=file_targets
    row['empty_function_scope_reasons']=dict(Counter(e.get('reason','unspecified') for e in (gold or {}).get('scope_exempt_changes',[]))) if gold_status=='COMPLETE_EMPTY' else {}
    if status == 'NOT_RUN':cause = 'not_run'
    elif status != 'complete':cause = 'execution_failure'
    elif not gold or gold_status not in ('COMPLETE_NONEMPTY', 'COMPLETE_EMPTY'):cause = 'evaluation_unavailable'
    elif not fn_scorable:cause = 'function_truth_empty'
    elif row['function_hit_5']:
        cause = 'hit_with_recall_gap' if row['function_recall_5'] < 1 else 'hit_all_targets'
    else:
        causes = {t['cause'] for t in targets if not t['hit_at5']}
        cause = next(iter(causes)) if len(causes) == 1 else 'mixed_target_gaps'
    row.update(primary_cause=cause, primary_cause_zh=CAUSE_ZH[cause],
               issue_excerpt=re.sub(r'\s+', ' ', job['problem_statement']).strip()[:350],
               artifacts={'job': record['job'], 'result': str(folder/'result.json'), 'events': str(folder/'events.jsonl'),
                          'context': str(folder/'context.json')})
    target_rows = [dict(instance_id=row['instance_id'], status=status, **t) for t in targets]
    source_rows = [dict(instance_id=row['instance_id'], **s) for s in sources]
    action_rows = []
    node_calls = [c for c in calls if c['stage'] == 'node_selection']
    for step, call in enumerate(node_calls):
        related = [e for e in events if e.get('step') == step]
        action_rows.append({'instance_id': row['instance_id'], 'proposal_index': step,
                           'raw_response': call['content'], 'request_path': str(Path(call['path'])/'request.json'),
                           'parse_error': any(e['event'] == 'parse_error' for e in related),
                           'explicit_exit': any(e['event'] == 'explicit_exit' for e in related),
                           'executions': [e for e in related if e['event'] == 'tool_io_audit']})
    return row, target_rows, source_rows, action_rows, attempts


def confidence(values, repos, repeats=10000, seed=CI_SEED):
    import numpy as np
    if not values:
        return {'issue_bootstrap95': [None, None], 'repo_cluster_bootstrap95': [None, None]}
    array = np.array(values, float);rng = np.random.default_rng(seed)
    boot = array[rng.integers(0, len(array), size=(repeats, len(array)))].mean(axis=1)
    grouped = defaultdict(list)
    for repo, value in zip(repos, values):grouped[repo].append(value)
    names = sorted(grouped);sums = np.array([sum(grouped[r]) for r in names]);sizes = np.array([len(grouped[r]) for r in names])
    picked = rng.integers(0, len(names), size=(repeats, len(names)))
    clustered = sums[picked].sum(axis=1) / sizes[picked].sum(axis=1)
    return {'issue_bootstrap95': [float(v) for v in np.quantile(boot, [.025, .975])],
            'repo_cluster_bootstrap95': [float(v) for v in np.quantile(clustered, [.025, .975])]}


def describe(values):
    import numpy as np
    known = [v for v in values if number(v)]
    return {'known_n': len(known), 'missing_n': len(values)-len(known),
            'mean': statistics.mean(known) if known else None, 'median': statistics.median(known) if known else None,
            'p90': float(np.quantile(known, .9)) if known else None,
            'known_subtotal': sum(known), 'total': sum(known) if len(known) == len(values) else None}


def summaries(rows, repeats=10000):
    output = []
    for population in ('allocation', 'executed'):
        chosen = [r for r in rows if population == 'allocation' or r['status_family'] != 'NOT_RUN']
        for kind in ('file', 'function'):
            subset = [r for r in chosen if r[kind+'_scorable']]
            for metric in [f'{m}_{k}' for k in KS for m in ('hit', 'precision', 'recall', 'f1', 'all_coverage')] + ['mrr_10']:
                key = kind + '_' + metric
                values = [r[key] if r[key] is not None else 0. for r in subset]
                output.append({'population': population, 'kind': kind, 'metric': metric, 'denominator': len(subset),
                    'repositories': len({r['repo'] for r in subset}), 'mean': statistics.mean(values) if values else None,
                    'not_run_in_denominator': sum(r['status_family'] == 'NOT_RUN' for r in subset),
                    'terminal_failures_in_denominator': sum(r['status_family'] == 'failed' for r in subset),
                    'interpretation': 'allocation lower bound; NOT_RUN filled0 only here' if any(r['status_family']=='NOT_RUN' for r in subset) else 'observed outcomes; failures retained',
                    **confidence(values, [r['repo'] for r in subset], repeats)})
    return output


def compare_dsimple(rows, ds_rows):
    previous = {r['instance_id']: r for r in ds_rows}
    if len(previous) != len(ds_rows) or set(previous) != {r['instance_id'] for r in rows}:
        raise ValueError('D-SIMPLE comparison must match exactly the same unique issue IDs')
    result = []
    for row in rows:
        old = previous[row['instance_id']]
        if old.get('repo', row['repo']) != row['repo'] or old.get('base_commit', row['base_commit']) != row['base_commit']:
            raise ValueError('D-SIMPLE issue/base identity mismatch')
        item = {'instance_id': row['instance_id'], 'repo': row['repo'], 'cosil_status': row['status'],
                'dsimple_status': old.get('status'), 'comparison_scope': 'descriptive; D-SIMPLE retained old+targeted paper93 mixed protocol'}
        for kind in ('file', 'function'):
            for metric in ('hit_1', 'hit_3', 'hit_5', 'precision_5', 'recall_5', 'f1_5', 'all_coverage_5', 'mrr_10'):
                key = kind+'_'+metric;left = row.get(key);right = old.get(key)
                try:right = float(right) if right not in ('', 'None', 'null', None) else None
                except (ValueError, TypeError):right = None
                item['cosil_'+key] = left;item['dsimple_'+key] = right
                item['delta_'+key] = left-right if left is not None and right is not None else None
        result.append(item)
    return result


def write_output(directory, name, value):
    directory = Path(directory)
    if not directory.resolve().is_relative_to(C.REPORTS.resolve()):
        raise PermissionError('Reporter may only write its independent report directory')
    directory.mkdir(parents=True, exist_ok=True);path = directory/name
    if path.is_symlink():raise PermissionError('Report target must not be a symlink')
    if name.endswith('.csv'):
        fields = list(dict.fromkeys(k for row in value for k in row)) or ['status']
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields);writer.writeheader()
            for row in value:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})
    elif name.endswith('.json'):
        C.write(path, value)
    else:path.write_text(value)


def report(*, repeats=10000):
    manifest = read_json(C.INPUTS/'prepare_manifest.json');records = manifest['records']
    if manifest['count'] != 265 or len(records) != 265 or len({r['instance_id'] for r in records}) != 265:
        raise ValueError('Report requires the complete frozen265 roster')
    rows, targets, sources, actions, attempts = [], [], [], [], []
    for record in records:
        iid = record['instance_id']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', iid) or iid in ('.', '..'):raise ValueError('Unsafe iid')
        private = C.FROZEN/'evaluator_private/eval_v2/filtered265'/iid
        gold = read_json(private/'gold_v2.json')
        index = read_json(private/'code_index_v2.json', {})
        result = evaluate_case(record, gold, index, C.RUN/'cases'/iid)
        row, ts, ss, aa, http = result
        row['artifacts'].update(gold=str(private/'gold_v2.json'), evaluation_index=str(private/'code_index_v2.json'))
        rows.append(row);targets.extend(ts);sources.extend(ss);actions.extend(aa)
        attempts.extend(dict(instance_id=iid, **{k:v for k,v in a.items() if k not in ('request','response')}) for a in http)
    metrics = summaries(rows, repeats)
    observed = [r for r in rows if r['status_family'] != 'NOT_RUN']
    resources = {key:describe([r.get(key) for r in observed]) for key in (
        'elapsed_seconds','process_cpu_seconds','file_stage_wall_seconds','function_stage_wall_seconds',
        'prompt_tokens','completion_tokens','semantic_calls','http_attempts','http_attempt_wall_seconds')}
    summary = {'generated_utc': C.utc(), 'run_id': C.RUN_ID, 'model_id': C.MODEL_ID,
        'allocated':265, 'executed':len(observed), 'complete':sum(r['status_family']=='complete' for r in rows),
        'NOT_RUN':sum(r['status_family']=='NOT_RUN' for r in rows), 'statuses':dict(Counter(r['status'] for r in rows)),
        'gold_statuses':dict(Counter(r['gold_status'] for r in rows)),
        'input_origin_counts':dict(Counter(r['origin'] for r in rows)),
        'input_origin_interpretation':'input provenance only; this CoSIL run uses new Qwen3-8B outcomes and never reuses D-SIMPLE predictions',
        'repositories':len({r['repo'] for r in rows}),
        'function_scorable':sum(r['function_scorable'] for r in rows), 'file_scorable':sum(r['file_scorable'] for r in rows),
        'expected_function_nonempty':235, 'expected_function_empty':30,
        'expected_gold_counts_match':sum(r['function_scorable'] for r in rows)==235 and sum(r['gold_status']=='COMPLETE_EMPTY' for r in rows)==30,
        'function_gold_over5_cases':sum(r['function_gold_over5'] for r in rows),
        'scoring':'strict path::QN; original slots incl invalid/class/duplicates; P@k denominator k; failures retained with actual completed endpoint slots (missing prediction=[]); NOT_RUN perissueNA/allocation lowerbound',
        'file_endpoint_predictions':sum(r['file_endpoint_prediction_present'] for r in rows),
        'function_endpoint_predictions':sum(r['function_endpoint_prediction_present'] for r in rows),
        'metrics':metrics, 'resources_per_executed_issue':resources,
        'tool_statistics':{key:sum(r[key] for r in rows) for key in ('node_selection_proposals','tool_parse_errors','tool_executions','tool_successes','tool_target_errors','source_retrievals','valid_source_retrievals','source_judge_seen','source_agent_seen','source_final_seen')},
        'tool_rate_denominators':'parse/proposal=actual node_selection calls; source delivery/retrieval=distinct source_id per retrieval; no judge/agent inference from gold',
        'predictions_without_agent_source':sum(r['predictions_without_agent_source'] for r in rows),
        'raw_locations_without_agent_source':sum(r['raw_locations_without_agent_source'] for r in rows),
        'file_failure_causes':dict(Counter(t['cause'] for r in rows if r['status']=='complete' for t in r['file_target_diagnostics'] if t['cause']!='hit')),
        'empty_function_scope_reasons_overlap':dict(sum((Counter(r['empty_function_scope_reasons']) for r in rows),Counter())),
        'failure_causes':dict(Counter(r['primary_cause'] for r in rows)),
        'function_complete_miss':sum(r['status']=='complete' and r['function_hit_5']==0 for r in rows),
        'file_complete_miss':sum(r['status']=='complete' and r['file_hit_5']==0 for r in rows),
        'complete_hit5_recall_gap':sum(r['status']=='complete' and r['function_hit_5']==1 and r['function_recall_5']<1 for r in rows),
        'local_API_invoice_usd':0., 'compute_cost_or_GPU_kernel_seconds_measured':False,
        'usage_unknown_attempts':sum(r['usage_unknown_attempts'] for r in rows),
        'protocol_audit':{key:sum(r[key] for r in rows) for key in ('reasoning_responses','nonthinking_request_violations','model_response_mismatches','finish_reason_not_stop')},
        'semantic_format_repair_calls':len({a['request_path'] for a in attempts if 'format_retry' in a.get('stage','')}),
        'method_limitations':'Qwen3-8B nonthinking CoSIL-off, Python3.12 full base index; four-rule265 with repeated repos, not CQ2-CARE300; gold_patch_pass/empty_patch_fail NOT_CHECKED',
        'source_manifest_sha256':manifest['source_manifest_sha256'], 'prepare_manifest_sha256':C.sha(C.INPUTS/'prepare_manifest.json'),
        'report_module_sha256':C.sha(__file__), 'no_model_API_GPU_or_patch_execution_by_reporter':True}
    ds_path=C.FROZEN/'reports/paper_retest93/merged265_per_issue.csv'
    with ds_path.open(newline='') as stream:ds=list(csv.DictReader(stream))
    comparison=compare_dsimple(rows,ds)
    summary['dsimple_comparison']={'path':str(ds_path),'sha256':C.sha(ds_path),'scope':'mixed old retained plus targeted paper93 re-evaluation; descriptive paired-ID table, not uniform protocol or causal attribution'}
    for name,value in [('per_issue.csv',rows),('method_summary.csv',metrics),('gold_source_evidence.csv',targets),
                       ('source_delivery.csv',sources),('tool_actions.csv',actions),('http_attempts.csv',attempts),
                       ('comparison_dsimple.csv',comparison),('evaluation_summary.json',summary)]:write_output(C.REPORTS,name,value)
    lines=['# CoSIL Qwen3-8B：SWE-rebench四规则265题离线报告','','逐题按固定iid/base匹配；保留全部265题。',
        f"完成{summary['complete']}，已执行{summary['executed']}，未运行{summary['NOT_RUN']}；函数可评价{summary['function_scorable']}，文件可评价{summary['file_scorable']}。",'',
        '原槽位中的class、无效身份和重复项不压缩；P@k除k。失败留在已执行分母，并保留已完成端点的真实预测；未到达端点为空。未运行逐题NA，固定分配组另报明确下界。', '',
        '|范围|层级|指标|分母|均值|issue 95% CI|repo cluster 95% CI|','|---|---|---|---:|---:|---|---|']
    for m in metrics:
        if m['metric'] in ('hit_1','hit_3','hit_5','precision_5','recall_5','f1_5','all_coverage_5','mrr_10'):
            lines.append('|'+ '|'.join(str(m[k]) for k in ('population','kind','metric','denominator','mean','issue_bootstrap95','repo_cluster_bootstrap95'))+'|')
    lines+=['','资源按已执行题统计mean/median/P90；token只计HTTP实际usage，缺失NA并列known subtotal。HTTP墙钟含推理与调度，不是GPU kernel时间；本地API无按调用账单不代表计算免费。',
        '源码送达依据原base span/SHA、同轮judge和context_accept后的有效HTTP请求；文本子串存在本身不证明本次检索因果送达。',
        'D-SIMPLE对照是保留旧结果加定向paper93重测的混合协议，逐IID描述比较，不宣称统一配置或因果胜负。',
        '输入来源的old100_reuse44仅指44题旧base数据来源；本轮CoSIL预测均为新Qwen3-8B运行，不复用D-SIMPLE预测。',
        '本任务允许重复仓库；95%区间同时给issue bootstrap与repo cluster bootstrap。testqualification NOT_CHECKED，不冒称完全CQ2资格。']
    write_output(C.REPORTS,'总览.md','\n'.join(lines)+'\n')
    failure=['# 逐题可观测失败与召回缺口','','以下为保存证据的自动分类，不推测模型内部思维；完整手工语义复核可另补。','']
    by_iid=defaultdict(list)
    for target in targets:by_iid[target['instance_id']].append(target)
    for row in rows:
        if row['primary_cause']=='hit_all_targets' and row['file_hit_5']==1:continue
        failure += [f"## {row['instance_id']}",'',f"状态：{row['status']}；{row['primary_cause_zh']}。文件Hit5={row['file_hit_5']}，函数Hit5={row['function_hit_5']}。",row['issue_excerpt'],'']
        for target in by_iid[row['instance_id']]:
            if not target['hit_at5']:
                failure.append(f"- {target['gold_identity']}：{target['cause_zh']}；judge完整={target['judge_seen_target_full']}，agent完整={target['agent_seen_target_full']}，最终完整={target['final_seen_target_full']}，原排名={target['normalized_raw_rank']}。")
        for target in row['file_target_diagnostics']:
            if target['cause']!='hit':failure.append(f"- 文件 {target['path']}：{CAUSE_ZH[target['cause']]}；原排名={target['normalized_raw_rank']}，该文件源码被agent收到={target['agent_received_source_in_file']}。")
        failure+=['',f"证据：{json.dumps(row['artifacts'],ensure_ascii=False)}",'']
    write_output(C.REPORTS,'逐题失败分析.md','\n'.join(failure)+'\n')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-frozen',action='store_true',required=True)
    parser.add_argument('--bootstrap-repeats',type=int,default=10000)
    args=parser.parse_args()
    if args.bootstrap_repeats<1000:raise ValueError('At least1000 bootstrap repeats required')
    result=report(repeats=args.bootstrap_repeats)
    print(json.dumps({k:result[k] for k in ('allocated','executed','complete','NOT_RUN','gold_statuses')},ensure_ascii=False))


if __name__=='__main__':main()
