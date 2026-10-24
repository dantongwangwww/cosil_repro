"""Synthetic exact-wire reuse and seven-stage paper integration tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from code_repair50 import locator as L
from code_repair50 import prepare as P


class Provider:
    def __init__(self):
        self.calls = []

    def ask(self, messages, stage, **parameters):
        self.calls.append((copy.deepcopy(messages), stage, parameters))
        if stage.startswith("file_draw_"):
            content = {"ranked_files": ["src/spack/spack/logic.py"]}
        elif stage == "query_planning":
            content = {"queries": []}
        else:
            content = {"ranked_functions": [{"path": "src/spack/spack/logic.py",
                "qualified_name": "wrong_identity", "evidence_start_line": 1, "evidence_end_line": 1}]}
        return {"content": json.dumps(content), "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                "receipt": {"new": True}}


class LocatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        base = self.root / "base"
        (base / "src/spack/spack").mkdir(parents=True)
        source = base / "src/spack/spack/logic.py"
        source.write_text("def f():\n    return 1\n")
        index = {"src/spack/spack/logic.py": {"definitions": [
            {"kind": "function", "qualified_name": "f", "start_line": 1, "end_line": 2}]}}
        self.index = self.root / "index.json"
        self.structure = self.root / "structure.json"
        self.index.write_text(json.dumps(index))
        self.structure.write_text("{}")
        self.job = {"instance_id": "spack__spack-1", "repo": "spack/spack", "base_commit": "a" * 40,
                    "problem_statement": "Fix spack/spack behavior in src/spack/spack/logic.py.",
                    "cohort": "repair50", "snapshot": str(base), "paths": ["src/spack/spack/logic.py"],
                    "code_index": str(self.index), "structure": str(self.structure)}
        self.qualified = {"frozen": True, "tasks": [{k: self.job[k] for k in
                          ("instance_id", "repo", "base_commit")} ] + [
                              {"instance_id": f"fixture__repo-{n}", "repo": f"fixture{n}/repo",
                               "base_commit": "a" * 40, "qualification_passed": True}
                              for n in range(1, 50)]}

    def tearDown(self):
        self.temporary.cleanup()

    def history(self, messages, stage="file_draw_0", content="historic"):
        job_path = self.root / "oldjob.json"
        job_path.write_text(json.dumps(self.job))
        prep = self.root / "oldprep.json"
        source = Path(self.job["snapshot"]) / self.job["paths"][0]
        prep.write_text(json.dumps({"status": "complete", "data_sha256": {
            str(job_path): P.sha256(job_path), str(self.index): P.sha256(self.index),
            str(self.structure): P.sha256(self.structure)},
            "snapshot_sha256": {str(source): P.sha256(source)}}))
        folder = self.root / "oldresult/calls" / ("0001_" + stage)
        folder.mkdir(parents=True)
        request = L.wire_request(messages, 6144)
        response = {"model": "deepseek-flash", "choices": [{"finish_reason": "stop",
                    "message": {"role": "assistant", "content": content}}]}
        receipt = {"attempt": 0, "http_status": 200, "thinking_mode": "disabled",
                   "reasoning_content_present": False, "finish_reason": "stop",
                   "request_sha256": L.digest(request),
                   "response_sha256": L.digest(json.dumps(response, sort_keys=True))}
        usage = {"prompt_tokens": 3, "completion_tokens": 2}
        for name, value in (("request.json", {"request": request, "sha256": L.digest(request)}),
                            ("result.json", {"content": content, "receipt": receipt, "usage": usage}),
                            ("attempt_0_receipt.json", receipt), ("attempt_0_response.json", response)):
            (folder / name).write_text(json.dumps(value))
        return {"job": str(job_path), "preparation_receipt": str(prep),
                "result_dir": str(self.root / "oldresult")}, folder

    def test_seven_stages_preserve_issue_source_path_and_wrong_prediction(self):
        provider = Provider()
        result = L.run_locator(self.job, self.root / "new", provider, self.qualified)
        self.assertEqual(len(provider.calls), 7)
        self.assertEqual([c[1] for c in provider.calls], [f"file_draw_{n}" for n in range(5)]
                         + ["query_planning", "function_localization"])
        self.assertIn("spack/spack", provider.calls[0][0][0]["content"])
        self.assertIn("src/spack/spack/logic.py", provider.calls[-1][0][0]["content"])
        self.assertNotIn("BENCHMARK_METADATA", provider.calls[-1][0][0]["content"])
        self.assertEqual(result["predicted_functions"][0]["qualified_name"], "wrong_identity")
        self.assertEqual([c[2]["max_tokens"] for c in provider.calls], [6144] * 5 + [4096, 4096])
        self.assertTrue(all(c[2]["temperature"] is None for c in provider.calls))
        self.assertEqual(result["new_localization_requests"], 7)

    def test_unqualified_roster_blocks_before_any_paid_call(self):
        provider = Provider()
        with self.assertRaisesRegex(ValueError, "frozen"):
            L.run_locator(self.job, self.root / "new", provider, {"frozen": False, "tasks": []})
        self.assertEqual(provider.calls, [])

    def test_qualified_identity_mismatch_blocks(self):
        manifest = copy.deepcopy(self.qualified)
        manifest["tasks"][0]["base_commit"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "same base"):
            L.qualification_member(self.job, manifest)

    def test_one_pseudo_frozen_task_cannot_authorize_calls(self):
        provider = Provider()
        manifest = {"frozen": True, "tasks": self.qualified["tasks"][:1]}
        with self.assertRaisesRegex(ValueError, "exactly 50"):
            L.run_locator(self.job, self.root / "new", provider, manifest)
        self.assertEqual(provider.calls, [])

    def test_missing_fiftieth_task_blocks(self):
        manifest = copy.deepcopy(self.qualified)
        manifest["tasks"].pop()
        with self.assertRaisesRegex(ValueError, "exactly 50"):
            L.qualification_member(self.job, manifest)

    def test_duplicate_qualified_repository_blocks(self):
        manifest = copy.deepcopy(self.qualified)
        manifest["tasks"][1]["repo"] = manifest["tasks"][0]["repo"]
        with self.assertRaisesRegex(ValueError, "repositories must be distinct"):
            L.qualification_member(self.job, manifest)

    def test_duplicate_qualified_id_blocks(self):
        manifest = copy.deepcopy(self.qualified)
        manifest["tasks"][1]["instance_id"] = manifest["tasks"][0]["instance_id"]
        with self.assertRaisesRegex(ValueError, "IDs must be distinct"):
            L.qualification_member(self.job, manifest)

    def test_nonboolean_frozen_truthy_values_block(self):
        for value in (1, "true", "True", [True]):
            manifest = copy.deepcopy(self.qualified)
            manifest["frozen"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "frozen"):
                L.qualification_member(self.job, manifest)

    def test_empty_identity_fields_block(self):
        for key in ("instance_id", "repo", "base_commit"):
            manifest = copy.deepcopy(self.qualified)
            manifest["tasks"][1][key] = "  "
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "nonempty"):
                L.qualification_member(self.job, manifest)

    def test_explicit_nonpassing_qualification_blocks(self):
        for value in (False, None, "NOT_CHECKED", 1):
            manifest = copy.deepcopy(self.qualified)
            manifest["tasks"][1]["qualification_passed"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "passed qualification"):
                L.qualification_member(self.job, manifest)

    def test_identical_successful_http_request_reuses_without_provider(self):
        messages = [{"role": "user", "content": "literal src/spack/spack/logic.py"}]
        record, _ = self.history(messages)
        provider = Provider()
        wrapper = L.ExactHistoricalStages(self.job, self.root / "new", provider, record)
        result = wrapper.ask(messages, "file_draw_0", max_tokens=6144)
        self.assertEqual(result["content"], "historic")
        self.assertEqual(provider.calls, [])
        self.assertTrue(wrapper.reuse[0]["reused"])
        self.assertEqual(wrapper.reuse[0]["new_API_calls"], 0)

    def test_old_path_mask_is_not_inverted_or_reused(self):
        record, _ = self.history([{"role": "user", "content": "src/[BENCHMARK_METADATA]/logic.py"}])
        provider = Provider()
        wrapper = L.ExactHistoricalStages(self.job, self.root / "new", provider, record)
        wrapper.ask([{"role": "user", "content": "src/spack/spack/logic.py"}],
                    "file_draw_0", max_tokens=6144)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(wrapper.reuse[0]["reason"], "ACTUAL_WIRE_OR_REQUEST_SHA_DIFFERS")

    def test_original_response_tampering_is_not_reused(self):
        messages = [{"role": "user", "content": "literal"}]
        record, folder = self.history(messages)
        response = json.loads((folder / "attempt_0_response.json").read_text())
        response["choices"][0]["message"]["content"] = "tampered"
        (folder / "attempt_0_response.json").write_text(json.dumps(response))
        provider = Provider()
        wrapper = L.ExactHistoricalStages(self.job, self.root / "new", provider, record)
        wrapper.ask(messages, "file_draw_0", max_tokens=6144)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(wrapper.reuse[0]["reason"], "ORIGINAL_HTTP_RESPONSE_SHA_DIFFERS")

    def test_source_drift_disables_historical_reuse(self):
        messages = [{"role": "user", "content": "literal"}]
        record, _ = self.history(messages)
        source = Path(self.job["snapshot"]) / self.job["paths"][0]
        source.write_text("def f():\n    return 99\n")
        provider = Provider()
        wrapper = L.ExactHistoricalStages(self.job, self.root / "new", provider, record)
        wrapper.ask(messages, "file_draw_0", max_tokens=6144)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(wrapper.reuse[0]["reason"], "BASE_SOURCE_SHA_MISMATCH")

    def test_wire_omits_sampling_and_disables_thinking(self):
        wire = L.wire_request([{"role": "user", "content": "x"}], 4096)
        self.assertEqual(wire["thinking"], {"type": "disabled"})
        self.assertNotIn("temperature", wire)
        self.assertNotIn("top_p", wire)
        with self.assertRaises(ValueError):
            L.wire_request([], 1, temperature=0)


if __name__ == "__main__":
    unittest.main()
