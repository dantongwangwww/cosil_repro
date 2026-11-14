"""Sampling invariants; synthetic fixtures never become experimental rosters."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('sampling_under_test', Path(__file__).with_name('sample.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def row(iid, repo, source='old'):
    return {'instance_id': iid, 'repo': repo, 'base_commit': 'a' * 40, 'source_id': source}


def q(record, nonempty=True, complete=True):
    return {'instance_id': record['instance_id'], 'base_commit': record['base_commit'],
            'complete': complete, 'nonempty': nonempty}


class SamplingTests(unittest.TestCase):
    def setUp(self):
        self.old = {'records': [row('old-1', 'old/a'), row('old-2', 'old/b')]}
        self.doc = {'sources': [
            {'source_id': 'old', 'dataset': 'frozen/old', 'revision': '1' * 40, 'sha256': '1' * 64},
            {'source_id': 'new', 'dataset': 'frozen/new', 'revision': '2' * 40, 'sha256': '2' * 64}],
            'records': [row('a-1', 'new/a'), row('a-2', 'new/a'), row('b-1', 'new/b')]}
        self.qual = {'records': [q(self.old['records'][0]), q(self.old['records'][1], False)] +
            [q(r) for r in self.doc['records']]}

    def run_sample(self, **kw):
        return s.sample(self.doc, self.old, self.qual, reference_source='old', **kw)

    def test_shortage_retains_old_na_and_never_publishes_partial_roster(self):
        result = self.run_sample(target_function_count=4)
        self.assertEqual(result['status'], 'INSUFFICIENT_CAPACITY')
        self.assertFalse(result['selection_frozen'])
        self.assertEqual(result['records'], [])
        self.assertEqual(result['existing_task_count'], 2)
        self.assertEqual(result['existing_function_count'], 1)
        self.assertEqual(len(result['existing_records']), 2)
        self.assertEqual(result['new_function_tasks_required'], 3)
        self.assertEqual(result['minimum_total_tasks_if_target_met'], 5)
        self.assertEqual(result['capacity']['maximum_function_denominator'], 3)
        self.assertEqual(result['capacity']['shortfall'], 1)

    def test_expansion_requires_opt_in_and_immutable_source_registry(self):
        added = row('c-1', 'extra/c', 'new')
        self.doc['records'].append(added); self.qual['records'].append(q(added))
        blocked = self.run_sample(target_function_count=4)
        self.assertEqual(blocked['capacity']['shortfall'], 1)
        enabled = self.run_sample(target_function_count=4, allow_source_expansion=True)
        self.assertEqual(enabled['status'], 'READY')
        self.assertEqual(enabled['n'], 3)
        self.assertEqual(sum(r['source_id'] == 'new' for r in enabled['records']), 1)
        for key in ('revision', 'sha256'):
            saved = self.doc['sources'][1][key]
            self.doc['sources'][1][key] = 'main'
            with self.assertRaises(ValueError): self.run_sample(allow_source_expansion=True)
            self.doc['sources'][1][key] = saved

    def test_repo_relaxation_is_explicit_and_case_insensitive(self):
        self.doc['records'][1]['repo'] = 'NEW/A'
        unique = self.run_sample(target_function_count=4)
        self.assertEqual(unique['capacity']['eligible_new_function_tasks'], 2)
        repeated = self.run_sample(target_function_count=4, keep_repo_unique=False)
        self.assertEqual(repeated['n'], 3)
        self.assertFalse(repeated['keep_repo_unique'])

    def test_stable_hash_order_and_capacity_only_never_freezes(self):
        expected = self.run_sample(target_function_count=3)
        self.doc['records'].reverse(); self.qual['records'].reverse()
        actual = self.run_sample(target_function_count=3)
        self.assertEqual(expected['records'], actual['records'])
        self.assertEqual(expected['candidate_order'], actual['candidate_order'])
        audit = self.run_sample(target_function_count=3, capacity_only=True)
        self.assertEqual(audit['status'], 'CAPACITY_ONLY')
        self.assertEqual(audit['records'], [])
        self.assertFalse(audit['selection_frozen'])

    def test_deny_receipt_uses_exported_ids_not_sealed_contents(self):
        denied = {'split_id_union': {'test': ['b-1']}, 'excluded_repositories': ['NEW/A']}
        result = s.sample(self.doc, self.old, self.qual, [denied], reference_source='old')
        self.assertEqual(result['capacity']['eligible_new_function_tasks'], 0)
        self.assertEqual(result['capacity']['exclusion_counts_overlapping']['protected_or_history_issue'], 1)
        self.assertFalse(result['test_contents_read'])
        with self.assertRaisesRegex(ValueError, 'Existing cohort'):
            s.sample(self.doc, self.old, self.qual, [{'instance_ids': ['old-2']}], reference_source='old')

    def test_gold_and_outcomes_cannot_enter_metadata_or_qualifications(self):
        self.doc['records'][0]['prediction'] = 'correct'
        with self.assertRaisesRegex(ValueError, 'Unexpected metadata'): self.run_sample()
        del self.doc['records'][0]['prediction']
        self.qual['records'][0]['gold_functions'] = ['secret.py::f']
        with self.assertRaisesRegex(ValueError, 'Qualifications accept'): self.run_sample()
        del self.qual['records'][0]['gold_functions']
        self.qual['records'][0]['complete'] = 1
        with self.assertRaisesRegex(ValueError, 'boolean'): self.run_sample()

    def test_missing_and_partial_functions_do_not_fill_function_target(self):
        self.qual['records'][-1]['complete'] = False
        result = self.run_sample(target_function_count=3)
        self.assertEqual(result['capacity']['maximum_function_denominator'], 2)
        self.qual['records'].pop(0)
        with self.assertRaisesRegex(ValueError, 'All original tasks'): self.run_sample()

    def test_only_relative_jobs_and_whitelisted_runtime_identity_survive(self):
        for r in self.doc['records']:
            r.update(job='inputs/' + r['instance_id'] + '/job.json', job_sha256='f' * 64)
        result = self.run_sample(target_function_count=3)
        self.assertTrue(result['runtime_ready'])
        expected = s.FIELDS | {'source', 'source_revision', 'source_sha256'}
        self.assertTrue(all(set(r) <= expected for r in result['records']))
        self.assertTrue(all('complete' not in r and 'nonempty' not in r for r in result['records']))
        self.doc['records'][0]['job'] = '../escape/job.json'
        with self.assertRaisesRegex(ValueError, 'future manifest'): self.run_sample()

    def test_conflicting_identity_fails_instead_of_choosing_a_convenient_base(self):
        conflict = copy.deepcopy(self.doc['records'][0]); conflict['base_commit'] = 'b' * 40
        self.doc['records'].append(conflict)
        with self.assertRaisesRegex(ValueError, 'Conflicting'): self.run_sample()


if __name__ == '__main__':
    unittest.main()
