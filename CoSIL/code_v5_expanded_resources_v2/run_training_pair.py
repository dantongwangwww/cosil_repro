"""Execute the frozen C judges sequentially on any naturally idle GPU.

This driver never chooses a winner, evaluates test, changes labels, downloads
weights, or controls another process. Invoke it from a persistent tmux session.
"""
from __future__ import annotations

import argparse
import csv
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


RESOURCE_POLICY = "any_naturally_idle_gpu_no_reservation_v2"
RESOURCE_AUTH = ROOT / "results/v5_pruner/C_dynamic_GPU_resource_authorization_v2.json"
PACKAGE_FILES = ("__init__.py", "train_judges.py", "race_and_calibrate.py",
                 "report_outcome.py", "run_training_pair.py", "run_sequence.py")
EXPECTED_PROFILES = {
    "reranker": {"rank": 8, "dropout": .1, "alpha": 32},
    "instruct": {"rank": 16, "dropout": 0., "alpha": 32},
}


def validate_resource_authorization(decision_file):
    """A separate root receipt binds this resource-only package to frozen C."""
    if not RESOURCE_AUTH.is_file():
        raise RuntimeError("No root C dynamic-GPU resource authorization")
    auth = json.loads(RESOURCE_AUTH.read_text())
    digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    old_code = {"code_v5_expanded/" + name: digest(ROOT / "code_v5_expanded" / name)
                for name in PACKAGE_FILES}
    new_code = {"code_v5_expanded_resources_v2/" + name:
                digest(ROOT / "code_v5_expanded_resources_v2" / name) for name in PACKAGE_FILES}
    if (auth.get("root_authorized") is not True or auth.get("allow_C_training") is not True
            or auth.get("test_open_allowed") is not False or auth.get("resource_policy") != RESOURCE_POLICY
            or auth.get("allowed_gpu_ids") != [0, 1, 2, 3] or auth.get("reserved_gpu_ids") != []
            or auth.get("peer_processes_may_be_modified") is not False
            or auth.get("allow_sharing_busy_gpu") is not False
            or auth.get("yield_on_foreign_gpu_use") is not True
            or auth.get("monitor_interval_seconds") != 10
            or auth.get("pause_action") != "terminate_own_child_preserve_completed_checkpoints"
            or auth.get("C_decision_sha256") != digest(decision_file)
            or auth.get("C_original_code_sha256") != old_code
            or auth.get("C_resources_v2_code_sha256") != new_code
            or auth.get("adapter_profiles") != EXPECTED_PROFILES
            or auth.get("data_policy") != "verified-plus-B-runtime-v1"):
        raise RuntimeError("Resource receipt differs from root C decision, frozen source, or no-sharing policy")
    return {"path": str(RESOURCE_AUTH), "sha256": digest(RESOURCE_AUTH), "policy": RESOURCE_POLICY,
            "allowed_gpu_ids": auth["allowed_gpu_ids"], "reserved_gpu_ids": [],
            "peer_processes_modified": False, "yield_on_foreign_gpu_use": True,
            "monitor_interval_seconds": 10}


def gpu_idle_reasons(snapshot, index):
    """Only this physical card must be empty; all non-Xorg contexts matter."""
    inventory = snapshot["inventory"]
    if index not in inventory:
        return [f"GPU{index} unavailable in inventory"]
    record = inventory[index]
    reasons = []
    if record["memory_mib"] > 128:
        reasons.append(f"GPU{index} memory {record['memory_mib']} MiB")
    if record["utilization"] != 0:
        reasons.append(f"GPU{index} utilization {record['utilization']}%")
    for process in snapshot["full_processes"]:
        if process["gpu_uuid"] != record["uuid"]:
            continue
        if process["type"] == "G" and Path(process["process_name"]).name == "Xorg":
            continue
        reasons.append(f"GPU{index} pid {process['pid']} type {process['type']}")
    for row in csv.reader(snapshot.get("compute_apps", [])):
        if row and row[0].strip() == record["uuid"]:
            reasons.append(f"GPU{index} compute pid {row[1].strip()}")
    return reasons


def idle_gpu_ids(snapshot, allowed_gpu_ids):
    return [index for index in allowed_gpu_ids if not gpu_idle_reasons(snapshot, index)]


