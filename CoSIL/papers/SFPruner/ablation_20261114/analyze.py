"""CPU analysis of real component re-scoring on a fixed historical visit set.

No model is loaded; no sealed test is read. Raw logits, labels and R2 targets
are joined only here, after isolated scoring. All outputs use a new directory.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from specprune.metrics import fit_temperature

VARIANTS = ('full', 'no_lora', 'no_neighbors')
ROUTES = ('reject', 'qwen', 'retain')
SEED = 20261114
DRAWS = 2000


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sigmoid(value):
    return 1 / (1 + math.exp(-value)) if value >= 0 else math.exp(value) / (1 + math.exp(value))


def route(probability, low, high):
    return 'reject' if probability <= low else 'retain' if probability >= high else 'qwen'


def auc(labels, scores):
    """Tie-aware Mann–Whitney AUC; repeated bootstrap rows remain repeated."""
    pairs = sorted(zip(scores, labels))
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    rank_sum, start = 0.0, 0
    while start < len(pairs):
        end = start + 1
        while end < len(pairs) and pairs[end][0] == pairs[start][0]:
            end += 1
        rank_sum += ((start + 1 + end) / 2) * sum(label for _, label in pairs[start:end])
        start = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def discrimination(rows):
    labels = [row['label'] for row in rows]
    logits = [row['logit_difference'] for row in rows]
    counts = Counter('TP' if label and value >= 0 else 'FN' if label else
                     'FP' if value >= 0 else 'TN' for label, value in zip(labels, logits))
    return {'n': len(rows), 'auc': auc(labels, logits),
            'accuracy': (counts['TP'] + counts['TN']) / len(rows) if rows else None,
            'threshold': 0.5, 'uses_raw_logits': True,
            'confusion': {key: counts[key] for key in ('TP', 'FN', 'FP', 'TN')}}


def calibration_metrics(rows, temperature):
    bins = [[] for _ in range(10)]
    losses, squared = [], []
    for row in rows:
        value = row['logit_difference'] / temperature
        probability = sigmoid(value)
        signed = -value if row['label'] else value
        losses.append(max(signed, 0) + math.log1p(math.exp(-abs(signed))))
        squared.append((probability - int(row['label'])) ** 2)
        bins[min(int(probability * 10), 9)].append((probability, int(row['label'])))
    report, numerator = [], 0.0
    for index, values in enumerate(bins):
        mean_p = sum(p for p, _ in values) / len(values) if values else None
        observed = sum(y for _, y in values) / len(values) if values else None
        gap = abs(mean_p - observed) if values else None
        if values:
            numerator += len(values) * gap
        report.append({'lower': index / 10, 'upper': (index + 1) / 10,
                       'upper_inclusive': index == 9, 'n': len(values),
                       'mean_probability': mean_p, 'positive_fraction': observed, 'gap': gap})
    n = len(rows)
    return {'n': n, 'temperature': temperature,
            'nll': sum(losses) / n if n else None,
            'brier': sum(squared) / n if n else None,
            'ece10': numerator / n if n else None, 'bins': report,
            'scope': 'in-sample validation diagnostic; no independent calibration test'}


def derive_calibration(rows, frozen=None):
    predictions = [{**row, 'p_yes': sigmoid(row['logit_difference']), 'split': 'val',
                    'label_sources': row.get('label_sources', [])} for row in rows]
    # Historical calibrated probability fields must not masquerade as raw input.
    for row in predictions:
        row.pop('temperature', None)
        row.pop('p_yes_uncalibrated', None)
    fitted = fit_temperature(predictions, split='val')
    temperature = frozen['temperature'] if frozen else fitted['temperature']
    gold = [sigmoid(row['logit_difference'] / temperature) for row in rows
            if row['distribution_group'] == 'gold_AB']
    if not gold:
        raise ValueError('No validation gold_AB rows for the strict-low rule')
    calculated_low = math.nextafter(min(gold), -math.inf)
    low = frozen['low'] if frozen else calculated_low
    if not 0 <= low < 0.9:
        raise ValueError('Strict-low protocol is not deployable: low outside [0,0.9)')
    if frozen and (abs(fitted['temperature'] - temperature) > 1e-5 or abs(calculated_low - low) > 1e-6):
        raise ValueError('Full historical logits do not reproduce frozen calibration')
    return {'temperature': temperature, 'low': low, 'high': 0.9,
            'refitted_temperature': fitted['temperature'], 'strict_low_recomputed': calculated_low,
            'temperature_difference_from_refit': temperature - fitted['temperature'],
            'fit_pairs': len(rows), 'gold_pairs': len(gold),
            'rule': 'val NLL temperature; nextafter(min gold_AB probability,-infinity); high=.9',
            'source': 'historical frozen deployment, refit checked' if frozen else 'this variant validation logits',
            'validation_gold_zero_reject_is_constructed': True,
            'val_predictions_sha256': fitted['val_predictions_sha256']}


def route_rows(rows, config):
    return [{**row, 'calibrated_p_yes': sigmoid(row['logit_difference'] / config['temperature']),
             'route': route(sigmoid(row['logit_difference'] / config['temperature']), config['low'], config['high'])}
            for row in rows]


def route_counts(rows):
    counts = Counter(row['route'] for row in rows)
    return {'n': len(rows), 'counts': {key: counts[key] for key in ROUTES},
            'fractions': {key: counts[key] / len(rows) if rows else None for key in ROUTES},
            'automatic_coverage': (counts['reject'] + counts['retain']) / len(rows) if rows else None}


def validation_routing(rows, config):
    routed = route_rows(rows, config)
    groups = {'overall': routed,
              'gold_AB': [r for r in routed if r['distribution_group'] == 'gold_AB'],
              'positive': [r for r in routed if r['label']],
              'negative': [r for r in routed if not r['label']],
              'E_negative': [r for r in routed if r['distribution_group'] == 'E_negative']}
    result = {group: route_counts(values) for group, values in groups.items()}
    rejected = [r for r in routed if r['route'] == 'reject']
    result['rejection_precision'] = sum(not r['label'] for r in rejected) / len(rejected) if rejected else None
    result['rejection_precision_denominator'] = len(rejected)
    return result


def percentile_interval(values):
    if not values:
        return [None, None]
    values = sorted(values)
    return [values[max(0, math.ceil(.025 * len(values)) - 1)],
            values[max(0, math.ceil(.975 * len(values)) - 1)]]


def paired_cluster_bootstrap(rows_by_variant, draws=DRAWS, seed=SEED):
    full = {r['case_id']: r for r in rows_by_variant['full']}
    clusters = defaultdict(list)
    for key in sorted(full):
        clusters[full[key]['instance_id']].append(key)
    issues = sorted(clusters)
    values = {v: {metric: [] for metric in ('auc', 'accuracy')} for v in VARIANTS[1:]}
    maps = {v: {r['case_id']: r for r in rows_by_variant[v]} for v in VARIANTS}
    if any(set(mapping) != set(full) for mapping in maps.values()):
        raise ValueError('Cluster bootstrap requires exactly paired case IDs')
    rng = random.Random(seed)
    for _ in range(draws):
        keys = [key for issue in rng.choices(issues, k=len(issues)) for key in clusters[issue]]
        point = {v: discrimination([maps[v][key] for key in keys]) for v in VARIANTS}
        for variant in VARIANTS[1:]:
            for metric in ('auc', 'accuracy'):
                if point[variant][metric] is not None and point['full'][metric] is not None:
                    values[variant][metric].append(point[variant][metric] - point['full'][metric])
    original = {v: discrimination(rows_by_variant[v]) for v in VARIANTS}
    result = {'method': 'paired issue-cluster percentile bootstrap, variant minus full',
              'seed': seed, 'draws': draws, 'clusters': len(issues),
              'calibration_refitted_inside_bootstrap': False,
              'multiplicity_adjusted': False, 'comparisons': {}}
    for variant in VARIANTS[1:]:
        result['comparisons'][variant] = {}
        for metric in ('auc', 'accuracy'):
            delta = original[variant][metric] - original['full'][metric] if original['full'][metric] is not None and original[variant][metric] is not None else None
            result['comparisons'][variant][metric] = {'delta': delta,
                'ci95': percentile_interval(values[variant][metric]),
                'valid_draws': len(values[variant][metric]),
                'undefined_draws': draws - len(values[variant][metric])}
    return result


def any_route_units(rows, key):
    grouped = defaultdict(set)
    for row in rows:
        grouped[key(row)].add(row['route'])
    counts = {decision: sum(decision in routes for routes in grouped.values()) for decision in ROUTES}
    return {'n': len(grouped), 'counts': counts,
            'fractions': {decision: value / len(grouped) if grouped else None for decision, value in counts.items()},
            'multiple_route_units': sum(len(routes) > 1 for routes in grouped.values()),
            'route_combinations': dict(sorted(Counter('+'.join(sorted(routes)) for routes in grouped.values()).items())),
            'counts_may_overlap': True, 'definition': 'unit has at least one visit with this route'}


def target_identity(function_id):
    """Static-graph IDs add @start_line; R2 identities are exact path::qualname."""
    name, separator, line = function_id.rpartition('@')
    return name if separator and line.isdigit() else function_id


def runtime_routing(rows, events, config, gold, inventory):
    routed = route_rows(rows, config)
    by_case = {row['case_id']: row for row in routed}
    eligible = {iid for iid, g in gold.items() if g['status'] == 'COMPLETE_NONEMPTY' and g['set_complete'] and g['targets']}
    for iid in eligible:
        if not set(gold[iid]['targets']).issubset(inventory[iid]['function_identities']):
            raise ValueError('R2 target absent from inventory: ' + iid)
    for row in routed:
        iid = row['instance_id']
        row['target_identity'] = target_identity(row['function_id'])
        row['r2_function_eligible'] = iid in eligible
        row['is_r2_target'] = iid in eligible and row['target_identity'] in gold[iid]['targets']
    repeated = []
    for event in events:
        if event['case_id'] not in by_case:
            raise ValueError('Runtime event lacks a scored case')
        row = by_case[event['case_id']]
        if (event['instance_id'], event['function_id']) != (row['instance_id'], row['function_id']):
            raise ValueError('Runtime event identity mismatch')
        repeated.append(row)
    target = [r for r in routed if r['is_r2_target']]
    target_events = [r for r in repeated if r['is_r2_target']]
    function_key = lambda r: (r['instance_id'], r['target_identity'])
    issue_key = lambda r: r['instance_id']
    result = {
        'events': {'all': route_counts(repeated), 'target': route_counts(target_events)},
        'unique_inputs': {'all': route_counts(routed), 'target': route_counts(target)},
        'unique_functions': {'all': any_route_units(routed, function_key), 'target': any_route_units(target, function_key)},
        'issues': {'all': any_route_units(routed, issue_key), 'target': any_route_units(target, issue_key)},
        'cohort': {'total_issues': len(gold), 'function_eligible_issues': len(eligible),
                   'r2_target_identities': sum(len(gold[iid]['targets']) for iid in eligible),
                   'visited_eligible_issues': len({r['instance_id'] for r in routed if r['r2_function_eligible']}),
                   'visited_ineligible_issues': len({r['instance_id'] for r in routed if not r['r2_function_eligible']}),
                   'unique_inputs_absent_from_inventory': sum(r['target_identity'] not in inventory[r['instance_id']]['function_identities'] for r in routed),
                   'eligible_issues_without_target_visit': len(eligible - {r['instance_id'] for r in target})},
        'nongold_is_not_negative': True,
        'scope': 'conditioned on full historical visits; not a new search or independent event sample'}
    return result


def load_inputs(inputs, scores):
    inputs = Path(inputs)
    score_paths = [Path(scores)] if isinstance(scores, (str, Path)) else [Path(p) for p in scores]
    manifest = read_json(inputs / 'manifest.json')
    paths = {name: inputs / 'evaluation' / (name + suffix) for name, suffix in
             (('cases', '.jsonl'), ('reference_scores', '.jsonl'), ('runtime_events', '.jsonl'), ('cohort', '.json'))}
    paths['deployment'] = inputs / 'public/deployment.json'
    for path in [*paths.values(), inputs / 'public/requests.jsonl']:
        name = path.relative_to(inputs).as_posix()
        if sha(path) != manifest['files'][name]['sha256']:
            raise ValueError('Frozen prepared-input SHA mismatch: ' + name)
    cases = read_jsonl(paths['cases'])
    cohort = read_json(paths['cohort'])
    events = read_jsonl(paths['runtime_events'])
    case_map = {r['case_id']: r for r in cases}
    if len(case_map) != len(cases):
        raise ValueError('Duplicate case_id in evaluation cases')
    requests = {r['request_id']: r for r in read_jsonl(inputs / 'public/requests.jsonl')}
    new_scores = [row for path in score_paths for row in read_jsonl(path)]
    new_ids = set()
    for row in new_scores:
        request_id = row.get('request_id')
        if request_id not in requests or request_id in new_ids or row.get('source') != 'new':
            raise ValueError('Unknown, repeated, or non-new score request')
        new_ids.add(request_id)
        for key in ('case_id', 'variant', 'input_sha256', 'source_input_sha256'):
            if row[key] != requests[request_id][key]:
                raise ValueError('New score/request mismatch: ' + key)
    if new_ids != set(requests):
        raise ValueError(f'Incomplete new requests: missing {len(set(requests) - new_ids)}')
    scored = read_jsonl(paths['reference_scores']) + new_scores
    joined = {variant: {'val': [], 'runtime': []} for variant in VARIANTS}
    seen = set()
    for score in scored:
        variant, case_id = score['variant'], score['case_id']
        if variant not in VARIANTS or case_id not in case_map:
            raise ValueError('Unknown variant/case in scores')
        if score.get('status') != 'complete':
            raise ValueError('Incomplete score is not a prediction')
        if (variant, case_id) in seen:
            raise ValueError('Duplicate variant/case score')
        seen.add((variant, case_id))
        case = case_map[case_id]
        for key in ('split', 'instance_id', 'function_id', 'source_input_sha256'):
            if score[key] != case[key]:
                raise ValueError('Score/case mismatch: ' + key)
        if not isinstance(score['logit_difference'], (float, int)) or isinstance(score['logit_difference'], bool) or not math.isfinite(score['logit_difference']):
            raise ValueError('Missing/nonfinite logit')
        probability = score['p_yes']
        if isinstance(probability, bool) or not isinstance(probability, (float, int)) or not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('Raw probability must be a finite number in [0,1]')
        if abs(probability - sigmoid(score['logit_difference'])) > 1e-12:
            raise ValueError('p_yes is not the raw logit probability')
        if variant in ('full', 'no_lora') and score['input_sha256'] != case['source_input_sha256']:
            raise ValueError('Unexpected full/no_lora input change')
        row = {**case, **score}
        if case['split'] == 'val' and type(row['label']) is not bool:
            raise ValueError('Validation label must be bool')
        joined[variant][case['split']].append(row)
    expected = {(v, c) for v in VARIANTS for c in case_map}
    if seen != expected:
        raise ValueError(f'Incomplete score matrix: missing {len(expected - seen)}')
    counts = Counter(r['split'] for r in cases)
    if counts != {'val': 487, 'runtime': 568} or len(events) != 652:
        raise ValueError('This protocol requires 487 val, 568 unique runtime inputs, 652 events')
    if len({r['instance_id'] for r in cases if r['split'] == 'val'}) != 44:
        raise ValueError('Validation issue roster differs from the frozen 44 clusters')
    for variant in VARIANTS:
        for split in ('val', 'runtime'):
            joined[variant][split].sort(key=lambda r: r['case_id'])
    def resolve(source):
        path = Path(source)
        return path if path.is_absolute() else (inputs / path).resolve()
    paths['gold'] = resolve(cohort['gold_path'])
    paths['inventory'] = resolve(cohort['inventory_path'])
    paths['evaluation_asset_manifest'] = paths['gold'].parent / 'ASSET_MANIFEST.json'
    asset_manifest = read_json(paths['evaluation_asset_manifest'])
    for key in ('gold', 'inventory'):
        if sha(paths[key]) != asset_manifest['export_hashes'][key + '.json']:
            raise ValueError('Frozen evaluation asset SHA mismatch: ' + key)
    gold, inventory = read_json(paths['gold']), read_json(paths['inventory'])
    ids = set(cohort.get('fixed_ids', [r['instance_id'] for r in cohort.get('records', [])]))
    if len(ids) != 100 or ids != set(gold) or ids != set(inventory):
        raise ValueError('Fixed 100-issue cohort/gold/inventory mismatch')
    if not {r['instance_id'] for r in cases if r['split'] == 'runtime'}.issubset(ids):
        raise ValueError('Runtime case outside the fixed cohort')
    paths['manifest'] = inputs / 'manifest.json'
    paths.update({f'scores_{i + 1}': path for i, path in enumerate(score_paths)})
    return joined, events, gold, inventory, {name: {'path': str(path), 'sha256': sha(path)} for name, path in paths.items()}


def analyze(joined, events, gold, inventory, provenance, draws=DRAWS):
    began = time.perf_counter()
    frozen_path = provenance['deployment']['path']
    if sha(frozen_path) != provenance['deployment']['sha256']:
        raise ValueError('Frozen deployment changed after input loading')
    frozen = read_json(frozen_path)
    summary = {'schema_version': 1, 'experiment': 'SFPruner fixed-visit component ablation',
        'protocol_sha256': sha(Path(__file__).with_name('PROTOCOL.md')),
        'scope': {'validation_pairs': 487, 'validation_issues': 44, 'runtime_visits': 652,
                  'runtime_unique_inputs': 568, 'new_end_to_end_runs': 0,
                  'full_scores': 'historical', 'new_main_model_requests': 0,
                  'new_component_forward_requests': 1813,
                  'identical_input_no_neighbor_reuses': 297,
                  'calibration_data_are_also_validation_diagnostics': True},
        'provenance': provenance, 'variants': {}}
    for variant in VARIANTS:
        val, runtime = joined[variant]['val'], joined[variant]['runtime']
        calibration_began = time.perf_counter()
        config = derive_calibration(val, frozen if variant == 'full' else None)
        calibration_seconds = time.perf_counter() - calibration_began
        same_frozen = {k: frozen[k] for k in ('temperature', 'low', 'high')}
        summary['variants'][variant] = {
            'calibration': {**config, 'cpu_wall_seconds': calibration_seconds},
            'validation': {'discrimination': discrimination(val),
                           'uncalibrated': calibration_metrics(val, 1.0),
                           'calibrated': calibration_metrics(val, config['temperature']),
                           'routing': validation_routing(val, config)},
            'runtime': {'independent_calibration': runtime_routing(runtime, events, config, gold, inventory)},
            'same_frozen_threshold_diagnostic': {
                'calibration': same_frozen,
                'validation': {'calibrated': calibration_metrics(val, frozen['temperature']),
                               'routing': validation_routing(val, same_frozen)},
                'runtime': runtime_routing(runtime, events, same_frozen, gold, inventory)},
            'score_sources': dict(Counter(r.get('source', 'unknown') for r in val + runtime)),
            'score_input_tokens': sum(r['input_tokens'] for r in val + runtime)}
    summary['paired_cluster_bootstrap'] = paired_cluster_bootstrap(
        {v: joined[v]['val'] for v in VARIANTS}, draws=draws)
    # At T>0 the binary p=.5 decision is the raw logit sign. This replay uses
    # frozen full scores, and is deliberately separate from component results.
    binary = {'temperature': frozen['temperature'], 'low': math.nextafter(.5, -math.inf), 'high': .5}
    summary['binary_no_gray_policy_replay'] = {
        'new_inference': False, 'source_variant': 'full', 'rule': 'p<.5 reject; p>=.5 retain',
        'validation': validation_routing(joined['full']['val'], binary),
        'runtime': runtime_routing(joined['full']['runtime'], events, binary, gold, inventory),
        'scope': 'strategy replay only; cannot establish effects on localization or online cost'}
    summary['limitations'] = [
        'Validation calibration is in-sample; zero gold rejection is enforced by threshold construction.',
        'Runtime candidates were selected by the historical full policy, conditioning the comparison on its visits.',
        'No-neighbor intervention changes inference inputs for a model trained with neighbors.',
        'Runtime nongold identities are not semantic negatives; repeated visits are not independent samples.',
        'Cluster intervals are exploratory, unadjusted, and do not establish equivalence or causal endpoint effects.',
        'No new Hit@k, online latency, or main-model token savings are measured.']
    summary['analysis_cpu_wall_seconds'] = time.perf_counter() - began
    summary['analysis_integrity_revision'] = {
        'note': 'Read frozen prepared deployment and verify existing R2 asset manifest; reject nonfinite raw probabilities.',
        'changes_scoring_protocol': False, 'prepared_inputs_changed': False,
        'analyze_code_sha256': sha(__file__)}
    return summary


def comparison_rows(summary):
    rows = []
    for variant in VARIANTS:
        value = summary['variants'][variant]
        runtime = value['runtime']['independent_calibration']
        row = {'variant': variant, **{k: value['validation']['discrimination'][k] for k in ('auc', 'accuracy')},
               **{k: value['calibration'][k] for k in ('temperature', 'low', 'high')},
               'runtime_unique_input_n': runtime['unique_inputs']['all']['n'],
               'runtime_unique_auto_coverage': runtime['unique_inputs']['all']['automatic_coverage'],
               'target_unique_function_n': runtime['unique_functions']['target']['n'],
               'target_unique_function_any_reject': runtime['unique_functions']['target']['counts']['reject'],
               'target_unique_function_any_qwen': runtime['unique_functions']['target']['counts']['qwen'],
               'target_unique_function_any_retain': runtime['unique_functions']['target']['counts']['retain'],
               'target_event_n': runtime['events']['target']['n'],
               'target_event_reject': runtime['events']['target']['counts']['reject']}
        if variant != 'full':
            for metric, values in summary['paired_cluster_bootstrap']['comparisons'][variant].items():
                row[metric + '_delta'] = values['delta']
                row[metric + '_delta_ci95_low'], row[metric + '_delta_ci95_high'] = values['ci95']
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--scores', type=Path, action='append', required=True,
                        help='New score JSONL; repeat for separately scored variants')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Analysis output already exists; never overwrite historical results')
    loaded = load_inputs(args.inputs, args.scores)
    summary = analyze(*loaded)
    rows = comparison_rows(summary)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    with (args.out / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'output': str(args.out), 'variants': rows}, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
