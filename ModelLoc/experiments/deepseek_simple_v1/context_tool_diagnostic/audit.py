"""B0: inspect frozen inference artifacts without dispatch, gold, models, or network.

Only the explicit Lite manifest is traversed. Historical files are never written.
The old audit's 43 repeated-delimiter DSML cases remain diagnostic-only.
"""
import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import tokenize

from .protocol import parse_action, target_resolution, ToolCall, ProtocolError, DSML_REFERENCE

METHODS = ("D-COSIL", "Q-COSIL", "Q-PRUNER")
EXPECTED = {
    "D-COSIL": {"actions": 411, "parse_failures": 81, "executions": 301, "execution_successes": 298},
    "Q-COSIL": {"actions": 400, "parse_failures": 33, "executions": 367, "execution_successes": 233},
    "Q-PRUNER": {"actions": 392, "parse_failures": 34, "executions": 358, "execution_successes": 201},
}


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def guarded(path):
    path = Path(path)
    forbidden = ("holdout", "sealed", "pruner_test", "evaluator_private")
    if any(word in str(path).lower() for word in forbidden):
        raise PermissionError("B0 forbidden data path")
    return path


def read_json(path):
    return json.loads(guarded(path).read_text())


def read_events(path):
    path = guarded(path)
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v
                             for k, v in row.items()})


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def protocol_diagnostic(raw, protocol):
    try:
        call = parse_action(raw, protocol)
        return {"valid": True, "call": call.as_dict(), "category": None, "reason": None}
    except ProtocolError as exc:
        return {"valid": False, "call": None, "category": exc.category, "reason": exc.reason}


def _observed_requests(folder):
    """An HTTP 200 receipt tied to saved request+response proves delivery.

    A response ending in length still proves receipt of its input, although the
    semantic result failed. This distinction is preserved in each evidence row.
    """
    inputs = []
    for call_folder in sorted(folder.glob("calls/*")):
        request_file = call_folder / "request.json"
        if not request_file.exists():
            continue
        saved = read_json(request_file)
        sequence, stage = call_folder.name.split("_", 1)
        for receipt_file in sorted(call_folder.glob("attempt_*_receipt.json")):
            receipt = read_json(receipt_file)
            response_file = receipt_file.with_name(receipt_file.name.replace("_receipt.json", "_response.json"))
            if not response_file.exists():
                continue
            response = read_json(response_file)
            valid = (receipt.get("http_status") == 200
                     and digest(json.dumps(saved["request"], sort_keys=True, ensure_ascii=False)) == saved["sha256"]
                     and receipt.get("request_sha256") == saved["sha256"]
                     and receipt.get("response_sha256") == digest(json.dumps(response, sort_keys=True)))
            if valid:
                inputs.append({"sequence": int(sequence), "stage": stage,
                               "messages": saved["request"]["messages"],
                               "request_artifact": str(request_file), "receipt_artifact": str(receipt_file),
                               "finish_reason": receipt.get("finish_reason"), "request_sha256": saved["sha256"]})
    return inputs


def _decode(raw):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def _source_text(call, io_event, context, requests, job, index):
    """Recover exact returned bytes by recorded SHA, never by target correction."""
    wanted = io_event.get("returned_sha256") if io_event else None
    if not wanted:
        return None, None, False
    for block in context.get("retrieved_blocks", context.get("blocks", [])):
        text = block.get("text")
        if text is not None and digest(text) == wanted:
            return text, "context.json::retrieved_blocks", True
    for request in requests:
        if request["stage"].startswith("pruner"):
            for message in request["messages"]:
                for match in re.finditer(r"<code>\n(.*?)\n</code>", message.get("content", ""), re.S):
                    if digest(match[1]) == wanted:
                        return match[1], request["request_artifact"] + "::<code>", True
    # Getter/setter share an identity; the original dispatcher can return one
    # span while the adapter deliberately declines to choose a unique span.
    path = call.arguments[0]
    if path not in index:
        return None, None, False
    snapshot = Path(job["snapshot"]).resolve()
    source_path = guarded(snapshot / path)
    if not source_path.resolve().is_relative_to(snapshot):
        return None, None, False
    text = _decode(source_path.read_bytes())
    if digest(text) != index[path]["sha256"]:
        raise ValueError("Frozen base source SHA mismatch: " + path)
    qn = ".".join(call.arguments[1:])
    kind = "class" if call.name == "get_code_of_class" else "function"
    for definition in index[path]["definitions"]:
        if definition["kind"] != kind or definition["qualified_name"] != qn:
            continue
        span = "".join(text.splitlines(keepends=True)[definition["start_line"] - 1:definition["end_line"]])
        for candidate in (span, span.rstrip("\r\n"), "\n".join(span.splitlines())):
            if digest(candidate) == wanted:
                return candidate, str(source_path) + "::recorded_SHA_exact_span", True
    return None, None, False


