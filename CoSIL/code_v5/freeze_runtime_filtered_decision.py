"""Freeze B authorization only after all300 runtime results and full30 review.

Preserves original B raw/pending review; creates a separate exact TRAIN-error
deletion derivative. No test decoding, Torch, training, or model/API calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from code_v5.runtime_filtered_policy import (
    ROOT, B_RAW, B_TRAINING, CODE_BINDINGS, POLICY, derive_reviewed_B,
    read_json, sha, validate_authorization, validate_decision, validate_reviewed_B,
)


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--review", type=Path, help="Complete signed B TRAIN-only 30 records, required to derive initial reviewed dataset")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    contract = read_json(args.contract); validate_authorization(contract)
    if not B_TRAINING.exists():
        if args.review is None:
            raise RuntimeError("B full30 signed review is required before training authorization")
        derive_reviewed_B(args.review)
    elif args.review is not None and sha(args.review) != sha(B_TRAINING / "human_review_codex_reviewed.jsonl"):
        raise RuntimeError("Preserve existing B full30 signatures; do not replace them")
    stats, seal, _ = validate_reviewed_B(B_TRAINING, audit_construction=True)
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError("B frozen authorization needs a new directory; old decisions remain intact")
    output.mkdir(parents=True)
    snapshot = output / "execution_contract_snapshot.json"
    snapshot.write_bytes(args.contract.read_bytes())
    failed = sorted(k for k, v in stats["quality_gates"].items() if v is not True)
    decision = {"schema_version": 1, "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "track": "exploratory", "data_policy": POLICY, "formal_failed": True, "test_open_allowed": False,
        "data_dir": str(B_TRAINING), "raw_data_dir": str(B_RAW),
        "reason": "Independent user-authorized B observed-runtime filtering; genuine source/coverage review is disclosed and all confirmed TRAIN errors are exactly excluded; original labels/split/test seal remain unchanged.",
        "statistics_sha256": sha(B_TRAINING / "statistics.json"), "raw_statistics_sha256": sha(B_RAW / "statistics.json"),
        "execution_contract_path": str(snapshot), "execution_contract_sha256": sha(snapshot),
        "execution_contract_source_path": str(args.contract.resolve()),
        "policy_code_sha256": {p: sha(ROOT / p) for p in CODE_BINDINGS},
        "selected_counts": stats["selected"], "raw_counts": stats["raw_counts"],
        "formal_gate_results": stats["quality_gates"], "allowed_failed_gates": failed,
        "reviewed_records": 30, "review_label_errors": stats["review"]["label_errors"],
        "runtime_manifest_sha256": sha(B_RAW / "runtime_manifest.json"),
        "review_sha256": sha(B_TRAINING / "human_review_codex_reviewed.jsonl"),
        "reviewed_train_derivation_sha256": sha(B_TRAINING / "reviewed_train_derivation.json"),
        "seal_sha256": sha(B_TRAINING / "test_file_seal.json"),
        "split_manifest_sha256": sha(B_TRAINING / "split_manifest.json"),
        **{s + "_sha256": sha(B_TRAINING / f"pruner_{s}.jsonl") for s in ("train", "val", "test")}}
    decision_path = output / "root_exploratory_decision.json"
    write_new(decision_path, decision)
    validate_decision(B_TRAINING, decision_path)
    print(json.dumps({"decision_path": str(decision_path), "decision_sha256": sha(decision_path),
                      "data_policy": POLICY, "review_errors": stats["review"]["label_errors"],
                      "model_training_started": False, "test_rows_decoded": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
