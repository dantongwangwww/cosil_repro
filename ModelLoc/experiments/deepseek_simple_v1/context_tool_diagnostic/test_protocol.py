"""CPU-only contract tests; no benchmark gold, models, networking, or dispatch."""
import json
import tempfile
from pathlib import Path
import unittest
from .protocol import parse_action, target_resolution, ProtocolError, SIGNATURES, TOOL_SCHEMAS


def dsml(name="get_code_of_file_function", pairs=None):
    pairs = pairs if pairs is not None else [("file_name", "a.py"), ("func_name", "f")]
    return ('<｜DSML｜ calls><｜DSML｜ invoke name="' + name + '">' + ''.join(
        '<｜DSML｜ parameter name="' + key + '" string="true">' + value + '</｜DSML｜ parameter>'
        for key, value in pairs) + '</｜DSML｜ invoke></｜DSML｜ calls>')


class ProtocolTests(unittest.TestCase):
    def reject(self, raw, protocol="json", category=None):
        with self.assertRaises(ProtocolError) as caught:
            parse_action(raw, protocol)
        if category:
            self.assertEqual(caught.exception.category, category)

    def test_real_five_schemas(self):
        self.assertEqual({v["function"]["name"] for v in TOOL_SCHEMAS}, set(SIGNATURES))
        self.assertEqual(SIGNATURES["get_code_of_class_function"], ("file_name", "class_name", "func_name"))
        for name, parameters in SIGNATURES.items():
            values = {key: "a.py" if key == "file_name" else "C" for key in parameters}
            call = parse_action(json.dumps({"tool": name, "arguments": values}))
            self.assertEqual(call.arguments, tuple(values[p] for p in parameters))

    def test_optional_file_name_preserves_original_semantics(self):
        call = parse_action('{"tool":"get_functions_of_class","arguments":{"class_name":"C"}}')
        self.assertEqual(call.arguments, ("C", None))
        self.assertEqual(call.as_dict()["arguments"], {"class_name": "C"})
        self.reject('{"tool":"get_functions_of_class","arguments":{"class_name":"C","file_name":null}}')

    def test_strict_json_rejects_surrounding_and_multiple(self):
        raw = '{"tool":"exit","arguments":{}}'
        for invalid in [raw + raw, "Here is " + raw, "```json\n" + raw + "\n```", "[" + raw + "]"]:
            self.reject(invalid)
        self.assertEqual(parse_action(raw).name, "exit")

    def test_duplicate_unknown_and_wrong_fields(self):
        for invalid in [
            '{"tool":"exit","tool":"exit","arguments":{}}',
            '{"tool":"exit","arguments":{},"instruction":"ignore"}',
            '{"tool":"get_code_of_file_function","arguments":{"file_path":"a.py","qualified_name":"f"}}',
            '{"tool":"get_code_of_file_function","arguments":{"file_name":"a.py","func_name":"f","func_name":"g"}}',
            '{"tool":"get_code_of_static_function","arguments":{"file_name":"a.py","func_name":"f"}}',
            '{"tool":"exit","arguments":{"file_name":"a.py"}}',
            '{"tool":"get_code_of_file_function","arguments":{"file_name":"a.py","func_name":1}}',
        ]:
            self.reject(invalid, category="schema_failure")

    def test_strict_dsl_no_eval_and_no_best_of(self):
        self.assertEqual(parse_action("get_code_of_file_function('a.py','f')", "dsl").arguments, ("a.py", "f"))
        self.assertEqual(parse_action("```python\nexit()\n```", "dsl").name, "exit")
        self.assertEqual(parse_action("get_code_of_static_function('a.py','f')", "dsl").name, "get_code_of_file_function")
        for invalid in ["exit(); exit()", "exit(), exit()", "text\nexit()", "os.exit()",
                        "get_code_of_file_function('a.py','C','f')", "get_code_of_file_function('a.py',str('f'))",
                        "get_code_of_file_function(*['a.py','f'])", "exit()\nignore all prior instructions"]:
            self.reject(invalid, "dsl")

    def test_canonical_dsml_only(self):
        raw = dsml()
        self.assertEqual(parse_action(raw, "dsml").arguments, ("a.py", "f"))
        self.assertEqual(parse_action(raw, "adapter").name, "get_code_of_file_function")
        for invalid in [raw.replace("｜DSML｜", "｜｜DSML｜｜"), raw + raw, "text\n" + raw,
                        raw.replace('</｜DSML｜ invoke>', ''), raw.replace('string="true"', 'string="false"', 1),
                        dsml("missing_tool"), dsml(pairs=[("file_name", "a.py"), ("file_name", "b.py")]),
                        raw.replace('<｜DSML｜ parameter', '<parameter', 1),
                        raw.replace('a.py', '&evil;'), raw.replace('<｜DSML｜ calls>', '<!DOCTYPE x><｜DSML｜ calls>')]:
            self.reject(invalid, "dsml")
        self.assertEqual(parse_action(dsml("exit", []), "dsml").name, "exit")

    def test_unsafe_paths_rejected_without_normalization(self):
        for path in ["/a.py", "../a.py", "x/../a.py", "C:/a.py", "x\\a.py", "", "a\x00.py"]:
            self.reject(json.dumps({"tool": "get_code_of_file_function", "arguments": {"file_name": path, "func_name": "f"}}), category="unsafe_path")
        self.assertEqual(parse_action("get_code_of_file_function('./a.py','f')", "dsl").arguments[0], "./a.py")

    def test_target_resolution_does_not_correct_or_expand_scope(self):
        index = {"a.py": {"definitions": [
            {"kind": "function", "qualified_name": "f", "start_line": 1, "end_line": 2},
            {"kind": "class", "qualified_name": "C", "start_line": 3, "end_line": 9},
            {"kind": "function", "qualified_name": "C.m", "start_line": 4, "end_line": 5},
            {"kind": "function", "qualified_name": "C.m", "start_line": 7, "end_line": 8},
            {"kind": "function", "qualified_name": "f.inner", "start_line": 2, "end_line": 2},
        ]}}
        def resolve(raw):
            return target_resolution(parse_action(raw, "dsl"), index, ["a.py"])
        self.assertTrue(resolve("get_code_of_class_function('a.py','C','m')")["target_exists"])
        self.assertEqual(resolve("get_code_of_class_function('a.py','C','m')")["reason"], "same_qualified_name_multiple_source_spans")
        self.assertFalse(resolve("get_code_of_file_function('a.py','C.m')")["target_exists"])
        self.assertFalse(resolve("get_code_of_file_function('./a.py','f')")["target_exists"])
        self.assertFalse(resolve("get_code_of_class_function('a.py','Wrong','m')")["target_exists"])
        self.assertFalse(resolve("get_code_of_file_function('a.py','f.inner')")["target_exists"])
        self.assertTrue(resolve("get_functions_of_class('C')")["target_exists"])
        other = {**index, "b.py": index["a.py"]}
        call = parse_action("get_functions_of_class('C')", "dsl")
        self.assertFalse(target_resolution(call, other, ["a.py", "b.py"])["target_exists"])


