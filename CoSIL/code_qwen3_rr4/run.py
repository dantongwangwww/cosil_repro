"""Durable CPU controller; waits for three genuinely idle cards, never preempts."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
from datetime import datetime, timezone
from . import config as P


def now():
    return datetime.now(timezone.utc).isoformat()


def inventory():
    raw = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,memory.free,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
    apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'], text=True)
    busy = {line.split(',')[0].strip() for line in apps.splitlines() if line.strip()}
    rows = []
    for line in raw.splitlines():
        idx, uuid, free, util = (x.strip() for x in line.split(','))
        rows.append({'index': int(idx), 'uuid': uuid, 'free_mib': int(free), 'utilization': int(util), 'has_compute_process': uuid in busy})
    return rows


def eligible(rows):
    return [r['index'] for r in rows if not r['has_compute_process'] and r['free_mib'] >= 23000 and r['utilization'] == 0]


def verify():
    frozen = P.read(P.OUT/'freeze.json')
    for group in ('code_sha256', 'input_sha256', 'protected_sha256'):
        for path, expected in frozen[group].items():
            if P.sha(path) != expected:
                raise RuntimeError('Frozen source/input changed: '+path)
    if P.sha(P.OUT/'deployment.json') != frozen['deployment_sha256']:
        raise RuntimeError('Deployment parameters changed')
    from code_v6.common import test_stats
    if test_stats() != frozen['test_stat_only']:
        raise RuntimeError('Sealed test stat changed')
    publication = P.read(P.OUT/'implementation_publication.json')
    if not publication.get('verified') or publication['code_sha256'] != frozen['code_sha256']:
        raise RuntimeError('Exact tested/published code required')
    tests = P.read(P.OUT/'cpu_tests.json')
    if not tests.get('passed') or tests['code_sha256'] != frozen['code_sha256']:
        raise RuntimeError('Exact passing CPU tests required')
    return frozen


def worker_argv(job_path, out, arm, judge_gpu, *, shared=None, probe=False):
    from code_rebench_qwen import bootstrap as B
    args = B.argv(job_path, out)
    position = args.index('--chdir')
    mounts = []
    for name in ('code_qwen3_rr4', 'code_v5', 'code_v6', 'code_rebench_qwen_repair'):
        path = P.ROOT/name; mounts += ['--ro-bind', str(path), str(path)]
    paths = [P.OUT/'deployment.json', P.JUDGE_MODEL, P.ROOT/'models_v5/Qwen3-Reranker-0.6B',
             Path('/home/wdt/models/qwen25coder7b').resolve(),
             P.CHECKPOINT/'adapter_model.safetensors', P.CHECKPOINT/'adapter_config.json']
    if shared is not None:
        paths.append(shared)
    for path in paths:
        mounts += ['--ro-bind', str(path), str(path)]
    if arm == 'hybrid_safe' and not probe:
        mounts += ['--dev-bind', '/dev', '/dev']
    args[position:position] = mounts
    args[args.index('code_rebench_qwen.bootstrap')] = 'code_qwen3_rr4.worker'
    args += ['--arm', arm]
    if shared is not None:
        args += ['--shared', str(shared)]
    if probe:
        args += ['--probe']
    env = B.environment(out)
    env['CUDA_VISIBLE_DEVICES'] = str(judge_gpu) if arm == 'hybrid_safe' and not probe else ''
    return args, env


def one(record, arm, judge_gpu, shared=None):
    out = P.OUT/'run'/arm/record['instance_id']
    result_path = out/'result.json'
    if result_path.exists():
        return P.read(result_path)
    if (out/'started.json').exists():
        raise RuntimeError('Interrupted arm is immutable; no automatic model replay')
    out.mkdir(parents=True, exist_ok=True)
    P.write(out/'started.json', {'utc': now(), 'pid': os.getpid(), 'arm': arm}, immutable=True)
    args, env = worker_argv(record['job'], out, arm, judge_gpu, shared=shared)
    with (out/'controller_process.log').open('x') as stream:
        process = subprocess.Popen(args, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic()+3600
        while process.poll() is None:
            state = P.read(P.OUT/'controller_status.json')
            state.update(utc=now(), worker_pid=process.pid)
            P.write(P.OUT/'controller_status.json', state)
            if time.monotonic() >= deadline:
                # Popen owns this live independent session; never select arbitrary GPU PIDs.
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=30)
                raise TimeoutError('Isolated arm exceeded frozen1h deadline')
            time.sleep(10)
    if process.returncode or not result_path.exists():
        raise RuntimeError('Isolated arm process failed; inspect '+str(out))
    result = P.read(result_path)
    if result['status'] != 'complete':
        raise RuntimeError('Arm failed; keep original failure: '+record['instance_id']+'/'+arm)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait-hours', type=float, default=24.)
    args = parser.parse_args()
    if not 0 < args.wait_hours <= 48:
        raise ValueError('Positive wait deadline up to48h required')
    P.configure(); frozen = verify()
    lock = (P.OUT/'controller.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (P.OUT/'execution_started.json').exists():
        raise FileExistsError('No implicit controller restart/replay')
    P.write(P.OUT/'execution_started.json', {'utc': now(), 'pid': os.getpid()}, immutable=True)
    state = {'stage': 'WAITING_FOR_THREE_IDLE_GPUS', 'pid': os.getpid(), 'model_calls_started': False, 'completed_pairs': 0}
    service_started = False
    from .deployment import adapt
    D = adapt()
    from . import report
    def publish():
        state['utc'] = now(); P.write(P.OUT/'controller_status.json', state)
    try:
        publish(); report.create()
        deadline = time.monotonic()+args.wait_hours*3600; quiet = None; selected = None
        while True:
            rows = inventory(); free = eligible(rows)
            state['gpu_observation'] = rows
            chosen = tuple(free[:3]) if len(free) >= 3 else None
            quiet = (quiet or time.monotonic()) if chosen is not None and chosen == selected else (time.monotonic() if chosen else None)
            selected = chosen
            state['continuous_idle_seconds'] = time.monotonic()-quiet if quiet else 0
            publish()
            if quiet and time.monotonic()-quiet >= 90:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('No three-card idle window within frozen wait deadline')
            time.sleep(30)
        verify()
        records = P.read(P.OUT/'inputs/manifest.json')['records']
        probe_out = P.OUT/'run/isolation_probe'
        command, env = worker_argv(records[0]['job'], probe_out, 'baseline', selected[2], probe=True)
        done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        P.write(probe_out/'controller.json', {'returncode': done.returncode, 'stdout': done.stdout, 'stderr': done.stderr})
        if done.returncode or not P.read(probe_out/'probe.json')['passed']:
            raise RuntimeError('Filesystem isolation probe failed')
        D.GPUS = selected[:2]
        state.update(stage='LOADING_OWNED_QWEN3', selected_gpus=selected); publish()
        # A start failure may occur after Popen/ownership was written. Preserve
        # that ownership and still clean up the exact new session in finally.
        try:
            D.start(execute=True)
        finally:
            service_started = (D.SERVICE/'ownership.json').exists()
        ready = time.monotonic()+900
        while True:
            try:
                D.health(synthetic=True); break
            except Exception:
                if time.monotonic() >= ready:
                    raise TimeoutError('Owned Qwen3 readiness exceeded15min')
                time.sleep(5)
        state.update(stage='RUNNING_CANARY', model_calls_started=True); publish()
        for record in records:
            iid = record['instance_id']; state.update(active_issue=iid, active_arm='baseline'); publish()
            off = one(record, 'baseline', selected[2])
            shared = P.OUT/'shared'/f'{iid}.json'
            P.write(shared, {'instance_id': iid, 'base_commit': record['base_commit'],
                'files': off['file_rank_after_reflection'], 'raw_file_responses': off['raw_file_responses'],
                'baseline_result_sha256': P.sha(P.OUT/'run/baseline'/iid/'result.json')}, immutable=True)
            state.update(active_arm='hybrid_safe'); publish()
            one(record, 'hybrid_safe', selected[2], shared)
            assessment = report.create(); state['completed_pairs'] = assessment['n']; publish()
            if assessment['delta'] < -.03-1e-12:
                state.update(stage='STOP_LOSS', stop_issue=iid); publish(); break
        else:
            state.update(stage='COMPLETE'); publish()
    except BaseException as error:
        state.update(stage='FAILED', error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc()); publish()
        raise
    finally:
        if service_started:
            state['shutdown'] = D.stop(execute=True)
        publish(); report.create()


if __name__ == '__main__':
    main()
