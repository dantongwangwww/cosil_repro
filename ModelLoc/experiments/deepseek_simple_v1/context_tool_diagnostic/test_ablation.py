"""CPU-only coverage for frozen paired contexts; no model or service calls."""
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from context_tool_diagnostic.ablation import (
    EXPRESSION_CHAR_CAP, FrozenContextError, RANKING_INSTRUCTION,
    build_messages, extract_candidates, parse_final, prepare,
)


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


class AblationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cosil-ablation-test-")
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repository"
        self.repo.mkdir()
        self.source = ('class A:\n'
                       '    @property\n'
                       '    def p(self):\n'
                       '        """SECRET_DOCSTRING"""\n'
                       '        return "SECRET_BODY"\n'
                       '    @p.setter\n'
                       '    def p(self, value):\n'
                       '        self.value = value\n'
                       '    async def f(self, x: int = 2, /, *, y: str = "v") -> str:\n'
                       '        def nested(z=None):\n'
                       '            return "NESTED_BODY"\n'
                       '        return nested(x)\n'
                       'def _TR56(value):\n'
                       '    def _f(x):\n'
                       '        return x\n'
                       '    return _f(value)\n')
        self.second = 'def other():\n    return 5\n'
        (self.repo / "a.py").write_text(self.source)
        (self.repo / "b.py").write_text(self.second)
        (self.repo / "evidence.py").write_text('def forbidden_evidence():\n    return "GREP_SECRET"\n')
        self.git("init", "-q")
        self.git("add", "a.py", "b.py", "evidence.py")
        self.git("-c", "user.name=CPU test", "-c", "user.email=cpu@example.invalid", "commit", "-qm", "base fixture")
        commit = self.git("rev-parse", "HEAD").strip()
        mirror = self.root / "mirrors/example.git"
        subprocess.run(["git", "clone", "--bare", "--quiet", str(self.repo), str(mirror)], check=True)
        self.job = {"instance_id": "example__example-1", "repo": "example/example", "base_commit": commit,
                    "snapshot": str(self.repo), "problem_statement": "A problem in example__example-1 example/example " + commit}
        self.original = self.root / "historical_run"
        self.issue = self.original / "lite_pilot/D-SIMPLE/example__example-1"
        self.issue.mkdir(parents=True)
        self.out = self.root / "diagnostic/issue"
        self.selection = {"draws": [["b.py", "a.py"]] * 5,
                          "roles": {"L0": 0, "L1": 1, "L2": 2, "agreement_only": [3, 4]},
                          "fallback": False, "parse_error_draws": [], "ranked_edit_files": ["b.py", "a.py"]}
        self.context = {"loaded_whole_files": ["b.py", "a.py"], "ranked_edit_files": ["b.py", "a.py"],
                        "skipped_files": [{"path": "large.py", "reason": "whole_file_overflow"}],
                        "reference_tokens": 123, "evidence_tokens": 4,
                        "queries": [{"query": {"kind": "literal", "text": "GREP_SECRET"}, "new_files": ["evidence.py"]}],
                        "blocks": [self.block("b.py", self.second), self.block("a.py", self.source),
                                   self.block("evidence.py", (self.repo / "evidence.py").read_text())]}
        self.write_history()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    @staticmethod
    def block(path, text):
        return {"path": path, "text": text, "sha256": sha(text), "start_line": 1,
                "end_line": len(text.splitlines()), "complete_file": True}

    def write_history(self):
        (self.issue / "file_selection.json").write_text(json.dumps(self.selection))
        (self.issue / "context.json").write_text(json.dumps(self.context))

    def freeze(self):
        return prepare(self.job, self.out, original_run=self.original, mirror_root=self.root / "mirrors")

    def test_all_definitions_same_order_and_identity_in_both_arms(self):
        frozen = self.freeze()
        ids = [c["identity"] for c in frozen["candidates"]]
        self.assertEqual(ids, ["b.py::other", "a.py::A.p", "a.py::A.p", "a.py::A.f",
                               "a.py::A.f.nested", "a.py::_TR56", "a.py::_TR56._f"])
        arms = build_messages(self.job, frozen)
        signature, full = arms["A-SIGNATURE"], arms["A-FULL"]
        self.assertEqual(signature["candidate_id_order"], full["candidate_id_order"])
        self.assertEqual(signature["candidate_sha256"], full["candidate_sha256"])
        self.assertEqual(signature["source_file_order"], ["b.py", "a.py"])
        self.assertEqual(signature["messages"][0], {"role": "system", "content": RANKING_INSTRUCTION})
        sigmsg, fullmsg = signature["messages"][1]["content"], full["messages"][1]["content"]
        self.assertEqual(sigmsg.split("<source>\n")[0], fullmsg.split("<source>\n")[0])
        for text in ("SECRET_DOCSTRING", "SECRET_BODY", "NESTED_BODY", "@property", "@p.setter", "GREP_SECRET", "forbidden_evidence"):
            self.assertNotIn(text, sigmsg)
        self.assertIn(self.source, fullmsg)
        self.assertIn(self.second, fullmsg)
        self.assertNotIn("GREP_SECRET", fullmsg)
        self.assertNotIn("forbidden_evidence", fullmsg)
        self.assertNotIn(self.job["instance_id"], sigmsg)
        self.assertNotIn(self.job["base_commit"], sigmsg)
        self.assertNotIn("def_line", sigmsg)
        self.assertEqual(frozen["manifest"]["excluded_grep_evidence"][0]["origin"], "grep_evidence")
        self.assertTrue(frozen["manifest"]["excluded_grep_evidence"][0]["original_complete_file_flag"])

    def test_uniform_expression_limit_and_annotation_async(self):
        source = ('async def f(x: list[int] = "' + "a" * 300 + '", *, y=2) -> str:\n'
                  '    return "BODY_SHOULD_NOT_SHOW"\n')
        candidates, log = extract_candidates("a.py", source)
        self.assertIn("async def f(x: list[int]", candidates[0]["signature"])
        self.assertIn("-> str:", candidates[0]["signature"])
        self.assertIn("<expression exceeded 160 characters>", candidates[0]["signature"])
        self.assertNotIn("BODY_SHOULD_NOT_SHOW", candidates[0]["signature"])
        self.assertEqual(log["expression_char_cap"], EXPRESSION_CHAR_CAP)
        self.assertEqual(len(log["truncations"]), 1)

    def test_source_context_overflow_never_truncates_and_excludes_issue(self):
        frozen = self.freeze()
        ordinary = build_messages(self.job, frozen)
        cap = ordinary["A-SIGNATURE"]["context_o200k_tokens"]
        arms = build_messages(self.job, frozen, context_cap=cap)
        self.assertEqual(arms["A-SIGNATURE"]["status"], "ready")
        self.assertEqual(arms["A-FULL"]["status"], "context_overflow")
        self.assertIn(self.source, arms["A-FULL"]["messages"][1]["content"])
        job = dict(self.job, problem_statement="Huge issue. " * 2000)
        expanded = build_messages(job, frozen, context_cap=cap)
        self.assertEqual(expanded["A-SIGNATURE"]["context_o200k_tokens"], cap)
        self.assertEqual(expanded["A-SIGNATURE"]["status"], "ready")

    def test_parser_fixed_slots_duplicates_and_strict_id(self):
        frozen = self.freeze()
        output = {"ranked_functions": [{"path": "a.py", "qualified_name": "A.p"},
                    {"path": "./a.py", "qualified_name": "A.p"},
                    {"path": "a.py", "qualified_name": "A.p"}, "bad",
                    {"path": "evidence.py", "qualified_name": "forbidden_evidence"},
                    {"path": "a.py", "qualified_name": "A.f.nested"}]}
        parsed = parse_final(json.dumps(output), frozen)
        self.assertEqual(parsed["normalized_candidate_slots"], ["a.py::A.p", None, "a.py::A.p", None, None, "a.py::A.f.nested"])
        self.assertEqual(parsed["invalid_slots"], [2, 4, 5])
        self.assertEqual(parsed["duplicate_slots"], [3])
        self.assertIsNone(parsed["predicted_functions"][1])

    def test_parser_rejects_multiple_outputs_duplicate_keys_and_extra_fields(self):
        frozen = self.freeze()
        good = '{"ranked_functions":[]}'
        cases = [good + good, "```json\n" + good + "\n```", '{"ranked_functions":[],"ranked_functions":[]}',
                 '{"ranked_functions":[],"explanation":"x"}', '{"ranked_functions":null}',
                 '{"ranked_functions":[NaN]}', json.dumps({"ranked_functions": [None] * 11})]
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(parse_final(raw, frozen)["status"], "parse_error")

    def test_base_sha_and_original_snapshot_content_are_checked(self):
        self.freeze()
        (self.repo / "a.py").write_text(self.source + "# changed\n")
        with self.assertRaisesRegex(FrozenContextError, "Git base"):
            self.freeze()
        (self.repo / "a.py").write_text(self.source)
        self.context["blocks"][1]["sha256"] = "bad"
        self.write_history()
        with self.assertRaisesRegex(FrozenContextError, "SHA drift"):
            self.freeze()

    def test_frozen_source_and_candidate_metadata_drift_are_detected(self):
        frozen = self.freeze()
        changed = copy.deepcopy(frozen)
        changed["files"][0]["text"] += "# changed\n"
        with self.assertRaisesRegex(FrozenContextError, "source SHA"):
            build_messages(self.job, changed)
        changed = copy.deepcopy(frozen)
        changed["candidates"][0]["qualified_name"] = "invented"
        with self.assertRaisesRegex(FrozenContextError, "candidates drift"):
            build_messages(self.job, changed)

    def test_frozen_order_idempotency_and_historical_isolation(self):
        before = {p.name: p.read_bytes() for p in self.issue.iterdir()}
        first, second = self.freeze(), self.freeze()
        self.assertEqual(first, second)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.issue.iterdir()})
        with self.assertRaisesRegex(FrozenContextError, "outside historical"):
            prepare(self.job, self.issue / "new", original_run=self.original, mirror_root=self.root / "mirrors")
        changed = copy.deepcopy(first)
        changed["files"].reverse()
        with self.assertRaisesRegex(FrozenContextError, "ordering drift"):
            build_messages(self.job, changed)

    def test_prepare_reads_only_explicit_history_base_and_no_private_labels(self):
        original_read_bytes, original_read_text = Path.read_bytes, Path.read_text
        seen = []
        def guarded_bytes(path, *args, **kwargs):
            seen.append(str(path))
            self.assertNotIn("evaluator_private", str(path))
            self.assertNotIn("holdout", str(path))
            self.assertNotIn("pruner_test", str(path))
            return original_read_bytes(path, *args, **kwargs)
        def guarded_text(path, *args, **kwargs):
            self.assertNotIn("evaluator_private", str(path))
            self.assertNotIn("holdout", str(path))
            self.assertNotIn("pruner_test", str(path))
            return original_read_text(path, *args, **kwargs)
        with patch.object(Path, "read_bytes", guarded_bytes), patch.object(Path, "read_text", guarded_text):
            frozen = self.freeze()
            build_messages(self.job, frozen)
        self.assertEqual(set(seen), {str(self.issue / "file_selection.json"), str(self.issue / "context.json"),
                                     str(self.repo / "a.py"), str(self.repo / "b.py")})

    def test_ast_parse_failure_and_unsafe_paths(self):
        rows, log = extract_candidates("a.py", "def invalid(:\n")
        self.assertEqual(rows, [])
        self.assertEqual(log["status"], "parse_error")
        for path in ("../a.py", "/a.py", "./a.py", "a//b.py", "a\\b.py"):
            with self.subTest(path=path), self.assertRaises(FrozenContextError):
                extract_candidates(path, "def f(): pass\n")


if __name__ == "__main__":
    unittest.main()
