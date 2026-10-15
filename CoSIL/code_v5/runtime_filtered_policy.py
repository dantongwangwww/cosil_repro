"""B-only data integrity and runtime evidence rules; no models or test decoder.

This module does not change the frozen A policy. Runtime absence is an exclusion
proxy, never evidence that a candidate is causally unrelated.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/v5_pruner/data_v3"
POLICY = "runtime-covered-v3"
B_RAW = ROOT / "results/v5_pruner/data_v3_runtime_filtered"
B_TRAINING = ROOT / "results/v5_pruner/data_v3_runtime_filtered_reviewed"
REVIEW_FIELDS = {"review_status", "label_error", "review_note"}
CODE_BINDINGS = (
    "code_v5/runtime_filtered_policy.py", "code_v5/prepare_runtime_filtered_data.py",
    "code_v5/freeze_runtime_filtered_decision.py", "code_v5_runtime/__init__.py",
    "code_v5_runtime/train_judges.py", "code_v5_runtime/race_and_calibrate.py",
    "code_v5_runtime/run_training_pair.py", "code_v5_runtime/run_sequence.py",
    "code_v5_runtime/report_outcome.py", "code_v5/judge_models.py", "code_v5/metrics.py",
)
MINER_SHA = "95d56df3bf8d3cbbf41d310c41ab71d2693275c6b57b8721fec43ceda3284372"
SOURCE_STATS_SHA = "2bed8571dfc5769f09f0bcb5edefb6e6a5cf981e7b91e3401241e7e859c8dbd2"
SOURCE_REVIEW_SHA = "c0e181f1fe825954a2e7b086a1f3a6c53dd279ad5d2987b4cfb6f28ae39997cb"


def official_runtime_metadata():
    """Read benchmark test metadata, never the sealed learned-judge test rows.

