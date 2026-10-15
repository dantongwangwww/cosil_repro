"""One isolated rank8/dropout0.1 reranker, queued after the complete original A."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from code_v5.noise_disclosed_policy import ROOT, DERIVED
from code_v5_regularized.policy import validate_decision
from code_v5.run_training_pair import gpu_preflight, _gpu_inventory

A_RESULT = ROOT / "results/v5_pruner/A_v3_noise_disclosed_outcome_exploratory/assessment_report.json"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def status(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    validate_decision(DERIVED, args.decision_file)
    output = args.output_dir.resolve()
    if output.exists() or not output.name.endswith("_exploratory"):
        raise RuntimeError("Use new separately marked regularized output")
    output.mkdir(parents=True)
    state = output / "sequence_status.json"
    while not A_RESULT.exists():
        status(state, {"time": now(), "stage": "waiting_for_complete_original_A", "model_loaded": False,
                       "test_opened": False, "gpu_claimed": False})
        pair = ROOT / "results/v5_pruner/A_v3_noise_disclosed_training_exploratory/pair_status.json"
        if pair.exists() and json.loads(pair.read_text())["stage"] == "failed":
            raise RuntimeError("Original A failed; preserve its incomplete model slot")
        time.sleep(30)
    status(state, {"time": now(), "stage": "waiting_for_natural_gpu_idle", "test_opened": False})
    preflight = gpu_preflight(wait_for_idle=True, wait_status_path=output / "gpu_wait_status.json")
    training, race, outcome = output / "reranker", output / "race", output / "outcome"
    commands = [
        [sys.executable, "-u", "-m", "code_v5_regularized.train_judges", "--kind", "reranker",
         "--model-dir", str(ROOT / "models_v5/Qwen3-Reranker-0.6B"), "--data-dir", str(DERIVED),
         "--output-dir", str(training), "--gpu", "2", "--track", "exploratory",
         "--data-policy", "noise-disclosed-v3-regularized", "--decision-file", str(args.decision_file.resolve()),
         "--effective-batch", "8", "--micro-batch", "2"],
        [sys.executable, "-u", "-m", "code_v5_regularized.race_and_calibrate", "--data-dir", str(DERIVED),
         "--reranker-run", str(training), "--instruct-run", str(ROOT / "results/v5_pruner/A_v3_noise_disclosed_training_exploratory/instruct"),
         "--output-dir", str(race), "--track", "exploratory", "--data-policy", "noise-disclosed-v3-regularized",
         "--root-decision-file", str(args.decision_file.resolve()), "--threshold-policy", "val_safety"],
        [sys.executable, "-u", "-m", "code_v5_regularized.report_outcome", "--training-dir", str(training),
         "--race-dir", str(race), "--decision-file", str(args.decision_file.resolve()), "--output-dir", str(outcome)]]
    for phase, command in zip(("training", "val_race", "report"), commands):
        status(state, {"time": now(), "stage": phase, "command": command, "gpu_preflight": preflight,
                       "test_opened": False, "experiment_condition": "rank8_dropout0.1_alpha32"})
        with (output / (phase + ".log")).open("x") as log:
            result = subprocess.run(command, cwd=ROOT, env=dict(os.environ, CUDA_VISIBLE_DEVICES="2", TOKENIZERS_PARALLELISM="false"),
                                    stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            status(state, {"time": now(), "stage": "failed", "phase": phase, "returncode": result.returncode,
                           "test_opened": False, "logs_preserved": True})
            raise SystemExit(result.returncode)
    status(state, {"time": now(), "stage": "complete", "test_opened": False, "outcome": str(outcome),
                   "gpu_final_observed": _gpu_inventory(), "peer_processes_changed": False})
