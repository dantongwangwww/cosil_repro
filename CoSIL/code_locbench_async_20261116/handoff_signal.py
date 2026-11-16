"""Stdlib-only pidfd handoff, executed by the system Python3.12.

Only the exact old top monitor may receive a signal. Never killpg, never signal
the GPU queue, models or workers, and never fall back to an unbound PID signal.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal


def identity(pid):
    p = Path('/proc') / str(pid)
    try:
        text = (p / 'stat').read_text()
        f = text[text.rfind(')') + 2:].split()
        raw = (p / 'cmdline').read_bytes()
        return {'pid': int(pid), 'uid': p.stat().st_uid, 'state': f[0], 'pgid': int(f[2]),
            'sid': int(f[3]), 'start_ticks': int(f[19]),
            'cmdline_sha256': hashlib.sha256(raw).hexdigest(),
            'argv': raw.rstrip(b'\0').decode().split('\0'), 'cwd': str((p / 'cwd').resolve(strict=True))}
    except (OSError, ValueError):
        return None


def expected(receipt, root, observed):
    saved = receipt['identity']; command = receipt['command']
    try:
        family = (command[command.index('-m') + 1] == 'code_locbench_full_20261116.supervise'
            and '--prepare-only' not in command
            and Path(command[command.index('--root') + 1]).resolve() == Path(root).resolve())
    except (ValueError, IndexError):
        return False
    return bool(family and observed and observed['state'] != 'Z'
        and saved['uid'] == os.getuid() and saved['pgid'] == saved['pid'] == saved['sid']
        and receipt['cwd'] == str(Path(__file__).resolve().parents[1])
        and all(saved[k] == observed[k] for k in
            ('pid', 'uid', 'pgid', 'sid', 'start_ticks', 'cmdline_sha256'))
        and observed['argv'] == command and observed['cwd'] == receipt['cwd'])


def stop_monitor(receipt, root, *, observe=identity, opener=None, sender=None, closer=os.close):
    opener = opener or getattr(os, 'pidfd_open', None)
    sender = sender or getattr(signal, 'pidfd_send_signal', None)
    if opener is None or sender is None:
        raise RuntimeError('Use system Python3.12 with pidfd support; no PID fallback')
    pid = receipt['identity']['pid']; observed = observe(pid)
    if observed is None or observed['state'] == 'Z':
        return {'status': 'ALREADY_EXITED', 'signal_sent': False, 'pid': pid}
    if not expected(receipt, root, observed):
        raise RuntimeError('Exact top-monitor identity check failed; no signal')
    fd = opener(pid, 0)
    try:
        if not expected(receipt, root, observe(pid)):
            raise RuntimeError('Monitor identity changed after opening pidfd')
        sender(fd, signal.SIGKILL, None, 0)
    finally:
        closer(fd)
    return {'status': 'EXACT_MONITOR_PIDFD_SIGNALED', 'signal_sent': True,
        'pid': pid, 'pidfd_bound': True, 'killpg_used': False,
        'queue_model_worker_signals': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt', type=Path, required=True); p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(stop_monitor(json.loads(a.receipt.read_text()), a.root)))


if __name__ == '__main__':
    main()
