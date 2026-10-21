"""Dedicated offline evaluation. Never import this module from an online worker.

Only the explicit Lite-50 private label files are opened, in build_report/main.
Pure scoring/statistical helpers and synthetic tests do not read private labels.
Historical controllers, reporting.run, inference, dispatch, and test seals are
never invoked. All derived label-bearing outputs stay under RUN/reports.
"""
from __future__ import annotations

import csv
import hashlib
import tokenize
import io
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from analysis.evaluation_extension import normalize_functions
from src.metrics import scores, mrr
from .common import ROOT, RUN, OLD, utc
from .protocol import DSML_REFERENCE

HISTORICAL = ('D-SIMPLE', 'D-COSIL', 'Q-COSIL', 'Q-PRUNER')
ARMS = ('A-SIGNATURE', 'A-FULL')
STRUCTURED = ('D-COSIL-STRUCTURED', 'Q-COSIL-STRUCTURED', 'Q-PRUNER-STRUCTURED')
METRICS = ('hit_1', 'hit_3', 'hit_5', 'recall_5', 'all_coverage_5', 'mrr_10')
SEED = 20261021
BOOTSTRAPS = 10000
PENDING = {'NOT_RUN', 'BLOCKED_FAIRNESS'}


def load_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.is_file() else default


def load_lines(path):
    path = Path(path)
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.is_file() else []


def load_csv(path):
    path = Path(path)
    if not path.is_file():
        return []
    rows = []
    for row in csv.DictReader(io.StringIO(path.read_text())):
        for key, value in row.items():
            if value in ('True', 'False'):
                row[key] = value == 'True'
            elif value and value[:1] in '[{':
                try:
                    row[key] = json.loads(value)
                except ValueError:
                    pass
        rows.append(row)
    return rows


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def write_csv(path, rows, empty_fields=('status',)):
    fields = list(dict.fromkeys(k for row in rows for k in row)) or list(empty_fields)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v
                         for k, v in row.items()})
    Path(path).write_text(stream.getvalue())


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def describe(values):
    values = [v for v in values if v is not None]
    return {'mean': mean(values), 'median': statistics.median(values) if values else None,
            'p90': float(np.quantile(values, .9)) if values else None}


def metric_values(raw, index, targets, status='complete'):
    """Historical final identity normalizer; duplicate/invalid slots never compact."""
    slots, invalid = normalize_functions(raw, index)
    result = {'normalized_function_slots': slots, 'invalid_function_count': invalid,
              'duplicate_function_count': len([x for x in slots if x is not None]) - len(set(x for x in slots if x is not None))}
    for k in (1, 3, 5, 10):
        for name, value in scores(slots, targets, k).items():
            result[name + '_' + str(k)] = None if status in PENDING else value
    result['mrr_10'] = None if status in PENDING else mrr(slots, targets)
    result['final_invalid_or_empty'] = not any(s is not None for s in slots)
    return result


def exact_mcnemar(wins, losses):
    n = wins + losses
    return min(1., 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n) if n else 1.


def paired_statistics(pairs, metric, *, bootstraps=BOOTSTRAPS, seed=SEED):
    """Metric-specific wins; explicitly separate the binary Hit@5 four cells."""
    hit5_cells = {
        'a_win_b_lose': sum(a['hit_5'] > b['hit_5'] for a, b in pairs),
        'a_lose_b_win': sum(a['hit_5'] < b['hit_5'] for a, b in pairs),
        'both_correct': sum(a['hit_5'] == b['hit_5'] == 1 for a, b in pairs),
        'both_wrong': sum(a['hit_5'] == b['hit_5'] == 0 for a, b in pairs),
    }
    if not pairs:
        return {'paired_strict_n': 0, 'mean_difference': None, 'issue_bootstrap95': [None, None],
                'repo_cluster_bootstrap95': [None, None], 'a_win_b_lose': 0, 'a_lose_b_win': 0,
                'ties': 0, 'both_correct': 0 if metric == 'hit_5' else None,
                'both_wrong': 0 if metric == 'hit_5' else None,
                'hit5_four_cells': hit5_cells, 'McNemar_exact_two_sided': None}
    delta = np.array([a[metric] - b[metric] for a, b in pairs], dtype=float)
    rng = np.random.default_rng(seed)
    issue = delta[rng.integers(0, len(delta), size=(bootstraps, len(delta)))].mean(axis=1)
    byrepo = defaultdict(list)
    for (a, b), value in zip(pairs, delta):
        byrepo[a['repo']].append(value)
    repos = sorted(byrepo)
    sums = np.array([sum(byrepo[r]) for r in repos]); sizes = np.array([len(byrepo[r]) for r in repos])
    choices = rng.integers(0, len(repos), size=(bootstraps, len(repos)))
    cluster = sums[choices].sum(axis=1) / sizes[choices].sum(axis=1)
    wins = sum(a[metric] > b[metric] for a, b in pairs)
    losses = sum(a[metric] < b[metric] for a, b in pairs)
    return {'paired_strict_n': len(pairs), 'mean_difference': float(delta.mean()),
            'issue_bootstrap95': [float(x) for x in np.quantile(issue, [.025, .975])],
            'repo_cluster_bootstrap95': [float(x) for x in np.quantile(cluster, [.025, .975])],
            'a_win_b_lose': wins, 'a_lose_b_win': losses, 'ties': len(pairs) - wins - losses,
            'both_correct': hit5_cells['both_correct'] if metric == 'hit_5' else None,
            'both_wrong': hit5_cells['both_wrong'] if metric == 'hit_5' else None,
            'hit5_four_cells': hit5_cells,
            'McNemar_exact_two_sided': exact_mcnemar(hit5_cells['a_win_b_lose'], hit5_cells['a_lose_b_win']) if metric == 'hit_5' else None}


def coverage_audit(frozen, targets, index):
    """Label access is confined to this offline audit; never change candidates."""
    identities = {c['identity'] for c in frozen['candidates']}
    whole = set(frozen['manifest']['loaded_whole_files'])
    grep = frozen['manifest']['excluded_grep_evidence']
    candidate = [g for g in targets if g in identities]
    complete = [g for g in targets if g.split('::', 1)[0] in whole]
    grep_only, partial = [], []
    for identity in targets:
        path, qn = identity.split('::', 1)
        if path in whole:
            continue
        definitions = [d for d in index.get(path, {}).get('definitions', [])
                       if d['kind'] == 'function' and d['qualified_name'] == qn]
        spans = [b for b in grep if b['path'] == path]
        if any(b['start_line'] <= d['start_line'] and b['end_line'] >= d['end_line'] for b in spans for d in definitions):
            grep_only.append(identity)
        elif any(b['end_line'] >= d['start_line'] and b['start_line'] <= d['end_line'] for b in spans for d in definitions):
            partial.append(identity)
    return {'gold_function_count': len(set(targets)), 'candidate_gold_count': len(set(candidate)),
            'candidate_gold_recall': len(set(candidate)) / len(set(targets)) if targets else None,
            'candidate_all_gold_covered': int(set(targets) <= identities) if targets else None,
            'full_file_gold_count': len(set(complete)),
            'full_file_gold_recall': len(set(complete)) / len(set(targets)) if targets else None,
            'gold_only_in_excluded_grep': grep_only, 'gold_partial_in_excluded_grep': partial,
            'full_files': frozen['manifest']['loaded_whole_files'],
            'candidate_count': len(frozen['candidates']), 'candidate_sha256': frozen['manifest']['candidate_sha256']}


def receipts(folder, method, *, budget=None, historical=False):
    """Only observed request IDs are aggregated; unknown billing stays separate."""
    rows, seen = [], set()
    for call in sorted((Path(folder) / 'calls').glob('*')):
        evidence = sorted(call.glob('attempt_*_receipt.json')) + sorted(call.glob('attempt_*_error.json'))
        completed = {p.name.rsplit('_', 1)[0] for p in evidence}
        evidence += [p for p in sorted(call.glob('attempt_*_started.json')) if p.name.rsplit('_', 1)[0] not in completed]
        for path in evidence:
            row = load_json(path); request_id = row.get('request_id')
            if not request_id or request_id in seen:
                continue
            seen.add(request_id)
            usage = row.get('usage') or {}
            paid = method.startswith(('D-', 'A-'))
            normalized = row.get('api_cost_usd_normalized')
            if normalized is None and paid and usage:
                normalized = (usage.get('prompt_tokens', 0) * .3 + usage.get('completion_tokens', 0) * 1.2) / 1e6
            reserve = (budget or {}).get('attempts', {}).get(request_id, {})
            rows.append({'method': method, 'model_method_requested': row.get('method'),
                'instance_id': row.get('instance_id'), 'request_id': request_id, 'stage': row.get('stage'),
                'sequence': row.get('sequence'), 'attempt': row.get('attempt'),
                'prompt_tokens': usage.get('prompt_tokens', 0), 'completion_tokens': usage.get('completion_tokens', 0),
                'prompt_cache_hit_tokens': usage.get('prompt_cache_hit_tokens'),
                'api_cost_usd_actual': row.get('api_cost_usd_actual') if paid else None,
                'api_cost_usd_normalized_peak_no_cache': normalized if paid else None,
                'charged_or_reserved_upper_usd': reserve.get('charged_upper_usd'),
                'billing_unknown': bool(paid and not usage), 'price_tier': row.get('price_tier'),
                'http_status': row.get('http_status'), 'finish_reason': row.get('finish_reason'),
                'thinking_mode': row.get('thinking_mode'), 'max_output_tokens': row.get('max_output_tokens'),
                'start_utc': row.get('start_utc'), 'end_utc': row.get('end_utc'),
                'elapsed_seconds': row.get('attempt_elapsed_seconds'), 'request_sha256': row.get('request_sha256'),
                'receipt_artifact': str(path), 'scope': 'historical_pipeline' if historical else 'new_diagnostic_only'})
    return rows


