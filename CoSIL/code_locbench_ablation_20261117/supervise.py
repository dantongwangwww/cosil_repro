"""Persistent owned service supervision with an independent CPU report queue."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

from code_locbench_full_20261116 import recovery
from code_locbench_sfpruner_20261116.supervise import queue_environment
from . import common as c
from . import reporter


def status(root, phase, **extra):
    value = {'phase': phase, 'utc_unix': time.time(), 'pid': os.getpid(), **extra}
    c.write(Path(root) / 'controller/status.json', value)
    return value


def stop_dispatch(root, error):
    path = Path(root) / 'controller/stop_dispatch.json'
    if not path.exists():
        c.write(path, {'status': 'STOP_NEW_DISPATCH', 'utc_unix': time.time(),
                      'reason': str(error), 'scores_used_for_decision': False,
                      'already_started_arms_must_not_replay': True}, immutable=True)


def closed(root):
    root = Path(root)
    n = c.read(root / 'manifest.json')['n']
    marker = root / 'controller/checkpoints' / (str(n) + '.json')
    return reporter.prefix_closed(root, n) if marker.is_file() else False


def service_release(root):
    """Real start-tick observations; argv retitling is never evidence of exit."""
    from .services import leader_exit_observation, MAIN_GPUS, JUDGE_GPU
    root = Path(root)
    directory = root / 'controller/service_queue'
    observations, cuda_rows, missing, session_requirements = [], [], [], []
    for session in sorted((directory / 'sessions').glob('*')):
        if not session.is_dir():
            continue
        leaders = list(session.glob('*/ownership.json'))
        for path in leaders:
            saved = c.read(path)['identity']
            observations.append({'receipt': str(path), **leader_exit_observation(saved)})
        gpu_leaders = [p for p in leaders if p.parent.name in ('main', 'judge')]
        expected_roles = {p.parent.name: (p, c.read(p)['identity']) for p in gpu_leaders}
        captures = list(session.glob('cuda_ownership*.json'))
        witnessed, observed_no_cuda = set(), set()
        for path in captures:
            capture = c.read(path)
            for record in capture.get('records', []):
                if not record.get('claimed_owned'):
                    continue
                role = record.get('owned_role')
                saved = record.get('current_basic')
                owner = expected_roles.get(role)
                if (not saved or record.get('expected_gpu') is not True or owner is None
                        or record.get('leader_pid') != owner[1]['pid']
                        or record.get('leader_start_ticks') != owner[1]['start_ticks']):
                    missing.append(str(path) + ': incomplete owned CUDA identity')
                    continue
                witnessed.add(role)
                cuda_rows.append({'receipt': str(path), 'role': role,
                                  **leader_exit_observation(saved)})
            if capture.get('observation_phase') == 'after_shutdown':
                for role, (ownership_path, owner) in expected_roles.items():
                    negative = capture.get('role_observations', {}).get(role, {})
                    expected_devices = set(MAIN_GPUS if role == 'main' else (JUDGE_GPU,))
                    if (negative.get('no_compute_on_expected_devices') is True
                            and negative.get('nvml_query_complete') is True
                            and negative.get('ownership_receipt') == str(ownership_path)
                            and negative.get('ownership_receipt_sha256') == c.sha(ownership_path)
                            and negative.get('saved_pid') == owner['pid']
                            and negative.get('saved_start_ticks') == owner['start_ticks']
                            and set(negative.get('expected_gpus', [])) == expected_devices
                            and capture.get('status') == 'OBSERVED' and not capture.get('errors')
                            and expected_devices <= set(capture.get('gpu_inventory', {}).values())
                            and not any(r.get('gpu_index') in expected_devices or r.get('gpu_index') is None
                                        for r in capture.get('records', []))):
                        observed_no_cuda.add(role)
        uncovered = set(expected_roles) - witnessed - observed_no_cuda
        if uncovered:
            missing.append(str(session) + ': started roles lack CUDA/explicit no-CUDA evidence: '
                           + ','.join(sorted(uncovered)))
        session_requirements.append({'session': str(session), 'started_roles': sorted(expected_roles),
            'CUDA_witnessed_roles': sorted(witnessed),
            'post_shutdown_no_CUDA_observed_roles': sorted(observed_no_cuda),
            'unwitnessed_roles': sorted(uncovered)})
    if any((root / 'run').glob('pairs/*/*/started.json')) and not observations:
        missing.append('Started model arms lack service ownership exit evidence')
    ready = (not missing and all(x['leader_exited'] for x in observations + cuda_rows))
    result = {'all_owned_services_and_CUDA_children_exited': ready,
              'leader_observations': observations, 'cuda_observations': cuda_rows,
              'session_requirements': session_requirements,
              'missing_evidence': missing, 'signals_sent': False,
              'foreign_GPU0_and_unresolved_GPU1_not_claimed': True}
    c.write(root / 'controller/service_release_observation.json', result)
    return result


def verified_report_completion(root):
    root = Path(root)
    path = root / 'reports/completion.json'
    if not path.is_file():
        return None
    value = c.read(path)
    expected = c.read(root / 'manifest.json')['n']
    if value.get('status') != reporter.COMPLETE or value.get('allocated') != expected:
        raise ValueError('CPU report completion scope/status mismatch')
    reports = value.get('reports', [])
    ns = [n for n in c.CHECKPOINTS if n <= expected]
    if [r.get('allocated') for r in reports] != ns:
        raise ValueError('CPU report completion skipped or reordered a prefix')
    for entry in reports:
        actual = reporter.validate_report(entry['directory'], entry['allocated'])
        if actual['output_manifest_sha256'] != entry['output_manifest_sha256']:
            raise ValueError('CPU report completion output SHA changed')
    return value


def launch(root, role, *, starter=None):
    root = Path(root)
    starter = starter or recovery.start_or_adopt
    env = queue_environment()
    if role == 'reporter':
        module = 'code_locbench_ablation_20261117.reporter'
        env.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2')
        extra = ['--poll-seconds', '10']
    else:
        module = 'code_locbench_ablation_20261117.services'
        extra = ['--wait', '--poll-seconds', '10']
    command = [sys.executable, '-B', '-m', module, '--root', str(root), *extra]
    return starter(command, cwd=c.ROOT, env=env,
                   ownership_path=root / 'controller' / (role + '_ownership.json'),
                   logbase=root / 'controller' / role)


def run(root, *, poll_seconds=10, starter=None, release=None, guard=None,
        sleeper=time.sleep, monotonic=time.monotonic):
    root = Path(root).resolve()
    if poll_seconds != 10:
        raise ValueError('The frozen supervisor heartbeat is10 seconds')
    release, guard = release or service_release, guard or c.require_execution_freeze
    with c.original.lock_output(root / 'controller/supervisor_lock'):
        try:
            guard(root)
        except Exception as error:
            stop_dispatch(root, error)
            status(root, 'SUPERVISOR_BLOCKED', error_type=type(error).__name__, error=str(error),
                   completion_claimed=False)
            raise
        progress = root / 'run/progress.json'
        if not progress.is_file():
            raise ValueError('Controller.prepare must precede service startup')
        ledger_path = root / 'controller/supervisor_launches.json'
        ledger = c.read(ledger_path) if ledger_path.exists() else {'services': [], 'reporter': []}
        def start(role):
            history = ledger[role]
            if len(history) >= 3:
                # Exact adoption of an already-live third launch remains allowed.
                pointer = root / 'controller' / (role + '_ownership.json')
                if not pointer.is_file():
                    raise RuntimeError('Infrastructure process launch allowance exhausted')
                from code_sfpruner300_20261114 import service_queue as sq
                saved = c.read(pointer)
                current = sq.identity(saved['identity']['pid'])
                if not sq.owned(saved['identity'], current, saved['command'], saved['cwd']):
                    raise RuntimeError('Infrastructure process launch allowance exhausted')
            process, receipt = launch(root, role, starter=starter)
            key = receipt.get('attempt', str(receipt['identity']['pid']) + ':' + str(receipt['identity']['start_ticks']))
            if key not in history:
                if len(history) >= 3:
                    raise RuntimeError('Unexpected launch exceeded the persistent allowance')
                history.append(key)
                c.write(ledger_path, ledger)
            return process, receipt
        cpu, cpu_receipt = start('reporter')
        queue = queue_receipt = None
        fatal = None
        exit_records = []
        try:
            if not closed(root):
                sessions = root / 'controller/service_queue/sessions'
                if len(list(sessions.glob('*'))) >= 3:
                    raise RuntimeError('Three infrastructure service sessions already exist')
                queue, queue_receipt = start('services')
            drain_started = None
            release_started = None
            while True:
                try:
                    guard(root)
                    if (root / 'controller/report_fatal.json').exists():
                        raise ValueError('Independent CPU reporter reported an integrity/fatal error')
                except Exception as error:
                    if fatal is None:
                        fatal = type(error).__name__ + ': ' + str(error)
                        stop_dispatch(root, fatal)
                        drain_started = monotonic()
                queue_code = queue.poll() if queue is not None else None
                if queue is not None and queue_code is not None:
                    exit_records.append({'returncode': queue_code,
                                         'ownership_receipt': queue_receipt,
                                         'unknown_exit_is_not_zero': queue_code == recovery.UNKNOWN_EXIT})
                    queue = None
                if queue is None:
                    released = release(root)
                    if not released['all_owned_services_and_CUDA_children_exited']:
                        release_started = release_started or monotonic()
                        if monotonic() - release_started > 60:
                            raise RuntimeError('Service/CUDA exit evidence incomplete; preserve run for review')
                        status(root, 'WAITING_OWNED_SERVICE_RELEASE', fatal=fatal)
                        sleeper(poll_seconds)
                        continue
                    release_started = None
                    if fatal:
                        raise RuntimeError(fatal)
                    if closed(root):
                        reports = verified_report_completion(root)
                        if reports:
                            guard(root)
                            result = {'phase': 'COMPLETE_REPORT_READY',
                                      'allocated': c.read(root / 'manifest.json')['n'],
                                      'terminal_arms': 3 * c.read(root / 'manifest.json')['n'],
                                      'all_groups_and_arms_terminal': True,
                                      'service_release': released, 'reports': reports,
                                      'queue_exits': exit_records, 'reporting_blocked_GPU_dispatch': False,
                                      'models_called_by_supervisor': False}
                            c.write(root / 'completion.json', result, immutable=True)
                            return status(root, **result)
                    else:
                        sessions = root / 'controller/service_queue/sessions'
                        if len(list(sessions.glob('*'))) >= 3:
                            raise RuntimeError('Three infrastructure service sessions exhausted')
                        queue, queue_receipt = start('services')
                if cpu.poll() is not None and verified_report_completion(root) is None:
                    if (root / 'controller/report_fatal.json').exists():
                        continue
                    cpu, cpu_receipt = start('reporter')
                if fatal and drain_started is not None and monotonic() - drain_started > 3660:
                    raise RuntimeError('Dispatcher did not drain after integrity stop; no completion claimed')
                queue_status = root / 'controller/service_queue/status.json'
                observation = c.read(queue_status) if queue_status.exists() else {}
                heartbeat_age = max(0., time.time() - max(
                    progress.stat().st_mtime,
                    queue_status.stat().st_mtime if queue_status.exists() else 0.))
                status(root, 'DRAINING_INTEGRITY_STOP' if fatal else 'RUNNING',
                       queue_phase=observation.get('phase'), queue_owned_pid=queue.pid if queue else None,
                       heartbeat_age_seconds=heartbeat_age, stale_warning=heartbeat_age > 180,
                       CPU_reports_independent=True, completed_prefixes_do_not_block_GPU=True)
                sleeper(poll_seconds)
        except BaseException as error:
            stop_dispatch(root, type(error).__name__ + ': ' + str(error))
            # These are exact, independent-session receipts; foreign PIDs are never addressed.
            shutdown = {}
            for role, process, receipt in [('services', queue, queue_receipt), ('reporter', cpu, cpu_receipt)]:
                if process is not None and receipt is not None and process.poll() is None:
                    shutdown[role] = recovery.stop_saved(receipt)
            status(root, 'SUPERVISOR_BLOCKED', error_type=type(error).__name__, error=str(error),
                   owned_shutdown=shutdown, raw_evidence_preserved=True, completion_claimed=False)
            raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=c.DEFAULT_ROOT)
    p.add_argument('--poll-seconds', type=int, default=10)
    args = p.parse_args()
    run(args.root, poll_seconds=args.poll_seconds)


if __name__ == '__main__':
    main()
