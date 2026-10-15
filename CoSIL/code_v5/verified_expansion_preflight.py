"""Local-only Verified inventory and prospective issue-split checks.

This is a preflight, never an expansion authorization. It does not download,
mine labels, run tests/models, or decode any sealed pruner_test file. Historical
Verified gold keys are only a provisional inventory, not official issue input.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPLIT_SHA = "85d8f77cae0ec000e9bd0bcebe9e649864bbf42dbaa153d2c510b8faafd8a777"
REQUIRED = ("instance_id", "repo", "base_commit", "version", "FAIL_TO_PASS",
            "test_patch", "patch", "problem_statement")
ALLOWED_NEW_LINES = ("A", "C", "D", "e_bm25", "e_anchor")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    path = Path(path)
    if path.name.startswith("pruner_test") or path.resolve().name.startswith("pruner_test"):
        raise PermissionError("Sealed pruner test files must never be decoded")
    return json.loads(path.read_text(encoding="utf-8"))


def local_rows(path):
    path = Path(path)
    if path.name.startswith("pruner_test") or path.resolve().name.startswith("pruner_test"):
        raise PermissionError("Sealed pruner test files must never be decoded")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    value = read_json(path)
    if isinstance(value, dict):
        value = value.get("rows", value.get("instance_ids", list(value.values())))
    if not isinstance(value, list):
        raise ValueError("Local pool/metadata must contain a JSON list or JSONL rows")
    return value


def verified_metadata(path):
    rows = local_rows(path)
    if len(rows) != 500:
        raise ValueError("This preflight expects the full 500-issue Verified snapshot")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or any(key not in row for key in REQUIRED):
            raise ValueError("Official Verified metadata lacks required issue/test fields")
        iid = row["instance_id"]
        if not isinstance(iid, str) or iid in by_id:
            raise ValueError("Verified metadata IDs must be unique strings")
        if any(not isinstance(row[key], str) or not row[key]
               for key in ("repo", "base_commit", "version", "test_patch", "patch", "problem_statement")):
            raise ValueError("Verified metadata has an empty/non-string required field")
        ftp = row["FAIL_TO_PASS"]
        if isinstance(ftp, str):
            ftp = json.loads(ftp)
        if not isinstance(ftp, list) or not ftp or any(not isinstance(t, str) or not t for t in ftp):
            raise ValueError("FAIL_TO_PASS must contain actual nonempty test identities")
        by_id[iid] = row
    return by_id


def ood_ids(path, official_ids, lite_ids):
    """Read actual pool identities; repeated function rows do not duplicate IDs.

    Mechanical identity checks cannot certify that a supplied file is the
    historical v4 pool. Root must separately record its verified provenance.
    """
    rows = local_rows(path)
    if any(not isinstance(row, (str, dict)) for row in rows):
        raise ValueError("OOD source rows must be issue strings or source records")
    ids = {row if isinstance(row, str) else row.get("instance_id") for row in rows}
    if None in ids or any(not isinstance(iid, str) or not iid for iid in ids):
        raise ValueError("OOD source rows lack issue identities")
    if len(ids) != 231:
        raise ValueError("Historical OOD pool must contain exactly 231 unique source IDs")
    if ids & lite_ids:
        raise ValueError("Historical OOD reservation overlaps Lite300")
    if ids - official_ids:
        raise ValueError("Historical OOD reservation contains IDs absent from official Verified input")
    return ids


def allocate(groups, quota, capacities):
    total = sum(len(ids) for ids in groups.values())
    if not total:
        return {key: 0 for key in groups}
    target = {key: quota * len(ids) / total for key, ids in groups.items()}
    counts = {key: min(capacities[key], math.floor(target[key])) for key in groups}
    while sum(counts.values()) < quota:
        available = [key for key in groups if counts[key] < capacities[key]]
        if not available:
            raise ValueError("New issue split cannot satisfy requested capacity")
        chosen = max(available, key=lambda key: (target[key] - counts[key], key))
        counts[chosen] += 1
    return counts


def proposed_new_splits(issues, eligible, old, seed):
    """Prospective repo-stratified 80/10/10, no existing issue is reassigned."""
    groups = defaultdict(list)
    for iid in eligible:
        groups[issues[iid]["repo"]].append(iid)
    quota = len(eligible) // 10
    val_n = allocate(groups, quota, {key: len(ids) for key, ids in groups.items()})
    test_n = allocate(groups, quota, {key: len(ids) - val_n[key] for key, ids in groups.items()})
    splits = {key: [] for key in ("train", "val", "test")}
    for repo in sorted(groups):
        ordered = sorted(groups[repo], key=lambda iid: hashlib.sha256(f"{seed}:{iid}".encode()).hexdigest())
        v, t = val_n[repo], test_n[repo]
        splits["val"].extend(ordered[:v])
        splits["test"].extend(ordered[v:v + t])
        splits["train"].extend(ordered[v + t:])
    splits = {key: sorted(ids) for key, ids in splits.items()}
    merged = {key: sorted(old[key] + splits[key]) for key in splits}
    flattened = [iid for ids in merged.values() for iid in ids]
    if len(flattened) != len(set(flattened)):
        raise ValueError("Existing/new split identity collision or leakage")
    if any(set(old[key]) - set(merged[key]) for key in old):
        raise AssertionError("An existing issue split assignment was lost")
    return {"seed": seed, "method": "new issues only: repo largest-remainder; SHA256-ranked IDs; val/test floor(N/10)",
            "new_splits": splits, "combined_splits": merged,
            "old_split_assignments_preserved": True,
            "not_frozen_or_training_authorized": True}


def inventory(root=ROOT, verified_path=None, ood_path=None):
    root = Path(root)
    source_split = root / "results/v5_pruner/data_v3/split_manifest.json"
    if sha(source_split) != SPLIT_SHA:
        raise ValueError("Original v3 split bytes changed")
    old = read_json(source_split)
    split = old["splits"]
    lite = set(read_json(root / "results/qwen_300/prepared_inputs.json")["instances"])
    flattened = [iid for ids in split.values() for iid in ids]
    if len(lite) != 300 or len(flattened) != 300 or set(flattened) != lite or len(set(flattened)) != 300:
        raise ValueError("Frozen Lite300 split identity mismatch")
    gold_path = root / "evaluation/gt_verified.json"
    provisional = set(read_json(gold_path))
    structures = {p.stem for p in (root / "repo_structures_verified").glob("*.json")}
    blockers = []
    result = {
        "schema_version": 1, "status": "preflight_only_not_expansion_authorization",
        "network_used": False, "mining_started": False, "model_calls": 0,
        "sealed_test_decoded": False, "source_split_sha256": sha(source_split),
        "Lite_unique_ids": len(lite), "existing_split_counts": {key: len(ids) for key, ids in split.items()},
        "historical_gold_inventory": {"path": str(gold_path), "sha256": sha(gold_path), "unique_ids": len(provisional),
            "Lite_intersection_count": len(provisional & lite), "Lite_intersection_ids": sorted(provisional & lite),
            "nonLite_count": len(provisional - lite), "official_metadata_authority": False},
        "structure_inventory": {"directory": str(root / "repo_structures_verified"), "count": len(structures),
            "Lite_count": len(structures & lite), "nonLite_count": len(structures - lite)},
        "local_cache_inventory": [], "allowed_new_label_lines": list(ALLOWED_NEW_LINES),
        "forbidden_new_label_lines": ["B", "e_log"],
        "trigger": "Root must bind actual rank8/dropout0.1 prescription val accuracy <0.80 before download/mining",
        "OOD_provenance_caveat": "A local file's count/hash is not proof that it is the historical v4 reserved pool; root must verify origin.",
    }
    for path in [root / "datasets/SWE-bench_Verified_test", root / "swebench_local/SWE-bench_Verified_test",
                 Path("/home/wdt/.cache/huggingface/datasets"), Path("/home/wdt/.cache/huggingface/hub")]:
        result["local_cache_inventory"].append({"path": str(path), "exists": path.exists(),
            "children": sorted(p.name for p in path.iterdir()) if path.is_dir() else []})
    issues = None
    if verified_path is None:
        blockers.append("Official Verified full issue/test metadata is not supplied locally")
    else:
        issues = verified_metadata(verified_path)
        official = set(issues)
        result["official_input"] = {"path": str(Path(verified_path).resolve()), "sha256": sha(verified_path),
            "unique_ids": len(official), "Lite_intersection_count": len(official & lite),
            "Lite_intersection_ids": sorted(official & lite), "diff_from_historical_gold_ids": sorted(official ^ provisional)}
    if ood_path is None:
        blockers.append("Historical v4 231-issue OOD identities/provenance are missing; exact expansion is not executable")
    elif issues is None:
        blockers.append("OOD identities cannot be certified against absent official metadata")
    else:
        reserved = ood_ids(ood_path, set(issues), lite)
        eligible = set(issues) - lite - reserved
        result["OOD_input"] = {"path": str(Path(ood_path).resolve()), "sha256": sha(ood_path),
                               "unique_ids": len(reserved), "instance_ids": sorted(reserved)}
        result["eligible_after_identity_exclusions"] = {"count": len(eligible), "instance_ids": sorted(eligible)}
        result["split_precheck"] = proposed_new_splits(issues, eligible, split, old["seed"])
    blockers.extend(["Prescription trigger and expansion execution contract are not verified by this inventory tool",
                     "Expanded runtime collector/data/review policy must be independently frozen before training"])
    result["execution_blockers"] = blockers
    result["ready_to_mine"] = False
    result["Lite_B_continues_independently"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified-jsonl", type=Path)
    parser.add_argument("--ood-pool", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inventory(verified_path=args.verified_jsonl, ood_path=args.ood_pool)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists() and args.output.read_text() != data:
            raise FileExistsError("Existing audit snapshot is immutable; choose a new output path")
        if not args.output.exists():
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(data)
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
