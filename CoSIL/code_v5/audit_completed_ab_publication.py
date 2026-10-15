"""Root independent audit of actual A/B report artifacts and paired val scores.

Reads train/val summary metadata and val predictions only. Never decodes sealed
test rows, trains, loads models, changes historical predictions or publishes.
"""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import re

from code_v5.metrics import evaluate_predictions

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/v5_pruner'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if path.name.startswith('pruner_test'):
        raise PermissionError('Publication audit refuses learned-judge test decoder')
    return json.loads(path.read_text())


def val_rows(path):
    path = Path(path)
    if not path.name.startswith(('val_epoch_', 'pruner_val')):
        raise PermissionError('Only explicit val row files accepted')
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    assert all(r['split'] == 'val' for r in rows)
    indexed = {(r['instance_id'], r['function_id']): r for r in rows}
    assert len(indexed) == len(rows)
    return indexed


def paired_interval(left, right):
    grouped = defaultdict(list)
    for k in sorted(left):
        a, b = left[k], right[k]
        grouped[k[0]].append(int((b['p_yes'] >= .5) == b['label']) - int((a['p_yes'] >= .5) == a['label']))
    ids = sorted(grouped); n = sum(map(len, grouped.values()))
    point = sum(map(sum, grouped.values())) / n
    rng = random.Random(20261014); samples = []
    for _ in range(2000):
        chosen = [grouped[rng.choice(ids)] for _ in ids]
        samples.append(sum(map(sum, chosen)) / sum(map(len, chosen)))
    samples.sort()
    return point, [samples[int(.025 * 1999)], samples[int(.975 * 1999)]]


def main():
    work = BASE / 'AB_final_report_coordinator_v3'
    plan = read(work / 'plan.json'); receipt = read(work / 'final_report_receipt.json')
    assert receipt['status'] == 'completed_CPU_reports_for_actual_A_B_only'
    assert receipt['coordinator_plan_sha256'] == sha(work / 'plan.json')
    for table in (plan['source_bindings_sha256'], receipt['snapshot_files_sha256']):
        for path, digest in table.items():
            assert sha(path) == digest, path
    assert not receipt['model_loaded'] and receipt['new_model_calls'] == 0 and not receipt['GPU_claimed']
    assert not receipt['test_rows_decoded'] and not receipt['cross_experiment_matrix_modified']
    comp_path = BASE / 'A_post_vs_B_runtime_comparison_exploratory/comparison.json'
    comp = read(comp_path)
    data = {side: val_rows(BASE / directory / 'pruner_val.jsonl') for side, directory in
            [('A', 'data_v3_noise_disclosed'), ('B', 'data_v3_runtime_filtered_reviewed')]}
    common = set(data['A']) & set(data['B'])
    assert len(common) == comp['validation_pair_counts']['common'] == 345
    for k in common:
        assert data['A'][k]['input_sha256'] == data['B'][k]['input_sha256']
        assert data['A'][k]['label'] == data['B'][k]['label']
    assert {tuple(k) for k in comp['common_validation_pairs']} == common
    model_checks = {}
    config_fields = ('kind', 'rank', 'alpha', 'dropout', 'target_modules', 'learning_rate',
                     'epochs', 'effective_batch', 'micro_batch', 'cutoff', 'dtype', 'seed',
                     'gradient_checkpointing', 'only_lora_trainable', 'weight_decay',
                     'max_gradient_norm', 'early_stop')
    for kind in ('reranker', 'instruct'):
        predicted = {}; configs = []
        for side in ('A', 'B'):
            artifact = comp['artifacts'][side + '/' + kind]
            assert sha(artifact['summary']) == artifact['summary_sha256']
            assert sha(artifact['val_predictions']) == artifact['val_prediction_sha256']
            summary = read(artifact['summary']); assert summary['test_opened'] is False
            assessment = summary['checkpoint_assessments']['best']
            assert assessment['epoch'] == comp['models'][kind][side]['best_epoch']
            source_manifest = comp['artifacts'][side + '/' + kind + '/manifest']
            assert sha(source_manifest['path']) == source_manifest['sha256']
            manifest = read(source_manifest['path'])
            adapter = read(Path(assessment['checkpoint']) / 'adapter_config.json')
            assert adapter['r'] == manifest['rank'] and adapter['lora_alpha'] == manifest['alpha']
            assert adapter['lora_dropout'] == manifest['dropout']
            configs.append({**{k: manifest[k] for k in config_fields}, 'base_model_sha256': manifest['model']['sha256']})
            predictions = val_rows(artifact['val_predictions'])
            assert set(predictions) == set(data[side])
            assert all(predictions[k]['label'] == data[side][k]['label'] for k in predictions)
            actual = evaluate_predictions(list(predictions.values()))
            assert actual == comp['models'][kind][side]['val'] == assessment['val']
            predicted[side] = {k: predictions[k] for k in common}
            assert evaluate_predictions(list(predicted[side].values())) == comp['models'][kind]['common_val'][side]
        assert configs[0] == configs[1] == comp['models'][kind]['matched_training_configuration']
        point, interval = paired_interval(predicted['A'], predicted['B'])
        stored = comp['models'][kind]['paired_accuracy']
        assert point == stored['difference_B_minus_A'] and interval == stored['issue_cluster_percentile_95_interval']
        model_checks[kind] = {'same_actual_profile_verified': True, 'common_pairs': len(common),
                              'difference_B_minus_A': point, 'issue_cluster_95_interval': interval,
                              'bootstrap_independently_recomputed': True}
    snapshot = Path(receipt['snapshot_overview_path']); text = snapshot.read_text()
    links = re.findall(r'!?\[[^\]\n]*\]\(([^\)\n]+)\)', text)
    local = []
    for href in links:
        href = href.strip('<>')
        if href.startswith(('http://', 'https://', '#', 'mailto:')):
            continue
        path = Path(href.partition('#')[0]); assert path.is_absolute() and path.exists(), href
        local.append(str(path))
    for directory in ('data', 'data_v2', 'data_v3', 'data_v3_noise_disclosed',
                      'data_v3_runtime_filtered', 'data_v3_runtime_filtered_reviewed'):
        assert not list((BASE / directory).glob('pruner_test.jsonl.*opened*.json'))
    assert sha(ROOT / 'results/comparison/逐题定位对照数据.json') == '225686335c337eff698858d98cd4f41b3b527b3badf194b9a3775d935dc2dd28'
    result = {'scope': 'root independent completed A/B val/model profile/report audit', 'passed': True,
              'coordinator_plan_sha256': sha(work / 'plan.json'), 'coordinator_receipt_sha256': sha(work / 'final_report_receipt.json'),
              'snapshot_path': str(snapshot), 'snapshot_sha256': sha(snapshot),
              'bound_sources_checked': len(plan['source_bindings_sha256']),
              'bound_outputs_checked': len(receipt['snapshot_files_sha256']), 'local_hrefs_checked': len(local),
              'models': model_checks, 'root_script_path': str(Path(__file__)), 'root_script_sha256': sha(__file__),
              'test_decoded': False, 'models_loaded': False, 'baseline_matrix_unchanged': True,
              'new_end_to_end_localization_claimed': False, 'expanded_C_training_complete': False}
    out = BASE / 'AB_completed_root_publication_audit_v1.json'
    with out.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({'passed': True, 'local_links': len(local), 'models': model_checks}, ensure_ascii=False))


if __name__ == '__main__':
    main()
