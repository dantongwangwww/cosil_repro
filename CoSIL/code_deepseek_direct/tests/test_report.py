"""Synthetic artifact tests; never access an actual run, model, or evaluator."""

import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_deepseek_direct import common as C
from code_deepseek_direct.report import CSV_NAME, TRACE_NAME, render


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="direct-report-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run, self.docs = self.root / "run", self.root / "docs"
        self.run.mkdir()
        self.initial = [{"role": "system", "content": "Synthetic public instructions 中文"},
                        {"role": "user", "content": "Synthetic issue only."}]
        self.history = copy.deepcopy(self.initial)
        self.put("initial_messages.json", self.initial)
        self.tool_count = 0
        self.turn_count = 0
        self.final = None

    def put(self, name, value):
        destination = self.run / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def tool(self, name, arguments, data=None, ok=True, raw=None, call_id=None):
        call_id = call_id or "tool-" + str(self.tool_count + 1)
        return {"id": call_id, "type": "function", "function": {
            "name": name, "arguments": raw if raw is not None else json.dumps(arguments)}}, {
                "ok": ok, "tool": name, "arguments": arguments, "data": data,
                "error": None if ok else {"code": "synthetic_error"}}

    def turn(self, content, tools=(), failures=(), usage=None, cost=0.01):
        self.turn_count += 1
        turn = self.turn_count
        folder = f"calls/{turn:04}"
        self.put(folder + "/request.json", {"messages": copy.deepcopy(self.history),
                                            "thinking": {"type": "disabled"}})
        message = {"role": "assistant", "content": content,
                   "reasoning_content": "PRIVATE_COT_SENTINEL"}
        if tools:
            message["tool_calls"] = [tool[0] for tool in tools]
        response = {"model": "synthetic", "id": f"response-{turn}", "choices": [{
            "message": message, "finish_reason": "tool_calls" if tools else "stop"}]}
        receipt = {"http_status": 200, "elapsed_seconds": 1.25,
                   "usage": usage if usage is not None else {
                       "prompt_tokens": 100, "completion_tokens": 20,
                       "prompt_cache_hit_tokens": 40, "total_tokens": 120},
                   "cost": {"usd": cost, "not_provider_invoice": True}}
        for attempt, failure in enumerate(failures):
            self.put(f"{folder}/attempt_{attempt}_started.json", {"utc": "synthetic"})
            if failure is not None:
                self.put(f"{folder}/attempt_{attempt}_receipt.json", failure)
        attempt = len(failures)
        self.put(f"{folder}/attempt_{attempt}_started.json", {"utc": "synthetic"})
        self.put(f"{folder}/attempt_{attempt}_receipt.json", receipt)
        self.put(f"{folder}/attempt_{attempt}_response.json", response)
        self.put(folder + "/result.json", {"response": response, "receipt": receipt})
        public = {key: value for key, value in message.items() if key != "reasoning_content"}
        self.history.append(public)
        for position, (call, output) in enumerate(tools):
            self.tool_count += 1
            wire = json.dumps(output, ensure_ascii=False)
            record = {"turn": turn, "position": position, "tool_call_id": call["id"],
                      "name": call["function"]["name"], "raw_arguments": call["function"]["arguments"],
                      "arguments": output["arguments"], "output": output, "wire_content": wire,
                      "output_sha256": C.digest(output), "output_utf8_bytes": len(wire.encode()),
                      "elapsed_seconds": 0.1}
            self.put(f"tools/{self.tool_count:04}.json", record)
            self.history.append({"role": "tool", "tool_call_id": call["id"], "content": wire})
        self.final = content

    def finish(self):
        self.put("result.json", {"status": "complete", "final_response": self.final,
                                 "model_turns": self.turn_count, "tool_calls": self.tool_count,
                                 "model": "synthetic", "elapsed_seconds": 9.0})

    def generated(self):
        self.finish()
        return render(self.run, self.docs)

    def read_data(self, path="file.py", sha="same", lo=1, hi=5, content="synthetic"):
        return {"path": path, "sha256": sha, "start_line": lo, "end_line": hi,
                "line_count": max(hi, 0), "content": content}

    def test_complete_public_trace_has_no_truncation_or_private_cot(self):
        text = "中文公开说明\n```\n" + "FULL_CONTENT\n" * 25000 + "FINAL_SENTINEL"
        read = self.tool("read_file", {"path": "file.py", "start_line": 1},
                         self.read_data(content=text), raw=' { "path" : "file.py", "start_line": 1 } ')
        self.turn(None, [read])
        self.turn("公开进度\n````\nMore evidence", [self.tool("list_symbols", {"path": "file.py"},
                  {"path": "file.py", "symbols": []})])
        self.turn('{"files":[],"functions":[],"summary":"完成"}')
        outputs = self.generated()
        trace = (self.docs / TRACE_NAME).read_text()
        self.assertIn("Synthetic public instructions 中文", trace)
        self.assertIn("公开进度\n````\nMore evidence", trace)
        self.assertIn(read[0]["function"]["arguments"], trace)
        wire = json.loads((self.run / "tools/0001.json").read_text())["wire_content"]
        self.assertIn(wire, trace)
        self.assertIn("FINAL_SENTINEL", trace)
        self.assertIn(self.final, trace)
        self.assertIn("`````text\n", trace)
        self.assertGreater(len(trace), 300000)
        for path in outputs["outputs"].values():
            self.assertNotIn("PRIVATE_COT_SENTINEL", Path(path).read_text())
        self.assertEqual(outputs["summary"]["warnings"], [])
        self.assertEqual(outputs["summary"]["actual_api_attempts"], 3)

    def test_attempt_identity_retries_and_unknown_billing_are_not_zero_or_double_counted(self):
        failures = [dict(http_status=500, usage=None, billing_unknown=True, elapsed_seconds=2),
                    dict(status="transport_error", usage=None, billing_unknown=True,
                         elapsed_seconds=3), None]
        self.turn("Finished", failures=failures)
        summary = self.generated()["summary"]
        self.assertEqual(summary["actual_api_attempts"], 4)
        self.assertEqual(summary["http_successful_attempts"], 1)
        self.assertEqual(summary["http_error_attempts"], 1)
        self.assertEqual(summary["transport_failure_attempts"], 1)
        self.assertEqual(summary["started_or_response_without_receipt"], 1)
        self.assertEqual(summary["billing_unknown_attempts"], 3)
        self.assertEqual(summary["known_token_totals"]["prompt_tokens"], 100)
        self.assertEqual(summary["usage_missing_attempts"]["prompt_tokens"], 3)
        self.assertEqual(summary["known_estimated_cost_usd"], 0.01)
        self.assertIsNone(summary["total_cost_usd"])
        with (self.docs / CSV_NAME).open(encoding="utf-8-sig", newline="") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["api_attempts"], "4")
        self.assertEqual(row["prompt_tokens"], "100")
        self.assertEqual(row["total_cost_usd"], "")
        self.assertEqual(row["latency_seconds_all_receipted_attempts"], "6.25")

    def test_zero_usage_cache_and_cost_are_known(self):
        self.turn("Done", usage={"prompt_tokens": 0, "completion_tokens": 0,
                                  "prompt_tokens_details": {"cached_tokens": 0}}, cost=0)
        summary = self.generated()["summary"]
        self.assertEqual(summary["known_token_totals"], dict.fromkeys(summary["known_token_totals"], 0))
        self.assertEqual(summary["usage_missing_attempts"], dict.fromkeys(summary["usage_missing_attempts"], 0))
        self.assertEqual(summary["total_cost_usd"], 0)
        self.assertEqual(summary["cost_unknown_attempts"], 0)

    def test_read_coverage_uses_returned_intervals_path_and_raw_sha(self):
        tools = [self.tool("read_file", {"path": "file.py", "end_line": 999},
                           self.read_data(lo=lo, hi=hi), call_id="same-id")
                 for lo, hi in [(1, 5), (4, 8), (20, 22)]]
        tools += [self.tool("read_file", {"path": "empty.py"},
                            self.read_data(path="empty.py", lo=1, hi=0)),
                  self.tool("read_file", {"path": "failed.py"}, ok=False)]
        self.turn(None, tools)
        self.turn("Done")
        summary = self.generated()["summary"]
        coverage = summary["read_file_coverage"]
        self.assertEqual(summary["executed_tool_calls"], 5)
        self.assertEqual(summary["native_tool_calls_in_api_responses"], 5)
        self.assertEqual(coverage["unique_paths"], 2)
        self.assertEqual(coverage["unique_lines"], 11)
        file = next(x for x in coverage["files"] if x["path"] == "file.py")
        self.assertEqual(file["intervals"], [[1, 8], [20, 22]])
        self.assertEqual(file["returned_lines_with_repetition"], 13)
        self.assertEqual(file["read_calls"], 3)

    def test_search_and_symbols_do_not_inflate_read_file_line_coverage(self):
        data = {"path": ".", "pattern": "target", "regex": False, "searched_files": 10,
                "match_count": 2, "files": [{"path": "a.py", "matches": [
                    {"context": {"start_line": 1, "end_line": 999}}]}], "skipped": []}
        self.turn(None, [self.tool("search_repository", {"pattern": "target"}, data),
                         self.tool("search_repository", {"pattern": "target"}, data),
                         self.tool("list_symbols", {"path": "a.py"}, {"path": "a.py", "symbols": []})])
        self.turn("Done")
        summary = self.generated()["summary"]
        self.assertEqual(summary["read_file_coverage"]["unique_lines"], 0)
        self.assertEqual(summary["search"]["successful_calls"], 2)
        self.assertEqual(summary["search"]["searched_files_with_repetition"], 20)
        self.assertEqual(summary["search"]["matches_with_repetition"], 4)
        self.assertEqual(summary["search"]["unique_matched_paths"], ["a.py"])
        self.assertEqual(summary["list_symbols_unique_paths"], ["a.py"])

    def test_malformed_raw_arguments_and_extra_continuation_message_are_preserved(self):
        self.turn("Partial", [self.tool("read_file", None, ok=False, raw="{broken")])
        self.history.append({"role": "user", "content": "Continue exactly from prior output."})
        self.turn("Done")
        summary = self.generated()["summary"]
        trace = (self.docs / TRACE_NAME).read_text()
        self.assertIn("{broken", trace)
        self.assertIn("Continue exactly from prior output.", trace)
        self.assertEqual(summary["warnings"], [])

    def test_only_whitelisted_sources_are_read_and_originals_are_unchanged(self):
        self.turn("Done")
        self.finish()
        self.put("gold.json", {"never": "FORBIDDEN_GOLD"})
        self.put("old_predictions.json", {"never": "FORBIDDEN_PREDICTION"})
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.run.rglob("*.json")}
        original = Path.read_bytes

        def guarded(path):
            self.assertNotIn(path.name, {"gold.json", "old_predictions.json"})
            self.assertTrue(path.is_relative_to(self.run))
            return original(path)

        with patch.object(Path, "read_bytes", guarded):
            summary = render(self.run, self.docs)["summary"]
        for path, digest in before.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertNotIn("gold.json", summary["source_artifacts_sha256"])
        self.assertNotIn("old_predictions.json", summary["source_artifacts_sha256"])

    def test_incomplete_or_wrong_final_answer_is_rejected_before_writing(self):
        self.put("result.json", {"status": "running"})
        with self.assertRaises(ValueError):
            render(self.run, self.docs)
        self.assertFalse(self.docs.exists())
        self.turn("Actual final")
        self.finish()
        self.put("result.json", {"status": "complete", "final_response": "Wrong final"})
        with self.assertRaises(ValueError):
            render(self.run, self.docs)
        self.assertFalse(self.docs.exists())

    def test_symlink_artifact_cannot_read_outside_run(self):
        outside = self.root / "outside.json"
        outside.write_text('{"private":"OUTSIDE_SECRET"}')
        (self.run / "result.json").symlink_to(outside)
        with self.assertRaises(ValueError):
            render(self.run, self.docs)
        self.assertFalse(self.docs.exists())

    def test_terminal_context_error_preserves_prior_trace_without_inventing_final(self):
        self.turn("Public progress only", [self.tool("read_file", {"path": "file.py"},
                                                    self.read_data(content="Already inspected evidence"))])
        self.put("calls/0002/request.json", {"messages": self.history})
        self.put("calls/0002/attempt_0_started.json", {"utc": "synthetic"})
        self.put("calls/0002/attempt_0_receipt.json", {"http_status": 400, "usage": None,
                 "elapsed_seconds": 0.75, "billing_unknown": False})
        self.put("error.json", {"type": "RuntimeError", "error": "DeepSeek API HTTP 400",
                                 "utc": "synthetic", "traceback": "PRIVATE_COT_SENTINEL"})
        summary = render(self.run, self.docs)["summary"]
        trace = (self.docs / TRACE_NAME).read_text()
        self.assertEqual(summary["status"], "terminal_error")
        self.assertFalse(summary["model_final_localization_available"])
        self.assertEqual(summary["actual_api_attempts"], 2)
        self.assertEqual(summary["http_error_attempts"], 1)
        self.assertEqual(summary["known_token_totals"]["prompt_tokens"], 100)
        self.assertEqual(summary["executed_tool_calls"], 1)
        self.assertIn("模型未给出最终定位", trace)
        self.assertIn("Public progress only", trace)
        self.assertIn("Already inspected evidence", trace)
        self.assertIn("本轮未记录到模型的公开 assistant 响应", trace)
        self.assertNotIn("PRIVATE_COT_SENTINEL", trace)
        self.assertNotIn("## 最终回答", trace)

    def test_private_extension_fields_are_omitted_but_public_source_literals_remain(self):
        self.turn(None, [self.tool("read_file", {"path": "file.py"},
                                  self.read_data(content="reasoning_content is a source identifier"))])
        self.turn("Done")
        self.finish()
        for name in ("calls/0001/result.json", "calls/0001/attempt_0_response.json"):
            value = json.loads((self.run / name).read_text())
            response = value.get("response", value)
            response["choices"][0]["message"]["tool_calls"][0]["reasoning_content"] = "PRIVATE_COT_SENTINEL"
            self.put(name, value)
        for name in ("calls/0001/result.json", "calls/0001/attempt_0_receipt.json"):
            value = json.loads((self.run / name).read_text())
            receipt = value.get("receipt", value)
            receipt["reasoning_content"] = "PRIVATE_COT_SENTINEL"
            receipt["usage"]["reasoning_content"] = "PRIVATE_COT_SENTINEL"
            self.put(name, value)
        outputs = render(self.run, self.docs)["outputs"]
        for path in outputs.values():
            self.assertNotIn("PRIVATE_COT_SENTINEL", Path(path).read_text())
        self.assertIn("reasoning_content is a source identifier", (self.docs / TRACE_NAME).read_text())

    def test_billing_unknown_with_partial_cost_remains_unknown_and_invalid_latency_is_safe(self):
        failure = dict(status="transport_error", usage=None, billing_unknown=True,
                       elapsed_seconds=None, cost={"usd": 0.02})
        self.turn("Done", failures=[failure])
        summary = self.generated()["summary"]
        self.assertEqual(summary["known_estimated_cost_usd"], 0.03)
        self.assertIsNone(summary["total_cost_usd"])
        self.assertEqual(summary["billing_unknown_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
