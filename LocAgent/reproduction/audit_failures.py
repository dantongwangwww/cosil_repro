"""Read-only failure/output audit, with a separate post-terminal gold layer.

Default analysis never opens private/ or uses target identities.  It replays the
unchanged upstream postprocessing helpers only for attribution, never rewrites
native rankings, graphs, results, tool schemas, or model requests.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import pickle
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUEST_ERRORS = {"api_error", "transport_error", "protocol_error", "parse_error"}
DIRECTIVE_PREFIXES = ("function:", "method:", "class:", "variable:", "variables:", "line:", "lines:")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, bindings):
    raw = Path(path).read_bytes()
    bindings[str(Path(path).resolve())] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def empty_fence(text):
    return bool(re.fullmatch(r"\s*```(?:[A-Za-z0-9_+-]+)?[ \t]*\r?\n?[ \t\r\n]*```\s*", text or ""))


def inline_identities(text):
    found = []
    for line in (text or "").splitlines():
        match = re.fullmatch(r"\s*(?:[-*]\s*)?([\w./-]+\.py):(?::)?([\w.]+)(?:\(\))?\s*", line)
        if match:
            found.append(match.group(1) + ":" + match.group(2))
    return found


def file_of(entity):
    return entity.split(":", 1)[0] if isinstance(entity, str) and ":" in entity else None


def numbers_from_directive(directive, file_content):
    """The upstream line-number lexical interpretation, without changing it."""
    loc = ":".join(directive.split(":")[1:]).strip().split(":")[1].strip()
    matches = re.findall(r"\s*(\d+)(?:-(\d+))?", loc)
    numbers = []
    for start, end in matches:
        lo = max(1, int(start))
        hi = min(len(file_content.splitlines()), int(end) if end else lo)
        numbers.extend(range(lo, hi + 1))
    if not matches and loc.split():
        try:
            numbers.append(int(loc.split()[0].strip()))
        except ValueError:
            pass
    return sorted(set(numbers))


def line_attribution(run, iid, result, bindings):
    """Trace upstream mappings using public graph/raw output; no gold access."""
    from dependency_graph.traverse_graph import RepoEntitySearcher
    from util.process_output import (get_edit_entities_from_raw_locs,
                                     get_modules_from_line_numbers, parse_raw_loc_output)
    graph_path = run / "public/graph_index" / (iid + ".pkl")
    receipt_path = graph_path.with_suffix(".receipt.json")
    receipt = read(receipt_path, bindings)
    if receipt.get("status") != "success" or sha(graph_path) != receipt.get("graph_sha256"):
        raise ValueError("Public graph cannot be attributed without its exact successful SHA")
    bindings[str(graph_path.resolve())] = receipt["graph_sha256"]
    with graph_path.open("rb") as handle:
        graph = pickle.load(handle)
    searcher = RepoEntitySearcher(graph)
    valid_files = [node["name"] for node in searcher.get_all_nodes_by_type("file")]
    raw_outputs = result.get("raw_output_loc", [])
    sample_outputs = [s for s in result.get("samples", []) if s.get("raw_location")]
    native_per_sample = result.get("official_per_sample_found_entities", [])
    native_audits = result.get("official_postprocessing_audit", [])
    samples, mappings = [], []
    entity_support = defaultdict(lambda: {"cross_file": False, "legitimate": False, "uncertain": False})
    for index, raw in enumerate(raw_outputs):
        parsed_files, directives = parse_raw_loc_output(raw, valid_files)
        item = {"raw_location_index": index, "sample": sample_outputs[index].get("sample") if index < len(sample_outputs) else None,
                "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "parsed_valid_files": parsed_files, "directives": directives,
                "inline_identity_lines": inline_identities(raw), "empty_code_fence": empty_fence(raw),
                "attribution_errors": []}
        if index < len(native_audits):
            saved = native_audits[index]
            item["saved_parser_projection_matches"] = (saved.get("parsed_valid_file_candidates") == parsed_files
                and saved.get("parsed_location_directives") == directives)
        named = [d for d in directives if not ":".join(d.split(":")[1:]).strip().startswith(("line:", "lines:"))]
        try:
            explicit = set(get_edit_entities_from_raw_locs(named, searcher)) if named else set()
        except Exception as error:
            explicit = set()
            item["attribution_errors"].append("named-directive replay: " + repr(error))
        cross, same = set(), set()
        for directive in directives:
            loc = ":".join(directive.split(":")[1:]).strip()
            if not loc.startswith(("line:", "lines:")):
                continue
            requested_file = directive.split(":", 1)[0]
            if not searcher.has_node(requested_file):
                continue
            try:
                line_numbers = numbers_from_directive(directive, graph.nodes[requested_file]["code"])
                # Exact official helper; it currently lacks the source-file constraint.
                modules = get_modules_from_line_numbers(line_numbers, requested_file, searcher)
                for module in modules:
                    if module.get("type") != "function":
                        continue
                    entity = module["name"]
                    crossing = file_of(entity) != requested_file
                    (cross if crossing else same).add(entity)
                    mappings.append({"instance_id": iid, "raw_location_index": index,
                        "sample": item["sample"], "directive": directive,
                        "requested_file": requested_file, "mapped_entity": entity,
                        "mapped_file": file_of(entity), "cross_file": crossing})
            except Exception as error:
                item["attribution_errors"].append("line-directive replay: " + repr(error))
        candidates = native_per_sample[index] if index < len(native_per_sample) else []
        legitimate = explicit | same
        only_cross = set(candidates) & cross - legitimate
        uncertain = set(candidates) - cross - legitimate
        item.update(native_function_candidates=candidates,
                    explicit_or_same_file_supported=sorted(set(candidates) & legitimate),
                    cross_file_line_derived=sorted(set(candidates) & cross),
                    only_cross_file_line_derived=sorted(only_cross),
                    attribution_uncertain_entities=sorted(uncertain))
        for entity in candidates:
            entity_support[entity]["cross_file"] |= entity in cross
            entity_support[entity]["legitimate"] |= entity in legitimate
            entity_support[entity]["uncertain"] |= entity in uncertain or bool(item["attribution_errors"])
        samples.append(item)
    final_entities = result.get("found_entities", [])
    only_cross_final = [e for e in final_entities if e in entity_support
                        and entity_support[e]["cross_file"] and not entity_support[e]["legitimate"]
                        and not entity_support[e]["uncertain"]]
    any_cross_final = [e for e in final_entities if entity_support.get(e, {}).get("cross_file")]
    if sha(graph_path) != receipt["graph_sha256"]:
        raise ValueError("Read-only attribution changed the graph pickle")
    return {"samples": samples, "line_mappings": mappings,
            "final_entities_with_cross_file_line_contribution": any_cross_final,
            "final_entities_supported_only_by_cross_file_line_mapping": only_cross_final}


def classify(result, attribution):
    statuses = [s.get("status", "UNKNOWN") for s in result.get("samples", [])]
    flags = set()
    for status in statuses:
        if status in REQUEST_ERRORS:
            flags.add("request_or_protocol_error")
        elif status in ("context_limit", "step_limit", "timeout", "empty_output", "worker_error"):
            flags.add(status)
    raw = result.get("raw_output_loc", [])
    if any(empty_fence(text) for text in raw): flags.add("finish_empty_code_fence")
    if any(inline_identities(text) for text in raw): flags.add("inline_path_entity_format")
    if result.get("error") and raw: flags.add("postprocessing_exception_or_worker_error_after_raw_output")
    if attribution.get("final_entities_with_cross_file_line_contribution"):
        flags.add("upstream_cross_file_line_mapping_in_final_rank")
    parsed = attribution.get("samples", [])
    if any(s["attribution_errors"] for s in parsed): flags.add("attribution_uncertain")
    def function_directives(sample):
        locs = [":".join(d.split(":")[1:]).strip() for d in sample["directives"]]
        return any(loc.startswith(("function:", "method:", "line:", "lines:"))
                   or (loc.startswith("class:") and "." in loc.split(":", 1)[-1]) for loc in locs)
    if any(function_directives(s) and not s["native_function_candidates"] for s in parsed):
        flags.add("entity_directives_unresolved_or_filtered")
    has_functions, has_files = bool(result.get("found_entities")), bool(result.get("found_files"))
    if has_functions:
        primary = "native_function_output_gold_not_assessed"
    elif result.get("error") and raw:
        primary = "postprocessing_exception_after_raw_output"
    elif raw and all(empty_fence(text) for text in raw):
        primary = "finish_contains_only_empty_code_fence"
    elif not has_files and raw and any(s["inline_identity_lines"] for s in parsed) and not any(s["parsed_valid_files"] for s in parsed):
        primary = "inline_path_entity_format_discarded_by_native_parser"
    elif has_files and any(function_directives(s) for s in parsed):
        primary = "file_output_but_function_directives_unresolved_or_filtered"
    elif has_files:
        primary = "file_output_without_usable_function_directives"
    elif raw:
        primary = "nonempty_raw_output_but_no_native_candidates"
    elif "request_or_protocol_error" in flags:
        primary = "request_or_protocol_failure_without_prediction"
    elif flags & {"context_limit", "step_limit", "timeout"}:
        primary = "resource_or_turn_limit_without_prediction"
    elif result.get("controller_created_terminal"):
        primary = "controller_or_environment_terminal_without_prediction"
    else:
        primary = "no_raw_localization_output_reason_in_record"
    return primary, sorted(flags), statuses


def score_layer(run, rows, results, bindings):
    """Separate offline gold read, strictly after the complete terminal barrier."""
    if not rows or any(row.get("terminal") is not True for row in rows):
        raise ValueError("Gold scoring audit requires all frozen tasks to be terminal")
    from reproduction.evaluate import frozen_evaluator, identity_item
    evaluator, evaluator_path = frozen_evaluator()
    bindings[str(evaluator_path)] = sha(evaluator_path)
    gold = read(run / "private/gold.json", bindings)
    inventory = read(run / "private/inventory.json", bindings)
    if set(gold) != {r["instance_id"] for r in rows} or set(inventory) != set(gold):
        raise ValueError("Offline scoring rosters differ")
    native_hits, masked_hits = Counter(), Counter()
    influenced_hits, dependent_hits = Counter(), Counter()
    output = []
    for row in rows:
        iid = row["instance_id"]
        g, inv = gold[iid], inventory[iid]
        result = results[iid]
        raw_functions = [identity_item(e) for e in result.get("found_entities", [])]
        slots = evaluator.slots(raw_functions, inv["function_identities"], functions=True)
        convert = lambda e: e.replace(":", "::", 1) if "::" not in e else e
        unsupported = {convert(e) for e in row["final_entities_supported_only_by_cross_file_line_mapping"]}
        any_cross = {convert(e) for e in row["final_entities_with_cross_file_line_contribution"]}
        masked = [None if entity in unsupported else entity for entity in slots]
        metrics, masked_metrics = {}, {}
        for k in (1, 3, 5):
            metrics[str(k)] = evaluator.scores(slots, g["targets"], k)
            masked_metrics[str(k)] = evaluator.scores(masked, g["targets"], k)
            hit, masked_hit = metrics[str(k)]["hit"], masked_metrics[str(k)]["hit"]
            native_hits[str(k)] += hit
            masked_hits[str(k)] += masked_hit
            influenced_hits[str(k)] += bool(set(slots[:k]) & set(g["targets"]) & any_cross)
            dependent_hits[str(k)] += bool(hit and not masked_hit)
        output.append({"instance_id": iid, "native_function_scores": metrics,
                       "only_cross_file_entity_masked_scores_preserving_original_slots": masked_metrics,
                       "native_slots": slots, "unsupported_cross_file_slots": sorted(unsupported),
                       "nonhit_with_nonempty_valid_native_functions": any(slots) and not metrics["5"]["hit"],
                       "normal_nonhit_without_observed_runtime_or_parser_flags": any(slots)
                           and not metrics["5"]["hit"] and not row["flags"]})
    return {"scope": "separate offline gold-scoring diagnostics after all terminals",
            "allocated": len(rows), "native_hit_numerators": dict(native_hits),
            "native_hits_with_any_cross_file_gold_contribution": dict(influenced_hits),
            "native_hits_depending_on_only_cross_file_supported_entities": dict(dependent_hits),
            "masked_hit_numerators_preserving_original_slots": dict(masked_hits),
            "counterfactual_note": "Diagnostic only, not corrected method results. Mask unsupported cross-file entities in-place; no reranking/backfill. MRR rank changes from mixed legitimate/cross-file support remain uncertain.",
            "records": output, "native_predictions_changed": False}


def analyze(run, out, *, include_scoring=False):
    run, out = Path(run).resolve(strict=True), Path(out).absolute()
    if out.exists(): raise FileExistsError("Never overwrite an earlier audit snapshot")
    bindings = {str(Path(__file__).resolve()): sha(__file__)}
    manifest = read(run / "selection/manifest.json", bindings)
    rows, all_samples, all_mappings, results = [], [], [], {}
    for record in manifest["records"]:
        iid = record["instance_id"]
        path = run / "outputs" / iid / "result.json"
        row = {"instance_id": iid, "terminal": False,
               "primary_category": "running" if (path.parent / "controller_started.json").exists() else "not_started",
               "status": None, "execution_status": None, "flags": [], "sample_statuses": [],
               "native_files": 0, "native_modules": 0, "native_functions": 0,
               "final_entities_with_cross_file_line_contribution": [],
               "final_entities_supported_only_by_cross_file_line_mapping": []}
        if path.is_file():
            result = read(path, bindings)
            if result.get("terminal") is True:
                if any(result.get(k) != record[k] for k in ("instance_id", "repo", "base_commit")):
                    raise ValueError("Runtime task identity mismatch: " + iid)
                attribution = line_attribution(run, iid, result, bindings) if result.get("raw_output_loc") else {"samples": [], "line_mappings": []}
                primary, flags, statuses = classify(result, attribution)
                row.update(terminal=True, primary_category=primary, flags=flags, sample_statuses=statuses,
                           status=result.get("status"), execution_status=result.get("execution_status"),
                           native_files=len(result.get("found_files", [])),
                           native_modules=len(result.get("found_modules", [])),
                           native_functions=len(result.get("found_entities", [])),
                           final_entities_with_cross_file_line_contribution=attribution.get("final_entities_with_cross_file_line_contribution", []),
                           final_entities_supported_only_by_cross_file_line_mapping=attribution.get("final_entities_supported_only_by_cross_file_line_mapping", []))
                all_mappings.extend(attribution["line_mappings"])
                for item in attribution["samples"]:
                    all_samples.append({"instance_id": iid, **item})
                results[iid] = result
        rows.append(row)
    scoring_bindings = dict(bindings)
    scoring = score_layer(run, rows, results, scoring_bindings) if include_scoring else None
    if scoring is not None:
        scoring["source_sha256"] = scoring_bindings
    for relative in ("util/process_output.py", "dependency_graph/traverse_graph.py", "reproduction/worker.py"):
        path = ROOT / relative
        bindings[str(path)] = sha(path)
    terminal_rows = [r for r in rows if r["terminal"]]
    report = {"scope": "gold-free execution/output provenance audit", "created_utc": datetime.now(timezone.utc).isoformat(),
              "status": "FINAL_TERMINALS" if len(terminal_rows) == len(rows) else "PARTIAL_INFERENCE_CONTINUES",
              "allocated": len(rows), "terminal": len(terminal_rows),
              "execution_statuses": dict(Counter(r["status"] for r in terminal_rows)),
              "primary_categories": dict(Counter(r["primary_category"] for r in rows)),
              "mechanism_flags_overlapping": dict(Counter(flag for r in terminal_rows for flag in r["flags"])),
              "tasks_with_cross_file_line_mapping": len({m["instance_id"] for m in all_mappings if m["cross_file"]}),
              "distinct_issue_cross_file_entities": len({(m["instance_id"], m["mapped_entity"]) for m in all_mappings if m["cross_file"]}),
              "distinct_sample_cross_file_entities": len({(m["instance_id"], m["raw_location_index"], m["mapped_entity"]) for m in all_mappings if m["cross_file"]}),
              "tasks_with_final_cross_file_line_contribution": sum(bool(r["final_entities_with_cross_file_line_contribution"]) for r in rows),
              "distinct_final_cross_file_entities": sum(len(set(r["final_entities_with_cross_file_line_contribution"])) for r in rows),
              "tasks_with_final_only_cross_file_supported_entities": sum(bool(r["final_entities_supported_only_by_cross_file_line_mapping"]) for r in rows),
              "distinct_final_only_cross_file_supported_entities": sum(len(set(r["final_entities_supported_only_by_cross_file_line_mapping"])) for r in rows),
              "records": rows, "gold_read_for_this_report": False,
              "classification_limit": "Execution failed is not a localization miss; execution complete does not imply usable predictions; no normal-nonhit claim is made without the separate gold layer.",
              "source_sha256": bindings}
    out.mkdir(parents=True)
    (out / "gold_free_analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if scoring is not None:
        (out / "offline_gold_scoring_diagnostics.json").write_text(json.dumps(scoring, ensure_ascii=False, indent=2) + "\n")
    for name, data in (("per_issue.csv", rows), ("per_sample.csv", all_samples), ("line_mapping.csv", all_mappings)):
        with (out / name).open("w", encoding="utf-8-sig", newline="") as handle:
            fields = list(dict.fromkeys(key for item in data for key in item))
            if fields:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in item.items()} for item in data)
    lines = ["# 定位运行与原生输出审计", "", f"固定任务{len(rows)}道，当前终态{len(terminal_rows)}道；状态：{report['status']}。",
             "", "本报告默认不读金标，不以运行失败代替定位未命中，也不把complete状态当作非空有效预测。原生parser、图和预测未修改。", "",
             "| 分类（互斥） | 题数 |", "|---|---:|"]
    lines.extend(f"| {key} | {count} |" for key, count in report["primary_categories"].items())
    lines += ["", "多标签原因可重叠，详见JSON；不能将各原因数直接相加。", "",
              f"检测到行号跨文件映射的任务{report['tasks_with_cross_file_line_mapping']}道，独立样本—跨文件实体对{report['distinct_sample_cross_file_entities']}个。",
              f"最终排名含跨文件行号贡献{report['tasks_with_final_cross_file_line_contribution']}道；包含仅依赖跨文件行号派生实体{report['tasks_with_final_only_cross_file_supported_entities']}道。",
              "跨文件派生不是模型在结构化输出中明确选中了该文件下的函数；混合多样本支持与MRR名次影响须保留不确定性。",
              "", "逐题、逐样本和逐行号映射证据分别见per_issue.csv、per_sample.csv、line_mapping.csv。",
              "正常非命中仅在全题终态后的单独gold评分层判断；该评分层不会修正主native结果。"]
    (out / "运行失败与输出机制_草表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--include-scoring", action="store_true")
    args = parser.parse_args()
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    logging.getLogger().setLevel(logging.ERROR)
    result = analyze(args.run_dir, args.output_dir, include_scoring=args.include_scoring)
    print(json.dumps({k: result[k] for k in ("status", "allocated", "terminal", "primary_categories",
          "tasks_with_cross_file_line_mapping", "tasks_with_final_only_cross_file_supported_entities")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
