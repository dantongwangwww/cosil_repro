"""Old allowlist worker environment with explicit, source-bound ablation entry."""
from __future__ import annotations

import json
from pathlib import Path
import socket

from .common import PACKAGE, ARMS, INTERNAL_ARM, original, sha, package_sources


def isolated_command(module, arguments, *, readonly=(), writable=(), gpu=False):
    from specprune import isolation
    from code_sfpruner300_20261114.judge_launcher import with_ldconfig
    if not module.startswith('code_locbench_ablation_20261117_v2.'):
        raise ValueError('Unexpected isolated entry point')
    argv = isolation.command(arguments,
        readonly=[(PACKAGE, '/ablation/code_locbench_ablation_20261117_v2'), *readonly],
        writable=writable, gpu=gpu)
    positions = [i for i in range(len(argv) - 1)
                 if argv[i] == '-m' and argv[i + 1] == 'specprune.runner']
    if len(positions) != 1:
        raise ValueError('Frozen isolation entry point changed')
    argv[positions[0] + 1] = module
    env = [i for i in range(len(argv) - 2)
           if argv[i:i + 2] == ['--setenv', 'PYTHONPATH']]
    if len(env) != 1 or argv[env[0] + 2] != '/bundle':
        raise ValueError('Unexpected isolation PYTHONPATH')
    argv[env[0] + 2] = '/ablation:/bundle'
    return with_ldconfig(argv, gpu=gpu)


def judge_health(path):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(20)
        sock.connect(str(path))
        sock.sendall(b'{"operation":"health"}\n')
        with sock.makefile('rb') as stream:
            line = stream.readline(1024 * 1024 + 1)
    if len(line) > 1024 * 1024 or not line.endswith(b'\n'):
        raise RuntimeError('Incomplete ablation judge health response')
    result = json.loads(line)
    if not result.get('ok'):
        raise RuntimeError('Ablation judge health failed: ' + str(result.get('error')))
    return result


class FrozenBackend(original.FrozenBackend):
    simulation = False

    def protocol(self):
        return {'original_execution': super().protocol(),
                'ablation_package_files_sha256': package_sources(),
                'experimental_arms': list(ARMS), 'internal_worker_arm': INTERNAL_ARM,
                'shared_upstream_baseline_is_not_new_execution': True}

    def check_services(self, model_dir, judge_socket, out):
        value = super().check_services(model_dir, judge_socket, out)
        ready = original.read(Path(judge_socket).parent / 'ready.json')
        if ready.get('experimental_arms', ready.get('variants')) != list(ARMS):
            raise RuntimeError('Resident judge does not implement the three frozen ablations')
        health = judge_health(judge_socket)
        deployment = original.read(original.BUNDLE / 'configs/deployment.json')
        required = {'status': 'READY', 'model_load_count': 1, 'adapter_loaded': True,
                    'adapter_merged': False, 'adapter_sha256': deployment['adapter_sha256'],
                    **{k: deployment[k] for k in ('temperature', 'low', 'high')}}
        if (ready.get('protocol') != 'locbench560_single_factor_ablation_v1'
                or ready.get('cross_arm_cache') is not False
                or any(ready.get(k) != v or health.get('result', {}).get(k) != v
                       for k, v in required.items())
                or health.get('result', {}).get('variants') != list(ARMS)):
            raise RuntimeError('Frozen scorer configuration or adapter restoration contract mismatch')
        return {**value, 'ablation_judge_ready_sha256': sha(Path(judge_socket).parent / 'ready.json'),
                'ablation_judge_health': health}

    def command(self, arm, staged, snapshot, armout, runtime):
        if arm not in ARMS:
            raise ValueError('Only new ablation conditions may be dispatched')
        readonly = [(staged, '/input'), (snapshot, '/snapshot'),
                    (original.BUNDLE / 'configs/deployment.json', '/deployment.json'),
                    (Path(runtime['tokenizer_directory']), '/main_model'),
                    (original.BUNDLE / 'assets/tokenizers', '/bundle/assets/tokenizers'),
                    (Path(runtime['judge_socket']), '/judge.sock')]
        return isolated_command('code_locbench_ablation_20261117_v2.worker',
                                ['--variant', arm], readonly=readonly,
                                writable=[(armout, '/output')], gpu=False)
