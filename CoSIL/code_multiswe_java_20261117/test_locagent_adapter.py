"""CPU synthetic contract checks; no model, benchmark execution or gold read."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from code_multiswe_java_20261117.locagent_adapter import (
    build_locagent_graph, java_tools, merge_mrr, name_aliases, parse_sample, read_job,
)


def synthetic_index():
    text = "class C {\n C() {}\n void f(int n) {}\n void f(String n) {}\n class D {\n void g() {}\n }\n}\n"
    def definition(qn, line, owner, name):
        return {"kind": "function", "qualified_name": qn, "name": name,
                "canonical_id": "src/C.java::" + qn,
                "start_line": line, "end_line": line, "parent_qualified_name": owner}
    return {"src/C.java": {"content": text,
        "raw_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "classes": [{"kind": "class", "qualified_name": "C", "start_line": 1, "end_line": 8,
                     "parent_qualified_name": None},
                    {"kind": "class", "qualified_name": "C.D", "start_line": 5, "end_line": 7,
                     "parent_qualified_name": "C"}],
        "definitions": [definition("C.<init>()", 2, "C", "<init>"),
                        definition("C.f(int)", 3, "C", "f"),
                        definition("C.f(String)", 4, "C", "f"),
                        definition("C.D.g()", 6, "C.D", "g")]}}


class JavaLocAgentContracts(unittest.TestCase):
    def test_graph_preserves_overloads_constructor_nested_parent(self):
        graph = build_locagent_graph(synthetic_index(), {"edges": []})
        self.assertEqual(len([1 for _, d in graph.nodes(data=True) if d["type"] == "function"]), 4)
        self.assertIn("src/C.java:C.<init>()", graph)
        self.assertTrue(graph.has_edge("src/C.java", "src/C.java:C"))
        self.assertTrue(graph.has_edge("src/C.java:C.D", "src/C.java:C.D.g()"))
        self.assertFalse(graph.has_edge("src/C.java:C", "src/C.java:C.D.g()"))

    def test_dependencies_translate_only_separators(self):
        edge = {"source": "src/C.java::C.D.g()", "target": "src/C.java::C.f(int)", "type": "calls"}
        graph = build_locagent_graph(synthetic_index(), {"edges": [edge]})
        self.assertEqual(graph["src/C.java:C.D.g()"]["src/C.java:C.f(int)"][0]["type"], "invokes")

    def test_unknown_dependency_is_not_silently_added(self):
        with self.assertRaises(ValueError):
            build_locagent_graph(synthetic_index(), {"edges": [{"source": "missing", "target": "missing"}]})

    def test_exact_import_inheritance_and_interface_edges(self):
        from code_multiswe_java_20261117.java_index import parse_java
        sources = {"p/Base.java": b"package p; public class Base {}",
                   "q/I.java": b"package q; public interface I {}",
                   "q/C.java": b"package q; import p.Base; class C extends Base implements I {}"}
        index = {path: parse_java(path, raw) for path, raw in sources.items()}
        graph = build_locagent_graph(index)
        self.assertEqual(graph["q/C.java"]["p/Base.java:Base"][0]["type"], "imports")
        self.assertEqual(graph["q/C.java:C"]["p/Base.java:Base"][0]["type"], "inherits")
        self.assertEqual(graph["q/C.java:C"]["q/I.java:I"][0]["type"], "inherits")

    def test_wildcard_or_external_import_never_guesses_global_class(self):
        from code_multiswe_java_20261117.java_index import parse_java
        sources = {"p/Base.java": b"package p; public class Base {}",
                   "q/C.java": b"package q; import p.*; class C extends Base {}",
                   "q/Base.java": b"package q; class Base {}",
                   "q/D.java": b"package q; import external.Base; class D extends Base {}"}
        index = {path: parse_java(path, raw) for path, raw in sources.items()}
        graph = build_locagent_graph(index)
        self.assertFalse(graph.has_edge("q/C.java:C", "p/Base.java:Base"))
        self.assertTrue(graph.has_edge("q/C.java:C", "q/Base.java:Base"))
        self.assertFalse(graph.has_edge("q/D.java:D", "q/Base.java:Base"))
        self.assertTrue(graph.graph["dependency_audit"]["unresolved"])

    def test_duplicate_fqn_is_unresolved_and_nested_parent_is_exact(self):
        from code_multiswe_java_20261117.java_index import parse_java
        sources = {"module1/p/Base.java": b"package p; public class Base {}",
                   "module2/p/Base.java": b"package p; public class Base {}",
                   "q/C.java": b"package q; import p.Base; class C extends Base {}",
                   "q/O.java": b"package q; class O { class B{} class D extends B{} }"}
        index = {path: parse_java(path, raw) for path, raw in sources.items()}
        graph = build_locagent_graph(index)
        self.assertFalse(any(d["type"] == "inherits" for *_, d in graph.out_edges("q/C.java:C", data=True)))
        self.assertTrue(graph.has_edge("q/O.java:O.D", "q/O.java:O.B"))

    def test_lexical_class_shadows_package_name(self):
        from code_multiswe_java_20261117.java_index import parse_java
        sources = {"Outer/Base.java": b"package Outer; public class Base {}",
                   "p/C.java": b"package p; class Outer{} class C extends Outer.Base {}"}
        index = {path: parse_java(path, raw) for path, raw in sources.items()}
        graph = build_locagent_graph(index)
        self.assertFalse(graph.has_edge("p/C.java:C", "Outer/Base.java:Base"))

    def test_exact_signature_survives_directives(self):
        result = parse_sample("```\nsrc/C.java\nfunction: C.f(String)\nmethod: C.<init>()\n```", synthetic_index())
        self.assertEqual(result["functions"], ["src/C.java::C.f(String)", "src/C.java::C.<init>()"])

    def test_ambiguous_unqualified_method_does_not_expand_or_guess(self):
        result = parse_sample("src/C.java\nfunction: C.f", synthetic_index())
        self.assertEqual(result["functions"], [])
        self.assertEqual(result["resolution_audit"][0]["status"], "ambiguous")
        self.assertEqual(result["resolution_audit"][0]["candidate_count"], 2)

    def test_inline_identity_and_nested_class(self):
        result = parse_sample("src/C.java::C.D.g()", synthetic_index())
        self.assertEqual(result["files"], ["src/C.java"])
        self.assertEqual(result["functions"], ["src/C.java::C.D.g()"])

    def test_line_resolution_never_uses_another_file(self):
        index = synthetic_index()
        index["other/C.java"] = copy.deepcopy(index["src/C.java"])
        result = parse_sample("src/C.java\nline: 3", index)
        self.assertEqual(result["functions"], ["src/C.java::C.f(int)"])

    def test_line_mapping_finds_nested_method(self):
        result = parse_sample("src/C.java\nline: 6", synthetic_index())
        self.assertEqual(result["functions"], ["src/C.java::C.D.g()"])

    def test_named_java_paths_are_not_redacted(self):
        index = {"myrepo/src/C.java": synthetic_index()["src/C.java"]}
        result = parse_sample("myrepo/src/C.java\nfunction: C.f(int)", index)
        self.assertEqual(result["functions"], ["myrepo/src/C.java::C.f(int)"])

    def test_two_sample_mrr_matches_fixed_reciprocal_rank(self):
        result = merge_mrr([{"files": ["A", "B"]}, {"files": ["B", "C"]}], "files")
        self.assertEqual(result, ["B", "A", "C"])

    def test_tool_schema_changes_examples_only(self):
        original = [{"type": "function", "function": {"name": "search_code_snippets",
            "parameters": {"properties": {"file_path_or_pattern": {"type": "string", "default": "**/*.py"}}},
            "description": "Read Python src/C.py"}}]
        adapted = java_tools(original)
        self.assertEqual(adapted[0]["function"]["name"], original[0]["function"]["name"])
        self.assertEqual(adapted[0]["function"]["parameters"]["properties"]["file_path_or_pattern"]["default"], "**/*.java")
        self.assertIn("Python", original[0]["function"]["description"])

    def test_aliases_do_not_split_parameter_type_dots(self):
        aliases = name_aliases("src/C.java:C.f(java.lang.String)", {
            "type": "function", "qualified_name": "C.f(java.lang.String)", "name": "f"})
        self.assertIn("f", aliases)
        self.assertNotIn("String)", aliases)

    def test_public_job_rejects_patch_and_validates_base_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot = root / "base"
            (snapshot / "src").mkdir(parents=True)
            index = synthetic_index()
            (snapshot / "src/C.java").write_text(index["src/C.java"]["content"])
            (root / "index.json").write_text(json.dumps(index))
            job = {"instance_id": "x-1", "repo": "a/b", "base_commit": "abc", "problem_statement": "issue",
                   "snapshot": "base", "code_index": "index.json"}
            path = root / "job.json"
            path.write_text(json.dumps(job))
            self.assertEqual(read_job(path)[3], index)
            path.write_text(json.dumps({**job, "fix_patch": "secret"}))
            with self.assertRaises(ValueError):
                read_job(path)
            path.write_text(json.dumps(job))
            (snapshot / "src/C.java").write_text("drift")
            with self.assertRaises(ValueError):
                read_job(path)

    def test_shared_java_parser_graph_and_real_tools_cpu(self):
        from code_multiswe_java_20261117.java_index import parse_java
        from code_multiswe_java_20261117.locagent_adapter import load_worker, install_java_boundaries
        source_root = Path(__file__).resolve().parents[2] / "LocAgent"
        worker = load_worker(source_root)
        raw = b"class C {\n void f(int n) {}\n void f(String n) {}\n void g(){ f(1); }\n}\n"
        index = {"src/C.java": parse_java("src/C.java", raw)}
        graph = build_locagent_graph(index)
        self.assertTrue(graph.has_edge("src/C.java", "src/C.java:C"))
        # Same-arity overload call remains unresolved, rather than fan-out edges.
        self.assertFalse(any(d["type"] == "invokes" for *_, d in graph.edges(data=True)))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot = root / "base"
            snapshot.mkdir()
            functions = install_java_boundaries(worker, source_root,
                {"instance_id": "demo-1", "repo": "demo/repo", "base_commit": "abc", "problem_statement": "issue"},
                snapshot, index, graph, root)
            exact = functions["get_entity_contents"](["src/C.java:C.f(int)"])
            self.assertIn("2 |  void f(int n)", exact)
            line = functions["search_code_snippets"](line_nums=[3], file_path_or_pattern="src/C.java")
            self.assertIn("C.f(String)", line)
            tree = functions["explore_tree_structure"](start_entities=["/"], traversal_depth=3,
                                                       dependency_type_filter=["contains"])
            self.assertIn("src/C.java:C", tree)

    def test_native_upstream_search_two_samples_and_usage_without_network(self):
        import code_multiswe_java_20261117.locagent_adapter as module
        source_root = Path(__file__).resolve().parents[2] / "LocAgent"
        worker = module.load_worker(source_root)
        requests = []
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self):
                return json.dumps({"id": "cpu-fixture", "object": "chat.completion", "created": 0,
                    "model": "qwen3-8b", "choices": [{"index": 0, "finish_reason": "tool_calls",
                    "message": {"role": "assistant", "content": None, "tool_calls": [{
                    "id": "finish-fixture", "type": "function", "function": {"name": "finish",
                    "arguments": json.dumps({"final_response": "src/C.java\nfunction: C.f(int)"})}}]}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 24}}).encode()
        def opener(request, timeout):
            payload = json.loads(request.data)
            requests.append(payload)
            self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
            self.assertEqual(payload["max_completion_tokens"], 2048)
            self.assertEqual(payload["temperature"], 1)
            return Response()
        original_adapter = worker.CompletionAdapter
        worker.CompletionAdapter = lambda *args, **kwargs: original_adapter(*args, opener=opener, **kwargs)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot = root / "base"
            (snapshot / "src").mkdir(parents=True)
            index = synthetic_index()
            (snapshot / "src/C.java").write_text(index["src/C.java"]["content"])
            (root / "index.json").write_text(json.dumps(index))
            job = {"instance_id": "demo-1", "repo": "demo/repo", "base_commit": "abc", "problem_statement": "Issue fixture",
                   "snapshot": str(snapshot), "code_index": str(root / "index.json")}
            job_path = root / "job.json"
            job_path.write_text(json.dumps(job))
            args = SimpleNamespace(job=job_path, out=root / "out", model="qwen3-8b", sample_timeout=20,
                                   main_api_base="http://127.0.0.1:7343/v1", locagent_source_root=source_root)
            with patch.object(module, "load_worker", return_value=worker), patch.dict(os.environ, {"MULTISWE_JAVA_SANDBOXED": "1"}):
                result = module.run_task(args)
            self.assertEqual(result["status"], "complete", result.get("error"))
            self.assertEqual(len(requests), 2)
            self.assertEqual(result["usage"]["total_tokens"], 48)
            self.assertEqual(result["ranked_functions"][0]["canonical_id"], "src/C.java::C.f(int)")
            self.assertEqual(len(result["samples"]), 2)
            self.assertTrue((args.out / "samples/sample_01/requests/request_001_attempt_1_request.json").is_file())
            self.assertTrue((args.out / "samples/sample_02/final_messages.json").is_file())
            with patch.dict(os.environ, {"MULTISWE_JAVA_SANDBOXED": "1"}), self.assertRaises(FileExistsError):
                module.run_task(args)


if __name__ == "__main__":
    unittest.main()
