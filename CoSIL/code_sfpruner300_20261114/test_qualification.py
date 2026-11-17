"""Real CPU R2 and transport-isolation controls; no network or model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_sfpruner300_20261114 import prepare_candidates as p
from code_sfpruner300_20261114 import qualification as q

BASE = 'def f(x):\n    return x\n'
PATCH = 'diff --git a/pkg/f.py b/pkg/f.py\n--- a/pkg/f.py\n+++ b/pkg/f.py\n@@ -1,2 +1,2 @@\n def f(x):\n-    return x\n+    return x + 1\n'


def record(root, iid='owner__repo-1', repo='owner/repo'):
    row = dict(instance_id=iid, repo=repo, base_commit='a' * 40,
               problem_statement='An issue ' * 30, patch=PATCH)
    path = root / (iid + '.raw.json'); path.write_text(json.dumps(row))
    return row, dict(instance_id=iid, repo=repo, base_commit=row['base_commit'], source_id=p.FULL_ID,
        raw_row_path=str(path), raw_row_sha256=p.sha(path),
        issue_sha256=hashlib.sha256(row['problem_statement'].encode()).hexdigest(),
        patch_sha256=hashlib.sha256(row['patch'].encode()).hexdigest())


class ScreeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.screen, cls.parser, _ = p.load_legacy()
        cls.exclusions = {k: set() for k in ('instance_id', 'repo', 'repo_pr', 'repo_base',
                                            'issue_sha256', 'patch_sha256', 'protected_split_ids')}

    def test_all_patch_files_count_and_test_patch_does_not_enter_business_filter(self):
        row = dict(instance_id='owner__repo-1', repo='owner/repo', base_commit='a' * 40,
                   problem_statement='word ' * 40, patch=PATCH, test_patch='invalid ignored test diff')
        a = p.inspect_row(row, 's', self.screen, self.parser, self.exclusions, set(), set())
        self.assertTrue(a['four_filter_pass'])
        self.assertEqual(a['problem_words'], 40)
        self.assertNotIn('test_patch', a)
        row['patch'] += 'diff --git a/README b/README\n--- a/README\n+++ b/README\n@@ -1 +1 @@\n-old\n+new\n'
        b = p.inspect_row(row, 's', self.screen, self.parser, self.exclusions, set(), set())
        self.assertEqual(b['business_patch']['files'], 2)
        self.assertIn('files_gt1', b['four_filter_reasons'])

    def test_history_and_existing_repo_exclusions_preserve_all_reasons(self):
        row = dict(instance_id='owner__repo-1', repo='owner/repo', base_commit='a' * 40,
                   problem_statement='short', patch=PATCH)
        exclusions = {k: set(v) for k, v in self.exclusions.items()}
        exclusions['protected_split_ids'].add(row['instance_id'])
        a = p.inspect_row(row, 's', self.screen, self.parser, exclusions,
                          {row['instance_id']}, {'owner/repo'})
        self.assertTrue({'problem_words_lt40', 'protected_split_id', 'already_selected_issue',
                         'already_selected_repository'}.issubset(a['reasons']))
        self.assertFalse(a['qualified_for_function_check'])


class QualificationTests(unittest.TestCase):
    def test_actual_r2_business_only_snapshot_produces_existing_target_and_resumes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); _, rec = record(root)
            calls = []
            def fetch(row, name, folder, **kw):
                calls.append(name); folder.mkdir(parents=True, exist_ok=True)
                path = folder / 'mock-base.raw'; path.write_bytes(BASE.encode())
                return path, {'sha256': p.sha(path), 'bytes': path.stat().st_size}
            a = q.qualify(rec, root / 'out', offline_only=True, fetcher=fetch)
            self.assertEqual(a['status'], 'QUALIFIED')
            self.assertTrue(a['complete']); self.assertTrue(a['nonempty'])
            self.assertEqual(a['base_files_sha256'], {'pkg/f.py': hashlib.sha256(BASE.encode()).hexdigest()})
            gold = json.loads(Path(a['R2_gold_path']).read_text())
            self.assertEqual(gold['existing_function_targets'], ['pkg/f.py::f'])
            b = q.qualify(rec, root / 'out', offline_only=True,
                          fetcher=lambda *a, **k: self.fail('Completed qualification was fetched again'))
            self.assertEqual(a, b); self.assertEqual(calls, ['pkg/f.py'])

    def test_missing_offline_cache_blocks_without_a_network_request(self):
        with tempfile.TemporaryDirectory() as d:
            row = dict(repo='owner/repo', base_commit='a' * 40)
            with self.assertRaisesRegex(q.NetworkBlocked, 'cache missing'):
                q.fetch_base(row, 'f.py', Path(d), proxy=None, offline_only=True,
                             client_factory=lambda **kw: self.fail('Offline mode attempted network'))

    def test_verified_connector_cache_and_definitive_unavailability_are_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); name = 'f.py'; key = hashlib.sha256(name.encode()).hexdigest()
            row = dict(repo='owner/repo', base_commit='a' * 40)
            url = 'https://raw.githubusercontent.com/owner/repo/' + 'a' * 40 + '/f.py'
            body = folder / (key + '.raw'); body.write_bytes(BASE.encode())
            receipt = folder / (key + '.receipt.json')
            receipt.write_text(json.dumps(dict(url=url, path=name, sha256=p.sha(body), bytes=len(BASE))))
            result, _ = q.fetch_base(row, name, folder, proxy=None, offline_only=True)
            self.assertEqual(result.read_bytes(), BASE.encode())
            receipt.write_text(json.dumps(dict(url=url, status='SOURCE_UNAVAILABLE', definitive=False)))
            with self.assertRaises(q.NetworkBlocked): q.fetch_base(row, name, folder, proxy=None, offline_only=True)
            receipt.write_text(json.dumps(dict(url=url, status='SOURCE_UNAVAILABLE', definitive=True, reason='404')))
            with self.assertRaises(q.BaseUnavailable): q.fetch_base(row, name, folder, proxy=None, offline_only=True)

    def test_transient_failure_blocks_global_prefix_instead_of_using_a_later_task(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); records = [record(root, 'a-1', 'owner/a')[1], record(root, 'b-1', 'owner/b')[1]]
            records.sort(key=p.order_key)
            screen = root / 'screen.json'; screen.write_text(json.dumps({'records': records, 'sources': []}))
            original = root / 'original.json'; original.write_text(json.dumps({'records': [
                dict(instance_id=f'old-{i}', repo=f'old/r{i}') for i in range(100)]}))
            args = argparse.Namespace(screen=screen, original=original, out=root/'out',
                target_new=1, proxy=None, retry_blocked_network=False, offline_only=True)
            with patch.object(q, 'qualify', side_effect=q.NetworkBlocked('cache pending')) as infer:
                result = q.run(args)
            self.assertEqual(infer.call_count, 1)
            self.assertEqual(result['blocked_instance_id'], records[0]['instance_id'])
            self.assertFalse(result['prefix_complete'])
            self.assertFalse(result['formal_selection_frozen'])
            self.assertFalse((args.out / 'selected_candidate_metadata.json').exists())


if __name__ == '__main__': unittest.main()
