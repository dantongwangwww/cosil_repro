"""Persistently execute the two frozen local judge trainings on GPU2 only.

This driver never chooses a winner, evaluates test, changes labels, downloads
weights, or controls another process. Invoke it from a persistent tmux session.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def write_status(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def gpu_preflight(*, wait_for_idle=False, wait_status_path=None):
    """Read GPU inventory; refuse to train if assigned or reserved cards are busy."""
    began = time.monotonic()
    snapshots = []
    while True:
        snapshot = _gpu_inventory()
        snapshots.append(snapshot)
        busy = []
        for index in (2, 3):
            record = snapshot["inventory"][index]
            if record["memory_mib"] > 128:
                busy.append(f"GPU{index} memory {record['memory_mib']} MiB")
            # Query-compute-apps can omit simulator C+G contexts. The complete
            # XML PIDS table is authoritative; only resident Xorg G is ignored.
            for process in snapshot["full_processes"]:
                if process["gpu_uuid"] != record["uuid"]:
                    continue
                if process["type"] == "G" and Path(process["process_name"]).name == "Xorg":
                    continue
                busy.append(f"GPU{index} pid {process['pid']} type {process['type']}")
        if not busy and all(snapshot["inventory"][index]["utilization"] == 0 for index in (2, 3)):
            return {**snapshot, "snapshots": snapshots, "waited_seconds": time.monotonic() - began,
                    "assigned": 2, "reserved_free": 3, "other_processes_changed": False}
        if wait_for_idle:
            if wait_status_path is not None:
                write_status(Path(wait_status_path), {"time": now(), "stage": "waiting_for_natural_gpu_idle",
                    "waited_seconds": time.monotonic() - began, "latest": snapshot, "busy_reasons": busy,
                    "assigned_gpu": 2, "reserved_free_gpu": 3, "poll_interval_seconds": 30,
                    "peer_processes_stopped_or_modified": False, "model_loaded": False})
            # Keep bounded memory while retaining each snapshot in a journal.
            if wait_status_path is not None:
                with Path(wait_status_path).with_suffix(".jsonl").open("a") as stream:
                    stream.write(json.dumps({"time": now(), "busy_reasons": busy, "snapshot": snapshot}) + "\n")
            snapshots = snapshots[-2:]
            time.sleep(30)
            continue
        if busy:
            raise RuntimeError("Assigned/reserved GPU busy; preserve peers: " + "; ".join(busy))
        # A utilization sample may briefly lag the just-finished local child.
        # Only wait when memory and process lists are already empty; never stop
        # or wait through an actual peer job or automatically retry a phase.
        if time.monotonic() - began >= 10:
            raise RuntimeError("GPU2/3 utilization remained nonzero for 10 seconds despite empty process/memory checks")
        time.sleep(1)


def _gpu_inventory():
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.used,utilization.gpu",
                          "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True)
    applications = subprocess.run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory",
                                   "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True)
    # NVIDIA-SMI does not allow the display selector together with XML output.
    # Full XML still includes the complete PIDS table, including C+G contexts.
    pids = subprocess.run(["nvidia-smi", "-q", "-x"], capture_output=True, text=True, check=True)
    full_processes = []
    for node in ET.fromstring(pids.stdout).findall("gpu"):
        for process in node.findall("./processes/process_info"):
            full_processes.append({"gpu_uuid": node.findtext("uuid"),
                "pid": int(process.findtext("pid")), "type": process.findtext("type"),
                "process_name": process.findtext("process_name") or "",
                "used_memory": process.findtext("used_memory")})
    inventory = {}
    for line in gpu.stdout.splitlines():
        index, uuid, memory, utilization = [part.strip() for part in line.split(",")]
        inventory[int(index)] = {"uuid": uuid, "memory_mib": int(memory), "utilization": int(utilization)}
    return {"time": now(), "inventory": inventory, "compute_apps": applications.stdout.splitlines(),
            "full_processes": full_processes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--track", choices=("formal", "exploratory"), required=True)
    parser.add_argument("--decision-file", type=Path)
    parser.add_argument("--effective-batch", type=int, choices=(4, 8), default=8)
    parser.add_argument("--micro-batch", type=int, choices=(1, 2), default=2)
    parser.add_argument("--data-policy", choices=("original", "runtime-covered-v3"), default="original")
    parser.add_argument("--wait-for-idle", action="store_true")
    args = parser.parse_args()
    if args.data_policy == "runtime-covered-v3":
        completed_A = ROOT / "results/v5_pruner/A_v3_noise_disclosed_outcome_exploratory/assessment_report.json"
        if not completed_A.exists():
            raise RuntimeError("B must wait until the complete A pair/race/report exists; never take A inter-model GPU window")
        A_report = json.loads(completed_A.read_text())
        A_pair = json.loads((ROOT / "results/v5_pruner/A_v3_noise_disclosed_training_exploratory/pair_status.json").read_text())
        if A_pair["stage"] != "complete" or A_report.get("test_opened") is not False or set(A_report.get("models", {})) != {"reranker", "instruct"}:
            raise RuntimeError("A is not completely assessed and published yet")
        branch_receipt_path = ROOT / "results/v5_pruner/A_branch_processing_receipt.json"
        if not branch_receipt_path.exists():
            raise RuntimeError("Root must complete A conditional branch processing before B may use GPU2")
        branch_receipt = json.loads(branch_receipt_path.read_text())
        regularized_result = ROOT / "results/v5_pruner/A_rank8_dropout01_exploratory/outcome/assessment_report.json"
        regularized_state = ROOT / "results/v5_pruner/A_rank8_dropout01_exploratory/sequence_status.json"
        if not regularized_result.exists() or not regularized_state.exists():
            raise RuntimeError("B must wait for the real rank8/dropout0.1 A prescription outcome")
        regularized_report = json.loads(regularized_result.read_text())
        if (branch_receipt.get("A_branch_processing_complete") is not True
                or branch_receipt.get("allow_B_training") is not True
                or branch_receipt.get("A_assessment_report_sha256") != hashlib.sha256(completed_A.read_bytes()).hexdigest()
                or branch_receipt.get("A_regularized_assessment_report_sha256") != hashlib.sha256(regularized_result.read_bytes()).hexdigest()
                or regularized_report.get("test_opened") is not False
                or json.loads(regularized_state.read_text())["stage"] != "complete"):
            raise RuntimeError("A conditional retry/expansion branch is not cleared for this exact A assessment")
    if args.data_policy == "runtime-covered-v3":
        from code_v5.runtime_filtered_policy import validate_decision
        if args.track != "exploratory" or args.decision_file is None or not args.wait_for_idle:
            raise RuntimeError("Runtime-covered pair needs its explicit exploratory authorization and natural-idle waiting")
        validate_decision(args.data_dir, args.decision_file)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "pair.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status_path = output / "pair_status.json"
        if status_path.exists():
            raise FileExistsError("Pair directory already has an attempt; preserve it and use a new directory")
        status = {"started_at": now(), "track": args.track, "stage": "preflight", "runs": [],
                  "physical_gpu": 2, "reserved_free_gpu": 3, "test_opened": False,
                  "effective_batch": args.effective_batch, "micro_batch": args.micro_batch}
        write_status(status_path, status)
        try:
            for kind, model in (("reranker", "Qwen3-Reranker-0.6B"), ("instruct", "Qwen2.5-0.5B-Instruct")):
                status["stage"] = "waiting_for_natural_gpu_idle"
                write_status(status_path, status)
                run = {"kind": kind, "started_at": now(), "gpu_preflight": gpu_preflight(
                    wait_for_idle=args.wait_for_idle, wait_status_path=output / "gpu_wait_status.json")}
                status["stage"] = kind
                status["runs"].append(run)
                command = [sys.executable, "-u", "-m", "code_v5_runtime.train_judges", "--kind", kind,
                           "--model-dir", str(ROOT / "models_v5" / model), "--data-dir", str(args.data_dir.resolve()),
                           "--output-dir", str(output / kind), "--gpu", "2", "--track", args.track,
                           "--effective-batch", str(args.effective_batch), "--micro-batch", str(args.micro_batch)]
                command.extend(["--data-policy", args.data_policy])
                if args.decision_file is not None:
                    command.extend(["--decision-file", str(args.decision_file.resolve())])
                run["command"] = command
                run["log"] = str(output / (kind + ".log"))
                write_status(status_path, status)
                environment = dict(os.environ, CUDA_VISIBLE_DEVICES="2", TOKENIZERS_PARALLELISM="false")
                began = time.perf_counter()
                with Path(run["log"]).open("x") as log:
                    completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
                                               stderr=subprocess.STDOUT, check=False)
                run.update(finished_at=now(), returncode=completed.returncode,
                           elapsed_seconds=time.perf_counter() - began)
                write_status(status_path, status)
                if completed.returncode:
                    raise RuntimeError(f"{kind} training failed with exit code {completed.returncode}; inspect its preserved log")
            # Peers may naturally start while our last child exits. Only report
            # resource release; never require other people's GPUs to be empty.
            status.update(stage="complete", finished_at=now(), gpu_final=_gpu_inventory(),
                          postflight_policy="Our children completed and exited; peer allocations are only observed")
            write_status(status_path, status)
            return 0
        except Exception as error:
            status.update(stage="failed", finished_at=now(), error=f"{type(error).__name__}: {error}")
            write_status(status_path, status)
            raise


if __name__ == "__main__":
    raise SystemExit(main())
