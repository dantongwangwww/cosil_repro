"""Exact parser/application tests use disposable synthetic repositories only."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from code_repair50.editing import (
    EditProtocolError, apply_edits, parse_edits, plan_edits,
    protected_path, validate_relative_path,
)


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="repair50_synthetic_")
        self.root = Path(self.temp.name)
        self.base = self.root / "base"
        self.base.mkdir()
        (self.base / "pkg").mkdir()
        (self.base / "pkg/mod.py").write_bytes(b"def calculate():\n    return 1\n")
        self.out = self.root / "artifacts"

    def tearDown(self):
        self.temp.cleanup()

    def edit(self, **updates):
        value = {"path": "pkg/mod.py", "search": "return 1", "replace": "return 2"}
        value.update(updates)
        return value

    def test_strict_json_and_empty_edits(self):
        self.assertEqual(parse_edits('{"edits":[]}'), [])
        self.assertEqual(parse_edits(json.dumps({"edits": [self.edit()]})), [self.edit()])

    def test_duplicate_keys_rejected_at_all_levels(self):
        examples = ['{"edits":[],"edits":[]}',
                    '{"edits":[{"path":"a.py","path":"b.py","search":"x","replace":"y"}]}']
        for value in examples:
            with self.subTest(value=value), self.assertRaises(EditProtocolError):
                parse_edits(value)

    def test_no_fences_extra_fields_or_parser_repair(self):
        examples = ['```json\n{"edits":[]}\n```', '{"edits":[],"reason":"x"}',
                    '{"edits":[{"path":"a.py","search":"x","replace":"y","line":1}]}',
                    '{"edits":null}', '{"edits":[]}{"edits":[]}', '{"edits":[NaN]}',
                    '{"edits":[],}', '[]']
        for value in examples:
            with self.subTest(value=value), self.assertRaises(EditProtocolError):
                parse_edits(value)

    def test_paths_are_never_normalized_or_unmasked(self):
        for value in ("pkg/pkg.py", "a file.py", "中文.py", "[BENCHMARK_METADATA].py"):
            self.assertEqual(validate_relative_path(value), value)
        for value in ("", "/x.py", "../x.py", "pkg/../x.py", "./x.py", "pkg//x.py",
                      "pkg/./x.py", ".git/config", "pkg/.GIT/config", "C:/x.py", "C:x.py",
                      "pkg\\x.py", "x.py\x00", "x.py\n"):
            with self.subTest(path=value), self.assertRaises(EditProtocolError):
                validate_relative_path(value)

    def test_general_test_protection(self):
        for path in ("tests/a.py", "pkg/tests/a.py", "test/a.py", "pkg/test_mod.py",
                     "pkg/mod_test.py", "conftest.py", "pytest.ini", "tox.ini", ".coveragerc",
                     ".github/workflows/a.yml", "pkg/fixtures/item.py", "a.test.ts"):
            with self.subTest(path=path):
                self.assertTrue(protected_path(path))
                with self.assertRaises(EditProtocolError):
                    parse_edits(json.dumps({"edits": [self.edit(path=path)]}))
        self.assertFalse(protected_path("pkg/testable.py"))
        self.assertFalse(protected_path("pyproject.toml"))
        self.assertFalse(protected_path("setup.cfg"))

    def test_mixed_toml_business_changes_are_allowed(self):
        before = '[project]\nname = "example"\nversion = "1.0"\n[tool.pytest.ini_options]\naddopts = "-ra"\n'
        (self.base / "pyproject.toml").write_text(before)
        plan = plan_edits(self.base, [self.edit(path="pyproject.toml", search='version = "1.0"', replace='version = "1.1"')])
        self.assertIn('version = "1.1"', plan["contents"]["pyproject.toml"])

    def test_mixed_ini_business_changes_are_allowed(self):
        before = '[metadata]\nname = example\nversion = 1.0\n[tool:pytest]\naddopts = -ra\n'
        (self.base / "setup.cfg").write_text(before)
        plan = plan_edits(self.base, [self.edit(path="setup.cfg", search="version = 1.0", replace="version = 1.1")])
        self.assertIn("version = 1.1", plan["contents"]["setup.cfg"])

    def test_toml_framework_semantics_cannot_be_changed_removed_or_added(self):
        examples = [
            ('[tool.pytest.ini_options]\naddopts = "-ra"\n', '[tool.pytest.ini_options]\naddopts = "--ignore=tests"\n'),
            ('[tool.unittest]\nstart = "tests"\n', '[tool.unittest]\nstart = "empty"\n'),
            ('[tool.tox]\nlegacy_tox_ini = "checked"\n', ''),
            ('[tool.coverage.run]\nbranch = true\n', '[tool.coverage.run]\nbranch = 1\n'),
            ('[tool.hypothesis]\nmax_examples = 100\n', '[tool.hypothesis]\nmax_examples = 1\n'),
            ('[tool.poetry.group.test.dependencies]\npytest = "8"\n', ''),
            ('[project.optional-dependencies]\ntest = ["pytest"]\n', '[project.optional-dependencies]\ntest = []\n'),
            ('[project]\nname = "example"\n', '[project]\nname = "example"\n[tool.pytest.ini_options]\naddopts = "-k nothing"\n'),
        ]
        for before, after in examples:
            with self.subTest(before=before):
                (self.base / "pyproject.toml").write_text(before)
                with self.assertRaises(EditProtocolError):
                    plan_edits(self.base, [self.edit(path="pyproject.toml", search=before, replace=after)])

    def test_ini_testing_sections_and_defaults_remain_effectively_unchanged(self):
        examples = [
            ('[tool:pytest]\naddopts = -ra\n', '[tool:pytest]\naddopts = --ignore=tests\n'),
            ('[testenv:unit]\ncommands = pytest\n', '[testenv:unit]\ncommands = echo pass\n'),
            ('[coverage:run]\nbranch = True\n', ''),
            ('[options.extras_require]\ntest = pytest\n', '[options.extras_require]\ntest =\n'),
            ('[DEFAULT]\nflags = -ra\n[tool:pytest]\naddopts = %(flags)s\n',
             '[DEFAULT]\nflags = --ignore=tests\n[tool:pytest]\naddopts = %(flags)s\n'),
        ]
        for before, after in examples:
            with self.subTest(before=before):
                (self.base / "setup.cfg").write_text(before)
                with self.assertRaises(EditProtocolError):
                    plan_edits(self.base, [self.edit(path="setup.cfg", search=before, replace=after)])

    def test_configuration_comments_and_spacing_can_change_without_semantic_change(self):
        examples = [
            ("pyproject.toml", '[tool.pytest.ini_options]\naddopts = "-ra"\n', '# comment\n[tool.pytest.ini_options]\naddopts="-ra"\n'),
            ("setup.cfg", '[tool:pytest]\naddopts = -ra\n', '# comment\n[tool:pytest]\naddopts=-ra\n'),
        ]
        for path, before, after in examples:
            with self.subTest(path=path):
                (self.base / path).write_text(before)
                plan = plan_edits(self.base, [self.edit(path=path, search=before, replace=after)])
                self.assertEqual(plan["contents"][path], after)

    def test_invalid_configuration_has_no_unchecked_fallback(self):
        cases = [("pyproject.toml", '[project]\nname = "ok"\n', '[project\n'),
                 ("setup.cfg", '[metadata]\nname = ok\n', '[broken\n'),
                 ("setup.cfg", '[tool:pytest]\naddopts = %(missing)s\n', '[tool:pytest]\naddopts = -ra\n')]
        for path, before, after in cases:
            with self.subTest(path=path):
                (self.base / path).write_text(before)
                with self.assertRaises(EditProtocolError):
                    plan_edits(self.base, [self.edit(path=path, search=before, replace=after)])

    def test_transaction_exports_valid_diff_without_changing_base(self):
        original = (self.base / "pkg/mod.py").read_bytes()
        receipt = apply_edits(self.base, [self.edit()], self.out)
        self.assertEqual((self.base / "pkg/mod.py").read_bytes(), original)
        self.assertEqual((self.out / "files/pkg/mod.py").read_bytes(), original.replace(b"return 1", b"return 2"))
        self.assertFalse(receipt["empty_modification"])
        self.assertIn("-    return 1\n+    return 2", (self.out / "patch.diff").read_text())
        self.assertEqual(json.loads((self.out / "manifest.json").read_text())["edit_count"], 1)

    def test_late_invalid_edit_leaves_no_artifact_or_base_change(self):
        original = (self.base / "pkg/mod.py").read_bytes()
        edits = [self.edit(), self.edit(search="does not exist", replace="x")]
        with self.assertRaises(EditProtocolError):
            apply_edits(self.base, edits, self.out)
        self.assertFalse(self.out.exists())
        self.assertEqual((self.base / "pkg/mod.py").read_bytes(), original)
        self.assertEqual(list(self.root.glob(".artifacts.pending-*")), [])

    def test_ordered_edits_match_updated_contents(self):
        plan = plan_edits(self.base, [self.edit(), self.edit(search="return 2", replace="return 3")])
        self.assertIn("return 3", plan["contents"]["pkg/mod.py"])
        self.assertEqual(plan["edit_count"], 2)

    def test_no_empty_or_ambiguous_search(self):
        (self.base / "pkg/mod.py").write_text("aaa\nreturn 1\nreturn 1\n")
        for search in ("", "return 1", "aa", "return 9"):
            with self.subTest(search=search), self.assertRaises(EditProtocolError):
                apply_edits(self.base, [self.edit(search=search)], self.out)

    def test_no_whitespace_or_line_number_repair(self):
        for search in ("return  1", "2:     return 1", "RETURN 1"):
            with self.subTest(search=search), self.assertRaises(EditProtocolError):
                plan_edits(self.base, [self.edit(search=search)])

    def test_symlink_targets_and_parent_directories_forbidden(self):
        outside = self.root / "outside.py"
        outside.write_text("return 1\n")
        (self.base / "link.py").symlink_to(outside)
        (self.base / "alias").symlink_to(self.base / "pkg", target_is_directory=True)
        for path in ("link.py", "alias/mod.py"):
            with self.subTest(path=path), self.assertRaises(EditProtocolError):
                plan_edits(self.base, [self.edit(path=path)])
        self.assertEqual(outside.read_text(), "return 1\n")

    def test_missing_file_binary_and_non_utf8_rejected(self):
        for name, raw in (("binary.py", b"x\x00y"), ("latin.py", b"\xff")):
            (self.base / name).write_bytes(raw)
        for path in ("missing.py", "binary.py", "latin.py"):
            with self.subTest(path=path), self.assertRaises(EditProtocolError):
                plan_edits(self.base, [self.edit(path=path)])

    def test_empty_and_no_op_edits_are_legal_no_change(self):
        for edits in ([], [self.edit(replace="return 1")]):
            with self.subTest(edits=edits):
                plan = plan_edits(self.base, edits)
                self.assertTrue(plan["empty_modification"])
                self.assertEqual(plan["patch"], "")
                self.assertEqual(plan["changed_files"], [])

    def test_existing_output_or_nested_base_output_refused(self):
        self.out.mkdir()
        with self.assertRaises(EditProtocolError):
            apply_edits(self.base, [], self.out)
        with self.assertRaises(EditProtocolError):
            apply_edits(self.base, [], self.base / "new")
        self.assertFalse((self.base / "new").exists())

    @unittest.skipUnless(shutil.which("git"), "synthetic diff check requires git")
    def test_exported_diffs_apply_exactly_for_newline_space_unicode_cases(self):
        cases = [
            ("space file.py", "hello", "hello\n"),
            ("中文.py", "return 1\n", "return 2"),
            ("windows.py", "a\r\nreturn 1\r\n", "a\r\nreturn 2\r\n"),
            ("empty.py", "return 1\n", ""),
        ]
        for number, (path, before, after) in enumerate(cases):
            with self.subTest(path=path):
                source = self.base / path
                source.write_bytes(before.encode())
                out = self.root / ("case_" + str(number))
                apply_edits(self.base, [{"path": path, "search": before, "replace": after}], out)
                verify = self.root / ("verify_" + str(number))
                verify.mkdir()
                (verify / path).write_bytes(before.encode())
                command = subprocess.run(
                    ["git", "apply", "--check", str(out / "patch.diff")],
                    cwd=verify, capture_output=True, check=False,
                )
                self.assertEqual(command.returncode, 0, command.stderr.decode())
                applied = subprocess.run(
                    ["git", "apply", str(out / "patch.diff")], cwd=verify,
                    capture_output=True, check=False,
                )
                self.assertEqual(applied.returncode, 0, applied.stderr.decode())
                self.assertEqual((verify / path).read_bytes(), after.encode())


if __name__ == "__main__":
    unittest.main()
