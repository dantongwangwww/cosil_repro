"""Clean runtime safety, identity, exact-source and real CPU build tests."""
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_runtime as b

SOURCE = b'class C:\n    async def f(self):\n        return 1\n'
BASE = '1' * 40


def make_tar(path, rows):
    with tarfile.open(path, 'w:gz') as out:
        root = tarfile.TarInfo('repo-' + BASE); root.type = tarfile.DIRTYPE; out.addfile(root)
        for name, raw, kind in rows:
            item = tarfile.TarInfo('repo-' + BASE + '/' + name)
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = len(raw); out.addfile(item, io.BytesIO(raw))
            else:
                item.linkname = '../../outside'; out.addfile(item)
    return path


def prep():
    return {'instance_id': 'owner__repo-1', 'repo': 'owner/repo', 'base_commit': BASE,
            'problem_statement': 'A public issue body.', 'source_id': 'full',
            'source_revision': '2' * 40, 'source_sha256': '3' * 64,
            'base_files_sha256': {'src/代码.py': b.digest(SOURCE)}}


def selection(row):
    return {key: row[key] for key in ('instance_id', 'repo', 'base_commit',
            'source_id', 'source_revision', 'source_sha256')} | {'source': 'nebius/SWE-rebench'}


class ArchiveTests(unittest.TestCase):
    def test_only_python_materialized_all_normal_paths_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = make_tar(root / 'base.tar.gz', [
                ('src/代码.py', SOURCE, tarfile.REGTYPE), ('README.md', b'hello', tarfile.REGTYPE),
                ('.git/config', b'private', tarfile.REGTYPE)])
            info = b.extract_archive(archive, root / 'snapshot')
            self.assertEqual(info['paths'], ['README.md', 'src/代码.py'])
            self.assertEqual((root / 'snapshot/src/代码.py').read_bytes(), SOURCE)
            self.assertEqual([p.relative_to(root / 'snapshot').as_posix()
                              for p in (root / 'snapshot').rglob('*') if p.is_file()], ['src/代码.py'])

    def test_traversal_python_links_duplicate_and_device_refused(self):
        cases = [
            [('src/../../outside.py', SOURCE, tarfile.REGTYPE)],
            [('src/a.py', b'', tarfile.SYMTYPE)],
            [('a.py', SOURCE, tarfile.REGTYPE), ('a.py', SOURCE, tarfile.REGTYPE)],
            [('device', b'', tarfile.CHRTYPE)],
        ]
        for rows in cases:
            with self.subTest(rows=rows), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); archive = make_tar(root / 'x.tar.gz', rows)
                with self.assertRaises(ValueError): b.extract_archive(archive, root / 'snapshot')
                self.assertFalse((root / 'outside.py').exists())
                self.assertFalse((root / 'snapshot').exists())

    def test_multiple_roots_and_resource_limit_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); archive = root / 'x.tar.gz'
            with tarfile.open(archive, 'w:gz') as out:
                for name in ('one/a.py', 'two/b.py'):
                    item = tarfile.TarInfo(name); item.size = len(SOURCE);out.addfile(item, io.BytesIO(SOURCE))
            with self.assertRaisesRegex(ValueError, 'multiple roots'):
                b.extract_archive(archive, root / 'snapshot')
            make_tar(archive, [('a.py', SOURCE, tarfile.REGTYPE)])
            with patch.object(b, 'MAX_PYTHON_BYTES', 1), self.assertRaisesRegex(ValueError, 'RESOURCE_LIMIT'):
                b.extract_archive(archive, root / 'snapshot')

    def test_qualification_sha_and_target_parse_errors_never_relaxed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root / 'src/代码.py'; p.parent.mkdir();p.write_bytes(SOURCE)
            b.verify_qualified(root, prep()['base_files_sha256'])
            with self.assertRaisesRegex(ValueError, 'SOURCE_MISMATCH'):
                b.verify_qualified(root, {'src/代码.py': '0' * 64})
            with self.assertRaisesRegex(ValueError, 'SOURCE_AST'):
                b.verify_qualified(root, prep()['base_files_sha256'], {'src/代码.py': {'parse_error': 'SyntaxError'}})


class DownloadTests(unittest.TestCase):
    def test_network_lifetime_attempt_cap_survives_new_invocation(self):
        import requests
        class Broken:
            calls = 0
            def get(self, *args, **kwargs):
                self.calls += 1; raise requests.ConnectionError('fixture offline')
        with tempfile.TemporaryDirectory() as tmp, patch.object(b.time, 'sleep'):
            client = Broken()
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, 'BLOCKED_ARCHIVE_DOWNLOAD'):
                    b.download_archive(prep(), Path(tmp), session=client)
            self.assertEqual(client.calls, 3)
            records = [json.loads(line) for p in Path(tmp).glob('*.attempts.jsonl') for line in p.read_text().splitlines()]
            self.assertEqual([r['attempt'] for r in records if r['status'] == 'started'], [1, 2, 3])

    def test_cached_archive_bytes_bound_to_repo_base_and_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp); row = prep(); key = b.archive_key(row['repo'], BASE)
            p = make_tar(cache / (key + '.tar.gz'), [('a.py', SOURCE, tarfile.REGTYPE)])
            value = {'repo': row['repo'], 'base_commit': BASE, 'archive_sha256': b.sha(p)}
            b.write(cache / (key + '.receipt.json'), value)
            self.assertEqual(b.download_archive(row, cache)[0], p)
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA changed'): b.download_archive(row, cache)


