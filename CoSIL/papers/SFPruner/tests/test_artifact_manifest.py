import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from specprune.verify import check_manifest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/freeze_artifact.py'
module_spec = importlib.util.spec_from_file_location('artifact_freeze', SCRIPT)
freeze = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(freeze)

class ManifestTests(unittest.TestCase):
    def test_missing_asset_policy_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'a.py').write_bytes(b'a')
            m = {'files': [dict(path='a.py', bytes=1, sha256=hashlib.sha256(b'a').hexdigest()),
                           dict(path='assets/x', bytes=1, sha256='x', distribution='local_assets')]}
            self.assertTrue(check_manifest(root, m)['ok'])
            self.assertFalse(check_manifest(root, m, True)['ok'])
            (root/'a.py').write_bytes(b'b')
            self.assertFalse(check_manifest(root, m)['ok'])

    def test_manifest_cannot_escape_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            m = {'files': [dict(path='../outside', bytes=1, sha256='x')]}
            self.assertFalse(check_manifest(Path(directory), m)['ok'])

    def test_packaging_preserves_task_source_named_models_or_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keep = ['assets/runtime/issue/snapshot/pkg/models/a.py',
                    'assets/runtime/issue/snapshot/build/b.py',
                    'assets/runtime/issue/snapshot/dist/c.py']
            drop = ['models/weight.bin', 'build/temp.py', '__pycache__/temp.pyc']
            for rel in keep + drop:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('content')
            with patch.object(freeze, 'ROOT', root):
                actual = {p.relative_to(root).as_posix() for p in freeze.distributable_files()}
            self.assertEqual(actual, set(keep))
