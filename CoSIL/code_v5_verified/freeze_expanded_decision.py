"""Sign C after complete source/runtime30 review; preserve historical B.

All explicit unsafe TRAIN examples are deleted in a new derivative, including
newly reviewed old-Lite negatives. No labels flip, replacement examples, test
decoding or model execution. A frozen root C contract remains necessary.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from code_v5 import build_pruner_data as miner
from code_v5 import prepare_runtime_filtered_data as historical_builder
from code_v5_verified import expanded_policy as policy
from code_v5_verified.prepare_static_extension import exclusive_json


def derive(review_path):
    raw, receipt, split, ids = policy.validate_construction()
    reviewed, unsafe = policy.validate_review(review_path, audit_source=True)
    if policy.TRAINING.exists(): raise FileExistsError("Reviewed C derivative is immutable; no overwrites")
    selected = policy.read_rows(policy.RAW / "selected_source_pool.jsonl")
    if miner.summarize(selected) != raw["selected"]:
        raise RuntimeError("Source-selected construction rows changed")
    bad = {policy.triple(r) for r in unsafe}
    deleted = [r for r in selected if policy.triple(r) in bad]
    if len(deleted) != len(unsafe) or any(r["label"] is not False or r["split"] != "train" for r in deleted):
        raise RuntimeError("Only exact signed30 TRAIN negative identities can be excluded")
    selected = [r for r in selected if policy.triple(r) not in bad]
    counts = miner.summarize(selected); gates = policy.quantity_gates(counts, len(unsafe))
    if any(gates[k] is not True for k in ("negative_to_positive_ratio_about_2", "E_fraction_of_negatives_ge_one_third", "ordinary_D_negatives_retained")):
        raise RuntimeError("C has a nonexempt ratio/E-fraction/D-only quality failure; no reviewed training derivative")
    policy.TRAINING.mkdir()
    # Preserve original raw TRAIN line encodings while removing exact identities.
    lines = []
    for line in (policy.RAW / "pruner_train.jsonl").read_bytes().splitlines(keepends=True):
        if policy.triple(json.loads(line)) not in bad: lines.append(line)
    (policy.TRAINING / "pruner_train.jsonl").write_bytes(b"".join(lines))
    for name in ("pruner_val.jsonl", "pruner_test.jsonl", "split_manifest.json", "human_review.jsonl",
                 "runtime_manifest.json", "review_source_runtime_evidence.json", "comparison_B_C_val_shared_pairs.json", "joint_TRAIN_sampling_ledger.json"):
        (policy.TRAINING / name).write_bytes((policy.RAW / name).read_bytes())
    signed = policy.TRAINING / "human_review_codex_reviewed.jsonl"
    signed.write_bytes(Path(review_path).read_bytes())
    seal = deepcopy(raw["seal"])
    for role in ("train", "val", "test"):
        p = policy.TRAINING / f"pruner_{role}.jsonl"
        seal["frozen_files"][role] = {"path": str(p), "sha256": policy.sha(p), "count": sum(r["split"] == role for r in selected)}
    seal["test_path"] = str(policy.TRAINING / "pruner_test.jsonl")
    exclusive_json(policy.TRAINING / "test_file_seal.json", seal)
    stats = deepcopy(raw)
    stats.update(selected=counts, seal=seal, passed=False, exploratory_quality_gate_passed=True,
        quality_gates=gates,
        runtime_distribution=historical_builder.runtime_distribution(selected))
    new_ids = set(split["eligible_new_IDs"])
    stats["new_selected_before_review"] = deepcopy(raw["new_selected"])
    stats["new_selected"] = miner.summarize([r for r in selected if r["instance_id"] in new_ids])
    stats["original_B_selected_before_review"] = deepcopy(raw["original_B_selected"])
    stats["old_Lite_selected_with_TRAIN_replenishment_before_review"] = deepcopy(raw["old_Lite_selected_with_TRAIN_replenishment"])
    stats["old_B_selected_after_C_review"] = miner.summarize([r for r in selected if r["instance_id"] not in new_ids])
    stats["review"] = {"review_complete": True, "passed": len(unsafe) <= 2,
        "historical_threshold_only_not_current_veto": True, "reviewed_records": 30,
        "label_errors": len(unsafe), "unsafe_negative_count": len(unsafe),
        "classification_counts": dict(Counter(r["relation_classification"] for r in reviewed)),
        "observed_stratified_conservative_exclusion_fraction": len(unsafe) / 30,
        "family_counts": dict(Counter(r["review_family"] for r in reviewed)),
        "review_sha256": policy.sha(signed), "reviewer_kind": "Codex source/runtime evidence review, not human signature",
        "human_signature": False,
        "interpretation": "Full30 family-stratified conservative exclusion observation, not population noise, zero-noise certification or 30 certain causal errors. Conditional risks remain explicitly distinct."}
    exclusive_json(policy.TRAINING / "statistics.json", stats)
    exclusive_json(policy.TRAINING / "reviewed_train_derivation.json", {
        "raw_statistics_sha256": policy.sha(policy.RAW / "statistics.json"), "review_sha256": policy.sha(signed),
        "excluded_training_pairs": [list(policy.triple(r)) for r in unsafe],
        "excluded_training_rows": deleted, "labels_flipped": 0, "replacement_labels_created": 0,
        "additional_old_Lite_train_masks": [list(policy.triple(r)) for r in deleted if r["instance_id"] not in split["eligible_new_IDs"]],
        "original_B_history_unchanged": True, "val_test_split_bytes_unchanged": True,
        "remaining_review_examples_not_relabelled_as_new_random_pass": True})
    policy.validate_reviewed(policy.TRAINING, audit_source=True)
    return stats


def freeze(contract_path, output_dir):
    stats, seal, split = policy.validate_reviewed(policy.TRAINING, audit_source=True)
    contract = policy.read_json(contract_path); cfg = contract.get(policy.CONTRACT_KEY, {})
    if any(cfg.get(k) != v for k, v in policy.required_contract_fields().items()):
        raise RuntimeError("No complete root C execution contract; no frozen authorization")
    output = Path(output_dir).resolve()
    expected = policy.ROOT / "results/v5_pruner/C_Verified_plus_B_runtime_authorization_exploratory"
    if output != expected or output.exists(): raise PermissionError("C authorization requires a new dedicated output")
    failed = sorted(k for k, v in stats["quality_gates"].items() if v is not True)
    allowed = policy.allowed_failed_gates(cfg, stats)
    if not set(failed) <= allowed: raise RuntimeError("Nonquantity quality failure cannot be exempted")
    output.mkdir()
    snapshot = output / "execution_contract_snapshot.json"; snapshot.write_bytes(Path(contract_path).read_bytes())
    decision = {"data_policy": policy.POLICY, "track": "exploratory", "formal_failed": True,
        "exploratory_quality_gate_passed": True, "test_open_allowed": False,
        "data_dir": str(policy.TRAINING), "execution_contract_path": str(snapshot),
        "execution_contract_sha256": policy.sha(snapshot), "allowed_failed_gates": failed,
        "selected_counts": stats["selected"], "formal_gate_results": stats["quality_gates"],
        "policy_code_sha256": {p: policy.sha(policy.ROOT / p) for p in policy.CODE_BINDINGS},
        "statistics_sha256": policy.sha(policy.TRAINING / "statistics.json"),
        "seal_sha256": policy.sha(policy.TRAINING / "test_file_seal.json"),
        "split_manifest_sha256": policy.sha(policy.TRAINING / "split_manifest.json"),
        "review_sha256": policy.sha(policy.TRAINING / "human_review_codex_reviewed.jsonl"),
        "raw_statistics_sha256": policy.sha(policy.RAW / "statistics.json"),
        "construction_receipt_sha256": policy.sha(policy.RAW / "construction_receipt.json"),
        "runtime_manifest_sha256": policy.sha(policy.RAW / "runtime_manifest.json"),
        "reviewed_train_derivation_sha256": policy.sha(policy.TRAINING / "reviewed_train_derivation.json"),
        **{r + "_sha256": policy.sha(policy.TRAINING / f"pruner_{r}.jsonl") for r in ("train", "val", "test")}}
    path = output / "root_exploratory_decision.json"; exclusive_json(path, decision)
    policy.validate_decision(policy.TRAINING, path)
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--review", type=Path)
    p.add_argument("--contract", type=Path); p.add_argument("--output", type=Path,
        default=policy.ROOT / "results/v5_pruner/C_Verified_plus_B_runtime_authorization_exploratory")
    a = p.parse_args()
    if a.review: derive(a.review)
    if a.contract:
        path = freeze(a.contract, a.output); print(json.dumps({"decision_path": str(path), "sha256": policy.sha(path)}))
    elif not a.review: raise RuntimeError("Specify genuine review and/or final root C contract")


if __name__ == "__main__": main()
