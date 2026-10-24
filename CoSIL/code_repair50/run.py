"""Injected, resumable single-candidate orchestration; no API client at import.

Root supplies pristine preparation, budget/provider construction and the pinned
official evaluator. This module never chooses tasks, fixes model output, starts
a container itself, or sends test feedback to a model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
import time

from .editing import EditProtocolError, apply_edits, parse_edits, plan_edits
from .input_rules import SHARED_SYSTEM_PROMPT
from .prepare import durable, json_bytes, load


OUTPUT_LIMIT = 32768
CONTEXT_LIMIT = 1_000_000


class BudgetStop(RuntimeError):
    pass


def persist(path, value):
    durable(Path(path), json_bytes(value))


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def generation_attempt_summary(provider_out):
    """Aggregate persisted attempts; SENT without receipt retains unknown cost.

    A contract-invalid HTTP response can still have authoritative usage/cost.
    Partial known totals stay separate from all-attempt totals. No provider is
    invoked and no model content is interpreted by this read-only projection.
    """
    folder = Path(provider_out) / "calls" / "repair"
    attempts = {}
    for path in folder.glob("attempt_*_*.json"):
        match = re.fullmatch(r"attempt_(\d+)_(sent|receipt)\.json", path.name)
        if match:
            attempts.setdefault(int(match[1]), {})[match[2]] = path
    known_cost, unknown_cost = 0.0, 0
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "cache_hit_tokens": 0}
    known_token_counts = {key: 0 for key in tokens}
    durations, receipts = [], []
    returned_model = None
    valid_number = lambda value: type(value) in (int, float) and value >= 0 and math.isfinite(value)
    for number, paths in sorted(attempts.items()):
        receipt = load(paths["receipt"]) if "receipt" in paths else {}
        if "receipt" in paths:
            receipts.append(str(paths["receipt"]))
        charge = receipt.get("usage_cost") or {}
        cost = receipt.get("cost_usd")
        if not valid_number(cost):
            cost = charge.get("cost_usd")
        if valid_number(cost):
            known_cost += cost
        else:
            unknown_cost += 1
        usage = charge
        response_path = folder / f"attempt_{number}_response.json"
        if response_path.exists():
            response = load(response_path)
            raw_usage = response.get("usage") if isinstance(response, dict) else None
            if isinstance(raw_usage, dict):
                usage = {**raw_usage, **charge}
        cache = usage.get("cache_hit_tokens", usage.get("prompt_cache_hit_tokens"))
        if cache is None:
            cache = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        projected = {"prompt_tokens": usage.get("prompt_tokens"),
                     "completion_tokens": usage.get("completion_tokens"), "cache_hit_tokens": cache}
        for key, value in projected.items():
            if type(value) is int and value >= 0:
                tokens[key] += value
                known_token_counts[key] += 1
        if valid_number(receipt.get("duration_seconds")):
            durations.append(receipt["duration_seconds"])
        returned_model = receipt.get("returned_model", returned_model)
    count = len(attempts)
    if not count:
        unknown_cost = 1  # Exceptional path without receipts is never assumed free.
    return {"cost_usd": known_cost if count and not unknown_cost else None,
            "known_generation_cost_usd": known_cost,
            "unknown_generation_cost_attempts": unknown_cost,
            "generation_attempt_count": count,
            "usage": {key: total if count and known_token_counts[key] == count else None
                      for key, total in tokens.items()},
            "known_generation_usage": tokens,
            "generation_usage_known_attempt_counts": known_token_counts,
            "generation_seconds": sum(durations) if count and len(durations) == count else None,
            "returned_model": returned_model, "attempt_receipt_paths": receipts,
            "unknown_transport_fee_not_zero": unknown_cost > 0}


def validate_roster(roster):
    if not isinstance(roster, dict) or roster.get("frozen") is not True:
        raise ValueError("Officially qualified frozen roster required before any model callback")
    tasks = roster.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 50:
        raise ValueError("Exactly 50 qualified tasks required")
    for key in ("instance_id", "repo", "base_commit"):
        if any(not isinstance(task.get(key), str) or not task[key] for task in tasks):
            raise ValueError("Missing qualified task identity")
    if len({task["instance_id"] for task in tasks}) != 50 or len({task["repo"] for task in tasks}) != 50:
        raise ValueError("Qualified tasks and repositories must be distinct")
    if any("qualification_passed" in task and task["qualification_passed"] is not True for task in tasks):
        raise ValueError("Nonqualified task in frozen roster")
    return tasks


def arm_order(task):
    value = hashlib.sha256(("repair50-arms\0" + "20261024\0" + task["instance_id"]).encode()).digest()
    return ("A", "B") if value[0] % 2 == 0 else ("B", "A")


def validate_pair(pair):
    if not isinstance(pair, dict) or set(("A", "B", "diagnostics")) - set(pair):
        raise ValueError("Complete prepared A/B pair required")
    payloads = {}
    for arm in ("A", "B"):
        messages = pair[arm]["messages"]
        if (len(messages) != 2 or messages[0] != {"role": "system", "content": SHARED_SYSTEM_PROMPT}
                or messages[1].get("role") != "user"):
            raise ValueError("Repair arms must use the exact shared two-message template")
        payloads[arm] = json.loads(messages[1]["content"])
        if set(payloads[arm]) != {"issue", "source_context", "location_suggestions"}:
            raise ValueError("Unapproved model input field")
    if payloads["A"]["issue"] != payloads["B"]["issue"]:
        raise ValueError("Arms must receive the same original issue")
    diag = pair["diagnostics"]
    if (diag.get("B_all_target_definitions_visible") is not True
            or diag.get("gold_patch_or_modified_lines_in_model_input") is not False
            or diag.get("context_truncated_by_repair_preparation") is not False):
        raise ValueError("Prepared context isolation/completeness guard failed")


def prepare_inputs(roster, output, prepare_case, prompt_upper, budget_prompt_upper):
    """Prepare all 50 locations first; freeze one adequate common input cap.

    prepare_case(task, case_dir) may invoke the approved locator through the
    shared budget. It returns {base_root, pair_inputs, context_audit?, ...} and
    must itself persist/resume its individual upstream stages without replay.
    """
    tasks = validate_roster(roster)
    output = Path(output)
    prepared, survey = [], []
    for task in tasks:
        folder = output / "cases" / task["instance_id"]
        path = folder / "prepared.json"
        case = load(path) if path.exists() else prepare_case(copy.deepcopy(task), folder)
        if not isinstance(case, dict) or not Path(case["base_root"]).is_dir():
            raise ValueError("Pristine base root is unavailable")
        validate_pair(case["pair_inputs"])
        persist(path, case)
        counts = {}
        for arm in ("A", "B"):
            messages = case["pair_inputs"][arm]["messages"]
            context, financial = prompt_upper(messages), budget_prompt_upper(messages)
            if type(context) is not int or type(financial) is not int or not 0 < context <= financial:
                raise ValueError("Conservative positive prompt token bounds required")
            if context + OUTPUT_LIMIT > CONTEXT_LIMIT:
                persist(folder / "context_overflow.json", {"arm": arm, "prompt_upper": context,
                    "output_limit": OUTPUT_LIMIT, "model_context_limit": CONTEXT_LIMIT,
                    "context_dropped": False})
                raise ValueError("CONTEXT_OVERFLOW: no source was silently truncated")
            counts[arm] = {"prompt_upper": context, "budget_prompt_upper": financial,
                           "messages_sha256": digest(messages)}
        survey.append({"instance_id": task["instance_id"], **counts})
        prepared.append((task, case))
    frozen = {"roster_sha256": digest(roster), "tasks": survey, "task_count": 50,
              "input_limit": max(row[arm]["prompt_upper"] for row in survey for arm in ("A", "B")),
              "output_limit": OUTPUT_LIMIT, "model_context_limit": CONTEXT_LIMIT,
              "thinking": {"type": "disabled"}, "temperature": 0,
              "candidates_per_task_arm": 1, "sample_order": "frozen qualified roster order",
              "arm_order": "SHA256('repair50-arms\\0'+'20261024'+'\\0'+iid), first-byte parity",
              "no_context_truncation": True, "first_smoke_tasks": [task["instance_id"] for task in tasks[:3]]}
    persist(output / "repair_input_freeze.json", frozen)
    return prepared, frozen


def generate_arm(task, case, arm, folder, provider, evaluate):
    """One normal candidate response; normal format/test failures never retry."""
    folder = Path(folder)
    record_path = folder / "arm_record.json"
    if record_path.exists():
        record = load(record_path)
        if record["instance_id"] != task["instance_id"] or record["arm"] != arm:
            raise ValueError("Persisted candidate identity mismatch")
        return record
    started = folder / "generation_started.json"
    # A prior active segment can have completed generation/export/evaluation
    # without sealing arm_record. Its wall clock cannot be reconstructed from
    # this process's monotonic clock, even when its candidate is safely reused.
    resuming = any(path.exists() for path in (started,
        folder / "candidate_response.json", folder / "edit_artifacts",
        folder / "evaluation_record.json", folder / "evaluation"))
    messages = case["pair_inputs"][arm]["messages"]
    request_key = {"messages_sha256": digest(messages), "max_tokens": OUTPUT_LIMIT, "temperature": 0}
    # Provider owns transport resume and its original response receipt. Reusing
    # a started marker is safe only via that same persisted provider stage.
    persist(started, request_key)
    before = time.perf_counter()
    record = {"instance_id": task["instance_id"], "arm": arm, "status": "GENERATION_STARTED",
        "resolved": None, "patch_generated": False, "parse_ok": None, "apply_ok": None,
        "test_completed": False, "official_verdict": False, "environment_error": False,
        "error_type": None, "usage": {}, "cost_usd": None, "generation_seconds": None,
        "test_seconds": None, "end_to_end_seconds": None, "paths": {}}
    try:
        response_path = folder / "candidate_response.json"
        response = (load(response_path) if response_path.exists() else
                    provider.ask(messages, "repair", max_tokens=OUTPUT_LIMIT, json_mode=True, temperature=0))
    except Exception:
        # Do not seal an ambiguous failure as free or issue a second semantic
        # request. Root must reconcile the provider's durable ledger/response.
        persist(folder / "generation_interrupted.json", {"request": request_key,
            "status": "PROVIDER_INTERRUPTED_RECONCILE_BEFORE_RESUME", "fee_unknown_not_zero": True})
        raise
    persist(folder / "candidate_response.json", response)
    receipt = response.get("receipt") or {}
    generation_seconds = receipt.get("generation_seconds")
    if generation_seconds is None and not resuming:
        generation_seconds = time.perf_counter() - before
    record.update(patch_generated=True, usage=response.get("usage") or {},
        cost_usd=receipt.get("cost_usd"), generation_seconds=generation_seconds,
        request_model="deepseek-flash", returned_model=receipt.get("returned_model"),
        paths={"response": str(folder / "candidate_response.json"),
               "request": str(folder / "provider/calls/repair/request.json")},
        known_generation_cost_usd=receipt.get("known_attempt_cost_usd"),
        unknown_generation_cost_attempts=receipt.get("unknown_cost_attempts",0))
    if list((folder / "provider/calls/repair").glob("attempt_*_sent.json")):
        record.update(generation_attempt_summary(folder / "provider"))
    usage = record["usage"]
    if "cache_hit_tokens" not in usage and "prompt_cache_hit_tokens" in usage:
        record["usage"] = {**usage, "cache_hit_tokens": usage["prompt_cache_hit_tokens"]}
    if receipt.get("finish_reason", response.get("finish_reason")) == "length":
        record.update(status="OUTPUT_TRUNCATED", parse_ok=False, error_type="OUTPUT_TRUNCATED")
    else:
        try:
            edits = parse_edits(response.get("content"))
            record["parse_ok"] = True
        except EditProtocolError as exc:
            record.update(status="PARSE_FAILED", parse_ok=False, error_type=type(exc).__name__)
        if record["parse_ok"]:
            try:
                export_root = folder / "edit_artifacts"
                if export_root.exists():
                    manifest = load(export_root / "manifest.json")
                    plan = plan_edits(case["base_root"], edits)
                    patch_file = export_root / "patch.diff"
                    if (manifest["patch_sha256"] != plan["patch_sha256"]
                            or hashlib.sha256(patch_file.read_bytes()).hexdigest() != plan["patch_sha256"]):
                        raise ValueError("Persisted patch differs from the one frozen candidate")
                    export = {**manifest, "patch_path": str(patch_file)}
                else:
                    export = apply_edits(case["base_root"], edits, export_root)
                record["deterministic_apply_ok"] = True
                record["paths"]["patch"] = export["patch_path"]
            except (EditProtocolError, OSError) as exc:
                record.update(status="APPLY_FAILED", apply_ok=False, deterministic_apply_ok=False,
                              error_type=type(exc).__name__)
            else:
                evaluated = evaluate(task["instance_id"], arm, export["patch_path"],
                                     task=task, output_dir=folder / "evaluation")
                allowed = {key: evaluated[key] for key in ("status", "resolved", "test_completed",
                    "official_verdict", "environment_error", "error_type", "test_seconds", "apply_ok") if key in evaluated}
                record.update(allowed)
                if "apply_ok" not in evaluated and evaluated.get("patch_applied") is not None:
                    record["apply_ok"] = evaluated["patch_applied"]
                if record["official_verdict"] and record["apply_ok"] is None:
                    raise ValueError("Official evaluator must explicitly report patch application")
                record["paths"].update(evaluated.get("paths") or evaluated.get("logpaths") or {})
                persist(folder / "evaluation_record.json", evaluated)
    active_seconds = time.perf_counter() - before
    record["localization_seconds"] = case.get("localization_seconds")
    if resuming:
        record["end_to_end_seconds"] = None
        record["resume_active_seconds"] = active_seconds
        record["timing_scope"] = ("resumed arm: original complete wall time unavailable; "
            "end_to_end_seconds unknown; resume_active_seconds covers only this active "
            "generation-reuse/export/test segment, excluding localization and queue wait; "
            "known generation/test/localization durations retained separately")
    else:
        record["end_to_end_seconds"] = active_seconds + (case.get("localization_seconds") or 0)
        record["timing_scope"] = "arm active generation/export/test seconds plus recorded localization seconds; queue wait excluded"
    persist(record_path, record)
    return record


def run_pairs(roster, output, prepared, frozen, *, reserve_pair, provider_factory, evaluate,
              budget_exceptions=(BudgetStop,), terminal_provider_exceptions=(), finish_pair=None):
    """Root calls this explicitly; callbacks own all paid/network/container work."""
    tasks = validate_roster(roster)
    if frozen.get("roster_sha256") != digest(roster) or len(prepared) != 50:
        raise ValueError("All 50 prepared inputs and the same roster must already be frozen")
    if [task["instance_id"] for task, _ in prepared] != [task["instance_id"] for task in tasks]:
        raise ValueError("Prepared task order differs from frozen sample")
    by_id = {row["instance_id"]: row for row in frozen["tasks"]}
    output, records = Path(output), []
    for number, (task, case) in enumerate(prepared):
        survey = by_id[task["instance_id"]]
        for arm in ("A", "B"):
            if survey[arm]["messages_sha256"] != digest(case["pair_inputs"][arm]["messages"]):
                raise ValueError("Prepared message changed after offline freeze")
        folder = output / "cases" / task["instance_id"]
        paths = {arm: folder / arm / "arm_record.json" for arm in ("A", "B")}
        if all(path.exists() for path in paths.values()):
            pair_records = [load(paths[arm]) for arm in arm_order(task)]
        else:
            reservation_path = folder / "pair_reservation.json"
            if reservation_path.exists():
                reservations = load(reservation_path)
            else:
                try:
                    reservations = reserve_pair(task["instance_id"], survey["A"]["budget_prompt_upper"],
                                                survey["B"]["budget_prompt_upper"], OUTPUT_LIMIT)
                except budget_exceptions:
                    persist(output / "budget_stop.json", {"status": "BUDGET_STOP_BEFORE_NEW_PAIR",
                        "next_instance_id": task["instance_id"], "completed_pair_n": number})
                    return {"status": "BUDGET_STOP", "records": records}
                persist(reservation_path, reservations)
            pair_records = []
            for arm in arm_order(task):
                provider = provider_factory(task, arm, folder / arm / "provider", reservations[arm])
                try:
                    arm_record = generate_arm(task, case, arm, folder / arm, provider, evaluate)
                except budget_exceptions + terminal_provider_exceptions as exc:
                    # A may have exhausted retry funds after an ambiguously
                    # billed transport attempt. Preserve B's first reservation.
                    arm_record = {"instance_id": task["instance_id"], "arm": arm,
                        "status": "GENERATION_RETRY_BUDGET_EXHAUSTED" if isinstance(exc,budget_exceptions) else "GENERATION_PROVIDER_TERMINAL_FAILURE", "resolved": None,
                        "patch_generated": False, "parse_ok": None, "apply_ok": None,
                        "test_completed": False, "official_verdict": False,
                        "environment_error": False, "error_type": type(exc).__name__,
                        "usage": {}, "cost_usd": None, "generation_seconds": None,
                        "test_seconds": None, "end_to_end_seconds": None,
                        "paths": {"provider_receipts": str(folder / arm / "provider"),
                                  "request": str(folder / arm / "provider/calls/repair/request.json")},
                        "unknown_transport_fee_not_zero": True}
                    arm_record.update(generation_attempt_summary(folder / arm / "provider"))
                    persist(folder / arm / "arm_record.json", arm_record)
                pair_records.append(arm_record)
            if finish_pair is not None:
                finish_pair(task["instance_id"], reservations)
        records.extend(pair_records)
        if number == 2:
            smoke = records[:]
            normal = lambda row: row.get("official_verdict") is True or row.get("parse_ok") is False or row.get("apply_ok") is False
            passed = (len(smoke) == 6 and all(not row.get("environment_error") and normal(row) for row in smoke)
                      and any(row.get("official_verdict") is True for row in smoke))
            persist(output / "smoke_gate.json", {"passed": passed, "records_n": len(smoke),
                "selection_or_prompt_changed_from_smoke_results": False})
            if not passed:
                return {"status": "SMOKE_ENGINEERING_BLOCKED", "records": records}
    return {"status": "COMPLETE", "records": records}