def navigation_usage(ledger, local_usage, *, paid):
    """Same suffix on both sides: node/pruner/final only, never file/init."""
    calls = [r for r in ledger if r.get('stage') in ('node_selection', 'pruner', 'final_summary')]
    node_starts = [r['start_utc'] for r in calls if r.get('stage') == 'node_selection' and r.get('start_utc')]
    final_ends = [r['end_utc'] for r in calls if r.get('stage') == 'final_summary' and r.get('end_utc')]
    ends = final_ends or [r['end_utc'] for r in calls if r.get('end_utc')]
    start, end = min(node_starts, default=None), max(ends, default=None)
    elapsed = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() if start and end else None
    closed = all(r.get('end_utc') is not None for r in calls)
    tokens_in = sum(r.get('prompt_tokens', 0) for r in calls)
    tokens_out = sum(r.get('completion_tokens', 0) for r in calls)
    return {'navigation_http_input_tokens': tokens_in, 'navigation_http_output_tokens': tokens_out,
            'navigation_total_model_input_tokens': tokens_in + local_usage.get('small_judge_input_tokens', 0),
            'navigation_total_model_output_tokens': tokens_out + local_usage.get('small_judge_output_tokens', 0),
            'navigation_api_cost_usd_actual_known': sum(r.get('api_cost_usd_actual') or 0 for r in calls) if paid else None,
            'navigation_api_cost_usd_normalized_peak_no_cache': sum(r.get('api_cost_usd_normalized_peak_no_cache') or 0 for r in calls) if paid else None,
            'navigation_request_count': len(calls),
            'navigation_billing_unknown_attempts': sum(bool(r.get('billing_unknown')) for r in calls),
            'navigation_interval_started_utc': start, 'navigation_interval_ended_utc': end,
            'navigation_measured_interval_seconds': elapsed if closed else None,
            'navigation_interval_lower_bound_seconds': elapsed if not closed else None, 'navigation_interval_closed': closed,
            'navigation_interval_end_kind': 'final_summary_end' if final_ends else 'last_observed_navigation_attempt_end' if ends else 'no_observed_navigation_end',
            'navigation_resource_scope': 'node_selection_pruner_final_summary_only_excludes_file_and_initial_selection'}


def _verify_returned_source(event, folder, job=None, index=None):
    """Match recorded bytes against every legal base span, including properties."""
    if job is None or index is None:
        return bool(event.get('exact_base_span_available')), 'declared_unique_base_span_without_offline_artifact_check'
    source_id = event.get('source_id', '')
    if not source_id or Path(source_id).name != source_id:
        return False, 'invalid_source_artifact_key'
    artifact = load_json(Path(folder) / 'sources' / (source_id + '.json'))
    if not artifact or not isinstance(artifact.get('text'), str):
        return False, 'missing_recorded_source_artifact'
    text = artifact['text']
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    if digest(text) != event.get('source_sha256') or digest(text) != artifact.get('sha256'):
        return False, 'recorded_source_sha_mismatch'
    path, arguments = artifact.get('path'), artifact.get('arguments', [])
    if path not in index or not arguments or arguments[0] != path:
        return False, 'source_path_or_arguments_not_in_base_index'
    snapshot = Path(job['snapshot']).resolve()
    source_path = snapshot / path
    if not source_path.resolve().is_relative_to(snapshot):
        return False, 'source_path_outside_base_snapshot'
    raw = source_path.read_bytes()
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    source = raw.decode(encoding)
    if index[path].get('sha256') and digest(source) != index[path]['sha256']:
        return False, 'base_source_index_sha_mismatch'
    name = '.'.join(arguments[1:])
    kind = 'class' if artifact.get('tool') == 'get_code_of_class' else 'function'
    definitions = [d for d in index[path].get('definitions', [])
                   if d['kind'] == kind and d['qualified_name'] == name]
    for definition in definitions:
        span = ''.join(source.splitlines(keepends=True)[definition['start_line'] - 1:definition['end_line']])
        if any(digest(candidate) == digest(text) for candidate in (span, span.rstrip('\r\n'), '\n'.join(span.splitlines()))):
            return True, 'recorded_sha_matches_one_of_base_identity_spans'
    return False, 'recorded_source_does_not_match_any_base_identity_span'


def structured_calls(folder, method, iid, events, *, job=None, index=None):
    """Keep byte presence observations separate from same-action delivery.

    A source may occur in a later class body or an older accepted retrieval.
    Those observations do not prove that the current action delivered it.
    """
    rows, seen, errors, hashes = [], set(), set(), set()
    positions = {id(event): position for position, event in enumerate(events)}
    http_events = [e for e in events if e['event'] == 'http_request_effective']

    def round_of(event):
        return event.get('step', event.get('navigation_round'))

    def effective_request(visible, after, purpose):
        if visible.get('purpose') not in purpose:
            return False
        for request in http_events:
            if not (after < positions[id(request)] <= positions[id(visible)]):
                continue
            if request.get('purpose') != visible.get('purpose'):
                continue
            shared = [key for key in ('request_id', 'sequence', 'request_sha256')
                      if request.get(key) is not None and visible.get(key) is not None]
            if shared and all(request[key] == visible[key] for key in shared):
                return True
        return False

    for event in [e for e in events if e['event'] == 'raw_model_tool_output']:
        step = round_of(event)
        group = [e for e in events if round_of(e) == step]
        parsed = next((e for e in group if e['event'] == 'parsed_tool_call'), None)
        resolution = next((e.get('target_resolution', {}) for e in group if e['event'] == 'target_resolution'), {})
        ios = [e for e in group if e['event'] == 'tool_io_audit']
        sources = [e for e in group if e['event'] == 'source_returned']
        ids = {e['source_id'] for e in sources}
        returned_at = min((positions[id(e)] for e in sources), default=len(events))
        judges = [e for e in events if e['event'] == 'judge_seen' and e.get('source_id') in ids]
        agents = [e for e in events if e['event'] == 'agent_seen' and e.get('source_id') in ids]
        same_action_judges = [e for e in judges if round_of(e) == step and positions[id(e)] > returned_at]
        main = [e for e in same_action_judges if e.get('recipient') == 'main_judge'
                and e.get('full_source_in_request') and effective_request(e, returned_at, ('pruner',))]
        small = [e for e in same_action_judges if e.get('recipient') == 'small_judge' and e.get('full_source_in_request')]
        accepts = [e for e in group if e['event'] == 'context_accept' and parsed
                   and e.get('tool') == parsed.get('tool') and e.get('arguments') == parsed.get('arguments')
                   and positions[id(e)] > returned_at]
        accepted_at = min((positions[id(e)] for e in accepts), default=len(events))
        delivered = [e for e in agents if e.get('full_source_in_request')
                     and positions[id(e)] > accepted_at
                     and effective_request(e, accepted_at, ('node_selection', 'final_summary'))]
        verified = [_verify_returned_source(e, folder, job, index) for e in sources]
        key = json.dumps([parsed.get('tool'), parsed.get('arguments')] if parsed else None, sort_keys=True)
        tool_error = any(e['event'] == 'tool_error' for e in group)
        sha = [e.get('source_sha256') for e in sources]
        row = {'scope': 'new_structured', 'method': method, 'instance_id': iid, 'step': step,
               'raw_model_output': event['raw_model_tool_output'], 'events_artifact': str(Path(folder) / 'events.jsonl'),
               'syntax_contract_valid': parsed is not None, 'canonical_tool': parsed.get('tool') if parsed else None,
               'arguments': parsed.get('arguments') if parsed else None, 'target_resolution': resolution,
               'target_exists': resolution.get('target_exists'), 'executed': any(e.get('executed') for e in ios),
               'execution_success': any(e.get('success') for e in ios), 'source_returned': bool(sources),
               'source_ids': sorted(ids), 'source_sha_valid': any(v[0] for v in verified),
               'source_verification': [v[1] for v in verified],
               'main_judge_byte_visible_full_source': any(e.get('recipient') == 'main_judge' and e.get('full_source_in_request') for e in judges),
               'small_judge_byte_visible_full_source': any(e.get('recipient') == 'small_judge' and e.get('full_source_in_request') for e in judges),
               'agent_byte_visible_full_source': any(e.get('full_source_in_request') for e in agents),
               'main_judge_seen_full_source': bool(main), 'small_judge_seen_full_source': bool(small),
               'agent_seen_full_source': bool(delivered), 'context_accept_same_action': bool(accepts),
               'delivery_definition': 'same_action_judge_or_accept_then_later_effective_agent_request',
               'repeated_same_arguments': bool(parsed and key in seen),
               'repeated_previous_error_arguments': bool(parsed and key in errors),
               'repeated_source': any(s in hashes for s in sha),
               'category': 'response_parse_failure' if not parsed else 'explicit_exit' if parsed.get('tool') == 'exit'
                    else 'target_failure' if resolution.get('target_exists') is False else 'tool_runtime_failure' if tool_error
                    else 'executed_source_success' if sources else 'executed_metadata_success',
               'actual_reject': any(e['event'] == 'context_reject' for e in group),
               'small_judge_route': next((e.get('route') for e in group if e['event'] == 'small_judge'), None),
               'native_tool_call': False}
        row['judge_seen_full_source'] = bool(main or small)
        rows.append(row)
        if parsed:
            seen.add(key)
        if tool_error or resolution.get('target_exists') is False:
            errors.add(key)
        hashes.update(sha)
    return rows


def local_judge_usage(events):
    small = [e for e in events if e['event'] == 'small_judge']
    setup = [e for e in events if e['event'] == 'local_judge_setup']
    load = sum(e.get('judge_load_seconds', 0) for e in setup) if setup else sum(e.get('model_load_seconds', 0) for e in small if e.get('first_prediction'))
    return {'small_judge_input_tokens': sum(e.get('input_tokens', 0) for e in small),
            'small_judge_output_tokens': sum(e.get('generated_output_tokens', 0) for e in small),
            'small_judge_forward_sync_wall_seconds': sum(e.get('forward_seconds', 0) for e in small),
            'small_judge_load_wall_seconds': load,
            'base_graph_and_render_setup_wall_seconds': sum(e.get('base_graph_and_render_setup_seconds', 0) for e in setup),
            'small_judge_calls': len(small)}


