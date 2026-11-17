"""Correct runtime-to-canonical risk attribution without changing sealed reports.

Only the completed prefix's Gold is opened, after both its REPORT_COMPLETE
receipt and all three-arm group barriers have been independently checked.
This module imports no model, active controller or old report implementation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import tokenize
import time

VARIANTS = ('ablation_no_lora', 'ablation_no_neighbors', 'ablation_no_defer')
LOCAL = ('hybrid_safe',) + VARIANTS
ARMS = ('baseline',) + LOCAL
CUTS = (100, 200, 300, 400, 500, 560)
TERMINAL = {'complete', 'worker_failed', 'controller_failed', 'interrupted', 'timed_out',
            'source_preparation_blocked', 'upstream_file_stage_unavailable'}
LOW, HIGH, TEMPERATURE = .12947567721292427, .9, 2.9846201034621833
GRAPH_SOURCE = Path(__file__).resolve().parents[1] / 'papers/SFPruner/vendor/code_v5/static_calls.py'
CONTROLLER_SOURCE = Path(__file__).resolve().parents[1] / 'code_locbench_ablation_20261117_v2/controller.py'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_digest(value):
    """The frozen controller's exact JSON digest, not a machine-file SHA."""
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             allow_nan=False, separators=(',', ':')).encode())


class Evidence:
    """Hash only files actually consumed; never traverse an authority tree."""
    def __init__(self):
        self.hashes, self.stats = {}, {}

    def raw(self, path, expected=None):
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Evidence must be a regular file, not a symlink: ' + str(path))
        path = path.resolve(strict=True)
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        stamp = lambda s: (s.st_size, s.st_mtime_ns, s.st_ino)
        if stamp(before) != stamp(after):
            raise ValueError('Evidence changed while read: ' + str(path))
        actual = digest(data)
        if expected is not None and actual != expected:
            raise ValueError('Bound evidence SHA mismatch: ' + str(path))
        if str(path) in self.hashes and self.hashes[str(path)] != actual:
            raise ValueError('Evidence changed across reads: ' + str(path))
        self.hashes[str(path)], self.stats[str(path)] = actual, stamp(after)
        return data

    def json(self, path, expected=None):
        return json.loads(self.raw(path, expected))

    def unchanged(self):
        for path, expected in self.stats.items():
            stat = Path(path).stat()
            if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != expected:
                raise ValueError('Evidence changed during analysis: ' + path)


def same_identity(value, row):
    for key in ('instance_id', 'base_commit'):
        if value.get(key) != row[key]:
            raise ValueError('Identity/base mismatch: ' + key)