class RuntimeTests(unittest.TestCase):
    def inputs(self, root):
        row = prep(); selected = selection(row)
        b.write(root / 'selection.json', {'status': 'READY', 'selection_frozen': True, 'n': 1, 'records': [selected]})
        b.write(root / 'preparations.json', {'records': [row]})
        return row, selected

    def test_input_sidecars_reject_gold_and_selection_source_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); row, selected = self.inputs(root)
            b.load_inputs(root / 'selection.json', root / 'preparations.json')
            row['patch'] = 'not allowed'
            (root / 'preparations.json').write_text(json.dumps({'records': [row]}))
            with self.assertRaisesRegex(ValueError, 'public/source-SHA'): b.load_inputs(root / 'selection.json', root / 'preparations.json')
            row.pop('patch');row['source_sha256'] = '4' * 64
            (root / 'preparations.json').write_text(json.dumps({'records': [row]}))
            with self.assertRaisesRegex(ValueError, 'identity drift'): b.load_inputs(root / 'selection.json', root / 'preparations.json')

    def test_real_python312_index_cache_controller_compatible_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); row, selected = self.inputs(root)
            archive = make_tar(root / 'base.tar.gz', [('src/代码.py', SOURCE, tarfile.REGTYPE), ('README.md', b'hello', tarfile.REGTYPE)])
            calls = []
            def local_download(r, cache):
                calls.append(r['instance_id']);return archive, {'archive_sha256': b.sha(archive), 'offline_fixture': True}
            result = b.build_one(selected, row, root / 'runtime', root / 'private', root / 'cache', downloader=local_download)
            task = root / 'runtime/tasks' / row['instance_id']
            job = b.load_job(task / 'job.json');self.assertEqual(set(job), b.validate_clean_job(job).keys())
            self.assertEqual(job['paths'], ['README.md', 'src/代码.py'])
            index = b.read(task / 'code_index.json')
            self.assertEqual([d['qualified_name'] for d in index['src/代码.py']['definitions']], ['C', 'C.f'])
            self.assertFalse(index['src/代码.py']['parse_error'])
            cache = b.read(task / 'render_cache.json'); self.assertEqual(cache['base_commit'], BASE)
            self.assertTrue(cache['functions'])
            b.write(root / 'runtime/manifest.json', {'n': 1, 'records': [result]})
            import controller
            _, records = controller.load_manifest(root / 'runtime/manifest.json')
            self.assertEqual(records[0]['instance_id'], row['instance_id'])
            self.assertEqual(b.build_one(selected, row, root / 'runtime', root / 'private', root / 'cache', downloader=local_download), result)
            self.assertEqual(len(calls), 1)
            (task / 'code_index.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'asset changed'):
                b.build_one(selected, row, root / 'runtime', root / 'private', root / 'cache', downloader=local_download)

    def test_verified_legacy_sources_are_copied_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);row, selected = self.inputs(root)
            archive = make_tar(root / 'base.tar.gz', [('src/代码.py', SOURCE, tarfile.REGTYPE)])
            first = b.build_one(selected, row, root / 'oldruntime', root / 'private1', root / 'cache',
                                downloader=lambda r, c: (archive, {'offline_fixture': True}))
            oldtask = root / 'oldruntime/tasks' / row['instance_id']
            old = {'instance_id': row['instance_id'], 'repo': row['repo'], 'base_commit': BASE,
                   'status': 'complete', 'job': str(oldtask / 'job.json'),
                   'data_sha256': {str(p): b.sha(p) for p in oldtask.rglob('*') if p.is_file()}}
            def forbidden(r, c): raise AssertionError('Legacy task unexpectedly downloaded')
            second = b.build_one(selected, row, root / 'newruntime', root / 'private2', root / 'cache', legacy=old, downloader=forbidden)
            self.assertEqual(second['source_files'], first['source_files'])
            self.assertEqual((root / 'newruntime/tasks'/row['instance_id']/'snapshot/src/代码.py').read_bytes(), SOURCE)
            receipt = b.read(root / 'private2' / (row['instance_id'] + '.json'))
            self.assertEqual(receipt['origin']['origin'], 'verified_legacy_base_assets')

    def test_private_runtime_roots_cannot_overlap(self):
        row = prep()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'disjoint'):
                b.build_one(selection(row), row, root, root/'private', root/'cache')


if __name__ == '__main__': unittest.main()
