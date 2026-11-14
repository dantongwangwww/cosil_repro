"""Authorized joint TRAIN supplementation from frozen original D-only rows.

This changes selection, never labels or E rules. Construction decodes only
TRAIN bodies in the old eligible pool; model gates use the frozen ledger and
TRAIN rows. Held-out source rows expose split/input-hash metadata only.
"""
from __future__ import annotations

from collections import Counter
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tokenize

from code_v5 import build_pruner_data as miner
from code_v5 import runtime_filtered_policy as historical
from code_v5_verified import expanded_policy as policy

ROOT = policy.ROOT
IMPLEMENTATION = ROOT / "results/v5_pruner/C4_joint_TRAIN_sampling_implementation_decision.json"
IMPLEMENTATION_SHA = "b563203e9dcb00e41d231ffda0a327a31fd5c00c1cd4de68ab78ffa8e5d4a83e"
SUPPLY_AUDIT = ROOT / "results/v5_pruner/C_D_only_TRAIN_supply_independent_audit.json"
SUPPLY_SHA = "9e8b87e4cde62a7f5e82669782847efef7c4c4dea2bcef2934689dfab20f4dd5"
DEEP_SUPPLY_AUDIT = ROOT / "results/v5_pruner/C_old_B_TRAIN_D_supply_deep_readonly_audit.json"
DEEP_SUPPLY_SHA = "7c7ab9130f4b604b49eedfc6e1ef88f1694ea70b0e2eeb5ff1adf5b92c16f873"
SOURCE_POOL = historical.B_RAW / "candidate_pool.jsonl"
LEDGER_NAME = "joint_TRAIN_sampling_ledger.json"
SEED = 20261013


def _value_end(text, start):
    depth = 0; quoted = False; escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if quoted:
            if escaped: escaped = False
            elif char == "\\": escaped = True
            elif char == '"': quoted = False
        elif char == '"': quoted = True
        elif char in "[{": depth += 1
        elif char in "]}":
            if depth == 0: return i
            depth -= 1
        elif char == "," and depth == 0: return i
    return len(text)


def outer_field(text, name):
    """Read one outer scalar without decoding skipped labels/code strings."""
    i = 1
    while i < len(text):
        while i < len(text) and (text[i].isspace() or text[i] == ","): i += 1
        if i >= len(text) or text[i] == "}": break
        if text[i] != '"': raise ValueError("Malformed JSON outer key")
        j = i + 1; escaped = False
        while j < len(text):
            if escaped: escaped = False
            elif text[j] == "\\": escaped = True
            elif text[j] == '"': break
            j += 1
        key = json.loads(text[i:j + 1]); i = j + 1
        while text[i].isspace(): i += 1
        if text[i] != ":": raise ValueError("Malformed JSON outer colon")
        i += 1
        while text[i].isspace(): i += 1
        end = _value_end(text, i)
        if key == name: return json.loads(text[i:end])
        i = end
    raise KeyError(name)


def train_pool(path):
    policy.static.forbid_test_decoder(path)
    train = []; hashes = []; roles = Counter()
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip(): continue
            role = outer_field(line, "split")
            if role not in ("train", "val", "test"): raise RuntimeError("Unknown source role")
            roles[role] += 1; hashes.append(outer_field(line, "input_sha256"))
            if role == "train": train.append(json.loads(line))
    return train, hashes, dict(roles)


