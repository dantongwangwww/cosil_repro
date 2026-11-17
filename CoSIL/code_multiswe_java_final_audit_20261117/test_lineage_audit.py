"""Synthetic-only lineage contracts; no real benchmark or Gold inputs."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from code_multiswe_java_final_audit_20261117 import lineage_audit as module
from code_multiswe_java_signature_v2_20261117.view import normalize_cosil, normalize_locagent
from code_multiswe_java_20261117.locagent_adapter import parse_sample


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def fixture(root, missing_result=False):
    root.mkdir()
    view = root / module.VIEW
    view.mkdir(parents=True)
    rows = [{"instance_id": "toy-1", "repo": "toy/java", "base_commit": "a" * 40},
            {"instance_id": "toy-2", "repo": "toy/java", "base_commit": "b" * 40}]
    put(root / "allocation.json", {"n": 2, "records": rows})
    shutil.copyfile(root / "allocation.json", view / "allocation.json")
    (root / "public").mkdir()
    (view / "public").symlink_to(root / "public", target_is_directory=True)
    private = root / "evaluator_private"
    private.mkdir()
    (private / "NEVER_READ.json").write_text("invalid json: do not open private targets")
    (view / "evaluator_private").symlink_to(private, target_is_directory=True)
    frozen_code = root / "synthetic_source.py"
    frozen_code.write_text("# synthetic source only\n")
    for name in ["execution_freeze.json", "audits/analysis_execution_freeze.json", "audits/signature_view_execution_freeze.json"]:
        put(root / name, {"commit": "c" * 40, "files_sha256": {str(frozen_code): module.sha(frozen_code)}})
    manifest_records = []
    text = "class C {\n void f(A a,B b){}\n}\n"
    index = {"C.java": {"content": text, "raw_sha256": __import__("hashlib").sha256(text.encode()).hexdigest(),
                       "definitions": [{"kind": "function", "name": "f", "qualified_name": "C.f(A,B)",
                         "canonical_id": "C.java::C.f(A,B)", "start_line": 2, "end_line": 2}]}}
    for row in rows:
        iid = row["instance_id"]
        public, staged = root / "public" / iid, root / "run" / iid / "input"
        (public / "snapshot").mkdir(parents=True)
        (public / "snapshot/C.java").write_text(text)
        job = {**row, "problem_statement": "synthetic issue", "cohort": "synthetic", "snapshot": str(public / "snapshot"),
               "paths": ["C.java"], "code_index": str(public / "code_index.json"), "structure": str(public / "structure.json")}
        put(public / "job.json", job)
        put(staged / "job.json", {**job, "snapshot": "/snapshot", "code_index": "/input/code_index.json", "structure": "/input/structure.json"})
        for name, value in [("code_index.json", index), ("structure.json", {}), ("direct_edges.json", {"edges": []})]:
            put(public / name, value)
            staged.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(public / name, staged / name)
        source_group, derived_group = root / "run" / iid, view / "run" / iid
        derived_group.mkdir(parents=True)
        (derived_group / "input").symlink_to(staged, target_is_directory=True)
        old_terminals, new_terminals = {}, {}
        for arm in module.ARMS:
            origin, target = source_group / arm, derived_group / arm
            origin.mkdir()
            target.mkdir()
            terminal = {"instance_id": iid, "arm": arm, "status": "complete", "keep_in_denominator": True,
                        "elapsed_seconds": 1.5, "result_sha256": None}
            if missing_result and iid == "toy-2" and arm == "locagent":
                terminal.update(status="preparation_blocked", model_called=False)
            else:
                original = {**row, "status": "complete", "elapsed_seconds": 1.0,
                            "usage": {"total_tokens": 10, "api_cost_usd": 0},
                            "predicted_files": ["C.java"], "predicted_functions": [
                                {"path": "C.java", "qualified_name": "C.f(A, B)"},
                                {"path": "C.java", "qualified_name": "C.f(A, B)"},
                                {"path": "C.java", "qualified_name": None}]}
                if arm == "locagent":
                    raw = "C.java\nfunction: C.f(A, B)"
                    original = {**row, "status": "partial", "elapsed_seconds": 1.0, "protocol": "synthetic-native",
                        "source_inventory_sha256": module.sha(public / "code_index.json"), "usage": {"total_tokens": 10, "api_cost_usd": 0},
                        "ranked_files": ["C.java"], "ranked_functions": [], "found_files": ["C.java"], "found_entities": [],
                        "samples": [{"sample": 1, "status": "complete", "raw_location": raw, "parsed": parse_sample(raw, index)},
                                    {"sample": 2, "status": "step_limit", "raw_location": "", "parsed": parse_sample("", index)}]}
                    terminal["status"] = "partial"
                put(origin / "result.json", original)
                terminal["result_sha256"] = module.sha(origin / "result.json")
                if arm != "locagent":
                    put(origin / "worker_protocol.json", {"index_sha256": module.sha(public / "code_index.json")})
                put(origin / "calls/physical_receipt.json", {"usage": {"prompt_tokens": 8, "completion_tokens": 2}})
                expected, proof = (normalize_locagent(original, index) if arm == "locagent" else normalize_cosil(original, index))
                expected["offline_identity_view"] = {"version": "java_signature_format_v2", "original_result": str(origin / "result.json"),
                    "original_result_sha256": module.sha(origin / "result.json"), "base_index_sha256": module.sha(public / "code_index.json"),
                    "new_model_calls": 0, "Gold_read_for_normalization": False}
                put(target / "result.json", expected)
                put(target / "normalization_provenance.json", proof)
                manifest_records.append({"instance_id": iid, "arm": arm, "original_result_sha256": module.sha(origin / "result.json"),
                    "derived_result_sha256": module.sha(target / "result.json"), "provenance_sha256": module.sha(target / "normalization_provenance.json")})
                for child in origin.iterdir():
                    if child.name != "result.json":
                        (target / child.name).symlink_to(child, target_is_directory=child.is_dir())
            put(origin / "terminal.json", terminal)
            old_terminals[arm] = terminal
            new_terminal = {**terminal, "offline_view_only": True}
            if (target / "result.json").exists():
                new_terminal["result_sha256"] = module.sha(target / "result.json")
            put(target / "terminal.json", new_terminal)
            new_terminals[arm] = new_terminal
        put(source_group / "group_terminal.json", {"instance_id": iid, "status": "group_terminal", "arms": old_terminals})
        put(derived_group / "group_terminal.json", {"instance_id": iid, "status": "group_terminal", "arms": new_terminals, "offline_view_only": True})
    for directory in [root, view]:
        put(directory / "run/completion.json", {"status": "COMPLETE", "allocated": 2, "groups": 2})
    put(view / "view_manifest.json", {"status": "COMPLETE", "allocated": 2, "original_root": str(root),
        "source_allocation_sha256": module.sha(root / "allocation.json"), "new_model_calls": 0, "new_api_charge": 0,
        "normalization_uses_Gold": False, "records": manifest_records})
    summary = {"allocated": 2, "selected": 2, "file_denominator": 2, "function_denominator": 2,
               "arm_status_counts": {}, "metrics": {"synthetic": 0.0}}
    put(root / "reports/final128/summary.json", summary)
    put(root / "reports/signature_v2_evaluation/summary.json", {**summary, "metrics": {"synthetic": 0.5}})
    for directory in ["resources128", "signature_v2_resources"]:
        put(root / "reports" / directory / "summary.json", {"totals": {"calls": 6}, "judge_rpc_provenance_sha256": {}})
        (root / "reports" / directory / "per_issue_resources.csv").write_text("id,tokens\ntoy-1,10\n")
    (root / "reports/failures128").mkdir()
    (root / "reports/signature_v2_failures").mkdir()
    old_completion = {"status": "ANALYSIS_READY_FOR_INDEPENDENT_REVIEW", "outputs_sha256": {}}
    put(root / "analysis_supervisor/completion.json", old_completion)
    put(root / "signature_view_supervisor/completion.json", {"status": "NORMALIZED_REPORTS_READY_FOR_INDEPENDENT_REVIEW",
        "original_analysis_completion_sha256": module.sha(root / "analysis_supervisor/completion.json"),
        "view_manifest_sha256": module.sha(view / "view_manifest.json"), "outputs_sha256": {}})
    return view


class LineageContracts(unittest.TestCase):
    def test_waiting_never_opens_inventory_or_private(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "WAITING_COMPLETION")
            self.assertEqual(result["new_model_calls"], 0)

    def test_complete_synthetic_lineage_passes_without_reading_gold(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            fixture(root)
            original_read = module.read
            def no_gold(path):
                self.assertNotIn("evaluator_private", str(Path(path).resolve()))
                return original_read(path)
            with patch.object(module, "read", side_effect=no_gold):
                result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "PASS", result["errors"])
            self.assertEqual(result["terminal_conditions_checked"], 6)
            self.assertEqual(result["result_transformations"], 6)
            self.assertEqual(result["private_gold_files_opened"], 0)
            self.assertTrue(result["report_comparison"]["aggregate_summary_differences"])

    def test_legitimate_absent_result_not_a_missing_manifest_record(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            fixture(root, missing_result=True)
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "PASS", result["errors"])
            self.assertEqual(result["terminal_conditions_checked"], 6)
            self.assertEqual(result["manifest_records"], 5)
            self.assertEqual(result["legitimate_no_result_terminals"], 1)

    def test_mutating_original_result_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            fixture(root)
            path = root / "run/toy-1/cosil/result.json"
            value = module.read(path)
            value["elapsed_seconds"] = 999
            put(path, value)
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("original_result_terminal_sha", [e["check"] for e in result["errors"]])

    def test_base_source_drift_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            fixture(root)
            (root / "public/toy-1/snapshot/C.java").write_text("class C { /* drift */ }")
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("base_source_sha", [e["check"] for e in result["errors"]])

    def test_staged_index_must_equal_public_snapshot_index(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            fixture(root)
            path = root / "run/toy-1/input/code_index.json"
            value = module.read(path)
            value["C.java"]["definitions"] = []
            put(path, value)
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("staged_index_binding", [e["check"] for e in result["errors"]])

    def test_derivative_cannot_change_status_usage_or_raw_location(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            view = fixture(root)
            path = view / "run/toy-1/locagent/result.json"
            value = module.read(path)
            value["samples"][1]["raw_location"] = "C.java\nfunction: C.f(A,B)"
            value["usage"]["total_tokens"] = 0
            put(path, value)
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("derived_exactly_declared_transform_all_other_fields_identical", [e["check"] for e in result["errors"]])

    def test_log_relink_to_another_source_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            view = fixture(root)
            target = view / "run/toy-1/cosil/calls"
            target.unlink()
            target.symlink_to(root / "run/toy-2/cosil/calls", target_is_directory=True)
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("original_resource_artifact_reused", [e["check"] for e in result["errors"]])

    def test_manifest_duplicate_records_are_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            view = fixture(root)
            path = view / "view_manifest.json"
            value = module.read(path)
            value["records"].append(copy.deepcopy(value["records"][0]))
            put(path, value)
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("unique_manifest_result_record", [e["check"] for e in result["errors"]])

    def test_resource_table_cannot_silently_recharge_new_calls(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            fixture(root)
            path = root / "reports/signature_v2_resources/summary.json"
            value = module.read(path)
            value["totals"]["calls"] = 12
            put(path, value)
            result = module.audit(root, expected_n=2)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("resource_totals_reused_not_charged_twice", [e["check"] for e in result["errors"]])

    def test_independent_lexical_tokens_reject_glued_identifiers(self):
        self.assertTrue(module.token_equivalent("C.f(A, B)", "C.f(A,B)"))
        self.assertTrue(module.token_equivalent("C.f(List<? extends Foo>)", "C.f(List<?extendsFoo>)"))
        self.assertFalse(module.token_equivalent("C.f(A B)", "C.f(AB)"))

    def test_output_is_create_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "audit.json"
            module.write_new(path, {"status": "synthetic"})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                module.write_new(path, {"status": "overwrite"})
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
