"""Check train-only QC evidence; never sign a review or change dataset labels.

The report is supporting evidence for a subsequent Codex review, not a human
signature, a model evaluation, or a replacement for the formal size gates.
Only BM25 recomputation reuses the frozen miner, so it is explicitly not an
independent BM25 oracle. No pruner_test file is opened by this script.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict, deque
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tokenize

ROOT = Path(__file__).resolve().parents[1]
MINER_SHA256 = "95d56df3bf8d3cbbf41d310c41ab71d2693275c6b57b8721fec43ceda3284372"
GRAPH_VERSION = "06abfb41ac155fcb5a04331c6ce9ff34e43758046a87b32de811206ac8a3f4c7"
E_FAMILIES = ("e_log", "e_bm25", "e_anchor")
REVIEW_FIELDS = {"review_family", "reviewer", "review_status", "label_error", "review_note"}


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def quad(row):
    return tuple(row[key] for key in ("review_family", "instance_id", "function_id", "input_sha256"))


def leaf(name):
    return name.strip().strip("`").split("(", 1)[0].split("#", 1)[0].strip().rsplit(".", 1)[-1]


def mentions(text):
    calls = re.findall(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(", text)
    identifiers = [value for value in re.findall(r"`([^`\n]+)`", text)
                   if re.fullmatch(r"\w+(?:\.\w+)*", value.strip())]
    return {leaf(value) for value in calls + identifiers}


def closure(seeds, adjacency):
    visited, pending = set(seeds), deque(seeds)
    while pending:
        for target in adjacency.get(pending.popleft(), ()):
            if target not in visited:
                visited.add(target)
                pending.append(target)
    return visited


class Definitions(ast.NodeVisitor):
    """Recover exact lexical AST identities from a verified base git blob."""
    def __init__(self):
        self.scope, self.functions = [], {}

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        name = ".".join(self.scope + [node.name])
        self.functions[(name, node.lineno)] = node.end_lineno
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def source_file(graph, filename, cache):
    if filename in cache:
        return cache[filename]
    mirror = ROOT / "mirror_cache" / (graph["repo"].rsplit("/", 1)[-1] + ".git")
    prefix = ["git", "--git-dir", str(mirror)]
    blob = subprocess.run(prefix + ["rev-parse", graph["base_commit"] + ":" + filename],
                          check=True, capture_output=True, timeout=20).stdout.decode().strip()
    data = subprocess.run(prefix + ["cat-file", "blob", blob], check=True,
                          capture_output=True, timeout=20).stdout
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if actual != blob:
        raise ValueError("Base git blob SHA1 mismatch: " + filename)
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    text = data.decode(encoding)
    visitor = Definitions()
    visitor.visit(ast.parse(text, filename=filename))
    evidence = {item["file"]: item["blob_sha1"] for item in graph["audit"]["base_blob_evidence"]}
    cache[filename] = (text, visitor.functions, blob, evidence.get(filename) == blob)
    return cache[filename]


def resolve_fetch(event, fetched, functions):
    args, tool = event.get("arguments", []), event.get("tool")
    candidates = []
    if tool == "get_code_of_class_function" and len(args) == 3:
        candidates = [node for node in functions.values() if node["file"] == args[0]
                      and leaf(node["qualified_name"]) == args[2]
                      and "." in node["qualified_name"]
                      and leaf(node["qualified_name"].rsplit(".", 1)[0]) == leaf(args[1])]
    elif tool == "get_code_of_file_function" and len(args) == 2:
        candidates = [node for node in functions.values() if node["file"] == args[0]
                      and leaf(node["qualified_name"]) == args[1]]
    head = str(fetched.get("code_snippet_head") or event.get("code_snippet_head") or "")
    head = head.replace("\r\n", "\n").strip()
    matches = [node["id"] for node in candidates
               if head and node["source"].replace("\r\n", "\n").strip().startswith(head)]
    return matches, head


def raw_true(value):
    value = str(value).strip()
    if value.startswith("```") and value.endswith("```"):
        value = value[3:-3].strip()
        value = re.sub(r"^(?:python|json)\s*\n", "", value, flags=re.IGNORECASE).strip()
    return value.lower() == "true"


def log_check(evidence, row, functions, events_root, cache):
    flags = {}
    arm, iid = evidence.get("arm"), row["instance_id"]
    expected = events_root / str(arm) / "events" / f"{arm}_{iid}.jsonl"
    flags["original_log_path"] = arm in ("off", "on", "shuffled") and Path(evidence["path"]).resolve() == expected.resolve()
    if not flags["original_log_path"]:
        return {"flags": flags, "passed": False, "evidence": evidence}
    if expected not in cache:
        cache[expected] = jsonl(expected)
    events = cache[expected]
    number = evidence.get("line")
    flags["original_log_line"] = type(number) is int and 1 <= number <= len(events)
    if not flags["original_log_line"]:
        return {"flags": flags, "passed": False, "evidence": evidence}
    event = events[number - 1]
    flags["complete_single_run"] = sum(e.get("event") == "run_start" for e in events) == 1 and sum(e.get("event") == "run_end" for e in events) == 1
    flags["run_identity"] = all(e.get("instance_id") == iid and e.get("arm") == arm for e in events)
    flags["prune_event"] = event.get("event") == "prune"
    flags["prune_identity"] = all(canonical(event.get(key)) == canonical(evidence.get(key))
                                   for key in ("arm", "step", "tool", "arguments", "decision"))
    flags["explicit_true"] = event.get("decision") in (True, "True", "true") and raw_true(event.get("llm_raw_response", ""))
    key = (event.get("step"), event.get("tool"), canonical(event.get("arguments", [])))
    fetched = None
    for candidate in events[:number - 1]:
        candidate_key = (candidate.get("step"), candidate.get("tool"), canonical(candidate.get("arguments", [])))
        if candidate.get("event") == "tool_result" and candidate_key == key:
            fetched = candidate
    flags["successful_source_fetch"] = bool(fetched and fetched.get("success") and fetched.get("kind") == "source")
    if fetched:
        matches, head = resolve_fetch(event, fetched, functions)
        flags["unique_physical_function"] = matches == [row["function_id"]]
        flags["retrieved_head_hash"] = evidence.get("retrieved_head_sha256") == sha(str(fetched.get("code_snippet_head", "")))
        flags["raw_response_hash"] = evidence.get("raw_response_sha256") == sha(str(event.get("llm_raw_response", "")))
        flags["fetch_metadata"] = evidence.get("fetch_success") is True and evidence.get("fetch_kind") == "source" and evidence.get("code_chars") == fetched.get("code_chars")
    else:
        head = ""
    return {"passed": all(flags.values()), "flags": flags, "evidence": evidence,
            "original_prune_event": event, "original_source_fetch": fetched,
            "matched_source_head": head}


def issue_rows(path, selected):
    if path.suffix == ".jsonl":
        result = {}
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    value = json.loads(line)
                    if value["instance_id"] in selected:
                        if value["instance_id"] in result:
                            raise ValueError("Duplicate benchmark issue identity")
                        result[value["instance_id"]] = value
        return result
    values = json.loads(path.read_text())
    values = values.values() if isinstance(values, dict) else values
    return {value["instance_id"]: value for value in values if value["instance_id"] in selected}


def check_issue(iid, samples, train_by_pair, gold, issue, graphs, events, miner):
    graph_path = graphs / (iid + ".json")
    graph_bytes = graph_path.read_bytes()
    graph = json.loads(graph_bytes)
    functions = {node["id"]: node for node in graph["functions"]}
    common = {"graph_identity": graph.get("instance_id") == iid,
              "graph_inventory_unique": len(functions) == len(graph["functions"]),
              "repo_base_identity": graph["repo"] == gold["repo"] == issue["repo"] and graph["base_commit"] == gold["base_commit"] == issue["base_commit"],
              "frozen_graph_version": graph["audit"]["graph_version_sha256"] == GRAPH_VERSION}
    by_region = defaultdict(list)
    for fid, node in functions.items():
        by_region[(node["file"], node["qualified_name"], node.get("def_line", node["start_line"]))].append(fid)
    gold_ids, unmapped = set(), []
    for region in gold.get("existing_gold_function_regions", []):
        matched = by_region[(region["file"], region["name"], region["def_line"])]
        if len(matched) == 1:
            gold_ids.add(matched[0])
        else:
            unmapped.append(region)
    common["all_base_gold_regions_mapped"] = not unmapped
    incoming, outgoing = defaultdict(set), defaultdict(set)
    for edge in graph["edges"]:
        outgoing[edge["caller"]].add(edge["callee"])
        incoming[edge["callee"]].add(edge["caller"])
    common["all_edge_nodes_exist"] = all(e["caller"] in functions and e["callee"] in functions for e in graph["edges"])
    one_hop = {neighbor for fid in gold_ids for neighbor in outgoing[fid] | incoming[fid]} - gold_ids
    all_causal = closure(gold_ids, outgoing) | closure(gold_ids, incoming)
    multi_hop = all_causal - gold_ids - one_hop
    changed = defaultdict(set)
    for evidence in gold.get("evidence", []):
        changed[evidence.get("file")].update(evidence.get("changed_before", []))
    tokens = None
    bm25_ranking, bm25_audit, bm25_error = [], None, None
    if any("e_bm25" in sample["label_sources"] for sample in samples):
        try:
            tokens, bm25_audit = miner.full_function_token_counts(functions, graph)
            bm25_ranking = miner.bm25_top15(functions, issue["problem_statement"], tokens)
        except Exception as error:
            bm25_error = f"{type(error).__name__}: {error}"
    ranked = {fid: (rank, score) for rank, (fid, score) in enumerate(bm25_ranking, 1)}
    source_cache, log_cache, reports = {}, {}, []
    for sample in samples:
        flags, details = dict(common), {}
        fid, family = sample["function_id"], sample["review_family"]
        row = train_by_pair.get((iid, fid))
        flags["identical_training_payload"] = row is not None and canonical(row) == canonical({k: v for k, v in sample.items() if k not in REVIEW_FIELDS})
        flags["training_negative_E"] = sample.get("split") == "train" and sample.get("label") is False and family in E_FAMILIES and family in sample["label_sources"]
        flags["pending_Codex_review"] = sample.get("reviewer") == "Codex/机械证据审阅" and sample.get("review_status") == "pending" and sample.get("label_error") is None and sample.get("review_note") is None
        flags["input_hash"] = sample["input_sha256"] == sha(json.dumps([sample["issue"], sample["function"]], ensure_ascii=False))
        flags["full_issue_cut"] = sample["issue"] == issue["problem_statement"][:2000]
        flags["record_identity"] = sample["repo"] == graph["repo"] and sample["base_commit"] == graph["base_commit"]
        flags["graph_file_hash"] = sample["graph"]["graph_sha256"] == sha(graph_bytes)
        flags["graph_source_identity"] = Path(sample["graph"]["graph_path"]).resolve() == graph_path.resolve() and sample["graph"]["base_commit"] == graph["base_commit"] and sample["graph"]["graph_version_sha256"] == GRAPH_VERSION
        flags["physical_function_present"] = fid in functions
        full_source = None
        if fid in functions:
            node = functions[fid]
            start, end = node.get("def_line", node["start_line"]), node["end_line"]
            flags["physical_function_fields"] = sample["function_file"] == node["file"] and sample["function_qualified_name"] == node["qualified_name"] and sample["function_def_line"] == start and fid == f'{node["file"]}::{node["qualified_name"]}@{start}'
            try:
                source, definitions, blob, blob_matches = source_file(graph, node["file"], source_cache)
                full_source = "".join(source.splitlines(keepends=True)[start - 1:end])
                flags["base_blob_identity"] = blob_matches
                flags["physical_AST_definition"] = definitions.get((node["qualified_name"], start)) == end
                flags["full_function_source_hash"] = sha(full_source) == node["source_sha256"] == sample["full_function_source_sha256"]
                flags["source_length_and_cut"] = len(full_source) == node["source_characters"] and full_source[:1500] == node["source"] == sample["function"]
                details["verified_base_blob_sha1"] = blob
            except Exception as error:
                flags["source_restore"] = False
                details["source_restore_error"] = f"{type(error).__name__}: {error}"
            enclosed_gold = [r for r in gold.get("existing_gold_function_regions", []) if r["file"] == node["file"] and start <= r["def_line"] and r["end_line"] <= end]
            enclosed_after = [r for r in gold.get("target_regions", []) if r["file"] == node["file"] and r.get("kind") == "function" and r.get("side") == "after" and r["name"].startswith(node["qualified_name"] + ".")]
            touched = sorted(line for line in changed[node["file"]] if start <= line <= end)
            flags["excluded_gold"] = fid not in gold_ids
            flags["excluded_one_hop"] = fid not in one_hop
            flags["excluded_multi_hop"] = fid not in multi_hop
            flags["excluded_patch_container"] = not touched and not enclosed_gold and not enclosed_after
            details["patch_container_check"] = {"changed_before_inside_source": touched, "enclosed_existing_gold": enclosed_gold, "enclosed_after_gold_scope": enclosed_after}
        source_checks = {}
        for source in E_FAMILIES:
            if source not in sample["label_sources"]:
                continue
            evidence_rows = [e for e in sample["provenance"] if e.get("source") == source]
            flags[source + "_evidence_present"] = bool(evidence_rows)
            flags[source + "_exclusion_evidence"] = bool(evidence_rows) and all(e.get("excluded_gold_and_causal_reachability") is True and e.get("source_does_not_enclose_gold_patch") is True for e in evidence_rows)
            if source == "e_log":
                source_checks[source] = [log_check(e, sample, functions, events, log_cache) for e in evidence_rows]
            elif source == "e_anchor":
                actual_leaf = leaf(functions[fid]["qualified_name"]) if fid in functions else None
                source_checks[source] = [{"passed": e.get("issue_named_function_leaf") == actual_leaf and actual_leaf in mentions(issue["problem_statement"]) and e.get("extractor") == "frozen-v3c issue_mentions regex", "evidence": e, "candidate_leaf": actual_leaf, "extracted_issue_leaves": sorted(mentions(issue["problem_statement"]))} for e in evidence_rows]
            else:
                actual = ranked.get(fid)
                source_checks[source] = [{"passed": bool(actual and e.get("rank_in_all_repo_functions") == actual[0] and type(e.get("bm25_score")) in (int, float) and math.isclose(e["bm25_score"], actual[1], rel_tol=1e-12, abs_tol=1e-12) and e.get("query_is_full_issue") is True and e.get("bm25_document") == "complete verified base AST function source"), "evidence": e, "recomputed_rank_score": actual, "recompute_error": bm25_error} for e in evidence_rows]
            flags[source + "_verified"] = bool(evidence_rows) and all(e["passed"] for e in source_checks[source])
        reports.append({"identity": dict(zip(("review_family", "instance_id", "function_id", "input_sha256"), quad(sample))),
                        "passed": all(flags.values()), "flags": flags,
                        "failed_checks": [key for key, value in flags.items() if not value],
                        "issue_full": issue["problem_statement"], "function_full": full_source,
                        "training_issue_cut": sample["issue"], "training_function_cut": sample["function"],
                        "gold_patch": issue.get("patch"), "gold_evidence": gold.get("evidence"),
                        "gold_function_ids": sorted(gold_ids), "gold_regions_unmapped": unmapped,
                        "one_hop_count": len(one_hop), "multi_hop_count": len(multi_hop),
                        "source_checks": source_checks, "details": details,
                        "bm25_top15": [{"rank": rank, "function_id": value[0], "score": value[1]} for rank, value in enumerate(bm25_ranking, 1)],
                        "bm25_audit": bm25_audit, "sample": sample})
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "results/v5_pruner/data")
    parser.add_argument("--gold", type=Path, default=ROOT / "ground_truth_300.json")
    parser.add_argument("--graphs", type=Path, default=ROOT / "results/v5_pruner/graphs")
    parser.add_argument("--events", type=Path, default=ROOT / "results/qwen_300/fixed")
    parser.add_argument("--issues", type=Path, default=ROOT.parent / "GraphLocator/datasets/swe_bench_lite.jsonl")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.data / "review_evidence_checks.json"
    if output.name != "review_evidence_checks.json":
        parser.error("Output must be named review_evidence_checks.json; dataset/statistics files are never writable here")
    paths = {"human_review": args.data / "human_review.jsonl", "train": args.data / "pruner_train.jsonl", "split_manifest": args.data / "split_manifest.json", "gold": args.gold, "issues": args.issues, "miner": ROOT / "code_v5/build_pruner_data.py"}
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print(json.dumps({"status": "not_ready", "missing": missing, "report_written": False}, ensure_ascii=False))
        return 3
    before = {name: file_sha(path) for name, path in paths.items()}
    if before["miner"] != MINER_SHA256:
        raise RuntimeError("Frozen miner SHA changed; BM25 reuse refused")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    from code_v5 import build_pruner_data as miner
    samples, train = jsonl(paths["human_review"]), jsonl(paths["train"])
    selected = {sample["instance_id"] for sample in samples}
    splits = json.loads(paths["split_manifest"].read_text())["splits"]
    split_ids = [iid for values in splits.values() for iid in values]
    gold = json.loads(args.gold.read_text())
    issues = issue_rows(args.issues, selected)
    train_by_pair = {(row["instance_id"], row["function_id"]): row for row in train}
    global_checks = {"exactly_30_samples": len(samples) == 30,
                     "three_families_10_each": dict(Counter(r["review_family"] for r in samples)) == {family: 10 for family in E_FAMILIES},
                     "unique_review_quads": len({quad(row) for row in samples}) == len(samples),
                     "unique_review_pairs": len({(r["instance_id"], r["function_id"]) for r in samples}) == len(samples),
                     "frozen_split_240_30_30_disjoint": [len(splits[name]) for name in ("train", "val", "test")] == [240, 30, 30] and len(split_ids) == len(set(split_ids)) == 300,
                     "selected_issues_in_frozen_train": selected <= set(splits["train"]),
                     "train_pairs_unique": len(train_by_pair) == len(train),
                     "train_file_only_train": all(row.get("split") == "train" and row["instance_id"] in splits["train"] for row in train),
                     "selected_issues_present": selected <= gold.keys() and selected <= issues.keys()}
    grouped = defaultdict(list)
    for sample in samples:
        grouped[sample["instance_id"]].append(sample)
    report_records = []
    for number, (iid, group) in enumerate(sorted(grouped.items()), 1):
        try:
            report_records.extend(check_issue(iid, group, train_by_pair, gold[iid], issues[iid], args.graphs, args.events, miner))
        except Exception as error:
            for sample in group:
                report_records.append({"identity": dict(zip(("review_family", "instance_id", "function_id", "input_sha256"), quad(sample))), "passed": False, "flags": {"issue_check_completed": False}, "failed_checks": ["issue_check_completed"], "error": f"{type(error).__name__}: {error}"})
        print(f"QC evidence {number}/{len(grouped)} issues; {len(report_records)}/{len(samples)} records", flush=True)
    after = {name: file_sha(path) for name, path in paths.items()}
    global_checks["input_files_unchanged_during_check"] = before == after
    report = {"schema_version": 1, "status": "supporting_mechanical_evidence_only",
              "passed": all(global_checks.values()) and all(record["passed"] for record in report_records),
              "review_signed": False, "labels_changed": False, "statistics_changed": False,
              "test_labels_opened": False, "model_calls": 0,
              "BM25_oracle": "Frozen miner implementation reused; this is a reproducibility check, not an independent oracle",
              "limitations": ["Static call reachability is not proof of runtime causal ground truth.", "A passing report still requires root to read each QC record and record Codex evidence review.", "Formal P>=8000 and E>=3000 gates remain independent and are never updated by this script."],
              "sources": {name: {"path": str(path.resolve()), "sha256": before[name]} for name, path in paths.items()},
              "graph_version_sha256": GRAPH_VERSION, "checker_sha256": file_sha(Path(__file__)),
              "global_checks": global_checks, "record_count": len(report_records),
              "passed_records": sum(record["passed"] for record in report_records),
              "records": report_records}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)
    print(json.dumps({"report": str(output.resolve()), "passed": report["passed"], "passed_records": report["passed_records"], "global_checks": global_checks}, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
