"""Gold-free, read-only engineering review of the fixed Java128 first three.

This module never invokes a provider, imports an evaluator, reads private Gold,
or writes the controller's gate. Missing terminals are PENDING, never PASS.
Natural model exits, empty predictions and class/gray routes are observations;
they are not converted into accuracy-based protocol changes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import time


ARMS = ('cosil', 'sfpruner', 'locagent')
PUBLIC_FIELDS = {'instance_id', 'repo', 'base_commit', 'problem_statement', 'cohort',
                 'snapshot', 'paths', 'code_index', 'structure'}
TOOLS = {'explore_tree_structure', 'search_code_snippets', 'get_entity_contents', 'finish'}
RPC_FIELDS = {'model_input', 'input_version', 'input_sha256', 'issue', 'function', 'neighbors'}
NATURAL_STOPS = {'step_limit', 'timeout', 'empty_output'}


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def text_sha(text):
    return sha_bytes(text.encode('utf-8'))


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def jsonlines(path):
    path = Path(path)
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()] if path.exists() else []


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def usage_known(usage):
    return isinstance(usage, dict) and all(integer(usage.get(k)) for k in ('prompt_tokens', 'completion_tokens'))


def message_texts(request):
    for message in request.get('messages', []):
        value = message.get('content')
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and isinstance(item.get('text'), str):
                    yield item['text']


def complaint(errors, code, detail, **scope):
    errors.append({'code': code, 'detail': str(detail), **scope})


def raw_function_slots(raw):
    blocks = re.findall(r'```(?:[^\n]*\n)?(.*?)```', raw, re.S)
    path, out = '', []
    for line in ('\n'.join(blocks) if blocks else raw).splitlines():
        line = line.strip()
        if line.endswith('.java'):
            path = line
        elif line.startswith(('function:', 'class:', 'variable:')):
            kind, name = line.split(':', 1)
            out.append({'path': path, 'qualified_name': name.strip() if kind == 'function' else None,
                        'raw_name': name.strip(), 'legacy_kind': kind})
    return out


def index_inventory(index):
    return {path + '::' + d['qualified_name']: (path, d)
            for path, entry in index.items() for d in entry.get('definitions', []) if d.get('kind') == 'function'}


def check_chat(request, response, errors, label, *, locagent=False):
    if request.get('model') != 'qwen3-8b':
        complaint(errors, 'wrong_request_model', request.get('model'), artifact=label)
    if request.get('chat_template_kwargs', {}).get('enable_thinking') is not False:
        complaint(errors, 'thinking_not_explicitly_disabled', label)
    expected = {'temperature': 1.0, 'top_p': .8, 'repetition_penalty': 1.05,
                'max_completion_tokens': 2048, 'parallel_tool_calls': False} if locagent else {
                    'temperature': 0., 'seed': 0, 'max_tokens': 2048}
    for key, value in expected.items():
        if request.get(key) != value:
            complaint(errors, 'request_parameter_drift', f'{key}={request.get(key)!r}, expected {value!r}', artifact=label)
    if locagent:
        names = {item.get('function', {}).get('name') for item in request.get('tools', [])}
        if names != TOOLS:
            complaint(errors, 'locagent_tool_schema_drift', sorted(str(x) for x in names), artifact=label)
    if not isinstance(response, dict):
        complaint(errors, 'raw_response_not_json', label)
        return
    if response.get('model') != 'qwen3-8b':
        complaint(errors, 'wrong_response_model', response.get('model'), artifact=label)
    if not usage_known(response.get('usage')):
        complaint(errors, 'successful_response_usage_unknown', label)
    for choice in response.get('choices', []):
        if choice.get('message', {}).get('reasoning_content'):
            complaint(errors, 'thinking_response_present', label)


def cosil_http(directory, errors):
    requests, ids = [], {}
    totals = {'prompt_tokens': 0, 'completion_tokens': 0, 'http_attempts': 0, 'successful_responses': 0}
    for folder in sorted((directory / 'calls').glob('*')):
        request_path = folder / 'request.json'
        if not request_path.exists():
            continue
        request = load(request_path)
        record = {'request': request, 'purpose': re.sub(r'^\d+_', '', folder.name),
                  'artifact': str(request_path), 'responses': []}
        requests.append(record)
        starts = sorted(folder.glob('attempt_*_start.json'))
        if not starts:
            complaint(errors, 'semantic_request_without_http_attempt', request_path)
        for start in starts:
            totals['http_attempts'] += 1
            receipt_path = start.with_name(start.name.replace('_start.json', '_receipt.json'))
            response_path = start.with_name(start.name.replace('_start.json', '_response.json'))
            if not receipt_path.exists():
                complaint(errors, 'http_attempt_without_receipt', start)
                continue
            receipt = load(receipt_path)
            if receipt.get('http_status') != 200:
                complaint(errors, 'main_http_error', receipt.get('error', receipt.get('http_status')), artifact=str(receipt_path))
                continue
            if not response_path.exists():
                complaint(errors, 'successful_http_without_raw_response', receipt_path)
                continue
            response = load(response_path)
            check_chat(request, response, errors, str(request_path))
            if usage_known(response.get('usage')):
                for key in ('prompt_tokens', 'completion_tokens'):
                    totals[key] += response['usage'][key]
            totals['successful_responses'] += 1
            if receipt.get('usage') != response.get('usage'):
                complaint(errors, 'receipt_usage_differs_from_raw_response', receipt_path)
            payload_digest = sha_bytes(json.dumps(request, sort_keys=True, ensure_ascii=False).encode())
            if receipt.get('request_sha256') != payload_digest:
                complaint(errors, 'request_receipt_sha_mismatch', request_path)
            if receipt.get('input_tokens_local', 0) + 2048 > 65536:
                complaint(errors, 'main_context_budget_violation', receipt_path)
            if response.get('id'):
                ids[response['id']] = {**record, 'receipt': receipt}
            record['responses'].append(response)
    return requests, ids, totals


def check_source(source, job, index, errors):
    path, qn = source.get('path'), source.get('qualified_name')
    if path not in index:
        complaint(errors, 'returned_source_outside_inventory', path)
        return None
    entry = index[path]
    definitions = entry.get('classes', []) if source.get('kind') == 'class' else entry.get('definitions', [])
    found = [d for d in definitions if d.get('qualified_name') == qn]
    if len(found) != 1:
        complaint(errors, 'returned_identity_ambiguous_or_absent', path + '::' + str(qn))
        return None
    definition = found[0]
    root = Path(job['snapshot']).resolve()
    base = root / path
    if base.is_symlink() or not base.resolve().is_relative_to(root):
        complaint(errors, 'returned_source_path_escape', path)
        return None
    raw = base.read_bytes()
    if sha_bytes(raw) != entry['raw_sha256']:
        complaint(errors, 'returned_base_file_sha_mismatch', path)
    body = raw[definition['start_byte']:definition['end_byte']].decode('utf-8')
    text = source.get('text', '')
    header = f'[Exact base source identity: {path}::{qn}]\n'
    if text != header + body or source.get('sha256') != text_sha(text):
        complaint(errors, 'returned_source_not_exact_base_bytes', path + '::' + qn)
    if source.get('raw_source_text_sha256') != text_sha(body):
        complaint(errors, 'returned_source_body_sha_mismatch', path + '::' + qn)
    return body


def cosil_review(directory, arm, job, index, errors, observations):
    result = load(directory / 'result.json')
    requests, request_ids, tokens = cosil_http(directory, errors)
    if not requests:
        complaint(errors, 'no_real_main_http_requests', directory)
    protocol_path = directory / 'worker_protocol.json'
    if not protocol_path.exists():
        complaint(errors, 'missing_worker_protocol', directory)
    else:
        p = load(protocol_path)
        expected_arm = 'baseline' if arm == 'cosil' else 'hybrid_safe'
        if p.get('arm') != expected_arm or p.get('cross_language_zero_shot') is not True or p.get('train_or_recalibrate') is not False:
            complaint(errors, 'worker_protocol_identity_drift', protocol_path)
    if result.get('predicted_functions', []) != raw_function_slots(result.get('raw_output', '')):
        complaint(errors, 'final_function_ranks_rewritten_or_guessed', directory)
    valid = index_inventory(index)
    invalid = [r for r in result.get('predicted_functions', [])
               if r.get('path', '') + '::' + str(r.get('qualified_name')) not in valid]
    if invalid:
        observations.append({'kind': 'invalid_raw_prediction_slots_preserved', 'count': len(invalid)})
    events = jsonlines(directory / 'events.jsonl')
    context = load(directory / 'context.json') if (directory / 'context.json').exists() else {}
    sources = context.get('retrieved_blocks', [])
    if not sources:
        observations.append({'kind': 'no_source_retrieved', 'natural_model_behavior_possible': True})
    source_ids = {s['source_id'] for s in sources}
    for event in events:
        if event.get('event') == 'source_returned' and event.get('source_id') not in source_ids:
            complaint(errors, 'source_event_missing_durable_source', event.get('source_id'))
    rpc_rows = {}
    for folder in sorted((directory / 'judge_rpc').glob('*')):
        request_path = folder / 'request.json'
        if not request_path.exists():
            continue
        req = load(request_path)
        if set(req) != {'operation', 'row'} or req['operation'] != 'score' or set(req['row']) != RPC_FIELDS:
            complaint(errors, 'judge_rpc_input_whitelist_violation', request_path)
            continue
        row = req['row']
        expected_text = (f"<issue>\n{row['issue']}\n</issue>\n<function>\n{row['function']}\n</function>\n"
                         f"<direct_call_context>\n{row['neighbors']}\n</direct_call_context>")
        if row['model_input'] != expected_text or text_sha(row['model_input']) != row['input_sha256']:
            complaint(errors, 'judge_rendered_input_mismatch', request_path)
        response_path, receipt_path = folder / 'response.json', folder / 'receipt.json'
        if not response_path.exists() or not receipt_path.exists():
            complaint(errors, 'judge_rpc_without_terminal_receipt', folder)
        else:
            response, receipt = load(response_path), load(receipt_path)
            if not response.get('ok') or receipt.get('status') != 'success':
                complaint(errors, 'judge_rpc_error', folder)
            scored = response.get('result', {})
            if not integer(scored.get('input_tokens')) or scored.get('generated_output_tokens') != 0:
                complaint(errors, 'judge_usage_unknown_or_generation_enabled', folder)
        rpc_rows[row['input_sha256']] = row
    chains, deliveries = [], 0
    for source in sources:
        body = check_source(source, job, index, errors)
        sid, step = source['source_id'], source.get('step')
        related = [e for e in events if e.get('source_id') == sid]
        scored = [e for e in events if e.get('event') == 'local_judge' and e.get('step') == step
                  and e.get('arguments') == source.get('arguments')]
        main_judge = [e for e in related if e.get('event') == 'judge_seen']
        accepted = sid in context.get('accepted_source_ids', [])
        if not main_judge and not scored:
            complaint(errors, 'returned_source_without_any_judge_evidence', sid)
        for event in main_judge + [e for e in related if e.get('event') == 'agent_seen']:
            found = request_ids.get(event.get('request_id'))
            if found is None or not any(source['text'] in text for text in message_texts(found['request'])):
                complaint(errors, 'claimed_delivery_missing_actual_http_source', sid, recipient=event.get('recipient'))
            elif event.get('request_sha256') != found['receipt'].get('request_sha256'):
                complaint(errors, 'delivery_request_sha_mismatch', sid)
        for event in scored:
            row = rpc_rows.get(event.get('input_sha256'))
            if row is None or body is None or not body.startswith(row['function']):
                complaint(errors, 'local_judge_missing_actual_bound_function_input', sid)
            if body is not None and event.get('source_sha256') != text_sha(body):
                complaint(errors, 'local_judge_full_source_sha_mismatch', sid)
            expected_id = source['path'] + '::' + source['qualified_name']
            if event.get('function_id') != expected_id:
                complaint(errors, 'local_judge_identity_mismatch', expected_id)
        agent = [e for e in related if e.get('event') == 'agent_seen']
        accept_events = [e for e in events if e.get('event') == 'context_accept' and e.get('step') == step
                         and e.get('arguments') == source.get('arguments')]
        if accepted and (not agent or not accept_events):
            complaint(errors, 'accepted_source_missing_search_delivery_chain', sid)
        deliveries += bool(agent)
        chains.append({'source_id': sid, 'identity': source['path'] + '::' + source['qualified_name'],
            'kind': source.get('kind'), 'main_judge_delivery_events': len(main_judge),
            'small_judge_events': len(scored), 'context_accepted': accepted,
            'search_agent_delivery_events': len(agent)})
    count = Counter(e.get('event') for e in events)
    for kind, key in [('natural_explicit_exit', 'explicit_exit'), ('class_bypass', 'pruner_class_fallback'),
                      ('binding_fallback', 'judge_binding_fallback'), ('invalid_tool_request', 'parse_error')]:
        if count[key]:
            observations.append({'kind': kind, 'count': count[key]})
    if arm == 'sfpruner' and not count['local_judge']:
        observations.append({'kind': 'no_small_judge_forward', 'class_bypass_or_early_exit_possible': True})
    for event in events:
        if event.get('event') == 'tool_io_audit' and not event.get('success', True):
            # An exact valid inventory request rejected by the dispatcher is an
            # interface failure; malformed/nonexistent model requests are not.
            args = event.get('arguments', [])
            path = args[0] if args else None
            qn = '.'.join(args[1:]) if all(isinstance(x, str) for x in args) else ''
            candidates = index.get(path, {}).get('classes' if event.get('tool') == 'get_code_of_class' else 'definitions', [])
            if any(d.get('qualified_name') == qn for d in candidates):
                complaint(errors, 'valid_java_tool_identity_rejected', event.get('error'), identity=str(path) + '::' + qn)
            else:
                observations.append({'kind': 'model_invalid_tool_identity', 'error': event.get('error')})
    if arm == 'sfpruner' and any(r['purpose'].startswith('file') for r in requests):
        complaint(errors, 'sfpruner_recomputed_shared_file_stage', directory)
    return {'http': tokens, 'event_counts': dict(count), 'source_chains': chains,
            'actual_search_source_deliveries': deliveries, 'small_judge_forward_count': count['local_judge'],
            'ranked_function_slots': len(result.get('predicted_functions', [])), 'invalid_prediction_slots': len(invalid)}


def locagent_source_witness(output, index, errors, label):
    """Check numbered, full-source lines against mentioned base files.

    Skeletons are explicitly compressed metadata, so they are observed rather
    than falsely counted as complete source delivery.
    """
    if 'Just show the structure' in output or ('[...]' in output and 'Source:' in output):
        return {'source_lines': 0, 'skeleton_only': True, 'witnesses': []}
    paths = [p for p in index if p in output]
    witnesses = []
    for number, value in re.findall(r'^\s*(\d+)\s*\| ?(.*)$', output, re.M):
        number = int(number)
        if not paths:
            continue
        candidates = []
        for path in paths:
            lines = index[path].get('text', index[path].get('content', '')).split('\n')
            if 1 <= number <= len(lines) and lines[number - 1].rstrip('\r').strip() == value.rstrip('\r').strip():
                candidates.append(path)
        if not candidates:
            complaint(errors, 'locagent_numbered_source_differs_from_base', f'line {number}', artifact=label)
        elif len(value.strip()) >= 8 and re.search('[A-Za-z]', value):
            witnesses.append({'paths': candidates, 'line': number, 'source_line_sha256': text_sha(value)})
    return {'source_lines': len(witnesses), 'skeleton_only': False, 'witnesses': witnesses[:20]}


def locagent_review(directory, job, index, errors, observations):
    result = load(directory / 'result.json')
    protocol = load(directory / 'protocol.json') if (directory / 'protocol.json').exists() else {}
    for key, expected in [('samples', 2), ('thinking', False), ('context_tokens', 65536),
                          ('output_tokens', 2048), ('temperature', 1.0), ('top_p', .8),
                          ('repetition_penalty', 1.05)]:
        if protocol.get(key) != expected:
            complaint(errors, 'locagent_protocol_drift', f'{key}={protocol.get(key)!r}')
    if len(result.get('samples', [])) != 2:
        complaint(errors, 'locagent_did_not_preserve_two_samples', directory)
    inventory = index_inventory(index)
    for slot in result.get('ranked_functions', []):
        identity = slot.get('path', '') + '::' + slot.get('qualified_name', '')
        if identity not in inventory:
            complaint(errors, 'locagent_final_identity_outside_inventory', identity)
    output = {'samples': [], 'actual_search_source_deliveries': 0,
              'http': {'prompt_tokens': 0, 'completion_tokens': 0, 'http_attempts': 0, 'successful_responses': 0}}
    for number in (1, 2):
        sample = directory / 'samples' / f'sample_{number:02d}'
        terminal_path = sample / 'result.json'
        if not terminal_path.exists():
            complaint(errors, 'locagent_sample_missing_terminal', sample)
            continue
        terminal = load(terminal_path)
        if terminal.get('status') in NATURAL_STOPS:
            observations.append({'kind': 'locagent_natural_or_resource_stop', 'sample': number,
                                 'status': terminal['status']})
        elif terminal.get('status') != 'complete':
            complaint(errors, 'locagent_sample_system_error', terminal.get('error', terminal.get('status')), sample=number)
        requests = []
        request_root = sample / 'requests'
        ledger = jsonlines(request_root / 'http_ledger.jsonl')
        starts = [r for r in ledger if r.get('event') == 'started']
        finishes = {(r.get('completion_request'), r.get('transport_retry')): r
                    for r in ledger if r.get('event') == 'finished'}
        for start in starts:
            output['http']['http_attempts'] += 1
            request_path = request_root / start['request_file']
            request = load(request_path)
            requests.append(request)
            finish = finishes.get((start.get('completion_request'), start.get('transport_retry')))
            if finish is None:
                complaint(errors, 'locagent_http_attempt_without_terminal_ledger', request_path)
                continue
            if finish.get('status_code') != 200:
                complaint(errors, 'locagent_http_error', finish.get('error', finish.get('status_code')), artifact=str(request_path))
                continue
            response_path = request_root / finish.get('response_file', '')
            if not response_path.is_file():
                complaint(errors, 'locagent_successful_http_without_raw_response', request_path)
                continue
            response = load(response_path)
            check_chat(request, response, errors, str(request_path), locagent=True)
            if response.get('usage') != finish.get('usage'):
                complaint(errors, 'locagent_usage_receipt_mismatch', response_path)
            output['http']['successful_responses'] += 1
            if usage_known(response.get('usage')):
                for key in ('prompt_tokens', 'completion_tokens'):
                    output['http'][key] += response['usage'][key]
        if not starts:
            complaint(errors, 'locagent_sample_without_http_attempts', sample)
        tools = jsonlines(sample / 'tools.jsonl')
        details = []
        for event in tools:
            tool = event.get('function')
            if tool not in TOOLS - {'finish'}:
                observations.append({'kind': 'invalid_model_tool_expression', 'sample': number, 'error': event.get('error')})
                continue
            if event.get('status') != 'success':
                error = str(event.get('error', ''))
                if any(s in error for s in ('AttributeError', 'FileNotFoundError', 'ModuleNotFoundError', 'UnicodeDecodeError')):
                    complaint(errors, 'locagent_tool_runtime_error', error, sample=number)
                else:
                    observations.append({'kind': 'locagent_model_tool_error', 'sample': number, 'error': error})
                continue
            text = event.get('output', '')
            delivered = bool(text) and any(text in content for req in requests for content in message_texts(req))
            witness = locagent_source_witness(text, index, errors, str(sample / 'tools.jsonl')) if tool in {
                'search_code_snippets', 'get_entity_contents'} else {'source_lines': 0, 'skeleton_only': False, 'witnesses': []}
            if delivered and witness['source_lines']:
                output['actual_search_source_deliveries'] += 1
            if not delivered:
                observations.append({'kind': 'tool_output_not_seen_in_subsequent_http', 'sample': number,
                                     'tool': tool, 'terminal_status': terminal.get('status')})
            details.append({'tool': tool, 'sequence': event.get('sequence'), 'output_delivered': delivered, **witness})
        # Never let an overloaded bare name expand into several predicted methods.
        raw = terminal.get('raw_location', '')
        parsed = terminal.get('parsed', {})
        for identity in parsed.get('functions', []):
            if identity not in inventory:
                complaint(errors, 'locagent_sample_identity_outside_inventory', identity, sample=number)
                continue
            path, definition = inventory[identity]
            bare = definition['qualified_name'].partition('(')[0]
            peers = [d for p, d in inventory.values() if p == path and d['qualified_name'].partition('(')[0] == bare]
            if len(peers) > 1 and definition['qualified_name'] not in raw:
                lines = [int(s) for s in re.findall(r'\bline\s*:\s*(\d+)', raw, re.I)]
                if not any(definition['start_line'] <= line <= definition['end_line'] for line in lines):
                    complaint(errors, 'overload_resolved_without_signature_or_line_evidence', identity, sample=number)
        if not tools:
            observations.append({'kind': 'locagent_no_tool_calls', 'sample': number})
        output['samples'].append({'sample': number, 'status': terminal.get('status'),
            'http_attempts': len(starts), 'tools': details, 'raw_location_empty': not bool(raw)})
    return output


def review(root):
    root = Path(root).resolve(strict=True)
    errors, pending, cases = [], [], []
    freeze_path, allocation_path = root / 'execution_freeze.json', root / 'allocation.json'
    if not freeze_path.exists() or not allocation_path.exists():
        return {'status': 'PENDING', 'errors': [], 'pending': ['execution freeze or allocation not yet present'],
                'gold_read': False, 'accuracy_used': False, 'gate_written': False}
    freeze, allocation = load(freeze_path), load(allocation_path)
    if not freeze.get('commit'):
        complaint(errors, 'missing_recoverable_execution_commit', freeze_path)
    if sha(allocation_path) != freeze.get('allocation_sha256'):
        complaint(errors, 'allocation_sha_changed', allocation_path)
    source_checks = []
    for filename, expected in freeze.get('files_sha256', {}).items():
        path = Path(filename)
        actual = sha(path) if path.is_file() else None
        source_checks.append({'path': filename, 'expected_sha256': expected, 'actual_sha256': actual, 'matches': actual == expected})
        if actual != expected:
            complaint(errors, 'execution_source_sha_changed', filename)
    if not source_checks:
        complaint(errors, 'execution_freeze_without_sources', freeze_path)
    rows = allocation.get('records', [])
    if allocation.get('n') != 128 or len(rows) != 128 or len({r['instance_id'] for r in rows}) != 128:
        complaint(errors, 'allocation_not_complete_java128', allocation_path)
    expected_ids = [r['instance_id'] for r in rows[:3]]
    canary_terminal = root / 'run/canary_terminal.json'
    if not canary_terminal.exists():
        pending.append('Fixed canary controller has not written its terminal receipt')
    elif load(canary_terminal).get('ids') != expected_ids:
        complaint(errors, 'canary_membership_differs_from_first3', canary_terminal)
    deliveries = Counter()
    for row in rows[:3]:
        iid = row['instance_id']
        if not re.fullmatch('[A-Za-z0-9_.-]+', iid) or iid in ('.', '..'):
            complaint(errors, 'unsafe_canary_identity', iid)
            continue
        public, group = root / 'public' / iid, root / 'run' / iid
        case = {'instance_id': iid, 'repo': row.get('repo'), 'base_commit': row.get('base_commit'), 'arms': {}}
        cases.append(case)
        if not (public / 'job.json').exists():
            pending.append(iid + ': public preparation pending')
            continue
        job = load(public / 'job.json')
        if set(job) != PUBLIC_FIELDS:
            complaint(errors, 'public_job_field_whitelist', iid)
            continue
        for key in ('instance_id', 'repo', 'base_commit'):
            if job.get(key) != row.get(key):
                complaint(errors, 'public_job_allocation_identity_mismatch', iid, field=key)
        job['snapshot'] = str(public / 'snapshot')
        index = load(public / 'code_index.json')
        for arm in ARMS:
            directory = group / arm
            entry_errors, observations = [], []
            record = {'observations': observations, 'errors': entry_errors}
            case['arms'][arm] = record
            terminal_path = directory / 'terminal.json'
            if not terminal_path.exists():
                record['status'] = 'PENDING'
                pending.append(iid + '/' + arm + ': terminal pending')
                continue
            terminal = load(terminal_path)
            if terminal.get('instance_id') != iid or terminal.get('arm') != arm or terminal.get('keep_in_denominator') is not True:
                complaint(entry_errors, 'terminal_identity_or_denominator_drift', terminal_path)
            record['terminal_status'] = terminal.get('status')
            result_path = directory / 'result.json'
            if not result_path.exists():
                complaint(entry_errors, 'terminal_without_worker_result', terminal_path)
            else:
                result = load(result_path)
                for key in ('instance_id', 'repo', 'base_commit'):
                    if result.get(key) != row.get(key):
                        complaint(entry_errors, 'worker_result_identity_mismatch', result_path, field=key)
                if terminal.get('result_sha256') != sha(result_path):
                    complaint(entry_errors, 'worker_result_terminal_sha_mismatch', result_path)
                if result.get('status') not in ('complete', 'partial'):
                    complaint(entry_errors, 'worker_failed_before_complete_protocol', result.get('error', result.get('status')))
                try:
                    record['evidence'] = (locagent_review(directory, job, index, entry_errors, observations) if arm == 'locagent'
                        else cosil_review(directory, arm, job, index, entry_errors, observations))
                    deliveries[arm] += record['evidence']['actual_search_source_deliveries']
                except Exception as error:
                    complaint(entry_errors, 'audit_evidence_unreadable', type(error).__name__ + ': ' + str(error))
            isolation = directory / 'isolation.json'
            if not isolation.exists() or load(isolation).get('passed') is not True:
                complaint(entry_errors, 'missing_or_failed_actual_mount_isolation', isolation)
            start = directory / 'controller_started.json'
            if not start.exists():
                complaint(entry_errors, 'missing_durable_controller_start', directory)
            elif load(start).get('job_sha256') != sha(group / 'input/job.json'):
                complaint(entry_errors, 'controller_start_job_sha_mismatch', start)
            record['status'] = 'FAIL' if entry_errors else 'PASS'
            for error in entry_errors:
                errors.append({'instance_id': iid, 'arm': arm, **error})
        if all((group / arm / 'result.json').exists() for arm in ('cosil', 'sfpruner')):
            original, hybrid = [load(group / arm / 'result.json') for arm in ('cosil', 'sfpruner')]
            shared = load(group / 'shared.json') if (group / 'shared.json').exists() else {}
            if shared.get('files') != original.get('file_rank_after_reflection') or shared.get('raw_file_responses') != original.get('raw_file_responses'):
                complaint(errors, 'shared_file_stage_not_exact_baseline', iid)
            if hybrid.get('raw_file_responses') != original.get('raw_file_responses'):
                complaint(errors, 'hybrid_file_stage_not_exact_baseline', iid)
    if not errors and not pending:
        for arm in ARMS:
            if not deliveries[arm]:
                pending.append(arm + ': no actual source-to-search delivery observed in fixed canary; natural behavior is not an engineering failure')
    status = 'FAIL' if errors else 'PENDING' if pending else 'PASS'
    return {'schema': 1, 'status': status, 'scope': 'fixed first3 x three arms, engineering only',
        'canary_ids': expected_ids, 'cases': cases, 'errors': errors, 'pending': pending,
        'source_checks': source_checks, 'actual_source_delivery_counts': dict(deliveries),
        'execution_commit': freeze.get('commit'), 'execution_freeze_sha256': sha(freeze_path),
        'allocation_sha256': sha(allocation_path), 'gold_read': False, 'accuracy_used': False,
        'gate_written': False, 'models_called_or_started': False,
        'recommendation': 'Root may review this evidence and create its separate engineering gate; this audit never creates that gate.',
        'audit_source_sha256': sha(__file__), 'time': time.time()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(strict=True), args.out.resolve()
    if not out.is_relative_to(root / 'audits') or out.name == 'canary_engineering_gate.json':
        raise ValueError('Write only a separate review under RUN/audits; never the controller gate')
    result = review(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name('.' + out.name + '.' + str(os.getpid()))
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, out)
    print(json.dumps({'status': result['status'], 'errors': len(result['errors']),
                      'pending': result.get('pending', []), 'review': str(out)}, ensure_ascii=False))
    return 2 if result['status'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
