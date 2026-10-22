"""Synthetic CPU tests; no real gold, benchmark datasets, APIs or repo tests."""
import difflib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dsimple_v2 import gold


def diff(old, new, path='a.py'):
    # difflib emits missing-EOL content without the Git marker; these general
    # fixtures use LF. Dedicated tests exercise the marker explicitly.
    return f'diff --git a/{path} b/{path}\n' + ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), 'a/' + path, 'b/' + path))


def map_text(old, new, path='a.py'):
    item = gold.parse_patch(diff(old, new, path))[0]
    parsed = gold.parse_many([old, new])
    return gold.map_file(path, path, old, item, parsed[gold.digest(old)], parsed[gold.digest(new)])


class MappingTests(unittest.TestCase):
    def test_body_edit_and_import_are_complete_scopes(self):
        result = map_text('def f():\n    return 1\n', 'import os\n\ndef f():\n    return 2\n')
        self.assertEqual(result['targets'], ['a.py::f'])
        self.assertFalse(result['errors'])
        self.assertIn('module_level', {v['reason'] for v in result['scope_exempt_changes']})

    def test_inserted_tail_statement_does_not_claim_next_module_statement(self):
        result = map_text('def f():\n    x = 1\n', 'def f():\n    x = 1\n    x += 2\n\nVALUE = 4\n')
        self.assertEqual(result['targets'], ['a.py::f'])
        self.assertEqual(sum(v['change'] == '+' for v in result['changed_line_evidence']), 1)
        self.assertIn('module_level', {v['reason'] for v in result['scope_exempt_changes']})

    def test_only_new_nested_helper_is_not_promoted_to_outer(self):
        result = map_text('def f():\n    return 1\n', 'def f():\n    def helper():\n        return 2\n    return 1\n')
        self.assertEqual(result['targets'], [])
        self.assertTrue(any(v.get('owner', {}).get('qualified_name') == 'f.helper' for v in result['scope_exempt_changes']))

    def test_new_nested_and_changed_outer_call_have_outer_target(self):
        result = map_text('def f():\n    return 1\n', 'def f():\n    def helper():\n        return 2\n    return helper()\n')
        self.assertEqual(result['targets'], ['a.py::f'])

    def test_function_rename_uses_base_identity(self):
        result = map_text('def old():\n    return 1\n', 'def renamed():\n    return 1\n')
        self.assertEqual(result['targets'], ['a.py::old'])
        self.assertNotIn('a.py::renamed', result['targets'])

    def test_class_rename_and_insert_uses_old_method_qn(self):
        result = map_text('class Old:\n    def f(self):\n        return 1\n', 'class New:\n    def f(self):\n        value = 2\n        return 1\n')
        self.assertEqual(result['targets'], ['a.py::Old.f'])
        self.assertTrue(any(v.get('mapping_proof') == 'unchanged_def_line' for v in result['changed_line_evidence']))

    def test_decorator_addition_and_async(self):
        result = map_text('async def f():\n    return 1\n', '@decorate\nasync def f():\n    return 1\n')
        self.assertEqual(result['targets'], ['a.py::f'])
        self.assertEqual(result['changed_line_evidence'][0]['mapping_proof'], 'unchanged_def_line')

    def test_shared_property_span_identity_and_new_setter(self):
        old = 'class C:\n    @property\n    def x(self):\n        return 1\n'
        new = old + '\n    @x.setter\n    def x(self, value):\n        self._x = value\n'
        result = map_text(old, new)
        self.assertEqual(result['targets'], ['a.py::C.x'])
        setter = [v for v in result['changed_line_evidence'] if v['mapping_proof'] == 'new_definition_existing_identity']
        self.assertTrue(setter)
        self.assertTrue(all(v['matched_base_span'] is None for v in setter))
        changed = map_text(new, new.replace('self._x = value', 'self._x = int(value)'))
        self.assertEqual(changed['targets'], ['a.py::C.x'])

    def test_file_delete_and_rename_operations(self):
        old = 'def f():\n    return 1\n'
        text = 'diff --git a/a.py b/a.py\ndeleted file mode 100644\n--- a/a.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-def f():\n-    return 1\n'
        item = gold.parse_patch(text)[0]; parsed = gold.parse_many([old, ''])
        result = gold.map_file('a.py', '/dev/null', old, item, parsed[gold.digest(old)], parsed[gold.digest('')])
        self.assertEqual(result['targets'], ['a.py::f'])
        rename = gold.parse_patch('diff --git a/a.py b/b.py\nsimilarity index 100%\nrename from a.py\nrename to b.py\n')[0]
        self.assertEqual((rename['old'], rename['new'], rename['hunks']), ('a.py', 'b.py', []))
        moved = diff(old, old.replace('1', '2')).replace('b/a.py', 'b/b.py')
        item = gold.parse_patch(moved)[0]
        p = gold.parse_many([old, old.replace('1', '2')])
        self.assertEqual(gold.map_file('a.py', 'b.py', old, item, p[gold.digest(old)], p[gold.digest(old.replace('1', '2'))])['targets'], ['a.py::f'])

    def test_no_final_newline_and_insert_zero_count(self):
        patch_text = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x=1\n\\ No newline at end of file\n+x=2\n\\ No newline at end of file\n'
        fixed, mapping, changes = gold.apply_file('x=1', gold.parse_patch(patch_text)[0]['hunks'])
        self.assertEqual(fixed, 'x=2'); self.assertEqual(mapping, {}); self.assertEqual(len(changes), 2)
        insertion = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,0 +2 @@\n+y=2\n'
        self.assertEqual(gold.apply_file('x=1\n', gold.parse_patch(insertion)[0]['hunks'])[0], 'x=1\ny=2\n')

    def test_bad_patch_and_unsafe_path_fail_explicitly(self):
        with self.assertRaises(ValueError):
            gold.parse_patch('diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1 @@\n-old\n+new\n')
        with self.assertRaises(ValueError):
            gold.apply_file('wrong\n', gold.parse_patch(diff('old\n', 'new\n'))[0]['hunks'])
        with self.assertRaises(ValueError):
            gold.safe_path('../secret.py')
        self.assertEqual(gold.patch_path('"a/a b.py"', 'a/'), 'a b.py')

    def test_python312_fstring_is_not_silently_empty(self):
        text = 'def f(flag):\n    return f"{"yes" if flag else "no"}"\n'
        result = gold.parse_many([text])[gold.digest(text)]
        self.assertIsNone(result['parse_error'])
        self.assertEqual(result['definitions'][0]['qualified_name'], 'f')
        invalid = gold.parse_many(['def broken(:\n'])[gold.digest('def broken(:\n')]
        self.assertEqual(invalid['parse_error']['type'], 'SyntaxError')


