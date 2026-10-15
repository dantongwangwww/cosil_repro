"""Persistent A driver: natural-idle wait, paired training, val-only race/report."""
import json
import os
from pathlib import Path
import subprocess
import sys
from code_v5.noise_disclosed_policy import ROOT, DERIVED, validate_decision

AUTH = ROOT / "results/v5_pruner/A_v3_noise_disclosed_authorization_v2_exploratory/root_exploratory_decision.json"
TRAIN = ROOT / "results/v5_pruner/A_v3_noise_disclosed_training_exploratory"
RACE = ROOT / "results/v5_pruner/A_v3_noise_disclosed_race_exploratory"
OUT = ROOT / "results/v5_pruner/A_v3_noise_disclosed_outcome_exploratory"


if __name__ == "__main__":
    validate_decision(DERIVED, AUTH)
    if OUT.exists() or TRAIN.exists() or RACE.exists():
        raise FileExistsError("A output exists; preserve it rather than reexecute automatically")
    commands = [
        [sys.executable, "-u", "-m", "code_v5.run_training_pair", "--data-dir", str(DERIVED),
         "--output-dir", str(TRAIN), "--track", "exploratory", "--data-policy", "noise-disclosed-v3",
         "--decision-file", str(AUTH), "--effective-batch", "8", "--micro-batch", "2", "--wait-for-idle"],
        [sys.executable, "-u", "-m", "code_v5.race_and_calibrate", "--data-dir", str(DERIVED),
         "--reranker-run", str(TRAIN / "reranker"), "--instruct-run", str(TRAIN / "instruct"),
         "--output-dir", str(RACE), "--track", "exploratory", "--data-policy", "noise-disclosed-v3",
         "--root-decision-file", str(AUTH), "--threshold-policy", "val_safety"],
        [sys.executable, "-u", "-m", "code_v5.report_noise_disclosed_A", "--training-dir", str(TRAIN),
         "--race-dir", str(RACE), "--output-dir", str(OUT)]]
    for command in commands:
        print(json.dumps({"event": "start_phase", "command": command}), flush=True)
        result = subprocess.run(command, cwd=ROOT, env=dict(os.environ, TOKENIZERS_PARALLELISM="false"))
        print(json.dumps({"event": "phase_complete", "returncode": result.returncode}), flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
