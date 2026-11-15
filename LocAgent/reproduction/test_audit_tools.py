"""Synthetic CPU boundary checks for offline tool evidence accounting."""
import json
from pathlib import Path
import tempfile
import unittest

from reproduction.audit_tools import audit_run, sample_evidence, Reader, without_finish_parameters


class AuditToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        (self.run / "selection").mkdir(parents=True)
        (self.run / "selection/manifest.json").write_text(json.dumps({"records": [{"instance_id": "owner__repo-1"}]}))
        self.task = self.run / "outputs/owner__repo-1"
        self.sample = self.task / "samples/sample_01"
        self.requests = self.sample / "requests"
        self.requests.mkdir(parents=True)
        self.schema = [{"type": "function", "function": {"name": "get_entity_contents", "parameters": {
            "type": "object", "properties": {"entity_names": {"type": "array", "items": {"type": "string"}}},
            "required": ["entity_names"], "additionalProperties": False}}}]
        self.ledger = []

    def tearDown(self):
        self.temp.cleanup()

    def write_attempt(self, n, messages, response, status=200, finished=True, thinking=False):
        request_file = f"request_{n:03d}_attempt_1_request.json"
        response_file = f"request_{n:03d}_attempt_1_response.txt"
        request = {"model": "qwen3-8b", "messages": messages, "tools": self.schema,
                   "chat_template_kwargs": {"enable_thinking": thinking}}
        (self.requests / request_file).write_text(json.dumps(request))
        if response is not None:
            (self.requests / response_file).write_text(json.dumps(response))
        self.ledger.append({"event": "started", "http_attempt": n, "completion_request": n,
                            "request_file": request_file, "endpoint": "http://127.0.0.1:7353/v1/chat/completions"})
        if finished:
            self.ledger.append({"event": "finished", "http_attempt": n, "completion_request": n,
                                "response_file": response_file, "status_code": status,
                                "usage": response.get("usage") if response else None})
        (self.requests / "http_ledger.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.ledger))

    def base_response(self, calls):
        return {"model": "qwen3-8b", "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": calls}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3}}

    def prepare_tool(self, *, later=True, matching_id=True, accepted=True, terminal=True):
        arguments = {"entity_names": ["module.py:target"]}
        call = {"id": "call_1", "type": "function", "function": {
            "name": "get_entity_contents", "arguments": json.dumps(arguments)}}
        self.write_attempt(1, [{"role": "user", "content": "issue"}], self.base_response([call]))
        event = {"sequence": 1, "code": "print(get_entity_contents(**{'entity_names':['module.py:target']}))",
                 "function": "get_entity_contents", "args": [], "kwargs": arguments, "status": "success", "output": "name only"}
        (self.sample / "tools.jsonl").write_text(json.dumps(event) + "\n")
        if later:
            message = {"role": "tool", "tool_call_id": "call_1" if matching_id else "wrong_id",
                       "name": "get_entity_contents", "content": "OBSERVATION:\nname only"}
            response = self.base_response([]) if accepted else {"error": "context overflow"}
            self.write_attempt(2, [message], response, status=200 if accepted else 400)
        if terminal:
            (self.sample / "result.json").write_text(json.dumps({"terminal": True, "status": "complete"}))
            (self.task / "result.json").write_text(json.dumps({"terminal": True, "status": "complete", "found_files": ["module.py"], "found_entities": []}))

    def test_id_arguments_execution_and_exact_text_delivery(self):
        self.prepare_tool()
        summary, tasks, calls = audit_run(self.run)
        self.assertEqual(summary["status"], "FINAL")
        self.assertEqual(summary["official_function_calls_entered"], 1)
        self.assertEqual(summary["return_text_received_by_model"], 1)
        self.assertTrue(calls[0]["return_text_received_by_model"])
        self.assertIsNone(calls[0]["full_function_source_verified"])
        self.assertEqual(summary["known_total_tokens"], 26)

    def test_wrong_call_id_never_counts_as_delivery(self):
        self.prepare_tool(matching_id=False)
        summary, _, calls = audit_run(self.run)
        self.assertEqual(summary["return_text_received_by_model"], 0)
        self.assertEqual(calls[0]["delivery_state"], "no_matching_return_text_despite_later_request")

    def test_rejected_request_is_not_model_receipt(self):
        self.prepare_tool(accepted=False)
        summary, _, calls = audit_run(self.run)
        self.assertTrue(calls[0]["return_text_in_later_request"])
        self.assertFalse(calls[0]["return_text_received_by_model"])
        self.assertEqual(calls[0]["delivery_state"], "return_text_in_rejected_or_unconfirmed_request_only")
        self.assertIsNone(summary["total_tokens"])
        self.assertEqual(summary["unknown_usage_attempts"], 1)

    def test_last_terminal_tool_has_no_later_request(self):
        self.prepare_tool(later=False)
        summary, _, calls = audit_run(self.run)
        self.assertEqual(calls[0]["delivery_state"], "last_tool_return_no_later_request")
        self.assertEqual(summary["return_text_received_by_model"], 0)

    def test_running_delivery_is_pending_not_final_loss(self):
        self.prepare_tool(later=False, terminal=False)
        summary, _, calls = audit_run(self.run)
        self.assertEqual(summary["status"], "RUNNING_SNAPSHOT")
        self.assertEqual(calls[0]["delivery_state"], "pending_or_unconfirmed_during_run")

    def test_unfinished_http_usage_is_not_zero(self):
        self.write_attempt(1, [], None, finished=False)
        summary, _, _ = audit_run(self.run)
        self.assertEqual(summary["unknown_usage_attempts"], 1)
        self.assertEqual(summary["unfinished_http_attempts"], 1)
        self.assertIsNone(summary["total_tokens"])
        self.assertEqual(summary["known_total_tokens"], 0)

    def test_zero_tool_fence_is_not_parseable_location(self):
        finish = {"id": "finish_1", "function": {"name": "finish", "arguments": json.dumps({"final_response": "```"})}}
        self.write_attempt(1, [], self.base_response([finish]))
        (self.sample / "result.json").write_text(json.dumps({"terminal": True, "status": "complete", "raw_location": "```"}))
        (self.task / "result.json").write_text(json.dumps({"terminal": True, "status": "complete", "found_files": [], "found_entities": []}))
        summary, _, _ = audit_run(self.run)
        self.assertEqual(summary["zero_tools_without_location"], 1)
        self.assertEqual(summary["zero_tools_with_location"], 0)

    def test_explicit_thinking_false_requires_boolean_false(self):
        self.write_attempt(1, [], self.base_response([]), thinking=None)
        summary, _, _ = audit_run(self.run)
        self.assertEqual(summary["requests_explicit_thinking_false"], 0)

    def test_call_validation_error_not_counted_as_entered_function(self):
        self.prepare_tool(later=False)
        event = {"sequence": 1, "code": "print(get_entity_contents(**{'entity_names':['module.py:target']}))",
                 "status": "tool_error", "output": "ToolError: bad arguments"}
        (self.sample / "tools.jsonl").write_text(json.dumps(event) + "\n")
        summary, _, calls = audit_run(self.run)
        self.assertTrue(calls[0]["dispatch_observed"])
        self.assertFalse(calls[0]["official_function_entered"])
        self.assertEqual(summary["pre_execution_validation_errors"], 1)

    def test_finish_normalization_does_not_change_task_or_retrieval(self):
        original = {"messages": [{"role": "user", "content": "issue"}], "tools": [
            {"function": {"name": "finish", "parameters": {"required": ["final_response"]}}},
            {"function": {"name": "get_entity_contents", "parameters": {"type": "object"}}}]}
        stripped = without_finish_parameters(original)
        self.assertNotIn("parameters", stripped["tools"][0]["function"])
        self.assertIn("parameters", original["tools"][0]["function"])
        self.assertEqual(stripped["messages"], original["messages"])
        self.assertEqual(stripped["tools"][1], original["tools"][1])

    def test_reused_call_id_does_not_certify_unique_delivery(self):
        self.prepare_tool(later=False)
        arguments = {"entity_names": ["module.py:target"]}
        repeated = {"id": "call_1", "function": {"name": "get_entity_contents", "arguments": json.dumps(arguments)}}
        self.write_attempt(2, [], self.base_response([repeated]))
        self.write_attempt(3, [{"role": "tool", "tool_call_id": "call_1", "name": "get_entity_contents",
                               "content": "OBSERVATION:\nname only"}], self.base_response([]))
        events = [json.loads(x) for x in (self.sample / "tools.jsonl").read_text().splitlines()]
        events.append({**events[0], "sequence": 2})
        (self.sample / "tools.jsonl").write_text("".join(json.dumps(x) + "\n" for x in events))
        summary, _, calls = audit_run(self.run)
        self.assertEqual(summary["successful_execution_events"], 2)
        self.assertEqual(summary["return_text_received_by_model"], 0)
        self.assertTrue(all(c["delivery_state"] == "ambiguous_or_missing_tool_call_id" for c in calls))


if __name__ == "__main__":
    unittest.main()