def service_phase_accounting(run):
    rows = []
    for phase in ('smoke', 'full'):
        folder = Path(run) / 'service/phase_history' / phase
        owned = load_json(folder / 'owned_process.json', {})
        startup = load_json(folder / 'startup_timing.json', {})
        stopped = load_json(folder / 'shutdown.json', {})
        if not owned and not startup and not stopped:
            continue
        start = owned.get('started_at'); end = stopped.get('time', stopped.get('stopped_at'))
        allocated = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() if start and end else None
        rows.append({'phase': phase, 'gpu': 'GPU0', 'process_started_utc': start, 'process_stopped_utc': end,
                     'owned_process_allocated_wall_seconds': allocated, 'startup_wall_seconds': startup.get('seconds'),
                     'measurement': 'owned_service_process_allocation_wall_not_gpu_kernel_seconds',
                     'evidence_directory': str(folder)})
    return rows


def mechanism_counts(calls, events, result):
    def count(key):
        return sum(bool(c.get(key)) for c in calls)
    syntax = sum(bool(c.get('syntax_contract_valid', (c.get('strict_dsl') or {}).get('valid', c.get('historical_parsed')))) for c in calls)
    target_calls = [c for c in calls if c.get('canonical_tool') and c['canonical_tool'] != 'exit']
    first = [int(c['step']) + 1 for c in calls if c.get('source_returned') and c.get('step') is not None]
    return {'actions': len(calls), 'syntax_valid': syntax, 'syntax_valid_rate': syntax / len(calls) if calls else None,
            'target_proposals': len(target_calls), 'target_exists': sum(bool(c.get('target_exists')) for c in target_calls),
            'executions': count('executed'), 'execution_successes': count('execution_success'),
            'source_returned_count': count('source_returned'), 'source_returned_issue': count('source_returned') > 0,
            'main_judge_seen_full_source_count': count('main_judge_seen_full_source'),
            'small_judge_seen_full_source_count': count('small_judge_seen_full_source'),
            'agent_seen_full_source_count': count('agent_seen_full_source'),
            'agent_byte_visible_full_source_count': count('agent_byte_visible_full_source'),
            'main_judge_byte_visible_full_source_count': count('main_judge_byte_visible_full_source'),
            'small_judge_byte_visible_full_source_count': count('small_judge_byte_visible_full_source'),
            'agent_seen_full_source_issue': count('agent_seen_full_source') > 0,
            'returned_but_agent_unseen_count': sum(bool(c.get('source_returned')) and not c.get('agent_seen_full_source') for c in calls),
            'repeated_error_count': count('repeated_previous_error_arguments'), 'repeated_source_count': count('repeated_source'),
            'first_source_return_round': min(first) if first else None,
            'navigation_round_limit_reached': len(calls) >= 10 and not any(c.get('canonical_tool') == 'exit' for c in calls),
            'entered_search': bool(result.get('entered_search')) or any(e['event'] == 'search_start' for e in events),
            'context_budget_events': sum(e['event'] == 'context_budget' for e in events)}


def direct_prune(calls, targets, index):
    """Actual gold-identity rejects; distinguish full delivery and shared spans."""
    hits = []
    for row in calls:
        if not (row.get('actual_reject') and row.get('source_returned')):
            continue
        if not row.get('source_sha_valid'):
            continue
        args, tool = row.get('arguments') or [], row.get('canonical_tool')
        if not args:
            continue
        path = args[0]
        if tool == 'get_code_of_class':
            prefix = args[1] + '.'
            names = [d['qualified_name'] for d in index.get(path, {}).get('definitions', [])
                     if d['kind'] == 'function' and d['qualified_name'].startswith(prefix)]
        elif tool in ('get_code_of_class_function', 'get_code_of_file_function'):
            names = ['.'.join(args[1:])]
        else:
            names = []
        matched = sorted(set(path + '::' + q for q in names) & set(targets))
        if matched:
            route = row.get('small_judge_route')
            reject_route = 'small_router_reject' if route == 'reject' else 'gray_to_main_reject' if route == 'qwen' else 'main_judge_reject' if route is None else 'unknown_route'
            shared = [identity for identity in matched if sum(d['kind'] == 'function' and d['qualified_name'] == identity.split('::', 1)[1] for d in index.get(path, {}).get('definitions', [])) > 1]
            hits.append({'step': row.get('step'), 'gold_identities': matched, 'evidence': row.get('events_artifact'),
                         'reject_route': reject_route, 'full_judge_source_delivered': bool(row.get('judge_seen_full_source')),
                         'shared_qualified_name_identities': shared, 'modified_span_verified': False,
                         'qualification': 'actual_reject_recorded_base_source_gold_path_qualified_name_identity'})
    return hits


def summarize(rows, *, population='all_allocated'):
    selected = rows if population == 'all_allocated' else [r for r in rows if r['entered_search']] if population == 'entered_search' else [r for r in rows if r['status'] == 'complete']
    strict = [r for r in selected if r['gold_mapping_status'] == 'fully_mappable']
    observed = [r for r in selected if r['status'] not in PENDING]
    result = {'method': rows[0]['method'], 'scope': rows[0]['scope'], 'population': population,
              'allocated_n': len(rows), 'population_n': len(selected), 'observed_n': len(observed),
              'completed_n': sum(r['status'] == 'complete' for r in selected),
              'strict_n': len(strict), 'partial_n': sum(r['gold_mapping_status'] == 'partially_mappable' for r in selected),
              'unmapped_n': sum(r['gold_mapping_status'] == 'unmappable' for r in selected),
              'statuses': dict(Counter(r['status'] for r in selected)),
              'pending_n': sum(r['status'] in PENDING for r in selected),
              'metric_status': 'COMPLETE' if selected and len(observed) == len(selected) else 'INCOMPLETE_OR_NOT_RUN',
              'time_scope': rows[0]['time_scope']}
    for metric in METRICS:
        result[metric] = mean([r[metric] if r[metric] is not None else 0 for r in strict]) if observed else None
    partial = [r for r in selected if r['gold_mapping_status'] == 'partially_mappable']
    result['partial_hit_5'] = mean([r['hit_5'] if r['hit_5'] is not None else 0 for r in partial]) if observed else None
    for field in ('elapsed_seconds', 'input_tokens', 'output_tokens', 'api_cost_usd_actual_known', 'api_cost_usd_normalized_peak_no_cache',
                  'small_judge_input_tokens', 'small_judge_output_tokens', 'total_model_input_tokens',
                  'total_model_output_tokens', 'small_judge_forward_sync_wall_seconds', 'small_judge_load_wall_seconds',
                  'base_graph_and_render_setup_wall_seconds'):
        for stat, value in describe([r[field] for r in observed]).items():
            result[field + '_' + stat] = value
    for field in ('actions', 'syntax_valid', 'target_proposals', 'target_exists', 'executions', 'execution_successes',
                  'source_returned_count', 'agent_seen_full_source_count', 'main_judge_seen_full_source_count',
                  'small_judge_seen_full_source_count', 'agent_byte_visible_full_source_count',
                  'main_judge_byte_visible_full_source_count', 'small_judge_byte_visible_full_source_count', 'returned_but_agent_unseen_count', 'repeated_error_count',
                  'repeated_source_count', 'input_tokens', 'output_tokens', 'billing_unknown_attempts', 'gold_direct_prune_count',
                  'gold_reject_full_judge_delivery_count', 'gold_small_router_reject_count', 'gold_gray_to_main_reject_count', 'gold_main_judge_reject_count',
                  'api_search_input_tokens', 'api_search_output_tokens', 'small_judge_input_tokens', 'small_judge_output_tokens',
                  'total_model_input_tokens', 'total_model_output_tokens', 'small_judge_forward_sync_wall_seconds', 'small_judge_calls',
                  'small_judge_load_wall_seconds', 'base_graph_and_render_setup_wall_seconds'):
        result[field] = sum(r.get(field, 0) or 0 for r in observed)
    for name, numerator, denominator in (('syntax_contract_rate', 'syntax_valid', 'actions'),
            ('target_exists_rate', 'target_exists', 'target_proposals'),
            ('execution_success_rate', 'execution_successes', 'executions'),
            ('effective_tool_proposal_rate', 'execution_successes', 'actions')):
        result[name] = result[numerator] / result[denominator] if result[denominator] else None
    result['agent_received_source_issues'] = sum(r['agent_seen_full_source_issue'] for r in observed)
    result['source_returned_issues'] = sum(r['source_returned_issue'] for r in observed)
    result['final_invalid_output_rate'] = mean([int(r['final_invalid_or_empty']) for r in observed])
    result['file_start_identical_rate'] = mean([int(r['file_start_identical']) for r in observed if r['scope'] == 'new_structured'])
    result['first_source_return_round_mean'] = mean([r['first_source_return_round'] for r in observed])
    result['api_cost_usd_actual_known'] = sum(r['api_cost_usd_actual_known'] or 0 for r in observed) if any(r['api_paid'] for r in observed) else None
    result['api_cost_usd_normalized_peak_no_cache'] = sum(r['api_cost_usd_normalized_peak_no_cache'] or 0 for r in observed) if any(r['api_paid'] for r in observed) else None
    return result


def paired_table(rows, method_a, method_b, population='all_allocated'):
    a = {r['instance_id']: r for r in rows if r['method'] == method_a}
    b = {r['instance_id']: r for r in rows if r['method'] == method_b}
    pairs = [(a[i], b[i]) for i in a if i in b and a[i]['gold_mapping_status'] == 'fully_mappable']
    if population == 'entered_search':
        pairs = [(x, y) for x, y in pairs if x['entered_search'] and y['entered_search']]
    elif population == 'completed':
        pairs = [(x, y) for x, y in pairs if x['status'] == y['status'] == 'complete']
    pending = any(x['status'] in PENDING or y['status'] in PENDING for x, y in pairs)
    output = []
    for metric in METRICS:
        stat = paired_statistics([] if pending else pairs, metric)
        stat.update(method_a=method_a, method_b=method_b, direction='method_a_minus_method_b',
                    metric=metric, population=population, allocated_strict_pairs=len(pairs),
                    comparison_status='INCOMPLETE_NOT_RUN_PRESENT' if pending else 'COMPLETE',
                    exploratory_multiple_metrics=True, equivalence_claim=False, bootstrap_seed=SEED)
        output.append(stat)
    return output


