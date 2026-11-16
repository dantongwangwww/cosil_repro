"""CPU preparation pipeline, conservative GPU queue, and fixed-prefix reports.

The pilot100 and the original execution implementation are read-only. Five new
batches run the remaining460 once. Outcome checkpoints never change the method,
membership or order, and no ablation/training/repair experiment is dispatched.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from code_locbench_sfpruner_20261116 import report as old_report
from code_locbench_sfpruner_20261116 import supervise as old_supervisor
from code_locbench_sfpruner_20261116.parallel_controller import ParallelController
from code_sfpruner300_20261114 import controller as c, service_queue as sq

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NEW = (100, 100, 100, 100, 60)


def read(path):
    return c.read(Path(path))


def update(root, phase, **extra):
    value = {'phase': phase, 'utc_unix': time.time(), 'pid': os.getpid(), **extra}
    c.write(Path(root) / 'controller/status.json', value)
    return value


def plan_for(root):
    from .prepare import validate_plan
    root = Path(root).resolve()
    plan = validate_plan(root)
    batches = plan['batches']
    if tuple(x['n'] for x in batches) != EXPECTED_NEW:
        raise ValueError('Only the authorized100/100/100/100/60 continuation is allowed')
    return plan


def code_files():
    return sorted(set(old_report.source_files() + list(Path(__file__).parent.glob('*.py'))))


def verify_hashes(mapping):
    for path, expected in mapping.items():
        if c.sha(path) != expected:
            raise ValueError('Frozen continuation source/input changed: ' + path)


def bind_execution(root):
    root = Path(root)
    publication = root / 'audits/execution_publication/publication_receipt.json'
    receipt = read(publication)
    if not str(receipt.get('status', '')).endswith('PASS') or not receipt.get('commit'):
        raise ValueError('Published recoverable continuation source is required')
    target = root / 'controller/execution_freeze.json'
    if target.exists():
        frozen = read(target)
        if (frozen['publication_sha256'] != c.sha(publication)
                or frozen['plan_sha256'] != c.sha(root / 'plan.json')):
            raise ValueError('Published execution or membership changed on continuation')
        verify_hashes(frozen['files_sha256'])
        return frozen
    plan = plan_for(root)
    pilot = Path(plan['pilot'])
    published = receipt.get('source_sha256', {})
    new_sources = {str(p.resolve()) for p in Path(__file__).parent.glob('*.py')}
    if not new_sources <= set(published):
        raise ValueError('Execution publication omits continuation source byte bindings')
    verify_hashes(published)
    prior_source_map = read(pilot / 'controller/report_freeze.json')['source_sha256']
    inherited = {str(p.resolve()) for p in code_files()} - new_sources
    if not inherited <= set(prior_source_map):
        raise ValueError('An inherited execution dependency lacks its original frozen binding')
    verify_hashes({p: prior_source_map[p] for p in inherited})
    prior_reports = read(pilot / 'reports/final/output_sha256.json')
    pilot_inputs = {str(pilot / 'reports/final' / name): sha for name, sha in prior_reports.items()}
    pilot_inputs.update(old_supervisor.immutable_arm_files(pilot / 'paired_run'))
    verify_hashes(pilot_inputs)
    frozen = {'status': 'FROZEN_BEFORE_NEW_MODEL_CALLS', 'commit': receipt['commit'],
        'plan_sha256': c.sha(root / 'plan.json'), 'publication_sha256': c.sha(publication),
        'files_sha256': {str(p.resolve()): c.sha(p) for p in code_files()},
        'pilot_preserved_sha256': pilot_inputs, 'method_changes': False,
        'ablation_training_repair_dispatched': False, 'sealed_test_opened': False}
    c.write(target, frozen, immutable=True)
    return frozen


def validate_before_launch(work):
    """Offline source qualification; no Gold content enters the clean jobs."""
    work = Path(work)
    allocation = read(work / 'allocation.json')['records']
    manifest = read(work / 'runtime/runnable_manifest.json')
    status = read(work / 'runtime/allocation_status.json')
    gold = read(work / 'evaluator_private/official_gold.private.json')
    if (status['allocated'] != len(allocation) or status['runnable'] != manifest['n']
            or len(gold) != len(allocation) or status['blocked'] + manifest['n'] != len(allocation)):
        raise ValueError('Every allocated task must retain a preparation outcome')
    targets = files = 0
    for row in manifest['records']:
        iid = row['instance_id']
        job_path = (work / 'runtime' / row['job']).resolve(strict=True)
        job = c.load_job(job_path)
        index = read(job['code_index'])
        actual = {path + '::' + definition['qualified_name'] for path, item in index.items()
                  for definition in item['definitions'] if definition['kind'] == 'function'}
        wanted = set(gold[iid]['targets'])
        if (not wanted or not gold[iid].get('set_complete') or not wanted <= actual
                or any(job[key] != row[key] for key in ('instance_id', 'repo', 'base_commit'))):
            raise ValueError('Official complete existing targets missing from clean base inventory: ' + iid)
        for name in gold[iid]['gold_files']:
            if c.sha(Path(job['snapshot']) / name) != index[name]['raw_sha256']:
                raise ValueError('Target base file bytes changed: ' + iid)
        targets += len(wanted)
        files += len(gold[iid]['gold_files'])
    value = {'status': 'PASS', 'allocated': len(allocation), 'runnable': manifest['n'],
        'preparation_blocked': status['blocked'], 'qualified_existing_targets': targets,
        'target_file_pairs': files, 'gold_used_for_source_qualification_only': True,
        'gold_scored': False, 'model_called': False, 'clean_job_schema_enforced': True}
    c.write(work / 'audits/prelaunch_inventory_gate.json', value, immutable=True)
    return value


def prepare_execution(root, spec, frozen):
    work = Path(spec['work'])
    verify_hashes(frozen['files_sha256'])
    old_report.check_public_inputs(old_report.locations(work), expected_n=spec['n'])
    validate_before_launch(work)
    manifest = work / 'runtime/runnable_manifest.json'
    count = read(manifest)['n']
    if count:
        ParallelController(manifest, work / 'paired_run').prepare()
    raw_freeze = work / 'controller/report_freeze_original.json'
    report_freeze = work / 'controller/report_freeze.json'
    if not raw_freeze.exists():
        old_report.freeze_inputs(work, raw_freeze)
    extended = read(raw_freeze)
    extended['source_sha256'].update(frozen['files_sha256'])
    extended['continuation_execution_commit'] = frozen['commit']
    extended['continuation_plan_sha256'] = frozen['plan_sha256']
    c.write(report_freeze, extended, immutable=True)
    sources = dict(frozen['files_sha256'])
    for path in (work / 'protocol.json', work / 'allocation.json', manifest,
                 work / 'runtime/allocation_status.json', work / 'audits/runtime_gate.json',
                 work / 'audits/prelaunch_inventory_gate.json', report_freeze):
        sources[str(path)] = c.sha(path)
    if count:
        sources[str(work / 'paired_run/freeze.json')] = c.sha(work / 'paired_run/freeze.json')
    ready = {'status': 'READY', 'allocated': spec['n'], 'runnable': count,
        'protocol_sha256': c.sha(work / 'protocol.json'), 'execution_commit': frozen['commit'],
        'files_sha256': sources, 'pair_workers': 2, 'method_unchanged': True,
        'prior_pilot_predictions_replayed': False}
    c.write(work / 'controller/launch_ready.json', ready, immutable=True)
    return ready


def descendants(work):
    """Capture only descendants of this batch's saved service leaders."""
    work = Path(work)
    saved_file = work / 'controller/observed_service_processes.json'
    saved = read(saved_file)['identities'] if saved_file.exists() else {}
    leaders = []
    for p in (work / 'service_queue/sessions').glob('*/*/ownership.json'):
        identity = read(p)['identity']
        key = str(identity['pid']) + ':' + str(identity['start_ticks'])
        saved[key] = identity
        if c.same_process(identity, sq.identity(identity['pid'])):
            leaders.append(identity['pid'])
    parents = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            stat = (p / 'stat').read_text()
            fields = stat[stat.rfind(')') + 2:].split()
            parents[int(p.name)] = int(fields[1])
        except (OSError, ValueError):
            pass
    owned = set(leaders)
    while True:
        new = {pid for pid, parent in parents.items() if parent in owned}
        if new <= owned:
            break
        owned |= new
    for pid in owned:
        identity = sq.identity(pid)
        if identity is not None and identity['uid'] == os.getuid():
            saved[str(pid) + ':' + str(identity['start_ticks'])] = identity
    if saved:
        c.write(saved_file, {'identities': saved, 'signals_sent': False})
    return saved


