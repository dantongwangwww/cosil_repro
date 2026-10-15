"""CPU-only closure checks and a disabled template for a separate root decision.

The original exploratory decision continues to forbid test. This namespace
requires a new decision for the subsequent evaluation stage; no old receipt is
rewritten. Preparing the template never decodes sealed test JSONL.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from code_v5.run_pipeline import load_winner, sha256, write_new, now

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/v5_pruner"
C_RUN = BASE / "C_Verified_plus_B_runtime_resources_v3_exploratory"
C_DATA = BASE / "data_verified_plus_B_runtime_reviewed"
AUTH = BASE / "C_postexploratory_evaluation_root_authorization.json"
TEST_OUTPUT = BASE / "postexploratory_C_resources_v3/test_once"
PIPELINE_OUTPUT = ROOT / "results/v5_pruner_exploratory/pipeline/C_resources_v3"
PACKAGE = ("__init__.py", "authority.py", "test_once.py", "run_pipeline.py",
           "run_pipeline_sequence.py", "historical_comparison.py", "check_interfaces.py")


def metadata(path):
    path = Path(path).resolve()
    if path.suffix != ".json":
        raise PermissionError("Metadata reader never decodes a JSONL file")
    return json.loads(path.read_text(encoding="utf-8"))


def add_file(files, path):
    path = Path(path).resolve()
    files[str(path)] = sha256(path)


def source_files():
    return [ROOT / "code_v5_postexploratory" / name for name in PACKAGE] + [
        ROOT / "code_v5" / name for name in ("pruner_pipeline.py", "judge_models.py", "metrics.py", "run_pipeline.py")
    ] + [ROOT / "code_v5_c_reports_resources_v2/validate_completed_C_resource_run.py",
         ROOT / "code_v5/build_pruner_data.py", ROOT / "code_v5/prepare_historical_qwen_pair_reuse.py",
         ROOT / "code_v3b/tool_dispatch.py", ROOT / "code_v3b/run_experiment_300.py",
         ROOT / "code_v5/race_and_calibrate.py", ROOT / "code_v5/report_gold_routes.py",
         ROOT / "code_v5_expanded_resources_v3/run_training_pair.py"]


def require_closed_qualified_c():
    """Validate actual completed checkpoints/val race, not an anticipated result."""
    from code_v5_c_reports_resources_v2.validate_completed_C_resource_run import validate_run
    from code_v5_expanded_resources_v3.race_and_calibrate import (
        load_candidate, choose_candidate, qualified, read_val, fit_temperature,
        apply_temperature, select_thresholds)
    files = {}
    for relative in ("sequence_status.json", "training/pair_status.json", "outcome/assessment_report.json"):
        path = C_RUN / relative
        record = metadata(path)
        if relative.endswith("status.json") and record.get("stage") != "complete":
            raise RuntimeError("C actual sequence/pair is incomplete; evaluation stays disabled")
        if record.get("test_opened") is not False:
            raise PermissionError("C closure lacks explicit unopened-test evidence")
        add_file(files, path)
    outcome = metadata(C_RUN / "outcome/assessment_report.json")
    if outcome.get("track") != "exploratory" or outcome.get("data_dir") != str(C_DATA):
        raise RuntimeError("Actual C outcome has another data/track identity")
    seal_path = C_DATA / "test_file_seal.json"
    seal = metadata(seal_path)
    val = read_val(C_DATA / "pruner_val.jsonl")
    truth = {(row["instance_id"], row["function_id"]): row for row in val}
    if len(truth) != len(val):
        raise RuntimeError("Duplicate frozen val identity")
    candidates = {}
    for kind, profile in (("reranker", (8, .1)), ("instruct", (16, 0.))):
        run = C_RUN / "training" / kind
        checked = validate_run(run, C_DATA, kind=kind, rank=profile[0], dropout=profile[1])
        files.update(checked["files_sha256"])
        candidates[kind] = load_candidate(run, kind, data_seal_sha=sha256(seal_path), val_truth=truth, track="exploratory")
        if outcome["models"][kind]["best"]["val"] != candidates[kind]["metrics"]:
            raise RuntimeError("Actual outcome and independently reproduced best val differ")
    selected, selection = choose_candidate(candidates)
    race = metadata(C_RUN / "race/race_report.json")
    if (selected is None or race.get("selected_kind") != selected
            or race.get("selection") != selection or race.get("winner_published") is not True
            or race.get("test_used_for_selection") is not False or race.get("test_opened") is not False
            or outcome.get("validation_race") != race):
        raise RuntimeError("Frozen C actual race is unqualified or inconsistent")
    winner_path = C_RUN / "race/winner.json"
    winner, winner_sha = load_winner(winner_path)
    if (winner.get("qualified_on_val") is not True or winner.get("test_used_for_selection") is not False
            or winner["kind"] != selected or not qualified(candidates[selected]["metrics"])
            or race.get("winner_sha256") != winner_sha
            or Path(winner["adapter_dir"]).resolve() != Path(candidates[selected]["adapter_dir"]).resolve()):
        raise RuntimeError("Winner does not match the real val-selected checkpoint")
    reproduction = fit_temperature(candidates[selected]["predictions"], split="val")
    if any(winner["calibration"].get(key) != value for key, value in reproduction.items()):
        raise RuntimeError("Saved temperature/calibration do not reproduce frozen val")
    thresholds = select_thresholds(apply_temperature(candidates[selected]["predictions"], winner["temperature"]), policy="val_safety")
    threshold_path = winner["artifacts"]["threshold_selection"]["path"]
    saved_thresholds = metadata(threshold_path)
    if not thresholds["passed"] or any(saved_thresholds.get(key) != value for key, value in thresholds.items()):
        raise RuntimeError("Frozen val-only safety thresholds do not reproduce")
    if (winner["low"], winner["high"]) != (thresholds["selected"]["low"], thresholds["selected"]["high"]):
        raise RuntimeError("Winner thresholds differ from frozen val selection")
    from code_v5.metrics import _verify_contract, verify_test_seal
    contract_path = C_RUN / "race/test_contract.json"
    contract = _verify_contract(contract_path)
    if (contract["winner"] != selected or contract["artifacts"]["winner_config"]["sha256"] != winner_sha
            or contract["calibration"] != winner["calibration"]
            or (contract["thresholds"]["low"], contract["thresholds"]["high"]) != (winner["low"], winner["high"])
            or contract["test"] != verify_test_seal(seal["test_path"], seal_path)):
        raise RuntimeError("Original test contract differs from the val freeze")
    if Path(seal["test_path"]).with_name(Path(seal["test_path"]).name + ".v5_opened_once.json").exists():
        raise RuntimeError("The global once-only test opening has already been consumed")
    from code_v5.run_pipeline import inference_core
    original_core, _ = inference_core()  # verifies frozen v3c sources/candidates; no model/labels
    for relative, expected in original_core["original_sha256"].items():
        add_file(files, ROOT / relative)
        if files[str((ROOT / relative).resolve())] != expected:
            raise RuntimeError("Original baseline inference source changed during preparation")
    for path in (*source_files(), winner_path, contract_path, seal_path,
                 C_DATA / "statistics.json", C_DATA / "split_manifest.json",
                 C_RUN / "race/race_report.json", C_RUN / "race/calibration.json", threshold_path,
                 ROOT / "results/v3b_dataset_ten.json", ROOT / "results/qwen_300/prepared_inputs.json",
                 ROOT / "results/comparison/逐题定位对照数据.json"):
        add_file(files, path)
    for entry in seal["frozen_files"].values():
        add_file(files, entry["path"])  # binary hashes only, including test
    for artifact in winner["artifacts"].values():
        add_file(files, artifact["path"])
    for relative, expected in winner["base_model_files"].items():
        path = Path(winner["model_dir"]) / relative
        add_file(files, path)
        if files[str(path.resolve())] != expected:
            raise RuntimeError("Winning local base-model bytes differ from training")
    return files, winner, winner_path, contract_path


def prepare_authorization(output):
    files, winner, winner_path, contract = require_closed_qualified_c()
    template = {"schema_version": 1, "created_at": now(), "root_authorized": False,
        "stage": "postexploratory_evaluation", "allow_test_once": False, "allow_pipeline": False,
        "user_conditional_workflow": "qualified C val race -> frozen calibration -> test once -> historical Qwen comparison -> 60 canaries -> small/hybrid300",
        "C_run": str(C_RUN), "C_data": str(C_DATA), "winner_file": str(winner_path),
        "winner_sha256": sha256(winner_path), "test_contract": str(contract),
        "test_output": str(TEST_OUTPUT), "pipeline_output": str(PIPELINE_OUTPUT),
        "files_sha256": files, "selected_kind": winner["kind"],
        "resource_policy": "shared_gpu_with_sufficient_headroom_v3", "allowed_gpu_ids": [0,1,2,3],
        "reserved_gpu_ids": [], "minimum_free_mib": 12288, "peer_processes_may_be_modified": False,
        "test_reselection_allowed": False, "sealed_test_rows_decoded": False,
        "historical_Qwen300_rerun_allowed": False, "Decision_1_allowed": False,
        "llm_labels_allowed": False, "class_judge": "original Qwen",
        "canary": {"ids_source": str(ROOT / "results/v3b_dataset_ten.json"), "issues": 10, "modes": ["qwen","small","hybrid"], "repeats": [1,2]},
        "full": {"issues": 300, "modes": ["small","hybrid"], "qwen": "reuse historical v3c off"},
        "selection_remains_exploratory": True,
        "instruction": "Root must review actual completed checks and sign a separate execution receipt. Original C exploratory authorization remains unchanged."}
    write_new(output, template)
    return {"disabled_template": str(Path(output).resolve()), "sha256": sha256(output), "models_loaded": False, "test_rows_decoded": False}


def validate_authority(path, action):
    if action not in ("check", "test", "comparison", "pipeline"):
        raise ValueError("Unknown postexploratory action")
    path = Path(path).resolve()
    if path != AUTH:
        raise PermissionError("Use the canonical separate root postexploratory authorization")
    record = metadata(path)
    required = {"root_authorized": True, "stage": "postexploratory_evaluation", "allow_test_once": True,
        "allow_pipeline": True, "C_run": str(C_RUN), "C_data": str(C_DATA),
        "winner_file": str(C_RUN / "race/winner.json"), "test_contract": str(C_RUN / "race/test_contract.json"),
        "test_output": str(TEST_OUTPUT), "pipeline_output": str(PIPELINE_OUTPUT),
        "resource_policy": "shared_gpu_with_sufficient_headroom_v3", "allowed_gpu_ids": [0,1,2,3],
        "reserved_gpu_ids": [], "minimum_free_mib": 12288, "peer_processes_may_be_modified": False,
        "test_reselection_allowed": False, "historical_Qwen300_rerun_allowed": False,
        "Decision_1_allowed": False, "llm_labels_allowed": False, "class_judge": "original Qwen"}
    if any(record.get(key) != value for key, value in required.items()):
        raise PermissionError("Separate root execution authorization is absent or has a different scope")
    files = record.get("files_sha256", {})
    mandatory = {str(p.resolve()) for p in source_files()} | {
        str(C_RUN / p) for p in ("sequence_status.json", "training/pair_status.json", "outcome/assessment_report.json",
                               "race/winner.json", "race/race_report.json", "race/calibration.json", "race/threshold_selection.json", "race/test_contract.json")}
    mandatory |= {str(C_DATA / p) for p in ("test_file_seal.json", "pruner_train.jsonl", "pruner_val.jsonl", "pruner_test.jsonl", "statistics.json", "split_manifest.json")}
    if not mandatory <= set(files) or any(sha256(p) != expected for p, expected in files.items()):
        raise RuntimeError("Postexploratory source/data/checkpoint/frozen selection bindings drifted")
    winner, winner_sha = load_winner(record["winner_file"])
    if winner_sha != record.get("winner_sha256") or winner.get("qualified_on_val") is not True:
        raise RuntimeError("Frozen actual C val-qualified winner differs")
    if action in ("comparison", "pipeline"):
        from code_v5.metrics import load_saved_test_predictions
        load_saved_test_predictions(TEST_OUTPUT)  # saved predictions only; original test never reopened
    if action == "pipeline":
        comparison = metadata(BASE / "postexploratory_C_resources_v3/historical_off_comparison/comparison.json")
        if (comparison.get("authorization_sha256") != sha256(path)
                or comparison.get("winner_sha256") != winner_sha
                or comparison.get("new_model_calls") != 0
                or comparison.get("sealed_test_original_reopened") is not False):
            raise RuntimeError("Historical off comparison has not completed under this frozen authority")
    return record, winner, sha256(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare-authorization", "check"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization", type=Path, default=AUTH)
    args = parser.parse_args()
    if args.action == "prepare-authorization":
        if not args.output: parser.error("--output is required")
        result = prepare_authorization(args.output)
    else:
        record, winner, auth_sha = validate_authority(args.authorization, "check")
        result = {"qualified_winner": winner["kind"], "authorization_sha256": auth_sha, "model_loaded": False, "test_rows_decoded": False}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
