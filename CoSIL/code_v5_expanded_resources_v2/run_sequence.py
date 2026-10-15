"""C expanded persistent queue: complete B first, then GPU-idle pair, val-only race/report."""
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
B_RESULT = ROOT / "results/v5_pruner/B_runtime_reviewed_regularized_exploratory/outcome/assessment_report.json"
B_PAIR = ROOT / "results/v5_pruner/B_runtime_reviewed_regularized_exploratory/training/pair_status.json"
B_STATE = ROOT / "results/v5_pruner/B_runtime_reviewed_regularized_exploratory/sequence_status.json"
C_QUEUE_RELEASE = ROOT / "results/v5_pruner/C_training_queue_release.json"


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
    from code_v5_verified.expanded_policy import validate_decision
    validate_decision(args.data_dir, args.decision_file)
    from code_v5_expanded_resources_v2.run_training_pair import validate_queue_release
    # Root must bind both data and the new resource-only package before the
    # sequence creates any output directory or invokes a model subprocess.
    validate_queue_release(args.decision_file)
    output = args.output_dir.resolve()
    if not output.name.endswith("_exploratory") or output.exists():
        raise RuntimeError("Use a new explicitly marked C exploratory output directory")
    output.mkdir(parents=True)
    state_path = output / "sequence_status.json"
    while not (B_RESULT.exists() and C_QUEUE_RELEASE.exists()):
        state = {"time": now(), "stage": "waiting_for_complete_B_and_root_C_queue_release",
                 "model_loaded": False, "test_opened": False, "B_result_path": str(B_RESULT),
                 "C_release_path": str(C_QUEUE_RELEASE), "gpu_claimed": False}
        status(state_path, state)
        if B_PAIR.exists() and json.loads(B_PAIR.read_text()).get("stage") == "failed":
            state.update(stage="blocked_by_B_failure", error="B failed; C cannot take its inter-model GPU window")
            status(state_path, state)
            return 1
        time.sleep(30)
    validate_queue_release(args.decision_file)
    train, race, outcome = output / "training", output / "race", output / "outcome"
    commands = [
        [sys.executable, "-u", "-m", "code_v5_expanded_resources_v2.run_training_pair", "--data-dir", str(args.data_dir.resolve()),
         "--output-dir", str(train), "--track", "exploratory", "--data-policy", "verified-plus-B-runtime-v1",
         "--decision-file", str(args.decision_file.resolve()), "--effective-batch", "8", "--micro-batch", "2", "--wait-for-idle"],
        [sys.executable, "-u", "-m", "code_v5_expanded_resources_v2.race_and_calibrate", "--data-dir", str(args.data_dir.resolve()),
         "--reranker-run", str(train / "reranker"), "--instruct-run", str(train / "instruct"),
         "--output-dir", str(race), "--track", "exploratory", "--data-policy", "verified-plus-B-runtime-v1",
         "--root-decision-file", str(args.decision_file.resolve()), "--threshold-policy", "val_safety"],
        [sys.executable, "-u", "-m", "code_v5_expanded_resources_v2.report_outcome", "--data-dir", str(args.data_dir.resolve()),
         "--decision-file", str(args.decision_file.resolve()), "--training-dir", str(train), "--race-dir", str(race), "--output-dir", str(outcome)]]
    for phase, command in zip(("training", "val_race", "report"), commands):
        status(state_path, {"time": now(), "stage": phase, "command": command, "test_opened": False})
        print(json.dumps({"time": now(), "phase": phase, "command": command}), flush=True)
        result = subprocess.run(command, cwd=ROOT, env=dict(os.environ, TOKENIZERS_PARALLELISM="false"))
        if result.returncode:
            if phase == "training" and result.returncode == 75:
                pair_status = json.loads((train / "pair_status.json").read_text())
                if pair_status.get("stage") == "paused_due_to_foreign_GPU_use_or_observation_failure":
                    status(state_path, {"time": now(), "stage": pair_status["stage"], "phase": phase,
                                        "returncode": 75, "pause_reason": pair_status["pause_reason"],
                                        "test_opened": False, "preserved_logs": True,
                                        "race_or_report_started": False, "automatic_resume_performed": False})
                    return 75
            status(state_path, {"time": now(), "stage": "failed", "phase": phase, "returncode": result.returncode,
                                "test_opened": False, "preserved_logs": True})
            return result.returncode
    status(state_path, {"time": now(), "stage": "complete", "test_opened": False, "outcome": str(outcome)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
