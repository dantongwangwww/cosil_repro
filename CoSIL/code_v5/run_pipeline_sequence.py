"""Durably run the exact 60 canaries, then authorized small/hybrid300.

Only a frozen validation-qualified winner is accepted. Full Qwen is never
launched. Test and all selection decisions stay outside this driver.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from code_v5.run_pipeline import (assess_canaries, inference_core, load_winner,
                                  select_inputs, validate_output)
from code_v5.run_training_pair import ROOT, gpu_preflight, now, write_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--winner-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--through-full", action="store_true")
    args = parser.parse_args()
    winner, winner_sha = load_winner(args.winner_file)
    if winner.get("qualified_on_val") is not True:
        raise RuntimeError("Pipeline sequence requires a validation-qualified frozen winner")
    output = validate_output(args.output_dir, winner["track"])
    output.mkdir(parents=True, exist_ok=True)
    status_path = output / "sequence_status.json"
    with (output / "sequence.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if status_path.exists():
            raise FileExistsError("Sequence attempt already exists; inspect artifacts before explicit repair/resume")
        status = {"started_at": now(), "stage": "preflight", "track": winner["track"],
                  "winner_file": str(args.winner_file.resolve()), "winner_sha256": winner_sha,
                  "through_full": args.through_full, "physical_gpu": 2, "reserved_free_gpu": 3,
                  "test_labels_read": False, "runs": []}
        write_status(status_path, status)
        try:
            phases = [("canary", mode, repeat) for mode in ("qwen", "small", "hybrid") for repeat in (1, 2)]
            if args.through_full:
                phases.extend(("full", mode, 1) for mode in ("small", "hybrid"))
            for phase, mode, repeat in phases:
                if phase == "full":
                    _, core_sha = inference_core()
                    ids, _, _ = select_inputs("canary")
                    gate = assess_canaries(output, ids, core_sha=core_sha, winner_sha=winner_sha)
                    if not gate["passed"]:
                        raise RuntimeError("Frozen 60 canaries failed; no full small/hybrid is launched")
                folder = output / phase / mode
                if phase == "canary":
                    folder /= f"repeat_{repeat}"
                run = {"phase": phase, "mode": mode, "repeat": repeat, "started_at": now(),
                       "gpu_preflight": gpu_preflight()}
                status.update(stage=f"{phase}/{mode}/{repeat}")
                status["runs"].append(run)
                command = [sys.executable, "-u", "-m", "code_v5.run_pipeline", "--phase", phase,
                           "--mode", mode, "--repeat", str(repeat), "--winner-file", str(args.winner_file.resolve()),
                           "--output-dir", str(output), "--gpu", "2", "--workers", str(args.workers)]
                log_path = output / f"{phase}_{mode}_{repeat}.log"
                run.update(command=command, log=str(log_path))
                write_status(status_path, status)
                environment = dict(os.environ, CUDA_VISIBLE_DEVICES="2", TOKENIZERS_PARALLELISM="false")
                began = time.perf_counter()
                with log_path.open("x") as log:
                    completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
                                               stderr=subprocess.STDOUT, check=False)
                run.update(finished_at=now(), returncode=completed.returncode,
                           elapsed_seconds=time.perf_counter() - began)
                if completed.returncode:
                    raise RuntimeError(f"{phase}/{mode}/{repeat} failed with code {completed.returncode}; inspect preserved log")
                summary = json.loads((folder / "phase_summary.json").read_text())
                run["summary"] = summary
                write_status(status_path, status)
                if summary["failed"] or summary["missing"] or summary["completed"] != summary["expected"]:
                    raise RuntimeError(f"{phase}/{mode}/{repeat} has failed/missing cases; repair before further stages")
            _, core_sha = inference_core()
            ids, _, _ = select_inputs("canary")
            gate = assess_canaries(output, ids, core_sha=core_sha, winner_sha=winner_sha)
            status.update(stage="complete" if gate["passed"] else "canary_failed", finished_at=now(),
                          canary_gate=gate, gpu_final=gpu_preflight())
            write_status(status_path, status)
            return 0 if gate["passed"] else 2
        except Exception as error:
            status.update(stage="failed", finished_at=now(), error=f"{type(error).__name__}: {error}")
            write_status(status_path, status)
            raise


if __name__ == "__main__":
    raise SystemExit(main())