def terminal_barrier(root, rows, evidence, expected_execution):
    """Public metadata only. No Gold or prediction parsing is needed here."""
    root = Path(root)
    freeze = evidence.json(root / 'run/freeze.json')
    if (freeze.get('allocated') != 560 or tuple(freeze.get('arms', ())) != VARIANTS
            or freeze.get('simulation') is True):
        raise ValueError('Unexpected run freeze')
    protocol = freeze['protocol_sha256']
    # Machine protocol SHA and derived controller protocol SHA are distinct.
    # The latter must genuinely derive from the former plus frozen inputs.
    controller_sha = expected_execution['files_sha256'].get(str(CONTROLLER_SOURCE.resolve()))
    if not controller_sha:
        raise ValueError('Execution freeze does not bind the original controller')
    evidence.raw(CONTROLLER_SOURCE, controller_sha)
    expected = {'user_protocol_sha256': expected_execution['protocol_sha256'],
                'manifest_sha256': expected_execution['manifest_sha256'],
                'preparation_authority_sha256': expected_execution['authority_sha256'],
                'controller_sha256': controller_sha}
    if any(freeze.get(key) != wanted for key, wanted in expected.items()):
        raise ValueError('Execution-to-run protocol derivation chain mismatch')
    if canonical_digest({k: v for k, v in freeze.items() if k != 'protocol_sha256'}) != protocol:
        raise ValueError('Forged or changed derived controller protocol digest')
    terms = {}
    for row in rows:
        directory = root / 'run/pairs' / row['instance_id']
        states = {}
        for arm in VARIANTS:
            base = directory / arm
            term = evidence.json(base / 'terminal.json')
            same_identity(term, row)
            if (term.get('arm') != arm or term.get('protocol_sha256') != protocol
                    or term.get('status') not in TERMINAL or term.get('simulation') is not False
                    or term.get('keep_in_denominator') is not True):
                raise ValueError('New arm is not honestly terminal')
            if row['no_model_dispatch']:
                if (term['status'] != row['upstream_status'] or term.get('model_called') is not False
                        or term.get('upstream_status') != row['upstream_status']
                        or any((base / name).exists() for name in ('started.json', 'process.json', 'result.json'))):
                    raise ValueError('No-call terminal was executed or disguised')
            else:
                if term.get('internal_arm') != 'hybrid_safe':
                    raise ValueError('Internal worker identity drift')
                if (base / 'started.json').exists():
                    started = evidence.json(base / 'started.json')
                    same_identity(started, row)
                    if started.get('arm') != arm or started.get('protocol_sha256') != protocol:
                        raise ValueError('Started identity drift')
                elif term['status'] in ('complete', 'worker_failed'):
                    raise ValueError('Result-bearing arm never started')
                if term['status'] in ('complete', 'worker_failed') and not term.get('result_sha256'):
                    raise ValueError('Result-bearing arm has no frozen result')
                if term.get('result_sha256'):
                    evidence.raw(base / 'result.json', term['result_sha256'])
            terms[(row['instance_id'], arm)] = term
            states[arm] = term
        group = evidence.json(directory / 'group_terminal.json')
        same_identity(group, row)
        if (group.get('protocol_sha256') != protocol or group.get('arms') != states
                or group.get('simulation') is not False or group.get('keep_in_denominator') is not True):
            raise ValueError('Missing or inconsistent three-arm group barrier')
    marker = evidence.json(root / 'controller/checkpoints' / (str(len(rows)) + '.json'))
    if (marker.get('status') != 'PREFIX_ALL_ARMS_TERMINAL' or marker.get('n') != len(rows)
            or marker.get('protocol_sha256') != protocol):
        raise ValueError('No authoritative closed-prefix marker')
    return terms


def sealed_scope(root, n, evidence):
    root = Path(root).resolve(strict=True)
    if n not in CUTS:
        raise ValueError('Only frozen report checkpoints are allowed')
    execution = evidence.json(root / 'controller/execution_freeze.json')
    if execution.get('status') != 'EXECUTION_FROZEN_READY':
        raise ValueError('No frozen execution authority')
    protocol = evidence.json(root / 'protocol.json', execution['protocol_sha256'])
    manifest = evidence.json(root / 'manifest.json', execution['manifest_sha256'])
    authority = evidence.json(root / 'authority.json', execution['authority_sha256'])
    all_rows = manifest['records']
    if (manifest.get('n') != 560 or len(all_rows) != 560 or protocol.get('allocated') != 560
            or protocol.get('experiment_id') != 'locbench_qwen3_sfpruner_ablation_20261117'
            or Path(protocol.get('root', '')).resolve() != root
            or len({r['instance_id'] for r in all_rows}) != 560
            or [r['rank'] for r in all_rows] != list(range(1, 561))
            or tuple(manifest.get('arms', ())) != VARIANTS):
        raise ValueError('Wrong frozen560 scope')
    rows = all_rows[:n]
    terms = terminal_barrier(root, rows, evidence, execution)
    checkpoint = evidence.json(root / 'reports/checkpoints' / (str(n) + '.json'))
    report = root / 'reports' / ('cumulative' + str(n))
    if (checkpoint.get('status') != 'REPORT_COMPLETE' or checkpoint.get('allocated') != n
            or Path(checkpoint.get('directory', '')).resolve() != report.resolve()
            or checkpoint.get('models_called') != 0):
        raise ValueError('The sealed CPU report is not complete')
    output = evidence.json(report / 'output_sha256.json', checkpoint['output_manifest_sha256'])
    for name, expected in output.items():
        if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
            raise ValueError('Unsafe sealed output name')
        evidence.raw(report / name, expected)
    allocation = evidence.json(report / 'allocation.json', output['allocation.json'])
    if allocation.get('n') != n or allocation.get('records') != rows:
        raise ValueError('Report allocation differs from immutable prefix')
    summary = evidence.json(report / 'summary.json', output['summary.json'])
    if (summary.get('allocated') != n or summary.get('terminal_barrier_before_gold') is not True
            or summary.get('models_called_by_evaluator') != 0):
        raise ValueError('Sealed report scope/barrier invalid')
    bound = evidence.json(report / 'input_sha256.json', output['input_sha256.json'])
    run_freeze = str((root / 'run/freeze.json').resolve())
    if bound.get(run_freeze) != evidence.hashes[run_freeze]:
        raise ValueError('Derived run protocol differs from the sealed report input')
    return {'root': root, 'n': n, 'rows': rows, 'terms': terms, 'protocol': protocol,
            'authority': authority, 'report': report, 'report_sha': checkpoint['output_manifest_sha256'],
            'input_sha': bound, 'execution': execution}