def b2_matched_tables(rows, b2_ids):
    """Descriptive mechanism/resource comparison on the same preregistered IDs."""
    ids = set(b2_ids)
    summaries, paired = [], []
    mechanisms = ('actions', 'syntax_valid', 'syntax_valid_rate', 'target_exists_rate', 'execution_success_rate',
                  'effective_tool_proposal_rate', 'target_proposals', 'target_exists',
                  'executions', 'execution_successes', 'source_returned_count', 'source_returned_issue',
                  'main_judge_seen_full_source_count', 'small_judge_seen_full_source_count',
                  'agent_seen_full_source_count', 'agent_seen_full_source_issue', 'returned_but_agent_unseen_count',
                  'repeated_error_count', 'repeated_source_count', 'first_source_return_round',
                  'final_invalid_or_empty', 'hit_5', 'recall_5')
    resources = ('navigation_http_input_tokens', 'navigation_http_output_tokens',
                 'navigation_total_model_input_tokens', 'navigation_total_model_output_tokens',
                 'navigation_api_cost_usd_actual_known', 'navigation_api_cost_usd_normalized_peak_no_cache',
                 'navigation_request_count', 'navigation_billing_unknown_attempts',
                 'navigation_measured_interval_seconds', 'small_judge_forward_sync_wall_seconds',
                 'small_judge_load_wall_seconds', 'base_graph_and_render_setup_wall_seconds')
    for variant in STRUCTURED:
        base = variant.removesuffix('-STRUCTURED')
        selected = [r for r in rows if r['instance_id'] in ids and r['method'] in (base, variant)]
        for method in (base, variant):
            method_rows = [r for r in selected if r['method'] == method]
            if not method_rows:
                continue
            for population in ('all_allocated', 'entered_search', 'completed'):
                summary = summarize(method_rows, population=population)
                # Whole historical pipeline vs new resumed elapsed stay in original
                # tables; only same-navigation resources appear as comparable here.
                unpaired_prefixes = ('elapsed_seconds', 'input_tokens', 'output_tokens', 'api_cost_usd',
                                     'total_model_input_tokens', 'total_model_output_tokens', 'api_search_')
                summary = {k: v for k, v in summary.items() if not k.startswith(unpaired_prefixes)}
                summary.update(cohort='fixed_b2_ids_same_issues_each_methods_own_historical_start',
                    cohort_n=len(ids), baseline_method=base,
                    original_elapsed_scope=method_rows[0]['time_scope'],
                    time_scope='first_node_attempt_start_to_final_or_last_navigation_receipt_end',
                    conditional_population='each_methods_own_entered_or_completed; pairwise_common_filters_are_separate')
                population_rows = method_rows if population == 'all_allocated' else [r for r in method_rows if r['entered_search']] if population == 'entered_search' else [r for r in method_rows if r['status'] == 'complete']
                observed = [r for r in population_rows if r['status'] not in PENDING]
                for field in resources:
                    values = [r.get(field) for r in observed]
                    summary[field + '_observed_n'] = sum(v is not None for v in values)
                    summary[field + '_sum'] = sum(v for v in values if v is not None) if any(v is not None for v in values) else None
                    for stat, value in describe(values).items():
                        summary[field + '_' + stat] = value
                summaries.append(summary)
        old = {r['instance_id']: r for r in selected if r['method'] == base}
        new = {r['instance_id']: r for r in selected if r['method'] == variant}
        for iid in sorted(ids):
            if iid not in old or iid not in new:
                continue
            a, b = new[iid], old[iid]
            row = {'instance_id': iid, 'repo': a['repo'], 'baseline_method': base, 'new_method': variant,
                   'cohort': 'fixed_b2_ids_same_issue_pairs', 'old_status': b['status'], 'new_status': a['status'],
                   'old_entered_search': b['entered_search'], 'new_entered_search': a['entered_search'],
                   'both_entered_search': a['entered_search'] and b['entered_search'],
                   'both_completed': a['status'] == b['status'] == 'complete',
                   'old_whole_pipeline_elapsed_seconds': b['elapsed_seconds'],
                   'new_resumed_pipeline_elapsed_seconds': a['elapsed_seconds'],
                   'pipeline_elapsed_comparable': False,
                   'old_navigation_interval_end_kind': b.get('navigation_interval_end_kind'),
                   'new_navigation_interval_end_kind': a.get('navigation_interval_end_kind'),
                   'old_navigation_interval_closed': b.get('navigation_interval_closed'),
                   'new_navigation_interval_closed': a.get('navigation_interval_closed'),
                   'descriptive_only_no_additional_inference': True}
            for field in (*mechanisms, *resources):
                before, after = b.get(field), a.get(field)
                rate_fields = {'target_exists_rate': ('target_exists', 'target_proposals'),
                               'execution_success_rate': ('execution_successes', 'executions'),
                               'effective_tool_proposal_rate': ('execution_successes', 'actions')}
                if field in rate_fields:
                    numerator, denominator = rate_fields[field]
                    before = b.get(numerator, 0) / b[denominator] if b.get(denominator) else None
                    after = a.get(numerator, 0) / a[denominator] if a.get(denominator) else None
                row[field + '_old'], row[field + '_new'] = before, after
                row[field + '_new_minus_old'] = after - before if before is not None and after is not None else None
            paired.append(row)
    return summaries, paired


