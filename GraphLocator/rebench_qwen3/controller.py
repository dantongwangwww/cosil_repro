"""Gold-blind, resumable scheduling for the fixed GraphLocator280 experiment."""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_check(protocol):
    bindings = protocol.get("source_sha256")
    if protocol.get("status") != "FROZEN" or not isinstance(bindings, dict) or not bindings:
        raise ValueError("A frozen, content-bound protocol is required")
    for name, digest in bindings.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != digest:
            raise ValueError("Frozen source changed: " + name)


def select_tasks(run, phase):
    protocol = read(run / "protocol.json")
    for name, key in (("manifest.json", "selection_manifest_sha256"),
                      ("pilot20.json", "pilot20_manifest_sha256")):
        if protocol.get(key) != sha(run / "selection" / name):
            raise ValueError("Frozen roster SHA differs: " + name)
    manifest = read(run / "selection/manifest.json")
    records = manifest["records"]
    ids = [r["instance_id"] for r in records]
    if len(records) != 280 or len(set(ids)) != 280:
        raise ValueError("The complete fixed280 roster is required")
    if len({r["repo"] for r in records}) != 280:
        raise ValueError("Fixed280 must retain its one-repository-per-task identity")
    for iid in ids:
        if not isinstance(iid, str) or Path(iid).name != iid or iid in (".", ".."):
            raise ValueError("Unsafe issue identity")
    pilot = read(run / "selection/pilot20.json")
    selected = pilot["records"]
    if selected != records[:20]:
        raise ValueError("Pilot must be the fixed-order first20, with no result selection")
    if phase == "pilot20":
        return selected
    gate = read(run / "controller/pilot_gate.json")
    if gate.get("technical_passed") is not True or gate.get("protocol_sha256") != sha(run / "protocol.json"):
        raise ValueError("An explicit, same-protocol technical pilot gate is required")
    return records


def terminal_result(run, task):
    path = run / "outputs" / task["instance_id"] / "result.json"
    if not path.exists():
        return None
    row = read(path)
    for key in ("instance_id", "repo", "base_commit"):
        if row.get(key) != task[key]:
            raise ValueError("Terminal identity differs: " + task["instance_id"])
    if row.get("terminal") is not True or row.get("status") not in ("complete", "partial", "failed"):
        raise ValueError("Existing output is not a valid terminal task")
    binding = row.get("protocol_sha256")
    launch = path.parent / "controller_launch.json"
    if binding is None and launch.is_file():
        binding = read(launch).get("protocol_sha256")
    if binding != sha(run / "protocol.json"):
        raise ValueError("Existing terminal task belongs to a different or unbound protocol")
    if row["status"] == "failed" and (row.get("found_files") or row.get("found_entities")):
        raise ValueError("A failed execution cannot be rescued with partial predictions")
    return row


def service_ready(endpoint, model):
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/models", timeout=3) as response:
            value = json.load(response)
        return any(row.get("id") == model for row in value.get("data", []))
    except (OSError, ValueError, KeyError):
        return False


def process_identity(pid):
    path = Path("/proc") / str(pid)
    try:
        stat = (path / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "uid": path.stat().st_uid, "start_ticks": int(stat[19]),
                "pgid": os.getpgid(pid),
                "cmd": (path / "cmdline").read_bytes().replace(b"\0", b" ").decode()}
    except (OSError, ValueError, IndexError):
        return None


def stop_owned_worker(identity):
    current = process_identity(identity["pid"])
    if current is None:
        return
    if any(current[k] != identity[k] for k in ("uid", "start_ticks", "pgid", "cmd")):
        raise RuntimeError("Worker identity changed; refusing to signal")
    if current["uid"] != os.getuid() or current["pgid"] != current["pid"]:
        raise RuntimeError("Worker is not the owned session leader")
    os.killpg(current["pid"], signal.SIGTERM)


