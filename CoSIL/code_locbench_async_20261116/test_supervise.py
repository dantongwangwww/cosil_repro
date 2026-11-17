import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest import mock

from . import handoff_signal as h, supervise as s


class HandoffSafety(unittest.TestCase):
    def fixture(self):
        root = Path('/tmp/synthetic-continuation')
        command = ['python', '-B', '-m', 'code_locbench_full_20261116.supervise', '--root', str(root)]
        identity = {'pid': 123456, 'uid': os.getuid(), 'state': 'S', 'pgid': 123456,
            'sid': 123456, 'start_ticks': 34, 'cmdline_sha256': 'abc',
            'argv': command, 'cwd': str(s.ROOT)}
        return root, {'identity': dict(identity), 'command': command, 'cwd': str(s.ROOT)}, identity

    def test_pidfd_targets_only_exact_old_monitor(self):
        root, receipt, identity = self.fixture()
        opener, sender, closer = mock.Mock(return_value=45), mock.Mock(), mock.Mock()
        result = h.stop_monitor(receipt, root, observe=lambda pid: identity,
            opener=opener, sender=sender, closer=closer)
        opener.assert_called_once_with(identity['pid'], 0)
        sender.assert_called_once_with(45, signal.SIGKILL, None, 0)
        closer.assert_called_once_with(45)
        self.assertFalse(result['killpg_used'])
        self.assertFalse(result['queue_model_worker_signals'])

    def test_reused_pid_is_never_signaled(self):
        root, receipt, identity = self.fixture(); identity['start_ticks'] += 1
        opener, sender = mock.Mock(), mock.Mock()
        with self.assertRaisesRegex(RuntimeError, 'identity check failed'):
            h.stop_monitor(receipt, root, observe=lambda pid: identity, opener=opener, sender=sender)
        opener.assert_not_called(); sender.assert_not_called()

    def test_identity_changes_after_pidfd_open_are_rejected(self):
        root, receipt, identity = self.fixture()
        changed = dict(identity, start_ticks=999); observations = iter([identity, changed])
        sender, closer = mock.Mock(), mock.Mock()
        with self.assertRaisesRegex(RuntimeError, 'after opening'):
            h.stop_monitor(receipt, root, observe=lambda pid: next(observations),
                opener=lambda *args: 45, sender=sender, closer=closer)
        sender.assert_not_called(); closer.assert_called_once_with(45)

    def test_queue_or_worker_command_can_never_match_monitor(self):
        root, receipt, identity = self.fixture()
        receipt['command'][3] = 'code_locbench_sfpruner_20261116.queue'
        self.assertFalse(h.expected(receipt, root, identity))

    def test_foreign_uid_or_wrong_session_cannot_match(self):
        root, receipt, identity = self.fixture()
        self.assertFalse(h.expected(receipt, root, dict(identity, uid=os.getuid()+1)))
        self.assertFalse(h.expected(receipt, root, dict(identity, pgid=1)))