The old GraphLocator issue JSONL intentionally omits version/FAIL_TO_PASS and
test_patch; collector uses the existing local official Lite dataset instead.
"""
    directory = ROOT / "swebench_local/SWE-bench_Lite_test"
    python = Path("/home/wdt/miniconda3/envs/cosil/bin/python")
    script = ("import json,sys; from datasets import load_from_disk; "
              "d=load_from_disk(sys.argv[1]); "
              "keys=['instance_id','repo','base_commit','version','FAIL_TO_PASS','test_patch','patch','problem_statement']; "
              "print(json.dumps({'fingerprint':d._fingerprint,'rows':[{k:r[k] for k in keys} for r in d]}))")
    result = subprocess.run([str(python), "-c", script, str(directory)], check=True,
                            capture_output=True, text=True, timeout=90)
    value = json.loads(result.stdout)
    rows = {r["instance_id"]: r for r in value["rows"]}
    if len(value["rows"]) != 300 or len(rows) != 300:
        raise RuntimeError("Official runtime metadata is not unique Lite300")
    files = {str(p): sha(p) for p in sorted(directory.rglob("*")) if p.is_file()}
    return rows, {"path": str(directory), "dataset_fingerprint": value["fingerprint"], "file_sha256": files}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_rows(path):
    if Path(path).name == "pruner_test.jsonl":
        raise PermissionError("B data preparation never decodes a sealed pruner test")
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def canonical(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def row_bytes(rows):
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode()


def pair(row):
    return row["instance_id"], row["function_id"]


def triple(row):
    return (*pair(row), row["input_sha256"])


def assert_tests_sealed(extra=None):
    for directory in [SOURCE.parent / n for n in ("data", "data_v2", "data_v3", "data_v3_noise_disclosed", "data_v3_runtime_filtered")] + ([Path(extra)] if extra else []):
        marker = directory / "pruner_test.jsonl.v5_opened_once.json"
        if marker.exists():
            raise PermissionError("A sealed pruner test has opened; reconstruction prohibited: " + str(marker))


def replay_frozen_source():
    """Reproduce old v3 selection from pools; old test is only hashed, not decoded."""
    assert_tests_sealed()
    if sha(SOURCE / "statistics.json") != SOURCE_STATS_SHA or sha(SOURCE / "human_review_codex_reviewed.jsonl") != SOURCE_REVIEW_SHA:
        raise RuntimeError("Original v3 evidence changed")
    if sha(ROOT / "code_v5/build_pruner_data.py") != MINER_SHA:
        raise RuntimeError("Frozen miner changed; do not silently change sampling")
    from code_v5 import build_pruner_data as miner
    stats = read_json(SOURCE / "statistics.json")
    receipt = read_json(SOURCE / "review_failure_and_dataset_hashes.json")
    protected = dict(receipt["protected_dataset_sha256"])
    for relative, expected in protected.items():
        if sha(ROOT / relative) != expected:
            raise RuntimeError("Protected v3 bytes changed: " + relative)
    original = stats["reconstruction_sources"]["candidate_pool.jsonl"]
    if sha(original["path"]) != original["sha256"]:
        raise RuntimeError("Original raw pool changed")
    original_cleaned, _ = miner.deduplicate_inputs(read_rows(original["path"]))
    positives = [r for r in original_cleaned if r["label"]]
    if len(positives) != 1542:
        raise RuntimeError("Original positive eligibility is not 1542")
    pool = read_rows(SOURCE / "candidate_pool.jsonl")
    if canonical(miner.summarize(pool)) != canonical(stats["candidate_pool"]):
        raise RuntimeError("v3 pool counts changed")
    cleaned, input_audit = miner.deduplicate_inputs(pool)
    eligible = positives + [r for r in cleaned if not r["label"]]
    manifest = read_json(SOURCE / "split_manifest.json")
    rows, sampling = miner.sample_rows(eligible, manifest["seed"])
    if (canonical(miner.summarize(rows)) != canonical(stats["selected"])
            or canonical(sampling) != canonical(stats["sampling"])
            or canonical(input_audit) != canonical(stats["truncated_input_audit"])):
        raise RuntimeError("Exact v3 dedup/sample replay failed")
    for split in ("train", "val", "test"):
        encoded = row_bytes([r for r in rows if r["split"] == split])
        # Reconstructed source-pool test bytes are hashed in memory, never read
        # from the sealed old test or used to score model predictions.
        if hashlib.sha256(encoded).hexdigest() != sha(SOURCE / f"pruner_{split}.jsonl"):
            raise RuntimeError("v3 split replay byte hash differs: " + split)
    reviewed = read_rows(SOURCE / "human_review_codex_reviewed.jsonl")
    errors = [r for r in reviewed if r["label_error"]]
    if (len(reviewed) != 30 or len(errors) != 3
            or Counter(r["review_family"] for r in reviewed) != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}
            or any(r["split"] != "train" or r["label"] is not False for r in errors)):
        raise RuntimeError("Preserved v3 train-only review changed")
    error_keys = {triple(r) for r in errors}
    if sum(triple(r) in error_keys for r in pool) != 3:
        raise RuntimeError("The three known train errors must occur exactly once in v3 pool")
    issue_source = stats["sources"]["issue_source"]
    gold_path = Path(stats["sources"]["gold_path"])
    if sha(issue_source["path"]) != issue_source["sha256"] or sha(gold_path) != stats["sources"]["gold_sha256"]:
        raise RuntimeError("Frozen issues/gold changed")
    gold = read_json(gold_path)
    issues, _ = miner.read_issues(Path(issue_source["path"]), gold)
    official, official_source = official_runtime_metadata()
    if set(official) != set(issues):
        raise RuntimeError("Runtime metadata issue-ID alignment differs from fixed Lite300")
    for iid, old in issues.items():
        row = official[iid]
        if (row["repo"] != old["repo"] or row["base_commit"] != old["base_commit"]
                or row["problem_statement"] != old["problem_statement"]
                or row["patch"] != old.get("patch", old.get("fix_patch"))):
            raise RuntimeError("Official runtime metadata drifts from frozen issue/patch: " + iid)
    issues = official
    splits = {iid: name for name, ids in manifest["splits"].items() for iid in ids}
    if (set(splits) != set(issues) or [len(manifest["splits"][s]) for s in ("train", "val", "test")] != [240, 30, 30]
            or any(r["split"] != splits[r["instance_id"]] for r in pool)):
        raise RuntimeError("Original instance-ID split drift")
    return {"stats": stats, "pool": pool, "positives": positives, "manifest": manifest,
            "errors": errors, "issues": issues, "gold": gold, "protected_hashes": protected,
            "official_runtime_metadata_source": official_source,
            "source_replay": {"exact_selected_counts": True, "train_val_bytes_replayed": True,
                              "old_test_hash_replayed_from_pool_only": True, "old_test_rows_decoded": False,
                              "positive_eligible": 1542, "raw_positive": sum(r["label"] for r in pool),
                              "original_ineligible_positive_pairs_not_resurrected": sum(r["label"] for r in pool) - 1542}}


def expected_tests(issue):
    value = issue["FAIL_TO_PASS"]
    return json.loads(value) if isinstance(value, str) else value


def gold_ids(gt):
    """All base-existing gold, including added-line changes mapped to base AST."""
    return {f"{f['file']}::{f['name']}@{f['def_line']}"
            for f in gt.get("existing_gold_function_regions", [])}


def collector_reported_gold_ids(gt):
    """The frozen collector's original before-region receipt (not full gold)."""
    return {f"{f['file']}::{f['name']}@{f.get('def_line', f['start_line'])}"
            for f in gt.get("target_regions", []) if f["side"] == "before" and f["kind"] == "function"}


