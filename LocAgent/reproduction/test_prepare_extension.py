"""CPU-only checks for ordered extension and exact historical reuse bindings."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("prepare_extension", Path(__file__).with_name("prepare_extension.py"))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def record(i):
    return {"instance_id": f"owner{i}__repo-{i}", "repo": f"owner{i}/repo", "base_commit": str(i),
            "source_id": "source", "snapshot_tree_sha256": "tree"}


class ExtensionTests(unittest.TestCase):
    def test_set_difference_preserves_parent_order_and_prior_order_is_irrelevant(self):
        full = [record(i) for i in (4, 1, 3, 0, 2)]
        self.assertEqual([r["instance_id"] for r in p.extension_records(full, [record(1), record(4)])],
                         [record(i)["instance_id"] for i in (3, 0, 2)])
        self.assertEqual(full, [record(i) for i in (4, 1, 3, 0, 2)])

    def test_identity_drift_duplicates_and_nonparent_history_rejected(self):
        full = [record(0), record(1)]
        for previous in ([record(2)], [record(0), record(0)], [{**record(0), "base_commit": "changed"}]):
            with self.assertRaises(ValueError):
                p.extension_records(full, previous)
        with self.assertRaises(ValueError):
            p.extension_records([record(0), record(0)], [])

    def test_graph_reuse_requires_exact_source_builder_and_graph_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            graph = run / "public/graph_index" / (record(1)["instance_id"] + ".pkl")
            graph.parent.mkdir(parents=True)
            graph.write_bytes(b"already-frozen-graph")
            receipt = {"instance_id": record(1)["instance_id"], "status": "success", "graph_ready": True,
                       "snapshot_tree_sha256": "tree", "official_builder_sha256": "builder",
                       "graph_sha256": p.base.sha(graph)}
            receipt_path = graph.with_suffix(".receipt.json")
            receipt_path.write_text(json.dumps(receipt))
            self.assertEqual(p.graph_binding(run, record(1), "builder")["graph_sha256"], p.base.sha(graph))
            for changed in ({"snapshot_tree_sha256": "other"}, {"status": "failed"}, {"official_builder_sha256": "other"}):
                receipt_path.write_text(json.dumps(receipt | changed))
                with self.assertRaises(ValueError):
                    p.graph_binding(run, record(1), "builder")
            receipt_path.write_text(json.dumps(receipt))
            graph.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                p.graph_binding(run, record(1), "builder")

    def test_result_reuse_binds_view_to_raw_and_keeps_failed_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            row = record(1)
            original = run / "outputs" / row["instance_id"] / "result.json"
            view = run / "audits/postprocess_requested_file_final100/outputs" / row["instance_id"] / "result.json"
            original.parent.mkdir(parents=True)
            view.parent.mkdir(parents=True)
            raw = {k: row[k] for k in ("instance_id", "repo", "base_commit")} | {"terminal": True, "status": "failed"}
            original.write_text(json.dumps(raw))
            value = raw | {"source_inference_result_sha256": p.base.sha(original)}
            view.write_text(json.dumps(value))
            p.result_binding(run, row)
            self.assertEqual(json.loads(original.read_text())["status"], "failed")
            for changed in ({"terminal": False}, {"base_commit": "other"}, {"source_inference_result_sha256": "wrong"}):
                view.write_text(json.dumps(value | changed))
                with self.assertRaises(ValueError):
                    p.result_binding(run, row)

    def test_offline_tokenizer_cache_is_required_and_copied_byte_identically(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "old"
            with self.assertRaises(ValueError):
                p.tokenizer_binding(run)
            source = run / "public/tokenizer_cache"
            source.mkdir(parents=True)
            for name in p.TOKENIZER_CACHE_FILES:
                (source / name).write_bytes(b"immutable table " + name.encode())
            cache = p.tokenizer_binding(run)
            out = Path(directory) / "new"
            (out / "public").mkdir(parents=True)
            p.copy_tokenizer(cache, out)
            self.assertEqual(p.tokenizer_binding(out)["files"], cache["files"])
            for item in cache["files"]:
                self.assertEqual((out / "public/tokenizer_cache" / item["path"]).read_bytes(),
                                 (source / item["path"]).read_bytes())
            (source / next(iter(p.TOKENIZER_CACHE_FILES))).write_bytes(b"")
            with self.assertRaises(ValueError):
                p.tokenizer_binding(run)
            with self.assertRaises(ValueError):
                p.copy_tokenizer(cache, Path(directory) / "missing-output")


if __name__ == "__main__":
    unittest.main()
