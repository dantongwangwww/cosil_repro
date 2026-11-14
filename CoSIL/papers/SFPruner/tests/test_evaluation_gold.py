"""Synthetic repository fixtures only; no benchmark or sealed test content."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from specprune import gold

class GoldMappingTests(unittest.TestCase):
    def test_hunk_exact_unique_offset_and_no_fuzz(self):
        patch='diff --git a/p.py b/p.py\n--- a/p.py\n+++ b/p.py\n@@ -99,2 +99,2 @@\n def f():\n-    return 1\n+    return 2\n'
        hunks=gold.parse_patch(patch)[0]['hunks']
        placements=[]
        fixed,_,_=gold.apply_file('# prefixed\ndef f():\n    return 1\n',hunks,placements)
        self.assertIn('return 2',fixed)
        self.assertFalse(placements[0]['fuzz'])
        with self.assertRaises(ValueError):
            gold.apply_file('def f():\n    return 1\ndef f():\n    return 1\n',hunks)
        with self.assertRaises(ValueError):
            gold.apply_file('def f():\n  return 1\n',hunks)

    def test_unsafe_source_path_rejected(self):
        for name in ('../x.py','/etc/x.py','x\\y.py'):
            with self.assertRaises(ValueError):
                gold.safe_path(name)

    @unittest.skipUnless(shutil.which('python3.12'), 'R2 requires Python 3.12')
    def test_existing_function_and_new_function_are_separate(self):
        source='def old():\n    return 1\n'
        patch='diff --git a/p.py b/p.py\n--- a/p.py\n+++ b/p.py\n@@ -1,2 +1,5 @@\n def old():\n-    return 1\n+    return 2\n+\n+def added():\n+    return 3\n'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); snap=root/'base'; snap.mkdir(); (snap/'p.py').write_text(source)
            patchfile=root/'fix.diff'; patchfile.write_text(patch)
            previous=gold.OUTPUT_ROOT
            try:
                gold.OUTPUT_ROOT=root/'output'; gold.PARSE_CACHE.clear(); gold.PARSER=None
                manifest=gold.prepare_snapshot_manifest(snap,patchfile,'example-1','org/repo','synthetic-base')
                summary=gold.run_manifest(manifest,'unit')
                result=json.loads((root/'output/unit/example-1/gold_v2.json').read_text())
                self.assertEqual(result['existing_function_targets'],['p.py::old'])
                self.assertEqual(result['status'],'COMPLETE_NONEMPTY')
                self.assertNotIn('p.py::added',result['existing_function_targets'])
                self.assertEqual((snap/'p.py').read_text(),source)
                self.assertEqual(result['parser']['version_info'][:2],[3,12])
                self.assertFalse(result['model_or_API_called'])
            finally:
                gold.OUTPUT_ROOT=previous

if __name__=='__main__':
    unittest.main()
