"""Mechanism-audit tests; no model or network requests, no production writes."""
import hashlib
import json
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest import mock

from reproduction import audit_failures as a


class FailureAuditTests(unittest.TestCase):
    def test_empty_fence_is_distinct_from_empty_string_and_content(self):
        self.assertTrue(a.empty_fence("```\n```"))
        self.assertTrue(a.empty_fence("```python\n \n```"))
        self.assertFalse(a.empty_fence(""))
        self.assertFalse(a.empty_fence("```\npkg/a.py\n```"))
        self.assertFalse(a.empty_fence("Explanation\n```\n```"))

    def test_inline_identity_format_has_no_false_file_header(self):
        self.assertEqual(a.inline_identities("```\npkg/a.py:C.run\n```"), ["pkg/a.py:C.run"])
        self.assertEqual(a.inline_identities("pkg/a.py\nfunction: C.run"), [])

    def test_line_range_parsing_uses_the_original_file_bounds(self):
        self.assertEqual(a.numbers_from_directive("pkg/a.py:lines: 2-9, 1", "one\ntwo\nthree"), [1, 2, 3])

    def test_execution_failure_is_not_called_a_localization_miss(self):
        result = {"status": "failed", "samples": [{"status": "step_limit"}, {"status": "context_limit"}],
                  "found_files": [], "found_entities": [], "raw_output_loc": []}
        primary, flags, _ = a.classify(result, {"samples": []})
        self.assertEqual(primary, "resource_or_turn_limit_without_prediction")
        self.assertEqual(set(flags), {"step_limit", "context_limit"})
        self.assertNotIn("miss", primary)

    def test_complete_can_still_mean_empty_fence_prediction(self):
        result = {"status": "complete", "samples": [{"status": "complete"}],
                  "raw_output_loc": ["```\n```"], "found_files": [], "found_entities": []}
        self.assertEqual(a.classify(result, {"samples": []})[0], "finish_contains_only_empty_code_fence")

    def test_class_only_output_is_not_a_failed_function_directive(self):
        result = {"found_files": ["pkg/a.py"], "found_entities": [], "raw_output_loc": ["pkg/a.py\nclass: C"]}
        attribution = {"samples": [{"directives": ["pkg/a.py:class: C"], "native_function_candidates": [],
                                     "attribution_errors": []}]}
        primary, flags, _ = a.classify(result, attribution)
        self.assertEqual(primary, "file_output_without_usable_function_directives")
        self.assertNotIn("entity_directives_unresolved_or_filtered", flags)

    def test_gold_layer_stops_before_any_gold_read_if_task_pending(self):
        with mock.patch.object(a, "read") as read:
            with self.assertRaises(ValueError):
                a.score_layer(Path("/must-not-read"), [{"terminal": False}], {}, {})
            read.assert_not_called()

    def test_real_upstream_cross_file_line_mapping_is_traced_without_gold(self):
        try:
            import networkx as nx
            from dependency_graph.traverse_graph import RepoEntitySearcher
            import util.process_output
        except ImportError as error:
            self.skipTest("CPU graph/parser dependencies are unavailable: " + str(error))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public/graph_index").mkdir(parents=True)
            graph = nx.MultiDiGraph()
            graph.add_node("pkg/a.py", type="file", code="x = 1\n" * 20)
            graph.add_node("pkg/b.py", type="file", code="\n\ndef other():\n    return 1\n")
            graph.add_node("pkg/b.py:other", type="function", code="def other():\n    return 1", start_line=3, end_line=4)
            path = root / "public/graph_index/o__r-1.pkl"
            path.write_bytes(pickle.dumps(graph))
            before = path.read_bytes()
            path.with_suffix(".receipt.json").write_text(json.dumps({"status": "success", "graph_sha256": hashlib.sha256(before).hexdigest()}))
            raw = "```\npkg/a.py\nline: 3\n```"
            result = {"raw_output_loc": [raw], "samples": [{"sample": 1, "raw_location": raw}],
                      "official_per_sample_found_entities": [["pkg/b.py:other"]],
                      "found_entities": ["pkg/b.py:other"]}
            actual = a.line_attribution(root, "o__r-1", result, {})
            self.assertEqual(actual["final_entities_supported_only_by_cross_file_line_mapping"], ["pkg/b.py:other"])
            self.assertEqual(actual["line_mappings"][0]["requested_file"], "pkg/a.py")
            self.assertEqual(actual["line_mappings"][0]["mapped_file"], "pkg/b.py")
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