def assess_result(result, path, issue, gt):
    """Strict successful-evidence qualification; invalid runs retain static rows."""
    if (result["instance_id"] != issue["instance_id"] or result["repo"] != issue["repo"]
            or result["base_commit"] != issue["base_commit"] or result.get("version") != issue.get("version")):
        raise RuntimeError("Runtime result identity/commit mismatch: " + str(path))
    reasons = []
    require = lambda condition, reason: reasons.append(reason) if not condition else None
    require(result.get("status") == "runtime_evidence_usable" and result.get("eligible_for_dual_evidence") is True, "collector_not_eligible")
    require(result.get("completed_at") is not None, "incomplete_result")
    require(result.get("all_expected_tests_reproduced_as_failures") is True, "FAIL_TO_PASS_not_all_failed")
    require(result.get("gold_coverage_complete") is True, "base_gold_not_all_covered")
    require(result.get("source_install_success") is True and result.get("production_import_verified_from_base_clone") is True, "source_install_or_import_unverified")
    require(result.get("test_patch_production_source_untouched") is True, "production_source_touched_or_unverified")
    require(result.get("test_selection_exact") is True, "test_selection_not_exact")
    require(result.get("trace_truncation_detected") is False and not result.get("mapping_parse_errors"), "trace_incomplete_or_mapping_errors")
    statuses = result.get("fail_to_pass_status", [])
    tests = expected_tests(issue)
    require(bool(tests) and result.get("fail_to_pass") == tests and len(statuses) == len(tests)
            and {x.get("test") for x in statuses} == set(tests)
            and all(x.get("status") == "failed_in_test_call" for x in statuses), "FAIL_TO_PASS_metadata_or_phase_mismatch")
    failed = set(result.get("failed_test_function_ids", [])); bootstrap = set(result.get("bootstrap_function_ids", []))
    covered = set(result.get("covered_function_ids", [])); targets = gold_ids(gt)
    require(bool(failed) and covered == failed | bootstrap, "missing_failed_context_or_union_mismatch")
    reported_targets = collector_reported_gold_ids(gt)
    require(bool(targets) and set(result.get("base_gold_function_ids", [])) == reported_targets
            and set(result.get("base_gold_covered", [])) == reported_targets
            and targets <= covered, "complete_base_gold_identity_or_coverage_mismatch")
    require(all(re.fullmatch(r"[^/].*::.+@[1-9]\d*", fid) for fid in covered), "invalid_function_identity")
    spec = result.get("input_spec", {})
    patch_sha = hashlib.sha256(issue["test_patch"].encode()).hexdigest()
    require(spec.get("base_commit") == issue["base_commit"] and spec.get("repo") == issue["repo"]
            and spec.get("fail_to_pass") == tests and spec.get("test_patch_sha256") == patch_sha
            and result.get("test_patch_sha256") == patch_sha, "input_spec_mismatch")
    require(hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest() == result.get("input_fingerprint"), "input_fingerprint_mismatch")
    code = spec.get("code", {})
    require(code.get("runtime_coverage.py") == result.get("collector_sha256")
            and code.get("runtime_coverage_probe.py") == result.get("probe_sha256")
            and set(code) == {"runtime_coverage.py", "runtime_coverage_probe.py", "runtime_coverage_pytest.py"}, "instrumentation_fingerprint_mismatch")
    traces = result.get("trace_files", [])
    require(bool(traces), "no_completed_trace_artifact")
    for trace in traces:
        p = Path(trace["path"])
        require(p.resolve().parent == (Path(path).parent / "traces").resolve()
                and p.is_file() and sha(p) == trace.get("sha256"), "trace_artifact_missing_or_changed")
    test_commands = [c for c in result.get("commands", []) if Path(c.get("log", "")).name == "test.log"]
    require(bool(test_commands) and all(c.get("timeout") is False and c.get("exit_code", -1) > 0 for c in test_commands), "test_timeout_hard_exit_or_not_failed")
    require(result.get("model_calls") == 0 and result.get("gpu_used") is False and result.get("pruner_test_labels_opened") is False, "unexpected_model_gpu_or_pruner_test_access")
    return {"status": "runtime_qualified" if not reasons else "runtime_unavailable", "qualified": not reasons,
            "unavailable_reasons": sorted(set(reasons)), "collector_status": result.get("status"),
            "result_path": str(Path(path).resolve()), "result_sha256": sha(path),
            "input_fingerprint": result.get("input_fingerprint"), "coverage_scope": result.get("coverage_scope"),
            "covered": covered if not reasons else set(), "covered_count": len(covered),
            "limitations": result.get("limitations", [])}


def runtime_metadata(evidence, positive=False):
    fields = {k: deepcopy(v) for k, v in evidence.items() if k != "covered"}
    fields.update(static_v3_eligible=True, positive_preserved=positive,
                  interpretation="coverage absence is an exclusion proxy; it does not prove causal irrelevance",
                  eligibility_basis="positive_original_eligibility" if positive else
                  "static_and_runtime_absent" if evidence["qualified"] else "pure_static_runtime_unavailable")
    return fields