def gpu_preflight(*, wait_for_idle=False, wait_status_path=None,
                  allowed_gpu_ids=(0, 1, 2, 3), assigned_gpu=None):
    """Wait naturally for any idle card, or recheck an already chosen card."""
    candidates = list(allowed_gpu_ids) if assigned_gpu is None else [assigned_gpu]
    if (not candidates or any(type(index) is not int or index not in allowed_gpu_ids
                              for index in candidates)):
        raise RuntimeError("Only actually authorized physical GPU IDs can be selected")
    began = time.monotonic()
    snapshots = []
    while True:
        snapshot = _gpu_inventory()
        snapshots.append(snapshot)
        idle = idle_gpu_ids(snapshot, candidates)
        busy = {str(index): gpu_idle_reasons(snapshot, index) for index in candidates}
        if idle:
            return {**snapshot, "snapshots": snapshots, "waited_seconds": time.monotonic() - began,
                    "assigned": idle[0], "reserved_free_gpu_ids": [], "allowed_gpu_ids": list(allowed_gpu_ids),
                    "resource_policy": RESOURCE_POLICY, "peer_processes_modified_by_this_experiment": False}
        if wait_for_idle:
            if wait_status_path is not None:
                write_status(Path(wait_status_path), {"time": now(), "stage": "waiting_for_natural_gpu_idle",
                    "waited_seconds": time.monotonic() - began, "latest": snapshot, "busy_reasons": busy,
                    "candidate_gpu_ids": candidates, "reserved_free_gpu_ids": [], "poll_interval_seconds": 30,
                    "peer_processes_stopped_or_modified": False, "model_loaded": False})
            # Keep bounded memory while retaining each snapshot in a journal.
            if wait_status_path is not None:
                with Path(wait_status_path).with_suffix(".jsonl").open("a") as stream:
                    stream.write(json.dumps({"time": now(), "busy_reasons": busy, "snapshot": snapshot}) + "\n")
            snapshots = snapshots[-2:]
            time.sleep(30)
            continue
        raise RuntimeError("No authorized GPU naturally idle; preserve peers: " + json.dumps(busy))


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


def foreign_gpu_processes(snapshot, index, own_child_pid):
    """Observe peers, but never use an observed GPU PID as a stop target."""
    record = snapshot["inventory"][index]
    foreign = {}
    for process in snapshot["full_processes"]:
        if process["gpu_uuid"] != record["uuid"] or process["pid"] == own_child_pid:
            continue
        if process["type"] == "G" and Path(process["process_name"]).name == "Xorg":
            continue
        foreign[process["pid"]] = process
    for row in csv.reader(snapshot.get("compute_apps", [])):
        if row and row[0].strip() == record["uuid"] and int(row[1].strip()) != own_child_pid:
            pid = int(row[1].strip())
            foreign.setdefault(pid, {"gpu_uuid": record["uuid"], "pid": pid,
                                     "type": "compute_apps", "process_name": row[2].strip()})
    return list(foreign.values())


def run_monitored_child(command, *, environment, log, physical_gpu, monitor_interval_seconds=10):
    """Yield only our directly spawned training child if a peer arrives.

    No automatic restart: last completed checkpoint and every partial artifact
    remain available for root to audit before a same-manifest resume decision.
    """
    child = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    while True:
        try:
            return {"own_child_pid": child.pid, "returncode": child.wait(timeout=monitor_interval_seconds),
                    "paused": False, "peer_processes_stopped_or_modified": False}
        except subprocess.TimeoutExpired:
            try:
                snapshot = _gpu_inventory()
                foreign = foreign_gpu_processes(snapshot, physical_gpu, child.pid)
                if not foreign:
                    continue
                reason = "foreign_GPU_context_arrived"
            except Exception as error:
                snapshot, foreign = None, []
                reason = "GPU_observation_unavailable: " + type(error).__name__ + ": " + str(error)
            # The stop target is the Popen object we created, never a GPU PIDS
            # table entry. Other experiments and services are never controlled.
            child.terminate()
            try:
                returncode = child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                returncode = child.wait(timeout=30)
            return {"own_child_pid": child.pid, "returncode": returncode, "paused": True,
                    "pause_reason": reason, "foreign_GPU_observation": foreign, "snapshot": snapshot,
                    "stopped_only_own_direct_child": True, "peer_processes_stopped_or_modified": False,
                    "completed_checkpoint_and_partial_logs_preserved": True,
                    "automatic_resume_performed": False}


C_QUEUE_RELEASE = ROOT / "results/v5_pruner/C_training_queue_release.json"
B_RUN = ROOT / "results/v5_pruner/B_runtime_reviewed_regularized_exploratory"
B_AUTH = ROOT / "results/v5_pruner/B_runtime_filtered_regularized_authorization_exploratory/root_exploratory_decision.json"