def safe_relative(path):
    if not isinstance(path, str) or not path or '\\' in path:
        raise ValueError('Invalid source path')
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or '..' in parsed.parts or str(parsed) != path:
        raise ValueError('Unsafe source path')
    return parsed


class Mapper:
    """Gold-blind exact-ID validation; no suffix stripping or Gold lookup."""
    def __init__(self, cache, index, snapshot, base_commit, evidence):
        if cache.get('base_commit') != base_commit:
            raise ValueError('Cache from another base commit')
        self.cache, self.index, self.snapshot, self.evidence = cache, index, Path(snapshot).resolve(), evidence
        self.by_name = defaultdict(list)
        for raw_id, row in cache['functions'].items():
            self.by_name[(row.get('file'), row.get('qualified_name'))].append(raw_id)
        self.loaded = {}

    def unknown(self, reason):
        return {'mapping_status': 'unknown', 'mapping_reason': reason, 'canonical_function_id': None}

    def resolve(self, event):
        raw_id = event.get('function_id')
        fn = self.cache['functions'].get(raw_id)
        if fn is None:
            return self.unknown('exact_runtime_id_absent_from_frozen_cache')
        try:
            path = fn['file']; qn = fn['qualified_name']; safe_relative(path)
            if (not qn or fn.get('id') != raw_id
                    or raw_id != f"{path}::{qn}@{fn['def_line']}"):
                return self.unknown('runtime_id_and_cache_fields_disagree')
            if len(self.by_name[(path, qn)]) != 1:
                return self.unknown('ambiguous_repeated_qualified_name_in_cache')
            item = self.index.get(path)
            if not item or item.get('parse_error'):
                return self.unknown('absent_or_unparseable_base_index')
            defs = [d for d in item['definitions'] if d.get('kind') == 'function' and d.get('qualified_name') == qn]
            if len(defs) != 1:
                return self.unknown('ambiguous_or_absent_base_qualified_name')
            definition = defs[0]
            if (definition['def_line'] != fn['def_line'] or definition['end_line'] != fn['end_line']
                    or fn['start_line'] != fn['def_line']):
                return self.unknown('base_definition_range_mismatch')
            source = (self.snapshot / path).resolve(strict=True)
            if not source.is_relative_to(self.snapshot):
                return self.unknown('source_escaped_base_snapshot')
            if path not in self.loaded:
                raw = self.evidence.raw(source)
                if digest(raw) != item['raw_sha256']:
                    return self.unknown('base_file_raw_sha_mismatch')
                encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
                self.loaded[path] = raw.decode(encoding)
            lines = self.loaded[path].splitlines(keepends=True)
            if not 1 <= fn['def_line'] <= fn['end_line'] <= len(lines):
                return self.unknown('definition_outside_base_source')
            body = ''.join(lines[fn['def_line'] - 1:fn['end_line']])
            body_sha = digest(body.encode('utf-8'))
            if (body_sha != fn['source_sha256'] or body_sha != event.get('source_sha256')
                    or len(body) != fn.get('source_characters')):
                return self.unknown('full_function_source_sha_or_length_mismatch')
            return {'mapping_status': 'verified', 'mapping_reason': 'exact_cache_base_definition_and_source_verified',
                    'canonical_function_id': path + '::' + qn, 'path': path, 'qualified_name': qn,
                    'def_line': fn['def_line'], 'end_line': fn['end_line'],
                    'base_index_start_line': definition['start_line'],
                    'decorator_start_differs': definition['start_line'] != definition['def_line'],
                    'base_file_raw_sha256': item['raw_sha256'], 'full_function_source_sha256': body_sha}
        except (KeyError, TypeError, ValueError, OSError, UnicodeError) as error:
            return self.unknown(type(error).__name__ + ': ' + str(error))


