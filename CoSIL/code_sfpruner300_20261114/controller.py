"""Durable controller around the frozen SFPruner paired worker.

This module never selects tasks, starts a model service, changes model settings,
or opens evaluation assets. The CLI runs only real frozen workers. Test backends
are available through dependency injection and are marked as simulations.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'papers/SFPruner'
sys.path.insert(0, str(BUNDLE))
from specprune.runtime_helpers import load_job, validate_clean_job

ARMS = ('baseline', 'hybrid_safe')
RECORD_KEYS = {'instance_id', 'repo', 'base_commit', 'job', 'job_sha256',
               'source', 'source_id', 'revision', 'source_revision',
               'source_sha256', 'source_files', 'source_bytes'}
TERMINAL = {'complete', 'worker_failed', 'controller_failed', 'interrupted',
            'timed_out', 'dependency_blocked'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                   allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value, *, immutable=False):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refuse symlink output: ' + str(path))
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if path.exists() and immutable:
        if path.read_text(encoding='utf-8') != data:
            raise ValueError('Immutable artifact changed: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if immutable:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def current_process(pid):
    """No command text is exported; start ticks detect PID reuse."""
    proc = Path('/proc') / str(pid)
    try:
        raw = (proc / 'stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        return {'pid': int(pid), 'uid': proc.stat().st_uid, 'state': fields[0],
                'pgid': int(fields[2]), 'sid': int(fields[3]),
                'start_ticks': int(fields[19]),
                'cmdline_sha256': hashlib.sha256((proc / 'cmdline').read_bytes()).hexdigest()}
    except (FileNotFoundError, ProcessLookupError):
        return None


def same_process(saved, observed):
    return bool(observed and observed['state'] != 'Z' and all(
        saved.get(key) == observed.get(key)
        for key in ('pid', 'uid', 'pgid', 'sid', 'start_ticks', 'cmdline_sha256')))


def signal_owned(saved, *, observe=current_process, send=os.killpg):
    """Signal only an exact saved leader of its own independent session."""
    observed = observe(saved['pid'])
    if not same_process(saved, observed):
        return {'signal_sent': False, 'reason': 'gone_or_identity_mismatch'}
    if saved['pgid'] != saved['pid'] or saved['sid'] != saved['pid'] or saved['uid'] != os.getuid():
        return {'signal_sent': False, 'reason': 'not_owned_independent_session'}
    send(saved['pgid'], signal.SIGTERM)
    return {'signal_sent': 'SIGTERM', 'forced_kill': False}


@contextmanager
def lock_output(out):
    out = Path(out)
    if out.is_symlink():
        raise ValueError('Output root cannot be a symlink')
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'controller.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def load_manifest(path):
    path = Path(path).resolve(strict=True)
    value = read(path)
    if not isinstance(value.get('records'), list) or value.get('n') != len(value['records']):
        raise ValueError('Manifest requires n and records with exact cardinality')
    records, seen = [], set()
    for supplied in value['records']:
        if set(supplied) - RECORD_KEYS:
            raise ValueError('Unknown/private manifest record fields')
        if not {'instance_id', 'repo', 'base_commit', 'job', 'job_sha256'} <= set(supplied):
            raise ValueError('Manifest record lacks public identity or job SHA')
        relative = Path(supplied['job'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Manifest job must be a contained relative path')
        job_path = (path.parent / relative).resolve(strict=True)
        if not job_path.is_relative_to(path.parent):
            raise ValueError('Manifest job escaped input root')
        if sha(job_path) != supplied['job_sha256']:
            raise ValueError('Manifest job SHA changed')
        job = load_job(job_path)
        for key in ('instance_id', 'repo', 'base_commit'):
            if supplied[key] != job[key]:
                raise ValueError('Manifest/job identity mismatch: ' + key)
        if job['instance_id'] in seen:
            raise ValueError('Duplicate issue ID')
        seen.add(job['instance_id'])
        # Evaluation outcomes and selection criteria are never consulted.
        records.append({**supplied, 'job_path': str(job_path)})
    if not records:
        raise ValueError('An empty manifest is not runnable')
    return path, records


def source_receipt(job_path):
    job = load_job(job_path)
    snapshot = Path(job['snapshot'])
    if not snapshot.is_dir():
        raise ValueError('Missing clean base snapshot')
    index = read(job['code_index'])
    actual = set()
    for path in snapshot.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in base snapshot')
        if path.is_file():
            relative = path.relative_to(snapshot).as_posix()
            if not relative.endswith('.py'):
                raise ValueError('Only base Python source is allowed in model snapshot')
            actual.add(relative)
    if actual != set(index):
        raise ValueError('Snapshot and complete index differ')
    for relative, entry in index.items():
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Unsafe indexed source path')
        if sha(snapshot / relative) != entry['raw_sha256']:
            raise ValueError('Base source bytes changed: ' + relative)
    return {'job_sha256': sha(job_path), 'base_commit': job['base_commit'],
            'snapshot': str(snapshot), 'index_sha256': sha(job['code_index']),
            'structure_sha256': sha(job['structure']),
            'source_sha256': digest({key: index[key]['raw_sha256'] for key in sorted(index)})}


class FrozenBackend:
    simulation = False

    def protocol(self):
        files = {str(p.relative_to(BUNDLE)): sha(p) for p in (BUNDLE / 'specprune').glob('*.py')}
        vendor = read(BUNDLE / 'vendor/SOURCE_MANIFEST.json')
        for item in vendor['files']:
            if sha(BUNDLE / 'vendor' / item['path']) != item['sha256']:
                raise ValueError('Frozen vendor source changed: ' + item['path'])
        for name in ('configs/runtime.json', 'configs/deployment.json', 'vendor/SOURCE_MANIFEST.json',
                     'provenance/main_model_files.json'):
            files[name] = sha(BUNDLE / name)
        runtime = read(BUNDLE / 'configs/runtime.json')
        if runtime['context_limit'] != 65536 or runtime['output_tokens'] != 2048 or runtime['main_model_dtype'] != 'bfloat16':
            raise ValueError('Unexpected frozen execution profile')
        return {'files_sha256': files, 'runtime': runtime,
                'deployment': read(BUNDLE / 'configs/deployment.json')}

    def stage(self, job_path, destination):
        from specprune.runner import stage_inputs
        return stage_inputs(job_path, destination)

    def check_services(self, model_dir, judge_socket, out):
        if not Path(judge_socket).is_socket():
            raise RuntimeError('Start the frozen resident judge service before --run')
        from specprune.model_ops import verify_base_model
        pin = read(BUNDLE / 'provenance/main_model_files.json')
        verified = verify_base_model(model_dir, pin['files_sha256'])
        # A worker only needs the pinned tokenizer, never a broad model directory.
        tokenizer = Path(out) / '_main_tokenizer'
        tokenizer.mkdir(exist_ok=True)
        permitted = {name: h for name, h in pin['files_sha256'].items()
                     if not name.endswith('.safetensors') and name != 'model.safetensors.index.json'}
        if {p.name for p in tokenizer.iterdir()} - set(permitted):
            raise ValueError('Unexpected content in tokenizer mount')
        for name, expected in permitted.items():
            dest = tokenizer / name
            if not dest.exists():
                with dest.open('xb') as stream:
                    stream.write((Path(model_dir) / name).read_bytes())
            if dest.is_symlink() or sha(dest) != expected:
                raise ValueError('Frozen tokenizer changed')
        connection = http.client.HTTPConnection('127.0.0.1', 7343, timeout=5)
        try:
            connection.request('GET', '/v1/models')
            response = connection.getresponse()
            raw = response.read(1024 * 1024 + 1)
            if response.status != 200 or len(raw) > 1024 * 1024:
                raise RuntimeError('Local main-model metadata unavailable')
            models = json.loads(raw)
            if 'qwen3-8b' not in {item['id'] for item in models.get('data', [])}:
                raise RuntimeError('Unexpected served model alias')
        finally:
            connection.close()
        return {'verified_model_directory': str(Path(model_dir).resolve()),
                'model': pin['model_id'], 'revision': pin['revision'],
                'verified_files': verified['verified_files'], 'tokenizer_directory': str(tokenizer),
                'judge_socket': str(Path(judge_socket).resolve()),
                'alias_is_not_weight_identity_proof': True,
                'service_launch_receipt_still_required_for_publication': True}

    def command(self, arm, staged, snapshot, armout, runtime):
        from specprune.isolation import command
        readonly = [(staged, '/input'), (snapshot, '/snapshot'),
                    (BUNDLE / 'configs/deployment.json', '/deployment.json'),
                    (Path(runtime['tokenizer_directory']), '/main_model'),
                    (BUNDLE / 'assets/tokenizers', '/bundle/assets/tokenizers')]
        if arm == 'hybrid_safe':
            readonly.append((Path(runtime['judge_socket']), '/judge.sock'))
        return command(['_worker', '--arm', arm], readonly=readonly,
                       writable=[(armout, '/output')], gpu=False)


class Controller:
    def __init__(self, manifest, out, *, backend=None, heartbeat_seconds=2., timeout_seconds=3600.):
        self.manifest, self.records = load_manifest(manifest)
        self.out = Path(out).absolute()
        self.backend = backend or FrozenBackend()
        if heartbeat_seconds <= 0 or timeout_seconds != 3600:
            raise ValueError('Positive heartbeat and frozen 3600s arm timeout required')
        self.heartbeat_seconds, self.timeout_seconds = heartbeat_seconds, timeout_seconds
        self.protocol = {'schema': 1, 'manifest_sha256': sha(self.manifest),
                         'records': self.records, 'simulation': self.backend.simulation,
                         'controller_sha256': sha(__file__), 'execution': self.backend.protocol(),
                         'arms': list(ARMS), 'replay_policy': 'never replay an already started arm',
                         'arm_timeout_seconds': timeout_seconds, 'new_model_service_started': False}
        self.protocol_sha = digest(self.protocol)

    def pair(self, record):
        return self.out / 'pairs' / record['instance_id']

    def prepare(self):
        with lock_output(self.out):
            write(self.out / 'freeze.json', {**self.protocol, 'protocol_sha256': self.protocol_sha}, immutable=True)
            for record in self.records:
                pair = self.pair(record)
                pair.mkdir(parents=True, exist_ok=True)
                receipt = source_receipt(record['job_path'])
                prep = pair / 'prepared.json'
                if prep.exists():
                    self.verify_pair(record)
                    continue
                stage = pair / '_public_inputs'
                if stage.exists():
                    raise RuntimeError('Interrupted preparation retained; use a new output directory')
                self.backend.stage(Path(record['job_path']), stage)
                staged = {p.name: sha(p) for p in stage.iterdir() if p.is_file()}
                if set(staged) != {'job.json', 'code_index.json', 'repo_structures', 'render_cache.json', 'public_receipt.json'} - {'repo_structures'}:
                    raise ValueError('Unexpected stage file inventory')
                files = {str(p.relative_to(stage)): sha(p) for p in stage.rglob('*') if p.is_file()}
                write(prep, {'protocol_sha256': self.protocol_sha, 'source': receipt,
                             'staged_sha256': files}, immutable=True)
            self.progress('prepared')

    def verify_pair(self, record):
        pair = self.pair(record); prep = read(pair / 'prepared.json')
        if prep['protocol_sha256'] != self.protocol_sha or prep['source'] != source_receipt(record['job_path']):
            raise ValueError('Frozen input identity or source changed')
        stage = pair / '_public_inputs'
        actual = {}
        for p in stage.rglob('*'):
            if p.is_symlink():
                raise ValueError('Symlink in public inputs')
            if p.is_file():
                rel = p.relative_to(stage).as_posix()
                if rel != 'shared.json':
                    actual[rel] = sha(p)
        if actual != prep['staged_sha256']:
            raise ValueError('Staged model inputs changed or contain extra/private files')
        if (stage / 'shared.json').exists():
            baseline = pair / 'baseline/result.json'
            if not baseline.exists():
                raise ValueError('Shared model input exists without a baseline result')
            self.shared(record)  # Reconstruct and verify solely from that baseline.
        return prep

    def terminal(self, record, arm, status, **extra):
        value = {'instance_id': record['instance_id'], 'base_commit': record['base_commit'],
                 'arm': arm, 'status': status, 'protocol_sha256': self.protocol_sha,
                 'keep_in_denominator': True, 'simulation': self.backend.simulation, **extra}
        write(self.pair(record) / arm / 'terminal.json', value, immutable=True)
        return value

    def arm_state(self, record, arm):
        directory = self.pair(record) / arm
        terminal = directory / 'terminal.json'
        if terminal.exists():
            result = read(terminal)
            for key, expected in (('protocol_sha256', self.protocol_sha), ('instance_id', record['instance_id']),
                                  ('base_commit', record['base_commit']), ('arm', arm)):
                if result.get(key) != expected:
                    raise ValueError('Terminal identity drift: ' + key)
            if result['status'] not in TERMINAL:
                raise ValueError('Unknown terminal state')
            if 'result_sha256' in result and sha(directory / 'result.json') != result['result_sha256']:
                raise ValueError('Historical model output changed')
            return result
        started = directory / 'started.json'
        if not started.exists():
            return {'status': 'unstarted'}
        receipt = read(started)
        if receipt['protocol_sha256'] != self.protocol_sha:
            raise ValueError('Started arm protocol mismatch')
        if (directory / 'result.json').exists():
            result = read(directory / 'result.json')
            if result.get('instance_id') != record['instance_id'] or result.get('base_commit') != record['base_commit']:
                raise ValueError('Model result identity mismatch')
            if result.get('repo', record['repo']) != record['repo'] or result.get('arm', arm) != arm:
                raise ValueError('Model result repository/arm mismatch')
            return self.terminal(record, arm, 'complete' if result.get('status') == 'complete' else 'worker_failed',
                                 result_status=result.get('status'), result_sha256=sha(directory / 'result.json'),
                                 failure_attribution=None if result.get('status') == 'complete' else
                                 'undetermined; retain original worker error, not a repair-capability verdict')
        process = read(directory / 'process.json') if (directory / 'process.json').exists() else None
        if process and same_process(process, current_process(process['pid'])):
            raise RuntimeError('Previously started owned worker is still alive; do not launch a duplicate')
        return self.terminal(record, arm, 'interrupted',
                             reason='started arm has no terminal model result; never replayed',
                             signal_sent=False)

    def shared(self, record):
        pair = self.pair(record); path = pair / '_public_inputs/shared.json'
        result_path = pair / 'baseline/result.json'
        if not result_path.exists():
            return None
        result = read(result_path)
        # Match frozen runner.run_pair's file-stage gate exactly. Other keys
        # alone never qualify a baseline result for shared-file reuse.
        if 'ranked_edit_files' not in result:
            return None
        if 'file_rank_after_reflection' not in result or 'raw_file_responses' not in result:
            raise ValueError('Qualified frozen baseline lacks its shared-file evidence')
        public = {'instance_id': record['instance_id'], 'base_commit': record['base_commit'],
                  'files': result['file_rank_after_reflection'], 'raw_file_responses': result['raw_file_responses']}
        write(path, public, immutable=True)
        write(pair / 'shared_receipt.json', {'baseline_result_sha256': sha(result_path),
                                           'shared_sha256': sha(path),
                                           'protocol_sha256': self.protocol_sha}, immutable=True)
        return path

    def execute_arm(self, record, arm, runtime):
        self.verify_pair(record)
        if self.arm_state(record, arm)['status'] != 'unstarted':
            return
        pair = self.pair(record); directory = pair / arm
        directory.mkdir(exist_ok=True)
        command = self.backend.command(arm, pair / '_public_inputs',
                                       Path(read(pair / 'prepared.json')['source']['snapshot']), directory, runtime)
        write(directory / 'started.json', {'protocol_sha256': self.protocol_sha,
                                          'started_utc': time.time(), 'command_sha256': digest(command)}, immutable=True)
        process = None; owner = None; began = time.monotonic()
        try:
            with (directory / 'console.log').open('x', encoding='utf-8') as stream:
                process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                owner = current_process(process.pid)
                if owner is None:
                    raise RuntimeError('Worker exited before its ownership identity was captured')
                write(directory / 'process.json', owner, immutable=True)
                while process.poll() is None:
                    write(pair / 'heartbeat.json', {'instance_id': record['instance_id'], 'arm': arm,
                          'utc': time.time(), 'worker_identity': owner,
                          'elapsed_seconds': time.monotonic() - began})
                    self.progress('running')
                    if time.monotonic() - began > self.timeout_seconds:
                        stopped = signal_owned(owner)
                        self.terminal(record, arm, 'timed_out', shutdown=stopped)
                        try: process.wait(timeout=10)
                        except subprocess.TimeoutExpired: pass
                        return
                    time.sleep(self.heartbeat_seconds)
            if process.returncode:
                if (directory / 'result.json').exists():
                    self.arm_state(record, arm)
                else:
                    self.terminal(record, arm, 'controller_failed', returncode=process.returncode)
            elif (directory / 'result.json').exists():
                self.arm_state(record, arm)
            else:
                self.terminal(record, arm, 'controller_failed', reason='worker exited without result')
        except BaseException as error:
            stopped = signal_owned(owner) if process is not None and owner is not None and process.poll() is None else {'signal_sent': False}
            if not (directory / 'terminal.json').exists():
                self.terminal(record, arm, 'interrupted', reason=type(error).__name__ + ': ' + str(error), shutdown=stopped)
            raise

    def progress(self, phase):
        records = []
        for record in self.records:
            pair = self.pair(record)
            states = {}
            for arm in ARMS:
                f = pair / arm / 'terminal.json'
                states[arm] = read(f)['status'] if f.exists() else 'started' if (pair / arm / 'started.json').exists() else 'unstarted'
            records.append({'instance_id': record['instance_id'], 'arms': states,
                            'terminal_pair': all(value in TERMINAL for value in states.values())})
        write(self.out / 'progress.json', {'phase': phase, 'utc': time.time(),
              'protocol_sha256': self.protocol_sha, 'selected': len(records),
              'terminal_pairs': sum(r['terminal_pair'] for r in records),
              'all_selected_retained': True, 'records': records})

    def run(self, model_dir, judge_socket):
        with lock_output(self.out):
            if read(self.out / 'freeze.json') != {**self.protocol, 'protocol_sha256': self.protocol_sha}:
                raise ValueError('Manifest or execution protocol drift; refuse resume')
            for record in self.records:
                self.verify_pair(record)
            pending = [(r, arm) for r in self.records for arm in ARMS
                       if self.arm_state(r, arm)['status'] == 'unstarted']
            if not pending:
                self.progress('complete'); return
            runtime = self.backend.check_services(model_dir, judge_socket, self.out)
            write(self.out / 'runtime_environment.json', runtime, immutable=True)
            for record in self.records:
                self.execute_arm(record, 'baseline', runtime)
                shared = self.shared(record)
                if shared is None:
                    state = self.arm_state(record, 'hybrid_safe')
                    if state['status'] == 'unstarted':
                        self.terminal(record, 'hybrid_safe', 'dependency_blocked',
                                      model_called=False, reason='baseline file stage unavailable')
                    elif state['status'] != 'dependency_blocked':
                        raise ValueError('Hybrid had started without a valid frozen file stage')
                else:
                    self.execute_arm(record, 'hybrid_safe', runtime)
                states = {arm: self.arm_state(record, arm) for arm in ARMS}
                write(self.pair(record) / 'pair_terminal.json', {'instance_id': record['instance_id'],
                      'protocol_sha256': self.protocol_sha, 'arms': states,
                      'keep_in_denominator': True}, immutable=True)
                self.progress('running')
            self.progress('complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare-only', action='store_true')
    action.add_argument('--run', action='store_true')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--main-model-dir', type=Path)
    parser.add_argument('--judge-socket', type=Path)
    args = parser.parse_args()
    controller = Controller(args.manifest, args.out)
    if args.prepare_only:
        controller.prepare()
    else:
        if args.main_model_dir is None or args.judge_socket is None:
            parser.error('--run requires --main-model-dir and --judge-socket')
        controller.run(args.main_model_dir, args.judge_socket)
    print(json.dumps({'out': str(controller.out), 'phase': read(controller.out / 'progress.json')['phase'],
                      'selected': len(controller.records), 'simulation': controller.backend.simulation,
                      'gpu_or_service_started_by_controller': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
