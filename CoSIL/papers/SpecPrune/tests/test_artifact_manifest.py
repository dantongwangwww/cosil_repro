import hashlib
import tempfile
import unittest
from pathlib import Path
from specprune.verify import check_manifest

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
