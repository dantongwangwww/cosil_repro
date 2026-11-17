"""Gold-blind offline serialization compatibility view; native scores stay primary.

Only graph-verified ``path.py[:|::]QualifiedName`` lines and an existing
top-level Python file's carrier are repaired. The official entity parser,
function filtering and MRR merge remain the same. No worker code is imported
or modified, and no model, network, gold, patch or scoring is used.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pickle
import re
import types

from reproduction.audit_tools import Reader, write_csv


VIEW = "offline_format_compatibility_diagnostic_v1"
ONE_LINE = re.compile(r"(?P<path>[^:\r\n]+\.py)(?P<separator>::?)(?P<qualified>[^\s:]+)")


def canonical_prediction(value):
    return {key: value.get(key, []) for key in ("found_files", "found_modules", "found_entities")}


def make_parser(official, valid_files):
    """Reuse the official parser code with only its top-level-file extractor fixed."""
    valid = set(valid_files)
    original = official.extract_python_file_path
    def extract(line, folders):
        found = original(line, folders)
        if found is not None:
            return found
        match = re.search(r"[\w\./-]+\.py", line)
        candidate = match.group(0) if match else None
        return candidate if candidate in valid and "/" not in candidate else None
    namespace = dict(official.parse_raw_loc_output.__globals__)
    namespace["extract_python_file_path"] = extract
    parser = types.FunctionType(official.parse_raw_loc_output.__code__, namespace,
        official.parse_raw_loc_output.__name__, official.parse_raw_loc_output.__defaults__,
        official.parse_raw_loc_output.__closure__)
    return parser, extract


def normalize_sample(raw: str, searcher, official, source: dict):
    valid_files = [node["name"] for node in searcher.get_all_nodes_by_type(official.NODE_TYPE_FILE)]
    valid = set(valid_files)
    parser, extractor = make_parser(official, valid_files)
    normalized, origins, changes = [], [], []
    for number, original in enumerate(raw.splitlines(), 1):
        line = original.strip()
        match = ONE_LINE.fullmatch(line)
        replacement = [original]
        if match:
            file, qualified = match.group("path"), match.group("qualified")
            identity = f"{file}:{qualified}"
            if file in valid and searcher.has_node(identity):
                data = searcher.get_node_data([identity])[0]
                kind = data.get("type")
                if kind in {official.NODE_TYPE_FUNCTION, official.NODE_TYPE_CLASS}:
                    label = "function" if kind == official.NODE_TYPE_FUNCTION else "class"
                    proposed = [file, f"{label}: {qualified}"]
                    # The official parser truncates some three-part names.
                    # Refuse that conversion instead of changing model identity.
                    identity_preserved = True
                    if kind == official.NODE_TYPE_FUNCTION:
                        resolved = official.get_edit_entities_from_raw_locs(
                            [f"{file}:function: {qualified}"], searcher, include_variable=False)
                        identity_preserved = resolved == [identity]
                    if identity_preserved:
                        replacement = proposed
                    changes.append({**source, "source_line": number, "original_line": original,
                        "new_lines": proposed if identity_preserved else [original],
                        "graph_identity": identity, "graph_entity_type": kind,
                        "rule": "exact_graph_verified_single_line_entity",
                        "applied": identity_preserved,
                        "reason": "serialization only" if identity_preserved else "official entity parser cannot preserve exact qualified identity"})
        for rewritten in replacement:
            normalized.append(rewritten)
            origins.append((number, original))
    rendered = "\n".join(normalized) if any(change["applied"] for change in changes) else raw
    folders = list(dict.fromkeys(file.split("/")[0] for file in valid_files))
    for line, (number, original) in zip(normalized, origins):
        stripped = line.strip().strip(":").strip()
        if (stripped.endswith(".py") and official.extract_python_file_path(stripped, folders) is None
                and extractor(stripped, folders) in valid):
            file = extractor(stripped, folders)
            changes.append({**source, "source_line": number, "original_line": original,
                "new_lines": [stripped], "graph_identity": file, "graph_entity_type": "file",
                "rule": "existing_top_level_python_file_carrier", "applied": True,
                "reason": "recognize an exact existing top-level file; no spelling/path correction"})
    native_files, native_locations = official.parse_raw_loc_output(raw, valid_files)
    found_files, locations = parser(rendered, valid_files)
    eligible = []
    suppressed = []
    for location in locations:
        directive = ":".join(location.split(":")[1:]).strip()
        if directive.startswith(("line:", "lines:")) and location not in native_locations:
            suppressed.append(location)
        else:
            eligible.append(location)
    entities = official.get_edit_entities_from_raw_locs(eligible, searcher, include_variable=False)
    functions, modules = [], []
    # This is the unchanged filtering/order rule in get_loc_results_from_raw_outputs.
    for entity in entities:
        if not searcher.has_node(entity):
            continue
        data = searcher.get_node_data([entity])[0]
        if data["type"] == official.NODE_TYPE_FUNCTION:
            functions.append(entity)
        module = ".".join(entity.split(".")[:-1]) if "." in entity.split(":")[-1] else entity
        if searcher.has_node(module) and module not in modules:
            modules.append(module)
    return {"rendered": rendered, "found_files": found_files, "found_modules": modules,
            "found_entities": functions, "changes": changes,
            "new_line_only_directives_suppressed": suppressed}


def merge_samples(samples, official):
    if not samples:
        return {"found_files": [], "found_modules": [], "found_entities": []}
    per = [[sample[key] for sample in samples] for key in ("found_files", "found_modules", "found_entities")]
    merged = official.merge_sample_locations(*per, ranking_method="mrr")
    return dict(zip(("found_files", "found_modules", "found_entities"), merged))


def raw_sources(task: Path, result: dict, run: Path, reader: Reader):
    sources = []
    for sample in result.get("samples", []):
        raw = sample.get("raw_location")
        if not raw:
            continue
        number = sample.get("sample")
        sample_dir = task / "samples" / f"sample_{number:02d}"
        references = []
        for path in sorted((sample_dir / "requests").glob("*_response.txt")):
            response = reader.data(path)
            choices = response.get("choices") if isinstance(response, dict) else None
            if not choices:
                continue
            message = choices[0].get("message", {})
            for tool in message.get("tool_calls") or []:
                function = tool.get("function", {})
                if function.get("name") != "finish":
                    continue
                try:
                    args = json.loads(function.get("arguments", "{}"))
                except (TypeError, json.JSONDecodeError):
                    continue
                payload = next(iter(args.values()), None) if isinstance(args, dict) else None
                if isinstance(payload, str) and payload and payload in raw:
                    references.append(str(path.relative_to(run)))
        sources.append({"sample": number, "source_responses": references, "raw_location_sha256": hashlib.sha256(raw.encode()).hexdigest()})
    return sources


def build_views(run: Path, output: Path):
    import util.process_output as official
    from dependency_graph import RepoEntitySearcher
    reader = Reader()
    manifest = reader.data(run / "selection/manifest.json")
    records = manifest["records"]
    graph_dir = run / "public/graph_index"
    official.GRAPH_INDEX_DIR = str(graph_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows, changes, native_rows, compatible_rows, failures = [], [], [], [], []
    source_results = {}
    for record in records:
        iid = record["instance_id"]
        if not isinstance(iid, str) or "/" in iid or iid in {".", ".."}:
            raise ValueError("Unsafe instance ID in frozen manifest")
        task = run / "outputs" / iid
        result_path = task / "result.json"
        result = reader.data(result_path)
        if not isinstance(result, dict) or result.get("terminal") is not True:
            pending = {"instance_id": iid, "terminal": False, "status": "pending", "postprocess_view": VIEW}
            native_rows.append({**pending, "view": "native"})
            compatible_rows.append({**pending, "view": "compatible"})
            rows.append({"instance_id": iid, "state": "pending"})
            continue
        source_results[str(result_path)] = reader.hashes[str(result_path)]
        native = canonical_prediction(result)
        compatible = copy.deepcopy(native)
        applied, refused, suppressed = [], [], []
        normalized_samples = []
        raw_outputs = result.get("raw_output_loc", [])
        error = None
        try:
            if raw_outputs:
                graph_path = graph_dir / f"{iid}.pkl"
                receipt = reader.data(graph_dir / f"{iid}.receipt.json")
                graph_raw = graph_path.read_bytes()
                digest = hashlib.sha256(graph_raw).hexdigest()
                reader.hashes[str(graph_path)] = digest
                if (receipt.get("status") != "success" or not receipt.get("graph_ready")
                        or receipt.get("instance_id") != iid or receipt.get("base_commit") != record["base_commit"]
                        or receipt.get("graph_sha256") != digest):
                    raise ValueError("Graph receipt identity/digest is not valid")
                graph = pickle.loads(graph_raw)
                searcher = RepoEntitySearcher(graph)
                original_per_sample = official.get_loc_results_from_raw_outputs(iid, raw_outputs)
                original_merged = official.merge_sample_locations(*original_per_sample, ranking_method="mrr")
                recomputed = dict(zip(("found_files", "found_modules", "found_entities"), original_merged))
                if recomputed != native:
                    raise ValueError("Official native recomputation differs from the frozen result; refusing a diagnostic replacement")
                sources = raw_sources(task, result, run, reader)
                if len(sources) != len(raw_outputs):
                    raise ValueError("Cannot bind every raw output to its original sample")
                for raw, source in zip(raw_outputs, sources):
                    normalized = normalize_sample(raw, searcher, official, {"instance_id": iid, **source})
                    if any(change["applied"] for change in normalized["changes"]) and not source["source_responses"]:
                        raise ValueError("A proposed serialization repair cannot be bound to its original model response")
                    normalized_samples.append(normalized)
                    applied.extend(change for change in normalized["changes"] if change["applied"])
                    refused.extend(change for change in normalized["changes"] if not change["applied"])
                    suppressed.extend(normalized["new_line_only_directives_suppressed"])
                compatible = merge_samples(normalized_samples, official)
                if not applied and compatible != native:
                    raise ValueError("A compliant output changed without an allowed serialization repair")
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
            failures.append({"instance_id": iid, "error": error})
            compatible = copy.deepcopy(native)
        changes.extend(applied + refused)
        row = {"instance_id": iid, "state": "diagnostic_error" if error else "terminal",
            "prediction_changed": compatible != native, "applied_transforms": len(applied),
            "refused_transforms": len(refused), "new_line_only_directives_suppressed": suppressed,
            "native_files": native["found_files"], "compatible_files": compatible["found_files"],
            "native_functions": native["found_entities"], "compatible_functions": compatible["found_entities"],
            "error": error}
        rows.append(row)
        native_view = {**copy.deepcopy(result), "postprocess_view": "native_frozen_primary",
                       "source_inference_result_sha256": source_results[str(result_path)], "new_model_calls": 0}
        compatible_view = {**copy.deepcopy(result), **compatible,
            "postprocess_view": VIEW, "primary_result": False,
            "source_inference_result_sha256": source_results[str(result_path)],
            "postprocess_diagnostic_error": error, "new_model_calls": 0,
            "resource_attribution": "Reuses exactly the same v2 inference; do not add native and compatible usage together"}
        native_rows.append(native_view)
        compatible_rows.append(compatible_view)
        for view, value in (("native", native_view), ("compatible", compatible_view)):
            target = output / view / "outputs" / iid
            target.mkdir(parents=True, exist_ok=True)
            (target / "result.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        if normalized_samples:
            target = output / "compatible" / "outputs" / iid
            (target / "normalized_samples.json").write_text(json.dumps(normalized_samples, ensure_ascii=False, indent=2) + "\n")
    terminal = sum(row["state"] != "pending" for row in rows)
    data = {"view": VIEW, "status": "FINAL" if terminal == len(records) else "RUNNING_SNAPSHOT",
        "created_utc": datetime.now(timezone.utc).isoformat(), "expected_tasks": len(records), "terminal_tasks": terminal,
        "changed_tasks": sum(row.get("prediction_changed", False) for row in rows),
        "applied_transforms": sum(row.get("applied_transforms", 0) for row in rows),
        "refused_transforms": sum(row.get("refused_transforms", 0) for row in rows),
        "diagnostic_failures": failures, "read_errors": reader.errors,
        "new_model_calls": 0, "gold_read": False, "true_scores_computed": False,
        "native_remains_primary": True, "source_results_sha256": source_results,
        "source_files_sha256": reader.hashes, "analysis_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "official_postprocess_sha256": hashlib.sha256(Path(official.__file__).read_bytes()).hexdigest(),
        "constraints": ["No spelling/path correction", "No class-to-function expansion", "No new line-only inferred functions", "Same official entity filtering and MRR", "No choosing a view based on scores"]}
    for name, values in (("native_predictions.jsonl", native_rows), ("compatible_predictions.jsonl", compatible_rows)):
        (output / name).write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))
    write_csv(output / "逐题视图差异.csv", rows)
    write_csv(output / "逐转换记录.csv", changes)
    (output / "summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    (output / "README.md").write_text(
        "# 离线格式归一化诊断\n\n"
        "官方native预测仍是主结果；compatible仅诊断通用序列化损失，不构成新增模型实验。\n\n"
        "仅识别图中严格存在的顶层Python文件，以及整行path.py:QualifiedName/path.py::QualifiedName；"
        "不改拼写、路径或排序，不扩展类为函数，不根据金标、补丁或行号添加新函数。"
        "原本合规的输出须与native逐项一致，仍使用官方实体处理、过滤及MRR。\n\n"
        "逐转换记录保存原行、新行、原始response引用和图身份。原始结果只读，"
        "两份视图复用同一批v2推理及费用，不能将其usage相加；未终态标pending。"
        "此模块不读取private/gold，也不计算真实定位分数；待100题终态后，须由隔离评价器分别评分。\n",
        encoding="utf-8")
    for path, digest in source_results.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise RuntimeError("A frozen source result changed during offline analysis")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    output = Path(args.output).resolve() if args.output else run / "audits/postprocess_compat"
    result = build_views(run, output)
    print(json.dumps({key: result[key] for key in ("status", "expected_tasks", "terminal_tasks", "changed_tasks", "applied_transforms", "refused_transforms", "diagnostic_failures")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
