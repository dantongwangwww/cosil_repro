"""Ordered, CPU-only reporting behind independent GPU completion barriers."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import time

from code_locbench_full_20261116 import prepare, report, recovery
from code_locbench_sfpruner_20261116 import supervise as old_supervisor
from code_sfpruner300_20261114 import controller as c, service_queue as sq

CPU_ATTEMPTS = 3
REPORTS_COMPLETE = 'ALL_REPORTS_COMPLETE'


def verify_execution(root, *, include_pilot=False):
    root = Path(root).resolve()
    if not (root/'controller/async_execution_freeze.json').is_file():
        raise ValueError('Missing async execution authority')
    for path in [root/'plan.json',root/'controller/execution_freeze.json']:
        if not path.is_file():
            raise ValueError('Missing mandatory frozen authority: '+str(path))
    frozen = c.read(root/'controller/async_execution_freeze.json')
    if (frozen.get('status') != 'ASYNC_EXECUTION_FROZEN' or not frozen.get('commit')
            or frozen.get('plan_sha256') != c.sha(root/'plan.json')
            or frozen.get('old_execution_freeze_sha256') != c.sha(root/'controller/execution_freeze.json')):
        raise ValueError('Async source/execution authority changed')
    source = frozen.get('files_sha256', {})
    required = [Path(__file__).resolve(), Path(report.__file__).resolve()]
    if not source or any(str(p) not in source for p in required):
        raise ValueError('Async worker or frozen evaluator missing from source binding')
    old = c.read(root/'controller/execution_freeze.json')
    if any(source.get(path) != wanted for path,wanted in old['files_sha256'].items()):
        raise ValueError('Async execution dropped or changed original frozen code')
    for path,wanted in source.items():
        if not Path(path).is_file() or c.sha(path) != wanted:
            raise ValueError('Frozen async source changed: '+path)
    pub = Path(frozen.get('async_publication_path',
        root/'audits/async_execution_publication/publication_receipt.json'))
    if not pub.is_file() or c.sha(pub) != frozen['async_publication_sha256']:
        raise ValueError('Async publication receipt changed')
    if include_pilot:
        for path,wanted in frozen['pilot_preserved_sha256'].items():
            if not Path(path).is_file() or c.sha(path) != wanted:
                raise ValueError('Historical pilot evidence changed: '+path)
    prepare.validate_plan(root)
    return frozen


def update(root, phase, **fields):
    value = {'phase':phase, 'utc_unix':time.time(), 'pid':os.getpid(),
        'models_called':False, 'gpu_used':False, **fields}
    c.write(Path(root)/'reports/async_status.json',value)
    return value


def gpu_gate(root, spec):
    verify_execution(root)
    work = Path(spec['work']); path = work/'controller/gpu_completion.json'
    for mandatory in [path,work/'runtime/runnable_manifest.json',work/'allocation.json',
                      work/'controller/report_freeze.json']:
        if not mandatory.is_file():
            raise ValueError('Missing mandatory GPU/frozen-input authority: '+str(mandatory))
    completed = c.read(path); manifest = c.read(work/'runtime/runnable_manifest.json')
    n = manifest['n']
    if (completed.get('status') != 'GPU_BATCH_COMPLETE'
            or completed.get('batch') != spec['name']
            or completed.get('n') != spec['n'] or completed.get('allocated') != spec['n']
            or completed.get('runnable') != n
            or completed.get('inference_protocol_changed') is not False
            or completed.get('service_release',{}).get('all_observed_service_processes_exited') is not True):
        raise ValueError('GPU completion/release barrier is incomplete or belongs to another batch')
    for field, target in [('manifest_sha256',work/'runtime/runnable_manifest.json'),
            ('allocation_sha256',work/'allocation.json'),
            ('report_freeze_sha256',work/'controller/report_freeze.json')]:
        if completed.get(field) != c.sha(target):
            raise ValueError('GPU completion frozen-input drift: '+field)
    counts = old_supervisor.terminal_counts(work/'runtime/runnable_manifest.json',work/'paired_run')
    if completed.get('counts') != counts or not counts['all_terminal']:
        raise ValueError('Not all runnable arms/pairs are terminal')
    expected = {str((work/'paired_run/pairs'/r['instance_id']/suffix).resolve())
        for r in manifest['records'] for suffix in
        ('baseline/terminal.json','hybrid_safe/terminal.json','pair_terminal.json')}
    terminals = completed.get('terminal_sha256',{})
    if set(terminals) != expected or len(terminals) != 3*n:
        raise ValueError('GPU completion omits or adds terminal receipts')
    for path,wanted in terminals.items():
        if Path(path).is_symlink() or not Path(path).is_file() or c.sha(path) != wanted:
            raise ValueError('Terminal receipt drift before offline scoring')
    # Subsequent batches may already own the same GPU/port; only this batch's
    # saved identities are checked. No global port/card idleness is required.
    saved = []
    for p in (work/'service_queue/sessions').glob('*/*/ownership.json'):
        saved.append(c.read(p)['identity'])
    observed = work/'controller/observed_service_processes.json'
    if observed.exists():
        saved += list(c.read(observed)['identities'].values())
    if n and not saved:
        raise ValueError('No saved service ownership proves release')
    if any(c.same_process(identity,sq.identity(identity['pid'])) for identity in saved):
        raise ValueError('This batch still has an original service process alive')
    verify_execution(root)
    barrier = report.original.terminal_barrier(c.read(work/'controller/report_freeze.json'))
    return completed, barrier


def cumulative_gate(directory, total, expected_reports):
    directory, _ = report.verified_outputs(directory)
    summary = c.read(directory/'summary.json')
    if (summary.get('status') != 'FINAL_CUMULATIVE_CHECKPOINT'
            or summary.get('allocated') != total
            or summary.get('dataset') != 'czlll/Loc-Bench_V1'
            or summary.get('future_batch_gold_opened') is not False
            or [Path(b['directory']).resolve() for b in summary['batches']]
                != [Path(p).resolve() for p in expected_reports]):
        raise ValueError('Cumulative report does not represent the fixed completed prefix')
    inputs = c.read(directory/'input_sha256.json')
    if not inputs:
        raise ValueError('Cumulative report lacks its immutable input provenance')
    for path,wanted in inputs.items():
        if c.sha(path) != wanted:
            raise ValueError('Cumulative source report changed: '+path)
    return summary


def process_batch(root, plan, spec, completed_dirs):
    root = Path(root).resolve(); work = Path(spec['work']).resolve()
    expected_prior = [Path(plan['pilot'])/'reports/final'] + [
        Path(b['work'])/'reports/final' for b in plan['batches'] if b['index']<spec['index']]
    if [Path(p).resolve() for p in completed_dirs] != [p.resolve() for p in expected_prior]:
        raise ValueError('Async reporting may not skip or reorder a batch')
    verify_execution(root,include_pilot=True)
    gpu_done, _ = gpu_gate(root,spec)
    update(root,'REPORTING_BATCH',batch=spec['name'],allocated=spec['n'])
    destination = work/'reports/final'
    if not (destination/'output_sha256.json').exists():
        recovery.preserve_partial_output(destination)
        verify_execution(root)
        report.report_batch(work)
    verify_execution(root)
    report.report_gate(destination)
    directories = list(expected_prior)+[destination]
    total = 100+sum(b['n'] for b in plan['batches'] if b['index']<=spec['index'])
    cumulative = root/'reports'/('cumulative'+str(total))
    if not (cumulative/'output_sha256.json').exists():
        recovery.preserve_partial_output(cumulative)
        verify_execution(root)
        update(root,'REPORTING_CUMULATIVE',batch=spec['name'],cumulative_allocated=total)
        report.combine(directories,cumulative)
    verify_execution(root)
    cumulative_gate(cumulative,total,directories)
    done = {'status':'REPORT_COMPLETE','batch':spec['name'],'allocated':spec['n'],
        'runnable':gpu_done['runnable'],'cumulative_allocated':total,
        'batch_report':str(destination),'report':str(cumulative),
        'gpu_completion_sha256':c.sha(work/'controller/gpu_completion.json'),
        'batch_output_manifest_sha256':c.sha(destination/'output_sha256.json'),
        'cumulative_output_manifest_sha256':c.sha(cumulative/'output_sha256.json'),
        'inference_protocol_changed':False,'models_called_by_reporter':False,
        'scoring_does_not_control_future_sampling_or_parameters':True}
    c.write(work/'completion.json',done,immutable=True)
    update(root,'REPORT_COMPLETE',**done)
    return done


def run(root, *, poll_seconds=10):
    if not 2<=poll_seconds<=60:
        raise ValueError('Polling must be between2 and60 seconds')
    root = Path(root).resolve()
    with c.lock_output(root/'reports/async_worker_lock'):
        verify_execution(root,include_pilot=True); plan = prepare.validate_plan(root)
        completed = [Path(plan['pilot'])/'reports/final']; records=[]
        for spec in plan['batches']:
            marker = Path(spec['work'])/'controller/gpu_completion.json'
            while not marker.exists():
                verify_execution(root)
                update(root,'WAITING_GPU_COMPLETION',batch=spec['name'],allocated=spec['n'])
                time.sleep(poll_seconds)
            for attempt in range(1,CPU_ATTEMPTS+1):
                try:
                    done = process_batch(root,plan,spec,completed)
                    break
                except OSError as error:
                    update(root,'REPORT_IO_ERROR',batch=spec['name'],cpu_attempt=attempt,
                        error_type=type(error).__name__,error=str(error),preserved_evidence=True)
                    if attempt==CPU_ATTEMPTS:
                        raise
                    time.sleep(2)
                except ValueError as error:
                    update(root,'FATAL_INTEGRITY_ERROR',batch=spec['name'],
                        error_type=type(error).__name__,error=str(error),preserved_evidence=True)
                    raise
            completed.append(Path(spec['work'])/'reports/final');records.append(done)
        verify_execution(root,include_pilot=True)
        result = {'status':REPORTS_COMPLETE,'allocated':560,'new_allocated':460,
            'reused_pilot':100,'batches':records,'report_directory':str(root/'reports/cumulative560'),
            'models_called':False,'gpu_used':False,'future_batch_gold_opened':False}
        c.write(root/'reports/async_completion.json',result,immutable=True)
        update(root,REPORTS_COMPLETE,allocated=560)
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--poll-seconds',type=int,default=10)
    args=parser.parse_args()
    try:
        run(args.root,poll_seconds=args.poll_seconds)
    except ValueError as error:
        update(args.root,'FATAL_INTEGRITY_ERROR',error_type=type(error).__name__,error=str(error))
        raise
    except OSError as error:
        update(args.root,'REPORT_IO_ERROR',error_type=type(error).__name__,error=str(error))
        raise


if __name__=='__main__':
    main()
