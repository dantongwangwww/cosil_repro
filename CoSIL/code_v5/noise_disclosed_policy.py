"""Explicit v3 train-only noise-disclosure policy; original formal gates stay failed.

No Torch, model/API calls, test JSON decoder, or inferred replacement labels.
The policy permits the acknowledged review and quantity failures only under a
new frozen user authorization, after exactly the three signed train errors are
removed. All source bytes, validation bytes and sealed test bytes are verified.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
POLICY = "noise-disclosed-v3"
REVIEW_GATE = "review_30_train_E_examples_at_most_2_errors"
ALLOWED_FAILED = {"positive_unique_pairs_ge_8000", "E_unique_pairs_ge_3000", REVIEW_GATE}
REVIEW_FIELDS = {"review_status", "label_error", "review_note"}
SOURCE = ROOT / "results/v5_pruner/data_v3"
DERIVED = ROOT / "results/v5_pruner/data_v3_noise_disclosed"
SIGNOFF = ROOT / "results/v5_pruner/v3_review_final_signoff.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def read_jsonl(path):
    if "test" in Path(path).name:
        raise PermissionError("This policy never decodes test rows")
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def identity(row):
    return tuple(row[k] for k in ("instance_id", "function_id", "input_sha256"))


def validate_source():
    stats = read_json(SOURCE / "statistics.json")
    receipt = read_json(SOURCE / "review_failure_and_dataset_hashes.json")
    signoff = read_json(SIGNOFF)
    for filename, field in (("statistics.json", "statistics_sha256"),
                            ("human_review_codex_reviewed.jsonl", "review_sha256"),
                            ("review_final_counterexamples.json", "counterexamples_sha256")):
        if sha(SOURCE / filename) != receipt[field]:
            raise RuntimeError("Frozen source evidence changed: " + filename)
    for path, expected in receipt["protected_dataset_sha256"].items():
        if sha(ROOT / path) != expected:
            raise RuntimeError("Frozen source dataset changed: " + path)
    if (stats["passed"] is not False or stats["mechanical_labels_only"] is not True
            or stats["model_calls"] != 0 or stats["review"]["passed"] is not False
            or stats["review"]["label_errors"] != 3):
        raise RuntimeError("Original v3 must retain its actual failed review and formal gate")
    failed = {k for k, v in stats["quality_gates"].items() if v is not True}
    if not failed <= ALLOWED_FAILED or REVIEW_GATE not in failed:
        raise RuntimeError("Any nonreview integrity failure still prohibits training")
    if (signoff["review_count"] != 30 or signoff["known_label_errors"] != 3
            or signoff["conclusion"] != "failed" or signoff["reviewer"] != "Codex/机械证据审阅"):
        raise RuntimeError("The original 30-record failed signoff must be preserved")
    pending = {identity(r): r for r in read_jsonl(SOURCE / "human_review.jsonl")}
    reviewed_rows = read_jsonl(SOURCE / "human_review_codex_reviewed.jsonl")
    reviewed = {identity(r): r for r in reviewed_rows}
    if len(pending) != 30 or len(reviewed_rows) != 30 or pending.keys() != reviewed.keys():
        raise RuntimeError("Missing or duplicated signed review identity")
    if Counter(r["review_family"] for r in reviewed_rows) != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}:
        raise RuntimeError("The actual stratified review must remain 10 per E family")
    for key, row in reviewed.items():
        original = pending[key]
        if ({k: v for k, v in row.items() if k not in REVIEW_FIELDS}
                != {k: v for k, v in original.items() if k not in REVIEW_FIELDS}):
            raise RuntimeError("Signed review changed a label or source payload")
        if (row["split"] != "train" or row["label"] is not False
                or row["review_status"] != "reviewed" or type(row["label_error"]) is not bool
                or not row["review_note"].strip()):
            raise RuntimeError("Incomplete train-only review")
    errors = [r for r in reviewed_rows if r["label_error"]]
    if len(errors) != 3:
        raise RuntimeError("Exactly the three original confirmed errors must be disclosed")
    proof_ids = {identity(p["identity"]) for p in read_json(SOURCE / "review_final_counterexamples.json")["proofs"]}
    if proof_ids != {identity(r) for r in errors}:
        raise RuntimeError("Excluded identities must equal the source-proved counterexamples")
    manifest = read_json(SOURCE / "split_manifest.json")
    split_ids = {s: set(manifest["splits"][s]) for s in ("train", "val", "test")}
    benchmark_ids = set(read_json(ROOT / "results/comparison/逐题定位对照数据.json")["issue_order"])
    if ([len(split_ids[s]) for s in ("train", "val", "test")] != [240, 30, 30]
            or set.union(*split_ids.values()) != benchmark_ids):
        raise RuntimeError("Original disjoint issue split differs from Lite300")
    for version in ("data", "data_v2", "data_v3", DERIVED.name):
        marker = SOURCE.parent / version / "pruner_test.jsonl.v5_opened_once.json"
        if marker.exists():
            raise RuntimeError("A test opening marker exists; no further tuning allowed")
    return stats, receipt, errors, split_ids


def train_bytes_without_errors(errors):
    error_map = {identity(r): r for r in errors}
    kept, removed, original_rows = [], [], []
    for line in (SOURCE / "pruner_train.jsonl").read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        original_rows.append(row)
        if identity(row) in error_map:
            reviewed = error_map[identity(row)]
            if row["label"] is not False or row["split"] != "train":
                raise RuntimeError("Only signed negative TRAIN errors may be removed")
            if any(row[k] != reviewed[k] for k in row):
                raise RuntimeError("Excluded row payload differs from the reviewed sample")
            removed.append(row)
        else:
            kept.append(line)
    if len(removed) != 3 or {identity(r) for r in removed} != set(error_map):
        raise RuntimeError("The original train must contain exactly all three excluded identities")
    return b"".join(kept), removed, original_rows


def check_train_val(rows_by_split, split_ids):
    inputs, pairs = set(), set()
    for split, rows in rows_by_split.items():
        for row in rows:
            pair = (row["instance_id"], row["function_id"])
            fingerprint = hashlib.sha256(json.dumps([row["issue"], row["function"]], ensure_ascii=False).encode()).hexdigest()
            if (row["instance_id"] not in split_ids[split] or row["split"] != split
                    or type(row["label"]) is not bool or len(row["issue"]) > 2000
                    or len(row["function"]) > 1500 or fingerprint != row["input_sha256"]
                    or row["input_sha256"] in inputs or pair in pairs):
                raise RuntimeError("Train/val data integrity, duplicate input, or issue-split failure")
            inputs.add(row["input_sha256"])
            pairs.add(pair)


def derive_data():
    stats, receipt, errors, split_ids = validate_source()
    kept_bytes, removed, original_train = train_bytes_without_errors(errors)
    new_train = [r for r in original_train if identity(r) not in {identity(x) for x in removed}]
    val = read_jsonl(SOURCE / "pruner_val.jsonl")
    check_train_val({"train": new_train, "val": val}, split_ids)
    if DERIVED.exists():
        raise FileExistsError("Derived data is immutable; an existing directory is never overwritten")
    DERIVED.mkdir()
    (DERIVED / "pruner_train.jsonl").write_bytes(kept_bytes)
    for filename in ("pruner_val.jsonl", "pruner_test.jsonl", "split_manifest.json",
                     "human_review.jsonl", "human_review_codex_reviewed.jsonl",
                     "review_final_counterexamples.json", "review_call_evidence.json", "review_benchmark_patches.json"):
        shutil.copyfile(SOURCE / filename, DERIVED / filename)
    selected = deepcopy(stats["selected"])
    selected["unique_pairs"] -= 3
    for row in removed:
        changes = {"negative": 1, "primary_source_" + row["label_source"]: 1, "E_unique_union": 1}
        changes.update({"source_" + s: 1 for s in row["label_sources"]})
        for key, count in changes.items():
            selected[key] -= count
            selected["by_split"]["train"][key] -= count
        selected["by_repo"][row["repo"]]["negative"] -= 1
        selected["by_anchor"][row["anchor"]]["negative"] -= 1
    selected["by_split"]["train"]["issues_with_rows"] = len({r["instance_id"] for r in new_train})
    selected["by_split"]["train"]["issues_with_positive_rows"] = len({r["instance_id"] for r in new_train if r["label"]})
    seal = deepcopy(stats["seal"])
    seal["dataset_version"] = "v3_noise_disclosed_train_three_errors_removed"
    seal["test_path"] = str(DERIVED / "pruner_test.jsonl")
    for split in ("train", "val", "test"):
        path = DERIVED / f"pruner_{split}.jsonl"
        seal["frozen_files"][split]["path"] = str(path)
        seal["frozen_files"][split]["sha256"] = sha(path)
    seal["frozen_files"]["train"]["count"] -= 3
    write_json(DERIVED / "test_file_seal.json", seal)
    derivation = {"policy": POLICY, "source_data_dir": str(SOURCE), "source_statistics_sha256": sha(SOURCE / "statistics.json"),
                  "source_review_sha256": sha(SOURCE / "human_review_codex_reviewed.jsonl"),
                  "source_signoff_sha256": sha(SIGNOFF), "source_signoff_path": str(SIGNOFF),
                  "source_protected_hashes": receipt["protected_dataset_sha256"],
                  "excluded_confirmed_train_errors": [{k: r[k] for k in ("instance_id", "function_id", "input_sha256", "label", "split", "label_sources")} for r in removed],
                  "removed_count": 3, "new_labels_generated": 0, "test_rows_decoded": False,
                  "validation_and_test_bytes_unchanged": True,
                  "original_stratified_review": {"count": 30, "errors": 3, "family_counts": {"e_log": 10, "e_bm25": 10, "e_anchor": 10}, "sample_error_fraction": .1,
                                                 "interpretation": "Stratified training-only sample, not a random population estimate or proof of no remaining noise; other unseen train/val/test labels may remain noisy."}}
    write_json(DERIVED / "noise_disclosure_derivation.json", derivation)
    new_stats = {"schema_version": 1, "dataset_version": seal["dataset_version"], "mechanical_labels_only": True,
                 "model_calls": 0, "training_started": False, "test_performance_opened": False,
                 "raw_counts": stats["raw_counts"], "selected": selected, "quality_gates": deepcopy(stats["quality_gates"]),
                 "review": deepcopy(stats["review"]), "passed": False,
                 "seal": seal, "split_manifest_sha256": sha(DERIVED / "split_manifest.json"),
                 "data_policy": POLICY, "derivation_path": str(DERIVED / "noise_disclosure_derivation.json"),
                 "derivation_sha256": sha(DERIVED / "noise_disclosure_derivation.json"),
                 "limitations": stats["limitations"] + ["Original 3/30 review failed; disclosed as exploratory label noise, not falsely passed.", "Removing three train errors reduces E to 2997; neither remaining noise nor test accuracy is known.", "D-only stays 84; negative distribution remains dominated by E."]}
    new_stats["quality_gates"]["E_unique_pairs_ge_3000"] = selected["E_unique_union"] >= 3000
    write_json(DERIVED / "statistics.json", new_stats)
    validate_derived(DERIVED)
    return new_stats


def validate_derived(data_dir):
    data_dir = Path(data_dir).resolve()
    if data_dir != DERIVED:
        raise RuntimeError("This explicit policy only authorizes the separate v3 noise-disclosed dataset")
    original_stats, receipt, errors, split_ids = validate_source()
    expected_train, removed, _ = train_bytes_without_errors(errors)
    stats = read_json(data_dir / "statistics.json")
    derivation = read_json(data_dir / "noise_disclosure_derivation.json")
    if sha(data_dir / "noise_disclosure_derivation.json") != stats["derivation_sha256"]:
        raise RuntimeError("Frozen train deletion derivation changed")
    expected_ids = {identity(r) for r in removed}
    if (derivation["policy"] != POLICY or derivation["removed_count"] != 3
            or {identity(r) for r in derivation["excluded_confirmed_train_errors"]} != expected_ids
            or derivation["source_statistics_sha256"] != sha(SOURCE / "statistics.json")
            or derivation["source_signoff_sha256"] != sha(SIGNOFF)
            or derivation["source_review_sha256"] != sha(SOURCE / "human_review_codex_reviewed.jsonl")):
        raise RuntimeError("Train-only deletion or original failed review provenance changed")
    if ((data_dir / "pruner_train.jsonl").read_bytes() != expected_train
            or stats["mechanical_labels_only"] is not True or stats["model_calls"] != 0
            or stats["passed"] is not False or stats["review"] != original_stats["review"]):
        raise RuntimeError("Derived train/labels or original failed review result changed")
    for name in ("pruner_val.jsonl", "pruner_test.jsonl", "split_manifest.json", "human_review.jsonl",
                 "human_review_codex_reviewed.jsonl", "review_final_counterexamples.json", "review_call_evidence.json", "review_benchmark_patches.json"):
        if sha(data_dir / name) != sha(SOURCE / name):
            raise RuntimeError("Unchanged validation/test/evidence bytes were modified: " + name)
    rows_by_split = {s: read_jsonl(data_dir / f"pruner_{s}.jsonl") for s in ("train", "val")}
    check_train_val(rows_by_split, split_ids)
    seal = read_json(data_dir / "test_file_seal.json")
    if seal != stats["seal"] or sha(data_dir / "split_manifest.json") != stats["split_manifest_sha256"]:
        raise RuntimeError("Derived seal or original split changed")
    for split in ("train", "val", "test"):
        path = data_dir / f"pruner_{split}.jsonl"
        entry = seal["frozen_files"][split]
        if Path(entry["path"]).resolve() != path or sha(path) != entry["sha256"]:
            raise RuntimeError("Derived sealed file changed: " + split)
        if split in rows_by_split and len(rows_by_split[split]) != entry["count"]:
            raise RuntimeError("Derived train/val count differs from seal")
    for split in ("train", "val"):
        rows = rows_by_split[split]
        summary = stats["selected"]["by_split"][split]
        if summary["positive"] != sum(r["label"] for r in rows) or summary["negative"] != sum(not r["label"] for r in rows):
            raise RuntimeError("Measured selected count changed")
    if (stats["selected"]["positive"] != 1542 or stats["selected"]["negative"] != 3081
            or stats["selected"]["E_unique_union"] != 2997 or seal["count"] != 339):
        raise RuntimeError("Expected actual post-deletion v3 counts")
    failed = {k for k, v in stats["quality_gates"].items() if v is not True}
    if failed != ALLOWED_FAILED:
        raise RuntimeError("Only the disclosed review and two actual quantity failures may remain")
    return stats, seal, split_ids


def validate_authorization(contract):
    policy = contract.get("noise_disclosed_exploratory_v3", {})
    expected = {"enabled": True, "source_data_dir": str(SOURCE), "derived_data_dir": str(DERIVED),
                "exclude_confirmed_train_errors": 3, "test_open_allowed": False,
                "review_as_noise_disclosure": True}
    if any(policy.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Frozen root contract lacks exact explicit noise-disclosed v3 authorization")
    e_policy = policy.get("E_quantity_specific_authorization", {})
    if (e_policy.get("original_minimum") != 3000 or e_policy.get("derived_count_allowed") != 2997
            or e_policy.get("general_E_quantity_waiver") is not False
            or e_policy.get("new_replacement_labels_allowed") is not False
            or e_policy.get("sole_allowed_reason") != "exactly three confirmed E errors removed from train"):
        raise RuntimeError("E=2997 must be specifically authorized only due to the three deletions")
    return policy


def validate_decision(data_dir, decision_file):
    stats, seal, split_ids = validate_derived(data_dir)
    decision = read_json(decision_file)
    if (decision.get("track") != "exploratory" or decision.get("data_policy") != POLICY
            or decision.get("formal_failed") is not True or decision.get("test_open_allowed") is not False
            or decision.get("statistics_sha256") != sha(DERIVED / "statistics.json")):
        raise RuntimeError("Noise-disclosed exploratory decision does not bind the actual derived statistics")
    contract_path = Path(decision["execution_contract_path"])
    if sha(contract_path) != decision["execution_contract_sha256"]:
        raise RuntimeError("Frozen authorized root contract changed")
    validate_authorization(read_json(contract_path))
    code_hashes = decision["policy_code_sha256"]
    required = {"noise_disclosed_policy.py", "prepare_noise_disclosed_data.py", "freeze_noise_disclosed_decision.py", "train_judges.py", "run_training_pair.py", "race_and_calibrate.py", "judge_models.py", "metrics.py"}
    if set(code_hashes) != required or any(sha(ROOT / "code_v5" / name) != value for name, value in code_hashes.items()):
        raise RuntimeError("Frozen explicit policy or training/metric code changed")
    binding = {"seal_sha256": sha(DERIVED / "test_file_seal.json"), "split_manifest_sha256": sha(DERIVED / "split_manifest.json"),
               "train_sha256": sha(DERIVED / "pruner_train.jsonl"), "val_sha256": sha(DERIVED / "pruner_val.jsonl"),
               "test_sha256": sha(DERIVED / "pruner_test.jsonl"), "derivation_sha256": sha(DERIVED / "noise_disclosure_derivation.json"),
               "source_statistics_sha256": sha(SOURCE / "statistics.json"), "source_review_sha256": sha(SOURCE / "human_review_codex_reviewed.jsonl"), "source_signoff_sha256": sha(SIGNOFF)}
    if any(decision.get(k) != v for k, v in binding.items()):
        raise RuntimeError("Decision no longer binds source evidence and train-only deletion bytes")
    if (set(decision.get("allowed_failed_gates", [])) != ALLOWED_FAILED
            or decision.get("selected_counts") != stats["selected"] or decision.get("formal_gate_results") != stats["quality_gates"]):
        raise RuntimeError("Decision has misrepresented actual failed gates or selected counts")
    provenance = {"statistics_sha256": sha(DERIVED / "statistics.json"), "seal_sha256": sha(DERIVED / "test_file_seal.json"),
                  "split_manifest_sha256": sha(DERIVED / "split_manifest.json"), "review_sha256": stats["review"]["review_sha256"],
                  "reviewer_kind": stats["review"]["reviewer_kind"], "test_labels_read": False,
                  "track": "exploratory", "data_policy": POLICY, "formal_data_gate_passed": False,
                  "noise_disclosure": read_json(DERIVED / "noise_disclosure_derivation.json")["original_stratified_review"],
                  "root_decision": {"path": str(Path(decision_file).resolve()), "sha256": sha(decision_file),
                                    "execution_contract_path": str(contract_path), "execution_contract_sha256": decision["execution_contract_sha256"],
                                    "allowed_failed_gates": decision["allowed_failed_gates"], "formal_failed": True}}
    return stats, seal, split_ids, provenance
