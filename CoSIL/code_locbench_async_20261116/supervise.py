"""Advance GPU batches without waiting for ordered CPU report generation.

Frozen inference code and raw predictions remain unchanged. The old top
monitor alone is replaced, and its running queue is adopted without replay.
"""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import time

from code_locbench_full_20261116 import supervise as old
from code_locbench_full_20261116.recovery import start_or_adopt, stop_saved
from code_locbench_sfpruner_20261116 import supervise as original

c, sq, ROOT = old.c, old.sq, old.ROOT


def read(path):
    return c.read(Path(path))


def source_files():
    return sorted(set(old.code_files() + list(Path(__file__).parent.glob('*.py'))))


def bind_async(root):
    root = Path(root).resolve()
    publication = root / 'audits/async_execution_publication/publication_receipt.json'
    published = read(publication)
    if not str(published.get('status', '')).endswith('PASS') or not published.get('commit'):
        raise ValueError('Recoverable async publication required')
    new_paths = {str(p.resolve()) for p in Path(__file__).parent.glob('*.py')}
    if not new_paths <= set(published.get('source_sha256', {})):
        raise ValueError('Async published byte map incomplete')
    old.verify_hashes(published['source_sha256'])
    prior_path = root / 'controller/execution_freeze.json'; prior = read(prior_path)
    old.verify_hashes(prior['files_sha256']); old.verify_hashes(prior['pilot_preserved_sha256'])
    plan = old.plan_for(root)
    if prior['plan_sha256'] != c.sha(root / 'plan.json'):
        raise ValueError('Cohort changed')
    target = root / 'controller/async_execution_freeze.json'
    if target.exists():
        saved = read(target)
        if (saved['async_publication_sha256'] != c.sha(publication)
                or saved['old_execution_freeze_sha256'] != c.sha(prior_path)):
            raise ValueError('Inherited or async publication drift')
        old.verify_hashes(saved['files_sha256'])
        return saved
    value = {**deepcopy(prior), 'status': 'ASYNC_EXECUTION_FROZEN', 'commit': published['commit'],
        'prior_execution_commit': prior['commit'], 'async_publication_path': str(publication),
        'async_publication_sha256': c.sha(publication), 'old_execution_freeze_sha256': c.sha(prior_path),
        'files_sha256': {str(p.resolve()): c.sha(p) for p in source_files()},
        'reporting_only_change': True, 'inference_protocol_changed': False,
        'first_batch_existing_report_freeze_reused': True, 'reporter_gpu_use': False,
        'allocated': 560, 'remaining_plan_n': plan['n']}
    c.write(target, value, immutable=True)
    return value


def live_queues(root):
    found = []
    for p in Path(root).glob('batch*/controller/queue_attempt_*/ownership.json'):
        receipt = read(p); seen = sq.identity(receipt['identity']['pid'])
        if c.same_process(receipt['identity'], seen):
            if not sq.owned(receipt['identity'], seen, receipt['command'], receipt['cwd']):
                raise RuntimeError('Live queue failed exact ownership')
            found.append((p, receipt))
    return found


