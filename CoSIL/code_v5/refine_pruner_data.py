"""Build a new mechanical dataset version from the frozen raw candidate pool.

Possible name/dunder calls and exact traceback chains exclude whole negative
pairs. They never become real graph edges or positive/C labels. The old miner,
graphs, dataset, and sealed test are not modified. The old test rows are never
opened; original positive eligibility is reconstructed from the raw pool.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MINER_SHA = "95d56df3bf8d3cbbf41d310c41ab71d2693275c6b57b8721fec43ceda3284372"
GRAPH_VERSION = "06abfb41ac155fcb5a04331c6ce9ff34e43758046a87b32de811206ac8a3f4c7"
E_SOURCES = {"e_log", "e_bm25", "e_anchor"}
TRACE_FRAME = re.compile(r'^\s*File\s+["\']([^"\']+)["\'],\s*line\s+(\d+),\s*in\s+([^\r\n]+)', re.MULTILINE)
TRACE_START = re.compile(r"Traceback\s*\(most recent call last\):")
TRACE_END = re.compile(r"^(?:[A-Za-z_]\w*(?:\.\w+)*:|Exception\s+(?:Type|Value):|\s*```|\s*#{1,6}\s)", re.MULTILINE)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


class IntegrityError(RuntimeError):
    """Frozen identity/hash drift is a hard stop, never a negative filter."""


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def callee_leaf(call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def ast_witness(node, source, file):
    focus = node.test if isinstance(node, (ast.If, ast.IfExp, ast.While, ast.Assert)) else node.iter if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)) else node
    location = focus if hasattr(focus, "lineno") else next(child for child in ast.walk(focus) if hasattr(child, "lineno"))
    dump = ast.dump(focus, include_attributes=False)
    expression = ast.get_source_segment(source, focus)
    return {"file": file, "line": location.lineno, "column": location.col_offset,
            "end_line": getattr(location, "end_lineno", location.lineno),
            "operation_node_kind": type(node).__name__, "witness_node_kind": type(focus).__name__,
            "AST_dump": dump[:4096], "AST_dump_sha256": digest(dump), "AST_dump_truncated": len(dump) > 4096,
            "expression": expression[:512] if expression else expression,
            "expression_sha256": digest(expression) if expression is not None else None,
            "expression_characters": len(expression) if expression is not None else None,
            "expression_truncated": bool(expression and len(expression) > 512)}


class FunctionNodes(ast.NodeVisitor):
    """Keep each physical definition, including getter/setter, async and nested."""
    def __init__(self):
        self.scope, self.nodes = [], {}

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        name = ".".join(self.scope + [node.name])
        self.nodes[(name, node.lineno)] = node
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def restore_function(graph, node, file_cache, source_file):
    filename = node["file"]
    if filename not in file_cache:
        try:
            text, definitions, blob, blob_matches = source_file(graph, filename, {})
        except (UnicodeError, LookupError):
            raise
        except ValueError as error:
            raise IntegrityError(f"Verified base blob source failed: {error}") from error
        inventory = FunctionNodes()
        inventory.visit(ast.parse(text, filename=filename))
        if not blob_matches:
            raise IntegrityError("Recorded graph blob does not equal base_commit:path")
        file_cache[filename] = (text, definitions, blob, inventory.nodes)
    text, definitions, blob, nodes = file_cache[filename]
    start, end = node.get("def_line", node["start_line"]), node["end_line"]
    key = (node["qualified_name"], start)
    full = "".join(text.splitlines(keepends=True)[start - 1:end])
    if definitions.get(key) != end or key not in nodes:
        raise IntegrityError("Exact physical AST definition is missing")
    if digest(full) != node["source_sha256"] or len(full) != node["source_characters"] or not full.startswith(node["source"]):
        raise IntegrityError("Complete function source does not match frozen AST source")
    expected_id = f'{filename}::{node["qualified_name"]}@{start}'
    if node["id"] != expected_id:
        raise IntegrityError("Canonical physical function ID mismatch")
    return {"node": nodes[key], "file_source": text, "function_source": full,
            "full_source_sha256": digest(full), "base_blob_sha1": blob,
            "calls": [call for call in ast.walk(nodes[key]) if isinstance(call, ast.Call) and start <= call.lineno <= end]}


def possible_name_calls(candidate, candidate_leaf, gold_sources, gold_leaves, file):
    """Bidirectional conservative name evidence; no receiver/type is inferred."""
    result = []
    for call in candidate["calls"]:
        name = callee_leaf(call)
        if name in gold_leaves:
            result.append({"kind": "candidate_possible_call_to_gold_leaf", "overapproximation": True,
                           "callee_leaf": name, "matching_gold_ids": sorted(gold_leaves[name]),
                           "candidate_callsite": ast_witness(call, candidate["file_source"], file)})
        for gold_id, gold in gold_sources.items():
            qualified = gold.get("qualified_name", "")
            if qualified.rsplit(".", 1)[-1] in {"__init__", "__new__"} and "." in qualified and name == qualified.rsplit(".", 1)[0].rsplit(".", 1)[-1]:
                result.append({"kind": "candidate_possible_constructor_to_gold", "overapproximation": True,
                               "callee_leaf": name, "gold_function_id": gold_id,
                               "gold_full_source_sha256": gold["full_source_sha256"],
                               "candidate_callsite": ast_witness(call, candidate["file_source"], file)})
    for gold_id, gold in gold_sources.items():
        for call in gold["calls"]:
            if callee_leaf(call) == candidate_leaf:
                result.append({"kind": "gold_possible_call_to_candidate_leaf", "overapproximation": True,
                               "callee_leaf": candidate_leaf, "gold_function_id": gold_id,
                               "gold_full_source_sha256": gold["full_source_sha256"],
                               "gold_callsite": ast_witness(call, gold["file_source"], gold["file"])})
    return result


OPERATOR_METHODS = {
    ast.Add: {"__add__", "__radd__", "__iadd__"}, ast.Sub: {"__sub__", "__rsub__", "__isub__"},
    ast.Mult: {"__mul__", "__rmul__", "__imul__"}, ast.MatMult: {"__matmul__", "__rmatmul__", "__imatmul__"},
    ast.Div: {"__truediv__", "__rtruediv__", "__itruediv__"}, ast.FloorDiv: {"__floordiv__", "__rfloordiv__", "__ifloordiv__"},
    ast.Mod: {"__mod__", "__rmod__", "__imod__"}, ast.Pow: {"__pow__", "__rpow__", "__ipow__"},
    ast.LShift: {"__lshift__", "__rlshift__", "__ilshift__"}, ast.RShift: {"__rshift__", "__rrshift__", "__irshift__"},
    ast.BitOr: {"__or__", "__ror__", "__ior__"}, ast.BitAnd: {"__and__", "__rand__", "__iand__"},
    ast.BitXor: {"__xor__", "__rxor__", "__ixor__"}, ast.UAdd: {"__pos__"}, ast.USub: {"__neg__"},
    ast.Invert: {"__invert__"}, ast.Not: {"__bool__", "__len__"},
    ast.Eq: {"__eq__"}, ast.NotEq: {"__ne__", "__eq__"},
    ast.Lt: {"__lt__", "__gt__"}, ast.LtE: {"__le__", "__ge__"},
    ast.Gt: {"__gt__", "__lt__"}, ast.GtE: {"__ge__", "__le__"},
    ast.In: {"__contains__", "__iter__", "__getitem__"}, ast.NotIn: {"__contains__", "__iter__", "__getitem__"},
}
BUILTIN_METHODS = {"len": {"__len__"}, "iter": {"__iter__", "__getitem__"}, "next": {"__next__"},
                   "str": {"__str__"}, "repr": {"__repr__"}, "hash": {"__hash__"},
                   "bool": {"__bool__", "__len__"}, "abs": {"__abs__"}, "round": {"__round__"},
                   "int": {"__int__", "__index__"}, "float": {"__float__"}, "complex": {"__complex__"}}


def possible_dunder_calls(candidate, gold_leaves, file):
    result = []
    for node in ast.walk(candidate["node"]):
        if hasattr(node, "lineno") and not candidate["node"].lineno <= node.lineno <= candidate["node"].end_lineno:
            continue
        methods = set()
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.AugAssign)):
            methods |= OPERATOR_METHODS.get(type(node.op), set())
        elif isinstance(node, ast.Compare):
            for op in node.ops:
                methods |= OPERATOR_METHODS.get(type(op), set())
        elif isinstance(node, ast.Subscript):
            methods |= {ast.Load: {"__getitem__"}, ast.Store: {"__setitem__"}, ast.Del: {"__delitem__"}}.get(type(node.ctx), set())
        elif isinstance(node, ast.Call):
            methods |= {"__call__"}
            methods |= BUILTIN_METHODS.get(callee_leaf(node), set())
        elif isinstance(node, (ast.For, ast.comprehension)):
            methods |= {"__iter__", "__next__", "__getitem__"}
        elif isinstance(node, ast.AsyncFor):
            methods |= {"__aiter__", "__anext__"}
        elif isinstance(node, ast.Await):
            methods |= {"__await__"}
        elif isinstance(node, (ast.If, ast.IfExp, ast.While, ast.BoolOp, ast.Assert)):
            methods |= {"__bool__", "__len__"}
        elif isinstance(node, ast.Attribute):
            methods |= {ast.Load: {"__getattribute__", "__getattr__"}, ast.Store: {"__setattr__"}, ast.Del: {"__delattr__"}}.get(type(node.ctx), set())
        elif isinstance(node, ast.FormattedValue):
            methods |= {"__format__", "__str__", "__repr__"}
        for method in sorted(methods & gold_leaves.keys()):
            result.append({"kind": "candidate_possible_dunder_dispatch_to_gold", "overapproximation": True,
                           "dunder": method, "matching_gold_ids": sorted(gold_leaves[method]),
                           "candidate_callsite": ast_witness(node, candidate["file_source"], file)})
    return result


def frame_path_matches(trace_path, graph_file):
    """Exact package suffixes permit installation prefixes, never basename-only."""
    trace = trace_path.replace("\\", "/").rstrip("/")
    target = graph_file.replace("\\", "/").strip("/")
    choices = {target}
    parts = target.split("/")
    if parts[0] in {"lib", "src"} and len(parts) > 2:
        choices.add("/".join(parts[1:]))
    return any(trace == choice or trace.endswith("/" + choice) for choice in choices)


def traceback_chains(issue, functions):
    starts = list(TRACE_START.finditer(issue))
    chains = []
    for number, start in enumerate(starts):
        line_prefix = issue[issue.rfind("\n", 0, start.start()) + 1:start.start()]
        if "INTERNALERROR>" in line_prefix:
            continue
        end = starts[number + 1].start() if number + 1 < len(starts) else len(issue)
        section = issue[start.end():end]
        termination = TRACE_END.search(section)
        if termination:
            section = section[:termination.start()]
        # Standard Python frames have indented source context. Stop at ordinary
        # prose, a blank after a frame, or a pytest-prefixed line; never join a
        # later unrelated File line into this chain.
        accepted, seen_frame = [], False
        for line in section.splitlines(keepends=True):
            if "INTERNALERROR>" in line:
                break
            if TRACE_FRAME.match(line):
                seen_frame = True
                accepted.append(line)
            elif not line.strip():
                if seen_frame:
                    break
                accepted.append(line)
            elif line[0].isspace() and seen_frame:
                accepted.append(line)
            else:
                break
        section = "".join(accepted)
        frames = []
        for frame in TRACE_FRAME.finditer(section):
            path, line, name = frame.group(1), int(frame.group(2)), frame.group(3).strip()
            if name in {"<module>", "<lambda>"}:
                matches = []
            else:
                matches = [fid for fid, node in functions.items()
                           if frame_path_matches(path, node["file"])
                           and (node["qualified_name"] == name if "." in name else node["qualified_name"].rsplit(".", 1)[-1] == name)
                           and node.get("def_line", node["start_line"]) <= line <= node["end_line"]]
            frames.append({"path": path, "line": line, "frame_name": name,
                           "unique_function_id": matches[0] if len(matches) == 1 else None,
                           "ambiguous_matches": matches if len(matches) != 1 else [],
                           "raw_frame": frame.group(0).strip()})
        if frames:
            chains.append({"traceback_index": number, "issue_offset": start.start(), "frames": frames})
    return chains


def traceback_witnesses(fid, gold_ids, chains):
    result = []
    for chain in chains:
        candidates = [(i, frame) for i, frame in enumerate(chain["frames"]) if frame["unique_function_id"] == fid]
        gold = [(i, frame) for i, frame in enumerate(chain["frames"]) if frame["unique_function_id"] in gold_ids]
        for candidate_index, candidate_frame in candidates:
            for gold_index, gold_frame in gold:
                result.append({"kind": "exact_traceback_chain_with_gold", "overapproximation": False,
                               "traceback_index": chain["traceback_index"],
                               "candidate_frame_index": candidate_index, "gold_frame_index": gold_index,
                               "candidate_frame": candidate_frame, "gold_frame": gold_frame,
                               "claim": "same observed issue traceback chain; no static edge or positive label inferred"})
    return result


def v1_review_summary(original_stats, pending_path, completed_path):
    result = {"original_review": deepcopy(original_stats["review"]), "status": "v1_QC_failed_in_root_review",
              "exact_error_count": None, "root_confirmed_error_lower_bound": 3,
              "note": "At least three root-reviewed causal counterexamples triggered this reconstruction; completed review count is recorded only when supplied."}
    if completed_path is None:
        return result
    reviewed = [json.loads(line) for line in completed_path.read_text().splitlines() if line.strip()]
    pending = [json.loads(line) for line in pending_path.read_text().splitlines() if line.strip()]
    identity = lambda row: tuple(row[key] for key in ("review_family", "instance_id", "function_id", "input_sha256"))
    expected = {identity(row): row for row in pending}
    if len(reviewed) != 30 or len(expected) != 30 or len({identity(row) for row in reviewed}) != 30 or {identity(row) for row in reviewed} != set(expected):
        raise IntegrityError("Supplied v1 review must match the 30 frozen QC identities")
    for row in reviewed:
        frozen = expected[identity(row)]
        allowed = {"review_status", "label_error", "review_note"}
        if canonical({k: v for k, v in row.items() if k not in allowed}) != canonical({k: v for k, v in frozen.items() if k not in allowed}):
            raise IntegrityError("Supplied v1 review evidence fields changed")
        if row.get("review_status") != "reviewed" or type(row.get("label_error")) is not bool or not isinstance(row.get("review_note"), str) or not row["review_note"].strip():
            raise IntegrityError("Supplied v1 review is incomplete")
    result.update({"review_path": str(completed_path.resolve()), "review_sha256": file_digest(completed_path),
                   "reviewed_records": len(reviewed), "exact_error_count": sum(row["label_error"] for row in reviewed)})
    return result


def refine_issue(iid, rows, gold, issue, graph_path, expected_graph, source_file):
    negatives = [row for row in rows if row["label"] is False]
    positives = [row for row in rows if row["label"] is True]
    def reject_all(kind, error=None):
        return positives, [{"instance_id": iid, "function_id": row["function_id"],
                            "input_sha256": row["input_sha256"], "original_row_sha256": digest(canonical(row)),
                            "full_source_sha256": row["full_function_source_sha256"],
                            "complete_source_verified": False, "label_sources": row["label_sources"],
                            "graph_sha256": expected_graph["graph_sha256"],
                            "reasons": [{"kind": kind, "error": error}]} for row in negatives]
    raw = graph_path.read_bytes()
    graph = json.loads(raw)
    if digest(raw) != expected_graph["graph_sha256"] or graph["audit"]["graph_version_sha256"] != GRAPH_VERSION:
        raise IntegrityError("Frozen graph hash/version drift")
    if graph["instance_id"] != iid or graph["repo"] != gold["repo"] or graph["base_commit"] != gold["base_commit"]:
        raise IntegrityError("Graph/gold identity drift")
    functions = {node["id"]: node for node in graph["functions"]}
    if len(functions) != len(graph["functions"]):
        raise IntegrityError("Duplicate graph function identity")
    for row in rows:
        if row["function_id"] not in functions or row["instance_id"] != iid or canonical(row["graph"]) != canonical(expected_graph) or row["repo"] != graph["repo"] or row["base_commit"] != graph["base_commit"]:
            raise IntegrityError("Candidate physical/source identity drift")
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
    file_cache, gold_sources, gold_leaves = {}, {}, defaultdict(set)
    try:
        for fid in sorted(gold_ids):
            node = functions[fid]
            gold_sources[fid] = {**restore_function(graph, node, file_cache, source_file), "file": node["file"], "qualified_name": node["qualified_name"]}
            gold_leaves[node["qualified_name"].rsplit(".", 1)[-1]].add(fid)
    except (SyntaxError, UnicodeError, LookupError, OSError, subprocess.SubprocessError) as error:
        return reject_all("gold_full_source_unavailable", f"{type(error).__name__}: {error}")
    chains = traceback_chains(issue["problem_statement"], functions)
    kept, rejected = list(positives), []
    for row in negatives:
        reasons, candidate = [], None
        try:
            node = functions[row["function_id"]]
            candidate = restore_function(graph, node, file_cache, source_file)
            if candidate["full_source_sha256"] != row["full_function_source_sha256"] or candidate["function_source"][:1500] != row["function"]:
                raise IntegrityError("Candidate row full-source hash/cut drift")
        except (SyntaxError, UnicodeError, LookupError, OSError, subprocess.SubprocessError) as error:
            reasons.append({"kind": "candidate_full_source_unavailable", "error": f"{type(error).__name__}: {error}"})
        if not reasons:
            name = node["qualified_name"].rsplit(".", 1)[-1]
            reasons.extend(possible_name_calls(candidate, name, gold_sources, gold_leaves, node["file"]))
            reasons.extend(possible_dunder_calls(candidate, gold_leaves, node["file"]))
            reasons.extend(traceback_witnesses(row["function_id"], gold_ids, chains))
        if reasons:
            rejected.append({"instance_id": iid, "function_id": row["function_id"],
                             "input_sha256": row["input_sha256"], "original_row_sha256": digest(canonical(row)),
                             "full_source_sha256": row["full_function_source_sha256"],
                             "verified_full_source_sha256": candidate["full_source_sha256"] if candidate else None,
                             "complete_source_verified": candidate is not None,
                             "base_blob_sha1": candidate["base_blob_sha1"] if candidate else None,
                             "graph_sha256": expected_graph["graph_sha256"],
                             "label_sources": row["label_sources"], "reasons": reasons})
        else:
            kept.append(row)
    return sorted(kept, key=lambda row: row["function_id"]), rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-data", type=Path, default=ROOT / "results/v5_pruner/data")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v5_pruner/data_v2")
    parser.add_argument("--v1-review-results", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/v5-pruner/数据重构_v2与质量门.md")
    args = parser.parse_args()
    if args.output.resolve() == args.source_data.resolve() or args.output.exists():
        parser.error("A new, nonexistent output directory is required; frozen v1 is never overwritten")
    source_paths = {name: args.source_data / name for name in ("candidate_pool.jsonl", "statistics.json", "split_manifest.json", "test_file_seal.json", "human_review.jsonl", "pruner_train.jsonl", "pruner_val.jsonl", "pruner_test.jsonl")}
    if args.v1_review_results:
        source_paths["v1_completed_review"] = args.v1_review_results
    before = {name: file_digest(path) for name, path in source_paths.items()}
    if file_digest(ROOT / "code_v5/build_pruner_data.py") != MINER_SHA:
        raise RuntimeError("Frozen miner hash changed")
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
    v1_qc = v1_review_summary(original_stats, source_paths["human_review.jsonl"], args.v1_review_results)
    original_split = json.loads(source_paths["split_manifest.json"].read_text())
    splits = {iid: split for split, ids in original_split["splits"].items() for iid in ids}
    if [len(original_split["splits"][key]) for key in ("train", "val", "test")] != [240, 30, 30] or len(splits) != 300:
        raise ValueError("Original frozen split identity is invalid")
    raw_pool = [json.loads(line) for line in source_paths["candidate_pool.jsonl"].read_text().splitlines() if line.strip()]
    if any(type(row["label"]) is not bool or splits[row["instance_id"]] != row["split"] for row in raw_pool):
        raise ValueError("Candidate pool label/split invariant failed")
    if len({(row["instance_id"], row["function_id"]) for row in raw_pool}) != len(raw_pool):
        raise ValueError("Duplicate raw candidate physical pair")
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
        raise AssertionError("Truncated input leakage after v2 sampling")
    if {(r["instance_id"], r["function_id"]) for r in rows} & {(r["instance_id"], r["function_id"]) for r in rejected}:
        raise AssertionError("Excluded physical negative reappeared under another source")
    if before != {name: file_digest(path) for name, path in source_paths.items()}:
        raise RuntimeError("Frozen source data changed during refinement")
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
    seal = {"schema_version": 1, "dataset_version": "v2_mechanical_negative_refinement",
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
    statistics = {"schema_version": 1, "dataset_version": "v2_mechanical_negative_refinement",
                  "mechanical_labels_only": True, "model_calls": 0, "training_started": False,
                  "test_performance_opened": False, "old_test_rows_opened": False,
                  "sources": deepcopy(original_stats["sources"]),
                  "source_priority": deepcopy(original_stats["source_priority"]),
                  "C_scope": original_stats["C_scope"], "E_filter": original_stats["E_filter"],
                  "BM25": deepcopy(original_stats["BM25"]),
                  "raw_counts": deepcopy(original_stats["raw_counts"]),
                  "raw_counts_scope": "unfiltered original v1 mining observations; v2 exclusions are counted separately",
                  "per_issue_mining": deepcopy(original_stats["per_issue_mining"]),
                  "reconstruction_sources": {name: {"path": str(path.resolve()), "sha256": before[name]} for name, path in source_paths.items()},
                  "refiner_sha256": file_digest(Path(__file__)),
                  "negative_filter": "drop whole D/E pair on bidirectional full-AST possible gold leaf call, possible gold dunder dispatch, exact shared traceback chain, unavailable complete source, or absent base gold; no relabeling or new graph edges",
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
                  "limitations": ["Name and dunder matching overapproximate possible calls; they are not causal proof or real graph edges.",
                                  "Traceback identity requires exact package path, function name and base line containment; version-drift frames may remain unmapped.",
                                  "Formal P>=8000 remains failed at the original 1542 eligible positives.",
                                  "E>=3000 with N/P=2 still leaves at most 84 D-only negatives; retained-D gate only checks nonzero coverage."]}
    miner.atomic_json(args.output / "statistics.json", statistics)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(f"# v2 机械负例重构与质量门\n\n正式 D2 通过：{statistics['passed']}。未训练、未调用模型、未评测 test；v1 全部保留。\n\n候选负例排除 {len(rejected)} 条；正例 {p}、负例 {n}、E {e}、D-only {selected.get('primary_source_D',0)}。原始正例及原 dedup 正例资格保持不变。\n\n排除理由按 pair 计数（可重叠）：{json.dumps(dict(reason_counts), ensure_ascii=False)}。\n\n质量门：{json.dumps(gates, ensure_ascii=False)}。新版 train 的 E 三族各10条仍待 Codex逐条证据审阅；此报告不签审阅。\n\n逐条 witness：{(args.output/'negative_exclusions.jsonl').resolve()}\n\n统计：{(args.output/'statistics.json').resolve()}\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "positive": p, "negative": n, "E": e,
                      "excluded_negative": len(rejected), "reason_counts": dict(reason_counts),
                      "quality_gates": gates, "passed": statistics["passed"]}, ensure_ascii=False), flush=True)
    return 0 if statistics["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
