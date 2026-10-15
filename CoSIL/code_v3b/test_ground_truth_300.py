import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from code_v3b.build_ground_truth_300 import apply_hunks, changed_targets, patch_sections


class GoldTests(unittest.TestCase):
    def test_function_body_change_is_located(self):
        targets, outside, _ = changed_targets('def foo():\n    return 2\n', {2})
        self.assertEqual([(t['kind'], t['name']) for t in targets], [('function', 'foo')])
        self.assertEqual(outside, [])

    def test_config_change_does_not_use_nearby_hunk_function(self):
        source = 'def gettext_noop(x):\n    return x\n\nFILE_UPLOAD_PERMISSION = 0o644\n'
        targets, outside, _ = changed_targets(source, {4})
        self.assertEqual(targets, [])
        self.assertEqual(outside, [4])

    def test_new_method_uses_after_ast_not_previous_hunk_method(self):
        source = 'class C:\n    def previous(self):\n        return 1\n\n    def new_method(self):\n        return 2\n'
        targets, _, _ = changed_targets(source, {4, 5, 6})
        self.assertEqual([t['name'] for t in targets], ['C.new_method'])

    def test_nested_function_uses_innermost_boundary(self):
        targets, _, _ = changed_targets('def outer():\n    def inner():\n        return 1\n    return inner()\n', {3})
        self.assertEqual(targets[0]['name'], 'outer.inner')

    def test_offset_hunk_requires_unique_context(self):
        source = '# extra\n\ndef foo():\n    return 1\n'
        hunk = {'old_start': 1, 'old_count': 2, 'new_start': 1, 'new_count': 2,
                'lines': [' def foo():', '-    return 1', '+    return 2']}
        after, old, new = apply_hunks(source, [hunk])
        self.assertIn('return 2', after)
        self.assertEqual(old, {4})
        self.assertEqual(new, {4})
        self.assertEqual(hunk['actual_old_start'], 3)

    def test_two_files_remain_separate(self):
        patch = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x=1\n+x=2\ndiff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n-y=1\n+y=2\n'
        self.assertEqual([s['new_path'] for s in patch_sections(patch)], ['a.py', 'b.py'])


if __name__ == '__main__':
    unittest.main()
