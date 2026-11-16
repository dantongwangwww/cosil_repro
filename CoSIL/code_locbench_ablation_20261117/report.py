"""Offline five-condition ablation evaluation; terminal barriers precede Gold.

This module never changes the historical two-arm modules or starts a model.
Public preparation and external/internal identities are verified before private
Gold is parsed. All allocated, function-eligible failures retain their denominator.
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
import time

from code_locbench_sfpruner_20261116 import report as old

c, f, e = old.c, old.f, old.e
VARIANTS = ('ablation_no_lora', 'ablation_no_neighbors', 'ablation_no_defer')
ARMS = ('baseline', 'hybrid_safe') + VARIANTS
CUTS = (100, 200, 300, 400, 500, 560)
IDENTITY = ('instance_id', 'repo', 'base_commit')
CLEAN_JOB = {'instance_id', 'repo', 'base_commit', 'problem_statement', 'cohort',
             'snapshot', 'paths', 'code_index', 'structure'}
SHARED = {'instance_id', 'base_commit', 'files', 'raw_file_responses'}
NO_DISPATCH = {'source_preparation_blocked', 'upstream_file_stage_unavailable'}
LABELS = {'baseline': 'CoSIL', 'hybrid_safe': '完整SFPruner',
          'ablation_no_lora': '禁用LoRA', 'ablation_no_neighbors': '移除邻居摘要',
          'ablation_no_defer': '取消正常灰区复核'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def consume(path, provenance):
    path = Path(path).resolve(strict=True)
    provenance[str(path)] = sha(path)
    return read(path)


def verify_map(mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('A byte-binding map is required')
    for path, wanted in mapping.items():
        path = Path(path)
        if path.is_symlink() or not path.is_file() or sha(path) != wanted:
            raise ValueError('Frozen input/source drift: ' + str(path))


def identity(value, row, label):
    if value.get('simulation') or value.get('not_benchmark_result'):
        raise ValueError('Simulated artifact: ' + label)
    for key in IDENTITY:
        if key in value and value[key] != row[key]:
            raise ValueError(label + ' identity mismatch: ' + key)


def public_inputs(row):
    """No private labels are accepted into the staged model-readable tree."""
    if row['upstream_status'] in NO_DISPATCH:
        if row.get('no_model_dispatch') is not True:
            raise ValueError('Explicit upstream failure must prohibit dispatch')
        return
    if row['upstream_status'] != 'ready' or row.get('no_model_dispatch') is not False:
        raise ValueError('Unknown or contradictory upstream qualification')
    directory = Path(row['public_input_path']).resolve(strict=True)
    expected = {'job.json', 'code_index.json', 'render_cache.json', 'public_receipt.json',
                'shared.json', 'repo_structures/' + row['instance_id'] + '.json'}
    actual = set()
    for path in directory.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in public input')
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
        elif path.is_dir() and path.relative_to(directory).as_posix() != 'repo_structures':
            raise ValueError('Unexpected public input directory')
    if actual != expected or set(row['public_files_sha256']) != expected:
        raise ValueError('Unexpected/private model-readable file inventory')
    for name, wanted in row['public_files_sha256'].items():
        if sha(directory / name) != wanted:
            raise ValueError('Public model input SHA drift')
    job = read(directory / 'job.json')
    if set(job) != CLEAN_JOB:
        raise ValueError('Only nine clean base job fields are accepted')
    identity(job, row, 'staged job')
    source_job = c.load_job(row['source_job_path'])
    expected_job = dict(source_job, snapshot='/snapshot', code_index='/input/code_index.json',
                        structure='/input/repo_structures/' + row['instance_id'] + '.json')
    if job != expected_job:
        raise ValueError('Staged job changed the original public issue/base input')
    if any(not isinstance(job[k], str) for k in CLEAN_JOB - {'paths'}):
        raise ValueError('Invalid clean job scalar')
    if not isinstance(job['paths'], list) or len(job['paths']) != len(set(job['paths'])):
        raise ValueError('Invalid public path inventory')
    shared = read(directory / 'shared.json')
    if set(shared) != SHARED or shared['instance_id'] != row['instance_id'] or shared['base_commit'] != row['base_commit']:
        raise ValueError('Shared file evidence identity/whitelist mismatch')
    if not isinstance(shared['files'], list) or not isinstance(shared['raw_file_responses'], list):
        raise ValueError('Invalid shared file evidence')
    verify_map(row['upstream_files_sha256'])


def public_manifest(root, n, *, expected_n=560):
    root = Path(root).resolve(strict=True)
    if expected_n == 560:
        from .common import require_execution_freeze
        require_execution_freeze(root)
    authority = read(root / 'authority.json')
    if authority['manifest_sha256'] != sha(root / 'manifest.json') or authority['protocol_sha256'] != sha(root / 'protocol.json'):
        raise ValueError('Preparation/protocol authority drift')
    verify_map(authority['files_sha256'])
    value = read(root / 'manifest.json'); rows = value['records']
    if (value.get('schema') != 1 or value.get('n') != expected_n or value.get('allocated') != expected_n
            or len(rows) != expected_n or tuple(value.get('arms', ())) != VARIANTS
            or len({r['instance_id'] for r in rows}) != expected_n):
        raise ValueError('Wrong frozen ablation roster or arm list')
    if not 1 <= n <= expected_n or (expected_n == 560 and n not in CUTS):
        raise ValueError('Invalid fixed prefix length')
    if [r['rank'] for r in rows] != list(range(1, expected_n + 1)):
        raise ValueError('Frozen rank order changed')
    chosen = rows[:n]
    for row in chosen:
        public_inputs(row)
    return root, chosen, authority


def result_status(state, result, *, invalid=False):
    if state == 'complete':
        if invalid or result.get('status') != 'complete':
            raise ValueError('Complete terminal lacks a complete raw result')
        return 'complete'
    if state == 'worker_failed':
        return 'ARTIFACT_INVALID' if invalid else result.get('status', 'WORKER_FAILURE')
    return {'dependency_blocked': 'DEPENDENCY_BLOCKED', 'interrupted': 'EXECUTION_INCOMPLETE',
            'timed_out': 'ENVIRONMENT_TIMEOUT', 'controller_failed': 'CONTROLLER_FAILURE'}[state]


def terminal_barrier(root, rows):
    """Read public provenance/terminal metadata only; never read Gold here."""
    root = Path(root); freeze = read(root / 'run/freeze.json')
    protocol = freeze['protocol_sha256']
    if len(protocol) != 64 or tuple(freeze.get('arms', VARIANTS)) != VARIANTS or freeze.get('simulation'):
        raise ValueError('Wrong or simulated run authority')
    provenance = {str((root / 'run/freeze.json').resolve()): sha(root / 'run/freeze.json')}
    terms = {}; groups = 0
    for row in rows:
        iid = row['instance_id']; directory = root / 'run/pairs' / iid; states = {}
        for arm in VARIANTS:
            arm_dir = directory / arm; path = arm_dir / 'terminal.json'
            term = consume(path, provenance); identity(term, row, 'new terminal')
            if (term.get('instance_id') != iid or term.get('base_commit') != row['base_commit']
                    or term.get('arm') != arm or term.get('protocol_sha256') != protocol
                    or term.get('simulation') is not False or term.get('keep_in_denominator') is not True):
                raise ValueError('External terminal identity/protocol mismatch')
            state = term.get('status')
            if row['no_model_dispatch']:
                if (state not in ('dependency_blocked', 'preparation_blocked', 'source_preparation_blocked',
                                  'upstream_file_stage_unavailable') or term.get('model_called') is not False
                        or term.get('upstream_status') != row['upstream_status']
                        or any((arm_dir / name).exists() for name in ('started.json', 'process.json', 'result.json'))):
                    raise ValueError('No-dispatch qualification was hidden or actually executed')
            else:
                if state not in c.TERMINAL or term.get('internal_arm') != 'hybrid_safe':
                    raise ValueError('New arm is not a real frozen internal hybrid worker')
                started = arm_dir / 'started.json'
                if state in ('complete', 'worker_failed') and not started.is_file():
                    raise ValueError('Result-bearing arm never started')
                if started.exists():
                    start = consume(started, provenance)
                    if start.get('protocol_sha256') != protocol:
                        raise ValueError('Started protocol mismatch')
                    for field in ('arm', 'experimental_arm'):
                        if field in start and start[field] != arm:
                            raise ValueError('Started external condition mismatch')
                if state in ('complete', 'worker_failed') and not term.get('result_sha256'):
                    raise ValueError('Missing frozen result SHA')
                if term.get('result_sha256'):
                    result = arm_dir / 'result.json'
                    if not result.is_file() or sha(result) != term['result_sha256']:
                        raise ValueError('Raw worker result SHA mismatch')
                    provenance[str(result.resolve())] = sha(result)
            terms[(iid, arm)] = term; states[arm] = term
        group = consume(directory / 'group_terminal.json', provenance)
        identity(group, row, 'group terminal')
        if (group.get('instance_id') != iid or group.get('base_commit') != row['base_commit']
                or group.get('simulation') is not False or group.get('protocol_sha256') != protocol
                or group.get('arms') != states or group.get('keep_in_denominator') is not True):
            raise ValueError('Three-arm group is not fully terminal')
        groups += 1
    return {'passed': True, 'allocated': len(rows), 'terminal_arms': 3 * len(rows),
            'terminal_groups': groups, 'gold_opened': False, 'provenance_sha256': provenance}, terms


def blocked_resource():
    return {**old.empty_resource(), 'http_attempts_recorded': 0,
            'file_main_usage': {'prompt': 0, 'completion': 0, 'unknown': 0},
            'local_forward_seconds': 0., 'local_generated_output_tokens': 0,
            'event_counts': {}, 'file_stage_http_attempts': 0,
            'http_phase_attempts': {}, 'http_unknown_phase_attempts': 0,
            'phase_count_source': 'explicit_no_dispatch_receipt',
            'usage_source': 'explicit_no_dispatch_receipt'}


def http_phases(directory, result, provenance):
    attempts = {}; unknown = 0
    for path in sorted((Path(directory) / 'calls').glob('*/attempt_*_*.json')):
        suffix = '_receipt.json' if path.name.endswith('_receipt.json') else '_start.json' if path.name.endswith('_start.json') else None
        if suffix is None:
            continue
        record = consume(path, provenance)
        key = str(path.parent) + '/' + path.name[:-len(suffix)]
        stage = record.get('stage')
        if key in attempts and attempts[key] != stage:
            raise ValueError('HTTP start/receipt stage mismatch')
        attempts[key] = stage
    if attempts:
        phases = Counter(v for v in attempts.values() if isinstance(v, str))
        unknown = sum(not isinstance(v, str) for v in attempts.values())
        file_calls = sum(v for k, v in phases.items() if k.startswith('file'))
        return {'http_phase_attempts': dict(phases), 'http_unknown_phase_attempts': unknown,
            'file_stage_http_attempts': None if unknown else file_calls,
            'phase_count_source': 'raw_attempt_start_and_receipt_union',
            'file_stage_http_attempts_known': file_calls}
    if result.get('http_attempts') == 0 and result.get('local_model') is True:
        return {'http_phase_attempts': {}, 'http_unknown_phase_attempts': 0,
            'file_stage_http_attempts': 0, 'phase_count_source': 'explicit_worker_zero_attempts',
            'file_stage_http_attempts_known': 0}
    return {'http_phase_attempts': {}, 'http_unknown_phase_attempts': None,
        'file_stage_http_attempts': None, 'phase_count_source': 'unrecorded_phase_usage',
        'file_stage_http_attempts_known': 0}


def read_events(directory, provenance):
    path = Path(directory) / 'events.jsonl'
    if not path.exists():
        return [], False
    provenance[str(path.resolve())] = sha(path)
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete event JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()], True


def judge_journal(directory, arm, provenance, local_events=(), *, no_dispatch=False):
    """Physical local scoring evidence, independent of successful agent events.

    Unmatched starts and error receipts leave usage/forward totals unknown.
    Known sums are lower bounds; no error is silently converted to zero work.
    """
    attempts = {}
    for path in sorted((Path(directory) / 'judge_rpc').glob('*.json')):
        suffix = '_start.json' if path.name.endswith('_start.json') else '_receipt.json' if path.name.endswith('_receipt.json') else None
        if suffix is None:
            raise ValueError('Unexpected judge RPC journal file')
        if path.is_symlink():
            raise ValueError('Symlink judge RPC journal')
        value = consume(path, provenance); request = path.name[:-len(suffix)]
        if (value.get('request_id') != request or value.get('experimental_arm') != arm
                or value.get('internal_arm') != 'hybrid_safe'):
            raise ValueError('Judge RPC request/condition identity mismatch')
        slot = 'start' if suffix == '_start.json' else 'receipt'
        if slot in attempts.setdefault(request, {}):
            raise ValueError('Duplicate judge RPC journal role')
        attempts[request][slot] = value
    if no_dispatch and attempts:
        raise ValueError('No-dispatch arm contains local score attempts')
    values = Counter(); probe = Counter(); records = []
    for request, pair in attempts.items():
        start, receipt = pair.get('start'), pair.get('receipt')
        item = start or receipt; operation = item.get('operation')
        if operation not in ('score', 'probe', 'health'):
            raise ValueError('Unknown judge journal operation')
        if start and receipt and any(start.get(k) != receipt.get(k) for k in
                ('operation', 'request_id', 'experimental_arm', 'internal_arm', 'input_sha256')):
            raise ValueError('Judge start/receipt identity mismatch')
        counter = values if operation == 'score' else probe
        counter['attempts'] += 1
        closed = start is not None and receipt is not None
        success = bool(receipt and receipt.get('status') == 'success'
                       and receipt.get('forward_status') == 'confirmed_score_success')
        if success and receipt.get('adapter_active') is not (arm != 'ablation_no_lora'):
            raise ValueError('Confirmed judge receipt adapter state mismatch')
        token_known = bool(success and receipt.get('usage_status') == 'known'
            and all(type(receipt.get(k)) is int and receipt[k] >= 0
                    for k in ('input_tokens', 'generated_output_tokens')))
        counter['known_forward_sum'] += int(success)
        counter['unknown_forward_attempts'] += int(not success or not closed)
        counter['known_input_tokens_sum'] += receipt['input_tokens'] if token_known else 0
        counter['known_output_tokens_sum'] += receipt['generated_output_tokens'] if token_known else 0
        counter['unknown_usage_attempts'] += int(not token_known or not closed)
        counter['error_attempts'] += int(bool(receipt and receipt.get('status') == 'error'))
        counter['unclosed_attempts'] += int(not closed)
        counter['successful_receipts'] += int(success)
        if receipt and isinstance(receipt.get('elapsed_seconds'), (int, float)):
            counter['known_rpc_elapsed_seconds_sum'] += receipt['elapsed_seconds']
        records.append({'request_id': request, 'operation': operation, 'closed': closed,
            'confirmed_forward': success, 'usage_known': token_known,
            'input_sha256': item.get('input_sha256'),
            'score_sequence': receipt.get('score_sequence') if receipt else None})
    unbound_events = 0
    for event in local_events:
        request = event.get('judge_rpc_request_id')
        if request not in attempts:
            unbound_events += 1
        else:
            item = attempts[request].get('start') or attempts[request].get('receipt')
            if item.get('input_sha256') != event.get('input_sha256'):
                raise ValueError('Local event/judge journal input identity mismatch')
    # Successful agent events do not erase missing physical journal evidence.
    values['unknown_forward_attempts'] += unbound_events
    values['unknown_usage_attempts'] += unbound_events
    values['missing_journal_for_success_events'] = unbound_events
    known_seconds = sum(e.get('latency_seconds', 0.) for e in local_events
                        if isinstance(e.get('latency_seconds'), (int, float)))
    latency_unknown = max(values['attempts'] - len(local_events), 0) + values['missing_journal_for_success_events']
    result = {'judge_rpc_attempts': values['attempts'],
        'judge_forward_known_sum': values['known_forward_sum'],
        'judge_forward_unknown_attempts': values['unknown_forward_attempts'],
        'judge_input_tokens_known_sum': values['known_input_tokens_sum'],
        'judge_output_tokens_known_sum': values['known_output_tokens_sum'],
        'judge_usage_unknown_attempts': values['unknown_usage_attempts'],
        'judge_error_attempts': values['error_attempts'],
        'judge_unclosed_attempts': values['unclosed_attempts'],
        'judge_rpc_success_receipts': values['successful_receipts'],
        'judge_rpc_elapsed_seconds_known_sum': values['known_rpc_elapsed_seconds_sum'],
        'local_successful_score_events': len(local_events),
        'local_input_tokens': None if values['unknown_usage_attempts'] else values['known_input_tokens_sum'],
        'local_generated_output_tokens': None if values['unknown_usage_attempts'] else values['known_output_tokens_sum'],
        'local_physical_scoring_forwards': None if values['unknown_forward_attempts'] else values['known_forward_sum'],
        'local_forward_seconds_known_sum': known_seconds,
        'local_forward_seconds_unknown_attempts': latency_unknown,
        'local_forward_seconds': None if latency_unknown else known_seconds,
        'local_accounting_source': 'independent_pre_call_rpc_start_and_receipt_journal',
        'judge_nonbenchmark_operations': dict(probe), 'judge_journal_records': records,
        'probe_scope': 'per-arm non-score journal only; service readiness probes remain outside benchmark accounting'}
    return result


def new_arm(root, row, arm, terminal, provenance):
    directory = Path(root) / 'run/pairs' / row['instance_id'] / arm
    if row['no_model_dispatch']:
        name = 'PREPARATION_BLOCKED' if row['upstream_status'] == 'source_preparation_blocked' else 'UPSTREAM_FILE_STAGE_UNAVAILABLE'
        return {'status': name, 'predicted_files': [], 'predicted_functions': []}, {
            'resource': {**blocked_resource(), **judge_journal(directory, arm, provenance, no_dispatch=True)},
            'local_events': [], 'all_events': [], 'all_events_available': True, 'execution_status': terminal['status'],
            'terminal_verified': True, 'model_called': False, 'upstream_status': row['upstream_status']}
    path = directory / 'result.json'; result = {}; invalid = False
    if path.exists():
        try:
            result = consume(path, provenance)
        except (json.JSONDecodeError, UnicodeDecodeError):
            provenance[str(path.resolve())] = sha(path); invalid = True
    if result:
        identity(result, row, 'new raw result')
        if result.get('arm') != 'hybrid_safe' or result.get('experimental_arm') != arm:
            raise ValueError('Raw internal/external condition identity mismatch')
        if 'internal_arm' in result and result['internal_arm'] != 'hybrid_safe':
            raise ValueError('Raw internal worker mode mismatch')
    status = result_status(terminal['status'], result, invalid=invalid)
    used = terminal['status'] in ('complete', 'worker_failed') and not invalid
    pred = {'status': status, 'predicted_files': result.get('predicted_files', []) if used else [],
            'predicted_functions': result.get('predicted_functions', []) if used else []}
    resource, events = f.resource_record(directory, result, status, provenance)
    phase = http_phases(directory, result, provenance)
    if phase['file_stage_http_attempts_known']:
        raise ValueError('Ablation unexpectedly called the file model; frozen shared-stage protocol violated')
    resource.update(phase)
    resource.update(judge_journal(directory, arm, provenance, events))
    all_events, events_available = read_events(directory, provenance)
    for event in events:
        if event.get('experimental_arm') != arm or event.get('internal_arm') != 'hybrid_safe':
            raise ValueError('Local score event condition identity mismatch')
        if event.get('adapter_active') is not (arm != 'ablation_no_lora'):
            raise ValueError('Actual local score adapter state mismatch')
        text = event.get('model_input')
        if not isinstance(text, str) or hashlib.sha256(text.encode()).hexdigest() != event.get('input_sha256'):
            raise ValueError('Actual local score input bytes mismatch')
        if arm == 'ablation_no_neighbors' and (event.get('neighbors_selected') != 0
                or not text.endswith('<direct_call_context>\n\n</direct_call_context>')):
            raise ValueError('No-neighbor event still exposes a neighbor summary')
    return pred, {'resource': resource, 'local_events': events, 'all_events': all_events,
                  'all_events_available': events_available, 'execution_status': terminal['status'],
                  'terminal_verified': True, 'result_path': str(path), 'raw_result_sha256': sha(path) if path.exists() else None}


def load_bundle(root, rows, terms, provenance):
    """Private targets are first parsed here, after terminal_barrier succeeds."""
    records = []; gold = {}; inventory = {}; details = {}; frozen_work = {}
    for row in rows:
        work = Path(row['original_work']).resolve(strict=True)
        if work not in frozen_work:
            frozen_path = work / 'controller/report_freeze.json'
            frozen = consume(frozen_path, provenance)
            # Hash every referenced source, including Gold, without changing it.
            verify_map(frozen['source_sha256'])
            old_gate, allocated, runnable, statuses = old.terminal_barrier(frozen)
            frozen_work[work] = (frozen, {r['instance_id']: r for r in allocated},
                {r['instance_id']: r for r in runnable}, statuses,
                consume(frozen['gold'], provenance), consume(frozen['inventory'], provenance))
        frozen, allocated, runnable, statuses, old_gold, old_inv = frozen_work[work]
        iid = row['instance_id']
        if iid not in allocated or any(row[k] != allocated[iid][k] for k in IDENTITY):
            raise ValueError('Same IID points to another historical base')
        g = old_gold[iid]
        if any(g.get(k, row[k]) != row[k] for k in IDENTITY):
            raise ValueError('Gold base identity mismatch')
        gold[iid] = g; inv = old_inv[iid]
        if iid in runnable:
            job = c.load_job((work / 'runtime' / runnable[iid]['job']).resolve(strict=True))
            index = consume(job['code_index'], provenance)
            inv = {'paths': sorted(index), 'function_identities': sorted({path + '::' + d['qualified_name']
                for path, item in index.items() for d in item['definitions'] if d['kind'] == 'function'})}
        inventory[iid] = inv; arms = {}
        for arm in ('baseline', 'hybrid_safe'):
            if iid in runnable:
                old_control = consume(Path(frozen['run_root']) / 'freeze.json', provenance)
                arms[arm], detail = f.read_new_arm(Path(frozen['run_root']) / 'pairs' / iid / arm,
                    {k: row[k] for k in IDENTITY}, arm, old_control['protocol_sha256'], provenance)
                historical_events, historical_available = read_events(Path(frozen['run_root']) / 'pairs' / iid / arm, provenance)
                detail.update(all_events=historical_events, all_events_available=historical_available)
            else:
                arms[arm] = {'status': 'PREPARATION_BLOCKED', 'predicted_files': [], 'predicted_functions': []}
                detail = {'resource': blocked_resource(), 'local_events': [], 'all_events': [], 'all_events_available': True, 'execution_status': 'preparation_blocked',
                          'terminal_verified': None, 'model_called': False}
            details[(iid, arm)] = {**detail, 'historical_reuse': True, 'new_api_usd': 0}
        for arm in VARIANTS:
            arms[arm], details[(iid, arm)] = new_arm(root, row, arm, terms[(iid, arm)], provenance)
        records.append({**{k: row[k] for k in IDENTITY}, 'arms': arms})
    return {'records': records, 'gold': gold, 'inventory': inventory, 'details': details}


def holm(pvalues):
    """Holm step-down adjusted p values, retaining the registered comparison keys."""
    if any(not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1 for p in pvalues.values()):
        raise ValueError('Invalid p value')
    ranked = sorted(pvalues, key=lambda key: (pvalues[key], key)); out = {}; previous = 0.
    for rank, key in enumerate(ranked):
        previous = max(previous, min(1., (len(ranked) - rank) * pvalues[key])); out[key] = previous
    return out


def evaluate(bundle, *, draws=5000):
    result = e.evaluate(bundle['records'], bundle['gold'], bundle['inventory'], arms=ARMS,
                        seed=e.DEFAULT_SEED, draws=draws)
    eligible = [row for row in result['records'] if row['function_scorable']]
    paired = {}; pvalues = {}
    for arm in VARIANTS:
        for k in (1, 3, 5):
            key = arm + ':hit' + str(k)
            value = e.paired([r['hybrid_safe_function']['hit' + str(k)] for r in eligible],
                             [r[arm + '_function']['hit' + str(k)] for r in eligible],
                             seed=e.DEFAULT_SEED, draws=draws)
            value.update(reference='hybrid_safe', comparison=arm, metric='hit' + str(k))
            paired[key] = value; pvalues[key] = value['exact_mcnemar_p']
    adjusted = holm(pvalues)
    for key, value in paired.items():
        value['holm_p_9_registered_tests'] = adjusted[key]
    result['paired_against_full_sf'] = paired
    return result


def route_risk(bundle):
    by_arm = {}
    for arm in ARMS:
        total = Counter(); visited = set(); rejected = set(); tasks_visited = set(); tasks_rejected = set()
        per_issue = []
        for row in bundle['records']:
            iid = row['instance_id']; targets = set(bundle['gold'][iid]['targets'])
            events = bundle['details'][(iid, arm)].get('local_events', [])
            local = []
            for event in events:
                p = event.get('p_yes')
                if (not isinstance(p, (int, float)) or isinstance(p, bool) or not math.isfinite(p) or not 0 <= p <= 1):
                    continue
                original = event.get('route_original') or ('reject' if p <= event.get('low', .12947567721292427)
                    else 'retain' if p >= event.get('high', .9) else 'qwen')
                effective = event.get('route_effective', event.get('route'))
                if effective not in ('reject', 'retain', 'qwen'):
                    raise ValueError('Successful local score has no valid effective route')
                fid = event.get('function_id'); is_gold = fid in targets
                total['successful_score_events'] += 1; total['route_' + effective] += 1
                total['original_gray_events'] += original == 'qwen'
                total['normal_gray_to_qwen_events'] += original == 'qwen' and effective == 'qwen'
                total['gray_direct_override_events'] += original == 'qwen' and effective != 'qwen'
                if is_gold:
                    visited.add((iid, fid)); tasks_visited.add(iid); total['gold_score_visits'] += 1
                    if effective == 'reject':
                        rejected.add((iid, fid)); tasks_rejected.add(iid); total['gold_direct_reject_events'] += 1
                local.append({'function_id': fid, 'p_yes': p, 'route_original': original,
                    'route_effective': effective, 'is_gold': is_gold})
            resource = bundle['details'][(iid, arm)]['resource']
            events_count = resource.get('event_counts', {})
            total['class_fallback_events'] += events_count.get('pruner_class_fallback', 0)
            total['binding_fallback_events'] += events_count.get('judge_binding_fallback', 0)
            total['tool_identity_help_events'] += events_count.get('tool_identity_help', 0)
            all_events = bundle['details'][(iid, arm)].get('all_events')
            if all_events is not None:
                binding, flagged = set(), set()
                for number, event in enumerate(all_events):
                    key = (event.get('step'), event.get('tool'), json.dumps(event.get('arguments'), sort_keys=True))
                    if event.get('step') is None or event.get('tool') is None:
                        key = ('unlinked_event', number)
                    if event.get('event') == 'judge_binding_fallback': binding.add(key)
                    if event.get('event') == 'prune' and event.get('technical_fallback') is True: flagged.add(key)
                total['technical_fallback_events_known_sum'] += len(binding | flagged)
                total['technical_fallback_prune_events'] += sum(e.get('event') == 'prune' and e.get('technical_fallback') is True for e in all_events)
                if bundle['details'][(iid, arm)].get('all_events_available') is False:
                    total['technical_fallback_unknown_tasks'] += 1
            else:
                # Historical count is a recorded binding attempt, not an invented event name.
                total['technical_fallback_events_known_sum'] += events_count.get('judge_binding_fallback', 0)
            total['rpc_failure_events'] += resource.get('judge_error_attempts', events_count.get('judge_rpc_failure', 0))
            per_issue.append({'instance_id': iid, 'successful_scores': len(local),
                              'gold_visits': sum(v['is_gold'] for v in local), 'events': local})
        all_gold = sum(len(bundle['gold'][r['instance_id']]['targets']) for r in bundle['records'])
        visits = total['gold_score_visits']; rejects = total['gold_direct_reject_events']
        by_arm[arm] = {**dict(total),
            'technical_fallback_events': None if total['technical_fallback_unknown_tasks'] else total['technical_fallback_events_known_sum'],
            'technical_fallback_count_policy': 'union judge_binding_fallback and prune technical_fallback by step/tool/arguments; no double counting',
            'scope': 'successful local small-pruner scoring events only; baseline main-pruner decisions are not measured by this table',
            'local_scoring_applicable': arm != 'baseline',
            'gold_available_unique_identities': all_gold,
            'gold_visited_unique_identities': len(visited), 'gold_direct_rejected_unique_identities': len(rejected),
            'gold_visited_tasks': len(tasks_visited), 'gold_direct_rejected_tasks': len(tasks_rejected),
            'allocated_tasks': len(bundle['records']), 'gold_direct_reject_fraction_given_visit': rejects / visits if visits else None,
            'gold_unique_reject_fraction_given_visited_identity': len(rejected) / len(visited) if visited else None,
            'unvisited_gold_is_not_counted_as_retained': True, 'records': per_issue}
    return by_arm


def resource_summary(bundle):
    result = {}
    for arm in ARMS:
        items = [bundle['details'][(row['instance_id'], arm)]['resource'] for row in bundle['records']]
        historical = arm in ('baseline', 'hybrid_safe')
        def known(key):
            vals = [item.get(key) for item in items]
            return sum(vals) if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals) else None
        shared = [bundle['details'][(row['instance_id'], 'baseline')]['resource'].get('file_main_usage')
                  for row in bundle['records']]
        shared_known = all(isinstance(v, dict) and all(type(v.get(k)) is int for k in ('prompt', 'completion', 'unknown')) for v in shared)
        shared_tokens = sum(v['prompt'] + v['completion'] for v in shared) if shared_known else None
        shared_unknown = sum(v['unknown'] for v in shared) if shared_known else None
        main = known('main_tokens')
        result[arm] = {'execution_source': 'historical_frozen_reuse' if historical else 'new_downstream_execution',
            'new_file_agent_http_calls': 0 if historical else known('file_stage_http_attempts'),
            'new_file_http_phase_verified_zero': historical or known('file_stage_http_attempts') == 0,
            'physical_main_tokens': main,
            'known_prompt_tokens': known('known_prompt_tokens'), 'known_completion_tokens': known('known_completion_tokens'),
            'unknown_usage_attempts': known('unknown_usage_attempts'), 'http_attempts_recorded': known('http_attempts_recorded'),
            'local_input_tokens': known('local_input_tokens'),
            'local_scoring_forwards_recorded': known('local_decisions') if historical else known('local_physical_scoring_forwards'),
            'local_successful_score_events': known('local_decisions') if historical else known('local_successful_score_events'),
            'judge_forward_known_sum': known('local_decisions') if historical else known('judge_forward_known_sum'),
            'judge_forward_unknown_attempts': 0 if historical else known('judge_forward_unknown_attempts'),
            'judge_input_tokens_known_sum': known('local_input_tokens') if historical else known('judge_input_tokens_known_sum'),
            'judge_output_tokens_known_sum': known('local_generated_output_tokens') if historical else known('judge_output_tokens_known_sum'),
            'judge_usage_unknown_attempts': 0 if historical else known('judge_usage_unknown_attempts'),
            'judge_rpc_error_attempts': 0 if historical else known('judge_error_attempts'),
            'judge_rpc_unclosed_attempts': 0 if historical else known('judge_unclosed_attempts'),
            'judge_rpc_attempts': None if historical else known('judge_rpc_attempts'),
            'local_accounting_source': 'historical independently matched ledger' if historical else 'per-arm immutable judge_rpc start/receipt journal',
            'per_arm_nonbenchmark_journal': [] if historical else [item.get('judge_nonbenchmark_operations', {}) for item in items],
            'local_forward_seconds': known('local_forward_seconds'),
            'shared_file_stage_tokens_known': shared_tokens, 'shared_file_stage_unknown_attempts': shared_unknown,
            'main_tokens_including_shared_file_stage': (main + shared_tokens if arm != 'baseline' and main is not None and shared_tokens is not None and not shared_unknown else main if arm == 'baseline' else None),
            'new_physical_api_usd': 0, 'historical_reuse_new_api_usd': 0,
            'new_physical_main_tokens': 0 if historical else main,
            'unknown_usage_is_not_zero': True, 'file_call_count_not_used_as_new_http_count': True,
            'latency_scope': 'worker elapsed includes service wait; upstream file reuse and historical controls preclude an independent end-to-end speedup claim',
            'GPU_electricity_and_depreciation': 'not measured'}
    return result


def csv_rows(evaluated, bundle):
    detail = {r['instance_id']: r for r in bundle['records']}; rows = []
    for row in evaluated['records']:
        iid = row['instance_id']; flat = {k: row[k] for k in ('instance_id', 'repo', 'base_commit', 'gold_status', 'function_scorable', 'gold_functions', 'gold_files')}
        for arm in ARMS:
            flat[arm + '_status'] = row[arm + '_status']
            flat[arm + '_raw_predicted_functions'] = detail[iid]['arms'][arm]['predicted_functions']
            flat[arm + '_raw_predicted_files'] = detail[iid]['arms'][arm]['predicted_files']
            flat[arm + '_resource'] = bundle['details'][(iid, arm)]['resource']
            for unit in ('function', 'file'):
                metric = row[arm + '_' + unit]
                for key in ('slots', 'hit1', 'hit3', 'hit5', 'precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
                    flat[arm + '_' + unit + '_' + key] = metric.get(key) if metric else None
        rows.append(flat)
    return rows


def markdown(evaluated, resources, risks):
    summary = evaluated['summary']; n = summary['allocated']; lines = [f'# LocBench{n}题：函数剪枝三项消融', '',
        '五个条件按相同issue ID比较。CoSIL与完整SFPruner为已冻结历史控制，三个消融只重跑共享文件选择之后的搜索。固定温度与阈值，不重新训练或重拟合；失败保留可评价分母。', '',
        '| 条件 | 函数Hit@1 | Hit@3 | Hit@5（主终点） | Macro-P@5 | Macro-R@5 | Macro-F1@5 | 全目标覆盖@5 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        m = summary['metrics'][arm]['function']; den = m['n']
        lines.append('|' + '|'.join([LABELS[arm]] + [f'{m["hit"+str(k)+"_numerator"]}/{den} ({m["hit"+str(k)]:.2%})' for k in (1, 3, 5)]
            + [f'{m[key]:.2%}' if m[key] is not None else 'NA' for key in ('precision5', 'recall5', 'f15', 'all_coverage5')]) + '|')
    lines += ['', '函数指标使用完整既有目标集合和严格path::qualified_name；__init__不折叠，无效或重复槽位不压缩。Hit使用Wilson区间，其余指标和同题差使用冻结seed的issue bootstrap；完整95%CI保存在evaluation.json。', '',
        '| 消融−完整SF | 指标 | 两组命中 | 仅完整SF | 仅消融 | 均未中 | 差值 | 配对95%CI | McNemar p | Holm p（9项） |',
        '|---|---|---:|---:|---:|---:|---:|---|---:|---:|']
    for value in evaluated['paired_against_full_sf'].values():
        lines.append('|' + '|'.join([LABELS[value['comparison']], value['metric'], str(value['both_success']), str(value['only_a']), str(value['only_b']),
            str(value['both_failure']), f'{value["b_minus_a"]:.2%}', str(value['b_minus_a_ci95']), str(value['exact_mcnemar_p']), str(value['holm_p_9_registered_tests'])]) + '|')
    lines += ['', f'固定任务{n}，函数可评价{summary["function_denominator"]}；执行状态：`{json.dumps(summary["statuses"], ensure_ascii=False)}`。源码准备失败与上游文件阶段失败分别记录，不当作消融模型已尝试后的能力失败。', '',
        '三个消融的含义仅限于固定部署规则下移除一个组件：禁用LoRA仍沿用训练版温度/阈值；移除邻居不会补长已拟合issue或函数；取消复核仅作用于成功评分的正常灰区，类请求和技术回退保持原规则。', '',
        '文件排名来自共同冻结的上游文件阶段，不能解释成三个新文件定位器的独立实验。资源按新真实HTTP回执与独立4B RPC start/receipt实账计数（成功决策事件另列，异常或未闭合记unknown）；历史控制本轮新增调用与费用为零，共享文件阶段的公平归一化总账另列。未知usage不会记为零。', '',
        'Gold直剪仅指被实际成功评分并直接reject的目标访问事件；未访问Gold不能声称被安全保留。访问次数、唯一目标身份、任务层风险、正常灰区与类/技术回退均在route_risk.json中分开。', '',
        '本次单seed、历史控制复用；issue-bootstrap没有校正仓库内相关，结果不得解释为最优base模型或跨部署的普适结论。', '',
        '复现：`python -B -m code_locbench_ablation_20261117.report --root <实验根目录> --n ' + str(n) + ' --out <新报告目录>`。', '']
    return '\n'.join(lines)


def run(root, n, out, *, draws=5000, expected_n=560):
    out = Path(out)
    if out.exists():
        raise FileExistsError('Never overwrite an ablation checkpoint report')
    if draws < 40:
        raise ValueError('At least40 bootstrap draws required')
    root, rows, authority = public_manifest(root, n, expected_n=expected_n)
    gate, terms = terminal_barrier(root, rows)
    provenance = {**gate['provenance_sha256'], str(root / 'manifest.json'): sha(root / 'manifest.json'),
        str(root / 'authority.json'): sha(root / 'authority.json'), str(root / 'protocol.json'): sha(root / 'protocol.json')}
    bundle = load_bundle(root, rows, terms, provenance)
    evaluated = evaluate(bundle, draws=draws); resources = resource_summary(bundle); risks = route_risk(bundle)
    for path, wanted in provenance.items():
        if sha(path) != wanted:
            raise ValueError('Immutable input changed during offline scoring')
    out.mkdir(parents=True)
    summary = {'status': 'FINAL_ABLATION_CHECKPOINT', 'allocated': n, 'arms': list(ARMS),
        'revision': old.SOURCE_REVISION, 'dataset': 'czlll/Loc-Bench_V1', 'primary_endpoint': 'function_hit5',
        'function_denominator': evaluated['summary']['function_denominator'],
        'file_denominator': evaluated['summary']['file_denominator'], 'resources': resources,
        'terminal_barrier_before_gold': True, 'models_called_by_evaluator': 0, 'test_unsealed': False,
        'bootstrap_seed': e.DEFAULT_SEED, 'bootstrap_draws': draws,
        'report_source_sha256': sha(__file__), 'new_file_agent_calls': 0}
    for name, value in [('summary', summary), ('evaluation', evaluated), ('terminal_gate', gate),
                        ('route_risk', risks), ('resources', resources), ('input_sha256', provenance),
                        ('allocation', {'n': n, 'records': rows})]:
        c.write(out / (name + '.json'), value, immutable=True)
    flat = csv_rows(evaluated, bundle)
    with (out / '逐题定位与资源.csv').open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, list(flat[0]) if flat else [])
        writer.writeheader()
        for row in flat:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    (out / '消融实验_总览.md').write_text(markdown(evaluated, resources, risks), encoding='utf-8')
    c.write(out / 'output_sha256.json', {p.name: sha(p) for p in out.iterdir() if p.is_file()}, immutable=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--n', type=int, choices=CUTS, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--bootstrap-draws', type=int, default=5000)
    args = parser.parse_args()
    result = run(args.root, args.n, args.out, draws=args.bootstrap_draws)
    print(json.dumps({'status': result['status'], 'allocated': result['allocated']}))


if __name__ == '__main__':
    main()
