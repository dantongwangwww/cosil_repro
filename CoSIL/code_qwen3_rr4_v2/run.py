"""Durable two-GPU canary controller, with one resident scorer and owned shutdown."""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
from code_qwen3_rr4.run import inventory, eligible, now
from . import config as P
from .rpc import request


def verify():
    frozen = P.read(P.OUT / 'freeze.json')
    for key in ('code_sha256', 'input_sha256', 'protected_sha256'):
        for path, expected in frozen[key].items():
            if P.sha(path) != expected:
                raise RuntimeError('Frozen artifact changed: ' + path)
    for path, expected in P.read(P.OUT / 'v1_results_protection.json').items():
        if P.sha(path) != expected:
            raise RuntimeError('Completed v1 result changed: ' + path)
    for filename, key in [('deployment.json', 'deployment_sha256'), ('evaluation_private.json', 'evaluation_private_sha256'),
                          ('score_smoke_private.json', 'score_smoke_sha256'), ('render_equivalence103.json', 'render_equivalence_sha256')]:
        if P.sha(P.OUT / filename) != frozen[key]:
            raise RuntimeError('Frozen configuration changed')
    from code_v6.common import test_stats
    if test_stats() != frozen['test_stat_only']:
        raise RuntimeError('Sealed test stat changed')
    for name in ('implementation_publication.json', 'cpu_tests.json'):
        receipt = P.read(P.OUT / name)
        if not receipt.get('verified', receipt.get('passed', False)) or receipt['code_sha256'] != frozen['code_sha256']:
            raise RuntimeError('Exact tested/published v2 source required')
    return frozen


def argv(record, out, arm='baseline', shared=None, *, probe=False, server=False, gpu=None):
    from code_rebench_qwen import bootstrap as B
    args = B.argv(record['job'], out)
    position = args.index('--chdir'); mounts = []
    for name in ('code_qwen3_rr4_v2', 'code_qwen3_rr4', 'code_v5', 'code_v6', 'code_rebench_qwen_repair'):
        path = P.ROOT / name; mounts += ['--ro-bind', str(path), str(path)]
    paths = [P.OUT / 'deployment.json']
    if server:
        paths += [P.JUDGE_MODEL, P.CHECKPOINT / 'adapter_model.safetensors', P.CHECKPOINT / 'adapter_config.json']
        mounts += ['--dev-bind', '/dev', '/dev', '--bind', str(P.TRANSPORT), str(P.TRANSPORT)]
    else:
        paths += [Path(record['cache']), P.ROOT / 'models_v5/Qwen3-Reranker-0.6B', P.LEGACY_TOKENIZER]
        if shared:
            paths.append(shared)
        if arm == 'hybrid_safe':
            mounts += ['--ro-bind', str(P.TRANSPORT), str(P.TRANSPORT)]
    for path in paths:
        mounts += ['--ro-bind', str(path), str(path)]
    args[position:position] = mounts
    args[args.index('code_rebench_qwen.bootstrap')] = 'code_qwen3_rr4_v2.service' if server else 'code_qwen3_rr4_v2.worker'
    if not server:
        args += ['--arm', arm, '--cache', record['cache'], '--cache-sha', record['cache_sha256']]
        if shared:
            args += ['--shared', str(shared)]
        if probe:
            args += ['--probe']
    env = B.environment(out)
    env['CUDA_VISIBLE_DEVICES'] = str(gpu) if server else ''
    return args, env


def one(record, arm, publish, state, shared=None):
    out = P.OUT / 'run' / arm / record['instance_id']
    if (out / 'started.json').exists() or (out / 'result.json').exists():
        raise FileExistsError('No model replay or result overwrite')
    P.write(out / 'started.json', {'utc': now(), 'arm': arm}, immutable=True)
    command, env = argv(record, out, arm, shared)
    with (out / 'controller_process.log').open('x') as stream:
        process = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 3600
        state['worker_pid'] = process.pid; publish()
        while process.poll() is None:
            publish()
            if time.monotonic() >= deadline:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=30)
                raise TimeoutError('Frozen one-hour arm deadline')
            time.sleep(2)
    if process.returncode or not (out / 'result.json').exists():
        raise RuntimeError('Isolated arm failed: ' + str(out))
    result = P.read(out / 'result.json')
    if result['status'] != 'complete':
        raise RuntimeError('Model arm incomplete; preserve failure')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait-hours', type=float, default=24)
    args = parser.parse_args()
    if not 0 < args.wait_hours <= 48:
        raise ValueError('Wait deadline must be 0–48 hours')
    P.configure(); verify()
    lock = (P.OUT / 'controller.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (P.OUT / 'execution_started.json').exists():
        raise FileExistsError('No implicit controller replay')
    P.write(P.OUT / 'execution_started.json', {'utc': now(), 'pid': os.getpid()}, immutable=True)
    state = {'stage': 'WAITING_FOR_TWO_IDLE_GPUS', 'pid': os.getpid(), 'completed_pairs': 0,
             'physical_gpu_limit': 2, 'model_calls_started': False}
    def publish():
        state['utc'] = now(); P.write(P.OUT / 'controller_status.json', state)
    from .deployment import adapt, stop_owned
    from . import report
    D = adapt(); service_started = False; scorer_process = None; scorer_stream = None
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
        probe_out = P.OUT / 'run/isolation_probe'
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
        judge_out = P.OUT / 'run/judge_service'
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
        state.update(stage='RUNNING_CANARY', model_calls_started=True); publish()
        for item in records:
            iid = item['instance_id']; state.update(active_issue=iid, active_arm='baseline'); publish()
            baseline = one(item, 'baseline', publish, state)
            shared = P.OUT / 'shared' / (iid + '.json')
            P.write(shared, {'instance_id': iid, 'base_commit': item['base_commit'],
                  'files': baseline['file_rank_after_reflection'], 'raw_file_responses': baseline['raw_file_responses'],
                  'baseline_result_sha256': P.sha(P.OUT / 'run/baseline' / iid / 'result.json')}, immutable=True)
            state['active_arm'] = 'hybrid_safe'; publish()
            one(item, 'hybrid_safe', publish, state, shared)
            assessment = report.create(); state['completed_pairs'] = assessment['all_targets']['n']; publish()
            deltas = [group['delta'] for group in assessment.values()]
            if any(delta is not None and delta < -.03 - 1e-12 for delta in deltas):
                state.update(stage='STOP_LOSS', stop_issue=iid); publish(); break
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
        P.write(P.OUT / 'shutdown.json', cleanup)
        publish(); report.create()


if __name__ == '__main__':
    main()
