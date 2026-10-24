"""Render terminal native-tool runs without models, credentials, or evaluators.

Only an explicit set of run artifacts is read. Original artifacts are never
changed; the three derived outputs are atomically replaced on regeneration.
"""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile

from . import common as C


TRACE_NAME = "完整工具轨迹.md"
CSV_NAME = "逐轮统计.csv"
METRICS = ("prompt_tokens", "completion_tokens", "total_tokens",
           "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")


def _integer(value):
    return type(value) is int and value >= 0


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def _block(value, language="text"):
    """A dynamic fence preserves arbitrary source text, including backticks."""
    fence = "`" * max(3, 1 + max((len(x) for x in re.findall(r"`+", value)), default=0))
    return fence + language + "\n" + value + ("" if value.endswith("\n") else "\n") + fence + "\n"


def _public_message(message):
    # Whitelist only API public fields, rather than copying reasoning fields.
    public = {key: message[key] for key in ("role", "name", "content", "tool_call_id") if key in message}
    if "tool_calls" in message:
        public["tool_calls"] = [_public_call(call) for call in message["tool_calls"]]
    return public


def _public_call(call):
    public = {key: call[key] for key in ("id", "type") if key in call}
    public["function"] = {key: call.get("function", {})[key] for key in ("name", "arguments")
                          if key in call.get("function", {})}
    return public


def _public_attempt(attempt):
    receipt = attempt["receipt"] or {}
    public = {key: attempt[key] for key in ("turn", "attempt", "http_success", "transport_failure",
                                          "billing_unknown", "receipt_missing")}
    public["started"] = {key: (attempt["started"] or {})[key] for key in ("utc", "request_sha256")
                         if key in (attempt["started"] or {})}
    public["receipt"] = {key: receipt[key] for key in (
        "started_utc", "ended_utc", "elapsed_seconds", "http_status", "status", "error_type",
        "request_sha256", "response_sha256", "request_id", "model", "billing_unknown",
        "system_fingerprint") if key in receipt}
    public["receipt"]["usage"] = _usage(receipt)
    cost = receipt.get("cost") or {}
    public["receipt"]["cost"] = {key: cost[key] for key in (
        "usd", "price_tier", "cache_hits_known", "estimate_or_upper", "source",
        "not_provider_invoice", "usage_unknown") if key in cost}
    return public


