"""Real tiny CPU child processes test durable ownership and never-replay."""
from contextlib import contextmanager
from pathlib import Path
import json
import shutil
import subprocess
import sys
import unittest
from unittest import mock

from . import controller as ctl
from . import common as c
from .test_prepare import fixture


class FakeBackend:
    simulation = True

    def __init__(self):
        self.commands = []

    def protocol(self):
        return {'simulation': True, 'backend': 'tiny CPU process, no model or GPU'}

    def check_services(self, *unused):
        return {'simulation': True}

    def command(self, arm, staged, snapshot, out, runtime):
        self.commands.append(arm)
        job = c.read(staged / 'job.json')
        value = {k: job[k] for k in ('instance_id', 'repo', 'base_commit')}
        value.update(status='complete', arm=c.INTERNAL_ARM, internal_arm=c.INTERNAL_ARM,
                     experimental_arm=arm, simulation=True)
        program = ('import json,sys,time; from pathlib import Path; time.sleep(.08); '
                   'Path(sys.argv[1]).write_text(json.dumps(json.loads(sys.argv[2])))')
        return [sys.executable, '-B', '-c', program, str(out / 'result.json'), json.dumps(value)]


@contextmanager
def controller_fixture(blocked=False):
    with fixture() as (base, old_stage, identity, job, old_prepared, old_result):
        root = base / 'new'
        root.mkdir()
        c.write(root / 'protocol.json', {'experiment_id': 'locbench_qwen3_sfpruner_ablation_20261117',
            'root': str(root), 'parent': str(base / 'old'), 'n': 1, 'allocated': 1,
            'arms': list(c.ARMS)})
        source_job = base / 'source_job.json'
        c.write(source_job, job)
        source = c.original.source_receipt(source_job)
        public_receipt = c.read(old_stage / 'public_receipt.json')
        public_receipt['original_job_sha256'] = source['job_sha256']
        c.write(old_stage / 'public_receipt.json', public_receipt)
        stage = root / 'inputs' / identity['instance_id']
        shutil.copytree(old_stage, stage)
        upstream = base / 'upstream.json'
        c.write(upstream, {'public_file_stage': True})
        receipt = root / 'prepared_receipts' / (identity['instance_id'] + '.json')
        c.write(receipt, {'source_receipt': source})
        row = {**identity, 'rank': 1, 'source_job_path': str(source_job),
            'source_snapshot': job['snapshot'], 'prepared_receipt_path': str(receipt),
            'public_input_path': str(stage), 'public_files_sha256': c.hashes_under(stage),
            'upstream_files_sha256': {str(upstream): c.sha(upstream)},
            'upstream_status': 'ready', 'no_model_dispatch': False}
        if blocked:
            row.update(upstream_status='source_preparation_blocked', no_model_dispatch=True,
                       public_input_path=None, public_files_sha256={},
                       upstream_reason={'explicit_original_source_failure': True})
        c.write(root / 'manifest.json', {'n': 1, 'allocated': 1, 'arms': list(c.ARMS), 'records': [row]})
        c.write(root / 'authority.json', {'manifest_sha256': c.sha(root / 'manifest.json'),
            'protocol_sha256': c.sha(root / 'protocol.json'),
            'files_sha256': {str(receipt): c.sha(receipt)}})
        backend = FakeBackend()
        ctrl = ctl.Controller(root, backend=backend, expected_n=1, heartbeat_seconds=.02)
        ctrl.prepare()
        yield ctrl, row, backend


