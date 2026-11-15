#!/usr/bin/env python3
"""Durable controller for only the frozen 180 previously unstarted tasks.

The frozen worker/runner own all localization behavior. This module only
queues two tasks, preserves terminal attempts, records progress, and diagnoses
infrastructure interruptions. It never imports an evaluator or starts/stops
a model service. All model HTTP calls remain in the isolated official worker.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.request

SOURCE = Path(__file__).resolve().parents[1]
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
from reproduction.controller import failure, read, recover_usage, sha, write
from reproduction.service import proc

RUNTIME_FILES = ("reproduction/worker.py", "reproduction/runner.py",
                 "reproduction/requirements-runtime.txt", "auto_search_main.py")
ENDPOINT = "http://127.0.0.1:7353/v1/models"
STOP = threading.Event()
TOKENIZER_CACHE_FILES = {
    "9b5ad71b2ce5302211f9c61530b329a4922fc6a4": "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7",
    "fb374d419588a4632f3f557e76b4b70aebbca790": "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d",
}


class InfrastructureBlocked(RuntimeError):
    """Unstarted work is retained; infrastructure is not a model failure."""


def validate_tokenizer_cache(run):
    """Read-only check of the two exact previously prewarmed tiktoken files.

    These are cl100k_base/o200k_base content hashes; missing data must never
    trigger an implicit download inside a worker or consume a task attempt.
    """
    cache = run / "public/tokenizer_cache"
    for filename, expected in TOKENIZER_CACHE_FILES.items():
        path = cache / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise InfrastructureBlocked(f"Required prewarmed tokenizer cache missing/empty: {path}")
        if sha(path) != expected:
            raise InfrastructureBlocked(f"Prewarmed tokenizer cache content hash mismatch: {path}")
    return {"path": str(cache), "files_sha256": dict(TOKENIZER_CACHE_FILES)}


def preparation_ready(run):
    receipt = read(run / "selection/extension_preparation_receipt.json")
    if (receipt.get("status") != "FROZEN_READY" or receipt.get("full_n") != 280
            or receipt.get("new_execution_n") != 180 or receipt.get("reused_n") != 100
            or receipt.get("full_manifest_sha256") != sha(run / "selection/manifest.json")
            or receipt.get("extension_manifest_sha256") != sha(run / "selection/extension_manifest.json")):
        raise ValueError("Frozen preparation barrier or manifest hashes do not match")
    return receipt


def validate_rosters(run):
    preparation_ready(run)
    validate_tokenizer_cache(run)
    full = read(run / "selection/manifest.json")
    extension = read(run / "selection/extension_manifest.json")
    records = extension["records"]
    full_ids = [r["instance_id"] for r in full["records"]]
    new_ids = [r["instance_id"] for r in records]
    if len(full_ids) != 280 or len(set(full_ids)) != 280:
        raise ValueError("Exactly 280 unique frozen full tasks are required")
    if len(new_ids) != 180 or len(set(new_ids)) != 180 or not set(new_ids) < set(full_ids):
        raise ValueError("Exactly 180 unique extension tasks, a subset of the 280, are required")
    old = {r["instance_id"] for r in full["records"] if r.get("execution_origin") == "existing100_reuse"}
    if len(old) != 100 or old & set(new_ids) or old | set(new_ids) != set(full_ids):
        raise ValueError("Old 100 and new 180 must be explicitly disjoint and exhaustive")
    full_by_id = {r["instance_id"]: r for r in full["records"]}
    for record in records:
        iid = record["instance_id"]
        if not isinstance(iid, str) or iid in {".", ".."} or "/" in iid:
            raise ValueError("Unsafe instance ID")
        for key in ("repo", "base_commit", "instance", "snapshot"):
            if record[key] != full_by_id[iid][key]:
                raise ValueError(f"Extension/full identity mismatch: {iid}/{key}")
        instance = read(run / record["instance"])
        if set(instance) != {"instance_id", "repo", "base_commit", "problem_statement"}:
            raise ValueError("Only the four public fields may be provided to a worker")
        if any(instance[k] != record[k] for k in ("instance_id", "repo", "base_commit")):
            raise ValueError("Public instance identity mismatch")
        if record.get("instance_sha256") and sha(run / record["instance"]) != record["instance_sha256"]:
            raise ValueError("Public instance hash mismatch")
    return records


def freeze_controller(run, records):
    path = run / "controller_extension/protocol.json"
    frozen = {"full_manifest_sha256": sha(run / "selection/manifest.json"),
              "extension_manifest_sha256": sha(run / "selection/extension_manifest.json"),
              "preparation_receipt_sha256": sha(run / "selection/extension_preparation_receipt.json"),
              "tokenizer_cache": validate_tokenizer_cache(run),
              "runtime_sha256": {p: sha(SOURCE / p) for p in RUNTIME_FILES},
              "controller_sha256": sha(Path(__file__)),
              "tasks": [r["instance_id"] for r in records], "workers": 2,
              "unchanged_protocol": {"samples": 2, "sample_seconds": 900,
                  "soft_turns": 20, "hard_completions": 21, "output_tokens": 2048,
                  "context_tokens": 65536, "temperature": 1.0, "top_p": 0.8,
                  "thinking": False, "model": "qwen3-8b"},
              "no_semantic_resampling": True, "gold_access": False,
              "service_lifecycle_managed_externally": True}
    if path.exists():
        previous = read(path)
        if any(previous.get(k) != v for k, v in frozen.items()):
            raise ValueError("Frozen controller, roster, or runtime changed")
        return previous
    frozen["frozen_time"] = time.time()
    write(path, frozen)
    return frozen


def same_process(identity):
    if not identity:
        return False
    current = proc(identity["pid"])
    return bool(current and current["uid"] == identity["uid"] == os.getuid()
                and current["start_ticks"] == identity["start_ticks"]
                and current["cmd"] == identity["cmd"]
                and current["pgid"] == identity["pid"])


def terminate_owned(identity, grace=10):
    """Signal only a verified process group this controller durably launched."""
    if not same_process(identity):
        return False
    os.killpg(identity["pid"], signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and same_process(identity):
        time.sleep(0.2)
    if same_process(identity):
        os.killpg(identity["pid"], signal.SIGKILL)
    return True


def terminal_result(work, record):
    path = work / "result.json"
    if not path.exists():
        return None
    result = read(path)
    if result.get("terminal") is not True:
        return None
    if result.get("status") not in {"complete", "partial", "failed"}:
        raise ValueError("Unknown terminal status")
    if any(result.get(k) != record[k] for k in ("instance_id", "repo", "base_commit")):
        raise ValueError("Terminal result identity does not match frozen task")
    return result


def recover_previous(run, record, *, poll_seconds=2):
    """Observe a still-live owned runner; never launch a replacement attempt."""
    work = run / "outputs" / record["instance_id"]
    marker = read(work / "controller_started.json")
    identity = marker.get("runner_identity")
    deadline = marker.get("started_at", marker.get("time", time.time())) + 2200
    while same_process(identity) and time.time() < deadline:
        result = terminal_result(work, record)
        if result:
            return result
        time.sleep(poll_seconds)
    terminate_owned(identity)
    result = terminal_result(work, record)
    if result:
        return result
    return failure(run, record, "interrupted_previous_attempt_not_replayed",
                   max(0.0, time.time() - marker.get("started_at", time.time())))


def execute(run, record):
    iid = record["instance_id"]
    work = run / "outputs" / iid
    previous = terminal_result(work, record)
    if previous:
        return previous
    if (work / "controller_started.json").exists():
        return recover_previous(run, record)
    if (work / "result.json").exists() or (work / "started.json").exists():
        return failure(run, record, "unowned_nonterminal_previous_attempt_not_replayed")
    graph = run / "public/graph_index" / f"{iid}.pkl"
    receipt = read(graph.with_suffix(".receipt.json"))
    if (receipt.get("status") != "success" or receipt.get("graph_ready") is not True
            or receipt.get("instance_id") != iid or receipt.get("base_commit") != record["base_commit"]
            or receipt.get("graph_sha256") != sha(graph)):
        return failure(run, record, "graph_preparation_identity_or_hash_failure")
    # Recheck before creating any durable task-attempt marker or subprocess.
    validate_tokenizer_cache(run)
    work.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(SOURCE / "reproduction/runner.py"),
        "--venv", str(SOURCE / ".venv"), "--instance", str(run / record["instance"]),
        "--graph", str(graph), "--snapshot", str(run / record["snapshot"]),
        "--work", str(work), "--tiktoken-cache", str(run / "public/tokenizer_cache"),
        "--api-base", "http://127.0.0.1:7353/v1", "--model", "qwen3-8b", "--timeout", "2100"]
    graph_time = receipt.get("elapsed_seconds", receipt.get("graph_elapsed_seconds"))
    if graph_time is not None:
        command += ["--graph-elapsed-seconds", str(graph_time)]
    marker = {"instance_id": iid, "started_at": time.time(),
              "instance_sha256": sha(run / record["instance"]), "graph_sha256": sha(graph),
              "command": command, "runner_identity": None}
    # The marker precedes subprocess launch: a crash cannot cause a duplicate.
    write(work / "controller_started.json", marker)
    write(work / "controller_command.json", command)
    started = time.monotonic()
    with (work / "runner_stdout.log").open("a") as out, (work / "runner_stderr.log").open("a") as err:
        child = subprocess.Popen(command, cwd=SOURCE, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, start_new_session=True)
        marker["runner_identity"] = proc(child.pid)
        write(work / "controller_started.json", marker)
        timed_out = False
        try:
            child.wait(timeout=2200)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_owned(marker["runner_identity"])
            child.wait(timeout=15)
        elapsed = time.monotonic() - started
    result = terminal_result(work, record)
    if result:
        return result
    return failure(run, record, "runner_timeout" if timed_out else f"environment_worker_exit_{child.returncode}", elapsed)


def service_ready():
    try:
        with urllib.request.urlopen(ENDPOINT, timeout=5) as response:
            data = json.load(response)
        return any(item.get("id") == "qwen3-8b" for item in data.get("data", []))
    except (OSError, ValueError):
        return False


def progress(run, records, active, stage, previous=0):
    statuses = Counter()
    finished_ids, known_requests, unknown = set(), 0, 0
    for record in records:
        result = terminal_result(run / "outputs" / record["instance_id"], record)
        if result:
            statuses[result["status"]] += 1
            finished_ids.add(record["instance_id"])
            usage = result.get("usage", {})
            known_requests += usage.get("completion_requests") or usage.get("known_completion_requests") or 0
            unknown += usage.get("unknown_usage_requests", 0)
    for iid in set(active.values()) - finished_ids:
        usage = recover_usage(run / "outputs" / iid)
        known_requests += usage.get("completion_requests") or usage.get("known_completion_requests") or 0
        unknown += usage.get("unknown_usage_requests", 0)
    count = sum(statuses.values())
    if count < previous:
        raise RuntimeError("Terminal progress decreased; a frozen result disappeared")
    payload = {"stage": stage, "heartbeat_time": time.time(), "expected_tasks": len(records),
               "terminal_tasks": count, "active": list(active.values()),
               "pending": len(records) - count - len(set(active.values()) - finished_ids),
               "terminal_statuses": dict(statuses), "observed_completion_requests": known_requests,
               "unknown_usage_requests": unknown}
    write(run / "controller_extension/progress.json", payload)
    return count


def run_stage(run, records, all_records, *, label, outage_limit=900):
    validate_tokenizer_cache(run)
    pending, active = [], {}
    for record in records:
        if not terminal_result(run / "outputs" / record["instance_id"], record):
            pending.append(record)
    last_terminal, outage_start, graph_wait = 0, None, None
    with ThreadPoolExecutor(max_workers=2) as pool:
        while pending or active:
            ready = service_ready() if pending else True
            if pending and not ready:
                outage_start = outage_start or time.monotonic()
                write(run / "controller_extension/service_pause.json", {
                    "time": time.time(), "reason": "local_service_unavailable", "new_tasks_paused": True})
                if time.monotonic() - outage_start >= outage_limit and not active:
                    raise RuntimeError("Local service unavailable for 900s; unstarted tasks retained")
            else:
                outage_start = None
            while ready and pending and len(active) < 2 and not STOP.is_set():
                validate_tokenizer_cache(run)
                record = pending[0]
                graph_receipt = run / "public/graph_index" / (record["instance_id"] + ".receipt.json")
                work = run / "outputs" / record["instance_id"]
                # Never turn a still-building graph into a model/task failure.
                if not graph_receipt.exists() and not (work / "controller_started.json").exists():
                    graph_wait = graph_wait or time.monotonic()
                    if time.monotonic() - graph_wait > 2400 and not active:
                        raise RuntimeError("Graph preparation stalled for 2400s; task remains unstarted")
                    break
                graph_wait = None
                pending.pop(0)
                active[pool.submit(execute, run, record)] = record["instance_id"]
            completed, _ = wait(active, timeout=5, return_when=FIRST_COMPLETED) if active else (set(), set())
            for future in completed:
                iid = active.pop(future)
                record = next(r for r in records if r["instance_id"] == iid)
                try:
                    result = future.result()
                except InfrastructureBlocked:
                    # Do not manufacture a failed model attempt for a missing
                    # shared asset; controller status records the actual block.
                    raise
                except Exception as error:
                    result = failure(run, record, f"controller_exception:{type(error).__name__}:{error}")
                print(json.dumps({"time": time.time(), "instance_id": iid, "status": result["status"],
                                  "execution_status": result["execution_status"]}, ensure_ascii=False), flush=True)
            last_terminal = progress(run, all_records, active, label, last_terminal)
            if STOP.is_set() and not active:
                raise RuntimeError("Stop requested; unstarted tasks retained without resampling")
            if not active and pending:
                time.sleep(5)
    return [terminal_result(run / "outputs" / r["instance_id"], r) for r in records]


def infrastructure_failures(results):
    return [r["instance_id"] for r in results if
        str(r.get("execution_status", "")).startswith(("environment_", "controller_", "runner_", "graph_"))
        or any(s.get("status") in {"api_error", "parse_error", "protocol_error", "worker_error", "transport_error"}
               for s in r.get("samples", []))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=[2], default=2)
    parser.add_argument("--canary-only", action="store_true")
    args = parser.parse_args()
    run = args.run_dir.resolve()
    folder = run / "controller_extension"
    folder.mkdir(exist_ok=True)
    lock = (folder / "controller.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        records = validate_rosters(run)
        freeze_controller(run, records)
    except Exception as error:
        write(folder / "preflight_error.json", {"status": "INFRASTRUCTURE_BLOCKED", "time": time.time(),
              "error": f"{type(error).__name__}: {error}", "worker_started": False,
              "model_calls_from_this_start": 0, "task_results_created": False})
        write(folder / "status.json", {"status": "INFRASTRUCTURE_BLOCKED", "time": time.time(),
              "error": f"{type(error).__name__}: {error}"})
        raise
    write(folder / "ownership.json", {"pid": os.getpid(), "uid": os.getuid(), "started": time.time()})
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    try:
        write(folder / "status.json", {"status": "RUNNING", "time": time.time(), "allocated_tasks": 180})
        results = run_stage(run, records[:3], records, label="NEW_CANARY_3")
        failures = infrastructure_failures(results)
        write(folder / "canary_gate.json", {"status": "STOP" if failures else "PASS",
            "task_ids": [r["instance_id"] for r in records[:3]], "failures": failures,
            "performance_used_for_gate": False, "time": time.time()})
        if failures:
            raise RuntimeError("New canary infrastructure failed; remaining 177 not started")
        if args.canary_only:
            write(folder / "status.json", {"status": "CANARY_COMPLETE", "time": time.time()})
            return
        run_stage(run, records[3:], records, label="NEW_REMAINDER_177")
        if not all(terminal_result(run / "outputs" / r["instance_id"], r) for r in records):
            raise RuntimeError("An expected task has no terminal result")
        write(folder / "status.json", {"status": "COMPLETE", "time": time.time(),
              "terminal_tasks": 180, "gold_read": False, "service_stopped": False})
    except BaseException as error:
        write(folder / "status.json", {"status": "NEEDS_ATTENTION", "time": time.time(),
            "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    main()
