"""Prepare auditable static Verified candidates after an explicit root gate.

Default mode validates inputs and proposes splits only. --execute needs the
actual post-prescription trigger, source-derived regenerated OOD and a frozen root
authorization. This stage never runs benchmark tests, trains, calls a model,
fetches repositories, or decodes a sealed pruner_test. Runtime/review remain
pending; its outputs are not an authorized training dataset.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
from code_v5 import verified_expansion_preflight as pre

OOD_SCOPE = "user_authorized_regenerated_Verified_function_name_OOD_v1"
OOD_ADJUDICATION_SHA = "21ae3b4486a3798d21e7a9e057c18819682a8f93ca4e65c1f1142a25be65266f"

ALLOWED = ("A", "C", "D", "e_bm25", "e_anchor")
FROZEN_DEPS = {
    "code_v5/build_pruner_data.py": "95d56df3bf8d3cbbf41d310c41ab71d2693275c6b57b8721fec43ceda3284372",
    "code_v5/static_calls.py": "06abfb41ac155fcb5a04331c6ce9ff34e43758046a87b32de811206ac8a3f4c7",
    "code_v5/refine_pruner_data.py": "7decc711b94dda810de8780f924ef315b8c6d7fcb0b1be560d883990a8783d33",
    "code_v5/refine_pruner_data_v3.py": "18075ca5a26c85bf2a692d74907460176061e00d8ca24bfad8038739d8a9b3e5",
    "code_v3b/build_ground_truth_300.py": "9d80194b376efb2a073f628c630c2da9cf1014b75cbd080941039c55927c93d3",
    "code_v5/verify_review_evidence.py": "7eb0584e49ba2ccc9b3c222d38a7ac1a418d6e7cbc9475552cd644ab9c396329",
}


def read(path):
    forbid_test_decoder(path)
    return pre.read_json(path)


def rows(path):
    forbid_test_decoder(path)
    return pre.local_rows(path)


def forbid_test_decoder(path):
    if "pruner_test" in Path(path).name or "pruner_test" in Path(path).resolve().name:
        raise PermissionError("No old or new sealed pruner test preview may be decoded")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def encoded(value):
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in value).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def exclusive_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text() != data:
            raise FileExistsError("Immutable stage artifact differs: " + str(path))
    else:
        with path.open("x", encoding="utf-8") as f:
            f.write(data)


def code_bindings():
    names = list(FROZEN_DEPS) + ["code_v5_verified/__init__.py", "code_v5_verified/prepare_static_extension.py",
                                  "code_v5_verified/static_miner_no_logs.py",
                                  "code_v5_verified/regenerate_ood_manifest.py",
                                  "code_v5/verified_expansion_preflight.py"]
    result = {name: pre.sha(ROOT / name) for name in names}
    if any(result[name] != expected for name, expected in FROZEN_DEPS.items()):
        raise RuntimeError("A frozen graph/gold/miner/v3 dependency changed")
    return result


def official_inputs(metadata, source_receipt):
    forbid_test_decoder(metadata)
    data = pre.verified_metadata(metadata)
    source = read(source_receipt)
    if (source.get("dataset") != "SWE-bench/SWE-bench_Verified"
            or source.get("all500_required_issue_and_test_metadata_valid") is not True
            or source.get("unique_official_IDs") != 500
            or Path(source["normalized_full_metadata_jsonl_path"]).resolve() != Path(metadata).resolve()
            or source.get("normalized_full_metadata_jsonl_sha256") != pre.sha(metadata)
            or not isinstance(source.get("revision"), str) or len(source["revision"]) != 40
            or source.get("parquet_sha256") != pre.sha(source["parquet_path"])):
        raise RuntimeError("Official full metadata/source snapshot is not bound")
    return data, source


def reserve_OOD(manifest_path, official_issues, lite_ids):
    if manifest_path is None or not Path(manifest_path).is_file():
        raise RuntimeError("New source-derived OOD manifest missing; no mining")
    m = read(manifest_path)
    meta = m["metadata"]
    if (m.get("scope") != OOD_SCOPE or m.get("complete_source_derived") is not True
            or m.get("historical_231_pool_reconstructed") is not False
            or meta.get("user_adjudication_sha256") != OOD_ADJUDICATION_SHA
            or pre.sha(meta["user_adjudication_path"]) != OOD_ADJUDICATION_SHA
            or pre.sha(meta["script_path"]) != meta["script_sha256"]
            or m.get("graphs_mined") is not False or m.get("training_started") is not False
            or m.get("old_pruner_test_decoded") is not False):
        raise RuntimeError("OOD manifest lacks exact new user/source-derived authority")
    from code_v5_verified.regenerate_ood_manifest import classify, RULE
    if m["matching_rule"].get("method") != RULE:
        raise RuntimeError("Regenerated matching rule differs from explicit casefold substring")
    nonlite = set(official_issues) - lite_ids
    index = {r["instance_id"]: r for r in m["records"]}
    if len(m["records"]) != len(nonlite) or set(index) != nonlite:
        raise RuntimeError("OOD source records fail full nonLite identity alignment")
    for iid, record in index.items():
        if record["official_metadata_row_sha256"] != digest(official_issues[iid]):
            raise RuntimeError("OOD official row fingerprint drift")
        gold = read(record["gold_path"])
        if pre.sha(record["gold_path"]) != record["gold_sha256"] or record.get("source_evidence_complete") is not True:
            raise RuntimeError("OOD base/after gold source artifact changed")
        for item in gold["full_source_archive"]:
            if pre.sha(item["path"]) != item["sha256"]: raise RuntimeError("OOD full source archive changed")
        expected = classify(official_issues[iid], gold)
        if any(record.get(k) != v for k, v in expected.items()):
            raise RuntimeError("OOD matching/gold metadata no longer reproduces source-backed rule")
    reserved = {iid for iid, record in index.items() if record["reserved_for_OOD"]}
    eligible = nonlite - reserved
    if (m.get("instance_ids") != sorted(reserved) or m.get("actual_reserved_count") != len(reserved)
            or m.get("mining_eligible_instance_ids") != sorted(eligible)
            or m.get("actual_mining_eligible_count") != len(eligible)
            or m.get("no_function_gold_reserved_count") != sum(r["no_function_gold"] for r in index.values())
            or reserved & lite_ids):
        raise RuntimeError("Actual regenerated OOD/eligible counts or identities differ; never force231")
    return reserved


def prescription_trigger(path, expected_sha):
    if pre.sha(path) != expected_sha:
        raise RuntimeError("Actual post-prescription report bytes differ")
    report = read(path)
    if (report.get("track") != "exploratory" or report.get("test_opened") is not False
            or report.get("experiment_condition") != "rank8_dropout0.1_alpha32"):
        raise RuntimeError("Only the actual unopened-test rank8/dropout0.1 report can trigger expansion")
    model = report["models"]["reranker"]; summary_path = Path(model["training_summary_path"])
    if pre.sha(summary_path) != model["summary_sha256"]:
        raise RuntimeError("Report does not bind real completed training summary")
    summary = read(summary_path); config = read(summary_path.with_name("training_manifest.json"))
    peak = summary["checkpoint_assessments"]["best"]
    acc = peak["val"]["overall"]["accuracy"]
    if (summary.get("kind") != "reranker" or summary.get("epochs_completed", 0) < 1
            or summary.get("test_opened") is not False
            or config.get("rank") != 8 or config.get("dropout") != .1 or config.get("alpha") != 32
            or report["comparison"]["post_regularization_peak"] != peak
            or type(acc) not in (int, float) or not 0 <= acc < .80
            or report.get("expansion_trigger_val_accuracy_lt_0_80") is not True):
        raise RuntimeError("No genuine completed prescription val<0.80 trigger")
    return {"path": str(Path(path).resolve()), "sha256": expected_sha, "val_accuracy": acc,
            "training_summary_sha256": pre.sha(summary_path), "training_manifest_sha256": pre.sha(summary_path.with_name("training_manifest.json"))}


def plan(metadata, source_receipt, ood_manifest):
    issues, official = official_inputs(metadata, source_receipt)
    old_path = ROOT / "results/v5_pruner/data_v3/split_manifest.json"
    if pre.sha(old_path) != pre.SPLIT_SHA:
        raise RuntimeError("Original issue split changed")
    old = read(old_path); lite = set(read(ROOT / "results/qwen_300/prepared_inputs.json")["instances"])
    old_ids = [iid for ids in old["splits"].values() for iid in ids]
    if len(old_ids) != 300 or len(set(old_ids)) != 300 or set(old_ids) != lite:
        raise RuntimeError("Original fixed split differs from Lite300")
    reserved = reserve_OOD(ood_manifest, issues, lite)
    eligible = set(issues) - lite - reserved
    proposed = pre.proposed_new_splits(issues, eligible, old["splits"], old["seed"])
    return {"schema_version": 1, "stage": "Verified_plus_B_static_preparation", "training_allowed": False,
            "test_open_allowed": False, "runtime_collection_started": False, "review_complete": False,
            "metadata_path": str(Path(metadata).resolve()), "metadata_sha256": pre.sha(metadata),
            "official_source_receipt_path": str(Path(source_receipt).resolve()), "official_source_receipt_sha256": pre.sha(source_receipt),
            "verified_revision": official["revision"], "ood_manifest_path": str(Path(ood_manifest).resolve()),
            "ood_manifest_sha256": pre.sha(ood_manifest), "reserved_OOD_IDs": sorted(reserved),
            "OOD_scope": OOD_SCOPE, "OOD_user_adjudication_sha256": OOD_ADJUDICATION_SHA,
            "eligible_new_IDs_sha256": digest(sorted(eligible)),
            "Lite_intersection_IDs": sorted(set(issues) & lite), "eligible_new_IDs": sorted(eligible),
            "old_split_sha256": pre.SPLIT_SHA, "new_split_proposal": proposed,
            "allowed_new_sources": list(ALLOWED), "code_sha256": code_bindings()}


def authorize(planned, auth_path, output):
    if auth_path is None:
        raise RuntimeError("Execution needs a root frozen authorization; plan is not approval")
    auth = read(auth_path)
    expected = {"enabled": True, "stage": planned["stage"], "track": "exploratory",
                "test_open_allowed": False, "llm_labels_allowed": False, "fetch_repositories_allowed": False,
                "allowed_new_sources": list(ALLOWED), "old_split_sha256": pre.SPLIT_SHA,
                "metadata_sha256": planned["metadata_sha256"], "official_source_receipt_sha256": planned["official_source_receipt_sha256"],
                "ood_manifest_sha256": planned["ood_manifest_sha256"], "preparation_code_sha256": planned["code_sha256"]}
    expected.update(OOD_scope=OOD_SCOPE, OOD_user_adjudication_sha256=OOD_ADJUDICATION_SHA,
                    eligible_new_IDs_sha256=planned["eligible_new_IDs_sha256"])
    if any(auth.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Root authorization fails exact input/source/test/label/code binding")
    if Path(auth["output_dir"]).resolve() != Path(output).resolve():
        raise RuntimeError("Static stage output differs from authorized destination")
    trigger = prescription_trigger(auth["prescription_report_path"], auth["prescription_report_sha256"])
    independent = read(auth["OOD_independent_audit_path"])
    if (pre.sha(auth["OOD_independent_audit_path"]) != auth["OOD_independent_audit_sha256"]
            or independent.get("passed") is not True
            or independent.get("cases_checked") != 407
            or independent.get("manifest_sha256") != planned["ood_manifest_sha256"]
            or Path(independent["manifest_path"]).resolve() != Path(planned["ood_manifest_path"]).resolve()
            or independent.get("pruner_test_decoded") is not False
            or pre.sha(independent["script_path"]) != independent["script_sha256"]):
        raise RuntimeError("Independent OOD source/matching audit is not bound to this manifest")
    old_decision = Path(auth["old_B_decision_path"])
    if pre.sha(old_decision) != auth["old_B_decision_sha256"]:
        raise RuntimeError("Existing B frozen decision changed")
    return auth, trigger, old_decision


def existing_B_rows(decision):
    """Construction only: regenerate old test-role rows from pool, hash not decode sealed test."""
    from code_v5 import runtime_filtered_policy as B
    from code_v5 import build_pruner_data as miner
    stats, _, split_ids, _ = B.validate_decision(B.B_TRAINING, decision)
    raw_pool = rows(B.B_RAW / "candidate_pool.jsonl")
    chosen, _ = miner.sample_rows(raw_pool, 20261013)
    signature = rows(B.B_TRAINING / "human_review_codex_reviewed.jsonl")
    excluded = {B.triple(r) for r in signature if r["label_error"]}
    old = [r for r in chosen if B.triple(r) not in excluded]
    for role in ("train", "val", "test"):
        if digest(encoded([r for r in old if r["split"] == role])) != pre.sha(B.B_TRAINING / f"pruner_{role}.jsonl"):
            raise RuntimeError("Existing B row reconstruction differs; preserve old splits and labels")
    if sum(r["label"] for r in old) != 1542 or miner.summarize(old) != stats["selected"]:
        raise RuntimeError("Original 1542 eligibility changed or old excluded C resurrected")
    return old, {"decision_path": str(decision), "decision_sha256": pre.sha(decision),
                 "statistics_sha256": pre.sha(B.B_TRAINING / "statistics.json"),
                 "pool_sha256": pre.sha(B.B_RAW / "candidate_pool.jsonl"),
                 "split_sha256": pre.sha(B.B_TRAINING / "split_manifest.json"),
                 "split_hashes": {r: pre.sha(B.B_TRAINING / f"pruner_{r}.jsonl") for r in ("train", "val", "test")},
                 "old_test_role_reconstructed_only_for_preparation_hash": True, "old_test_file_decoded": False}


def dedup_new_preserving_old(new, old):
    from code_v5 import build_pruner_data as miner
    clean, audit = miner.deduplicate_inputs(new)
    old_inputs = {r["input_sha256"] for r in old}
    rejected = [r for r in clean if r["input_sha256"] in old_inputs]
    clean = [r for r in clean if r["input_sha256"] not in old_inputs]
    audit["new_pairs_colliding_with_fixed_old_inputs_dropped"] = len(rejected)
    return clean, audit, [{"instance_id": r["instance_id"], "function_id": r["function_id"],
        "input_sha256": r["input_sha256"], "reason": "protect_frozen_old_input_identity_and_label"} for r in rejected]


def mine_one(iid, issue, split, directory, authoritative_gold_path=None):
    """Real base direct graph + exact changed-line gold + unchanged v3 rules."""
    from code_v3b.build_ground_truth_300 import derive
    from code_v5 import static_calls as graph, build_pruner_data as miner, refine_pruner_data_v3 as v3
    from code_v5.verify_review_evidence import source_file
    graph_dir = directory / "graphs"; graph_dir.mkdir(exist_ok=True)
    gold = read(authoritative_gold_path) if authoritative_gold_path else derive(issue)
    if gold["instance_id"] != iid or gold["repo"] != issue["repo"] or gold["base_commit"] != issue["base_commit"]:
        raise RuntimeError("Full source-derived gold issue/base identity mismatch")
    exclusive_json(directory / "gold" / (iid + ".json"), gold)
    graph.build_one((iid, issue, str(graph_dir), graph.version_hash()))
    gp = graph_dir / (iid + ".json")
    from code_v5_verified.static_miner_no_logs import prepare_miner
    no_log_miner, adapter = prepare_miner()
    # Original old miner cannot accept missing histories. Its explicit copied
    # AST adapter removes only that loop; no fake case or event JSON is written.
    candidate, counts, evidence = no_log_miner(iid, issue, gold, gp, None, split, "Verified_new_unclassified")
    exclusive_json(directory / "no_log_miner_derivation.json", adapter)
    if any(set(r["label_sources"]) - set(ALLOWED) for r in candidate):
        raise RuntimeError("New issue unexpectedly received B/e_log or invented source")
    kept, exclusions = v3.refine_issue(iid, candidate, gold, issue, gp, evidence, source_file)
    inventory = read(gp); physical = {n["id"]: n for n in inventory["functions"]}; cache = {}
    full_sources = {}
    for r in candidate:
        source = v3.restore_complete(inventory, physical[r["function_id"]], cache, source_file)
        full_sources[r["function_id"]] = {"file": r["function_file"], "def_line": r["function_def_line"],
            "base_blob_sha1": source["base_blob_sha1"], "full_source_sha256": source["full_source_sha256"],
            "full_source": source["function_source"]}
    exclusive_json(directory / "full_source_cache" / (iid + ".json"), {"instance_id": iid,
                   "repo": issue["repo"], "base_commit": issue["base_commit"], "functions": full_sources})
    for row in kept:
        row["runtime_filter"] = {"qualified": False, "status": "runtime_collection_pending",
            "eligibility_basis": "static_only_runtime_not_collected", "static_v3_eligible": True,
            "interpretation": "Preparation only; no failed-path absence evidence exists yet"}
    return {"instance_id": iid, "split": split, "gold_path": str(directory / "gold" / (iid + ".json")),
            "gold_sha256": pre.sha(directory / "gold" / (iid + ".json")), "graph": evidence,
            "full_source_cache_sha256": pre.sha(directory / "full_source_cache" / (iid + ".json")),
            "mining_counts": counts, "rows": kept, "negative_exclusions": exclusions,
            "input_metadata_sha256": digest(issue)}


def execute(planned, auth_path, output):
    output = Path(output).resolve()
    if output.parent != ROOT / "results/v5_pruner" or not output.name.startswith("verified_extension_"):
        raise PermissionError("Expansion needs a separate new artifact directory")
    replayed_plan = plan(planned["metadata_path"], planned["official_source_receipt_path"], planned["ood_manifest_path"])
    if planned != replayed_plan:
        raise RuntimeError("Static plan identity/split/source changed; recompute from real frozen inputs")
    auth, trigger, decision = authorize(planned, auth_path, output)
    old, old_provenance = existing_B_rows(decision)
    issues, _ = official_inputs(planned["metadata_path"], planned["official_source_receipt_path"])
    gold_by_id = {r["instance_id"]: r["gold_path"] for r in read(planned["ood_manifest_path"])["records"]}
    split = {iid: name for name, ids in planned["new_split_proposal"]["new_splits"].items() for iid in ids}
    if set(split) != set(planned["eligible_new_IDs"]) or set(split) & {r["instance_id"] for r in old}:
        raise RuntimeError("Expansion overlaps original Lite or changes fixed identity assignment")
    manifest = {"plan": planned, "authorization_sha256": pre.sha(auth_path), "trigger": trigger,
                "original_B": old_provenance, "training_allowed": False, "test_open_allowed": False}
    output.mkdir(parents=True, exist_ok=True); exclusive_json(output / "preparation_manifest.json", manifest)
    all_new = []; issue_receipts = []
    for number, iid in enumerate(planned["eligible_new_IDs"], 1):
        cache = output / "cases" / (iid + ".json")
        if cache.exists():
            cache_seal = read(cache.with_suffix(".sha256.json"))
            if cache_seal.get("sha256") != pre.sha(cache):
                raise RuntimeError("Cached new labels/receipt bytes changed")
            result = read(cache)
            if result["input_metadata_sha256"] != digest(issues[iid]) or result["split"] != split[iid]:
                raise RuntimeError("Cached new issue input/split changed")
            for path, expected in [(result["graph"]["graph_path"], result["graph"]["graph_sha256"]),
                                   (result["gold_path"], result["gold_sha256"]),
                                   (output / "full_source_cache" / (iid + ".json"), result["full_source_cache_sha256"])]:
                if pre.sha(path) != expected: raise RuntimeError("Cached new graph/gold/source changed")
        else:
            result = mine_one(iid, issues[iid], split[iid], output, gold_by_id[iid]); exclusive_json(cache, result)
            exclusive_json(cache.with_suffix(".sha256.json"), {"sha256": pre.sha(cache), "input_metadata_sha256": digest(issues[iid])})
        all_new.extend(result["rows"]); issue_receipts.append({k: v for k, v in result.items() if k not in ("rows", "negative_exclusions")})
        if number % 5 == 0: print(f"Static preparation {number}/{len(split)}; runtime/review/train still pending", flush=True)
    from code_v5 import build_pruner_data as miner
    new, dedup, collisions = dedup_new_preserving_old(all_new, old)
    selected, sampling = miner.sample_rows(new, 20261013)
    merged = sorted(old + selected, key=lambda r: (r["instance_id"], r["function_id"]))
    for name, data in [("static_candidate_pool.jsonl", new), ("new_static_selected.jsonl", selected)]:
        path = output / name
        contents = encoded(data)
        if path.exists() and path.read_bytes() != contents: raise FileExistsError(path)
        if not path.exists(): path.write_bytes(contents)
    split_files = {}
    for role in ("train", "val", "test"):
        path = output / ("static_pruner_" + role + "_preview.jsonl")
        data = encoded([r for r in merged if r["split"] == role])
        if path.exists() and path.read_bytes() != data: raise FileExistsError(path)
        if not path.exists(): path.write_bytes(data)
        split_files[role] = {"path": str(path), "sha256": pre.sha(path), "count": sum(r["split"] == role for r in merged)}
    exclusive_json(output / "static_test_preview_seal.json", {"test_open_allowed": False,
        "test_rows_decoded": False, "test_constructed_from_pool_only": True, "frozen_files": split_files})
    exclusive_json(output / "new_input_collision_exclusions.json", collisions)
    exclusive_json(output / "runtime_requests.json", {"execution_started": False, "collector_version": None,
        "requests": [{"instance_id": iid, "repo": issues[iid]["repo"], "base_commit": issues[iid]["base_commit"],
            "version": issues[iid]["version"], "FAIL_TO_PASS": issues[iid]["FAIL_TO_PASS"],
            "test_patch_sha256": hashlib.sha256(issues[iid]["test_patch"].encode()).hexdigest(),
            "gold_path": str(output / "gold" / (iid + ".json")), "graph_path": str(output / "graphs" / (iid + ".json")),
            "metadata_source_path": planned["metadata_path"], "runtime_state": "pending_not_static_failure"} for iid in split]})
    # Preserve old row identities/inputs/labels, including pool-regenerated test role.
    old_index = {(r["instance_id"], r["function_id"]): r for r in old}
    actual = {(r["instance_id"], r["function_id"]): r for r in merged if r["instance_id"] not in split}
    if actual != old_index or code_bindings() != planned["code_sha256"]:
        raise RuntimeError("Historical rows/labels or frozen preparation code drifted")
    receipt = {"stage_complete": True, "stage": planned["stage"], "training_allowed": False,
        "runtime_coverage_complete": False, "source_runtime_review_complete": False,
        "old_selected": miner.summarize(old), "new_static_selected": miner.summarize(selected),
        "combined_static_preview": miner.summarize(merged), "new_sampling": sampling, "new_dedup": dedup,
        "old_labels_input_bytes_and_issue_splits_preserved": True, "old_ineligible4C_not_resurrected": True,
        "new_sources": dict(Counter(s for r in selected for s in r["label_sources"])), "issue_receipts": issue_receipts,
        "case_artifact_sha256": {str(p): pre.sha(p) for p in sorted((output / "cases").glob("*.json"))},
        "prescription": trigger, "original_B": old_provenance, "model_calls": 0, "test_performance_opened": False,
        "limitation": "Static preparation only. Runtime profile and failed-test coverage, conservative fallback decisions and fresh TRAIN source/runtime review remain mandatory; these previews cannot authorize training."}
    exclusive_json(output / "static_preparation_receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--ood-manifest", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    planned = plan(args.metadata, args.source_receipt, args.ood_manifest)
    if args.execute:
        receipt = execute(planned, args.authorization, args.output)
        print(json.dumps({"stage_complete": True, "training_allowed": False, "new": receipt["new_static_selected"]}))
    else:
        destination = args.output.resolve()
        protected = [ROOT / "results/v5_pruner" / n for n in
                     ("data", "data_v2", "data_v3", "data_v3_noise_disclosed", "data_v3_runtime_filtered", "data_v3_runtime_filtered_reviewed")]
        if not destination.is_relative_to(ROOT / "results/v5_pruner") or any(destination.is_relative_to(p) for p in protected):
            raise PermissionError("Plan needs a separate new audit file; frozen source data is protected")
        exclusive_json(args.output, planned)
        print(json.dumps({"plan_only": True, "training_allowed": False, "new_IDs": len(planned["eligible_new_IDs"])}))


if __name__ == "__main__":
    main()
