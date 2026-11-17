import difflib
import unittest

from code_multiswe_java_20261117.java_index import parse_java
from code_multiswe_java_20261117.gold import build_gold, parse_patch, is_test_path, score_predictions


def case(before, after, path='src/A.java'):
    patch = 'diff --git a/{0} b/{0}\n'.format(path) + ''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), fromfile='a/'+path, tofile='b/'+path))
    return ({path: parse_java(path, before.encode())}, {path: parse_java(path, after.encode())}, patch)


class GoldTests(unittest.TestCase):
    def test_pure_addition_inside_existing_method_uses_new_ast(self):
        before = 'class A {\n int f(){\n  return 1;\n }\n}\n'
        after = before.replace('  return 1;', '  int x = 0;\n  return 1;')
        gold = build_gold(*case(before, after))
        self.assertEqual(gold['function_targets'], ['src/A.java::A.f()'])
        self.assertTrue(gold['function_evaluable'])
        self.assertEqual(parse_patch(case(before, after)[2])[0]['changed_old_lines'], [])

    def test_actual_changed_lines_not_hunk_heading(self):
        before = 'class A {\n int f(){return 1;}\n int g(){return 2;}\n}\n'
        after = before.replace('return 2', 'return 3')
        args = list(case(before, after))
        args[2] = args[2].replace('@@ -1,4 +1,4 @@', '@@ -1,4 +1,4 @@ A.f')
        gold = build_gold(*args)
        self.assertEqual(gold['function_targets'], ['src/A.java::A.g()'])

    def test_mixed_fields_and_existing_method_remain_evaluable(self):
        before = 'class A {\n int n = 0;\n int f(){return 1;}\n}\n'
        after = before.replace('n = 0', 'n = 2').replace('return 1', 'return 3')
        gold = build_gold(*case(before, after))
        self.assertTrue(gold['function_evaluable'])
        self.assertEqual(gold['patch_scope'], 'mixed_method_and_other_changes')

    def test_new_method_is_not_an_existing_target(self):
        before = 'class A {\n int f(){return 1;}\n}\n'
        after = before.replace('\n}', '\n int added(){return 2;}\n}')
        gold = build_gold(*case(before, after))
        self.assertFalse(gold['function_evaluable'])
        self.assertEqual(gold['function_targets'], [])
        self.assertTrue(gold['file_evaluable'])

    def test_constructor_and_overload_identity(self):
        before = 'class A {\n A(int a){}\n int f(int x){return x;}\n int f(String x){return 0;}\n}\n'
        after = before.replace('A(int a){}', 'A(int a){ f(a); }').replace('return x', 'return x+1')
        gold = build_gold(*case(before, after))
        self.assertEqual(gold['function_targets'], ['src/A.java::A.<init>(int)', 'src/A.java::A.f(int)'])

    def test_parser_failure_is_partial_not_a_miss(self):
        before = 'class A {\n int f(){return 1;}\n}\n'
        after = before.replace('return 1', 'return 2').replace('\n}', '\nBROKEN(')
        gold = build_gold(*case(before, after))
        self.assertFalse(gold['function_evaluable'])
        self.assertEqual(gold['function_status'], 'partial')
        self.assertTrue(gold['limitations'])
        self.assertIsNone(score_predictions({'functions': []}, gold)['function_hit@5'])

    def test_test_rule_and_new_file(self):
        self.assertTrue(is_test_path('src/test/java/A.java'))
        self.assertTrue(is_test_path('src/AStaticTest.java'))
        self.assertFalse(is_test_path('src/main/java/Testability.java'))
        patch = 'diff --git a/src/New.java b/src/New.java\nnew file mode 100644\n--- /dev/null\n+++ b/src/New.java\n@@ -0,0 +1,3 @@\n+class New {\n+ void f() {}\n+}\n'
        after = {'src/New.java': parse_java('src/New.java', b'class New {\n void f() {}\n}\n')}
        gold = build_gold({}, after, patch)
        self.assertFalse(gold['file_evaluable'])
        self.assertFalse(gold['function_evaluable'])
        self.assertEqual(gold['new_java_file_targets'], ['src/New.java'])

    def test_signature_edit_keeps_old_identity(self):
        before = 'class A {\n int f(int x){\n  return x;\n }\n}\n'
        after = before.replace('f(int x)', 'f(int x, int y)')
        gold = build_gold(*case(before, after))
        self.assertEqual(gold['function_targets'], ['src/A.java::A.f(int)'])

    def test_test_patch_content_is_not_an_argument(self):
        with self.assertRaises(TypeError):
            build_gold({}, {}, '', test_patch='must not be used')


if __name__ == '__main__':
    unittest.main()