def authorization_metadata():
    if policy.sha(IMPLEMENTATION) != IMPLEMENTATION_SHA or policy.sha(SUPPLY_AUDIT) != SUPPLY_SHA:
        raise RuntimeError("Frozen joint TRAIN implementation/supply authority drifted")
    authorization = policy.read_json(IMPLEMENTATION); audit = policy.read_json(SUPPLY_AUDIT)
    if (authorization.get("root_authorized") is not True
            or authorization.get("stage") != "implementation_only_joint_TRAIN_sampling_correction"
            or authorization.get("data_construction_authorized") is not False
            or authorization.get("training_authorized") is not False
            or authorization.get("test_open_allowed") is not False
            or authorization.get("seed") != SEED or authorization.get("addition_count") != 1052
            or authorization.get("original_ratio_gate_floor") != 1.8
            or authorization.get("source_pool_path") != str(SOURCE_POOL)
            or authorization.get("source_pool_sha256") != policy.sha(SOURCE_POOL)
            or authorization.get("independent_supply_audit_sha256") != SUPPLY_SHA
            or audit.get("passed") is not True or audit.get("D_only_available") != 3366
            or audit.get("proposed_addition_count") != 1052
            or audit.get("old_B_decision_sha256") != policy.OLD_B_SHA
            or audit.get("source_pool_sha256") != policy.sha(SOURCE_POOL)):
        raise RuntimeError("No exact conservative original D-only TRAIN supply authority")
    identities = audit["proposed_inventory_only_not_dataset_rows"]
    if (len(identities) != 1052 or len({(r["instance_id"], r["function_id"]) for r in identities}) != 1052
            or policy.object_sha(identities) != authorization["proposed_identity_ledger_sha256"]):
        raise RuntimeError("Root-authorized original stable supply identity ledger drifted")
    return authorization, audit


def source_artifacts(ledger):
    """Only hashes/metadata, no pool-row decoder; safe in a model gate."""
    _, audit = authorization_metadata()
    if policy.sha(DEEP_SUPPLY_AUDIT) != DEEP_SUPPLY_SHA:
        raise RuntimeError("Complete original3366 D-only source census changed")
    deep = policy.read_json(DEEP_SUPPLY_AUDIT)
    if (deep.get("passed") is not True or deep.get("unused_TRAIN_D_only") != 3859
            or deep.get("eligible_after_deep_audit") != 3366
            or deep.get("needed_for_joint_TRAIN_2_to_1") != 1052
            or deep.get("source_pool_sha256") != policy.sha(SOURCE_POOL)
            or deep.get("Git_files_independently_checked") != 184
            or deep.get("runtime_cases_checked") != 185 or deep.get("graphs_checked") != 184):
        raise RuntimeError("No complete real original3366/proposed1052 source inventory")
    expected = dict(deep["source_artifact_sha256"])
    if expected.pop(str(SOURCE_POOL), None) != policy.sha(SOURCE_POOL):
        raise RuntimeError("Full supply census does not bind original eligible pool")
    if not isinstance(ledger.get("source_artifact_sha256"), dict) or ledger["source_artifact_sha256"] != expected:
        raise RuntimeError("Joint TRAIN source map must contain the entire exact frozen graph/runtime inventory")
    manifest_path = historical.B_RAW / "runtime_manifest.json"
    receipt = policy.read_json(historical.B_RAW / "construction_receipt.json")
    if policy.sha(manifest_path) != receipt["raw_files_sha256"]["runtime_manifest.json"]:
        raise RuntimeError("Original frozen B runtime manifest changed")
    manifest = policy.read_json(manifest_path)
    if (manifest.get("all_300_completed") is not True or manifest.get("result_count") != 300
            or manifest.get("missing_ids") != []):
        raise RuntimeError("Original B runtime manifest is incomplete")
    runtime_paths = {p for p in expected if p.endswith("/result.json")}
    graph_paths = {p for p in expected if "/graphs/" in p}
    if (len(runtime_paths) != 185 or len(graph_paths) != 184 or runtime_paths | graph_paths != set(expected)
            or any(manifest["result_sha256"].get(p) != expected[p] for p in runtime_paths)
            or any(expected.get(p) != h for p, h in audit["source_graph_sha256"].items())
            or any(r["graph_path"] not in graph_paths or r["runtime_result_path"] not in runtime_paths
                   for r in audit["proposed_inventory_only_not_dataset_rows"])):
        raise RuntimeError("Proposed/full graph/runtime inventory fails independent supply or frozen B cross-binding")
    sources = {str(IMPLEMENTATION): IMPLEMENTATION_SHA, str(SUPPLY_AUDIT): SUPPLY_SHA,
        str(DEEP_SUPPLY_AUDIT): DEEP_SUPPLY_SHA, str(manifest_path): policy.sha(manifest_path),
        str(SOURCE_POOL): policy.sha(SOURCE_POOL),
        str(historical.B_RAW / "construction_receipt.json"): policy.sha(historical.B_RAW / "construction_receipt.json")}
    sources.update(ledger["source_artifact_sha256"])
    policy.verify_hash_map(sources)
    return sources