def handoff(root):
    root = Path(root).resolve(); frozen = bind_async(root)
    with c.lock_output(root / 'async_handoff_lock'):
        target = root / 'controller/async_handoff.json'
        if target.exists():
            saved = read(target)
            if saved['status'] != 'MONITOR_HANDOFF_COMPLETE':
                raise RuntimeError('Inspect incomplete handoff')
            return saved
        monitor_path = root / 'controller/supervisor_ownership.json'; monitor = read(monitor_path)
        from .handoff_signal import expected
        observed = sq.identity(monitor['identity']['pid'])
        if observed is not None and observed['state'] != 'Z' and not expected(monitor, root, observed):
            raise ValueError('Only the exact old top monitor may be replaced')
        queues = live_queues(root)
        if any(r['identity']['pgid'] == monitor['identity']['pgid'] for _, r in queues):
            raise ValueError('Queue sessions must differ from monitor session')
        intent_path = root / 'controller/async_handoff_intent.json'
        if intent_path.exists():
            intent = read(intent_path)
            if (intent['old_monitor_receipt_sha256'] != c.sha(monitor_path)
                    or intent['async_execution_commit'] != frozen['commit']):
                raise ValueError('Handoff intent changed')
            before = intent['existing_arm_sha256']; old.verify_hashes(before)
            queues = []
            for item in intent['queues']:
                path = Path(item['receipt'])
                if c.sha(path) != item['receipt_sha256']:
                    raise ValueError('Original queue ownership changed during handoff')
                queues.append((path, read(path)))
        else:
            before = {}
            for spec in old.plan_for(root)['batches']:
                before.update(original.immutable_arm_files(Path(spec['work']) / 'paired_run'))
            c.write(intent_path, {
                'status': 'BEFORE_MONITOR_ONLY_HANDOFF', 'old_monitor_receipt_sha256': c.sha(monitor_path),
                'old_monitor_identity': monitor['identity'],
                'queues': [{'receipt': str(p), 'receipt_sha256': c.sha(p)} for p, _ in queues],
                'existing_arm_sha256': before, 'async_execution_commit': frozen['commit'],
                'reason': 'replace only monitor; SIGTERM cleanup would stop the running queue'}, immutable=True)
        command = ['/usr/bin/python3.12', '-B', '-m', 'code_locbench_async_20261116.handoff_signal',
            '--receipt', str(monitor_path), '--root', str(root)]
        import json
        stopped = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=15))
        deadline = time.monotonic() + 10
        while c.same_process(monitor['identity'], sq.identity(monitor['identity']['pid'])):
            if time.monotonic() >= deadline:
                raise RuntimeError('Old monitor still alive; no replacement launched')
            time.sleep(.1)
        continuity = []
        for p, receipt in queues:
            same = sq.owned(receipt['identity'], sq.identity(receipt['identity']['pid']),
                            receipt['command'], receipt['cwd'])
            natural = False
            if not same:
                work = p.parents[2]
                natural = (original.terminal_counts(work / 'runtime/runnable_manifest.json', work / 'paired_run')['all_terminal']
                    and old.release_check(work)['all_observed_service_processes_exited'])
                if not natural:
                    raise RuntimeError('Queue continuity failed; inspect without replay')
            continuity.append({'receipt': str(p), 'pid': receipt['identity']['pid'],
                'same_identity': same, 'natural_batch_completion': natural})
        old.verify_hashes(before); old.verify_hashes(frozen['files_sha256'])
        result = {'status': 'MONITOR_HANDOFF_COMPLETE', 'old_monitor_pid': monitor['identity']['pid'],
            'monitor_signal': stopped, 'queue_continuity': continuity,
            'existing_arm_bytes_preserved': True, 'model_or_queue_signals': False,
            'inference_protocol_changed': False, 'async_execution_commit': frozen['commit']}
        c.write(target, result, immutable=True)
        return result


def ready_for_batch(root, spec, frozen):
    work = Path(spec['work']); path = work / 'controller/launch_ready.json'
    if path.exists():
        ready = read(path); old.verify_hashes(ready['files_sha256'])
        if (ready['status'] != 'READY' or ready['allocated'] != spec['n']
                or ready['protocol_sha256'] != c.sha(work / 'protocol.json')):
            raise ValueError('Existing batch preparation drift')
        # The running controller holds its lock. Never call prepare() again.
        return ready
    return old.prepare_execution(root, spec, frozen)


def gpu_completion(work, spec, attempts, frozen):
    work = Path(work); manifest = work / 'runtime/runnable_manifest.json'
    counts = original.terminal_counts(manifest, work / 'paired_run')
    if not counts['all_terminal']:
        raise ValueError('GPU completion requires all runnable arm and pair terminals')
    release = old.release_check(work)
    if not release['all_observed_service_processes_exited']:
        raise RuntimeError('Owned GPU descendants remain alive')
    terminals = terminal_metadata(work)
    result = {'status': 'GPU_BATCH_COMPLETE', 'batch': spec['name'], 'name': spec['name'],
        'n': spec['n'], 'allocated': spec['n'], 'runnable': counts['selected'], 'counts': counts,
        'terminal_sha256': terminals, 'service_release': release, 'attempts': attempts,
        'manifest_sha256': c.sha(manifest), 'allocation_sha256': c.sha(work / 'allocation.json'),
        'report_freeze_sha256': c.sha(work / 'controller/report_freeze.json'),
        'inference_protocol_changed': False, 'async_execution_commit': frozen['commit'],
        'report_complete': False, 'next_batch_does_not_wait_for_report': True}
    c.write(work / 'controller/gpu_completion.json', result, immutable=True)
    return result


def terminal_metadata(work):
    """Tiny metadata/result hashes only; no Gold or whole-repository hashing."""
    work = Path(work); manifest = work / 'runtime/runnable_manifest.json'
    terminals = {}; records = read(manifest)['records']
    protocol = read(work / 'paired_run/freeze.json')['protocol_sha256'] if records else None
    for row in records:
        pair = work / 'paired_run/pairs' / row['instance_id']
        states = {}
        for arm in c.ARMS:
            path = pair / arm / 'terminal.json'; term = read(path)
            if (term.get('instance_id') != row['instance_id'] or term.get('base_commit') != row['base_commit']
                    or term.get('arm') != arm or term.get('protocol_sha256') != protocol
                    or term.get('status') not in c.TERMINAL or term.get('simulation') is not False
                    or term.get('keep_in_denominator') is not True):
                raise ValueError('Terminal identity/protocol drift')
            if term.get('result_sha256'):
                if c.sha(pair / arm / 'result.json') != term['result_sha256']:
                    raise ValueError('Terminal/result SHA drift')
            elif term['status'] == 'complete':
                raise ValueError('Completed arm lacks a result binding')
            states[arm] = term
        paired = read(pair / 'pair_terminal.json')
        if (paired.get('instance_id') != row['instance_id'] or paired.get('protocol_sha256') != protocol
                or paired.get('arms') != states or paired.get('keep_in_denominator') is not True):
            raise ValueError('Pair terminal content drift')
        for p in [pair / arm / 'terminal.json' for arm in c.ARMS] + [pair / 'pair_terminal.json']:
            terminals[str(p.resolve())] = c.sha(p)
    return terminals


