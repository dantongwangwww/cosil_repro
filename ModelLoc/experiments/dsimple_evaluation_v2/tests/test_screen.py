"""Synthetic CPU checks for exactly four filters and post-filter isolation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dsimple_v2 import screen as s


MOD = 'diff --git a/src/a.py b/src/a.py\nindex 1111111..2222222 100644\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-old\n+new\n'


def row(i, repo=None, problem=None, business=MOD, test=''):
    return {'instance_id': f'owner__repo-{i}', 'repo': repo or f'owner/repo{i}', 'base_commit': f'{i:040x}',
            'problem_statement': problem if problem is not None else ' '.join(['word'] * 40),
            'patch': business, 'test_patch': test}


def exclusions():
    return {key: set() for key in ('instance_id', 'repo', 'repo_pr', 'repo_base', 'issue_sha256', 'patch_sha256', 'protected_split_ids')}


class ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Parser, _ = s.load_parser('/tmp/external_lite_four_audit_unidiff075')

    def test_pinned_official_parser_and_independent_headers(self):
        stats = s.patch_stats(MOD, self.Parser)
        self.assertEqual((stats['files'], stats['hunks'], stats['added_files'], stats['removed_files']), (1, 1, 0, 0))

    def test_user_word_boundary_exact_40(self):
        stats = s.patch_stats(MOD, self.Parser)
        self.assertEqual(s.four_reasons(40, stats), [])
        self.assertEqual(s.four_reasons(39, stats), ['problem_words_lt40'])
        self.assertEqual(len('one\t two\nthree  four'.split()), 4)

    def test_whole_business_patch_counts_documentation(self):
        business = MOD + MOD.replace('src/a.py', 'docs/readme.md')
        records = s.screen_rows([row(1, business=business)], exclusions(), set(), set(), set(), self.Parser)
        self.assertEqual(records[0]['business_patch']['files'], 2)
        self.assertEqual(records[0]['four_filter_reasons'], ['files_gt1'])

    def test_no_python_or_mapping_requirement(self):
        business = MOD.replace('src/a.py', 'settings.json')
        records = s.screen_rows([row(1, business=business)], exclusions(), set(), set(), set(), self.Parser)
        self.assertTrue(records[0]['qualified'])

    def test_test_patch_never_changes_qualification(self):
        test = MOD + MOD.replace('src/a.py', 'tests/second.py')
        a, b = row(1), row(2, test=test)
        records = s.screen_rows([a, b], exclusions(), set(), set(), set(), self.Parser)
        self.assertTrue(all(r['qualified'] for r in records))
        summary = s.summarize(records)
        self.assertEqual(summary['test_patch_audit_only']['fail_same_three_patch_limits'], 1)
        self.assertFalse(summary['test_patch_audit_only']['affected_qualified_pool'])

    def test_create_and_delete_metadata_without_hunks(self):
        new = 'diff --git a/new.py b/new.py\nnew file mode 100644\nindex 0000000..e69de29\n'
        deleted = 'diff --git a/old.py b/old.py\ndeleted file mode 100644\nindex e69de29..0000000\n'
        for business in (new, deleted):
            stats = s.patch_stats(business, self.Parser)
            self.assertIn('creates_or_deletes_file', s.four_reasons(40, stats))

    def test_devnull_creation_detected(self):
        business = 'diff --git a/new.py b/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+new\n'
        stats = s.patch_stats(business, self.Parser)
        self.assertTrue(stats['dev_null'])
        self.assertEqual(stats['added_files'], 1)

    def test_rename_recorded_without_adding_fifth_filter(self):
        business = 'diff --git a/old.txt b/new.txt\nsimilarity index 100%\nrename from old.txt\nrename to new.txt\n'
        stats = s.patch_stats(business, self.Parser)
        self.assertEqual(stats['files'], 1)
        self.assertEqual(stats['rename_metadata_files'], 1)
        self.assertEqual(s.four_reasons(40, stats), [])

    def test_history_applied_after_four_for_waterfall(self):
        ex = exclusions(); ex['repo'].add('owner/repo1')
        records = s.screen_rows([row(1, problem='short'), row(2)], ex, set(), set(), set(), self.Parser)
        first = next(r for r in records if r['instance_id'] == row(1)['instance_id'])
        self.assertIn('problem_words_lt40', first['four_filter_reasons'])
        self.assertIn('history_repository', first['history_reasons'])
        summary = s.summarize(records)
        self.assertEqual(summary['four_filter_pass']['issues'], 1)
        self.assertEqual(summary['after_history']['issues'], 1)
        self.assertEqual(summary['history_reasons_overlap_all860']['history_repository'], 1)
        self.assertEqual(summary['history_reasons_overlap_after_four'], {})

    def test_old100_not_excluded_and_prepared200_not_observed(self):
        rows = [row(1), row(2), row(3)]
        records = s.screen_rows(rows, exclusions(), {rows[0]['instance_id']}, {rows[1]['instance_id']}, {'owner/repo1'}, self.Parser)
        by_id = {r['instance_id']: r for r in records}
        self.assertEqual(by_id[rows[0]['instance_id']]['observation_group'], 'old100_observed')
        self.assertTrue(by_id[rows[0]['instance_id']]['qualified'])
        self.assertEqual(by_id[rows[1]['instance_id']]['observation_group'], 'old200_prepared_not_run')
        self.assertFalse(by_id[rows[1]['instance_id']]['repository_observed_in_old100'])

    def test_global_hash_order_does_not_preserve_old100(self):
        rows = [row(1, repo='owner/same'), row(2, repo='owner/same')]
        expected = min(rows, key=lambda r: (s.order_hash(r['instance_id']), r['instance_id']))['instance_id']
        observed = next(r['instance_id'] for r in rows if r['instance_id'] != expected)
        records = s.screen_rows(rows[::-1], exclusions(), {observed}, set(), {'owner/same'}, self.Parser)
        proposed = [r['instance_id'] for r in records if r['proposed_each_repo']]
        self.assertEqual(proposed, [expected])
        self.assertEqual(s.summarize(records)['maximum_each_repository']['issues'], 1)

    def test_protected_id_excluded_using_metadata_only(self):
        ex = exclusions(); ex['protected_split_ids'].add(row(1)['instance_id'])
        records = s.screen_rows([row(1)], ex, set(), set(), set(), self.Parser)
        self.assertFalse(records[0]['qualified'])
        self.assertEqual(records[0]['history_reasons'], ['protected_split_id'])

    def test_all_failure_reasons_retained(self):
        stats = s.header_stats(MOD * 4)
        stats['new_file_mode'] = True
        self.assertEqual(s.four_reasons(1, stats), list(s.RULES))

    def test_save_bytes_is_immutable_and_csv_crlf_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(s, 'ROOT', root):
                path = root / 'rows.csv'; s.save_text(path, 'a,b\r\n1,2\r\n'); s.save_text(path, 'a,b\r\n1,2\r\n')
                with self.assertRaisesRegex(RuntimeError, 'Frozen screening bytes differ'):
                    s.save_text(path, 'changed')


if __name__ == '__main__': unittest.main()