def validate_construction_receipt(data_dir=B_RAW):
    """Hash-only whole-cohort integrity at model gates; no test-role pool parser."""
    data_dir = Path(data_dir).resolve()
    if data_dir != B_RAW or not (data_dir / "statistics.json").is_file():
        raise RuntimeError("The independently frozen B construction is not ready")
    assert_tests_sealed(B_TRAINING)
    stats = read_json(data_dir / "statistics.json")
    receipt_path = data_dir / "construction_receipt.json"
    receipt = read_json(receipt_path)
    stats_payload = {k: v for k, v in stats.items() if k != "construction_receipt_sha256"}
    if (sha(receipt_path) != stats.get("construction_receipt_sha256")
            or hashlib.sha256(canonical(stats_payload).encode()).hexdigest() != receipt["raw_statistics_payload_sha256"]
            or receipt.get("construction_completed") is not True or receipt.get("data_policy") != POLICY
            or receipt.get("known_three_train_errors_excluded") is not True
            or receipt["source_statistics_sha256"] != SOURCE_STATS_SHA
            or receipt["source_review_sha256"] != SOURCE_REVIEW_SHA):
        raise RuntimeError("B frozen construction receipt changed")
    required_files = {"candidate_pool.jsonl", "negative_exclusions.jsonl", "split_manifest.json",
        "pruner_train.jsonl", "pruner_val.jsonl", "pruner_test.jsonl", "test_file_seal.json",
        "human_review.jsonl", "runtime_manifest.json", "review_source_runtime_evidence.json",
        "comparison_A_B_val_shared_pairs.json", "derivation.json"}
    if set(receipt["raw_files_sha256"]) != required_files:
        raise RuntimeError("B construction receipt omits a sealed/evidence artifact")
    for name, expected in receipt["raw_files_sha256"].items():
        if sha(data_dir / name) != expected:
            raise RuntimeError("B frozen construction bytes changed: " + name)
    if sha(SOURCE / "statistics.json") != SOURCE_STATS_SHA or sha(SOURCE / "human_review_codex_reviewed.jsonl") != SOURCE_REVIEW_SHA:
        raise RuntimeError("Original v3 source/review bytes changed")
    original_stats = read_json(SOURCE / "statistics.json")
    sources = original_stats["sources"]
    if (sha(sources["gold_path"]) != sources["gold_sha256"]
            or sha(sources["issue_source"]["path"]) != sources["issue_source"]["sha256"]
            or canonical(receipt["original_raw_pool"]) != canonical(original_stats["reconstruction_sources"]["candidate_pool.jsonl"])):
        raise RuntimeError("Original gold/issue/raw eligibility provenance changed")
    for path, expected in receipt["source_protected_sha256"].items():
        if sha(ROOT / path) != expected: raise RuntimeError("Original v3 protected source changed")
    original_pool = receipt["original_raw_pool"]
    if sha(original_pool["path"]) != original_pool["sha256"]:
        raise RuntimeError("Original raw eligibility pool changed")
    for path, expected in receipt["official_runtime_metadata_source"]["file_sha256"].items():
        if sha(path) != expected: raise RuntimeError("Official runtime benchmark metadata changed")
    manifest = read_json(data_dir / "split_manifest.json")
    if sha(data_dir / "split_manifest.json") != sha(SOURCE / "split_manifest.json"):
        raise RuntimeError("Original B instance split changed")
    ids = {iid for group in manifest["splits"].values() for iid in group}
    runtime = receipt["runtime_manifest"]
    cases_dir = ROOT / "results/v5_pruner/runtime_coverage/cases_final"
    if (runtime["all_300_completed"] is not True or runtime["result_count"] != 300 or runtime["missing_ids"]
            or Path(runtime["result_directory"]).resolve() != cases_dir
            or {Path(path).parent.name for path in runtime["result_sha256"]} != ids
            or len(runtime["result_sha256"]) != 300):
        raise RuntimeError("B construction lacks same exact 300 permanent runtime cases")
    if sha(runtime["frozen_collector_policy_path"]) != runtime["frozen_collector_policy_sha256"]:
        raise RuntimeError("B collector frozen policy changed")
    for name, expected in runtime["collector_code_sha256"].items():
        if sha(ROOT / "code_v5" / name) != expected:
            raise RuntimeError("Frozen runtime instrumentation changed")
    for path, expected in {**runtime["result_sha256"], **runtime["trace_artifact_sha256"]}.items():
        if not Path(path).resolve().is_relative_to(cases_dir) or sha(path) != expected:
            raise RuntimeError("Permanent B runtime evidence bytes changed")
    if canonical(runtime) != canonical(read_json(data_dir / "runtime_manifest.json")):
        raise RuntimeError("B runtime manifest differs from construction receipt")
    for name, expected in stats["preparation_code_sha256"].items():
        if sha(ROOT / "code_v5" / name) != expected:
            raise RuntimeError("Frozen B construction code changed")
    return stats, read_json(data_dir / "test_file_seal.json"), {"manifest": manifest}, read_rows(data_dir / "human_review.jsonl")


def validate_raw_B(data_dir=B_RAW, *, audit_construction=True):
    """Reproduce the frozen B dataset using all permanent runtime results.

Only pool rows are decoded for reconstruction. The sealed old/new pruner tests
are checked as byte hashes, never decoded or supplied to a model.
"""
    data_dir = Path(data_dir).resolve()
    if data_dir != B_RAW:
        raise RuntimeError("B raw source must be the separately frozen runtime-filtered directory")
    if not (data_dir / "statistics.json").is_file():
        raise RuntimeError("B raw dataset is not frozen; all300 results must complete first")
    validated = validate_construction_receipt(data_dir)
    if not audit_construction:
        return validated
    assert_tests_sealed(B_TRAINING)
    from code_v5.prepare_runtime_filtered_data import load_runtime, prepare_rows
    context = replay_frozen_source()
    stats = read_json(data_dir / "statistics.json")
    runtime_manifest = read_json(data_dir / "runtime_manifest.json")
    derivation = read_json(data_dir / "derivation.json")
    if (runtime_manifest["all_300_completed"] is not True or runtime_manifest["result_count"] != 300
            or runtime_manifest["missing_ids"] or stats["data_policy"] != POLICY
            or stats["mechanical_labels_only"] is not True or stats["model_calls"] != 0
            or stats["passed"] is not False or derivation["frozen"] is not True
            or derivation["new_labels_generated"] != 0 or derivation["old_test_rows_decoded"] is not False):
        raise RuntimeError("B source is incomplete or misstates provenance/quality")
    for relative, expected in stats["preparation_code_sha256"].items():
        if sha(ROOT / "code_v5" / relative) != expected:
            raise RuntimeError("Frozen B preparation code changed")
    if sha(data_dir / "runtime_manifest.json") != stats["runtime_manifest_sha256"]:
        raise RuntimeError("Frozen all300 runtime fingerprints changed")
    evidence, replay_manifest = load_runtime(context, runtime_manifest["result_directory"])
    if canonical(replay_manifest) != canonical(runtime_manifest):
        raise RuntimeError("Permanent runtime result or collector fingerprint changed")
    eligible, selected, excluded, sampling, audit = prepare_rows(context, evidence)
    from code_v5 import build_pruner_data as miner
    if (canonical(miner.summarize(selected)) != canonical(stats["selected"])
            or canonical(sampling) != canonical(stats["sampling"])
            or canonical(audit) != canonical(stats["truncated_input_audit"])
            or sha(data_dir / "candidate_pool.jsonl") != hashlib.sha256(row_bytes(eligible)).hexdigest()
            or sha(data_dir / "negative_exclusions.jsonl") != hashlib.sha256(row_bytes(excluded)).hexdigest()):
        raise RuntimeError("B fixed-rule row replay failed")
    seal = read_json(data_dir / "test_file_seal.json")
    if seal != stats["seal"] or sha(data_dir / "split_manifest.json") != sha(SOURCE / "split_manifest.json"):
        raise RuntimeError("B original split or seal changed")
    for split in ("train", "val", "test"):
        encoded = row_bytes([r for r in selected if r["split"] == split])
        entry = seal["frozen_files"][split]; path = data_dir / f"pruner_{split}.jsonl"
        if (Path(entry["path"]).resolve() != path or entry["sha256"] != sha(path)
                or entry["sha256"] != hashlib.sha256(encoded).hexdigest()
                or entry["count"] != sum(r["split"] == split for r in selected)):
            raise RuntimeError("B sealed split does not reproduce the authorized pool: " + split)
    pending = miner.review_samples(selected, context["manifest"]["seed"])
    if sha(data_dir / "human_review.jsonl") != hashlib.sha256(row_bytes(pending)).hexdigest():
        raise RuntimeError("B review resampling changed")
    if (sha(data_dir / "review_source_runtime_evidence.json") != derivation["review_packet_sha256"]
            or sha(data_dir / "comparison_A_B_val_shared_pairs.json") != derivation["shared_val_sha256"]):
        raise RuntimeError("B source/runtime review packet or A/B shared pairs changed")
    return stats, seal, context, pending


