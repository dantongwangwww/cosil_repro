"""Integration guards use synthetic repositories and never start model services."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from . import supervise as s


class SupervisionGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def put(self, relative, value):
        path = self.root / relative
        s.c.write(path, value)
        return path

    def test_source_hash_drift_is_fatal(self):
        p = self.put('x.json', {'a': 1})
        saved = {str(p): s.c.sha(p)}
        s.verify_hashes(saved)
        p.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            s.verify_hashes(saved)

    def test_publication_cannot_be_missing_commit(self):
        self.put('audits/execution_publication/publication_receipt.json', {'status': 'PASS'})
        with self.assertRaisesRegex(ValueError, 'Published'):
            s.bind_execution(self.root)

    def test_existing_freeze_rejects_changed_membership(self):
        publication = self.put('audits/execution_publication/publication_receipt.json',
            {'status': 'PASS', 'commit': 'synthetic'})
        self.put('plan.json', {'a': 1})
        self.put('controller/execution_freeze.json', {'publication_sha256': s.c.sha(publication),
            'plan_sha256': 'different', 'files_sha256': {}})
        with self.assertRaisesRegex(ValueError, 'membership changed'):
            s.bind_execution(self.root)

    def task_fixture(self, *, target='pkg/a.py::C.f', complete=True, kind='function'):
        source = self.root / 'base/pkg/a.py'
        source.parent.mkdir(parents=True)
        source.write_text('class C:\n    def f(self):\n        return 1\n')
        index = self.put('index.json', {'pkg/a.py': {'raw_sha256': s.c.sha(source),
            'definitions': [{'qualified_name': 'C.f', 'kind': kind}]}})
        identity = {'instance_id': 'org__repo-1', 'repo': 'org/repo', 'base_commit': 'abc'}
        self.put('allocation.json', {'records': [identity]})
        self.put('runtime/runnable_manifest.json', {'n': 1, 'records': [{**identity, 'job': 'jobs/one.json'}]})
        self.put('runtime/jobs/one.json', {})
        self.put('runtime/allocation_status.json', {'allocated': 1, 'runnable': 1, 'blocked': 0})
        self.put('evaluator_private/official_gold.private.json', {identity['instance_id']: {
            'targets': [target], 'gold_files': ['pkg/a.py'], 'set_complete': complete}})
        return {**identity, 'snapshot': str(self.root / 'base'), 'code_index': str(index)}

    def test_source_qualification_validates_exact_existing_target(self):
        job = self.task_fixture()
        with mock.patch.object(s.c, 'load_job', return_value=job):
            gate = s.validate_before_launch(self.root)
        self.assertEqual(gate['qualified_existing_targets'], 1)
        self.assertFalse(gate['gold_scored'])
        self.assertFalse(gate['model_called'])

    def test_source_qualification_rejects_missing_function(self):
        job = self.task_fixture(target='pkg/a.py::C.other')
        with mock.patch.object(s.c, 'load_job', return_value=job):
            with self.assertRaisesRegex(ValueError, 'missing'):
                s.validate_before_launch(self.root)

    def test_class_is_not_a_function_target(self):
        job = self.task_fixture(kind='class')
        with mock.patch.object(s.c, 'load_job', return_value=job):
            with self.assertRaisesRegex(ValueError, 'missing'):
                s.validate_before_launch(self.root)

    def test_incomplete_target_collection_cannot_pass(self):
        job = self.task_fixture(complete=False)
        with mock.patch.object(s.c, 'load_job', return_value=job):
            with self.assertRaisesRegex(ValueError, 'missing'):
                s.validate_before_launch(self.root)

    def test_source_identity_drift_cannot_pass(self):
        job = self.task_fixture()
        job['base_commit'] = 'other'
        with mock.patch.object(s.c, 'load_job', return_value=job):
            with self.assertRaisesRegex(ValueError, 'missing'):
                s.validate_before_launch(self.root)

    def test_changed_base_source_cannot_pass(self):
        job = self.task_fixture()
        (self.root / 'base/pkg/a.py').write_text('modified source')
        with mock.patch.object(s.c, 'load_job', return_value=job):
            with self.assertRaisesRegex(ValueError, 'bytes changed'):
                s.validate_before_launch(self.root)

    def test_release_checks_children_without_sending_signals(self):
        identity = {'pid': 123, 'start_ticks': 2}
        with mock.patch.object(s, 'descendants', return_value={'123:2': identity}), \
             mock.patch.object(s.sq, 'identity', return_value=identity), \
             mock.patch.object(s.c, 'same_process', return_value=True), \
             mock.patch.object(s.os, 'kill') as signal:
            release = s.release_check(self.root, wait_seconds=0)
        self.assertFalse(release['all_observed_service_processes_exited'])
        self.assertEqual(release['still_alive'], [123])
        signal.assert_not_called()

    def test_release_accepts_gone_saved_identity(self):
        with mock.patch.object(s, 'descendants', return_value={'123:2': {'pid': 123}}), \
             mock.patch.object(s.sq, 'identity', return_value=None):
            release = s.release_check(self.root, wait_seconds=0)
        self.assertTrue(release['all_observed_service_processes_exited'])

    def queue_completion_fixture(self):
        self.put('controller/queue_attempt_01/previous_arm_sha256.json', {})
        self.put('controller/queue_attempt_01/completion.json', {
            'counts': {'all_terminal': True}, 'exit_code': 0})
        return {'work': str(self.root), 'name': 'batch01', 'index': 1, 'n': 100}

    def test_cached_completion_cannot_skip_live_child_release_check(self):
        spec = self.queue_completion_fixture()
        with mock.patch.object(s, 'release_check', return_value={
                'all_observed_service_processes_exited': False}), \
             mock.patch('code_locbench_full_20261116.recovery.start_or_adopt') as start:
            with self.assertRaisesRegex(RuntimeError, 'live owned service'):
                s.launch_queue(self.root, spec, 1, {'files_sha256': {}})
        start.assert_not_called()

    def test_cached_completion_is_reused_after_actual_process_release(self):
        spec = self.queue_completion_fixture()
        with mock.patch.object(s, 'release_check', return_value={
                'all_observed_service_processes_exited': True}), \
             mock.patch('code_locbench_full_20261116.recovery.start_or_adopt') as start:
            result = s.launch_queue(self.root, spec, 1, {'files_sha256': {}})
        self.assertTrue(result['prior_completion_release_rechecked'])
        self.assertTrue(result['counts']['all_terminal'])
        start.assert_not_called()

    def test_cleanup_refuses_an_unrelated_command_family(self):
        self.put('controller/cpu_preparation_ownership.json', {
            'identity': {'pid': 123}, 'command': ['python', '-m', 'unrelated'], 'cwd': str(s.ROOT)})
        with mock.patch('code_locbench_full_20261116.recovery.stop_saved') as stop:
            result = s.cleanup_on_error(self.root)
        stop.assert_not_called()
        self.assertEqual(result[0]['outcome']['reason'], 'unrecognized command family')

    def test_cleanup_refuses_queue_manifests_outside_this_root(self):
        self.put('batch01/controller/queue_attempt_01/ownership.json', {
            'identity': {'pid': 123}, 'command': ['python', '-m',
                'code_locbench_sfpruner_20261116.queue', '--manifest', '/another/run/runnable_manifest.json'],
            'cwd': str(s.ROOT)})
        with mock.patch('code_locbench_full_20261116.recovery.stop_saved') as stop:
            s.cleanup_on_error(self.root)
        stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()
