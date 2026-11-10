"""Controller-only continuation: never replay existing model outputs or relax context limits."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import time
import traceback
from code_qwen3_rr4.run import inventory, eligible, now
from . import config as P
from .rpc import request
from .run import verify, argv, one


def verify_continuation():
    frozen = P.read(P.OUT / 'continuation_freeze.json')
    for group in ('new_code_sha256', 'prior_model_artifacts_sha256'):
        for path, digest in frozen[group].items():
            if P.sha(path) != digest: raise RuntimeError('Continuation protected artifact changed: ' + path)
    receipt = P.read(P.OUT / 'continuation_implementation_publication.json')
    tests = P.read(P.OUT / 'continuation_cpu_tests.json')
    if not receipt['verified'] or not tests['passed'] or receipt['new_code_sha256'] != frozen['new_code_sha256'] or tests['new_code_sha256'] != frozen['new_code_sha256']:
        raise RuntimeError('Published/tested exact continuation source required')


def dependency_result(item, baseline):
    if baseline.get('status') == 'complete' or 'file_rank_after_reflection' in baseline:
        raise ValueError('Cannot replace a valid shared file stage')
    return {'status':'BLOCKED_SHARED_FILE_STAGE', 'instance_id':item['instance_id'], 'repo':item['repo'],
        'base_commit':item['base_commit'], 'arm':'hybrid_safe', 'model_called':False,
        'record_origin':'supervisor_dependency_failure_ledger_not_model_prediction',
        'reason':baseline.get('error','File stage unavailable'), 'dependency_baseline_status':baseline['status'],
        'predicted_files':[], 'predicted_functions':[], 'elapsed_seconds':0., 'file_stage_wall_seconds':0.,
        'stage_resources':{}, 'semantic_calls':0, 'http_attempts':0, 'known_prompt_tokens':0, 'known_completion_tokens':0,
        'usage_unknown_attempts':0, 'enable_thinking':False}


def record_dependency_block(item, baseline):
    directory = P.OUT / 'run/hybrid_safe' / item['instance_id']
    if (directory / 'started.json').exists() or (directory / 'calls').exists():
        raise RuntimeError('Do not replace any already started model arm')
    P.write(directory / 'result.json', dependency_result(item,baseline), immutable=True)
    P.write(directory / 'dependency_block.json', {'model_called':False,'preserve_allocated_denominator':True,
        'baseline_result_sha256':P.sha(P.OUT/'run/baseline'/item['instance_id']/'result.json')}, immutable=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait-hours', type=float, default=24)
    args = parser.parse_args()
    if not 0 < args.wait_hours <= 48:
        raise ValueError('Wait deadline must be 0–48 hours')
    P.configure(); verify(); verify_continuation()
    lock = (P.OUT / 'continuation.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (P.OUT / 'continuation_started.json').exists():
        raise FileExistsError('No implicit controller replay')
    P.write(P.OUT / 'continuation_started.json', {'utc': now(), 'pid': os.getpid()}, immutable=True)
    state = {'stage': 'WAITING_FOR_TWO_IDLE_GPUS', 'pid': os.getpid(), 'completed_pairs': 0,
             'physical_gpu_limit': 2, 'model_calls_started': False}
    def publish():
        state['utc'] = now(); P.write(P.OUT / 'continuation_status.json', state)
    from .deployment import adapt, stop_owned
    from . import continuation_report as report
    D = adapt(); D.SERVICE = P.OUT / 'run/service_continuation1'; service_started = False; scorer_process = None; scorer_stream = None
    try:
        publish(); report.create()
        deadline = time.monotonic() + args.wait_hours * 3600; previous = None; quiet = None
        while True:
            rows = inventory(); free = eligible(rows); chosen = tuple(free[:2]) if len(free) >= 2 else None
            quiet = (quiet or time.monotonic()) if chosen is not None and chosen == previous else (time.monotonic() if chosen else None)
            previous = chosen
            state.update(gpu_observation=rows, continuous_idle_seconds=time.monotonic() - quiet if quiet else 0)
            publish()
            if quiet and time.monotonic() - quiet >= 90:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('No two-card idle window before deadline')
            time.sleep(30)
        verify(); records = P.read(P.OUT / 'inputs/manifest.json')['records']
        probe_out = P.OUT / 'run/isolation_probe_continuation1'
        command, env = argv(records[0], probe_out, probe=True)
        probe = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        P.write(probe_out / 'controller.json', {'returncode': probe.returncode, 'stdout': probe.stdout, 'stderr': probe.stderr})
        if probe.returncode or not P.read(probe_out / 'probe.json')['passed']:
            raise RuntimeError('CPU isolation/cache probe failed')
        D.GPUS = chosen; state.update(stage='LOADING_OWNED_QWEN3', selected_gpus=chosen); publish()
        try:
            D.start(execute=True)
        finally:
            service_started = (D.SERVICE / 'ownership.json').exists()
        ready_deadline = time.monotonic() + 900
        while True:
            try:
                D.health(synthetic=True); break
            except Exception:
                owner = P.read(D.SERVICE / 'ownership.json')
                try:
                    alive = D.identity(owner['identity']['pid'])['state'] != 'Z'
                except (FileNotFoundError, ProcessLookupError):
                    alive = False
                if not alive or time.monotonic() >= ready_deadline:
                    raise RuntimeError('Qwen3 startup failed')
                time.sleep(5)
        state.update(stage='LOADING_RESIDENT_4B'); publish()
        if P.TRANSPORT.is_symlink():
            raise PermissionError('Transport cannot be a symlink')
        P.TRANSPORT.mkdir(mode=0o700, exist_ok=True)
        if P.SOCKET.exists() or P.SOCKET.is_symlink():
            raise FileExistsError('Existing judge socket belongs to another attempt')
        judge_out = P.OUT / 'run/judge_service_continuation1'
        command, env = argv(records[0], judge_out, server=True, gpu=chosen[1])
        scorer_stream = (judge_out / 'process.log').open('x')
        scorer_process = subprocess.Popen(command, env=env, stdout=scorer_stream, stderr=subprocess.STDOUT, start_new_session=True)
        P.write(judge_out / 'ownership.json', {'pid': scorer_process.pid, 'gpu': chosen[1], 'argv': command}, immutable=True)
        ready_deadline = time.monotonic() + 300
        while True:
            try:
                health = request('health'); break
            except (OSError, RuntimeError):
                if scorer_process.poll() is not None or time.monotonic() >= ready_deadline:
                    raise RuntimeError('Resident scorer startup failed')
                publish(); time.sleep(2)
        P.write(judge_out / 'health.json', health, immutable=True)
        resource = request('probe')
        P.write(judge_out / 'resource_probe.json', resource, immutable=True)
        if not resource['passed']:
            raise RuntimeError('Two-card max-length coexistence failed')
        smoke = P.read(P.OUT / 'score_smoke_private.json'); smoke_results = []
        for item in smoke['rows']:
            scored = request('score', item['row'])
            route = P.route(scored['p_yes'], P.read(P.OUT / 'deployment.json')['low'])
            good = abs(scored['logit_difference'] - item['reference_logit_difference']) <= smoke['maximum_logit_drift'] and route == item['reference_route']
            smoke_results.append({'instance_id': item['instance_id'], 'step': item['step'], 'passed': good, **scored})
            if not good:
                P.write(judge_out / 'smoke_failure.json', smoke_results)
                raise RuntimeError('Resident score fidelity failed; no benchmark calls')
        P.write(judge_out / 'smoke3.json', {'passed': True, 'rows': smoke_results, 'benchmark_calls': 0}, immutable=True)
        state.update(stage='RUNNING_REBENCH100', model_calls_started=True); publish()
        for item in records:
            iid = item['instance_id']
            old_b = P.OUT / 'run/baseline' / iid / 'result.json'
            old_h = P.OUT / 'run/hybrid_safe' / iid / 'result.json'
            if old_b.exists() and old_h.exists():
                continue
            state.update(active_issue=iid, active_arm='baseline'); publish()
            baseline = P.read(old_b) if old_b.exists() else one(item, 'baseline', publish, state)
            if baseline.get('status') != 'complete' and 'file_rank_after_reflection' not in baseline:
                record_dependency_block(item, baseline)
                state['completed_pairs'] = report.create()['attempted_pairs']; publish(); continue
            shared = P.OUT / 'shared' / (iid + '.json')
            P.write(shared, {'instance_id': iid, 'base_commit': item['base_commit'],
                  'files': baseline['file_rank_after_reflection'], 'raw_file_responses': baseline['raw_file_responses'],
                  'baseline_result_sha256': P.sha(P.OUT / 'run/baseline' / iid / 'result.json')}, immutable=True)
            state['active_arm'] = 'hybrid_safe'; publish()
            one(item, 'hybrid_safe', publish, state, shared)
            assessment = report.create(); state['completed_pairs'] = assessment['attempted_pairs']; publish()
            print('PAIRED', state['completed_pairs'], '/100', iid, flush=True)
        else:
            state['stage'] = 'COMPLETE'; publish()
    except BaseException as error:
        state.update(stage='FAILED', error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc()); publish()
        raise
    finally:
        cleanup = {}
        if scorer_process is not None:
            try:
                if scorer_process.poll() is None:
                    cleanup['judge'] = request('shutdown', timeout=20)
                    scorer_process.wait(timeout=30)
                cleanup['judge_exit_code'] = scorer_process.poll()
            except Exception as error:
                cleanup['judge_shutdown_error'] = str(error)
                if scorer_process.poll() is None:
                    scorer_process.terminate()
                    try:
                        scorer_process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        cleanup['judge_still_alive'] = True
        if scorer_stream:
            scorer_stream.close()
        if service_started:
            try:
                cleanup['main'] = stop_owned(D)
            except Exception as error:
                cleanup['main_shutdown_error'] = str(error)
        state['shutdown'] = cleanup
        P.write(P.OUT / 'continuation_shutdown.json', cleanup)
        publish(); report.create()


if __name__ == '__main__':
    main()