def release_check(work, *, wait_seconds=60):
    deadline = time.monotonic() + wait_seconds
    while True:
        observed = descendants(work)
        alive = [x['pid'] for x in observed.values()
                 if c.same_process(x, sq.identity(x['pid']))]
        if not alive or time.monotonic() >= deadline:
            value = {'all_observed_service_processes_exited': not alive, 'still_alive': alive,
                'observed_processes': len(observed), 'signals_sent': False,
                'preserved_cleanup_warnings': [str(p) for p in
                    (Path(work) / 'service_queue/sessions').glob('*/failure.json')]}
            c.write(Path(work) / 'controller/service_release.json', value)
            return value
        time.sleep(5)


def launch_queue(root, spec, attempt, frozen, *, poll=10, cpu_child=None):
    from .recovery import start_or_adopt, stop_saved
    work = Path(spec['work'])
    manifest, run = work / 'runtime/runnable_manifest.json', work / 'paired_run'
    command = [sys.executable, '-B', '-m', 'code_locbench_sfpruner_20261116.queue', '--wait',
        '--manifest', str(manifest), '--run-dir', str(run), '--queue-dir', str(work / 'service_queue'),
        '--judge-gpu', '1', '--poll-seconds', str(poll)]
    out = work / 'controller' / f'queue_attempt_{attempt:02d}'
    existed = out.exists()
    out.mkdir(exist_ok=True)
    previous_file = out / 'previous_arm_sha256.json'
    if previous_file.exists():
        previous = read(previous_file)
        old_supervisor.verify_existing(previous)
    else:
        if existed:
            raise RuntimeError('Interrupted queue launch lacks its prior-byte binding')
        previous = old_supervisor.immutable_arm_files(run)
        c.write(previous_file, previous, immutable=True)
    if (out / 'completion.json').exists():
        release = release_check(work)
        if not release['all_observed_service_processes_exited']:
            raise RuntimeError('A prior completed attempt still has a live owned service')
        return {**read(out / 'completion.json'), 'service_release': release,
                'prior_completion_release_rechecked': True}
    receipt_path = out / 'ownership.json'
    if existed:
        if not receipt_path.exists():
            raise RuntimeError('Interrupted queue launch lacks an ownership receipt; refuse guessing')
        saved = read(receipt_path)
        current = sq.identity(saved['identity']['pid'])
        if not c.same_process(saved['identity'], current):
            release = release_check(work)
            result = {'exit_code': None, 'exit_status_known': False,
                'counts': old_supervisor.terminal_counts(manifest, run),
                'previous_arm_bytes_preserved': True, 'whole_arm_or_task_reruns': 0,
                'recovered_prior_queue_exit': True, 'service_release': release}
            if not release['all_observed_service_processes_exited']:
                raise RuntimeError('Prior queue has a live owned service; refuse a replacement')
            c.write(out / 'completion.json', result, immutable=True)
            return result
    child, receipt = start_or_adopt(command, cwd=ROOT, env=old_supervisor.queue_environment(),
        ownership_path=receipt_path, logbase=out / 'console')
    try:
        while child.poll() is None:
            counts = old_supervisor.terminal_counts(manifest, run)
            queue_status = read(work / 'service_queue/status.json') if (work / 'service_queue/status.json').exists() else {}
            descendants(work)
            cpu_exit = cpu_child.poll() if cpu_child is not None else None
            prepared_status = root / 'preparation/status.json'
            prepared_phase = read(prepared_status).get('phase') if prepared_status.exists() else None
            phase = ('RUNNING_WITH_CPU_PREPARATION_ERROR'
                     if cpu_exit not in (None, 0) and prepared_phase != 'ALL_CPU_PREPARED' else 'RUNNING')
            update(root, phase, batch=spec['name'], batch_index=spec['index'],
                batch_n=spec['n'], attempt=attempt, queue_phase=queue_status.get('phase'),
                cpu_preparation_exit_code=cpu_exit, **counts)
            verify_hashes(frozen['files_sha256'])
            time.sleep(poll)
    except BaseException:
        stopped = stop_saved(receipt)
        c.write(out / ('supervisor_error_shutdown_' + str(time.time_ns()) + '.json'), stopped, immutable=True)
        release_check(work)
        raise
    old_supervisor.verify_existing(previous)
    release = release_check(work)
    result = {'exit_code': None if child.adopted else child.returncode,
        'exit_status_known': not child.adopted,
        'counts': old_supervisor.terminal_counts(manifest, run),
        'previous_arm_bytes_preserved': True, 'whole_arm_or_task_reruns': 0, 'service_release': release}
    c.write(out / 'completion.json', result, immutable=True)
    if not release['all_observed_service_processes_exited']:
        raise RuntimeError('Owned service descendant still alive; refusing duplicate model service')
    return result


