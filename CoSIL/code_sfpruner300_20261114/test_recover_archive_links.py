"""Archive-link recovery tests use tiny CPU source fixtures, no model calls."""
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recover_archive_links as r
import build_runtime as b
from test_build_runtime import BASE, SOURCE, make_tar, prep, selection


class NormalizeTests(unittest.TestCase):
    def test_every_link_is_discarded_without_following_ordinary_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = make_tar(root / 'original.tar.gz', [
                ('src/代码.py', SOURCE, tarfile.REGTYPE), ('README.md', b'plain', tarfile.REGTYPE),
                ('tests/link.py', b'', tarfile.SYMTYPE), ('hard.py', b'', tarfile.LNKTYPE),
                ('docs/link', b'', tarfile.SYMTYPE)])
            old = b.sha(original); meta = {'archive_sha256': old, 'repo': 'owner/repo', 'base_commit': BASE}
            receipt = r.normalize_archive(original, root / 'normalized.tar.gz', root / 'normalization.json', meta)
            self.assertEqual(b.sha(original), old)
            self.assertEqual(len(receipt['discarded_links']), 3)
            self.assertTrue(all(not x['followed'] and not x['materialized'] for x in receipt['discarded_links']))
            extracted = b.extract_archive(root / 'normalized.tar.gz', root / 'snapshot')
            self.assertEqual(extracted['paths'], ['README.md', 'src/代码.py'])
            self.assertEqual((root / 'snapshot/src/代码.py').read_bytes(), SOURCE)
            self.assertEqual(len(receipt['ordinary_file_sha256']), 2)
            self.assertEqual(r.normalize_archive(original, root / 'normalized.tar.gz', root / 'normalization.json', meta), receipt)
            self.assertIn('normalized derivative', receipt['source_scope'])

    def test_traversal_and_devices_still_rejected(self):
        for rows in ([('../evil.py', SOURCE, tarfile.REGTYPE)], [('device', b'', tarfile.CHRTYPE)]):
            with self.subTest(rows=rows), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); original = make_tar(root / 'a.tar.gz', rows)
                with self.assertRaises(ValueError):
                    r.normalize_archive(original, root / 'n.tar.gz', root / 'receipt.json', {'archive_sha256': b.sha(original)})
                self.assertFalse((root / 'n.tar.gz').exists())
                self.assertFalse((root / 'receipt.json').exists())

    def test_source_and_normalized_tar_hashes_are_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); original = make_tar(root / 'a.tar.gz', [('a.py', SOURCE, tarfile.REGTYPE)])
            metadata = {'archive_sha256': b.sha(original)}
            r.normalize_archive(original, root / 'n.tar.gz', root / 'receipt.json', metadata)
            (root / 'n.tar.gz').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                r.normalize_archive(original, root / 'n.tar.gz', root / 'receipt.json', metadata)


