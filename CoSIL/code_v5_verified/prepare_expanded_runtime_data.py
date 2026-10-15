"""Construct independent C raw data after complete real Verified runtime.

No training, model calls, sealed test decoding, repository downloads or label
invention. Default dry-run refuses incomplete static/runtime receipts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from code_v5 import build_pruner_data as miner
from code_v5 import prepare_runtime_filtered_data as historical_builder
from code_v5 import runtime_filtered_policy as historical
from code_v5_verified import prepare_static_extension as static
from code_v5_verified import expanded_policy as policy

ROOT = policy.ROOT
STATIC = ROOT / "results/v5_pruner/verified_extension_regenerated_ood_v1"
RUNTIME = ROOT / "results/v5_pruner/runtime_coverage_verified_v2/cases_final"
RUNTIME_CODE = ROOT / "code_v5_verified_runtime_v2"


def terminal_runtime_metadata(directory, planned):
    """Validate real formal186 terminal chain; no result or trace decoder here."""
    directory = Path(directory).resolve(); parent = directory.parent
    frozen_path = parent / "execution_policy_frozen.json"; frozen = policy.read_json(frozen_path)
    completion_path = parent / "final_completion_independent_audit.json"
    completion = policy.read_json(completion_path)
    terminal_path = parent / "formal_pipeline_terminal_receipt.json"; terminal = policy.read_json(terminal_path)
    plan_path = parent / "formal_pipeline_plan.json"; plan = policy.read_json(plan_path)
    ids = set(planned["eligible_new_IDs"]); core = frozen["policy_core_sha256"]
    code = frozen["collector_code_sha256"]
    expected_core = hashlib.sha256(json.dumps({k: v for k, v in frozen.items() if k not in (
        "phase", "authorized_run_ids", "created_at", "approved_canaries", "root_authorized", "policy_core_sha256")}, sort_keys=True).encode()).hexdigest()
    if (core != expected_core or frozen.get("phase") != "formal" or frozen.get("root_authorized") is not True
            or frozen.get("pruner_test_labels_may_be_decoded") is not False
            or set(frozen.get("authorized_run_ids", [])) != ids or len(ids) != 186
            or set(frozen.get("eligible_cohort_ids", [])) != ids
            or Path(frozen["result_directory"]).resolve() != directory
            or frozen["OOD_manifest_sha256"] != planned["ood_manifest_sha256"]
            or frozen["official_metadata_sha256"] != planned["metadata_sha256"]):
        raise RuntimeError("Runtime final root policy/cohort/OOD/input core drift")
    if (completion.get("status") != "passed" or completion.get("passed") is not True
            or completion.get("phase") != "formal" or completion.get("completed") != 186 or completion.get("expected") != 186
            or completion.get("errors") != [] or completion.get("policy_core_sha256") != core
            or completion.get("collector_code_sha256") != code or completion.get("result_directory") != str(directory)
            or completion.get("audit_code_sha256") != policy.sha(RUNTIME_CODE / "audit_runtime_results.py")
            or completion.get("OOD_manifest_sha256") != planned["ood_manifest_sha256"]
            or completion.get("model_calls") != 0 or completion.get("GPU_used") is not False
            or completion.get("pruner_test_labels_decoded") is not False):
        raise RuntimeError("No full formal186 independent audit with actual source/resource boundaries")
    if (terminal.get("status") != "complete" or terminal.get("collector_exit_code") != 0 or terminal.get("audit_exit_code") != 0
            or terminal.get("terminal_audit_path") != str(completion_path) or terminal.get("terminal_audit_sha256") != policy.sha(completion_path)
            or terminal.get("plan_path") != str(plan_path) or terminal.get("plan_sha256") != policy.sha(plan_path)
            or terminal.get("policy_core_sha256") != core or terminal.get("canary_results_preserved") is not True
            or terminal.get("model_calls") != 0 or terminal.get("GPU_used") is not False
            or terminal.get("pruner_test_labels_decoded") is not False):
        raise RuntimeError("Formal collector and independent audit lack a successful permanent terminal chain")
    authorization = Path(completion["authorization_path"])
    if (completion["authorization_sha256"] != policy.sha(authorization)
            or authorization.read_bytes() != frozen_path.read_bytes()
            or plan.get("authorization_path") != str(authorization) or plan.get("authorization_sha256") != policy.sha(authorization)
            or plan.get("execution_policy_frozen_sha256") != policy.sha(frozen_path)
            or plan.get("policy_core_sha256") != core or set(plan.get("expected_ids", [])) != ids):
        raise RuntimeError("Formal authorization/plan/frozen policy bytes are not the same actual execution")
    expected_bindings = {str(authorization): policy.sha(authorization),
        **{str(RUNTIME_CODE / name): fingerprint for name, fingerprint in code.items()},
        str(RUNTIME_CODE / "run_authorized_formal.py"): policy.sha(RUNTIME_CODE / "run_authorized_formal.py"),
        str(RUNTIME_CODE / "audit_runtime_results.py"): policy.sha(RUNTIME_CODE / "audit_runtime_results.py")}
    if plan.get("source_and_receipt_bindings") != expected_bindings:
        raise RuntimeError("Formal source/auditor code bindings incomplete")
    cases = completion["cases"]
    if len(cases) != 186 or len({r["instance_id"] for r in cases}) != 186 or {r["instance_id"] for r in cases} != ids:
        raise RuntimeError("Formal audit misses or duplicates actual case identities")
    if (completion.get("dual_evidence_eligible") != sum(r["eligible_for_dual_evidence"] is True for r in cases)
            or completion.get("statuses") != dict(Counter(r["status"] for r in cases))
            or any(type(r.get("eligible_for_dual_evidence")) is not bool for r in cases)):
        raise RuntimeError("Formal audit aggregate states do not match actual permanent case ledger")
    hashes = {str(p): policy.sha(p) for p in (frozen_path, completion_path, terminal_path, plan_path)} | expected_bindings
    for field in ("official_metadata", "gold", "OOD_manifest", "independent_OOD_gold_audit"):
        hashes[frozen[field + "_path"]] = frozen[field + "_sha256"]
    hashes[frozen["user_adjudication_path"]] = frozen["user_adjudication_sha256"]
    for record in cases:
        if (record.get("audit_errors") != [] or Path(record["result_path"]).resolve() != directory / record["instance_id"] / "result.json"
                or not isinstance(record.get("trace_sha256"), dict)):
            raise RuntimeError("Formal audit contains source/error/trace ambiguity")
        hashes[record["result_path"]] = record["result_sha256"]
        hashes[record["execution_authorization_path"]] = record["execution_authorization_sha256"]
        hashes.update(record["trace_sha256"])
    policy.verify_hash_map(hashes)
    return frozen, completion, hashes


def write_json(path, value):
    static.exclusive_json(path, value)


def checked_static(directory):
    directory = Path(directory).resolve()
    if directory != STATIC: raise RuntimeError("C uses only the separately authorized immutable static stage")
    receipt = policy.read_json(directory / "static_preparation_receipt.json")
    manifest = policy.read_json(directory / "preparation_manifest.json")
    planned = manifest["plan"]
    auth_path = ROOT / "results/v5_pruner/Verified_regenerated_static_execution_authorization_v1.json"
    if policy.sha(auth_path) != manifest["authorization_sha256"]:
        raise RuntimeError("Executed static preparation root authorization changed")
    auth, _, _ = static.authorize(planned, auth_path, directory)
    if (receipt.get("stage_complete") is not True or receipt.get("training_allowed") is not False
            or receipt.get("model_calls") != 0 or receipt.get("test_performance_opened") is not False
            or manifest.get("test_open_allowed") is not False or static.code_bindings() != planned["code_sha256"]
            or planned["OOD_scope"] != static.OOD_SCOPE or len(planned["eligible_new_IDs"]) != 186):
        raise RuntimeError("Actual immutable static source stage is incomplete or drifted")
    source_hashes = {str(directory / "static_preparation_receipt.json"): policy.sha(directory / "static_preparation_receipt.json"),
        str(directory / "preparation_manifest.json"): policy.sha(directory / "preparation_manifest.json"),
        planned["metadata_path"]: planned["metadata_sha256"],
        planned["official_source_receipt_path"]: planned["official_source_receipt_sha256"],
        planned["ood_manifest_path"]: planned["ood_manifest_sha256"],
        **{str(ROOT / p): h for p, h in planned["code_sha256"].items()}, **receipt["case_artifact_sha256"]}
    source_hashes[str(auth_path)] = policy.sha(auth_path)
    source_hashes[auth["OOD_independent_audit_path"]] = auth["OOD_independent_audit_sha256"]
    for item in receipt["issue_receipts"]:
        iid = item["instance_id"]
        source_hashes.update({item["gold_path"]: item["gold_sha256"],
            item["graph"]["graph_path"]: item["graph"]["graph_sha256"],
            str(directory / "full_source_cache" / (iid + ".json")): item["full_source_cache_sha256"]})
        if item["mining_counts"].get("gold_base_region_unmapped", 0):
            raise RuntimeError("Verified base gold failed physical graph mapping: " + iid)
    policy.verify_hash_map(source_hashes)
    source_hashes[str(directory / "static_candidate_pool.jsonl")] = policy.sha(directory / "static_candidate_pool.jsonl")
    candidate = policy.read_rows(directory / "static_candidate_pool.jsonl")
    if any(r["instance_id"] not in planned["eligible_new_IDs"] or set(r["label_sources"]) - set(static.ALLOWED) for r in candidate):
        raise RuntimeError("New candidate source includes reserved/Lite/phantom logs")
    # Only preparation replays source-pool labels, including new test roles.
    # Model gates later use the frozen construction receipt and binary hashes.
    old_rows, _ = static.existing_B_rows(policy.OLD_B_DECISION)
    case_rows = []
    for iid in planned["eligible_new_IDs"]:
        cached = policy.read_json(directory / "cases" / (iid + ".json"))
        if cached["instance_id"] != iid: raise RuntimeError("Static cached row identity drift")
        case_rows.extend(cached["rows"])
    replay, _, _ = static.dedup_new_preserving_old(case_rows, old_rows)
    if candidate != replay:
        raise RuntimeError("C candidate pool labels/eligibility do not reproduce authorized frozen per-issue sources")
    issues, _ = static.official_inputs(planned["metadata_path"], planned["official_source_receipt_path"])
    gold = {iid: policy.read_json(directory / "gold" / (iid + ".json")) for iid in planned["eligible_new_IDs"]}
    return candidate, planned, gold, issues, source_hashes


def checked_runtime(directory, planned, gold, issues):
    directory = Path(directory).resolve(); parent = directory.parent
    if directory != RUNTIME: raise RuntimeError("C uses only the actual separately authorized final v2 runtime")
    frozen, completion, hashes = terminal_runtime_metadata(directory, planned)
    completion_path = parent / "final_completion_independent_audit.json"
    audited = {r["instance_id"]: r for r in completion["cases"]}
    code = frozen["collector_code_sha256"]
    for filename, expected in code.items():
        path = RUNTIME_CODE / filename
        if policy.sha(path) != expected: raise RuntimeError("Verified final collector code changed")
        hashes[str(path)] = expected
    paths = {p.parent.name: p for p in directory.glob("*/result.json")}
    if set(paths) != set(planned["eligible_new_IDs"]):
        raise RuntimeError("All and only exact eligible Verified186 permanent results required")
    evidence = {}
    for iid, path in paths.items():
        result = policy.read_json(path)
        case = audited[iid]
        if (case["result_sha256"] != policy.sha(path) or case["status"] != result["status"]
                or case["eligible_for_dual_evidence"] != result["eligible_for_dual_evidence"]
                or case["full_existing_gold_function_ids"] != sorted(historical.gold_ids(gold[iid]))
                or case["trace_sha256"] != {t["path"]: t["sha256"] for t in result.get("trace_files", [])}):
            raise RuntimeError("Actual runtime result/complete gold/trace differs from independent formal audit")
        gold_digest = hashlib.sha256(json.dumps(gold[iid], sort_keys=True).encode()).hexdigest()
        spec = result.get("static_input_spec", {})
        expected = {"instance_id": iid, "repo": issues[iid]["repo"], "base_commit": issues[iid]["base_commit"],
            "version": issues[iid]["version"], "fail_to_pass": historical.expected_tests(issues[iid]),
            "test_patch_sha256": hashlib.sha256(issues[iid]["test_patch"].encode()).hexdigest(),
            "gold_record_sha256": gold_digest, "full_existing_gold_ids": sorted(historical.gold_ids(gold[iid])),
            "code_sha256": code, "policy_core_sha256": frozen["policy_core_sha256"]}
        if (result.get("completed_at") is None or spec != expected
                or hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest() != result.get("static_input_fingerprint")
                or result.get("collector_sha256") != code["runtime_coverage.py"]
                or result.get("probe_sha256") != code["runtime_coverage_probe.py"]):
            raise RuntimeError("Completed runtime result instrumentation/gold fingerprint changed: " + iid)
        # Cached canaries may legitimately bind an earlier canary receipt while
        # the immutable policy core remains identical to the final formal run.
        auth_path = Path(result["execution_authorization_path"])
        if policy.sha(auth_path) != result["execution_authorization_sha256"]:
            raise RuntimeError("Verified result root execution authorization changed")
        authorization = policy.read_json(auth_path)
        if (authorization.get("root_authorized") is not True or iid not in authorization.get("authorized_run_ids", [])
                or authorization.get("phase") not in ("canary", "formal")
                or authorization.get("pruner_test_labels_may_be_decoded") is not False
                or authorization.get("collector_code_sha256") != code
                or authorization.get("policy_core_sha256") != frozen["policy_core_sha256"]):
            raise RuntimeError("Unapproved or foreign-policy Verified result: " + iid)
        hashes[str(auth_path)] = result["execution_authorization_sha256"]
        evidence[iid] = policy.assess_new_result(result, path, issues[iid], gold[iid])
        hashes[str(path)] = policy.sha(path)
        for trace in result.get("trace_files", []):
            path = Path(trace["path"])
            if path.resolve().parent != (paths[iid].parent / "traces").resolve() or policy.sha(path) != trace["sha256"]:
                raise RuntimeError("Verified final trace bytes changed")
            hashes[str(path)] = trace["sha256"]
    return evidence, hashes, {"result_directory": str(directory), "eligible_IDs": planned["eligible_new_IDs"],
        "result_count": len(paths), "all_eligible_completed": True,
        "qualified_issues": sum(x["qualified"] for x in evidence.values()),
        "static_only_issues": sum(not x["qualified"] for x in evidence.values()),
        "collector_code_sha256": code, "runtime_artifact_sha256": hashes,
        "final_completion_audit_path": str(completion_path), "final_completion_audit_sha256": policy.sha(completion_path)}


def expected_source_artifacts(mechanical_audit=None, sampling_ledger=None):
    """Metadata-only complete required hash map; never read any source-pool rows."""
    stage = policy.read_json(STATIC / "static_preparation_receipt.json")
    manifest = policy.read_json(STATIC / "preparation_manifest.json"); planned = manifest["plan"]
    auth_path = ROOT / "results/v5_pruner/Verified_regenerated_static_execution_authorization_v1.json"
    auth, _, _ = static.authorize(planned, auth_path, STATIC)
    if not stage.get("stage_complete") or len(stage["issue_receipts"]) != 186 or manifest["authorization_sha256"] != policy.sha(auth_path):
        raise RuntimeError("Full static required-source receipt is unavailable")
    hashes = {str(STATIC / name): policy.sha(STATIC / name) for name in (
        "static_preparation_receipt.json", "preparation_manifest.json", "static_candidate_pool.jsonl")}
    hashes.update({planned["metadata_path"]: planned["metadata_sha256"],
        planned["official_source_receipt_path"]: planned["official_source_receipt_sha256"],
        planned["ood_manifest_path"]: planned["ood_manifest_sha256"],
        str(auth_path): policy.sha(auth_path), auth["OOD_independent_audit_path"]: auth["OOD_independent_audit_sha256"],
        **{str(ROOT / path): h for path, h in planned["code_sha256"].items()}, **stage["case_artifact_sha256"]})
    for item in stage["issue_receipts"]:
        hashes.update({item["gold_path"]: item["gold_sha256"], item["graph"]["graph_path"]: item["graph"]["graph_sha256"],
            str(STATIC / "full_source_cache" / (item["instance_id"] + ".json")): item["full_source_cache_sha256"]})
    _, _, runtime_hashes = terminal_runtime_metadata(RUNTIME, planned)
    hashes.update(runtime_hashes)
    hashes.update({str(historical.B_TRAINING / name): policy.sha(historical.B_TRAINING / name) for name in (
        "pruner_train.jsonl", "pruner_val.jsonl", "pruner_test.jsonl", "statistics.json", "test_file_seal.json", "split_manifest.json", "human_review_codex_reviewed.jsonl")})
    hashes[str(policy.OLD_B_DECISION)] = policy.OLD_B_SHA
    hashes[str(ROOT / "ground_truth_300.json")] = policy.sha(ROOT / "ground_truth_300.json")
    frozen_old = policy.read_json(historical.B_RAW / "construction_receipt.json")["official_runtime_metadata_source"]["file_sha256"]
    hashes.update(frozen_old)
    mechanical_audit = mechanical_audit or policy.read_json(policy.RAW / "review_source_mechanical_audit.json")
    if mechanical_audit.get("passed") is not True or mechanical_audit.get("checked_records") != 30:
        raise RuntimeError("Full TRAIN30 source inventory lacks its mechanical source audit")
    hashes.update(mechanical_audit["source_artifact_sha256"])
    from code_v5_verified import joint_train_sampling as joint
    sampling_ledger = sampling_ledger or policy.read_json(policy.RAW / joint.LEDGER_NAME)
    joint.validate_ledger(sampling_ledger)
    hashes.update(joint.source_artifacts(sampling_ledger))
    return hashes


def filtered_new(candidate, evidence, old):
    rejected = []; kept = []; unsafe = {policy.pair(r) for r in policy.known_unsafe()}
    for original in candidate:
        row = deepcopy(original); ev = policy.row_evidence(evidence[row["instance_id"]], row)
        if policy.pair(row) in unsafe: raise RuntimeError("Historical known unsafe pair entered new candidate set")
        if not row["label"] and ev["qualified"] and row["function_id"] in ev["covered"]:
            rejected.append({"instance_id": row["instance_id"], "function_id": row["function_id"],
                "input_sha256": row["input_sha256"], "reason": "valid_failed_test_or_bootstrap_coverage", "runtime_filter": policy.runtime_metadata(ev)})
            continue
        row["runtime_filter"] = policy.runtime_metadata(ev, row["label"]); kept.append(row)
    # Static-stage eligibility already resolves cross-new dedup and old input
    # collisions. Do not dedup again and resurrect an earlier ineligible C.
    if len({r["input_sha256"] for r in kept + old}) != len(kept + old):
        raise RuntimeError("New filtering must preserve frozen dedup and old input collision exclusions")
    selected, sampling = miner.sample_rows(kept, 20261013)
    if {policy.triple(r) for r in selected if r["label"]} != {policy.triple(r) for r in candidate if r["label"]}:
        raise RuntimeError("Runtime filtering lost or resurrected positive eligibility")
    return kept, selected, rejected, sampling


def prepare(static_dir, runtime_dir):
    policy.assert_sealed()
    candidate, planned, gold, official, source_hashes = checked_static(static_dir)
    evidence, runtime_hashes, runtime_manifest = checked_runtime(runtime_dir, planned, gold, official)
    old, old_receipt = static.existing_B_rows(policy.OLD_B_DECISION)
    eligible, new, excluded, sampling = filtered_new(candidate, evidence, old)
    selected = sorted(old + new, key=lambda r: (r["instance_id"], r["function_id"]))
    unsafe = {policy.pair(r) for r in policy.known_unsafe()}
    if len(old) != 4618 or sum(r["label"] for r in old) != 1542 or any(policy.pair(r) in unsafe for r in selected):
        raise RuntimeError("Old B selected eligibility or historical 3+8 exclusion changed")
    original_samples = miner.review_samples(selected, 20261013)
    from code_v5_verified import joint_train_sampling as joint
    additions, joint_ledger = joint.supplement(selected, STATIC / "static_candidate_pool.jsonl")
    selected = sorted(selected + additions, key=lambda r: (r["instance_id"], r["function_id"]))
    samples = miner.review_samples(selected, 20261013)
    if samples != original_samples:
        raise RuntimeError("D-only TRAIN supplementation changed the existing E review selection")
    if Counter(r["review_family"] for r in samples) != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}:
        raise RuntimeError("Real source supply cannot complete three-family30; report shortage, do not fabricate")
    old_meta, old_meta_receipt = historical.official_runtime_metadata()
    old_gold = policy.read_json(ROOT / "ground_truth_300.json")
    old_evidence = {}
    for sample in samples:
        iid = sample["instance_id"]
        if iid in old_meta and iid not in old_evidence:
            path = Path(sample["runtime_filter"]["result_path"])
            old_evidence[iid] = historical.assess_result(policy.read_json(path), path, old_meta[iid], old_gold[iid])
    context = {"issues": {**old_meta, **{iid: official[iid] for iid in planned["eligible_new_IDs"]}},
               "gold": {**old_gold, **gold}}
    packet = historical_builder.review_packet(samples, context, {**evidence, **old_evidence})
    for record, sample in zip(packet, samples):
        # A test-patch-modified candidate may be static-only even if its issue
        # otherwise qualified. Carry the actual per-row flag into the packet.
        record["candidate_row_runtime_filter"] = deepcopy(sample["runtime_filter"])
        iid = sample["instance_id"]
        gold_path = STATIC / "gold" / (iid + ".json") if iid in planned["eligible_new_IDs"] else ROOT / "ground_truth_300.json"
        record["source_binding"] = {"candidate_row_sha256": policy.object_sha(sample),
            "issue_record": context["issues"][iid], "issue_record_sha256": policy.object_sha(context["issues"][iid]),
            "gold_record": context["gold"][iid], "gold_record_sha256": policy.object_sha(context["gold"][iid]),
            "gold_path": str(gold_path), "gold_file_sha256": policy.sha(gold_path),
            "runtime_result_path": sample["runtime_filter"]["result_path"],
            "runtime_result_sha256": sample["runtime_filter"]["result_sha256"]}
        if not record.get("source_evidence_complete") or not record.get("gold"):
            raise RuntimeError("A genuine fresh30 source packet is incomplete; do not sign or train")
    source_audit = policy.audit_source_packet(samples, packet, full_source=True)
    original = policy.read_json(historical.SOURCE / "split_manifest.json")
    split = {"seed": original["seed"], "old_splits": original["splits"],
        "new_splits": planned["new_split_proposal"]["new_splits"], "eligible_new_IDs": planned["eligible_new_IDs"],
        "splits": {k: sorted(original["splits"][k] + planned["new_split_proposal"]["new_splits"][k]) for k in ("train", "val", "test")}}
    source_hashes.update(runtime_hashes)
    source_hashes.update({str(historical.B_TRAINING / name): policy.sha(historical.B_TRAINING / name) for name in (
        "pruner_train.jsonl", "pruner_val.jsonl", "pruner_test.jsonl", "statistics.json", "test_file_seal.json", "split_manifest.json",
        "human_review_codex_reviewed.jsonl")})
    source_hashes[str(policy.OLD_B_DECISION)] = policy.OLD_B_SHA
    source_hashes[str(ROOT / "ground_truth_300.json")] = policy.sha(ROOT / "ground_truth_300.json")
    source_hashes.update(old_meta_receipt["file_sha256"])
    source_hashes.update(source_audit["source_artifact_sha256"])
    source_hashes.update(joint.source_artifacts(joint_ledger))
    return {"selected": selected, "new_candidate": eligible, "new_selected": new, "old": old,
        "excluded": excluded, "sampling": sampling, "samples": samples, "packet": packet, "split": split,
        "runtime_manifest": runtime_manifest, "source_hashes": source_hashes, "old_receipt": old_receipt,
        "planned": planned, "source_audit": source_audit, "joint_TRAIN_sampling_ledger": joint_ledger,
        "old_Lite_selected_with_TRAIN_replenishment": sorted(old + additions, key=lambda r: (r["instance_id"], r["function_id"]))}


def freeze(context, authorization):
    from code_v5_verified import joint_train_sampling as joint
    auth = policy.read_json(authorization)
    expected = {"enabled": True, "stage": "Verified_plus_B_runtime_data_construction", "track": "exploratory",
        "test_open_allowed": False, "llm_labels_allowed": False, "old_B_decision_sha256": policy.OLD_B_SHA,
        "static_receipt_sha256": policy.sha(STATIC / "static_preparation_receipt.json"),
        "runtime_final_audit_sha256": context["runtime_manifest"]["final_completion_audit_sha256"],
        "ood_manifest_sha256": context["planned"]["ood_manifest_sha256"],
        "preparation_code_sha256": {p: policy.sha(ROOT / p) for p in ("code_v5_verified/expanded_policy.py", "code_v5_verified/prepare_expanded_runtime_data.py", "code_v5_verified/joint_train_sampling.py")},
        "joint_TRAIN_sampling_implementation_sha256": joint.IMPLEMENTATION_SHA,
        "joint_TRAIN_supply_independent_audit_sha256": joint.SUPPLY_SHA,
        "joint_TRAIN_supply_deep_audit_sha256": joint.DEEP_SUPPLY_SHA,
        "joint_TRAIN_sampling_ledger_sha256": policy.object_sha(context["joint_TRAIN_sampling_ledger"])}
    if any(auth.get(k) != v for k, v in expected.items()) or Path(auth.get("output_dir", "")).resolve() != policy.RAW:
        raise RuntimeError("Actual full-runtime C construction requires a new exact root authorization")
    if policy.RAW.exists(): raise FileExistsError("C raw construction immutable; never overwrite")
    real_audit = policy.audit_source_packet(context["samples"], context["packet"], full_source=True)
    if real_audit != context["source_audit"] or context["source_hashes"] != expected_source_artifacts(real_audit, context["joint_TRAIN_sampling_ledger"]):
        raise RuntimeError("C source context lacks full independently replayed TRAIN30 and fixed source inventory")
    selected = context["selected"]; counts = miner.summarize(selected)
    policy.verify_hash_map(context["source_hashes"])
    joint.validate_ledger(context["joint_TRAIN_sampling_ledger"], [r for r in selected if r["split"] == "train"])
    policy.RAW.mkdir()
    write_json(policy.RAW / "split_manifest.json", context["split"])
    for name, rows in (("candidate_pool.jsonl", context["new_candidate"]), ("selected_source_pool.jsonl", selected),
                       ("human_review.jsonl", context["samples"]), ("negative_exclusions.jsonl", context["excluded"])):
        (policy.RAW / name).write_bytes(policy.row_bytes(rows))
    sealed = {}
    for role in ("train", "val", "test"):
        rows = [r for r in selected if r["split"] == role]; p = policy.RAW / f"pruner_{role}.jsonl"
        p.write_bytes(policy.row_bytes(rows)); sealed[role] = {"path": str(p), "sha256": policy.sha(p), "count": len(rows)}
    seal = {"dataset_version": policy.POLICY, "test_path": sealed["test"]["path"], "sha256": sealed["test"]["sha256"],
        "test_sha256": sealed["test"]["sha256"], "count": sealed["test"]["count"], "frozen_files": sealed,
        "test_performance_opened": False, "sealed_test_file_decoded": False, "test_constructed_from_source_pool_only": True,
        "split_manifest_sha256": policy.sha(policy.RAW / "split_manifest.json")}
    write_json(policy.RAW / "test_file_seal.json", seal)
    write_json(policy.RAW / "runtime_manifest.json", context["runtime_manifest"])
    write_json(policy.RAW / joint.LEDGER_NAME, context["joint_TRAIN_sampling_ledger"])
    write_json(policy.RAW / "review_source_runtime_evidence.json", {"status": "pending_new_Codex_source_runtime30_review", "records": context["packet"]})
    source_audit = deepcopy(context["source_audit"])
    source_audit.update(packet_sha256=policy.sha(policy.RAW / "review_source_runtime_evidence.json"),
        sample_sha256=policy.sha(policy.RAW / "human_review.jsonl"))
    write_json(policy.RAW / "review_source_mechanical_audit.json", source_audit)
    bval = {policy.triple(r): r for r in policy.read_rows(historical.B_TRAINING / "pruner_val.jsonl")}
    cval = {policy.triple(r): r for r in selected if r["split"] == "val"}; common = sorted(bval.keys() & cval.keys())
    if any(bval[k]["label"] != cval[k]["label"] for k in common): raise RuntimeError("B/C common val label drift")
    write_json(policy.RAW / "comparison_B_C_val_shared_pairs.json", {"B_val_count": len(bval), "C_val_count": len(cval),
        "shared_val_count": len(common), "shared_val_pairs": [dict(instance_id=k[0], function_id=k[1], input_sha256=k[2], label=bval[k]["label"]) for k in common],
        "input_and_label_equal": True, "test_opened": False})
    stats = {"data_policy": policy.POLICY, "dataset_version": policy.POLICY, "track": "exploratory", "passed": False,
        "exploratory_quality_gate_passed": False, "mechanical_labels_only": True, "model_calls": 0,
        "training_started": False, "test_performance_opened": False, "selected": counts,
        "original_B_selected": miner.summarize(context["old"]), "new_selected": miner.summarize(context["new_selected"]),
        "old_Lite_selected_with_TRAIN_replenishment": miner.summarize(context["old_Lite_selected_with_TRAIN_replenishment"]),
        "joint_TRAIN_sampling": {"addition_count": context["joint_TRAIN_sampling_ledger"]["addition_count"],
            "ledger_sha256": policy.sha(policy.RAW / joint.LEDGER_NAME),
            "original_D_only_labels_reused": True, "E_memberships_unchanged": True},
        "new_sampling": context["sampling"], "runtime_distribution": historical_builder.runtime_distribution(selected),
        "quality_gates": policy.quantity_gates(counts, 30), "seal": seal,
        "review": {"review_complete": False, "passed": False, "reviewed_records": 0, "label_errors": None,
            "family_counts": dict(Counter(r["review_family"] for r in context["samples"])), "human_signature": False},
        "interpretation": "Complete raw source construction, not authorized training. Fresh30 signed source/runtime evidence and exact conservative TRAIN exclusion remain mandatory. Runtime absence is not causal irrelevance."}
    write_json(policy.RAW / "statistics.json", stats)
    receipt = {"construction_completed": True, "data_policy": policy.POLICY,
        "Verified_runtime_all_eligible_completed": True, "old_B_exact_rows_inputs_labels_preserved": True,
        "original_ineligible4C_not_resurrected": True, "historical11_unsafe_not_reintroduced": True,
        "sealed_test_file_decoded": False, "statistics_payload_sha256": hashlib.sha256(policy.canonical(stats).encode()).hexdigest(),
        "construction_authorization_path": str(Path(authorization).resolve()), "construction_authorization_sha256": policy.sha(authorization),
        "source_artifact_sha256": context["source_hashes"],
        "raw_files_sha256": {p.name: policy.sha(p) for p in policy.RAW.iterdir() if p.is_file() and p.name != "statistics.json"},
        "boundary": "Source pools including test-role rows constructed only here; model gates hash receipts and load train/val only."}
    write_json(policy.RAW / "construction_receipt.json", receipt)
    stats["construction_receipt_sha256"] = policy.sha(policy.RAW / "construction_receipt.json")
    # Only the creator adds the final receipt pointer, before this dataset is
    # externally frozen. Existing artifacts cannot otherwise be overwritten.
    (policy.RAW / "statistics.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n")
    policy.validate_construction()
    return stats


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--static-dir", type=Path, default=STATIC); p.add_argument("--runtime-dir", type=Path, default=RUNTIME)
    p.add_argument("--authorization", type=Path); p.add_argument("--freeze", action="store_true")
    args = p.parse_args(); context = prepare(args.static_dir, args.runtime_dir)
    if args.freeze:
        if args.authorization is None: raise RuntimeError("No new C construction authorization; no freeze")
        stats = freeze(context, args.authorization)
    else: stats = {"selected": miner.summarize(context["selected"]), "runtime_manifest": context["runtime_manifest"], "freeze": False}
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
