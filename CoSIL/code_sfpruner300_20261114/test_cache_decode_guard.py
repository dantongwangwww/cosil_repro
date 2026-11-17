"""Decoder-fixture preparation regression and valid-source equivalence."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cache_decode_guard as guard
from specprune import runtime_renderer


class DecodeGuardTests(unittest.TestCase):
    def fixture(self, root, extra=None):
        source = {'module.py': b'def first():\n    return second()\ndef second():\n    return 2\n'}
        source.update(extra or {})
        snapshot = root / 'snapshot';snapshot.mkdir()
        for name, raw in source.items(): (snapshot / name).write_bytes(raw)
        index = {name: {'raw_sha256': hashlib.sha256(raw).hexdigest()} for name, raw in source.items()}
        (root / 'index.json').write_text(json.dumps(index))
        return {'snapshot': str(snapshot), 'code_index': str(root / 'index.json'), 'base_commit': '1' * 40}, source

    def test_valid_source_graph_equals_frozen_algorithm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);job, _ = self.fixture(root)
            runtime_renderer.build(job, root / 'frozen.json')
            guard.build(job, root / 'guarded.json')
            original = json.loads((root / 'frozen.json').read_text())
            guarded = json.loads((root / 'guarded.json').read_text());metadata = guarded.pop('preparation_adapter')
            self.assertEqual(guarded, original)
            self.assertEqual(metadata['decode_error_files'], 0)

    def test_unknown_and_invalid_encoding_retains_bytes_and_records_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);job, raw = self.fixture(root, {
                'bad_cookie.py': b'# coding: zlatin-1\nprint(1)\n',
                'bad_bytes.py': b'# coding: ascii\n# \xff\n'})
            with self.assertRaises((SyntaxError, UnicodeError)):runtime_renderer.build(job, root / 'old.json')
            guard.build(job, root / 'new.json');cache = json.loads((root / 'new.json').read_text())
            self.assertEqual(cache['preparation_adapter']['decode_error_files'], 2)
            self.assertEqual({e['path'] for e in cache['parse_errors']}, {'bad_cookie.py', 'bad_bytes.py'})
            self.assertEqual(len(cache['functions']), 2)
            for name, wanted in raw.items(): self.assertEqual((root / 'snapshot' / name).read_bytes(), wanted)

    def test_scope_restores_frozen_producer_even_on_exception(self):
        original = runtime_renderer.build
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            with guard.enabled():
                self.assertIs(runtime_renderer.build, guard.build)
                raise RuntimeError('fixture')
        self.assertIs(runtime_renderer.build, original)


if __name__ == '__main__': unittest.main()