def _target_reason(call, resolution, index):
    reason = resolution["reason"]
    if resolution["target_exists"] or call.name in ("exit", "get_functions_of_class"):
        return reason
    path = call.arguments[0]
    if path not in index:
        aliases = [p for p in index if Path(p).name == Path(path).name]
        return "path_alias_or_wrong_directory" if aliases else "path_not_in_base_index"
    definitions = index[path]["definitions"]
    if call.name == "get_code_of_file_function":
        qn = call.arguments[1]
        if any(d["kind"] == "function" and d["qualified_name"].split(".")[-1] == qn and "." in d["qualified_name"] for d in definitions):
            return "member_or_nested_function_sent_to_top_level_tool"
    if call.name == "get_code_of_class_function":
        class_name, func_name = call.arguments[1:]
        if any(d["kind"] == "function" and d["qualified_name"] == func_name for d in definitions):
            return "top_level_function_sent_to_class_method_tool"
        if not any(d["kind"] == "class" and d["qualified_name"] == class_name for d in definitions):
            return "class_not_in_supplied_file"
        if any(d["kind"] == "function" and d["qualified_name"].split(".")[-1] == func_name for d in definitions):
            return "method_belongs_to_different_class_or_scope"
        return "method_not_in_supplied_class"
    return reason


def _delivery(source, step, action_sequence, next_action_sequence, requests, events):
    output = {"main_judge_seen_full_source": False, "main_judge_seen_partial_source": False,
              "small_judge_seen_function_text": False, "small_judge_seen_full_source": False,
              "small_judge_seen_partial_or_different_source": False, "small_judge_source_relation": None,
              "small_judge_saved_input_hash_valid": None, "agent_seen_full_source": False,
              "agent_seen_partial_source": False, "judge_http_evidence": [], "agent_http_evidence": [],
              "small_judge_evidence": [], "context_accept_event": any(
                  e["event"] == "context_accept" and e.get("step") == step for e in events)}
    if source is None:
        output["delivery_exact_source_unavailable"] = True
        return output
    output["delivery_exact_source_unavailable"] = False
    for request in requests:
        if request["sequence"] <= action_sequence:
            continue
        body = "\n".join(m.get("content", "") for m in request["messages"])
        evidence = {k: request[k] for k in ("request_artifact", "receipt_artifact", "finish_reason", "request_sha256")}
        if request["stage"].startswith("pruner") and request["sequence"] < next_action_sequence and source in body:
            output["main_judge_seen_full_source"] = True
            output["judge_http_evidence"].append(evidence)
        if (request["stage"] in ("node_selection", "final_summary") and output["context_accept_event"]
                and any(m.get("role") == "user" and m.get("content") == source for m in request["messages"])):
            output["agent_seen_full_source"] = True
            output["agent_http_evidence"].append(evidence)
    for event in events:
        if event["event"] != "v6_judge_input" or event.get("step") != step:
            continue
        text = event["model_input"]
        valid = digest(text) == event["input_sha256"]
        match = re.search(r"<function>\n(.*?)\n</function>", text, re.S)
        function = match[1] if match else None
        output["small_judge_saved_input_hash_valid"] = valid
        # Hash validity authenticates saved input, not source completeness.
        output["small_judge_seen_function_text"] = bool(valid and function)
        output["small_judge_seen_full_source"] = bool(valid and function == source)
        output["small_judge_seen_partial_or_different_source"] = bool(valid and function and function != source)
        output["small_judge_source_relation"] = ("exact" if function == source else
            "prefix_truncated" if function and source.startswith(function) else "different_span_or_text")
        output["small_judge_evidence"].append({"event": "v6_judge_input", "step": step,
            "input_sha256": event["input_sha256"], "function_chars": len(function or ""),
            "source_chars": len(source), "function_sha256": digest(function or "")})
    output["judge_seen_any_function_text"] = bool(output["main_judge_seen_full_source"] or output["small_judge_seen_function_text"])
    output["judge_seen_full_source"] = bool(output["main_judge_seen_full_source"] or output["small_judge_seen_full_source"])
    return output


