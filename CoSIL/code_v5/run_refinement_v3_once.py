"""Persistently execute the final root-reviewed mechanical refinement round."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

from code_v5.run_training_pair import ROOT, now, write_status


def main():
    work = ROOT / "results/v5_pruner"
    status_path = work / "refinement_v3_status.json"
    expected = "18075ca5a26c85bf2a692d74907460176061e00d8ca24bfad8038739d8a9b3e5"
    script = ROOT / "code_v5/refine_pruner_data_v3.py"
    before = hashlib.sha256(script.read_bytes()).hexdigest()
    if before != expected:
        raise RuntimeError("Root-reviewed final refiner bytes changed")
    with (work / "refinement_v3.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if status_path.exists() or (work / "data_v3").exists():
            raise FileExistsError("A final v3 attempt already exists; no automatic retries or overwrites")
        command = [sys.executable, "-u", "-m", "code_v5.refine_pruner_data_v3",
                   "--source-data", str(work / "data"), "--previous-data", str(work / "data_v2"),
                   "--v1-review-results", str(work / "review_v1_for_refiner.jsonl"),
                   "--v2-review-results", str(work / "data_v2/human_review_codex_reviewed.jsonl"),
                   "--output", str(work / "data_v3")]
        status = {"started_at": now(), "stage": "running", "pid": os.getpid(), "command": command,
                  "refiner_sha256": expected, "final_data_repair_round": True,
                  "test_performance_opened": False, "model_calls": 0, "log": str(work / "refinement_v3.log")}
        write_status(status_path, status)
        began = time.perf_counter()
        with (work / "refinement_v3.log").open("x") as log:
            completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        stats_path = work / "data_v3/statistics.json"
        after = hashlib.sha256(script.read_bytes()).hexdigest()
        normal_gate_stop = completed.returncode == 2 and stats_path.exists() and after == before
        status.update(finished_at=now(), returncode=completed.returncode,
                      elapsed_seconds=time.perf_counter() - began, refiner_after_sha256=after,
                      source_unchanged=before == after,
                      stage="awaiting_actual_QC" if normal_gate_stop else ("complete" if completed.returncode == 0 and before == after else "failed"))
        if stats_path.exists():
            statistics = json.loads(stats_path.read_text())
            status.update(selected=statistics["selected"], quality_gates=statistics["quality_gates"],
                          formal_passed=statistics["passed"], statistics_sha256=hashlib.sha256(stats_path.read_bytes()).hexdigest())
        write_status(status_path, status)
        return 0 if normal_gate_stop else (completed.returncode if before == after else 1)


if __name__ == "__main__":
    raise SystemExit(main())