def validate_queue_release(decision_file):
    """Require root's exact completed-B release before any C model can load."""
    resource = validate_resource_authorization(decision_file)
    required = (C_QUEUE_RELEASE, B_RUN / "outcome/assessment_report.json",
                B_RUN / "sequence_status.json", B_RUN / "training/pair_status.json", B_AUTH)
    if any(not path.is_file() for path in required):
        raise RuntimeError("C waits for a real complete B pair/race/report and separate root queue release")
    receipt = json.loads(C_QUEUE_RELEASE.read_text())
    report = json.loads((B_RUN / "outcome/assessment_report.json").read_text())
    state = json.loads((B_RUN / "sequence_status.json").read_text())
    pair = json.loads((B_RUN / "training/pair_status.json").read_text())
    digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if (receipt.get("allow_C_training") is not True or receipt.get("test_open_allowed") is not False
            or receipt.get("resource_authorization_sha256") != resource["sha256"]
            or receipt.get("resource_policy") != RESOURCE_POLICY
            or receipt.get("C_decision_sha256") != digest(decision_file)
            or receipt.get("B_assessment_report_sha256") != digest(B_RUN / "outcome/assessment_report.json")
            or receipt.get("B_decision_sha256") != digest(B_AUTH)
            or report.get("test_opened") is not False or set(report.get("models", {})) != {"reranker", "instruct"}
            or pair.get("stage") != "complete" or state.get("stage") != "complete"
            or pair.get("test_opened") is not False or state.get("test_opened") is not False):
        raise RuntimeError("C queue release is not bound to its authorization and the fully completed B")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--track", choices=("exploratory",), required=True)
    parser.add_argument("--decision-file", type=Path, required=True)
    parser.add_argument("--effective-batch", type=int, choices=(8,), default=8)
    parser.add_argument("--micro-batch", type=int, choices=(2,), default=2)
    parser.add_argument("--data-policy", choices=("verified-plus-B-runtime-v1",), default="verified-plus-B-runtime-v1")
    parser.add_argument("--wait-for-idle", action="store_true")
    args = parser.parse_args()
    if not args.wait_for_idle:
        raise RuntimeError("C always waits for natural idle; no peer job is stopped or modified")
    from code_v5_verified.expanded_policy import validate_decision
    validate_decision(args.data_dir, args.decision_file)
    validate_queue_release(args.decision_file)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "pair.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status_path = output / "pair_status.json"
        if status_path.exists():
            raise FileExistsError("Pair directory already has an attempt; preserve it and use a new directory")
        status = {"started_at": now(), "track": args.track, "stage": "preflight", "runs": [],
                  "resource_policy": RESOURCE_POLICY, "allowed_gpu_ids": [0, 1, 2, 3],
                  "reserved_free_gpu_ids": [], "test_opened": False,
                  "effective_batch": args.effective_batch, "micro_batch": args.micro_batch}
        write_status(status_path, status)
        try:
            for kind, model in (("reranker", "Qwen3-Reranker-0.6B"), ("instruct", "Qwen2.5-0.5B-Instruct")):
                status["stage"] = "waiting_for_natural_gpu_idle"
                write_status(status_path, status)
                run = {"kind": kind, "started_at": now(), "gpu_preflight": gpu_preflight(
                    wait_for_idle=args.wait_for_idle, wait_status_path=output / "gpu_wait_status.json")}
                selected_gpu = run["gpu_preflight"]["assigned"]
                status["stage"] = kind
                status["runs"].append(run)
                command = [sys.executable, "-u", "-m", "code_v5_expanded_resources_v2.train_judges", "--kind", kind,
                           "--model-dir", str(ROOT / "models_v5" / model), "--data-dir", str(args.data_dir.resolve()),
                           "--output-dir", str(output / kind), "--gpu", str(selected_gpu), "--track", args.track,
                           "--effective-batch", str(args.effective_batch), "--micro-batch", str(args.micro_batch)]
                command.extend(["--data-policy", args.data_policy])
                if args.decision_file is not None:
                    command.extend(["--decision-file", str(args.decision_file.resolve())])
                run["command"] = command
                run["log"] = str(output / (kind + ".log"))
                write_status(status_path, status)
                environment = dict(os.environ, CUDA_VISIBLE_DEVICES=str(selected_gpu), TOKENIZERS_PARALLELISM="false")
                began = time.perf_counter()
                with Path(run["log"]).open("x") as log:
                    monitored = run_monitored_child(command, environment=environment, log=log,
                                                    physical_gpu=selected_gpu)
                run.update(finished_at=now(), returncode=monitored["returncode"], resource_monitor=monitored,
                           elapsed_seconds=time.perf_counter() - began)
                write_status(status_path, status)
                if monitored["paused"]:
                    status.update(stage="paused_due_to_foreign_GPU_use_or_observation_failure", finished_at=now(),
                                  pause_reason=monitored["pause_reason"], automatic_resume_performed=False,
                                  completed_checkpoints_preserved=True, test_opened=False)
                    write_status(status_path, status)
                    return 75
                if monitored["returncode"]:
                    raise RuntimeError(f"{kind} training failed with exit code {monitored['returncode']}; inspect its preserved log")
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
