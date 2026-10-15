"""Run the root-reviewed v2 refiner once in a persistent terminal session."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from code_v5.run_training_pair import ROOT, now, write_status


def main():
    work = ROOT / "results/v5_pruner"
    status_path = work / "refinement_v2_status.json"
    expected = "7decc711b94dda810de8780f924ef315b8c6d7fcb0b1be560d883990a8783d33"
    script = ROOT / "code_v5/refine_pruner_data.py"
    if hashlib.sha256(script.read_bytes()).hexdigest() != expected:
        raise RuntimeError("Root-reviewed refiner bytes changed")
    with (work / "refinement_v2.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if status_path.exists() or (work / "data_v2").exists():
            raise FileExistsError("A v2 attempt already exists; do not overwrite or silently retry")
        command = [sys.executable, "-u", "-m", "code_v5.refine_pruner_data", "--source-data", str(work / "data"),
                   "--output", str(work / "data_v2"), "--v1-review-results", str(work / "review_v1_for_refiner.jsonl")]
        status = {"started_at": now(), "stage": "running", "pid": os.getpid(), "command": command,
                  "refiner_sha256": expected, "test_performance_opened": False, "model_calls": 0,
                  "log": str(work / "refinement_v2.log")}
        write_status(status_path, status)
        began = time.perf_counter()
        with (work / "refinement_v2.log").open("x") as log:
            completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        stats_path = work / "data_v2/statistics.json"
        normal_gate_stop = completed.returncode == 2 and stats_path.exists()
        status.update(finished_at=now(), returncode=completed.returncode, elapsed_seconds=time.perf_counter() - began,
                      stage="awaiting_actual_QC" if normal_gate_stop else ("complete" if completed.returncode == 0 else "failed"))
        if stats_path.exists():
            statistics = json.loads(stats_path.read_text())
            status.update(selected=statistics["selected"], quality_gates=statistics["quality_gates"],
                          formal_passed=statistics["passed"], statistics_sha256=hashlib.sha256(stats_path.read_bytes()).hexdigest())
        write_status(status_path, status)
        return 0 if normal_gate_stop else completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