class AsyncScheduling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_reporting_in_progress_does_not_block_the_next_gpu_batch(self):
        specs = [{'name': 'batch01', 'index': 1, 'n': 100, 'work': str(self.root/'batch01')},
                 {'name': 'batch02', 'index': 2, 'n': 100, 'work': str(self.root/'batch02')}]
        s.c.write(self.root/'reports/async_status.json', {'phase': 'REPORTING_CUMULATIVE'})
        events = []; reporter = mock.Mock()
        reporter.wait.side_effect = AssertionError('GPU scheduling must not wait for CPU reports')
        def ready(root, spec, frozen):
            events.append('prepare:'+spec['name']); return {'runnable': 100}
        def launch(root, spec, attempt, frozen, **kw):
            events.append('infer:'+spec['name']); return {'counts': {'all_terminal': True}}
        def done(work, spec, attempts, frozen):
            events.append('gpu_done:'+spec['name']); return {'runnable': 100}
        with mock.patch.object(s.old, 'verify_hashes'), mock.patch.object(s.old, 'update'), \
             mock.patch.object(s, 'ready_for_batch', side_effect=ready), \
             mock.patch.object(s.old, 'launch_queue', side_effect=launch), \
             mock.patch.object(s, 'gpu_completion', side_effect=done):
            result = s.model_batches(self.root, {'batches': specs}, {'files_sha256': {}}, reporter)
        self.assertEqual(events, ['prepare:batch01','infer:batch01','gpu_done:batch01',
                                  'prepare:batch02','infer:batch02','gpu_done:batch02'])
        reporter.wait.assert_not_called(); self.assertEqual(len(result), 2)

    def test_fatal_integrity_error_blocks_a_new_batch(self):
        s.c.write(self.root/'reports/async_status.json', {'phase': 'FATAL_INTEGRITY_ERROR'})
        spec = {'name':'batch01','work':str(self.root/'batch01')}
        with mock.patch.object(s.old, 'verify_hashes'), mock.patch.object(s.old, 'launch_queue') as launch:
            with self.assertRaisesRegex(RuntimeError, 'integrity error'):
                s.model_batches(self.root, {'batches':[spec]}, {'files_sha256':{}}, mock.Mock())
        launch.assert_not_called()

    def test_io_report_error_does_not_stop_gpu_scheduling(self):
        s.c.write(self.root/'reports/async_status.json', {'phase':'REPORT_IO_ERROR'})
        spec = {'name':'batch01','work':str(self.root/'batch01')}
        with mock.patch.object(s.old, 'verify_hashes'), mock.patch.object(s.old, 'update'), \
             mock.patch.object(s, 'ready_for_batch', return_value={'runnable':1}), \
             mock.patch.object(s.old, 'launch_queue', return_value={'counts':{'all_terminal':True}}) as launch, \
             mock.patch.object(s, 'gpu_completion', return_value={'runnable':1}):
            s.model_batches(self.root, {'batches':[spec]}, {'files_sha256':{}}, mock.Mock())
        launch.assert_called_once()

    def test_running_prepared_batch_is_not_prepared_again(self):
        work = self.root/'batch01'; s.c.write(work/'protocol.json', {'fake':'protocol'})
        s.c.write(work/'controller/launch_ready.json', {'status':'READY','allocated':100,
            'protocol_sha256':s.c.sha(work/'protocol.json'),'files_sha256':{},'runnable':100})
        with mock.patch.object(s.old, 'prepare_execution') as prepare:
            ready = s.ready_for_batch(self.root, {'work':str(work),'n':100}, {})
        prepare.assert_not_called(); self.assertEqual(ready['runnable'],100)

    def test_prior_gpu_completion_uses_the_full_worker_barrier(self):
        work = self.root/'batch01'; spec={'work':str(work),'n':100}
        with mock.patch('code_locbench_async_20261116.worker.gpu_gate', return_value=({'runnable':99}, {})) as gate, \
             mock.patch.object(s.old, 'release_check', return_value={'all_observed_service_processes_exited':True}):
            result=s.validate_gpu_completion(work,spec)
        gate.assert_called_once_with(self.root,spec); self.assertEqual(result['runnable'],99)

    def test_supervisor_and_worker_use_one_completion_constant(self):
        from .worker import REPORTS_COMPLETE
        self.assertEqual(REPORTS_COMPLETE, 'ALL_REPORTS_COMPLETE')

    def metadata_fixture(self):
        work = self.root/'batch01'; row={'instance_id':'org__repo-1','base_commit':'abc'}
        s.c.write(work/'runtime/runnable_manifest.json', {'n':1,'records':[row]})
        s.c.write(work/'paired_run/freeze.json', {'protocol_sha256':'fixed'})
        pair=work/'paired_run/pairs'/row['instance_id']; terms={}
        for arm in s.c.ARMS:
            s.c.write(pair/arm/'result.json', {'status':'complete','arm':arm})
            terms[arm]={**row,'arm':arm,'status':'complete','protocol_sha256':'fixed',
                'simulation':False,'keep_in_denominator':True,
                'result_sha256':s.c.sha(pair/arm/'result.json')}
            s.c.write(pair/arm/'terminal.json',terms[arm])
        s.c.write(pair/'pair_terminal.json',{'instance_id':row['instance_id'],
            'protocol_sha256':'fixed','arms':terms,'keep_in_denominator':True})
        return work,pair

    def test_light_gpu_gate_checks_protocol_arm_pair_and_result_hashes(self):
        work,pair=self.metadata_fixture()
        self.assertEqual(len(s.terminal_metadata(work)),3)

    def test_light_gpu_gate_rejects_changed_raw_result(self):
        work,pair=self.metadata_fixture()
        s.c.write(pair/'baseline/result.json',{'status':'changed'})
        with self.assertRaisesRegex(ValueError,'result SHA drift'):
            s.terminal_metadata(work)

    def test_light_gpu_gate_rejects_inconsistent_pair(self):
        work,pair=self.metadata_fixture()
        data=s.read(pair/'pair_terminal.json');data['arms']['baseline']['status']='worker_failed'
        s.c.write(pair/'pair_terminal.json',data)
        with self.assertRaisesRegex(ValueError,'Pair terminal'):
            s.terminal_metadata(work)


if __name__ == '__main__':
    unittest.main()
