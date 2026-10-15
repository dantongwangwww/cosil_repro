"""Create new immutable regularized authorization; never rewrite original A."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from code_v5.noise_disclosed_policy import (ROOT, SOURCE, DERIVED, SIGNOFF, ALLOWED_FAILED,
                                          validate_derived, validate_authorization, sha, write_json)
from code_v5_regularized.policy import FILES, ORIGINAL_DECISION, ORIGINAL_RERANKER, validate_prescription


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    stats, seal, split_ids = validate_derived(DERIVED)
    contract = json.loads(args.contract.read_text())
    validate_authorization(contract)
    validate_prescription(contract)
    if args.output_dir.exists():
        raise FileExistsError("New prescription authorization output must be new")
    args.output_dir.mkdir(parents=True)
    snapshot = args.output_dir.resolve() / "execution_contract_snapshot.json"
    snapshot.write_bytes(args.contract.read_bytes())
    core = ("noise_disclosed_policy.py", "prepare_noise_disclosed_data.py", "freeze_noise_disclosed_decision.py",
            "train_judges.py", "run_training_pair.py", "race_and_calibrate.py", "judge_models.py", "metrics.py")
    decision = {"schema_version": 1, "track": "exploratory", "data_policy": "noise-disclosed-v3", "formal_failed": True,
                "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "reason": "Explicit user correction treats the measured 23.93pp train/val gap as overfitting; retain original A and train an isolated rank8/dropout0.1 model, same data and other hyperparameters, selecting completed-epoch val-accuracy peak.",
                "experiment_condition": "rank8_dropout0.1_alpha32", "test_open_allowed": False, "data_dir": str(DERIVED),
                "statistics_sha256": sha(DERIVED / "statistics.json"), "derivation_sha256": sha(DERIVED / "noise_disclosure_derivation.json"),
                "source_statistics_sha256": sha(SOURCE / "statistics.json"), "source_review_sha256": sha(SOURCE / "human_review_codex_reviewed.jsonl"),
                "source_signoff_sha256": sha(SIGNOFF), "execution_contract_path": str(snapshot), "execution_contract_sha256": sha(snapshot),
                "policy_code_sha256": {name: sha(ROOT / "code_v5" / name) for name in core},
                "regularized_code_sha256": {name: sha(ROOT / "code_v5_regularized" / name) for name in FILES},
                "original_A_decision_sha256": sha(ORIGINAL_DECISION),
                "original_reranker_summary_sha256": sha(ORIGINAL_RERANKER / "training_summary.json"),
                "original_reranker_val_accuracy_peak_prediction_sha256": sha(ORIGINAL_RERANKER / "val_epoch_3.jsonl"),
                "allowed_failed_gates": sorted(ALLOWED_FAILED), "raw_counts": stats["raw_counts"], "selected_counts": stats["selected"],
                "formal_gate_results": stats["quality_gates"], "formal_passed_preserved_false": True, "test_json_parsed": False,
                "seal_sha256": sha(DERIVED / "test_file_seal.json"), "split_manifest_sha256": sha(DERIVED / "split_manifest.json"),
                **{s + "_sha256": sha(DERIVED / f"pruner_{s}.jsonl") for s in ("train", "val", "test")}}
    output = args.output_dir / "root_exploratory_decision.json"
    write_json(output, decision)
    print(json.dumps({"decision": str(output), "sha256": sha(output), "contract_sha256": sha(snapshot)}))
