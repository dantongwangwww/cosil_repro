"""Frozen user prescription atop the unchanged v3 noise-disclosed data gate."""
from pathlib import Path
import json
from code_v5.noise_disclosed_policy import ROOT, DERIVED, validate_decision as validate_original, sha

FILES = ("__init__.py", "policy.py", "freeze_decision.py", "train_judges.py", "race_and_calibrate.py", "run_sequence.py", "report_outcome.py")
ORIGINAL_DECISION = ROOT / "results/v5_pruner/A_v3_noise_disclosed_authorization_v2_exploratory/root_exploratory_decision.json"
ORIGINAL_RERANKER = ROOT / "results/v5_pruner/A_v3_noise_disclosed_training_exploratory/reranker"


def validate_prescription(contract):
    policy = contract.get("A_regularized_exploratory_v3", {})
    expected = {"enabled": True, "rank": 8, "dropout": .1, "alpha": 32, "epochs": 3,
                "learning_rate": 5e-5, "effective_batch_size": 8, "micro_batch_size": 2,
                "cutoff": 4096, "data_dir": str(DERIVED), "test_open_allowed": False, "retain_original_A": True}
    if any(policy.get(k) != v for k, v in expected.items()):
        raise RuntimeError("Exact separately authorized rank8/dropout0.1/alpha32 prescription required")
    if policy.get("checkpoint_selection") != "maximum val accuracy among completed epochs; ties higher AUC, then E rejection, then earlier epoch":
        raise RuntimeError("The new val-accuracy-peak checkpoint rule must be predeclared")
    return policy


def validate_decision(data_dir, decision_file):
    stats, seal, split_ids, provenance = validate_original(data_dir, decision_file)
    decision = json.loads(Path(decision_file).read_text())
    contract = json.loads(Path(decision["execution_contract_path"]).read_text())
    validate_prescription(contract)
    hashes = decision.get("regularized_code_sha256", {})
    if set(hashes) != set(FILES) or any(sha(ROOT / "code_v5_regularized" / name) != value for name, value in hashes.items()):
        raise RuntimeError("Separate regularized code fingerprints changed")
    expected = {"original_A_decision_sha256": sha(ORIGINAL_DECISION),
                "original_reranker_summary_sha256": sha(ORIGINAL_RERANKER / "training_summary.json"),
                "original_reranker_val_accuracy_peak_prediction_sha256": sha(ORIGINAL_RERANKER / "val_epoch_3.jsonl")}
    if any(decision.get(k) != v for k, v in expected.items()):
        raise RuntimeError("The original pre-regularization A experiment changed")
    if decision.get("experiment_condition") != "rank8_dropout0.1_alpha32":
        raise RuntimeError("Do not silently relabel the regularized experiment")
    provenance.update(experiment_condition="rank8_dropout0.1_alpha32", data_policy="noise-disclosed-v3-regularized",
                      original_A_preserved=True, actual_formal_gate_passed=False)
    return stats, seal, split_ids, provenance
