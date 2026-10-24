import json
from pathlib import Path
import tempfile
import unittest

from code_repair50.case_analysis import ArtifactReader, analyze_cases, build_case_report


class CaseAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.roster = {"frozen": False, "tasks": [{"instance_id": "task", "repo": "owner/repo", "base_commit": "a" * 40}]}

    def tearDown(self):
        self.temp.cleanup()

    def record(self, arm, resolved=False, full=True):
        folder = self.root / arm; (folder / "evaluation").mkdir(parents=True)
        patch = folder / "patch.diff"
        patch.write_text('diff --git "a/pkg/file.py" "b/pkg/file.py"\n--- "a/pkg/file.py"\n+++ "b/pkg/file.py"\n@@ -1 +1 @@\n-x\n+y\n')
        result = {"instance_id": "task", "arm": arm, "fully_observed_expected_tests": full,
            "official_result": {"tests_status": {"FAIL_TO_PASS": {"success": [], "failure": [] if resolved else ["check"]},
                                                  "PASS_TO_PASS": {"success": [], "failure": []}}}}
        (folder / "evaluation_record.json").write_text(json.dumps(result))
        (folder / "evaluation/parsed_test_statuses.json").write_text(json.dumps({"check": "PASSED" if resolved else "FAILED"}))
        return {"instance_id": "task", "arm": arm, "status": "TEST_COMPLETED", "resolved": resolved,
            "patch_generated": True, "parse_ok": True, "apply_ok": True, "test_completed": True,
            "official_verdict": True, "environment_error": False,
            "paths": {"patch": str(patch), "directory": str(folder / "evaluation")}}

    def test_source_gain_is_association_not_single_cause(self):
        records = [self.record("A"), self.record("B", True)]
        audits = [{"instance_id": "task", "gold_target_count": 2, "A_target_visible_count": 1,
                   "A_prediction_target_hit_count": 1, "B_added_source": True, "source_content_identical": False}]
        result = build_case_report(self.roster, records, audits, self.root, self.root / "report")
        self.assertEqual(result["cases"][0]["pair_category"], "ONLY_B_WITH_ADDED_SOURCE")
        text = (self.root / "report/修复失败分析_先分类再逐题.md").read_text()
        self.assertIn("不能单独证明因果机制", text)
        self.assertIn("../A/patch.diff", text)
        self.assertEqual(result["cases"][0]["A"]["F2P"]["observed_failure_n"], 1)

    def test_complete_vs_missing_observations_do_not_share_logic_label(self):
        records = [self.record("A", full=True), self.record("B", full=False)]
        result = analyze_cases(self.roster, records, [], self.root)
        self.assertEqual(result["cases"][0]["A"]["category"], "TEST_REQUIREMENTS_UNSATISFIED")
        self.assertEqual(result["cases"][0]["B"]["category"], "INCOMPLETE_TEST_OBSERVATIONS")
        self.assertIn("原因不确定", result["cases"][0]["specific_logic_cause"])

    def test_environment_and_unexecuted_never_become_both_failure(self):
        a = {"instance_id": "task", "arm": "A", "status": "ENVIRONMENT_ERROR", "resolved": None,
             "environment_error": True, "patch_generated": False}
        result = analyze_cases(self.roster, [a], [], self.root)
        self.assertEqual(result["cases"][0]["pair_category"], "UNPAIRED_OR_UNDETERMINED")
        self.assertEqual(result["cases"][0]["A"]["category"], "ENVIRONMENT_FAILURE")
        self.assertEqual(result["cases"][0]["B"]["category"], "NOT_EXECUTED")

    def test_integrity_rejection_is_not_environment_or_formal_test_failure(self):
        a = {"instance_id": "task", "arm": "A", "status": "INTEGRITY_REJECTED", "resolved": None,
             "environment_error": False, "patch_generated": True, "parse_ok": True, "apply_ok": False}
        result = analyze_cases(self.roster, [a, self.record("B", True)], [], self.root)
        self.assertEqual(result["cases"][0]["A"]["category"], "INTEGRITY_REJECTED")
        self.assertEqual(result["cases"][0]["pair_category"], "ONLY_B_PIPELINE_DELIVERED")

    def test_reference_patch_and_benchmark_row_are_not_read(self):
        private = self.root / "gold.diff"; private.write_text("secret reference repair")
        row = self.root / "benchmark_row.json"; row.write_text('{"patch":"private"}')
        reader = ArtifactReader(self.root)
        self.assertIsNone(reader.read(private, patch=True))
        self.assertIsNone(reader.read(row))
        self.assertEqual(len(reader.warnings), 2)

    def test_symlink_and_outside_artifacts_are_refused(self):
        outside = self.root.parent / (self.root.name + "_outside.json")
        outside.write_text('{}')
        try:
            link = self.root / "result.json"; link.symlink_to(outside)
            reader = ArtifactReader(self.root)
            self.assertIsNone(reader.read(link))
            self.assertIsNone(reader.read(outside))
        finally:
            outside.unlink()

    def test_cross_arm_evaluation_receipt_rejected(self):
        record = self.record("A")
        path = self.root / "A/evaluation_record.json"
        content = json.loads(path.read_text()); content["arm"] = "B"; path.write_text(json.dumps(content))
        with self.assertRaises(ValueError):
            analyze_cases(self.roster, [record], [], self.root)

    def test_durable_report_does_not_overwrite_changed_evidence(self):
        records = [self.record("A"), self.record("B")]
        destination = self.root / "report"
        build_case_report(self.roster, records, [], self.root, destination)
        build_case_report(self.roster, records, [], self.root, destination)
        records[0]["status"] = "OTHER"
        with self.assertRaises(FileExistsError):
            build_case_report(self.roster, records, [], self.root, destination)


if __name__ == "__main__":
    unittest.main()