def validate_review(raw_stats, pending, review_path):
    """Noise disclosure requires all 30 signatures; it never claims zero noise."""
    reviewed = read_rows(review_path)
    index = {triple(r): r for r in pending}
    if (len(pending) != 30 or len(reviewed) != 30 or len(index) != 30
            or {triple(r) for r in reviewed} != set(index)
            or Counter(r["review_family"] for r in reviewed) != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}):
        raise RuntimeError("B requires complete genuine three-family train-only review; do not duplicate shortages")
    packet = read_json(B_RAW / "review_source_runtime_evidence.json")["records"]
    if (len(packet) != 30 or {triple(r["identity"]) for r in packet} != set(index)
            or not all(r.get("source_evidence_complete") is True for r in packet)):
        raise RuntimeError("All 30 B records require complete verified source/runtime evidence")
    for r in reviewed:
        original = index[triple(r)]
        if ({k: v for k, v in r.items() if k not in REVIEW_FIELDS}
                != {k: v for k, v in original.items() if k not in REVIEW_FIELDS}
                or r["split"] != "train" or r["label"] is not False
                or r["review_status"] != "reviewed" or type(r["label_error"]) is not bool
                or not isinstance(r["review_note"], str) or not r["review_note"].strip()):
            raise RuntimeError("B review changed labels/source payload or is incomplete")
    return reviewed, [r for r in reviewed if r["label_error"]]


def expected_B_train(errors):
    error_keys = {triple(r) for r in errors}
    kept = []; removed = []
    for line in (B_RAW / "pruner_train.jsonl").read_bytes().splitlines(keepends=True):
        r = json.loads(line)
        if triple(r) in error_keys:
            expected = next(x for x in errors if triple(x) == triple(r))
            if any(r[k] != expected[k] for k in r) or r["label"] is not False or r["split"] != "train":
                raise RuntimeError("Only source-verified signed B TRAIN negatives may be excluded")
            removed.append(r)
        else:
            kept.append(line)
    if len(removed) != len(error_keys) or {triple(r) for r in removed} != error_keys:
        raise RuntimeError("All and only the newly signed B train errors must be removed")
    return b"".join(kept), removed