def technical_counts(events):
    counts = Counter(); binding, flagged = set(), set()
    for number, event in enumerate(events):
        name = event.get('event')
        counts['class_fallback_events'] += name == 'pruner_class_fallback'
        counts['binding_fallback_events'] += name == 'judge_binding_fallback'
        counts['tool_identity_help_events'] += name == 'tool_identity_help'
        key = (event.get('step'), event.get('tool'), json.dumps(event.get('arguments'), sort_keys=True))
        if event.get('step') is None or event.get('tool') is None:
            key = ('unlinked_event', number)
        if name == 'judge_binding_fallback': binding.add(key)
        if name == 'prune' and event.get('technical_fallback') is True: flagged.add(key)
    counts['technical_fallback_events'] = len(binding | flagged)
    return dict(counts)


def original_route(p):
    return 'reject' if p <= LOW else 'retain' if p >= HIGH else 'qwen'


def route_fields(event, arm):
    p = event.get('p_yes')
    if (isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p)
            or not 0 <= p <= 1):
        return {'route_valid': False, 'route_error': 'nonfinite_or_invalid_score'}
    original = original_route(p)
    effective = ('retain' if p >= .5 else 'reject') if arm == 'ablation_no_defer' and original == 'qwen' else original
    observed = event.get('route_effective', event.get('route'))
    valid = (event.get('route_original', original) == original and observed == effective
             and event.get('low', LOW) == LOW and event.get('high', HIGH) == HIGH
             and event.get('temperature', TEMPERATURE) == TEMPERATURE)
    return {'route_valid': valid, 'route_error': None if valid else 'frozen_probability_route_or_calibration_mismatch',
            'derived_original_route': original, 'observed_effective_route': observed}


def local_event_rows(events, mapper, iid, arm, event_path):
    rows = []
    for number, event in enumerate(events, 1):
        if event.get('event') != 'local_judge': continue
        if event.get('instance_id') != iid or event.get('arm') != 'hybrid_safe':
            raise ValueError('Local-score event identity drift')
        if arm in VARIANTS and event.get('experimental_arm') != arm:
            raise ValueError('External condition event identity drift')
        rows.append({'instance_id': iid, 'condition': arm, 'event_path': str(event_path), 'event_line': number,
                     'raw_function_id': event.get('function_id'), 'p_yes': event.get('p_yes'),
                     'raw_route': event.get('route'), 'raw_route_original': event.get('route_original'),
                     'raw_route_effective': event.get('route_effective'),
                     'source_sha256': event.get('source_sha256'), 'input_sha256': event.get('input_sha256'),
                     **mapper.resolve(event), **route_fields(event, arm)})
    return rows


def read_events(path, expected, evidence):
    raw = evidence.raw(path, expected)
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete raw events JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def inputs_for_issue(row, scope, evidence):
    public = Path(row['public_input_path'])
    expected = row['public_files_sha256']
    index = evidence.json(public / 'code_index.json', expected['code_index.json'])
    cache = evidence.json(public / 'render_cache.json', expected['render_cache.json'])
    job = evidence.json(row['source_job_path'], row['upstream_files_sha256'][row['source_job_path']])
    same_identity(job, row)
    snapshot = Path(job['snapshot'])
    if not snapshot.is_absolute(): snapshot = Path(row['source_job_path']).parent / snapshot
    if snapshot.resolve() != Path(row['source_snapshot']).resolve():
        raise ValueError('Wrong actual base snapshot')
    if cache.get('index_sha256') != expected['code_index.json']:
        raise ValueError('Cache/index SHA mismatch')
    graph_source = GRAPH_SOURCE
    # The graph producer's original byte SHA is itself inside the immutable
    # render-cache bytes. It need not appear as an independent execution file.
    if not isinstance(cache.get('graph_code_sha256'), str) or len(cache['graph_code_sha256']) != 64:
        raise ValueError('Missing original graph producer binding')
    evidence.raw(graph_source, cache['graph_code_sha256'])
    return Mapper(cache, index, row['source_snapshot'], row['base_commit'], evidence)


