"""Prepare an immutable LocAgent roster, public base sources, and private R2 assets.

This CPU-only projection never opens sealed training test files, executes target
repositories, reads predictions for selection, or invokes a model.  The input
280-task cohort was selected after observing earlier results; its provenance is
retained, so this reproduction is not presented as an independent blind test.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil


SEED = 20261115
PREFIX = "locagent_rebench100_v1"
PUBLIC_KEYS = ("instance_id", "repo", "base_commit", "problem_statement")
ROSTER_KEYS = ("instance_id", "repo", "base_commit", "source_id")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path, bindings):
    path = Path(path).resolve(strict=True)
    bindings[str(path)] = sha(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                                allow_nan=False) + "\n")


def choose(candidates, *, seed=SEED, count=100):
    """Hash metadata only; retain every candidate and every exclusion decision."""
    if count <= 0:
        raise ValueError("count must be positive")
    ids = set()
    projected = []
    for row in candidates:
        if set(row) != set(ROSTER_KEYS):
            raise ValueError("Roster must contain metadata only: " + str(set(row)))
        if not all(isinstance(row[k], str) and row[k] for k in ROSTER_KEYS):
            raise ValueError("Empty or non-string task identity")
        iid = row["instance_id"]
        if iid in ids or "/" in iid or "\\" in iid or iid in (".", ".."):
            raise ValueError("Duplicate or unsafe instance ID: " + iid)
        ids.add(iid)
        projected.append({**row, "sampling_hash": hashlib.sha256(
            f"{PREFIX}|{seed}|{iid}".encode("utf-8")).hexdigest()})
    projected.sort(key=lambda r: (r["sampling_hash"], r["instance_id"]))
    selected, repos = [], set()
    for rank, row in enumerate(projected, 1):
        repo = row["repo"].casefold()
        reason = "duplicate_repository" if repo in repos else (
            "sample_size_reached" if len(selected) >= count else "selected")
        row.update(rank=rank, decision=reason)
        if reason == "selected":
            repos.add(repo)
            selected.append(row)
    if len(selected) != count:
        raise ValueError(f"Only {len(selected)} distinct repositories; requested {count}")
    return selected, projected


def normalize_gold(raw, expected):
    for key in ("instance_id", "repo", "base_commit"):
        if key in raw and raw[key] != expected[key]:
            raise ValueError("R2 gold identity mismatch: " + key)
    if raw.get("evaluation_revision") != "r2_exact_context_offsets":
        raise ValueError("Only the frozen exact-context-offset R2 gold is allowed")
    result = {
        "status": raw["status"],
        "set_complete": raw.get("existing_function_target_set_complete", raw.get("set_complete")),
        "targets": raw.get("existing_function_targets", raw.get("targets", [])),
        "gold_files": raw["gold_files"],
        "evaluation_revision": raw["evaluation_revision"],
    }
    if result["status"] != "COMPLETE_NONEMPTY" or result["set_complete"] is not True or not result["targets"]:
        raise ValueError("Selected task lost complete nonempty existing-function targets")
    if "regions" in raw:
        result["regions"] = raw["regions"]
    return result


def source_files(snapshot, index):
    """Only index-listed base Python files; no Git or evaluation attachments."""
    snapshot = Path(snapshot).resolve(strict=True)
    files = []
    for name in sorted(index):
        rel = PurePosixPath(name)
        if (not isinstance(name, str) or rel.is_absolute() or ".." in rel.parts
                or ".git" in rel.parts or "\\" in name or rel.suffix != ".py"):
            raise ValueError("Unsafe/non-Python source inventory path: " + str(name))
        path = (snapshot / name).resolve(strict=True)
        if not path.is_relative_to(snapshot) or not path.is_file():
            raise ValueError("Base source escapes its snapshot: " + name)
        actual = sha(path)
        expected = index[name].get("raw_sha256", index[name].get("sha256"))
        if expected is not None and expected != actual:
            raise ValueError("Base source SHA drift: " + name)
        files.append({"path": name, "sha256": actual, "bytes": path.stat().st_size})
    if not files:
        raise ValueError("No base Python sources")
    return files


def prepare(cosil_root, run_dir, *, seed=SEED, count=100):
    root, out = Path(cosil_root).resolve(strict=True), Path(run_dir).absolute()
    bindings = {}
    roster_path = root / "papers/SFPruner/datasets/test_280/instances.jsonl"
    bindings[str(roster_path)] = sha(roster_path)
    candidates = [json.loads(line) for line in roster_path.read_text().splitlines() if line.strip()]
    if len(candidates) != 280:
        raise ValueError("The frozen input cohort must contain exactly 280 tasks")
    selected, ordered = choose(candidates, seed=seed, count=count)
    bundle = root / "papers/SFPruner"
    old_gold = read(bundle / "assets/evaluation/gold.json", bindings)
    old_inventory = read(bundle / "assets/evaluation/inventory.json", bindings)
    new_root = root / "results/sfpruner300_20261114"
    pointers = read(new_root / "selection/r2_sources.private.json", bindings)
    comparison_path = new_root / "reports/逐题定位与资源.csv"
    bindings[str(comparison_path)] = sha(comparison_path)
    with comparison_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        comparison_fields = reader.fieldnames
        comparison_rows = list(reader)
    comparison = {r["instance_id"]: r for r in comparison_rows}
    if len(comparison) != len(comparison_rows):
        raise ValueError("Duplicate IDs in frozen historical comparison")
    plan, gold, inventory = [], {}, {}
    for record in selected:
        iid = record["instance_id"]
        new_job = new_root / "runtime/tasks" / iid / "job.json"
        job_path = new_job if new_job.is_file() else bundle / "assets/runtime" / iid / "job.json"
        job = read(job_path, bindings)
        if any(job.get(k) != record[k] for k in ("instance_id", "repo", "base_commit")):
            raise ValueError("Job/roster identity mismatch: " + iid)
        if not isinstance(job.get("problem_statement"), str) or not job["problem_statement"].strip():
            raise ValueError("Issue text missing: " + iid)
        def resolve(key):
            path = Path(job[key])
            return (path if path.is_absolute() else job_path.parent / path).resolve(strict=True)
        snapshot, index_path = resolve("snapshot"), resolve("code_index")
        index = read(index_path, bindings)
        files = source_files(snapshot, index)
        if new_job.is_file():
            pointer = pointers[iid]
            gold_path = Path(pointer["path"]).resolve(strict=True)
            if sha(gold_path) != pointer["sha256"]:
                raise ValueError("Qualified R2 gold SHA drift: " + iid)
            gold[iid] = normalize_gold(read(gold_path, bindings), record)
            inventory[iid] = {"paths": sorted(index), "function_identities": sorted(
                path + "::" + d["qualified_name"] for path, item in index.items()
                for d in item["definitions"] if d["kind"] == "function")}
        else:
            gold[iid] = normalize_gold(old_gold[iid], record)
            inventory[iid] = old_inventory[iid]
            current = sorted(path + "::" + d["qualified_name"] for path, item in index.items()
                             for d in item["definitions"] if d["kind"] == "function")
            # Historical inventories retain every repository path, including
            # non-Python files.  Preserve that frozen file-scoring inventory;
            # only Python sources belong to the graph-building projection.
            if (set(current) != set(inventory[iid]["function_identities"])
                    or not set(index).issubset(inventory[iid]["paths"])
                    or set(job.get("paths", index)) != set(inventory[iid]["paths"])):
                raise ValueError("Historical inventory/base source mismatch: " + iid)
        if not set(gold[iid]["targets"]).issubset(inventory[iid]["function_identities"]):
            raise ValueError("Gold function absent from base inventory: " + iid)
        if iid not in comparison:
            raise ValueError("Historical comparison row missing: " + iid)
        public_instance = {k: job[k] for k in PUBLIC_KEYS}
        plan.append((record, public_instance, snapshot, files, job_path, index_path))

    # Preflight all source identities before creating any execution assets.
    out.mkdir(parents=True, exist_ok=True)
    for name in ("selection", "public", "private"):
        if (out / name).exists():
            raise FileExistsError("Refusing to overwrite prepared data: " + str(out / name))
    (out / "selection").mkdir()
    (out / "public/tasks").mkdir(parents=True)
    (out / "public/snapshots").mkdir()
    (out / "private").mkdir(mode=0o700)
    public_records, snapshots = [], {}
    for record, instance, snapshot, files, job_path, index_path in plan:
        iid = record["instance_id"]
        task = out / "public/tasks" / iid
        task.mkdir()
        instance_path = task / "instance.json"
        write(instance_path, instance)
        target = out / "public/snapshots" / iid
        target.mkdir()
        for item in files:
            destination = target / item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snapshot / item["path"], destination)
            if sha(destination) != item["sha256"]:
                raise ValueError("Copied source mismatch: " + str(destination))
            destination.chmod(0o444)
        tree_sha = digest(files)
        snapshots[iid] = {"original_snapshot": str(snapshot), "tree_sha256": tree_sha,
                          "python_files": len(files), "bytes": sum(f["bytes"] for f in files), "files": files}
        public_records.append({k: record[k] for k in ROSTER_KEYS} | {
            "sampling_hash": record["sampling_hash"],
            "instance": f"public/tasks/{iid}/instance.json",
            "instance_sha256": sha(instance_path), "snapshot": f"public/snapshots/{iid}",
            "snapshot_tree_sha256": tree_sha, "source_job": str(job_path),
            "source_index": str(index_path)})
    write(out / "private/gold.json", gold)
    write(out / "private/inventory.json", inventory)
    with (out / "private/comparison_original.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=comparison_fields)
        writer.writeheader()
        writer.writerows(comparison[r["instance_id"]] for r in selected)
    with (out / "selection/ordered_candidates.jsonl").open("x", encoding="utf-8") as handle:
        for row in ordered:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write(out / "selection/snapshot_sources.json", snapshots)
    if any(sha(path) != expected for path, expected in bindings.items()):
        raise ValueError("An input changed during preparation")
    manifest = {
        "schema": 1, "status": "FROZEN_READY", "seed": seed, "n": count,
        "input_cohort_n": len(candidates), "sampling_prefix": PREFIX,
        "sampling_algorithm": "SHA256(UTF8(prefix+'|'+str(seed)+'|'+instance_id)), then instance_id; first per repo.casefold(); no outcome access in selection",
        "cohort_origin": "280 tasks selected post hoc from 300 function-evaluable tasks after inspecting earlier arm outcomes; 18 baseline-favored and 2 both-miss tasks excluded",
        "independent_blind_test": False, "new_model_calls": 0,
        "sealed_training_test_opened": False, "records": public_records,
        "source_distribution": dict(Counter(r["source_id"] for r in selected)),
        "source_files_sha256": bindings,
        "public_schema": list(PUBLIC_KEYS),
        "private_assets": ["private/gold.json", "private/inventory.json", "private/comparison_original.csv"],
        "isolation_requirement": "Inference may read public base sources/issue records and graph artifacts only; never mount private, selection, parent CoSIL, home, or credentials",
    }
    write(out / "selection/manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cosil-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    result = prepare(args.cosil_root, args.run_dir, seed=args.seed, count=args.count)
    print(json.dumps({"manifest": str(args.run_dir / "selection/manifest.json"),
                      "status": result["status"], "n": result["n"],
                      "first_three": [r["instance_id"] for r in result["records"][:3]],
                      "independent_blind_test": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
