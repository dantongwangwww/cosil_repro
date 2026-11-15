"""Project the frozen 280-task cohort and reuse the preceding 100 CPU graphs.

No new sampling occurs: the extension is the ordered set difference of the same
metadata-only hash ordering and the already frozen 100-task manifest. Historical
predictions and scores are read only after this difference is established.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare as base

ROOT = Path(__file__).resolve().parents[1]
TOKENIZER_CACHE_FILES = frozenset(("9b5ad71b2ce5302211f9c61530b329a4922fc6a4",
                                   "fb374d419588a4632f3f557e76b4b70aebbca790"))


def extension_records(full, previous):
    """Keep the parent ordering and reject identity drift or duplicate records."""
    all_ids = [r["instance_id"] for r in full]
    old_ids = [r["instance_id"] for r in previous]
    if len(set(all_ids)) != len(all_ids) or len(set(old_ids)) != len(old_ids):
        raise ValueError("Duplicate task identity in frozen manifests")
    by_id = {r["instance_id"]: r for r in full}
    for old in previous:
        if old["instance_id"] not in by_id:
            raise ValueError("Historical task absent from parent cohort")
        current = by_id[old["instance_id"]]
        for key in base.ROSTER_KEYS:
            if current[key] != old[key]:
                raise ValueError("Historical task metadata drift: " + key)
    old_set = set(old_ids)
    return [r for r in full if r["instance_id"] not in old_set]


def graph_binding(old_run, record, builder_sha):
    """Check the exact official builder, source tree, and existing pickle bytes."""
    iid = record["instance_id"]
    graph = old_run / "public/graph_index" / (iid + ".pkl")
    receipt_path = graph.with_suffix(".receipt.json")
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get("instance_id") != iid or receipt.get("status") != "success"
            or receipt.get("graph_ready") is not True
            or receipt.get("snapshot_tree_sha256") != record["snapshot_tree_sha256"]
            or receipt.get("official_builder_sha256") != builder_sha
            or receipt.get("graph_sha256") != base.sha(graph)):
        raise ValueError("Historical graph/source binding changed: " + iid)
    return {"graph": str(graph), "graph_sha256": base.sha(graph),
            "receipt": str(receipt_path), "receipt_sha256": base.sha(receipt_path)}


def result_binding(old_run, record):
    """Reuse the frozen view only with its unchanged original inference output."""
    iid = record["instance_id"]
    original = old_run / "outputs" / iid / "result.json"
    requested = old_run / "audits/postprocess_requested_file_final100/outputs" / iid / "result.json"
    native = json.loads(original.read_text())
    view = json.loads(requested.read_text())
    for value in (native, view):
        if value.get("terminal") is not True:
            raise ValueError("Refusing to reuse a nonterminal historical result")
        if any(value.get(k) != record[k] for k in ("instance_id", "repo", "base_commit")):
            raise ValueError("Historical result identity mismatch")
    actual = base.sha(original)
    if view.get("source_inference_result_sha256") != actual:
        raise ValueError("Requested-file view is not bound to the original raw output")
    return {"original_run": str(old_run), "original_result": str(original),
            "original_result_sha256": actual, "requested_file_result": str(requested),
            "requested_file_result_sha256": base.sha(requested)}


def tokenizer_binding(old_run):
    """The sandbox requires the same two prewarmed, offline tokenizer tables."""
    source = old_run / "public/tokenizer_cache"
    if not source.is_dir() or {p.name for p in source.iterdir()} != TOKENIZER_CACHE_FILES:
        raise ValueError("The exact prewarmed tokenizer cache is missing or incomplete")
    files = []
    for name in sorted(TOKENIZER_CACHE_FILES):
        path = source / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Tokenizer tables must be nonempty regular files")
        files.append({"path": name, "sha256": base.sha(path), "bytes": path.stat().st_size})
    return {"source": str(source), "files": files, "tree_sha256": base.digest(files)}


def copy_tokenizer(cache, out):
    for item in cache["files"]:
        if base.sha(Path(cache["source"]) / item["path"]) != item["sha256"]:
            raise ValueError("Tokenizer source changed before projection")
    destination = out / "public/tokenizer_cache"
    destination.mkdir()
    for item in cache["files"]:
        source = Path(cache["source"]) / item["path"]
        if base.sha(source) != item["sha256"]:
            raise ValueError("Tokenizer source changed before projection")
        target = destination / item["path"]
        shutil.copyfile(source, target)
        if base.sha(target) != item["sha256"]:
            raise ValueError("Copied tokenizer cache SHA differs")
        target.chmod(0o444)


def replace_json(path, value):
    temporary = path.with_name("." + path.name + ".extension.tmp")
    base.write(temporary, value)
    temporary.replace(path)


def prepare_extension(cosil_root, run_dir, old_run):
    root = Path(cosil_root).resolve(strict=True)
    out = Path(run_dir).absolute()
    old_run = Path(old_run).resolve(strict=True)
    old_manifest_path = old_run / "selection/manifest.json"
    old = json.loads(old_manifest_path.read_text())
    if old["n"] != 100 or len(old["records"]) != 100:
        raise ValueError("The preceding frozen manifest must contain 100 tasks")
    parent_path = root / "papers/SFPruner/datasets/test_280/instances.jsonl"
    candidates = [json.loads(line) for line in parent_path.read_text().splitlines() if line.strip()]
    if len(candidates) != 280:
        raise ValueError("The parent cohort must contain exactly 280 tasks")
    ordered, _ = base.choose(candidates, seed=base.SEED, count=280)
    remaining = extension_records(ordered, old["records"])
    if len(remaining) != 180 or [r["instance_id"] for r in ordered[:100]] != [r["instance_id"] for r in old["records"]]:
        raise ValueError("Frozen 100-task prefix or 180-task extension changed")

    # Freeze metadata selection before reading any historical prediction or gold.
    original_order = [r["instance_id"] for r in ordered]
    remaining_ids = {r["instance_id"] for r in remaining}
    cache = tokenizer_binding(old_run)
    csv_path = parent_path.with_name("test_280.csv")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        parent_rows = list(csv.DictReader(handle))
    if len(parent_rows) != 280 or {r["instance_id"] for r in parent_rows} != set(original_order):
        raise ValueError("Parent CSV and metadata manifest differ")
    parent_by_id = {r["instance_id"]: r for r in parent_rows}
    for record in ordered:
        if any(parent_by_id[record["instance_id"]][k] != record[k] for k in base.ROSTER_KEYS):
            raise ValueError("Parent CSV task identity drift")
    builder_sha = base.sha(ROOT / "dependency_graph/build_graph.py")
    reuse = {}
    for record in old["records"]:
        iid = record["instance_id"]
        reuse[iid] = graph_binding(old_run, record, builder_sha) | result_binding(old_run, record)
    protected = {str(old_manifest_path): base.sha(old_manifest_path), str(parent_path): base.sha(parent_path),
                 str(csv_path): base.sha(csv_path)}
    protected.update({str(Path(cache["source"]) / item["path"]): item["sha256"] for item in cache["files"]})
    for item in reuse.values():
        for key in ("graph", "receipt", "original_result", "requested_file_result"):
            protected[item[key]] = item[key + "_sha256"]

    manifest = base.prepare(root, out, seed=base.SEED, count=280)
    copy_tokenizer(cache, out)
    old_by_id = {r["instance_id"]: r for r in old["records"]}
    old_gold = json.loads((old_run / "private/gold.json").read_text())
    old_inventory = json.loads((old_run / "private/inventory.json").read_text())
    gold = json.loads((out / "private/gold.json").read_text())
    inventory = json.loads((out / "private/inventory.json").read_text())
    (out / "public/graph_index").mkdir()
    for record in manifest["records"]:
        iid = record["instance_id"]
        record["execution_origin"] = "new180" if iid in remaining_ids else "existing100_reuse"
        if iid in reuse:
            if (record["snapshot_tree_sha256"] != old_by_id[iid]["snapshot_tree_sha256"]
                    or gold[iid] != old_gold[iid] or inventory[iid] != old_inventory[iid]
                    or base.sha(out / record["instance"]) != base.sha(old_run / old_by_id[iid]["instance"])):
                raise ValueError("Original base inputs or private scoring assets changed: " + iid)
            record.update(result_binding(old_run, record))
            for key, suffix in (("graph", ".pkl"), ("receipt", ".receipt.json")):
                (out / "public/graph_index" / (iid + suffix)).symlink_to(Path(reuse[iid][key]).resolve(strict=True))
    with (out / "private/comparison_original.csv").open(encoding="utf-8-sig", newline="") as handle:
        historical = {r["instance_id"]: r for r in csv.DictReader(handle)}
    for iid, row in parent_by_id.items():
        if any(historical[iid].get(k) != value for k, value in row.items()):
            raise ValueError("Historical arm record differs from frozen parent CSV: " + iid)
    shutil.copyfile(parent_path, out / "selection/parent_instances.jsonl")
    shutil.copyfile(csv_path, out / "private/parent_test_280.csv")
    manifest.update(
        execution_origin_counts={"existing100_reuse": 100, "new180": 180},
        original_100_manifest=str(old_manifest_path), original_100_manifest_sha256=protected[str(old_manifest_path)],
        extension_order="Ordered set difference of full fixed SHA256 ordering minus the unchanged original 100-task manifest; no new random sampling",
        unified_postprocessing="format compatibility plus requested_file-constrained line mapping for every one of 280 tasks; original raw outputs retained",
        prerequisite_remote_commit="49e740117c86d654849e1a23a592bd1b1b94ecda",
        tokenizer_cache=cache,
    )
    manifest["source_files_sha256"].update({str(csv_path): protected[str(csv_path)], str(old_manifest_path): protected[str(old_manifest_path)]})
    replace_json(out / "selection/manifest.json", manifest)
    extension = {**manifest, "n": 180, "records": [r for r in manifest["records"] if r["instance_id"] in remaining_ids],
                 "full_manifest": "selection/manifest.json", "full_manifest_sha256": base.sha(out / "selection/manifest.json"),
                 "execution_origin_counts": {"new180": 180}}
    extension["source_distribution"] = dict(Counter(r["source_id"] for r in extension["records"]))
    base.write(out / "selection/extension_manifest.json", extension)
    if any(base.sha(path) != expected for path, expected in protected.items()):
        raise ValueError("A historical source changed during preparation")
    receipt = {"status": "FROZEN_READY", "full_n": 280, "new_execution_n": 180, "reused_n": 100,
               "reused_graphs": reuse, "protected_source_sha256": protected,
               "sealed_training_test_opened": False, "new_model_calls": 0, "gpu_used": False,
               "tokenizer_cache": cache,
               "full_manifest_sha256": base.sha(out / "selection/manifest.json"),
               "extension_manifest_sha256": base.sha(out / "selection/extension_manifest.json")}
    base.write(out / "selection/extension_preparation_receipt.json", receipt)
    return {k: v for k, v in receipt.items() if k not in ("reused_graphs", "protected_source_sha256")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cosil-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--old-run", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_extension(args.cosil_root, args.run_dir, args.old_run), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