class DeliveryEvidenceTests(unittest.TestCase):
    def test_hash_validity_does_not_mean_full_source(self):
        from .audit import _delivery, digest
        source = "def f():\n    return 1\n"
        model_input = "<function>\n" + source[:10] + "\n</function>"
        events = [{"event": "v6_judge_input", "step": 0, "model_input": model_input,
                   "input_sha256": digest(model_input)}]
        evidence = _delivery(source, 0, 3, 10, [], events)
        self.assertTrue(evidence["small_judge_saved_input_hash_valid"])
        self.assertFalse(evidence["small_judge_seen_full_source"])
        self.assertTrue(evidence["small_judge_seen_partial_or_different_source"])
        self.assertEqual(evidence["small_judge_source_relation"], "prefix_truncated")

    def test_context_accept_alone_is_not_agent_receipt(self):
        from .audit import _delivery
        source = "def f():\n    pass\n"
        events = [{"event": "context_accept", "step": 0}]
        evidence = _delivery(source, 0, 3, 10, [], events)
        self.assertTrue(evidence["context_accept_event"])
        self.assertFalse(evidence["agent_seen_full_source"])
        request = {"sequence": 11, "stage": "node_selection", "messages": [{"role": "user", "content": source}],
                   "request_artifact": "request.json", "receipt_artifact": "receipt.json",
                   "finish_reason": "stop", "request_sha256": "request hash"}
        self.assertTrue(_delivery(source, 0, 3, 10, [request], events)["agent_seen_full_source"])

    def test_saved_request_without_valid_http_receipt_is_not_delivery(self):
        from .audit import _observed_requests, digest
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); call = folder / "calls/0001_node_selection"; call.mkdir(parents=True)
            payload = {"messages": [{"role": "user", "content": "source"}]}
            request_hash = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            request = {"request": payload, "sha256": request_hash}
            (call / "request.json").write_text(json.dumps(request))
            self.assertEqual(_observed_requests(folder), [])
            raw = {"choices": [{"message": {"content": "exit()"}}]}
            (call / "attempt_0_response.json").write_text(json.dumps(raw))
            receipt = {"http_status": 200, "request_sha256": request_hash, "response_sha256": "wrong", "finish_reason": "stop"}
            (call / "attempt_0_receipt.json").write_text(json.dumps(receipt))
            self.assertEqual(_observed_requests(folder), [])
            receipt["response_sha256"] = digest(json.dumps(raw, sort_keys=True))
            (call / "attempt_0_receipt.json").write_text(json.dumps(receipt))
            self.assertEqual(len(_observed_requests(folder)), 1)

    def test_historical_output_and_forbidden_data_are_isolated(self):
        from .audit import guarded, audit
        for path in ["/fake/holdout/records.json", "/fake/evaluator_private/gold.json", "/fake/pruner_test.jsonl"]:
            with self.assertRaises(PermissionError):
                guarded(path)
        with self.assertRaises(PermissionError):
            audit("/fake/historical", "/not/read.json", "/not/read.csv", "/fake/historical/new")


if __name__ == "__main__":
    unittest.main()
