"""Freeze one E=.5 condition before any new training/validation result exists."""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import os
from pathlib import Path
import random

from code_v5.metrics import E_FAMILIES, _sources
from code_v5_e_weight_ablation.policy import (BASELINE, COMMON, DATA, E_WEIGHT, OUTPUT,
                                             PROFILES, PROTOCOL, ROOT, protected_paths, sha,
                                             validate_protocol)


def freeze():
    if PROTOCOL.exists() or (OUTPUT / 'status.json').exists():
        raise FileExistsError('Do not replace a frozen or started condition')
    checks = json.loads((PROTOCOL.parent / 'CPU_checks.json').read_text())
    if checks.get('passed') is not True or checks.get('actual_model_loaded') is not False:
        raise RuntimeError('Targeted CPU checks must pass before freezing')
    datasets = {}
    for split in ['train', 'val']:
        path = DATA / f'pruner_{split}.jsonl'
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        if any(r['split'] != split for r in rows):
            raise RuntimeError('Wrong data split')
        datasets[split] = rows
    if len(datasets['train']) != 13411 or len(datasets['val']) != 714:
        raise RuntimeError('Existing C train/val must remain unchanged')
    for kind in PROFILES:
        baseline = json.loads((BASELINE / 'training' / kind / 'training_manifest.json').read_text())
        if any(sha(DATA / f'pruner_{s}.jsonl') != baseline['data'][s+'_sha256'] for s in ['train','val']):
            raise RuntimeError('Baseline data hash mismatch')
    train = datasets['train']
    e = [r for r in train if _sources(r) & (set(E_FAMILIES)|{'E'})]
    if len(e) != 4378 or any(r['label'] is not False for r in e):
        raise RuntimeError('Frozen E membership or labels differ')
    old_path = ROOT/'results/v5_pruner/data_v3_runtime_filtered_reviewed/pruner_val.jsonl'
    old_ids = sorted({json.loads(x)['instance_id'] for x in old_path.read_text().splitlines() if x.strip()})
    if sum(r['instance_id'] in old_ids for r in datasets['val']) != 363:
        raise RuntimeError('Old 363 validation subset is not exactly retained')
    order_hashes = {}
    for epoch in range(1,4):
        order = list(range(len(train))); random.Random(epoch).shuffle(order)
        order_hashes[str(epoch)] = hashlib.sha256(json.dumps(order,separators=(',',':')).encode()).hexdigest()
    positive = sum(r['label'] for r in train)
    negative = len(train) - positive
    protocol = {
        'generated_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'protocol_path': str(PROTOCOL), 'user_authorized': True,
        'user_request': '用现有train/val做一次仅调整E训练权重的对照，其他条件保持一致；重点看gold直接剪掉比例和AUC；test继续封存',
        'track': 'exploratory', 'e_weight': E_WEIGHT, 'non_e_weight': 1.0,
        'baseline_e_weight': 1.0, 'data_dir': str(DATA), 'output_dir': str(OUTPUT),
        'test_open_allowed': False, 'change_labels_or_rows': False,
        'change_sampling_or_tokenization': False, 'calibration_or_threshold_search_allowed': False,
        'paid_api_or_downloads_allowed': False, 'new_E_reconstruction_allowed': False,
        'profiles': PROFILES, 'common_training': COMMON,
        'nominal_routes': {'low': .6, 'high': .9, 'temperature': 1.0},
        'weight_normalization': 'original_unweighted_example_or_response_token_denominator',
        'E_membership': 'union of canonical e_log/e_bm25/e_anchor provenance, including D overlap, weighted once',
        'train_counts': {'pairs': len(train), 'positive': positive, 'negative': negative,
                         'E_union': len(e), 'non_E': len(train)-len(e),
                         'E_D_overlap': sum('D' in _sources(r) for r in e),
                         'weighted_negative_example_mass': negative-(1-E_WEIGHT)*len(e),
                         'weighted_negative_to_positive_example_ratio': (negative-(1-E_WEIGHT)*len(e))/positive},
        'val_counts': {'pairs':len(datasets['val']),
                       'issues':len({r['instance_id'] for r in datasets['val']}),
                       'gold':sum(r['label'] and bool(_sources(r)&{'A','B'}) for r in datasets['val']),
                       'E':sum(bool(_sources(r)&set(E_FAMILIES)) for r in datasets['val'])},
        'shuffle_order_sha256_by_epoch': order_hashes, 'old_Lite_val_issue_ids': old_ids,
        'bootstrap': {'paired_issue_cluster_iterations': 2000, 'seed':20261015},
        'baseline_usage': 'reuse immutable completed C weights=1.0; no baseline rerun',
        'checkpoint_selection': 'unchanged original per-kind rule; common-epoch comparisons also mandatory',
        'resources': {'allowed_gpu_ids':[0,1,2,3], 'minimum_free_mib':12288,
                      'max_parallel_trainers':2,'prefer_gpu_ids':[2,3,1,0],
                      'peer_processes_may_be_modified':False,'pause_when_peer_arrives':False},
        'sealed_test_file_stat': {},
        'protected_sha256': {os.path.relpath(p, ROOT):sha(p) for p in protected_paths()},
    }
    for directory in [DATA, ROOT/'results/v5_pruner/data_verified_plus_B_runtime']:
        stat=(directory/'pruner_test.jsonl').stat()
        protocol['sealed_test_file_stat'][str(directory)]={'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'inode':stat.st_ino}
    with PROTOCOL.open('x') as stream:
        stream.write(json.dumps(protocol,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    validate_protocol()
    return {'protocol':str(PROTOCOL),'sha256':sha(PROTOCOL),'train':protocol['train_counts'],
            'val':protocol['val_counts'],'test_opened':False}


if __name__=='__main__':
    print(json.dumps(freeze(),ensure_ascii=False,indent=2))
