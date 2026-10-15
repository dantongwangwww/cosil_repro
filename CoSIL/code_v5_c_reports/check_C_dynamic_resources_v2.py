"""CPU-only guards for the independent C resource package; no GPU/model load."""
import ast
from copy import deepcopy
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v5_expanded_resources_v2 import run_training_pair as pair


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    prep = ROOT / "results/v5_pruner/C_launch_preparation_resource_v2"
    prep.mkdir(exist_ok=False)
    history = ROOT / "results/v5_pruner/protocol_history/C6_GPU2_reserve3_before_dynamic_policy_v2"
    old_receipt = json.loads((history / "original_bytes_receipt.json").read_text())
    for relative, digest in old_receipt["original_bytes_sha256"].items():
        assert sha(ROOT / relative) == sha(history / relative) == digest
    code = {"code_v5_expanded_resources_v2/" + n: sha(ROOT / "code_v5_expanded_resources_v2" / n)
            for n in pair.PACKAGE_FILES}
    diffs = []
    for name in pair.PACKAGE_FILES:
        old = (ROOT / "code_v5_expanded" / name).read_text()
        new = (ROOT / "code_v5_expanded_resources_v2" / name).read_text()
        ast.parse(new)
        diffs.extend(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                      fromfile="code_v5_expanded/" + name, tofile="code_v5_expanded_resources_v2/" + name))
    diff_path = prep / "resource_v2_vs_frozen_C6.diff"
    diff_path.write_text("".join(diffs))
    checks = []
    def checked(name, condition):
        assert condition, name
        checks.append({"name": name, "passed": True})
    def functions(file):
        return {node.name: node for node in ast.parse(file.read_text()).body if isinstance(node, ast.FunctionDef)}
    old = functions(ROOT / "code_v5_expanded/train_judges.py")
    new = functions(ROOT / "code_v5_expanded_resources_v2/train_judges.py")
    unchanged = ["load_training_splits", "_epoch_score", "prepare_lora", "validate_epoch", "_save_predictions",
                 "validate_track_output", "training_lock", "atomic_json", "append_journal", "_point"]
    checked("ten_train_val_LoRA_selection_helpers_AST_identical", all(ast.dump(old[x]) == ast.dump(new[x]) for x in unchanged))
    def epoch_loop(node):
        return next(x for x in ast.walk(node) if isinstance(x, ast.For) and isinstance(x.target, ast.Name) and x.target.id == "epoch")
    checked("entire_epoch_training_validation_checkpoint_loop_AST_identical", ast.dump(epoch_loop(old["train"])) == ast.dump(epoch_loop(new["train"])))
    old_race = (ROOT / "code_v5_expanded/race_and_calibrate.py").read_text().replace("code_v5_expanded.", "code_v5_expanded_resources_v2.")
    new_race = (ROOT / "code_v5_expanded_resources_v2/race_and_calibrate.py").read_text()
    checked("entire_val_race_calibration_test_refusal_AST_unchanged_except_namespace", ast.dump(ast.parse(old_race)) == ast.dump(ast.parse(new_race)))
    base = {"inventory": {i: {"uuid": "GPU-test-" + str(i), "memory_mib": 19, "utilization": 0} for i in range(4)},
            "full_processes": [], "compute_apps": [], "time": "SYNTHETIC_CPU_GUARD_ONLY"}
    checked("GPU0_is_selectable_when_actually_idle", pair.idle_gpu_ids(base, [0, 1, 2, 3])[0] == 0)
    busy = deepcopy(base)
    for i in [0, 1, 3]:
        busy["full_processes"].append({"gpu_uuid": "GPU-test-" + str(i), "pid": 999000 + i, "type": "C+G", "process_name": "synthetic_protected_context"})
    checked("no_reserve3_allows_GPU2_while_other_cards_busy", pair.idle_gpu_ids(busy, [0, 1, 2, 3]) == [2])
    busy["full_processes"].append({"gpu_uuid": "GPU-test-2", "pid": 999002, "type": "C+G", "process_name": "synthetic_context"})
    checked("low_memory_CplusG_on_every_card_hard_refused", pair.idle_gpu_ids(busy, [0, 1, 2, 3]) == [])
    csv_only = deepcopy(base); csv_only["compute_apps"] = ["GPU-test-0, 999009, synthetic_context, 1"]
    checked("CSV_only_context_blocks_when_XML_snapshot_lacks_it", 0 not in pair.idle_gpu_ids(csv_only, [0, 1, 2, 3]))
    xorg = deepcopy(base); xorg["full_processes"] = [{"gpu_uuid": "GPU-test-0", "pid": 999010, "type": "G", "process_name": "/usr/lib/xorg/Xorg"}]
    checked("only_resident_Xorg_G_ignored", 0 in pair.idle_gpu_ids(xorg, [0, 1, 2, 3]))
    xorg["full_processes"][0]["process_name"] = "synthetic_non_Xorg"
    checked("other_graphics_context_is_not_ignored", 0 not in pair.idle_gpu_ids(xorg, [0, 1, 2, 3]))
    used = deepcopy(base); used["inventory"][0]["memory_mib"] = 129; used["inventory"][1]["utilization"] = 1
    checked("memory_and_utilization_both_required_idle", pair.idle_gpu_ids(used, [0, 1, 2, 3]) == [2, 3])
    own = deepcopy(base); own["full_processes"] = [{"gpu_uuid": "GPU-test-0", "pid": 12345, "type": "C", "process_name": "synthetic_own_child"}]
    checked("monitor_ignores_only_exact_own_child_not_all_same_uid_jobs", pair.foreign_gpu_processes(own, 0, 12345) == [] and bool(pair.foreign_gpu_processes(own, 0, 54321)))
    decision = ROOT / "results/v5_pruner/C_Verified_plus_B_runtime_authorization_exploratory/root_exploratory_decision.json"
    checked("actual_data_decision_present", decision.is_file())
    checked("no_actual_resource_authorization_preexists", not pair.RESOURCE_AUTH.exists())
    try:
        pair.validate_resource_authorization(decision)
        raise AssertionError("Missing root resource receipt accepted")
    except RuntimeError as error:
        checked("actual_missing_resource_receipt_refuses_before_any_model", "No root C dynamic-GPU" in str(error))
    auth = {"root_authorized": True, "allow_C_training": True, "test_open_allowed": False,
            "resource_policy": pair.RESOURCE_POLICY, "allowed_gpu_ids": [0, 1, 2, 3], "reserved_gpu_ids": [],
            "peer_processes_may_be_modified": False, "allow_sharing_busy_gpu": False,
            "yield_on_foreign_gpu_use": True, "monitor_interval_seconds": 10,
            "pause_action": "terminate_own_child_preserve_completed_checkpoints", "C_decision_sha256": sha(decision),
            "C_original_code_sha256": {"code_v5_expanded/" + n: sha(ROOT / "code_v5_expanded" / n) for n in pair.PACKAGE_FILES},
            "C_resources_v2_code_sha256": code, "adapter_profiles": pair.EXPECTED_PROFILES,
            "data_policy": "verified-plus-B-runtime-v1"}
    with tempfile.TemporaryDirectory(prefix="v5-resource-CPU-guard-", dir="/tmp") as temporary:
        fixture = Path(temporary) / "synthetic_resource_authorization_NOT_EXECUTION.json"
        fixture.write_text(json.dumps(auth))
        with patch.object(pair, "RESOURCE_AUTH", fixture):
            checked("schema_guard_synthetic_valid_receipt_only", pair.validate_resource_authorization(decision)["reserved_gpu_ids"] == [])
            for name, mutate in [
                ("wrong_decision_SHA_refused", lambda x: x.update(C_decision_sha256="0" * 64)),
                ("reserve3_refused", lambda x: x.update(reserved_gpu_ids=[3])),
                ("busy_GPU_sharing_refused", lambda x: x.update(allow_sharing_busy_gpu=True)),
                ("disabled_runtime_yield_refused", lambda x: x.update(yield_on_foreign_gpu_use=False)),
                ("unbound_execution_source_refused", lambda x: x["C_resources_v2_code_sha256"].update({"code_v5_expanded_resources_v2/train_judges.py": "0" * 64})),
            ]:
                damaged = deepcopy(auth); mutate(damaged); fixture.write_text(json.dumps(damaged))
                try:
                    pair.validate_resource_authorization(decision)
                    raise AssertionError(name)
                except RuntimeError:
                    checked(name, True)
        # Two small CPU-only fixtures belong to this test, not external jobs.
        # A synthetic GPU table lists one as non-child; only monitor's own
        # directly created Popen child may be terminated. No nvidia-smi is run.
        cpu_other = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
        try:
            pretend = deepcopy(base)
            pretend["full_processes"] = [{"gpu_uuid": "GPU-test-0", "pid": cpu_other.pid, "type": "C+G", "process_name": "SYNTHETIC_CPU_FIXTURE_NOT_REAL_GPU"}]
            with (Path(temporary) / "cpu_guard_child.log").open("w") as log, patch.object(pair, "_gpu_inventory", return_value=pretend):
                result = pair.run_monitored_child([sys.executable, "-c", "import time;time.sleep(30)"],
                         environment=dict(os.environ), log=log, physical_gpu=0, monitor_interval_seconds=.05)
            checked("actual_CPU_child_yields_only_itself_synthetic_peer_lives", result["paused"] and result["returncode"] == -15 and cpu_other.poll() is None and result["automatic_resume_performed"] is False)
        finally:
            cpu_other.terminate(); cpu_other.wait(timeout=10)
        with (Path(temporary) / "cpu_observation_failure.log").open("w") as log, patch.object(pair, "_gpu_inventory", side_effect=RuntimeError("SYNTHETIC_OBSERVATION_FAILURE")):
            result = pair.run_monitored_child([sys.executable, "-c", "import time;time.sleep(30)"],
                     environment=dict(os.environ), log=log, physical_gpu=0, monitor_interval_seconds=.05)
        checked("monitor_observation_failure_yields_only_own_CPU_child", result["paused"] and result["returncode"] == -15 and result["foreign_GPU_observation"] == [])
    sequence = (ROOT / "code_v5_expanded_resources_v2/run_sequence.py").read_text()
    checked("sequence_explicitly_propagates_pause_without_race_report", '"race_or_report_started": False' in sequence and 'return 75' in sequence)
    checked("original_C6_and_original_launcher_bytes_still_identical", all(sha(ROOT / p) == s for p, s in old_receipt["original_bytes_sha256"].items()))
    checked("no_Torch_transformers_import_no_models_or_GPU", not any(x == "torch" or x.startswith("transformers") for x in sys.modules))
    receipt = {"status": "CPU_preparation_guards_passed_no_execution_authorization", "checks": checks,
               "resource_package_sha256": code, "original_snapshot_receipt_path": str(history / "original_bytes_receipt.json"),
               "original_snapshot_receipt_sha256": sha(history / "original_bytes_receipt.json"),
               "source_diff_path": str(diff_path), "source_diff_sha256": sha(diff_path),
               "C_decision_sha256": sha(decision), "checker_sha256": sha(__file__),
               "scope": "GPU tables/receipt mutations were explicitly synthetic CPU guard fixtures; two tiny CPU-only fixture processes were created/cleaned by this checker. No real GPU job was started or stopped, no external PID targeted.",
               "actual_resource_authorization_created": False, "training_started": False, "GPU_used": False,
               "models_loaded": False, "test_decoded": False, "source_baseline_rerun": False,
               "actual_job_ownership_determined_from_synthetic_guards": False}
    path = prep / "CPU_guard_receipt.json"
    with path.open("x") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2); handle.write("\n")
    # Requirements are a schema description, never a root-approved real receipt.
    auth["root_authorized"] = False; auth["allow_C_training"] = False
    with (prep / "resource_authorization_REQUIREMENTS_NOT_APPROVAL.json").open("x") as handle:
        json.dump(auth, handle, ensure_ascii=False, indent=2); handle.write("\n")
    print(json.dumps({"receipt_path": str(path), "sha256": sha(path), "checks": len(checks), "package": code}))


if __name__ == "__main__":
    main()
