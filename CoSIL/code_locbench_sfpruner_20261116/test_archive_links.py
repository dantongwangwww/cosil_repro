"""Archive link byte preservation, confinement and resource-limit checks."""
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from . import archive_links as a


def file(name, body=b'pass\n'):
    member = tarfile.TarInfo(name); member.size = len(body)
    return member, body


def directory(name):
    member = tarfile.TarInfo(name); member.type = tarfile.DIRTYPE
    return member, None


def link(name, target, hard=False):
    member = tarfile.TarInfo(name)
    member.type = tarfile.LNKTYPE if hard else tarfile.SYMTYPE
    member.linkname = target
    return member, None


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def archive(self, members):
        path = self.root / 'source.tar.gz'
        with tarfile.open(path, 'w:gz') as stream:
            for member, body in [directory('repo'), *members]:
                stream.addfile(member, None if body is None else io.BytesIO(body))
        return path

    def extract(self, members):
        archive = self.archive(members); snapshot = self.root / 'snapshot'
        raw = archive.read_bytes()
        result = a.extract_archive(archive, snapshot)
        self.assertEqual(raw, archive.read_bytes())
        self.assertFalse(any(p.is_symlink() for p in snapshot.rglob('*')))
        self.assertEqual(result['archive_link_materialization']['archive_sha256'], a.b.sha(archive))
        return snapshot, result

    def blocked(self, members, pattern='BLOCKED|Duplicate|Unsupported|multiple roots'):
        archive = self.archive(members); snapshot = self.root / 'snapshot'
        with self.assertRaisesRegex(ValueError, pattern):
            a.extract_archive(archive, snapshot)
        self.assertFalse(snapshot.exists())
        self.assertEqual(list(self.root.glob('.snapshot.*')), [])

    def test_aiohttp_sibling_python_symlink_copies_exact_15390bytes(self):
        raw = b'#' * 15389 + b'\n'
        snapshot, result = self.extract([
            directory('repo/aiohttp/_websocket'),
            file('repo/aiohttp/_websocket/reader_py.py', raw),
            link('repo/aiohttp/_websocket/reader_c.py', 'reader_py.py')])
        self.assertEqual((snapshot/'aiohttp/_websocket/reader_c.py').read_bytes(), raw)
        self.assertEqual(result['python_sha256']['aiohttp/_websocket/reader_c.py'], a.b.digest(raw))
        event = result['archive_link_materialization']['materialized_python_links'][0]
        self.assertEqual(event['resolved_member'], 'repo/aiohttp/_websocket/reader_py.py')
        self.assertFalse(event['host_link_created'])

    def test_internal_parent_relative_chain_is_resolved_to_regular_bytes(self):
        snapshot, result = self.extract([file('repo/pkg/real.py', b'def f(): pass\n'),
            link('repo/pkg/sub/mid.py', '../real.py'),
            link('repo/pkg/deeper/alias.py', '../sub/mid.py')])
        self.assertEqual((snapshot/'pkg/deeper/alias.py').read_bytes(), b'def f(): pass\n')
        event = next(x for x in result['archive_link_materialization']['materialized_python_links']
                     if x['path']=='pkg/deeper/alias.py')
        self.assertEqual(len(event['chain']), 3)

    def test_archive_hardlink_namespace_is_not_host_or_parent_relative(self):
        snapshot, result = self.extract([file('repo/pkg/real.py', b'one\n'),
            link('repo/pkg/alias.py', 'repo/pkg/real.py', hard=True)])
        self.assertEqual((snapshot/'pkg/alias.py').read_bytes(), b'one\n')
        self.assertEqual(result['archive_link_materialization']['materialized_python_links'][0]['type'], 'hardlink')

    def test_ordinary_archive_keeps_original_outputs_and_all_source_bytes(self):
        archive = self.archive([file('repo/a.py', b'print(1)\r\n'),
            file('repo/docs/data.txt', b'other'), file('repo/.git/config', b'ignored'),
            link('repo/ignored.txt', '/not/materialized')])
        original = a.b.extract_archive(archive, self.root/'old')
        adapted = a.extract_archive(archive, self.root/'new')
        audit = adapted.pop('archive_link_materialization')
        self.assertEqual(original, adapted)
        self.assertEqual((self.root/'old/a.py').read_bytes(), (self.root/'new/a.py').read_bytes())
        self.assertFalse((self.root/'new/ignored.txt').exists())
        self.assertEqual(audit['ignored_nonpython_links'], 1)

    def test_absolute_symlink_is_rejected(self):
        self.blocked([link('repo/a.py', '/etc/passwd')], 'ABSOLUTE')

    def test_windows_absolute_link_is_rejected(self):
        self.blocked([link('repo/a.py', 'C:/outside.py')], 'ABSOLUTE')

    def test_escape_even_if_later_components_return_is_rejected(self):
        self.blocked([link('repo/pkg/a.py', '../../repo/b.py'), file('repo/b.py')], 'ESCAPE')

    def test_cross_root_hardlink_is_rejected(self):
        self.blocked([link('repo/a.py', 'other/a.py', hard=True)], 'OTHER_ROOT')

    def test_cyclic_links_are_rejected(self):
        self.blocked([link('repo/a.py','b.py'),link('repo/b.py','a.py')], 'CYCLE')

    def test_missing_final_target_is_rejected(self):
        self.blocked([link('repo/a.py','missing.py')], 'MISSING')

    def test_directory_as_file_target_is_rejected(self):
        self.blocked([directory('repo/pkg'),link('repo/a.py','pkg')], 'NOT_REGULAR')

    def test_nondirectory_ancestor_is_rejected(self):
        self.blocked([file('repo/pkg'),file('repo/pkg/a.py')], 'NON_DIRECTORY_ANCESTOR')

    def test_duplicate_member_is_rejected(self):
        self.blocked([file('repo/a.py'),file('repo/a.py')], 'Duplicate')

    def test_device_member_is_rejected(self):
        member = tarfile.TarInfo('repo/device'); member.type = tarfile.CHRTYPE
        self.blocked([(member,None),file('repo/a.py')], 'Unsupported')

    def test_git_metadata_cannot_be_reached_through_python_alias(self):
        self.blocked([file('repo/.git/hidden.py'),link('repo/a.py','.git/hidden.py')], 'SCOPE')

    def test_path_traversal_member_is_rejected(self):
        self.blocked([file('repo/../a.py')], 'Unsafe')

    def test_oversized_member_is_rejected_and_temporary_removed(self):
        with patch.object(a.b,'MAX_MEMBER_BYTES',4):
            self.blocked([file('repo/a.py',b'12345')], 'RESOURCE_LIMIT')

    def test_expanded_byte_cap_is_not_bypassed(self):
        with patch.object(a.b,'MAX_EXPANDED_BYTES',5):
            self.blocked([file('repo/a.py',b'1234'),file('repo/data',b'12')], 'RESOURCE_LIMIT')

    def test_python_logical_cap_counts_every_materialized_alias(self):
        with patch.object(a.b,'MAX_PYTHON_BYTES',6):
            self.blocked([file('repo/real.py',b'1234'),link('repo/a.py','real.py')], 'PYTHON_RESOURCE_LIMIT')

    def test_member_count_bound_is_enforced(self):
        with patch.object(a,'MAX_MEMBERS',2):
            self.blocked([file('repo/a.py'),file('repo/b.py')], 'RESOURCE_LIMIT')

    def test_chain_depth_is_bounded(self):
        with patch.object(a,'MAX_LINK_HOPS',2):
            self.blocked([link('repo/a.py','b.py'),link('repo/b.py','c.py'),
                link('repo/c.py','r.py'),file('repo/r.py')], 'DEPTH')

    def test_enabled_restores_original_on_exception_and_rejects_nested_use(self):
        original = a.b.extract_archive
        with self.assertRaisesRegex(RuntimeError,'intentional'):
            with a.enabled():
                self.assertIs(a.b.extract_archive,a.extract_archive)
                with self.assertRaisesRegex(RuntimeError,'already active'):
                    with a.enabled():
                        pass
                raise RuntimeError('intentional')
        self.assertIs(a.b.extract_archive,original)


if __name__ == '__main__':
    unittest.main()