def prepare_all(root, *, workers=4):
    from .prepare import prepare_batch
    root = Path(root).resolve()
    with c.lock_output(root / 'cpu_preparation_lock'):
        plan = plan_for(root)
        for spec in plan['batches']:
            work = Path(spec['work'])
            c.write(root / 'preparation/status.json', {'phase': 'PREPARING', 'batch': spec['name'],
                'pid': os.getpid(), 'utc_unix': time.time()})
            if (work / 'audits/runtime_gate.json').exists():
                gate = read(work / 'audits/runtime_gate.json')
                if gate['status'] != 'PASS':
                    raise RuntimeError('Existing CPU gate failed')
            else:
                prepare_batch(work, workers=workers)
        c.write(root / 'preparation/status.json', {'phase': 'ALL_CPU_PREPARED',
            'pid': os.getpid(), 'utc_unix': time.time(), 'batches': 5, 'allocated': 460})


def _wait(root, *, poll=10):
    from . import report
    from .recovery import start_or_adopt, preserve_partial_output, UNKNOWN_EXIT
    root = Path(root).resolve()
    with c.lock_output(root / 'supervisor_lock'):
        plan = plan_for(root)
        frozen = bind_execution(root)
        cpu_command = [sys.executable, '-B', '-m', 'code_locbench_full_20261116.supervise',
            '--prepare-only', '--root', str(root)]
        all_cpu_ready = all((Path(spec['work']) / 'audits/runtime_gate.json').exists()
                            for spec in plan['batches'])
        cpu_child = cpu_receipt = None
        if not all_cpu_ready:
            cpu_child, cpu_receipt = start_or_adopt(cpu_command, cwd=ROOT, env=None,
                ownership_path=root / 'controller/cpu_preparation_ownership.json',
                logbase=root / 'controller/cpu_preparation')
        completed_reports = [Path(plan['pilot']) / 'reports/final']
        batch_results = []
        for spec in plan['batches']:
            work = Path(spec['work'])
            while not (work / 'audits/runtime_gate.json').is_file():
                if cpu_child is None or cpu_child.poll() is not None:
                    raise RuntimeError('CPU preparation exited before this fixed batch was ready')
                update(root, 'WAITING_CPU_PREPARATION', batch=spec['name'], batch_n=spec['n'])
                time.sleep(poll)
            ready = prepare_execution(root, spec, frozen)
            old_completion = read(work / 'completion.json') if (work / 'completion.json').exists() else None
            if old_completion and not release_check(work)['all_observed_service_processes_exited']:
                raise RuntimeError('A completed batch still has a live owned service')
            attempts = old_completion['attempts'] if old_completion else []
            if ready['runnable'] and not old_completion:
                for attempt in range(1, 4):
                    result = launch_queue(root, spec, attempt, frozen, poll=poll, cpu_child=cpu_child)
                    attempts.append(result)
                    if result['counts']['all_terminal']:
                        break
                else:
                    raise RuntimeError('Three infrastructure launches exhausted; started arms never replayed')
            update(root, 'SCORING_BATCH', batch=spec['name'], batch_n=spec['n'])
            batch_report = work / 'reports/final'
            if (batch_report / 'output_sha256.json').exists():
                report.report_gate(batch_report)
            else:
                preserve_partial_output(batch_report)
                report.report_batch(work)
            completed_reports.append(work / 'reports/final')
            total = 100 + sum(read(p / 'summary.json')['allocated'] for p in completed_reports[1:])
            update(root, 'SCORING_CUMULATIVE', total=total, batch=spec['name'])
            cumulative = root / 'reports' / f'cumulative{total}'
            if (cumulative / 'output_sha256.json').exists():
                report.verified_outputs(cumulative)
                combined = read(cumulative / 'summary.json')
                if combined['allocated'] != total:
                    raise ValueError('Existing cumulative report has the wrong denominator')
            else:
                preserve_partial_output(cumulative)
                combined = report.combine(completed_reports, cumulative)
            done = {'batch': spec['name'], 'allocated': spec['n'], 'attempts': attempts,
                'cumulative_allocated': total, 'report': str(root / 'reports' / f'cumulative{total}'),
                'method_changed_after_outcomes': False}
            c.write(work / 'completion.json', done, immutable=True)
            batch_results.append(done)
            update(root, 'CHECKPOINT_COMPLETE', **done)
            verify_hashes(frozen['pilot_preserved_sha256'])
        if cpu_child is not None:
            cpu_exit = cpu_child.wait(timeout=60)
            if cpu_exit not in (0, UNKNOWN_EXIT) or not all(
                    (Path(spec['work']) / 'audits/runtime_gate.json').exists() for spec in plan['batches']):
                raise RuntimeError('CPU preparation pipeline returned a failure')
        verify_hashes(frozen['files_sha256'])
        verify_hashes(frozen['pilot_preserved_sha256'])
        result = {'phase': 'COMPLETE_REPORT_READY', 'allocated': 560, 'reused_pilot': 100,
            'new_allocated': 460, 'batches': batch_results,
            'report_directory': str(root / 'reports/cumulative560'),
            'ablation_training_repair_dispatched': False, 'external_API_USD': 0}
        c.write(root / 'completion.json', result, immutable=True)
        return update(root, **result)


