"""One lifetime of frozen Qwen/4B services for all three ablation conditions.

The original main command, credential whitelist, weight verification, 90-second
admission rules and exact owned-process cleanup are reused. Only the isolated
judge entry, three-condition controller and terminal gate are adapted. Import,
--plan and --observe-once never start a model service.
"""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from code_sfpruner300_20261114 import service_queue as base
from . import common as c
from .backend import isolated_command
from .policy import ARMS

MAIN_GPUS = (2, 3)
JUDGE_GPU = 1
MAX_CUMULATIVE_INFRASTRUCTURE_LAUNCHES = 3
identity, owned, stop_owned = base.identity, base.owned, base.stop_owned


def basic_identity(pid):
    """Read UID/start ticks/ancestry even when a CUDA child's cwd is unavailable.

    Only explicit disappearance returns None. Permission or other observation
    failures remain errors, never evidence that a process exited.
    """
    proc = Path('/proc') / str(int(pid))
    try:
        raw = (proc / 'stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        return {'pid': int(pid), 'uid': proc.stat().st_uid, 'state': fields[0],
                'ppid': int(fields[1]), 'pgid': int(fields[2]), 'sid': int(fields[3]),
                'start_ticks': int(fields[19]), 'identity_kind': 'basic'}
    except (FileNotFoundError, ProcessLookupError):
        return None


def leader_exit_observation(saved, observe=None):
    """Retitled argv or failed ownership comparison alone never means exited."""
    try:
        current = (observe or basic_identity)(saved['pid'])
        if current is None:
            return {'leader_exited': True, 'evidence': 'proc_disappeared', 'observed': None}
        if current['start_ticks'] != saved['start_ticks']:
            return {'leader_exited': True, 'evidence': 'pid_reused_old_start_ticks_gone', 'observed': current}
        if current['state'] == 'Z':
            return {'leader_exited': True, 'evidence': 'zombie', 'observed': current}
        return {'leader_exited': False, 'evidence': 'same_start_ticks_still_alive', 'observed': current}
    except Exception as error:
        return {'leader_exited': False, 'evidence': 'observation_error',
                'error': type(error).__name__ + ': ' + str(error)}


