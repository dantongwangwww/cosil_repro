"""Add readable, verified candidate/gold callsites to a train-only QC report.

This is supporting evidence for Codex review. It never signs reviews, updates
statistics, changes labels, or opens pruner test rows. Dynamic name matches are
explicitly possible calls, not invented graph edges or positive labels.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import copy
import json
from pathlib import Path

from code_v5.refine_pruner_data import (FunctionNodes, possible_dunder_calls,
                                       traceback_chains, traceback_witnesses)
from code_v5.verify_review_evidence import file_sha, source_file

ROOT = Path(__file__).resolve().parents[1]


def calls(node, text):
    result = []
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        leaf = call.func.id if isinstance(call.func, ast.Name) else (call.func.attr if isinstance(call.func, ast.Attribute) else None)
        result.append({"line": call.lineno, "leaf": leaf,
                       "expression": ast.get_source_segment(text, call)})
    return result


def restore(graph, fid, cache):
    inventory = {node["id"]: node for node in graph["functions"]}
    node = inventory[fid]
    if node["file"] not in cache:
        text, definitions, blob, valid_blob = source_file(graph, node["file"], {})
        visitor = FunctionNodes()
        visitor.visit(ast.parse(text, filename=node["file"]))
        if not valid_blob:
            raise RuntimeError("Base git blob differs from the graph evidence")
        cache[node["file"]] = (text, definitions, blob, visitor.nodes)
    text, definitions, blob, nodes = cache[node["file"]]
    start = node.get("def_line", node["start_line"])
    key = (node["qualified_name"], start)
    if definitions.get(key) != node["end_line"]:
        raise RuntimeError("Physical AST function identity mismatch")
    source = "".join(text.splitlines(keepends=True)[start - 1:node["end_line"]])
    import hashlib
    if hashlib.sha256(source.encode()).hexdigest() != node["source_sha256"]:
        raise RuntimeError("Complete source hash mismatch")
    function = nodes[key]
    readable = copy.deepcopy(function)
    for child in ast.walk(readable):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.body:
            first = child.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                child.body.pop(0)
    return {"function_id": fid, "file": node["file"], "leaf": node["qualified_name"].rsplit(".", 1)[-1],
            "base_blob_sha1": blob, "full_source_sha256": node["source_sha256"],
            "full_source": source, "readable_body": ast.unparse(readable),
            "calls": calls(function, text), "node": function, "file_source": text}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "results/v5_pruner/data_v2")
    args = parser.parse_args()
    checker_path = args.data / "review_evidence_checks.json"
    report = json.loads(checker_path.read_text())
    if report.get("test_labels_opened") is not False or report["record_count"] != 30:
        raise PermissionError("Only the 30 train-only supporting QC records are allowed")
    original_hash = file_sha(checker_path)
    grouped = defaultdict(list)
    for index, record in enumerate(report["records"]):
        if record["sample"].get("split") != "train":
            raise PermissionError("Callsite enrichment accepts training QC examples only")
        grouped[record["identity"]["instance_id"]].append((index, record))
    enriched = []
    for iid, records in grouped.items():
        graph_path = Path(records[0][1]["sample"]["graph"]["graph_path"])
        graph = json.loads(graph_path.read_text())
        if file_sha(graph_path) != records[0][1]["sample"]["graph"]["graph_sha256"]:
            raise RuntimeError("Frozen graph bytes changed")
        functions = {node["id"]: node for node in graph["functions"]}
        cache = {}
        gold_ids = set(records[0][1]["gold_function_ids"])
        gold = {fid: restore(graph, fid, cache) for fid in gold_ids}
        gold_leaf = {value["leaf"] for value in gold.values()}
        chains = traceback_chains(records[0][1]["issue_full"], functions)
        for index, record in records:
            candidate = restore(graph, record["identity"]["function_id"], cache)
            possible = [{"direction": "candidate_to_gold_leaf", "call": call,
                         "possible_targets": [value["function_id"] for value in gold.values() if value["leaf"] == call["leaf"]]}
                        for call in candidate["calls"] if call["leaf"] in gold_leaf]
            possible += [{"direction": "gold_to_candidate_leaf", "gold_function_id": fid, "call": call}
                         for fid, value in gold.items() for call in value["calls"] if call["leaf"] == candidate["leaf"]]
            dunder = possible_dunder_calls(candidate, {name: {fid for fid, value in gold.items() if value["leaf"] == name}
                                                      for name in gold_leaf}, candidate["file"])
            observed = traceback_witnesses(candidate["function_id"], gold_ids, chains)
            clean = lambda value: {key: item for key, item in value.items() if key not in ("node", "file_source")}
            enriched.append({"record_index": index, "identity": record["identity"],
                             "candidate": clean(candidate), "gold": {fid: clean(value) for fid, value in gold.items()},
                             "possible_bidirectional_calls": possible, "possible_dunder_calls": dunder,
                             "observed_traceback_gold_chain": observed,
                             "new_refinement_rule_counterexample": bool(possible or dunder or observed),
                             "no_base_gold": not gold_ids})
    if original_hash != file_sha(checker_path):
        raise RuntimeError("QC source report changed during enrichment")
    output = args.data / "review_call_evidence.json"
    payload = {"status": "supporting_callsite_evidence_only", "review_signed": False,
               "test_labels_read": False, "labels_changed": False, "statistics_changed": False,
               "checker_report_sha256": original_hash, "script_sha256": file_sha(Path(__file__)),
               "records": sorted(enriched, key=lambda row: row["record_index"]),
               "limitations": ["Name/dunder and exact traceback rules reuse the frozen refiner; this is reproducibility evidence, not an independent causal oracle.",
                               "Codex must still inspect source, issue and patch and count actual counterexamples."]}
    with output.open("x") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"path": str(output), "records": len(enriched),
                      "refinement_rule_counterexamples": sum(row["new_refinement_rule_counterexample"] for row in enriched),
                      "no_base_gold": sum(row["no_base_gold"] for row in enriched)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