def derive_reviewed_B(review_path):
    raw_stats, raw_seal, context, pending = validate_raw_B()
    reviewed, errors = validate_review(raw_stats, pending, review_path)
    train, removed = expected_B_train(errors)
    if B_TRAINING.exists():
        raise FileExistsError("B reviewed training derivative is immutable; never overwrite it")
    B_TRAINING.mkdir()
    (B_TRAINING / "pruner_train.jsonl").write_bytes(train)
    for name in ("pruner_val.jsonl", "pruner_test.jsonl", "split_manifest.json", "human_review.jsonl",
                 "review_source_runtime_evidence.json", "comparison_A_B_val_shared_pairs.json", "runtime_manifest.json"):
        (B_TRAINING / name).write_bytes((B_RAW / name).read_bytes())
    signed_path = B_TRAINING / "human_review_codex_reviewed.jsonl"
    signed_path.write_bytes(Path(review_path).read_bytes())
    stats = deepcopy(raw_stats); selected = stats["selected"]
    selected["unique_pairs"] -= len(removed)
    for row in removed:
        changes = {"negative": 1, "E_unique_union": 1, "primary_source_" + row["label_source"]: 1}
        changes.update({"source_" + s: 1 for s in row["label_sources"]})
        for k, n in changes.items():
            selected[k] -= n; selected["by_split"]["train"][k] -= n
        selected["by_repo"][row["repo"]]["negative"] -= 1
        selected["by_anchor"][row["anchor"]]["negative"] -= 1
    rows = [json.loads(x) for x in train.splitlines() if x.strip()]
    selected["by_split"]["train"]["issues_with_rows"] = len({r["instance_id"] for r in rows})
    selected["by_split"]["train"]["issues_with_positive_rows"] = len({r["instance_id"] for r in rows if r["label"]})
    seal = deepcopy(raw_seal); seal["dataset_version"] = POLICY + "-reviewed-train-errors-excluded"
    seal["test_path"] = str(B_TRAINING / "pruner_test.jsonl")
    for split in ("train", "val", "test"):
        entry = seal["frozen_files"][split]; p = B_TRAINING / f"pruner_{split}.jsonl"
        entry.update(path=str(p), sha256=sha(p))
    seal["frozen_files"]["train"]["count"] -= len(removed)
    (B_TRAINING / "test_file_seal.json").write_text(json.dumps(seal, ensure_ascii=False, indent=2) + "\n")
    stats["seal"] = seal; stats["dataset_version"] = seal["dataset_version"]
    stats["review"] = {"passed": len(errors) <= 2, "historical_threshold_only": True,
        "review_complete": True, "noise_disclosure_policy": True, "status": "reviewed_full30_noise_disclosed",
        "review_path": str(signed_path), "review_sha256": sha(signed_path), "reviewed_records": 30,
        "label_errors": len(errors), "observed_stratified_fraction": len(errors) / 30,
        "reviewer_kind": "Codex/机械证据审阅; not a human signature", "family_counts": dict(Counter(r["review_family"] for r in reviewed)),
        "interpretation": "Full original stratified sample retained. Removing confirmed errors does not make remaining samples random or certify zero remaining noise."}
    p, n, e = selected["positive"], selected["negative"], selected.get("E_unique_union", 0)
    stats["quality_gates"].update(positive_unique_pairs_ge_8000=p >= 8000, E_unique_pairs_ge_3000=e >= 3000,
        negative_to_positive_ratio_about_2=bool(p and 1.8 <= n / p <= 2.2), E_fraction_of_negatives_ge_one_third=bool(n and e / n >= 1/3),
        review_30_train_E_examples_at_most_2_errors=len(errors) <= 2)
    stats["passed"] = False
    from code_v5.prepare_runtime_filtered_data import runtime_distribution
    val = read_rows(B_TRAINING / "pruner_val.jsonl")
    distribution = deepcopy(raw_stats["runtime_distribution"])
    measured = runtime_distribution(rows + val)
    for split in ("train", "val"):
        distribution["by_split"][split] = measured["by_split"][split]
    totals = Counter()
    for value in distribution["by_split"].values(): totals.update(value)
    distribution["all"] = dict(totals); stats["runtime_distribution"] = distribution
    derivation = {"data_policy": POLICY, "raw_data_dir": str(B_RAW), "raw_statistics_sha256": sha(B_RAW / "statistics.json"),
        "signed_full30_review_path": str(signed_path), "signed_full30_review_sha256": sha(signed_path),
        "reviewed_records": 30, "observed_errors": len(errors), "removed_train_error_count": len(removed),
        "removed_train_errors": [{k: r[k] for k in ("instance_id", "function_id", "input_sha256", "label", "split")} for r in removed],
        "new_labels_generated": 0, "old_or_new_test_rows_decoded": False,
        "val_test_split_bytes_preserved": True,
        "raw_protected_files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in B_RAW.iterdir() if p.is_file()}}
    dpath = B_TRAINING / "reviewed_train_derivation.json"
    dpath.write_text(json.dumps(derivation, ensure_ascii=False, indent=2) + "\n")
    stats["reviewed_train_derivation_sha256"] = sha(dpath)
    (B_TRAINING / "statistics.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n")
    return stats


def validate_authorization(contract):
    policy = contract.get("runtime_filtered_exploratory_v3", {})
    expected = {"enabled": True, "track": "exploratory", "data_policy": POLICY,
        "original_static_data_dir": str(SOURCE), "derived_data_dir": str(B_RAW),
        "reviewed_training_data_dir": str(B_TRAINING), "coverage_required_unique_issue_results": 300,
        "coverage_cases_dir": str(ROOT / "results/v5_pruner/runtime_coverage/cases_final"),
        "known_v3_train_errors_must_remain_excluded": 3, "new_review_count": 30,
        "review_as_noise_disclosure": True, "all_review_records_require_complete_source_evidence": True,
        "review_confirmed_train_errors_must_be_excluded_in_final_training_derivation": True,
        "exact_known_train_error_exclusion": True,
        "training_labels_may_be_flipped": False, "llm_labels_allowed": False,
        "keep_original_issue_split": True, "previous_sealed_test_json_rows_may_be_decoded": False,
        "test_open_allowed": False, "test_json_performance_may_be_used_for_selection": False,
        "sampling_seed": 20261013}
    if any(policy.get(k) != v for k, v in expected.items()):
        raise RuntimeError("Root B snapshot lacks exact independent coverage/noise/train-deletion authorization")
    if set(policy.get("allowed_measured_quantity_failed_gates", [])) != {
            "positive_unique_pairs_ge_8000", "E_unique_pairs_ge_3000", "negative_to_positive_ratio_about_2"}:
        raise RuntimeError("Only the three explicitly authorized measured quantity targets may be disclosed")
    if policy.get("review_by_family_target") != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}:
        raise RuntimeError("The new independent B review must be ten genuine train records per family")
    return policy


