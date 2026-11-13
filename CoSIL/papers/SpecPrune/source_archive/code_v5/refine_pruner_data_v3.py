"""Mechanical v3 negative refinement with separate caller/callee risk closure.

No model calls, label flips, new C labels, or writes to v1/v2/graphs occur.
Possible name, alias, nested-scope and dynamic-name relationships are explicitly
overapproximations. They are supporting exclusion evidence, not a causal graph.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict, deque
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v5 import refine_pruner_data as v2

MINER_SHA = v2.MINER_SHA
GRAPH_VERSION = v2.GRAPH_VERSION
V2_SHA = "7decc711b94dda810de8780f924ef315b8c6d7fcb0b1be560d883990a8783d33"
IntegrityError = v2.IntegrityError
canonical, digest, file_digest = v2.canonical, v2.digest, v2.file_digest
SOURCE_ERRORS = (SyntaxError, UnicodeError, LookupError, OSError, subprocess.SubprocessError)


def assert_test_unopened(data_path):
    test_path = Path(data_path).resolve() / "pruner_test.jsonl"
    marker = test_path.with_name(test_path.name + ".v5_opened_once.json")
    if marker.exists():
        raise IntegrityError("Previous test was already opened; dataset reconstruction refused: " + str(marker))


def own_nodes(function):
    pending = [function]
    while pending:
        node = pending.pop()
        if node is not function and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if not hasattr(node, "lineno") or function.lineno <= node.lineno <= function.end_lineno:
            yield node
            pending.extend(ast.iter_child_nodes(node))


def joined_pattern(left, right):
    merged = []
    for part in left + right:
        if merged and isinstance(part, str) and isinstance(merged[-1], str):
            merged[-1] += part
        elif part is None and merged and merged[-1] is None:
            continue
        else:
            merged.append(part)
    return tuple(merged)


def string_patterns(node, strings):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {(node.value,)}
    if isinstance(node, ast.Name):
        return strings.get(node.id, {(None,)})
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return {joined_pattern(a, b) for a in string_patterns(node.left, strings) for b in string_patterns(node.right, strings)}
    if isinstance(node, ast.IfExp):
        return string_patterns(node.body, strings) | string_patterns(node.orelse, strings)
    if isinstance(node, ast.JoinedStr):
        patterns = {()}
        for part in node.values:
            variants = string_patterns(part, strings) if isinstance(part, ast.Constant) else {(None,)}
            patterns = {joined_pattern(a, b) for a in patterns for b in variants}
        return patterns
    return {(None,)}


def expression_targets(node, aliases, strings):
    if isinstance(node, ast.Attribute):
        return {("leaf", node.attr)}
    if isinstance(node, ast.Name):
        return aliases.get(node.id, {("leaf", node.id)})
    if isinstance(node, ast.IfExp):
        return expression_targets(node.body, aliases, strings) | expression_targets(node.orelse, aliases, strings)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
        return {("pattern", pattern) for pattern in string_patterns(node.args[1], strings)
                if any(isinstance(part, str) and part for part in pattern)}
    return set()


def pattern_matches(pattern, name):
    return bool(any(isinstance(part, str) and part for part in pattern) and
                re.fullmatch("".join(".*" if part is None else re.escape(part) for part in pattern), name))


def summarized_calls(restored, file):
    """Monotone unions over simple local bindings, never execute Python code."""
    body = list(own_nodes(restored["node"]))
    assignments = [node for node in body if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))]
    needed = {node.func.id for node in body if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    for node in body:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
            needed.update(part.id for part in ast.walk(node.args[1]) if isinstance(part, ast.Name))
    # Only summarize variables feeding a callable alias or getattr name. Large
    # unrelated text-building expressions are outside this intentionally small
    # analysis and cannot cause irrelevant Cartesian string growth.
    changed = True
    while changed:
        changed = False
        for assignment in assignments:
            targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
            if any(isinstance(target, ast.Name) and target.id in needed for target in targets):
                dependencies = {part.id for part in ast.walk(assignment.value) if isinstance(part, ast.Name)} if assignment.value is not None else set()
                prior = len(needed)
                needed.update(dependencies)
                changed |= len(needed) != prior
    assignments = [assignment for assignment in assignments if any(isinstance(target, ast.Name) and target.id in needed for target in (assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]))]
    aliases, strings, binding_nodes = {}, {}, defaultdict(list)
    for _ in range(len(assignments) + 1):
        changed = False
        for assignment in assignments:
            value = assignment.value
            targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
            for target in targets:
                if not isinstance(target, ast.Name) or value is None:
                    continue
                possible = expression_targets(value, aliases, strings)
                patterns = string_patterns(value, strings)
                prior_alias, prior_strings = aliases.get(target.id, set()), strings.get(target.id, set())
                updated_alias, updated_strings = prior_alias | possible, prior_strings | patterns
                if len(updated_alias) > 128 or len(updated_strings) > 128:
                    raise RuntimeError("Local alias/string summary capacity exceeded; source analysis unavailable")
                changed |= updated_alias != prior_alias or updated_strings != prior_strings
                aliases[target.id], strings[target.id] = updated_alias, updated_strings
                if assignment not in binding_nodes[target.id]:
                    binding_nodes[target.id].append(assignment)
        if not changed:
            break
    calls = []
    for node in body:
        if not isinstance(node, ast.Call):
            continue
        targets = expression_targets(node.func, aliases, strings)
        if isinstance(node.func, ast.Name) and node.func.id == "getattr":
            targets |= expression_targets(node, aliases, strings)
        binding_names = {part.id for part in ast.walk(node) if isinstance(part, ast.Name)}
        bindings = [v2.ast_witness(assignment, restored["file_source"], file)
                    for name in sorted(binding_names) for assignment in binding_nodes.get(name, [])]
        for kind, target in sorted(targets, key=repr):
            calls.append({"target_kind": kind, "target": target,
                          "callsite": v2.ast_witness(node, restored["file_source"], file),
                          "local_binding_witnesses": bindings[:32], "local_binding_witness_count": len(bindings),
                          "local_binding_witnesses_truncated": len(bindings) > 32,
                          "all_local_binding_witnesses_sha256": digest(canonical(bindings)),
                          "source_full_sha256": restored["full_source_sha256"],
                          "base_blob_sha1": restored["base_blob_sha1"]})
    return calls


def provenance(fid, functions, restored):
    node = functions[fid]
    return {"function_id": fid, "file": node["file"], "full_source_sha256": node["source_sha256"],
            "complete_source_verified_in_v3": fid in restored,
            "base_blob_sha1": restored[fid]["base_blob_sha1"] if fid in restored else None,
            "basis": "verified complete base blob AST" if fid in restored else "previously validated frozen graph source identity"}


def directional_risks(functions, edges, roots, restored, calls_by_id, extra_up_seeds=None):
    """UP never consumes DOWN targets; DOWN never consumes UP caller seeds."""
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for edge in edges:
        if edge["caller"] not in functions or edge["callee"] not in functions:
            raise IntegrityError("Resolved edge identity drift")
        outgoing[edge["caller"]].append(edge)
        incoming[edge["callee"]].append(edge)
    leaf_ids, leaf_callers, pattern_callers = defaultdict(list), defaultdict(list), []
    for fid in restored:
        leaf_ids[functions[fid]["qualified_name"].rsplit(".", 1)[-1]].append(fid)
    for caller, calls in calls_by_id.items():
        for call in calls:
            if call["target_kind"] == "leaf":
                leaf_callers[call["target"]].append((caller, call))
            else:
                pattern_callers.append((caller, call))
    up, down = {}, {}
    for direction, result in (("UP", up), ("DOWN", down)):
        pending = deque()
        direction_roots = {**roots, **(extra_up_seeds or {})} if direction == "UP" else roots
        for fid, root in sorted(direction_roots.items()):
            result[fid] = {"root_function_id": fid, "parent": None, "edge": root, "direction": direction}
            pending.append(fid)
        def add(fid, parent, proof):
            if fid not in result:
                result[fid] = {"root_function_id": result[parent]["root_function_id"],
                               "parent": parent, "edge": proof, "direction": direction}
                pending.append(fid)
        while pending:
            target = pending.popleft()
            if direction == "UP":
                for edge in incoming.get(target, []):
                    add(edge["caller"], target, {"kind": "resolved_caller_ancestor", "overapproximation": False, "graph_edge": edge})
                names = {functions[target]["qualified_name"].rsplit(".", 1)[-1]}
                if names & {"__init__", "__new__"} and "." in functions[target]["qualified_name"]:
                    names.add(functions[target]["qualified_name"].rsplit(".", 1)[0].rsplit(".", 1)[-1])
                matches = [value for name in sorted(names) for value in leaf_callers.get(name, [])]
                matches += [(caller, call) for caller, call in pattern_callers if any(pattern_matches(call["target"], name) for name in names)]
                for caller, call in matches:
                    add(caller, target, {"kind": "possible_call_to_gold_or_UP_risk", "overapproximation": True,
                                         "risk_target_id": target, "possible_call": call})
            else:
                for edge in outgoing.get(target, []):
                    add(edge["callee"], target, {"kind": "resolved_callee_descendant", "overapproximation": False, "graph_edge": edge})
                for call in calls_by_id.get(target, []):
                    candidates = leaf_ids.get(call["target"], []) if call["target_kind"] == "leaf" else [fid for name, ids in leaf_ids.items() if pattern_matches(call["target"], name) for fid in ids]
                    for callee in candidates:
                        add(callee, target, {"kind": "possible_callee_of_gold_or_DOWN_risk", "overapproximation": True,
                                            "risk_caller_id": target, "possible_call": call})
    return up, down


def risk_path(fid, result, functions, restored):
    path, current = [], fid
    while current is not None:
        item = result[current]
        path.append({"node": provenance(current, functions, restored), "proof": item["edge"]})
        current = item["parent"]
    return {"direction": result[fid]["direction"], "root_function_id": result[fid]["root_function_id"],
            "path_order": "excluded candidate to risk root", "path": path,
            "overapproximation": any(value["proof"].get("overapproximation", False) for value in path)}


def restore_complete(graph, node, cache, source_file):
    """Split and parse a module once while verifying every full physical source."""
    filename = node["file"]
    if filename not in cache:
        try:
            text, definitions, blob, blob_matches = source_file(graph, filename, {})
        except (UnicodeError, LookupError):
            raise
        except ValueError as error:
            raise IntegrityError(f"Verified base blob source failed: {error}") from error
        if not blob_matches:
            raise IntegrityError("Recorded base blob differs from base_commit:path")
        inventory = v2.FunctionNodes()
        inventory.visit(ast.parse(text, filename=filename))
        cache[filename] = (text, text.splitlines(keepends=True), definitions, inventory.nodes, blob)
    text, lines, definitions, nodes, blob = cache[filename]
    start, end = node.get("def_line", node["start_line"]), node["end_line"]
    key = node["qualified_name"], start
    full = "".join(lines[start - 1:end])
    if key not in nodes or definitions.get(key) != end or node["id"] != f'{filename}::{node["qualified_name"]}@{start}':
        raise IntegrityError("Complete physical AST identity differs from frozen graph")
    if digest(full) != node["source_sha256"] or len(full) != node["source_characters"] or not full.startswith(node["source"]):
        raise IntegrityError("Complete source hash/length differs from frozen graph")
    return {"node": nodes[key], "file_source": text, "function_source": full,
            "full_source_sha256": digest(full), "base_blob_sha1": blob,
            "calls": [call for call in own_nodes(nodes[key]) if isinstance(call, ast.Call)]}


def refine_issue(iid, rows, gold, issue, graph_path, expected_graph, source_file):
    raw = graph_path.read_bytes()
    graph = json.loads(raw)
    if digest(raw) != expected_graph["graph_sha256"] or graph["audit"]["graph_version_sha256"] != GRAPH_VERSION:
        raise IntegrityError("Frozen graph hash/version drift")
    if graph["instance_id"] != iid or graph["repo"] != gold["repo"] or graph["base_commit"] != gold["base_commit"]:
        raise IntegrityError("Graph/gold identity drift")
    functions = {node["id"]: node for node in graph["functions"]}
    if len(functions) != len(graph["functions"]):
        raise IntegrityError("Duplicate graph physical function identity")
    for row in rows:
        if row["function_id"] not in functions or row["instance_id"] != iid or canonical(row["graph"]) != canonical(expected_graph) or row["repo"] != graph["repo"] or row["base_commit"] != graph["base_commit"]:
            raise IntegrityError("Candidate physical/source identity drift")
    positives, negatives = [r for r in rows if r["label"]], [r for r in rows if not r["label"]]
    def reject_all(kind, error=None):
        return positives, [{"instance_id": iid, "function_id": row["function_id"], "input_sha256": row["input_sha256"],
                            "original_row_sha256": digest(canonical(row)), "full_source_sha256": row["full_function_source_sha256"],
                            "complete_source_verified": False, "graph_sha256": expected_graph["graph_sha256"],
                            "label_sources": row["label_sources"], "reasons": [{"kind": kind, "error": error}]} for row in negatives]
    by_region = defaultdict(list)
    for fid, node in functions.items():
        by_region[(node["file"], node["qualified_name"], node.get("def_line", node["start_line"]))].append(fid)
    gold_ids = set()
    for region in gold.get("existing_gold_function_regions", []):
        matches = by_region[(region["file"], region["name"], region["def_line"])]
        if len(matches) != 1:
            raise IntegrityError("Gold physical identity unresolved")
        gold_ids.add(matches[0])
    if not gold_ids:
        return reject_all("no_base_existing_gold_function")
    roots = {fid: {"kind": "base_gold_risk_root", "overapproximation": False} for fid in gold_ids}
    for gold_id in sorted(gold_ids):
        target = functions[gold_id]
        for fid, node in functions.items():
            if fid != gold_id and node["file"] == target["file"] and target["qualified_name"].startswith(node["qualified_name"] + ".") and node["def_line"] < target["def_line"] and node["end_line"] >= target["end_line"]:
                roots[fid] = {"kind": "existing_outer_function_of_nested_gold", "overapproximation": True,
                              "nested_gold_function_id": gold_id, "nested_gold_full_source_sha256": target["source_sha256"]}
    initial_files = {functions[row["function_id"]]["file"] for row in rows} | {functions[fid]["file"] for fid in roots}
    outgoing = defaultdict(set)
    for edge in graph["edges"]:
        if edge["caller"] not in functions or edge["callee"] not in functions:
            raise IntegrityError("Resolved edge identity drift")
        outgoing[edge["caller"]].add(edge["callee"])
    # Finite expansion along existing directed successors only. Recover every
    # physical function in those files so an unqueried helper can seed UP risk.
    frontier = deque(fid for fid, node in functions.items() if node["file"] in initial_files)
    successors = set(frontier)
    while frontier:
        for target in outgoing.get(frontier.popleft(), ()):
            if target not in successors:
                successors.add(target)
                frontier.append(target)
    files = initial_files | {functions[fid]["file"] for fid in successors}
    restored, calls, file_cache = {}, {}, {}
    try:
        for fid, node in functions.items():
            if node["file"] in files:
                restored[fid] = restore_complete(graph, node, file_cache, source_file)
                try:
                    calls[fid] = summarized_calls(restored[fid], node["file"])
                except RuntimeError as error:
                    return reject_all("full_AST_alias_summary_unavailable", f"{type(error).__name__}: {error}")
    except SOURCE_ERRORS as error:
        return reject_all("required_helper_full_source_unavailable", f"{type(error).__name__}: {error}")
    # Retain the v2 dunder and precise traceback exclusions as additional UP
    # seeds, then propagate through directed ancestors without switching DOWN.
    gold_leaves = defaultdict(set)
    for fid in roots:
        gold_leaves[functions[fid]["qualified_name"].rsplit(".", 1)[-1]].add(fid)
    extra_seeds = {}
    for fid, source in (restored.items() if any(name.startswith("__") and name.endswith("__") for name in gold_leaves) else []):
        witnesses = v2.possible_dunder_calls(source, gold_leaves, functions[fid]["file"])
        if witnesses and fid not in roots:
            extra_seeds[fid] = {"kind": "possible_dunder_caller_seed", "overapproximation": True, "witnesses": witnesses}
    up, down = directional_risks(functions, graph["edges"], roots, restored, calls, extra_up_seeds=extra_seeds)
    chains = v2.traceback_chains(issue["problem_statement"], functions)
    kept, rejected = list(positives), []
    for row in negatives:
        fid, source = row["function_id"], restored[row["function_id"]]
        if source["full_source_sha256"] != row["full_function_source_sha256"] or source["function_source"][:1500] != row["function"]:
            raise IntegrityError("Candidate row complete-source hash/cut drift")
        reasons = []
        if fid in up:
            reasons.append({"kind": "directed_UP_gold_or_possible_caller_risk", **risk_path(fid, up, functions, restored)})
        if fid in down:
            reasons.append({"kind": "directed_DOWN_gold_or_possible_callee_risk", **risk_path(fid, down, functions, restored)})
        reasons.extend(v2.traceback_witnesses(fid, gold_ids, chains))
        if reasons:
            rejected.append({"instance_id": iid, "function_id": fid, "input_sha256": row["input_sha256"],
                             "original_row_sha256": digest(canonical(row)), "full_source_sha256": row["full_function_source_sha256"],
                             "verified_full_source_sha256": source["full_source_sha256"], "complete_source_verified": True,
                             "base_blob_sha1": source["base_blob_sha1"], "graph_sha256": expected_graph["graph_sha256"],
                             "label_sources": row["label_sources"], "reasons": reasons,
                             "scan_summary": {"initial_files": len(initial_files), "expanded_files": len(files), "restored_functions": len(restored), "UP_risk_functions": len(up), "DOWN_risk_functions": len(down)}})
        else:
            kept.append(row)
    return sorted(kept, key=lambda row: row["function_id"]), rejected


def validate_previous_data(path, source_stats, source_split_sha):
    assert_test_unopened(path)
    paths = {name: path / name for name in ("candidate_pool.jsonl", "negative_exclusions.jsonl", "statistics.json", "split_manifest.json", "test_file_seal.json", "human_review.jsonl", "pruner_train.jsonl", "pruner_val.jsonl", "pruner_test.jsonl", "review_failure_and_dataset_hashes.json", "review_multihop_counterexamples.json", "human_review_codex_reviewed.jsonl")}
    hashes = {name: file_digest(file) for name, file in paths.items()}
    stats, seal = json.loads(paths["statistics.json"].read_text()), json.loads(paths["test_file_seal.json"].read_text())
    if canonical(stats["seal"]) != canonical(seal) or hashes["split_manifest.json"] != source_split_sha or seal["test_performance_opened"] is not False:
        raise IntegrityError("Previous v2 seal/split/performance state drift")
    for split in ("train", "val", "test"):
        if hashes[f"pruner_{split}.jsonl"] != seal["frozen_files"][split]["sha256"] or Path(seal["frozen_files"][split]["path"]).resolve() != paths[f"pruner_{split}.jsonl"].resolve():
            raise IntegrityError("Previous v2 frozen file SHA/path drift: " + split)
    if canonical(stats["sources"]) != canonical(source_stats["sources"]) or not stats.get("original_dedup_positive_rows_unchanged"):
        raise IntegrityError("Previous v2 original source/positive eligibility drift")
    archive = json.loads(paths["review_failure_and_dataset_hashes.json"].read_text())
    for relative_path, registered in archive["protected_dataset_sha256"].items():
        file = ROOT / relative_path
        if file.parent.resolve() != path.resolve() or file.name not in hashes or hashes[file.name] != registered:
            raise IntegrityError("Previous v2 registered protected hash drift: " + relative_path)
    if archive["statistics_sha256"] != hashes["statistics.json"] or archive["counterexamples_sha256"] != hashes["review_multihop_counterexamples.json"] or archive["review_sha256"] != hashes["human_review_codex_reviewed.jsonl"]:
        raise IntegrityError("Previous v2 QC archive/statistics/review identity drift")
    if archive["label_errors"] != 5 or archive["review_count"] != 30 or stats["review"].get("passed") is not False or stats["review"].get("label_errors") != archive["label_errors"]:
        raise IntegrityError("Previous v2 actual failed QC state is not the archived five-error review")
    return paths, hashes, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-data", type=Path, default=ROOT / "results/v5_pruner/data")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v5_pruner/data_v3")
    parser.add_argument("--v1-review-results", type=Path)
    parser.add_argument("--previous-data", type=Path, default=ROOT / "results/v5_pruner/data_v2")
    parser.add_argument("--v2-review-results", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/v5-pruner/数据重构_v3与质量门.md")
    args = parser.parse_args()
    assert_test_unopened(args.source_data)
    assert_test_unopened(args.previous_data)
    if args.output.resolve() in {args.source_data.resolve(), args.previous_data.resolve()} or args.output.exists():
        parser.error("A new, nonexistent output directory is required; frozen v1 is never overwritten")
    source_paths = {name: args.source_data / name for name in ("candidate_pool.jsonl", "statistics.json", "split_manifest.json", "test_file_seal.json", "human_review.jsonl", "pruner_train.jsonl", "pruner_val.jsonl", "pruner_test.jsonl")}
    if args.v1_review_results:
        source_paths["v1_completed_review"] = args.v1_review_results
    before = {name: file_digest(path) for name, path in source_paths.items()}
    if file_digest(ROOT / "code_v5/build_pruner_data.py") != MINER_SHA:
        raise RuntimeError("Frozen miner hash changed")
    if file_digest(ROOT / "code_v5/refine_pruner_data.py") != V2_SHA:
        raise IntegrityError("Frozen v2 refiner changed")
    from code_v5 import build_pruner_data as miner
    from code_v5.verify_review_evidence import source_file
    original_stats = json.loads(source_paths["statistics.json"].read_text())
    old_seal = json.loads(source_paths["test_file_seal.json"].read_text())
    if canonical(old_seal) != canonical(original_stats["seal"]) or old_seal["test_performance_opened"] is not False:
        raise IntegrityError("Original seal/statistics identity changed or test already opened")
    for split in ("train", "val", "test"):
        sealed = old_seal["frozen_files"][split]
        path = source_paths[f"pruner_{split}.jsonl"]
        if Path(sealed["path"]).resolve() != path.resolve() or sealed["sha256"] != before[f"pruner_{split}.jsonl"]:
            raise IntegrityError("Original frozen file SHA/path mismatch: " + split)
    v1_qc = v2.v1_review_summary(original_stats, source_paths["human_review.jsonl"], args.v1_review_results)
    previous_paths, previous_hashes, previous_stats = validate_previous_data(args.previous_data, original_stats, before["split_manifest.json"])
    previous_completed = args.v2_review_results or previous_paths["human_review_codex_reviewed.jsonl"]
    previous_qc = v2.v1_review_summary(previous_stats, previous_paths["human_review.jsonl"], previous_completed)
    previous_qc["status"] = "v2_QC_failed_in_root_review"
    previous_qc["root_confirmed_error_lower_bound"] = 5
    previous_qc["error_count_is_lower_bound"] = True
    previous_qc["note"] = "Archived actual v2 review has five confirmed causal-path label errors; generic source-checker pass is not a QC signature."
    original_split = json.loads(source_paths["split_manifest.json"].read_text())
    splits = {iid: split for split, ids in original_split["splits"].items() for iid in ids}
    if [len(original_split["splits"][key]) for key in ("train", "val", "test")] != [240, 30, 30] or len(splits) != 300:
        raise ValueError("Original frozen split identity is invalid")
    raw_pool = [json.loads(line) for line in source_paths["candidate_pool.jsonl"].read_text().splitlines() if line.strip()]
    if any(type(row["label"]) is not bool or splits[row["instance_id"]] != row["split"] for row in raw_pool):
        raise ValueError("Candidate pool label/split invariant failed")
    if len({(row["instance_id"], row["function_id"]) for row in raw_pool}) != len(raw_pool):
        raise ValueError("Duplicate raw candidate physical pair")
    raw_by_pair = {(r["instance_id"], r["function_id"]): canonical(r) for r in raw_pool}
    previous_rows = [json.loads(line) for line in previous_paths["candidate_pool.jsonl"].read_text().splitlines() if line.strip()]
    if any(raw_by_pair.get((r["instance_id"], r["function_id"])) != canonical(r) for r in previous_rows) or canonical(miner.summarize(previous_rows)) != canonical(previous_stats["candidate_pool"]):
        raise IntegrityError("Previous v2 pool is not an unchanged subset of original v1 raw rows")
    if previous_stats["reconstruction_sources"]["candidate_pool.jsonl"]["sha256"] != before["candidate_pool.jsonl"] or previous_stats["refiner_sha256"] != V2_SHA:
        raise IntegrityError("Previous v2 pool source/refiner identity drift")
    del previous_rows, raw_by_pair
    original_cleaned, original_input_audit = miner.deduplicate_inputs(raw_pool)
    if canonical(miner.summarize(raw_pool)) != canonical(original_stats["candidate_pool"]) or canonical(original_input_audit) != canonical(original_stats["truncated_input_audit"]):
        raise ValueError("Raw candidate counts/original dedup audit do not match v1 statistics")
    baseline_positives = [row for row in original_cleaned if row["label"]]
    if len(baseline_positives) != original_stats["selected"]["positive"]:
        raise ValueError("Reconstructed v1 positive eligibility does not match v1 statistics")
    baseline_positive_canonical = {canonical(row) for row in baseline_positives}
    issues, issue_source = miner.read_issues(Path(original_stats["sources"]["issue_source"]["path"]), json.loads(Path(original_stats["sources"]["gold_path"]).read_text()))
    gold = json.loads(Path(original_stats["sources"]["gold_path"]).read_text())
    if file_digest(Path(original_stats["sources"]["gold_path"])) != original_stats["sources"]["gold_sha256"] or issue_source["sha256"] != original_stats["sources"]["issue_source"]["sha256"]:
        raise ValueError("Gold/benchmark issue source changed")
    grouped = defaultdict(list)
    for row in raw_pool:
        grouped[row["instance_id"]].append(row)
    refined, rejected, per_issue = [], [], {}
    for number, (iid, rows) in enumerate(sorted(grouped.items()), 1):
        graph_evidence = original_stats["sources"]["graphs"][iid]
        kept, failures = refine_issue(iid, rows, gold[iid], issues[iid], Path(graph_evidence["graph_path"]), graph_evidence, source_file)
        refined.extend(kept)
        rejected.extend(failures)
        per_issue[iid] = {"raw_pairs": len(rows), "raw_positive": sum(r["label"] for r in rows),
                          "raw_negative": sum(not r["label"] for r in rows),
                          "excluded_negative": len(failures), "remaining_negative": sum(not r["label"] for r in kept)}
        print(f"Mechanical refinement {number}/300; excluded negative pairs {len(rejected)}", flush=True)
    if {canonical(row) for row in refined if row["label"]} != {canonical(row) for row in raw_pool if row["label"]}:
        raise AssertionError("Raw positive rows changed")
    cleaned, input_audit = miner.deduplicate_inputs(refined)
    eligible = baseline_positives + [row for row in cleaned if not row["label"]]
    rows, sampling = miner.sample_rows(eligible, original_split["seed"])
    if {canonical(row) for row in rows if row["label"]} != baseline_positive_canonical:
        raise AssertionError("Original deduplicated positive eligibility/content changed")
    if len({row["input_sha256"] for row in rows}) != len(rows):
        raise AssertionError("Truncated input leakage after v3 sampling")
    if {(r["instance_id"], r["function_id"]) for r in rows} & {(r["instance_id"], r["function_id"]) for r in rejected}:
        raise AssertionError("Excluded physical negative reappeared under another source")
    if before != {name: file_digest(path) for name, path in source_paths.items()}:
        raise RuntimeError("Frozen source data changed during refinement")
    if previous_hashes != {name: file_digest(path) for name, path in previous_paths.items()}:
        raise IntegrityError("Previous frozen v2 files changed during v3 reconstruction")
    assert_test_unopened(args.source_data)
    assert_test_unopened(args.previous_data)
    args.output.mkdir(parents=True)
    (args.output / "split_manifest.json").write_bytes(source_paths["split_manifest.json"].read_bytes())
    miner.write_jsonl(args.output / "candidate_pool.jsonl", refined, immutable=True)
    miner.write_jsonl(args.output / "negative_exclusions.jsonl", rejected, immutable=True)
    sealed_files = {}
    for split in ("train", "val", "test"):
        path = args.output / f"pruner_{split}.jsonl"
        subset = [row for row in rows if row["split"] == split]
        miner.write_jsonl(path, subset, immutable=True)
        sealed_files[split] = {"path": str(path.resolve()), "sha256": file_digest(path), "count": len(subset)}
    seal = {"schema_version": 1, "dataset_version": "v3_directional_mechanical_negative_refinement",
            "test_path": sealed_files["test"]["path"], "sha256": sealed_files["test"]["sha256"],
            "test_sha256": sealed_files["test"]["sha256"], "count": sealed_files["test"]["count"],
            "split_manifest_sha256": before["split_manifest.json"], "frozen_files": sealed_files,
            "test_performance_opened": False, "old_test_rows_opened": False,
            "allowed_before_open": "provenance/count/hash audit only; no prediction performance"}
    miner.atomic_json(args.output / "test_file_seal.json", seal)
    review_samples = miner.review_samples(rows, original_split["seed"])
    miner.write_jsonl(args.output / "human_review.jsonl", review_samples, immutable=True)
    selected = miner.summarize(rows)
    p, n, e = selected.get("positive", 0), selected.get("negative", 0), selected.get("E_unique_union", 0)
    gates = {"positive_unique_pairs_ge_8000": p >= 8000, "E_unique_pairs_ge_3000": e >= 3000,
             "negative_to_positive_ratio_about_2": bool(p and 1.8 <= n / p <= 2.2),
             "E_fraction_of_negatives_ge_one_third": bool(n and e / n >= 1 / 3),
             "ordinary_D_negatives_retained": selected.get("primary_source_D", 0) > 0,
             "issue_split_disjoint_240_30_30": True, "truncated_inputs_unique_and_disjoint": True,
             "all_base_gold_regions_mapped": original_stats["quality_gates"]["all_base_gold_regions_mapped"],
             "review_30_train_E_examples_at_most_2_errors": False}
    reason_counts = Counter()
    for exclusion in rejected:
        reason_counts.update({reason["kind"] for reason in exclusion["reasons"]})
    statistics = {"schema_version": 1, "dataset_version": "v3_directional_mechanical_negative_refinement",
                  "mechanical_labels_only": True, "model_calls": 0, "training_started": False,
                  "test_performance_opened": False, "old_test_rows_opened": False,
                  "sources": deepcopy(original_stats["sources"]),
                  "source_priority": deepcopy(original_stats["source_priority"]),
                  "C_scope": original_stats["C_scope"], "E_filter": original_stats["E_filter"],
                  "BM25": deepcopy(original_stats["BM25"]),
                  "raw_counts": deepcopy(original_stats["raw_counts"]),
                  "raw_counts_scope": "unfiltered original v1 mining observations; v3 exclusions are counted separately",
                  "per_issue_mining": deepcopy(original_stats["per_issue_mining"]),
                  "reconstruction_sources": {name: {"path": str(path.resolve()), "sha256": before[name]} for name, path in source_paths.items()},
                  "refiner_sha256": file_digest(Path(__file__)),
                  "negative_filter": "drop whole D/E pairs by separate directed UP caller and DOWN callee risk closure; full AST aliases, nested gold outer roots, dynamic literal-prefix/suffix getattr, resolved graph paths, dunder and exact traceback evidence; no relabeling or graph writes",
                  "final_data_revision": True, "stop_after_v3_QC_failure": "30QC errors>2 or any nonquantity gate failure ends the current plan; no v4",
                  "previous_v2_QC": previous_qc,
                  "previous_data_sources": {name: {"path": str(path.resolve()), "sha256": previous_hashes[name]} for name, path in previous_paths.items()},
                  "previous_pool_origin_verified": True, "old_v1_v2_test_rows_opened": False,
                  "refiner_v2_sha256": V2_SHA,
                  "positive_eligibility": "original raw-pool deduplication; all original eligible positive payloads preserved byte-semantically",
                  "raw_positive_rows_unchanged": True, "original_dedup_positive_rows_unchanged": True,
                  "original_positive_count": len(baseline_positives), "candidate_pool": miner.summarize(refined),
                  "original_candidate_pool": deepcopy(original_stats["candidate_pool"]),
                  "after_truncated_input_deduplication": miner.summarize(eligible), "selected": selected,
                  "sampling": sampling, "truncated_input_audit": input_audit,
                  "original_truncated_input_audit": original_input_audit,
                  "suppressed_positive_resurrections": sum(r["label"] and canonical(r) not in baseline_positive_canonical for r in cleaned),
                  "excluded_negative_unique_pairs": len(rejected), "exclusion_reason_pair_counts": dict(reason_counts),
                  "per_issue_refinement": per_issue, "v1_QC": v1_qc,
                  "split_manifest_sha256": before["split_manifest.json"], "seal": seal,
                  "review": miner.review_gate(review_samples, None),
                  "review_family_counts": dict(Counter(r["review_family"] for r in review_samples)),
                  "quality_gates": gates, "passed": all(gates.values()),
                  "stop_reason": "Formal D2 incomplete/failed; no training authorized by this report",
                  "limitations": ["Name/alias/dynamic and dunder matches are conservative possible relationships, not runtime causal proof or real graph edges.",
                                  "UP only follows callers of gold/UP; DOWN only follows callees of gold/DOWN. A shared downstream utility never becomes an UP root.",
                                  "Source recovery scans candidate/gold files and directed resolved successor files; it is not a complete Python points-to analyzer.",
                                  "Traceback identity requires exact package path, function name and base line containment; version-drift frames may remain unmapped.",
                                  "Formal P>=8000 remains failed at the original 1542 eligible positives.",
                                  "E>=3000 with N/P=2 still leaves at most 84 D-only negatives; retained-D gate only checks nonzero coverage."]}
    miner.atomic_json(args.output / "statistics.json", statistics)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(f"# v3 有向机械负例重构与质量门\n\n正式 D2 通过：{statistics['passed']}。未训练、未调用模型、未评测 test；v1 全部保留。\n\n候选负例排除 {len(rejected)} 条；正例 {p}、负例 {n}、E {e}、D-only {selected.get('primary_source_D',0)}。原始正例及原 dedup 正例资格保持不变。\n\n排除理由按 pair 计数（可重叠）：{json.dumps(dict(reason_counts), ensure_ascii=False)}。\n\n质量门：{json.dumps(gates, ensure_ascii=False)}。新版 train 的 E 三族各10条仍待 Codex逐条证据审阅；此报告不签审阅。\n\n逐条 witness：{(args.output/'negative_exclusions.jsonl').resolve()}\n\n统计：{(args.output/'statistics.json').resolve()}\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "positive": p, "negative": n, "E": e,
                      "excluded_negative": len(rejected), "reason_counts": dict(reason_counts),
                      "quality_gates": gates, "passed": statistics["passed"]}, ensure_ascii=False), flush=True)
    return 0 if statistics["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
