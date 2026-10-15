"""Persistent authorized 60 canaries, then one small/hybrid300 sequence.

Default is a CPU authorization check. --execute runs the original fixed cases,
technical gate and judge interfaces, with separately recorded shared resources.
No full Qwen300, paid API, test re-selection, or peer process control.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys

from code_v5.run_pipeline import now, write_new, write_derived
from code_v5_postexploratory.authority import AUTH, PIPELINE_OUTPUT, validate_authority


def execute(authorization, *, workers=2, through_full=False):
    auth, winner, auth_sha = validate_authority(authorization, "pipeline")
    from code_v5_postexploratory.run_pipeline import assess_canaries, select_inputs, inference_core
    from code_v5_expanded_resources_v3.run_training_pair import gpu_preflight, run_monitored_child
    if PIPELINE_OUTPUT.exists():
        raise FileExistsError("Preserve prior sequence/output; no automatic favorable rerun")
    PIPELINE_OUTPUT.mkdir(parents=True)
    state_path = PIPELINE_OUTPUT / "sequence_status.json"
    state = {"started_at": now(), "stage": "preflight", "authorization_sha256": auth_sha,
        "winner_sha256": auth["winner_sha256"], "through_full": through_full,
        "stage_kind": "postexploratory_evaluation", "selection_used_test": False,
        "resource_policy": auth["resource_policy"], "reserved_gpu_ids": [],
        "peer_processes_stopped_or_modified": False, "runs": []}
    write_new(state_path, state)
    with (PIPELINE_OUTPUT / "sequence.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            phases = [("canary", mode, repeat) for mode in ("qwen", "small", "hybrid") for repeat in (1,2)]
            if through_full:
                phases += [("full", mode, 1) for mode in ("small", "hybrid")]
            for phase, mode, repeat in phases:
                if phase == "full":
                    _, core_sha = inference_core()
                    ids, _, _ = select_inputs("canary")
                    gate = assess_canaries(PIPELINE_OUTPUT, ids, core_sha=core_sha, winner_sha=auth["winner_sha256"])
                    if gate["passed"] is not True:
                        raise RuntimeError("Frozen 60-run technical/stability gate failed; full remains closed")
                if mode == "qwen":
                    gpu, preflight = 0, {"local_judge_loaded": False, "local_GPU_allocated": False,
                                         "Qwen": "existing service only"}
                else:
                    preflight = gpu_preflight(wait_for_idle=True,
                        wait_status_path=PIPELINE_OUTPUT / f"{phase}_{mode}_{repeat}_resource_wait.json",
                        allowed_gpu_ids=auth["allowed_gpu_ids"], minimum_free_mib=auth["minimum_free_mib"])
                    gpu = preflight["assigned"]
                command = [sys.executable, "-u", "-m", "code_v5_postexploratory.run_pipeline",
                    "--phase", phase, "--mode", mode, "--repeat", str(repeat),
                    "--winner-file", auth["winner_file"], "--output-dir", str(PIPELINE_OUTPUT),
                    "--gpu", str(gpu), "--workers", str(workers)]
                record = {"phase": phase, "mode": mode, "repeat": repeat, "started_at": now(),
                    "command": command, "gpu_preflight": preflight, "physical_judge_gpu": gpu if mode != "qwen" else None}
                state.update(stage=f"{phase}/{mode}/{repeat}")
                state["runs"].append(record)
                write_derived(state_path, state)
                log_path = PIPELINE_OUTPUT / f"{phase}_{mode}_{repeat}.log"
                with log_path.open("x") as log:
                    monitor = run_monitored_child(command,
                        environment=dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), TOKENIZERS_PARALLELISM="false"),
                        log=log, physical_gpu=gpu,
                        observation_path=PIPELINE_OUTPUT / f"{phase}_{mode}_{repeat}_resource_observations.jsonl")
                record.update(finished_at=now(), returncode=monitor["returncode"], resource_monitor=monitor)
                write_derived(state_path, state)
                if monitor["returncode"]:
                    raise RuntimeError(f"{phase}/{mode}/{repeat} failed; preserve logs and partial cases")
                folder = PIPELINE_OUTPUT / phase / mode
                if phase == "canary": folder /= f"repeat_{repeat}"
                summary = json.loads((folder / "phase_summary.json").read_text())
                record["summary"] = summary
                if summary["failed"] or summary["missing"] or summary["completed"] != summary["expected"]:
                    raise RuntimeError(f"{phase}/{mode}/{repeat} has failed/missing cases")
                write_derived(state_path, state)
            _, core_sha = inference_core()
            ids, _, _ = select_inputs("canary")
            gate = assess_canaries(PIPELINE_OUTPUT, ids, core_sha=core_sha, winner_sha=auth["winner_sha256"])
            state.update(stage="complete" if gate["passed"] else "canary_failed", finished_at=now(), canary_gate=gate)
            write_derived(state_path, state)
            return 0 if gate["passed"] else 2
        except Exception as error:
            state.update(stage="failed", finished_at=now(), error=f"{type(error).__name__}: {error}")
            write_derived(state_path, state)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--workers", type=int, choices=(1,2), default=2)
    parser.add_argument("--through-full", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute:
        return execute(args.authorization, workers=args.workers, through_full=args.through_full)
    auth, winner, digest = validate_authority(args.authorization, "check")
    print(json.dumps({"checked": True, "authorization_sha256": digest, "execute": False,
                      "model_loaded": False, "original_test_reopened": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
