"""Independent full Java128 metrics audit; standard library only.

All inference and analysis closure checks precede any Gold/index/result parsing.
This module does not import the production evaluator, normalizer, model code or
provider. The view's already frozen exported ranks are the evaluation inputs;
this audit neither normalizes names nor repairs model answers.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import time


ARMS = ('cosil', 'sfpruner', 'locagent')
UNITS = ('file', 'function')
METRICS = ('hit1', 'hit3', 'hit5', 'precision5', 'recall5', 'f1_5', 'allcoverage5', 'mrr10')
BINARY = ('hit1', 'hit3', 'hit5', 'allcoverage5')
TERMINAL = {'complete', 'partial', 'worker_failed', 'timed_out', 'dependency_blocked',
            'preparation_blocked', 'preparation_failed', 'failed', 'error'}
SEED, DRAWS = 20261117, 2000
EXPECTED_N, EXPECTED_FILE_N, EXPECTED_FUNCTION_N = 128, 125, 117


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def issue_error(errors, kind, detail, **scope):
    errors.append({'kind': kind, 'detail': str(detail), **scope})


class Reader:
    """Record exact input bytes; Gold reads are an explicit post-fence operation."""
    def __init__(self):
        self.artifacts = {}
        self.gold_opened = False
        self.gate_passed = False

    def json(self, path, category):
        path = Path(path)
        if category == 'gold':
            if not self.gate_passed:
                raise RuntimeError('Gold is forbidden before the complete inference/analysis fence')
            self.gold_opened = True
        raw = path.read_bytes()
        self.artifacts[str(path.absolute())] = {'sha256': hashlib.sha256(raw).hexdigest(), 'category': category}
        return json.loads(raw)

    def bind(self, path, expected, category, errors):
        path = Path(path)
        private_parts = {'evaluator_private', 'sealed', 'sealed_test', 'sealed_tests'}
        resolved = path.resolve()
        if not self.gate_passed and (private_parts.intersection((*path.parts, *resolved.parts))
                or {path.name, resolved.name}.intersection({'gold.json', 'train.json', 'val.json', 'test.json',
                                                          'train.jsonl', 'val.jsonl', 'test.jsonl'})):
            issue_error(errors, 'private_data_binding_forbidden_before_fence', path)
            return False
        actual = digest(path) if path.is_file() else None
        self.artifacts[str(path.absolute())] = {'sha256': actual, 'category': category}
        if actual != expected:
            issue_error(errors, 'bound_sha_mismatch', path, expected=expected, actual=actual)
        return actual == expected


def verify_source_freeze(path, reader, errors, pending):
    path = Path(path)
    if not path.is_file():
        pending.append('Missing source freeze: ' + str(path))
        return
    frozen = reader.json(path, 'source_freeze')
    if not frozen.get('commit') or not frozen.get('files_sha256'):
        issue_error(errors, 'source_freeze_incomplete', path)
        return
    for source, expected in frozen['files_sha256'].items():
        # These are source/config artifacts, not inference weights or datasets.
        if Path(source).suffix not in ('.py', '.json', '.md', '.txt', '.sh'):
            issue_error(errors, 'unexpected_source_binding_scope', source)
            continue
        reader.bind(source, expected, 'execution_or_analysis_source', errors)


def inference_fence(root, roster, reader, errors, pending, *, view=False):
    completion = root / 'run/completion.json'
    if not completion.is_file():
        pending.append('Inference completion absent: ' + str(completion))
    else:
        marker = reader.json(completion, 'inference_completion')
        if marker.get('status') != 'COMPLETE' or marker.get('allocated') != EXPECTED_N or marker.get('groups') != EXPECTED_N:
            issue_error(errors, 'invalid_inference_completion', completion)
    for row in roster:
        iid = row['instance_id']
        group = root / 'run' / iid
        group_path = group / 'group_terminal.json'
        group_record = None
        if not group_path.is_file():
            pending.append('Group terminal absent: ' + str(group_path))
        else:
            group_record = reader.json(group_path, 'group_terminal')
            if group_record.get('instance_id') != iid or group_record.get('status') != 'group_terminal':
                issue_error(errors, 'invalid_group_terminal', group_path)
        for arm in ARMS:
            terminal_path = group / arm / 'terminal.json'
            if not terminal_path.is_file():
                pending.append('Arm terminal absent: ' + str(terminal_path))
                continue
            terminal = reader.json(terminal_path, 'arm_terminal')
            if group_record is not None and group_record.get('arms', {}).get(arm) != terminal:
                issue_error(errors, 'group_arm_terminal_disagrees', terminal_path)
            if terminal.get('instance_id') != iid or terminal.get('arm') != arm or terminal.get('status') not in TERMINAL or terminal.get('keep_in_denominator') is not True:
                issue_error(errors, 'arm_terminal_identity_or_status', terminal_path)
            result = group / arm / 'result.json'
            if result.exists():
                reader.bind(result, terminal.get('result_sha256'), 'terminal_bound_raw_result', errors)
            elif terminal.get('status') in ('complete', 'partial'):
                issue_error(errors, 'successful_terminal_missing_result', terminal_path)
            elif terminal.get('result_sha256') is not None:
                issue_error(errors, 'missing_result_has_nonempty_binding', terminal_path)
            if view and terminal.get('offline_view_only') is not True:
                issue_error(errors, 'derived_terminal_not_marked_offline', terminal_path)


def closed_completion(path, expected_status, reader, errors, pending):
    path = Path(path)
    if not path.is_file():
        pending.append('Analysis completion absent: ' + str(path))
        return None
    result = reader.json(path, 'analysis_completion')
    if result.get('status') != expected_status:
        issue_error(errors, 'analysis_not_closed', path, status=result.get('status'))
    if not isinstance(result.get('outputs_sha256'), dict) or not result['outputs_sha256']:
        issue_error(errors, 'analysis_completion_without_output_bindings', path)
    for name, expected in result.get('outputs_sha256', {}).items():
        reader.bind(name, expected, 'closed_analysis_delivery', errors)
    if result.get('new_model_calls', 0) != 0:
        issue_error(errors, 'analysis_unexpected_model_calls', path)
    return result


def initial_fence(root, evaluation_dir, view_root, reader):
    """No Gold, public inventory or result JSON is parsed by this fence."""
    errors, pending = [], []
    allocation = root / 'allocation.json'
    if not allocation.is_file():
        return [], [{'kind': 'allocation_missing', 'detail': str(allocation)}], []
    value = reader.json(allocation, 'allocation')
    roster = value.get('records', [])
    ids = [r.get('instance_id') for r in roster]
    if value.get('n') != EXPECTED_N or len(roster) != EXPECTED_N or len(set(ids)) != EXPECTED_N:
        issue_error(errors, 'full128_roster_required', allocation)
        return [], errors, pending
    for row in roster:
        iid = row.get('instance_id')
        if not isinstance(iid, str) or not iid or '/' in iid or '\\' in iid or iid in ('.', '..'):
            issue_error(errors, 'unsafe_issue_id', iid)
    if errors:
        return [], errors, pending
    verify_source_freeze(root / 'execution_freeze.json', reader, errors, pending)
    if (root / 'execution_freeze.json').is_file():
        execution = reader.json(root / 'execution_freeze.json', 'source_freeze')
        if execution.get('allocation_sha256') is not None:
            reader.bind(allocation, execution['allocation_sha256'], 'frozen_allocation', errors)
    verify_source_freeze(root / 'audits/analysis_execution_freeze.json', reader, errors, pending)
    inference_fence(root, roster, reader, errors, pending)
    analysis = closed_completion(root / 'analysis_supervisor/completion.json',
        'ANALYSIS_READY_FOR_INDEPENDENT_REVIEW', reader, errors, pending)
    if view_root != root:
        view_allocation = view_root / 'allocation.json'
        if not view_allocation.exists():
            pending.append('View allocation absent: ' + str(view_allocation))
        elif reader.json(view_allocation, 'view_allocation') != value:
            issue_error(errors, 'view_changed_full_roster_or_order', view_allocation)
        verify_source_freeze(root / 'audits/signature_view_execution_freeze.json', reader, errors, pending)
        inference_fence(view_root, roster, reader, errors, pending, view=True)
        closure = closed_completion(root / 'signature_view_supervisor/completion.json',
            'NORMALIZED_REPORTS_READY_FOR_INDEPENDENT_REVIEW', reader, errors, pending)
        manifest_path = view_root / 'view_manifest.json'
        if not manifest_path.is_file():
            pending.append('View manifest absent: ' + str(manifest_path))
        else:
            manifest = reader.json(manifest_path, 'view_manifest')
            if manifest.get('status') != 'COMPLETE' or manifest.get('allocated') != EXPECTED_N or manifest.get('new_model_calls') != 0 or manifest.get('normalization_uses_Gold') is not False:
                issue_error(errors, 'view_manifest_protocol_drift', manifest_path)
            if Path(manifest.get('original_root', '')).resolve() != root or manifest.get('source_allocation_sha256') != digest(allocation):
                issue_error(errors, 'view_original_root_or_allocation_changed', manifest_path)
            if closure and closure.get('view_manifest_sha256') != digest(manifest_path):
                issue_error(errors, 'view_completion_manifest_sha_mismatch', manifest_path)
            if closure and analysis and closure.get('original_analysis_completion_sha256') != digest(root / 'analysis_supervisor/completion.json'):
                issue_error(errors, 'view_original_analysis_binding_changed', manifest_path)
            seen = set()
            for item in manifest.get('records', []):
                iid, arm = item.get('instance_id'), item.get('arm')
                if iid not in ids or arm not in ARMS or (iid, arm) in seen:
                    issue_error(errors, 'view_manifest_record_scope', item)
                    continue
                seen.add((iid, arm))
                for base, name, expected in [
                    (root, 'result.json', item.get('original_result_sha256')),
                    (view_root, 'result.json', item.get('derived_result_sha256')),
                    (view_root, 'normalization_provenance.json', item.get('provenance_sha256'))]:
                    reader.bind(base / 'run' / iid / arm / name, expected, 'view_source_binding', errors)
            for row in roster:
                for arm in ARMS:
                    if (root / 'run' / row['instance_id'] / arm / 'result.json').exists() and (row['instance_id'], arm) not in seen:
                        issue_error(errors, 'view_manifest_omitted_existing_result', row['instance_id'], arm=arm)
    for filename in ('per_issue.json', 'summary.json', 'per_issue.csv'):
        if not (evaluation_dir / filename).is_file():
            pending.append('Evaluation output absent: ' + str(evaluation_dir / filename))
    return roster, errors, pending


def canonical_slots(raw, index, unit):
    """No cleanup, fuzzy match, alias expansion or signature normalization."""
    if not isinstance(raw, list):
        return [], ['ranking_field_not_list']
    inventory = Counter()
    for path, item in index.items():
        for definition in item.get('definitions', []):
            if definition.get('kind') == 'function':
                inventory[definition.get('canonical_id', path + '::' + definition.get('qualified_name', ''))] += 1
    slots, seen = [], set()
    for rank, value in enumerate(raw, 1):
        identity, reason = None, None
        if unit == 'file':
            identity = value if isinstance(value, str) else value.get('path') if isinstance(value, dict) else None
            if not isinstance(identity, str):
                reason = 'invalid_file_slot'
            elif identity not in index:
                reason = 'file_not_in_base_java_inventory'
        else:
            if isinstance(value, str):
                identity = value
            elif isinstance(value, dict):
                path, name, supplied = value.get('path'), value.get('qualified_name'), value.get('canonical_id')
                if isinstance(path, str) and isinstance(name, str):
                    identity = path + '::' + name
                    if supplied is not None and supplied != identity:
                        reason = 'canonical_id_disagrees_with_fields'
                elif isinstance(supplied, str) and 'path' not in value and 'qualified_name' not in value:
                    identity = supplied
                else:
                    reason = 'invalid_function_slot'
            else:
                reason = 'invalid_function_slot'
            if reason is None and inventory[identity] != 1:
                reason = 'ambiguous_or_nonexistent_method_identity'
        if reason is None:
            if identity in seen:
                reason = 'duplicate_rank_slot'
            seen.add(identity)
        slots.append({'rank': rank, 'raw': value, 'canonical_id': identity,
                      'valid': reason is None, 'reason': reason})
    return slots, []


def ranking(result, index, arm):
    file_fields = ('ranked_files',) if arm == 'locagent' else ('ranked_edit_files', 'file_rank_after_reflection', 'predicted_files')
    file_field = next((k for k in file_fields if k in result), None)
    function_field = next((k for k in ('ranked_functions', 'predicted_functions') if k in result), None)
    files, a = canonical_slots(result.get(file_field, []) if file_field else [], index, 'file')
    methods, b = canonical_slots(result.get(function_field, []) if function_field else [], index, 'function')
    return {'file': files, 'function': methods, 'file_field': file_field, 'function_field': function_field,
            'field_errors': a + b}


def measure(slots, targets):
    targets = set(targets)
    if not targets:
        raise ValueError('No evaluable target set')
    correct = {k: {s['canonical_id'] for s in slots[:k] if s['valid']} & targets for k in (1, 3, 5)}
    true_count, predicted = len(correct[5]), min(5, len(slots))
    p = true_count / predicted if predicted else 0.
    r = true_count / len(targets)
    return {'hit1': bool(correct[1]), 'hit3': bool(correct[3]), 'hit5': bool(correct[5]),
        'tp5': true_count, 'prediction_slots5': predicted, 'target_count': len(targets),
        'precision5': p, 'recall5': r, 'f1_5': 2 * p * r / (p + r) if p + r else 0.,
        'allcoverage5': true_count == len(targets),
        'mrr10': next((1 / item['rank'] for item in slots[:10] if item['valid'] and item['canonical_id'] in targets), 0.)}


def wilson(count, total):
    if not total:
        return None
    z = statistics.NormalDist().inv_cdf(.975)
    p, z2 = count / total, z * z
    midpoint = (p + z2 / (2 * total)) / (1 + z2 / total)
    margin = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / (1 + z2 / total)
    return [max(0., midpoint - margin), min(1., midpoint + margin)]


def bootstrap(values, draws=DRAWS, seed=SEED):
    if not values:
        return None
    if len(set(values)) == 1:
        return [values[0], values[0]]
    randomizer = random.Random(seed)
    n = len(values)
    samples = sorted(sum(values[randomizer.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return [samples[int((draws - 1) * .025)], samples[int((draws - 1) * .975)]]


def aggregate(rows):
    result = {'denominator': len(rows)}
    for key in BINARY:
        count = sum(bool(r[key]) for r in rows)
        result[key] = {'numerator': count, 'denominator': len(rows), 'value': count / len(rows) if rows else None,
                       'ci95': wilson(count, len(rows)), 'ci_method': 'Wilson_score'}
    for key in ('precision5', 'recall5', 'f1_5', 'mrr10'):
        values = [r[key] for r in rows]
        result[key] = {'numerator_sum': sum(values), 'denominator': len(values),
            'value': statistics.fmean(values) if values else None, 'ci95': bootstrap(values),
            'ci_method': 'task_percentile_bootstrap', 'draws': DRAWS, 'seed': SEED}
    return result


def paired(records):
    output = {}
    for a, b in (('cosil', 'sfpruner'), ('cosil', 'locagent'), ('sfpruner', 'locagent')):
        table = output[a + '_vs_' + b] = {}
        for unit in UNITS:
            table[unit] = {}
            for key in ('hit1', 'hit3', 'hit5'):
                rows = [r for r in records if r['arms'][a]['metrics'][unit] is not None]
                pairs = [(int(r['arms'][a]['metrics'][unit][key]), int(r['arms'][b]['metrics'][unit][key])) for r in rows]
                cells = Counter(pairs)
                only_a, only_b = cells[(1, 0)], cells[(0, 1)]
                discordant = only_a + only_b
                p = min(1., 2 * sum(math.comb(discordant, k) for k in range(min(only_a, only_b) + 1)) / (2 ** discordant)) if discordant else 1.
                delta = [right - left for left, right in pairs]
                table[unit][key] = {'n': len(pairs), 'both_success': cells[(1, 1)],
                    'only_a': only_a, 'only_b': only_b, 'both_failure': cells[(0, 0)],
                    'b_minus_a': statistics.fmean(delta) if delta else None,
                    'paired_ci95': bootstrap(delta), 'exact_mcnemar_p': p,
                    'inference_calls_added': 0, 'equivalence_claimed': False}
    return output


def close_enough(actual, expected):
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-12)
    if isinstance(actual, dict) and isinstance(expected, dict):
        return set(actual) == set(expected) and all(close_enough(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(close_enough(x, y) for x, y in zip(actual, expected))
    return actual == expected


def same(errors, checks, key, actual, expected, **scope):
    ok = close_enough(actual, expected)
    checks[key] += 1
    if not ok:
        issue_error(errors, 'reported_value_mismatch', key, independent=actual, reported=expected, **scope)
    return ok


def reconstruct(root, view_root, roster, reader, errors):
    records = []
    qualification = reader.json(root / 'audits/evaluator_qualification_frozen.json', 'frozen_evaluator_qualification')
    for key, expected in (('allocated', EXPECTED_N), ('file_evaluable', EXPECTED_FILE_N),
                          ('function_evaluable', EXPECTED_FUNCTION_N)):
        if qualification.get(key) != expected:
            issue_error(errors, 'frozen_qualification_count_changed', key, actual=qualification.get(key), expected=expected)
    gold_bindings = qualification.get('gold_files_sha256', {})
    if len(gold_bindings) != EXPECTED_N:
        issue_error(errors, 'frozen_qualification_not_bound_to128_gold_files', len(gold_bindings))
    for row in roster:
        iid = row['instance_id']
        index_path, gold_path = view_root / 'public' / iid / 'code_index.json', view_root / 'evaluator_private' / iid / 'gold.json'
        index = reader.json(index_path, 'public_index')
        gold = reader.json(gold_path, 'gold')
        raw_gold = root / 'evaluator_private' / iid / 'gold.json'
        expected_gold = gold_bindings.get(str(raw_gold))
        if expected_gold is None:
            issue_error(errors, 'gold_missing_from_frozen_qualification', raw_gold)
        else:
            reader.bind(raw_gold, expected_gold, 'frozen_gold_byte_binding', errors)
        if digest(raw_gold) != digest(gold_path):
            issue_error(errors, 'view_changed_gold_bytes', iid)
        for key in ('instance_id', 'repo', 'base_commit'):
            if gold.get(key) != row[key]:
                issue_error(errors, 'gold_allocation_identity_mismatch', iid, field=key)
        if gold.get('base_index_sha256') is not None and gold['base_index_sha256'] != digest(index_path):
            issue_error(errors, 'gold_index_sha_mismatch', iid)
        if digest(root / 'public' / iid / 'code_index.json') != digest(index_path):
            issue_error(errors, 'view_changed_base_inventory', iid)
        inventory = Counter(path + '::' + d['qualified_name'] for path, entry in index.items()
                            for d in entry.get('definitions', []) if d.get('kind') == 'function')
        for path, entry in index.items():
            if not path.endswith('.java') or Path(path).is_absolute() or '..' in Path(path).parts:
                issue_error(errors, 'unsafe_or_nonjava_inventory_path', path, instance_id=iid)
            for d in entry.get('definitions', []):
                if d.get('kind') == 'function' and d.get('canonical_id', path + '::' + d['qualified_name']) != path + '::' + d['qualified_name']:
                    issue_error(errors, 'inventory_canonical_id_inconsistent', iid)
        for unit, key in (('file', 'file_targets'), ('function', 'function_targets')):
            targets = gold.get(key)
            if not isinstance(targets, list) or any(not isinstance(t, str) for t in targets) or len(targets) != len(set(targets)):
                raise ValueError('Invalid Gold target list for ' + iid + '/' + unit)
            if gold.get(unit + '_evaluable') is True and not targets:
                issue_error(errors, 'evaluable_gold_empty', iid, unit=unit)
        if gold.get('function_evaluable') is True:
            if gold.get('existing_target_set_complete') is not True or any(inventory[t] != 1 for t in gold['function_targets']):
                issue_error(errors, 'evaluable_method_gold_incomplete_or_absent', iid)
        if any(path not in index for path in gold['file_targets']):
            issue_error(errors, 'existing_file_gold_outside_inventory', iid)
        record = {**row, 'selected_for_evaluation': True, 'gold_status': gold.get('function_status', 'ERROR_MISSING_STATUS'),
            'gold_error': None, 'file_evaluable': gold.get('file_evaluable'),
            'function_evaluable': gold.get('function_evaluable'), 'gold_files': gold['file_targets'],
            'gold_functions': gold['function_targets'], 'gold_limitations': gold.get('limitations'), 'arms': {}}
        for arm in ARMS:
            directory = view_root / 'run' / iid / arm
            terminal = reader.json(directory / 'terminal.json', 'arm_terminal')
            result_path = directory / 'result.json'
            result = reader.json(result_path, 'raw_or_frozen_view_result') if result_path.is_file() else {}
            if view_root != root:
                origin_path = root / 'run' / iid / arm / 'result.json'
                original_terminal = reader.json(origin_path.with_name('terminal.json'), 'original_arm_terminal')
                mutable = {'result_sha256', 'offline_view_only'}
                if ({k: v for k, v in original_terminal.items() if k not in mutable}
                        != {k: v for k, v in terminal.items() if k not in mutable}):
                    issue_error(errors, 'derived_view_changed_terminal_outcome_or_timing', iid, arm=arm)
            if view_root != root and result:
                original = reader.json(origin_path, 'original_inference_result')
                meta = result.get('offline_identity_view', {})
                if (Path(meta.get('original_result', '')).resolve() != origin_path.resolve()
                        or meta.get('original_result_sha256') != digest(origin_path)
                        or meta.get('base_index_sha256') != digest(index_path)
                        or meta.get('new_model_calls') != 0
                        or meta.get('Gold_read_for_normalization') is not False):
                    issue_error(errors, 'derived_result_source_identity_binding', iid, arm=arm)
                for key in ('status', 'terminal', 'usage', 'elapsed_seconds', 'generation_seconds',
                            'tool_elapsed_seconds', 'num_samples', 'ranking_method', 'actual_request_model',
                            'protocol', 'raw_output', 'stage_resources', 'prompt_tokens', 'completion_tokens'):
                    if result.get(key) != original.get(key):
                        issue_error(errors, 'derived_view_changed_inference_field', iid, arm=arm, field=key)
                file_key = 'ranked_files' if arm == 'locagent' else 'ranked_edit_files'
                if result.get(file_key) != original.get(file_key):
                    issue_error(errors, 'derived_view_changed_file_predictions', iid, arm=arm)
                if arm != 'locagent':
                    old_slots, new_slots = original.get('predicted_functions', []), result.get('predicted_functions', [])
                    if len(old_slots) != len(new_slots):
                        issue_error(errors, 'derived_view_added_or_removed_prediction_slots', iid, arm=arm)
                    else:
                        for before, after in zip(old_slots, new_slots):
                            if isinstance(before, dict) and isinstance(after, dict):
                                before = {k: v for k, v in before.items() if k != 'qualified_name'}
                                after = {k: v for k, v in after.items() if k != 'qualified_name'}
                            if before != after:
                                issue_error(errors, 'derived_view_changed_nonformat_slot_fields', iid, arm=arm)
                elif [(s.get('raw_location'), s.get('status'), s.get('usage'), s.get('elapsed_seconds'))
                      for s in result.get('samples', [])] != [
                         (s.get('raw_location'), s.get('status'), s.get('usage'), s.get('elapsed_seconds'))
                         for s in original.get('samples', [])]:
                    issue_error(errors, 'derived_view_changed_original_sample_evidence', iid, arm=arm)
            simulation = result.get('simulation') is True or result.get('not_benchmark_result') is True
            slots = ranking({} if simulation else result, index, arm)
            measurements = {unit: measure(slots[unit], gold[key]) if gold.get(unit + '_evaluable') is True else None
                            for unit, key in (('file', 'file_targets'), ('function', 'function_targets'))}
            record['arms'][arm] = {'status': 'invalid_simulation' if simulation else terminal['status'],
                'result_status': result.get('status'), 'ranking': slots, 'metrics': measurements,
                'invalid_slot_counts': {unit: sum(not s['valid'] for s in slots[unit]) for unit in UNITS},
                'duplicate_slot_counts': {unit: sum(s['reason'] == 'duplicate_rank_slot' for s in slots[unit]) for unit in UNITS}}
            if result and any(result.get(k) != row[k] for k in ('instance_id', 'repo', 'base_commit')):
                issue_error(errors, 'result_allocation_identity_mismatch', iid, arm=arm)
        records.append(record)
    return records


def compare_report(records, evaluation_dir, view_root, reader, errors):
    checks = Counter()
    reported_records = reader.json(evaluation_dir / 'per_issue.json', 'reported_per_issue')
    reported_summary = reader.json(evaluation_dir / 'summary.json', 'reported_summary')
    provenance = {str(view_root / 'allocation.json'): digest(view_root / 'allocation.json')}
    for row in records:
        iid = row['instance_id']
        for arm in ARMS:
            for filename in ('terminal.json', 'result.json'):
                path = view_root / 'run' / iid / arm / filename
                if path.is_file():
                    provenance[str(path)] = digest(path)
        for path in (view_root / 'evaluator_private' / iid / 'gold.json',
                     view_root / 'public' / iid / 'code_index.json'):
            provenance[str(path)] = digest(path)
    same(errors, checks, 'summary_exact_artifact_provenance', provenance,
         reported_summary.get('provenance_sha256'))
    if len(reported_records) != EXPECTED_N or len({r['instance_id'] for r in reported_records}) != EXPECTED_N:
        issue_error(errors, 'reported_per_issue_roster_invalid', evaluation_dir)
        return {}, {}, checks
    by_id = {r['instance_id']: r for r in reported_records}
    if set(by_id) != {r['instance_id'] for r in records}:
        issue_error(errors, 'reported_per_issue_different_ids', evaluation_dir)
        return {}, {}, checks
    csv_path = evaluation_dir / 'per_issue.csv'
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        csv_rows = list(csv.DictReader(stream))
    reader.artifacts[str(csv_path.absolute())] = {'sha256': digest(csv_path), 'category': 'reported_csv'}
    if len(csv_rows) != EXPECTED_N or len({r['instance_id'] for r in csv_rows}) != EXPECTED_N:
        issue_error(errors, 'reported_csv_roster_invalid', csv_path)
        return {}, {}, checks
    csv_by_id = {r['instance_id']: r for r in csv_rows}
    if set(csv_by_id) != set(by_id):
        issue_error(errors, 'reported_csv_different_ids', csv_path)
        return {}, {}, checks
    for record in records:
        iid = record['instance_id']
        saved, csvrow = by_id[iid], csv_by_id[iid]
        for key in ('repo', 'base_commit', 'selected_for_evaluation', 'gold_status', 'gold_error',
                    'file_evaluable', 'function_evaluable', 'gold_files', 'gold_functions', 'gold_limitations'):
            same(errors, checks, 'per_issue_' + key, record[key], saved.get(key), instance_id=iid)
        for key in ('repo', 'base_commit', 'selected_for_evaluation', 'gold_status', 'gold_error', 'file_evaluable', 'function_evaluable'):
            expected = '' if record[key] is None else str(record[key])
            same(errors, checks, 'csv_' + key, expected, csvrow.get(key), instance_id=iid)
        for key in ('gold_files', 'gold_functions'):
            same(errors, checks, 'csv_' + key, record[key], json.loads(csvrow[key]), instance_id=iid)
        for arm in ARMS:
            ours, theirs = record['arms'][arm], saved['arms'][arm]
            for key in ('status', 'result_status', 'ranking', 'metrics'):
                same(errors, checks, 'per_issue_arm_' + key, ours[key], theirs.get(key), instance_id=iid, arm=arm)
            for key in ('status', 'result_status'):
                same(errors, checks, 'csv_arm_' + key, '' if ours[key] is None else str(ours[key]),
                     csvrow.get(arm + '_' + key), instance_id=iid, arm=arm)
            for unit in UNITS:
                same(errors, checks, 'csv_original_slots', ours['ranking'][unit],
                    json.loads(csvrow[f'{arm}_{unit}_original_slots']), instance_id=iid, arm=arm, unit=unit)
                for key in METRICS:
                    value = ours['metrics'][unit][key] if ours['metrics'][unit] is not None else None
                    cell = csvrow.get(f'{arm}_{unit}_{key}')
                    if value is None:
                        actual = None if cell == '' else cell
                    elif isinstance(value, bool):
                        actual = True if cell == 'True' else False if cell == 'False' else cell
                    else:
                        actual = float(cell)
                    same(errors, checks, 'csv_metric_' + key, value, actual, instance_id=iid, arm=arm, unit=unit)
    metrics = {arm: {unit: aggregate([r['arms'][arm]['metrics'][unit] for r in records
                                    if r['arms'][arm]['metrics'][unit] is not None]) for unit in UNITS} for arm in ARMS}
    denominator = {'file': sum(r['file_evaluable'] is True for r in records),
                   'function': sum(r['function_evaluable'] is True for r in records)}
    expected_counts = {'file': EXPECTED_FILE_N, 'function': EXPECTED_FUNCTION_N}
    for unit in UNITS:
        same(errors, checks, 'frozen_' + unit + '_denominator', denominator[unit], expected_counts[unit])
        same(errors, checks, 'reported_' + unit + '_denominator', denominator[unit], reported_summary.get(unit + '_denominator'))
    same(errors, checks, 'summary_metrics_and_ci', metrics, reported_summary.get('metrics'))
    statuses = {arm: dict(Counter(r['arms'][arm]['status'] for r in records)) for arm in ARMS}
    same(errors, checks, 'summary_arm_status_counts', statuses, reported_summary.get('arm_status_counts'))
    same(errors, checks, 'summary_gold_status_counts', dict(Counter(r['gold_status'] for r in records)), reported_summary.get('gold_status_counts'))
    for key, expected in (('allocated', EXPECTED_N), ('selected', EXPECTED_N), ('status', 'EVALUATED'), ('gold_opened', True), ('incomplete_arms', [])):
        same(errors, checks, 'summary_' + key, expected, reported_summary.get(key))
    return metrics, statuses, checks


def audit(root, evaluation_dir, view_root=None):
    root, evaluation_dir = Path(root).resolve(), Path(evaluation_dir).resolve()
    view_root = Path(view_root).resolve() if view_root is not None else root
    reader = Reader()
    if not evaluation_dir.is_relative_to(root / 'reports'):
        raise ValueError('The evaluation report must belong to this run root')
    if view_root != root and not view_root.is_relative_to(root / 'evaluation_views'):
        raise ValueError('Only the original run or its explicitly bound evaluation view is supported')
    roster, errors, pending = initial_fence(root, evaluation_dir, view_root, reader)
    report = {'schema': 1, 'audit': 'Independent Java128 strict metrics and report audit',
        'root': str(root), 'view_root': str(view_root), 'evaluation_dir': str(evaluation_dir),
        'status': 'FAIL' if errors else 'PENDING' if pending else 'FENCE_PASSED',
        'errors': errors, 'pending': pending, 'gold_opened': False,
        'future_gold_opened_before_full_completion': False, 'production_metric_functions_imported': False,
        'models_called': False, 'sealed_project_test_opened': False,
        'replay_or_protocol_change': False, 'read_artifacts': reader.artifacts,
        'source_scope': ['Frozen inference/analysis/signature-view source and configuration files',
            'Full128 allocation, 128 group terminals, 384 arm terminals, inference and analysis completion receipts',
            'Only after all fences pass: frozen public indexes and corresponding offline Java Gold',
            'Original or separately bound derived result JSON, exported per-issue JSON/CSV and summary'],
        'full_model_weight_rehash': False, 'audit_source_sha256': digest(__file__), 'time': time.time()}
    if errors or pending:
        return report
    reader.gate_passed = True
    try:
        records = reconstruct(root, view_root, roster, reader, errors)
        metrics, statuses, checks = compare_report(records, evaluation_dir, view_root, reader, errors)
        report.update(records=records, metrics=metrics, arm_status_counts=statuses,
            denominators={'allocated': EXPECTED_N, 'file': sum(r['file_evaluable'] is True for r in records),
                          'function': sum(r['function_evaluable'] is True for r in records)},
            paired_comparisons=paired(records), comparison_counts=dict(checks),
            original_slots_preserved=True, failed_tasks_retained_in_eligible_denominators=True,
            independent_ci={'binary': 'Wilson score, NormalDist 97.5% quantile',
                'macro': '2000 task bootstrap draws, seed 20261117; floor percentile of (draws-1)*q',
                'paired': 'Same-issue bootstrap and exact two-sided McNemar; descriptive, not equivalence'},
            invalid_slots={arm: {unit: sum(r['arms'][arm]['invalid_slot_counts'][unit] for r in records)
                                for unit in UNITS} for arm in ARMS},
            duplicate_slots={arm: {unit: sum(r['arms'][arm]['duplicate_slot_counts'][unit] for r in records)
                                  for unit in UNITS} for arm in ARMS})
    except Exception as error:
        issue_error(errors, 'independent_reconstruction_error', type(error).__name__ + ': ' + str(error))
    report['status'] = 'FAIL' if errors else 'PASS'
    report['gold_opened'] = reader.gold_opened
    report['read_artifacts'] = reader.artifacts
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--evaluation-dir', required=True, type=Path)
    parser.add_argument('--view-root', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(args.root.resolve() / 'audits'):
        raise ValueError('Independent audit output belongs under this run/audits')
    if out.exists():
        raise FileExistsError('Use a new machine audit artifact; no implicit overwriting')
    result = audit(args.root, args.evaluation_dir, args.view_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'gold_opened': result['gold_opened'],
                      'errors': len(result['errors']), 'pending': len(result['pending']), 'out': str(out)}, ensure_ascii=False))
    return 2 if result['status'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