def build_report(run=RUN, old=OLD, root=ROOT, *, expected_reference=None):
    """Call in a dedicated CPU process; tests supply an entirely synthetic root."""
    run, old, root = Path(run), Path(old), Path(root)
    output = run / 'reports'; output.mkdir(parents=True, exist_ok=True)
    manifest = load_json(run / 'run_manifest.json')
    if manifest is None:
        raise RuntimeError('Missing preregistered run manifest')
    recs = manifest['records']; b2_ids = set(manifest['b2_ids'])
    audit_calls = load_csv(run / 'audit/tool_protocol_per_call.csv')
    for row in audit_calls:
        row['scope'] = 'historical'
    audit_summary = load_json(run / 'audit/summary.json', {})
    budget = load_json(run / 'budget.json', {'attempts': {}, 'stage_cap_usd': 3.})
    per_issue, coverage, ledger, protocol, gold_rejections = [], [], [], list(audit_calls), []
    for rec in recs:
        iid = rec['instance_id']
        if not isinstance(iid, str) or '/' in iid or '\\' in iid or iid in ('', '.', '..'):
            raise ValueError('Invalid explicit issue key')
        # This is the only private-label read in the entire diagnostic package.
        label_path = root / 'evaluator_private' / iid / 'gold.json'
        gold = load_json(label_path)
        if gold is None:
            raise RuntimeError('Missing existing private mapping: ' + str(label_path))
        targets = gold['gold_functions']; job = load_json(rec['job']); index = load_json(job['code_index'])
        frozen = load_json(run / 'frozen' / iid / 'frozen_context.json')
        cov = coverage_audit(frozen, targets, index)
        coverage.append({'instance_id': iid, 'repo': rec['repo'], 'gold_mapping_status': gold['mapping_status'], **cov})
        variants = [*HISTORICAL, *ARMS, 'D-COSIL-ADAPTER', *(STRUCTURED if iid in b2_ids else ())]
        for method in variants:
            historical = method in HISTORICAL
            folder = (old if historical else run) / 'lite_pilot' / method / iid
            result = load_json(folder / 'result.json', {'status': 'BLOCKED_FAIRNESS' if method == 'D-COSIL-ADAPTER' else 'NOT_RUN', 'predicted_functions': []})
            events = load_lines(folder / 'events.jsonl')
            calls = [dict(c) for c in audit_calls if c['method'] == method and c['instance_id'] == iid] if historical else structured_calls(folder, method, iid, events, job=job, index=index) if method in STRUCTURED else []
            if not historical:
                protocol.extend(calls)
            issue_ledger = receipts(folder, method, budget=budget, historical=historical)
            if not historical:
                ledger.extend(issue_ledger)
            metrics = metric_values(result.get('predicted_functions', []), index, targets, result['status'])
            mechanism = mechanism_counts(calls, events, result)
            local_usage = local_judge_usage(events)
            for call in calls:
                step = int(call['step']) if call.get('step') is not None else None
                call['small_judge_route'] = next((e.get('route') for e in events if e['event'] == 'small_judge' and e.get('step', e.get('navigation_round')) == step), call.get('small_judge_route'))
            direct = direct_prune(calls, targets, index)
            gold_rejections.extend({'method': method, 'instance_id': iid, **d} for d in direct)
            upstream = load_json(run / 'upstream' / method.removesuffix('-STRUCTURED') / iid / 'upstream_status.json', {}) if method in STRUCTURED else {}
            file_audit = load_json(folder / 'frozen_state_audit.json', {})
            file_start_identical = bool(file_audit.get('file_start_identical')) or (result['status'] == 'upstream_failure' and result.get('predicted_files', result.get('ranked_edit_files', [])) == upstream.get('files'))
            paid = method.startswith(('D-', 'A-'))
            row = {'method': method, 'instance_id': iid, 'repo': rec['repo'], 'base_commit': rec['base_commit'],
                'scope': 'historical' if historical else 'new_ablation' if method in ARMS else 'blocked_adapter' if method == 'D-COSIL-ADAPTER' else 'new_structured',
                'status': result['status'], 'gold_mapping_status': gold['mapping_status'],
                'gold_function_count': len(set(targets)), 'gold_group': 'single' if len(set(targets)) == 1 else 'multiple' if targets else 'unmapped',
                'elapsed_seconds': result.get('elapsed_seconds'),
                'time_scope': 'historical_whole_localization_pipeline' if historical else 'final_ranking_only' if method in ARMS else 'frozen_initial_state_to_final_ranking',
                'input_tokens': sum(x['prompt_tokens'] for x in issue_ledger),
                'output_tokens': sum(x['completion_tokens'] for x in issue_ledger),
                'api_cost_usd_actual_known': sum(x['api_cost_usd_actual'] or 0 for x in issue_ledger) if paid else None,
                'api_cost_usd_normalized_peak_no_cache': sum(x['api_cost_usd_normalized_peak_no_cache'] or 0 for x in issue_ledger) if paid else None,
                'api_paid': paid, 'local_gpu_cost_usd': None, 'direct_gpu_compute_seconds': None,
                'billing_unknown_attempts': sum(x['billing_unknown'] for x in issue_ledger),
                'request_count': len(issue_ledger), 'successful_semantic_responses': sum(x['http_status'] == 200 and x['finish_reason'] == 'stop' for x in issue_ledger),
                'file_start_identical': file_start_identical, 'file_start_expected': upstream.get('files'),
                'file_start_actual': file_audit.get('files'), 'error_type': result.get('error_type'),
                'error_message': result.get('error_message', result.get('reason')), 'raw_artifact_path': str(folder),
                'gold_direct_prune_count': len(direct),
                'gold_reject_full_judge_delivery_count': sum(d['full_judge_source_delivered'] for d in direct),
                'gold_small_router_reject_count': sum(d['reject_route'] == 'small_router_reject' for d in direct),
                'gold_gray_to_main_reject_count': sum(d['reject_route'] == 'gray_to_main_reject' for d in direct),
                'gold_main_judge_reject_count': sum(d['reject_route'] == 'main_judge_reject' for d in direct), **metrics, **mechanism, **local_usage}
            row.update(navigation_usage(issue_ledger, local_usage, paid=paid))
            row['api_search_input_tokens'] = row['input_tokens']
            row['api_search_output_tokens'] = row['output_tokens']
            row['total_model_input_tokens'] = row['input_tokens'] + row['small_judge_input_tokens']
            row['total_model_output_tokens'] = row['output_tokens'] + row['small_judge_output_tokens']
            if method in ARMS:
                row.update({k: cov[k] for k in ('candidate_gold_recall', 'full_file_gold_recall', 'candidate_all_gold_covered')})
                context = result.get('context_stats', {})
                row.update(context_o200k_tokens=context.get('context_o200k_tokens'), candidate_sha256=cov['candidate_sha256'])
                delivered = method == 'A-FULL' and any(x['http_status'] == 200 for x in issue_ledger)
                row['actual_full_source_delivered'] = delivered
                row['actual_full_source_gold_recall'] = cov['full_file_gold_recall'] if delivered else 0 if targets else None
            row['failure_layer'] = ('not_run' if result['status'] in PENDING else 'upstream_not_entered' if method in (*STRUCTURED, *HISTORICAL[1:]) and not row['entered_search']
                else 'calls_failed_before_source' if calls and not row['source_returned_issue']
                else 'source_returned_agent_unseen' if row['source_returned_issue'] and not row['agent_seen_full_source_issue']
                else 'agent_saw_source_still_wrong' if row['agent_seen_full_source_issue'] and metrics['hit_5'] == 0
                else 'context_overflow' if result['status'] == 'context_overflow'
                else 'candidate_coverage_failure' if method in ARMS and cov['candidate_all_gold_covered'] == 0
                else 'ranked_correct' if metrics['hit_5'] == 1 else 'currently_cannot_distinguish')
            per_issue.append(row)
    # New requests alone; reject rather than silently double-count a reused ID.
    unique = {}
    for row in ledger:
        if row['request_id'] in unique and unique[row['request_id']] != row:
            raise RuntimeError('Conflicting new request_id in cost ledger')
        unique[row['request_id']] = row
    ledger = list(unique.values())
    methods = [*HISTORICAL, *ARMS, 'D-COSIL-ADAPTER', *STRUCTURED]
    summary = []
    for method in methods:
        rows = [r for r in per_issue if r['method'] == method]
        if not rows:
            continue
        populations = ('all_allocated', 'entered_search', 'completed') if method in (*STRUCTURED, 'D-COSIL', 'Q-COSIL', 'Q-PRUNER') else ('all_allocated', 'completed')
        summary.extend(summarize(rows, population=p) for p in populations)
    reproduction = {}
    for method in HISTORICAL:
        rs = [r for r in per_issue if r['method'] == method]
        strict = [r for r in rs if r['gold_mapping_status'] == 'fully_mappable']
        reproduction[method] = {'strict_n': len(strict), 'strict_hit5': sum(r['hit_5'] for r in strict),
                               'partial_n': sum(r['gold_mapping_status'] == 'partially_mappable' for r in rs),
                               'unmapped_n': sum(r['gold_mapping_status'] == 'unmappable' for r in rs)}
    if expected_reference is not None:
        for method, expected_hits in expected_reference.items():
            actual = reproduction[method]
            if actual != {'strict_n': 41, 'strict_hit5': expected_hits, 'partial_n': 7, 'unmapped_n': 2}:
                raise RuntimeError('Historical final evaluator reproduction failed: ' + method + ' ' + str(actual))
    paired = paired_table(per_issue, 'A-FULL', 'A-SIGNATURE') + paired_table(per_issue, 'A-FULL', 'A-SIGNATURE', 'completed')
    for method in STRUCTURED:
        for population in ('all_allocated', 'entered_search', 'completed'):
            paired.extend(paired_table(per_issue, method, method.removesuffix('-STRUCTURED'), population))
    a_index = {(r['method'], r['instance_id']): r for r in per_issue if r['method'] in ARMS}
    ablation = []
    for rec in recs:
        a, b = a_index['A-FULL', rec['instance_id']], a_index['A-SIGNATURE', rec['instance_id']]
        ablation.append({'instance_id': rec['instance_id'], 'repo': rec['repo'], 'gold_mapping_status': a['gold_mapping_status'],
            'full_status': a['status'], 'signature_status': b['status'], 'gold_function_count': a['gold_function_count'],
            'pair_state_hit5': 'NOT_RUN' if a['status'] in PENDING or b['status'] in PENDING else 'NA' if a['hit_5'] is None
                 else 'FULL_win' if a['hit_5'] > b['hit_5'] else 'SIGNATURE_win' if a['hit_5'] < b['hit_5'] else 'both_correct' if a['hit_5'] else 'both_wrong',
            **{metric + '_full_minus_signature': a[metric] - b[metric] if a[metric] is not None and b[metric] is not None else None for metric in METRICS},
            **{field + '_full_minus_signature': a[field] - b[field] for field in ('input_tokens', 'output_tokens', 'api_cost_usd_actual_known', 'api_cost_usd_normalized_peak_no_cache')},
            'candidate_gold_recall': a.get('candidate_gold_recall'), 'full_file_gold_recall': a.get('full_file_gold_recall')})
    grouped = []
    for method in methods:
        rs = [r for r in per_issue if r['method'] == method and r['gold_mapping_status'] == 'fully_mappable']
        for dimension in ('repo', 'gold_group', 'failure_layer'):
            for group in sorted({r[dimension] for r in rs}):
                xs = [r for r in rs if r[dimension] == group]
                grouped.append({'method': method, 'dimension': dimension, 'group': group, 'strict_n': len(xs),
                                'observed_n': sum(r['status'] not in PENDING for r in xs),
                                **{metric: mean([r[metric] for r in xs]) for metric in METRICS}})
    matched_summary, mechanism_pairs = b2_matched_tables(per_issue, b2_ids)
    write_csv(output / 'b2_matched_method_summary.csv', matched_summary)
    write_csv(output / 'b2_mechanism_pairwise.csv', mechanism_pairs)
    write_csv(output / 'per_issue.csv', per_issue)
    write_csv(output / 'method_summary.csv', summary)
    write_csv(output / 'paired_comparisons.csv', paired)
    write_csv(output / 'ablation_pairwise.csv', ablation)
    write_csv(output / 'cost_ledger.csv', ledger, ('method', 'instance_id', 'request_id', 'scope'))
    write_csv(output / 'tool_protocol_per_call.csv', protocol)
    taxonomy = load_csv(run / 'audit/tool_failure_taxonomy.csv')
    taxonomy.extend(c for c in protocol if c.get('scope') == 'new_structured')
    write_csv(output / 'tool_failure_taxonomy.csv', taxonomy)
    write_csv(output / 'coverage_offline_audit.csv', coverage)
    write_csv(output / 'grouped_metrics.csv', grouped)
    write_csv(output / 'gold_direct_prune_offline.csv', gold_rejections)
    write_json(output / 'baseline_reproduction.json', reproduction)
    service_phases = service_phase_accounting(run)
    write_csv(output / 'service_phase_accounting.csv', service_phases)
    wire_order = Counter()
    for rec in recs:
        starts = {arm: min((x['start_utc'] for x in ledger if x['method'] == arm and x['instance_id'] == rec['instance_id'] and x.get('start_utc')), default=None) for arm in ARMS}
        if all(starts.values()):
            wire_order['SIGNATURE_first' if starts[ARMS[0]] < starts[ARMS[1]] else 'FULL_first' if starts[ARMS[1]] < starts[ARMS[0]] else 'same_recorded_start'] += 1
        else:
            wire_order['no_paired_wire_receipt'] += 1
    payload = {'generated_at': utc(), 'b2_matched_summary': matched_summary, 'service_phase_accounting': service_phases, 'ablation_wire_order': dict(wire_order), 'summary': summary, 'paired': paired, 'historical_reproduction': reproduction,
               'audit_summary': audit_summary, 'new_cost_known_actual_usd': sum(r['api_cost_usd_actual'] or 0 for r in ledger),
               'new_cost_normalized_peak_no_cache_usd': sum(r['api_cost_usd_normalized_peak_no_cache'] or 0 for r in ledger),
               'new_billing_unknown_attempts': sum(r['billing_unknown'] for r in ledger),
               'charged_or_reserved_upper_usd': sum(a['charged_upper_usd'] for a in budget.get('attempts', {}).values()),
               'independent_budget_cap_usd': budget.get('stage_cap_usd'), 'new_request_count': len(ledger),
               'coverage': coverage, 'b2_n': len(b2_ids), 'allocated_n': len(recs),
               'actual_full_source_gold_recall_macro_strict': mean([r.get('actual_full_source_gold_recall') for r in per_issue if r['method'] == 'A-FULL' and r['gold_mapping_status'] == 'fully_mappable'])}
    write_json(output / 'evaluation_summary.json', payload)
    render_report(output, payload, per_issue, ablation, grouped)
    return payload