def cuda_ownership_snapshot(processes, *, query=None, observe_basic=None, observe_full=None):
    """Attribute only real NVML PIDs with a witnessed host ancestry to our leaders."""
    observe_basic, observe_full = observe_basic or basic_identity, observe_full or base.identity
    query = query or (lambda argv: subprocess.check_output(argv, text=True, stderr=subprocess.PIPE, timeout=10))
    result = {'observed_utc': time.time(), 'status': 'OBSERVED', 'leaders': {}, 'records': [],
              'errors': [], 'signals_sent': False, 'foreign_or_unresolved_never_claimed': True}
    leaders = {}
    for role, process, receipt, directory in processes:
        if role not in ('main', 'judge'):
            continue
        saved = receipt['identity']
        try:
            current = observe_basic(saved['pid'])
            matched = bool(current and all(current.get(k) == saved.get(k)
                for k in ('pid', 'uid', 'start_ticks', 'pgid', 'sid')) and current['state'] != 'Z')
            result['leaders'][role] = {'saved': saved, 'current_basic': current,
                'basic_saved_identity_matches': matched, 'ownership_receipt': str(directory/'ownership.json')}
            if matched and saved['uid'] == os.getuid():
                leaders[saved['pid']] = (role, saved)
        except Exception as error:
            result['leaders'][role] = {'saved': saved, 'observation_error': type(error).__name__ + ': ' + str(error)}
    try:
        gpu_text = query(['nvidia-smi', '--query-gpu=index,uuid', '--format=csv,noheader,nounits'])
        gpu_indices = {}
        for parts in csv.reader(io.StringIO(gpu_text)):
            if not parts: continue
            if len(parts) != 2: raise ValueError('Invalid NVML GPU identity row')
            index, uid = [p.strip() for p in parts]
            gpu_indices[uid] = int(index)
        result['gpu_inventory'] = gpu_indices
        apps = query(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory',
                      '--format=csv,noheader,nounits'])
        for parts in csv.reader(io.StringIO(apps)):
            if not parts: continue
            if len(parts) != 4: raise ValueError('Invalid NVML compute process row')
            gpu_uuid, pid_text, process_name, used = [p.strip() for p in parts]
            pid = int(pid_text)
            record = {'gpu_uuid': gpu_uuid, 'gpu_index': gpu_indices.get(gpu_uuid), 'pid': pid,
                      'nvml_process_name': process_name, 'nvml_used_mib': used, 'claimed_owned': False,
                      'owned_role': None, 'ancestry': []}
            result['records'].append(record)
            seen = set(); current_pid = pid
            try:
                for depth in range(64):
                    if current_pid <= 0 or current_pid in seen: break
                    seen.add(current_pid)
                    current = observe_basic(current_pid)
                    if current is None:
                        record['ancestry_limitation'] = 'host_pid_absent_or_ancestor_exited'
                        break
                    record['ancestry'].append(current)
                    if current_pid in leaders:
                        role, saved = leaders[current_pid]
                        if (current['uid'] == saved['uid'] and current['start_ticks'] == saved['start_ticks']
                                and record['ancestry'][0]['uid'] == saved['uid']):
                            record.update(claimed_owned=True, owned_role=role,
                                leader_pid=current_pid, leader_start_ticks=saved['start_ticks'])
                        break
                    current_pid = current['ppid']
                if record['claimed_owned']:
                    try: full = observe_full(pid)
                    except Exception as error:
                        full = None; record['full_identity_error'] = type(error).__name__ + ': ' + str(error)
                    if full is not None and any(full.get(k) != record['ancestry'][0].get(k)
                                                for k in ('pid', 'uid', 'start_ticks')):
                        full = None
                        record['full_identity_error'] = 'Full/basic identity changed during observation'
                    # Never present an inaccessible cwd as fully witnessed.
                    record['current_basic'] = record['ancestry'][0]
                    record['current_full'] = full
                    record['identity_scope'] = 'full' if full is not None else 'basic_only_cwd_or_argv_unavailable'
                    expected = MAIN_GPUS if record['owned_role'] == 'main' else (JUDGE_GPU,)
                    record['expected_gpu'] = record['gpu_index'] in expected
                else:
                    record['identity_scope'] = 'foreign_or_unresolved_not_owned'
            except Exception as error:
                record['observation_error'] = type(error).__name__ + ': ' + str(error)
    except Exception as error:
        result['errors'].append(type(error).__name__ + ': ' + str(error))
    if result['errors'] or any('observation_error' in row for row in result['records']):
        result['status'] = 'OBSERVATION_PARTIAL'
    return result


def role_cuda_observations(snapshot, processes):
    """Explicit negative evidence is different from a missing CUDA snapshot.

    A failed CPU startup can own a service leader without ever creating CUDA.
    Only a complete NVML observation of every expected device with no compute
    row supports that case. Unknown/foreign rows on those devices do not.
    """
    result = {}
    for role, process, receipt, directory in processes:
        if role not in ('main', 'judge'):
            continue
        expected = set(MAIN_GPUS if role == 'main' else (JUDGE_GPU,))
        inventory = set(snapshot.get('gpu_inventory', {}).values())
        complete = (snapshot.get('status') == 'OBSERVED' and not snapshot.get('errors')
                    and expected <= inventory
                    and all(row.get('gpu_index') is not None for row in snapshot.get('records', [])))
        rows = [r for r in snapshot.get('records', []) if r.get('gpu_index') in expected]
        path = directory / 'ownership.json'
        result[role] = {'ownership_receipt': str(path),
            'ownership_receipt_sha256': c.sha(path) if path.is_file() else None,
            'saved_pid': receipt['identity']['pid'],
            'saved_start_ticks': receipt['identity']['start_ticks'],
            'expected_gpus': sorted(expected), 'nvml_query_complete': complete,
            'expected_device_compute_records': len(rows),
            'no_compute_on_expected_devices': complete and not rows,
            'observed_owned_cuda_pids': [r['pid'] for r in rows
                                        if r.get('claimed_owned') and r.get('owned_role') == role]}
    return result