def validate_reviewed_B(data_dir, *, audit_construction=False):
    if Path(data_dir).resolve() != B_TRAINING:
        raise RuntimeError("Only the separately reviewed B training derivative is authorized")
    raw_stats, raw_seal, context, pending = validate_raw_B(audit_construction=audit_construction)
    stats = read_json(B_TRAINING / "statistics.json")
    reviewed, errors = validate_review(raw_stats, pending, B_TRAINING / "human_review_codex_reviewed.jsonl")
    expected_train, removed = expected_B_train(errors)
    if (B_TRAINING / "pruner_train.jsonl").read_bytes() != expected_train:
        raise RuntimeError("B training labels/rows changed beyond exact signed errors")
    derivation_path = B_TRAINING / "reviewed_train_derivation.json"
    derivation = read_json(derivation_path)
    if (sha(derivation_path) != stats["reviewed_train_derivation_sha256"]
            or derivation["removed_train_error_count"] != len(removed)
            or {triple(r) for r in derivation["removed_train_errors"]} != {triple(r) for r in removed}
            or derivation["raw_statistics_sha256"] != sha(B_RAW / "statistics.json")):
        raise RuntimeError("B signed train-only exclusion derivation changed")
    for p, expected in derivation["raw_protected_files_sha256"].items():
        if sha(ROOT / p) != expected: raise RuntimeError("Original B raw dataset/evidence changed")
    for name in ("pruner_val.jsonl", "pruner_test.jsonl", "split_manifest.json", "human_review.jsonl",
                 "review_source_runtime_evidence.json", "comparison_A_B_val_shared_pairs.json", "runtime_manifest.json"):
        if sha(B_TRAINING / name) != sha(B_RAW / name):
            raise RuntimeError("B val/test/split/full30 evidence bytes changed")
    train = read_rows(B_TRAINING / "pruner_train.jsonl"); val = read_rows(B_TRAINING / "pruner_val.jsonl")
    rows = train + val; fingerprints = [r["input_sha256"] for r in rows]
    split_ids = {s: set(context["manifest"]["splits"][s]) for s in ("train", "val", "test")}
    if (len({pair(r) for r in rows}) != len(rows) or len(set(fingerprints)) != len(rows)
            or any(r["instance_id"] not in split_ids[r["split"]] or type(r["label"]) is not bool
                   or len(r["issue"]) > 2000 or len(r["function"]) > 1500
                   or hashlib.sha256(json.dumps([r["issue"], r["function"]], ensure_ascii=False).encode()).hexdigest() != r["input_sha256"] for r in rows)):
        raise RuntimeError("B fixed split/input dedup or original boolean labels changed")
    expected_counts = deepcopy(raw_stats["selected"])
    expected_counts["unique_pairs"] -= len(removed)
    for row in removed:
        changes = {"negative": 1, "E_unique_union": 1, "primary_source_" + row["label_source"]: 1}
        changes.update({"source_" + s: 1 for s in row["label_sources"]})
        for k, n in changes.items():
            expected_counts[k] -= n; expected_counts["by_split"]["train"][k] -= n
        expected_counts["by_repo"][row["repo"]]["negative"] -= 1
        expected_counts["by_anchor"][row["anchor"]]["negative"] -= 1
    expected_counts["by_split"]["train"]["issues_with_rows"] = len({r["instance_id"] for r in train})
    expected_counts["by_split"]["train"]["issues_with_positive_rows"] = len({r["instance_id"] for r in train if r["label"]})
    if canonical(stats["selected"]) != canonical(expected_counts):
        raise RuntimeError("B train/repo/anchor/source/test aggregate counts changed beyond exact exclusions")
    selected = stats["selected"]; positive = selected["positive"]; negative = selected["negative"]; e = selected.get("E_unique_union", 0)
    expected_gates = {"positive_unique_pairs_ge_8000": positive >= 8000,
        "E_unique_pairs_ge_3000": e >= 3000,
        "negative_to_positive_ratio_about_2": bool(positive and 1.8 <= negative / positive <= 2.2),
        "E_fraction_of_negatives_ge_one_third": bool(negative and e / negative >= 1 / 3),
        "ordinary_D_negatives_retained": selected.get("primary_source_D", 0) > 0,
        "issue_split_disjoint_240_30_30": True, "truncated_inputs_unique_and_disjoint": True,
        "all_base_gold_regions_mapped": raw_stats["quality_gates"]["all_base_gold_regions_mapped"],
        "review_30_train_E_examples_at_most_2_errors": len(errors) <= 2}
    if stats["quality_gates"] != expected_gates:
        raise RuntimeError("B quality/quantity gates do not represent measured post-exclusion counts")
    from code_v5 import build_pruner_data as miner
    summary = miner.summarize(rows)
    if (stats["passed"] is not False or stats["mechanical_labels_only"] is not True or stats["model_calls"] != 0
            or stats["review"]["reviewed_records"] != 30 or stats["review"]["label_errors"] != len(errors)
            or stats["review"]["review_complete"] is not True
            or stats["review"]["passed"] != (len(errors) <= 2)
            or stats["review"]["observed_stratified_fraction"] != len(errors) / 30
            or stats["review"]["family_counts"] != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}
            or stats["review"]["review_sha256"] != sha(B_TRAINING / "human_review_codex_reviewed.jsonl")
            or any({k: v for k, v in stats["selected"]["by_split"][s].items() if v != 0}
                   != {k: v for k, v in summary["by_split"][s].items() if v != 0} for s in ("train", "val"))
            or stats["selected"]["positive"] != 1542
            or stats["selected"]["negative"] != raw_stats["selected"]["negative"] - len(removed)
            or stats["selected"]["E_unique_union"] != raw_stats["selected"].get("E_unique_union", 0) - len(removed)):
        raise RuntimeError("B actual post-exclusion counts or full-sample noise disclosure changed")
    seal = read_json(B_TRAINING / "test_file_seal.json")
    if seal != stats["seal"]: raise RuntimeError("B reviewed seal differs from actual stats")
    if (seal["count"] != raw_seal["count"] or seal["test_sha256"] != raw_seal["test_sha256"]
            or seal["frozen_files"]["train"]["count"] != len(train)
            or seal["frozen_files"]["val"]["count"] != len(val)
            or seal["frozen_files"]["test"]["count"] != raw_seal["frozen_files"]["test"]["count"]):
        raise RuntimeError("B reviewed seal actual counts changed")
    for split in ("train", "val", "test"):
        entry = seal["frozen_files"][split]; path = B_TRAINING / f"pruner_{split}.jsonl"
        if Path(entry["path"]).resolve() != path or sha(path) != entry["sha256"]:
            raise RuntimeError("B reviewed sealed bytes changed: " + split)
    return stats, seal, split_ids


