"""Third offline diagnostic: compatible serialization + exact line-file scope.

The original native and compatible views are not replaced. The only extra
parsing rule is that a line-number-derived function must belong to the exact
requested file. Every sample is reparsed before the original filtering/MRR;
there is no post-hoc mask of the final rank and no gold or model invocation.
This is not a complete AST/parser repair.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import difflib
import hashlib
import inspect
import json
from pathlib import Path
import pickle
import types

from reproduction.audit_tools import Reader, write_csv
from reproduction.postprocess_compat import canonical_prediction, merge_samples, normalize_sample, raw_sources


VIEW = "offline_format_plus_requested_file_scope_diagnostic_v1"
CHECKPOINT = "5c9dca19d5f6420cf3efce615a920777f372346a"
RUNTIME_FILES = ("worker.py", "runner.py", "test_runtime.py", "requirements-runtime.txt")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clone_function(function, replacements):
    namespace = dict(function.__globals__)
    namespace.update(replacements)
    cloned = types.FunctionType(function.__code__, namespace, function.__name__,
                               function.__defaults__, function.__closure__)
    cloned.__kwdefaults__ = function.__kwdefaults__
    return cloned


def line_scope_adapter(official, mapping_events=None, context=None):
    """Compile the original line mapper with only the missing file filter added."""
    original = inspect.getsource(official.get_module_from_line_number)
    anchor = "    for nid in searcher.G.nodes():\n"
    if original.count(anchor) != 1:
        raise ValueError("Frozen upstream line mapper no longer has the expected node loop")
    addition = '        if ":" not in nid or nid.partition(":")[0] != file_path:\n            continue\n'
    patched = original.replace(anchor, anchor + addition, 1)
    namespace = dict(official.get_module_from_line_number.__globals__)
    exec(compile(patched, "<offline_requested_file_scope>", "exec"), namespace)
    strict_core = namespace["get_module_from_line_number"]
    events = mapping_events if mapping_events is not None else []
    current = context if context is not None else {}

    def scoped_mapper(line, file_path, searcher):
        node, end_line = strict_core(line, file_path, searcher)
        identity = node.get("name") if node else None
        if identity and identity.partition(":")[0] != file_path:
            raise AssertionError("Requested-file guard did not hold")
        events.append({**copy.deepcopy(current), "requested_file": file_path,
                       "requested_line": line, "mapped_entity": identity,
                       "mapped_entity_file": identity.partition(":")[0] if identity else None,
                       "mapped_start_line": node.get("start_line") if node else None,
                       "mapped_end_line": end_line, "scope_verified": bool(identity)})
        return node, end_line

    modules = clone_function(official.get_modules_from_line_numbers,
                             {"get_module_from_line_number": scoped_mapper})
    entities = clone_function(official.get_edit_entities_from_raw_locs,
                              {"get_modules_from_line_numbers": modules})
    proxy = types.SimpleNamespace(**vars(official))
    proxy.get_module_from_line_number = scoped_mapper
    proxy.get_modules_from_line_numbers = modules
    proxy.get_edit_entities_from_raw_locs = entities
    patch = "".join(difflib.unified_diff(original.splitlines(keepends=True), patched.splitlines(keepends=True),
        fromfile="upstream/get_module_from_line_number", tofile="offline_requested_file_scope/get_module_from_line_number"))
    return proxy, {"original_source": original, "patched_source": patched, "patch": patch,
        "original_source_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "patched_source_sha256": hashlib.sha256(patched.encode()).hexdigest(),
        "source_patch_sha256": hashlib.sha256(patch.encode()).hexdigest()}


def freeze_protocol(run: Path, output: Path):
    import util.process_output as official
    _, sources = line_scope_adapter(official)
    reproduction = Path(__file__).resolve().parent
    code = {name: digest(reproduction / name) for name in RUNTIME_FILES}
    code["postprocess_compat.py"] = digest(reproduction / "postprocess_compat.py")
    code["postprocess_requested_file.py"] = digest(__file__)
    code["test_postprocess_requested_file.py"] = digest(reproduction / "test_postprocess_requested_file.py")
    code["upstream/util/process_output.py"] = digest(official.__file__)
    path = output / "protocol.json"
    if path.exists():
        data = json.loads(path.read_text())
        if data.get("code_sha256") != code or data.get("source_patch_sha256") != sources["source_patch_sha256"]:
            raise ValueError("Frozen third-view code/rules changed; use a new diagnostic version/directory")
        return data
    output.mkdir(parents=True, exist_ok=True)
    previous = run / "audits/postprocess_compat"
    protected = {str(p): digest(p) for p in previous.rglob("*") if p.is_file()} if previous.exists() else {}
    data = {"view": VIEW, "rule_frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "prechange_checkpoint": CHECKPOINT, "base_view": "offline_format_compatibility_diagnostic_v1",
        "only_additional_rule": "For line-derived functions, nid must contain ':' and nid.partition(':')[0] must equal requested_file exactly",
        "replay": "Every original sample: same compatible serialization, scoped original entity parser, same function filtering and MRR",
        "not_a_complete_parser_or_ast_repair": True, "new_model_calls": 0, "gold_read": False,
        "limitations": ["Original graph node omissions remain", "Original qualified-name/class parsing remains",
                        "Compatible new-line-only suppression remains", "No final-rank masking or gold-based selection"],
        "source_patch_sha256": sources["source_patch_sha256"],
        "original_line_helper_sha256": sources["original_source_sha256"],
        "patched_line_helper_sha256": sources["patched_source_sha256"],
        "code_sha256": code, "protected_existing_compatible_files_sha256": protected}
    (output / "original_line_helper.txt").write_text(sources["original_source"], encoding="utf-8")
    (output / "requested_file_line_helper.txt").write_text(sources["patched_source"], encoding="utf-8")
    (output / "line_scope.patch").write_text(sources["patch"], encoding="utf-8")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def check_protected(protocol):
    for path, expected in protocol["protected_existing_compatible_files_sha256"].items():
        if not Path(path).is_file() or digest(path) != expected:
            raise RuntimeError(f"An existing native/compatible artifact changed: {path}")


def build_view(run: Path, output: Path):
    import util.process_output as official
    from dependency_graph import RepoEntitySearcher
    # This happens before opening manifest/raw model outputs.
    protocol = freeze_protocol(run, output)
    check_protected(protocol)
    reader = Reader()
    manifest = reader.data(run / "selection/manifest.json")
    records = manifest["records"]
    mappings, context = [], {}
    scoped, source_patch = line_scope_adapter(official, mappings, context)
    rows, predictions, transformations, errors, source_hashes = [], [], [], [], {}
    for record in records:
        iid = record["instance_id"]
        if not isinstance(iid, str) or "/" in iid or iid in {".", ".."}:
            raise ValueError("Unsafe instance ID")
        task = run / "outputs" / iid
        source_path = task / "result.json"
        result = reader.data(source_path)
        if not isinstance(result, dict) or result.get("terminal") is not True:
            predictions.append({"instance_id": iid, "terminal": False, "status": "pending", "postprocess_view": VIEW})
            rows.append({"instance_id": iid, "state": "pending"})
            continue
        source_hashes[str(source_path)] = digest(source_path)
        native = canonical_prediction(result)
        compatible = copy.deepcopy(native)
        strict = copy.deepcopy(native)
        normal_samples, strict_samples = [], []
        error = None
        mapping_start = len(mappings)
        try:
            raw_outputs = result.get("raw_output_loc", [])
            if raw_outputs:
                graph_path = run / "public/graph_index" / f"{iid}.pkl"
                receipt = reader.data(graph_path.with_suffix(".receipt.json"))
                raw_graph = graph_path.read_bytes()
                graph_hash = hashlib.sha256(raw_graph).hexdigest()
                reader.hashes[str(graph_path)] = graph_hash
                if (receipt.get("status") != "success" or not receipt.get("graph_ready")
                        or receipt.get("instance_id") != iid or receipt.get("base_commit") != record["base_commit"]
                        or receipt.get("graph_sha256") != graph_hash):
                    raise ValueError("Base graph receipt does not match this task")
                sources = raw_sources(task, result, run, reader)
                if len(sources) != len(raw_outputs):
                    raise ValueError("Cannot bind all raw outputs to their samples")
                for raw, source in zip(raw_outputs, sources):
                    # Separate graph objects prevent in-memory upstream name assignments
                    # in one view from affecting the other.
                    normal_searcher = RepoEntitySearcher(pickle.loads(raw_graph))
                    strict_searcher = RepoEntitySearcher(pickle.loads(raw_graph))
                    normal = normalize_sample(raw, normal_searcher, official, {"instance_id": iid, **source})
                    context.clear()
                    context.update({"instance_id": iid, **source,
                        "raw_line_directives": [line for line in raw.splitlines() if line.strip().startswith(("line:", "lines:"))]})
                    guarded = normalize_sample(raw, strict_searcher, scoped, {"instance_id": iid, **source})
                    if any(c["applied"] for c in guarded["changes"]) and not source["source_responses"]:
                        raise ValueError("A serialization change lacks its original response binding")
                    normal_samples.append(normal)
                    strict_samples.append(guarded)
                    transformations.extend(guarded["changes"])
                compatible = merge_samples(normal_samples, official)
                strict = merge_samples(strict_samples, scoped)
                original = run / "audits/postprocess_compat/compatible/outputs" / iid / "result.json"
                previous = reader.data(original)
                if previous and canonical_prediction(previous) != compatible:
                    raise ValueError("Fresh compatible replay differs from the preserved existing compatible view")
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
            errors.append({"instance_id": iid, "error": error})
            strict = copy.deepcopy(native)
        changed_vs_compatible = strict != compatible
        row = {"instance_id": iid, "state": "diagnostic_error" if error else "terminal",
            "changed_vs_native": strict != native, "changed_vs_compatible": changed_vs_compatible,
            "line_mapping_events": len(mappings) - mapping_start,
            "native_files": native["found_files"], "compatible_files": compatible["found_files"], "scoped_files": strict["found_files"],
            "native_functions": native["found_entities"], "compatible_functions": compatible["found_entities"],
            "scoped_functions": strict["found_entities"], "error": error}
        rows.append(row)
        value = {**copy.deepcopy(result), **strict, "postprocess_view": VIEW,
            "primary_result": False, "new_model_calls": 0, "source_inference_result_sha256": source_hashes[str(source_path)],
            "source_patch_sha256": protocol["source_patch_sha256"], "rule_frozen_at_utc": protocol["rule_frozen_at_utc"],
            "postprocess_diagnostic_error": error, "not_a_complete_parser_or_ast_repair": True,
            "resource_attribution": "Same original v2 inference; never add usage across the three offline views"}
        predictions.append(value)
        target = output / "outputs" / iid
        target.mkdir(parents=True, exist_ok=True)
        (target / "result.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if strict_samples:
            (target / "replayed_samples.json").write_text(json.dumps(strict_samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    terminal = sum(row["state"] != "pending" for row in rows)
    summary = {"view": VIEW, "status": "FINAL" if terminal == len(records) else "RUNNING_SNAPSHOT",
        "expected_tasks": len(records), "terminal_tasks": terminal,
        "changed_vs_native": sum(row.get("changed_vs_native", False) for row in rows),
        "changed_vs_compatible": sum(row.get("changed_vs_compatible", False) for row in rows),
        "line_mapping_events": len(mappings), "diagnostic_errors": errors, "read_errors": reader.errors,
        "created_utc": datetime.now(timezone.utc).isoformat(), "new_model_calls": 0, "gold_read": False,
        "true_scores_computed": False, "native_remains_primary": True,
        "not_a_complete_parser_or_ast_repair": True, "rule_frozen_at_utc": protocol["rule_frozen_at_utc"],
        "source_patch_sha256": protocol["source_patch_sha256"], "code_sha256": protocol["code_sha256"],
        "source_results_sha256": source_hashes, "source_files_sha256": reader.hashes}
    check_protected(protocol)
    for path, expected in source_hashes.items():
        if digest(path) != expected:
            raise RuntimeError("A primary inference result changed during offline replay")
    (output / "predictions.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in predictions), encoding="utf-8")
    write_csv(output / "逐题视图差异.csv", rows)
    write_csv(output / "行号映射记录.csv", mappings)
    write_csv(output / "继承的序列化转换.csv", transformations)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# 第三视图：格式归一化＋requested_file约束诊断\n\n"
        "官方native仍为主结果；既有compatible产物不覆盖。本视图不新增模型调用、不读取gold，不计算真实评分。\n\n"
        "继承compatible的两项通用序列化规则，仅为官方行号→函数映射增加严格requested_file过滤；"
        "对每个原始sample重跑官方实体处理、函数过滤和MRR，绝不对最终排名保守mask。"
        "源码差异、规则冻结时间和SHA见protocol.json与line_scope.patch；逐行映射可追溯到原response。\n\n"
        "该视图不是完整parser/AST修复：构造函数缺图、名字截断、其他类/函数处理均沿用原规则，"
        "compatible对新增line-only指令的抑制也保留。三份视图复用同一次推理，其usage不能相加。"
        "未终态任务为pending；100题冻结后再由隔离评价器统一评分，不能择优替换主结果。\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output")
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    output = Path(args.output).resolve() if args.output else run / "audits/postprocess_requested_file"
    result = freeze_protocol(run, output) if args.freeze_only else build_view(run, output)
    keys = ("view", "rule_frozen_at_utc", "source_patch_sha256") if args.freeze_only else (
        "status", "expected_tasks", "terminal_tasks", "changed_vs_native", "changed_vs_compatible", "line_mapping_events", "diagnostic_errors")
    print(json.dumps({key: result[key] for key in keys}, ensure_ascii=False))


if __name__ == "__main__":
    main()