def validate_gpu_completion(work, spec):
    from .worker import gpu_gate
    work = Path(work)
    result, _ = gpu_gate(work.parent, spec)
    if not old.release_check(work)['all_observed_service_processes_exited']:
        raise RuntimeError('Prior GPU services still alive')
    return result


def model_batches(root, plan, frozen, reporter):
    results = []
    for spec in plan['batches']:
        old.verify_hashes(frozen['files_sha256'])
        report_status_path = Path(root) / 'reports/async_status.json'
        status = read(report_status_path) if report_status_path.exists() else {}
        if status.get('phase') == 'FATAL_INTEGRITY_ERROR':
            raise RuntimeError('Report integrity error; do not launch another GPU batch')
        work = Path(spec['work'])
        if (work / 'controller/gpu_completion.json').exists():
            results.append(validate_gpu_completion(work, spec)); continue
        ready = ready_for_batch(root, spec, frozen); attempts = []
        if ready['runnable']:
            for attempt in range(1, 4):
                value = old.launch_queue(root, spec, attempt, frozen, poll=10)
                attempts.append(value)
                if value['counts']['all_terminal']:
                    break
            else:
                raise RuntimeError('Infrastructure allowance exhausted; no started arm may replay')
        results.append(gpu_completion(work, spec, attempts, frozen))
        old.update(root, 'GPU_BATCH_COMPLETE_REPORT_ASYNC', batch=spec['name'],
            reports_phase=status.get('phase'), next_batch_waits_for_report=False)
        # There is deliberately no reporter.wait/report_batch/combine here.
    return results


def run(root, *, poll_seconds=10):
    from .worker import REPORTS_COMPLETE
    root = Path(root).resolve(); reporter = reporter_receipt = None
    with c.lock_output(root / 'supervisor_lock'):
        frozen = bind_async(root)
        if read(root / 'controller/async_handoff.json')['status'] != 'MONITOR_HANDOFF_COMPLETE':
            raise ValueError('Witnessed monitor-only handoff required')
        plan = old.plan_for(root)
        command = [sys.executable, '-B', '-m', 'code_locbench_async_20261116.worker',
            '--root', str(root), '--poll-seconds', str(poll_seconds)]
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='2')
        reporter, reporter_receipt = start_or_adopt(command, cwd=ROOT, env=env,
            ownership_path=root / 'controller/async_reporter_ownership.json',
            logbase=root / 'controller/async_reporter')
        try:
            models = model_batches(root, plan, frozen, reporter)
            c.write(root / 'controller/all_gpu_batches_complete.json', {
                'status': 'ALL_GPU_BATCHES_COMPLETE', 'batches': models, 'allocated': 560,
                'new_runnable': sum(x['runnable'] for x in models),
                'all_gpu_services_released': True}, immutable=True)
            done = root / 'reports/async_completion.json'
            while not done.exists():
                if reporter.poll() is not None:
                    raise RuntimeError('CPU reporter exited before checkpoint reports were ready')
                old.update(root, 'ALL_MODELS_COMPLETE_AWAITING_CPU_REPORTS',
                    allocated=560, model_services_running=False)
                time.sleep(poll_seconds)
            completed = read(done)
            if completed['status'] != REPORTS_COMPLETE or completed['allocated'] != 560:
                raise ValueError('Final CPU completion mismatch')
            old.verify_hashes(frozen['pilot_preserved_sha256'])
            result = {'phase': 'COMPLETE_REPORT_READY', 'allocated': 560, 'reused_pilot': 100,
                'new_allocated': 460, 'gpu_batches': models, 'cpu_reports': completed,
                'report_directory': str(root / 'reports/cumulative560'),
                'reporting_overlapped_subsequent_inference': True,
                'inference_protocol_changed': False, 'external_API_USD': 0}
            c.write(root / 'completion.json', result, immutable=True)
            old.update(root, **result)
            return result
        except BaseException:
            old.cleanup_on_error(root)
            if reporter_receipt is not None:
                c.write(root / 'controller' / ('async_report_error_shutdown_' + str(time.time_ns()) + '.json'),
                    stop_saved(reporter_receipt), immutable=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--handoff', action='store_true')
    parser.add_argument('--poll-seconds', type=int, default=10)
    args = parser.parse_args()
    try:
        handoff(args.root) if args.handoff else run(args.root, poll_seconds=args.poll_seconds)
    except BaseException as error:
        old.update(args.root, 'ASYNC_SUPERVISOR_BLOCKED', error_type=type(error).__name__,
            error=str(error), raw_evidence_preserved=True)
        raise


if __name__ == '__main__':
    main()