def failed_receipt(run, task, execution_status, detail):
    """Delivery failure only; never invent zero usage after unreturned HTTP."""
    directory = run / "outputs" / task["instance_id"]
    existing = terminal_result(run, task)
    if existing is not None:
        return existing
    usage = {"known_prompt_tokens": None, "known_completion_tokens": None,
             "known_total_tokens": None, "unknown_usage_requests": None,
             "http_attempts": None, "api_cost_usd": 0.0,
             "accounting_status": "UNKNOWN_PENDING_RAW_LEDGER_RECONCILIATION"}
    try:
        from .transport import summary_usage
        usage = summary_usage(directory)
    except (ImportError, AttributeError, OSError, ValueError, TypeError):
        pass
    value = {k: task[k] for k in ("instance_id", "repo", "base_commit")}
    value.update(terminal=True, status="failed", execution_status=execution_status,
                 error=detail, found_files=[], found_entities=[], found_modules=[],
                 usage=usage, source="controller_environment_receipt", model="qwen3-8b",
                 thinking_enabled=False, elapsed_seconds=None,
                 protocol_sha256=sha(run / "protocol.json"))
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / (".controller_terminal_" + str(os.getpid()) + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, directory / "result.json")
        except FileExistsError:
            # A concurrently finishing owned worker wins; no result is replaced.
            return terminal_result(run, task)
    finally:
        temporary.unlink(missing_ok=True)
    return value


def prior_started_attempt(run, task):
    directory = run / "outputs" / task["instance_id"]
    if not any((directory / name).exists() for name in ("controller_launch.json", "runner_started.json")):
        return False
    launch = directory / "controller_launch.json"
    if launch.exists() and read(launch).get("protocol_sha256") != sha(run / "protocol.json"):
        raise ValueError("An interrupted attempt belongs to another protocol")
    return True


