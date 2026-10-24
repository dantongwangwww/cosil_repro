"""CPU-only tests; fixtures never inspect the experiment repository or issue."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from code_deepseek_direct.tools import RepoTools, TOOLS


class RepositoryToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="direct-tools-test-")
        self.addCleanup(self.temporary.cleanup)
        self.area = Path(self.temporary.name)
        self.repo = self.area / "repo"
        self.repo.mkdir()
        self.tools = RepoTools(self.repo)
        self.addCleanup(self.tools.close)

    def write(self, path, content):
        destination = self.repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content.encode() if isinstance(content, str) else content)
        return destination

    def call(self, name, **arguments):
        result = self.tools.execute(name, arguments)
        self.assertEqual(set(result), {"ok", "tool", "arguments", "data", "error"})
        self.assertEqual(result["tool"], name)
        self.assertEqual(result["arguments"], arguments)
        json.dumps(result)
        return result

    def successful(self, name, **arguments):
        result = self.call(name, **arguments)
        self.assertTrue(result["ok"], result)
        self.assertIsNone(result["error"])
        return result["data"]

    def failure(self, name, code, **arguments):
        result = self.call(name, **arguments)
        self.assertFalse(result["ok"], result)
        self.assertIsNone(result["data"])
        self.assertEqual(result["error"]["code"], code, result)
        return result["error"]

    def test_schemas_have_only_four_read_only_tools(self):
        self.assertEqual([item["function"]["name"] for item in TOOLS],
                         ["list_directory", "search_repository", "read_file", "list_symbols"])
        for item in TOOLS:
            self.assertEqual(item["type"], "function")
            self.assertFalse(item["function"]["parameters"]["additionalProperties"])
        json.dumps(TOOLS)

    def test_unknown_tool_and_non_object_arguments(self):
        self.failure("shell", "unknown_tool", command="cat secret")
        for arguments in (None, [], "path", 1):
            with self.subTest(arguments=arguments):
                result = self.tools.execute("read_file", arguments)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "invalid_arguments")
        self.assertEqual(self.tools.execute([], {})["error"]["code"], "unknown_tool")

    def test_schema_required_extra_and_inexact_types(self):
        cases = [
            ("read_file", {}), ("list_symbols", {}), ("search_repository", {}),
            ("read_file", {"path": "x", "unused": 1}),
            ("list_directory", {"recursive": 1}),
            ("search_repository", {"pattern": 1}),
            ("search_repository", {"pattern": "x", "regex": "false"}),
            ("search_repository", {"pattern": "x", "context_lines": True}),
            ("search_repository", {"pattern": "x", "context_lines": -1}),
            ("read_file", {"path": None}),
            ("read_file", {"path": "x", "start_line": True}),
            ("read_file", {"path": "x", "start_line": 0}),
            ("read_file", {"path": "x", "end_line": 0}),
            ("read_file", {"path": "x", "start_line": 3, "end_line": 2}),
        ]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments):
                self.failure(name, "invalid_arguments", **arguments)

    def test_absolute_parent_git_and_ambiguous_paths_are_rejected(self):
        (self.area / "apikey").write_text("OUTSIDE_SECRET")
        self.write(".git/config", "GIT_SECRET")
        for path in (str(self.area / "apikey"), "../apikey", "dir/../../apikey",
                     ".git", ".git/config", "dir/.git/config", "C:/apikey", "C:apikey"):
            with self.subTest(path=path):
                for name, args in (("read_file", {}), ("list_symbols", {}),
                                   ("list_directory", {}),
                                   ("search_repository", {"pattern": "SECRET"})):
                    self.failure(name, "forbidden_path", path=path, **args)
        for path in ("", "bad\x00path", "dir\\..\\apikey"):
            self.failure("read_file", "invalid_path", path=path)

    def test_symlink_file_and_directory_are_never_followed(self):
        self.write("real.txt", "inside")
        outside = self.area / "private"
        outside.mkdir()
        (outside / "secret.txt").write_text("OUTSIDE_SECRET")
        (self.repo / "link.txt").symlink_to(outside / "secret.txt")
        (self.repo / "internal-link").symlink_to(self.repo / "real.txt")
        (self.repo / "dir-link").symlink_to(outside, target_is_directory=True)
        for path in ("link.txt", "internal-link", "dir-link", "dir-link/secret.txt"):
            for name, args in (("read_file", {}), ("list_symbols", {}),
                               ("list_directory", {}),
                               ("search_repository", {"pattern": "SECRET"})):
                with self.subTest(path=path, name=name):
                    self.failure(name, "symlink_forbidden", path=path, **args)
        listing = self.successful("list_directory", recursive=True)
        self.assertEqual({item["path"] for item in listing["skipped"]},
                         {"link.txt", "internal-link", "dir-link"})
        search = self.successful("search_repository", pattern="OUTSIDE_SECRET")
        self.assertEqual(search["match_count"], 0)
        self.assertEqual(len(search["skipped"]), 3)

    def test_root_symlink_is_rejected(self):
        alias = self.area / "alias"
        alias.symlink_to(self.repo, target_is_directory=True)
        with self.assertRaises(ValueError):
            RepoTools(alias)

    def test_outside_secrets_history_evaluator_are_isolated(self):
        for name in ("apikey", "history.jsonl", "evaluator.py"):
            (self.area / name).write_text("NEVER_RETURN_THIS_SECRET")
        self.write("base.py", "def base():\n    pass\n")
        result = self.successful("search_repository", pattern="NEVER_RETURN_THIS_SECRET")
        self.assertEqual(result["searched_files"], 1)
        self.assertEqual(result["files"], [])
        for name in ("apikey", "history.jsonl", "evaluator.py"):
            self.failure("read_file", "forbidden_path", path="../" + name)
            self.failure("read_file", "not_found", path=name)

    def test_recursive_list_reports_every_entry_and_raw_hash(self):
        raw = b"first\r\nsecond\r\n"
        self.write("dir/a.txt", raw)
        self.write("z.txt", "last")
        self.write(".git/config", "private")
        immediate = self.successful("list_directory")
        self.assertEqual([entry["path"] for entry in immediate["entries"]], ["dir", "z.txt"])
        recursive = self.successful("list_directory", recursive=True)
        self.assertEqual([entry["path"] for entry in recursive["entries"]],
                         ["dir", "dir/a.txt", "z.txt"])
        entry = recursive["entries"][1]
        self.assertEqual(entry["size_bytes"], len(raw))
        self.assertEqual(entry["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(recursive["skipped"], [{"path": ".git", "code": "forbidden_path"}])

    def test_read_exact_inclusive_lines_and_complete_raw_metadata(self):
        raw = "α\r\nbeta\r\nlast".encode()
        self.write("lines.txt", raw)
        data = self.successful("read_file", path="./lines.txt", start_line=2, end_line=2)
        self.assertEqual(data["path"], "lines.txt")
        self.assertEqual(data["content"], "beta\r\n")
        self.assertEqual((data["start_line"], data["end_line"], data["line_count"]), (2, 2, 3))
        self.assertEqual(data["size_bytes"], len(raw))
        self.assertEqual(data["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(data["encoding"], "utf-8")
        self.assertEqual(self.successful("read_file", path="lines.txt")["content"], raw.decode())
        self.assertEqual(self.successful("read_file", path="lines.txt", start_line=3,
                                         end_line=999)["content"], "last")
        self.failure("read_file", "line_out_of_range", path="lines.txt", start_line=4)

    def test_empty_file_and_terminal_line_endings(self):
        self.write("empty", b"")
        data = self.successful("read_file", path="empty")
        self.assertEqual(data["content"], "")
        self.assertEqual((data["line_count"], data["start_line"], data["end_line"]), (0, 1, 0))
        self.failure("read_file", "line_out_of_range", path="empty", start_line=2)
        for ending in ("\n", "\r\n", "\r"):
            with self.subTest(ending=ending):
                self.write("one", "one" + ending)
                one = self.successful("read_file", path="one")
                self.assertEqual(one["line_count"], 1)
                self.assertEqual(one["content"], "one" + ending)

    def test_no_read_or_search_truncation(self):
        content = "needle\n" * 20000 + "FINAL_MARKER"
        self.write("large.txt", content)
        read = self.successful("read_file", path="large.txt")
        self.assertEqual(read["content"], content)
        search = self.successful("search_repository", pattern="needle", path="large.txt")
        self.assertEqual(search["match_count"], 20000)
        self.assertEqual(len(search["files"][0]["matches"]), 20000)
        self.assertEqual(search["files"][0]["matches"][-1]["start_line"], 20000)

    def test_no_directory_entry_truncation(self):
        for index in range(1100):
            self.write(f"files/{index:04}.txt", "hit")
        result = self.successful("list_directory", path="files")
        self.assertEqual(len(result["entries"]), 1100)
        search = self.successful("search_repository", pattern="hit", path="files")
        self.assertEqual(search["match_count"], 1100)
        self.assertEqual(search["searched_files"], 1100)

    def test_pep263_and_bom_are_explicit_and_hash_original_bytes(self):
        latin = b"# coding: latin-1\nname = 'caf\xe9'\n"
        self.write("latin.py", latin)
        data = self.successful("read_file", path="latin.py")
        self.assertIn("café", data["content"])
        self.assertEqual(data["encoding"], "iso-8859-1")
        self.assertEqual(data["sha256"], hashlib.sha256(latin).hexdigest())
        bom = b"\xef\xbb\xbfvalue = 1\n"
        self.write("bom.py", bom)
        data = self.successful("read_file", path="bom.py")
        self.assertEqual(data["encoding"], "utf-8-sig")
        self.assertEqual(data["content"], "value = 1\n")
        self.assertEqual(data["size_bytes"], len(bom))
        self.assertEqual(data["sha256"], hashlib.sha256(bom).hexdigest())

    def test_binary_and_invalid_encoding_are_errors_with_no_fake_text(self):
        for name, raw in (("nul.bin", b"hello\x00world"), ("control.bin", b"\x01\x02"),
                          ("invalid.bin", b"\xff\xfe\xff")):
            with self.subTest(name=name):
                self.write(name, raw)
                error = self.failure("read_file", "binary_file", path=name)
                self.assertEqual(error["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(error["size_bytes"], len(raw))
        self.write("encoding.py", b"# coding: no-such-encoding\nx = 1\n")
        self.failure("read_file", "decode_error", path="encoding.py")
        result = self.successful("search_repository", pattern="hello")
        self.assertEqual(result["match_count"], 0)
        self.assertEqual(len(result["skipped"]), 4)

    def test_literal_regex_multiline_context_and_character_spans(self):
        content = "α pre\r\nfirst.*\r\nsecond\r\nafter\r\n"
        self.write("sample.txt", content)
        literal = self.successful("search_repository", pattern="first.*\r\nsecond",
                                  context_lines=1)
        match = literal["files"][0]["matches"][0]
        begin = content.index("first")
        end = content.index("second") + len("second")
        self.assertEqual(match["span"], {"start": begin, "end": end})
        self.assertEqual((match["start_line"], match["start_column"]), (2, 1))
        self.assertEqual((match["end_line"], match["end_column"]), (3, 7))
        self.assertEqual(match["context"], {"start_line": 1, "end_line": 4,
                                           "content": content})
        regex = self.successful("search_repository", pattern=r"^first.*\r\nsecond", regex=True)
        self.assertEqual(regex["match_count"], 1)
        self.assertEqual(regex["files"][0]["matches"][0]["match"], "first.*\r\nsecond")
        self.assertEqual(self.successful("search_repository", pattern="first.*")["match_count"], 1)

    def test_invalid_regex_is_a_structured_model_visible_error(self):
        self.failure("search_repository", "invalid_regex", pattern="[", regex=True)
        self.write("text", "[")
        self.assertEqual(self.successful("search_repository", pattern="[")["match_count"], 1)

    def test_zero_width_empty_and_eof_search_positions(self):
        self.write("empty", "")
        match = self.successful("search_repository", pattern="", path="empty")["files"][0]["matches"][0]
        self.assertEqual(match["span"], {"start": 0, "end": 0})
        self.assertEqual(match["context"], {"start_line": 1, "end_line": 0, "content": ""})
        self.write("text", "a\n")
        matches = self.successful("search_repository", pattern=r"\Z", regex=True,
                                  path="text")["files"][0]["matches"]
        self.assertEqual(matches[0]["start_line"], 2)
        self.assertEqual(matches[0]["context"], {"start_line": 2, "end_line": 1, "content": ""})
        context = self.successful("search_repository", pattern=r"\Z", regex=True,
                                  path="text", context_lines=1)["files"][0]["matches"][0]["context"]
        self.assertEqual(context, {"start_line": 1, "end_line": 1, "content": "a\n"})

    def test_ast_qualified_nested_async_definitions_and_ranges(self):
        source = ("class Outer:\n"
                  "    @staticmethod\n"
                  "    async def method():\n"
                  "        def nested():\n"
                  "            pass\n"
                  "        class Inner:\n"
                  "            async def run(self):\n"
                  "                return 1\n"
                  "        return nested\n"
                  "\n"
                  "def top():\n"
                  "    pass\n")
        self.write("symbols.py", source)
        data = self.successful("list_symbols", path="symbols.py")
        self.assertEqual(data["symbols"], [
            {"qualified_name": "Outer", "start_line": 1, "end_line": 9},
            {"qualified_name": "Outer.method", "start_line": 3, "end_line": 9},
            {"qualified_name": "Outer.method.nested", "start_line": 4, "end_line": 5},
            {"qualified_name": "Outer.method.Inner", "start_line": 6, "end_line": 8},
            {"qualified_name": "Outer.method.Inner.run", "start_line": 7, "end_line": 8},
            {"qualified_name": "top", "start_line": 11, "end_line": 12},
        ])
        self.assertEqual(data["sha256"], hashlib.sha256(source.encode()).hexdigest())

    def test_invalid_ast_and_missing_file_errors_do_not_end_tools(self):
        self.write("broken.py", "def broken(\n")
        self.failure("list_symbols", "parse_error", path="broken.py")
        self.failure("read_file", "not_found", path="missing.py")
        self.write("good.py", "def good(): pass\n")
        self.assertEqual(self.successful("list_symbols", path="good.py")["symbols"][0]["qualified_name"],
                         "good")

    def test_special_files_are_not_read_and_do_not_block(self):
        os.mkfifo(self.repo / "pipe")
        self.failure("read_file", "not_regular_file", path="pipe")
        self.assertEqual(self.successful("list_directory")["skipped"],
                         [{"path": "pipe", "code": "not_regular_file"}])

    def test_closed_tools_return_an_error(self):
        self.tools.close()
        self.failure("read_file", "closed", path="file")


if __name__ == "__main__":
    unittest.main()
