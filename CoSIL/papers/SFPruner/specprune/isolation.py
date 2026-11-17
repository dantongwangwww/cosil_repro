"""Allowlist-only Linux bubblewrap launch; unavailable isolation is fatal."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .runtime_helpers import BUNDLE


def command(arguments, *, readonly=(), writable=(), gpu=False):
    executable = shutil.which('bwrap')
    if executable is None:
        raise RuntimeError('bubblewrap (bwrap) is required; unisolated fallback is forbidden')
    argv = [executable, '--die-with-parent', '--new-session', '--unshare-pid',
        '--unshare-ipc', '--unshare-uts', '--tmpfs', '/', '--proc', '/proc',
        '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/run', '--clearenv']
    # Never bind /, /home, the publication root, evaluation assets, or an entire
    # experiment output root. Python's environment and OS libraries are distinct.
    system = ['/usr', '/bin', '/lib', '/lib64', '/etc/ld.so.cache', '/etc/localtime',
              '/etc/passwd', '/etc/group', '/etc/nsswitch.conf']
    system += [sys.prefix, sys.base_prefix]
    covered = []
    for raw in system:
        path = Path(raw)
        if not path.exists(): continue
        if any(path.is_relative_to(p) for p in covered): continue
        argv += ['--ro-bind', str(path), str(path)]
        covered.append(path)
    for source, target in [(BUNDLE / 'specprune', '/bundle/specprune'),
                           (BUNDLE / 'vendor', '/bundle/vendor'), *readonly]:
        source = Path(source).resolve(strict=True)
        if str(target) in ('/', '/home', '/bundle', '/bundle/assets'):
            raise ValueError('Overbroad inference mount')
        argv += ['--ro-bind', str(source), str(target)]
    for source, target in writable:
        source = Path(source).resolve(strict=True)
        if str(target) in ('/', '/home', '/bundle', '/bundle/assets'):
            raise ValueError('Overbroad output mount')
        argv += ['--bind', str(source), str(target)]
    if gpu:
        # Explicit judge-server invocation only. The main-model service is never
        # started/stopped by the experiment runner.
        for path in sorted(Path('/dev').glob('nvidia*')):
            argv += ['--dev-bind', str(path), str(path)]
    variables = {'PATH': os.path.dirname(sys.executable) + ':/usr/bin:/bin',
        'PYTHONPATH': '/bundle', 'HOME': '/tmp', 'TMPDIR': '/tmp',
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
        'CUDA_VISIBLE_DEVICES': os.environ.get('CUDA_VISIBLE_DEVICES', '') if gpu else '',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'HF_HOME': '/tmp/hf', 'TOKENIZERS_PARALLELISM': 'false',
        'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    for key, value in variables.items(): argv += ['--setenv', key, value]
    return argv + ['--chdir', '/bundle', sys.executable, '-B', '-m',
                   'specprune.runner', *map(str, arguments)]


def run(arguments, *, readonly=(), writable=(), log=None, timeout=3600, gpu=False):
    argv = command(arguments, readonly=readonly, writable=writable, gpu=gpu)
    if log is None:
        return subprocess.run(argv, check=True, timeout=timeout)
    with Path(log).open('x', encoding='utf-8') as stream:
        return subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT,
                              check=True, timeout=timeout)
