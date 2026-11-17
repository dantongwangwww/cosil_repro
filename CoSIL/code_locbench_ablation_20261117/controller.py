"""Durable three-condition search; no file selection reruns or Gold reads."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
import json
import os
import subprocess
import threading
import time

from .common import (ARMS, INTERNAL_ARM, TERMINAL, CHECKPOINTS, original as c,
                     root_protocol, read, write, sha, digest, hashes_under,
                     verify_hashes, arm_order, require_execution_freeze)
from .backend import FrozenBackend


class Controller:
    def __init__(self, root, *, backend=None, heartbeat_seconds=2., timeout_seconds=3600.,
                 expected_n=560):
        self.backend = backend or FrozenBackend()
        if expected_n != 560 and not self.backend.simulation:
            raise ValueError('Only synthetic test backends may use a smaller scope')
        self.root, self.user_protocol = root_protocol(root, expected_n=expected_n)
        self.manifest = self.root / 'manifest.json'
        data = read(self.manifest)
        if (data['n'] != expected_n or data['allocated'] != expected_n
                or data['arms'] != list(ARMS) or len(data['records']) != expected_n):
            raise ValueError('Wrong three-condition manifest scope')
        self.records = data['records']
        ids = [x['instance_id'] for x in self.records]
        if len(set(ids)) != len(ids) or [x['rank'] for x in self.records] != list(range(1, expected_n + 1)):
            raise ValueError('Duplicate identity or noncontiguous frozen ranks')
        self.authority = read(self.root / 'authority.json')
        if (self.authority['manifest_sha256'] != sha(self.manifest)
                or self.authority['protocol_sha256'] != sha(self.root / 'protocol.json')):
            raise ValueError('Public preparation authority drift')
        self.out = self.root / 'run'
        self.timeout_seconds = timeout_seconds
        self.heartbeat_seconds = heartbeat_seconds
        if timeout_seconds != 3600 or heartbeat_seconds <= 0:
            raise ValueError('Frozen 3600s limit and positive heartbeat required')
        self.protocol = {'schema': 1, 'manifest_sha256': sha(self.manifest),
            'user_protocol_sha256': sha(self.root / 'protocol.json'),
            'preparation_authority_sha256': sha(self.root / 'authority.json'),
            'controller_sha256': sha(__file__), 'execution': self.backend.protocol(),
            'arms': list(ARMS), 'internal_worker_arm': INTERNAL_ARM,
            'simulation': self.backend.simulation, 'allocated': expected_n,
            'pair_workers': 2, 'per_issue_order': 'SHA256(20261117:instance_id:arm)',
            'canary_first_ready_issues': 3, 'arm_timeout_seconds': 3600,
            'replay_policy': 'never replay an already started arm',
            'new_file_stage_model_calls': 0}
        self.protocol_sha = digest(self.protocol)
        self._progress_lock = threading.RLock()

    def pair(self, record):
        return self.out / 'pairs' / record['instance_id']

    def prepare(self):
        with c.lock_output(self.out):
            write(self.out / 'freeze.json', {**self.protocol, 'protocol_sha256': self.protocol_sha}, immutable=True)
            for record in self.records:
                group = self.pair(record)
                group.mkdir(parents=True, exist_ok=True)
                receipt = Path(record['prepared_receipt_path'])
                wanted = {'instance_id': record['instance_id'],
                    'base_commit': record['base_commit'], 'protocol_sha256': self.protocol_sha,
                    'prepared_receipt_sha256': sha(receipt),
                    'public_files_sha256': record['public_files_sha256'],
                    'upstream_files_sha256': record['upstream_files_sha256'],
                    'upstream_status': record['upstream_status']}
                write(group / 'prepared.json', wanted, immutable=True)
                self.verify_group(record)
                if record['upstream_status'] != 'ready':
                    for arm in ARMS:
                        self.terminal(record, arm, record['upstream_status'], model_called=False,
                            upstream_status=record['upstream_status'],
                            reason=record['upstream_reason'], new_file_model_calls=0)
                    self.group_terminal(record)
            self.progress('prepared')

    def verify_group(self, record):
        group = self.pair(record)
        receipt = Path(record['prepared_receipt_path'])
        prepared = read(group / 'prepared.json')
        if (prepared['protocol_sha256'] != self.protocol_sha
                or prepared['prepared_receipt_sha256'] != sha(receipt)
                or prepared['upstream_status'] != record['upstream_status']):
            raise ValueError('Prepared group source or protocol drift')
        if str(receipt) not in self.authority['files_sha256'] or sha(receipt) != self.authority['files_sha256'][str(receipt)]:
            raise ValueError('Preparation receipt is not bound to original authority')
        verify_hashes(record['upstream_files_sha256'])
        if record['upstream_status'] == 'ready':
            if record.get('no_model_dispatch') is not False:
                raise ValueError('Ready task has contradictory dispatch flag')
            actual = hashes_under(record['public_input_path'])
            if actual != record['public_files_sha256'] or actual != prepared['public_files_sha256']:
                raise ValueError('Public inputs changed or contain extra files')
            source = read(receipt)['source_receipt']
            job = c.load_job(record['source_job_path'])
            if (sha(record['source_job_path']) != source['job_sha256']
                    or sha(job['code_index']) != source['index_sha256']
                    or sha(job['structure']) != source['structure_sha256']
                    or job['snapshot'] != record['source_snapshot']
                    or source['snapshot'] != record['source_snapshot']):
                raise ValueError('Frozen source job/index/structure changed')
            if any(job[k] != record[k] for k in ('instance_id', 'repo', 'base_commit')):
                raise ValueError('Model job identity mismatch')
            # The preparation rehashed every base byte. The isolated source
            # resolver additionally validates each retrieved file against this
            # unchanged complete index before exposing it to either model.
        elif (record['upstream_status'] not in TERMINAL or not record.get('no_model_dispatch')
                or record['public_input_path'] is not None or record['public_files_sha256']):
            raise ValueError('Invalid explicit upstream no-dispatch record')
        return prepared

    verify_pair = verify_group

    def terminal(self, record, arm, status, **extra):
        if arm not in ARMS or status not in TERMINAL:
            raise ValueError('Unknown experimental arm or terminal status')
        value = {'instance_id': record['instance_id'], 'repo': record['repo'],
            'base_commit': record['base_commit'], 'arm': arm, 'experimental_arm': arm,
            'internal_arm': INTERNAL_ARM, 'internal_worker_arm': INTERNAL_ARM,
            'status': status, 'protocol_sha256': self.protocol_sha,
            'keep_in_denominator': True, 'simulation': self.backend.simulation, **extra}
        write(self.pair(record) / arm / 'terminal.json', value, immutable=True)
        return value

    def arm_state(self, record, arm):
        if arm not in ARMS:
            raise ValueError('Historical controls are never new worker arms')
        directory = self.pair(record) / arm
        process_path = directory / 'process.json'
        if process_path.exists():
            saved = read(process_path)
            observed = c.current_process(saved['pid'])
            # A command-title change is not evidence of exit. The raw result can
            # be written before the worker has finished flushing its receipts.
            if (observed and observed.get('state') != 'Z' and all(
                    saved.get(key) == observed.get(key)
                    for key in ('pid', 'uid', 'start_ticks'))):
                raise RuntimeError('Owned previously started worker remains live; no duplicate dispatch or premature terminal')
        if (directory / 'terminal.json').exists():
            value = read(directory / 'terminal.json')
            expected = {'instance_id': record['instance_id'], 'base_commit': record['base_commit'],
                        'arm': arm, 'internal_arm': INTERNAL_ARM, 'protocol_sha256': self.protocol_sha,
                        'simulation': self.backend.simulation, 'keep_in_denominator': True}
            if any(value.get(k) != v for k, v in expected.items()) or value.get('status') not in TERMINAL:
                raise ValueError('Terminal identity or source drift')
            if 'result_sha256' in value and sha(directory / 'result.json') != value['result_sha256']:
                raise ValueError('Previously recorded model output changed')
            return value
        if not (directory / 'started.json').exists():
            return {'status': 'unstarted'}
        started = read(directory / 'started.json')
        if (started['protocol_sha256'] != self.protocol_sha or started['arm'] != arm
                or started['instance_id'] != record['instance_id']):
            raise ValueError('Started condition drift')
        if (directory / 'result.json').exists():
            value = read(directory / 'result.json')
            expected = {'instance_id': record['instance_id'], 'repo': record['repo'],
                'base_commit': record['base_commit'], 'arm': INTERNAL_ARM,
                'internal_arm': INTERNAL_ARM, 'experimental_arm': arm}
            if any(value.get(k) != v for k, v in expected.items()):
                raise ValueError('Worker result external/internal identity mismatch')
            return self.terminal(record, arm, 'complete' if value.get('status') == 'complete' else 'worker_failed',
                result_status=value.get('status'), result_sha256=sha(directory / 'result.json'),
                new_file_model_calls=0,
                failure_attribution=None if value.get('status') == 'complete' else
                    'retain raw worker error; not automatically a model capability failure')
        process = read(directory / 'process.json') if (directory / 'process.json').exists() else None
        if process and c.same_process(process, c.current_process(process['pid'])):
            raise RuntimeError('Owned previously started worker remains live; no duplicate dispatch')
        return self.terminal(record, arm, 'interrupted',
                             reason='Started worker lacks a result; never replayed', signal_sent=False)

    def close_worker(self, process, owner):
        """Wait for actual exit after an exactly owned SIGTERM; never guess."""
        if process.poll() is not None:
            return {'worker_exited': True, 'returncode': process.returncode, 'signal_sent': False}
        shutdown = c.signal_owned(owner) if owner is not None else {
            'signal_sent': False, 'reason': 'no_exact_saved_owner'}
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            return {**shutdown, 'worker_exited': False, 'returncode': None}
        return {**shutdown, 'worker_exited': True, 'returncode': process.returncode}

    def unresolved_worker(self, record, arm, observation):
        value = {'status': 'STOP_NEW_DISPATCH_UNRESOLVED_WORKER',
            'instance_id': record['instance_id'], 'arm': arm,
            'protocol_sha256': self.protocol_sha, 'observation': observation,
            'terminal_claimed': False, 'already_started_arms_must_not_replay': True}
        write(self.pair(record) / arm / 'exit_unresolved.json', value)
        write(self.root / 'controller/stop_dispatch.json', value)

    def group_terminal(self, record):
        states = {arm: self.arm_state(record, arm) for arm in ARMS}
        if any(value['status'] not in TERMINAL for value in states.values()):
            raise ValueError('Cannot close a group with an unfinished condition')
        write(self.pair(record) / 'group_terminal.json', {'instance_id': record['instance_id'],
            'base_commit': record['base_commit'], 'protocol_sha256': self.protocol_sha,
            'arms': states, 'keep_in_denominator': True, 'simulation': self.backend.simulation}, immutable=True)

    def execute_arm(self, record, arm, runtime):
        self.verify_group(record)
        if self.arm_state(record, arm)['status'] != 'unstarted':
            return
        if (self.root / 'controller/report_fatal.json').exists() or (self.root / 'controller/stop_dispatch.json').exists():
            raise RuntimeError('Stop dispatch on recorded source/terminal/report integrity failure')
        if not self.backend.simulation:
            require_execution_freeze(self.root)
        if record['upstream_status'] != 'ready':
            raise ValueError('Never dispatch upstream blocked tasks')
        directory = self.pair(record) / arm
        directory.mkdir(parents=True, exist_ok=True)
        command = self.backend.command(arm, Path(record['public_input_path']),
                                       Path(record['source_snapshot']), directory, runtime)
        started = {'protocol_sha256': self.protocol_sha,
            'instance_id': record['instance_id'], 'base_commit': record['base_commit'],
            'arm': arm, 'internal_arm': INTERNAL_ARM, 'started_utc': time.time(),
            'command_sha256': digest(command)}
        if hasattr(self, '_current_runtime_receipt'):
            started.update(runtime_environment_receipt=self._current_runtime_receipt,
                           runtime_environment_sha256=sha(self._current_runtime_receipt))
        write(directory / 'started.json', started, immutable=True)
        process = owner = None
        began = time.monotonic()
        try:
            with (directory / 'console.log').open('xb') as stream:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                    stderr=subprocess.STDOUT, start_new_session=True)
                owner = c.current_process(process.pid)
                if owner is None:
                    raise RuntimeError('Worker ownership could not be witnessed')
                write(directory / 'process.json', owner, immutable=True)
                while process.poll() is None:
                    write(self.pair(record) / 'heartbeat.json', {'instance_id': record['instance_id'],
                        'arm': arm, 'utc': time.time(), 'worker_identity': owner,
                        'elapsed_seconds': time.monotonic() - began})
                    self.progress('running')
                    if time.monotonic() - began > self.timeout_seconds:
                        shutdown = self.close_worker(process, owner)
                        if not shutdown['worker_exited']:
                            self.unresolved_worker(record, arm, shutdown)
                            raise RuntimeError('Timed-out worker exit not confirmed; preserve started state')
                        self.terminal(record, arm, 'timed_out', shutdown=shutdown)
                        return
                    time.sleep(self.heartbeat_seconds)
            if (directory / 'result.json').exists():
                self.arm_state(record, arm)
            else:
                self.terminal(record, arm, 'controller_failed', returncode=process.returncode,
                              reason='Worker exited without model result')
        except BaseException as error:
            if (directory / 'exit_unresolved.json').exists():
                raise
            shutdown = self.close_worker(process, owner) if process is not None else {
                'signal_sent': False, 'worker_exited': True, 'reason': 'worker_not_launched'}
            if not shutdown['worker_exited']:
                self.unresolved_worker(record, arm, shutdown)
                raise RuntimeError('Worker exit not confirmed; preserve started state') from error
            if not (directory / 'terminal.json').exists():
                self.terminal(record, arm, 'interrupted', shutdown=shutdown,
                              reason=type(error).__name__ + ': ' + str(error))
            raise

    def progress(self, phase):
        with self._progress_lock:
            records = []
            for record in self.records:
                states = {}
                for arm in ARMS:
                    directory = self.pair(record) / arm
                    states[arm] = read(directory / 'terminal.json')['status'] if (directory / 'terminal.json').exists() else 'started' if (directory / 'started.json').exists() else 'unstarted'
                records.append({'instance_id': record['instance_id'], 'arms': states,
                    'terminal_pair': all(value in TERMINAL for value in states.values())
                        and (self.pair(record) / 'group_terminal.json').is_file()})
            terminal_pairs = sum(x['terminal_pair'] for x in records)
            value = {'phase': phase, 'utc': time.time(), 'pid': os.getpid(),
                'protocol_sha256': self.protocol_sha, 'selected': len(records),
                'terminal_pairs': terminal_pairs,
                'terminal_arms': sum(v in TERMINAL for x in records for v in x['arms'].values()),
                'complete_arms': sum(v == 'complete' for x in records for v in x['arms'].values()),
                'all_selected_retained': True, 'records': records}
            write(self.out / 'progress.json', value)
            # A CPU-only reporter consumes these immutable markers independently.
            for n in CHECKPOINTS:
                if n <= len(records) and all(x['terminal_pair'] for x in records[:n]):
                    marker = self.root / 'controller/checkpoints' / (str(n) + '.json')
                    if not marker.exists():
                        write(marker, {'status': 'PREFIX_ALL_ARMS_TERMINAL', 'n': n,
                            'protocol_sha256': self.protocol_sha, 'utc': time.time(),
                            'no_model_or_Gold_calls_by_marker': True}, immutable=True)
            return value

    def run_group(self, record, runtime):
        for arm in arm_order(record['instance_id']):
            self.execute_arm(record, arm, runtime)
        self.group_terminal(record)
        self.progress('running')

    def run_groups(self, records, runtime):
        iterator = iter(records)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = {}
            for _ in range(2):
                record = next(iterator, None)
                if record is not None:
                    pending[pool.submit(self.run_group, record, runtime)] = record
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    future.result()
                for future in done:
                    del pending[future]
                    record = next(iterator, None)
                    if record is not None:
                        pending[pool.submit(self.run_group, record, runtime)] = record

    def canary_check(self, records):
        counts = Counter()
        exercised = {arm: Counter() for arm in ARMS}
        for record in records:
            for arm in ARMS:
                state = self.arm_state(record, arm)
                if state['status'] not in TERMINAL:
                    raise ValueError('Canary did not reach an honest terminal state')
                counts[state['status']] += 1
                exercised[arm][state['status']] += 1
                directory = self.pair(record) / arm
                for request in (directory / 'calls').glob('*/request.json'):
                    exercised[arm]['main_requests'] += 1
                    value = read(request)
                    if (value.get('chat_template_kwargs', {}).get('enable_thinking') is not False
                            or value.get('max_tokens') != 2048 or value.get('temperature') != 0
                            or value.get('seed') != 0 or value.get('model') != 'qwen3-8b'):
                        raise ValueError('Canary main-request configuration drift')
                event_path = directory / 'events.jsonl'
                events = [json.loads(line) for line in event_path.read_text().splitlines()] if event_path.exists() else []
                if (not self.backend.simulation and state['status'] == 'complete'
                        and not any(e.get('event') == 'shared_file_stage' for e in events)):
                    raise ValueError('Completed canary did not exercise the frozen shared file stage')
                if state['status'] in ('controller_failed', 'interrupted'):
                    raise ValueError('Canary did not exercise a complete worker boundary; retain failure and stop dispatch')
                if state['status'] == 'worker_failed':
                    raw = read(directory / 'result.json')
                    # These indicate an integration/identity failure rather than
                    # an unfavorable localization outcome. Do not spend the
                    # remaining benchmark on a broken variant interface.
                    for marker in ('condition mismatch', 'Effective worker route mismatch',
                                   'Unknown ablation variant', 'Only explicit score',
                                   'Cross-condition', 'Frozen scorer route differs',
                                   'Expected frozen v6 input', 'Overbroad inference mount'):
                        if marker.lower() in str(raw.get('error', '')).lower():
                            raise ValueError('Canary integration failure: ' + str(raw.get('error')))
                for event in events:
                    if event.get('experimental_arm') != arm or event.get('internal_arm') != INTERNAL_ARM:
                        raise ValueError('Canary external/internal event identity mismatch')
                    if event['event'] == 'shared_file_stage' and event.get('new_file_model_calls') != 0:
                        raise ValueError('New file selection call in downstream-only ablation')
                    if event['event'] == 'local_judge':
                        exercised[arm]['local_judge'] += 1
                        if event.get('adapter_active') is not (arm != 'ablation_no_lora'):
                            raise ValueError('Canary adapter state mismatch')
                        if arm == 'ablation_no_neighbors' and (event['neighbors_selected'] != 0 or not event['model_input'].endswith('<direct_call_context>\n\n</direct_call_context>')):
                            raise ValueError('Neighbor ablation failed to remove the summary')
                        if arm == 'ablation_no_defer' and event.get('route_original') == 'qwen' and event.get('route') == 'qwen':
                            raise ValueError('Normal uncertain candidates were still deferred')
        if not self.backend.simulation:
            for arm, evidence in exercised.items():
                if any(evidence[key] < 1 for key in ('complete', 'main_requests', 'local_judge')):
                    raise ValueError('Engineering canary lacks a completed real main/judge chain for ' + arm)
        return {'status': 'ENGINEERING_CANARY_PASS', 'issues': len(records), 'arms': len(records) * 3,
                'statuses': dict(counts), 'accuracy_or_Gold_used_for_gate': False,
                'structural_only': True, 'simulation': self.backend.simulation,
                'exercised_by_condition': {arm: dict(value) for arm, value in exercised.items()}}

    def run(self, model_dir, judge_socket):
        if not self.backend.simulation:
            require_execution_freeze(self.root)
        with c.lock_output(self.out):
            if read(self.out / 'freeze.json') != {**self.protocol, 'protocol_sha256': self.protocol_sha}:
                raise ValueError('Refuse source/input/scheduling drift')
            for record in self.records:
                self.verify_group(record)
                states = [self.arm_state(record, arm) for arm in ARMS]
                if all(state['status'] in TERMINAL for state in states):
                    # Crash recovery may find the final arm receipt but not the
                    # group closure. Reconstruct it without replaying inference.
                    self.group_terminal(record)
            pending = [r for r in self.records if any(self.arm_state(r, arm)['status'] == 'unstarted' for arm in ARMS)]
            if not pending:
                if self.progress('complete')['terminal_pairs'] != len(self.records):
                    raise ValueError('Cannot complete a ledger without every group closure')
                return
            runtime = self.backend.check_services(model_dir, judge_socket, self.out)
            environment_path = self.out / 'runtime_environment.json'
            previous_environment_sha = None
            if environment_path.exists():
                previous_environment_sha = sha(environment_path)
                environment_path = self.out / 'runtime_environments' / (str(time.time_ns()) + '.json')
            write(environment_path, runtime, immutable=True)
            if previous_environment_sha is not None:
                write(self.out / 'runtime_environment_continuations' / (environment_path.stem + '.json'),
                    {'protocol_sha256': self.protocol_sha, 'original_environment_sha256': previous_environment_sha,
                     'new_environment': str(environment_path), 'new_environment_sha256': sha(environment_path),
                     'historical_environment_retained': True, 'started_arms_replayed': False}, immutable=True)
            self._current_runtime_receipt = str(environment_path)
            first = [r for r in self.records if r['upstream_status'] == 'ready'][:3]
            self.run_groups(first, runtime)
            write(self.root / 'controller/canary_gate.json', self.canary_check(first), immutable=True)
            first_ids = {r['instance_id'] for r in first}
            self.run_groups([r for r in pending if r['instance_id'] not in first_ids], runtime)
            result = self.progress('complete')
            if result['terminal_pairs'] != len(self.records):
                raise ValueError('Cannot complete a partial three-condition ledger')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare-only', action='store_true')
    action.add_argument('--run', action='store_true')
    parser.add_argument('--main-model-dir', type=Path)
    parser.add_argument('--judge-socket', type=Path)
    args = parser.parse_args()
    controller = Controller(args.root)
    if args.prepare_only:
        controller.prepare()
    else:
        if args.main_model_dir is None or args.judge_socket is None:
            parser.error('--run needs --main-model-dir and --judge-socket')
        controller.run(args.main_model_dir, args.judge_socket)
    print(read(controller.out / 'progress.json')['phase'])


if __name__ == '__main__':
    main()