def audit_case(folder, record, method, csv_rows):
    events = read_events(folder / "events.jsonl")
    result = read_json(folder / "result.json")
    job = read_json(record["job"])
    index = read_json(job["code_index"])
    context = read_json(folder / "context.json") if (folder / "context.json").exists() else {}
    file_end = next((e for e in events if e["event"] == "file_stage_end"), None)
    files = file_end["found_files"][:5] if file_end else []
    requests = _observed_requests(folder)
    actions = []
    for call_folder in sorted(folder.glob("calls/*_node_selection")):
        if (call_folder / "result.json").exists():
            actions.append((call_folder, read_json(call_folder / "result.json")["content"]))
    tool_events = {e["step"]: e for e in events if e["event"] == "tool_call"}
    result_events = {e["step"]: e for e in events if e["event"] == "tool_result"}
    error_events = {e["step"]: e for e in events if e["event"] == "tool_error"}
    parse_events = {e["step"]: e for e in events if e["event"] == "parse_error"}
    io_events = [e for e in events if e["event"] == "tool_io_audit"]
    ordered_tools = [e for e in events if e["event"] == "tool_call"]
    if len(ordered_tools) != len(io_events):
        raise ValueError("tool_call/tool_io count drift: " + str(folder))
    io_by_step = {}
    for tool, io_event in zip(ordered_tools, io_events):
        if tool["tool"] != io_event["tool"] or tool["arguments"] != io_event["arguments"]:
            raise ValueError("tool_call/tool_io binding drift: " + str(folder))
        io_by_step[tool["step"]] = io_event
    rows, dsml_rows, seen, error_seen, seen_source = [], [], set(), set(), set()
    source_before = 0
    for ordinal, (call_folder, raw) in enumerate(actions, 1):
        saved = csv_rows[(method, record["instance_id"], ordinal)]
        if saved["raw_model_output"] != raw or Path(saved["raw_artifact_path"]).resolve() != call_folder.resolve():
            raise ValueError("Frozen CSV/action raw mismatch")
        step = ordinal - 1
        sequence = int(call_folder.name.split("_", 1)[0])
        next_sequence = int(actions[ordinal][0].name.split("_", 1)[0]) if ordinal < len(actions) else 10**9
        parsed = saved["parsed"] == "True"
        if (step in parse_events) == parsed:
            raise ValueError("CSV and parse_error event disagree")
        row = {"method": method, "instance_id": record["instance_id"], "repo": record["repo"],
               "step": step, "node_request_number": ordinal, "raw_model_output": raw,
               "raw_output_sha256": digest(raw), "raw_artifact_path": str(call_folder / "result.json"),
               "events_artifact": str(folder / "events.jsonl"), "historical_parsed": parsed,
               "historical_parse_error": saved.get("error_message"), "executed": step in tool_events,
               "execution_success": step in result_events, "source_returned": bool(
                   step in result_events and result_events[step].get("kind") == "source"),
               "gold_direct_prune_available": False, "gold_direct_prune": None,
               "strict_dsl": protocol_diagnostic(raw, "dsl"),
               "strict_dsml": protocol_diagnostic(raw, "dsml") if "DSML" in raw else None,
               "historical_legacy_43_diagnostic": saved.get("dsml_structure_and_signature_valid") == "True",
               "legacy_report_judge_received_source": saved.get("judge_received_source") == "True",
               "legacy_report_agent_received_source": saved.get("search_agent_received_source") == "True",
               "native_tool_call": False, "semantic_retry_limit": 0}
        if "DSML" in raw:
            markers = re.findall(r"<(/?)(｜+DSML｜+)\s*(calls|invoke|parameter)", raw)
            old_target = None
            if row["historical_legacy_43_diagnostic"]:
                diagnostic_call = ToolCall(saved["dsml_tool"], tuple(json.loads(saved["dsml_arguments"])),
                                           saved["dsml_original_tool"], "saved_legacy_diagnostic_not_accepted")
                old_target = target_resolution(diagnostic_call, index, files)
            dsml_rows.append({"method": method, "instance_id": record["instance_id"], "step": step,
                "raw_artifact_path": row["raw_artifact_path"], "raw_output_sha256": digest(raw),
                "raw_model_output": raw, "markers": sorted(set(marker[1] for marker in markers)),
                "marker_codepoints": {m: [f"U+{ord(c):04X}" for c in m] for m in sorted(set(x[1] for x in markers))},
                "strict_canonical_accepted": row["strict_dsml"]["valid"],
                "strict_error": row["strict_dsml"]["reason"],
                "legacy_structure_signature_diagnostic": row["historical_legacy_43_diagnostic"],
                "legacy_offline_target_diagnostic": saved.get("dsml_offline_base_target_valid") == "True",
                "legacy_diagnostic_static_target_rechecked": old_target,
                "historical_executed": row["executed"], "official_reference": DSML_REFERENCE,
                "canonical_normalization_or_repair_applied": False})
        if not parsed:
            if saved.get("error_message") in ("Too many tool arguments", "Missing required tool argument", "Unknown or duplicated keyword argument"):
                row.update(category="schema_failure", reason="argument_count_or_field_mismatch")
            else:
                row.update(category="response_parse_failure", reason="noncanonical_or_malformed_dsml" if "DSML" in raw else "free_text_or_unselected_dsl")
        else:
            name = saved["canonical_tool"]
            arguments = tuple(json.loads(saved["arguments"] or "[]"))
            call = ToolCall(name, arguments, saved["original_tool"], "historical_legacy_dsl")
            resolution = target_resolution(call, index, files)
            row.update(canonical_tool=name, original_tool=call.original_name, arguments=list(arguments),
                       target_resolution=resolution, target_exists=resolution["target_exists"],
                       repeated_same_arguments=(name, arguments) in seen,
                       repeated_previous_error_arguments=(name, arguments) in error_seen)
            seen.add((name, arguments))
            if name == "exit":
                row.update(category="explicit_exit", reason="exit_before_source" if not source_before else "exit_after_source", source_reads_before_exit=source_before)
            elif step not in tool_events:
                row.update(category="missing_execution_evidence", reason="parsed_call_without_tool_call_event")
            else:
                actual = tool_events[step]
                if actual["tool"] != name or actual["arguments"] != list(arguments):
                    raise ValueError("Action/tool execution binding mismatch")
                io_event = io_by_step[step]
                row.update(tool_error=error_events.get(step, {}).get("error"),
                           returned_sha256=io_event.get("returned_sha256"), returned_chars=io_event.get("returned_chars"),
                           returned_head=io_event.get("returned_head", io_event.get("returned_error_text")),
                           tool_elapsed_seconds=io_event.get("wall_seconds"))
                if step in error_events:
                    row.update(category="target_failure" if not resolution["target_exists"] else "tool_runtime_failure",
                               reason=_target_reason(call, resolution, index))
                    error_seen.add((name, arguments))
                elif row["source_returned"]:
                    source, artifact, source_sha_valid = _source_text(call, io_event, context, requests, job, index)
                    row.update(category="executed_source_success", reason="source_returned",
                               source_text_available=source is not None, source_sha_valid=source_sha_valid,
                               source_evidence_artifact=artifact, repeated_source=io_event.get("returned_sha256") in seen_source)
                    seen_source.add(io_event.get("returned_sha256"))
                    row.update(_delivery(source, step, sequence, next_sequence, requests, events))
                    prune = next((e for e in events if e["event"] == "prune" and e.get("step") == step), None)
                    row["actual_relevance_decision"] = prune.get("decision") if prune else None
                    row["actual_reject"] = bool(prune and prune.get("decision") == "False")
                    row["not_delivered_to_agent_reason"] = (None if row["agent_seen_full_source"] else
                        "actual_relevance_reject" if row["actual_reject"] else
                        "no_later_effective_request_after_context_accept" if row["context_accept_event"] else
                        "not_inserted_into_context_or_judge_failure")
                    source_before += 1
                else:
                    row.update(category="executed_metadata_success", reason="node_catalog_is_not_source")
        rows.append(row)
    if len(rows) != len(actions) or sum(not r["historical_parsed"] for r in rows) != len(parse_events):
        raise ValueError("Action denominator mismatch")
    small = [e for e in events if e["event"] == "small_judge"]
    native_count = 0
    for response_file in folder.glob("calls/*/attempt_*_response.json"):
        response = read_json(response_file)
        native_count += sum(len(c.get("message", {}).get("tool_calls") or []) for c in response.get("choices", []))
    info = {"method": method, "instance_id": record["instance_id"], "repo": record["repo"],
            "status": result["status"], "error_type": result.get("error_type"), "error_message": result.get("error_message"),
            "file_stage_completed": bool(file_end), "frozen_files": files,
            "entered_search": any(e["event"] == "search_start" for e in events),
            "entered_navigation": bool(actions), "completed": result["status"] == "complete",
            "actions": len(rows), "parse_failures": len(parse_events), "executions": len(tool_events),
            "execution_successes": len(result_events), "tool_errors": len(error_events),
            "source_returned": sum(r["source_returned"] for r in rows),
            "agent_seen_full_source_count": sum(r.get("agent_seen_full_source", False) for r in rows),
            "judge_seen_full_source_count": sum(r.get("judge_seen_full_source", False) for r in rows),
            "actual_reject_count": sum(r.get("actual_reject", False) for r in rows),
            "round_limit_reached_without_exit": len(actions) == 10 and not any(r["category"] == "explicit_exit" for r in rows),
            "small_judge_calls": len(small), "small_judge_input_char_crop_candidates": sum(e["original_code_chars"] > 8192 for e in small),
            "small_judge_reported_token_trim": sum(e["token_budget_trimmed"] for e in small),
            "native_tool_calls": native_count,
            "final_None_or_missing_identity_slots": sum(not p.get("path") or not p.get("qualified_name") for p in result.get("predicted_functions", [])),
            "gold_evaluation_available": False}
    return rows, dsml_rows, info


