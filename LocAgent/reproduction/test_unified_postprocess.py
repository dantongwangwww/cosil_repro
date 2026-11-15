"""CPU fixtures: reuse/projection receipts, no model, graph execution, or gold."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from reproduction import unified_postprocess as u


def record(origin="new180"):
    return {"instance_id": "owner__repo-1", "repo": "owner/repo", "base_commit": "a" * 40,
            "execution_origin": origin, "instance": "public/task.json", "snapshot": "public/snapshot"}


def raw(row):
    return {k: row[k] for k in ("instance_id", "repo", "base_commit")} | {
        "status": "complete", "terminal": True, "execution_status": "complete",
        "found_files": ["file.py"], "found_entities": [], "found_modules": [],
        "raw_output_loc": ["file.py\nfunction: f"], "samples": [{"sample": 1, "raw_location": "file.py\nfunction: f"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}


def normalized(value, source_sha):
    return copy.deepcopy(value) | {"found_entities": ["file.py:f"], "postprocess_view": u.RULE_ID,
        "source_patch_sha256": u.SOURCE_PATCH_SHA256, "source_inference_result_sha256": source_sha,
        "postprocess_diagnostic_error": None}


PROTOCOL = {"rule": {"rule_first_frozen_at_utc": "2026-11-15T09:56:37.773978+00:00"}}


class ReuseTests(unittest.TestCase):
    def test_old100_is_byte_reused_and_bound_to_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); out = run / "audit"; row = record("existing100_reuse")
            source = run / "old/raw/result.json"; old = run / "old/normalized/result.json"
            u.write(source, raw(row)); value = normalized(raw(row), u.sha(source)); u.write(old, value)
            row.update(original_result=str(source), requested_file_result=str(old))
            before = source.read_bytes(), old.read_bytes()
            receipt = u.normalize_one(run, out, row, PROTOCOL)
            self.assertEqual(receipt["mode"], "frozen_old100_byte_reuse")
            self.assertEqual((out / "outputs" / row["instance_id"] / "result.json").read_bytes(), before[1])
            self.assertEqual((source.read_bytes(), old.read_bytes()), before)
            self.assertEqual(u.ready_receipt(out, row), receipt)

    def test_old_result_bound_to_different_raw_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); row = record("existing100_reuse")
            source = run / "old/raw.json"; old = run / "old/normalized.json"
            u.write(source, raw(row)); u.write(old, normalized(raw(row), "wrong"))
            row.update(original_result=str(source), requested_file_result=str(old))
            with self.assertRaisesRegex(ValueError, "bound"):
                u.normalize_one(run, run / "audit", row, PROTOCOL)

    def test_post_receipt_raw_mutation_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); out = run / "audit"; row = record("existing100_reuse")
            source = run / "old/raw.json"; old = run / "old/normalized.json"
            u.write(source, raw(row)); u.write(old, normalized(raw(row), u.sha(source)))
            row.update(original_result=str(source), requested_file_result=str(old))
            u.normalize_one(run, out, row, PROTOCOL)
            source.write_text(source.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "changed"):
                u.ready_receipt(out, row)


class ProjectionTests(unittest.TestCase):
    def fixture(self, run):
        row = record(); source = run / "outputs" / row["instance_id"] / "result.json"
        u.write(source, raw(row))
        graph = run / "public/graph_index" / f"{row['instance_id']}.pkl"
        graph.parent.mkdir(parents=True); graph.write_bytes(b"not executed")
        u.write(graph.with_suffix(".receipt.json"), {"status": "success"})
        return row, source

    def test_new_task_uses_one_record_projection_and_same_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); row, source = self.fixture(run); before = source.read_bytes()
            invoked = []
            def builder(project, output):
                manifest = u.read(project / "selection/manifest.json")
                self.assertEqual(manifest["records"], [row])
                self.assertTrue((project / "outputs" / row["instance_id"]).is_symlink())
                value = normalized(u.read(source), u.sha(source))
                u.write(output / "outputs" / row["instance_id"] / "result.json", value)
                invoked.append(project)
                return {"status": "FINAL", "expected_tasks": 1, "terminal_tasks": 1,
                        "diagnostic_errors": [], "read_errors": [], "source_patch_sha256": u.SOURCE_PATCH_SHA256}
            out = run / "audit"
            receipt = u.normalize_one(run, out, row, PROTOCOL, builder=builder)
            self.assertEqual(receipt["mode"], "new180_same_frozen_sample_parser_mrr")
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(len(invoked), 1)
            self.assertEqual(u.normalize_one(run, out, row, PROTOCOL, builder=builder), receipt)
            self.assertEqual(len(invoked), 1)

    def test_native_fallback_on_parser_error_is_not_published_as_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); row, _ = self.fixture(run)
            def builder(*_):
                return {"status": "FINAL", "expected_tasks": 1, "terminal_tasks": 1,
                        "diagnostic_errors": ["error"], "source_patch_sha256": u.SOURCE_PATCH_SHA256}
            with self.assertRaisesRegex(ValueError, "cleanly"):
                u.normalize_one(run, run / "audit", row, PROTOCOL, builder=builder)
            self.assertFalse((run / "audit/outputs" / row["instance_id"] / "normalization_receipt.json").exists())

    def test_nonterminal_and_missing_tasks_remain_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); row = record()
            self.assertIsNone(u.normalize_one(run, run / "audit", row, PROTOCOL))
            u.write(run / "outputs" / row["instance_id"] / "result.json", raw(row) | {"terminal": False})
            self.assertIsNone(u.normalize_one(run, run / "audit", row, PROTOCOL))

    def test_normalization_cannot_change_usage_status_or_samples(self):
        row = record(); source = raw(row)
        for key, wrong in (("usage", {"total_tokens": 0}), ("status", "failed"), ("samples", [])):
            changed = normalized(source, "a") | {key: wrong}
            with self.assertRaisesRegex(ValueError, "inference field"):
                u.verify_inference_unchanged(source, changed, row)

    def test_zero_inference_and_fixed_scope_in_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); out = run / "audit"
            summary = u.update_summary(run, out, [record()], {})
            self.assertEqual(summary["expected_tasks"], 1)
            self.assertEqual(summary["ready_tasks"], 0)
            self.assertEqual(summary["new_model_calls"], 0)
            self.assertFalse(summary["gold_read"])


if __name__ == "__main__": unittest.main()
