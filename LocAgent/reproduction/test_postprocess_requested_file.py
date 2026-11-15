"""No-gold counterexamples for the third offline requested-file view."""
import copy
import hashlib
import json
from pathlib import Path
import pickle
import tempfile
import unittest

import networkx as nx
import util.process_output as official
from dependency_graph import RepoEntitySearcher
from reproduction.postprocess_compat import merge_samples, normalize_sample
from reproduction.postprocess_requested_file import build_view, line_scope_adapter


class RequestedFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.graph = nx.MultiDiGraph()
        for file in ("pkg/a.py", "pkg/b.py", "pkg/a.py_extra.py", "root.py"):
            self.graph.add_node(file, name=file, type="file", code="# synthetic fixture\n" * 100,
                                start_line=1, end_line=100)
        self.add_function("pkg/a.py:f", 10, 30)
        self.add_function("pkg/b.py:g", 14, 16)
        self.add_function("root.py:target", 1, 3)
        self.source = {"instance_id": "owner__repo-1", "sample": 1, "source_responses": ["synthetic_response.json"]}

    def tearDown(self):
        self.temp.cleanup()

    def add_function(self, identity, start, end):
        self.graph.add_node(identity, name=identity, type="function", code="def fixture(): pass",
                            start_line=start, end_line=end)
        self.graph.add_edge(identity.partition(":")[0], identity, type="contains")

    def searcher(self):
        return RepoEntitySearcher(copy.deepcopy(self.graph))

    def test_foreign_narrower_range_is_not_the_requested_file(self):
        native, _ = official.get_module_from_line_number(15, "pkg/a.py", self.searcher())
        scoped, _ = line_scope_adapter(official)
        correct, _ = scoped.get_module_from_line_number(15, "pkg/a.py", self.searcher())
        self.assertEqual(native["name"], "pkg/b.py:g")
        self.assertEqual(correct["name"], "pkg/a.py:f")

    def test_file_prefix_collision_is_rejected(self):
        self.add_function("pkg/a.py_extra.py:h", 15, 15)
        scoped, _ = line_scope_adapter(official)
        node, _ = scoped.get_module_from_line_number(15, "pkg/a.py", self.searcher())
        self.assertEqual(node["name"], "pkg/a.py:f")

    def test_same_file_nested_range_behavior_is_preserved(self):
        self.add_function("pkg/a.py:f.inner", 14, 16)
        self.add_function("pkg/b.py:foreign", 15, 15)
        scoped, _ = line_scope_adapter(official)
        node, _ = scoped.get_module_from_line_number(15, "pkg/a.py", self.searcher())
        self.assertEqual(node["name"], "pkg/a.py:f.inner")

    def test_no_requested_file_function_does_not_invent_one(self):
        scoped, _ = line_scope_adapter(official)
        node, end = scoped.get_module_from_line_number(15, "root.py", self.searcher())
        self.assertIsNone(node)
        self.assertIsNone(end)

    def test_direct_names_unchanged_and_top_level_line_suppression_inherited(self):
        scoped, _ = line_scope_adapter(official)
        for raw in ("pkg/a.py\nfunction: f", "root.py\nline: 2"):
            normal = normalize_sample(raw, self.searcher(), official, self.source)
            strict = normalize_sample(raw, self.searcher(), scoped, self.source)
            self.assertEqual(merge_samples([normal], official), merge_samples([strict], scoped))

    def test_remerge_retains_explicit_foreign_candidate_instead_of_masking(self):
        scoped, _ = line_scope_adapter(official)
        raw1 = "pkg/a.py\nline: 15\npkg/b.py\nfunction: g"
        raw2 = "pkg/b.py\nfunction: g"
        normal = [normalize_sample(raw, self.searcher(), official, self.source) for raw in (raw1, raw2)]
        strict = [normalize_sample(raw, self.searcher(), scoped, self.source) for raw in (raw1, raw2)]
        self.assertEqual(merge_samples(normal, official)["found_entities"], ["pkg/b.py:g"])
        # B is still explicitly requested elsewhere; it retains its legitimate
        # MRR contribution and remains ahead of A. A final-rank mask cannot do this.
        self.assertEqual(merge_samples(strict, scoped)["found_entities"], ["pkg/b.py:g", "pkg/a.py:f"])

    def test_patch_contains_only_exact_file_guard_and_preserves_original_function(self):
        before = official.get_module_from_line_number
        scoped, sources = line_scope_adapter(official)
        self.assertIs(official.get_module_from_line_number, before)
        self.assertIn('nid.partition(":")[0] != file_path', sources["patched_source"])
        addition = '        if ":" not in nid or nid.partition(":")[0] != file_path:\n            continue\n'
        self.assertEqual(sources["patched_source"].replace(addition, "", 1), sources["original_source"])

    def test_actual_view_has_frozen_rule_and_does_not_touch_old_views_or_gold(self):
        run = self.path / "run"
        (run / "selection").mkdir(parents=True)
        (run / "selection/manifest.json").write_text(json.dumps({"records": [
            {"instance_id": "owner__repo-1", "base_commit": "abc"}]}))
        graph_dir = run / "public/graph_index"
        graph_dir.mkdir(parents=True)
        graph = graph_dir / "owner__repo-1.pkl"
        graph.write_bytes(pickle.dumps(self.graph))
        graph.with_suffix(".receipt.json").write_text(json.dumps({"status": "success", "graph_ready": True,
            "instance_id": "owner__repo-1", "base_commit": "abc", "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest()}))
        raw = "pkg/a.py\nline: 15"
        native = merge_samples([normalize_sample(raw, self.searcher(), official, self.source)], official)
        result = {"instance_id": "owner__repo-1", "repo": "owner/repo", "base_commit": "abc", "terminal": True,
            "status": "complete", "raw_output_loc": [raw], "samples": [{"sample": 1, "raw_location": raw}], **native}
        task = run / "outputs/owner__repo-1"
        requests = task / "samples/sample_01/requests"
        requests.mkdir(parents=True)
        (requests / "request_001_attempt_1_response.txt").write_text(json.dumps({"choices": [{"message": {
            "tool_calls": [{"function": {"name": "finish", "arguments": json.dumps({"final_response": raw})}}]}}]}))
        source = task / "result.json"
        source.write_text(json.dumps(result))
        old = run / "audits/postprocess_compat/compatible/outputs/owner__repo-1/result.json"
        old.parent.mkdir(parents=True)
        old.write_text(json.dumps(result))
        before_source, before_old = source.read_bytes(), old.read_bytes()
        (run / "private").mkdir()
        (run / "private/gold.json").write_text("DO NOT READ")
        output = run / "audits/postprocess_requested_file"
        summary = build_view(run, output)
        self.assertEqual(summary["status"], "FINAL")
        self.assertFalse(summary["diagnostic_errors"])
        self.assertEqual(summary["changed_vs_compatible"], 1)
        self.assertEqual(source.read_bytes(), before_source)
        self.assertEqual(old.read_bytes(), before_old)
        self.assertTrue(all("/private/" not in path for path in summary["source_files_sha256"]))
        self.assertTrue((output / "line_scope.patch").is_file())
        value = json.loads((output / "outputs/owner__repo-1/result.json").read_text())
        self.assertEqual(value["found_entities"], ["pkg/a.py:f"])
        self.assertTrue(value["not_a_complete_parser_or_ast_repair"])
        self.assertEqual(value["new_model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
