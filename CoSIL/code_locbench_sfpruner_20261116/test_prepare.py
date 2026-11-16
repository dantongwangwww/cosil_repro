"""Synthetic CPU checks for full-roster and base-only qualification boundaries."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from . import prepare as p


def row(targets=None):
    targets = targets or ['pkg/mod.py:C.__init__']
    return {'instance_id': 'owner__repo-1', 'repo': 'owner/repo',
        'base_commit': 'a'*40, 'problem_statement': 'Public issue text.',
        'patch': 'DO NOT INCLUDE REFERENCE PATCH', 'test_patch': 'SECRET TEST',
        'hints_text': 'DO NOT INCLUDE HINTS', 'edit_functions': targets,
        'edit_functions_length': len(targets),
        'added_functions': ['pkg/mod.py:future_function']}


class IdentityTests(unittest.TestCase):
    def test_legitimate_repository_component_and_constructor_remain(self):
        self.assertEqual(p.target_identity('repo/pkg.py:C.__init__'),
                         ('repo/pkg.py', 'C.__init__', 'repo/pkg.py::C.__init__'))

    def test_unsafe_or_malformed_target_rejected(self):
        for target in ('../x.py:f', '/x.py:f', 'x.py::f', 'x.py:', 'x.py:C..f', 'x.txt:f'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                p.target_identity(target)

    def test_roster_duplicates_cannot_be_silently_deduplicated(self):
        with self.assertRaisesRegex(ValueError, 'complete official roster'):
            p.validate_rows([row(), row()], expected_n=2)

    def test_class_is_not_a_function_target(self):
        r = row(['pkg/mod.py:C'])
        gold, _ = p.map_targets(r, {'pkg/mod.py': {'definitions': [
            {'qualified_name': 'C', 'kind': 'class'}], 'parse_error': None}}, {})
        self.assertFalse(gold['set_complete'])
        self.assertTrue(gold['missing_targets'][0]['reason']['class_with_same_name'])

    def test_incomplete_mapping_keeps_entire_official_set(self):
        r = row(['pkg/mod.py:C.f', 'pkg/mod.py:C.g'])
        gold, _ = p.map_targets(r, {'pkg/mod.py': {'definitions': [
            {'qualified_name': 'C.f', 'kind': 'function'}], 'parse_error': None}}, {})
        self.assertEqual(gold['targets'], ['pkg/mod.py::C.f', 'pkg/mod.py::C.g'])
        self.assertEqual(gold['mapped_targets'], ['pkg/mod.py::C.f'])
        self.assertEqual(gold['status'], 'INCOMPLETE')

    def test_python312_parser_retains_nested_async_and_init(self):
        module = p.q.gold_module()
        records, parser = p.parse_texts({'x.py': 'class C:\n def __init__(self):\n  pass\n async def f(self):\n  def inner():\n   pass\n'}, module.AST_WORKER)
        names = {d['qualified_name'] for d in records['x.py']['definitions'] if d['kind']=='function'}
        self.assertEqual(names, {'C.__init__', 'C.f', 'C.f.inner'})
        self.assertEqual(parser['version_info'][:2], [3, 12])


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.module = p.q.gold_module()

    def fetched(self, data):
        def fetcher(r, name, folder, **kwargs):
            self.assertTrue(kwargs['retry_blocked'])
            self.assertFalse(kwargs['offline_only'])
            folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
            path = folder / hashlib.sha256(name.encode()).hexdigest()
            path.write_bytes(data)
            return path, {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}
        return fetcher

    def prepare(self, r, fetcher):
        return p.prepare_one(r, self.root, {'protocol': 'synthetic'}, proxy=None,
            worker=self.module.AST_WORKER, decoder=self.module.decoded, fetcher=fetcher)

    def test_base_proof_public_projection_excludes_answers_and_added_target(self):
        result = self.prepare(row(), self.fetched(b'class C:\n def __init__(self):\n  pass\n'))
        self.assertFalse(result['runtime_preparation_blocked'])
        self.assertEqual(set(result['preparation_projection']), p.b.PREP_FIELDS)
        self.assertEqual(result['official_gold']['targets'], ['pkg/mod.py::C.__init__'])
        self.assertEqual(result['official_gold']['added_function_count_excluded'], 1)
        self.assertTrue(result['official_gold']['set_complete'])
        for forbidden in ('patch', 'test_patch', 'hints_text', 'edit_functions', 'targets'):
            self.assertNotIn(forbidden, result['preparation_projection'])

    def test_missing_gold_function_does_not_exclude_runnable_source(self):
        result = self.prepare(row(['pkg/mod.py:missing']), self.fetched(b'def other():\n pass\n'))
        self.assertEqual(result['status'], 'SOURCE_PROOF_READY')
        self.assertEqual(result['official_gold']['status'], 'INCOMPLETE')
        self.assertFalse(result['runtime_preparation_blocked'])

    def test_definitive_unavailable_keeps_a_blocked_case(self):
        def fetcher(*args, **kwargs):
            raise p.q.BaseUnavailable('HTTP 404')
        result = self.prepare(row(), fetcher)
        self.assertTrue(result['runtime_preparation_blocked'])
        self.assertIsNone(result['preparation_projection'])
        self.assertEqual(result['official_gold']['status'], 'SOURCE_UNAVAILABLE')
        self.assertEqual(result['official_gold']['targets'], ['pkg/mod.py::C.__init__'])

    def test_transient_unavailable_is_not_definitive_or_model_failure(self):
        def fetcher(*args, **kwargs):
            raise p.q.NetworkBlocked('timeout after fixed budget')
        result = self.prepare(row(), fetcher)
        self.assertEqual(result['official_gold']['status'], 'INCOMPLETE')
        self.assertEqual(result['runtime_preparation_errors']['pkg/mod.py']['type'], 'NETWORK_BLOCKED')
        self.assertEqual(result['model_calls'], 0)

    def test_resume_does_not_accept_changed_base_bytes(self):
        self.prepare(row(), self.fetched(b'class C:\n def __init__(self):\n  pass\n'))
        path = self.root/'cases/owner__repo-1/business_base/pkg/mod.py'
        path.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'base source changed'):
            self.prepare(row(), self.fetched(b'ignored'))


if __name__ == '__main__':
    unittest.main()