def audit(historical_run, manifest_path, tool_csv, output):
    historical_run, output = Path(historical_run).resolve(), Path(output).resolve()
    if output.is_relative_to(historical_run) or output == historical_run:
        raise PermissionError("Output must be outside frozen historical run")
    if output.exists() and any(output.iterdir()):
        provenance_file = output / "audit_manifest.json"
        summary_file = output / "summary.json"
        required = ("tool_failure_taxonomy.csv", "tool_protocol_per_call.csv", "dsml_offline_parser.csv",
                    "per_issue_audit.csv", "matrix.md")
        if provenance_file.exists() and summary_file.exists() and all((output / p).exists() for p in required):
            provenance = read_json(provenance_file)
            existing = read_json(summary_file)
            if (provenance.get("manifest_sha256") == digest(guarded(manifest_path).read_bytes())
                    and provenance.get("tool_csv_sha256") == digest(guarded(tool_csv).read_bytes())
                    and provenance.get("historical_run") == str(historical_run)
                    and existing.get("schema_version") == 1):
                return existing
        raise FileExistsError("Audit output is nonempty or incomplete; preserve existing artifacts")
    manifest = read_json(manifest_path)
    if manifest.get("cohort") != "lite_pilot" or len(manifest["records"]) != 50:
        raise ValueError("B0 requires the original Lite pilot 50")
    with guarded(tool_csv).open() as stream:
        original_rows = list(csv.DictReader(stream))
    lookup = {(r["method"], r["instance_id"], int(r["node_request_number"])): r for r in original_rows if r["method"] in METHODS}
    if len(lookup) != 1203:
        raise ValueError("Unexpected historical per-call CSV denominator")
    rows, dsml, issues = [], [], []
    for method in METHODS:
        for record in manifest["records"]:
            action_rows, dsml_rows, issue = audit_case(historical_run / "lite_pilot" / method / record["instance_id"], record, method, lookup)
            rows.extend(action_rows); dsml.extend(dsml_rows); issues.append(issue)
    summary = {"schema_version": 1, "audit_only": True, "historical_run": str(historical_run),
               "n_allocated_per_method": 50, "gold_read": False, "gold_direct_prune_available": False,
               "historical_outputs_executed": False, "api_requests": 0, "gpu_used": False,
               "dsml_reference": DSML_REFERENCE, "methods": {}}
    fields = ("actions", "parse_failures", "executions", "execution_successes", "tool_errors", "source_returned",
              "small_judge_calls", "small_judge_input_char_crop_candidates", "small_judge_reported_token_trim", "native_tool_calls")
    delivery_fields = ("main_judge_seen_full_source", "small_judge_seen_function_text", "small_judge_seen_full_source",
                       "small_judge_seen_partial_or_different_source", "judge_seen_full_source", "agent_seen_full_source")
    for method in METHODS:
        rs = [r for r in rows if r["method"] == method]; xs = [i for i in issues if i["method"] == method]
        counts = {field: sum(x[field] for x in xs) for field in fields}
        counts.update({field: sum(bool(r.get(field)) for r in rs) for field in delivery_fields})
        counts["main_small_full_source_overlap"] = sum(bool(r.get("main_judge_seen_full_source") and r.get("small_judge_seen_full_source")) for r in rs)
        counts["judge_full_source_union_verified"] = (counts["judge_seen_full_source"] ==
            counts["main_judge_seen_full_source"] + counts["small_judge_seen_full_source"] - counts["main_small_full_source_overlap"])
        if not counts["judge_full_source_union_verified"]:
            raise ValueError("Full source judge union mismatch")
        counts.update({"file_stage_completed": sum(x["file_stage_completed"] for x in xs),
                       "entered_search": sum(x["entered_search"] for x in xs),
                       "entered_navigation": sum(x["entered_navigation"] for x in xs),
                       "complete": sum(x["completed"] for x in xs),
                       "strict_dsl_valid": sum(r["strict_dsl"]["valid"] for r in rs),
                       "strict_dsml_valid": sum(bool(r["strict_dsml"] and r["strict_dsml"]["valid"]) for r in rs),
                       "repeated_arguments": sum(r.get("repeated_same_arguments", False) for r in rs),
                       "repeated_previous_error_arguments": sum(r.get("repeated_previous_error_arguments", False) for r in rs),
                       "repeated_source": sum(r.get("repeated_source", False) for r in rs),
                       "categories": dict(collections.Counter(r["category"] for r in rs)),
                       "reasons": dict(collections.Counter(r["reason"] for r in rs)),
                       "legacy_report_judge_received_source": sum(r["legacy_report_judge_received_source"] for r in rs),
                       "legacy_report_agent_received_source": sum(r["legacy_report_agent_received_source"] for r in rs),
                       "judge_seen_any_function_text": sum(r.get("judge_seen_any_function_text", False) for r in rs),
                       "delivery_count_differences": [{"instance_id": r["instance_id"], "step": r["step"],
                           "source_artifact": r.get("source_evidence_artifact"),
                           "legacy_judge": r["legacy_report_judge_received_source"],
                           "judge_seen_any_function_text": r.get("judge_seen_any_function_text", False),
                           "judge_seen_full_source": r.get("judge_seen_full_source", False),
                           "small_judge_source_relation": r.get("small_judge_source_relation"),
                           "legacy_agent": r["legacy_report_agent_received_source"],
                           "agent_seen_full_source": r.get("agent_seen_full_source", False)} for r in rs
                           if (r["legacy_report_judge_received_source"] != r.get("judge_seen_full_source", False)
                               or r["legacy_report_agent_received_source"] != r.get("agent_seen_full_source", False))],
                       "pre_navigation_failures": [{k: x[k] for k in ("instance_id", "error_type", "error_message", "file_stage_completed", "entered_search")} for x in xs if not x["entered_navigation"]]})
        for field, expected in EXPECTED[method].items():
            if counts[field] != expected:
                raise ValueError(f"Historical count mismatch {method}/{field}: {counts[field]} != {expected}")
        summary["methods"][method] = counts
    summary["dsml"] = {"all_candidates": len(dsml), "strict_canonical_accepted": sum(r["strict_canonical_accepted"] for r in dsml),
        "legacy_structure_signature_diagnostic": sum(r["legacy_structure_signature_diagnostic"] for r in dsml),
        "legacy_offline_target_diagnostic": sum(r["legacy_offline_target_diagnostic"] for r in dsml),
        "repaired_or_executed": 0}
    if summary["dsml"] != {"all_candidates": 68, "strict_canonical_accepted": 0,
                           "legacy_structure_signature_diagnostic": 43, "legacy_offline_target_diagnostic": 43, "repaired_or_executed": 0}:
        raise ValueError("DSML denominator drift")
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "tool_failure_taxonomy.csv", rows)
    write_csv(output / "tool_protocol_per_call.csv", rows)
    write_csv(output / "dsml_offline_parser.csv", dsml)
    write_csv(output / "per_issue_audit.csv", issues)
    write_json(output / "summary.json", summary)
    write_json(output / "audit_manifest.json", {"manifest_path": str(Path(manifest_path).resolve()),
        "manifest_sha256": digest(Path(manifest_path).read_bytes()), "tool_csv": str(Path(tool_csv).resolve()),
        "tool_csv_sha256": digest(Path(tool_csv).read_bytes()), "historical_run": str(historical_run),
        "issue_ids": [r["instance_id"] for r in manifest["records"]], "output": str(output),
        "read_scope": "Lite pilot manifest, clean jobs/base indexes, frozen action/context/request/receipt/response artifacts; source fallback only for recorded returned SHA",
        "no_gold_or_holdout_or_sealed_test": True})
    text = ["# B0 历史工具零 API 审计", "", "历史输出只解析、不重新执行；旧 run 和 reports 未写入。", "",
            "| 方法 | 动作 | 原解析失败 | 执行 | 成功/源码返回 | 主裁判完整源码 | 小裁判函数文本/完整源码 | 任一裁判完整源码(并集) | Agent完整源码 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for method in METHODS:
        s = summary["methods"][method]
        text.append(f'| {method} | {s["actions"]} | {s["parse_failures"]} | {s["executions"]} | {s["execution_successes"]} | {s["main_judge_seen_full_source"]} | {s["small_judge_seen_function_text"]}/{s["small_judge_seen_full_source"]} | {s["judge_seen_full_source"]} | {s["agent_seen_full_source"]} |')
    q = summary["methods"]["Q-PRUNER"]
    text += ["", "68 段 DSML 中，43 段只在旧审计将重复竖线归一化后结构/签名完整；严格 canonical 格式接受 0/68。未修复分隔符、未执行历史候选、未追认定位收益。",
             "", "与旧报告的送达计数差异：D 主裁判 296→298、Q 主裁判 231→233、Q Agent 105→107，来自按已记录返回 SHA 恢复 getter/setter 同限定名多 span 的真实返回文本；旧审计缺少唯一 retrieved_block 就未能核验。新增计数均附原始 HTTP 200 证据，未重放调用。"
             + f'Q-PRUNER 旧 judge=200 是任意函数文本口径；本次核验 {q["judge_seen_any_function_text"]} 次任意函数文本。完整原工具返回源码并集为 {q["judge_seen_full_source"]} 次：主裁判 {q["main_judge_seen_full_source"]} + 小裁判 {q["small_judge_seen_full_source"]} − 两者完整重叠 {q["main_small_full_source_overlap"]} = {q["judge_seen_full_source"]}。小裁判另有 {q["small_judge_seen_partial_or_different_source"]} 次部分或不同 span；其中部分经主裁判升级获得完整源码，不能直接从并集扣除。逐 action 差异见 summary.methods.<method>.delivery_count_differences。',
             "", "小裁判输入哈希有效仅证明保存的输入一致。逐条比较 <function> 字节与真实工具返回，单列完整、前缀裁剪及不同源码 span；未将 token_budget_trimmed=False 当作未发生字符裁剪。",
             "", "主裁判和 Agent 送达证据必须有后续 HTTP 200 receipt，并核对 request SHA 与 response SHA；Agent 还要求真实 context_accept 及后续 user 消息中完整源码。长度截断响应也证明收到输入，但保留其失败 finish_reason。",
             "", "每 action 的类别/原因、原文、源码 SHA、HTTP 证据与事件路径见 CSV。未读取 gold；gold_direct_prune 为不可用，实际 reject 不能直接视为误剪。",
             "", "B1 在线暂停：严格整段 DSL 会改变旧 parser 对外围解释正文的兼容行为。B2 采用严格文本 JSON，绝不称为原生 tool_calls。", ""]
    with (output / "matrix.md").open("x") as stream:
        stream.write("\n".join(text))
    return summary


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-run", type=Path, default=root / "runs/20261021_nonthinking_v3")
    parser.add_argument("--manifest", type=Path, default=root / "manifests/lite_pilot.json")
    parser.add_argument("--tool-csv", type=Path, default=root / "reports/lite_pilot_tool_io_per_call.csv")
    parser.add_argument("--output", type=Path, default=root / "runs/20261021_context_tool_diagnostic/audit")
    args = parser.parse_args(argv)
    summary = audit(args.historical_run, args.manifest, args.tool_csv, args.output)
    print(json.dumps({"audit_output": str(args.output), "historical_counts_reproduced": True, "dsml": summary["dsml"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
