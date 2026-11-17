"""Owned-process adoption and byte-preserving interrupted-report recovery.

Unknown exit status is explicitly UNKNOWN_EXIT, never successful execution.
This module neither launches services automatically nor changes model methods.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
import subprocess
import time
import uuid

from code_sfpruner300_20261114 import controller as c, service_queue as sq

UNKNOWN_EXIT = -255


class ProcessRef:
    def __init__(self, process=None, receipt=None, *, adopted=False, observe=None):
        if receipt is None or (process is None and not adopted):
            raise ValueError('A process or explicitly adopted saved identity is required')
        self.process, self.receipt, self.adopted = process, receipt, adopted
        self.pid = receipt['identity']['pid']
        self._observe = observe or sq.identity
        self._adopted_returncode = None

    def poll(self):
        if not self.adopted:
            return self.process.poll()
        if self._adopted_returncode is not None:
            return self._adopted_returncode
        observed = self._observe(self.pid)
        if not sq.owned(self.receipt['identity'], observed,
                        self.receipt['command'], self.receipt['cwd']):
            self._adopted_returncode = UNKNOWN_EXIT
        return self._adopted_returncode

    @property
    def returncode(self):
        return self.poll()

    def wait(self, timeout=None):
        if not self.adopted:
            return self.process.wait(timeout=timeout)
        deadline = None if timeout is None else time.monotonic()+timeout
        while True:
            result = self.poll()
            if result is not None:
                return result
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(self.receipt['command'], timeout)
            time.sleep(.05)


def _unique():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+uuid.uuid4().hex[:12]


def start_or_adopt(command, cwd, env, ownership_path, logbase, *, allow_adopt=True):
    """Return (ProcessRef, receipt); never signal or adopt an unknown live PID."""
    command = list(map(str, command)); cwd = str(Path(cwd).resolve())
    ownership_path, logbase = Path(ownership_path), Path(logbase)
    if ownership_path.is_symlink() or logbase.is_symlink():
        raise ValueError('Symlink process ownership/log destination forbidden')
    ownership_path.parent.mkdir(parents=True, exist_ok=True)
    logbase.parent.mkdir(parents=True, exist_ok=True)
    with c.lock_output(ownership_path.with_name(ownership_path.name+'.launch_lock')):
        previous = None
        if ownership_path.exists():
            previous = c.read(ownership_path)
            if previous.get('command') != command or previous.get('cwd') != cwd:
                raise ValueError('Saved process command/cwd differs; refusing reuse')
            observed = sq.identity(previous['identity']['pid'])
            if observed is not None and observed.get('state') != 'Z':
                if not sq.owned(previous['identity'], observed, command, cwd):
                    raise RuntimeError('Unknown/reused live PID; never adopt, signal or duplicate')
                if not allow_adopt:
                    raise RuntimeError('An exactly owned process is already alive; adoption disabled')
                return ProcessRef(receipt=previous, adopted=True), previous
        attempt = _unique()
        history = ownership_path.parent/(ownership_path.stem+'.attempts')/attempt
        history.mkdir(parents=True, exist_ok=False)
        if previous is not None:
            c.write(history/'previous_pointer.json', previous, immutable=True)
        log = logbase.with_name(logbase.name+'.attempt_'+attempt+'.log')
        with log.open('xb') as output:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        # Witness a stable post-exec argv/cwd rather than a transient /proc view.
        saved = sq.identity(process.pid)
        deadline = time.monotonic()+3
        while saved is not None and time.monotonic() < deadline:
            if not sq.owned(saved, saved, command, cwd):
                break
            time.sleep(.01)
            confirmed = sq.identity(process.pid)
            if sq.owned(saved, confirmed, command, cwd):
                saved = confirmed
                break
            saved = confirmed
        if saved is None or not sq.owned(saved, saved, command, cwd):
            failure = {'pid':process.pid, 'command':command, 'cwd':cwd,
                'log':str(log.resolve()), 'observed_identity':saved,
                'actual_exit_code_if_known':process.poll(), 'signals_sent':False}
            c.write(history/'unwitnessed_launch.json',failure,immutable=True)
            raise RuntimeError('New CPU/queue process identity could not be witnessed; inspect preserved log')
        receipt = {'identity':saved, 'command':command, 'cwd':cwd,
            'attempt':attempt, 'log':str(log.resolve()), 'started_utc':time.time(),
            'history_receipt':str((history/'ownership.json').resolve()),
            'previous_pointer_sha256':c.sha(history/'previous_pointer.json') if previous else None}
        c.write(history/'ownership.json',receipt,immutable=True)
        c.write(ownership_path,receipt)
        return ProcessRef(process,receipt), receipt


def stop_saved(receipt, **kwargs):
    """Only original exact argv/cwd/UID/session ownership may receive SIGTERM."""
    if isinstance(receipt, (str, Path)):
        receipt = c.read(receipt)
    return sq.stop_owned(receipt, **kwargs)


def preserve_partial_output(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Symlink output directory forbidden')
    if not path.exists():
        return {'status':'ABSENT','preserved':False,'path':str(path)}
    if not path.is_dir():
        raise ValueError('Report output must be a directory')
    manifest = path/'output_sha256.json'
    if manifest.exists():
        return {'status':'COMPLETE_MANIFEST_PRESENT','preserved':False,
            'path':str(path),'manifest_sha256':c.sha(manifest)}
    hashes = {}
    for file in sorted(path.rglob('*')):
        if file.is_symlink():
            raise ValueError('Symlink in interrupted output forbidden')
        if file.is_file():
            hashes[str(file.relative_to(path))]=c.sha(file)
    destination = path.with_name(path.name+'.preserved_interrupted_'+_unique())
    path.rename(destination)
    receipt = {'status':'PRESERVED_INTERRUPTED_OUTPUT','preserved':True,
        'original_path':str(path.resolve()),'preserved_path':str(destination.resolve()),
        'files_sha256':hashes,'deleted':False,'original_bytes_preserved':True}
    mismatches = [name for name,wanted in hashes.items() if c.sha(destination/name)!=wanted]
    receipt['original_bytes_preserved'] = not mismatches
    receipt['changed_during_preservation'] = mismatches
    receipt_path = destination.with_name(destination.name+'.preservation.json')
    c.write(receipt_path,receipt,immutable=True)
    receipt['receipt_path']=str(receipt_path.resolve())
    if mismatches:
        raise RuntimeError('Output changed during preservation; bytes retained for review')
    return receipt
