"""Freeze a newly explicit user-authorized v3 noise-disclosed exploratory policy."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from code_v5.noise_disclosed_policy import (ROOT, SOURCE, DERIVED, SIGNOFF, POLICY, ALLOWED_FAILED,
                                          read_json, sha, validate_authorization, validate_derived, write_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    stats, seal, split_ids = validate_derived(DERIVED)
    contract = read_json(args.contract)
    validate_authorization(contract)
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError("Frozen authorization output must be new")
    output.mkdir(parents=True)
    snapshot = output / "execution_contract_snapshot.json"
    snapshot.write_bytes(args.contract.read_bytes())
    files = ("noise_disclosed_policy.py", "prepare_noise_disclosed_data.py", "freeze_noise_disclosed_decision.py",
             "train_judges.py", "run_training_pair.py", "race_and_calibrate.py", "judge_models.py", "metrics.py")
    decision = {"schema_version": 1, "track": "exploratory", "data_policy": POLICY, "formal_failed": True,
                "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "reason": "New explicit user authorization treats the original failed 3/30 review as disclosed label noise; removes exactly three proven TRAIN errors. Original formal failure remains; integrity/issue split/dedup/leakage gates are not exempt.",
                "data_dir": str(DERIVED), "test_open_allowed": False,
                "statistics_sha256": sha(DERIVED / "statistics.json"), "derivation_sha256": sha(DERIVED / "noise_disclosure_derivation.json"),
                "source_statistics_sha256": sha(SOURCE / "statistics.json"), "source_review_sha256": sha(SOURCE / "human_review_codex_reviewed.jsonl"),
                "source_signoff_sha256": sha(SIGNOFF), "execution_contract_path": str(snapshot),
                "execution_contract_sha256": sha(snapshot), "execution_contract_source_path": str(args.contract.resolve()),
                "policy_code_sha256": {name: sha(ROOT / "code_v5" / name) for name in files},
                "allowed_failed_gates": sorted(ALLOWED_FAILED), "raw_counts": stats["raw_counts"],
                "selected_counts": stats["selected"], "formal_gate_results": stats["quality_gates"],
                "formal_passed_preserved_false": True, "test_json_parsed": False,
                "seal_sha256": sha(DERIVED / "test_file_seal.json"), "split_manifest_sha256": sha(DERIVED / "split_manifest.json"),
                **{split + "_sha256": sha(DERIVED / f"pruner_{split}.jsonl") for split in ("train", "val", "test")}}
    path = output / "root_exploratory_decision.json"
    write_json(path, decision)
    print(json.dumps({"decision_path": str(path), "sha256": sha(path), "data_policy": POLICY}, ensure_ascii=False))


if __name__ == "__main__":
    main()
