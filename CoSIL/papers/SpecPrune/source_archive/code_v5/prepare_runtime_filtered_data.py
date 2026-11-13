"""Prepare B data from frozen v3 static eligibility plus failed-test coverage.

Before all 300 issue results exist, only --dry-run is allowed. This program never
decodes an old sealed test, trains, calls a model, or modifies frozen A code/data.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import tokenize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from code_v5.runtime_filtered_policy import (SOURCE, POLICY, assess_result, assert_tests_sealed,
    canonical, gold_ids, pair, read_json, read_rows, replay_frozen_source, row_bytes,
    runtime_metadata, sha, triple)

DEFAULT_RUNTIME = ROOT / "results/v5_pruner/runtime_coverage/cases_final"
DEFAULT_OUTPUT = ROOT / "results/v5_pruner/data_v3_runtime_filtered"
DEFAULT_REPORT = ROOT / "docs/v5-pruner/B运行覆盖过滤_数据准备说明.md"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def json_write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def load_runtime(context, directory):
    directory = Path(directory).resolve()
    policy_path = directory.parent / "execution_policy_frozen.json"
    policy = read_json(policy_path)
    if Path(policy["result_directory"]).resolve() != directory:
        raise RuntimeError("Only collector's frozen final case directory is authorized")
    for name, expected in policy["code_sha256"].items():
        if sha(ROOT / "code_v5" / name) != expected:
            raise RuntimeError("Frozen runtime instrumentation changed: " + name)
    paths = {p.parent.name: p for p in directory.glob("*/result.json")}
    extras = set(paths) - set(context["issues"])
    if extras:
        raise RuntimeError("Foreign issue IDs in B runtime directory: " + repr(sorted(extras)))
    evidence, snapshots, trace_hashes = {}, {}, {}
    for iid, issue in context["issues"].items():
        if iid not in paths:
            evidence[iid] = {"status": "runtime_unavailable", "qualified": False,
                "unavailable_reasons": ["not_completed_yet_dry_run_only"], "collector_status": "missing",
                "result_path": None, "result_sha256": None, "input_fingerprint": None,
                "coverage_scope": None, "covered": set(), "covered_count": 0, "limitations": []}
            continue
        path = paths[iid]; result = read_json(path)
        if result.get("completed_at") is None:
            raise RuntimeError("Result lacks permanent completion marker: " + iid)
        if (result.get("collector_sha256") != policy["code_sha256"]["runtime_coverage.py"]
                or result.get("probe_sha256") != policy["code_sha256"]["runtime_coverage_probe.py"]):
            raise RuntimeError("Nonfinal instrumentation cached result: " + iid)
        if result.get("input_spec", {}).get("code") not in (None, policy["code_sha256"]):
            raise RuntimeError("Result fingerprint contains foreign instrumentation: " + iid)
        if result.get("input_spec") or result.get("input_fingerprint"):
            if (not isinstance(result.get("input_spec"), dict)
                    or hashlib.sha256(json.dumps(result["input_spec"], sort_keys=True).encode()).hexdigest() != result.get("input_fingerprint")):
                raise RuntimeError("Cached runtime input fingerprint is corrupt: " + iid)
        evidence[iid] = assess_result(result, path, issue, context["gold"][iid])
        snapshots[str(path)] = sha(path)
        for trace in result.get("trace_files", []):
            trace_path = Path(trace["path"])
            if (trace_path.resolve().parent != (path.parent / "traces").resolve()
                    or not trace_path.is_file() or sha(trace_path) != trace.get("sha256")):
                raise RuntimeError("Cached runtime trace artifact is corrupt: " + iid)
            trace_hashes[str(trace_path)] = trace["sha256"]
    return evidence, {"result_directory": str(directory), "result_count": len(paths),
        "missing_ids": sorted(set(context["issues"]) - set(paths)), "all_300_completed": len(paths) == 300,
        "frozen_collector_policy_path": str(policy_path), "frozen_collector_policy_sha256": sha(policy_path),
        "collector_code_sha256": policy["code_sha256"], "result_sha256": snapshots,
        "trace_artifact_sha256": trace_hashes}


def prepare_rows(context, evidence):
    """Use original positive eligibility, frozen dedup and unchanged sampling."""
    from code_v5 import build_pruner_data as miner
    excluded, filtered = [], []
    errors = {triple(r) for r in context["errors"]}
    for row in context["pool"]:
        ev = evidence[row["instance_id"]]
        if not row["label"] and triple(row) in errors:
            excluded.append({"instance_id": row["instance_id"], "function_id": row["function_id"],
                "input_sha256": row["input_sha256"], "split": row["split"],
                "reason": "signed_v3_confirmed_train_error", "runtime_result": runtime_metadata(ev)})
        elif not row["label"] and ev["qualified"] and row["function_id"] in ev["covered"]:
            excluded.append({"instance_id": row["instance_id"], "function_id": row["function_id"],
                "input_sha256": row["input_sha256"], "split": row["split"],
                "reason": "covered_on_valid_failed_test_path_or_bootstrap", "runtime_result": runtime_metadata(ev)})
        else:
            filtered.append(deepcopy(row))
    cleaned, audit = miner.deduplicate_inputs(filtered)
    eligible = deepcopy(context["positives"]) + [r for r in cleaned if not r["label"]]
    if {canonical(r) for r in eligible if r["label"]} != {canonical(r) for r in context["positives"]}:
        raise RuntimeError("Original positive eligibility changed")
    for row in eligible:
        row["runtime_filter"] = runtime_metadata(evidence[row["instance_id"]], positive=row["label"])
    selected, sampling = miner.sample_rows(eligible, context["manifest"]["seed"])
    if len({r["input_sha256"] for r in selected}) != len(selected):
        raise RuntimeError("Input duplication/leakage after B filtering")
    if {triple(r) for r in selected} & errors or sum(x["reason"] == "signed_v3_confirmed_train_error" for x in excluded) != 3:
        raise RuntimeError("Known three train errors must be excluded, never relabelled")
    if len([r for r in selected if r["label"]]) != 1542:
        raise RuntimeError("Lost or resurrected positive pair")
    for r in selected:
        ev = evidence[r["instance_id"]]
        if not r["label"] and ev["qualified"] and r["function_id"] in ev["covered"]:
            raise RuntimeError("Covered negative reappeared after dedup/sampling")
    return eligible, selected, excluded, sampling, audit


def runtime_distribution(rows):
    counts = Counter()
    by_split = {s: Counter() for s in ("train", "val", "test")}
    for r in rows:
        category = ("positive_original" if r["label"] else
                    "negative_runtime_filtered" if r["runtime_filter"]["qualified"] else "negative_static_only_runtime_unavailable")
        counts[category] += 1; by_split[r["split"]][category] += 1
    return {"all": dict(counts), "by_split": {s: dict(v) for s, v in by_split.items()}}


class Definitions(ast.NodeVisitor):
    def __init__(self): self.scope = []; self.nodes = {}
    def visit_ClassDef(self, node):
        self.scope.append(node.name); self.generic_visit(node); self.scope.pop()
    def visit_FunctionDef(self, node):
        name = ".".join(self.scope + [node.name]); self.nodes[(name, node.lineno)] = node
        self.scope.append(node.name); self.generic_visit(node); self.scope.pop()
    visit_AsyncFunctionDef = visit_FunctionDef


def review_packet(samples, context, evidence):
    """Verified candidate/gold source, issue/patch, static origin and runtime refs."""
    cache = {}; packet = []
    def function_source(row, fid):
        filename, target = fid.split("::", 1); qualified, line = target.rsplit("@", 1)
        key = row["repo"], row["base_commit"], filename
        if key not in cache:
            mirror = ROOT / "mirror_cache" / (row["repo"].rsplit("/", 1)[-1] + ".git")
            prefix = ["git", "--git-dir", str(mirror)]
            blob = subprocess.run(prefix + ["rev-parse", row["base_commit"] + ":" + filename], capture_output=True, check=True, timeout=30).stdout.decode().strip()
            data = subprocess.run(prefix + ["cat-file", "blob", blob], capture_output=True, check=True, timeout=30).stdout
            if hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() != blob:
                raise RuntimeError("Source Git blob hash drift")
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
            source = data.decode(encoding); inventory = Definitions(); inventory.visit(ast.parse(source, filename))
            cache[key] = source, inventory.nodes, blob
        source, nodes, blob = cache[key]; node = nodes[(qualified, int(line))]
        full = "".join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
        calls = [{"line": n.lineno, "expression": ast.get_source_segment(source, n)} for n in ast.walk(node) if isinstance(n, ast.Call)]
        return {"function_id": fid, "file": filename, "base_blob_sha1": blob,
            "full_source_sha256": hashlib.sha256(full.encode()).hexdigest(), "full_source": full, "calls": calls}
    for r in samples:
        entry = {"identity": {k: r[k] for k in ("review_family", "instance_id", "function_id", "input_sha256")},
                 "review_status": "pending", "reviewer": "Codex/机械证据审阅（非真人签字）",
                 "original_static_provenance": r["provenance"], "original_graph": r["graph"],
                 "full_issue": context["issues"][r["instance_id"]]["problem_statement"],
                 "official_patch": context["issues"][r["instance_id"]]["patch"],
                 "runtime_evidence": runtime_metadata(evidence[r["instance_id"]]),
                 "causal_scope": "Source/runtime evidence supports exclusion risk only. Coverage absence never certifies irrelevance or zero noise."}
        try:
            entry["candidate"] = function_source(r, r["function_id"])
            if entry["candidate"]["full_source_sha256"] != r["full_function_source_sha256"]:
                raise RuntimeError("Candidate full source differs from frozen row")
            entry["gold"] = {fid: function_source(r, fid) for fid in sorted(gold_ids(context["gold"][r["instance_id"]]))}
            entry["source_evidence_complete"] = True
        except (RuntimeError, KeyError, SyntaxError, UnicodeError, subprocess.SubprocessError) as error:
            entry["source_evidence_complete"] = False; entry["source_evidence_error"] = repr(error)
        packet.append(entry)
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--plan-output", type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true"); action.add_argument("--freeze", action="store_true")
    args = parser.parse_args(); began = time.perf_counter()
    context = replay_frozen_source(); evidence, runtime_manifest = load_runtime(context, args.runtime_dir)
    eligible, selected, excluded, sampling, input_audit = prepare_rows(context, evidence)
    from code_v5 import build_pruner_data as miner
    samples = miner.review_samples(selected, context["manifest"]["seed"])
    plan = {"data_policy": POLICY, "track": "exploratory", "created_at": now(), "dry_run": args.dry_run,
        "runtime_manifest": runtime_manifest, "source_replay": context["source_replay"],
        "official_runtime_metadata_source": context["official_runtime_metadata_source"],
        "source_statistics_sha256": sha(SOURCE / "statistics.json"), "source_review_sha256": sha(SOURCE / "human_review_codex_reviewed.jsonl"),
        "runtime_issue_status_counts": dict(Counter(e["status"] for e in evidence.values())),
        "runtime_completed_qualified": sum(e["qualified"] for e in evidence.values() if e["result_path"]),
        "runtime_completed_unavailable": sum(not e["qualified"] for e in evidence.values() if e["result_path"]),
        "runtime_pending_dry_run_only": len(runtime_manifest["missing_ids"]),
        "preview_selected_counts_not_final_before_300": miner.summarize(selected),
        "preview_runtime_distribution": runtime_distribution(selected),
        "excluded_reasons": dict(Counter(r["reason"] for r in excluded)),
        "review_family_counts": dict(Counter(r["review_family"] for r in samples)),
        "review_signed": False, "training_allowed": False, "model_calls": 0, "old_test_rows_decoded": False,
        "estimated_data_build_seconds_observed": time.perf_counter() - began}
    if args.dry_run:
        if args.plan_output:
            path = args.plan_output.resolve()
            frozen_dirs = [SOURCE.parent / name for name in ("data", "data_v2", "data_v3", "data_v3_noise_disclosed", "data_v3_runtime_filtered")]
            if path.suffix != ".json" or "plan" not in path.stem or any(path.is_relative_to(p) for p in frozen_dirs):
                raise PermissionError("Never write a dry-run plan into frozen source/A data")
            path.parent.mkdir(parents=True, exist_ok=True); json_write(path, plan)
        print(json.dumps({k: v for k, v in plan.items() if k != "runtime_manifest"}, ensure_ascii=False, indent=2))
        return
    if not runtime_manifest["all_300_completed"]:
        raise RuntimeError("B cannot freeze before exactly all 300 result.json files complete; use --dry-run")
    output = args.output.resolve()
    assert_tests_sealed(output)
    if output.exists(): raise FileExistsError("B dataset is immutable; existing output must be preserved")
    frozen_dirs = [SOURCE.parent / name for name in ("data", "data_v2", "data_v3", "data_v3_noise_disclosed")]
    if any(output.is_relative_to(p) for p in frozen_dirs):
        raise PermissionError("B must have a separate new directory")
    packet = review_packet(samples, context, evidence)
    for p, expected in runtime_manifest["result_sha256"].items():
        if sha(p) != expected: raise RuntimeError("Permanent runtime result changed during preparation")
    for p, expected in context["protected_hashes"].items():
        if sha(ROOT / p) != expected: raise RuntimeError("Original v3 protected bytes changed")
    for p, expected in context["official_runtime_metadata_source"]["file_sha256"].items():
        if sha(p) != expected: raise RuntimeError("Official benchmark runtime metadata changed")
    output.mkdir(parents=True)
    (output / "split_manifest.json").write_bytes((SOURCE / "split_manifest.json").read_bytes())
    miner.write_jsonl(output / "candidate_pool.jsonl", eligible, immutable=True)
    miner.write_jsonl(output / "negative_exclusions.jsonl", excluded, immutable=True)
    sealed = {}
    for split in ("train", "val", "test"):
        path = output / f"pruner_{split}.jsonl"
        subset = [r for r in selected if r["split"] == split]
        path.write_bytes(row_bytes(subset)); sealed[split] = {"path": str(path), "sha256": sha(path), "count": len(subset)}
    seal = {"schema_version": 1, "dataset_version": POLICY, "test_path": sealed["test"]["path"],
            "sha256": sealed["test"]["sha256"], "test_sha256": sealed["test"]["sha256"], "count": sealed["test"]["count"],
            "split_manifest_sha256": sha(output / "split_manifest.json"), "frozen_files": sealed,
            "test_performance_opened": False, "old_test_rows_opened": False,
            "allowed_before_open": "provenance/count/hash only; current B training uses only train/val"}
    json_write(output / "test_file_seal.json", seal); miner.write_jsonl(output / "human_review.jsonl", samples, immutable=True)
    json_write(output / "runtime_manifest.json", runtime_manifest)
    json_write(output / "review_source_runtime_evidence.json", {"status": "pending_Codex_source_runtime_review", "review_signed": False, "records": packet})
    a_val = read_rows(ROOT / "results/v5_pruner/data_v3_noise_disclosed/pruner_val.jsonl")
    a_keys = {triple(r): r for r in a_val}; b_val = {triple(r): r for r in selected if r["split"] == "val"}
    shared = sorted(a_keys.keys() & b_val.keys())
    comparison = {"A_val_count": len(a_keys), "B_val_count": len(b_val), "shared_val_count": len(shared),
                  "shared_val_pairs": [{"instance_id": iid, "function_id": fid, "input_sha256": digest,
                                        "label": a_keys[(iid, fid, digest)]["label"]} for iid, fid, digest in shared],
                  "interpretation": "Compare whole-val metrics with changed pair supply disclosed; also compare this common pair subset. No test predictions opened."}
    if any(a_keys[k]["label"] != b_val[k]["label"] for k in shared): raise RuntimeError("Shared A/B val label drift")
    json_write(output / "comparison_A_B_val_shared_pairs.json", comparison)
    counts = miner.summarize(selected); p = counts.get("positive", 0); n = counts.get("negative", 0); e = counts.get("E_unique_union", 0)
    quality = {"positive_unique_pairs_ge_8000": p >= 8000, "E_unique_pairs_ge_3000": e >= 3000,
        "negative_to_positive_ratio_about_2": bool(p and 1.8 <= n / p <= 2.2), "E_fraction_of_negatives_ge_one_third": bool(n and e / n >= 1/3),
        "ordinary_D_negatives_retained": counts.get("primary_source_D", 0) > 0,
        "issue_split_disjoint_240_30_30": True, "truncated_inputs_unique_and_disjoint": True,
        "all_base_gold_regions_mapped": context["stats"]["quality_gates"]["all_base_gold_regions_mapped"],
        "review_30_train_E_examples_at_most_2_errors": False}
    stats = {"schema_version": 1, "dataset_version": POLICY, "data_policy": POLICY, "track": "exploratory",
        "mechanical_labels_only": True, "model_calls": 0, "training_started": False, "test_performance_opened": False,
        "sources": deepcopy(context["stats"]["sources"]), "selected": counts, "candidate_pool": miner.summarize(eligible),
        "raw_counts": deepcopy(context["stats"]["raw_counts"]),
        "raw_counts_scope": "original frozen v1 mining observations; B coverage exclusions and actual selected supply reported separately",
        "sampling": sampling, "truncated_input_audit": input_audit, "runtime_distribution": runtime_distribution(selected),
        "quality_gates": quality, "passed": False, "seal": seal, "split_manifest_sha256": seal["split_manifest_sha256"],
        "source_replay": context["source_replay"], "runtime_manifest_sha256": sha(output / "runtime_manifest.json"),
        "review": {"passed": False, "status": "awaiting_train_only_Codex_source_runtime_review", "reviewed_records": 0,
                   "label_errors": None, "requested_family_counts": {"e_log": 10, "e_bm25": 10, "e_anchor": 10},
                   "actual_family_counts": dict(Counter(r["review_family"] for r in samples)),
                   "noise_disclosure_policy": True, "human_signature": False},
        "excluded_reasons": plan["excluded_reasons"], "known_three_train_errors_excluded": True,
        "limitations": ["Observed function coverage absence does not prove irrelevance or zero remaining noise.",
            "Unusable/failed runtime issues remain pure-static and are individually flagged; the dataset is not uniformly runtime-verified.",
            "Native extensions, hard-exit/foreign-interpreter subprocesses and untested branches can evade observed Python coverage.",
            "B resamples negative supply, so full-val denominators and pair identities can change; common A/B val pairs are separately provided.",
            "1542 positives retain original eligibility; four originally ineligible raw positive pairs are not resurrected.",
            "30-family-stratified review cannot estimate overall noise or prove a static error floor."],
        "preparation_code_sha256": {n: sha(ROOT / "code_v5" / n) for n in ("prepare_runtime_filtered_data.py", "runtime_filtered_policy.py")}}
    json_write(output / "statistics.json", stats)
    json_write(output / "derivation.json", {**plan, "dry_run": False, "frozen": True, "selected_counts": counts,
        "original_source_protected_sha256": context["protected_hashes"], "new_labels_generated": 0,
        "review_packet_sha256": sha(output / "review_source_runtime_evidence.json"), "shared_val_sha256": sha(output / "comparison_A_B_val_shared_pairs.json")})
    receipt = {"data_policy": POLICY, "construction_completed": True,
        "source_replay": context["source_replay"], "known_three_train_errors_excluded": True,
        "source_statistics_sha256": sha(SOURCE / "statistics.json"),
        "source_review_sha256": sha(SOURCE / "human_review_codex_reviewed.jsonl"),
        "source_protected_sha256": context["protected_hashes"],
        "original_raw_pool": context["stats"]["reconstruction_sources"]["candidate_pool.jsonl"],
        "official_runtime_metadata_source": context["official_runtime_metadata_source"],
        "runtime_manifest": runtime_manifest,
        "raw_statistics_payload_sha256": hashlib.sha256(canonical(stats).encode()).hexdigest(),
        "raw_files_sha256": {p.name: sha(p) for p in output.iterdir() if p.is_file() and p.name != "statistics.json"},
        "boundary": "Full candidate pools including test-role rows are constructed only during preparation/freeze. Model gates hash construction evidence and read train/val; they do not decode sealed test or replay test-role labels."}
    json_write(output / "construction_receipt.json", receipt)
    stats["construction_receipt_sha256"] = sha(output / "construction_receipt.json")
    json_write(output / "statistics.json", stats)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(f"# B 运行覆盖过滤版数据准备\n\n已按同一 Lite300 issue、原切分与 seed 冻结新数据；审阅尚未签，训练未启动。\n\n正例 {p}、负例 {n}、E {e}、D-only {counts.get('primary_source_D', 0)}。全部数值为实际独立 pair，未补造标签。\n\n运行资格：{dict(Counter(ev['status'] for ev in evidence.values()))}；负例分层：{stats['runtime_distribution']}。失败/不完整题保留纯静态负例并逐条标记，不能将全数据称为无噪声或干净真值。\n\n重抽 train 三族各10条实际数量：{stats['review']['actual_family_counts']}；完整候选/金标源码、issue/官方patch、原静态来源及runtime证据在 `{output / 'review_source_runtime_evidence.json'}`。Codex逐条审阅仍pending，不是真人人工签字。\n\nA/B共同val有 {len(shared)} pair；全val指标和共同pair指标须分别披露。旧test文件只hash，未解码；新B test由原候选池固定规则生成并封存，当前只允许train/val。\n\n局限：{'; '.join(stats['limitations'])}\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "statistics_sha256": sha(output / "statistics.json"), "selected": counts,
                      "review_signed": False, "training_started": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