def load_postterminal(scope, evidence):
    """Only this function opens private Gold; every public barrier already passed."""
    rows = scope['rows']; bound = scope['input_sha']; wanted = {r['instance_id'] for r in rows}
    work_rows = defaultdict(list)
    for row in rows: work_rows[row['original_work']].append(row)
    gold, old_runs = {}, {}
    for work, selected in work_rows.items():
        freeze_path = Path(work) / 'controller/report_freeze.json'
        frozen = evidence.json(freeze_path, bound[str(freeze_path)])
        allocation = evidence.json(frozen['allocation'], frozen['source_sha256'][frozen['allocation']])
        source_ids = {r['instance_id'] for r in allocation['records']}
        if not source_ids <= wanted or source_ids != {r['instance_id'] for r in selected}:
            raise ValueError('Would open Gold containing an unclosed/future issue')
        values = evidence.json(frozen['gold'], bound[str(Path(frozen['gold']).resolve())])
        if set(values) != source_ids:
            raise ValueError('Gold scope differs from its prior allocation')
        for row in selected:
            value = values[row['instance_id']]
            for key in ('instance_id', 'repo', 'base_commit'):
                if key in value and value[key] != row[key]:
                    raise ValueError('Gold identity/base mismatch')
            if value.get('status') != 'COMPLETE_NONEMPTY' or value.get('set_complete') is not True or not value.get('targets'):
                raise ValueError('Expected frozen complete existing-target Gold')
            gold[row['instance_id']] = set(value['targets'])
        old_runs[work] = Path(frozen['run_root'])
    mapped, technical, availability = [], {}, {}
    for row in rows:
        iid = row['instance_id']
        mapper = inputs_for_issue(row, scope, evidence) if not row['no_model_dispatch'] else None
        for arm in LOCAL:
            directory = (old_runs[row['original_work']] / 'pairs' / iid / 'hybrid_safe') if arm == 'hybrid_safe' else scope['root'] / 'run/pairs' / iid / arm
            if arm == 'hybrid_safe' and not row['no_model_dispatch']:
                term_path = directory / 'terminal.json'
                old_term = evidence.json(term_path, bound[str(term_path.resolve())])
                same_identity(old_term, row)
                if old_term.get('arm') != 'hybrid_safe': raise ValueError('Historical scorer condition identity drift')
            event_path = directory / 'events.jsonl'
            if not event_path.exists():
                if row['no_model_dispatch']:
                    availability[(iid, arm)] = 'explicit_no_call'
                    technical[(iid, arm)] = technical_counts([])
                    continue
                availability[(iid, arm)] = 'events_missing_unknown'
                technical[(iid, arm)] = None
                continue
            expected = bound.get(str(event_path.resolve()))
            if expected is None:
                raise ValueError('Events absent from sealed report provenance: ' + str(event_path))
            events = read_events(event_path, expected, evidence)
            availability[(iid, arm)] = 'recorded'
            technical[(iid, arm)] = technical_counts(events)
            if mapper is None:
                if any(e.get('event') == 'local_judge' for e in events):
                    raise ValueError('No-call source unexpectedly has local scores')
                continue
            mapped += local_event_rows(events, mapper, iid, arm, event_path)
    return gold, mapped, technical, availability


