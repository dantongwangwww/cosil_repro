"""Select/calibrate the v5 judge on val only, optionally open test once explicitly.

Default execution never loads a model or test labels. No API/provider is used.
Formal and exploratory tracks remain distinct; an unqualified model is never
published as the official winner. Source/test/model/data hashes remain frozen.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v5.metrics import (E_FAMILIES, apply_temperature, deduplicate_predictions, evaluate_predictions, fit_temperature,
                            freeze_test_contract, hybrid_route, load_saved_test_predictions,
                            run_test_once, _sources)
from code_v5.run_pipeline import load_winner, sha256, write_new


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_val(path):
    path = Path(path)
    if not re.fullmatch(r"(?:pruner_val|val_epoch_\d+)\.jsonl", path.name):
        raise PermissionError("Race accepts explicit val prediction/data filenames only")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or any(row.get("split") != "val" for row in rows):
        raise PermissionError("Every race/calibration row must explicitly be split='val'")
    return rows


def qualified(metrics):
    accuracy, auc = metrics["overall"]["accuracy"], metrics["overall"]["auc"]
    return accuracy is not None and accuracy >= .8 and auc is not None and auc >= .85


def choose_candidate(candidates):
    """Predeclared val race: E rate; <2 percentage points favors reranker."""
    eligible = {kind: candidate for kind, candidate in candidates.items()
                if qualified(candidate["metrics"]) and candidate["metrics"]["E_correct_rejection_rate"] is not None}
    if not eligible:
        return None, {"status": "unqualified", "primary_failed": True,
                      "reason": "Neither base satisfies val accuracy>=.80, AUC>=.85 and an evaluable E group"}
    if len(eligible) == 1:
        selected = next(iter(eligible))
        return selected, {"status": "qualified_winner", "primary_failed": False,
                          "reason": "Only one base meets the validation qualification"}
    a = eligible["reranker"]["metrics"]["E_correct_rejection_rate"]
    b = eligible["instruct"]["metrics"]["E_correct_rejection_rate"]
    tied = abs(a - b) < .02 - 1e-12
    selected = "reranker" if tied or a >= b else "instruct"
    return selected, {"status": "qualified_winner", "primary_failed": False,
                      "reason": "Difference <2pp: predeclared reranker tie-break" if tied else "Higher val E correct-rejection rate",
                      "val_E_difference_reranker_minus_instruct": a - b, "tie": tied,
                      "comparison_tolerance": "1e-12 at the exact 2pp boundary"}


def load_candidate(run_dir, kind, *, data_seal_sha, val_truth, track):
    run_dir = Path(run_dir).resolve()
    summary_path, manifest_path = run_dir / "training_summary.json", run_dir / "training_manifest.json"
    summary, manifest = read_json(summary_path), read_json(manifest_path)
    if summary["kind"] != kind or manifest["kind"] != kind or manifest.get("track", "formal") != track:
        raise ValueError("Model kind/track differs from its trained manifest")
    if manifest["data"]["seal_sha256"] != data_seal_sha:
        raise ValueError("Models must have trained on the exact same frozen data seal")
    peak_epoch = summary.get("selected_peak_epoch")
    best = ((run_dir / f"epoch_{int(peak_epoch)}").resolve() if peak_epoch is not None else Path(summary["best"]).resolve())
    if not best.is_relative_to(run_dir):
        raise ValueError("Best adapter must belong to this isolated training run")
    complete = read_json(best / "checkpoint_complete.json")
    if complete["manifest_sha256"] != sha256(manifest_path):
        raise ValueError("Best checkpoint belongs to a different training manifest")
    for key, filename in (("adapter_sha256", "adapter_model.safetensors"),
                          ("judge_metadata_sha256", "judge_metadata.json"),
                          ("training_state_sha256", "training_state.pt")):
        if sha256(best / filename) != complete[key]:
            raise ValueError(f"Frozen checkpoint changed: {filename}")
    metadata = read_json(best / "judge_metadata.json")
    if metadata["kind"] != kind or metadata["model"]["sha256"] != manifest["model"]["sha256"]:
        raise ValueError("Adapter/base model provenance mismatch")
    if metadata["training_manifest_sha256"] != sha256(manifest_path):
        raise ValueError("Adapter metadata training hash differs")
    epoch = int(complete["epoch"])
    prediction_path = run_dir / f"val_epoch_{epoch}.jsonl"
    predictions = read_val(prediction_path)
    pairs = [(row["instance_id"], row["function_id"]) for row in predictions]
    if len(set(pairs)) != len(pairs) or set(pairs) != set(val_truth):
        raise ValueError("Every distinct frozen validation pair must have one prediction")
    for row in predictions:
        original = val_truth[(row["instance_id"], row["function_id"])]
        if row["label"] != original["label"] or _sources(row) != _sources(original):
            raise ValueError("Val prediction labels/sources differ from the mechanical sealed data")
        if "temperature" in row or "p_yes_uncalibrated" in row:
            raise ValueError("Race/calibration require the saved uncalibrated epoch scores")
    metrics = evaluate_predictions(predictions)
    return {"kind": kind, "run_dir": str(run_dir), "best_epoch": epoch,
            "adapter_dir": str(best), "model_dir": metadata["model"]["path"],
            "base_model_sha256": metadata["model"]["sha256"], "model_files": metadata["model"]["files"],
            "training_manifest_path": str(manifest_path), "training_manifest_sha256": sha256(manifest_path),
            "training_summary_sha256": sha256(summary_path), "val_prediction_path": str(prediction_path),
            "val_prediction_file_sha256": sha256(prediction_path), "metrics": metrics,
            "qualified": qualified(metrics), "predictions": predictions}


def routing_risks(rows, *, low, high):
    counts = {route: {"pairs": 0, "positive": 0, "negative": 0, "gold_positive": 0}
              for route in ("retain", "reject", "qwen")}
    e_counts = {family: {route: 0 for route in counts} for family in E_FAMILIES}
    e_union = {route: 0 for route in counts}
    for row in rows:
        route = hybrid_route(row["p_yes"], low=low, high=high)
        counts[route]["pairs"] += 1
        counts[route]["positive" if row["label"] else "negative"] += 1
        sources = _sources(row)
        counts[route]["gold_positive"] += bool(row["label"] and sources & {"A", "B"})
        if sources & (set(E_FAMILIES) | {"E"}):
            e_union[route] += 1
        for family in E_FAMILIES:
            if family in sources:
                e_counts[family][route] += 1
    gold_count = sum(group["gold_positive"] for group in counts.values())

    def e_summary(group):
        total = sum(group.values())
        return {"pairs": total, "routes": group,
                "direct_correct_rejection_rate": group["reject"] / total if total else None,
                "direct_false_retention_rate": group["retain"] / total if total else None,
                "gray_fraction": group["qwen"] / total if total else None}

    return {"split": "val", "low": low, "high": high, "routes": counts,
            "pairs": len(rows), "gold_positive_pairs": gold_count,
            "E": e_summary(e_union), "E_families": {family: e_summary(group) for family, group in e_counts.items()},
            "gray_fraction": counts["qwen"]["pairs"] / len(rows) if rows else None,
            "gold_direct_rejection_fraction": counts["reject"]["gold_positive"] / gold_count if gold_count else None,
            "positive_direct_rejection_fraction": counts["reject"]["positive"] / sum(row["label"] for row in rows)
                if any(row["label"] for row in rows) else None,
            "interpretation": "Val-only routing risk; Qwen's gray-zone final verdict is not assumed correct"}


def select_thresholds(rows, *, policy="fixed", low=.6, high=.9):
    """Freeze hybrid thresholds on calibrated validation scores alone.

    A/B gold must never be directly rejected; at most 5% of distinct E pairs
    may be directly retained. Gray-zone Qwen correctness is not estimated.
    E>=.85 direct rejection and <=.20 gray coverage are report-only targets.
    """
    if policy not in ("fixed", "val_safety"):
        raise ValueError("Unknown threshold policy")
    supplied = list(rows)
    if any(row.get("split") != "val" for row in supplied):
        raise PermissionError("Threshold selection accepts explicitly val-only scores")
    unique = deduplicate_predictions(supplied)
    hybrid_route(.5, low=low, high=high)
    nominal = {"low": .6, "high": .9}
    grid = {"low": [step / 100 for step in range(0, 61, 5)],
            "high": [step / 100 for step in range(90, 101)]}
    report = {"schema_version": 1, "policy": policy, "split": "val", "pairs": len(unique),
              "supplied_rows": len(supplied), "test_used": False,
              "nominal_defaults": nominal, "grid": grid if policy == "val_safety" else None,
              "hard_constraints": {"gold_A_B_direct_rejected_count_max": 0,
                                   "E_direct_false_retention_rate_max": .05},
              "report_only_targets": {"E_direct_correct_rejection_rate_min": .85,
                                      "gray_fraction_max": .2},
              "selection_order": ["minimum gray pair fraction", "maximum E direct correct rejection rate",
                                  "minimum Manhattan distance to (.6,.9)", "larger low, then smaller high"],
              "fallback_to_fixed": False,
              "interpretation": "Direct decisions only; no assumption about Qwen gray-zone correctness"}

    def candidate(candidate_low, candidate_high):
        risks = routing_risks(unique, low=candidate_low, high=candidate_high)
        gold_count = risks["gold_positive_pairs"]
        e_count = risks["E"]["pairs"]
        checks = {"gold_evaluable": gold_count > 0, "E_evaluable": e_count > 0,
                  "gold_direct_rejection_zero": gold_count > 0 and risks["routes"]["reject"]["gold_positive"] == 0,
                  # Exact count comparison includes the 5% endpoint without float-rounding ambiguity.
                  "E_direct_false_retention_le_0_05": e_count > 0 and risks["E"]["routes"]["retain"] * 20 <= e_count}
        e_rate, gray = risks["E"]["direct_correct_rejection_rate"], risks["gray_fraction"]
        return {**risks, "hard_constraint_results": checks, "feasible": all(checks.values()),
                "report_only_target_results": {"E_direct_correct_rejection_ge_0_85": e_rate is not None and e_rate >= .85,
                                               "gray_fraction_le_0_20": gray is not None and gray <= .2}}

    candidates = ([candidate(low, high)] if policy == "fixed" else
                  [candidate(candidate_low, candidate_high) for candidate_low in grid["low"] for candidate_high in grid["high"]])
    report["candidates"] = candidates
    report["feasible_candidate_count"] = sum(entry["feasible"] for entry in candidates)
    if policy == "fixed":
        chosen = candidates[0]
        report.update(status="fixed", passed=True, reason="Explicit fixed thresholds; safety constraints reported only")
    else:
        feasible = [entry for entry in candidates if entry["feasible"]]
        if not feasible:
            failures = []
            if not candidates[0]["hard_constraint_results"]["gold_evaluable"]:
                failures.append("missing A/B gold on validation")
            if not candidates[0]["hard_constraint_results"]["E_evaluable"]:
                failures.append("missing E on validation")
            if not failures:
                failures.append("no feasible grid pair")
            report.update(status="threshold_policy_failed", passed=False, selected=None,
                          failures=failures, reason="; ".join(failures))
            return report
        # Counts suffice because all candidates share the same populations.
        chosen = min(feasible, key=lambda entry: (
            entry["routes"]["qwen"]["pairs"], -entry["E"]["routes"]["reject"],
            round(abs(entry["low"] - .6) + abs(entry["high"] - .9), 12),
            -entry["low"], entry["high"]))
        report.update(status="val_safety_selected", passed=True,
                      reason="Predeclared val-only safety constraints and coverage order")
    report["selected"] = chosen
    return report


def plot_reliability(calibration, path):
    os.environ.setdefault("MPLCONFIGDIR", str(Path(path).resolve().parent / ".matplotlib-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure, ax = plt.subplots(figsize=(5.5, 4.5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Ideal")
    for key, label in (("reliability_before", "Before"), ("reliability_after", "After val temperature")):
        bins = [row for row in calibration[key]["bins"] if row["count"]]
        ax.plot([row["mean_p_yes"] for row in bins], [row["observed_relevant_fraction"] for row in bins],
                marker="o", label=f"{label} (ECE={calibration[key]['ece']:.3f})")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean P(relevant)", ylabel="Observed relevant fraction",
           title="Validation reliability; test not used")
    ax.legend(loc="upper left", fontsize=8)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _artifact(path):
    return {"path": str(Path(path).resolve()), "sha256": sha256(path)}


def construct_winner(candidate, *, calibration, calibration_path, data_seal_path,
                     protocol_snapshot_path, track, low, high, root_decision_path=None,
                     threshold_selection_path=None, threshold_policy="fixed"):
    """Construct the exact schema consumed by run_pipeline.load_winner."""
    adapter = Path(candidate["adapter_dir"])
    model_config = Path(candidate["model_dir"]) / "config.json"
    if sha256(model_config) != candidate["model_files"].get("config.json"):
        raise ValueError("Base model config changed after training")
    artifacts = {"adapter_weights": _artifact(adapter / "adapter_model.safetensors"),
                 "adapter_metadata": _artifact(adapter / "judge_metadata.json"),
                 "training_manifest": _artifact(candidate["training_manifest_path"]),
                 "data_seal": _artifact(data_seal_path), "calibration": _artifact(calibration_path),
                 "val_predictions": _artifact(candidate["val_prediction_path"]),
                 "root_protocol": _artifact(protocol_snapshot_path)}
    artifacts["base_model_config"] = _artifact(model_config)
    if root_decision_path is not None:
        artifacts["root_exploratory_decision"] = _artifact(root_decision_path)
    if threshold_selection_path is not None:
        artifacts["threshold_selection"] = _artifact(threshold_selection_path)
    return {"schema_version": 1, "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "adapter_dir": str(adapter), "model_dir": candidate["model_dir"], "kind": candidate["kind"],
            "base_model_sha256": candidate["base_model_sha256"], "base_model_files": candidate["model_files"],
            "temperature": calibration["temperature"], "low": low, "high": high, "track": track,
            "threshold_policy": threshold_policy,
            "calibration": calibration, "artifacts": artifacts, "selected_on": "val only",
            "qualified_on_val": True, "classification_threshold": .5,
            "e_goal_met_on_val": candidate["metrics"]["E_correct_rejection_rate"] >= .85,
            "test_used_for_selection": False,
            "class_policy": "Retain original Qwen for all class requests; local judge trained on functions"}


def candidate_report(candidate):
    result = {key: value for key, value in candidate.items() if key != "predictions"}
    families = [candidate["metrics"]["groups"][source]["correct_rejection_rate"]
                for source in ("e_log", "e_bm25", "e_anchor")]
    result["E_three_family_macro"] = sum(families) / 3 if all(value is not None for value in families) else None
    result["E_three_family_values"] = dict(zip(("e_log", "e_bm25", "e_anchor"), families))
    return result


def _validate_track(data_dir, track, decision_path, protocol_sha, data_policy="original"):
    if data_policy == "runtime-covered-v3":
        if track != "exploratory" or decision_path is None:
            raise RuntimeError("Runtime coverage requires the explicit exploratory authorization")
        from code_v5.runtime_filtered_policy import validate_decision
        validate_decision(data_dir, decision_path)
        if read_json(decision_path)["execution_contract_sha256"] != protocol_sha:
            raise RuntimeError("Race must use the same frozen runtime-covered contract")
        return
    if data_policy != "original":
        raise ValueError("Unknown explicit data policy")
    statistics_path = Path(data_dir) / "statistics.json"
    statistics = read_json(statistics_path)
    gates = statistics.get("quality_gates", {})
    if statistics.get("mechanical_labels_only") is not True:
        raise ValueError("Mechanical labels required")
    if track == "formal":
        if statistics.get("passed") is not True or not gates or any(value is not True for value in gates.values()):
            raise RuntimeError("Formal data quality gate failed")
        return
    if track != "exploratory" or decision_path is None:
        raise RuntimeError("Exploratory track requires root's explicit bounded decision file")
    decision = read_json(decision_path)
    allowed = {"positive_unique_pairs_ge_8000", "E_unique_pairs_ge_3000"}
    failed = {key for key, value in gates.items() if value is not True}
    if not failed or not failed <= allowed:
        raise RuntimeError("Only the two formal quantity minima may fail in the exploratory track")
    if (decision.get("track") != "exploratory" or decision.get("statistics_sha256") != sha256(statistics_path)
            or decision.get("execution_contract_sha256") != protocol_sha):
        raise RuntimeError("Root's exploratory decision is not bound to this exact statistics/protocol")
    if sorted(decision.get("allowed_failed_gates", [])) != sorted(failed):
        raise RuntimeError("Exploratory decision differs from the real failed quantity gates")


def frozen_protocol_path(args):
    """Exploratory race follows the decision's snapshot, never a live status file."""
    requested = getattr(args, "protocol_file", None)
    if args.track == "exploratory":
        if args.root_decision_file is None:
            raise RuntimeError("Exploratory race needs its frozen root decision")
        decision = read_json(args.root_decision_file)
        snapshot = Path(decision["execution_contract_path"]).resolve()
        if sha256(snapshot) != decision["execution_contract_sha256"]:
            raise RuntimeError("Root decision's frozen execution contract changed")
        if requested is not None and Path(requested).resolve() != snapshot:
            raise ValueError("Use the decision-bound protocol snapshot; a dynamic execution contract is not accepted")
        return snapshot
    return Path(requested or ROOT / "results/v5_pruner/execution_contract.json").resolve()


