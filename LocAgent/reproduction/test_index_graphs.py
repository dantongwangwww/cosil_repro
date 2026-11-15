"""Standard-library graph-wrapper tests; no model or third-party imports."""
import json
from pathlib import Path
import tempfile
import unittest

from reproduction import index_graphs as g


class FakeGraph:
    def __init__(self, nodes):
        self.nodes = nodes


class GraphPreparationTests(unittest.TestCase):
    def test_atomic_receipts_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            g.atomic_json(path, {"status": "success"})
            with self.assertRaises(FileExistsError):
                g.atomic_json(path, {"status": "failed"})
            self.assertEqual(g.load(path), {"status": "success"})
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["receipt.json"])

    def test_cached_success_requires_matching_bytes_source_and_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public/graph_index").mkdir(parents=True)
            record = {"instance_id": "a__b-1", "snapshot_tree_sha256": "source"}
            graph, receipt = g.paths(root, "a__b-1")
            graph.write_bytes(b"frozen-graph")
            data = {"status": "success", "instance_id": "a__b-1", "snapshot_tree_sha256": "source",
                    "official_builder_sha256": "code", "graph_sha256": g.sha(graph)}
            g.atomic_json(receipt, data)
            self.assertEqual(g.validate_cached(root, record, "code"), data)
            with self.assertRaises(ValueError):
                g.validate_cached(root, record, "different-code")
            graph.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                g.validate_cached(root, record, "code")

    def test_failed_graph_is_terminal_not_automatically_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public/graph_index").mkdir(parents=True)
            record = {"instance_id": "a__b-1", "snapshot_tree_sha256": "source"}
            _, receipt = g.paths(root, "a__b-1")
            data = {"status": "timed_out", "instance_id": "a__b-1", "snapshot_tree_sha256": "source",
                    "official_builder_sha256": "code"}
            g.atomic_json(receipt, data)
            self.assertEqual(g.validate_cached(root, record, "code")["status"], "timed_out")

    def test_parse_audit_distinguishes_syntax_decode_and_upstream_skips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "valid.py").write_text("def run():\n    return 1\n")
            (root / "syntax.py").write_text("def bad(:\n")
            (root / "decode.py").write_bytes(b"\xff\xfe")
            (root / ".github").mkdir()
            (root / ".github/skip.py").write_text("def skipped(:\n")
            errors, skipped = g.syntax_audit(root, lambda path: ".github" in path)
            self.assertEqual({r["error_type"] for r in errors}, {"SyntaxError", "UnicodeDecodeError"})
            self.assertEqual(skipped, [".github/skip.py"])
            self.assertEqual(len(errors), 2)

    def test_source_check_refuses_changed_or_extra_python_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "selection").mkdir()
            (root / "public/snapshot").mkdir(parents=True)
            source = root / "public/snapshot/a.py"
            source.write_text("x = 1\n")
            files = [{"path": "a.py", "sha256": g.sha(source), "bytes": source.stat().st_size}]
            g.atomic_json(root / "selection/snapshot_sources.json", {"a__b-1": {"files": files}})
            record = {"instance_id": "a__b-1", "snapshot": "public/snapshot", "snapshot_tree_sha256": g.digest(files)}
            self.assertEqual(g.source_check(root, record), source.parent)
            (source.parent / "extra.py").write_text("x = 2\n")
            with self.assertRaises(ValueError):
                g.source_check(root, record)
            (source.parent / "extra.py").unlink()
            source.write_text("x = 3\n")
            with self.assertRaises(ValueError):
                g.source_check(root, record)

    def test_target_coverage_is_readonly_and_separates_constructor_class_fallback(self):
        graph = FakeGraph({"pkg/a.py": {"type": "file"}, "pkg/a.py:C": {"type": "class"},
                           "pkg/a.py:C.run": {"type": "function"}})
        before = json.dumps(graph.nodes, sort_keys=True)
        result = g.coverage_for_graph(graph, ["pkg/a.py::C.run", "pkg/a.py::C.__init__", "pkg/a.py::missing"])
        self.assertEqual(result["represented_function_nodes"], ["pkg/a.py::C.run"])
        self.assertTrue(result["missing_function_nodes"][0]["class_fallback_available"])
        self.assertFalse(result["missing_function_nodes"][1]["class_fallback_available"])
        self.assertEqual(json.dumps(graph.nodes, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()