def aggregate(ids, gold, events, technical, availability, *, draws=5000, seed=20261110):
    from .stats import issue_risk_ci, common_visited_comparison, exact_binomial_ci
    by_arm = {}; visits = {}; reject_rows = []
    for arm in LOCAL:
        per_issue = {iid: {'visited': set(), 'rejected': set(), 'gold_visits': 0, 'gold_rejects': 0,
                           'unknown_events': 0, 'score_events': 0} for iid in ids}
        totals = Counter(); arm_events = [e for e in events if e['condition'] == arm]
        for event in arm_events:
            item = per_issue[event['instance_id']]; item['score_events'] += 1
            known = event['mapping_status'] == 'verified' and event['route_valid']
            event['is_gold'] = (event['canonical_function_id'] in gold[event['instance_id']]) if known else None
            totals['successful_local_score_events'] += 1
            totals['verified_identity_events'] += event['mapping_status'] == 'verified'
            totals['decorator_start_differs_from_def_line_events'] += bool(event.get('decorator_start_differs'))
            if event['route_valid']:
                original, effective = event['derived_original_route'], event['observed_effective_route']
                totals['route_' + effective] += 1; totals['original_gray_events'] += original == 'qwen'
                totals['normal_gray_to_qwen_events'] += original == 'qwen' and effective == 'qwen'
                totals['gray_direct_override_events'] += original == 'qwen' and effective != 'qwen'
            if not known:
                totals['unknown_attribution_events'] += 1; item['unknown_events'] += 1
            elif event['is_gold']:
                fid = event['canonical_function_id']; item['visited'].add(fid); item['gold_visits'] += 1
                if event['observed_effective_route'] == 'reject':
                    item['rejected'].add(fid); item['gold_rejects'] += 1
        missing = [iid for iid in ids if availability[(iid, arm)] == 'events_missing_unknown']
        complete = not missing and not totals['unknown_attribution_events']
        v = sum(len(x['visited']) for x in per_issue.values()); r = sum(len(x['rejected']) for x in per_issue.values())
        vt = sum(bool(x['visited']) for x in per_issue.values()); rt = sum(bool(x['rejected']) for x in per_issue.values())
        ev = sum(x['gold_visits'] for x in per_issue.values()); er = sum(x['gold_rejects'] for x in per_issue.values())
        ci = issue_risk_ci([{'visited': len(x['visited']), 'rejected': len(x['rejected'])} for x in per_issue.values()], draws=draws, seed=seed) if complete else None
        fallback = Counter()
        for iid in ids:
            if technical[(iid, arm)] is not None: fallback.update(technical[(iid, arm)])
        by_arm[arm] = {'local_scoring_applicable': True, 'allocated': len(ids), **dict(totals),
            'attribution_complete': complete, 'event_log_missing_tasks': missing,
            'gold_available_unique_identities': sum(len(x) for x in gold.values()),
            'gold_score_visits': ev if complete else None, 'gold_direct_reject_events': er if complete else None,
            'gold_visited_unique_identities': v if complete else None, 'gold_direct_rejected_unique_identities': r if complete else None,
            'gold_visited_tasks': vt if complete else None, 'gold_direct_rejected_tasks': rt if complete else None,
            'known_lower_bounds': {'gold_score_visits': ev, 'gold_direct_reject_events': er,
                'gold_visited_unique_identities': v, 'gold_direct_rejected_unique_identities': r,
                'gold_visited_tasks': vt, 'gold_direct_rejected_tasks': rt},
            'event_conditional_risk': er / ev if complete and ev else None,
            'unique_identity_conditional_risk': ci,
            'task_any_gold_reject_conditional_risk': {'numerator': rt if complete else None, 'denominator': vt if complete else None,
                'point': rt / vt if complete and vt else None,
                'clopper_pearson_ci95': exact_binomial_ci(rt, vt) if complete else None,
                'post_checkpoint100_auxiliary_description_not_preregistered_test': True,
                'unit': 'issue with at least one successfully scored Gold identity; same-repo dependence not adjusted'},
            'class_and_technical_counts_known_sum': dict(fallback),
            'class_and_technical_counts_complete': not missing,
            'unvisited_gold_is_not_retained': True}
        visits[arm] = {iid: {'visited': x['visited'], 'rejected': x['rejected']} for iid, x in per_issue.items()}
        for iid, item in per_issue.items():
            if item['rejected']:
                reject_rows.append({'instance_id': iid, 'condition': arm, 'gold_direct_reject_events': item['gold_rejects'],
                    'gold_visited_unique_identities': len(item['visited']), 'gold_direct_rejected_unique_identities': len(item['rejected']),
                    'rejected_canonical_functions': sorted(item['rejected']), 'attribution_complete_for_issue': not item['unknown_events'] and iid not in missing})
    by_arm['baseline'] = {'local_scoring_applicable': False, 'allocated': len(ids),
                         'gold_score_visits': None, 'gold_direct_reject_events': None,
                         'unique_identity_conditional_risk': None, 'reason': 'Baseline main-pruner judgments are outside local-scorer risk attribution.'}
    common = {}
    for arm in VARIANTS:
        common[arm] = common_visited_comparison(visits['hybrid_safe'], visits[arm], draws=draws, seed=seed)
        common[arm]['verified_visit_attribution_complete'] = by_arm['hybrid_safe']['attribution_complete'] and by_arm[arm]['attribution_complete']
        common[arm]['reference'] = 'hybrid_safe'; common[arm]['comparison'] = arm
        if not common[arm]['verified_visit_attribution_complete']:
            old = common[arm]
            unknown = {name: {'unknown_attribution_events': by_arm[name].get('unknown_attribution_events', 0),
                             'event_log_missing_tasks': by_arm[name]['event_log_missing_tasks']}
                       for name in ('hybrid_safe', arm)}
            common[arm] = {'reference': 'hybrid_safe', 'comparison': arm,
                'exploratory': True, 'included_in_registered_nine_tests': False,
                'verified_visit_attribution_complete': False,
                'status': 'NA_INCOMPLETE_ATTRIBUTION_UNKNOWN_IS_NOT_NON_GOLD',
                'reference_risk': None, 'comparison_risk': None, 'comparison_minus_reference': None,
                'reference_ci95': None, 'comparison_ci95': None, 'difference_ci95': None,
                'degenerate_bootstrap': None, 'unknown_reasons_by_condition': unknown,
                'verified_lower_bound_counts_only': {key: old[key] for key in
                    ('issues', 'issues_with_common_visits', 'common_visited_identities',
                     'reference_rejected_identities', 'comparison_rejected_identities', 'per_issue')},
                'reason': 'An unknown event can be a rejection of a previously verified shared Gold identity; verified-only counts cannot determine the risk, contrast or confidence interval.'}
    return {'conditions': {arm: by_arm[arm] for arm in ARMS}, 'common_visited_exploratory': common}, reject_rows


