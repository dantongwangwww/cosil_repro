import copy
import csv
import io
import tempfile
from pathlib import Path
import unittest

from code_repair50.reporting import analyze, build_blocked_report, build_report, markdown


class ReportingTests(unittest.TestCase):
    def roster(self, frozen=True):
        return {"formal_frozen": frozen, "records": [
            {"instance_id": f"task-{i}", "repo": f"owner/repo-{i}", "base_commit": "a" * 40}
            for i in range(50)
        ]}

    def record(self, i=0, arm="A", resolved=True, **updates):
        value = {"instance_id": f"task-{i}", "arm": arm, "status": "TEST_COMPLETE",
                 "resolved": resolved, "patch_generated": True, "parse_ok": True, "apply_ok": True,
                 "test_completed": True, "official_verdict": True, "environment_error": False,
                 "error_type": None, "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                 "cache_hit_tokens": 20}, "cost_usd": 0.001, "generation_seconds": 2,
                 "test_seconds": 3, "end_to_end_seconds": 5, "paths": {"patch": "patch.diff"}}
        value.update(updates)
        return value

    def test_fixed50_vs_common_official_denominator(self):
        records = [self.record(0, "A", True), self.record(0, "B", False),
                   self.record(1, "A", False), self.record(1, "B", True)]
        result = analyze(self.roster(), records, n_bootstrap=50)
        self.assertEqual(result["arms"]["A"]["resolved_delivery_fixed50"]["denominator"], 50)
        self.assertEqual(result["arms"]["A"]["official_resolved_rate"]["denominator"], 2)
        self.assertEqual(result["paired_official"]["paired_n"], 2)
        self.assertEqual(result["paired_official"]["four_cells"]["both_failure"], 0)
        self.assertEqual(result["arms"]["A"]["status_counts"]["MISSING_RECORD"], 48)

    def test_environment_and_pending_do_not_become_model_failure(self):
        records = [self.record(0, "A", None, status="ENVIRONMENT_ERROR", environment_error=True,
                               official_verdict=False, test_completed=False), self.record(0, "B", True),
                   self.record(1, "A", None, status="PENDING_TEST", official_verdict=False, test_completed=False),
                   self.record(1, "B", True)]
        result = analyze(self.roster(), records, n_bootstrap=10)
        self.assertEqual(result["paired_official"]["paired_n"], 0)
        self.assertEqual(result["paired_model_pipeline_sensitivity"]["paired_n"], 0)
        self.assertEqual(result["arms"]["A"]["environment_failure_n"], 1)

    def test_unknown_environment_cause_does_not_enter_model_failure_sensitivity(self):
        a = self.record(0, "A", None, status="NO_TEST_OBSERVATIONS", environment_error=None,
                        official_verdict=False, test_completed=False, apply_ok=False)
        result = analyze(self.roster(), [a, self.record(0, "B", True)], n_bootstrap=10)
        self.assertEqual(result["paired_model_pipeline_sensitivity"]["paired_n"], 0)
        self.assertEqual(result["arms"]["A"]["status_counts"]["ENVIRONMENT_CAUSE_UNDETERMINED"], 1)

    def test_parse_and_apply_failure_enter_only_pipeline_sensitivity(self):
        a = self.record(0, "A", None, status="PARSE_FAILED", parse_ok=False, apply_ok=None,
                        test_completed=False, official_verdict=False)
        result = analyze(self.roster(), [a, self.record(0, "B", True)], n_bootstrap=20)
        self.assertEqual(result["paired_official"]["paired_n"], 0)
        pair = result["paired_model_pipeline_sensitivity"]
        self.assertEqual(pair["paired_n"], 1)
        self.assertEqual(pair["four_cells"]["only_B_success"], 1)

    def test_unknown_cost_and_usage_not_zero(self):
        record = self.record(cost_usd=None, usage={})
        result = analyze(self.roster(), [record], n_bootstrap=10)
        self.assertEqual(result["arms"]["A"]["cost_usd"]["unknown_n"], 1)
        self.assertIsNone(result["arms"]["A"]["cost_usd"]["sum_known"])
        self.assertIsNone(result["arms"]["A"]["usage"]["prompt_tokens"]["mean_known"])

    def test_unfrozen_roster_has_no_zero_over_50_claim(self):
        result = analyze(self.roster(False), [], n_bootstrap=10)
        self.assertIsNone(result["arms"]["A"]["resolved_delivery_fixed50"])
        self.assertIsNone(result["paired_official"])
        self.assertIn("正式50题名单尚未冻结", markdown(result))
        self.assertNotIn("0/50（", markdown(result))

    def test_duplicate_or_unknown_candidate_records_rejected(self):
        for records in ([self.record(), self.record()], [self.record(99)]):
            with self.assertRaises(ValueError):
                analyze(self.roster(), records, n_bootstrap=10)

    def test_invalid_outcome_provenance_rejected(self):
        for record in (self.record(official_verdict=False), self.record(environment_error=True),
                       self.record(resolved=1), self.record(cost_usd=float("nan")),
                       self.record(usage={"prompt_tokens": 1, "cache_hit_tokens": 2})):
            with self.assertRaises(ValueError):
                analyze(self.roster(), [record], n_bootstrap=10)

    def test_roster_formality_is_explicit_and_requires50_unique_repositories(self):
        a = self.roster(); a["records"].pop()
        with self.assertRaises(ValueError):
            analyze(a, [], n_bootstrap=10)
        b = self.roster(); b["records"][1]["repo"] = b["records"][0]["repo"]
        with self.assertRaises(ValueError):
            analyze(b, [], n_bootstrap=10)

    def test_canonical_roster_schema_and_alias_conflicts(self):
        old = self.roster()
        canonical = {"frozen": True, "tasks": old["records"]}
        result = analyze(canonical, [], n_bootstrap=10)
        self.assertTrue(result["formal_frozen"])
        for invalid in ({**canonical, "formal_frozen": False},
                        {**canonical, "records": []}, {**canonical, "frozen": 1}):
            with self.subTest(invalid_keys=list(invalid)), self.assertRaises(ValueError):
                analyze(invalid, [], n_bootstrap=10)
        with self.assertRaises(ValueError):
            analyze(canonical, [], formal_frozen=False, n_bootstrap=10)
        compatible = {**canonical, "records": canonical["tasks"], "formal_frozen": True}
        self.assertTrue(analyze(compatible, [], n_bootstrap=10)["formal_frozen"])

    def test_blocked_entrypoint_has_no_manufactured_attempts_or_scores(self):
        roster = {"frozen": False, "tasks": self.roster()["records"]}
        with tempfile.TemporaryDirectory() as temp:
            result = build_blocked_report(roster, "BLOCKED_DISK_CAPACITY", ["disk_receipt.json"], temp)
            self.assertEqual(result["arms"]["A"]["record_count"], 0)
            self.assertIsNone(result["arms"]["A"]["resolved_delivery_fixed50"])
            report = (Path(temp) / "实验报告_定位辅助修复配对.md").read_text()
            self.assertIn("BLOCKED_DISK_CAPACITY", report)
            self.assertIn("正式50题名单尚未冻结", report)
            self.assertNotIn("0/50（", report)

    def test_prediction_and_source_coverage_grouped_separately(self):
        audit = {"instance_id": "task-0", "gold_target_count": 2,
                 "A_prediction_target_hit_count": 0, "A_target_visible_count": 2,
                 "B_added_source": False, "source_content_identical": True}
        result = analyze(self.roster(), [], [audit], n_bootstrap=10)
        row = result["rows"][0]
        self.assertEqual(row["A_prediction_coverage_group"], "NONE")
        self.assertEqual(row["A_source_coverage_group"], "ALL")
        self.assertEqual(result["rows"][1]["A_source_coverage_group"], "UNKNOWN")

    def test_contradictory_context_or_bad_counts_rejected(self):
        audits = [{"instance_id": "task-0", "B_added_source": True, "source_content_identical": True},
                  {"instance_id": "task-0", "gold_target_count": 1, "A_target_visible_count": 2}]
        for audit in audits:
            with self.assertRaises(ValueError):
                analyze(self.roster(), [], [audit], n_bootstrap=10)

    def test_localization_missing_denominator_stays_explicit(self):
        result = analyze(self.roster(), [], [{"instance_id": "task-0", "A_function_hit5": True}], n_bootstrap=10)
        self.assertEqual(result["localization"]["A_function_hit5"]["known_n"], 1)
        self.assertEqual(result["localization"]["A_function_hit5"]["unknown_n"], 49)

    def test_report_is_durable_and_inputs_unchanged(self):
        records = [self.record(0, "A", False), self.record(0, "B", True)]
        before = copy.deepcopy(records)
        with tempfile.TemporaryDirectory() as temp:
            result = build_report(self.roster(), records, [], temp, n_bootstrap=20)
            build_report(self.roster(), records, [], temp, n_bootstrap=20)
            csv_text = (Path(temp) / "per_issue.csv").read_text(encoding="utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(csv_text)))
            self.assertEqual(len(rows), 50)
            self.assertEqual(rows[1]["A_resolved"], "")
            self.assertIn("仅B成功1", (Path(temp) / "实验报告_定位辅助修复配对.md").read_text())
            with self.assertRaises(FileExistsError):
                build_report(self.roster(), [], [], temp, n_bootstrap=20)
        self.assertEqual(records, before)
        self.assertEqual(result["paired_official"]["four_cells"]["only_B_success"], 1)


if __name__ == "__main__":
    unittest.main()
