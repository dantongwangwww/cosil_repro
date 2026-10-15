"""Freeze root's explicitly requested, quantity-only exploratory execution.

This utility has no model imports, API calls, or test JSON parser. It refuses
failed review/integrity gates and existing output. Root invokes it only after
actual dataset review; it never turns formal statistics.passed into true.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANTITY = {"positive_unique_pairs_ge_8000", "E_unique_pairs_ge_3000"}
REVIEW_FIELDS = {"review_status", "label_error", "review_note"}


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_review(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def identity(row):
    return tuple(row[key] for key in ("review_family", "instance_id", "function_id", "input_sha256"))


def validate(data):
    stats = read_json(data / "statistics.json")
    gates = stats["quality_gates"]
    failed = sorted(key for key, value in gates.items() if value is not True)
    if stats.get("passed") is not False or not failed or not set(failed) <= QUANTITY:
        raise RuntimeError("Only failed original quantity minima may receive an exploratory decision; QC/integrity must pass")
    if stats.get("mechanical_labels_only") is not True or stats.get("model_calls") != 0:
        raise RuntimeError("Labels must remain mechanical, with zero model calls during data creation")
    review = stats["review"]
    if (review.get("passed") is not True or review.get("reviewed_records") != 30
            or type(review.get("label_errors")) is not int or not 0 <= review["label_errors"] <= 2):
        raise RuntimeError("Actual 30-item evidence review did not qualify")
    review_path = Path(review["review_path"])
    if sha(review_path) != review["review_sha256"]:
        raise RuntimeError("Signed review SHA changed")
    pending = read_review(data / "human_review.jsonl")
    completed = read_review(review_path)
    expected = {identity(row): row for row in pending}
    actual = {identity(row): row for row in completed}
    if len(pending) != 30 or len(completed) != 30 or len(expected) != 30 or set(expected) != set(actual):
        raise RuntimeError("Review identities are missing, duplicated or changed")
    if Counter(row["review_family"] for row in pending) != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}:
        raise RuntimeError("Expected ten reviewed training E examples from each family")
    errors = 0
    for key, row in actual.items():
        if {k: v for k, v in row.items() if k not in REVIEW_FIELDS} != {k: v for k, v in expected[key].items() if k not in REVIEW_FIELDS}:
            raise RuntimeError("Review changed a label or evidence payload")
        if (row.get("review_status") != "reviewed" or type(row.get("label_error")) is not bool
                or not isinstance(row.get("review_note"), str) or not row["review_note"].strip()):
            raise RuntimeError("Incomplete actual evidence review")
        if row.get("split") != "train" or row.get("label") is not False or row.get("reviewer") != "Codex/机械证据审阅":
            raise RuntimeError("Review must remain train-only negative E, signed as Codex evidence review")
        errors += row["label_error"]
    if errors != review["label_errors"]:
        raise RuntimeError("Review error count differs from signed records")
    seal_path, split_path = data / "test_file_seal.json", data / "split_manifest.json"
    seal, manifest = read_json(seal_path), read_json(split_path)
    if seal != stats["seal"] or sha(split_path) != stats["split_manifest_sha256"]:
        raise RuntimeError("Frozen seal or issue split changed")
    split_ids = [set(manifest["splits"][name]) for name in ("train", "val", "test")]
    if [len(ids) for ids in split_ids] != [240, 30, 30] or len(set.union(*split_ids)) != 300:
        raise RuntimeError("Expected the original disjoint 240/30/30 issue assignment")
    benchmark_ids = set(read_json(ROOT / "results/comparison/逐题定位对照数据.json")["issue_order"])
    if set.union(*split_ids) != benchmark_ids:
        raise RuntimeError("Split does not match the same fixed benchmark issue IDs")
    hashes = {"split_manifest_sha256": sha(split_path), "seal_sha256": sha(seal_path)}
    for name in ("train", "val", "test"):
        path = (data / f"pruner_{name}.jsonl").resolve()
        entry = seal["frozen_files"][name]
        if Path(entry["path"]).resolve() != path or sha(path) != entry["sha256"]:
            raise RuntimeError(f"Frozen {name} SHA/path changed")
        if name == "test" and Path(seal["test_path"]).resolve() != path:
            raise RuntimeError("Test seal points to another physical test file")
        if name == "test" and path.with_name(path.name + ".v5_opened_once.json").exists():
            raise RuntimeError("Test opening has already been consumed")
        hashes[name + "_sha256"] = entry["sha256"]
    return stats, failed, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=ROOT / "results/v5_pruner/execution_contract.json")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    data, output = args.data_dir.resolve(), args.output_dir.resolve()
    if output.exists():
        raise FileExistsError("Existing root decisions and protocol snapshots are never overwritten")
    if not args.reason.strip():
        raise ValueError("Explicit actual limited-data reasoning is required")
    stats, failed, hashes = validate(data)
    contract_bytes = args.contract.read_bytes()
    contract_sha = hashlib.sha256(contract_bytes).hexdigest()
    contract = json.loads(contract_bytes)
    if contract["hybrid"].get("threshold_policy") != "val_safety":
        raise RuntimeError("Root's predeclared validation-only safety threshold policy is required")
    output.mkdir(parents=True)
    snapshot = output / "execution_contract_snapshot.json"
    snapshot.write_bytes(contract_bytes)
    decision = {"schema_version": 1, "track": "exploratory", "formal_failed": True,
                "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "reviewer": "Codex root; authorized autonomous execution", "reason": args.reason,
                "data_dir": str(data), "statistics_sha256": sha(data / "statistics.json"),
                "execution_contract_path": str(snapshot), "execution_contract_sha256": contract_sha,
                "execution_contract_source_path": str(args.contract.resolve()),
                "allowed_failed_gates": failed, "raw_counts": stats["raw_counts"],
                "selected_counts": stats["selected"], "formal_gate_results": stats["quality_gates"],
                "review_sha256": stats["review"]["review_sha256"],
                "test_json_parsed": False, "formal_passed_preserved_false": True, **hashes}
    path = output / "root_exploratory_decision.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(decision, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"decision_path": str(path), "decision_sha256": sha(path),
                      "allowed_failed_gates": failed, "track": "exploratory"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
