"""Synthetic CPU-only terminal export/recovery tests; no repository execution."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from code_repair50.finalize_report import finalize, _task_digest


COMMIT = "e4907b7a90eafaa1f0a6428fd04fe31cdd8b4284"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalizeReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.roster = self.root / "roster.json"
        self.ledger = self.root / "ledger.json"
        self.log = self.root / "terminal.jsonl"
        self.output = self.root / "new_delivery"
        self.tasks = []
        self.script = "synthetic official eval; never executed\n"
        self.script_sha = hashlib.sha256(self.script.encode()).hexdigest()
        for i in range(50):
            iid = "alibaba__opensandbox-816" if i == 0 else f"org__case-{i}"
            task = {"instance_id": iid, "repo": f"org/repo{i}", "base_commit": "a" * 40,
                    "qualification_passed": True,
                    "image_reference": "swerebench/synthetic@sha256:" + "c" * 64,
                    "gold_receipt": str(self.root / "qualification" / iid / "gold/result.json")}
            self.tasks.append(task)
            write(Path(task["gold_receipt"]).parent / "protocol.json",
                  {"official_eval_script_sha256": self.script_sha})
            case = self.run / "cases" / iid
            ua = {"issue": "Synthetic issue", "source_context": "def f(): pass\n", "location_suggestions": ["f", "g"]}
            ub = copy.deepcopy(ua)
            if 11 <= i < 41:
                ub["location_suggestions"] = ["f"]
            elif i >= 41:
                ub["source_context"] += "def extra(): pass\n"
                ub["location_suggestions"] = ["f"]
            messages = lambda u: [{"role": "system", "content": "Shared prompt"},
                                  {"role": "user", "content": json.dumps(u)}]
            prepared = {"pair_inputs": {"A": {"messages": messages(ua)}, "B": {"messages": messages(ub)}},
                        "context_audit": {"instance_id": iid, "base_commit": task["base_commit"],
                            "source_content_identical": i < 41, "B_added_source": i >= 41,
                            "gold_target_count": 1, "A_prediction_target_hit_count": 1,
                            "A_target_visible_count": 1}}
            write(case / "prepared.json", prepared)
            for arm in ("A", "B"):
                folder = case / arm
                patch = folder / "edit_artifacts/patch.diff"
                patch.parent.mkdir(parents=True)
                patch.write_text("synthetic model patch; not executable\n")
                response = folder / "candidate_response.json"
                write(response, {"content": "synthetic"})
                write(folder / "provider/calls/repair/request.json", {"request": {"messages": prepared["pair_inputs"][arm]["messages"]}})
                write(folder / "provider/calls/repair/attempt_1_response.json", {"usage": {}})
                record = {"instance_id": iid, "arm": arm, "status": "TEST_COMPLETED",
                    "resolved": arm == "B", "patch_generated": True, "parse_ok": True,
                    "deterministic_apply_ok": True, "apply_ok": True, "test_completed": True,
                    "official_verdict": True, "environment_error": False, "generation_seconds": 1,
                    "test_seconds": 2, "end_to_end_seconds": 3, "cost_usd": 0.001,
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cache_hit_tokens": 1},
                    "generation_identity": {"task_sha256": _task_digest(task),
                                            "messages_sha256": _task_digest(prepared["pair_inputs"][arm]["messages"])},
                    "paths": {"request": str(folder / "provider/calls/repair/request.json"),
                              "response": str(response), "patch": str(patch)}}
                self.evaluation(folder / "evaluation", task, arm, arm == "B", patch)
                write(folder / "arm_record.json", record)
        write(self.roster, {"frozen": True, "tasks": self.tasks})
        write(self.ledger, {"reservations": {
            "known": {"status": "SETTLED", "charge_nano_usd": 9, "upper_nano_usd": 999},
            "unknown": {"status": "UNKNOWN_COST", "charge_nano_usd": None, "upper_nano_usd": 13},
            "pending": {"status": "RESERVED", "charge_nano_usd": None, "upper_nano_usd": 17},
            "released": {"status": "RELEASED", "charge_nano_usd": None, "upper_nano_usd": 333}}})
        self.terminal("COMPLETE", 100)

    def terminal(self, status, n):
        self.log.write_text(json.dumps({"event": "paired_run_finished", "status": status, "records": n}) + "\n"
                            + json.dumps({"event": "report_saved", "arm_records": n}) + "\n")

    def evaluation(self, folder, task, arm, resolved, patch):
        folder.mkdir(parents=True)
        (folder / "patch.diff").write_bytes(patch.read_bytes())
        (folder / "eval.sh").write_text(self.script)
        (folder / "test_output.txt").write_text("synthetic saved test output; never executed\n")
        write(folder / "protocol.json", {"base_commit": task["base_commit"], "patch_sha256": digest(patch),
              "official_eval_script_sha256": self.script_sha})
        write(folder / "base_head.json", {"returncode": 0, "head": task["base_commit"], "expected": task["base_commit"]})
        write(folder / "result.json", {"instance_id": task["instance_id"], "arm": arm,
            "status": "TEST_COMPLETED", "resolved": resolved, "test_completed": True,
            "official_verdict": True, "environment_error": False, "apply_ok": True, "patch_applied": True,
            "fully_observed_expected_tests": True, "test_seconds": 2, "elapsed_seconds": 7,
            "official_result": {"resolved": resolved}, "image_reference": task["image_reference"],
            "official_harness_commit": COMMIT,
            "logpaths": {"test_output": str(folder / "test_output.txt"), "eval_script": str(folder / "eval.sh")}})

    def export(self, **options):
        return finalize(run=self.run, roster=self.roster, ledger=self.ledger, output=self.output,
                        terminal_log=self.log, n_bootstrap=8, **options)

    def recovery(self, *, original_environment=True, resolved=False):
        task = self.tasks[0]
        case = self.run / "cases" / task["instance_id"]
        arm_path = case / "A/arm_record.json"
        old_eval = case / "A/evaluation/result.json"
        patch = case / "A/edit_artifacts/patch.diff"
        if original_environment:
            record = read(arm_path)
            record.update(status="ENVIRONMENT_ERROR", environment_error=True, resolved=None,
                          official_verdict=False, test_completed=False, test_seconds=None, apply_ok=None,
                          end_to_end_seconds=99)
            write(arm_path, record)
            ev = read(old_eval)
            ev.update(status="ENVIRONMENT_ERROR", environment_error=True, resolved=None,
                      official_verdict=False, test_completed=False, test_seconds=None,
                      apply_ok=None, patch_applied=None, official_result=None, stage="IMAGE_IDENTITY_OR_TRANSPORT")
            write(old_eval, ev)
            for name in ("patch.diff", "test_output.txt"):
                (old_eval.parent / name).unlink()
        retry = self.root / "separate_recovery"
        self.evaluation(retry, task, "A", resolved, patch)
        ref = lambda p: {"path": str(p), "sha256": digest(p)}
        binding = {"schema": "repair50_offline_recovery_binding_v1", "instance_id": task["instance_id"],
            "arm": "A", "base_commit": task["base_commit"], "image_reference": task["image_reference"],
            "official_harness_commit": COMMIT,
            "original": {"arm_record": ref(arm_path), "evaluation_result": ref(old_eval), "patch": ref(patch)},
            "recovered": {"evaluation_result": ref(retry / "result.json"), "patch": ref(retry / "patch.diff")}}
        p = self.root / "binding.json"
        write(p, binding)
        return p

    def test_complete_preserves_all_sources_paths_strict_groups_and_unknown_cost(self):
        before = {p: digest(p) for p in self.root.rglob("*") if p.is_file()}
        result = self.export()
        self.assertEqual(result["paired_official"]["paired_n"], 50)
        groups = result["input_intervention_groups"]
        self.assertEqual(groups["MESSAGES_IDENTICAL"]["selected_n"], 11)
        self.assertEqual(groups["SOURCE_SAME_HINTS_DIFFERENT"]["selected_n"], 30)
        self.assertEqual(groups["B_SOURCE_ADDED"]["selected_n"], 9)
        self.assertEqual(result["billing"]["budget_occupancy_upper_nano_usd"], 39)
        self.assertEqual(result["billing"]["known_actual_estimate_nano_usd"], 9)
        self.assertIsNone(result["billing"]["unknown_actual_cost_usd"])
        with (self.output / "per_issue_delivery.csv").open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 50)
        for key in ("request", "response", "patch", "eval_result", "test_output", "eval_script"):
            self.assertTrue(Path(rows[0]["A_" + key + "_path"]).is_file())
        self.assertEqual({p: digest(p) for p in before}, before)
        with self.assertRaises(FileExistsError):
            self.export()

    def test_complete_rejects_99_original_records_and_does_not_create_output(self):
        (self.run / "cases" / self.tasks[-1]["instance_id"] / "B/arm_record.json").unlink()
        with self.assertRaisesRegex(ValueError, "100 original"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_prepared_and_request_cannot_jointly_replace_sealed_record_messages(self):
        case = self.run / "cases" / self.tasks[0]["instance_id"]
        prepared_path = case / "prepared.json"
        prepared = read(prepared_path)
        for arm in ("A", "B"):
            prepared["pair_inputs"][arm]["messages"][0]["content"] = "Changed common prompt"
            request = case / arm / "provider/calls/repair/request.json"
            write(request, {"request": {"messages": prepared["pair_inputs"][arm]["messages"]}})
        write(prepared_path, prepared)
        with self.assertRaisesRegex(ValueError, "generation messages"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_missing_or_later_nonterminal_event_rejects_export(self):
        self.log.write_text('{"event":"report_saved","arm_records":99}\n')
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.export()
        self.terminal("COMPLETE", 100)
        with self.log.open("a") as f:
            f.write('{"event":"location_preparation_started","instance_id":"resumed"}\n')
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.export()

    def test_budget_terminal_keeps50_and_excludes_missing_pair(self):
        (self.run / "cases" / self.tasks[-1]["instance_id"] / "B/arm_record.json").unlink()
        self.terminal("BUDGET_STOP", 99)
        result = self.export()
        self.assertEqual(result["selected_n"], 50)
        self.assertEqual(result["paired_official"]["paired_n"], 49)
        self.assertEqual(result["arms"]["B"]["resolved_delivery_fixed50"]["denominator"], 50)
        self.assertEqual(len(result["missing_arms"]), 1)
        self.assertIn("BUDGET_STOP", result["missing_arms"][0]["reason"])

    def test_real_direct_budget_stop_event_is_supported(self):
        self.log.write_text('{"event":"BUDGET_STOP","budget":{}}\n')
        self.assertEqual(self.export()["terminal"]["state"], "BUDGET_STOP")

    def test_valid_first_official_false_recovery_is_derived_only(self):
        binding = self.recovery(resolved=False)
        original = self.run / "cases" / self.tasks[0]["instance_id"] / "A/arm_record.json"
        old_hash, ledger_hash = digest(original), digest(self.ledger)
        result = self.export(recovery_bindings=[binding])
        self.assertEqual(result["derived_recovery_count"], 1)
        row = read(self.output / "summary.json")["rows"][0]["A"]
        self.assertFalse(row["resolved"])
        self.assertEqual(row["recovery_provenance"]["original_status"], "ENVIRONMENT_ERROR")
        self.assertIsNone(row["end_to_end_seconds"])
        self.assertIsNone(row["analysis_end_to_end_seconds"])
        self.assertEqual(row["raw_end_to_end_seconds"], 99)
        self.assertEqual(row["recovery_evaluation_elapsed_seconds"], 7)
        self.assertEqual(row["cost_usd"], 0.001)
        self.assertEqual(digest(original), old_hash)
        self.assertEqual(digest(self.ledger), ledger_hash)

    def test_officially_failed_original_cannot_be_recovered_or_selected_away(self):
        p = self.recovery(original_environment=False, resolved=True)
        with self.assertRaisesRegex(ValueError, "applied/tested/model-negative"):
            self.export(recovery_bindings=[p])

    def test_wrong_arm_patch_harness_rejected(self):
        p = self.recovery()
        original = read(p)
        for field, value in [("arm", "B"), ("official_harness_commit", "f" * 40)]:
            changed = copy.deepcopy(original)
            changed[field] = value
            write(p, changed)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.export(recovery_bindings=[p])
        write(p, original)
        patch = Path(original["recovered"]["patch"]["path"])
        patch.write_text("different candidate")
        original["recovered"]["patch"]["sha256"] = digest(patch)
        write(p, original)
        with self.assertRaisesRegex(ValueError, "exact original patch"):
            self.export(recovery_bindings=[p])

    def test_duplicate_recovery_for_one_arm_rejected(self):
        p = self.recovery()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.export(recovery_bindings=[p, p])

    def test_null_flags_do_not_authorize_retry_after_application_stage(self):
        p = self.recovery()
        b = read(p)
        original_eval = Path(b["original"]["evaluation_result"]["path"])
        ev = read(original_eval)
        ev["stage"] = "BUSINESS_PATCH_APPLICATION"
        write(original_eval, ev)
        b["original"]["evaluation_result"]["sha256"] = digest(original_eval)
        write(p, b)
        with self.assertRaisesRegex(ValueError, "pre-application"):
            self.export(recovery_bindings=[p])

    def test_neutral_setup_head_needs_existing_bound_proof(self):
        p = self.recovery()
        b = read(p)
        result_path = Path(b["recovered"]["evaluation_result"]["path"])
        head_path = result_path.parent / "base_head.json"
        head = read(head_path)
        head["head"] = "b" * 40
        write(head_path, head)
        with self.assertRaisesRegex(ValueError, "source proof"):
            self.export(recovery_bindings=[p])
        proof_path = result_path.parent / "base_source_identity/proof.json"
        task = self.tasks[0]
        proof = {"schema": "repair50_official_setup_source_identity_v1", "instance_id": task["instance_id"],
                 "expected_base_commit": task["base_commit"], "actual_head": head["head"],
                 "image_reference": task["image_reference"], "official_eval_script_sha256": self.script_sha,
                 "runtime_image_id": "sha256:" + "d" * 64,
                 "validation": {"clean": True, "business_source_matches_base": True, "source_mutated": False}}
        write(proof_path, proof)
        write(result_path.parent / "image_receipt.json", {"reference": task["image_reference"], "image_id": proof["runtime_image_id"]})
        result = read(result_path)
        result.update(base_source_identity_proof_path=str(proof_path), base_source_identity_sha256=digest(proof_path),
                      base_source_identity_schema=proof["schema"])
        write(result_path, result)
        b["recovered"]["evaluation_result"]["sha256"] = digest(result_path)
        write(p, b)
        self.assertEqual(self.export(recovery_bindings=[p])["derived_recovery_count"], 1)

    def test_maintenance_preserves_raw_time_outcome_generation_and_test(self):
        p = self.root / "maintenance.json"
        write(p, {"instance_id": self.tasks[0]["instance_id"], "arm": "A",
                  "controller_parent_paused_during_existing_worker_wait": True,
                  "original_automatic_end_to_end_may_include_maintenance": True,
                  "final_analysis_policy": "Maintenance overlap: active e2e unknown"})
        self.export(maintenance_metadata=p)
        row = read(self.output / "summary.json")["rows"][0]["A"]
        self.assertFalse(row["resolved"])
        self.assertEqual(row["raw_end_to_end_seconds"], 3)
        self.assertIsNone(row["analysis_end_to_end_seconds"])
        self.assertIsNone(row["end_to_end_seconds"])
        self.assertEqual((row["generation_seconds"], row["test_seconds"]), (1, 2))


if __name__ == "__main__":
    unittest.main()