def cleanup_on_error(root):
    """Stop only this root's exact saved CPU/queue sessions, never foreign jobs."""
    from .recovery import stop_saved
    root = Path(root).resolve()
    paths = list(root.glob('batch*/controller/queue_attempt_*/ownership.json'))
    cpu = root / 'controller/cpu_preparation_ownership.json'
    if cpu.exists():
        paths.append(cpu)
    outcomes = []
    for path in paths:
        saved = read(path)
        command = saved.get('command', [])
        try:
            module = command[command.index('-m') + 1]
            if module == 'code_locbench_full_20261116.supervise':
                valid = ('--prepare-only' in command and Path(command[command.index('--root') + 1]).resolve() == root)
            elif module == 'code_locbench_sfpruner_20261116.queue':
                manifest = Path(command[command.index('--manifest') + 1]).resolve()
                valid = manifest.is_relative_to(root) and manifest.name == 'runnable_manifest.json'
            else:
                valid = False
        except (ValueError, IndexError):
            valid = False
        outcome = stop_saved(saved) if valid else {'signal_sent': False, 'reason': 'unrecognized command family'}
        outcomes.append({'receipt': str(path), 'outcome': outcome})
    c.write(root / 'controller' / ('error_cleanup_' + str(time.time_ns()) + '.json'),
        {'outcomes': outcomes, 'foreign_processes_signaled': False}, immutable=True)
    return outcomes


def wait(root, *, poll=10):
    try:
        return _wait(root, poll=poll)
    except BaseException:
        cleanup_on_error(root)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--poll-seconds', type=int, default=10)
    args = parser.parse_args()
    if not 2 <= args.poll_seconds <= 60:
        parser.error('poll-seconds must be2..60')
    try:
        if args.prepare_only:
            prepare_all(args.root)
        else:
            wait(args.root, poll=args.poll_seconds)
    except BaseException as error:
        if args.prepare_only:
            c.write(args.root / 'preparation/status.json', {'phase': 'CPU_PREPARATION_BLOCKED',
                'pid': os.getpid(), 'utc_unix': time.time(), 'error_type': type(error).__name__,
                'error': str(error), 'evidence_preserved': True})
        else:
            update(args.root, 'SUPERVISOR_BLOCKED', error_type=type(error).__name__,
                error=str(error), evidence_preserved=True)
        raise


if __name__ == '__main__':
    main()
