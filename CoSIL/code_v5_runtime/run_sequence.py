"""B persistent queue: complete A first, then GPU-idle pair, val-only race/report."""
import argparse
import hashlib
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
A_RESULT = ROOT / "results/v5_pruner/A_v3_noise_disclosed_outcome_exploratory/assessment_report.json"
A_PAIR = ROOT / "results/v5_pruner/A_v3_noise_disclosed_training_exploratory/pair_status.json"
A_BRANCH_RECEIPT = ROOT / "results/v5_pruner/A_branch_processing_receipt.json"
A_REGULARIZED_RESULT = ROOT / "results/v5_pruner/A_rank8_dropout01_exploratory/outcome/assessment_report.json"
A_REGULARIZED_STATE = ROOT / "results/v5_pruner/A_rank8_dropout01_exploratory/sequence_status.json"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def status(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--decision-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    from code_v5.runtime_filtered_policy import validate_decision
    validate_decision(args.data_dir, args.decision_file)
    output = args.output_dir.resolve()
    if not output.name.endswith("_exploratory") or output.exists():
        raise RuntimeError("Use a new explicitly marked B exploratory output directory")
    output.mkdir(parents=True)
    state_path = output / "sequence_status.json"
    while not A_RESULT.exists():
        state = {"time": now(), "stage": "waiting_for_complete_A_pair_race_report", "model_loaded": False,
                 "test_opened": False, "A_result_path": str(A_RESULT), "gpu_claimed": False}
        status(state_path, state)
        if A_PAIR.exists() and json.loads(A_PAIR.read_text())["stage"] == "failed":
            state.update(stage="blocked_by_A_failure", error="A failed; B must not take its inter-model slot")
            status(state_path, state)
            return 1
        time.sleep(30)
    A_report = json.loads(A_RESULT.read_text())
    if json.loads(A_PAIR.read_text())["stage"] != "complete" or A_report["test_opened"] is not False:
        raise RuntimeError("A must have completed both assessed models/race/report without test opening")
    while True:
        if A_BRANCH_RECEIPT.exists() and A_REGULARIZED_RESULT.exists() and A_REGULARIZED_STATE.exists():
            receipt = json.loads(A_BRANCH_RECEIPT.read_text())
            regularized = json.loads(A_REGULARIZED_RESULT.read_text())
            regularized_state = json.loads(A_REGULARIZED_STATE.read_text())
            if (receipt.get("A_branch_processing_complete") is True and receipt.get("allow_B_training") is True
                    and receipt.get("A_assessment_report_sha256") == hashlib.sha256(A_RESULT.read_bytes()).hexdigest()
                    and receipt.get("A_regularized_assessment_report_sha256") == hashlib.sha256(A_REGULARIZED_RESULT.read_bytes()).hexdigest()
                    and regularized.get("test_opened") is False and regularized_state["stage"] == "complete"):
                break
        status(state_path, {"time": now(), "stage": "waiting_for_root_A_conditional_branch_clearance",
               "receipt": str(A_BRANCH_RECEIPT), "model_loaded": False, "gpu_claimed": False, "test_opened": False})
        time.sleep(30)
    train, race, outcome = output / "training", output / "race", output / "outcome"
    commands = [
        [sys.executable, "-u", "-m", "code_v5_runtime.run_training_pair", "--data-dir", str(args.data_dir.resolve()),
         "--output-dir", str(train), "--track", "exploratory", "--data-policy", "runtime-covered-v3",
         "--decision-file", str(args.decision_file.resolve()), "--effective-batch", "8", "--micro-batch", "2", "--wait-for-idle"],
        [sys.executable, "-u", "-m", "code_v5_runtime.race_and_calibrate", "--data-dir", str(args.data_dir.resolve()),
         "--reranker-run", str(train / "reranker"), "--instruct-run", str(train / "instruct"),
         "--output-dir", str(race), "--track", "exploratory", "--data-policy", "runtime-covered-v3",
         "--root-decision-file", str(args.decision_file.resolve()), "--threshold-policy", "val_safety"],
        [sys.executable, "-u", "-m", "code_v5_runtime.report_outcome", "--data-dir", str(args.data_dir.resolve()),
         "--decision-file", str(args.decision_file.resolve()), "--training-dir", str(train), "--race-dir", str(race), "--output-dir", str(outcome)]]
    for phase, command in zip(("training", "val_race", "report"), commands):
        status(state_path, {"time": now(), "stage": phase, "command": command, "test_opened": False})
        print(json.dumps({"time": now(), "phase": phase, "command": command}), flush=True)
        result = subprocess.run(command, cwd=ROOT, env=dict(os.environ, TOKENIZERS_PARALLELISM="false"))
        if result.returncode:
            status(state_path, {"time": now(), "stage": "failed", "phase": phase, "returncode": result.returncode,
                                "test_opened": False, "preserved_logs": True})
            return result.returncode
    status(state_path, {"time": now(), "stage": "complete", "test_opened": False, "outcome": str(outcome)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
