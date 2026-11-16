"""Synthetic service lifecycle/argv checks; no Popen, sockets, GPU or model."""
import copy
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import services as s
from .policy import ARMS


class Controller:
    def __init__(self, root=None):
        self.records = [{'instance_id': 'fixture__repo-1'}, {'instance_id': 'fixture__repo-2'}]
        self.protocol = {'fixture': 'three-arm CPU only'}
        self.protocol_sha = 'a' * 64
        self.states = {(r['instance_id'], arm): 'complete' for r in self.records for arm in ARMS}
        self.verified = []

    def verify_pair(self, record): self.verified.append(record['instance_id'])
    def arm_state(self, record, arm): return {'status': self.states[(record['instance_id'], arm)]}


def completed():
    return dict(phase='complete', selected=2, terminal_pairs=2, terminal_arms=6)


class ServicesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        inventory = patch.object(s.c, 'package_sources', return_value={'fake_source.py': 'f' * 64})
        inventory.start(); self.addCleanup(inventory.stop)

    def queue(self):
        return s.Queue(self.root, self.root/'main', self.root/'judge', self.root/'adapter')

    def test_main_command_environment_and_original_arm_constants_unchanged(self):
        queue = self.queue()
        command = queue.plan['main_command']
        self.assertEqual(command, s.base.main_command(queue.model))
        for flag, expected in [('--tensor-parallel-size', '2'), ('--max-model-len', '65536'),
                               ('--max-num-seqs', '1'), ('--gpu-memory-utilization', '0.59'),
                               ('--dtype', 'bfloat16'), ('--seed', '0'), ('--port', '7343')]:
            self.assertEqual(command[command.index(flag)+1], expected)
        self.assertEqual(tuple(s.base.c.ARMS), ('baseline', 'hybrid_safe'))
        self.assertEqual(queue.plan['idle_rule']['seconds'], 90)
        self.assertEqual(queue.plan['main_physical_gpus'], [2, 3])
        self.assertEqual(queue.plan['separate_judge_gpu'], 1)
        with patch.dict(os.environ, {'FORBIDDEN_SECRET_TEST': 'do not inherit'}, clear=False):
            environment, short = s.base.service_environment(queue.out, (2, 3))
        self.assertNotIn('FORBIDDEN_SECRET_TEST', environment)
        self.assertEqual(environment['CUDA_VISIBLE_DEVICES'], '2,3')
        self.assertEqual(environment['VLLM_USE_FLASHINFER_SAMPLER'], '0')
        self.assertEqual(environment['HF_HUB_OFFLINE'], '1')

    def test_exact_new_judge_and_controller_command_families(self):
        queue = self.queue()
        judge = s.judge_command(queue.judge, queue.adapter, '/tmp/fake/score')
        self.assertIn('code_locbench_ablation_20261117.services', judge)
        self.assertIn('judge-launcher', judge)
        self.assertEqual(judge[judge.index('--device') + 1], 'cuda:0')
        controller = queue.controller_command('/tmp/fake/score.sock')
        self.assertIn('code_locbench_ablation_20261117.controller', controller)
        self.assertEqual(controller[controller.index('--root') + 1], str(self.root))
        self.assertNotIn('--manifest', controller)
        with self.assertRaises(ValueError):
            s.Queue(self.root, 'm', 'j', 'a', judge_gpu=0)

    def test_launcher_maps_only_fixed_assets_and_new_inner_entry_without_starting(self):
        args = SimpleNamespace(socket_dir=self.root/'transport', model_dir=self.root/'judge',
            adapter_dir=self.root/'adapter', deployment=s.base.c.BUNDLE/'configs/deployment.json', device='cuda:0')
        with patch.object(s, 'isolated_command', return_value=['synthetic-command']) as command:
            with patch.object(s.subprocess, 'run', return_value='not-executed') as run:
                self.assertEqual(s.judge_launcher(args), 'not-executed')
        positional, keywords = command.call_args
        self.assertEqual(positional[0], 'code_locbench_ablation_20261117.judge_server')
        self.assertTrue(keywords['gpu'])
        self.assertEqual({target for _, target in keywords['readonly']},
            {'/judge_model', '/adapter', '/deployment.json', '/bundle/provenance/model_files.json'})
        self.assertEqual(keywords['writable'], [(self.root/'transport', '/transport')])
        run.assert_called_once_with(['synthetic-command'], check=True, timeout=None)

    def test_terminal_gate_requires_three_arms_and_keeps_preparation_failures(self):
        ctrl = Controller()
        for arm in ARMS:
            ctrl.states[(ctrl.records[0]['instance_id'], arm)] = 'source_preparation_blocked'
        self.assertTrue(s.terminal_gate(ctrl, completed()))
        self.assertEqual(len(ctrl.verified), 2)
        ctrl.states[(ctrl.records[1]['instance_id'], ARMS[2])] = 'running'
        with self.assertRaises(RuntimeError): s.terminal_gate(ctrl, completed())
        with self.assertRaises(RuntimeError): s.terminal_gate(Controller(), {**completed(), 'terminal_arms': 4})

    def test_service_bindings_restore_even_when_execution_raises(self):
        before = (s.base.judge_command, s.base.judge_rpc)
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            with s.service_bindings():
                self.assertIs(s.base.judge_command, s.judge_command)
                self.assertIs(s.base.judge_rpc, s.judge_probe)
                raise RuntimeError('synthetic')
        self.assertEqual(before, (s.base.judge_command, s.base.judge_rpc))

    def test_synthetic_probe_three_serial_forwards_disables_then_restores(self):
        from . import worker
        calls = []; sequence = [0]
        class Client:
            def __init__(self, variant, path): self.variant = variant
            def request(self, operation, row=None):
                if operation == 'health': return {'score_sequence': sequence[0]}
                calls.append((self.variant, copy.deepcopy(row))); sequence[0] += 1
                return {'experimental_arm': self.variant, 'adapter_active': self.variant != ARMS[0],
                        'logit_difference': 1. if self.variant == ARMS[0] else 2.}
        row = {'synthetic': True}
        with patch.object(worker, 'SocketClient', Client): result = s.judge_probe('unused', row)
        self.assertEqual([v for v, _ in calls], list(ARMS))
        self.assertTrue(all(value == row for _, value in calls))
        self.assertEqual(result['synthetic_forward_count'], 3)
        self.assertTrue(result['adapter_restoration_check']['passed'])
        self.assertFalse(result['benchmark_task'])

    def test_execute_reuses_original_lifecycle_but_rejects_gpu0(self):
        queue, ctrl = self.queue(), Controller()
        def original_execute(this, chosen, session, controller):
            self.assertIs(s.base.judge_command, s.judge_command)
            self.assertIs(s.base.judge_rpc, s.judge_probe)
            return completed()
        with patch.object(s.c, 'require_execution_freeze', return_value={'verified': True}):
            with patch.object(s.base.Queue, 'execute', original_execute):
                self.assertEqual(queue.execute((2, 3), self.root, ctrl), completed())
                with self.assertRaises(RuntimeError): queue.execute((0, 3), self.root, ctrl)

    def test_ready_requires_published_source_freeze_then_verifies_every_group(self):
        queue, ctrl = self.queue(), Controller()
        for path, value in [(self.root/'manifest.json', {}), (self.root/'run/progress.json', {}),
                            (self.root/'controller/execution_freeze.json', {}),
                            (self.root/'run/freeze.json', {**ctrl.protocol, 'protocol_sha256': ctrl.protocol_sha})]:
            s.c.write(path, value)
        module = SimpleNamespace(Controller=lambda root: ctrl)
        with patch.dict(sys.modules, {'code_locbench_ablation_20261117.controller': module}):
            with patch.object(s.c, 'require_execution_freeze', side_effect=ValueError('unpublished')):
                with self.assertRaisesRegex(ValueError, 'unpublished'): queue.ready()
            with patch.object(s.c, 'require_execution_freeze', return_value={}):
                self.assertIs(queue.ready(), ctrl)
                self.assertEqual(len(ctrl.verified), 2)
                s.c.write(self.root/'run/freeze.json', {'changed': True})
                with self.assertRaises(ValueError): queue.ready()

    def test_unknown_or_reused_pid_never_authorizes_signal(self):
        saved = dict(pid=123, pgid=123, sid=123, uid=os.getuid(), start_ticks=10, state='S',
                     argv=['fake'], cwd=str(s.base.c.ROOT))
        receipt = {'identity': saved, 'command': ['fake'], 'cwd': str(s.base.c.ROOT)}
        sent = []
        current = {**saved, 'start_ticks': 11}
        result = s.stop_owned(receipt, observe=lambda pid: current,
                              send=lambda *args: sent.append(args), wait_seconds=0)
        self.assertEqual(sent, [])
        self.assertTrue(result['ownership_mismatch'])

    def test_cleanup_accepts_only_new_exact_judge_command_before_ownership_checks(self):
        queue = self.queue()
        transport = Path('/tmp') / ('sfpq_' + s.c.digest(str(queue.out))[:12]) / 'judge_fixture'
        command = s.judge_command(queue.judge, queue.adapter, transport)
        receipt = dict(role='judge', command=command, cwd=str(s.base.c.ROOT),
                       plan_sha256=s.c.digest(queue.plan), identity={'pid': 123})
        path = queue.out/'sessions/fixture/judge/ownership.json'
        s.c.write(path, receipt)
        with patch.object(s.base, 'stop_owned', return_value={'leader_exited': True}) as stop:
            queue.cleanup_prior()
            stop.assert_called_once()
        bad = copy.deepcopy(receipt); bad['command'][3] = 'unrelated_service'
        s.c.write(path, bad)
        with patch.object(s.base, 'stop_owned') as stop:
            with self.assertRaises(RuntimeError): queue.cleanup_prior()
            stop.assert_not_called()

    def test_completed_wait_checks_all_three_arms_without_querying_or_starting(self):
        queue, ctrl = self.queue(), Controller()
        s.c.write(queue.run_dir/'progress.json', completed())
        with patch.object(queue, 'cleanup_prior'), patch.object(queue, 'ready', return_value=ctrl), \
                patch.object(s.c, 'require_execution_freeze', return_value={}):
            with patch.object(s.base, 'gpu_inventory', side_effect=AssertionError('no GPU query')):
                with patch.object(queue, 'spawn', side_effect=AssertionError('no process spawn')):
                    self.assertEqual(queue.wait()['phase'], 'DONE_NO_NEW_WORK')

    def test_real_original_execute_lifecycle_with_fake_services_and_three_arm_controller(self):
        queue, ctrl = self.queue(), Controller()
        session = self.root/'session'; session.mkdir()
        captured = []
        def spawn(role, command, environment, directory):
            captured.append((role, command, environment))
            if role == 'judge':
                transport = Path(command[command.index('--socket-dir')+1])
                s.c.write(transport/'ready.json', {'fixture': 'no actual scorer'})
            if role == 'controller':
                s.c.write(queue.run_dir/'progress.json', completed())
            return SimpleNamespace(returncode=0, poll=lambda: 0)
        inventory = [dict(index=i, has_compute_process=False, used_mib=0, free_mib=24000,
                          utilization=0) for i in (2, 3)]
        short = self.root/'short'
        def environment(work, cards): return {'CUDA_VISIBLE_DEVICES': ','.join(map(str, cards))}, short
        with ExitStack() as stack:
            for obj, name, kwargs in [
                (s.c, 'require_execution_freeze', {'return_value': {}}),
                (queue, 'verify_plan_now', {'return_value': None}),
                (queue, 'verify_models', {'return_value': None}),
                (queue, 'spawn', {'side_effect': spawn}),
                (queue, 'alive', {'return_value': True}),
                (queue, 'status', {'return_value': {}}),
                (s.base, 'gpu_inventory', {'return_value': inventory}),
                (s.base.gpu_spare, 'observe_spare', {'return_value': {'eligible': True}}),
                (s.base, 'service_environment', {'side_effect': environment}),
                (s.base, 'synthetic_judge_row', {'return_value': ({'synthetic': True, 'input_sha256': 'a'*64}, 8100)}),
                (s, 'judge_probe', {'return_value': {'synthetic_forward_count': 3, 'benchmark_task': False}}),
                (s.base.socket, 'socket', {}),
                (s.base, 'local_json', {'side_effect': [
                    {'data': [{'id': 'qwen3-8b'}]},
                    {'model': 'qwen3-8b', 'choices': [{'message': {'content': 'OK'}}]}]})]:
                stack.enter_context(patch.object(obj, name, **kwargs))
            self.assertEqual(queue.execute((2, 3), session, ctrl), completed())
        self.assertEqual([role for role, _, _ in captured], ['main', 'judge', 'controller'])
        self.assertEqual([env['CUDA_VISIBLE_DEVICES'] for _, _, env in captured], ['2,3', '1', ''])
        self.assertEqual(captured[0][1], s.base.main_command(queue.model))
        self.assertIn('judge-launcher', captured[1][1])
        self.assertIn('code_locbench_ablation_20261117.controller', captured[2][1])
        probe = s.c.read(session/'synthetic_capacity_probe.json')
        self.assertFalse(probe['benchmark_task'])
        self.assertEqual(probe['result']['synthetic_forward_count'], 3)

    def test_wait_unpublished_freeze_cannot_even_cleanup_prior_services(self):
        queue = self.queue()
        with patch.object(s.c, 'require_execution_freeze', side_effect=ValueError('not published')):
            with patch.object(queue, 'cleanup_prior') as cleanup:
                with self.assertRaisesRegex(ValueError, 'not published'): queue.wait()
                cleanup.assert_not_called()

    def test_cuda_snapshot_claims_only_saved_host_ancestry_and_marks_basic_limits(self):
        uid = os.getuid()
        def state(pid, ppid, start, *, owner=uid):
            return dict(pid=pid, ppid=ppid, uid=owner, start_ticks=start, state='S', pgid=pid, sid=pid)
        identities = {100: state(100, 1, 1000), 110: state(110, 100, 1100),
                      200: state(200, 1, 2000), 210: state(210, 200, 2100),
                      300: state(300, 1, 3000, owner=uid+1), 1: state(1, 0, 1, owner=0)}
        processes = [(role, None, {'identity': identities[pid]}, self.root/role)
                     for role, pid in [('main', 100), ('judge', 200)]]
        def query(command):
            if '--query-gpu=index,uuid' in command:
                return '0,GPU-0\n1,GPU-1\n2,GPU-2\n'
            return 'GPU-2,110,ours-main,100\nGPU-1,210,ours-judge,100\nGPU-0,300,foreign,100\nGPU-1,999,[Not Found],100\n'
        observed_full = []
        def full(pid):
            observed_full.append(pid)
            return {**identities[pid], 'cwd': '/actual/visible', 'argv': ['actual']} if pid == 110 else None
        result = s.cuda_ownership_snapshot(processes, query=query,
            observe_basic=lambda pid: identities.get(pid), observe_full=full)
        records = {r['pid']: r for r in result['records']}
        self.assertEqual({pid for pid, r in records.items() if r['claimed_owned']}, {110, 210})
        self.assertEqual(records[110]['owned_role'], 'main')
        self.assertEqual(records[210]['owned_role'], 'judge')
        self.assertEqual(records[210]['identity_scope'], 'basic_only_cwd_or_argv_unavailable')
        self.assertEqual(observed_full, [110, 210])
        self.assertFalse(records[300]['claimed_owned'])
        self.assertFalse(records[999]['claimed_owned'])
        self.assertFalse(result['signals_sent'])

    def test_controller_spawn_records_cuda_snapshot_before_actual_process_creation(self):
        queue = self.queue(); session = self.root/'session'; session.mkdir()
        snapshot = {'fixture': 'observational only'}
        def spawn(this, role, command, env, directory):
            self.assertEqual(s.c.read(session/'cuda_ownership.json'), snapshot)
            return 'synthetic-process'
        with patch.object(s, 'cuda_ownership_snapshot', return_value=snapshot), \
                patch.object(s.base.Queue, 'spawn', spawn):
            self.assertEqual(queue.spawn('controller', ['fake'], {}, session), 'synthetic-process')

    def test_retitle_is_not_exit_and_permission_error_is_not_absence(self):
        saved = {'pid': 123, 'start_ticks': 10}
        current = dict(pid=123, start_ticks=10, state='S', argv=['retitled'])
        result = s.leader_exit_observation(saved, observe=lambda pid: current)
        self.assertFalse(result['leader_exited'])
        self.assertEqual(result['evidence'], 'same_start_ticks_still_alive')
        def permission(pid): raise PermissionError('synthetic')
        self.assertFalse(s.leader_exit_observation(saved, observe=permission)['leader_exited'])
        for observed in (None, {**current, 'state': 'Z'}, {**current, 'start_ticks': 11}):
            self.assertTrue(s.leader_exit_observation(saved, observe=lambda pid: observed)['leader_exited'])

    def shutdown_fixture(self):
        queue = self.queue(); directory = self.root/'session/judge'; directory.mkdir(parents=True)
        legacy = {'signal_sent': 'SIGTERM', 'leader_exited': False, 'ownership_mismatch': True}
        s.c.write(directory/'shutdown.json', legacy)
        before = (directory/'shutdown.json').read_bytes()
        saved = {'pid': 123, 'uid': os.getuid(), 'start_ticks': 10}
        process = SimpleNamespace(poll=lambda: None)
        queue.processes = [('judge', process, {'identity': saved}, directory)]
        def original(this):
            this.processes = []; this.streams = []
            return {'judge': legacy}
        return queue, directory, before, original

    def test_shutdown_preserves_original_warning_then_observes_retitle_exit_no_extra_signal(self):
        queue, directory, before, original = self.shutdown_fixture()
        observed = [dict(pid=123, start_ticks=10, state='S'), None]
        now = [0.]
        def sleeper(delay): now[0] += delay
        with patch.object(s.base.Queue, 'shutdown', original), \
                patch.object(s.base, 'stop_owned', side_effect=AssertionError('no additional signal')):
            result = queue.shutdown(observe=lambda pid: observed.pop(0),
                clock=lambda: now[0], sleeper=sleeper,
                cuda_snapshotter=lambda _: {'status':'OBSERVED','records':[],
                    'gpu_inventory':{},'errors':[]})
        self.assertEqual((directory/'shutdown.json').read_bytes(), before)
        self.assertTrue(result['judge']['leader_exited'])
        self.assertFalse(result['judge']['original_leader_exited'])
        self.assertTrue(result['judge']['original_warning_preserved'])
        value = s.c.read(result['judge']['actual_exit_verification'])
        self.assertEqual(value['exit_evidence'], 'proc_disappeared')
        self.assertFalse(value['additional_signals_sent'])
        self.assertEqual(len(value['observations']), 2)

    def test_shutdown_same_start_ticks_still_alive_does_not_turn_warning_into_success(self):
        queue, directory, before, original = self.shutdown_fixture()
        now = [0.]
        def sleeper(delay): now[0] += delay
        with patch.object(s.base.Queue, 'shutdown', original):
            result = queue.shutdown(wait_seconds=.5,
                observe=lambda pid: dict(pid=123, start_ticks=10, state='S', argv=['retitled']),
                clock=lambda: now[0], sleeper=sleeper,
                cuda_snapshotter=lambda _: {'status':'OBSERVED','records':[],
                    'gpu_inventory':{},'errors':[]})
        self.assertFalse(result['judge']['leader_exited'])
        self.assertEqual((directory/'shutdown.json').read_bytes(), before)
        value = s.c.read(result['judge']['actual_exit_verification'])
        self.assertEqual(value['exit_evidence'], 'same_start_ticks_still_alive')

    def test_three_existing_lifetime_sessions_reject_before_gpu_queries_or_cleanup(self):
        queue, ctrl = self.queue(), Controller()
        for number in range(3): (queue.out/'sessions'/str(number)).mkdir(parents=True)
        s.c.write(queue.run_dir/'progress.json', {'phase': 'ready'})
        with patch.object(s.c, 'require_execution_freeze', return_value={}), \
                patch.object(queue, 'ready', return_value=ctrl), \
                patch.object(queue, 'cleanup_prior') as cleanup, \
                patch.object(s.base, 'gpu_inventory', side_effect=AssertionError('no GPU query')), \
                patch.object(queue, 'spawn', side_effect=AssertionError('no process spawn')):
            with self.assertRaisesRegex(RuntimeError, 'limit3'): queue.wait()
            cleanup.assert_not_called()

    def test_two_existing_sessions_allow_only_one_more_across_failed_startup(self):
        queue, ctrl = self.queue(), Controller()
        for number in range(2): (queue.out/'sessions'/str(number)).mkdir(parents=True)
        s.c.write(queue.run_dir/'progress.json', {'phase': 'ready'})
        class Gate:
            def observe(self, *args): return {'ready': True, 'chosen': (2, 3), 'idle_seconds': 90}
        with patch.object(s.c, 'require_execution_freeze', return_value={}), \
                patch.object(queue, 'ready', return_value=ctrl), patch.object(queue, 'cleanup_prior'), \
                patch.object(s.base, 'gpu_inventory', return_value=[]), \
                patch.object(s.base, 'IdleGate', Gate), patch.object(s.base.gpu_spare, 'SpareGate', Gate), \
                patch.object(s.base.gpu_spare, 'observe_spare', return_value={}), \
                patch.object(queue, 'execute', side_effect=RuntimeError('synthetic startup failure')) as execute, \
                patch.object(queue, 'shutdown', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'startup failure'): queue.wait()
            execute.assert_called_once()
        self.assertEqual(queue.session_count(), 3)
        admissions = list((queue.out/'sessions').glob('*/lifetime_admission.json'))
        self.assertEqual(len(admissions), 1)
        self.assertEqual(s.c.read(admissions[0])['session_ordinal'], 3)

    def test_all_terminal_with_three_sessions_can_finish_without_new_launch(self):
        queue, ctrl = self.queue(), Controller()
        for number in range(3): (queue.out/'sessions'/str(number)).mkdir(parents=True)
        s.c.write(queue.run_dir/'progress.json', completed())
        with patch.object(s.c, 'require_execution_freeze', return_value={}), \
                patch.object(queue, 'ready', return_value=ctrl), patch.object(queue, 'cleanup_prior'), \
                patch.object(s.base, 'gpu_inventory', side_effect=AssertionError('no GPU query')):
            self.assertEqual(queue.wait()['phase'], 'DONE_NO_NEW_WORK')

    def test_new_source_inventory_change_denies_queue_launch(self):
        queue = self.queue()
        with patch.object(s.c, 'package_sources', return_value={'different.py': 'b'*64}):
            with self.assertRaises(ValueError): queue.verify_plan_now()

    def test_failed_main_only_shutdown_records_pre_and_post_cuda_observations(self):
        queue=self.queue();directory=self.root/'session/main';directory.mkdir(parents=True)
        saved={'pid':123,'start_ticks':10,'uid':os.getuid()}
        receipt={'identity':saved};s.c.write(directory/'ownership.json',receipt)
        queue.processes=[('main',SimpleNamespace(poll=lambda:1),receipt,directory)]
        captures=[]
        def camera(items):
            captures.append([item[0] for item in items])
            return {'status':'OBSERVED','errors':[],'gpu_inventory':{'g0':0,'g1':1,'g2':2,'g3':3},
                    'records':[{'pid':999999,'gpu_index':0,'claimed_owned':False}]}
        def shutdown(this):this.processes=[];return {'main':{'leader_exited':True}}
        with patch.object(s.base.Queue,'shutdown',shutdown):
            queue.shutdown(observe=lambda _:None,cuda_snapshotter=camera)
        self.assertEqual(captures,[['main'],['main']])
        snapshots=[s.c.read(p) for p in directory.parent.glob('cuda_ownership*.json')]
        self.assertEqual({x['observation_phase'] for x in snapshots},{'before_shutdown','after_shutdown'})
        for snapshot in snapshots:
            self.assertEqual(snapshot['started_roles'],['main'])
            self.assertNotIn('judge',snapshot['role_observations'])
            self.assertTrue(snapshot['role_observations']['main']['no_compute_on_expected_devices'])
            self.assertFalse(snapshot['records'][0]['claimed_owned'])
            self.assertFalse(snapshot['signals_sent_by_observer'])

    def test_incomplete_nvml_query_cannot_supply_negative_cuda_evidence(self):
        directory=self.root/'session/main';directory.mkdir(parents=True)
        receipt={'identity':{'pid':123,'start_ticks':10}};s.c.write(directory/'ownership.json',receipt)
        items=[('main',None,receipt,directory)]
        for snapshot in [
            {'status':'OBSERVATION_PARTIAL','errors':['unavailable'],'records':[],
             'gpu_inventory':{'g2':2,'g3':3}},
            {'status':'OBSERVED','errors':[],'records':[],'gpu_inventory':{'g2':2}},
            {'status':'OBSERVED','errors':[],'records':[{'gpu_index':None}],
             'gpu_inventory':{'g2':2,'g3':3}}]:
            self.assertFalse(s.role_cuda_observations(snapshot,items)['main']['no_compute_on_expected_devices'])


if __name__ == '__main__':
    unittest.main()
