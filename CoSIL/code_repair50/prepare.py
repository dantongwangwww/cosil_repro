"""Deterministic CPU preparation, never qualification or model inference.

This program only projects identifiers from the frozen benchmark parquet.  It
does not import a provider, inspect predictions, run tests, or pass private gold
to any model.  The first 50 different repositories are a *preview*: only the
official gold/empty-patch qualification executor may freeze a final task list.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path

SEED = 20261024
REVISION = "34d5a58864acf91613740a09ec5d205228dcfa39"
DATASET_SHA256 = "1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf"
NAMESPACE = "repair50-v1"
ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT.parent / "ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1_delivery"
DATASET = (ROOT.parent / "ModelLoc/experiments/deepseek_simple_external_v1/"
           "evaluator_private/preparation/dataset/test-00000-of-00001.parquet")
OUTPUT = ROOT / "results/repair50_20261024"
BLOCKED = "NOT_CHECKED_SYSTEM_BLOCKED_DOCKER"


def sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path | str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def order_hash(instance_id: str) -> str:
    if not isinstance(instance_id, str) or not instance_id:
        raise ValueError("Nonempty instance_id required")
    payload = "\0".join((NAMESPACE, str(SEED), REVISION, instance_id))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def unique(records, label):
    output = {}
    for row in records:
        instance_id = row["instance_id"]
        if instance_id in output:
            raise ValueError("Duplicate instance_id in " + label)
        output[instance_id] = row
    return output


def derive_pool(roster, inputs, audit, gold_reader=load, strict_counts=True):
    """Join by instance_id and validate target completeness, without outcomes."""
    if roster.get("dataset_revision") != REVISION:
        raise ValueError("Frozen roster revision mismatch")
    if roster.get("dataset_sha256") != DATASET_SHA256:
        raise ValueError("Frozen roster dataset digest mismatch")
    roster_by_id = unique(roster["records"], "roster")
    input_by_id = unique(inputs["records"], "input manifest")
    audit_by_id = unique(audit["records"], "R2 audit")
    if set(roster_by_id) != set(input_by_id) or set(roster_by_id) != set(audit_by_id):
        raise ValueError("Roster, clean-input manifest and R2 audit IDs disagree")
    candidates, exclusions = [], []
    for instance_id, row in roster_by_id.items():
        gold_record = audit_by_id[instance_id]
        source = input_by_id[instance_id]
        if any(row[k] != gold_record[k] or row[k] != source[k]
               for k in ("repo", "base_commit")):
            raise ValueError("Repository/base identity mismatch: " + instance_id)
        gold = gold_reader(gold_record["gold_path"])
        if any(gold[k] != row[k] for k in ("instance_id", "repo", "base_commit")):
            raise ValueError("R2 gold identity mismatch: " + instance_id)
        if gold.get("evaluation_revision") != "r2_exact_context_offsets":
            raise ValueError("R2 evaluator revision mismatch: " + instance_id)
        targets = gold.get("existing_function_targets")
        if (not isinstance(targets, list)
                or any(not isinstance(v, str) or "::" not in v for v in targets)
                or len(set(targets)) != len(targets)):
            raise ValueError("Malformed existing target set: " + instance_id)
        if gold.get("existing_function_target_set_complete") is not True:
            raise ValueError("Incomplete R2 target extraction: " + instance_id)
        expected_status = "COMPLETE_NONEMPTY" if targets else "COMPLETE_EMPTY"
        if gold.get("status") != expected_status or gold_record["function_status"] != expected_status:
            raise ValueError("R2 status/target mismatch: " + instance_id)
        if gold_record.get("function_scorable") is not bool(targets):
            raise ValueError("R2 eligibility mismatch: " + instance_id)
        if gold_record.get("target_n") != len(targets):
            raise ValueError("R2 target count mismatch: " + instance_id)
        common = {"instance_id": instance_id, "repo": row["repo"],
                  "base_commit": row["base_commit"], "seed": SEED,
                  "dataset_revision": REVISION, "dataset_sha256": DATASET_SHA256,
                  "sampling_hash": order_hash(instance_id),
                  "gold_function_count": len(targets),
                  "gold_path": gold_record["gold_path"],
                  "gold_sha256": gold_record["gold_sha256"],
                  "index_path": gold_record["index_path"],
                  "index_sha256": gold_record["index_sha256"],
                  "job_path": source["job"], "snapshot_path": source["snapshot"],
                  "selection_uses_predictions": False,
                  "selection_uses_repair_outcomes": False}
        if targets:
            candidates.append(common)
        else:
            exclusions.append({**common, "reason": "FUNCTION_TARGET_SET_COMPLETE_BUT_EMPTY",
                               "scope": "repair50_existing_function_development_diagnostic"})
    candidates.sort(key=lambda r: (r["sampling_hash"], r["instance_id"]))
    exclusions.sort(key=lambda r: r["instance_id"])
    for rank, row in enumerate(candidates, 1):
        row["candidate_rank"] = rank
    if strict_counts and (len(roster_by_id), len(candidates), len(exclusions)) != (265, 235, 30):
        raise ValueError("Frozen 265/235/30 counts disagree")
    return candidates, exclusions


def first_unique_preview(candidates, limit=50):
    """No qualification exclusion: repeat repos can replace failed candidates."""
    selected, seen, preview = [], {}, []
    for row in candidates:
        instance_id, repo = row["instance_id"], row["repo"]
        if len(selected) >= limit:
            reason = "NOT_REACHED_IN_PROVISIONAL_FIRST50_PREVIEW"
        elif repo in seen:
            reason = "DUPLICATE_REPOSITORY_IN_PROVISIONAL_PREVIEW"
        else:
            reason = "PROVISIONALLY_SELECTED_PENDING_QUALIFICATION"
            seen[repo] = instance_id
            selected.append(row.copy())
        preview.append({"candidate_rank": row["candidate_rank"], "instance_id": instance_id,
                        "repo": repo, "preview_reason": reason,
                        "same_repository_provisionally_selected_id": seen.get(repo, ""),
                        "permanent_qualification_exclusion": False})
    return selected, preview


def durable(path, payload):
    """Identical reruns are allowed; changed evidence is never overwritten."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Output symlink refused")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise FileExistsError("Refusing to overwrite changed artifact: " + str(path))
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def csv_bytes(records, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue().encode("utf-8-sig")


def prepare(delivery=DELIVERY, dataset=DATASET, output=OUTPUT):
    delivery, dataset, output = Path(delivery), Path(dataset), Path(output)
    source_paths = {"roster": delivery / "manifests/filtered265_roster.json",
                    "clean_inputs": delivery / "manifests/filtered265.json",
                    "gold_audit": delivery / "reports/金标范围与复用一致性核验.json",
                    "dataset": dataset}
    source_hashes = {str(path): sha256(path) for path in source_paths.values()}
    if source_hashes[str(dataset)] != DATASET_SHA256:
        raise ValueError("Frozen parquet digest mismatch")
    roster, inputs, audit = (load(source_paths[name]) for name in ("roster", "clean_inputs", "gold_audit"))
    candidates, exclusions = derive_pool(roster, inputs, audit)
    # Read only the three clean identity columns, never patch or private tests.
    import pyarrow.parquet as pq
    public_rows = pq.read_table(dataset, columns=["instance_id", "repo", "base_commit"]).to_pylist()
    benchmark = unique(public_rows, "frozen benchmark")
    if len(benchmark) != 860:
        raise ValueError("Frozen benchmark is not 860 tasks")
    for row in candidates + exclusions:
        identity = benchmark.get(row["instance_id"])
        if identity is None or any(row[k] != identity[k] for k in ("repo", "base_commit")):
            raise ValueError("Frozen benchmark identity mismatch")
        for path_key, hash_key in (("gold_path", "gold_sha256"), ("index_path", "index_sha256")):
            if sha256(row[path_key]) != row[hash_key]:
                raise ValueError("Frozen R2 artifact changed: " + row["instance_id"])
        job = load(row["job_path"])
        if any(job[k] != row[k] for k in ("instance_id", "repo", "base_commit")):
            raise ValueError("Clean job identity mismatch: " + row["instance_id"])
        if not Path(row["snapshot_path"]).is_dir():
            raise FileNotFoundError("Missing base snapshot: " + row["instance_id"])
        row["job_sha256"] = sha256(row["job_path"])
    selected, preview = first_unique_preview(candidates)
    if len(selected) != 50:
        raise ValueError("Insufficient unique repository candidates even before qualification")
    common = {"experiment": "repair50_20261024", "seed": SEED,
              "dataset_revision": REVISION, "dataset_sha256": DATASET_SHA256,
              "hash_algorithm": "SHA256('repair50-v1\\0' + '20261024' + '\\0' + revision + '\\0' + instance_id)",
              "hash_encoding": "UTF-8; actual NUL separators (U+0000)",
              "sort_order": ["sampling_hash", "instance_id"],
              "scope": "既有函数目标任务上的开发诊断实验",
              "source_sha256": source_hashes,
              "candidate_count": len(candidates),
              "candidate_unique_repositories": len({r["repo"] for r in candidates}),
              "formal_qualified_count": 0, "API_requests": 0,
              "model_or_API_called": False, "sealed_data_opened": False}
    artifacts = {}
    def emit(name, payload):
        path = output / name
        durable(path, payload)
        artifacts[name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    emit("candidate_order.csv", csv_bytes(candidates, list(candidates[0])))
    emit("candidate_function_exclusions.csv", csv_bytes(exclusions, list(exclusions[0])))
    emit("provisional_sampling_preview.csv", csv_bytes(preview, list(preview[0])))
    emit("provisional_first50.json", json_bytes({**common,
        "status": "PROVISIONAL_NOT_QUALIFIED_NOT_FORMAL_ROSTER", "formal_roster": False,
        "qualification_checked": False, "task_count": len(selected), "tasks": selected,
        "replacement_policy": "Official qualification only, in the saved 235-candidate order; one repository per final roster. Preview duplicate skips are not permanent exclusions."}))
    qualification = [{"candidate_rank": row["candidate_rank"], "instance_id": row["instance_id"],
                      "repo": row["repo"], "base_commit": row["base_commit"],
                      "reference_patch_pass": BLOCKED, "empty_patch_unresolved": BLOCKED,
                      "qualification_status": BLOCKED, "qualification_attempted": False,
                      "formal_selected": False,
                      "reason": "System Docker executor unavailable; this CPU preparation performs no task test execution."}
                     for row in candidates]
    emit("qualification.csv", csv_bytes(qualification, list(qualification[0])))
    emit("qualified_manifest.json", json_bytes({**common, "status": "NOT_FROZEN_SYSTEM_BLOCKED_DOCKER",
        "frozen": False, "tasks": [], "qualification_status": BLOCKED,
        "qualification_not_checked_is_not_failure": True}))
    receipt = {**common, "preparation_status": "CPU_PREPARATION_COMPLETE_QUALIFICATION_BLOCKED",
               "excluded_empty_target_tasks": len(exclusions),
               "provisional_unique_repository_count": len(selected),
               "provisional_prefix_duplicate_repo_skips": sum(
                   r["preview_reason"] == "DUPLICATE_REPOSITORY_IN_PROVISIONAL_PREVIEW" for r in preview),
               "implementation_sha256": sha256(__file__), "artifacts": artifacts,
               "benchmark_columns_read": ["instance_id", "repo", "base_commit"],
               "history_predictions_read": False, "repair_requests": 0,
               "qualification_performed_by_this_program": False}
    durable(output / "preparation_receipt.json", json_bytes(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = prepare(output=args.output)
    print(json.dumps({key: result[key] for key in (
        "preparation_status", "candidate_count", "candidate_unique_repositories",
        "excluded_empty_target_tasks", "provisional_unique_repository_count",
        "formal_qualified_count", "API_requests")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