class ExactOffsetTests(unittest.TestCase):
    def item(self, hunks):
        return gold.parse_patch('diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n' + hunks)[0]

    def test_unique_complete_context_relocates_and_records_actual_lines(self):
        item = self.item('@@ -1,2 +1,2 @@\n anchor\n-old\n+new\n')
        placements = []
        fixed, mapping, changes = gold.apply_file('extra\nanchor\nold\n', item['hunks'], placements)
        self.assertEqual(fixed, 'extra\nanchor\nnew\n')
        self.assertEqual(mapping, {1: 1, 2: 2})
        self.assertEqual([(c['old_line'], c['new_line']) for c in changes], [(3, None), (None, 3)])
        self.assertEqual(placements[0]['offset_lines'], 1)
        self.assertEqual(placements[0]['proof'], 'unique_complete_old_hunk_exact')
        self.assertFalse(placements[0]['fuzz'])

    def test_ambiguous_full_context_does_not_choose_nearest_match(self):
        item = self.item('@@ -3,2 +3,2 @@\n anchor\n-old\n+new\n')
        with self.assertRaisesRegex(ValueError, 'ambiguous_hunk_offset'):
            gold.apply_file('anchor\nold\nx\nanchor\nold\n', item['hunks'])

    def test_repeated_anchor_is_ok_when_entire_old_block_is_unique(self):
        item = self.item('@@ -2,2 +2,2 @@\n anchor\n-old\n+new\n')
        placements = []
        fixed, _, _ = gold.apply_file('anchor\nwrong\nx\nanchor\nold\n', item['hunks'], placements)
        self.assertEqual(fixed, 'anchor\nwrong\nx\nanchor\nnew\n')
        self.assertEqual(placements[0]['offset_lines'], 2)

    def test_multiple_hunks_have_independent_offsets_and_net_additions(self):
        item = self.item('@@ -1,2 +1,3 @@\n one\n-old1\n+new1\n+added\n@@ -4,2 +5,2 @@\n two\n-old2\n+new2\n')
        placements = []
        fixed, mapping, changes = gold.apply_file('extra\none\nold1\nbetween\nextra2\ntwo\nold2\n', item['hunks'], placements)
        self.assertEqual(fixed, 'extra\none\nnew1\nadded\nbetween\nextra2\ntwo\nnew2\n')
        self.assertEqual([p['offset_lines'] for p in placements], [1, 2])
        self.assertEqual([p['actual_new_start'] for p in placements], [2, 7])
        self.assertEqual([c['old_line'] for c in changes if c['change'] == '-'], [3, 7])
        self.assertEqual(mapping[7], 6)

    def test_offset_zero_keeps_declared_anchor_even_if_full_block_repeats(self):
        item = self.item('@@ -1,2 +1,2 @@\n anchor\n-old\n+new\n')
        placements = []
        fixed, mapping, changes = gold.apply_file('anchor\nold\nx\nanchor\nold\n', item['hunks'], placements)
        self.assertEqual(fixed, 'anchor\nnew\nx\nanchor\nold\n')
        self.assertEqual(placements[0]['offset_lines'], 0)
        self.assertEqual(placements[0]['proof'], 'declared_position_exact')
        self.assertEqual(mapping, {1: 1, 3: 3, 4: 4, 5: 5})

    def test_missing_context_or_whitespace_changes_are_not_fuzzed(self):
        item = self.item('@@ -1,2 +1,2 @@\n anchor\n-old\n+new\n')
        for base in ('wrong\nold\n', ' anchor\nold\n', 'anchor \nold\n'):
            with self.subTest(base=base), self.assertRaisesRegex(ValueError, 'patch_base_line_mismatch'):
                gold.apply_file(base, item['hunks'])

    def test_actual_function_owner_uses_relocated_base_coordinates(self):
        old = '# unrelated\n\ndef target():\n    return 1\n'
        item = self.item('@@ -1,2 +1,2 @@\n def target():\n-    return 1\n+    return 2\n')
        fixed = gold.apply_file(old, item['hunks'])[0]
        parsed = gold.parse_many([old, fixed])
        mapped = gold.map_file('a.py', 'a.py', old, item, parsed[gold.digest(old)], parsed[gold.digest(fixed)])
        self.assertEqual(mapped['targets'], ['a.py::target'])
        deleted = next(e for e in mapped['changed_line_evidence'] if e['change'] == '-')
        self.assertEqual(deleted['old_line'], 4)
        self.assertEqual(mapped['hunk_placements'][0]['actual_old_start'], 3)


