"""Route saved completed-epoch val scores and observe historical Qwen reuse.

Raw-probability fixed-threshold diagnostic only; no inference, calibration,
model selection, test access, or executed hybrid/localization claim.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from code_v5.metrics import evaluate_predictions, hybrid_route
from code_v5.prepare_historical_qwen_pair_reuse import (ROOT, ARMS, DATASETS, read_rows, pair, canonical, emit_json, emit_rows)
from code_v5.runtime_coverage import sha, now


def analyze(args):
    inventory = args.inventory_dir.resolve(); training = args.training_run.resolve(); output = args.output_dir.resolve()
    if output.exists(): raise FileExistsError('Saved-val observation reports are immutable')
    assert args.dataset in DATASETS and 0 <= args.low < args.high <= 1
    data = ROOT / 'results/v5_pruner' / DATASETS[args.dataset]
    val_path = data / 'pruner_val.jsonl'; val = read_rows(val_path); index = {pair(r): r for r in val}
    summary_path = training / 'training_summary.json'; summary = json.load(open(summary_path))
    assert summary['test_opened'] is False
    checkpoint = Path(summary['best']).resolve()
    assert checkpoint.parent == training
    complete_path = checkpoint / 'checkpoint_complete.json'; complete = json.load(open(complete_path)); epoch = complete['epoch']
    manifest_path = training / 'training_manifest.json'; manifest = json.load(open(manifest_path))
    assert complete['manifest_sha256'] == sha(manifest_path) and manifest['data']['test_labels_read'] is False
    assert manifest['data']['statistics_sha256'] == sha(data / 'statistics.json')
    seal = json.load(open(data / 'test_file_seal.json'))
    assert seal['frozen_files']['val']['sha256'] == sha(val_path)
    assert manifest['data']['seal_sha256'] == sha(data / 'test_file_seal.json')
    assert not (data / 'pruner_test.jsonl.v5_opened_once.json').exists()
    predictions_path = training / f'val_epoch_{epoch}.jsonl'
    predictions = read_rows(predictions_path)
    assert len(predictions) == len(index) and {pair(r) for r in predictions} == set(index)
    for row in predictions:
        old = index[pair(row)]
        assert row['split'] == 'val' and row['label'] == old['label'] and row['repo'] == old['repo']
        assert set(row['label_sources']) == set(old['label_sources'])
        assert 'p_yes_uncalibrated' not in row and 'temperature' not in row
    recomputed = evaluate_predictions(predictions)
    curves_path = training / 'training_curves.json'; curves = json.load(open(curves_path))
    curve = next(r for r in curves if r['epoch'] == epoch)
    assert canonical(recomputed) == canonical(curve['val']), 'Saved scores no longer reproduce actual completed-epoch validation'
    prior = json.load(open(inventory / 'inventory_report.json'))
    for name, digest in prior['artifacts_sha256'].items(): assert sha(inventory / name) == digest
    source_receipt = json.load(open(inventory / 'source_fingerprints.json'))
    assert source_receipt['paths'][str(val_path)] == sha(val_path)
    observed = [r for r in read_rows(inventory / 'selected_pair_inventory.jsonl')
                if r['dataset'] == args.dataset and r['split'] == 'val']
    qwen = {(*pair(r), r['arm']): r for r in observed}
    assert len(qwen) == len(index) * 3
    rows = []; report = {}
    for arm in ARMS:
        routes = Counter(); gold_routes = Counter(); gray_reasons = Counter(); historical_only = []; judge_on_history = []; observation_reuse = []
        for probability in predictions:
            original = index[pair(probability)]; old = qwen[*pair(probability), arm]
            route = hybrid_route(probability['p_yes'], low=args.low, high=args.high)
            routes[route] += 1
            gold = original['label'] and bool(set(original['label_sources']) & {'A', 'B'})
            if gold: gold_routes[route] += 1
            if old['status'] == 'consensus':
                historical_only.append({**probability, 'p_yes': float(old['consensus_verdict'] == 'True')})
                judge_on_history.append(probability)
            verdict = True if route == 'retain' else False if route == 'reject' else (
                old['consensus_verdict'] == 'True' if old['status'] == 'consensus' else None)
            if route == 'qwen': gray_reasons[old['status']] += 1
            record = {k: original[k] for k in ('instance_id', 'function_id', 'input_sha256', 'base_commit', 'label', 'label_sources')}
            record.update(arm=arm, p_yes_raw_saved=probability['p_yes'], route=route, mechanical_gold=gold,
                          historical_status=old['status'], historical_consensus=old['consensus_verdict'],
                          historical_observation_refs=old['historical_observation_refs'],
                          offline_observation_reuse_verdict=verdict,
                          unresolved_reason=old['status'] if route == 'qwen' and verdict is None else None)
            rows.append(record)
            if verdict is not None: observation_reuse.append({**probability, 'p_yes': float(verdict)})
        report[arm] = {'val_pairs': len(predictions), 'routing_from_saved_probability_only': dict(routes),
            'gold_routing_from_saved_probability_only': dict(gold_routes), 'gray_historical_status': dict(gray_reasons),
            'historical_same_pair_coverage': len(historical_only), 'Qwen_observed_consensus_metrics': evaluate_predictions(historical_only),
            'small_judge_binary_metrics_on_identical_observed_pairs': evaluate_predictions(judge_on_history),
            'offline_observation_reuse_resolved_pairs': len(observation_reuse),
            'offline_observation_reuse_missing_pairs': len(predictions) - len(observation_reuse),
            'offline_observation_reuse_metrics_resolved_subset_only': evaluate_predictions(observation_reuse),
            'experimental_claim': 'Offline direct routing plus reuse of already-recorded Qwen responses; not an executed hybrid pipeline or a localization score.'}
    output.mkdir(parents=True)
    emit_rows(output / 'val_routes_and_observation_reuse.jsonl', rows)
    emit_json(output / 'saved_val_observation_report.json', {'at': now(), 'status': 'raw_saved_probability_fixed_threshold_diagnostic',
        'dataset': args.dataset, 'training_run': str(training), 'kind': summary['kind'], 'epoch': epoch,
        'source_checkpoint_selection': 'Existing summary best checkpoint; diagnostic makes no new checkpoint choice',
        'manifest_experiment_condition': manifest.get('experiment_condition', 'original_A_r16'),
        'probability_kind': 'saved raw p_yes; not calibrated', 'thresholds': {'low': args.low, 'high': args.high},
        'threshold_choice': 'Explicit fixed descriptive diagnostic; not val-optimized or pipeline-authorized thresholds',
        'classification_endpoint_convention': 'p<=low reject; p>=high retain; low<p<high historical Qwen gray',
        'primary_Qwen_arm': 'off', 'arms': report, 'full_val_small_judge_binary_metrics': recomputed,
        'source_sha256': {str(p): sha(p) for p in [val_path, summary_path, complete_path, manifest_path, curves_path, predictions_path,
                           inventory / 'inventory_report.json', inventory / 'selected_pair_inventory.jsonl']},
        'output_rows_sha256': sha(output / 'val_routes_and_observation_reuse.jsonl'),
        'interpretation': 'B/e_log labels have historical Qwen selection dependency; comparisons are observed same-pair diagnostic scores, not independent evaluation. Gray missing/contradictory/invalid responses remain NA and are never filled False.',
        'new_model_calls': 0, 'test_labels_decoded': False, 'GPU_used': False, 'new_labels_generated': 0,
        'training_data_or_model_modified': False, 'fresh_hybrid_executed': False, 'new_localization_predictions': False})
    print(json.dumps({'report': str(output / 'saved_val_observation_report.json'), 'sha256': sha(output / 'saved_val_observation_report.json'),
                      'off_routes': report['off']['routing_from_saved_probability_only'], 'off_gold_routes': report['off']['gold_routing_from_saved_probability_only'],
                      'off_gray_history': report['off']['gray_historical_status']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory-dir', type=Path, required=True)
    parser.add_argument('--training-run', type=Path, required=True)
    parser.add_argument('--dataset', choices=tuple(DATASETS), required=True)
    parser.add_argument('--low', type=float, default=.6)
    parser.add_argument('--high', type=float, default=.9)
    parser.add_argument('--output-dir', type=Path, required=True)
    analyze(parser.parse_args())
