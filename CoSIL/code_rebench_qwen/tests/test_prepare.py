"""Synthetic CPU checks; no benchmark gold, provider, GPU or network access."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'prepare.py'
spec = importlib.util.spec_from_file_location('base_prepare', MODULE)
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='cosil_prepare_unit_')
        self.root = Path(self.temporary.name)
        self.base = self.root / 'old_base';self.base.mkdir()
        self.output = self.root / 'new_inputs'
        self.source = self.root / 'old_job.json'
        self.receipt = self.root / 'old_cpu_receipt.json'

    def tearDown(self):
        self.temporary.cleanup()

    def fixture(self, text='def old():\n    return 1\n'):
        raw = text.encode()
        (self.base / 'module.py').write_bytes(raw)
        job = {'instance_id': 'repo__case-1', 'repo': 'repo/case', 'base_commit': 'a' * 40,
               'problem_statement': 'A public issue only.', 'cohort': 'prior',
               'snapshot': str(self.base), 'paths': ['module.py', 'README.md'],
               'code_index': str(self.root / 'not_read_old_index.json'),
               'structure': str(self.root / 'not_read_old_structure.json')}
        self.source.write_text(json.dumps(job))
        receipt = {'instance_id': job['instance_id'], 'base_commit': job['base_commit'],
                   'data_sha256': {str(self.source): P.sha(self.source)},
                   'snapshot_sha256': {str(self.base / 'module.py'): P.sha(self.base / 'module.py')}}
        self.receipt.write_text(json.dumps(receipt))
        row = {k: job[k] for k in ('instance_id', 'repo', 'base_commit')}
        row.update(job=str(self.source), preparation_receipt=str(self.receipt), origin='new221')
        return row, job

    def spec(self, row):
        return P.case_spec(row, self.output, 'f' * 64, 'new_clean_cohort')

    def execute(self, row):
        return P.subprocess_case(self.spec(row), '/usr/bin/python3.12')

    def test_clean_job_exact_nine_fields_and_original_input_unchanged(self):
        row, old = self.fixture()
        before = {p: P.sha(p) for p in (self.source, self.receipt, self.base / 'module.py')}
        result = self.execute(row)
        clean = P.read_json(result['job'])
        self.assertEqual(set(clean), P.CLEAN_KEYS)
        self.assertEqual(clean['base_commit'], old['base_commit'])
        self.assertEqual(clean['snapshot'], str(self.base.resolve()))
        self.assertEqual(clean['paths'], old['paths'])
        self.assertEqual(before, {p: P.sha(p) for p in before})
        self.assertTrue(Path(clean['code_index']).is_relative_to(self.output))
        self.assertTrue(Path(clean['structure']).is_relative_to(self.output))
        self.assertFalse(Path(old['code_index']).exists())

    def test_nested_async_class_and_same_qn_spans_preserved(self):
        row, _ = self.fixture('''async def outer():
    async def inner():
        return 1
    class Inside:
        def method(self):
            def local():
                return 2
            return local()
    return inner
class C:
    @property
    def value(self):
        return 1
    @value.setter
    def value(self, value):
        self._value = value
''')
        result = self.execute(row);index = P.read_json(result['code_index'])['module.py']
        names = [d['qualified_name'] for d in index['definitions']]
        self.assertIn('outer.inner', names)
        self.assertIn('outer.Inside.method.local', names)
        self.assertEqual(names.count('C.value'), 2)
        leaf = P.read_json(result['structure'])['structure']['module.py']
        self.assertEqual([x['name'] for x in leaf['functions']], ['outer', 'outer.inner'])
        inside = next(c for c in leaf['classes'] if c['name'] == 'outer.Inside')
        self.assertEqual([m['name'] for m in inside['methods']], ['method', 'method.local'])
        c = next(c for c in leaf['classes'] if c['name'] == 'C')
        self.assertEqual([m['name'] for m in c['methods']], ['value', 'value'])

    def test_python312_syntax_is_indexed_by_actual312_subprocess(self):
        row, _ = self.fixture('type Number = int\ndef identity[T](x: T) -> T:\n    return x\n')
        result = self.execute(row)
        index = P.read_json(result['code_index'])['module.py']
        self.assertIsNone(index['parse_error'])
        self.assertIn('identity', [d['qualified_name'] for d in index['definitions']])
        self.assertTrue(result['python_ast_version'].startswith('3.12.'))

    def test_line_coordinates_ignore_formfeed_and_unicode_line_separator(self):
        row, _ = self.fixture('def outer():\n    text = "a\fb\u2028c"\n    def inner():\n        return text\n')
        result = self.execute(row)
        index = P.read_json(result['code_index'])['module.py']
        self.assertEqual(index['lines'], 4)
        inner = next(d for d in index['definitions'] if d['qualified_name'] == 'outer.inner')
        self.assertEqual((inner['start_line'], inner['end_line']), (3, 4))
        leaf = P.read_json(result['structure'])['structure']['module.py']
        self.assertEqual(len(leaf['text']), 4)
        self.assertEqual(leaf['functions'][1]['text'], ['    def inner():', '        return text'])

    def test_legacy_receipt_without_base_field_uses_verified_clean_job_identity(self):
        row, _ = self.fixture()
        receipt = P.read_json(self.receipt);receipt.pop('base_commit')
        self.receipt.write_text(json.dumps(receipt))
        self.assertEqual(self.execute(row)['base_commit'], 'a' * 40)

    def test_parse_failure_keeps_file_source_and_case(self):
        row, _ = self.fixture('def broken(:\n    return 1\n')
        result = self.execute(row)
        self.assertEqual(result['status'], 'complete')
        index = P.read_json(result['code_index'])['module.py']
        self.assertEqual(index['parse_error'], 'SyntaxError')
        self.assertEqual(index['definitions'], [])
        self.assertEqual(P.read_json(result['structure'])['structure']['module.py']['text'][0], 'def broken(:')
        self.assertEqual(result['source_files'], 1)

    def test_decoding_failure_is_retained_and_audited(self):
        row, _ = self.fixture()
        (self.base / 'module.py').write_bytes(b'\xff\n')
        receipt = P.read_json(self.receipt)
        receipt['snapshot_sha256'][str(self.base / 'module.py')] = P.sha(self.base / 'module.py')
        self.receipt.write_text(json.dumps(receipt))
        result = self.execute(row)
        self.assertEqual(result['decode_error_files'], 1)
        self.assertIn('module.py', P.read_json(result['code_index']))

    def test_answer_field_rejected_before_output(self):
        row, _ = self.fixture()
        dirty = P.read_json(self.source);dirty['patch'] = 'must never reach a model'
        self.source.write_text(json.dumps(dirty))
        with self.assertRaisesRegex(ValueError, 'nine clean'):
            self.spec(row)
        self.assertFalse(self.output.exists())

    def test_same_manifest_identity_requires_full_matching_base_sha(self):
        row, _ = self.fixture();row['base_commit'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.spec(row)

    def test_source_sha_drift_rejected_without_overwriting_original(self):
        row, _ = self.fixture();original = P.sha(self.source)
        (self.base / 'module.py').write_text('def changed():\n    pass\n')
        with self.assertRaisesRegex(RuntimeError, 'SHA mismatch'):
            self.execute(row)
        self.assertEqual(P.sha(self.source), original)
        self.assertFalse((self.output / row['instance_id'] / 'job.json').exists())

    def test_full_snapshot_coverage_not_old_index_filter(self):
        row, _ = self.fixture();(self.base / 'extra.py').write_text('def extra():\n    pass\n')
        with self.assertRaisesRegex(RuntimeError, 'inventory differs'):
            self.execute(row)

    def test_repeat_uses_exact_immutable_preparation_and_refuses_drift(self):
        row, _ = self.fixture();result = self.execute(row)
        before = P.sha(result['job'])
        self.assertEqual(self.execute(row)['data_sha256'], result['data_sha256'])
        self.assertEqual(P.sha(result['job']), before)
        Path(result['code_index']).write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'artifact changed'):
            self.execute(row)

    def test_safe_path_and_symlink_rejection(self):
        for name in ('../file.py', '/file.py', 'a/../b.py', 'a\\b.py'):
            with self.assertRaises(ValueError):
                P.relative_path(name)
        row, _ = self.fixture();(self.base / 'symlink.py').symlink_to(self.base / 'module.py')
        with self.assertRaisesRegex(RuntimeError, 'Nonregular'):
            self.execute(row)

    def test_raw_vs_decoded_hash_semantics(self):
        raw = b'\xef\xbb\xbfdef f():\r\n    pass\r\n'
        item, text = P.index_file('module.py', raw)
        self.assertEqual(item['raw_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(item['sha256'], hashlib.sha256(text.encode('utf-8')).hexdigest())
        self.assertNotEqual(item['sha256'], item['raw_sha256'])
        self.assertIn('\r\n', text)


if __name__ == '__main__':
    unittest.main()
