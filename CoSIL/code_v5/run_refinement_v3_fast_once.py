"""Persist the equivalent cached implementation of the final v3 data rules."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

from code_v5.run_training_pair import ROOT, now, write_status

EXPECTED = {"refine_pruner_data_v3.py": "18075ca5a26c85bf2a692d74907460176061e00d8ca24bfad8038739d8a9b3e5",
            "refine_pruner_data_v3_fast.py": "bd3f16cb6130824204e78edd3a483540d2958d8b17cf7f3ce5f479650a0c16ec",
            "ast_source_cache.py": "c461a6232936847812e3e279c771f1eac5965182c78cb193603c73f0881e12d9"}


def hashes():
    return {name: hashlib.sha256((ROOT / "code_v5" / name).read_bytes()).hexdigest() for name in EXPECTED}


def main():
    work = ROOT / "results/v5_pruner"
    status_path = work / "refinement_v3_fast_status.json"
    before = hashes()
    if before != EXPECTED:
        raise RuntimeError("Frozen v3 rule or equivalent fast implementation changed")
    with (work / "refinement_v3.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if status_path.exists() or (work / "data_v3").exists():
            raise FileExistsError("A fast final v3 attempt already exists; no automatic retry or overwrite")
        command = [sys.executable, "-u", "-m", "code_v5.refine_pruner_data_v3_fast",
                   "--source-data", str(work / "data"), "--previous-data", str(work / "data_v2"),
                   "--v1-review-results", str(work / "review_v1_for_refiner.jsonl"),
                   "--v2-review-results", str(work / "data_v2/human_review_codex_reviewed.jsonl"),
                   "--output", str(work / "data_v3")]
        status = {"started_at": now(), "stage": "running", "pid": os.getpid(), "command": command,
                  "source_sha256_before": before, "final_data_repair_round": True, "same_v3_rules": True,
                  "optimization_only": "unchanged stdlib AST line splitter cached; fresh list semantics",
                  "test_performance_opened": False, "model_calls": 0, "log": str(work / "refinement_v3_fast.log")}
        write_status(status_path, status)
        began = time.perf_counter()
        with (work / "refinement_v3_fast.log").open("x") as log:
            completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        stats_path = work / "data_v3/statistics.json"
        after = hashes()
        normal_gate_stop = completed.returncode == 2 and stats_path.exists() and after == before
        status.update(finished_at=now(), returncode=completed.returncode,
                      elapsed_seconds=time.perf_counter() - began, source_sha256_after=after,
                      source_unchanged=before == after,
                      stage="awaiting_actual_QC" if normal_gate_stop else ("complete" if completed.returncode == 0 and before == after else "failed"))
        if stats_path.exists():
            statistics = json.loads(stats_path.read_text())
            status.update(selected=statistics["selected"], quality_gates=statistics["quality_gates"],
                          formal_passed=statistics["passed"], statistics_sha256=hashlib.sha256(stats_path.read_bytes()).hexdigest(),
                          fast_implementation=statistics.get("fast_implementation"))
        write_status(status_path, status)
        return 0 if normal_gate_stop else (completed.returncode if before == after else 1)


if __name__ == "__main__":
    raise SystemExit(main())
