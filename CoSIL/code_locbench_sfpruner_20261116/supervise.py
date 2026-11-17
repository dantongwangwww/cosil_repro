"""Persistent frozen-method execution, monitoring and offline completion report.

Only unstarted arms may continue after infrastructure failure. Started receipts
and terminal predictions are immutable; the original controller enforces this.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from code_sfpruner300_20261114 import controller as c, service_queue as sq

ROOT = Path(__file__).resolve().parents[1]
DATASET_REVISION = 'c44cf3b74e07ca642cec841b471a9939907c12a7'


def read(path):
    return json.loads(Path(path).read_text())


def status(work, phase, **extra):
    value = {'phase': phase, 'utc_unix': time.time(), 'pid': os.getpid(), **extra}
    c.write(work/'controller/status.json', value)
    return value


def immutable_arm_files(run):
    """No previous attempt may be overwritten or removed on continuation."""
    paths = list(Path(run).glob('pairs/*/*/started.json'))
    paths += list(Path(run).glob('pairs/*/*/terminal.json'))
    paths += list(Path(run).glob('pairs/*/*/result.json'))
    return {str(p): c.sha(p) for p in paths}


def verify_existing(files):
    for path, expected in files.items():
        if not Path(path).is_file() or c.sha(path) != expected:
            raise ValueError('Existing arm evidence changed: '+path)


def terminal_counts(manifest, run):
    roster = read(manifest)['records']; run = Path(run)
    arms = pairs = 0
    for row in roster:
        pair = run/'pairs'/row['instance_id']; states = []
        for arm in c.ARMS:
            path = pair/arm/'terminal.json'
            if path.exists():
                term = read(path)
                if term.get('status') not in c.TERMINAL or term.get('instance_id') != row['instance_id']:
                    raise ValueError('Invalid terminal identity/status')
                arms += 1; states.append(True)
            else:
                states.append(False)
        if all(states) and (pair/'pair_terminal.json').is_file():
            pairs += 1
    return {'selected': len(roster), 'terminal_arms': arms, 'terminal_pairs': pairs,
            'all_terminal': arms == 2*len(roster) and pairs == len(roster)}


def verify_launch_inputs(work):
    ready = read(work/'controller/launch_ready.json')
    protocol = read(work/'protocol.json')
    if (c.sha(work/'protocol.json') != ready.get('protocol_sha256')
            or protocol.get('dataset') != 'czlll/Loc-Bench_V1'
            or protocol.get('revision') != DATASET_REVISION):
        raise ValueError('LocBench protocol drift')
    if (ready.get('status') != 'READY' or ready.get('allocated') != protocol.get('allocated')
            or protocol.get('allocated') not in (100, 560)):
        raise ValueError('Explicit preparation gate must match the authorized fixed roster')
    for path, expected in ready['files_sha256'].items():
        if c.sha(path) != expected:
            raise ValueError('Launch source/input drift: '+path)
    publication = read(work/'audits/execution_publication/publication_receipt.json')
    if not str(publication.get('status', '')).endswith('PASS') or not publication.get('commit'):
        raise ValueError('Recoverable execution-code publication is required')
    return ready


def queue_environment():
    env = dict(os.environ)
    env.update(PATH='/home/wdt/miniconda3/envs/cosil/lib/python3.11/site-packages/nvidia/cu13/bin:/home/wdt/miniconda3/envs/cosil/bin:/bin:/usr/bin',
        CUDA_HOME='/tmp/cosil_rebench_qwen3_8b_20261023/tools/cuda13',
        FLASHINFER_NVCC='/home/wdt/miniconda3/envs/cosil/lib/python3.11/site-packages/nvidia/cu13/bin/nvcc',
        PYTHONDONTWRITEBYTECODE='1')
    return env


def owned_services_released(work):
    """Check exact saved identities, never stop or adopt an unknown PID."""
    checks = []
    for p in sorted((work/'service_queue/sessions').glob('*/*/ownership.json')):
        saved = read(p)['identity']; current = sq.identity(saved['pid'])
        exited = current is None or current.get('state') == 'Z' or not c.same_process(saved, current)
        checks.append({'ownership_receipt': str(p), 'pid': saved['pid'], 'original_process_exited': exited})
    return {'all_original_processes_exited': all(x['original_process_exited'] for x in checks),
            'checks': checks, 'signals_sent_by_supervisor': False}


def launch_queue(work, attempt, *, poll=10):
    manifest, run = work/'runtime/runnable_manifest.json', work/'paired_run'
    command = [sys.executable, '-B', '-m', 'code_locbench_sfpruner_20261116.queue', '--wait',
        '--manifest', str(manifest), '--run-dir', str(run), '--queue-dir', str(work/'service_queue'),
        '--judge-gpu', '1', '--poll-seconds', str(poll)]
    out = work/'controller'/f'queue_attempt_{attempt:02d}'
    out.mkdir(exist_ok=False)
    prior = immutable_arm_files(run)
    c.write(out/'previous_arm_sha256.json', prior, immutable=True)
    with (out/'console.log').open('xb') as stream:
        child = subprocess.Popen(command, cwd=ROOT, env=queue_environment(), stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        saved = sq.identity(child.pid)
        if saved is None:
            raise RuntimeError('Cannot capture queue identity; preserve output')
        c.write(out/'ownership.json', {'identity': saved, 'command': command, 'cwd': str(ROOT)}, immutable=True)
        while child.poll() is None:
            counts = terminal_counts(manifest, run)
            queue_status = read(work/'service_queue/status.json') if (work/'service_queue/status.json').exists() else {}
            status(work, 'RUNNING', attempt=attempt, queue_phase=queue_status.get('phase'), **counts)
            time.sleep(poll)
    verify_existing(prior)
    result = {'exit_code': child.returncode, 'counts': terminal_counts(manifest, run),
              'previous_attempts_preserved': True, 'semantic_retry': False,
              'service_release': owned_services_released(work)}
    c.write(out/'completion.json', result, immutable=True)
    return result


def wait(work, *, poll=10, max_infra_launches=3):
    work = Path(work).resolve()
    with c.lock_output(work/'supervisor'):
        while not (work/'controller/launch_ready.json').is_file():
            status(work, 'WAITING_CPU_PREPARATION', model_services_started=False)
            time.sleep(poll)
        ready = verify_launch_inputs(work)
        c.write(work/'controller/supervisor_plan.json', {'protocol_sha256': c.sha(work/'protocol.json'),
            'source_sha256': c.sha(__file__), 'max_infrastructure_queue_launches': max_infra_launches,
            'semantic_retries': 0, 'attempted_arms_never_replayed': True,
            'launch_ready_sha256': c.sha(work/'controller/launch_ready.json')}, immutable=True)
        manifest, run = work/'runtime/runnable_manifest.json', work/'paired_run'
        total = len(read(manifest)['records'])
        attempts = []
        if total:
            for attempt in range(1, max_infra_launches+1):
                verify_launch_inputs(work)
                result = launch_queue(work, attempt, poll=poll); attempts.append(result)
                if not result['service_release']['all_original_processes_exited']:
                    raise RuntimeError('Original owned service still alive; do not create duplicate services')
                if result['counts']['all_terminal']:
                    break
            else:
                raise RuntimeError('Infrastructure launch allowance exhausted; retained unstarted/failed evidence')
        allocated = read(work/'protocol.json')['allocated']
        status(work, 'SCORING', allocated=allocated, runnable=total)
        report_command = [sys.executable, '-B', '-m', 'code_locbench_sfpruner_20261116.report',
            '--freeze-file', str(work/'controller/report_freeze.json'), '--out', str(work/'reports/final')]
        with (work/'controller/report.log').open('xb') as stream:
            completed = subprocess.run(report_command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        if completed.returncode:
            raise RuntimeError('Offline report failed; raw results retained, no new model calls')
        value = {'phase': 'COMPLETE_REPORT_READY', 'allocated': allocated, 'runnable': total,
            'report_directory': str(work/'reports/final'), 'queue_attempts': attempts,
            'paid_API': False, 'paper_modified': False}
        c.write(work/'completion.json', value, immutable=True)
        return status(work, **value)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--wait', action='store_true')
    p.add_argument('--poll-seconds', type=int, default=10)
    p.add_argument('--max-infra-launches', type=int, default=3)
    a = p.parse_args()
    if not 1 <= a.max_infra_launches <= 3 or not 2 <= a.poll_seconds <= 60:
        p.error('fixed infrastructure cap1..3 and polling2..60 seconds required')
    if not a.wait:
        print(json.dumps(read(a.work/'controller/status.json')))
        return
    try:
        value = wait(a.work, poll=a.poll_seconds, max_infra_launches=a.max_infra_launches)
        print(json.dumps(value))
    except BaseException as error:
        status(a.work.resolve(), 'SUPERVISOR_BLOCKED', error_type=type(error).__name__, error=str(error),
               raw_evidence_retained=True, semantic_retry=False)
        raise


if __name__ == '__main__':
    main()
