"""CPU engineering fixtures. Their output is never a localization result."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import controller as c


class FakeBackend(c.FrozenBackend):
    simulation = True

    def __init__(self, count, *, fail_baseline=False):
        self.count, self.fail_baseline = str(count), fail_baseline

    def protocol(self):
        return {'fake_worker': 'CPU fixture only', 'fail_baseline': self.fail_baseline}

    def check_services(self, model_dir, judge_socket, out):
        return {'simulation': True, 'no_model_services_contacted': True}

    def command(self, arm, staged, snapshot, armout, runtime):
        program = '''import json,sys,time
from pathlib import Path
job=json.loads(Path(sys.argv[1]).read_text());arm=sys.argv[2]
with Path(sys.argv[4]).open('a') as f:f.write(arm+'\\n')
time.sleep(.03)
result={k:job[k] for k in ('instance_id','repo','base_commit')}
result.update(arm=arm,status='failed' if sys.argv[5]=='yes' and arm=='baseline' else 'complete',simulation=True)
if not (sys.argv[5]=='yes' and arm=='baseline'):
 result.update(ranked_edit_files=['m.py'],file_rank_after_reflection=['m.py'],raw_file_responses=['synthetic fixture only'])
Path(sys.argv[3]).write_text(json.dumps(result))
'''
        return [sys.executable, '-B', '-c', program, str(staged / 'job.json'), arm,
                str(armout / 'result.json'), self.count, 'yes' if self.fail_baseline else 'no']


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sfpruner300-cpu-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        inputs = self.root / 'inputs'; task = inputs / 'task'; task.mkdir(parents=True)
        repo = task / 'snapshot'; repo.mkdir(); (repo / 'm.py').write_text('def f():\n    return 1\n')
        self.iid, self.base = 'fixture__repo-1', 'a' * 40
        index = {'m.py': {'raw_sha256': c.sha(repo / 'm.py')}}
        (task / 'index.json').write_text(json.dumps(index))
        (task / 'structure.json').write_text('{}')
        (task / 'render_cache.json').write_text('{}')
        self.job = task / 'job.json'
        self.public = {'instance_id': self.iid, 'repo': 'fixture/repo', 'base_commit': self.base,
                       'problem_statement': 'Synthetic controller wiring only.', 'cohort': 'cpu-fixture',
                       'snapshot': 'snapshot', 'paths': ['m.py'],
                       'code_index': 'index.json', 'structure': 'structure.json'}
        self.job.write_text(json.dumps(self.public))
        self.manifest = inputs / 'manifest.json'
        self.record = {'instance_id': self.iid, 'repo': 'fixture/repo', 'base_commit': self.base,
                       'job': 'task/job.json', 'job_sha256': c.sha(self.job)}
        self.manifest.write_text(json.dumps({'schema': 1, 'n': 1, 'records': [self.record]}))
        self.out = self.root / 'output'; self.count = self.root / 'fake_invocations.txt'

    def controller(self, backend=None):
        return c.Controller(self.manifest, self.out, backend=backend or FakeBackend(self.count), heartbeat_seconds=.01)

    def pair(self):
        return self.out / 'pairs' / self.iid

    def test_real_staging_fake_execution_and_resume_never_duplicate_calls(self):
        ctrl = self.controller(); ctrl.prepare(); ctrl.run(None, None)
        self.assertEqual(self.count.read_text().splitlines(), ['baseline', 'hybrid_safe'])
        original = c.sha(self.pair() / 'baseline/result.json')
        self.controller().prepare(); self.controller().run(None, None)
        self.assertEqual(self.count.read_text().splitlines(), ['baseline', 'hybrid_safe'])
        self.assertEqual(c.sha(self.pair() / 'baseline/result.json'), original)
        self.assertEqual(c.read(self.out / 'progress.json')['terminal_pairs'], 1)
        self.assertTrue(c.read(self.out / 'freeze.json')['simulation'])

    def test_completed_baseline_resumes_only_unstarted_hybrid(self):
        ctrl = self.controller(); ctrl.prepare()
        ctrl.execute_arm(ctrl.records[0], 'baseline', {'simulation': True})
        ctrl.shared(ctrl.records[0])
        self.assertEqual(self.count.read_text().splitlines(), ['baseline'])
        self.controller().run(None, None)
        self.assertEqual(self.count.read_text().splitlines(), ['baseline', 'hybrid_safe'])

    def test_file_stage_failure_blocks_hybrid_without_any_hybrid_call(self):
        ctrl = self.controller(FakeBackend(self.count, fail_baseline=True)); ctrl.prepare(); ctrl.run(None, None)
        self.assertEqual(self.count.read_text().splitlines(), ['baseline'])
        state = c.read(self.pair() / 'hybrid_safe/terminal.json')
        self.assertEqual(state['status'], 'dependency_blocked')
        self.assertFalse(state['model_called'])
        self.assertTrue(state['keep_in_denominator'])

    def test_started_missing_result_is_interrupted_without_semantic_replay(self):
        ctrl = self.controller(); ctrl.prepare()
        directory = self.pair() / 'baseline'; directory.mkdir()
        c.write(directory / 'started.json', {'protocol_sha256': ctrl.protocol_sha}, immutable=True)
        ctrl.run(None, None)
        self.assertFalse(self.count.exists())
        self.assertEqual(c.read(directory / 'terminal.json')['status'], 'interrupted')
        self.assertEqual(c.read(self.pair() / 'hybrid_safe/terminal.json')['status'], 'dependency_blocked')

    def test_shared_gate_matches_frozen_ranked_edit_files_qualification(self):
        ctrl = self.controller(); ctrl.prepare()
        directory = self.pair() / 'baseline'; directory.mkdir()
        c.write(directory / 'started.json', {'protocol_sha256': ctrl.protocol_sha}, immutable=True)
        c.write(directory / 'result.json', {'instance_id': self.iid, 'repo': 'fixture/repo',
                'base_commit': self.base, 'status': 'failed', 'file_rank_after_reflection': ['m.py'],
                'raw_file_responses': ['not enough without ranked_edit_files']}, immutable=True)
        ctrl.run(None, None)
        self.assertFalse(self.count.exists())
        self.assertEqual(c.read(self.pair() / 'hybrid_safe/terminal.json')['status'], 'dependency_blocked')

    def test_job_identity_and_protocol_drift_refuse_resume(self):
        ctrl = self.controller(); ctrl.prepare()
        self.public['base_commit'] = 'b' * 40
        self.job.write_text(json.dumps(self.public))
        with self.assertRaisesRegex(ValueError, 'job SHA'):
            self.controller()
        self.record.update(base_commit='b' * 40, job_sha256=c.sha(self.job))
        self.manifest.write_text(json.dumps({'n': 1, 'records': [self.record]}))
        with self.assertRaisesRegex(ValueError, 'protocol drift'):
            self.controller().run(None, None)
        self.assertFalse(self.count.exists())

    def test_snapshot_and_private_mount_contamination_fail_closed(self):
        ctrl = self.controller(); ctrl.prepare()
        private = self.pair() / '_public_inputs/gold.json'; private.write_text('{"secret":true}')
        with self.assertRaisesRegex(ValueError, 'private files'):
            ctrl.run(None, None)
        private.unlink()
        (self.job.parent / 'snapshot/m.py').write_text('def f():\n    return 99\n')
        with self.assertRaisesRegex(ValueError, 'source bytes changed'):
            ctrl.run(None, None)
        self.assertFalse(self.count.exists())

    def test_shared_stage_tampering_rejected_before_new_arm(self):
        ctrl = self.controller(); ctrl.prepare()
        ctrl.execute_arm(ctrl.records[0], 'baseline', {'simulation': True}); ctrl.shared(ctrl.records[0])
        shared = self.pair() / '_public_inputs/shared.json'
        data = c.read(shared); data['files'] = ['wrong.py']; shared.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Immutable artifact changed'):
            self.controller().run(None, None)
        self.assertEqual(self.count.read_text().splitlines(), ['baseline'])

    def test_completed_prediction_bytes_are_immutable(self):
        ctrl = self.controller(); ctrl.prepare(); ctrl.run(None, None)
        result = self.pair() / 'hybrid_safe/result.json'
        result.write_text(result.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'model output changed'):
            self.controller().run(None, None)

    def test_manifest_private_fields_path_escape_and_duplicate_ids_rejected(self):
        for change in ({'gold': ['m.py::f']}, {'job': '../job.json'}):
            row = {**self.record, **change}
            self.manifest.write_text(json.dumps({'n': 1, 'records': [row]}))
            with self.assertRaises(ValueError): self.controller()
        self.manifest.write_text(json.dumps({'n': 2, 'records': [self.record, self.record]}))
        with self.assertRaisesRegex(ValueError, 'Duplicate issue'):
            self.controller()

    def test_unknown_or_reused_process_is_never_signalled(self):
        owner = {'pid': 1234, 'uid': c.os.getuid(), 'pgid': 1234, 'sid': 1234,
                 'start_ticks': 42, 'cmdline_sha256': 'a', 'state': 'S'}
        signals = []
        for observed in (None, {**owner, 'start_ticks': 43}, {**owner, 'uid': owner['uid'] + 1}):
            receipt = c.signal_owned(owner, observe=lambda pid: observed, send=lambda *args: signals.append(args))
            self.assertFalse(receipt['signal_sent'])
        self.assertFalse(signals)
        receipt = c.signal_owned(owner, observe=lambda pid: owner, send=lambda *args: signals.append(args))
        self.assertEqual(receipt['signal_sent'], 'SIGTERM')
        self.assertEqual(signals, [(1234, c.signal.SIGTERM)])

    def test_fake_and_real_profiles_cannot_share_output(self):
        ctrl = self.controller(); ctrl.prepare()
        other = self.controller(FakeBackend(self.count, fail_baseline=True))
        with self.assertRaisesRegex(ValueError, 'Immutable artifact changed'):
            other.prepare()


if __name__ == '__main__':
    unittest.main()
