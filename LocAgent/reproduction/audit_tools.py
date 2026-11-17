"""Offline audit of actual LocAgent HTTP, tool-execution and delivery evidence.

This module never imports the worker, opens gold, starts models, or makes
network requests. A tool-call ID is linked to a later HTTP tool message, and
the execution log's exact returned text is checked separately. Execution
logs lack call IDs: exact name/arguments and ordering are used only when
their group counts agree; ambiguity remains explicit otherwise.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ast
from urllib.parse import urlsplit


RETRIEVAL = {"search_code_snippets", "get_entity_contents", "explore_tree_structure"}


class Reader:
    def __init__(self):
        self.hashes = {}
        self.errors = []

    def data(self, path: Path, *, jsonl=False):
        if not path.is_file():
            return [] if jsonl else None
        raw = path.read_bytes()
        self.hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            self.errors.append({"file": str(path), "error": str(error)})
            return [] if jsonl else None
        if jsonl:
            result = []
            for number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError as error:
                    self.errors.append({"file": str(path), "line": number, "error": str(error)})
            return result
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            self.errors.append({"file": str(path), "error": str(error)})
            return None


def json_arguments(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def schema_errors(value, schema: dict, path="$args") -> list[str]:
    """Check the declared tools' required/type/items/enum/property constraints.

    This deliberately does not claim unrestricted JSON-Schema conformance.
    The actual request schema is preserved for any additional validation.
    """
    if not isinstance(schema, dict):
        return []
    errors = []
    checks = {
        "object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str), "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
        "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "boolean": lambda x: isinstance(x, bool), "null": lambda x: x is None,
    }
    expected = schema.get("type")
    if expected:
        types = expected if isinstance(expected, list) else [expected]
        if not any(checks.get(t, lambda _: True)(value) for t in types):
            return [f"{path}: type is incompatible with {expected}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value outside enum")
    if isinstance(value, dict):
        for required in schema.get("required", []):
            if required not in value:
                errors.append(f"{path}: missing {required}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(schema_errors(item, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected property {key}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            errors.extend(schema_errors(item, schema["items"], f"{path}[{index}]"))
    return errors


def execution_identity(event: dict):
    if event.get("function") in RETRIEVAL:
        return event["function"], event.get("kwargs", {})
    # A dispatcher validation error occurs before its function field is set.
    # Decode its logged AST literally, never execute it.
    try:
        tree = ast.parse(event.get("code", ""), mode="exec")
        call = tree.body[0].value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "print":
            call = call.args[0]
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
            return None, None
        if call.args:
            return call.func.id, None
        kwargs = {}
        for key in call.keywords:
            item = ast.literal_eval(key.value)
            if key.arg is None:
                kwargs.update(item)
            else:
                kwargs[key.arg] = item
        return call.func.id, kwargs
    except (SyntaxError, ValueError, TypeError, AttributeError, IndexError):
        return None, None


def identity_key(name, arguments):
    if name not in RETRIEVAL or not isinstance(arguments, dict):
        return None
    return json.dumps([name, arguments], sort_keys=True, ensure_ascii=False)


def sample_evidence(sample: Path, iid: str, reader: Reader, *, task_terminal=False):
    terminal_result = reader.data(sample / "result.json") or {}
    terminal = bool(terminal_result.get("terminal")) or task_terminal
    events = reader.data(sample / "tools.jsonl", jsonl=True)
    ledger = reader.data(sample / "requests/http_ledger.jsonl", jsonl=True)
    attempts = {}
    for event in ledger:
        number = event.get("http_attempt")
        if isinstance(number, int):
            attempts.setdefault(number, {})[event.get("event", "unknown")] = event
    http = []
    for number, pair in sorted(attempts.items()):
        start, finish = pair.get("started", {}), pair.get("finished", {})
        request_name = start.get("request_file")
        if not request_name:
            request_name = finish.get("response_file", "").replace("_response.txt", "_request.json")
        if not request_name or Path(request_name).name != request_name:
            reader.errors.append({"file": str(sample), "error": "Missing or unsafe ledger request filename"})
            continue
        request_path = sample / "requests" / request_name
        response_name = finish.get("response_file") or request_name.replace("_request.json", "_response.txt")
        if Path(response_name).name != response_name:
            reader.errors.append({"file": str(sample), "error": "Unsafe ledger response filename"})
            continue
        response_path = sample / "requests" / response_name
        request = reader.data(request_path)
        response = reader.data(response_path) if response_path.exists() and response_path.stat().st_size else None
        usage = response.get("usage") if isinstance(response, dict) else finish.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        p, c = usage.get("prompt_tokens"), usage.get("completion_tokens")
        known = all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in (p, c))
        http.append({"attempt": number, "request_number": start.get("completion_request", finish.get("completion_request")),
                     "status": finish.get("status_code"), "finished": bool(finish),
                     "endpoint": start.get("endpoint"), "request": request or {}, "response": response or {},
                     "request_file": str(request_path), "response_file": str(response_path),
                     "usage_known": known, "prompt_tokens": p if known else None,
                     "completion_tokens": c if known else None})
    deliveries = defaultdict(list)
    calls = []
    finishes = []
    for h in http:
        for message in h["request"].get("messages", []):
            if message.get("role") == "tool" and message.get("tool_call_id"):
                deliveries[message["tool_call_id"]].append({
                    "http_attempt": h["attempt"], "request_number": h["request_number"],
                    "accepted_http200": h["status"] == 200, "function": message.get("name"),
                    "content": message.get("content"), "request_file": h["request_file"],
                })
        choices = h["response"].get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        for call_index, tool in enumerate(message.get("tool_calls") or []):
            function = tool.get("function") or {}
            name, arguments = function.get("name"), json_arguments(function.get("arguments"))
            record = {"instance_id": iid, "sample": sample.name, "tool_call_id": tool.get("id"),
                      "function": name, "arguments": arguments, "arguments_json_parseable": arguments is not None,
                      "response_http_attempt": h["attempt"], "response_request_number": h["request_number"],
                      "response_file": h["response_file"], "response_call_index": call_index}
            declared = [t.get("function", {}) for t in h["request"].get("tools", []) if t.get("function", {}).get("name") == name]
            record["declared_tool"] = bool(declared)
            record["schema_errors"] = schema_errors(arguments, declared[0].get("parameters", {})) if declared and arguments is not None else ["unparseable arguments or undeclared tool"]
            record["declared_constraints_satisfied"] = arguments is not None and bool(declared) and not record["schema_errors"]
            if name == "finish":
                record["payload"] = arguments.get("final_response") if isinstance(arguments, dict) else None
                record["assistant_content"] = message.get("content")
                finishes.append(record)
            else:
                calls.append(record)

    call_groups, event_groups = defaultdict(list), defaultdict(list)
    for call in calls:
        key = identity_key(call["function"], call["arguments"])
        if key is not None:
            call_groups[key].append(call)
    for event_index, event in enumerate(events):
        name, arguments = execution_identity(event)
        key = identity_key(name, arguments)
        if key is not None:
            event_groups[key].append((event_index, event))
    matched_events = set()
    for key, group in call_groups.items():
        executed = event_groups.get(key, [])
        if len(group) == len(executed):
            for call, (index, event) in zip(group, executed):
                call["execution_event"] = event
                call["execution_link_method"] = "exact_arguments_order_and_equal_group_counts"
                matched_events.add(index)
        else:
            for call in group:
                matches = []
                for index, event in executed:
                    expected = "OBSERVATION:\n" + str(event.get("output", ""))
                    delivered = deliveries.get(call["tool_call_id"], [])
                    if index not in matched_events and any(d["content"] == expected and d["function"] == call["function"] for d in delivered):
                        matches.append((index, event))
                if len(matches) == 1:
                    index, event = matches[0]
                    call["execution_event"] = event
                    call["execution_link_method"] = "unique_exact_arguments_and_matching_return_text"
                    matched_events.add(index)
    maximum_attempt = max((h["attempt"] for h in http), default=0)
    id_counts = Counter(c["tool_call_id"] for c in calls)
    for call in calls:
        event = call.pop("execution_event", None)
        messages = [d for d in deliveries.get(call["tool_call_id"], []) if d["http_attempt"] > call["response_http_attempt"]]
        call["execution_link_method"] = call.get("execution_link_method", "not_uniquely_linked")
        call["dispatch_observed"] = event is not None
        call["official_function_entered"] = bool(event and event.get("function") == call["function"])
        call["tool_success"] = bool(event and event.get("status") == "success")
        call["tool_error"] = bool(event and event.get("status") != "success")
        call["output_chars"] = len(str(event.get("output", ""))) if event else None
        call["output_sha256"] = hashlib.sha256(str(event.get("output", "")).encode()).hexdigest() if event else None
        call["full_function_source_verified"] = None
        call["return_text_delivery_scope"] = "tool-return text only; complete source not certified"
        expected = "OBSERVATION:\n" + str(event.get("output", "")) if event else None
        exact = [d for d in messages if d["function"] == call["function"] and expected is not None and d["content"] == expected]
        call["tool_call_id_unique"] = bool(call["tool_call_id"]) and id_counts[call["tool_call_id"]] == 1
        accepted = [d for d in exact if d["accepted_http200"]] if call["tool_call_id_unique"] else []
        call["return_text_in_later_request"] = bool(exact)
        call["return_text_received_by_model"] = bool(accepted)
        call["accepted_delivery_count"] = len(accepted)
        call["delivery_request_files"] = list(dict.fromkeys(d["request_file"] for d in accepted))
        call["no_later_http_request"] = maximum_attempt <= call["response_http_attempt"]
        if not call["tool_call_id_unique"]:
            state = "ambiguous_or_missing_tool_call_id"
        elif not event:
            state = "execution_not_uniquely_linked"
        elif accepted:
            state = "exact_return_text_in_later_http200_request"
        elif not terminal:
            state = "pending_or_unconfirmed_during_run"
        elif call["no_later_http_request"]:
            state = "last_tool_return_no_later_request"
        elif exact:
            state = "return_text_in_rejected_or_unconfirmed_request_only"
        else:
            state = "no_matching_return_text_despite_later_request"
        call["delivery_state"] = state
    return {"sample": sample.name, "terminal": terminal, "sample_result": terminal_result,
            "http": http, "calls": calls, "finishes": finishes, "execution_events": events,
            "unlinked_execution_events": len(events) - len(matched_events)}


def finite_usage(http: list[dict]) -> dict:
    known_p = sum(h["prompt_tokens"] for h in http if h["usage_known"])
    known_c = sum(h["completion_tokens"] for h in http if h["usage_known"])
    unknown = sum(not h["usage_known"] for h in http)
    return {"http_attempts": len(http), "unknown_usage_attempts": unknown,
            "unfinished_http_attempts": sum(not h["finished"] for h in http),
            "known_prompt_tokens": known_p, "known_completion_tokens": known_c,
            "known_total_tokens": known_p + known_c,
            "prompt_tokens": None if unknown else known_p,
            "completion_tokens": None if unknown else known_c,
            "total_tokens": None if unknown else known_p + known_c}


def audit_run(run: Path):
    reader = Reader()
    manifest = reader.data(run / "selection/manifest.json")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("records"), list):
        raise ValueError("A frozen selection/manifest.json with records is required")
    records = manifest["records"]
    ids = [r["instance_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate instance IDs in manifest")
    if any(not isinstance(iid, str) or "/" in iid or iid in {".", ".."} for iid in ids):
        raise ValueError("Unsafe task ID in frozen manifest")
    tasks, calls, all_http, all_finishes = [], [], [], []
    for iid in ids:
        task = run / "outputs" / iid
        result = reader.data(task / "result.json") or {}
        terminal = result.get("terminal") is True
        samples = [sample_evidence(s, iid, reader, task_terminal=terminal)
                   for s in sorted((task / "samples").glob("sample_*")) if s.is_dir()]
        http = [h for s in samples for h in s["http"]]
        tool_calls = [c for s in samples for c in s["calls"]]
        events = [e for s in samples for e in s["execution_events"]]
        valid_location = bool(result.get("found_files") or result.get("found_entities"))
        has_raw_finish = any(bool(s["sample_result"].get("raw_location")) for s in samples)
        usage = finite_usage(http)
        task_record = {
            "instance_id": iid, "terminal": terminal, "status": result.get("status", "pending"),
            "execution_status": result.get("execution_status", "pending"),
            "has_official_location_output": valid_location,
            "has_nonempty_raw_finish": has_raw_finish,
            "retrieval_calls_declared": len(tool_calls),
            "arguments_json_parseable": sum(c["arguments_json_parseable"] for c in tool_calls),
            "declared_constraints_satisfied": sum(c["declared_constraints_satisfied"] for c in tool_calls),
            "dispatcher_events": len(events),
            "official_function_calls_entered": sum(e.get("function") in RETRIEVAL for e in events),
            "successful_execution_events": sum(e.get("status") == "success" for e in events),
            "tool_error_events": sum(e.get("status") != "success" for e in events),
            "function_error_events": sum(e.get("status") != "success" and e.get("function") in RETRIEVAL for e in events),
            "pre_execution_validation_errors": sum(e.get("status") != "success" and e.get("function") not in RETRIEVAL for e in events),
            "return_text_delivered_events": sum(c["return_text_received_by_model"] for c in tool_calls),
            "last_return_not_sent": sum(c["delivery_state"] == "last_tool_return_no_later_request" for c in tool_calls),
            "pending_delivery_events": sum(c["delivery_state"] == "pending_or_unconfirmed_during_run" for c in tool_calls),
            "unlinked_execution_events": sum(s["unlinked_execution_events"] for s in samples),
            "finish_calls": sum(len(s["finishes"]) for s in samples),
            "zero_tools_with_location": terminal and bool(http) and not tool_calls and valid_location,
            "zero_tools_without_location": terminal and bool(http) and not tool_calls and not valid_location,
            "all_requests_explicit_nonthinking": all(h["request"].get("chat_template_kwargs", {}).get("enable_thinking") is False for h in http) if http else None,
            **usage,
        }
        tasks.append(task_record)
        calls.extend(tool_calls)
        all_http.extend(http)
        all_finishes.extend(f for s in samples for f in s["finishes"])
    terminal_n = sum(t["terminal"] for t in tasks)
    final = terminal_n == len(ids)
    request_models = Counter(h["request"].get("model", "UNKNOWN") for h in all_http)
    returned_models = Counter(h["response"].get("model", "UNKNOWN") for h in all_http if h["response"])
    explicit_false = sum(h["request"].get("chat_template_kwargs", {}).get("enable_thinking") is False for h in all_http)
    local = sum(urlsplit(h["endpoint"] or "").hostname in {"127.0.0.1", "localhost", "::1"} for h in all_http)
    summary = {
        "status": "FINAL" if final else "RUNNING_SNAPSHOT", "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run), "expected_tasks": len(ids), "terminal_tasks": terminal_n,
        "tasks_with_http_attempts": sum(t["http_attempts"] > 0 for t in tasks),
        "tasks_with_declared_retrieval_calls": sum(t["retrieval_calls_declared"] > 0 for t in tasks),
        "tasks_with_official_tool_execution": sum(t["official_function_calls_entered"] > 0 for t in tasks),
        "tasks_with_successful_tool_execution": sum(t["successful_execution_events"] > 0 for t in tasks),
        "zero_tools_with_location": sum(t["zero_tools_with_location"] for t in tasks),
        "zero_tools_without_location": sum(t["zero_tools_without_location"] for t in tasks),
        "requests_explicit_thinking_false": explicit_false, "local_endpoint_attempts": local,
        "request_model_counts": dict(request_models), "returned_model_counts": dict(returned_models),
        "retrieval_calls_declared": len(calls),
        "arguments_json_parseable": sum(c["arguments_json_parseable"] for c in calls),
        "declared_constraints_satisfied": sum(c["declared_constraints_satisfied"] for c in calls),
        "official_function_calls_entered": sum(t["official_function_calls_entered"] for t in tasks),
        "successful_execution_events": sum(t["successful_execution_events"] for t in tasks),
        "tool_error_events": sum(t["tool_error_events"] for t in tasks),
        "function_error_events": sum(t["function_error_events"] for t in tasks),
        "pre_execution_validation_errors": sum(t["pre_execution_validation_errors"] for t in tasks),
        "unlinked_execution_events": sum(t["unlinked_execution_events"] for t in tasks),
        "return_text_received_by_model": sum(c["return_text_received_by_model"] for c in calls),
        "delivery_state_counts": dict(Counter(c["delivery_state"] for c in calls)),
        "tool_name_counts": dict(Counter(c["function"] for c in calls)),
        "finish_calls": len(all_finishes), "full_function_source_verified": None,
        "source_scope": "Only exact tool-return text delivery is audited; no full-function body/semantic usefulness claim",
        "schema_validation_scope": "required,type,items,enum,additionalProperties only; actual schemas retained in requests",
        "analysis_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "read_errors": reader.errors, "source_files_sha256": reader.hashes,
        "new_model_calls": 0, "gold_read": False, **finite_usage(all_http),
    }
    return summary, tasks, calls


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def write_audit(run: Path, output: Path):
    summary, tasks, calls = audit_run(run)
    output.mkdir(parents=True, exist_ok=True)
    prefix = "" if summary["status"] == "FINAL" else "运行中快照_"
    (output / f"{prefix}工具使用审计.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    write_csv(output / f"{prefix}逐题工具使用.csv", tasks)
    write_csv(output / f"{prefix}逐调用工具送达.csv", calls)
    n, started = summary["expected_tasks"], summary["tasks_with_http_attempts"]
    total = summary["http_attempts"]
    lines = ["# LocAgent工具使用与实际送达审计", "", f"状态：**{summary['status']}**；固定任务{n}题，已终态{summary['terminal_tasks']}题，已发生HTTP调用{started}题。", "",
        "本报告只读原始HTTP请求、响应与工具执行事件，不读取金标，不修改预测，不新增模型调用。运行中数值会继续变化，不能当作全量成绩。", "",
        "## 任务层面", "", "| 项目 | 数量与分母 |", "|---|---:|",
        f"| 模型尝试调用检索工具 | {summary['tasks_with_declared_retrieval_calls']}/{started}道已调用题 |",
        f"| 实际进入官方工具函数 | {summary['tasks_with_official_tool_execution']}/{started}道已调用题 |",
        f"| 至少一次工具成功返回 | {summary['tasks_with_successful_tool_execution']}/{started}道已调用题 |",
        f"| 零检索调用但有官方可解析位置输出 | {summary['zero_tools_with_location']}道已终态题 |",
        f"| 零检索调用且无可解析位置输出 | {summary['zero_tools_without_location']}道已终态题 |", "",
        "这里的“有位置输出”仅指官方后处理得到非空文件或函数列表，不代表命中金标。未启动题不计入零工具失败。", "",
        "## 调用与送达", "", "| 项目 | 次数 |", "|---|---:|",
        f"| 响应声明的检索工具调用 | {summary['retrieval_calls_declared']} |",
        f"| 参数为可解析JSON对象 | {summary['arguments_json_parseable']} |",
        f"| 满足已检查的声明类型/必填项等约束 | {summary['declared_constraints_satisfied']} |",
        f"| 实际进入官方工具函数 | {summary['official_function_calls_entered']} |",
        f"| 工具成功返回事件 | {summary['successful_execution_events']} |",
        f"| 工具或调用前校验错误事件 | {summary['tool_error_events']} |",
        f"| 精确返回文本进入后续HTTP200模型请求 | {summary['return_text_received_by_model']} |",
        f"| 终态最后一次工具返回后没有后续请求 | {summary['delivery_state_counts'].get('last_tool_return_no_later_request', 0)} |", "",
        "关联首先使用同一样本内原始response的tool_call_id，再匹配后续实际HTTP请求的role=tool消息。执行日志不含call ID，须以函数名、参数与执行顺序关联；组内数量不一致且无法由精确返回文本消歧时保留未唯一关联。", "",
        "仅出现在HTTP400或尚未收到回执的请求中，不认定模型已接收。执行成功、工具返回文本送达与提供完整有用源码是不同事件；目录、名称或含def字样的文本均不自动算完整函数体。本次不认证完整函数源码覆盖。", "",
        "## 请求配置与真实usage", "",
        f"- 显式enable_thinking=False：{summary['requests_explicit_thinking_false']}/{total}次HTTP尝试。",
        f"- 本地loopback端点：{summary['local_endpoint_attempts']}/{total}次HTTP尝试。",
        f"- 请求模型：{json.dumps(summary['request_model_counts'], ensure_ascii=False)}；返回模型：{json.dumps(summary['returned_model_counts'], ensure_ascii=False)}。",
        f"- 已知prompt/completion token下界：{summary['known_prompt_tokens']}/{summary['known_completion_tokens']}，合计{summary['known_total_tokens']}。",
        f"- usage未知尝试：{summary['unknown_usage_attempts']}；未结束HTTP尝试：{summary['unfinished_http_attempts']}。",
        f"- 精确总token：{summary['total_tokens'] if summary['total_tokens'] is not None else '未知，不能记为0'}。",
        f"- 读取异常：{len(summary['read_errors'])}，详情和源文件SHA见JSON。", ""]
    (output / f"{prefix}工具使用审计.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def without_finish_parameters(request: dict) -> dict:
    result = copy.deepcopy(request)
    for tool in result.get("tools", []):
        if tool.get("function", {}).get("name") == "finish":
            tool["function"].pop("parameters", None)
    return result


def audit_finish_channel(v1: Path, v2: Path, output: Path):
    reader = Reader()
    manifest = reader.data(v2 / "selection/manifest.json")
    ids = [r["instance_id"] for r in manifest["records"][:3]]
    rows, payloads = [], []
    v1_http = []
    for iid in ids:
        for number in (1, 2):
            relative = Path("outputs") / iid / "samples" / f"sample_{number:02d}"
            p1 = v1 / relative / "requests/request_001_attempt_1_request.json"
            p2 = v2 / relative / "requests/request_001_attempt_1_request.json"
            r1, r2 = reader.data(p1), reader.data(p2)
            both = isinstance(r1, dict) and isinstance(r2, dict)
            finish1 = next((t["function"] for t in (r1 or {}).get("tools", []) if t["function"]["name"] == "finish"), None)
            finish2 = next((t["function"] for t in (r2 or {}).get("tools", []) if t["function"]["name"] == "finish"), None)
            rows.append({"instance_id": iid, "sample": number, "both_first_requests_exist": both,
                "messages_identical": both and r1.get("messages") == r2.get("messages"),
                "only_finish_parameters_differ": both and finish1 != finish2 and without_finish_parameters(r1) == without_finish_parameters(r2),
                "three_retrieval_schemas_identical": both and [t for t in r1.get("tools", []) if t["function"]["name"] != "finish"] == [t for t in r2.get("tools", []) if t["function"]["name"] != "finish"],
                "v1_finish_schema": finish1, "v2_finish_schema": finish2,
                "v1_request_sha256": reader.hashes.get(str(p1)), "v2_request_sha256": reader.hashes.get(str(p2))})
            s1 = sample_evidence(v1 / relative, iid, reader, task_terminal=True)
            v1_http.extend(s1["http"])
            s2 = sample_evidence(v2 / relative, iid, reader)
            raw = s2["sample_result"].get("raw_location", "")
            for finish in s2["finishes"]:
                payload = finish["payload"]
                is_string = isinstance(payload, str)
                payloads.append({"instance_id": iid, "sample": number, "tool_call_id": finish["tool_call_id"],
                    "response_file": finish["response_file"], "payload_is_string": is_string,
                    "payload_chars": len(payload) if is_string else None,
                    "payload_sha256": hashlib.sha256(payload.encode()).hexdigest() if is_string else None,
                    "raw_location_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "payload_equals_raw_location": is_string and payload == raw,
                    "payload_fully_present_in_raw_location": is_string and bool(payload) and payload in raw,
                    "payload_only_fence_or_whitespace": is_string and not payload.replace("`", "").strip(),
                    "sample_status": s2["sample_result"].get("status", "pending")})
    overhead = finite_usage(v1_http)
    data = {"status": "ANALYZED", "v1_run": str(v1), "v2_run": str(v2), "canary_instance_ids": ids,
        "first_request_comparisons": rows, "v2_payload_evidence": payloads,
        "all_six_only_finish_schema_differs": len(rows) == 6 and all(r["both_first_requests_exist"] and r["only_finish_parameters_differ"] and r["messages_identical"] and r["three_retrieval_schemas_identical"] for r in rows),
        "v1_engineering_overhead": overhead, "read_errors": reader.errors,
        "analysis_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_files_sha256": reader.hashes, "new_model_calls": 0, "gold_read": False}
    output.mkdir(parents=True, exist_ok=True)
    (output / "finish通道审计.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    write_csv(output / "六首请求差异.csv", rows)
    write_csv(output / "payload接收证据.csv", payloads)
    lines = ["# 原生finish结果通道工程审计", "",
        "此分析仅核对协议和数据流，不读取金标，不挑选预测，不回捞或修补v1答案。", "",
        f"固定前三题：{', '.join(ids)}。六个首请求除finish参数声明外一致：**{data['all_six_only_finish_schema_differs']}**。", "",
        f"原v1工程试跑保留{overhead['http_attempts']}次真实HTTP尝试，已知token为{overhead['known_prompt_tokens']}＋{overhead['known_completion_tokens']}＝{overhead['known_total_tokens']}；未知usage尝试{overhead['unknown_usage_attempts']}。", "",
        "v2仅在finish schema增加必填final_response字符串。官方parser已能将该参数传给FinishAction；逐条原始payload与sample raw_location的哈希及完整性核对见CSV/JSON。", "",
        "payload完整传递不代表模型提供了有效位置：空白或仅代码围栏等内容单独标识，不能据此宣称定位成功。模型仍可能早退、搜索无效或达到步数上限。本次没有为这些正常输出追加救分调用。", ""]
    (output / "finish通道审计.md").write_text("\n".join(lines), encoding="utf-8")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--v1-run-dir")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    summary = write_audit(run, Path(args.output).resolve())
    previous = args.v1_run_dir
    if previous is None:
        asset = run / "asset_reuse.json"
        if asset.is_file():
            previous = json.loads(asset.read_text()).get("source_run")
    if previous:
        audit_finish_channel(Path(previous).resolve(), run, run / "audits/finish_channel")
    print(json.dumps({key: summary[key] for key in ("status", "expected_tasks", "terminal_tasks", "http_attempts", "known_total_tokens", "unknown_usage_attempts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
