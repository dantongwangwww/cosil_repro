"""No-gold synthetic tests for the offline serialization-only diagnostic."""
import hashlib
import json
from pathlib import Path
import pickle
import tempfile
import unittest

import networkx as nx
import util.process_output as official
from dependency_graph import RepoEntitySearcher
from reproduction.postprocess_compat import build_views, canonical_prediction, merge_samples, normalize_sample


class PostprocessCompatTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name)
        self.old_graph_dir = official.GRAPH_INDEX_DIR
        self.graph = nx.MultiDiGraph()
        code = "class C:\n    def method(self):\n        return 1\ndef root():\n    return 2\ndef outer():\n    def inner():\n        def deep():\n            return 1\n        return deep\n    return inner\n"
        for name, text in [("pkg/a.py", code), ("root.py", "def target():\n    return 1\n")]:
            self.graph.add_node(name, name=name, type="file", code=text, start_line=1, end_line=len(text.splitlines()))
        for file, qualified, kind in [
            ("pkg/a.py", "C", "class"), ("pkg/a.py", "C.method", "function"),
            ("pkg/a.py", "root", "function"), ("pkg/a.py", "outer", "function"),
            ("pkg/a.py", "outer.inner", "function"), ("pkg/a.py", "outer.inner.deep", "function"),
            ("root.py", "target", "function"),
        ]:
            identity = f"{file}:{qualified}"
            self.graph.add_node(identity, name=identity, type=kind, code="def target():\n    return 1", start_line=1, end_line=2)
            self.graph.add_edge(file, identity, type="contains")
        self.searcher = RepoEntitySearcher(self.graph)
        self.source = {"instance_id": "owner__repo-1", "sample": 1, "source_responses": ["synthetic_response.json"]}
        (self.path / "owner__repo-1.pkl").write_bytes(pickle.dumps(self.graph))
        official.GRAPH_INDEX_DIR = str(self.path)

    def tearDown(self):
        official.GRAPH_INDEX_DIR = self.old_graph_dir
        self.temporary.cleanup()

    def normalize(self, raw):
        return normalize_sample(raw, self.searcher, official, self.source)

    def native(self, raw):
        samples = official.get_loc_results_from_raw_outputs("owner__repo-1", [raw])
        return dict(zip(("found_files", "found_modules", "found_entities"), official.merge_sample_locations(*samples, ranking_method="mrr")))

    def test_compliant_output_is_native_identical(self):
        raw = "```\npkg/a.py\nfunction: C.method\nfunction: root\n```"
        result = self.normalize(raw)
        self.assertEqual(result["rendered"], raw)
        self.assertFalse(result["changes"])
        self.assertEqual(merge_samples([result], official), self.native(raw))

    def test_existing_top_level_file_and_explicit_function(self):
        raw = "root.py\nfunction: target"
        self.assertEqual(self.native(raw)["found_entities"], [])
        result = self.normalize(raw)
        self.assertEqual(result["found_files"], ["root.py"])
        self.assertEqual(result["found_entities"], ["root.py:target"])
        self.assertTrue(all(change["graph_identity"] == "root.py" for change in result["changes"]))

    def test_both_single_line_separators_preserve_exact_identity(self):
        for separator in (":", "::"):
            result = self.normalize(f"pkg/a.py{separator}C.method")
            self.assertEqual(result["found_entities"], ["pkg/a.py:C.method"])
            self.assertEqual(result["changes"][0]["new_lines"], ["pkg/a.py", "function: C.method"])

    def test_unknown_or_misspelled_entity_is_not_corrected(self):
        for raw in ("pkg/a.py:C.methdo", "pkg/a.py::target", "missing.py:root", "./pkg/a.py:root"):
            result = self.normalize(raw)
            self.assertEqual(result["rendered"], raw)
            self.assertFalse(result["changes"])
            self.assertEqual(result["found_entities"], [])

    def test_class_is_not_expanded_to_its_methods(self):
        result = self.normalize("pkg/a.py:C")
        self.assertEqual(result["found_files"], ["pkg/a.py"])
        self.assertEqual(result["found_entities"], [])

    def test_refuse_new_conversion_that_would_truncate_qualified_identity(self):
        result = self.normalize("pkg/a.py:outer.inner.deep")
        self.assertEqual(result["found_entities"], [])
        self.assertFalse(result["changes"][0]["applied"])
        self.assertIn("cannot preserve exact", result["changes"][0]["reason"])

    def test_already_compliant_nested_identity_keeps_native_behavior(self):
        raw = "pkg/a.py\nfunction: outer.inner.deep"
        result = self.normalize(raw)
        self.assertEqual(merge_samples([result], official), self.native(raw))

    def test_existing_class_in_function_directive_keeps_native_module_only(self):
        raw = "pkg/a.py\nfunction: C"
        result = self.normalize(raw)
        self.assertEqual(result["found_entities"], [])
        self.assertEqual(merge_samples([result], official), self.native(raw))
        self.assertEqual(result["found_modules"], ["pkg/a.py:C"])

    def test_line_only_target_does_not_add_new_function(self):
        result = self.normalize("root.py\nline: 1")
        self.assertEqual(result["found_files"], ["root.py"])
        self.assertEqual(result["found_entities"], [])
        self.assertEqual(result["new_line_only_directives_suppressed"], ["root.py:line: 1"])

    def test_model_order_is_preserved_before_unchanged_mrr(self):
        result = self.normalize("root.py:target\npkg/a.py::C.method")
        self.assertEqual(result["found_files"], ["root.py", "pkg/a.py"])
        self.assertEqual(result["found_entities"], ["root.py:target", "pkg/a.py:C.method"])

    def test_views_never_modify_original_result_or_read_gold(self):
        run = self.path / "run"
        (run / "selection").mkdir(parents=True)
        (run / "selection/manifest.json").write_text(json.dumps({"records": [
            {"instance_id": "owner__repo-1", "base_commit": "abc"},
            {"instance_id": "owner__repo-2", "base_commit": "def"},
        ]}))
        graph_dir = run / "public/graph_index"
        graph_dir.mkdir(parents=True)
        graph = graph_dir / "owner__repo-1.pkl"
        graph.write_bytes(pickle.dumps(self.graph))
        graph.with_suffix(".receipt.json").write_text(json.dumps({"status": "success", "graph_ready": True,
            "instance_id": "owner__repo-1", "base_commit": "abc", "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest()}))
        raw = "root.py::target"
        result = {"instance_id": "owner__repo-1", "repo": "owner/repo", "base_commit": "abc", "terminal": True,
            "status": "complete", "raw_output_loc": [raw], "samples": [{"sample": 1, "raw_location": raw}],
            **self.native(raw)}
        task = run / "outputs/owner__repo-1"
        requests = task / "samples/sample_01/requests"
        requests.mkdir(parents=True)
        (requests / "request_001_attempt_1_response.txt").write_text(json.dumps({"choices": [{"message": {
            "tool_calls": [{"function": {"name": "finish", "arguments": json.dumps({"final_response": raw})}}]}}]}))
        source = task / "result.json"
        source.write_text(json.dumps(result))
        original = source.read_bytes()
        (run / "private").mkdir()
        (run / "private/gold.json").write_text("DO NOT READ")
        output = run / "audits/postprocess_compat"
        summary = build_views(run, output)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(summary["status"], "RUNNING_SNAPSHOT")
        self.assertEqual(summary["terminal_tasks"], 1)
        self.assertEqual(summary["changed_tasks"], 1)
        self.assertEqual(summary["new_model_calls"], 0)
        self.assertFalse(summary["gold_read"])
        self.assertTrue(all("/private/" not in path for path in summary["source_files_sha256"]))
        compatible = json.loads((output / "compatible/outputs/owner__repo-1/result.json").read_text())
        self.assertEqual(compatible["found_entities"], ["root.py:target"])
        native = json.loads((output / "native/outputs/owner__repo-1/result.json").read_text())
        self.assertEqual(canonical_prediction(native), canonical_prediction(result))


if __name__ == "__main__":
    unittest.main()
