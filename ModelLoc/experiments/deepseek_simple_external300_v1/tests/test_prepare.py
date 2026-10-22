"""Synthetic CPU tests: selection, isolation, concurrency and storage safety."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from supplement_v1 import prepare as p


def row(i, repo=None, issue=None, patch_text=None):
    return {'instance_id': f'owner__repo-{i}', 'repo': repo or f'owner/repo{i}',
            'base_commit': f'{i:040x}', 'problem_statement': issue or f'issue {i}',
            'patch': patch_text or f'patch {i}'}


def chosen(r):
    return {'qualified': True, **{k: r[k] for k in ('instance_id', 'repo', 'base_commit')},
            'sampling_hash': p.stable(p.NAMESPACE, r['instance_id']), 'job': '/new/jobs/' + r['instance_id']}


def seed(rows):
    return {'n': 100, 'records': [{k: v for k, v in chosen(r).items() if k != 'qualified'} for r in rows[:100]]}


def exclusions():
    return {k: set() for k in ('instance_id', 'repo', 'protected_split_ids') + p.IDENTITY_FIELDS}


def audit(rows):
    return [{'instance_id': r['instance_id'], 'status': 'selected' if i < 100 else 'not_examined',
             'reasons': ''} for i, r in enumerate(rows)]


def pool(rows):
    return [(r, {'status': 'candidate', 'reasons': ''}) for r in rows]


class PrepareTests(unittest.TestCase):
    def test_exact_frozen_stable_algorithm(self):
        self.assertEqual(p.stable(p.NAMESPACE, 'lincc-frameworks__nested-pandas-190'),
                         '003e80c4fb1644b88984a66bf44ed14000f4a0f62dd3459749b0b6363594f58c')

    def test_seed_base_drift_rejected(self):
        rows = [row(i) for i in range(102)]
        previous = seed(rows)
        previous['records'][0]['base_commit'] = 'f' * 40
        with self.assertRaisesRegex(ValueError, 'identity drift'):
            p.seed_identities(rows, previous)

    def test_previous_repo_issue_patch_and_frozen_failure_excluded(self):
        rows = [row(i) for i in range(106)]
        rows[100]['repo'] = rows[0]['repo']
        rows[101]['problem_statement'] = rows[1]['problem_statement']
        rows[102]['patch'] = rows[2]['patch']
        old = audit(rows)
        old[103].update(status='ineligible', reasons='base_unavailable')
        ex = exclusions()
        ex['protected_split_ids'].add(rows[104]['instance_id'])
        _, records, candidates, _, _ = p.make_pool(rows, seed(rows), ex, old)
        self.assertEqual([r['instance_id'] for r, _ in candidates], [rows[105]['instance_id']])
        by_id = {r['instance_id']: r for r in records}
        self.assertIn('previous100_repository', by_id[rows[100]['instance_id']]['reasons'])
        self.assertIn('previous100_issue_sha256', by_id[rows[101]['instance_id']]['reasons'])
        self.assertIn('previous100_patch_sha256', by_id[rows[102]['instance_id']]['reasons'])
        self.assertIn('previous_frozen_ineligible', by_id[rows[103]['instance_id']]['reasons'])
        self.assertIn('protected_split_id', by_id[rows[104]['instance_id']]['reasons'])

    def test_history_receipt_not_live_splits(self):
        history = []
        for i in range(707):
            history.append({'instance_id': f'h-{i}', 'repo': f'h/repo{i % 12}',
                            'repo_pr': f'h/repo{i % 12}#{i}', 'repo_base': f'h@{i}',
                            'issue_sha256': f'i{i}', 'patch_sha256': f'p{i}'})
        receipt = {'test_contents_read_or_hashed': False, 'history': history,
                   'excluded_repositories': sorted({r['repo'] for r in history}),
                   'exclusion_set_counts': {'instance_id': 707, 'repo': 12, 'repo_pr': 708,
                                            'repo_base': 708, 'issue_sha256': 707, 'patch_sha256': 707},
                   'extra_public_dataset_audit': {'records': [{'repo_pr': 'extra#1', 'repo_base': 'extra@1'}]},
                   'split_id_union': {'train': ['h-1'], 'val': ['h-2'], 'test': ['sealed-id-only']}}
        sets = p.history_sets(receipt)
        self.assertEqual(sets['protected_split_ids'], {'h-1', 'h-2', 'sealed-id-only'})
        self.assertIn('extra#1', sets['repo_pr'])
        receipt['test_contents_read_or_hashed'] = True
        with self.assertRaises(ValueError):
            p.history_sets(receipt)

    def test_concurrent_completion_cannot_reorder_selection(self):
        rows = [row(i) for i in range(4)]
        second_done = threading.Event()
        commits = []

        def download(r):
            if r['instance_id'] == rows[0]['instance_id']:
                self.assertTrue(second_done.wait(2))
            if r['instance_id'] == rows[1]['instance_id']:
                second_done.set()
            return r['instance_id']

        def qualify(r, data):
            commits.append(r['instance_id'])
            return chosen(r)

        result = p.select_ordered(pool(rows), 2, set(), {k: set() for k in p.IDENTITY_FIELDS},
                                  download, qualify, workers=2)
        self.assertEqual(commits, [r['instance_id'] for r in rows[:2]])
        self.assertEqual([r['instance_id'] for r in result], commits)

    def test_one_repository_and_cross_repository_fingerprint(self):
        rows = [row(1), row(2, repo='owner/repo1'), row(3, patch_text='patch 1'), row(4)]
        candidates = pool(rows)
        result = p.select_ordered(candidates, 2, set(), {k: set() for k in p.IDENTITY_FIELDS},
                                  lambda r: {}, lambda r, d: chosen(r), workers=4)
        self.assertEqual([r['instance_id'] for r in result], [rows[0]['instance_id'], rows[3]['instance_id']])
        self.assertEqual(candidates[1][1]['reasons'], 'one_issue_per_repository')
        self.assertIn('patch_sha256', candidates[2][1]['reasons'])

    def test_failed_qualification_stays_denominator_independent(self):
        rows = [row(1), row(2)]
        candidates = pool(rows)
        result = p.select_ordered(candidates, 1, set(), {k: set() for k in p.IDENTITY_FIELDS},
                                  lambda r: {}, lambda r, d: ({'qualified': False, 'reason': 'base_unavailable'}
                                  if r == rows[0] else chosen(r)), workers=2)
        self.assertEqual(result[0]['instance_id'], rows[1]['instance_id'])
        self.assertEqual(candidates[0][1], {'status': 'ineligible', 'reasons': 'base_unavailable'})

    def test_programming_error_stops_without_replacement(self):
        candidates = pool([row(1), row(2)])
        def broken(r, d):
            raise RuntimeError('synthetic defect')
        with self.assertRaisesRegex(RuntimeError, 'synthetic defect'):
            p.select_ordered(candidates, 1, set(), {k: set() for k in p.IDENTITY_FIELDS},
                             lambda r: {}, broken, workers=2)
        self.assertEqual(candidates[0][1]['status'], 'blocked')
        self.assertNotEqual(candidates[1][1]['status'], 'selected')

    def test_insufficient_pool_does_not_relax_dedup(self):
        rows = [row(1), row(2, issue='issue 1')]
        result = p.select_ordered(pool(rows), 2, set(), {k: set() for k in p.IDENTITY_FIELDS},
                                  lambda r: {}, lambda r, d: chosen(r), workers=1)
        self.assertEqual(len(result), 1)

    def test_qualification_cannot_replace_identity(self):
        def wrong(r, d):
            value = chosen(r)
            value['repo'] = 'different/repo'
            return value
        with self.assertRaisesRegex(ValueError, 'identity does not match'):
            p.select_ordered(pool([row(1)]), 1, set(), {k: set() for k in p.IDENTITY_FIELDS},
                             lambda r: {}, wrong, workers=1)

    def test_authorized_size_and_concurrency_before_io(self):
        with self.assertRaises(ValueError):
            p.prepare(199, 4)
        with self.assertRaises(ValueError):
            p.prepare(200, 5)

    def test_storage_registration_and_refuse_existing_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, storage = base / 'newproject', base / 'scratch'
            private = root / 'evaluator_private/preparation'
            def read(path):
                return json.loads(Path(path).read_text()) if Path(path).exists() else None
            def write(path, obj):
                path = Path(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(obj))
            with patch.multiple(p, ROOT=root, PRIVATE=private, STORAGE=storage, load=read, write=write), patch.object(p, 'space_guard'):
                p.prepare_storage()
                self.assertEqual((root / 'snapshots').resolve(), storage / 'clean_snapshots')
                self.assertEqual((private / 'mirrors').resolve(), storage / 'archives')
                first = (root / 'storage_manifest.json').read_text()
                p.prepare_storage()
                self.assertEqual(first, (root / 'storage_manifest.json').read_text())
                (root / 'snapshots').unlink()
                (root / 'snapshots').mkdir()
                with self.assertRaisesRegex(RuntimeError, 'Refuse to replace'):
                    p.prepare_storage()

    def test_unregistered_scratch_is_never_adopted(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / 'existing').mkdir()
            with patch.multiple(p, ROOT=base / 'root', PRIVATE=base / 'private', STORAGE=base / 'existing',
                                load=lambda _: None), patch.object(p, 'space_guard'):
                with self.assertRaisesRegex(RuntimeError, 'Unregistered'):
                    p.prepare_storage()

    def test_explicit_v1_upgrade_preserves_every_job_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, storage = base / 'newproject', base / 'scratch'
            private = root / 'evaluator_private/preparation'
            root.mkdir(); storage.mkdir()
            old_pairs = [(private / 'mirrors', storage / 'archives'), (root / 'snapshots', storage / 'clean_snapshots')]
            for link, target in old_pairs:
                target.mkdir(); link.parent.mkdir(parents=True, exist_ok=True); link.symlink_to(target)
            (root / 'jobs' / 'iid').mkdir(parents=True)
            (root / 'jobs' / 'iid' / 'job.json').write_text('{"frozen":"data"}')
            def read(path):
                return json.loads(Path(path).read_text()) if Path(path).exists() else None
            def write(path, obj):
                path = Path(path); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(obj))
            with patch.multiple(p, ROOT=root, PRIVATE=private, STORAGE=storage, load=read, write=write), patch.object(p, 'space_guard'):
                write(root / 'storage_manifest.json', p.storage_record(old_pairs, 'fixed-time'))
                before = p.file_inventory(root / 'jobs')
                with self.assertRaisesRegex(RuntimeError, 'explicit safe upgrade'):
                    p.prepare_storage()
                p.prepare_storage(allow_upgrade=True)
                self.assertTrue((root / 'jobs').is_symlink())
                self.assertEqual(p.file_inventory(root / 'jobs'), before)
                self.assertFalse((root / 'jobs.storage_migration_backup').exists())
                self.assertEqual(read(root / 'storage_manifest.json')['schema_version'], 3)
                self.assertEqual(read(private / 'jobs_storage_migration.json')['status'], 'complete')
                p.prepare_storage()

    def test_not_checked_does_not_change_eligibility(self):
        with tempfile.TemporaryDirectory() as folder:
            writes = []
            def capture(path, obj):
                writes.append((path, obj))
            with patch.multiple(p, PRIVATE=Path(folder), write=capture):
                rec = p.mark_execution_qualification(chosen(row(1)), Path(folder) / 'environment.json')
                self.assertTrue(rec['qualified'])
                self.assertEqual(rec['gold_patch_pass'], 'NOT_CHECKED')
                self.assertEqual(rec['empty_patch_fail'], 'NOT_CHECKED')
                self.assertEqual(writes[0][0].name, row(1)['instance_id'] + '.json')

    def test_combined_metadata_uses_full_population(self):
        rows = [row(i) for i in range(300)]
        previous = seed(rows)
        original = copy.deepcopy(previous)
        result = {'n': 200, 'records': [{k: v for k, v in chosen(r).items() if k != 'qualified'} for r in rows[100:]],
                  'quota_by_repo': {r['repo']: 1 for r in rows[100:]},
                  'previous100_issue_overlap': 0, 'previous100_repository_overlap': 0}
        combined = p.combined_manifest(result, previous)
        self.assertEqual(combined['n'], 300)
        self.assertEqual(len(combined['quota_by_repo']), 300)
        self.assertEqual(sum(r['origin'] == 'previous100' for r in combined['records']), 100)
        self.assertEqual(sum(r['origin'] == 'additional200' for r in combined['records']), 200)
        self.assertNotIn('previous100_issue_overlap', combined)
        self.assertEqual(combined['new_vs_previous100_issue_overlap'], 0)
        self.assertEqual(previous, original)

    def test_space_guard_uses_resolved_project_volume(self):
        with tempfile.TemporaryDirectory() as folder:
            actual = Path(folder) / 'actual'; actual.mkdir()
            logical = Path(folder) / 'logical'; logical.symlink_to(actual)
            calls = []
            def usage(path):
                calls.append(str(path))
                return type('Usage', (), {'free': 100 * 1024**3})()
            with patch.object(p, 'ROOT', logical), patch.object(p.shutil, 'disk_usage', usage):
                p.space_guard()
            self.assertEqual(calls, [str(actual), '/tmp'])


if __name__ == '__main__':
    unittest.main()
