"""Read-only, post-completion lineage and single-inference accounting audit.

No Gold labels, model calls, source edits or historical-output writes are used.
The CLI is fixed to Java128/384 terminals. Smaller cohorts are injectable only
through the Python API for synthetic tests. Missing legitimate failure results
remain missing and are distinguished from transformed-result manifest records.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import time


ARMS = ("cosil", "sfpruner", "locagent")
TERMINAL = {"complete", "partial", "worker_failed", "timed_out", "dependency_blocked", "preparation_blocked"}
VIEW = "evaluation_views/signature_format_v2"
_LEXER = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|\s+|[\w$]+|.', re.S)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def same_object(a, b):
    return Path(a).exists() and Path(b).exists() and os.path.samefile(a, b)


def _tokens(text):
    tokens = [t for t in _LEXER.findall(text) if not t.isspace()]
    output = []
    for token in tokens:
        # Public base inventories spell an explicit wildcard bound without
        # whitespace. Expand that representation for independent token checks.
        if output and output[-1] == "?":
            match = re.fullmatch(r"(extends|super)([\w$]+)", token)
            if match:
                output.extend(match.groups())
                continue
        output.append(token)
    return output


def token_equivalent(before, after):
    """Check lexical tokens, independently of the formatting implementation."""
    return isinstance(before, str) and isinstance(after, str) and _tokens(before) == _tokens(after)


def differences(before, after, prefix=""):
    """Exhaustive leaf-level differences, including removals and additions."""
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            name = prefix + "/" + str(key)
            if key not in before:
                result.append({"field": name, "change": "added", "after": after[key]})
            elif key not in after:
                result.append({"field": name, "change": "removed", "before": before[key]})
            else:
                result.extend(differences(before[key], after[key], name))
        return result
    if before == after:
        return []
    return [{"field": prefix or "/", "before": before, "after": after}]


class Checks:
    def __init__(self):
        self.count = 0
        self.errors = []

    def check(self, condition, label, **evidence):
        self.count += 1
        if not condition:
            self.errors.append({"check": label, **evidence})
        return bool(condition)


def closure(root, expected_n=128):
    """Do not open base inventories or prediction/report contents until closed."""
    root = Path(root)
    required = {"inference": root / "run/completion.json",
                "original_cpu": root / "analysis_supervisor/completion.json",
                "signature_cpu": root / "signature_view_supervisor/completion.json"}
    missing = [str(p) for p in required.values() if not p.is_file()]
    if missing:
        return {"ready": False, "missing": missing}
    original, normalized, inference = (read(required[k]) for k in ("original_cpu", "signature_cpu", "inference"))
    if inference.get("status") != "COMPLETE" or inference.get("allocated") != expected_n or inference.get("groups") != expected_n:
        raise ValueError("Invalid full inference closure")
    if original.get("status") != "ANALYSIS_READY_FOR_INDEPENDENT_REVIEW":
        raise ValueError("Original CPU analysis is not closed")
    if normalized.get("status") != "NORMALIZED_REPORTS_READY_FOR_INDEPENDENT_REVIEW":
        raise ValueError("Signature CPU analysis is not closed")
    if normalized.get("original_analysis_completion_sha256") != sha(required["original_cpu"]):
        raise ValueError("Normalized analysis is not bound to the original CPU completion")
    return {"ready": True, "markers": {name: str(path) for name, path in required.items()},
            "marker_sha256": {name: sha(path) for name, path in required.items()},
            "original": original, "normalized": normalized}


def _bindings(root, checks):
    bound = {}
    for name in ("execution_freeze.json", "audits/analysis_execution_freeze.json", "audits/signature_view_execution_freeze.json"):
        path = root / name
        if not checks.check(path.is_file(), "source_freeze_exists", path=str(path)):
            continue
        value = read(path)
        checks.check(bool(value.get("commit")) and bool(value.get("files_sha256")), "recoverable_source_freeze", path=str(path))
        for source, expected in value.get("files_sha256", {}).items():
            p = Path(source)
            actual = sha(p) if p.is_file() else None
            checks.check(actual == expected, "frozen_source_sha", path=source, expected=expected, actual=actual)
        bound[name] = {"sha256": sha(path), "commit": value.get("commit"), "files": len(value.get("files_sha256", {}))}
    return bound


def _public_binding(root, view, row, checks):
    iid = row["instance_id"]
    public, staged = root / "public" / iid, root / "run" / iid / "input"
    checks.check(same_object(view / "public", root / "public"), "public_inventory_reused", instance_id=iid)
    index_path = public / "code_index.json"
    index = read(index_path)
    index_sha = sha(index_path)
    checks.check(sha(staged / "code_index.json") == index_sha, "staged_index_binding", instance_id=iid)
    job, base_job = read(staged / "job.json"), read(public / "job.json")
    for key in ("instance_id", "repo", "base_commit"):
        checks.check(job.get(key) == row[key] == base_job.get(key), "task_base_identity", instance_id=iid, field=key)
    checks.check(job.get("problem_statement") == base_job.get("problem_statement"), "public_issue_binding", instance_id=iid)
    checks.check(set(job.get("paths", [])) == set(index), "public_path_inventory_binding", instance_id=iid)
    for name in ("structure.json", "direct_edges.json"):
        checks.check(sha(staged / name) == sha(public / name), "staged_public_artifact_binding", instance_id=iid, artifact=name)
    snapshot = public / "snapshot"
    paths = {p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*") if p.is_file()}
    checks.check(paths == set(index), "complete_base_snapshot_inventory", instance_id=iid)
    definitions = Counter()
    for path, entry in index.items():
        relative = PurePosixPath(path)
        if not checks.check(not relative.is_absolute() and ".." not in relative.parts and "\\" not in path,
                            "safe_relative_java_path", instance_id=iid, path=path):
            continue
        source = snapshot / path
        if not checks.check(source.is_file() and not source.is_symlink(), "base_regular_source", instance_id=iid, path=path):
            continue
        raw = source.read_bytes()
        checks.check(hashlib.sha256(raw).hexdigest() == entry.get("raw_sha256"), "base_source_sha", instance_id=iid, path=path)
        checks.check(raw.decode("utf-8", errors="replace") == entry.get("content", entry.get("text")),
                     "base_source_text_binding", instance_id=iid, path=path)
        for definition in entry.get("definitions", []):
            if definition.get("kind") == "function":
                identity = path + "::" + definition["qualified_name"]
                checks.check(definition.get("canonical_id", identity) == identity, "base_canonical_identity", instance_id=iid, identity=identity)
                definitions[identity] += 1
    checks.check(all(n == 1 for n in definitions.values()), "unique_public_method_inventory", instance_id=iid)
    return index, index_sha


def _expected_cosil(original, index, checks, iid, arm):
    # Independent of view.normalize_cosil: reproduce only its declared slot
    # rule, with an additional independent lexical-token equivalence check.
    from code_multiswe_java_signature_v2_20261117.normalize import normalize_qualified_name
    expected = copy.deepcopy(original)
    inventory = Counter(path + "::" + d["qualified_name"] for path, e in index.items()
                        for d in e.get("definitions", []) if d.get("kind") == "function")
    changes = []
    for slot, value in enumerate(expected.get("predicted_functions", []), 1):
        if not isinstance(value, dict) or not isinstance(value.get("qualified_name"), str):
            continue
        before = value["qualified_name"]
        after = normalize_qualified_name(before)
        if before == after:
            continue
        checks.check(token_equivalent(before, after), "formatting_preserves_java_tokens", instance_id=iid, arm=arm, slot=slot)
        valid = inventory[value.get("path", "") + "::" + after] == 1
        changes.append({"slot": slot, "before": before, "after": after, "applied": valid,
                        "basis": "Unique public base inventory identity; no Gold lookup"})
        if valid:
            value["qualified_name"] = after
    return expected, {"changes": changes, "slots_added_or_deleted": False, "Gold_read": False}


def _expected_locagent(original, index, checks, iid):
    from code_multiswe_java_signature_v2_20261117.normalize import replay_locagent
    if original.get("status") not in ("complete", "partial"):
        return copy.deepcopy(original), {"new_model_calls": 0, "Gold_read": False, "view_applied": False,
            "reason": "Original task did not deliver normal aggregation; do not salvage failed-task answers"}
    expected, provenance = replay_locagent(original, index)
    checks.check(len(expected.get("samples", [])) == len(original.get("samples", [])), "sample_count_preserved", instance_id=iid)
    for old_sample, new_sample, record in zip(original.get("samples", []), expected.get("samples", []), provenance["samples"]):
        checks.check(old_sample.get("raw_location") == new_sample.get("raw_location"), "literal_raw_location_preserved", instance_id=iid)
        for change in record["changes"]:
            checks.check(token_equivalent(change["original_value"], change["normalized_value"]),
                         "raw_signature_tokens_preserved", instance_id=iid, line=change["line"])
        checks.check(old_sample.get("status") == new_sample.get("status") and old_sample.get("usage") == new_sample.get("usage"),
                     "sample_state_usage_preserved", instance_id=iid)
        if not old_sample.get("raw_location"):
            checks.check(new_sample["parsed"]["functions"] == [] and new_sample["parsed"]["files"] == [],
                         "empty_failure_answer_never_salvaged", instance_id=iid)
    return expected, provenance


def _links(origin, derived, checks, iid, arm):
    linked = []
    for path in origin.iterdir():
        if path.name in ("result.json", "terminal.json"):
            continue
        target = derived / path.name
        checks.check(target.is_symlink() and same_object(path, target), "original_resource_artifact_reused",
                     instance_id=iid, arm=arm, artifact=path.name)
        linked.append({"artifact": path.name, "source": str(path.resolve()), "target": str(target),
                       "same_object": same_object(path, target)})
    allowed = {p.name for p in origin.iterdir()} | {"normalization_provenance.json"}
    checks.check(not ({p.name for p in derived.iterdir()} - allowed), "no_unaccounted_derived_raw_artifacts", instance_id=iid, arm=arm)
    return linked


def _judge_rpc(origin, checks, iid):
    summary = Counter()
    for directory in sorted((origin / "judge_rpc").glob("*")):
        if not directory.is_dir():
            continue
        summary["attempts"] += 1
        request, start, receipt = (directory / name for name in ("request.json", "start.json", "receipt.json"))
        if not request.is_file() or not start.is_file() or not receipt.is_file():
            summary["unknown_or_incomplete"] += 1
            continue
        row, begin, response = read(request), read(start), read(receipt)
        public = row.get("row", row)
        text = public.get("model_input")
        digest = hashlib.sha256(text.encode()).hexdigest() if isinstance(text, str) else None
        checks.check(digest is not None and public.get("input_sha256") == digest == begin.get("input_sha256"),
                     "judge_rpc_input_binding", instance_id=iid, request_id=directory.name)
        if response.get("status") == "success":
            checks.check(response.get("judge_rpc_request_id") == directory.name and response.get("generated_output_tokens") == 0,
                         "judge_rpc_scoring_identity", instance_id=iid, request_id=directory.name)
            summary["successful"] += 1
        else:
            summary["non_success"] += 1
    return dict(summary)


def _report_comparison(root, view, checks):
    original = root / "reports/final128/summary.json"
    derived = root / "reports/signature_v2_evaluation/summary.json"
    a, b = read(original), read(derived)
    for key in ("allocated", "selected", "file_denominator", "function_denominator", "arm_status_counts"):
        checks.check(a.get(key) == b.get(key), "report_scope_and_status_unchanged", field=key)
    summary_changes = differences(a, b)
    source_resources, view_resources = root / "reports/resources128", root / "reports/signature_v2_resources"
    resource_a, resource_b = read(source_resources / "summary.json"), read(view_resources / "summary.json")
    checks.check(resource_a.get("totals") == resource_b.get("totals"), "resource_totals_reused_not_charged_twice")
    old_rpc, new_rpc = resource_a.get("judge_rpc_provenance_sha256", {}), resource_b.get("judge_rpc_provenance_sha256", {})
    normalized_rpc = {str(Path(path).resolve()): value for path, value in new_rpc.items()}
    expected_rpc = {str(Path(path).resolve()): value for path, value in old_rpc.items()}
    checks.check(normalized_rpc == expected_rpc, "judge_ledger_provenance_resolves_to_original")
    csv_a, csv_b = source_resources / "per_issue_resources.csv", view_resources / "per_issue_resources.csv"
    checks.check(sha(csv_a) == sha(csv_b), "per_issue_resource_csv_identical")
    files = []
    for old_name, new_name in (("final128", "signature_v2_evaluation"), ("failures128", "signature_v2_failures"),
                               ("resources128", "signature_v2_resources")):
        old_dir, new_dir = root / "reports" / old_name, root / "reports" / new_name
        relatives = {p.relative_to(old_dir).as_posix() for p in old_dir.rglob("*") if p.is_file()}
        relatives |= {p.relative_to(new_dir).as_posix() for p in new_dir.rglob("*") if p.is_file()}
        for relative in sorted(relatives):
            old_file, new_file = old_dir / relative, new_dir / relative
            old_sha, new_sha = (sha(old_file) if old_file.is_file() else None), (sha(new_file) if new_file.is_file() else None)
            files.append({"original": str(old_file), "derived": str(new_file), "original_sha256": old_sha,
                          "derived_sha256": new_sha, "same_bytes": old_sha == new_sha})
    return {"aggregate_summary_differences": summary_changes,
            "resource_summary_differences": differences(resource_a, resource_b),
            "all_report_file_pairs": files,
            "scope": "Aggregate values compared, all report files hashed; per-issue Gold metrics are delegated, never reselected here"}


def audit(root, *, expected_n=128):
    root = Path(root).resolve(strict=True)
    base = {"schema": "java128_signature_lineage_audit_v1", "root": str(root), "expected_new_model_calls": 0,
            "new_model_calls": 0, "gpu_used": False, "gold_labels_opened": False,
            "private_gold_hash_verification": "DEFERRED_TO_INDEPENDENT_METRICS_AUDIT",
            "scope_limits": ["No main metric recomputation or Gold-based version selection",
                "Original immutability is checked against terminal and view-manifest hashes, not unknowable pre-terminal history",
                "Symlink identity proves one physical source of requests/tools/RPC logs; views are not a second inference run",
                "Report CSV/JSON files containing per-issue Gold labels are hashed, not interpreted"],
            "started_unix": time.time()}
    closed = closure(root, expected_n)
    if not closed["ready"]:
        return {**base, "status": "WAITING_COMPLETION", "closure": closed}
    checks = Checks()
    allocation = read(root / "allocation.json")
    rows = allocation["records"]
    checks.check(allocation.get("n") == expected_n, "allocation_size_declared")
    checks.check(len(rows) == expected_n and len({r["instance_id"] for r in rows}) == expected_n, "fixed_unique_allocation")
    if checks.errors:
        return {**base, "status": "FAIL", "errors": checks.errors}
    frozen_sources = _bindings(root, checks)
    view = root / VIEW
    manifest_path = view / "view_manifest.json"
    manifest = read(manifest_path)
    checks.check(manifest.get("status") == "COMPLETE" and manifest.get("allocated") == expected_n,
                 "derived_view_closed")
    checks.check(Path(manifest.get("original_root", "")).resolve() == root and
                 manifest.get("source_allocation_sha256") == sha(root / "allocation.json"), "view_original_allocation_binding")
    checks.check(manifest.get("new_model_calls") == 0 and manifest.get("new_api_charge") == 0 and
                 manifest.get("normalization_uses_Gold") is False, "no_new_calls_cost_or_gold_normalization")
    checks.check(closed["normalized"].get("view_manifest_sha256") == sha(manifest_path), "cpu_completion_view_manifest_binding")
    checks.check(sha(view / "allocation.json") == sha(root / "allocation.json"), "derived_allocation_identical")
    derived_completion = read(view / "run/completion.json")
    checks.check(derived_completion.get("status") == "COMPLETE" and derived_completion.get("allocated") == expected_n
                 and derived_completion.get("groups") == expected_n, "derived_full_terminal_marker")
    checks.check(same_object(view / "evaluator_private", root / "evaluator_private"), "same_private_directory_binding_without_opening_labels")
    for marker in (closed["original"], closed["normalized"]):
        for file, expected in marker.get("outputs_sha256", {}).items():
            checks.check(Path(file).is_file() and sha(file) == expected, "cpu_delivery_frozen_sha", path=file)
    indexed = {}
    for record in manifest.get("records", []):
        key = (record.get("instance_id"), record.get("arm"))
        checks.check(key not in indexed, "unique_manifest_result_record", identity=list(key))
        indexed[key] = record
    actual_results, records = set(), []
    no_result = terminal_count = 0
    judge_totals = Counter()
    for row in rows:
        iid = row["instance_id"]
        index, index_sha = _public_binding(root, view, row, checks)
        source_group, derived_group = root / "run" / iid, view / "run" / iid
        group = read(source_group / "group_terminal.json")
        derived_group_marker = read(derived_group / "group_terminal.json")
        checks.check(group.get("instance_id") == iid and group.get("status") == "group_terminal", "original_group_closed", instance_id=iid)
        checks.check(derived_group_marker.get("instance_id") == iid and derived_group_marker.get("status") == "group_terminal",
                     "derived_group_closed", instance_id=iid)
        for arm in ARMS:
            origin, target = source_group / arm, derived_group / arm
            old_terminal, new_terminal = read(origin / "terminal.json"), read(target / "terminal.json")
            terminal_count += 1
            checks.check(old_terminal.get("instance_id") == iid and old_terminal.get("arm") == arm and
                         old_terminal.get("status") in TERMINAL and old_terminal.get("keep_in_denominator") is True,
                         "allocated_terminal_closed_and_retained", instance_id=iid, arm=arm)
            checks.check(group.get("arms", {}).get(arm) == old_terminal, "group_arm_terminal_binding", instance_id=iid, arm=arm)
            expected_terminal = {**old_terminal, "offline_view_only": True}
            links = _links(origin, target, checks, iid, arm)
            original_path, derived_path = origin / "result.json", target / "result.json"
            record = {"instance_id": iid, "arm": arm, "terminal_status": old_terminal.get("status"),
                      "base_index_sha256": index_sha, "linked_original_artifacts": links}
            if original_path.is_file():
                actual_results.add((iid, arm))
                source_sha = sha(original_path)
                checks.check(old_terminal.get("result_sha256") == source_sha, "original_result_terminal_sha", instance_id=iid, arm=arm)
                checks.check(derived_path.is_file() and not derived_path.is_symlink(), "derived_result_is_independent_file", instance_id=iid, arm=arm)
                original, derived = read(original_path), read(derived_path)
                expected, proof = (_expected_locagent(original, index, checks, iid) if arm == "locagent"
                                   else _expected_cosil(original, index, checks, iid, arm))
                expected["offline_identity_view"] = {"version": "java_signature_format_v2", "original_result": str(original_path),
                    "original_result_sha256": source_sha, "base_index_sha256": index_sha,
                    "new_model_calls": 0, "Gold_read_for_normalization": False}
                checks.check(expected == derived, "derived_exactly_declared_transform_all_other_fields_identical", instance_id=iid, arm=arm)
                proof_path = target / "normalization_provenance.json"
                checks.check(read(proof_path) == proof, "normalization_provenance_replay_identical", instance_id=iid, arm=arm)
                expected_terminal["result_sha256"] = sha(derived_path)
                manifest_record = indexed.get((iid, arm), {})
                checks.check(manifest_record.get("original_result_sha256") == source_sha and
                             manifest_record.get("derived_result_sha256") == sha(derived_path) and
                             manifest_record.get("provenance_sha256") == sha(proof_path), "view_manifest_result_sha_bindings", instance_id=iid, arm=arm)
                if arm == "locagent":
                    checks.check(original.get("ranked_files", []) == derived.get("ranked_files", []), "file_ranking_identical", instance_id=iid, arm=arm)
                    if "source_inventory_sha256" in original:
                        checks.check(original["source_inventory_sha256"] == index_sha, "locagent_source_inventory_binding", instance_id=iid)
                elif (origin / "worker_protocol.json").is_file():
                    protocol = read(origin / "worker_protocol.json")
                    checks.check(protocol.get("index_sha256") == index_sha, "cosil_worker_source_inventory_binding", instance_id=iid, arm=arm)
                # Record all changes without opening Gold or judging whether
                # the corrected identity is a benchmark target.
                record.update(original_result_sha256=source_sha, derived_result_sha256=sha(derived_path),
                    differences=differences(original, derived), result_present=True,
                    resource_fields_preserved=all(original.get(k) == derived.get(k) for k in
                        ("status", "usage", "known_prompt_tokens", "known_completion_tokens", "elapsed_seconds",
                         "stage_resources", "billed_api_usd", "generation_seconds", "tool_elapsed_seconds")))
                checks.check(record["resource_fields_preserved"], "status_usage_latency_cost_unchanged", instance_id=iid, arm=arm)
                checks.check(sha(original_path) == source_sha, "original_result_unchanged_during_audit", instance_id=iid, arm=arm)
            else:
                no_result += 1
                checks.check(not derived_path.exists() and old_terminal.get("result_sha256") is None and
                             old_terminal.get("status") not in ("complete", "partial"),
                             "legitimate_missing_result_remains_missing", instance_id=iid, arm=arm)
                checks.check((iid, arm) not in indexed, "no_fake_manifest_transformation_for_absent_result", instance_id=iid, arm=arm)
                record.update(result_present=False, model_called=old_terminal.get("model_called", "UNKNOWN"))
            checks.check(new_terminal == expected_terminal, "terminal_state_timing_denominator_unchanged", instance_id=iid, arm=arm)
            checks.check(derived_group_marker.get("arms", {}).get(arm) == new_terminal,
                         "derived_group_arm_terminal_binding", instance_id=iid, arm=arm)
            if arm == "sfpruner":
                rpc = _judge_rpc(origin, checks, iid)
                judge_totals.update(rpc)
                record["original_judge_rpc"] = rpc
            records.append(record)
        for child in source_group.iterdir():
            if child.name not in (*ARMS, "group_terminal.json"):
                checks.check((derived_group / child.name).is_symlink() and same_object(child, derived_group / child.name),
                             "shared_group_input_resource_reused", instance_id=iid, artifact=child.name)
    checks.check(terminal_count == expected_n * len(ARMS), "all_allocated_terminals_checked")
    checks.check(set(indexed) == actual_results, "manifest_records_exactly_actual_original_results",
                 absent=[list(k) for k in sorted(actual_results - set(indexed))], extra=[list(k) for k in sorted(set(indexed) - actual_results)])
    reports = _report_comparison(root, view, checks)
    return {**base, "status": "PASS" if not checks.errors else "FAIL", "finished_unix": time.time(),
        "checks": checks.count, "errors": checks.errors, "allocated_tasks": expected_n,
        "terminal_conditions_checked": terminal_count, "result_transformations": len(actual_results),
        "legitimate_no_result_terminals": no_result, "manifest_records": len(indexed),
        "private_gold_files_opened": 0, "closure_marker_sha256": closed["marker_sha256"],
        "frozen_sources": frozen_sources, "physical_accounting": {"original_judge_rpc": dict(judge_totals),
            "derived_inference_runs": 0, "resource_csv_identical_required": True,
            "interpretation": "Original and derived resource tables describe the same physical requests; do not add their totals"},
        "records": records, "report_comparison": reports, "auditor_source_sha256": sha(__file__)}


def write_new(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError("Never replace an existing audit: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    descriptor, name = tempfile.mkstemp(prefix=".lineage-audit-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    output = args.out if args.out.is_absolute() else root / args.out
    try:
        result = audit(root)
    except Exception as error:
        result = {"status": "FAIL", "error": type(error).__name__ + ": " + str(error),
                  "new_model_calls": 0, "gold_labels_opened": False, "scope": "Lineage audit aborted; do not interpret as a passed study"}
    write_new(output, result)
    print(json.dumps({k: result.get(k) for k in ("status", "checks", "terminal_conditions_checked", "result_transformations", "error")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