class Sources:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if any(path.is_symlink() for path in (self.root, *self.root.parents)):
            raise ValueError("Run root must not contain symlink components")
        self.hashes = {}

    def path(self, relative):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Run artifact path must be relative")
        path = self.root
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                raise ValueError("Symlink run artifacts are forbidden")
        return path

    def read(self, relative):
        name = Path(relative).as_posix()
        try:
            raw = self.path(name).read_bytes()
        except FileNotFoundError:
            if not re.fullmatch(r"calls/\d+/request\.json", name):
                raise
            with gzip.open(self.path(name + ".gz"), "rb") as stream:
                raw = stream.read()
        self.hashes[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    def optional(self, relative):
        name = Path(relative).as_posix()
        available = self.path(name).is_file()
        if not available and re.fullmatch(r"calls/\d+/request\.json", name):
            available = self.path(name + ".gz").is_file()
        return self.read(name) if available else None

    def numbered(self, relative, directories=False):
        directory = self.path(relative)
        if not directory.exists():
            return []
        names = [path.name for path in directory.iterdir()
                 if re.fullmatch(r"\d+" if directories else r"\d+\.json", path.name)]
        for name in names:
            path = self.path(Path(relative) / name)
            if not (path.is_dir() if directories else path.is_file()):
                raise ValueError("Unexpected numbered run artifact type")
        return sorted(names, key=lambda name: int(name.split(".")[0]))


def _usage(receipt):
    usage = receipt.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    values = {key: usage.get(key) for key in METRICS}
    details = usage.get("prompt_tokens_details")
    if not _integer(values["prompt_cache_hit_tokens"]) and isinstance(details, dict):
        values["prompt_cache_hit_tokens"] = details.get("cached_tokens")
    prompt, output, hit = (values[key] for key in METRICS[:2] + ("prompt_cache_hit_tokens",))
    if not _integer(values["total_tokens"]) and _integer(prompt) and _integer(output):
        values["total_tokens"] = prompt + output
    if (not _integer(values["prompt_cache_miss_tokens"]) and _integer(prompt)
            and _integer(hit) and hit <= prompt):
        values["prompt_cache_miss_tokens"] = prompt - hit
    return {key: value if _integer(value) else None for key, value in values.items()}


def _aggregate(attempts):
    values = [_usage(attempt["receipt"] or {}) for attempt in attempts]
    totals = {key: sum(value[key] for value in values if value[key] is not None)
              for key in METRICS}
    missing = {key: sum(value[key] is None for value in values) for key in METRICS}
    costs = [(attempt["receipt"] or {}).get("cost") or {} for attempt in attempts]
    known_cost = sum(cost["usd"] for cost in costs if _number(cost.get("usd")))
    unknown_cost = sum(attempt["billing_unknown"] or not _number(cost.get("usd"))
                       for attempt, cost in zip(attempts, costs))
    return {"known_token_totals": totals, "usage_missing_attempts": missing,
            "known_estimated_cost_usd": known_cost,
            "cost_unknown_attempts": unknown_cost,
            "total_cost_usd": known_cost if not unknown_cost else None,
            "not_provider_invoice": True}


def _attempts(source, folder, turn):
    names = set()
    for path in source.path(folder).iterdir():
        match = re.fullmatch(r"attempt_(\d+)_(started|receipt|response)\.json", path.name)
        if match:
            source.path(Path(folder) / path.name)
            names.add(int(match.group(1)))
    attempts = []
    for index in sorted(names):
        stem = Path(folder) / f"attempt_{index}"
        started = source.optional(str(stem) + "_started.json")
        receipt = source.optional(str(stem) + "_receipt.json")
        response = source.optional(str(stem) + "_response.json")
        success = receipt is not None and receipt.get("http_status") == 200
        attempts.append({"turn": turn, "attempt": index, "started": started,
                         "receipt": receipt, "response": response,
                         "http_success": success,
                         "transport_failure": (receipt or {}).get("status") == "transport_error",
                         "billing_unknown": receipt is None or bool(receipt.get("billing_unknown")),
                         "receipt_missing": receipt is None})
    return attempts


def _merged(intervals):
    merged = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return merged


def _tool_summary(records):
    counts, successful, failed = Counter(), Counter(), Counter()
    coverage = {}
    searches = []
    symbols = set()
    for record in records:
        name = record["name"]
        output = record["output"]
        counts[name] += 1
        (successful if output.get("ok") else failed)[name] += 1
        data = output.get("data") or {}
        if not output.get("ok"):
            continue
        if name == "read_file":
            key = (data["path"], data["sha256"])
            item = coverage.setdefault(key, {"path": key[0], "sha256": key[1],
                                             "read_calls": 0, "returned_lines_with_repetition": 0,
                                             "intervals": []})
            item["read_calls"] += 1
            lo, hi = data["start_line"], data["end_line"]
            if hi >= lo:
                item["intervals"].append([lo, hi])
                item["returned_lines_with_repetition"] += hi - lo + 1
        elif name == "search_repository":
            searches.append({"turn": record["turn"], "tool_call_id": record["tool_call_id"],
                             "path": data["path"], "pattern": data["pattern"],
                             "regex": data["regex"], "searched_files": data["searched_files"],
                             "match_count": data["match_count"],
                             "matched_paths": [file["path"] for file in data["files"]],
                             "skipped_files": len(data.get("skipped", []))})
        elif name == "list_symbols":
            symbols.add(data["path"])
    versions = []
    for key, item in sorted(coverage.items()):
        item["intervals"] = _merged(item["intervals"])
        item["unique_lines"] = sum(hi - lo + 1 for lo, hi in item["intervals"])
        versions.append(item)
    return {"executed_tool_calls": len(records), "tool_calls_by_name": dict(counts),
            "successful_tool_calls_by_name": dict(successful), "failed_tool_calls_by_name": dict(failed),
            "read_file_coverage": {"scope": "Successful read_file results only; search context and "
                                  "list_symbols are excluded. Intervals are inclusive, grouped by path+SHA.",
                                  "unique_paths": len({key[0] for key in coverage}),
                                  "content_versions": len(versions),
                                  "unique_lines": sum(item["unique_lines"] for item in versions),
                                  "files": versions},
            "search": {"successful_calls": len(searches),
                       "searched_files_with_repetition": sum(x["searched_files"] for x in searches),
                       "matches_with_repetition": sum(x["match_count"] for x in searches),
                       "unique_matched_paths": sorted({path for x in searches for path in x["matched_paths"]}),
                       "calls": searches},
            "list_symbols_unique_paths": sorted(symbols)}


def _atomic_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def render(run, docs):
    """Read only whitelisted raw artifacts and write three derived reports."""
    source = Sources(run)
    docs = Path(docs).absolute()
    if any(path.is_symlink() for path in (docs, *docs.parents)):
        raise ValueError("Report destination must not contain symlink components")
    result = source.optional("result.json")
    complete = result is not None and result.get("status") == "complete"
    terminal_error = source.optional("error.json") if not complete else None
    if not complete and terminal_error is None:
        raise ValueError("A complete result.json or terminal error.json is required")
    result = result or {}
    initial = source.optional("initial_messages.json") or []
    records = [source.read(Path("tools") / name) for name in source.numbered("tools")]
    by_turn = defaultdict(list)
    for record in records:
        by_turn[record["turn"]].append(record)
    for items in by_turn.values():
        items.sort(key=lambda item: item["position"])
    markdown = ["# 完整工具轨迹\n\n", "以下内容直接来自本次运行的原始 API 和工具记录；不包含私有推理字段。"
                "参数及工具返回完整保留，无长度或命中数截断。费用仅为日志中的估算，不是服务商账单。\n\n",
                "## 完整初始 messages\n\n", _block(_json([_public_message(x) for x in initial]), "json")]
    rows, all_attempts, warnings = [], [], []
    if not initial:
        warnings.append("Initial messages artifact is absent or empty")
    expected_history = initial
    native_calls = 0
    final_content = None
    turns = source.numbered("calls", directories=True)
    for folder_name in turns:
        turn = int(folder_name)
        folder = Path("calls") / folder_name
        request = source.read(folder / "request.json")
        wrapped = source.optional(folder / "result.json")
        attempts = _attempts(source, folder, turn)
        all_attempts.extend(attempts)
        if not attempts:
            warnings.append("No actual attempt evidence for requested model turn " + str(turn))
        successful_attempts = [attempt for attempt in attempts if attempt["http_success"]]
        response = wrapped["response"] if wrapped else next((attempt["response"] for attempt in
                    reversed(attempts) if attempt["response"] is not None), None)
        if wrapped and not any(attempt["response"] == response and attempt["receipt"] == wrapped["receipt"]
                               for attempt in successful_attempts):
            warnings.append(f"Turn {turn}: result wrapper does not match an attempt response/receipt")
        for attempt in attempts:
            receipt = attempt["receipt"] or {}
            if receipt.get("request_sha256") and receipt["request_sha256"] != C.digest(request):
                warnings.append(f"Turn {turn} attempt {attempt['attempt']}: request SHA mismatch")
            if (attempt["response"] is not None and receipt.get("response_sha256")
                    and receipt["response_sha256"] != C.digest(attempt["response"])):
                warnings.append(f"Turn {turn} attempt {attempt['attempt']}: response SHA mismatch")
        choices = (response.get("choices") or []) if isinstance(response, dict) else []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        calls = message.get("tool_calls") or []
        native_calls += len(calls)
        if message:
            final_content = message.get("content")
        markdown.append(f"\n## 第 {turn} 轮\n\n")
        history = request["messages"]
        if history[:len(expected_history)] != expected_history:
            warnings.append(f"Turn {turn}: request history differs from reconstructed prior messages")
        extra = history[len(expected_history):]
        if extra:
            markdown.extend(["### 本轮额外输入消息\n\n",
                             _block(_json([_public_message(x) for x in extra]), "json")])
        markdown.extend(["### 原始公开 assistant.content\n\n",
                         (_block(message.get("content"), "text") if isinstance(message.get("content"), str)
                          else _block(_json(message.get("content")), "json")) if message
                         else "本轮未记录到模型的公开 assistant 响应。\n",
                         "\n公开原生工具调用：\n\n", _block(_json([_public_call(x) for x in calls]), "json"),
                         "\nAPI 尝试回执（不包含私有推理）：\n\n",
                         _block(_json([_public_attempt(attempt) for attempt in attempts]), "json")])
        expected_history = list(history)
        if message:
            expected_history.append(_public_message({"role": "assistant",
                "content": message.get("content"), **({"tool_calls": calls} if calls else {})}))
        turn_records = by_turn.get(turn, [])
        if len(turn_records) != len(calls):
            warnings.append(f"Turn {turn}: native tool call count differs from execution record count")
        for record in turn_records:
            position = record["position"]
            if position >= len(calls) or any((record["tool_call_id"] != calls[position].get("id"),
                    record["name"] != calls[position].get("function", {}).get("name"),
                    record["raw_arguments"] != calls[position].get("function", {}).get("arguments"))):
                warnings.append(f"Turn {turn} tool position {position}: execution differs from API call")
            markdown.extend([f"\n### Native tool {record['position'] + 1}: {record['name']}\n\n",
                             _block(_json({key: record.get(key) for key in
                                           ("tool_call_id", "elapsed_seconds", "output_sha256", "output_utf8_bytes")}), "json"),
                             "\n完整原始参数字符串：\n\n",
                             _block(record["raw_arguments"] if isinstance(record["raw_arguments"], str)
                                    else _json(record["raw_arguments"]), "json"),
                             "\n完整工具结果 JSON（原样传回模型的 wire_content）：\n\n",
                             _block(record["wire_content"], "json")])
            if json.loads(record["wire_content"]) != record["output"]:
                warnings.append(f"Turn {turn}: wire_content differs from logged output")
            if record.get("output_sha256") != C.digest(record["output"]):
                warnings.append(f"Turn {turn}: tool output SHA differs from logged output")
            expected_history.append({"role": "tool", "tool_call_id": record["tool_call_id"],
                                     "content": record["wire_content"]})
        aggregate = _aggregate(attempts)
        known = aggregate["known_token_totals"]
        missing = aggregate["usage_missing_attempts"]
        row = {"turn": turn, "api_attempts": len(attempts),
               "http_successful_attempts": len(successful_attempts),
               "transport_failure_attempts": sum(x["transport_failure"] for x in attempts),
               "billing_unknown_attempts": sum(x["billing_unknown"] for x in attempts),
               **{key: known[key] if missing[key] < len(attempts) else None for key in METRICS},
               **{key + "_missing_attempts": missing[key] for key in METRICS},
               "latency_seconds_all_receipted_attempts": sum((x["receipt"] or {})["elapsed_seconds"]
                   for x in attempts if _number((x["receipt"] or {}).get("elapsed_seconds"))),
               "latency_missing_attempts": sum(not _number((x["receipt"] or {}).get("elapsed_seconds"))
                                               for x in attempts),
               "known_estimated_cost_usd": aggregate["known_estimated_cost_usd"],
               "cost_unknown_attempts": aggregate["cost_unknown_attempts"],
               "total_cost_usd": aggregate["total_cost_usd"],
               "native_tool_calls": len(calls), "executed_tool_calls": len(turn_records),
               "finish_reason": choice.get("finish_reason"), "model": (response or {}).get("model"),
               "request_id": (response or {}).get("id")}
        rows.append(row)
    if complete and final_content != result.get("final_response"):
        raise ValueError("Final raw public assistant.content differs from result.final_response")
    if set(by_turn) - {int(name) for name in turns}:
        raise ValueError("Orphan tool records have no corresponding API turn")
    if complete and (len(turns) != result.get("model_turns") or len(records) != result.get("tool_calls")):
        warnings.append("Final result counts differ from raw API/tool artifact counts")
    if complete:
        markdown.extend(["\n## 最终回答（原始公开内容）\n\n", _block(result["final_response"], "text")])
    else:
        markdown.extend(["\n## 终止状态\n\n模型未给出最终定位。运行因原始错误记录而终止；"
                         "上述公开响应、工具记录和用量仅记录已经发生的过程，不补写最终答案。\n\n",
                         _block(_json({key: terminal_error.get(key) for key in ("utc", "type", "error")}), "json")])
    summary = {"schema_version": 1, "generated_utc": C.utc(),
               "status": "complete" if complete else "terminal_error",
               "model_final_localization_available": complete,
               "terminal_error": None if complete else {key: terminal_error.get(key)
                                                         for key in ("utc", "type", "error")},
               "model": result.get("model") or next((row["model"] for row in reversed(rows)
                                                        if row["model"]), None),
               "model_turns": len(turns),
               "model_turns_with_public_response": sum(bool(row["request_id"]) for row in rows),
               "actual_api_attempts": len(all_attempts),
               "http_successful_attempts": sum(x["http_success"] for x in all_attempts),
               "transport_failure_attempts": sum(x["transport_failure"] for x in all_attempts),
               "http_error_attempts": sum(x["receipt"] is not None
                                          and x["receipt"].get("http_status", 200) != 200
                                          for x in all_attempts),
               "started_or_response_without_receipt": sum(x["receipt_missing"] for x in all_attempts),
               "billing_unknown_attempts": sum(x["billing_unknown"] for x in all_attempts),
               "native_tool_calls_in_api_responses": native_calls,
               "api_latency_seconds_known": sum(row["latency_seconds_all_receipted_attempts"]
                                                   for row in rows),
               "api_latency_missing_attempts": sum(row["latency_missing_attempts"] for row in rows),
               "attempt_accounting": "Each (turn, attempt) is counted once; result.json wrappers "
                                     "do not create extra calls. Unknown usage/cost is never zero.",
               **_aggregate(all_attempts), **_tool_summary(records),
               "wall_elapsed_seconds": result.get("elapsed_seconds"), "warnings": warnings,
               "private_reasoning_fields_exported": False,
               "source_artifacts_sha256": dict(sorted(source.hashes.items()))}
    markdown.extend(["\n## 统计口径与完整性检查\n\n", _block(_json({
        "warnings": warnings, "actual_api_attempts": summary["actual_api_attempts"],
        "billing_unknown_attempts": summary["billing_unknown_attempts"],
        "known_estimated_cost_usd": summary["known_estimated_cost_usd"],
        "total_cost_usd": summary["total_cost_usd"],
        "note": "完整统计见 trace_summary.json；逐轮值见逐轮统计.csv。未知费用不按零计。"}), "json")])
    csv_stream = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(csv_stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    paths = {"trace": docs / TRACE_NAME, "per_turn": docs / CSV_NAME,
             "summary": source.root / "trace_summary.json"}
    _atomic_text(paths["trace"], "".join(markdown))
    _atomic_text(paths["per_turn"], "\ufeff" + csv_stream.getvalue())
    _atomic_text(paths["summary"], _json(summary) + "\n")
    return {"outputs": {key: str(path) for key, path in paths.items()}, "summary": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=C.RUN)
    parser.add_argument("--docs", type=Path, default=C.DOCS)
    args = parser.parse_args()
    rendered = render(args.run, args.docs)
    print(_json({"outputs": rendered["outputs"], "model_turns": rendered["summary"]["model_turns"],
                 "actual_api_attempts": rendered["summary"]["actual_api_attempts"]}))


if __name__ == "__main__":
    main()
