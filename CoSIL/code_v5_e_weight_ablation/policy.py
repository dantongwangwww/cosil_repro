"""Immutable, explicitly authorized new condition; never unlock test or inference."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'results/v5_pruner/data_verified_plus_B_runtime_reviewed'
BASELINE = ROOT / 'results/v5_pruner/C_Verified_plus_B_runtime_resources_v3_exploratory'
OUTPUT = ROOT / 'results/v5_pruner/E_weight05_C_frozen_trainval_exploratory'
PROTOCOL = ROOT / 'results/v5_pruner/E_weight05_ablation_authorization_exploratory/protocol.json'
C_DECISION = ROOT / 'results/v5_pruner/C_Verified_plus_B_runtime_authorization_exploratory/root_exploratory_decision.json'
E_WEIGHT = 0.5
PROFILES = {'reranker': {'rank': 8, 'dropout': 0.1},
            'instruct': {'rank': 16, 'dropout': 0.0}}
COMMON = {'alpha': 32, 'learning_rate': 5e-5, 'epochs': 3, 'effective_batch': 8,
          'micro_batch': 2, 'cutoff': 4096, 'dtype': 'bfloat16', 'seed': 0,
          'weight_decay': 0.0, 'max_gradient_norm': 1.0,
          'gradient_checkpointing': True, 'only_lora_trainable': True,
          'target_modules': 'all-linear', 'early_stop': 'validation E correct-rejection rate decreases'}


def protected_paths():
    paths = list((ROOT / 'code_v5_e_weight_ablation').glob('*.py'))
    paths += [ROOT / 'code_v5_expanded_resources_v3' / x for x in
              ['train_judges.py', 'run_training_pair.py']]
    paths += [ROOT / 'code_v5' / x for x in ['judge_models.py', 'metrics.py']]
    paths += [ROOT / 'code_v5_verified/expanded_policy.py', C_DECISION,
              ROOT / 'results/v5_pruner/C_shared_GPU_resource_authorization_v3.json',
              ROOT / 'results/v5_pruner/C_training_queue_release_resources_v3.json']
    paths += [DATA / x for x in ['pruner_train.jsonl', 'pruner_val.jsonl', 'split_manifest.json',
                                 'statistics.json', 'test_file_seal.json']]
    paths += [ROOT / 'docs/v5-pruner/E训练权重单因素对照_方案与冻结口径.md',
              PROTOCOL.parent / 'CPU_checks.json', PROTOCOL.parent / 'trainer_delta.patch',
              ROOT / 'results/comparison/逐题定位对照数据.json',
              ROOT.parent / '跨实验对照表/跨实验逐题定位对照表.xlsx']
    for kind in PROFILES:
        p = BASELINE / 'training' / kind
        paths += [p / x for x in ['training_manifest.json', 'training_summary.json', 'training_curves.json',
                                  'val_epoch_1.jsonl', 'val_epoch_2.jsonl', 'val_epoch_3.jsonl']]
    return sorted(set(paths))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_metadata(path):
    path = Path(path)
    if path.suffix == '.jsonl' or 'pruner_test' in path.name:
        raise PermissionError('Policy metadata reader refuses example/test files')
    return json.loads(path.read_text())


def validate_protocol(path=PROTOCOL):
    if Path(path).resolve() != PROTOCOL:
        raise PermissionError('Use the separately frozen E-weight-only protocol')
    protocol = read_metadata(PROTOCOL)
    if (protocol.get('user_authorized') is not True or protocol.get('track') != 'exploratory'
            or protocol.get('e_weight') != E_WEIGHT or protocol.get('non_e_weight') != 1.0
            or protocol.get('test_open_allowed') is not False
            or protocol.get('change_labels_or_rows') is not False
            or protocol.get('change_sampling_or_tokenization') is not False
            or protocol.get('calibration_or_threshold_search_allowed') is not False
            or protocol.get('paid_api_or_downloads_allowed') is not False
            or protocol.get('data_dir') != str(DATA) or protocol.get('output_dir') != str(OUTPUT)
            or protocol.get('profiles') != PROFILES or protocol.get('common_training') != COMMON
            or protocol.get('nominal_routes') != {'low': 0.6, 'high': 0.9, 'temperature': 1.0}
            or protocol.get('weight_normalization') != 'original_unweighted_example_or_response_token_denominator'):
        raise PermissionError('The single-factor protocol or test sealing changed')
    if set(protocol['protected_sha256']) != {os.path.relpath(p, ROOT) for p in protected_paths()}:
        raise RuntimeError('Protected artifact inventory changed')
    for relative, expected in protocol['protected_sha256'].items():
        path = ROOT / relative
        if 'pruner_test' in path.name and path.suffix == '.jsonl':
            raise PermissionError('Never register sealed test samples in an ablation SHA reader')
        if sha(path) != expected:
            raise RuntimeError('Frozen source, baseline, train/val or receipt changed: ' + relative)
    for kind in PROFILES:
        baseline = read_metadata(BASELINE / 'training' / kind / 'training_manifest.json')
        if any(baseline.get(k) != v for k, v in (COMMON | PROFILES[kind]).items()):
            raise RuntimeError('Baseline training profile differs from the frozen comparison')
    # Only inspect the existence of the formal once-open marker, never its samples.
    for directory in [DATA, ROOT / 'results/v5_pruner/data_verified_plus_B_runtime']:
        if (directory / 'pruner_test.jsonl.v5_opened_once.json').exists():
            raise PermissionError('Test has opened; exploratory E ablation is forbidden')
        stat = (directory / 'pruner_test.jsonl').stat()
        if protocol['sealed_test_file_stat'][str(directory)] != {
                'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'inode': stat.st_ino}:
            raise RuntimeError('Sealed test file stat changed; never decode it in this ablation')
    return protocol


def validate_training_request(args):
    p = validate_protocol(args.protocol_file)
    baseline = read_metadata(BASELINE / 'training' / args.kind / 'training_manifest.json')
    if (args.e_weight != E_WEIGHT or args.track != 'exploratory'
            or Path(args.data_dir).resolve() != DATA
            or Path(args.output_dir).resolve() != OUTPUT / 'training' / args.kind
            or Path(args.decision_file).resolve() != C_DECISION
            or Path(args.model_dir).resolve() != Path(baseline['model']['path'])
            or args.micro_batch != 2 or args.effective_batch != 8):
        raise PermissionError('Only the frozen E=.5 condition and original C inputs are authorized')
    return {'protocol_path': str(PROTOCOL), 'protocol_sha256': sha(PROTOCOL),
            'baseline_manifest_sha256': sha(BASELINE / 'training' / args.kind / 'training_manifest.json'),
            'e_weight': E_WEIGHT, 'non_e_weight': 1.0,
            'sample_selection_unchanged': True, 'labels_unchanged': True,
            'validation_weighted': False, 'test_open_allowed': False,
            'weight_normalization': p['weight_normalization']}


def validate_runtime_config(config):
    baseline = read_metadata(BASELINE / 'training' / config['kind'] / 'training_manifest.json')
    for key in (*COMMON, *PROFILES[config['kind']], 'model', 'data', 'libraries'):
        if config[key] != baseline[key]:
            raise RuntimeError('Non-weight training setting differs from C: ' + key)
