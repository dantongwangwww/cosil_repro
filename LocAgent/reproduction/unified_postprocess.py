#!/usr/bin/env python3
"""Incremental, gold-blind requested-file normalization for the frozen 280.

Old 100 outputs are byte-reused from their frozen requested_file view. Each
new terminal task is projected into a one-record public run and passed through
the exact frozen sample parser/filter/MRR. This never calls a model, reads a
private label, or changes source predictions. A ready receipt is published
only after source/result hashes and unchanged inference fields are checked.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time

SOURCE = Path(__file__).resolve().parents[1]
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
from reproduction.controller import read, sha, write
from reproduction.controller_extension import preparation_ready

RULE_ID = "offline_format_plus_requested_file_scope_diagnostic_v1"
SOURCE_PATCH_SHA256 = "7984406d757f4d5fb9cda6fd5d4b2e47f033890eda9f37d7e019a20c92a8446f"
OLD_RUN = SOURCE / "experiments/qwen3_rebench100_native_payload_v2_20261115"
OLD_VIEW = OLD_RUN / "audits/postprocess_requested_file_final100"
INFERENCE_FIELDS = ("instance_id", "repo", "base_commit", "status", "terminal", "execution_status",
                    "samples", "raw_output_loc", "usage", "elapsed_seconds", "generation_seconds",
                    "tool_elapsed_seconds", "graph_elapsed_seconds")


def explicit_path(run, value):
    path = Path(value)
    return path if path.is_absolute() else run / path


def source_paths(run, record):
    iid = record["instance_id"]
    origin = record.get("execution_origin")
    if origin == "existing100_reuse":
        raw = explicit_path(run, record.get("original_result", str(OLD_RUN / "outputs" / iid / "result.json")))
        normalized = explicit_path(run, record.get("requested_file_result", str(OLD_VIEW / "outputs" / iid / "result.json")))
        return raw, normalized
    if origin != "new180":
        raise ValueError("Every task must declare existing100_reuse or new180")
    return run / "outputs" / iid / "result.json", None


def verify_inference_unchanged(source, normalized, record):
    if source.get("terminal") is not True or normalized.get("terminal") is not True:
        raise ValueError("Only terminal predictions can be normalized")
    for key in ("instance_id", "repo", "base_commit"):
        if source.get(key) != record[key]:
            raise ValueError(f"Source task identity mismatch: {key}")
    for key in INFERENCE_FIELDS:
        if source.get(key) != normalized.get(key):
            raise ValueError(f"Normalization changed frozen inference field: {key}")
    if normalized.get("postprocess_view") != RULE_ID:
        raise ValueError("Normalization rule/version mismatch")
    if normalized.get("source_patch_sha256") != SOURCE_PATCH_SHA256:
        raise ValueError("Line-scope patch mismatch")
    if normalized.get("postprocess_diagnostic_error"):
        raise ValueError("Parser diagnosis failed; do not silently publish native fallback")


def rule_fingerprint(old_protocol=OLD_VIEW / "protocol.json"):
    protocol = read(old_protocol)
    if protocol.get("source_patch_sha256") != SOURCE_PATCH_SHA256 or protocol.get("view") != RULE_ID:
        raise ValueError("Frozen old requested-file rule does not match")
    # Only the exact already-frozen parser implementation is permitted.
    code = protocol["code_sha256"]
    paths = {"postprocess_compat.py": SOURCE / "reproduction/postprocess_compat.py",
             "postprocess_requested_file.py": SOURCE / "reproduction/postprocess_requested_file.py",
             "upstream/util/process_output.py": SOURCE / "util/process_output.py"}
    for key, path in paths.items():
        if sha(path) != code.get(key):
            raise ValueError(f"Frozen parser code changed: {key}")
    return {"rule_id": RULE_ID, "source_patch_sha256": SOURCE_PATCH_SHA256,
            "rule_first_frozen_at_utc": protocol["rule_frozen_at_utc"],
            "parser_sha256": {k: sha(p) for k, p in paths.items()},
            "original_protocol_path": str(old_protocol), "original_protocol_sha256": sha(old_protocol)}


def freeze_unified(run, output):
    preparation_ready(run)
    expected = {"rule": rule_fingerprint(), "manifest_sha256": sha(run / "selection/manifest.json"),
                "wrapper_sha256": sha(Path(__file__)), "new_model_calls": 0, "gold_read": False,
                "primary_evaluation_rule": "Frozen generic serialization compatibility plus exact requested-file line scope",
                "not_a_complete_parser_or_ast_repair": True,
                "old_native_views_unchanged": True, "no_score_based_view_selection": True}
    path = output / "protocol.json"
    if path.exists():
        previous = read(path)
        if any(previous.get(k) != v for k, v in expected.items()):
            raise ValueError("Unified parser rules, roster, or wrapper changed after freezing")
        return previous
    expected["delivery_frozen_at_utc"] = datetime.now(timezone.utc).isoformat()
    write(path, expected)
    return expected


def symlink_once(source, target):
    source = Path(source).resolve()
    if target.exists() or target.is_symlink():
        if not target.is_symlink() or target.resolve() != source:
            raise ValueError("Read-only source projection changed")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source, target_is_directory=source.is_dir())


def project_one(run, output, record, source):
    iid = record["instance_id"]
    project = output / "projects" / iid
    manifest = project / "selection/manifest.json"
    value = {"n": 1, "records": [copy.deepcopy(record)], "gold_read": False, "new_model_calls": 0}
    if manifest.exists():
        if read(manifest) != value:
            raise ValueError("Per-task projection manifest changed")
    else:
        write(manifest, value)
    symlink_once(source.parent, project / "outputs" / iid)
    for suffix in (".pkl", ".receipt.json"):
        symlink_once(run / "public/graph_index" / f"{iid}{suffix}",
                     project / "public/graph_index" / f"{iid}{suffix}")
    return project


def ready_receipt(output, record):
    target = output / "outputs" / record["instance_id"]
    receipt_path, result_path = target / "normalization_receipt.json", target / "result.json"
    if not receipt_path.exists():
        return None
    receipt = read(receipt_path)
    if (receipt.get("status") != "ready" or receipt.get("instance_id") != record["instance_id"]
            or receipt.get("rule_id") != RULE_ID or receipt.get("source_patch_sha256") != SOURCE_PATCH_SHA256
            or not result_path.is_file() or sha(result_path) != receipt.get("normalized_result_sha256")
            or sha(Path(receipt["source_result_path"])) != receipt.get("source_result_sha256")):
        raise ValueError("A ready normalization result/source/receipt changed")
    return receipt


def normalize_one(run, output, record, protocol, *, builder=None):
    existing = ready_receipt(output, record)
    if existing:
        return existing
    source, old_result = source_paths(run, record)
    if not source.is_file():
        return None
    raw = read(source)
    if raw.get("terminal") is not True:
        return None
    source_hash = sha(source)
    started = time.monotonic()
    if old_result is not None:
        payload = old_result.read_bytes()
        normalized = json.loads(payload)
        if normalized.get("source_inference_result_sha256") != source_hash:
            raise ValueError("Old normalized result is not bound to frozen old raw")
        verify_inference_unchanged(raw, normalized, record)
        mode, source_normalized = "frozen_old100_byte_reuse", str(old_result)
    else:
        project = project_one(run, output, record, source)
        if builder is None:
            from reproduction.postprocess_requested_file import build_view
            builder = build_view
        projection_output = project / "normalized"
        summary = builder(project, projection_output)
        if (summary.get("status") != "FINAL" or summary.get("expected_tasks") != 1
                or summary.get("terminal_tasks") != 1 or summary.get("diagnostic_errors")
                or summary.get("read_errors") or summary.get("source_patch_sha256") != SOURCE_PATCH_SHA256):
            raise ValueError("Per-sample normalization did not finish cleanly")
        generated = projection_output / "outputs" / record["instance_id"] / "result.json"
        payload = generated.read_bytes()
        normalized = json.loads(payload)
        verify_inference_unchanged(raw, normalized, record)
        mode, source_normalized = "new180_same_frozen_sample_parser_mrr", str(generated)
    if sha(source) != source_hash:
        raise RuntimeError("Raw inference changed during normalization")
    target = output / "outputs" / record["instance_id"]
    target.mkdir(parents=True, exist_ok=True)
    result_path = target / "result.json"
    if result_path.exists() and result_path.read_bytes() != payload:
        raise ValueError("An unreceipted normalized result differs; refusing overwrite")
    if not result_path.exists():
        temporary = target / "result.json.tmp"
        temporary.write_bytes(payload)
        os.replace(temporary, result_path)
    receipt = {"instance_id": record["instance_id"], "status": "ready", "rule_id": RULE_ID,
        "source_result_path": str(source.resolve()), "source_result_sha256": source_hash,
        "normalized_result_sha256": hashlib.sha256(payload).hexdigest(),
        "source_patch_sha256": SOURCE_PATCH_SHA256, "mode": mode,
        "source_normalized_result": source_normalized, "elapsed_seconds": time.monotonic() - started,
        "rule_first_frozen_at_utc": protocol["rule"]["rule_first_frozen_at_utc"],
        "new_model_calls": 0, "gold_read": False, "finished_at_utc": datetime.now(timezone.utc).isoformat()}
    write(target / "normalization_receipt.json", receipt)
    return receipt


def update_summary(run, output, records, errors):
    receipts, pending = [], []
    for record in records:
        receipt = ready_receipt(output, record)
        (receipts if receipt else pending).append(receipt if receipt else record["instance_id"])
    counts = {"existing100_reuse": 0, "new180": 0}
    by_id = {r["instance_id"]: r for r in records}
    for receipt in receipts:
        counts[by_id[receipt["instance_id"]]["execution_origin"]] += 1
    summary = {"status": "FINAL" if len(receipts) == len(records) and not errors else "RUNNING",
        "expected_tasks": len(records), "ready_tasks": len(receipts), "pending_tasks": pending,
        "ready_by_origin": counts, "errors": errors, "new_model_calls": 0, "gold_read": False,
        "rule_id": RULE_ID, "source_patch_sha256": SOURCE_PATCH_SHA256,
        "updated_at_utc": datetime.now(timezone.utc).isoformat()}
    write(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=10)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    output = args.output.resolve() if args.output else run / "audits/unified_requested_file"
    output.mkdir(parents=True, exist_ok=True)
    lock = (output / "postprocess.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    records = read(run / "selection/manifest.json")["records"]
    if len(records) != 280 or len({r["instance_id"] for r in records}) != 280:
        raise ValueError("Unified delivery requires exactly 280 unique frozen tasks")
    protocol = freeze_unified(run, output)
    errors = {}
    while True:
        for record in records:
            iid = record["instance_id"]
            if iid in errors:
                continue
            try:
                receipt = normalize_one(run, output, record, protocol)
                if receipt and not (output / "announced" / iid).exists():
                    write(output / "announced" / iid, receipt)
                    print(json.dumps({"instance_id": iid, "status": "ready", "mode": receipt["mode"]}), flush=True)
            except Exception as error:
                errors[iid] = f"{type(error).__name__}: {error}"
            # Publish progress after each CPU item, not after the whole batch.
            update_summary(run, output, records, errors)
        summary = update_summary(run, output, records, errors)
        if errors:
            raise RuntimeError(f"Gold-blind normalization errors: {errors}")
        if summary["status"] == "FINAL" or not args.watch:
            print(json.dumps(summary, ensure_ascii=False), flush=True)
            return
        time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    main()