def run_controller(args):
    run = args.run.resolve(strict=True)
    protocol = read(run / "protocol.json")
    source_check(protocol)
    protocol_digest = sha(run / "protocol.json")
    tasks = select_tasks(run, args.phase)
    if args.workers != protocol["inference"]["workers"] or args.workers > 2:
        raise ValueError("Worker count differs from the frozen protocol")
    if args.runner_timeout != protocol["inference"]["runner_timeout_seconds"]:
        raise ValueError("Timeout differs from the frozen protocol")
    folder = run / "controller"
    folder.mkdir(exist_ok=True)
    lock = (folder / "run.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    pending = [task for task in tasks if terminal_result(run, task) is None]
    active = {}
    phase_start = time.time()
    atomic(folder / (args.phase + "_launcher.json"), {
        "started": phase_start, "identity": process_identity(os.getpid()),
        "command": sys.argv, "protocol_sha256": protocol_digest,
        "expected_tasks": len(tasks), "reused_same_protocol_terminal_tasks": len(tasks) - len(pending),
        "gold_read": False})
    graph_wait_started = None
    paused_reason = None
    try:
        while pending or active:
            source_check(protocol)
            if sha(run / "protocol.json") != protocol_digest:
                raise RuntimeError("Protocol changed while inference was running")
            healthy = service_ready(protocol["endpoint"], protocol["model"]["served_name"])
            while pending and len(active) < args.workers and healthy:
                task = pending[0]
                iid = task["instance_id"]
                if prior_started_attempt(run, task):
                    paused_reason = "PAUSED_STARTED_ATTEMPT_REQUIRES_OBSERVATION"
                    break
                graph = run / "public/graphs" / (iid + ".json")
                receipt = graph.with_suffix(".receipt.json")
                if not receipt.exists():
                    graph_wait_started = graph_wait_started or time.monotonic()
                    break
                preparation = read(receipt)
                if preparation.get("status") not in ("success", "SUCCESS"):
                    pending.pop(0)
                    failed_receipt(run, task, "environment_graph_preparation_failed", preparation)
                    continue
                graph_wait_started = None
                directory = run / "outputs" / iid
                directory.mkdir(parents=True, exist_ok=True)
                command = [str(ROOT / ".venv/bin/python"), "-m", "rebench_qwen3.runner",
                           "--run", str(run), "--instance-id", iid, "--phase", "inference",
                           "--timeout", str(args.runner_timeout)]
                stdout = (directory / "runner_stdout.log").open("ab", buffering=0)
                stderr = (directory / "runner_stderr.log").open("ab", buffering=0)
                process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                    stdin=subprocess.DEVNULL, start_new_session=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "CUDA_VISIBLE_DEVICES": "",
                         "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
                identity = None
                for _ in range(100):
                    identity = process_identity(process.pid)
                    if identity and identity["cmd"] and identity["pgid"] == process.pid:
                        break
                    time.sleep(.01)
                if not identity or not identity["cmd"] or identity["pgid"] != process.pid:
                    raise RuntimeError("Unable to bind runner identity safely")
                active[iid] = {"process": process, "identity": identity, "task": task,
                               "started": time.monotonic(), "stdout": stdout, "stderr": stderr}
                atomic(directory / "controller_launch.json", {"command": command, "identity": identity,
                       "started": time.time(), "protocol_sha256": protocol_digest})
                pending.pop(0)
            for iid, info in list(active.items()):
                process = info["process"]
                if process.poll() is None and time.monotonic() - info["started"] > args.runner_timeout + 60:
                    stop_owned_worker(info["identity"])
                    process.wait(timeout=30)
                    if terminal_result(run, info["task"]) is None:
                        failed_receipt(run, info["task"], "environment_outer_timeout", "Owned worker exceeded hard timeout")
                if process.poll() is not None:
                    if terminal_result(run, info["task"]) is None:
                        failed_receipt(run, info["task"], "environment_runner_exit_" + str(process.returncode),
                                       "See immutable runner/worker logs; no semantic retry")
                    info["stdout"].close()
                    info["stderr"].close()
                    del active[iid]
            rows = [terminal_result(run, task) for task in tasks]
            rows = [row for row in rows if row is not None]
            progress = {"phase": args.phase, "status": "RUNNING", "time": time.time(),
                        "expected_tasks": len(tasks), "terminal_tasks": len(rows),
                        "statuses": dict(Counter(row["status"] for row in rows)),
                        "active": list(active), "pending": len(pending), "service_healthy": healthy,
                        "gold_read": False, "protocol_sha256": protocol_digest}
            atomic(folder / "progress.json", progress)
            if not active and pending and not healthy:
                paused_reason = "PAUSED_SERVICE_UNAVAILABLE"
                break
            if not active and paused_reason:
                break
            if graph_wait_started and time.monotonic() - graph_wait_started > args.graph_wait_seconds:
                paused_reason = "PAUSED_GRAPH_PREPARATION_WAIT"
                break
            if pending or active:
                time.sleep(args.poll_seconds)
        rows = [terminal_result(run, task) for task in tasks]
        status = "COMPLETE" if all(row is not None for row in rows) else (paused_reason or "INCOMPLETE")
        result = {"status": status, "phase": args.phase, "time": time.time(),
                  "terminal_tasks": sum(row is not None for row in rows), "expected_tasks": len(tasks),
                  "protocol_sha256": protocol_digest, "gold_read": False,
                  "source_code_unchanged": True, "automatic_semantic_retries": 0}
        atomic(folder / (args.phase + "_completion.json"), result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0 if status == "COMPLETE" else 2
    except BaseException as exc:
        atomic(folder / (args.phase + "_interruption.json"), {
            "status": "NEEDS_ATTENTION", "error": type(exc).__name__, "message": str(exc),
            "time": time.time(), "active_owned_workers": [v["identity"] for v in active.values()],
            "gold_read": False, "unstarted_tasks_not_failed": True})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--phase", choices=("pilot20", "full280"), required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--runner-timeout", type=int, default=1800)
    parser.add_argument("--graph-wait-seconds", type=int, default=7200)
    parser.add_argument("--poll-seconds", type=float, default=5.)
    raise SystemExit(run_controller(parser.parse_args()))


if __name__ == "__main__":
    main()
