#!/usr/bin/env python3
"""Own only this experiment's local Qwen service; never reset a GPU."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request

COSIL = Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL')
OLD = COSIL / 'results/sfpruner300_20261114/service_queue_sparejudge'


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, p)


def proc(pid):
    p = Path('/proc') / str(pid)
    try:
        stat = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'uid': p.stat().st_uid, 'start_ticks': int(stat[19]),
                'cmd': (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode(),
                'pgid': os.getpgid(pid)}
    except (OSError, ValueError, IndexError):
        return None


def gpu_sample(gpus):
    raw = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,memory.free,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
    rows = {}
    for line in raw.splitlines():
        a = [x.strip() for x in line.split(',')]
        if int(a[0]) in gpus:
            rows[int(a[0])] = {'index': int(a[0]), 'uuid': a[1], 'free_mib': int(a[2]), 'used_mib': int(a[3]), 'utilization': int(a[4]), 'processes': []}
    apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_memory', '--format=csv,noheader,nounits'], text=True)
    for line in apps.splitlines():
        a = [x.strip() for x in line.split(',')]
        if len(a) < 2: continue
        for r in rows.values():
            if a[0] == r['uuid']:
                r['processes'].append({'pid': int(a[1]), 'proc': proc(int(a[1])), 'reported_mib': a[2]})
    assert len(rows) == len(gpus), 'GPU inventory mismatch'
    return list(rows.values())


def start(args):
    service = args.run_dir / 'service'
    service.mkdir(parents=True, exist_ok=True)
    ownership = service / 'ownership.json'
    if ownership.exists():
        old = json.loads(ownership.read_text())
        current = proc(old['pid'])
        if current and current['start_ticks'] == old['start_ticks']:
            raise RuntimeError('Experiment service is already running')
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', args.port)) == 0:
            raise RuntimeError('Requested port is already occupied')
    observations = []
    start_time = time.monotonic()
    while True:
        sample = gpu_sample(args.gpus)
        observations.append({'time': time.time(), 'gpus': sample})
        write(service / 'idle_check.json', observations)
        for row in sample:
            assert row['free_mib'] >= 23000 and row['utilization'] == 0, 'Selected GPU is no longer idle'
            assert not any(p['proc'] for p in row['processes']), 'Visible compute process on selected GPU'
        if time.monotonic() - start_time >= args.idle_seconds: break
        time.sleep(min(10, args.idle_seconds - (time.monotonic() - start_time)))
    plan = json.loads((OLD / 'plan.json').read_text())
    command = plan['main_command'][:]
    command[command.index('--port') + 1] = str(args.port)
    command[command.index('--max-num-seqs') + 1] = '2'
    command += ['--enable-auto-tool-choice', '--tool-call-parser', 'hermes']
    assert Path(command[0]).exists() and Path(command[command.index('--model') + 1]).exists()
    old_env = json.loads((OLD / 'sessions/20261115T025232Z_d73096c9662e/runtime_environment.json').read_text())
    env = {k: v for k, v in os.environ.items() if k in ('HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'TZ', 'LD_LIBRARY_PATH')}
    env.update(old_env)
    env.pop('PYTHONPATH', None)
    env['CUDA_VISIBLE_DEVICES'] = ','.join(map(str, args.gpus))
    for key, suffix in {'HF_HOME':'hf_cache', 'HF_HUB_CACHE':'hf_cache/hub', 'TORCH_HOME':'torch_home', 'XDG_CACHE_HOME':'xdg_cache', 'VLLM_CACHE_ROOT':'vllm_cache', 'FLASHINFER_WORKSPACE_BASE':'flashinfer', 'TRITON_CACHE_DIR':'triton_cache', 'CUDA_CACHE_PATH':'cuda_cache', 'TORCH_EXTENSIONS_DIR':'torch_extensions', 'TORCHINDUCTOR_CACHE_DIR':'torch_cache'}.items():
        env[key] = str(service / suffix)
    tmpdir = Path(f'/tmp/locagent_{os.getuid()}_{args.port}')
    tmpdir.mkdir(exist_ok=True)
    env['TMPDIR'] = env['VLLM_RPC_BASE_PATH'] = str(tmpdir)
    write(service / 'launch.json', {'command': command, 'environment': env, 'gpus': args.gpus, 'idle_seconds': args.idle_seconds, 'paid_api': False})
    with (service / 'vllm.log').open('ab', buffering=0) as log:
        p = subprocess.Popen(command, env=env, cwd=service, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    identity = proc(p.pid)
    assert identity and identity['uid'] == os.getuid()
    write(ownership, {**identity, 'launch_time': time.time(), 'port': args.port, 'gpus': args.gpus})
    print(json.dumps({'status': 'STARTING', 'pid': p.pid, 'port': args.port}), flush=True)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if p.poll() is not None:
            raise RuntimeError(f'vLLM exited {p.returncode}; see {service / "vllm.log"}')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/v1/models', timeout=2) as r:
                models = json.load(r)
            write(service / 'ready.json', {'time': time.time(), 'pid': p.pid, 'models': models})
            print(json.dumps({'status': 'READY', 'pid': p.pid, 'port': args.port}), flush=True)
            return
        except (OSError, ValueError):
            time.sleep(5)
    raise TimeoutError('vLLM startup timeout; process retained for diagnosis')


def stop(args):
    service = args.run_dir / 'service'
    owner = json.loads((service / 'ownership.json').read_text())
    identity = proc(owner['pid'])
    if identity is None:
        print('Service parent already exited; no unrelated process signalled')
        return
    assert identity['uid'] == os.getuid() == owner['uid']
    assert identity['start_ticks'] == owner['start_ticks'] and identity['cmd'] == owner['cmd']
    assert identity['pgid'] == owner['pid'], 'Unexpected process group'
    os.killpg(owner['pid'], signal.SIGTERM)
    for _ in range(40):
        current = proc(owner['pid'])
        if not current or current['start_ticks'] != owner['start_ticks']: break
        time.sleep(0.5)
    write(service / 'shutdown.json', {'time': time.time(), 'signal': 'SIGTERM', 'parent_still_present': proc(owner['pid']) is not None, 'gpus': gpu_sample(owner['gpus'])})
    print('Owned service shutdown requested; no GPU reset or foreign signal used')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=7353)
    parser.add_argument('--gpus', type=lambda x: list(map(int, x.split(','))), default=[1, 3])
    parser.add_argument('--idle-seconds', type=int, default=90)
    args = parser.parse_args()
    (start if args.action == 'start' else stop)(args)
