"""Host-only metadata, integrity and allowlist helpers; no model or Gold reads."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

from code_sfpruner300_20261114 import controller as original

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parent
DEFAULT_ROOT = ROOT / 'results/locbench_qwen3_sfpruner_ablation_20261117_preflight_v2'
ARMS = ('ablation_no_lora', 'ablation_no_neighbors', 'ablation_no_defer')
INTERNAL_ARM = 'hybrid_safe'
CHECKPOINTS = (100, 200, 300, 400, 500, 560)
TERMINAL = {'complete', 'worker_failed', 'controller_failed', 'interrupted', 'timed_out',
            'source_preparation_blocked', 'upstream_file_stage_unavailable'}
read, write, sha, digest = original.read, original.write, original.sha, original.digest


def root_protocol(root, *, expected_n=560):
    root = Path(root).resolve(strict=True)
    value = read(root / 'protocol.json')
    if (value.get('experiment_id') != 'locbench_qwen3_sfpruner_ablation_20261117'
            or Path(value['root']).resolve() != root or value['n'] != expected_n
            or value['arms'] != list(ARMS) or value['allocated'] != expected_n):
        raise ValueError('Wrong ablation root, scope or arm contract')
    if Path(value['parent']).resolve() == root:
        raise ValueError('Historical and ablation roots must differ')
    return root, value


def hashes_under(directory):
    directory = Path(directory)
    result = {}
    for path in directory.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in public model inputs')
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = sha(path)
    return result


def verify_hashes(mapping):
    for path, expected in mapping.items():
        if not Path(path).is_file() or sha(path) != expected:
            raise ValueError('Bound source changed: ' + str(path))


def arm_order(instance_id):
    """Counterbalance three conditions without consulting their results."""
    return sorted(ARMS, key=lambda arm: (hashlib.sha256(
        ('20261117:' + instance_id + ':' + arm).encode()).hexdigest(), arm))


def package_sources():
    return {str(p.resolve()): sha(p) for p in sorted(PACKAGE.glob('*.py'))}


def require_execution_freeze(root):
    root, protocol = root_protocol(root)
    value = read(root / 'controller/execution_freeze.json')
    if (value.get('status') != 'EXECUTION_FROZEN_READY'
            or value['protocol_sha256'] != sha(root / 'protocol.json')
            or value['manifest_sha256'] != sha(root / 'manifest.json')):
        raise ValueError('Unpublished or drifted experiment execution')
    verify_hashes(value['files_sha256'])
    receipt = read(value['publication_receipt'])
    if sha(value['publication_receipt']) != value['publication_receipt_sha256']:
        raise ValueError('Execution publication receipt changed')
    if not receipt.get('commit') or receipt.get('new_model_calls', receipt.get('model_calls', 0)):
        raise ValueError('Invalid pre-execution publication receipt')
    if any(value['files_sha256'].get(path) != expected for path, expected in package_sources().items()):
        raise ValueError('New package source inventory drift')
    return value