def judge_command(model_dir, adapter_dir, socket_dir):
    return [sys.executable, '-B', '-m', 'code_locbench_ablation_20261117_v2.services',
            'judge-launcher', '--model-dir', str(model_dir), '--adapter-dir', str(adapter_dir),
            '--deployment', str(base.c.BUNDLE / 'configs/deployment.json'),
            '--socket-dir', str(socket_dir), '--device', 'cuda:0']


def judge_launcher(args):
    """Explicit outer host command; only the allowlisted inner scorer sees CUDA."""
    output = Path(args.socket_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    deployment = Path(args.deployment).resolve(strict=True)
    if c.sha(deployment) != c.sha(base.c.BUNDLE / 'configs/deployment.json'):
        raise ValueError('Only the frozen deployment may be mounted')
    command = isolated_command('code_locbench_ablation_20261117_v2.judge_server',
        ['--device', args.device], readonly=[
            (Path(args.model_dir), '/judge_model'), (Path(args.adapter_dir), '/adapter'),
            (deployment, '/deployment.json'),
            (base.c.BUNDLE / 'provenance/model_files.json', '/bundle/provenance/model_files.json')],
        writable=[(output, '/transport')], gpu=True)
    return subprocess.run(command, check=True, timeout=None)


def judge_probe(socket_path, row):
    """Three explicitly synthetic forwards: disabled, restored, restored again."""
    from .worker import SocketClient
    health_before = SocketClient(ARMS[0], str(socket_path)).request('health')
    records = []
    for variant in ARMS:
        result = SocketClient(variant, str(socket_path)).request('score', row)
        if (result.get('experimental_arm') != variant
                or result.get('adapter_active') is not (variant != ARMS[0])
                or not math.isfinite(result['logit_difference'])):
            raise RuntimeError('Synthetic judge condition/finite check failed')
        records.append({'variant': variant, 'result': result, 'benchmark_task': False})
    health_after = SocketClient(ARMS[0], str(socket_path)).request('health')
    if health_after['score_sequence'] - health_before['score_sequence'] != 3:
        raise RuntimeError('Synthetic capacity probe did not observe exactly three scores')
    # The latter two requests use the identical synthetic row and restored LoRA.
    # Compare numerical results; never impose a separation from no-LoRA scores.
    restored = [record['result']['logit_difference'] for record in records[1:]]
    difference = abs(restored[0] - restored[1])
    if difference > 1e-5:
        raise RuntimeError('Restored-adapter synthetic scores disagree')
    return {'ok': True, 'benchmark_task': False, 'synthetic_forward_count': 3,
            'records': records, 'health_before': health_before, 'health_after': health_after,
            'adapter_restoration_check': {'passed': True, 'enabled_score_difference': difference,
                                          'absolute_tolerance': 1e-5}}


@contextmanager
def service_bindings():
    """Temporary bindings only within this dedicated queue process."""
    old_command, old_rpc = base.judge_command, base.judge_rpc
    try:
        base.judge_command, base.judge_rpc = judge_command, judge_probe
        yield
    finally:
        base.judge_command, base.judge_rpc = old_command, old_rpc


def terminal_gate(controller, progress):
    """All allocated issues and all three conditions, including explicit failures."""
    records = controller.records
    if (progress.get('phase') != 'complete' or progress.get('selected') != len(records)
            or progress.get('terminal_pairs') != len(records)
            or progress.get('terminal_arms') != 3 * len(records)):
        raise RuntimeError('Three-arm controller is not completely terminal')
    for record in records:
        controller.verify_pair(record)
        for arm in ARMS:
            state = controller.arm_state(record, arm)
            if state is None or state.get('status') not in c.TERMINAL:
                raise RuntimeError('Completed progress disagrees with three-arm terminal evidence')
    return True


class Queue(base.Queue):
    def __init__(self, root, model_dir, judge_dir, adapter_dir, *, poll_seconds=10, judge_gpu=1):
        self.root = Path(root).resolve()
        if judge_gpu != JUDGE_GPU:
            raise ValueError('Frozen ablation judge is admitted only on GPU1')
        super().__init__(self.root / 'manifest.json', self.root / 'run',
            self.root / 'controller/service_queue', model_dir, judge_dir, adapter_dir,
            poll_seconds=poll_seconds, judge_gpu=judge_gpu)
        protocol_path = self.root / 'protocol.json'
        amendment = c.read(protocol_path).get('engineering_amendment') if protocol_path.exists() else None
        self.prior_service_sessions = [] if amendment is None else amendment.get('prior_service_sessions')
        if not isinstance(self.prior_service_sessions, list):
            raise ValueError('Engineering restart must preserve the prior service-session allowance')
        prior_paths = [item['session_directory'] for item in self.prior_service_sessions]
        if len(prior_paths) != len(set(prior_paths)):
            raise ValueError('Duplicate inherited service session')
        self._validate_prior_sessions()
        self.plan.update(experiment_root=str(self.root), experimental_arms=list(ARMS),
            internal_worker_arm='hybrid_safe', main_physical_gpus=list(MAIN_GPUS),
            ablation_services_sha256=c.sha(__file__), ablation_package_files_sha256=c.package_sources(),
            judge_command_family='code_locbench_ablation_20261117_v2.services judge-launcher',
            controller_command_family='code_locbench_ablation_20261117_v2.controller',
            nonbenchmark_judge_probe_forwards=3, reporter_joined=False,
            prior_service_sessions=self.prior_service_sessions,
            maximum_cumulative_infrastructure_launches=MAX_CUMULATIVE_INFRASTRUCTURE_LAUNCHES)

    def _validate_prior_sessions(self):
        for item in self.prior_service_sessions:
            directory = Path(item['session_directory'])
            path = Path(item['lifetime_admission_path'])
            if (path.parent != directory or path.name != 'lifetime_admission.json'
                    or path.is_symlink() or directory.is_symlink()
                    or c.sha(path) != item['lifetime_admission_sha256']):
                raise ValueError('Inherited service-session evidence changed')

    def session_count(self):
        self._validate_prior_sessions()
        prior = len(self.prior_service_sessions)
        directory = self.out/'sessions'
        if not directory.exists(): return prior
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError('Invalid lifetime service-session ledger')
        entries = list(directory.iterdir())
        if any(path.is_symlink() or not path.is_dir() for path in entries):
            raise ValueError('Unexpected entry in lifetime service-session ledger')
        return prior + len(entries)

    def require_launch_budget(self):
        count = self.session_count()
        if count >= MAX_CUMULATIVE_INFRASTRUCTURE_LAUNCHES:
            raise RuntimeError('Cumulative infrastructure launch limit3 reached; no new service session')
        return count

    def status(self, phase, **extra):
        extra.setdefault('experimental_arms', list(ARMS))
        return super().status(phase, **extra)

    def verify_plan_now(self):
        super().verify_plan_now()
        if (self.plan['ablation_services_sha256'] != c.sha(__file__)
                or self.plan['ablation_package_files_sha256'] != c.package_sources()
                or self.plan['main_command'] != base.main_command(self.model)):
            raise ValueError('Ablation service execution source or frozen command changed')

    def ready(self):
        self.verify_plan_now()
        required = [self.manifest, self.run_dir / 'freeze.json', self.run_dir / 'progress.json',
                    self.root / 'controller/execution_freeze.json']
        if not all(path.is_file() for path in required):
            return None
        c.require_execution_freeze(self.root)
        hashes = tuple(c.sha(path) for path in (self.manifest, self.run_dir / 'freeze.json', required[-1]))
        if self._ready_controller is not None:
            if hashes != self._ready_hashes:
                raise ValueError('Ready ablation manifest/freeze changed while queued')
            return self._ready_controller
        from .controller import Controller
        controller = Controller(self.root)
        if c.read(self.run_dir / 'freeze.json') != {**controller.protocol,
                                                   'protocol_sha256': controller.protocol_sha}:
            raise ValueError('Prepared ablation input/controller protocol changed')
        for record in controller.records:
            controller.verify_pair(record)
        self._ready_controller, self._ready_hashes = controller, hashes
        return controller

    def controller_command(self, socket_path=None):
        return [sys.executable, '-B', '-m', 'code_locbench_ablation_20261117_v2.controller',
                '--root', str(self.root), '--run', '--main-model-dir', str(self.model),
                '--judge-socket', str(socket_path or self.current_socket)]

    def spawn(self, role, command, env, session):
        if role == 'controller':
            snapshot = cuda_ownership_snapshot(self.processes)
            path = session/'cuda_ownership.json'
            if path.exists():
                path = session/('cuda_ownership_'+str(time.time_ns())+'.json')
            c.write(path, snapshot, immutable=True)
        return super().spawn(role, command, env, session)

    def save_shutdown_cuda(self, processes, phase, snapshotter=None):
        sessions = {}
        for item in processes:
            role, process, receipt, directory = item
            if role in ('main', 'judge'):
                sessions.setdefault(directory.parent, []).append(item)
        paths = []
        for session, items in sessions.items():
            try:
                snapshot = dict((snapshotter or cuda_ownership_snapshot)(items))
            except Exception as error:
                snapshot = {'status': 'OBSERVATION_PARTIAL', 'records': [],
                            'errors': [type(error).__name__ + ': ' + str(error)]}
            snapshot.update(observation_phase=phase,
                started_roles=sorted({item[0] for item in items}),
                role_observations=role_cuda_observations(snapshot, items),
                signals_sent_by_observer=False)
            path = session / ('cuda_ownership_' + phase + '_' + str(time.time_ns()) + '.json')
            c.write(path, snapshot, immutable=True)
            paths.append(str(path))
        return paths

    def shutdown(self, *, wait_seconds=20, observe=None, sleeper=time.sleep, clock=time.monotonic,
                 cuda_snapshotter=None):
        """Retain original stop receipts, then observe exit without more signals."""
        saved_processes = list(self.processes)
        # Includes failures before controller spawn or even before judge launch.
        before_cuda = self.save_shutdown_cuda(saved_processes, 'before_shutdown', cuda_snapshotter)
        original = super().shutdown()
        observations = {role: [] for role, _, _, _ in saved_processes}
        deadline = clock() + min(20, max(0, wait_seconds))
        while True:
            all_exited = True
            for role, process, receipt, directory in saved_processes:
                if observations[role] and observations[role][-1]['leader_exited']:
                    continue
                value = leader_exit_observation(receipt['identity'], observe)
                value.update(observed_utc=time.time(), popen_returncode=process.poll())
                observations[role].append(value)
                all_exited = all_exited and value['leader_exited']
            if all_exited or clock() >= deadline:
                break
            sleeper(.25)
        after_cuda = self.save_shutdown_cuda(saved_processes, 'after_shutdown', cuda_snapshotter)
        outcomes = {}
        for role, process, receipt, directory in saved_processes:
            first = original.get(role, {})
            final = observations[role][-1]
            artifacts = {str(p): c.sha(p) for p in directory.glob('shutdown*.json') if p.is_file()}
            value = {'role': role, 'saved_identity': receipt['identity'], 'original_shutdown': first,
                'original_shutdown_artifacts_sha256': artifacts, 'observations': observations[role],
                'leader_exited': final['leader_exited'], 'additional_signals_sent': False,
                'maximum_observation_seconds': min(20, max(0, wait_seconds)),
                'exit_evidence': final['evidence'], 'argv_retitle_alone_is_not_exit': True,
                'CUDA_observations_before_shutdown': before_cuda,
                'CUDA_observations_after_shutdown': after_cuda}
            path = directory/'actual_exit_verification.json'
            if path.exists(): path = directory/('actual_exit_verification_'+str(time.time_ns())+'.json')
            c.write(path, value, immutable=True)
            outcomes[role] = {**first, 'original_leader_exited': first.get('leader_exited'),
                'leader_exited': final['leader_exited'], 'actual_exit_verification': str(path),
                'original_warning_preserved': bool(first.get('ownership_mismatch') or first.get('shutdown_timeout')
                    or first.get('shutdown_error')), 'additional_signals_sent': False}
        return outcomes

    def cleanup_prior(self):
        with service_bindings():
            return super().cleanup_prior()

    def execute(self, chosen, session, controller):
        if tuple(chosen) != MAIN_GPUS:
            raise RuntimeError('Main model may use only physical GPUs2,3; GPU0 is never touched')
        c.require_execution_freeze(self.root)
        with service_bindings():
            result = super().execute(chosen, session, controller)
        terminal_gate(controller, result)
        return result

    def observe_once(self):
        with base.c.lock_output(self.out):
            c.write(self.out / 'plan.json', self.plan, immutable=True)
            controller = self.ready()
            try: rows, error = base.gpu_inventory(), None
            except Exception as exception: rows, error = [], type(exception).__name__ + ': ' + str(exception)
            return self.status('WAITING_INPUTS' if controller is None else 'OBSERVED_ONLY',
                data_ready=controller is not None, gpus=rows, gpu_query_error=error,
                services_started=False,
                eligible_gpus=list(base.eligible([r for r in rows if r['index'] in MAIN_GPUS])))

    def wait(self):
        with base.c.lock_output(self.out):
            c.write(self.out / 'plan.json', self.plan, immutable=True)
            c.require_execution_freeze(self.root)
            if self.session_count() >= MAX_CUMULATIVE_INFRASTRUCTURE_LAUNCHES:
                initial_controller = self.ready()
                initial_progress = c.read(self.run_dir/'progress.json') if initial_controller is not None else {}
                if initial_progress.get('phase') != 'complete':
                    self.require_launch_budget()  # Before cleanup, GPU queries or signals.
                terminal_gate(initial_controller, initial_progress)
            self.cleanup_prior()
            gate, spare_gate, attempts = base.IdleGate(), base.gpu_spare.SpareGate(), 0
            while True:
                controller = self.ready()
                if controller is None:
                    self.status('WAITING_INPUTS', services_started=False)
                    time.sleep(self.poll); continue
                progress = c.read(self.run_dir / 'progress.json')
                if progress.get('phase') == 'complete':
                    terminal_gate(controller, progress)
                    return self.status('DONE_NO_NEW_WORK', services_started=False, selected=progress['selected'])
                self.require_launch_budget()
                try:
                    rows = base.gpu_inventory()
                    observation = gate.observe([r for r in rows if r['index'] in MAIN_GPUS], time.monotonic())
                    spare = spare_gate.observe(base.gpu_spare.observe_spare(self.judge_gpu), time.monotonic())
                except Exception as error:
                    self.status('GPU_QUERY_ERROR', error=str(error), services_started=False)
                    time.sleep(self.poll); gate, spare_gate = base.IdleGate(), base.gpu_spare.SpareGate(); continue
                self.status('WAITING_TWO_IDLE_GPUS', gpus=rows, **observation,
                            separate_judge=spare, services_started=False)
                if not observation['ready'] or not spare['ready']:
                    time.sleep(self.poll); continue
                # This check and mkdir share the queue's exclusive output lock.
                cumulative_before = self.require_launch_budget()
                attempts += 1
                session = self.out / 'sessions' / (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
                                                   + '_' + uuid.uuid4().hex[:12])
                session.mkdir(parents=True)
                c.write(session/'lifetime_admission.json', {
                    'session_ordinal': cumulative_before+1,
                    'previous_session_count': cumulative_before,
                    'maximum_cumulative_infrastructure_launches': MAX_CUMULATIVE_INFRASTRUCTURE_LAUNCHES,
                    'exclusive_queue_lock_held': True, 'root': str(self.root),
                    'semantic_retry': False}, immutable=True)
                self.processes, self.streams = [], []
                cleanup = None
                try:
                    result = self.execute(observation['chosen'], session, controller)
                    later_cleanup = self.shutdown()
                    cleanup = {**(cleanup or {}), **later_cleanup}
                    if any(not item.get('leader_exited') for item in cleanup.values()):
                        raise RuntimeError('Owned service cleanup incomplete; inspect saved identity')
                    return self.status('COMPLETE', selected=result['selected'], terminal_pairs=result['terminal_pairs'],
                        terminal_arms=result['terminal_arms'], shutdown=cleanup, session=str(session))
                except BaseException as error:
                    # Keep the launch fact even when shutdown already cleared self.processes.
                    launched = (any(role == 'controller' for role, _, _, _ in self.processes)
                                or (session / 'controller/ownership.json').is_file())
                    later_cleanup = self.shutdown()
                    cleanup = {**(cleanup or {}), **later_cleanup}
                    failure = {'error_type': type(error).__name__, 'error': str(error),
                        'controller_launched': launched, 'shutdown': cleanup,
                        'infra_attempt': attempts, 'cumulative_infrastructure_launches': self.session_count(),
                        'semantic_retry': False}
                    c.write(session / 'failure.json', failure, immutable=True)
                    self.status('FAILED', **failure, session=str(session))
                    if (isinstance(error, (KeyboardInterrupt, SystemExit)) or launched
                            or attempts >= base.MAX_INFRA_ATTEMPTS
                            or self.session_count() >= MAX_CUMULATIVE_INFRASTRUCTURE_LAUNCHES
                            or any(not item.get('leader_exited') for item in cleanup.values())):
                        raise
                    self.status('RETRY_INFRA_BEFORE_BENCHMARK', attempt=attempts,
                        maximum_attempts=base.MAX_INFRA_ATTEMPTS, semantic_retry=False)
                    time.sleep(self.poll); gate, spare_gate = base.IdleGate(), base.gpu_spare.SpareGate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    if len(sys.argv) > 1 and sys.argv[1] == 'judge-launcher':
        parser.add_argument('command', choices=['judge-launcher'])
        parser.add_argument('--model-dir', required=True, type=Path)
        parser.add_argument('--adapter-dir', required=True, type=Path)
        parser.add_argument('--deployment', required=True, type=Path)
        parser.add_argument('--socket-dir', required=True, type=Path)
        parser.add_argument('--device', default='cuda:0')
        return judge_launcher(parser.parse_args())
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--wait', action='store_true')
    actions.add_argument('--observe-once', action='store_true')
    actions.add_argument('--plan', action='store_true')
    parser.add_argument('--root', type=Path, default=c.DEFAULT_ROOT)
    parser.add_argument('--main-model-dir', type=Path, default=Path('/tmp/cosil_rebench_qwen3_8b_20261023/model'))
    parser.add_argument('--judge-model-dir', type=Path, default=base.c.ROOT / 'models_v6/Qwen3-Reranker-4B')
    parser.add_argument('--adapter-dir', type=Path, default=base.c.BUNDLE / 'checkpoints/specprune_epoch1')
    parser.add_argument('--poll-seconds', type=int, default=10)
    parser.add_argument('--judge-gpu', type=int, default=1)
    args = parser.parse_args()
    queue = Queue(args.root, args.main_model_dir, args.judge_model_dir, args.adapter_dir,
                  poll_seconds=args.poll_seconds, judge_gpu=args.judge_gpu)
    if args.plan:
        print(json.dumps(queue.plan, ensure_ascii=False, indent=2)); return
    def graceful(signum, frame): raise SystemExit(128 + signum)
    base.c.signal.signal(base.c.signal.SIGTERM, graceful)
    try:
        result = queue.wait() if args.wait else queue.observe_once()
    except BaseException as error:
        queue.out.mkdir(parents=True, exist_ok=True)
        queue.status('SUPERVISOR_FAILED', error_type=type(error).__name__, error=str(error), semantic_retry=False)
        raise
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
