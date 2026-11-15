"""CPU-only checks for the LocAgent runtime boundaries (no model calls)."""
import ast
import hashlib
import io
import json
from pathlib import Path
from queue import Queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from reproduction.worker import (
    ALLOWED_TOOLS, CompletionAdapter, RunStop, SafeToolDispatcher,
    aggregate_usage, check_local_endpoint, load_public_instance, load_upstream_search,
)
from reproduction.runner import build_command


def tools():
    return [{"type": "function", "function": {"name": name}} for name in sorted(ALLOWED_TOOLS | {"finish"})]


class Response:
    status = 200
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def read(self):
        return json.dumps(self.value).encode()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name)
    def tearDown(self):
        self.temporary.cleanup()

    def adapter(self, opener, **kwargs):
        return CompletionAdapter(self.path / "http", opener=opener,
                                 response_factory=lambda **value: value, **kwargs)

    def complete(self, adapter):
        return adapter(model="openai/locagent-native", messages=[{"role": "user", "content": "issue"}], tools=tools())

    def test_loopback_endpoint_only(self):
        self.assertEqual(check_local_endpoint("http://127.0.0.1:7353/v1"), "http://127.0.0.1:7353/v1/chat/completions")
        for url in ("https://api.openai.com/v1", "http://evil.test:7353/v1", "http://key:secret@localhost:7353/v1",
                    "http://localhost/v1", "file:///tmp/input", "http://localhost:7353/v1?key=secret"):
            with self.assertRaises(ValueError, msg=url):
                check_local_endpoint(url)

    def test_public_instance_rejects_answer_fields(self):
        p = self.path / "instance.json"
        public = dict(instance_id="a__b-1", repo="a/b", base_commit="abc", problem_statement="issue")
        p.write_text(json.dumps(public))
        self.assertEqual(load_public_instance(p), public)
        p.write_text(json.dumps({**public, "patch": "SECRET"}))
        with self.assertRaises(ValueError):
            load_public_instance(p)

    def test_request_forces_nonthinking_and_frozen_sampling(self):
        recorded = []
        def opener(request, timeout):
            recorded.append((request, timeout))
            return Response({"usage": {"prompt_tokens": 10, "completion_tokens": 4}, "choices": []})
        adapter = self.adapter(opener)
        self.complete(adapter)
        request = json.loads(recorded[0][0].data)
        self.assertEqual(request["model"], "qwen3-8b")
        self.assertEqual(request["max_completion_tokens"], 2048)
        self.assertEqual(request["temperature"], 1.0)
        self.assertEqual(request["top_p"], 0.8)
        self.assertEqual(request["repetition_penalty"], 1.05)
        self.assertEqual(request["chat_template_kwargs"], {"enable_thinking": False})
        self.assertFalse(request["parallel_tool_calls"])
        self.assertNotIn("Authorization", dict(recorded[0][0].header_items()))
        self.assertEqual(adapter.usage()["total_tokens"], 14)

    def test_usage_is_recorded_before_response_validation(self):
        def bad_factory(**_):
            raise ValueError("bad model output")
        adapter = self.adapter(lambda *a, **k: Response({"usage": {"prompt_tokens": 12, "completion_tokens": 5}}))
        adapter.response_factory = bad_factory
        with self.assertRaises(RunStop) as raised:
            self.complete(adapter)
        self.assertEqual(raised.exception.status, "parse_error")
        self.assertEqual(adapter.usage()["total_tokens"], 17)
        ledger = [json.loads(x) for x in (adapter.output / "http_ledger.jsonl").read_text().splitlines()]
        self.assertEqual(ledger[-1]["usage"]["completion_tokens"], 5)
        self.assertTrue((adapter.output / "request_001_attempt_1_response.txt").exists())

    def test_missing_usage_is_unknown_not_zero(self):
        adapter = self.adapter(lambda *a, **k: Response({"choices": []}))
        self.complete(adapter)
        self.assertIsNone(adapter.usage()["total_tokens"])
        self.assertEqual(adapter.usage()["unknown_usage_requests"], 1)
        self.assertEqual(adapter.usage()["known_total_tokens"], 0)

    def test_only_one_transport_retry_and_unknown_attempt_preserved(self):
        attempts = []
        def opener(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise URLError("temporary transport failure")
            return Response({"usage": {"prompt_tokens": 6, "completion_tokens": 2}})
        adapter = self.adapter(opener)
        self.complete(adapter)
        self.assertEqual(len(attempts), 2)
        usage = adapter.usage()
        self.assertEqual(usage["known_total_tokens"], 8)
        self.assertIsNone(usage["total_tokens"])
        self.assertEqual(usage["http_attempts"], 2)

    def test_two_transport_errors_stop(self):
        count = []
        def opener(*args, **kwargs):
            count.append(1)
            raise URLError("offline")
        adapter = self.adapter(opener)
        with self.assertRaises(RunStop) as raised:
            self.complete(adapter)
        self.assertEqual(raised.exception.status, "transport_error")
        self.assertEqual(len(count), 2)

    def test_deadline_during_http_keeps_unknown_usage(self):
        def opener(*args, **kwargs):
            raise RunStop("timeout", "sample timer expired")
        adapter = self.adapter(opener)
        with self.assertRaises(RunStop) as raised:
            self.complete(adapter)
        self.assertEqual(raised.exception.status, "timeout")
        self.assertEqual(adapter.usage()["unknown_usage_requests"], 1)
        self.assertIsNone(adapter.usage()["total_tokens"])
        ledger = [json.loads(x) for x in (adapter.output / "http_ledger.jsonl").read_text().splitlines()]
        self.assertEqual(ledger[-1]["event"], "finished")
        self.assertFalse(ledger[-1]["usage_known"])

    def test_http_errors_are_not_retried(self):
        count = []
        def opener(*args, **kwargs):
            count.append(1)
            raise HTTPError("http://localhost:7353", 500, "error", {}, io.BytesIO(b'{"error":"server failure"}'))
        adapter = self.adapter(opener)
        with self.assertRaises(RunStop) as raised:
            self.complete(adapter)
        self.assertEqual(raised.exception.status, "api_error")
        self.assertEqual(len(count), 1)

    def test_context_overflow_is_explicit_and_not_truncated(self):
        def opener(*args, **kwargs):
            raise HTTPError("http://localhost:7353", 400, "error", {}, io.BytesIO(b'{"error":"maximum context exceeded"}'))
        adapter = self.adapter(opener)
        with self.assertRaises(RunStop) as raised:
            self.complete(adapter)
        self.assertEqual(raised.exception.status, "context_limit")

    def test_hard_request_cap(self):
        adapter = self.adapter(lambda *a, **k: Response({"usage": {"prompt_tokens": 1, "completion_tokens": 1}}), request_limit=1)
        self.complete(adapter)
        with self.assertRaises(RunStop) as raised:
            self.complete(adapter)
        self.assertEqual(raised.exception.status, "step_limit")
        self.assertEqual(adapter.http_attempts, 1)

    def dispatcher(self):
        def tool(query=None):
            return f"source:{query}"
        return SafeToolDispatcher({name: tool for name in ALLOWED_TOOLS}, self.path / "tools.jsonl")

    def test_dispatch_accepts_official_print_call(self):
        dispatcher = self.dispatcher()
        result = dispatcher("print(search_code_snippets(**{'query': 'keyword'}))")
        self.assertEqual(ast.literal_eval(result), "source:keyword")

    def test_dispatch_rejects_arbitrary_code_and_injection(self):
        dispatcher = self.dispatcher()
        payloads = [
            "__import__('os').system('true')",
            "print(open('/etc/passwd').read())",
            "print(search_code_snippets(**{'query': __import__('os').getcwd()}))",
            "print(search_code_snippets()); print(search_code_snippets())",
            "print(search_code_snippets(**{'query': 'a'}, query='b'))",
            "[print(search_code_snippets()) for x in range(2)]",
        ]
        for payload in payloads:
            self.assertTrue(ast.literal_eval(dispatcher(payload)).startswith("ToolError:"), payload)
        logs = [json.loads(x) for x in (self.path / "tools.jsonl").read_text().splitlines()]
        self.assertTrue(all(event["status"] == "tool_error" for event in logs))

    def test_dispatch_string_cannot_be_evaluated_as_code(self):
        payload = "__import__('os').system('false')"
        dispatcher = SafeToolDispatcher({name: (lambda: payload) for name in ALLOWED_TOOLS}, self.path / "tools.jsonl")
        encoded = dispatcher("print(get_entity_contents())")
        self.assertEqual(ast.literal_eval(encoded), payload)

    def test_only_original_functions_are_loaded(self):
        source = self.path / "official.py"
        source.write_text("raise RuntimeError('unused CLI imports must not run')\n"
                          "def get_task_instruction(x):\n    return x\n"
                          "def auto_search_process(x):\n    return x + 1\n")
        instruction, search, hashes = load_upstream_search(source, {})
        self.assertEqual(instruction(3), 3)
        self.assertEqual(search(3), 4)
        self.assertEqual(set(hashes), {"get_task_instruction", "auto_search_process"})

    def test_original_official_search_function_executes_with_native_finish(self):
        source = Path(__file__).resolve().parents[1] / "auto_search_main.py"
        action_type = SimpleNamespace(FINISH="finish", MESSAGE="message", RUN_IPYTHON="python")
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="file.py\nfunction: target"))],
                                   usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3))
        class Parser:
            def parse(self, value):
                return SimpleNamespace(action_type="finish", thought=value.choices[0].message.content)
        namespace = dict(logging=SimpleNamespace(info=lambda *a: None, debug=lambda *a: None),
                         List=list, deepcopy=lambda x: x, ResponseParser=Parser, ActionType=action_type,
                         litellm=SimpleNamespace(completion=lambda **k: response, BadRequestError=ValueError),
                         convert_to_json=lambda value: {"content": value.content})
        _, search, _ = load_upstream_search(source, namespace)
        queue = Queue()
        search(queue, model_name="openai/locagent-native", messages=[], fake_user_msg="continue", tools=tools())
        raw, messages, trajectory = queue.get_nowait()
        self.assertIn("function: target", raw)
        self.assertEqual(trajectory["usage"]["prompt_tokens"], 7)

    def test_aggregate_unknown_usage_preserves_lower_bound(self):
        adapter = self.adapter(lambda *a, **k: Response({"usage": {"prompt_tokens": 6, "completion_tokens": 2}}))
        self.complete(adapter)
        good = adapter.usage()
        unknown = {**good, "unknown_usage_requests": 1, "prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
        usage = aggregate_usage([{"usage": good}, {"usage": unknown}])
        self.assertIsNone(usage["total_tokens"])
        self.assertEqual(usage["known_total_tokens"], 16)

    def runner_fixture(self):
        root = self.path / "source"
        venv = self.path / "venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
        instance = self.path / "instance.json"
        instance.write_text(json.dumps({"instance_id": "a__b-1", "base_commit": "abc"}))
        graph = self.path / "a__b-1.pkl"
        graph.write_bytes(b"test graph digest")
        graph.with_suffix(".receipt.json").write_text(json.dumps({
            "instance_id": "a__b-1", "base_commit": "abc", "status": "success", "graph_ready": True,
            "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
        }))
        snapshot = self.path / "snapshot"
        snapshot.mkdir()
        cache = self.path / "tokenizer-cache"
        cache.mkdir()
        return dict(source_root=root, venv=venv, instance=instance, graph=graph,
                    snapshot=snapshot, work=self.path / "work", tiktoken_cache=cache)

    def test_runner_mounts_code_whitelist_not_whole_repository(self):
        args = self.runner_fixture()
        with patch("reproduction.runner.shutil.which", return_value="/usr/bin/bwrap"):
            command = build_command(**args)
        ro_sources = [command[i + 1] for i, x in enumerate(command) if x == "--ro-bind"]
        self.assertNotIn(str(args["source_root"]), ro_sources)
        self.assertFalse(any("experiments" in path or "/.git" in path for path in ro_sources))
        self.assertIn("--clearenv", command)
        self.assertIn("/source", command)
        self.assertEqual(sum(path.endswith(".pkl") for path in ro_sources), 1)

    def test_runner_requires_success_receipt(self):
        args = self.runner_fixture()
        args["graph"].with_suffix(".receipt.json").unlink()
        with patch("reproduction.runner.shutil.which", return_value="/usr/bin/bwrap"):
            with self.assertRaises(FileNotFoundError):
                build_command(**args)

    def test_runner_rejects_changed_graph(self):
        args = self.runner_fixture()
        args["graph"].write_bytes(b"changed graph")
        with patch("reproduction.runner.shutil.which", return_value="/usr/bin/bwrap"):
            with self.assertRaises(ValueError):
                build_command(**args)


if __name__ == "__main__":
    unittest.main()