def open_frozen_test(output, *, gpu=2):
    """Explicit second CLI action uses an already frozen winner, never re-races."""
    from code_v5.metrics import verify_test_seal
    output = Path(output).resolve()
    winner_path, contract_path = output / "winner.json", output / "test_contract.json"
    winner, winner_sha = load_winner(winner_path)
    noise_decision = winner.get("artifacts", {}).get("root_exploratory_decision")
    if noise_decision and read_json(noise_decision["path"]).get("test_open_allowed") is False:
        raise PermissionError("This frozen exploratory user authorization keeps test sealed")
    report, contract = read_json(output / "race_report.json"), read_json(contract_path)
    if (report["selection"]["status"] != "qualified_winner" or report["selection"]["primary_failed"]
            or report["winner_sha256"] != winner_sha or not winner.get("qualified_on_val")
            or not qualified(report["candidates"][winner["kind"]]["metrics"])):
        raise RuntimeError("Test requires the frozen, validation-qualified winner")
    config_artifact = contract["artifacts"].get("winner_config")
    if not config_artifact or config_artifact["sha256"] != winner_sha:
        raise RuntimeError("Winner config is not bound to the frozen test contract")
    seal_path = Path(winner["artifacts"]["data_seal"]["path"])
    seal = read_json(seal_path)
    verify_test_seal(seal["test_path"], seal_path)
    test_path = Path(seal["test_path"])
    if test_path.with_name(test_path.name + ".v5_opened_once.json").exists():
        raise RuntimeError("Test opening already consumed; rebuild reports from saved predictions only")
    if gpu != 2:
        raise PermissionError("Test scoring is assigned to single physical GPU 2")
    os.environ["CUDA_VISIBLE_DEVICES"] = "2"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    from code_v5.judge_models import JudgeModel
    # RAW p with T=1. The sealed test interface applies frozen T exactly once.
    load_started = time.perf_counter()
    judge = JudgeModel.from_adapter(winner["adapter_dir"], model_dir=winner["model_dir"], device="cuda:0", temperature=1.0)
    loader_wall_seconds = time.perf_counter() - load_started
    test_output = output / "test_once"
    latency_samples = []

    def predictor(inputs):
        result = []
        # The callback runs only after run_test_once consumes the exclusive opening
        # guard. Sidecars contain no labels/provenance and never enter score rows.
        write_new(test_output / "model_load.json", {
            "model_load_seconds": getattr(judge, "model_load_seconds", None),
            "loader_wall_seconds": loader_wall_seconds, "loaded_at_temperature": 1.0,
            "excluded_from_per_prediction_latency": True, "local_only": True})
        with (test_output / "latency_samples.jsonl").open("x", encoding="utf-8") as stream:
            for row in inputs:
                score = judge.predict(row["issue"], row["function"])
                telemetry = {"instance_id": row["instance_id"], "function_id": row["function_id"],
                             **{key: score.get(key) for key in (
                                 "latency_seconds", "input_tokens", "scored_positions", "generated_output_tokens",
                                 "unique_context_tokens", "forward_calls", "prediction_index", "first_prediction")}}
                latency_samples.append(telemetry)
                stream.write(json.dumps(telemetry, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                result.append({"instance_id": row["instance_id"], "function_id": row["function_id"],
                               "p_yes": score["p_yes_uncalibrated"], "logit_difference": score["logit_difference"]})
        return result
    completion = run_test_once(predictor=predictor, test_path=seal["test_path"], seal_path=seal_path,
                              contract_path=contract_path, state_directory=test_output, explicit_open=True)
    metrics = evaluate_predictions(load_saved_test_predictions(test_output))
    write_new(test_output / "test_metrics.json", {"track": winner["track"], "selection": "frozen on val",
              "completion": completion, "metrics": metrics, "temperature_applied_once": True})
    def latency_summary(samples):
        values = sorted(float(sample["latency_seconds"]) for sample in samples
                        if sample.get("latency_seconds") is not None)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Latency telemetry must be finite and nonnegative")
        def quantile(q):
            position = (len(values) - 1) * q
            left, right = math.floor(position), math.ceil(position)
            return values[left] + (values[right] - values[left]) * (position - left)
        return {"pairs": len(samples), "measured_pairs": len(values),
                "median_seconds": quantile(.5) if values else None,
                "p95_seconds": quantile(.95) if values else None,
                "maximum_seconds": max(values) if values else None,
                "strict_maximum_lt_0_3": len(values) == len(samples) and bool(values) and max(values) < .3}
    latency_path = test_output / "latency_samples.jsonl"
    write_new(test_output / "latency_summary.json", {
        "model_load_seconds": getattr(judge, "model_load_seconds", None), "loader_wall_seconds": loader_wall_seconds,
        "all_predictions": latency_summary(latency_samples),
        "first_prediction": latency_summary([sample for sample in latency_samples if sample.get("first_prediction") is True]),
        "warm_predictions": latency_summary([sample for sample in latency_samples if sample.get("first_prediction") is False]),
        "latency_samples_sha256": sha256(latency_path), "quantile_method": "linear interpolation",
        "interpretation": "Full local predict latency includes tokenization and first call; model load reported separately; no average overrides the strict maximum"})
    return {"test_opened": True, "test_metrics": str(test_output / "test_metrics.json"),
            "winner_sha256": winner_sha, "reraced": False}


def run(args):
    # No model import, GPU use, inference or test loading on the default path.
    output = Path(args.output_dir).resolve()
    if args.open_test_once and (output / "winner.json").exists():
        return open_frozen_test(output, gpu=args.gpu)
    if any(value is None for value in (args.data_dir, args.reranker_run, args.instruct_run)):
        raise ValueError("A new val race needs both --*-run directories and --data-dir")
    data_dir = Path(args.data_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Race output must be a new directory; frozen race/winner/calibration are not overwritten")
    protocol_path = frozen_protocol_path(args)
    protocol_sha = sha256(protocol_path)
    data_policy = getattr(args, "data_policy", "original")
    if data_policy == "runtime-covered-v3" and args.open_test_once:
        raise PermissionError("Runtime-covered exploratory assessment never opens test")
    _validate_track(data_dir, args.track, args.root_decision_file, protocol_sha, data_policy=data_policy)
    hybrid_route(.5, low=args.low, high=args.high)
    seal_path, val_path = data_dir / "test_file_seal.json", data_dir / "pruner_val.jsonl"
    seal = read_json(seal_path)
    val_entry = seal["frozen_files"]["val"]
    if Path(val_entry["path"]).resolve() != val_path or sha256(val_path) != val_entry["sha256"]:
        raise ValueError("Frozen validation data changed")
    val = read_val(val_path)
    truth = {(row["instance_id"], row["function_id"]): row for row in val}
    if len(truth) != len(val) or len(val) != val_entry["count"]:
        raise ValueError("Frozen validation pair count mismatch")
    candidates = {kind: load_candidate(path, kind, data_seal_sha=sha256(seal_path), val_truth=truth, track=args.track)
                  for kind, path in (("reranker", args.reranker_run), ("instruct", args.instruct_run))}
    selected, race = choose_candidate(candidates)
    output.mkdir(parents=True, exist_ok=True)
    snapshot_path = output / "root_protocol_snapshot.json"
    write_new(snapshot_path, read_json(protocol_path))
    report = {"schema_version": 1, "track": args.track, "data_policy": data_policy, "selection": race,
              "selected_kind": selected, "test_used_for_selection": False,
              "protocol_source_path": str(protocol_path), "protocol_source_sha256": protocol_sha,
              "protocol_snapshot_sha256": sha256(snapshot_path),
              "data_seal_sha256": sha256(seal_path), "val_data_sha256": sha256(val_path),
              "candidates": {kind: candidate_report(candidate) for kind, candidate in candidates.items()}}
    if selected is None:
        write_new(output / "race_report.json", report)
        if args.open_test_once:
            raise RuntimeError("No qualified winner: test remains sealed; no model is loaded")
        return report
    chosen = candidates[selected]
    calibration = fit_temperature(chosen["predictions"], split="val")
    calibration.update(selected_kind=selected, val_prediction_file_sha256=chosen["val_prediction_file_sha256"],
                       root_protocol_sha256=sha256(snapshot_path), data_seal_sha256=sha256(seal_path))
    calibration_path = output / "calibration.json"
    write_new(calibration_path, calibration)
    calibrated_val = apply_temperature(chosen["predictions"], calibration["temperature"])
    threshold_policy = getattr(args, "threshold_policy", "fixed")
    threshold_selection = select_thresholds(calibrated_val, policy=threshold_policy, low=args.low, high=args.high)
    threshold_selection.update(val_prediction_file_sha256=chosen["val_prediction_file_sha256"],
                               calibration_sha256=sha256(calibration_path), root_protocol_sha256=sha256(snapshot_path))
    threshold_selection_path = output / "threshold_selection.json"
    write_new(threshold_selection_path, threshold_selection)
    report["threshold_selection"] = {"path": str(threshold_selection_path), "sha256": sha256(threshold_selection_path),
                                     "policy": threshold_policy, "status": threshold_selection["status"],
                                     "passed": threshold_selection["passed"],
                                     "feasible_candidate_count": threshold_selection["feasible_candidate_count"]}
    report["calibrated_val_metrics"] = evaluate_predictions(calibrated_val)
    report["E_target_0_85_met"] = chosen["metrics"]["E_correct_rejection_rate"] >= .85
    plot_reliability(calibration, output / "val_reliability.png")
    report.update(calibration=calibration, test_opened=False)
    if not threshold_selection["passed"]:
        report["selection"] = {**race, "model_selection_status": race["status"],
                               "status": "threshold_policy_failed", "primary_failed": True,
                               "reason": threshold_selection["reason"]}
        report.update(winner_published=False, thresholds_frozen_before_test=False)
        write_new(output / "race_report.json", report)
        if args.open_test_once:
            raise RuntimeError("Validation threshold safety failed: test remains sealed; no model is loaded")
        return report
    selected_thresholds = threshold_selection["selected"]
    low, high = selected_thresholds["low"], selected_thresholds["high"]
    report["routing_risks"] = selected_thresholds
    winner = construct_winner(chosen, calibration=calibration, calibration_path=calibration_path,
                              data_seal_path=seal_path, protocol_snapshot_path=snapshot_path, track=args.track,
                              low=low, high=high, root_decision_path=args.root_decision_file,
                              threshold_selection_path=threshold_selection_path, threshold_policy=threshold_policy)
    winner_path = output / "winner.json"
    write_new(winner_path, winner)
    load_winner(winner_path)
    contract_path = output / "test_contract.json"
    freeze_test_contract(test_path=seal["test_path"], seal_path=seal_path, contract_path=contract_path,
                         winner=selected, calibration=calibration, thresholds={"low": low, "high": high},
                         artifact_paths={**{name: artifact["path"] for name, artifact in winner["artifacts"].items()},
                                         "winner_config": winner_path})
    report.update(winner_file=str(winner_path), winner_sha256=sha256(winner_path), calibration=calibration,
                  test_opened=False, thresholds_frozen_before_test=True, winner_published=True)
    write_new(output / "race_report.json", report)
    if args.open_test_once:
        return {**report, **open_frozen_test(output, gpu=args.gpu)}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reranker-run", type=Path)
    parser.add_argument("--instruct-run", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol-file", type=Path, help="Formal contract or the exact decision-bound exploratory snapshot")
    parser.add_argument("--track", choices=("formal", "exploratory"), default="formal")
    parser.add_argument("--root-decision-file", type=Path)
    parser.add_argument("--data-policy", choices=("original", "runtime-covered-v3"), default="original")
    parser.add_argument("--low", type=float, default=.6)
    parser.add_argument("--high", type=float, default=.9)
    parser.add_argument("--threshold-policy", choices=("fixed", "val_safety"), default="fixed",
                        help="Use explicit fixed thresholds or the predeclared val-only safety grid")
    parser.add_argument("--open-test-once", action="store_true")
    parser.add_argument("--gpu", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
