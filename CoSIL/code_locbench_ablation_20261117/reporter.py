"""Ordered CPU-only checkpoint consumer; never joins or controls inference."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import time
import uuid

from . import common as c

COMPLETE = 'ALL_ABLATION_REPORTS_COMPLETE'


def status(root, phase, **extra):
    value = {'phase': phase, 'utc': time.time(), 'pid': os.getpid(),
             'models_called': 0, 'gpu_used': False, **extra}
    c.write(Path(root) / 'reports/status.json', value)
    return value


def prefix_closed(root, n):
    """Metadata/SHA only. An arm terminal alone cannot close an issue group."""
    root = Path(root)
    manifest = c.read(root / 'manifest.json')
    freeze = c.read(root / 'run/freeze.json')
    rows = manifest['records'][:n]
    if len(rows) != n or [r['rank'] for r in rows] != list(range(1, n + 1)):
        raise ValueError('Wrong ordered checkpoint scope')
    marker = c.read(root / 'controller/checkpoints' / (str(n) + '.json'))
    if (marker.get('status') != 'PREFIX_ALL_ARMS_TERMINAL' or marker.get('n') != n
            or marker.get('protocol_sha256') != freeze['protocol_sha256']):
        raise ValueError('Checkpoint marker identity drift')
    evidence = {}
    for row in rows:
        group = root / 'run/pairs' / row['instance_id']
        states = {}
        for arm in c.ARMS:
            path = group / arm / 'terminal.json'
            if not path.is_file():
                return False
            term = c.read(path)
            expected = {'instance_id': row['instance_id'], 'base_commit': row['base_commit'],
                        'arm': arm, 'protocol_sha256': freeze['protocol_sha256']}
            if (any(term.get(k) != v for k, v in expected.items())
                    or term.get('status') not in c.TERMINAL):
                raise ValueError('Checkpoint arm identity/status drift')
            if 'result_sha256' in term and c.sha(group / arm / 'result.json') != term['result_sha256']:
                raise ValueError('Checkpoint raw result changed')
            states[arm] = term
            evidence[str(path)] = c.sha(path)
        closed = group / 'group_terminal.json'
        if not closed.is_file():
            return False
        value = c.read(closed)
        if (value.get('instance_id') != row['instance_id']
                or value.get('base_commit') != row['base_commit']
                or value.get('protocol_sha256') != freeze['protocol_sha256']
                or value.get('arms') != states):
            raise ValueError('Closed group differs from its three terminals')
        evidence[str(closed)] = c.sha(closed)
    return {'n': n, 'terminal_arms': 3 * n, 'groups': n, 'files_sha256': evidence}


def validate_report(directory, n):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError('Report output cannot be a symlink')
    directory = directory.resolve(strict=True)
    if any(p.is_symlink() for p in directory.rglob('*')):
        raise ValueError('Symlink in completed report')
    manifest = c.read(directory / 'output_sha256.json')
    if not manifest:
        raise ValueError('Empty report hash manifest')
    for name, expected in manifest.items():
        path = directory / name
        if (Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink()
                or not path.resolve(strict=True).is_relative_to(directory)
                or c.sha(path) != expected):
            raise ValueError('Completed report output SHA/inventory drift')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if actual != set(manifest) | {'output_sha256.json'}:
        raise ValueError('Completed report has unregistered output files')
    summary = c.read(directory / 'summary.json')
    if (summary.get('status') != 'FINAL_ABLATION_CHECKPOINT' or summary.get('allocated') != n
            or summary.get('models_called_by_evaluator') != 0
            or summary.get('terminal_barrier_before_gold') is not True):
        raise ValueError('Completed report scope/protocol mismatch')
    c.verify_hashes(c.read(directory / 'input_sha256.json'))
    return {'allocated': n, 'directory': str(directory),
            'output_manifest_sha256': c.sha(directory / 'output_sha256.json')}


def checkpoint(root, n, *, report_run=None, sleeper=time.sleep):
    root = Path(root)
    gate = prefix_closed(root, n)
    if not gate:
        return None
    output = root / 'reports' / ('cumulative' + str(n))
    if output.exists():
        value = validate_report(output, n)
    else:
        if report_run is None:
            from .report import run as report_run
        attempt_root = root / 'reports/attempts' / ('cumulative' + str(n))
        attempt_root.mkdir(parents=True, exist_ok=True)
        previous = len(list(attempt_root.glob('*.started.json')))
        if previous >= 3:
            raise RuntimeError('Report lifetime I/O allowance exhausted; attempts retained')
        for attempt in range(previous + 1, 4):
            c.require_execution_freeze(root)
            key = 'attempt_' + str(attempt) + '_' + uuid.uuid4().hex
            candidate = attempt_root / key
            status(root, 'REPORTING', allocated=n, attempt=attempt)
            c.write(attempt_root / (key + '.started.json'),
                    {'status': 'STARTED', 'candidate': str(candidate), 'allocated': n}, immutable=True)
            try:
                report_run(root, n, candidate)
                validate_report(candidate, n)
                if output.exists():
                    raise ValueError('Concurrent or previously unregistered final report appeared')
                os.rename(candidate, output)
                value = validate_report(output, n)
                c.write(attempt_root / (key + '.json'), {'status': 'FINALIZED',
                    'directory': str(output), 'partial_outputs_deleted': False}, immutable=True)
                break
            except OSError as error:
                c.write(attempt_root / (key + '.json'), {'status': 'IO_FAILED_PRESERVED',
                    'error_type': type(error).__name__, 'error': str(error),
                    'attempt_directory': str(candidate), 'partial_outputs_deleted': False}, immutable=True)
                if attempt == 3:
                    raise RuntimeError('Report I/O allowance exhausted; attempts retained') from error
                sleeper(2)
    c.write(root / 'reports/checkpoints' / (str(n) + '.json'),
            {'status': 'REPORT_COMPLETE', **value, 'models_called': 0}, immutable=True)
    return value


def fatal(root, error):
    value = {'status': 'REPORT_FATAL', 'utc': time.time(), 'error_type': type(error).__name__,
             'error': str(error), 'models_called': 0, 'raw_outputs_preserved': True}
    path = Path(root) / 'controller/report_fatal.json'
    if not path.exists():
        c.write(path, value, immutable=True)
    status(root, 'FATAL', error_type=type(error).__name__, error=str(error))


def run(root, *, poll=10, sleeper=time.sleep, report_run=None):
    root = Path(root).resolve()
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    try:
        with c.original.lock_output(root / 'reports/reporter_lock'):
            reports = []
            for n in c.CHECKPOINTS:
                while True:
                    c.require_execution_freeze(root)
                    if (root / 'controller/report_fatal.json').exists():
                        raise ValueError('A prior report fatal must not be silently resumed')
                    if (root / 'controller/checkpoints' / (str(n) + '.json')).is_file():
                        value = checkpoint(root, n, report_run=report_run, sleeper=sleeper)
                        if value is not None:
                            reports.append(value)
                            status(root, 'REPORT_COMPLETE', allocated=n)
                            break
                    status(root, 'WAITING_CLOSED_PREFIX', allocated=n)
                    sleeper(poll)
            result = {'status': COMPLETE, 'allocated': 560, 'reports': reports,
                      'models_called': 0, 'gpu_used': False}
            c.write(root / 'reports/completion.json', result, immutable=True)
            status(root, COMPLETE, allocated=560)
            return result
    except Exception as error:
        fatal(root, error)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--poll-seconds', type=int, default=10)
    args = parser.parse_args()
    if not 2 <= args.poll_seconds <= 60:
        parser.error('poll interval must be2..60 seconds')
    run(args.root, poll=args.poll_seconds)


if __name__ == '__main__':
    main()
