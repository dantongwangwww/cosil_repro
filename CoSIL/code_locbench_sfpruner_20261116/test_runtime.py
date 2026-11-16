"""Synthetic CPU tests for whole-roster preservation and archive-key concurrency."""
import json
from pathlib import Path
import tempfile
import unittest

from . import runtime as r


class ArchiveTests(unittest.TestCase):
    def test_four_distinct_issues_same_base_are_downloaded_once(self):
        rows = [{'instance_id': 'x__y-' + str(i), 'repo': 'x/y', 'base_commit': 'a'*40} for i in range(4)]
        unique = r.unique_archives(rows)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(unique), 1)
        self.assertEqual(next(iter(unique.values()))['instance_id'], rows[0]['instance_id'])

    def test_historical_cache_copy_is_verified_and_not_hardlinked(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = Path(folder)/'old', Path(folder)/'new'; old.mkdir(); new.mkdir()
            row = {'repo': 'x/y', 'base_commit': 'a'*40}; key = r.b.archive_key(**{'repo':row['repo'], 'base':row['base_commit']})
            body = old/(key+'.tar.gz'); body.write_bytes(b'complete synthetic archive')
            receipt = dict(row, archive_sha256=r.b.sha(body), bytes=body.stat().st_size)
            (old/(key+'.receipt.json')).write_text(json.dumps(receipt))
            old_bytes = body.read_bytes()
            copied = r.copy_verified_archive(row, old, new)
            self.assertEqual(copied['archive_sha256'], r.b.sha(body))
            self.assertNotEqual(body.stat().st_ino, (new/body.name).stat().st_ino)
            (new/body.name).write_bytes(b'changed new cache')
            self.assertEqual(body.read_bytes(), old_bytes)

    def test_bad_historical_hash_is_not_imported(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = Path(folder)/'old', Path(folder)/'new'; old.mkdir(); new.mkdir()
            row = {'repo': 'x/y', 'base_commit': 'a'*40}; key = r.b.archive_key(row['repo'],row['base_commit'])
            (old/(key+'.tar.gz')).write_bytes(b'wrong')
            (old/(key+'.receipt.json')).write_text(json.dumps(dict(row,archive_sha256='0'*64,bytes=5)))
            with self.assertRaisesRegex(ValueError, 'identity/hash'):
                r.copy_verified_archive(row, old, new)
            self.assertFalse(list(new.iterdir()))


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'instance_id': 'r__repo-'+str(i), 'repo': 'r/repo', 'base_commit': 'a'*40} for i in range(560)]
        self.alloc = {'records': self.rows}
        self.source = {'records': [{'instance_id': x['instance_id'], 'status': 'RUNTIME_PREPARATION_BLOCKED',
                     'runtime_preparation_blocked': True, 'runtime_preparation_errors': {'x.py': 'HTTP404'}} for x in self.rows]}

    def test_repeated_repos_and_preparation_failures_preserve560(self):
        selected = {'records': self.rows[:1]}
        rows = r.allocation_ledger(self.alloc, selected, self.source, self.rows[:1], {})
        self.assertEqual(len(rows),560)
        self.assertEqual(sum(x['runnable'] for x in rows),1)
        self.assertTrue(all(x['status']=='PREPARATION_BLOCKED' for x in rows[1:]))

    def test_missing_build_result_cannot_disappear(self):
        with self.assertRaisesRegex(ValueError, 'explicit builder failure'):
            r.allocation_ledger(self.alloc, {'records': self.rows[:1]}, self.source, [], {})

    def test_missing_selection_without_failure_evidence_is_not_blocked(self):
        self.source['records'][0]['status']='SOURCE_PROOF_READY'
        self.source['records'][0]['runtime_preparation_blocked']=False
        with self.assertRaisesRegex(ValueError, 'explicit preparation-blocked'):
            r.allocation_ledger(self.alloc, {'records': []}, self.source, [], {})

    def test_explicit_builder_failure_retains_its_issue(self):
        iid=self.rows[0]['instance_id']
        rows=r.allocation_ledger(self.alloc, {'records': self.rows[:1]},self.source,[],{iid:{'type':'SourceError'}})
        self.assertEqual(len(rows),560)
        self.assertEqual(rows[0]['errors']['type'],'SourceError')
        self.assertEqual(rows[0]['stage'],'runtime_builder')


if __name__ == '__main__':
    unittest.main()
