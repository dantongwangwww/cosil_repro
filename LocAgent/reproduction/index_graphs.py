"""CPU-only official LocAgent graph construction with permanent per-task receipts.

Builds call ``dependency_graph.build_graph.build_graph(snapshot,
global_import=True)`` without changing its parsing or node-inclusion rules.
Target coverage is a separate, read-only offline audit written under private/.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
import os
from pathlib import Path
import pickle
import signal
import subprocess
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from reproduction.prepare import digest, sha

TERMINAL = {"success", "failed", "timed_out", "interrupted"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value, *, replace=False):
    path = Path(path)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                indent=2, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def paths(run, iid):
    base = Path(run) / "public/graph_index"
    return base / (iid + ".pkl"), base / (iid + ".receipt.json")


def source_check(run, record):
    run = Path(run)
    expected = load(run / "selection/snapshot_sources.json")[record["instance_id"]]
    snapshot = (run / record["snapshot"]).resolve(strict=True)
    if digest(expected["files"]) != record["snapshot_tree_sha256"]:
        raise ValueError("Snapshot manifest tree SHA drift")
    actual_paths = {p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*.py") if p.is_file()}
    if actual_paths != {item["path"] for item in expected["files"]}:
        raise ValueError("Snapshot Python file inventory drift")
    for item in expected["files"]:
        path = snapshot / item["path"]
        if path.is_symlink() or sha(path) != item["sha256"]:
            raise ValueError("Snapshot source bytes drift: " + item["path"])
    return snapshot


def syntax_audit(snapshot, skip_directory=None):
    """Record same-interpreter parse failures the official builder silently skips."""
    failures, skipped = [], []
    for path in sorted(Path(snapshot).rglob("*.py")):
        rel = path.relative_to(snapshot).as_posix()
        parent = path.parent.relative_to(snapshot).as_posix()
        if skip_directory is not None and parent != "." and skip_directory(parent):
            skipped.append(rel)
            continue
        try:
            with path.open("r") as handle:
                ast.parse(handle.read(), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as error:
            failures.append({"path": rel, "error_type": type(error).__name__,
                             "line": getattr(error, "lineno", None), "message": str(error)})
    return failures, skipped


def validate_cached(run, record, code_sha):
    graph_path, receipt_path = paths(run, record["instance_id"])
    if not receipt_path.exists():
        if graph_path.exists():
            raise ValueError("Graph without a terminal receipt is not reusable")
        return None
    receipt = load(receipt_path)
    if receipt.get("status") not in TERMINAL or receipt.get("instance_id") != record["instance_id"]:
        raise ValueError("Malformed graph terminal receipt")
    if (receipt.get("snapshot_tree_sha256") != record["snapshot_tree_sha256"]
            or receipt.get("official_builder_sha256") != code_sha):
        raise ValueError("Graph receipt source/protocol binding changed")
    if receipt["status"] == "success":
        if not graph_path.is_file() or sha(graph_path) != receipt.get("graph_sha256"):
            raise ValueError("Cached graph SHA mismatch")
    return receipt


def build_one(run, iid):
    run = Path(run).resolve(strict=True)
    manifest = load(run / "selection/manifest.json")
    record = next(r for r in manifest["records"] if r["instance_id"] == iid)
    graph_path, receipt_path = paths(run, iid)
    code_sha = sha(ROOT / "dependency_graph/build_graph.py")
    prior = validate_cached(run, record, code_sha)
    if prior is not None:
        return prior
    started = time.monotonic()
    receipt = {"schema": 1, "instance_id": iid, "repo": record["repo"],
               "base_commit": record["base_commit"], "status": "failed", "terminal": True,
               "graph_ready": False, "snapshot_tree_sha256": record["snapshot_tree_sha256"],
               "official_builder_sha256": code_sha, "global_import": True,
               "official_default_fuzzy_search": True, "python": sys.version,
               "new_model_calls": 0, "gpu_used": False}
    try:
        snapshot = source_check(run, record)
        # Import the real pinned upstream implementation only after source checks.
        from dependency_graph.build_graph import build_graph, is_skip_dir
        import networkx
        receipt["networkx_version"] = networkx.__version__
        failures, skipped = syntax_audit(snapshot, is_skip_dir)
        receipt.update(syntax_skips=failures, upstream_skipped_directory_files=skipped,
                       syntax_audit_scope="same-interpreter read-only prepass; upstream unchanged")
        graph_started = time.monotonic()
        graph = build_graph(str(snapshot), global_import=True)
        receipt["official_build_seconds"] = time.monotonic() - graph_started
        receipt.update(nodes=graph.number_of_nodes(), edges=graph.number_of_edges(),
                       node_types=dict(Counter(d.get("type", "UNKNOWN") for _, d in graph.nodes(data=True))),
                       edge_types=dict(Counter(d.get("type", "UNKNOWN") for *_, d in graph.edges(data=True))))
        temporary = graph_path.with_name("." + graph_path.name + "." + uuid.uuid4().hex + ".tmp")
        with temporary.open("xb") as handle:
            pickle.dump(graph, handle, protocol=pickle.HIGHEST_PROTOCOL)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, graph_path)
        finally:
            temporary.unlink(missing_ok=True)
        receipt.update(status="success", graph_ready=True,
                       graph_sha256=sha(graph_path), graph_bytes=graph_path.stat().st_size)
    except Exception as error:
        receipt.update(error_type=type(error).__name__, error=str(error))
        traceback.print_exc()
    receipt["elapsed_seconds"] = time.monotonic() - started
    atomic_json(receipt_path, receipt)
    return receipt


def coverage_for_graph(graph, targets):
    represented, absent = [], []
    for identity in targets:
        path, qn = identity.split("::", 1)
        node = path + ":" + qn
        if node in graph.nodes and graph.nodes[node].get("type") == "function":
            represented.append(identity)
            continue
        parent = path + ":" + qn.rsplit(".", 1)[0] if "." in qn else None
        class_fallback = bool(qn.endswith(".__init__") and parent in graph.nodes
                              and graph.nodes[parent].get("type") == "class")
        absent.append({"identity": identity, "file_node_present": path in graph.nodes,
                       "class_fallback_available": class_fallback,
                       "reason": "upstream_omits_independent_constructor_node" if class_fallback else
                                 "target_not_a_function_node_in_upstream_graph"})
    return {"targets": list(targets), "represented_function_nodes": represented,
            "missing_function_nodes": absent, "all_target_function_nodes_present": not absent,
            "note": "Missing independent function nodes do not prove source is unavailable through class/file tools"}


def audit_coverage(run):
    run = Path(run).resolve(strict=True)
    manifest = load(run / "selection/manifest.json")
    gold = load(run / "private/gold.json")
    if set(gold) != {r["instance_id"] for r in manifest["records"]}:
        raise ValueError("Graph coverage audit/gold rosters differ")
    records = []
    for record in manifest["records"]:
        iid = record["instance_id"]
        graph_path, receipt_path = paths(run, iid)
        receipt = load(receipt_path)
        item = {"instance_id": iid, "graph_status": receipt["status"], "graph_ready": receipt["status"] == "success"}
        if item["graph_ready"]:
            before = sha(graph_path)
            if before != receipt["graph_sha256"]:
                raise ValueError("Graph changed before offline coverage audit")
            with graph_path.open("rb") as handle:
                graph = pickle.load(handle)
            item.update(coverage_for_graph(graph, gold[iid]["targets"]))
            if sha(graph_path) != before:
                raise ValueError("Read-only graph audit changed a graph")
        records.append(item)
    result = {"schema": 1, "allocated": len(records), "records": records,
              "successful_graphs": sum(r["graph_ready"] for r in records),
              "tasks_missing_target_function_nodes": sum(bool(r.get("missing_function_nodes")) for r in records),
              "targets_missing_function_nodes": sum(len(r.get("missing_function_nodes", [])) for r in records),
              "gold_read_by": "offline coverage audit only; never exposed to graph construction or inference",
              "graph_modified": False, "tasks_removed_or_replaced": False}
    destination = run / "private/graph_coverage.json"
    if destination.exists():
        if load(destination) != result:
            raise ValueError("Refusing to overwrite a different offline coverage audit")
    else:
        atomic_json(destination, result)
    return result


def run_all(run, *, workers=4, timeout=1800, poll_seconds=1.0):
    if not 1 <= workers <= 4 or timeout <= 0:
        raise ValueError("Use 1–4 CPU workers and a positive timeout")
    run = Path(run).resolve(strict=True)
    manifest = load(run / "selection/manifest.json")
    (run / "public/graph_index").mkdir(exist_ok=True)
    work = run / "graph_build"
    work.mkdir(exist_ok=True)
    code_sha = sha(ROOT / "dependency_graph/build_graph.py")
    contract = {"workers": workers, "timeout_seconds": timeout,
                "official_builder_sha256": code_sha, "script_sha256": sha(__file__),
                "manifest_sha256": sha(run / "selection/manifest.json"),
                "global_import": True, "semantic_retries": 0, "gpu_used": False}
    contract_path = work / "contract.json"
    if contract_path.exists():
        if load(contract_path) != contract:
            raise ValueError("Frozen graph-build contract changed")
    else:
        atomic_json(contract_path, contract)
    pending, results = [], {}
    for record in manifest["records"]:
        cached = validate_cached(run, record, code_sha)
        if cached is None:
            pending.append(record)
        else:
            results[record["instance_id"]] = cached
    active = {}
    env = {k: os.environ[k] for k in ("PATH", "LD_LIBRARY_PATH", "LANG", "LC_ALL") if k in os.environ}
    env.update(CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               MPLCONFIGDIR=str(work / "matplotlib"), PYTHONPATH=str(ROOT))
    progress = {"allocated": len(manifest["records"]), "terminal": len(results),
                "statuses": dict(Counter(r["status"] for r in results.values())),
                "active": [], "pending": len(pending), "updated_unix": time.time()}
    atomic_json(work / "progress.json", progress, replace=True)
    while pending or active:
        while pending and len(active) < workers:
            record = pending.pop(0)
            iid = record["instance_id"]
            log = (work / (iid + ".log")).open("xb")
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--run-dir", str(run), "--build-one", iid]
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            active[iid] = {"record": record, "process": process, "log": log, "started": time.monotonic()}
        for iid, state in list(active.items()):
            process = state["process"]
            expired = time.monotonic() - state["started"] > timeout
            if process.poll() is None and not expired:
                continue
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            state["log"].close()
            graph_path, receipt_path = paths(run, iid)
            if not receipt_path.exists():
                atomic_json(receipt_path, {"schema": 1, "instance_id": iid,
                    "status": "timed_out" if expired else "failed", "terminal": True,
                    "graph_ready": False, "snapshot_tree_sha256": state["record"]["snapshot_tree_sha256"],
                    "official_builder_sha256": code_sha, "returncode": process.returncode,
                    "elapsed_seconds": time.monotonic() - state["started"], "gpu_used": False,
                    "error": "CPU graph timeout" if expired else "child exited without graph receipt"})
            results[iid] = validate_cached(run, state["record"], code_sha)
            del active[iid]
        progress = {"allocated": len(manifest["records"]), "terminal": len(results),
                    "statuses": dict(Counter(r["status"] for r in results.values())),
                    "active": list(active), "pending": len(pending), "updated_unix": time.time()}
        atomic_json(work / "progress.json", progress, replace=True)
        if pending or active:
            time.sleep(poll_seconds)
    audit_coverage(run)
    return progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--build-one", help=argparse.SUPPRESS)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    if args.build_one:
        result = build_one(args.run_dir, args.build_one)
    elif args.audit_only:
        result = audit_coverage(args.run_dir)
    else:
        result = run_all(args.run_dir, workers=args.workers, timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
