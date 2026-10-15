"""Independent C data gate. Training gates hash receipts and read train/val only.

Construction may materialize test-role rows from source pools. No function here
decodes a sealed pruner_test file or evaluates held-out model performance.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tokenize
import types

from code_v5 import runtime_filtered_policy as historical
from code_v5_verified import prepare_static_extension as static

ROOT = Path(__file__).resolve().parents[1]
POLICY = "verified-plus-B-runtime-v1"
RAW = ROOT / "results/v5_pruner/data_verified_plus_B_runtime"
TRAINING = ROOT / "results/v5_pruner/data_verified_plus_B_runtime_reviewed"
CONTRACT_KEY = "verified_plus_B_runtime_exploratory_v1"
OLD_B_DECISION = ROOT / "results/v5_pruner/B_runtime_filtered_regularized_authorization_exploratory/root_exploratory_decision.json"
OLD_B_SHA = "416209904f95d4d55594165ee2e776d1a001602def49c07029eef7bf1384de0c"
CODE_BINDINGS = (
    "code_v5_verified/expanded_policy.py", "code_v5_verified/prepare_expanded_runtime_data.py",
    "code_v5_verified/freeze_expanded_decision.py", "code_v5_expanded/__init__.py",
    "code_v5_verified/joint_train_sampling.py",
    "code_v5_expanded/train_judges.py", "code_v5_expanded/race_and_calibrate.py",
    "code_v5_expanded/run_training_pair.py", "code_v5_expanded/run_sequence.py",
    "code_v5_expanded/report_outcome.py", "code_v5/judge_models.py", "code_v5/metrics.py",
)
RAW_FILES = {"split_manifest.json", "candidate_pool.jsonl", "selected_source_pool.jsonl", "human_review.jsonl",
    "negative_exclusions.jsonl", "pruner_train.jsonl", "pruner_val.jsonl", "pruner_test.jsonl", "test_file_seal.json",
    "runtime_manifest.json", "review_source_runtime_evidence.json", "review_source_mechanical_audit.json",
    "comparison_B_C_val_shared_pairs.json", "joint_TRAIN_sampling_ledger.json"}
SOURCE_SECTIONS = {"candidate", "gold", "runtime_evidence", "original_graph", "original_static_provenance"}
QUANTITY_GATES = {"positive_unique_pairs_ge_8000"}


def allowed_failed_gates(configuration, stats=None):
    names = configuration.get("allowed_measured_quantity_failed_gates", [])
    if not isinstance(names, list) or len(names) != len(set(names)) or not set(names) <= QUANTITY_GATES:
        raise RuntimeError("Only P8000 is generically deferred; E3000 and integrity/ratio gates cannot be waived")
    allowed = set(names) | {"review_30_train_E_examples_at_most_2_errors"}
    if stats is not None and not stats["quality_gates"]["E_unique_pairs_ge_3000"]:
        auth = configuration.get("E_quantity_specific_authorization", {})
        raw = read_json(RAW / "statistics.json")["selected"]["E_unique_union"]
        deleted = stats["review"]["unsafe_negative_count"]; derived = stats["selected"]["E_unique_union"]
        if (auth.get("enabled") is not True or auth.get("raw_E") != raw or auth.get("deleted_E") != deleted
                or auth.get("derived_E") != derived or auth.get("cause") != "exact_signed_TRAIN_E_exclusions_only"
                or raw < 3000 or derived != raw - deleted or deleted > 30
                or auth.get("review_sha256") != sha(TRAINING / "human_review_codex_reviewed.jsonl")):
            raise RuntimeError("E3000 deficit needs exact measured TRAIN exclusion authority; no supply-shortage waiver")
        allowed.add("E_unique_pairs_ge_3000")
    elif configuration.get("E_quantity_specific_authorization", {}).get("enabled") is True:
        raise RuntimeError("Passing E3000 must not receive an unused E deficit waiver")
    return allowed
sha = historical.sha
canonical = historical.canonical
row_bytes = historical.row_bytes
pair = historical.pair
triple = historical.triple


def read_json(path):
    static.forbid_test_decoder(path)
    return historical.read_json(path)


def read_rows(path):
    static.forbid_test_decoder(path)
    return historical.read_rows(path)


def assert_sealed():
    historical.assert_tests_sealed(historical.B_TRAINING)
    for directory in (RAW, TRAINING):
        if (directory / "pruner_test.jsonl.v5_opened_once.json").exists():
            raise PermissionError("Expanded test has opened; no exploratory model gate allowed")


def known_unsafe():
    old = read_rows(historical.SOURCE / "human_review_codex_reviewed.jsonl")
    b = read_rows(historical.B_TRAINING / "human_review_codex_reviewed.jsonl")
    errors = [r for r in old + b if r["label_error"]]
    if len(errors) != 11 or len({triple(r) for r in errors}) != 11 or any(
            r["split"] != "train" or r["label"] is not False for r in errors):
        raise RuntimeError("Exactly historical 3+8 distinct TRAIN exclusions must remain signed")
    return errors


def assess_new_result(result, path, issue, gold):
    """Retain original strict call-failure tests; use complete existing base gold.

    The frozen Lite checker remains untouched. A copied namespace substitutes
    its obsolete before-only target receipt with full physical gold identities.
    """
    namespace = dict(vars(historical))
    namespace["collector_reported_gold_ids"] = historical.gold_ids
    checker = types.FunctionType(historical.assess_result.__code__, namespace,
                                 "assess_Verified_full_existing_gold")
    evidence = checker(result, path, issue, gold)
    evidence["runtime_unavailable_function_files"] = sorted(set(
        result.get("runtime_unavailable_function_files", [])) | set(result.get("test_patch_modified_files", [])))
    return evidence


def row_evidence(evidence, row):
    ev = deepcopy(evidence)
    if row["function_file"] in ev.get("runtime_unavailable_function_files", []):
        ev["qualified"] = False
        ev["status"] = "runtime_unavailable"
        ev["covered"] = set()
        ev["unavailable_reasons"] = sorted(set(ev["unavailable_reasons"]) | {
            "candidate_test_patch_file_physical_mapping_unavailable"})
    return ev


def runtime_metadata(ev, positive=False):
    out = historical.runtime_metadata(ev, positive)
    if positive:
        out["eligibility_basis"] = "positive_frozen_source_eligibility"
    return out


def verify_hash_map(mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise RuntimeError("An empty artifact receipt is not complete evidence")
    for path, expected in mapping.items():
        p = Path(path)
        if not p.is_absolute(): p = ROOT / p
        if sha(p) != expected: raise RuntimeError("Protected source/evidence changed: " + str(p))


def object_sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_function(row, fid):
    """Re-read real Git blob and locate one physical AST def; no project import."""
    filename, target = fid.split("::", 1); qualified, line = target.rsplit("@", 1)
    mirror = ROOT / "mirror_cache" / (row["repo"].rsplit("/", 1)[-1] + ".git")
    prefix = ["git", "--git-dir", str(mirror)]
    blob = subprocess.run(prefix + ["rev-parse", row["base_commit"] + ":" + filename],
        capture_output=True, check=True, timeout=30).stdout.decode().strip()
    raw = subprocess.run(prefix + ["cat-file", "blob", blob], capture_output=True, check=True, timeout=30).stdout
    if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != blob:
        raise RuntimeError("Real source Git blob hash mismatch")
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline); source = raw.decode(encoding)
    from code_v5.prepare_runtime_filtered_data import Definitions
    inventory = Definitions(); inventory.visit(ast.parse(source, filename))
    node = inventory.nodes[(qualified, int(line))]
    full = "".join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
    return {"function_id": fid, "file": filename, "base_blob_sha1": blob,
        "full_source_sha256": hashlib.sha256(full.encode()).hexdigest(), "full_source": full,
        "calls": [{"line": n.lineno, "expression": ast.get_source_segment(source, n)}
                  for n in ast.walk(node) if isinstance(n, ast.Call)]}


def audit_source_packet(samples, records, full_source=False):
    """Full source audit only at preparation/derive/freeze; gates use its hashes."""
    if (len(samples) != 30 or len(records) != 30 or len({triple(r) for r in samples}) != 30
            or any(r["split"] != "train" or r["label"] is not False for r in samples)):
        raise RuntimeError("Only complete genuine TRAIN30 may receive a source audit")
    index = {triple(r["identity"]): r for r in records}
    if set(index) != {triple(r) for r in samples}: raise RuntimeError("Source packet identity mismatch")
    if not full_source:
        proof = read_json(RAW / "review_source_mechanical_audit.json")
        if (proof.get("passed") is not True or proof.get("checked_records") != 30
                or proof.get("audit_kind") != "real_base_Git_AST_fullgold_graph_official_runtime_TRAIN30"
                or proof.get("packet_sha256") != sha(RAW / "review_source_runtime_evidence.json")
                or proof.get("sample_sha256") != sha(RAW / "human_review.jsonl")
                or proof.get("record_sha256") != {canonical(list(triple(r))): object_sha(index[triple(r)]) for r in samples}
                or proof.get("input_row_sha256") != {canonical(list(triple(r))): object_sha(r) for r in samples}):
            raise RuntimeError("No complete frozen real-source TRAIN30 audit receipt")
        verify_hash_map(proof["source_artifact_sha256"])
    official = lite = None
    if full_source:
        from code_v5_verified.prepare_expanded_runtime_data import STATIC
        manifest = read_json(STATIC / "preparation_manifest.json")["plan"]
        official, _ = static.official_inputs(manifest["metadata_path"], manifest["official_source_receipt_path"])
        lite, _ = historical.official_runtime_metadata()
    hashes = {}; evidence_checks = []
    for row in samples:
        record = index[triple(row)]; binding = record.get("source_binding", {})
        if (record.get("source_evidence_complete") is not True
                or binding.get("candidate_row_sha256") != object_sha(row)
                or not isinstance(binding.get("issue_record"), dict) or not isinstance(binding.get("gold_record"), dict)
                or record.get("candidate_row_runtime_filter") != row["runtime_filter"]
                or record.get("original_static_provenance") != row["provenance"]
                or record.get("original_graph") != row["graph"]):
            raise RuntimeError("Review source packet lacks exact row/official/static/runtime binding")
        issue, gold = binding["issue_record"], binding["gold_record"]
        if (issue.get("instance_id") != row["instance_id"] or issue.get("repo") != row["repo"]
                or issue.get("base_commit") != row["base_commit"] or row["issue"] != issue.get("problem_statement", "")[:2000]
                or gold.get("repo") != row["repo"] or gold.get("base_commit") != row["base_commit"]
                or record.get("full_issue") != issue["problem_statement"] or record.get("official_patch") != issue["patch"]
                or binding.get("issue_record_sha256") != object_sha(issue) or binding.get("gold_record_sha256") != object_sha(gold)):
            raise RuntimeError("Review official issue/base/gold drift")
        gold_path = Path(binding["gold_path"]); hashes[str(gold_path)] = binding["gold_file_sha256"]
        graph_path = Path(row["graph"]["graph_path"]); hashes[str(graph_path)] = row["graph"]["graph_sha256"]
        runtime_path = Path(binding["runtime_result_path"]); hashes[str(runtime_path)] = binding["runtime_result_sha256"]
        if sha(gold_path) != hashes[str(gold_path)] or sha(graph_path) != hashes[str(graph_path)] or sha(runtime_path) != hashes[str(runtime_path)]:
            raise RuntimeError("Review graph/gold/runtime files changed")
        candidate = record.get("candidate", {})
        expected_gold_ids = historical.gold_ids(gold)
        if (not expected_gold_ids or set(record.get("gold", {})) != expected_gold_ids
                or candidate.get("function_id") != row["function_id"] or candidate.get("file") != row["function_file"]
                or not isinstance(candidate.get("full_source"), str) or not candidate["full_source"].strip()
                or candidate.get("full_source_sha256") != row["full_function_source_sha256"]
                or hashlib.sha256(candidate["full_source"].encode()).hexdigest() != candidate["full_source_sha256"]
                or row["function"] != candidate["full_source"][:1500]
                or hashlib.sha256(json.dumps([row["issue"], row["function"]], ensure_ascii=False).encode()).hexdigest() != row["input_sha256"]):
            raise RuntimeError("Candidate source/features or complete physical gold identity invalid")
        for fid, source in record["gold"].items():
            if (source.get("function_id") != fid or not isinstance(source.get("full_source"), str)
                    or not source["full_source"].strip() or hashlib.sha256(source["full_source"].encode()).hexdigest() != source.get("full_source_sha256")):
                raise RuntimeError("Full base-gold source payload invalid")
        if full_source:
            is_new = row["instance_id"] in official and row["instance_id"] not in lite
            authoritative_issue = official[row["instance_id"]] if is_new else lite[row["instance_id"]]
            if issue != authoritative_issue: raise RuntimeError("Packet issue is not official benchmark metadata")
            saved = read_json(gold_path); saved = saved if is_new else saved[row["instance_id"]]
            if saved != gold: raise RuntimeError("Packet gold is not frozen source gold")
            if candidate != source_function(row, row["function_id"]) or any(
                    source != source_function(row, fid) for fid, source in record["gold"].items()):
                raise RuntimeError("Packet source differs from actual Git blob/physical AST function")
            graph = read_json(graph_path); nodes = {n["id"]: n for n in graph["functions"]}
            node = nodes[row["function_id"]]
            if (graph["instance_id"] != row["instance_id"] or graph["repo"] != row["repo"]
                    or graph["base_commit"] != row["base_commit"] or node["file"] != row["function_file"]
                    or node["def_line"] != row["function_def_line"] or node["source_sha256"] != candidate["full_source_sha256"]
                    or not expected_gold_ids <= set(nodes)):
                raise RuntimeError("Packet physical graph identity/source drift")
            result = read_json(runtime_path)
            ev = assess_new_result(result, runtime_path, issue, gold) if is_new else historical.assess_result(result, runtime_path, issue, gold)
            row_ev = row_evidence(ev, row) if is_new else ev
            expected_metadata = runtime_metadata(row_ev)
            if expected_metadata != row["runtime_filter"] or historical.runtime_metadata(ev) != record["runtime_evidence"]:
                raise RuntimeError("Row runtime qualification/static fallback differs from actual evidence")
            if not is_new and sha(runtime_path) != row["runtime_filter"]["result_sha256"]:
                raise RuntimeError("Frozen Lite runtime row fingerprint differs")
            if is_new:
                spec = result["static_input_spec"]
                if spec["gold_record_sha256"] != hashlib.sha256(json.dumps(gold, sort_keys=True).encode()).hexdigest():
                    raise RuntimeError("New runtime gold digest differs")
                auth_path = Path(result["execution_authorization_path"])
                if sha(auth_path) != result["execution_authorization_sha256"]: raise RuntimeError("Runtime root source changed")
                hashes[str(auth_path)] = result["execution_authorization_sha256"]
            for trace in result.get("trace_files", []): hashes[trace["path"]] = trace["sha256"]
        evidence_checks.append({"identity": list(triple(row)), "candidate_blob_sha1": candidate.get("base_blob_sha1"),
            "full_base_gold_ids": sorted(expected_gold_ids), "runtime_result_path": str(runtime_path)})
    verify_hash_map(hashes)
    return {"passed": True, "checked_records": 30, "audit_kind": "real_base_Git_AST_fullgold_graph_official_runtime_TRAIN30",
        "record_sha256": {canonical(list(triple(r))): object_sha(index[triple(r)]) for r in samples},
        "input_row_sha256": {canonical(list(triple(r))): object_sha(r) for r in samples},
        "source_artifact_sha256": hashes, "evidence_checks": evidence_checks,
        "test_file_decoded": False, "model_calls": 0, "GPU_used": False}


def validate_construction():
    """No pool or test-role parser here; bind already audited construction."""
    assert_sealed()
    if sha(OLD_B_DECISION) != OLD_B_SHA: raise RuntimeError("Original B frozen authorization changed")
    historical.validate_decision(historical.B_TRAINING, OLD_B_DECISION)
    stats = read_json(RAW / "statistics.json")
    receipt = read_json(RAW / "construction_receipt.json")
    payload = {k: v for k, v in stats.items() if k != "construction_receipt_sha256"}
    if (stats.get("data_policy") != POLICY or stats.get("track") != "exploratory"
            or sha(RAW / "construction_receipt.json") != stats.get("construction_receipt_sha256")
            or hashlib.sha256(canonical(payload).encode()).hexdigest() != receipt.get("statistics_payload_sha256")
            or receipt.get("construction_completed") is not True
            or receipt.get("Verified_runtime_all_eligible_completed") is not True
            or receipt.get("old_B_exact_rows_inputs_labels_preserved") is not True
            or receipt.get("original_ineligible4C_not_resurrected") is not True
            or receipt.get("historical11_unsafe_not_reintroduced") is not True
            or receipt.get("sealed_test_file_decoded") is not False):
        raise RuntimeError("Expanded construction lacks complete source/runtime/old-row proof")
    from code_v5_verified.prepare_expanded_runtime_data import expected_source_artifacts
    if receipt["source_artifact_sha256"] != expected_source_artifacts():
        raise RuntimeError("C construction source hash map lacks the full fixed real-source/runtime inventory")
    verify_hash_map(receipt["source_artifact_sha256"])
    auth_path = Path(receipt["construction_authorization_path"])
    if sha(auth_path) != receipt["construction_authorization_sha256"]:
        raise RuntimeError("Expanded construction root authorization changed")
    construction_auth = read_json(auth_path)
    runtime_manifest = read_json(RAW / "runtime_manifest.json")
    from code_v5_verified import joint_train_sampling as joint
    sampling_ledger = read_json(RAW / joint.LEDGER_NAME)
    joint.validate_ledger(sampling_ledger, read_rows(RAW / "pruner_train.jsonl"))
    if stats.get("joint_TRAIN_sampling") != {"addition_count": 1052,
            "ledger_sha256": sha(RAW / joint.LEDGER_NAME), "original_D_only_labels_reused": True,
            "E_memberships_unchanged": True}:
        raise RuntimeError("C actual joint TRAIN selection correction receipt changed")
    expected_auth = {"enabled": True, "stage": "Verified_plus_B_runtime_data_construction", "track": "exploratory",
        "test_open_allowed": False, "llm_labels_allowed": False, "old_B_decision_sha256": OLD_B_SHA,
        "static_receipt_sha256": sha(ROOT / "results/v5_pruner/verified_extension_regenerated_ood_v1/static_preparation_receipt.json"),
        "runtime_final_audit_sha256": runtime_manifest["final_completion_audit_sha256"],
        "ood_manifest_sha256": sha(ROOT / "results/v5_pruner/verified_regenerated_ood/verified231_manifest.json"),
        "preparation_code_sha256": {p: sha(ROOT / p) for p in ("code_v5_verified/expanded_policy.py", "code_v5_verified/prepare_expanded_runtime_data.py", "code_v5_verified/joint_train_sampling.py")},
        "joint_TRAIN_sampling_implementation_sha256": joint.IMPLEMENTATION_SHA,
        "joint_TRAIN_supply_independent_audit_sha256": joint.SUPPLY_SHA,
        "joint_TRAIN_supply_deep_audit_sha256": joint.DEEP_SUPPLY_SHA,
        "joint_TRAIN_sampling_ledger_sha256": object_sha(sampling_ledger)}
    if (any(construction_auth.get(k) != v for k, v in expected_auth.items())
            or Path(construction_auth.get("output_dir", "")).resolve() != RAW):
        raise RuntimeError("Expanded source construction lacks dedicated safe root authority")
    if set(receipt["raw_files_sha256"]) != RAW_FILES:
        raise RuntimeError("C construction raw-file manifest must contain every fixed required artifact")
    for name, expected in receipt["raw_files_sha256"].items():
        if Path(name).name != name or sha(RAW / name) != expected:
            raise RuntimeError("Expanded raw construction bytes changed")
    split = read_json(RAW / "split_manifest.json")
    old = read_json(historical.SOURCE / "split_manifest.json")
    frozen_plan = read_json(ROOT / "results/v5_pruner/verified_extension_regenerated_ood_v1/preparation_manifest.json")["plan"]
    if (split["seed"] != old["seed"] or split["old_splits"] != old["splits"]
            or split["new_splits"] != frozen_plan["new_split_proposal"]["new_splits"]
            or split["eligible_new_IDs"] != frozen_plan["eligible_new_IDs"]):
        raise RuntimeError("Original Lite split changed")
    ids = {k: set(v) for k, v in split["splits"].items()}
    if (set(ids) != {"train", "val", "test"} or sum(map(len, ids.values())) != len(set().union(*ids.values()))
            or set().union(*ids.values()) != set(sum(old["splits"].values(), [])) | set(split["eligible_new_IDs"])
            or any(ids[k] != set(old["splits"][k]) | set(split["new_splits"][k]) for k in ids)):
        raise RuntimeError("Expanded new/old issue split union or leakage invalid")
    return stats, receipt, split, ids


REVIEW_FIELDS = {"review_status", "label_error", "review_note", "relation_classification", "evidence_refs"}


def validate_review(review_path, audit_source=False):
    pending = read_rows(RAW / "human_review.jsonl")
    reviewed = read_rows(review_path)
    expected = {triple(r): r for r in pending}
    if (len(pending) != 30 or len(reviewed) != 30 or len(expected) != 30
            or {triple(r) for r in reviewed} != set(expected)
            or Counter(r["review_family"] for r in reviewed) != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}):
        raise RuntimeError("Full genuine train-only three-family 30 review required; shortages cannot be duplicated")
    if {pair(r) for r in pending} & {pair(r) for r in known_unsafe()}:
        raise RuntimeError("Historical unsafe TRAIN pair reentered C review under another input hash")
    packet = read_json(RAW / "review_source_runtime_evidence.json")["records"]
    audit_source_packet(pending, packet, full_source=audit_source)
    packet_by_id = {triple(r["identity"]): r for r in packet}
    packet_path = RAW / "review_source_runtime_evidence.json"; packet_sha = sha(packet_path)
    for row in reviewed:
        if ({k: v for k, v in row.items() if k not in REVIEW_FIELDS}
                != {k: v for k, v in expected[triple(row)].items() if k not in REVIEW_FIELDS}
                or row["split"] != "train" or row["label"] is not False
                or row.get("review_status") != "reviewed" or type(row.get("label_error")) is not bool
                or not isinstance(row.get("review_note"), str) or not row["review_note"].strip()
                or not isinstance(row.get("evidence_refs"), list) or not row["evidence_refs"]
                or row.get("relation_classification") not in {"retained_limited_evidence", "confirmed_source_relation", "conditional_risk"}
                or row["label_error"] != (row["relation_classification"] != "retained_limited_evidence")):
            raise RuntimeError("Review altered payload/label or lacks signed source/runtime evidence and risk distinction")
        sections = set()
        for reference in row["evidence_refs"]:
            if (not isinstance(reference, dict) or set(reference) != {"artifact_path", "artifact_sha256", "record_sha256", "section"}
                    or not isinstance(reference["artifact_path"], str)
                    or Path(reference["artifact_path"]).resolve() != packet_path
                    or reference["artifact_sha256"] != packet_sha
                    or reference["record_sha256"] != object_sha(packet_by_id[triple(row)])
                    or reference["section"] not in SOURCE_SECTIONS):
                raise RuntimeError("Review evidence reference is not bound to this actual checked record")
            sections.add(reference["section"])
        if sections != SOURCE_SECTIONS:
            raise RuntimeError("Every signature must reference candidate/fullgold/runtime/graph/static source evidence")
    return reviewed, [r for r in reviewed if r["label_error"]]


def quantity_gates(selected, errors):
    p, n, e = selected["positive"], selected["negative"], selected.get("E_unique_union", 0)
    return {"positive_unique_pairs_ge_8000": p >= 8000,
            "E_unique_pairs_ge_3000": e >= 3000,
            "negative_to_positive_ratio_about_2": bool(p and 1.8 <= n / p <= 2.2),
            "E_fraction_of_negatives_ge_one_third": bool(n and e / n >= 1/3),
            "ordinary_D_negatives_retained": selected.get("primary_source_D", 0) > 0,
            "review_30_train_E_examples_at_most_2_errors": errors <= 2}


def summary_after_exclusion(raw, removed, actual_train_val):
    """Derive complete counts from raw metadata and TRAIN deletions, no test rows."""
    from code_v5 import build_pruner_data as miner
    measured = miner.summarize(actual_train_val)
    root = Counter({k: v for k, v in raw.items() if isinstance(v, int) and k != "unique_pairs"})
    for row in removed:
        root["negative"] -= 1; root["primary_source_" + row["label_source"]] -= 1
        for source in row["label_sources"]: root["source_" + source] -= 1
        if set(row["label_sources"]) & {"e_log", "e_bm25", "e_anchor"}: root["E_unique_union"] -= 1
    expected = {"unique_pairs": raw["unique_pairs"] - len(removed), **{k: v for k, v in root.items() if v > 0},
        "by_split": {"train": measured["by_split"]["train"], "val": raw["by_split"]["val"], "test": raw["by_split"]["test"]}}
    for field, attribute in (("by_repo", "repo"), ("by_anchor", "anchor")):
        counters = {k: Counter(v) for k, v in raw[field].items()}
        for row in removed: counters[row[attribute]]["negative"] -= 1
        expected[field] = {k: {a: n for a, n in v.items() if n > 0} for k, v in counters.items() if any(n > 0 for n in v.values())}
    return expected


def validate_reviewed(data_dir, audit_source=False):
    if Path(data_dir).resolve() != TRAINING:
        raise RuntimeError("Only separately reviewed C derivative is authorized; previews/raw are prohibited")
    raw, receipt, split, ids = validate_construction()
    stats = read_json(TRAINING / "statistics.json")
    review_path = TRAINING / "human_review_codex_reviewed.jsonl"
    reviewed, errors = validate_review(review_path, audit_source=audit_source)
    derivation = read_json(TRAINING / "reviewed_train_derivation.json")
    if (derivation["raw_statistics_sha256"] != sha(RAW / "statistics.json")
            or derivation["review_sha256"] != sha(review_path)
            or derivation["excluded_training_pairs"] != [list(triple(r)) for r in errors]
            or derivation.get("labels_flipped") != 0 or derivation.get("replacement_labels_created") != 0):
        raise RuntimeError("Expanded exact TRAIN review exclusion derivation changed")
    error_keys = {triple(r) for r in errors}; kept = []; removed = []
    for line in (RAW / "pruner_train.jsonl").read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        if triple(row) in error_keys:
            if row["split"] != "train" or row["label"] is not False: raise RuntimeError("Only reviewed TRAIN negatives can be excluded")
            removed.append(row)
        else: kept.append(line)
    if len(removed) != len(errors) or (TRAINING / "pruner_train.jsonl").read_bytes() != b"".join(kept):
        raise RuntimeError("All and only reviewed unsafe TRAIN rows must be deleted")
    new_ids = set(split["eligible_new_IDs"])
    if (derivation.get("excluded_training_rows") != removed
            or derivation.get("additional_old_Lite_train_masks") != [list(triple(r)) for r in removed if r["instance_id"] not in new_ids]
            or derivation.get("original_B_history_unchanged") is not True
            or derivation.get("val_test_split_bytes_unchanged") is not True
            or derivation.get("remaining_review_examples_not_relabelled_as_new_random_pass") is not True):
        raise RuntimeError("C exact removed-row/extra old TRAIN mask ledger differs from actual exclusions")
    for name in ("pruner_val.jsonl", "pruner_test.jsonl", "split_manifest.json", "human_review.jsonl",
                 "runtime_manifest.json", "review_source_runtime_evidence.json", "comparison_B_C_val_shared_pairs.json", "joint_TRAIN_sampling_ledger.json"):
        if sha(TRAINING / name) != sha(RAW / name): raise RuntimeError("Expanded val/test/split/evidence bytes changed")
    train = read_rows(TRAINING / "pruner_train.jsonl"); val = read_rows(TRAINING / "pruner_val.jsonl")
    rows = train + val; bad = {pair(r) for r in known_unsafe()} | {pair(r) for r in errors}
    if (len({pair(r) for r in rows}) != len(rows) or len({r["input_sha256"] for r in rows}) != len(rows)
            or {pair(r) for r in rows} & bad
            or any(r["instance_id"] not in ids[r["split"]] or type(r["label"]) is not bool
                   or len(r["issue"]) > 2000 or len(r["function"]) > 1500
                   or hashlib.sha256(json.dumps([r["issue"], r["function"]], ensure_ascii=False).encode()).hexdigest() != r["input_sha256"] for r in rows)):
        raise RuntimeError("Expanded train/val split/input/labels or known exclusions invalid")
    from code_v5 import build_pruner_data as miner
    measured = miner.summarize(rows)
    if (stats["data_policy"] != POLICY or stats.get("passed") is not False
            or stats.get("exploratory_quality_gate_passed") is not True
            or stats.get("mechanical_labels_only") is not True or stats.get("model_calls") != 0
            or stats["selected"]["unique_pairs"] != raw["selected"]["unique_pairs"] - len(errors)
            or stats["selected"]["positive"] != raw["selected"]["positive"]
            or stats["selected"]["negative"] != raw["selected"]["negative"] - len(errors)
            or stats["review"]["reviewed_records"] != 30 or stats["review"]["label_errors"] != len(errors)
            or stats["review"].get("review_complete") is not True
            or stats["review"]["review_sha256"] != sha(review_path)
            or stats["review"].get("classification_counts") != dict(Counter(r["relation_classification"] for r in reviewed))
            or stats["review"].get("family_counts") != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}
            or stats["review"].get("observed_stratified_conservative_exclusion_fraction") != len(errors) / 30
            or stats.get("new_selected_before_review") != raw["new_selected"]
            or stats.get("original_B_selected_before_review") != raw["original_B_selected"]
            or stats.get("old_Lite_selected_with_TRAIN_replenishment_before_review") != raw["old_Lite_selected_with_TRAIN_replenishment"]
            or stats["quality_gates"] != quantity_gates(stats["selected"], len(errors))
            or any(stats["selected"]["by_split"][k] != measured["by_split"][k] for k in ("train", "val"))):
        raise RuntimeError("C actual measured counts or truthful exploratory review disclosure changed")
    if stats["selected"] != summary_after_exclusion(raw["selected"], removed, rows):
        raise RuntimeError("C full source/repo/anchor/test metadata counts drifted beyond exact TRAIN exclusions")
    for field, group in (("new_selected", [r for r in rows if r["instance_id"] in new_ids]),
                         ("old_B_selected_after_C_review", [r for r in rows if r["instance_id"] not in new_ids])):
        group_summary = miner.summarize(group)
        group_removed = [r for r in removed if (r["instance_id"] in new_ids) == (field == "new_selected")]
        original = raw["new_selected"] if field == "new_selected" else raw["old_Lite_selected_with_TRAIN_replenishment"]
        if stats[field] != summary_after_exclusion(original, group_removed, group):
            raise RuntimeError("C raw-versus-reviewed old/new source counts are not measured")
    seal = read_json(TRAINING / "test_file_seal.json")
    if stats["seal"] != seal: raise RuntimeError("C stats and actual seal differ")
    for role in ("train", "val", "test"):
        item = seal["frozen_files"][role]; p = TRAINING / f"pruner_{role}.jsonl"
        if Path(item["path"]).resolve() != p or item["sha256"] != sha(p): raise RuntimeError("C sealed bytes differ")
    if seal["frozen_files"]["train"]["count"] != len(train) or seal["frozen_files"]["val"]["count"] != len(val):
        raise RuntimeError("C seal train/val counts differ")
    return stats, seal, ids


def required_contract_fields():
    """Read only completed metadata/receipts; no null preliminary authorization."""
    runtime = read_json(RAW / "runtime_manifest.json")
    from code_v5_verified import joint_train_sampling as joint
    return {"enabled": True, "data_policy": POLICY, "track": "exploratory", "test_open_allowed": False,
        "llm_labels_allowed": False, "derived_data_dir": str(RAW), "reviewed_training_data_dir": str(TRAINING),
        "old_B_decision_sha256": OLD_B_SHA, "known_historical_unsafe_exclusion_count": 11,
        "original_positive_eligibility_count": 1542, "allowed_new_sources": list(static.ALLOWED),
        "old_split_sha256": sha(historical.SOURCE / "split_manifest.json"),
        "statistics_sha256": sha(TRAINING / "statistics.json"),
        "construction_receipt_sha256": sha(RAW / "construction_receipt.json"),
        "runtime_manifest_sha256": sha(RAW / "runtime_manifest.json"),
        "joint_TRAIN_sampling_ledger_sha256": sha(RAW / "joint_TRAIN_sampling_ledger.json"),
        "joint_TRAIN_sampling_implementation_sha256": joint.IMPLEMENTATION_SHA,
        "joint_TRAIN_supply_deep_audit_sha256": joint.DEEP_SUPPLY_SHA,
        "review_sha256": sha(TRAINING / "human_review_codex_reviewed.jsonl"),
        "static_receipt_sha256": sha(ROOT / "results/v5_pruner/verified_extension_regenerated_ood_v1/static_preparation_receipt.json"),
        "runtime_final_audit_sha256": runtime["final_completion_audit_sha256"],
        "ood_manifest_sha256": sha(ROOT / "results/v5_pruner/verified_regenerated_ood/verified231_manifest.json")}


def validate_decision(data_dir, decision_file):
    stats, seal, ids = validate_reviewed(data_dir)
    decision = read_json(decision_file)
    if (decision.get("data_policy") != POLICY or decision.get("track") != "exploratory"
            or decision.get("test_open_allowed") is not False or decision.get("formal_failed") is not True
            or decision.get("exploratory_quality_gate_passed") is not True
            or Path(decision.get("data_dir", "")).resolve() != TRAINING):
        raise RuntimeError("C frozen decision lacks separate exploratory-only exact data authorization")
    snapshot = Path(decision["execution_contract_path"])
    if sha(snapshot) != decision["execution_contract_sha256"]: raise RuntimeError("C root contract snapshot changed")
    contract = read_json(snapshot); policy = contract.get(CONTRACT_KEY, {})
    if any(policy.get(k) != v for k, v in required_contract_fields().items()):
        raise RuntimeError("C root snapshot does not authorize this completed reviewed derivative")
    hashes = decision["policy_code_sha256"]
    if set(hashes) != set(CODE_BINDINGS) or any(sha(ROOT / p) != h for p, h in hashes.items()):
        raise RuntimeError("C own training/data/metric code binding changed")
    required = {"statistics_sha256": sha(TRAINING / "statistics.json"), "seal_sha256": sha(TRAINING / "test_file_seal.json"),
        "split_manifest_sha256": sha(TRAINING / "split_manifest.json"), "review_sha256": sha(TRAINING / "human_review_codex_reviewed.jsonl"),
        "raw_statistics_sha256": sha(RAW / "statistics.json"), "construction_receipt_sha256": sha(RAW / "construction_receipt.json"),
        "runtime_manifest_sha256": sha(RAW / "runtime_manifest.json"),
        "reviewed_train_derivation_sha256": sha(TRAINING / "reviewed_train_derivation.json"),
        **{s + "_sha256": sha(TRAINING / f"pruner_{s}.jsonl") for s in ("train", "val", "test")}}
    if any(decision.get(k) != v for k, v in required.items()) or decision.get("selected_counts") != stats["selected"]:
        raise RuntimeError("C decision no longer binds actual input/source/runtime/review/test-seal bytes")
    failed = {k for k, v in stats["quality_gates"].items() if v is not True}
    allowed = allowed_failed_gates(policy, stats)
    if not failed <= allowed or set(decision.get("allowed_failed_gates", [])) != failed:
        raise RuntimeError("C may disclose measured quantity/noise only; no integrity waiver")
    return stats, seal, ids, {**required, "reviewer_kind": "Codex source/runtime evidence review, not human signature",
        "test_labels_read": False, "track": "exploratory", "data_policy": POLICY,
        "exploratory_quality_gate_passed": True, "formal_data_gate_passed": False,
        "noise_disclosure": stats["review"], "runtime_distribution": stats["runtime_distribution"],
        "root_decision": {"path": str(Path(decision_file).resolve()), "sha256": sha(decision_file),
            "execution_contract_path": str(snapshot), "execution_contract_sha256": decision["execution_contract_sha256"]}}
