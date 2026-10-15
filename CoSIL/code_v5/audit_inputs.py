"""Inventory existing v5 inputs without creating labels or opening training splits.

Only a new input_audit.json is written. Existing output files are never replaced.
The existing v3c scoring functions are reused; no gold definition is changed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v3b.analyze_experiment_300 import expected, predictions, ranking_metrics

ARMS = ("off", "on", "shuffled")
READ_SOURCES = {}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe(path, hash_content=True):
    path = Path(path).resolve()
    info = {"path": str(path), "exists": path.exists()}
    if path.is_file():
        info["bytes"] = path.stat().st_size
        if hash_content:
            info["sha256"] = sha256(path)
            READ_SOURCES[str(path)] = info["sha256"]
    return info


def load_json(path):
    describe(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path):
    describe(path)
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def counted(values):
    return dict(sorted(Counter(values).items()))


def audit_formal(root, issue_ids, gold, metrics):
    result = {}
    issues = []
    for arm in ARMS:
        folder = root / "results/qwen_300/fixed" / arm
        cases = sorted((folder / "cases").glob("*.json"))
        event_files = sorted((folder / "events").glob("*.jsonl"))
        event_counts = Counter()
        verdicts, tools, prune_tools = Counter(), Counter(), Counter()
        parsed_cases = {}
        valid_prunes = 0
        trace_problems = []
        prune_count_by_issue = {}
        for path in cases:
            case = load_json(path)
            iid = case.get("instance_id")
            if iid in parsed_cases or iid != path.stem or case.get("arm") != arm:
                trace_problems.append({"path": str(path), "problem": "case ID/arm/uniqueness"})
            parsed_cases[iid] = case
        traces = set()
        for path in event_files:
            rows = load_jsonl(path)
            iid = path.stem.removeprefix(arm + "_")
            traces.add(iid)
            if any(row.get("instance_id") != iid or row.get("arm") != arm for row in rows):
                trace_problems.append({"path": str(path), "problem": "mixed event IDs or arms"})
            local = Counter(row.get("event", "missing_event") for row in rows)
            event_counts.update(local)
            prune_count_by_issue[iid] = local["prune"]
            if local["run_start"] != 1 or local["run_end"] != 1:
                trace_problems.append({"path": str(path), "problem": "not one complete run"})
            fetched = {(row.get("step"), row.get("tool"), tuple(row.get("arguments", [])))
                       for row in rows if row.get("event") == "tool_result"
                       and row.get("success") and row.get("kind") == "source"}
            for row in rows:
                event = row.get("event")
                if event == "tool_result" and row.get("success") and row.get("kind") == "source":
                    tools[row.get("tool", "missing")] += 1
                if event == "prune":
                    verdicts[str(row.get("decision", "missing"))] += 1
                    prune_tools[row.get("tool", "missing")] += 1
                    key = (row.get("step"), row.get("tool"), tuple(row.get("arguments", [])))
                    valid_prunes += key in fetched
        case_match = set(parsed_cases) == issue_ids
        event_match = traces == issue_ids
        if not case_match or not event_match or trace_problems:
            issues.append({"arm": arm, "problem": "formal cohort/trace integrity"})
        eligible, hits = 0, 0
        for iid, case in parsed_cases.items():
            if iid not in gold:
                continue
            targets = expected(gold[iid], "function")
            if targets:
                eligible += 1
                hits += ranking_metrics(predictions(case["found_related_locs"]), targets)["top5"]
        anchor_rows = metrics["cases"][arm]
        result[arm] = {
            "case_files": len(cases), "event_files": len(event_files),
            "case_ids_match_300": case_match, "event_ids_match_300": event_match,
            "case_statuses": counted(case.get("status", "missing") for case in parsed_cases.values()),
            "event_counts": dict(event_counts), "prune_decisions": dict(verdicts),
            "prune_tool_types": dict(prune_tools), "successful_source_tool_types": dict(tools),
            "prunes_with_matching_successful_source": valid_prunes,
            "prune_counts_by_issue": prune_count_by_issue,
            "trace_problems": trace_problems,
            "function_top5": {"hits": hits, "eligible": eligible,
                              "rate": hits / eligible if eligible else None,
                              "existing_score_functions": ["predictions", "expected", "ranking_metrics"]},
            "anchors_all_300": counted(case["anchor"] for case in anchor_rows),
            "anchors_function_scorable": counted(case["anchor"] for case in anchor_rows
                                                  if case["function_scorable"]),
        }
    return result, issues


def audit_old_logs(root):
    paths = sorted((root / "results/prune_logs_annot").glob("*.jsonl"))
    counts, events, ids, prunes = Counter(), Counter(), set(), 0
    details = []
    for path in paths:
        rows = load_jsonl(path)
        arm, iid = path.stem.split("_", 1)
        counts[arm] += 1
        ids.add(iid)
        local = Counter(row.get("event", "missing_event") for row in rows)
        events.update(local)
        prunes += local["prune"]
        details.append({"file": str(path.resolve()), "arm": arm, "instance_id": iid,
                        "rows": len(rows), "prunes": local["prune"]})
    return {"path": str((root / "results/prune_logs_annot").resolve()),
            "files": len(paths), "files_by_arm": dict(counts), "unique_issues": len(ids),
            "instance_ids": sorted(ids), "event_counts": dict(events), "prunes": prunes,
            "files_detail": details,
            "limitation": "Legacy ten-issue logs; not the formal 900-run v3c source."}


def audit_structures(root, issue_ids, gold):
    folder = root / "repo_structures_verified"
    available, mismatches, unreadable = [], [], []
    for iid in sorted(issue_ids):
        path = folder / (iid + ".json")
        if not path.is_file():
            unreadable.append({"instance_id": iid, "reason": "missing"})
            continue
        info = describe(path, hash_content=False)
        try:
            with path.open("rb") as stream:
                prefix = stream.read(4096).decode("utf-8")
            repo = re.search(r'"repo"\s*:\s*("(?:[^"\\]|\\.)*")', prefix)
            commit = re.search(r'"base_commit"\s*:\s*("(?:[^"\\]|\\.)*")', prefix)
            info["repo_header"] = json.loads(repo[1]) if repo else None
            info["base_commit_header"] = json.loads(commit[1]) if commit else None
            info["header_matches_gold"] = (info["repo_header"] == gold[iid]["repo"]
                                           and info["base_commit_header"] == gold[iid]["base_commit"])
            if not info["header_matches_gold"]:
                mismatches.append(iid)
        except (OSError, UnicodeError, ValueError) as exc:
            unreadable.append({"instance_id": iid, "reason": str(exc)})
        available.append(info)
    return {"path": str(folder.resolve()), "files": len(available),
            "total_bytes": sum(item["bytes"] for item in available),
            "header_base_commit_mismatches": mismatches, "unreadable": unreadable,
            "files_detail": available,
            "scope": "Readability and repo/base_commit prefix audit only; 22 GB of source bodies not decoded or hashed.",
            "total_structure_function_count": None,
            "function_count_status": "Deferred to source-mining stage; do not equate gold count with repository function count."}


def build_audit(root, handoff):
    prepared_path = root / "results/qwen_300/prepared_inputs.json"
    metrics_path = root / "results/qwen_300/metrics.json"
    gold_path = root / "ground_truth_300.json"
    prepared, metrics, gold = [load_json(path) for path in (prepared_path, metrics_path, gold_path)]
    instance_list = prepared["instances"]
    ids = set(instance_list)
    if len(instance_list) != 300 or len(ids) != 300 or set(gold) != ids:
        raise ValueError("Existing prepared cohort/gold must contain the same 300 unique issue IDs")
    formal, problems = audit_formal(root, ids, gold, metrics)
    structures = audit_structures(root, ids, gold)
    base_pairs = {(iid, region["file"], region["name"])
                  for iid, item in gold.items() for region in item.get("existing_gold_function_regions", [])}
    new_pairs = {(iid, name) for iid, item in gold.items() for name in item.get("new_functions", [])}
    all_gold = sum(sum(len(names) for names in item["gold_functions_by_file"].values()) for item in gold.values())
    auxiliary_names = ("周计划_v5执行周_2026-10-12.md", "v5剪枝裁判_训练全流程保姆级.md")
    auxiliary = {name: [describe(folder / name) for folder in (handoff.parent, root)]
                 for name in auxiliary_names}
    known_graph_paths = [root / "code_v3/ppr_batch.py", root / "results/ppr",
                         root / "results/call_graphs", root / "call_graphs",
                         root / "results/qwen_300/call_graphs"]
    known_graph = [describe(path) for path in known_graph_paths]
    patch_paths = [root / "code_v3b/fixed_search.py", root / "code_v3b/AFL_插桩版.py",
                   root / "code_v3b/AFL_插桩版_分派修复.py", root / "code_v3b/run_experiment_300.py",
                   root / "code_v3b/run_experiment.py", root / "code_v3b/build_ground_truth_300.py",
                   root / "code_v3b/analyze_experiment_300.py", root / "code_v3b/test_ground_truth_300.py"]
    patch_files = []
    frozen_hashes = prepared["configuration"]["sha256"]
    for path in patch_paths:
        item = describe(path)
        relative = str(path.relative_to(root))
        item["prepared_config_sha256"] = frozen_hashes.get(relative)
        item["matches_prepared_config"] = (item.get("sha256") == frozen_hashes[relative]
                                            if relative in frozen_hashes else None)
        patch_files.append(item)
    off = formal["off"]["function_top5"]
    checks = {"same_unique_300_ids": True, "formal_900_event_files": sum(v["event_files"] for v in formal.values()) == 900,
              "formal_900_case_files": sum(v["case_files"] for v in formal.values()) == 900,
              "formal_traces_one_complete_run_each": not problems,
              "gold_derivation_version_3": all(item.get("derivation_version") == 3 for item in gold.values()),
              "base_gold_unique_functions_321": len(base_pairs) == 321,
              "new_gold_functions_47": len(new_pairs) == 47,
              "off_baseline_111_of_293": off["hits"] == 111 and off["eligible"] == 293,
              "off_recomputed_matches_existing_metrics": off["hits"] == metrics["summary"]["off"]["function_top5"]
                   and off["eligible"] == metrics["summary"]["off"]["function_cases"],
              "structures_300_readable_matching_gold_headers": len(structures["files_detail"]) == 300
                   and not structures["unreadable"] and not structures["header_base_commit_mismatches"],
              "fixed_search_matches_frozen_input_configuration": next(item for item in patch_files
                    if item["path"] == str((root / "code_v3b/fixed_search.py").resolve()))["matches_prepared_config"]}
    return {"schema_version": 1, "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "phase": "D1 read-only inventory", "repository_root": str(root), "handoff": describe(handoff),
            "protected_actions": {"labels_created": False, "model_calls": 0, "training_started": False,
                                  "new_pruner_train_val_test_opened": False, "benchmark_dataset_opened": False,
                                  "historical_input_writes": False},
            "cohort": {"instances": 300, "issue_ids": instance_list, "source": describe(prepared_path)},
            "auxiliary_document_candidates": auxiliary,
            "missing_auxiliary_documents": [name for name, choices in auxiliary.items()
                                            if not any(item["exists"] for item in choices)],
            "formal_v3c": formal, "legacy_prune_logs": audit_old_logs(root),
            "gold": {"source": describe(gold_path), "derivation_versions": counted(item["derivation_version"] for item in gold.values()),
                     "all_gold_function_pairs": all_gold, "base_existing_unique_function_pairs": len(base_pairs),
                     "new_functions_without_base_source": len(new_pairs),
                     "function_scorable_issues": sum(bool(item["gold_functions_by_file"]) for item in gold.values()),
                     "derivation": "Official patch changed lines before/after repair plus AST boundaries; hunk headers are audit evidence only.",
                     "hunk_counterexample": {"instance_id": "django__django-10914", "file": "django/conf/global_settings.py",
                         "hunk_header": " def gettext_noop(s):", "changed_line": 307,
                         "changed_target": "module-level FILE_UPLOAD_PERMISSIONS", "gold_functions": []}},
            "structures": structures, "scoring_and_patch_sources": patch_files,
            "actual_patch_site": "code_v3b/fixed_search.py:AFL._prune (formal v3c runner)",
            "historical_patch_site": "code_v3b/AFL_插桩版.py (legacy ten-issue runner)",
            "ppr_graph_input_probe": {"known_paths": known_graph,
                "scope": "Known expected paths only; no claim that call graphs do not exist anywhere on the server.",
                "expected_ppr_script_missing": not (root / "code_v3/ppr_batch.py").is_file(),
                "explicit_graph_directories_found": [item["path"] for item in known_graph[1:] if item["exists"]]},
            "anchor_source": describe(metrics_path),
            "anchor_definition": "Existing v3c issue identifier/call-form categories; no LLM labels or anchor definition changes.",
            "checks": checks, "all_core_checks_pass": all(value is True for value in checks.values()),
            "core_problems": problems,
            "open_definition_items": ["E-only precision denominator must be confirmed before scoring/training.",
                                      "Hunk-header requirement conflicts with unchanged 111/293 AST baseline.",
                                      "Missing PPR adjacency and helper documents require inventory/recovery; no replacement labels created."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--handoff", type=Path, default=ROOT.parent / "交接文档_v5_给Codex.md")
    parser.add_argument("--output-directory", type=Path, default=ROOT / "results/v5_pruner")
    args = parser.parse_args()
    output = args.output_directory.resolve() / "input_audit.json"
    if output.exists():
        parser.error(f"Refusing to overwrite existing output: {output}")
    if not args.handoff.is_file():
        parser.error(f"Missing handoff: {args.handoff}")
    audit = build_audit(args.repository_root.resolve(), args.handoff.resolve())
    changed = [path for path, digest in READ_SOURCES.items() if sha256(Path(path)) != digest]
    audit["read_sources_sha256"] = dict(sorted(READ_SOURCES.items()))
    audit["read_sources_changed_during_audit"] = changed
    audit["checks"]["hashed_read_sources_unchanged"] = not changed
    audit["all_core_checks_pass"] = all(value is True for value in audit["checks"].values())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(audit, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(output), "all_core_checks_pass": audit["all_core_checks_pass"],
                      "formal_event_files": sum(item["event_files"] for item in audit["formal_v3c"].values()),
                      "prunes_by_arm": {arm: item["event_counts"]["prune"] for arm, item in audit["formal_v3c"].items()},
                      "gold": {key: audit["gold"][key] for key in ("all_gold_function_pairs", "base_existing_unique_function_pairs", "new_functions_without_base_source")},
                      "off_function_top5": audit["formal_v3c"]["off"]["function_top5"],
                      "missing_auxiliary_documents": audit["missing_auxiliary_documents"],
                      "ppr_expected_missing": audit["ppr_graph_input_probe"]["expected_ppr_script_missing"]}, ensure_ascii=False))
    return 0 if audit["all_core_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
