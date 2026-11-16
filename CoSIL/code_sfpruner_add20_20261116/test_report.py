"""Synthetic CPU-only tests. No measured issue, GPU, model or sealed test data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from code_sfpruner_add20_20261116 import report as r


class Fixture:
    def __init__(self, root, *, n=20):
        self.root = Path(root); self.runtime = self.root / 'runtime'
        self.run = self.root / 'paired_run'; self.qualified = self.root / 'qualified'
        self.manifest = self.runtime / 'manifest.json'; self.freeze = self.root / 'report_freeze.json'
        self.protocol = self.root / 'protocol.json'; self.records = []
        for number in range(n):
            iid = 'fixture-' + str(number)
            base = {'instance_id': iid, 'repo': 'fixture/repo-' + str(number // 3), 'base_commit': 'a' * 40}
            task = self.runtime / 'tasks' / iid; snapshot = task / 'snapshot'
            snapshot.mkdir(parents=True)
            (snapshot / 'm.py').write_text('def target():\n    return 1\n\ndef other():\n    return 2\n')
            r.c.write(task / 'index.json', {'m.py': {'raw_sha256': r.c.sha(snapshot / 'm.py'),
                'definitions': [{'kind': 'function', 'qualified_name': 'target'},
                                {'kind': 'function', 'qualified_name': 'other'}]}})
            r.c.write(task / 'structure.json', {'fixture': True})
            job = {**base, 'problem_statement': 'Synthetic CPU fixture, not benchmark data.',
                'cohort': 'synthetic', 'snapshot': 'snapshot', 'paths': ['m.py'],
                'code_index': 'index.json', 'structure': 'structure.json'}
            r.c.write(task / 'job.json', job)
            self.records.append({**base, 'job': 'tasks/' + iid + '/job.json',
                'job_sha256': r.c.sha(task / 'job.json'), 'source_id': 'rebench_34d5a588'})
        r.c.write(self.manifest, {'n': n, 'records': self.records})
        _, normalized = r.c.load_manifest(self.manifest)
        protocol = {'schema': 1, 'manifest_sha256': r.c.sha(self.manifest), 'records': normalized,
            'simulation': False, 'controller_sha256': r.c.sha(r.c.__file__),
            'execution': r.c.FrozenBackend().protocol(), 'arms': list(r.ARMS),
            'replay_policy': 'never replay an already started arm',
            'arm_timeout_seconds': 3600, 'new_model_service_started': False}
        self.protocol_sha = r.c.digest(protocol)
        r.c.write(self.run / 'freeze.json', {**protocol, 'protocol_sha256': self.protocol_sha})
        r.c.write(self.protocol, {'n_new_issues': n, 'selection_reads_model_outcomes': False})
        for number, record in enumerate(self.records):
            iid = record['instance_id']; pair = self.run / 'pairs' / iid
            job = self.runtime / record['job']
            r.c.write(pair / 'prepared.json', {'protocol_sha256': self.protocol_sha,
                'source': r.c.source_receipt(job), 'staged_sha256': {}})
            terms = {}
            for arm in r.ARMS:
                folder = pair / arm
                result = {**{key: record[key] for key in ('instance_id', 'repo', 'base_commit')},
                    'arm': arm, 'status': 'complete', 'predicted_files': ['m.py'],
                    'predicted_functions': [{'path': 'm.py', 'qualified_name': 'other'}],
                    'known_prompt_tokens': 10, 'known_completion_tokens': 2,
                    'usage_unknown_attempts': 0, 'elapsed_seconds': 1.5}
                term = {'instance_id': iid, 'base_commit': record['base_commit'], 'arm': arm,
                    'protocol_sha256': self.protocol_sha, 'keep_in_denominator': True,
                    'simulation': False, 'status': 'complete'}
                if number == 1:
                    if arm == 'baseline':
                        result['status'] = 'ERROR_fixture'; result['predicted_functions'] = []
                        term['status'] = 'worker_failed'
                    else:
                        term.update(status='dependency_blocked', model_called=False)
                        result = None
                elif number == 2:
                    result['predicted_functions'] = ([{'path': 'm.py', 'qualified_name': 'target'}] if arm == 'baseline'
                        else [None, None, {'path': 'm.py', 'qualified_name': 'target'}])
                if result is not None:
                    r.c.write(folder / 'result.json', result)
                    term['result_sha256'] = r.c.sha(folder / 'result.json')
                r.c.write(folder / 'terminal.json', term); terms[arm] = term
            r.c.write(pair / 'pair_terminal.json', {'instance_id': iid,
                'protocol_sha256': self.protocol_sha, 'keep_in_denominator': True, 'arms': terms})
            private = self.qualified / iid
            gold = {**{key: record[key] for key in ('instance_id', 'repo', 'base_commit')},
                'status': 'COMPLETE_NONEMPTY', 'existing_function_target_set_complete': True,
                'existing_function_targets': ['m.py::target'], 'gold_files': ['m.py'],
                'evaluation_revision': 'r2_exact_context_offsets'}
            r.c.write(private / 'gold.json', gold)
            r.c.write(private / 'qualification.private.json', {
                **{key: record[key] for key in ('instance_id', 'repo', 'base_commit')},
                'status': 'QUALIFIED', 'complete': True, 'nonempty': True,
                'source_id': 'rebench_34d5a588', 'R2_gold_path': 'gold.json',
                'R2_gold_sha256': r.c.sha(private / 'gold.json')})

    def freeze_inputs(self):
        return r.freeze_inputs(manifest=self.manifest, run_root=self.run,
            qualified_root=self.qualified, protocol=self.protocol, out=self.freeze, draws=40)


class TerminalAndScoringTests(unittest.TestCase):
    def test_missing_terminal_never_reads_gold_or_historical_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp); fixture.freeze_inputs()
            (fixture.run / 'pairs/fixture-19/hybrid_safe/terminal.json').unlink()
            with mock.patch.object(r.f, 'read_new') as gold, mock.patch.object(r, 'project_history') as history:
                with self.assertRaisesRegex(ValueError, 'missing arm terminal'):
                    r.execute(fixture.freeze, Path(tmp) / 'report')
                gold.assert_not_called(); history.assert_not_called()
            self.assertFalse((Path(tmp) / 'report').exists())

    def test_all_arms_without_twenty_pair_receipts_still_does_not_open_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp); fixture.freeze_inputs()
            (fixture.run / 'pairs/fixture-0/pair_terminal.json').unlink()
            with mock.patch.object(r.f, 'read_new') as gold:
                with self.assertRaisesRegex(ValueError, 'missing pair terminal'):
                    r.execute(fixture.freeze, Path(tmp) / 'report')
                gold.assert_not_called()

    def test_failed_and_both_wrong_retained_in_fixed_denominator_repeat_repos_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp); fixture.freeze_inputs(); output = Path(tmp) / 'report'
            summary = r.execute(fixture.freeze, output)
            metrics = summary['groups']['new20']
            self.assertEqual(metrics['allocated'], 20); self.assertEqual(metrics['function_denominator'], 20)
            self.assertEqual(metrics['metrics']['baseline']['function']['hit5_numerator'], 1)
            self.assertEqual(metrics['metrics']['hybrid_safe']['function']['hit5_numerator'], 1)
            self.assertEqual(metrics['metrics']['hybrid_safe']['function']['n'], 20)
            self.assertEqual(summary['terminal_gate']['terminal_arms'], 40)
            self.assertEqual(summary['terminal_gate']['terminal_pairs'], 20)
            self.assertEqual(metrics['statuses']['baseline']['ERROR_fixture'], 1)
            self.assertEqual(metrics['statuses']['hybrid_safe']['DEPENDENCY_BLOCKED'], 1)
            agreement = r.read(output / 'new20_agreement.json')['records']
            rows = {row['instance_id']: row for row in agreement}
            self.assertTrue(rows['fixture-0']['hit5_both_completed_and_missed'])
            self.assertFalse(rows['fixture-1']['hit5_both_completed_and_missed'])
            self.assertTrue(rows['fixture-1']['hit5_miss_involving_execution_failure'])
            self.assertEqual(rows['fixture-2']['hit1_cell'], 'only_baseline')
            self.assertEqual(rows['fixture-2']['hit3_cell'], 'both_hit')
            self.assertFalse(rows['fixture-2']['hit135_vectors_identical'])
            self.assertEqual(len(r.read(output / 'new20_evaluation.json')['records']), 20)
            self.assertTrue((output / 'new20_逐题定位与资源.csv').is_file())
            with self.assertRaises(FileExistsError):
                r.execute(fixture.freeze, output)

    def test_snapshot_drift_fails_before_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp); fixture.freeze_inputs()
            (fixture.runtime / 'tasks/fixture-0/snapshot/m.py').write_text('def wrong(): pass\n')
            with mock.patch.object(r.f, 'read_new') as gold:
                with self.assertRaisesRegex(ValueError, 'Base source bytes changed'):
                    r.execute(fixture.freeze, Path(tmp) / 'report')
                gold.assert_not_called()

    def test_code_source_drift_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'code.py'; source.write_text('a=1\n')
            frozen = {'source_sha256': {str(source): r.c.sha(source)}}
            source.write_text('a=2\n')
            with self.assertRaisesRegex(ValueError, 'Frozen source/input drift'):
                r.verify_sources(frozen)

    def test_staged_public_source_drift_rejected_before_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp); fixture.freeze_inputs()
            path = fixture.run / 'pairs/fixture-0/_public_inputs/unrecorded.json'
            r.c.write(path, {'not_in_original_stage': True})
            with mock.patch.object(r.f, 'read_new') as gold:
                with self.assertRaisesRegex(ValueError, 'Staged public input drift'):
                    r.execute(fixture.freeze, Path(tmp) / 'report')
                gold.assert_not_called()

    def test_historical_sha_drift_fails_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp)
            history = Path(tmp) / 'history.json'; r.c.write(history, {'placeholder': True})
            r.freeze_inputs(manifest=fixture.manifest, run_root=fixture.run,
                qualified_root=fixture.qualified, protocol=fixture.protocol, out=fixture.freeze,
                history_evaluation=history, history_sha256='b' * 64, draws=40)
            with self.assertRaisesRegex(ValueError, 'Historical evaluation source drift'):
                r.execute(fixture.freeze, Path(tmp) / 'report')
            self.assertFalse((Path(tmp) / 'report').exists())

    def test_freeze_does_not_open_gold_or_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp)
            missing_history = Path(tmp) / 'not_yet_read_gold_bearing_history.json'
            value = r.freeze_inputs(manifest=fixture.manifest, run_root=fixture.run,
                qualified_root=fixture.qualified, protocol=fixture.protocol, out=fixture.freeze,
                history_evaluation=missing_history, history_sha256='b' * 64, draws=40)
            self.assertFalse(value['gold_opened'])
            self.assertFalse(value['historical_source_hashed_or_parsed_during_freeze'])
            self.assertEqual(value['history_evaluation_sha256'], 'b' * 64)


class ProjectionAndResourceTests(unittest.TestCase):
    def historical(self):
        records = []; gold = {}; inventory = {}
        for number in range(3):
            iid = 'old-' + str(number)
            pred = {'status': 'complete', 'predicted_files': [None, 'm.py'],
                'predicted_functions': [None, {'path': 'm.py', 'qualified_name': 'other'},
                    {'path': 'm.py', 'qualified_name': 'target'}, {'path': 'm.py', 'qualified_name': 'target'}]}
            records.append({'instance_id': iid, 'repo': 'same/repo', 'base_commit': 'a' * 40,
                            'arms': {arm: copy.deepcopy(pred) for arm in r.ARMS}})
            gold[iid] = {'status': 'COMPLETE_NONEMPTY', 'set_complete': True,
                         'targets': ['m.py::target'], 'gold_files': ['m.py']}
            inventory[iid] = {'paths': ['m.py'], 'function_identities': ['m.py::target', 'm.py::other']}
        return r.f.e.evaluate(records, gold, inventory, draws=40)

    def test_historical_projection_preserves_all_scores_slots_statuses_and_original(self):
        original = self.historical(); before = copy.deepcopy(original)
        bundle, result, audit = r.project_history(original, draws=40, expected_n=3)
        self.assertEqual(original, before)
        self.assertTrue(audit['all_per_issue_metrics_statuses_and_slots_unchanged'])
        self.assertEqual(result['records'], before['records'])
        self.assertEqual(bundle['records'][0]['arms']['baseline']['predicted_functions'][0], None)
        self.assertEqual(result['records'][0]['baseline_function']['slots'][0], None)
        self.assertEqual(result['records'][0]['baseline_function']['recall5'], 1)

    def test_historical_inconsistent_score_is_not_silently_rewritten(self):
        original = self.historical(); original['records'][0]['baseline_function']['hit1'] = 1
        with self.assertRaisesRegex(ValueError, 'Historical per-issue scores/slots changed'):
            r.project_history(original, draws=40, expected_n=3)

    def test_repo_cap_three_allows_repetition_but_not_four(self):
        old, _, _ = r.project_history(self.historical(), draws=40, expected_n=3)
        empty = {'records': [], 'gold': {}, 'inventory': {}, 'details': {}}
        self.assertEqual(len(r.combine(empty, old)['records']), 3)
        extra = copy.deepcopy(empty); extra['records'] = [{'instance_id': 'new', 'repo': 'SAME/REPO'}]
        with self.assertRaisesRegex(ValueError, 'cap3'):
            r.combine(old, extra)

    def test_unknown_usage_is_never_total_zero(self):
        self.assertIsNone(r.usage({})['main_tokens'])
        self.assertIsNone(r.usage({'main_tokens': 15, 'unknown_usage_attempts': 1})['main_tokens'])
        self.assertEqual(r.usage({'main_tokens': 15, 'unknown_usage_attempts': 0})['main_tokens'], 15)
        bundle = {'records': [{'instance_id': 'missing'}, {'instance_id': 'known'}], 'details': {}}
        for arm in r.ARMS:
            bundle['details'][('missing', arm)] = {'resource': {}}
            bundle['details'][('known', arm)] = {'resource': {'main_tokens': 15, 'unknown_usage_attempts': 0}}
        resource = r.resource_summary(bundle)['baseline']
        self.assertEqual(resource['known_main_tokens_sum'], 15)
        self.assertEqual(resource['unknown_main_token_tasks'], 1)
        self.assertIsNone(resource['main_tokens_total'])
        self.assertIsNone(resource['unknown_usage_attempts_total'])


if __name__ == '__main__':
    unittest.main()