class CaseTests(unittest.TestCase):
    def fixture(self, base, files, patch_text, *, bad_sha=False):
        snapshot = base / 'snapshot'; snapshot.mkdir()
        index = {}
        for name, text in files.items():
            path = snapshot / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
            index[name] = {'sha256': 'wrong' if bad_sha else gold.digest(text), 'definitions': []}
        indexpath = base / 'index.json'; indexpath.write_text(json.dumps(index))
        job = {'instance_id': 'example__repo-1', 'repo': 'example/repo', 'base_commit': 'a'*40,
               'paths': list(files), 'snapshot': str(snapshot), 'code_index': str(indexpath)}
        jp = base / 'job.json'; jp.write_text(json.dumps(job))
        rp = base / 'row.json'; rp.write_text(json.dumps({**{k:job[k] for k in ('instance_id','repo','base_commit')},'patch':patch_text}))
        return jp, rp

    def evaluate(self, base, files, patch_text, **kwargs):
        jp, rp = self.fixture(base, files, patch_text, **kwargs)
        with patch.object(gold, 'ROOT', base):
            return gold.evaluate_case(jp, rp, base / 'evaluator_private/eval_v2/unit/one')

    def test_real_interface_full_index_and_no_old_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); old='def f():\n    return 1\n'; other='def valid_prediction():\n    return 3\n'
            result=self.evaluate(base, {'a.py':old,'other.py':other}, diff(old,old.replace('1','2')))
            self.assertEqual(result['status'],'COMPLETE_NONEMPTY')
            self.assertEqual(result['existing_function_targets'],['a.py::f'])
            index=json.loads(Path(result['code_index_v2_path']).read_text())
            self.assertEqual(index['other.py']['definitions'][0]['qualified_name'],'valid_prediction')
            self.assertEqual((base/'snapshot/a.py').read_text(),old)

    def test_module_only_and_new_file_are_complete_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); old='VALUE = 1\n'; newfile='diff --git a/new.py b/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+def added():\n+    pass\n'
            result=self.evaluate(base,{'a.py':old},diff(old,'VALUE = 2\n')+newfile)
            self.assertEqual(result['status'],'COMPLETE_EMPTY')
            self.assertIn('new_file_no_base_functions',{e['reason']for e in result['scope_exempt_changes']})

    def test_integrity_ast_apply_failures_are_incomplete(self):
        for mode in ('sha','syntax','apply'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                base=Path(directory); old='def f():\n    return 1\n'
                change=diff(old,'def f(:\n' if mode=='syntax' else old.replace('1','2'))
                if mode=='apply':change=change.replace('-    return 1','-    return 9')
                result=self.evaluate(base,{'a.py':old},change,bad_sha=mode=='sha')
                self.assertEqual(result['status'],'INCOMPLETE')
                self.assertTrue(result['errors'])

    def test_pure_rename_has_no_function_target(self):
        with tempfile.TemporaryDirectory() as directory:
            result=self.evaluate(Path(directory),{'a.py':'def f():\n    pass\n'},'diff --git a/a.py b/b.py\nsimilarity index 100%\nrename from a.py\nrename to b.py\n')
            self.assertEqual(result['status'],'COMPLETE_EMPTY')

    def test_output_confinement(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(gold,'ROOT',Path(directory)):
                with self.assertRaises(PermissionError):
                    gold.write_json(Path(directory)/'outside.json',{})


if __name__=='__main__':unittest.main()