def validate_decision(data_dir, decision_file):
    stats, seal, split_ids = validate_reviewed_B(data_dir)
    decision = read_json(decision_file)
    if (decision.get("track") != "exploratory" or decision.get("data_policy") != POLICY
            or decision.get("formal_failed") is not True or decision.get("test_open_allowed") is not False
            or decision.get("statistics_sha256") != sha(B_TRAINING / "statistics.json")
            or Path(decision.get("data_dir", "")).resolve() != B_TRAINING):
        raise RuntimeError("Independent B decision does not bind actual reviewed derivative")
    snapshot = Path(decision["execution_contract_path"])
    if sha(snapshot) != decision["execution_contract_sha256"]:
        raise RuntimeError("B root protocol snapshot changed")
    policy = validate_authorization(read_json(snapshot))
    hashes = decision["policy_code_sha256"]
    if set(hashes) != set(CODE_BINDINGS) or any(sha(ROOT / p) != h for p, h in hashes.items()):
        raise RuntimeError("Independent B code/metric fingerprints changed")
    actual_bindings = {"seal_sha256": sha(B_TRAINING / "test_file_seal.json"),
        "raw_statistics_sha256": sha(B_RAW / "statistics.json"), "runtime_manifest_sha256": sha(B_RAW / "runtime_manifest.json"),
        "review_sha256": sha(B_TRAINING / "human_review_codex_reviewed.jsonl"),
        "reviewed_train_derivation_sha256": sha(B_TRAINING / "reviewed_train_derivation.json"),
        "split_manifest_sha256": sha(B_TRAINING / "split_manifest.json"),
        **{s + "_sha256": sha(B_TRAINING / f"pruner_{s}.jsonl") for s in ("train", "val", "test")}}
    if any(decision.get(k) != h for k, h in actual_bindings.items()):
        raise RuntimeError("B decision no longer binds runtime/review/source/seal bytes")
    if decision.get("selected_counts") != stats["selected"] or decision.get("formal_gate_results") != stats["quality_gates"]:
        raise RuntimeError("B decision changed real measured counts or gate failures")
    failed = {k for k, v in stats["quality_gates"].items() if v is not True}
    # Runtime filtering changes actual negative supply; these are measured
    # sampling targets explicitly authorized by the B root snapshot. Integrity
    # and evidence completeness are checked separately and never waived.
    quantity_or_historical = set(policy["allowed_measured_quantity_failed_gates"]) | {
        "review_30_train_E_examples_at_most_2_errors"}
    if not failed <= quantity_or_historical or set(decision.get("allowed_failed_gates", [])) != failed:
        raise RuntimeError("B may disclose only actual sampling/review failures, never integrity failures")
    provenance = {"statistics_sha256": sha(B_TRAINING / "statistics.json"), "seal_sha256": sha(B_TRAINING / "test_file_seal.json"),
        "split_manifest_sha256": sha(B_TRAINING / "split_manifest.json"), "review_sha256": stats["review"]["review_sha256"],
        "reviewer_kind": stats["review"]["reviewer_kind"], "test_labels_read": False,
        "track": "exploratory", "data_policy": POLICY, "formal_data_gate_passed": False,
        "noise_disclosure": {"count": 30, "errors": stats["review"]["label_errors"],
            "family_counts": stats["review"]["family_counts"], "sample_error_fraction": stats["review"]["label_errors"] / 30,
            "interpretation": "B coverage-filtered full30 stratified review, not a population estimate or zero-noise certification"},
        "runtime_distribution": stats["runtime_distribution"],
        "root_decision": {"path": str(Path(decision_file).resolve()), "sha256": sha(decision_file),
            "execution_contract_path": str(snapshot), "execution_contract_sha256": decision["execution_contract_sha256"],
            "allowed_failed_gates": decision["allowed_failed_gates"], "formal_failed": True}}
    return stats, seal, split_ids, provenance
