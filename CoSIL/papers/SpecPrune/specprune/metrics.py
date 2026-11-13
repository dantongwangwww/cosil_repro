"""Binary pruner metrics and validation-only calibration. No test-opening API.

True means relevant and p_yes is P(relevant), never confidence in an arbitrary
verdict. This module has no model dependency and never opens a test implicitly.
"""
from collections import Counter
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import os

SOURCES = ("A", "B", "C", "D", "e_log", "e_bm25", "e_anchor")
E_FAMILIES = ("e_log", "e_bm25", "e_anchor")


def _now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(_canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _probability(value, name="p_yes"):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a finite number in [0, 1]")
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a finite number in [0, 1]")
    return value


def _sources(row):
    result = set()
    label_source = row.get("label_source")
    if label_source:
        if not isinstance(label_source, str):
            raise ValueError("label_source must be a string")
        result.add(label_source)
    sources = row.get("label_sources", [])
    if not isinstance(sources, (list, tuple)) or any(not isinstance(source, str) for source in sources):
        raise ValueError("label_sources must be a list of source strings")
    result.update(sources)
    provenance = row.get("provenance", [])
    if isinstance(provenance, dict):
        provenance = [provenance]
    if not isinstance(provenance, (list, tuple)):
        raise ValueError("provenance must be a list of evidence records")
    for evidence in provenance:
        source = evidence.get("source") if isinstance(evidence, dict) else evidence
        if source:
            if not isinstance(source, str):
                raise ValueError("provenance source must be a string")
            result.add(source)
    return result


def _pair(row):
    if any(not isinstance(row.get(key), str) or not row[key] for key in ("instance_id", "function_id")):
        raise ValueError("Rows require nonempty instance_id and function_id strings")
    return row["instance_id"], row["function_id"]


def deduplicate_predictions(rows):
    """Merge identical repeated predictions; reject conflicting pair predictions.

    Evidence is unioned, so a pair can belong to several E families, once in each.
    This never averages or selects the most favorable duplicate model answer.
    """
    found = {}
    for supplied in rows:
        row = dict(supplied)
        pair = _pair(row)
        if type(row.get("label")) is not bool:
            raise ValueError("label must be a bool: True means relevant")
        row["p_yes"] = _probability(row.get("p_yes"))
        row_sources = _sources(row)
        if row["label"] and (row_sources & set(E_FAMILIES) or "E" in row_sources):
            raise ValueError("An E-family sample must be negative; resolve source/label conflicts upstream")
        if pair not in found:
            row["label_sources"] = sorted(row_sources)
            row["provenance"] = list(row.get("provenance", [])) if not isinstance(row.get("provenance"), dict) else [row["provenance"]]
            found[pair] = row
            continue
        previous = found[pair]
        compared = ("label", "p_yes", "split", "logit_yes", "logit_no", "logit_difference",
                    "p_yes_uncalibrated", "temperature", "uncalibrated_logit_yes",
                    "uncalibrated_logit_no", "uncalibrated_logit_difference")
        if any(previous.get(key) != row.get(key) for key in compared):
            raise ValueError(f"Conflicting duplicate prediction for {pair}")
        previous["label_sources"] = sorted(_sources(previous) | row_sources)
        evidence = row.get("provenance", [])
        if isinstance(evidence, dict):
            evidence = [evidence]
        keys = {_canonical(item) for item in previous["provenance"]}
        for item in evidence:
            if _canonical(item) not in keys:
                previous["provenance"].append(item)
                keys.add(_canonical(item))
    return [found[key] for key in sorted(found)]


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def roc_auc(rows):
    """Mann-Whitney ROC AUC, awarding tied positive/negative scores one half."""
    scores = sorted((row["p_yes"], row["label"]) for row in rows)
    positives = sum(label for _, label in scores)
    negatives = len(scores) - positives
    if not positives or not negatives:
        return None
    positive_rank_sum = 0.0
    index = 0
    while index < len(scores):
        end = index + 1
        while end < len(scores) and scores[end][0] == scores[index][0]:
            end += 1
        mean_rank = ((index + 1) + end) / 2
        positive_rank_sum += mean_rank * sum(label for _, label in scores[index:end])
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _binary(rows, threshold):
    counts = Counter()
    for row in rows:
        yes = row["p_yes"] >= threshold
        counts["TP" if row["label"] and yes else "FN" if row["label"] else "FP" if yes else "TN"] += 1
    tp, fn, fp, tn = (counts[key] for key in ("TP", "FN", "FP", "TN"))
    return {"pairs": len(rows), "positives": tp + fn, "negatives": tn + fp,
            "confusion": {key: counts[key] for key in ("TP", "FN", "FP", "TN")},
            "accuracy": _ratio(tp + tn, len(rows)), "auc": roc_auc(rows),
            "retain_precision": _ratio(tp, tp + fp), "retain_recall": _ratio(tp, tp + fn),
            "reject_precision": _ratio(tn, tn + fn), "negative_rejection_rate": _ratio(tn, tn + fp),
            "predicted_yes": tp + fp, "predicted_no": tn + fn,
            "all_rejected": bool(rows) and not tp and not fp}


def evaluate_predictions(rows, *, threshold=0.5):
    """Return distinct-pair metrics, A/B/C/D/E groups, and three E-family rates.

    Undefined metrics are None (NA). E_correct_rejection_rate is TN/(TN+FP),
    not rejection precision TN/(TN+FN). Groups overlap when evidence does.
    Gold retention recall uses mechanical A/B gold-positive provenance only.
    """
    threshold = _probability(threshold, "threshold")
    supplied = list(rows)
    unique = deduplicate_predictions(supplied)
    overall = _binary(unique, threshold)
    groups = {}
    for source in (*SOURCES, "E"):
        members = [row for row in unique if source in _sources(row)
                   or source == "E" and bool(_sources(row) & set(E_FAMILIES))]
        group = _binary(members, threshold)
        if source in (*E_FAMILIES, "E"):
            group["correct_rejection_rate"] = group["negative_rejection_rate"]
            group["precision_is_not_the_E_target"] = True
        groups[source] = group
    gold = [row for row in unique if row["label"] and _sources(row) & {"A", "B"}]
    gold_kept = sum(row["p_yes"] >= threshold for row in gold)
    overall["gold_retention_recall"] = _ratio(gold_kept, len(gold))
    overall["gold_positive_pairs"] = len(gold)
    overall["gold_retained_pairs"] = gold_kept
    # Full qualification needs relevant and irrelevant examples; all-no is
    # explicitly barred even if an E-only table displays perfect rejection.
    gates = {"accuracy_at_least_0_80": overall["accuracy"] is not None and overall["accuracy"] >= 0.8,
             "auc_at_least_0_85": overall["auc"] is not None and overall["auc"] >= 0.85,
             "E_rejection_at_least_0_85": groups["E"]["correct_rejection_rate"] is not None
                 and groups["E"]["correct_rejection_rate"] >= 0.85,
             "not_all_rejected": bool(unique) and not overall["all_rejected"],
             "gold_recall_positive_when_gold_present": bool(gold) and gold_kept > 0}
    return {"p_yes_definition": "P(relevant)", "yes_if": "p_yes >= threshold", "threshold": threshold,
            "input_rows": len(supplied), "distinct_pairs": len(unique),
            "duplicate_rows_merged": len(supplied) - len(unique), "overall": overall,
            "groups": groups, "E_correct_rejection_rate": groups["E"]["correct_rejection_rate"],
            "qualification_checks": gates, "qualification_pass": all(gates.values()),
            "group_note": "Multi-source groups overlap; each issue/function pair contributes once per group."}


def _sigmoid(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1 + exp)


def _logit(row):
    if "logit_difference" in row:
        value = float(row["logit_difference"])
    elif "logit_yes" in row and "logit_no" in row:
        value = float(row["logit_yes"]) - float(row["logit_no"])
    else:
        p = min(1 - 1e-12, max(1e-12, row["p_yes"]))
        value = math.log(p) - math.log1p(-p)
    if not math.isfinite(value):
        raise ValueError("Binary logit difference must be finite")
    if any(key in row for key in ("logit_difference", "logit_yes", "logit_no")) and abs(_sigmoid(value) - row["p_yes"]) > 1e-6:
        raise ValueError("Raw logits and uncalibrated p_yes disagree")
    return value


def calibrated_probability(p_yes, temperature, *, logit_difference=None):
    """Calibrate an inference score without requiring or accepting a gold label."""
    p_yes = _probability(p_yes)
    if isinstance(temperature, bool) or not math.isfinite(float(temperature)) or float(temperature) <= 0:
        raise ValueError("Temperature must be finite and positive")
    row = {"p_yes": p_yes}
    if logit_difference is not None:
        row["logit_difference"] = logit_difference
    return _sigmoid(_logit(row) / float(temperature))


def hybrid_route(p_yes, *, low=0.6, high=0.9):
    """Return 'retain', 'reject', or 'qwen' with the frozen endpoint convention."""
    p_yes, low, high = (_probability(value, name) for value, name
                        in ((p_yes, "p_yes"), (low, "low"), (high, "high")))
    if low >= high:
        raise ValueError("Hybrid thresholds require low < high")
    return "retain" if p_yes >= high else "reject" if p_yes <= low else "qwen"


def _nll(logits, labels, temperature):
    losses = []
    for logit, label in zip(logits, labels):
        value = logit / temperature
        # Stable softplus(z) - y*z, expressed without cancellation for y=1.
        signed = -value if label else value
        losses.append(max(signed, 0) + math.log1p(math.exp(-abs(signed))))
    return sum(losses) / len(losses) if losses else None


def reliability_diagram(rows, *, bins=10):
    """Fixed equal-width P(yes) bins and expected calibration error, no plotting dependency."""
    if isinstance(bins, bool) or not isinstance(bins, int) or bins < 1:
        raise ValueError("bins must be a positive integer")
    unique = deduplicate_predictions(rows)
    groups = [[] for _ in range(bins)]
    edges = [index / bins for index in range(bins + 1)]
    for row in unique:
        groups[min(bins - 1, bisect_right(edges, row["p_yes"]) - 1)].append(row)
    result, ece = [], 0.0
    for index, values in enumerate(groups):
        mean_p = sum(row["p_yes"] for row in values) / len(values) if values else None
        observed = sum(row["label"] for row in values) / len(values) if values else None
        gap = abs(mean_p - observed) if values else None
        if values:
            ece += len(values) * gap
        result.append({"lower": index / bins, "upper": (index + 1) / bins,
                       "upper_inclusive": index == bins - 1, "count": len(values),
                       "mean_p_yes": mean_p, "observed_relevant_fraction": observed, "absolute_gap": gap})
    return {"pairs": len(unique), "bins": result, "ece": ece / len(unique) if unique else None}


def apply_temperature(rows, temperature):
    """Apply a frozen T to uncalibrated probabilities/logits without fitting."""
    if isinstance(temperature, bool) or not math.isfinite(float(temperature)) or float(temperature) <= 0:
        raise ValueError("Temperature must be finite and positive")
    result = []
    for row in deduplicate_predictions(rows):
        if "temperature" in row or "p_yes_uncalibrated" in row:
            raise ValueError("Temperature must be applied to uncalibrated rows only")
        calibrated = dict(row)
        calibrated["p_yes_uncalibrated"] = row["p_yes"]
        calibrated["p_yes"] = _sigmoid(_logit(row) / float(temperature))
        # These are now calibrated rows; keep original logits as audit evidence
        # without letting a second application mistake them for current logits.
        for key in ("logit_difference", "logit_yes", "logit_no"):
            if key in calibrated:
                calibrated["uncalibrated_" + key] = calibrated.pop(key)
        calibrated["temperature"] = float(temperature)
        result.append(calibrated)
    return result


def fit_temperature(rows, *, split="val", bins=10, temperature_bounds=(0.01, 100.0)):
    """Fit one T minimizing binary NLL; accepts only rows explicitly split='val'."""
    if split != "val":
        raise ValueError("Calibration may be fitted on validation only")
    unique = deduplicate_predictions(rows)
    if not unique or any(row.get("split") != "val" for row in unique):
        raise ValueError("Every calibration row must explicitly have split='val'")
    low, high = map(float, temperature_bounds)
    if not all(math.isfinite(t) and t > 0 for t in (low, high)) or not low <= 1 <= high or low >= high:
        raise ValueError("Temperature bounds must be positive and contain T=1")
    logits, labels = [_logit(row) for row in unique], [row["label"] for row in unique]
    left, right = math.log(low), math.log(high)
    ratio = (math.sqrt(5) - 1) / 2
    first, second = right - ratio * (right - left), left + ratio * (right - left)
    first_loss, second_loss = _nll(logits, labels, math.exp(first)), _nll(logits, labels, math.exp(second))
    for _ in range(96):
        if first_loss <= second_loss:
            right, second, second_loss = second, first, first_loss
            first = right - ratio * (right - left)
            first_loss = _nll(logits, labels, math.exp(first))
        else:
            left, first, first_loss = first, second, second_loss
            second = left + ratio * (right - left)
            second_loss = _nll(logits, labels, math.exp(second))
    candidates = [(temperature, _nll(logits, labels, temperature))
                  for temperature in (1.0, low, high, math.exp((left + right) / 2))]
    temperature, best_loss = min(candidates, key=lambda item: item[1])
    before = _nll(logits, labels, 1.0)
    if abs(before - best_loss) < 1e-12:
        temperature, best_loss = 1.0, before
    fitted_on = [{key: row[key] for key in ("instance_id", "function_id", "label", "p_yes", "label_sources", "split")}
                 | {"logit_difference": logit} for row, logit in zip(unique, logits)]
    calibrated = apply_temperature(unique, temperature)
    return {"schema_version": 1, "split": "val", "pairs": len(unique), "temperature": temperature,
            "temperature_bounds": [low, high], "nll_before": before, "nll_after": best_loss,
            "val_predictions_sha256": _digest(fitted_on),
            "clipped_boundary_probabilities": sum(row["p_yes"] in (0.0, 1.0) and not any(
                key in row for key in ("logit_difference", "logit_yes", "logit_no")) for row in unique),
            "reliability_before": reliability_diagram(unique, bins=bins),
            "reliability_after": reliability_diagram(calibrated, bins=bins)}

