"""Same two-card model profile, with PID-reuse-safe graceful shutdown polling."""
import os
from pathlib import Path
import signal
import time
from . import config as P


def stable_identity(pid):
    proc = Path('/proc') / str(pid)
    text = (proc / 'stat').read_text()
    fields = text[text.rfind(')') + 2:].split()
    return {'pid': int(pid), 'uid': proc.stat().st_uid, 'state': fields[0],
            'process_group': int(fields[2]), 'session_id': int(fields[3]), 'start_ticks': int(fields[19])}


def stop_owned(D, wait_seconds=40):
    owner = P.read(D.SERVICE / 'ownership.json')
    saved = owner['identity']
    try:
        current = D.identity(saved['pid'])
    except (FileNotFoundError, ProcessLookupError):
        receipt = {'leader_exited': True, 'signal_sent': False, 'other_processes_signalled': False}
        P.write(D.SERVICE / 'stop.json', receipt)
        return receipt
    # Full executable/cwd identity is checked BEFORE any signal.
    D.assert_identity(saved, current)
    os.killpg(saved['process_group'], signal.SIGTERM)
    deadline = time.monotonic() + wait_seconds
    exited = False
    while time.monotonic() < deadline:
        try:
            current = stable_identity(saved['pid'])
        except (FileNotFoundError, ProcessLookupError):
            exited = True; break
        if current['state'] == 'Z' or current['start_ticks'] != saved['start_ticks']:
            # Reused PID belongs to someone else; never send it another signal.
            exited = True; break
        if any(current[k] != saved[k] for k in ('pid', 'uid', 'process_group', 'session_id')):
            raise RuntimeError('Stable process ownership changed after SIGTERM')
        time.sleep(.5)
    receipt = {'leader_exited': exited, 'signal_sent': 'SIGTERM', 'forced_kill': False,
               'other_processes_signalled': False}
    P.write(D.SERVICE / 'stop.json', receipt)
    if not exited:
        raise RuntimeError('Owned service did not exit within deadline')
    return receipt


def adapt():
    P.configure()
    from code_rebench_qwen import deploy as D
    if getattr(D, '_rr4_v2_profile', None) == str(P.OUT):
        return D
    original_command, original_environment = D.command, D.cache_environment

    def command():
        args = original_command()
        args[args.index('--gpu-memory-utilization') + 1] = '0.59'
        args[args.index('--max-num-seqs') + 1] = '1'
        return args

    def environment():
        value = original_environment()
        short = Path('/tmp/rr4v2_ipc1110')
        short.mkdir(parents=True, exist_ok=True, mode=0o700)
        value.update(TMPDIR=str(short), VLLM_RPC_BASE_PATH=str(short))
        return value

    def verify_model():
        if not P.MODEL.is_dir() or P.MODEL.is_symlink():
            raise ValueError('Pinned model must be a real directory')
        files = {name: D.verify_file(P.MODEL / name, size, digest)
                 for name, (size, digest) in D.FILES.items()}
        receipt = {'model_id': 'Qwen/Qwen3-8B', 'revision': D.REVISION, 'files': files,
                   'total_bytes': sum(v['bytes'] for v in files.values())}
        P.write(P.OUT / 'model_files.json', receipt, immutable=True)
        return receipt

    D.command, D.cache_environment, D.verify_model = command, environment, verify_model
    D._rr4_v2_profile = str(P.OUT)
    return D
