"""Score the frozen winning C adapter once after separate root authorization.

The label-free callback is invoked behind the existing global O_EXCL marker.
Reports may be rebuilt from saved scores; test inference cannot be resumed or
repeated after failure. No selection or temperature fitting occurs here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

from code_v5.metrics import run_test_once, load_saved_test_predictions, evaluate_predictions
from code_v5.report_gold_routes import describe
from code_v5.run_pipeline import write_new, sha256
from code_v5_postexploratory.authority import AUTH, TEST_OUTPUT, metadata, validate_authority


def summarize_latency(samples):
    values = sorted(float(row["latency_seconds"]) for row in samples)
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Measured prediction latency must be finite and nonnegative")
    def quantile(q):
        position = (len(values)-1)*q
        lo, hi = math.floor(position), math.ceil(position)
        return values[lo] + (values[hi]-values[lo])*(position-lo)
    return {"pairs": len(values), "median_seconds": quantile(.5) if values else None,
        "p95_seconds": quantile(.95) if values else None, "maximum_seconds": max(values) if values else None,
        "strict_maximum_lt_0_3": bool(values) and max(values) < .3,
        "quantile_method": "linear interpolation", "shared_GPU_latency_causal_comparison": False}


def execute(authorization, *, assigned_gpu=None):
    auth, winner, auth_sha = validate_authority(authorization, "test")
    seal_path = winner["artifacts"]["data_seal"]["path"]
    seal = metadata(seal_path)
    test_path = Path(seal["test_path"])
    marker = test_path.with_name(test_path.name + ".v5_opened_once.json")
    if marker.exists() or TEST_OUTPUT.exists():
        raise RuntimeError("Test opening/output already exists; report saved predictions without re-inference")
    from code_v5_expanded_resources_v3.run_training_pair import gpu_preflight
    # Observation never stops/changes a process. The same user-authorized
    # resource-only function waits for >=12GiB headroom, not for other jobs to exit.
    preflight = gpu_preflight(wait_for_idle=True, assigned_gpu=assigned_gpu,
        allowed_gpu_ids=auth["allowed_gpu_ids"], minimum_free_mib=auth["minimum_free_mib"])
    os.environ["CUDA_VISIBLE_DEVICES"] = str(preflight["assigned"])
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    samples = []
    load_measurement = {}

    def predictor(inputs):
        # Import/load occurs only after the test-once interface has consumed
        # its global opening marker. Inputs contain IDs, issue, function only.
        from code_v5.judge_models import JudgeModel
        started = time.perf_counter()
        judge = JudgeModel.from_adapter(winner["adapter_dir"], model_dir=winner["model_dir"],
            device="cuda:0", temperature=1.0, cutoff=4096)
        load_measurement.update(loader_wall_seconds=time.perf_counter()-started,
            model_load_seconds=judge.model_load_seconds, loaded_at_temperature=1.0,
            excluded_from_per_prediction_latency=True)
        write_new(TEST_OUTPUT / "execution_metadata.json", {"authorization_sha256": auth_sha,
            "winner_sha256": auth["winner_sha256"], "gpu_preflight": preflight,
            "actual_physical_GPU": preflight["assigned"], "model_load": load_measurement,
            "peer_processes_modified": False, "no_test_reselection": True})
        scores = []
        with (TEST_OUTPUT / "latency_samples.jsonl").open("x", encoding="utf-8") as latency_file, \
             (TEST_OUTPUT / "label_free_input_fingerprints.jsonl").open("x", encoding="utf-8") as fingerprints:
            for row in inputs:
                score = judge.predict(row["issue"], row["function"])
                telemetry = {"instance_id": row["instance_id"], "function_id": row["function_id"],
                    **{key: score.get(key) for key in ("latency_seconds", "input_tokens", "scored_positions",
                        "generated_output_tokens", "unique_context_tokens", "forward_calls", "prediction_index", "first_prediction")}}
                samples.append(telemetry)
                latency_file.write(json.dumps(telemetry, ensure_ascii=False, allow_nan=False) + "\n")
                fingerprints.write(json.dumps({"instance_id": row["instance_id"], "function_id": row["function_id"],
                    "input_sha256": hashlib.sha256(json.dumps([row["issue"], row["function"]], ensure_ascii=False).encode()).hexdigest(),
                    "issue_sha256": hashlib.sha256(row["issue"].encode()).hexdigest(),
                    "source_sha256": hashlib.sha256(row["function"].encode()).hexdigest()}, ensure_ascii=False) + "\n")
                for stream in (latency_file, fingerprints):
                    stream.flush(); os.fsync(stream.fileno())
                scores.append({"instance_id": row["instance_id"], "function_id": row["function_id"],
                    "p_yes": score["p_yes_uncalibrated"], "logit_difference": score["logit_difference"]})
        return scores

    completion = run_test_once(predictor=predictor, test_path=test_path, seal_path=seal_path,
        contract_path=auth["test_contract"], state_directory=TEST_OUTPUT, explicit_open=True)
    saved = load_saved_test_predictions(TEST_OUTPUT)
    raw = []
    for row in saved:
        value = dict(row)
        value["p_yes"] = value.pop("p_yes_uncalibrated")
        value.pop("temperature")
        value["logit_difference"] = value.pop("uncalibrated_logit_difference")
        raw.append(value)
    report = {"stage": "postexploratory_evaluation", "training_track": winner["track"],
        "authorization_sha256": auth_sha, "winner_sha256": auth["winner_sha256"],
        "completion": completion, "metrics": evaluate_predictions(saved),
        "raw_metrics": evaluate_predictions(raw),
        "frozen_calibrated_routes": describe(saved, winner["low"], winner["high"]),
        "raw_nominal_routes_diagnostic_only": describe(raw, .6, .9),
        "frozen_temperature": winner["temperature"], "temperature_applied_once": True,
        "winner_or_thresholds_changed_after_test": False, "Qwen_gray_answers_assumed": False,
        "test_inference_repeated": False, "class_policy": "function pairs only; pipeline classes retain Qwen"}
    write_new(TEST_OUTPUT / "test_metrics.json", report)
    write_new(TEST_OUTPUT / "latency_summary.json", {"model_load": load_measurement,
        "all_predictions": summarize_latency(samples),
        "first_prediction": summarize_latency([r for r in samples if r["first_prediction"]]),
        "warm_predictions": summarize_latency([r for r in samples if not r["first_prediction"]]),
        "latency_samples_sha256": sha256(TEST_OUTPUT / "latency_samples.jsonl")})
    return {"test_opened_once": True, "pairs": len(saved), "metrics_path": str(TEST_OUTPUT / "test_metrics.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--gpu", type=int, choices=(0,1,2,3))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        auth, winner, digest = validate_authority(args.authorization, "check")
        result = {"checked": True, "authorization_sha256": digest, "execute": False,
                  "model_loaded": False, "test_labels_read": False}
    else:
        result = execute(args.authorization, assigned_gpu=args.gpu)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
