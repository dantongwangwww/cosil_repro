"""CPU-only safety regression for the explicitly authorized noise-disclosed track."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from code_v5.noise_disclosed_policy import DERIVED, SOURCE, sha, validate_decision, validate_authorization
from code_v5.train_judges import validate_quality_gate, validate_epoch
from code_v5.race_and_calibrate import _validate_track
from code_v5.run_training_pair import gpu_preflight, _gpu_inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    decision, checks = args.decision.resolve(), []
    d = json.loads(decision.read_text())

    def rejected(name, function):
        try:
            function()
        except (RuntimeError, PermissionError, ValueError) as error:
            checks.append({"check": name, "passed": True, "rejected": True, "reason": str(error)})
            return
        raise AssertionError(name + " unexpectedly accepted")

    rejected("historical_v3_formal_still_rejects", lambda: validate_quality_gate(SOURCE))
    rejected("historical_quantity_only_policy_still_rejects", lambda: validate_quality_gate(SOURCE, track="exploratory", decision_file=decision))
    rejected("derived_formal_still_rejects", lambda: validate_quality_gate(DERIVED))
    rejected("derived_old_quantity_policy_still_rejects", lambda: validate_quality_gate(DERIVED, track="exploratory", decision_file=decision))
    rejected("noise_policy_cannot_run_formal", lambda: validate_quality_gate(DERIVED, track="formal", decision_file=decision, data_policy="noise-disclosed-v3"))
    _, _, _, provenance = validate_quality_gate(DERIVED, track="exploratory", decision_file=decision, data_policy="noise-disclosed-v3")
    checks.append({"check": "exact_new_policy_accepted_without_forging_formal_pass", "passed": provenance["formal_data_gate_passed"] is False})
    _validate_track(DERIVED, "exploratory", decision, d["execution_contract_sha256"], data_policy="noise-disclosed-v3")
    checks.append({"check": "race_binds_exact_explicit_policy", "passed": True})
    rejected("race_old_quantity_gate_still_rejects", lambda: _validate_track(DERIVED, "exploratory", decision, d["execution_contract_sha256"]))
    with tempfile.TemporaryDirectory(prefix="v5-noise-guards-") as tmp:
        for field, value in (("statistics_sha256", "bad"), ("source_review_sha256", "bad"),
                             ("derivation_sha256", "bad"), ("test_open_allowed", True), ("data_policy", "original")):
            altered = copy.deepcopy(d)
            altered[field] = value
            path = Path(tmp) / (field + ".json")
            path.write_text(json.dumps(altered))
            rejected("tampered_decision_" + field, lambda path=path: validate_decision(DERIVED, path))
        altered = copy.deepcopy(d)
        altered["policy_code_sha256"]["train_judges.py"] = "bad"
        path = Path(tmp) / "code.json"
        path.write_text(json.dumps(altered))
        rejected("tampered_training_code", lambda: validate_decision(DERIVED, path))
    contract = json.loads(Path(d["execution_contract_path"]).read_text())
    contract["noise_disclosed_exploratory_v3"]["E_quantity_specific_authorization"]["general_E_quantity_waiver"] = True
    rejected("general_E_waiver_refused", lambda: validate_authorization(contract))
    rejected("test_split_accuracy_refused", lambda: validate_epoch(None, None, "reranker", [{"split": "test"}], "cpu", 4096, split="test"))
    base = {"inventory": {2: {"uuid": "GPU-2", "memory_mib": 19, "utilization": 0},
                          3: {"uuid": "GPU-3", "memory_mib": 19, "utilization": 0}},
            "compute_apps": [], "full_processes": [{"gpu_uuid": "GPU-2", "pid": 123, "type": "C+G", "process_name": "simulator"}]}
    with patch("code_v5.run_training_pair._gpu_inventory", return_value=base):
        rejected("C_plus_G_refused_even_if_missing_from_compute_apps", lambda: gpu_preflight())
    base["full_processes"] = [{"gpu_uuid": "GPU-2", "pid": 124, "type": "G", "process_name": "/usr/lib/xorg/Xorg"}]
    with patch("code_v5.run_training_pair._gpu_inventory", return_value=base):
        assert gpu_preflight()["assigned"] == 2
        checks.append({"check": "only_resident_Xorg_G_ignored", "passed": True})

    def fake_nvidia(command, **kwargs):
        if "-x" in command:
            assert "-d" not in command
            stdout = "<nvidia_smi_log><gpu><uuid>GPU-2</uuid><processes><process_info><pid>123</pid><type>C+G</type><process_name>simulator</process_name><used_memory>42 MiB</used_memory></process_info></processes></gpu></nvidia_smi_log>"
        elif any("query-gpu" in x for x in command):
            stdout = "2, GPU-2, 19, 0\n3, GPU-3, 19, 0\n"
        else:
            stdout = ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    with patch("code_v5.run_training_pair.subprocess.run", side_effect=fake_nvidia):
        inventory = _gpu_inventory()
        assert inventory["full_processes"][0]["type"] == "C+G"
        checks.append({"check": "complete_XML_PIDS_and_valid_NVIDIA_arguments", "passed": True})
    assert "torch" not in sys.modules
    result = {"status": "passed", "checks": checks, "check_count": len(checks), "decision_path": str(decision),
              "decision_sha256": sha(decision), "data_dir": str(DERIVED), "torch_imported": False,
              "model_loaded": False, "test_rows_decoded": False, "source_data_unchanged": True}
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "check_count": len(checks), "sha256": sha(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
