"""Independent CPU checks of worker isolation plans and controller failure handling."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from code_rebench_qwen import common as C
from code_rebench_qwen import bootstrap as B
from code_rebench_qwen import run as R


class Control(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cosil-control-test-')
        self.root = Path(self.tmp.name)
        self.patches = [patch.object(C, 'WORK', self.root),
                        patch.object(C, 'INPUTS', self.root/'inputs'),
                        patch.object(C, 'RUN', self.root/'run'),
                        patch.object(C, 'MODEL_DIR', self.root/'model')]
        for p in self.patches:
            p.start()
        self.iid = 'synthetic__repo-1'
        directory = C.INPUTS/self.iid
        self.job_path = directory/'job.json'
        self.job = dict(instance_id=self.iid, repo='synthetic/repo', base_commit='a'*40,
            problem_statement='synthetic regression', cohort=C.COHORT,
            snapshot=str(self.root/'snapshot'), paths=['m.py'],
            code_index=str(directory/'code_index.json'),
            structure=str(directory/'repo_structures'/f'{self.iid}.json'))
        C.write(self.job_path, self.job)
        C.write(self.job['code_index'], {})
        C.write(self.job['structure'], {'structure':{}})
        Path(self.job['snapshot']).mkdir()
        C.MODEL_DIR.mkdir()
        (C.WORK/'token_cache').mkdir()
        self.record = dict(instance_id=self.iid, job=str(self.job_path),
                           repo=self.job['repo'], base_commit=self.job['base_commit'])
        self.out = C.RUN/'cases'/self.iid

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    @staticmethod
    def mounts(command):
        return [(command[i], command[i+1], command[i+2])
                for i in range(len(command)-2) if command[i] in ('--ro-bind', '--bind')]

    def test_both_home_aliases_hidden_before_explicit_readonly_code(self):
        argv = B.argv(self.job_path, self.out)
        hides = [argv[i+1] for i, value in enumerate(argv[:-1]) if value=='--tmpfs']
        self.assertIn('/tmp', hides)
        for home in B.HOMES:
            if home.is_dir():
                canonical = str(home.resolve())
                self.assertIn(canonical, hides)
                hide_position = next(i for i in range(len(argv)-1)
                                     if argv[i]=='--tmpfs' and argv[i+1]==canonical)
                code_position = next(i for i in range(len(argv)-2)
                                     if argv[i]=='--ro-bind' and argv[i+1]==str(C.ROOT/'code_v3b'))
                self.assertLess(hide_position, code_position)
        mounted_sources = [source for _,source,_ in self.mounts(argv)]
        self.assertNotIn(str(C.FROZEN), mounted_sources)
        self.assertNotIn(str(C.ROOT/'results'), mounted_sources)
        self.assertNotIn(str(C.ROOT/'docs'), mounted_sources)
        self.assertNotIn(str(C.ROOT/'ground_truth_300.json'), mounted_sources)
        self.assertIn(str(Path(self.job['snapshot'])), mounted_sources)

    def test_home_mount_destinations_do_not_traverse_symlink_alias(self):
        command = B.argv(self.job_path, self.out)
        destinations = [destination for _,_,destination in self.mounts(command)]
        destinations += [command[i+1] for i in range(len(command)-1) if command[i]=='--tmpfs']
        for home in B.HOMES:
            if home != home.resolve():
                self.assertNotIn(str(home), destinations)
                self.assertNotIn(str(home/'miniconda3'), destinations)

    def test_preparation_sidecars_are_not_mounted_with_clean_inputs(self):
        mounts = self.mounts(B.argv(self.job_path, self.out))
        sources = [source for _,source,_ in mounts]
        self.assertNotIn(str(self.job_path.parent), sources)
        for path in (self.job_path, Path(self.job['code_index']), Path(self.job['structure'])):
            self.assertIn(str(path), sources)
        self.assertNotIn(str(self.job_path.parent/'preparation_receipt.json'), sources)
        self.assertNotIn(str(self.job_path.parent/'source_hashes.json'), sources)

    def test_only_case_output_is_explicitly_writable(self):
        command = B.argv(self.job_path, self.out)
        writable = [(a,b) for kind,a,b in self.mounts(command) if kind=='--bind']
        self.assertEqual(writable, [(str(self.out), str(self.out))])

    def test_allowlist_environment_drops_credentials_and_proxy(self):
        secrets = {'OPENAI_API_KEY':'sentinel', 'DEEPSEEK_API_KEY':'sentinel',
            'HF_TOKEN':'sentinel', 'AWS_SECRET_ACCESS_KEY':'sentinel',
            'HTTPS_PROXY':'http://sentinel', 'HTTP_PROXY':'http://sentinel',
            'PYTHONSTARTUP':'/tmp/sentinel.py', 'LD_PRELOAD':'/tmp/sentinel.so'}
        with patch.dict(os.environ, secrets):
            env = B.environment(self.out)
        self.assertTrue(set(env).isdisjoint(secrets))
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], '')
        self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(env['HF_HUB_OFFLINE'], '1')
        self.assertEqual(env['HOME'], '/tmp/worker_home')

    def test_extra_job_label_is_refused(self):
        C.write(self.job_path, dict(self.job, gold_functions=['forbidden']))
        with self.assertRaises(ValueError):
            B.argv(self.job_path, self.out)

    def test_job_outside_new_inputs_is_refused(self):
        other = C.WORK/'other.json'
        C.write(other, self.job)
        with self.assertRaises(PermissionError):
            B.argv(other, self.out)

    def test_output_outside_new_run_is_refused(self):
        with self.assertRaises(PermissionError):
            B.argv(self.job_path, C.WORK/'outside')

    def test_terminal_case_is_reused_without_any_new_process_or_rewrite(self):
        result = dict(instance_id=self.iid, status='complete', predicted_files=['m.py'])
        path = self.out/'result.json'
        C.write(path, result)
        before = C.sha(path)
        with patch.object(R.subprocess, 'run') as start:
            self.assertEqual(R.one(self.record), result)
        start.assert_not_called()
        self.assertEqual(C.sha(path), before)

    def test_failed_terminal_case_is_not_resampled(self):
        path = self.out/'result.json'
        C.write(path, dict(instance_id=self.iid, status='failed'))
        with patch.object(R.subprocess, 'run') as start:
            result = R.one(self.record)
        self.assertEqual(result['status'], 'failed')
        start.assert_not_called()

    def test_interrupted_case_requires_audit_without_new_request(self):
        C.write(self.out/'started.json', {'instance_id':self.iid})
        with patch.object(R.subprocess, 'run') as start:
            with self.assertRaisesRegex(RuntimeError, 'Interrupted'):
                R.one(self.record)
        start.assert_not_called()
        self.assertFalse((self.out/'result.json').exists())

    def test_worker_nonzero_exit_creates_terminal_failure_and_empty_slots(self):
        with patch.object(R.subprocess, 'run', return_value=SimpleNamespace(returncode=17)):
            result = R.one(self.record)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['returncode'], 17)
        self.assertEqual(result['predicted_files'], [])
        self.assertEqual(result['predicted_functions'], [])
        self.assertTrue((self.out/'controller_receipt.json').exists())

    def test_worker_spawn_error_also_preserves_terminal_denominator(self):
        with patch.object(R.subprocess, 'run', side_effect=OSError('synthetic spawn failure')):
            result = R.one(self.record)
        self.assertEqual(result['status'], 'failed')
        self.assertTrue((self.out/'result.json').exists())

    def test_progress_keeps_fixed_265_allocation_and_failed_separate(self):
        C.write(self.out/'result.json', dict(instance_id=self.iid,status='failed',elapsed_seconds=2.))
        state = R.progress([self.record])
        self.assertEqual(state['allocated'], 265)
        self.assertEqual(state['terminal'], 1)
        self.assertEqual(state['statuses'], {'failed':1})

    def test_verify_detects_preparation_and_prior_roster_drift(self):
        prior = C.WORK/'prior_manifest.json'
        with patch.object(C, 'SOURCE_MANIFEST', prior):
            C.write(prior, {'fixed':'roster'})
            C.write(C.INPUTS/'prepare_manifest.json', {'prepared':True})
            C.write(C.WORK/'model_files.json', {'revision':'synthetic'})
            frozen = dict(code_sha256={}, input_sha256={},
                model_files_sha256=C.sha(C.WORK/'model_files.json'),
                preparation_manifest_sha256=C.sha(C.INPUTS/'prepare_manifest.json'),
                prior_manifest_sha256=C.sha(prior))
            C.write(C.RUN/'frozen.json', frozen)
            self.assertEqual(R.verify(), frozen)
            C.write(C.INPUTS/'prepare_manifest.json', {'prepared':'drift'})
            with self.assertRaisesRegex(RuntimeError, 'manifest drift'):
                R.verify()
            C.write(C.INPUTS/'prepare_manifest.json', {'prepared':True})
            C.write(prior, {'fixed':'changed'})
            with self.assertRaisesRegex(RuntimeError, 'roster drift'):
                R.verify()

    def test_full_rejects_gate_from_a_different_freeze(self):
        C.write(C.RUN/'frozen.json', {'records':[]})
        C.write(C.RUN/'isolation_probe/probe.json', {'passed':True})
        C.write(C.RUN/'canary_gate.json', {'passed':True,'frozen_sha256':'otherfreeze'})
        with patch.object(R, 'verify', return_value={'records':[]}), patch.object(R, 'one') as one:
            with self.assertRaisesRegex(RuntimeError, 'exact freeze'):
                R.execute('full', 1)
        one.assert_not_called()


if __name__ == '__main__':
    unittest.main()