class RecoveryTests(unittest.TestCase):
    def fixture(self, root):
        row1 = prep();row2 = {**row1, 'instance_id': 'owner2__repo2-2', 'repo': 'owner2/repo2'}
        rows = [row1, row2]; records = [selection(row) for row in rows]
        selected = {'status': 'READY', 'selection_frozen': True, 'n': 2, 'records': records}
        b.write(root / 'selection.json', selected);b.write(root / 'preparations.json', {'records': rows})
        runtime, private, cache = root / 'runtime', root / 'v1_private', root / 'cache';cache.mkdir()
        first = make_tar(root / 'first.tar.gz', [('src/代码.py', SOURCE, tarfile.REGTYPE)])
        second = make_tar(cache / (b.archive_key(row2['repo'], BASE) + '.tar.gz'), [
            ('src/代码.py', SOURCE, tarfile.REGTYPE), ('tests/unrelated.py', b'', tarfile.SYMTYPE)])
        original_receipt = {'repo': row2['repo'], 'base_commit': BASE, 'archive_sha256': b.sha(second),
                            'url': 'https://codeload.github.com/owner2/repo2/tar.gz/' + BASE}
        b.write(cache / (b.archive_key(row2['repo'], BASE) + '.receipt.json'), original_receipt)
        first_record = b.build_one(records[0], row1, runtime, private / 'cases', cache,
                                  downloader=lambda row, _: (first, {'archive_sha256': b.sha(first)}))
        with self.assertRaisesRegex(ValueError, 'BLOCKED_PYTHON_LINK'):
            b.build_one(records[1], row2, runtime, private / 'cases', cache,
                        downloader=lambda row, _: (second, original_receipt))
        error = {'type': 'ValueError', 'error': 'BLOCKED_PYTHON_LINK: tests/unrelated.py'}
        b.write(private / 'contract.json', {'selection_sha256': b.sha(root / 'selection.json'),
                'preparations_sha256': b.sha(root / 'preparations.json'), 'builder_sha256': b.sha(b.__file__)})
        b.write(private / 'progress.json', {'selected': 2, 'complete': 1, 'blocked': {row2['instance_id']: error}})
        b.write(private / 'errors' / (row2['instance_id'] + '.json'), error)
        return runtime, private, cache, row2, second, first_record

    def test_recovery_preserves_v1_all_selected_and_source_bytes_and_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);runtime, private, cache, row2, original, first = self.fixture(root)
            progress_sha = b.sha(private / 'progress.json');error_sha = b.sha(private / 'errors' / (row2['instance_id'] + '.json'))
            receipt = r.recover(root / 'selection.json', root / 'preparations.json', runtime, private,
                                root / 'recovery', cache, expected_count=2)
            self.assertEqual(receipt['status'], 'READY');self.assertEqual(receipt['n'], 2)
            manifest = b.read(runtime / 'manifest.json')
            self.assertEqual(manifest['records'][0], first)
            self.assertEqual([x['instance_id'] for x in manifest['records']], ['owner__repo-1', 'owner2__repo2-2'])
            self.assertEqual(b.sha(private / 'progress.json'), progress_sha)
            self.assertEqual(b.sha(private / 'errors' / (row2['instance_id'] + '.json')), error_sha)
            self.assertEqual((runtime / 'tasks/owner2__repo2-2/snapshot/src/代码.py').read_bytes(), SOURCE)
            self.assertNotIn('tests/unrelated.py', b.read(runtime / 'tasks/owner2__repo2-2/job.json')['paths'])
            again = r.recover(root / 'selection.json', root / 'preparations.json', runtime, private,
                              root / 'recovery', cache, expected_count=2)
            self.assertEqual(again, receipt)
            ledger = b.read(receipt['recovery_ledger_path'])
            self.assertEqual(len(ledger['recovered_tasks']), 1)
            self.assertTrue(ledger['v1_errors_preserved'])

    def test_unrelated_errors_do_not_get_masked_by_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);runtime, private, cache, row2, _, _ = self.fixture(root)
            value = b.read(private / 'progress.json');value['blocked'][row2['instance_id']] = {'error': 'different failure'}
            b.write(private / 'progress.json', value, immutable=False)
            with self.assertRaisesRegex(RuntimeError, 'Unrelated'):
                r.recover(root / 'selection.json', root / 'preparations.json', runtime, private,
                          root / 'recovery', cache, expected_count=2)
            self.assertFalse((runtime / 'manifest.json').exists())

    def test_successful_v1_asset_tampering_blocks_finalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);runtime, private, cache, _, _, _ = self.fixture(root)
            (runtime / 'tasks/owner__repo-1/snapshot/src/代码.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA changed'):
                r.recover(root / 'selection.json', root / 'preparations.json', runtime, private,
                          root / 'recovery', cache, expected_count=2)
            self.assertFalse((runtime / 'manifest.json').exists())

    def test_required_qualification_file_cannot_be_replaced_by_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = make_tar(root / 'a.tar.gz', [('src/代码.py', b'', tarfile.SYMTYPE)])
            info = {'archive_sha256': b.sha(archive)}
            r.normalize_archive(archive, root / 'n.tar.gz', root / 'receipt.json', info)
            # No normal Python target remains: source qualification cannot pass.
            with self.assertRaisesRegex(ValueError, 'No base Python'):
                b.extract_archive(root / 'n.tar.gz', root / 'snapshot')

    def network_fixture(self, root):
        runtime, private, cache, row, archive, first = self.fixture(root)
        make_tar(archive, [('src/代码.py', SOURCE, tarfile.REGTYPE), ('README.md', b'public', tarfile.REGTYPE)])
        value = b.read(private / 'progress.json')
        value['blocked'][row['instance_id']] = {'error': 'BLOCKED_ARCHIVE_DOWNLOAD: fixed proxy attempts exhausted'}
        b.write(private / 'progress.json', value, immutable=False)
        direct = root / 'direct.json'
        b.write(direct, {'instance_id': row['instance_id'], 'repo': row['repo'], 'base_commit': BASE,
                        'archive_sha256': b.sha(archive), 'attempts': 1, 'transport': 'direct', 'status': 'complete'})
        evidence = {'instance_id': row['instance_id'], 'repo': row['repo'], 'base_commit': BASE,
                    'status': 'VERIFIED_ARCHIVE_READY', 'archive_path': str(archive.resolve()),
                    'archive_sha256': b.sha(archive), 'direct_ledger_path': str(direct.resolve()),
                    'direct_ledger_sha256': b.sha(direct)}
        b.write(root / 'network_evidence.json', {'records': [evidence]})
        return runtime, private, cache, row, evidence

    def test_verified_direct_cache_has_distinct_evidence_and_no_new_http_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);runtime, private, cache, row, _ = self.network_fixture(root)
            old_progress_sha = b.sha(private / 'progress.json')
            with patch.object(b, 'download_archive', side_effect=AssertionError('No new HTTP')):
                receipt = r.recover(root / 'selection.json', root / 'preparations.json', runtime, private,
                                    root / 'recovery', cache, expected_count=2,
                                    verified_network_recoveries=root / 'network_evidence.json')
            ledger = b.read(receipt['recovery_ledger_path'])
            recovered = ledger['recovered_tasks'][0]
            self.assertEqual(recovered['recovery_type'], 'verified_direct_archive_recovery')
            self.assertIsNone(recovered['normalization'])
            self.assertEqual(recovered['verified_direct_archive_recovery']['status'], 'VERIFIED_ARCHIVE_READY')
            self.assertEqual(b.sha(private / 'progress.json'), old_progress_sha)
            self.assertEqual(b.read(runtime / 'manifest.json')['n'], 2)

    def test_direct_recovery_identity_and_ledger_sha_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);runtime, private, cache, row, evidence = self.network_fixture(root)
            selected = b.read(root / 'selection.json')
            bad = {**evidence, 'base_commit': '7' * 40}
            b.write(root / 'bad.json', {'records': [bad]})
            with self.assertRaisesRegex(ValueError, 'base drift'):
                r.verified_network_evidence(root / 'bad.json', selected, cache)
            bad = {**evidence, 'direct_ledger_sha256': '0' * 64}
            b.write(root / 'bad_ledger.json', {'records': [bad]})
            with self.assertRaisesRegex(ValueError, 'ledger SHA'):
                r.verified_network_evidence(root / 'bad_ledger.json', selected, cache)
            self.assertFalse((runtime / 'manifest.json').exists())


if __name__ == '__main__': unittest.main()