def pct(value):
    return 'NA' if value is None else f'{100 * value:.2f}%'


def pp(value):
    return 'NA' if value is None else f'{100 * value:+.2f} pp'


def interval_pp(values):
    return 'NA' if not values or any(v is None for v in values) else f'[{100 * values[0]:+.2f}, {100 * values[1]:+.2f}] pp'


def number(value):
    return 'NA' if value is None else f'{value:.6g}'


def render_report(output, data, rows, ablation, grouped):
    summary, paired = data['summary'], data['paired']
    arm_rows = {arm: [r for r in rows if r['method'] == arm] for arm in ARMS}
    strict_arms = {arm: [r for r in arm_rows[arm] if r['gold_mapping_status'] == 'fully_mappable'] for arm in ARMS}
    a_hits = {arm: sum(r['hit_5'] or 0 for r in strict_arms[arm]) for arm in ARMS}
    a_effects = {p['metric']: p for p in paired if p['method_a'] == 'A-FULL' and p['population'] == 'all_allocated'}
    hit5_effect, hit1_effect = a_effects.get('hit_5', {}), a_effects.get('hit_1', {})
    a_conclusion = (f"A严格主分母：签名 {a_hits['A-SIGNATURE']}/{len(strict_arms['A-SIGNATURE'])} → 完整源码 {a_hits['A-FULL']}/{len(strict_arms['A-FULL'])}，Hit@5差 {pp(hit5_effect.get('mean_difference'))}；Hit@1差 {pp(hit1_effect.get('mean_difference'))}。"
                    + f"Hit@5精确McNemar p={number(hit5_effect.get('McNemar_exact_two_sided'))}，issue 95%CI {interval_pp(hit5_effect.get('issue_bootstrap95'))}；当前不能认定显著改善，也不能因未显著而认为等效。")
    paired_ids = set(r['instance_id'] for r in arm_rows['A-SIGNATURE'] if r['status'] == 'complete') & set(r['instance_id'] for r in arm_rows['A-FULL'] if r['status'] == 'complete')
    success_arms = {arm: [r for r in arm_rows[arm] if r['instance_id'] in paired_ids] for arm in ARMS}
    success_strict_n = sum(r['gold_mapping_status'] == 'fully_mappable' for r in success_arms['A-FULL'])
    def total(items, field):
        return sum(r.get(field) or 0 for r in items)
    def ratio(numerator, denominator):
        return 'NA' if not denominator else f'{numerator / denominator:.3f}×'
    def total_mean_median(items, field, money=False):
        values = [r.get(field) for r in items if r.get(field) is not None]
        if not values:
            return 'NA'
        values = [sum(values), mean(values), statistics.median(values)]
        return '/'.join(f'{v:.9f}' if money else number(v) for v in values)
    def mean_median(items, field):
        values = [r.get(field) for r in items if r.get(field) is not None]
        return 'NA' if not values else number(mean(values)) + '/' + number(statistics.median(values))
    matched = {s['method']: s for s in data['b2_matched_summary'] if s['population'] == 'all_allocated'}
    b2_conclusions = []
    b2_chain_details = []
    for variant in STRUCTURED:
        base = variant.removesuffix('-STRUCTURED')
        before, after = matched.get(base), matched.get(variant)
        if not before or not after:
            continue
        effect = next((p for p in paired if p['method_a'] == variant and p['population'] == 'all_allocated' and p['metric'] == 'hit_5'), {})
        old_hit = 'NA' if before['hit_5'] is None else str(round(before['hit_5'] * before['strict_n']))
        new_hit = 'NA' if after['hit_5'] is None else str(round(after['hit_5'] * after['strict_n']))
        b2_conclusions.append(f"{base} {old_hit}/{before['strict_n']} → {new_hit}/{after['strict_n']}（精确p={number(effect.get('McNemar_exact_two_sided'))}）")
        b2_chain_details.append(f"{base}：整段严格合约 {pct(before['syntax_contract_rate'])}→{pct(after['syntax_contract_rate'])}；真实执行/动作 {before['executions']}/{before['actions']}→{after['executions']}/{after['actions']}；成功返回源码 {before['source_returned_count']}→{after['source_returned_count']}；Agent完整源码题 {before['agent_received_source_issues']}/{before['allocated_n']}→{after['agent_received_source_issues']}/{after['allocated_n']}。")
    b2_complete = all(matched.get(v, {}).get('observed_n', 0) == matched.get(v, {}).get('allocated_n', -1) > 0 for v in STRUCTURED)
    b2_effect_text = ('D侧源码取回增加而Hit@5未增加；Q/Q-PRUNER各增加一个命中，三项精确McNemar p均为1.0，没有显著配对证据。严格格式检查率上升不能推导工具更有效或稳定定位收益，尤其Q侧执行与源码传递可能下降；现有证据不足以归因工具能力改善。' if b2_complete else 'B2仍有未运行项，暂不下最终收益结论；严格格式通过率与实际执行/传递分别报告。')
    observed_prunes = sum(s['gold_direct_prune_count'] for s in summary if s['population'] == 'all_allocated')
    cpu = load_json(Path(output).parent / 'cpu_tests.json', {})
    cpu_match = re.search(r'Ran (\d+) tests?', cpu.get('output', ''))
    cpu_note = ('CPU测试' + cpu_match.group(1) + '项全部通过。') if cpu.get('passed') and cpu_match else 'CPU测试证据见新run/cpu_tests.json。'
    shutdown_note = '本轮GPU0/2自有模型进程已关闭，服务退出归档见phase_history。' if data['service_phase_accounting'] and all(p.get('process_stopped_utc') for p in data['service_phase_accounting']) else '自有服务退出证据见service/phase_history。'
    lines = ['# 函数签名与工具协议开发诊断', '', '生成时间：' + data['generated_at'] + '。本报告仅依据现有落盘产物；未运行项保留分配数并标注 NOT_RUN。', '',
        '## 一页结果', '', a_conclusion, '', '| 方法 | 分配/观测/完成 | 严格N | Hit@1 | Hit@3 | Hit@5 | Macro-Recall@5 | AllCoverage@5 | MRR@10 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        if s['population'] == 'all_allocated':
            lines.append(f"| {s['method']} | {s['allocated_n']}/{s['observed_n']}/{s['completed_n']} | {s['strict_n']} | " + ' | '.join(pct(s[k]) for k in METRICS) + ' |')
    lines += ['', '未完成批次的 all_allocated 数字将待运行题暂记零，属于当前累计下界；配对推断在存在 NOT_RUN 时不计算。context_overflow、上游失败及实际请求失败计入主分母。7道部分可映射题的辅助指标只评分可映射函数子集，不代表该题完整gold召回；2道不可映射题标NA。41题严格主分母包含实际运行失败。', '',
              '历史最终评价器由 analysis/evaluation_extension.py 提供精确 path::qualified_name 身份；同名property多span共享ID，重复和无效预测占原排名槽，评分集合交集不去除槽位。未调用任何会覆盖旧报告的历史入口。', '',
              '历史原始输出离线复算：' + '；'.join(f"{m} {v['strict_hit5']}/{v['strict_n']}" for m, v in data['historical_reproduction'].items()) + '。', '',
              '## 甲：完整源码相对签名的增量', '', a_conclusion, '',
              '上游固定原50题D-SIMPLE的实际 loaded_whole_files，不按gold、grep或原最终预测补选。两臂相同候选、路径顺序、排名指令、模型和采样；仅完整源码块有无不同。全部grep来源块都排除，即使原complete_file=true。AST保留nested/async/property/重复定义；默认值和注解表达式统一160字符长度限制，原始源码不截断。', '',
              '80K o200k cap约束路径+候选+源码context，不含共同system和Issue。A共分配100个最终排序臂，预登记97个可发送请求、3个FULL上下文溢出；溢出仍保留在主分母。', '',
              '| FULL−SIGNATURE指标 | 配对严格N | 差值(pp) | issue bootstrap95%(pp) | 仓cluster95%(pp) | 精确McNemar p |',
              '|---|---:|---:|---|---|---:|']
    for p in paired:
        if p['method_a'] == 'A-FULL' and p['population'] == 'all_allocated':
            lines.append(f"| {p['metric']} | {p['allocated_strict_pairs']} | {pp(p['mean_difference'])} | {interval_pp(p['issue_bootstrap95'])} | {interval_pp(p['repo_cluster_bootstrap95'])} | {number(p['McNemar_exact_two_sided'])} |")
    states = Counter(x['pair_state_hit5'] for x in ablation if x['gold_mapping_status'] == 'fully_mappable')
    lines += ['', 'Hit@5同题四格：' + json.dumps(dict(states), ensure_ascii=False) + '。条件双方成功子表见 paired_comparisons.csv 的 completed，严格取同题双方完成交集，不能替代全体分母。method_summary.csv 的单臂completed各用自身完成题分母，不作为配对效应。10,000次重采样，seed=20261021；多个指标均为探索性，不因p>0.05或区间跨零声称等效。', '']
    lines += [f"全分配{data['allocated_n']}题资源：SIGNATURE输入token {int(total(arm_rows['A-SIGNATURE'], 'input_tokens')):,}，FULL {int(total(arm_rows['A-FULL'], 'input_tokens')):,}，总量FULL/SIGNATURE={ratio(total(arm_rows['A-FULL'], 'input_tokens'), total(arm_rows['A-SIGNATURE'], 'input_tokens'))}；FULL有{sum(r['status'] == 'context_overflow' for r in arm_rows['A-FULL'])}题未发送，输入和费用记零，这个总量比包含该分配策略代价。",
              f"双方成功同题{len(paired_ids)}对（其中严格{success_strict_n}对）的输入token：SIGNATURE {int(total(success_arms['A-SIGNATURE'], 'input_tokens')):,}，FULL {int(total(success_arms['A-FULL'], 'input_tokens')):,}，FULL/SIGNATURE={ratio(total(success_arms['A-FULL'], 'input_tokens'), total(success_arms['A-SIGNATURE'], 'input_tokens'))}。下面把这组同题资源与全分配口径分开列出；严格条件定位指标仍只用双方成功严格交集。", '',
              '| 资源群体 | 臂 | N/有请求记录 | 输入token 总/mean/median | 输出token 总/mean/median | 费率推算USD 总/mean/median | 最终阶段处理秒 mean/median |',
              '|---|---|---:|---:|---:|---:|---:|']
    for group, groups in ((f'全分配{data["allocated_n"]}题（含未发送）', arm_rows), (f'双方成功{len(paired_ids)}同题对', success_arms)):
        for arm in ARMS:
            items = groups[arm]
            lines.append(f"| {group} | {arm} | {len(items)}/{sum(r['request_count'] > 0 for r in items)} | {total_mean_median(items, 'input_tokens')} | {total_mean_median(items, 'output_tokens')} | {total_mean_median(items, 'api_cost_usd_actual_known', True)} | {mean_median(items, 'elapsed_seconds')} |")
    lines += ['', '全分配均值以每臂全部分配题为分母；未发送溢出的输入/费用为零，处理墙钟仍可能有准备开销。双方成功均值/中位数严格使用同一批issue，不把单臂各自completed样本混作配对。', '']
    cov = [c for c in data['coverage'] if c['gold_mapping_status'] == 'fully_mappable']
    lines += [f"严格41题（实际{len(cov)}）候选gold Macro覆盖率 {pct(mean([c['candidate_gold_recall'] for c in cov]))}，整文件gold Macro覆盖率 {pct(mean([c['full_file_gold_recall'] for c in cov]))}；所有gold均在候选内的题数 {sum(c['candidate_all_gold_covered'] or 0 for c in cov)}/{len(cov)}。",
              f"有gold仅完整出现在被排除grep证据的题数 {sum(bool(c['gold_only_in_excluded_grep']) for c in cov)}；身份和源码span证据仅在私有离线coverage_offline_audit.csv中列出，未反馈给模型或候选构建。", '',
              'FULL实际成功送达请求的整文件gold覆盖（溢出/未发送记零）Macro均值：' + pct(data['actual_full_source_gold_recall_macro_strict']) + '。',
              '任务提交顺序按SHA奇偶交替，但4线程并发不能保证真实wire先后平衡；按首次attempt receipt开始时间记录：' + json.dumps(data['ablation_wire_order'], ensure_ascii=False) + '。',
              '完整源码天生增加输入token；这里只能解释为增加完整源码信息的增量及其代价，不能直接归因于深层语义理解或等token预算。按仓库和单/多函数gold分组见 grouped_metrics.csv。', '',
              '## 乙：工具格式、参数与真实收益', '',
              '同一固定20题的严格可映射子集比较：' + '；'.join(b2_conclusions) + '。',
              b2_effect_text, '', *b2_chain_details, '']
    audit = data['audit_summary']
    lines += ['[DeepSeek官方DSML编码约定](' + DSML_REFERENCE + ')规定单U+FF5C分隔标签；本轮严格遵照原文，不归一化重复分隔符。', '']
    if audit:
        dsml = audit.get('dsml', {})
        lines += [f"B0零API静态审计复现历史动作。DSML候选 {dsml.get('all_candidates', 'NA')}，严格官方单U+FF5C标签可接受 {dsml.get('strict_canonical_accepted', 'NA')}；旧43段是重复双U+FF5C标签被旧审计正则归一化后的宽松结构诊断，不能追认为严格可解析或历史执行。", '',
                  '| 历史方法 | 动作 | 原解析失败 | 执行/成功 | 严格DSL可接受 | 源码返回 | Agent有效请求见完整源码 |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for method, x in audit.get('methods', {}).items():
            lines.append(f"| {method} | {x.get('actions')} | {x.get('parse_failures')} | {x.get('executions')}/{x.get('execution_successes')} | {x.get('strict_dsl_valid')} | {x.get('source_returned')} | {x.get('agent_seen_full_source')} |")
    else:
        lines += ['B0审计产物尚未完成；不能以预期数字冒充实测。']
    lines += ['', 'B1状态 BLOCKED_FAIRNESS，未进行在线D-COSIL-ADAPTER。原历史解析允许自由文本夹带一次DSL；新严格完整响应DSL仅275条可接受，原解析通过330条（含退出）。把严格DSL和DSML同时换入会改变超过accept_strict_dsml一个开关，构成混杂；68段DSML又全部不符合严格标签，不能自动修复后称为纯格式兼容。B1不能提供在线定位增益结论。', '',
              f"B2预登记同一固定{data['b2_n']}题，三个方法各自复用对应历史方法的文件起点及初始状态，不能声称不同模型统一了文件起点。实际协议是严格文本JSON，native tool_calls=False；约束由prompt加本地parser实现，provider json_mode=False且未发送response_format，未启用服务端JSON-schema/grammar constrained decoding。不能据fence失败断言Qwen不支持服务器JSON模式；服务器约束能力仍需另行独立验证。本轮是接口方案对照，轨迹变化不能全部归因parser。", '',
              '| 方法/群体 | 分配/群体/完成 | Hit@5 | 语法合约率 | 目标存在率 | 执行成功率 | Agent收到源码题数 | 起点同自身历史 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        if s['method'] in STRUCTURED:
            lines.append(f"| {s['method']}/{s['population']} | {s['allocated_n']}/{s['population_n']}/{s['completed_n']} | {pct(s['hit_5'])} | {pct(s['syntax_contract_rate'])} | {pct(s['target_exists_rate'])} | {pct(s['execution_success_rate'])} | {s['agent_received_source_issues']} | {pct(s['file_start_identical_rate'])} |")
    lines += ['', 'B2还显式声明原dispatcher已支持的第五个canonical工具 get_functions_of_class；原TOOL_REQUEST只示四个。这没有扩执行白名单，但提高了已有元数据工具可见性，属于接口表示/约束差异，不能视为纯parser因果效应。', '',
              '各B2方法与自身历史的all_allocated/entered_search/completed配对差、有效工具提议率、首次源码轮次、重复错误和最终无效输出率详见 method_summary.csv / paired_comparisons.csv；进入搜索前失败保留，不用重新选文件掩盖。完整源码返回、主裁判见到、小裁判见到、搜索Agent下一次有效请求收到分别统计。原始seen事件只证明字节在某请求中可见；离线因果送达口径要求judge对应本次retrieval同轮/source_id，Agent还须同step/tool/args的context_accept及之后有效node/final请求全字节可见。较早接受的同源码或后续class正文包含旧函数，只记byte_visible观察，不算该次reject动作送达。', '',
              '## B2同题机制与资源对照（固定20，历史50另保留）', '',
              '| 方法 | 同题分配/观测 | 整段严格合约率 | 真实执行/动作 | 目标存在率 | 执行成功率 | Agent见源码题数 | 导航HTTP输入累计 | 导航USD实际/峰未缓存 | 导航区间秒mean/median/p90 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
              *[f"| {s['method']} | {s['allocated_n']}/{s['observed_n']} | {pct(s['syntax_contract_rate'])} | {s['executions']}/{s['actions']} ({pct(s['executions'] / s['actions'] if s['actions'] else None)}) | {pct(s['target_exists_rate'])} | {pct(s['execution_success_rate'])} | {s['agent_received_source_issues']} | {number(s['navigation_http_input_tokens_sum'])} | {number(s['navigation_api_cost_usd_actual_known_sum'])}/{number(s['navigation_api_cost_usd_normalized_peak_no_cache_sum'])} | " + '/'.join(number(s['navigation_measured_interval_seconds_' + x]) for x in ('mean', 'median', 'p90')) + ' |' for s in data['b2_matched_summary'] if s['population'] == 'all_allocated'], '',
              '整段严格格式合约是离线按完整响应检查DSL或JSON；历史运行parser允许fence/prose夹带单次DSL，所以严格合约率与历史实际接受/执行率是两种口径，不能互相替代。b2_matched_method_summary.csv仅取冻结b2_ids中的同20题；旧方法全50的B0综合审计保留。all_allocated、entered_search和completed分别列出，后两者是各自条件分母；逐题配对b2_mechanism_pairwise.csv另标双方进入/完成，不把不同条件分母当同题效应。', '',
              '导航资源两侧均只计node_selection/pruner/final_summary回执，排除file/initial_selection。导航墙钟从首个node attempt开始至末个final_summary回执结束；未到final时取末次已观察导航回执结束并标记边界/是否闭合。本次elapsed与旧whole-pipeline elapsed均保留但不可直接比较；模型加载、CPU构图和小裁判同步前向wall另列，不宣称相对于历史完整流程的节省。回执实际价格时段不同，峰时未缓存归一列用于区分token资源与价格折扣，不能把折扣归因于协议。区间均值/分位数只对可观察完整边界计算，CSV另列每字段observed_n。这里仅做descriptive配对，不扩大检验。', '',
              '## 丙：剩余失败机制与可辨识边界', '',
              '| 方法 | 进入前失败 | 调用后无源码 | 返回但Agent未见 | Agent见源码仍Hit@5错 |',
              '|---|---:|---:|---:|---:|']
    for method in (*HISTORICAL[1:], *STRUCTURED):
        count = Counter(r['failure_layer'] for r in rows if r['method'] == method)
        lines.append('| ' + method + ' | ' + ' | '.join(str(count[k]) for k in ('upstream_not_entered', 'calls_failed_before_source', 'source_returned_agent_unseen', 'agent_saw_source_still_wrong')) + ' |')
    lines += ['', '分类描述可观测事件链，不能仅凭执行成功宣称定位改善。gold_direct_prune只计实际源码返回、源码SHA可核且真实reject对应gold path::QN身份；另列裁判完整收到源码子集，并按小裁判router reject、gray→主裁判reject、直接主裁判reject区分。源未取回、文件选择漏召回均不是误剪。重复QN只说明gold身份被拒，未核实gold修改span，不称实际修改实现被剪。hash有效不等于源码完整；小裁判部分/不同span输入单列。对于“Agent见了某些源码仍选错”，现有证据通常不能区分模型推断、搜索策略或未读到真正根因；目前不能区分。', '',
              '## gold身份实际reject：离线归因边界', '',
              f'当前观察到{observed_prunes}个gold身份实际reject；零次观察不代表裁判安全：gold可能根本未被选择/取回，或传递证据不足，无法据此评价见到真实修改源码后的误剪风险。', '',
              '| 方法 | 小router reject | gray→主reject | 主judge reject | 其中完整judge送达 |',
              '|---|---:|---:|---:|---:|',
              *[f"| {s['method']} | {s['gold_small_router_reject_count']} | {s['gold_gray_to_main_reject_count']} | {s['gold_main_judge_reject_count']} | {s['gold_reject_full_judge_delivery_count']} |" for s in summary if s['population'] == 'all_allocated' and s['method'] in (*HISTORICAL[1:], *STRUCTURED)], '',
              '## 费用、时间与计算范围', '',
              f"本轮新增请求 {data['new_request_count']}；按usage/缓存/时段费率推算API USD ${data['new_cost_known_actual_usd']:.9f}，峰时未缓存归一USD ${data['new_cost_normalized_peak_no_cache_usd']:.6f}；未知计费请求 {data['new_billing_unknown_attempts']}，保守已记/预约上界 ${data['charged_or_reserved_upper_usd']:.6f}，独立硬限 ${data['independent_budget_cap_usd']:.2f}。这是费用推算而非逐笔账单；旧run费用未并入cost_ledger.csv。", '',
              '| 方法 | 计时范围 | 秒mean/median/p90 | HTTP输入token mean/median/p90 | HTTP输出token mean/median/p90 | 费率推算USD | 峰时未缓存USD |',
              '|---|---|---:|---:|---:|---:|---:|']
    for s in summary:
        if s['population'] != 'all_allocated':
            continue
        def triple(field):
            return '/'.join(number(s[field + '_' + x]) for x in ('mean', 'median', 'p90'))
        lines.append(f"| {s['method']} | {s['time_scope']} | {triple('elapsed_seconds')} | {triple('input_tokens')} | {triple('output_tokens')} | {number(s['api_cost_usd_actual_known'])} | {number(s['api_cost_usd_normalized_peak_no_cache'])} |")
    lines += ['', 'A为最终排序阶段，B2为冻结初始搜索状态后至最终排序，历史为完整定位流水线；这些墙钟不能直接作等阶段速度比较。价格与版本依据2026-10-21核验的[DeepSeek官方价格页](https://api-docs.deepseek.com/quick_start/pricing/)：峰时输入miss/hit/输出分别USD0.3/0.006/1.2每百万token，off_peak乘0.5。表中USD直接使用API费率，7 CNY/USD仅沿用预算换算，不把美元结果再解释为人民币。off_peak实际费用与峰时未缓存归一费用分别保留；未知缓存/计费不伪报精确账单。Qwen/小裁判的USD空值不表示零成本，直接GPU计算秒未测得标NA，服务启动另见service记录。', '',
              '## 本地小裁判计算与全部模型token', '',
              '| 方法 | 分配/观测N | HTTP输入累计 | 小裁判输入累计 | 全部模型输入累计 | 小裁判输出累计 | 每题累计同步forward wall秒 总计/mean/median/p90 |',
              '|---|---:|---:|---:|---:|---:|---:|',
              *[f"| {s['method']} | {s['allocated_n']}/{s['observed_n']} | {s['input_tokens']} | {s['small_judge_input_tokens']} | {s['total_model_input_tokens']} | {s['small_judge_output_tokens']} | {number(s['small_judge_forward_sync_wall_seconds'])}/" + '/'.join(number(s['small_judge_forward_sync_wall_seconds_' + x]) for x in ('mean', 'median', 'p90')) + ' |' for s in summary if s['population'] == 'all_allocated'], '',
              'HTTP与小裁判使用各自tokenizer；累计总数是资源记账之和，不能当作同tokenizer等预算。表中mean/median/p90是每个已观测分配issue的累计forward墙钟分布，含0次判决题（历史50题、新B2 20题，N见表），不是单次prediction时延。小裁判forward_seconds包含CUDA同步前后墙钟，是已观测本地前向时间，不是GPU kernel计算秒；不把其token纳入DeepSeek美元账单。小裁判加载及CPU建图/渲染耗时在method_summary另列，不能把HTTP请求重叠耗时相加当GPU计算时间。', '',
              '| 新服务阶段 | GPU0 owned进程allocated wall秒 | 启动wall秒 |', '|---|---:|---:|',
              *[f"| {s['phase']} | {number(s['owned_process_allocated_wall_seconds'])} | {number(s['startup_wall_seconds'])} |" for s in data['service_phase_accounting']], '',
              '服务驻留范围由phase_history内自有进程开始至shutdown记录，属于allocated wall，不是GPU kernel秒。smoke/full分别归档，避免服务记录replace造成漏计。', '',
              '## 复现与限制', '',
              f"历史D-SIMPLE {data['historical_reproduction']['D-SIMPLE']['strict_hit5']}/{data['historical_reproduction']['D-SIMPLE']['strict_n']}包含原grep证据及旧prompt，也没有本次完全相同的显式候选函数清单，仅作观察参照；不能把它与A-FULL {a_hits['A-FULL']}/{len(strict_arms['A-FULL'])}的差异归因于源码。D-SIMPLE是CQ2-inspired流程的函数级扩展，不是论文官方函数定位方法，也没有验证修复率。", '',
              '本轮仅Lite公开开发诊断，不能宣称外部泛化或修复率。没有重跑上游文件选择/grep，不执行历史模型工具输出，不碰封存holdout/裁判test，不训练、不跑修复测试或SWE-rebench。DeepSeek显式thinking=disabled，模型别名deepseek-flash及文档版本DeepSeek-V4.1-Flash-1017保留于配置/回执。请求未固定DeepSeek seed，API别名不能独立锁定服务端权重快照；不冒称完全确定性或可逐字复现模型输出。', '',
              cpu_note + ' ' + shutdown_note, '',
              'CPU测试与独立离线报告命令见 README_如何复现.md。旧预测、gold映射及历史报告均只读；本报告可重建更新当前快照。']
    (output / 'final_diagnostic_report.md').write_text('\n'.join(lines) + '\n')
    readme = '''# 如何复现本轮诊断

以工程根目录为工作目录，使用原CPU环境。先执行CPU测试：

```bash
PYTHONDONTWRITEBYTECODE=1 /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m unittest discover -s context_tool_diagnostic -p 'test_*.py' -v
```

仅在A全部分配题已落盘后，在独立进程生成离线报告：

```bash
PYTHONDONTWRITEBYTECODE=1 /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m context_tool_diagnostic.evaluate
```

也可用主CLI的 `--phase report`；该命令必须由独立控制进程调用，在线worker不导入评价器。评价只读原50题既有evaluator_private/<iid>/gold.json，所有含标签派生产物只写新RUN/reports，该目录在worker中隐藏。报告运行不调用API、模型、工具执行或历史报告main。历史严格身份入口为analysis.evaluation_extension.normalize_functions，统计函数来自src.metrics。

run_manifest.json冻结50题、SHA256前5冒烟和固定20题B2子集；resolved_config.yaml冻结模型/非思考/上下文边界。A-SIGNATURE与A-FULL仅源码区块不同；FULL超80K标context_overflow且不截断。原结果仅为观察参照。41题严格主分母包含实际失败；7题partial辅助指标只评分可映射函数子集，不代表整题完整gold召回，2题unmappable为NA。DeepSeek请求未固定seed，API别名不能独立锁定服务端权重快照。B1因严格DSL与旧宽松提取不等价而BLOCKED_FAIRNESS。B2是严格文本JSON，不能称native tool_calls。

必需CSV：ablation_pairwise、per_issue、method_summary、paired_comparisons、cost_ledger、tool_failure_taxonomy、tool_protocol_per_call；另有coverage_offline_audit、grouped_metrics、gold_direct_prune_offline和baseline_reproduction.json。B2同题机制/资源比较见b2_matched_method_summary.csv和b2_mechanism_pairwise.csv，旧与新均限定同20题、导航stage回执；旧全流程和新恢复阶段elapsed不能直接作节省比较。cost_ledger只含本轮新增请求。NOT_RUN与实际失败分别记录；未完成配对不计算推断统计。完整实验调用顺序及预算遵从根CLI，不由本离线报告触发。
'''
    (output / 'README_如何复现.md').write_text(readme)


def main():
    manifest = load_json(RUN / 'run_manifest.json')
    if manifest is None:
        raise RuntimeError('Missing run manifest')
    pending = [(arm, r['instance_id']) for r in manifest['records'] for arm in ARMS
               if not (RUN / 'lite_pilot' / arm / r['instance_id'] / 'result.json').is_file()]
    if pending:
        raise RuntimeError('Finish all allocated A outcomes before private-label evaluation; pending=' + str(len(pending)))
    result = build_report(expected_reference={'D-SIMPLE': 38, 'D-COSIL': 34, 'Q-COSIL': 11, 'Q-PRUNER': 11})
    print(json.dumps({'report': str(RUN / 'reports/final_diagnostic_report.md'),
                      'new_request_count': result['new_request_count'], 'known_actual_usd': result['new_cost_known_actual_usd'],
                      'historical_reproduction': result['historical_reproduction']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