def _physical_witness(row, cache):
    filename, target = row["function_id"].split("::", 1)
    qualified, line = target.rsplit("@", 1); key = row["repo"], row["base_commit"], filename
    if key not in cache:
        mirror = ROOT / "mirror_cache" / (row["repo"].rsplit("/", 1)[-1] + ".git")
        prefix = ["git", "--git-dir", str(mirror)]
        blob = subprocess.run(prefix + ["rev-parse", row["base_commit"] + ":" + filename],
            capture_output=True, check=True, timeout=30).stdout.decode().strip()
        raw = subprocess.run(prefix + ["cat-file", "blob", blob], capture_output=True, check=True, timeout=30).stdout
        if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != blob:
            raise RuntimeError("Supplement physical Git blob mismatch")
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline); text = raw.decode(encoding)
        from code_v5.prepare_runtime_filtered_data import Definitions
        inventory = Definitions(); inventory.visit(ast.parse(text, filename)); cache[key] = text, inventory.nodes, blob
    text, nodes, blob = cache[key]; node = nodes[qualified, int(line)]
    full = "".join(text.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
    if (filename != row["function_file"] or int(line) != row["function_def_line"]
            or hashlib.sha256(full.encode()).hexdigest() != row["full_function_source_sha256"]
            or full[:1500] != row["function"]
            or hashlib.sha256(json.dumps([row["issue"], row["function"]], ensure_ascii=False).encode()).hexdigest() != row["input_sha256"]):
        raise RuntimeError("Supplement base physical AST/source/features mismatch")
    return {"instance_id": row["instance_id"], "function_id": row["function_id"],
        "input_sha256": row["input_sha256"], "source_blob_sha1": blob,
        "full_source_sha256": row["full_function_source_sha256"],
        "graph_path": row["graph"]["graph_path"], "runtime_result_path": row["runtime_filter"]["result_path"]}


def candidate_rejection(row, train_ids, forbidden_pairs, forbidden_hashes, result):
    """Explicit conservative vetoes; coverage counts even when issue unavailable."""
    if (row.get("split") != "train" or row.get("label") is not False
            or row.get("label_source") != "D" or set(row.get("label_sources", [])) != {"D"}
            or row.get("instance_id") not in train_ids): return "wrong_D_or_TRAIN"
    if policy.pair(row) in forbidden_pairs: return "known_unsafe_or_original4C_or_selected_pair"
    if row["input_sha256"] in forbidden_hashes: return "existing_or_new_input_collision"
    observed = set(result.get("covered_function_ids", [])) | set(result.get("failed_test_function_ids", [])) | set(result.get("bootstrap_function_ids", []))
    if row["function_id"] in observed: return "any_observed_failed_or_bootstrap_even_unqualified"
    if row["function_file"] in set(result.get("test_patch_modified_files", [])) | set(result.get("runtime_unavailable_function_files", [])):
        return "modified_test_file_mapping_unavailable"
    return None


def supplement(selected, new_static_pool):
    authorization, audit = authorization_metadata()
    historical.validate_decision(historical.B_TRAINING, policy.OLD_B_DECISION)
    pool, old_hashes, roles = train_pool(SOURCE_POOL)
    _, new_hashes, _ = train_pool(new_static_pool); new_hashes = set(new_hashes)
    if len(old_hashes) != 10702 or len(set(old_hashes)) != len(old_hashes):
        raise RuntimeError("Original eligible pool dedup drift")
    old_manifest = policy.read_json(historical.SOURCE / "split_manifest.json")
    train_ids = set(old_manifest["splits"]["train"])
    existing_pairs = {policy.pair(r) for r in selected}; existing_hashes = {r["input_sha256"] for r in selected}
    known = {policy.pair(r) for r in policy.known_unsafe()}; four = {tuple(x) for x in audit["old4_C_excluded_pairs"]}
    if len(four) != 4: raise RuntimeError("Original four C exclusions missing")
    runtime = {}; graphs = {}; sources = {}; qualified = []; rejected = Counter()
    for row in pool:
        if row["label"] is not False or set(row["label_sources"]) != {"D"} or policy.pair(row) in existing_pairs: continue
        reason = None
        if row["label_source"] != "D" or row["instance_id"] not in train_ids: reason = "wrong_D_or_TRAIN"
        elif policy.pair(row) in known | four: reason = "known_unsafe_or_original4C_pair"
        elif row["input_sha256"] in existing_hashes | new_hashes: reason = "existing_or_new_input_collision"
        if reason: rejected[reason] += 1; continue
        iid = row["instance_id"]; rp = Path(row["runtime_filter"]["result_path"])
        if iid not in runtime:
            result = policy.read_json(rp); runtime[iid] = result
            sources[str(rp)] = policy.sha(rp)
        result = runtime[iid]
        if (row["runtime_filter"].get("static_v3_eligible") is not True
                or row["runtime_filter"]["result_sha256"] != policy.sha(rp)
                or result["instance_id"] != iid or result["repo"] != row["repo"] or result["base_commit"] != row["base_commit"]):
            raise RuntimeError("Supplement original static/runtime identity changed")
        reason = candidate_rejection(row, train_ids, existing_pairs | known | four, existing_hashes | new_hashes, result)
        if reason: rejected[reason] += 1; continue
        if iid not in graphs:
            gp = Path(row["graph"]["graph_path"]); graph = policy.read_json(gp)
            graphs[iid] = graph, {n["id"]: n for n in graph["functions"]}; sources[str(gp)] = policy.sha(gp)
        graph, nodes = graphs[iid]; node = nodes[row["function_id"]]
        if (sources[row["graph"]["graph_path"]] != row["graph"]["graph_sha256"] or graph["instance_id"] != iid
                or graph["repo"] != row["repo"] or graph["base_commit"] != row["base_commit"]
                or node["file"] != row["function_file"] or node["def_line"] != row["function_def_line"]
                or node["source_sha256"] != row["full_function_source_sha256"]):
            raise RuntimeError("Supplement original physical graph source drift")
        qualified.append(row)
    qualified.sort(key=lambda r: (miner.stable_key(SEED, r["instance_id"] + "/" + r["function_id"]), r["instance_id"], r["function_id"]))
    train = miner.summarize([r for r in selected if r["split"] == "train"])
    count = 2 * train["positive"] - train["negative"]
    if count != authorization["addition_count"] or count != 1052 or len(qualified) != audit["D_only_available"]:
        raise RuntimeError("Actual joint TRAIN quota/supply no longer matches the root correction")
    added = qualified[:count]; cache = {}; witnesses = [_physical_witness(r, cache) for r in added]
    if witnesses != audit["proposed_inventory_only_not_dataset_rows"]:
        raise RuntimeError("Supplement stable identities/physical Git witnesses differ from independent root supply")
    if (len({r["input_sha256"] for r in selected + added}) != len(selected + added)
            or any(r["split"] != "train" or r["label"] is not False or set(r["label_sources"]) != {"D"} for r in added)):
        raise RuntimeError("Only existing unique D-only TRAIN negatives may supplement selection")
    ledger = {"selection_revision": "joint-original-D-only-TRAIN-v1", "seed": SEED,
        "implementation_decision_path": str(IMPLEMENTATION), "implementation_decision_sha256": IMPLEMENTATION_SHA,
        "independent_supply_audit_path": str(SUPPLY_AUDIT), "independent_supply_audit_sha256": SUPPLY_SHA,
        "full_D_only_supply_audit_path": str(DEEP_SUPPLY_AUDIT), "full_D_only_supply_audit_sha256": DEEP_SUPPLY_SHA,
        "original_source_pool_path": str(SOURCE_POOL), "original_source_pool_sha256": policy.sha(SOURCE_POOL),
        "target_rule": "2 * combined TRAIN positive - current TRAIN negative",
        "before_TRAIN_positive": train["positive"], "before_TRAIN_negative": train["negative"],
        "addition_count": count, "after_TRAIN_negative": train["negative"] + count,
        "available_D_only": len(qualified), "rejection_counts": dict(rejected),
        "added_identities_and_physical_witnesses": witnesses,
        "added_row_sha256": {policy.canonical(list(policy.triple(r))): policy.object_sha(r) for r in added},
        "added_summary": miner.summarize(added), "source_artifact_sha256": sources,
        "Git_files_checked": len(cache), "old_pool_role_metadata_counts": roles,
        "all_original_selected_rows_preserved": True, "E_memberships_unchanged": True,
        "val_test_split_unchanged": True, "labels_created_or_changed": 0,
        "heldout_source_row_bodies_decoded": False, "sealed_test_file_decoded": False,
        "interpretation": "Original mechanical D proxy negatives, not established causal irrelevance; excludes every recorded covered function even for a static-only issue."}
    source_artifacts(ledger)
    return added, ledger


def validate_ledger(ledger, train_rows=None):
    """No old pool row parser; verify frozen metadata and exact TRAIN additions."""
    authorization, audit = authorization_metadata()
    if (ledger.get("selection_revision") != "joint-original-D-only-TRAIN-v1" or ledger.get("seed") != SEED
            or ledger.get("implementation_decision_sha256") != IMPLEMENTATION_SHA
            or ledger.get("independent_supply_audit_sha256") != SUPPLY_SHA
            or ledger.get("full_D_only_supply_audit_path") != str(DEEP_SUPPLY_AUDIT)
            or ledger.get("full_D_only_supply_audit_sha256") != DEEP_SUPPLY_SHA
            or ledger.get("original_source_pool_sha256") != policy.sha(SOURCE_POOL)
            or ledger.get("addition_count") != 1052 or ledger.get("available_D_only") != 3366
            or ledger.get("before_TRAIN_positive") != authorization["before_TRAIN_positive"]
            or ledger.get("before_TRAIN_negative") != authorization["before_TRAIN_negative"]
            or ledger.get("after_TRAIN_negative") != 8946
            or ledger.get("added_identities_and_physical_witnesses") != audit["proposed_inventory_only_not_dataset_rows"]
            or ledger.get("heldout_source_row_bodies_decoded") is not False
            or ledger.get("sealed_test_file_decoded") is not False or ledger.get("labels_created_or_changed") != 0
            or any(ledger.get(k) is not True for k in ("all_original_selected_rows_preserved", "E_memberships_unchanged", "val_test_split_unchanged"))):
        raise RuntimeError("Joint TRAIN ledger is not the exact root-authorized selection correction")
    source_artifacts(ledger)
    expected = {(r["instance_id"], r["function_id"], r["input_sha256"]) for r in audit["proposed_inventory_only_not_dataset_rows"]}
    if set(ledger["added_row_sha256"]) != {policy.canonical(list(k)) for k in expected}:
        raise RuntimeError("Joint TRAIN added-row ledger is incomplete")
    if train_rows is not None:
        index = {policy.triple(r): r for r in train_rows}; added = [index[k] for k in expected]
        old = policy.read_rows(historical.B_TRAINING / "pruner_train.jsonl")
        if (any(index.get(policy.triple(r)) != r for r in old)
                or any(r["split"] != "train" or r["label"] is not False or r["label_source"] != "D"
                       or set(r["label_sources"]) != {"D"} or ledger["added_row_sha256"][policy.canonical(list(policy.triple(r)))] != policy.object_sha(r) for r in added)
                or miner.summarize(added) != ledger["added_summary"]):
            raise RuntimeError("Actual TRAIN supplement changed labels/original rows or exact D-only identities")
    return ledger