class ControllerTests(unittest.TestCase):
    def test_new_arms_run_once_without_new_baseline_and_keep_internal_identity(self):
        with controller_fixture() as (ctrl, row, backend):
            ctrl.run_group(row, {})
            before = {str(p): c.sha(p) for p in ctrl.pair(row).rglob('*') if p.is_file()}
            ctrl.run_group(row, {})
            self.assertEqual(backend.commands, c.arm_order(row['instance_id']))
            self.assertEqual(len(backend.commands), 3)
            for arm in c.ARMS:
                self.assertEqual(ctrl.arm_state(row, arm)['status'], 'complete')
                result = c.read(ctrl.pair(row) / arm / 'result.json')
                self.assertEqual(result['arm'], 'hybrid_safe')
                self.assertEqual(result['experimental_arm'], arm)
            self.assertTrue(all(c.sha(path) == value for path, value in before.items()))

    def test_prior_started_dead_worker_is_interrupted_and_never_replayed(self):
        with controller_fixture() as (ctrl, row, backend):
            arm = c.ARMS[0]
            c.write(ctrl.pair(row) / arm / 'started.json', {'protocol_sha256': ctrl.protocol_sha,
                'arm': arm, 'instance_id': row['instance_id']})
            ctrl.execute_arm(row, arm, {})
            self.assertEqual(ctrl.arm_state(row, arm)['status'], 'interrupted')
            self.assertEqual(backend.commands, [])

    def test_live_owned_preexisting_worker_cannot_be_relaunched(self):
        with controller_fixture() as (ctrl, row, backend):
            arm = c.ARMS[0]; directory = ctrl.pair(row) / arm
            c.write(directory / 'started.json', {'protocol_sha256': ctrl.protocol_sha,
                'arm': arm, 'instance_id': row['instance_id']})
            owner = {'pid': 123, 'start_ticks': 10, 'uid': 1, 'sid': 123, 'pgid': 123, 'state': 'S'}
            c.write(directory / 'process.json', owner)
            with mock.patch.object(ctl.c, 'current_process', return_value=owner):
                with self.assertRaisesRegex(RuntimeError, 'remains live'):
                    ctrl.execute_arm(row, arm, {})
            self.assertEqual(backend.commands, [])

    def test_public_input_and_upstream_drift_fail_before_dispatch(self):
        with controller_fixture() as (ctrl, row, backend):
            (Path(row['public_input_path']) / 'gold.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Public inputs'):
                ctrl.execute_arm(row, c.ARMS[0], {})
            self.assertEqual(backend.commands, [])

    def test_blocked_upstream_has_three_explicit_no_call_terminals(self):
        with controller_fixture(blocked=True) as (ctrl, row, backend):
            self.assertEqual(ctrl.progress('prepared')['terminal_pairs'], 1)
            for arm in c.ARMS:
                value = ctrl.arm_state(row, arm)
                self.assertFalse(value['model_called'])
                self.assertEqual(value['status'], 'source_preparation_blocked')
                self.assertFalse((ctrl.pair(row) / arm / 'started.json').exists())
            self.assertEqual(backend.commands, [])

    def test_checkpoint_requires_group_receipt_not_just_three_terminals(self):
        with controller_fixture(blocked=True) as (ctrl, row, backend):
            (ctrl.pair(row) / 'group_terminal.json').unlink()
            with mock.patch.object(ctl, 'CHECKPOINTS', (1,)):
                self.assertEqual(ctrl.progress('running')['terminal_pairs'], 0)
                self.assertFalse((ctrl.root / 'controller/checkpoints/1.json').exists())
                ctrl.group_terminal(row)
                self.assertEqual(ctrl.progress('running')['terminal_pairs'], 1)
                self.assertTrue((ctrl.root / 'controller/checkpoints/1.json').exists())

    def test_resume_rebuilds_missing_group_without_replaying_completed_arms(self):
        with controller_fixture() as (ctrl, row, backend):
            ctrl.run_group(row, {})
            group = ctrl.pair(row) / 'group_terminal.json'
            previous = c.sha(group)
            group.unlink()
            self.assertEqual(ctrl.progress('running')['terminal_pairs'], 0)
            with mock.patch.object(backend, 'check_services', side_effect=AssertionError('No service needed')):
                ctrl.run(None, None)
            self.assertEqual(c.sha(group), previous)
            self.assertEqual(len(backend.commands), 3)
            self.assertEqual(c.read(ctrl.out / 'progress.json')['terminal_pairs'], 1)

    def test_result_cannot_be_closed_while_saved_worker_is_still_live(self):
        with controller_fixture() as (ctrl, row, backend):
            ctrl.execute_arm(row, c.ARMS[0], {})
            directory = ctrl.pair(row) / c.ARMS[0]
            saved = c.read(directory / 'process.json')
            # Even an argv change does not imply the original PID exited.
            changed = {**saved, 'state': 'S', 'cmdline_sha256': 'retitled'}
            with mock.patch.object(ctl.c, 'current_process', return_value=changed):
                with self.assertRaisesRegex(RuntimeError, 'premature terminal'):
                    ctrl.arm_state(row, c.ARMS[0])

    def test_timeout_terminal_waits_for_worker_exit(self):
        with controller_fixture() as (ctrl, row, backend):
            class Child:
                pid = 123
                returncode = None
                def poll(self): return self.returncode
                def wait(self, timeout):
                    self.returncode = -15
                    return self.returncode
            child = Child()
            owner = {'pid': 123, 'uid': 1, 'pgid': 123, 'sid': 123,
                     'state': 'S', 'start_ticks': 10, 'cmdline_sha256': 'saved'}
            actual_terminal = ctrl.terminal
            def checked_terminal(*args, **kwargs):
                self.assertIsNotNone(child.poll())
                return actual_terminal(*args, **kwargs)
            ticks = iter((0., 4000., 4001.))
            with mock.patch.object(ctl.subprocess, 'Popen', return_value=child), \
                    mock.patch.object(ctl.c, 'current_process', return_value=owner), \
                    mock.patch.object(ctl.c, 'signal_owned', return_value={'signal_sent': 'SIGTERM'}), \
                    mock.patch.object(ctl.time, 'monotonic', side_effect=lambda: next(ticks)), \
                    mock.patch.object(ctrl, 'terminal', side_effect=checked_terminal):
                ctrl.execute_arm(row, c.ARMS[0], {})
            self.assertEqual(ctrl.arm_state(row, c.ARMS[0])['status'], 'timed_out')

    def test_unresolved_timeout_stops_dispatch_without_terminal_or_group(self):
        with controller_fixture() as (ctrl, row, backend):
            class Child:
                pid = 123
                returncode = None
                def poll(self): return None
                def wait(self, timeout): raise subprocess.TimeoutExpired('synthetic', timeout)
            owner = {'pid': 123, 'uid': 1, 'pgid': 123, 'sid': 123,
                     'state': 'S', 'start_ticks': 10, 'cmdline_sha256': 'saved'}
            ticks = iter((0., 4000., 4001.))
            with mock.patch.object(ctl.subprocess, 'Popen', return_value=Child()), \
                    mock.patch.object(ctl.c, 'current_process', return_value=owner), \
                    mock.patch.object(ctl.c, 'signal_owned', return_value={'signal_sent': 'SIGTERM'}), \
                    mock.patch.object(ctl.time, 'monotonic', side_effect=lambda: next(ticks)):
                with self.assertRaisesRegex(RuntimeError, 'exit not confirmed'):
                    ctrl.execute_arm(row, c.ARMS[0], {})
            self.assertFalse((ctrl.pair(row) / c.ARMS[0] / 'terminal.json').exists())
            self.assertFalse((ctrl.pair(row) / 'group_terminal.json').exists())
            self.assertTrue((ctrl.root / 'controller/stop_dispatch.json').exists())
            with self.assertRaisesRegex(RuntimeError, 'Stop dispatch'):
                ctrl.execute_arm(row, c.ARMS[1], {})

    def test_failed_real_canary_does_not_pass_with_no_model_chain(self):
        with controller_fixture(blocked=True) as (ctrl, row, backend):
            backend.simulation = False
            with mock.patch.object(ctrl, 'arm_state', return_value={'status': 'timed_out'}):
                with self.assertRaisesRegex(ValueError, 'lacks a completed real'):
                    ctrl.canary_check([row])

    def test_integrity_stop_marker_does_not_start_more_arms(self):
        with controller_fixture() as (ctrl, row, backend):
            c.write(ctrl.root / 'controller/stop_dispatch.json', {'reason': 'source drift'})
            with self.assertRaisesRegex(RuntimeError, 'Stop dispatch'):
                ctrl.execute_arm(row, c.ARMS[0], {})
            self.assertEqual(backend.commands, [])

    def test_historical_control_cannot_be_dispatched_as_an_ablation(self):
        with controller_fixture() as (ctrl, row, backend):
            with self.assertRaisesRegex(ValueError, 'Historical controls'):
                ctrl.arm_state(row, 'baseline')
            self.assertEqual(backend.commands, [])

    def test_corrupted_completed_result_is_never_silently_reaccepted(self):
        with controller_fixture() as (ctrl, row, backend):
            arm = c.ARMS[0]
            ctrl.execute_arm(row, arm, {})
            path = ctrl.pair(row) / arm / 'result.json'
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'output changed'):
                ctrl.arm_state(row, arm)

    def test_mini_scope_requires_explicit_simulated_backend(self):
        with self.assertRaisesRegex(ValueError, 'synthetic test'):
            ctl.Controller('/not_used', expected_n=1)

    def test_full_tiny_run_has_a_structural_canary_without_Gold(self):
        with controller_fixture() as (ctrl, row, backend):
            ctrl.run(None, None)
            self.assertEqual(c.read(ctrl.out / 'progress.json')['phase'], 'complete')
            gate = c.read(ctrl.root / 'controller/canary_gate.json')
            self.assertFalse(gate['accuracy_or_Gold_used_for_gate'])
            self.assertTrue(gate['simulation'])


if __name__ == '__main__':
    unittest.main()