def write_csv(path, rows, fields):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fields); writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key), (dict, list)) else ('NA' if row.get(key) is None else row.get(key)) for key in fields})


def run(root, n, out, *, draws=5000, seed=20261110):
    out = Path(out)
    if out.exists(): raise FileExistsError('Never overwrite an analysis output')
    allowed = Path(root).resolve() / 'reports/risk_revision_v3'
    if not out.resolve().is_relative_to(allowed) or out.resolve() == allowed:
        raise ValueError('Write only inside the independent reports/risk_revision_v3 tree')
    if draws != 5000 or seed != 20261110: raise ValueError('Frozen secondary bootstrap settings required')
    evidence = Evidence(); scope = sealed_scope(root, n, evidence)
    plan_path = scope['root'] / 'audits/final_secondary_analysis_plan.json'
    plan = evidence.json(plan_path)
    if plan['supplementary_gold_risk_CI']['seed'] != seed or plan['supplementary_gold_risk_CI']['draws'] != draws:
        raise ValueError('Secondary descriptive plan changed')
    addendum_path = scope['root'] / 'audits/final_secondary_analysis_addendum_cp_taskrisk.json'
    addendum = evidence.json(addendum_path)
    if (addendum.get('base_plan_sha256') != evidence.hashes[str(plan_path.resolve())]
            or addendum.get('status') != 'POST_FIRST100_DESCRIPTIVE_INTERVAL_ADDENDUM_NOT_PRIMARY_TEST_CHANGE'):
        raise ValueError('Missing explicit post-first100 interval addendum')
    gold, events, technical, availability = load_postterminal(scope, evidence)
    ids = [r['instance_id'] for r in scope['rows']]
    values, reject_rows = aggregate(ids, gold, events, technical, availability, draws=draws, seed=seed)
    # Existing sealed per-issue Hit fields are descriptive context, not re-scored here.
    with (scope['report'] / '逐题定位与资源.csv').open(encoding='utf-8-sig', newline='') as stream:
        metrics = {r['instance_id']: r for r in csv.DictReader(stream)}
    for row in reject_rows:
        for k in (1, 3, 5): row['existing_localization_hit' + str(k)] = metrics[row['instance_id']].get(row['condition'] + '_function_hit' + str(k))
        row['causality_warning'] = 'Local direct rejection alone neither proves final localization failure nor what a Qwen gray review would decide.'
    source_sha = {str(p.resolve()): digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}
    value = {'status': 'INDEPENDENT_OFFLINE_RISK_V3_POSTTERMINAL', 'allocated': n,
        'created_unix': time.time(), 'arms': list(ARMS), 'source_sha256': source_sha,
        'sealed_report': str(scope['report']), 'sealed_report_output_manifest_sha256': scope['report_sha'],
        'primary_metrics_changed': False, 'original_risk_table_status': 'Gold-attribution false-zero schema bug: runtime @def_line IDs were compared directly with canonical Gold; sealed files retained.',
        'identity_mapping': 'Exact cache ID + unique base qualified_name + AST def_line/end_line + file and full function source SHA, before Gold lookup; never strip suffix using Gold.',
        'unknown_identity_policy': 'Unknown/ambiguous/source mismatch is NA, never nongold; incomplete attribution yields known lower bounds and no total risk estimate.',
        'bootstrap_plan': plan['supplementary_gold_risk_CI'],
        'post_checkpoint100_auxiliary_amendment': {'method': 'Clopper-Pearson 95% issue-binomial descriptive interval for any-Gold-rejection among visited-Gold issues',
            'reason': 'Zero-event percentile bootstrap can degenerate to [0,0], which does not establish true zero risk.',
            'receipt': str(addendum_path), 'receipt_sha256': evidence.hashes[str(addendum_path.resolve())],
            'not_part_of_nine_primary_hypothesis_tests': True},
        'interpretation': 'Conditional visit risk and common-visited analysis are descriptive/exploratory. Different visit sets and same-repo dependence limit causal interpretation. Unvisited Gold is not retained. Local rejection does not establish final failure or counterfactual Qwen retention.',
        'new_model_calls': 0, 'GPU_used': False, 'sealed_test_opened': False, 'historical_outputs_modified': False,
        'future_gold_opened': False, **values}
    evidence.unchanged()
    out.mkdir(parents=True)
    (out / 'corrected_risk.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    fields = sorted({key for row in events for key in row})
    write_csv(out / '逐事件身份与风险.csv', events, fields or ['instance_id', 'condition', 'mapping_status', 'is_gold'])
    write_csv(out / 'Gold直剪逐题.csv', reject_rows, ['instance_id','condition','gold_direct_reject_events','gold_visited_unique_identities','gold_direct_rejected_unique_identities','rejected_canonical_functions','attribution_complete_for_issue','existing_localization_hit1','existing_localization_hit3','existing_localization_hit5','causality_warning'])
    notes = ['# Gold访问与直接剪除：独立离线修订v3', '',
        f'范围为已封存并闭合的前{n}题。原主定位指标仍有效；原风险表将带@def_line的运行时函数ID直接匹配canonical Gold，造成Gold访问与直剪假零。旧报告不改写，本目录为独立修订。', '',
        '| 条件 | Gold访问事件 | 访问Gold身份 | Gold直剪事件 | 直剪Gold身份 | 条件风险（身份） |', '|---|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        a=value['conditions'][arm]; risk=a.get('unique_identity_conditional_risk'); point=risk.get('point') if risk else None
        show=lambda x: 'NA' if x is None else str(x)
        notes.append('|'+ '|'.join([arm,show(a.get('gold_score_visits')),show(a.get('gold_visited_unique_identities')),show(a.get('gold_direct_reject_events')),show(a.get('gold_direct_rejected_unique_identities')),show(point)])+'|')
    notes += ['', '身份先与冻结缓存精确匹配，再核base库存的def_line/end_line及原文件/完整函数SHA；装饰器start_line不等于def_line，__init__与嵌套限定名保留。未知或歧义不算非Gold。', '',
        '身份条件风险使用issue-bootstrap 5000次、seed=20261110；重复评分保留事件账、身份账按issue内去重。0分母为NA，未访问不算保留。零误剪时bootstrap可退化为[0,0]，不能证明真实零风险。另报访问Gold任务中发生任一直剪的Clopper-Pearson描述区间；该辅助项是在首100诊断后增加，并非预注册9项主检验。', '',
        '共同已访问Gold身份比较为探索性分析，未加入9项Holm主检验。访问集合可能由流程影响，且未校正同仓相关，不能解释为纯粹的因果风险效应。', '',
        '局部直接拒绝不必然造成最终定位失败，也不能据此假定灰区Qwen会保留。Gold直剪逐题CSV附原定位Hit只作描述，未经修改、重跑或重新挑选。', '',
        'baseline没有此本地剪枝评分器，相关风险为不适用NA。类请求、正常灰区及技术回退分列，未知事件/用量不填零。原sealed报告、模型、预测、概率和路由均未改动；无GPU、无新增模型调用。', '',
        '复现：`.venv-v5/bin/python -B -m code_locbench_ablation_risk_v3_20261117.analysis --root <R2> --n '+str(n)+' --out <全新输出目录>`。运行前必须已有对应REPORT_COMPLETE与三臂组全终态；输出目录不得覆盖。', '']
    (out / '风险修订说明.md').write_text('\n'.join(notes))
    (out / 'input_sha256.json').write_text(json.dumps(evidence.hashes, ensure_ascii=False, indent=2)+'\n')
    (out / 'output_sha256.json').write_text(json.dumps({p.name:digest(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()},ensure_ascii=False,indent=2)+'\n')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--n', type=int, choices=CUTS, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args=parser.parse_args(); result=run(args.root,args.n,args.out)
    print(json.dumps({'status':result['status'],'allocated':result['allocated'],'new_model_calls':0}))


if __name__ == '__main__': main()
