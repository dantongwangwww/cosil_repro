"""Offline, write-once delivery export for the frozen repair50 experiment.

No provider, executor, source parser, or budget writer is imported here. A
controller terminal event is required; observing some arm records is not enough.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import re

from . import reporting
from .statistics import BOOTSTRAP_REPLICATES, paired_statistics


HASH = re.compile(r"[0-9a-f]{64}")
RECOVERY_SCHEMA = "repair50_offline_recovery_binding_v1"


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _task_digest(value):
    return _digest((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


class Sources:
    """Cache one byte snapshot in memory; expose only hashes in the manifest."""
    def __init__(self):
        self.raw = {}

    def read(self, path):
        path = Path(path).absolute()
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            raise ValueError("Missing/nonregular/linked source: " + str(path))
        if str(path) not in self.raw:
            self.raw[str(path)] = path.read_bytes()
        return self.raw[str(path)]

    def json(self, path):
        return json.loads(self.read(path))

    def ref(self, item, expected=None):
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("Recovery references require exactly path/sha256")
        path = Path(item["path"]).absolute()
        if expected is not None and path != Path(expected).absolute():
            raise ValueError("Recovery reference is not the original arm artifact")
        if not isinstance(item["sha256"], str) or not HASH.fullmatch(item["sha256"]):
            raise ValueError("Invalid source SHA256")
        if _digest(self.read(path)) != item["sha256"]:
            raise ValueError("Recovery source SHA256 mismatch")
        return path

    def optional(self, path):
        if path is None:
            return None
        path = Path(path).absolute()
        if path.exists() or path.is_symlink():
            self.read(path)
            return str(path)
        return None

    def manifest(self):
        return [{"path": p, "bytes": len(raw), "sha256": _digest(raw)}
                for p, raw in sorted(self.raw.items())]


def terminal_evidence(path, sources):
    events = []
    for line in sources.read(path).decode("utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and "event" in event:
            events.append(event)
    controls = [e for e in events if e["event"] != "report_saved"]
    if not controls:
        raise ValueError("No controller terminal evidence")
    final = controls[-1]
    if final.get("event") == "paired_run_finished" and final.get("status") in ("COMPLETE", "BUDGET_STOP"):
        state = final["status"]
    elif final.get("event") == "BUDGET_STOP":
        state = "BUDGET_STOP"
    else:
        raise ValueError("Controller log does not end in a supported terminal state")
    if state == "COMPLETE" and final.get("records") != 100:
        raise ValueError("COMPLETE terminal must explicitly report 100 records")
    return {"state": state, "event": final, "path": str(Path(path).absolute())}


def _roster(value):
    tasks = value.get("tasks")
    if value.get("frozen") is not True or not isinstance(tasks, list) or len(tasks) != 50:
        raise ValueError("Exactly 50 explicitly frozen tasks required")
    if (len({t.get("instance_id") for t in tasks}) != 50
            or len({t.get("repo") for t in tasks}) != 50):
        raise ValueError("Unique IID and repository required")
    for task in tasks:
        if (not isinstance(task.get("instance_id"), str) or not task["instance_id"]
                or not re.fullmatch(r"[0-9a-f]{40}", task.get("base_commit", ""))
                or not re.fullmatch(r"swerebench/[^@\s]+@sha256:[0-9a-f]{64}", task.get("image_reference", ""))
                or task.get("qualification_passed") is not True):
            raise ValueError("Frozen task identity/qualification missing")
    return tasks


def input_group(prepared):
    """Byte-sensitive whole messages are separate from source-only equality."""
    if prepared is None:
        return "UNKNOWN_PREPARATION"
    pair = prepared["pair_inputs"]
    a, b = pair["A"]["messages"], pair["B"]["messages"]
    ua, ub = json.loads(a[1]["content"]), json.loads(b[1]["content"])
    if ua["issue"] != ub["issue"] or a[0] != b[0]:
        raise ValueError("A/B issue or common system prompt differs")
    same_source = ua["source_context"] == ub["source_context"]
    audit = prepared["context_audit"]
    if ("source_content_identical" in audit
            and audit["source_content_identical"] is not same_source):
        raise ValueError("Saved source equality disagrees with prepared inputs")
    if audit.get("B_added_source") is True and same_source:
        raise ValueError("B added-source flag contradicts identical source")
    if a == b:
        return "MESSAGES_IDENTICAL"
    if same_source and ua["location_suggestions"] != ub["location_suggestions"]:
        if {k: v for k, v in ua.items() if k != "location_suggestions"} != {
                k: v for k, v in ub.items() if k != "location_suggestions"}:
            raise ValueError("Same-source intervention changes more than suggestions")
        return "SOURCE_SAME_HINTS_DIFFERENT"
    if same_source:
        return "SOURCE_SAME_HINTS_SAME_MESSAGES_DIFFERENT"
    return "B_SOURCE_ADDED" if audit.get("B_added_source") is True else "SOURCE_DIFFERENT_OTHER"


def _recovery(binding_path, sources, task, arm, original, case_dir):
    binding = sources.json(binding_path)
    if (set(binding) != {"schema", "instance_id", "arm", "base_commit", "image_reference",
                         "official_harness_commit", "original", "recovered"}
            or binding["schema"] != RECOVERY_SCHEMA):
        raise ValueError("Unsupported recovery binding schema")
    if any(binding[k] != task[k] for k in ("instance_id", "base_commit", "image_reference")) or binding["arm"] != arm:
        raise ValueError("Recovery IID/arm/base/image differs")
    old = binding["original"]
    if set(old) != {"arm_record", "evaluation_result", "patch"} or set(binding["recovered"]) != {"evaluation_result", "patch"}:
        raise ValueError("Recovery artifact set differs")
    original_path = case_dir / arm / "arm_record.json"
    sources.ref(old["arm_record"], original_path)
    old_eval_path = sources.ref(old["evaluation_result"], case_dir / arm / "evaluation/result.json")
    old_patch_path = sources.ref(old["patch"], (original.get("paths") or {}).get("patch", case_dir / arm / "edit_artifacts/patch.diff"))
    old_eval = sources.json(old_eval_path)
    pre_application_stages = {"IMAGE_IDENTITY_OR_TRANSPORT", "PRIVATE_SCORING_PATH_INTEGRITY_CHECK",
        "OFFICIAL_TEST_SPEC", "BASE_IDENTITY", "BASE_WORKTREE_IDENTITY", "BASE_SOURCE_IDENTITY"}
    if (original.get("status") != "ENVIRONMENT_ERROR" or original.get("environment_error") is not True
            or not all(original.get(k) is True for k in ("patch_generated", "parse_ok", "deterministic_apply_ok"))
            or original.get("apply_ok") is not None or original.get("resolved") is not None
            or original.get("test_completed") is not False or original.get("official_verdict") is not False
            or old_eval.get("status") != "ENVIRONMENT_ERROR" or old_eval.get("environment_error") is not True
            or old_eval.get("apply_ok") is not None or old_eval.get("patch_applied") is not None
            or old_eval.get("resolved") is not None or old_eval.get("official_result") is not None
            or old_eval.get("test_completed") is not False or old_eval.get("official_verdict") is not False):
        raise ValueError("Recovery cannot replace an applied/tested/model-negative candidate")
    if (old_eval.get("stage") not in pre_application_stages or any((old_eval_path.parent / name).exists() or (old_eval_path.parent / name).is_symlink()
            for name in ("patch.diff", "patch_apply.log", "test_output.txt", "official_report.json", "parsed_test_statuses.json"))):
        raise ValueError("Recovery lacks unambiguous pre-application evidence")
    new_path = sources.ref(binding["recovered"]["evaluation_result"])
    new_patch = sources.ref(binding["recovered"]["patch"], new_path.parent / "patch.diff")
    if new_path.parent == old_eval_path.parent or sources.read(old_patch_path) != sources.read(new_patch):
        raise ValueError("Recovery needs a separate directory and the exact original patch")
    new = sources.json(new_path)
    for ev in (old_eval, new):
        if (ev.get("instance_id") != task["instance_id"] or ev.get("arm") != arm
                or ev.get("image_reference") != task["image_reference"]
                or ev.get("official_harness_commit") != binding["official_harness_commit"]):
            raise ValueError("Recovery evaluator identity/harness differs")
    if (new.get("status") != "TEST_COMPLETED" or new.get("test_completed") is not True
            or new.get("official_verdict") is not True or new.get("environment_error") is not False
            or new.get("apply_ok") is not True or new.get("patch_applied") is not True
            or new.get("fully_observed_expected_tests") is not True or type(new.get("resolved")) is not bool
            or (new.get("official_result") or {}).get("resolved") is not new["resolved"]):
        raise ValueError("Recovered result lacks a complete first official verdict")
    protocol = sources.json(new_path.parent / "protocol.json")
    head = sources.json(new_path.parent / "base_head.json")
    for key, name in (("test_output", "test_output.txt"), ("eval_script", "eval.sh")):
        expected_path = new_path.parent / name
        if Path((new.get("logpaths") or {}).get(key, "")).absolute() != expected_path:
            raise ValueError("Recovered evaluation artifact path differs")
        sources.read(expected_path)
    qualified_protocol = sources.json(Path(task["gold_receipt"]).parent / "protocol.json")
    if (protocol.get("base_commit") != task["base_commit"]
            or protocol.get("patch_sha256") != _digest(sources.read(old_patch_path))
            or protocol.get("official_eval_script_sha256") != qualified_protocol.get("official_eval_script_sha256")
            or protocol.get("official_eval_script_sha256") != _digest(sources.read(new_path.parent / "eval.sh"))
            or head.get("returncode") != 0 or head.get("expected") != task["base_commit"]):
        raise ValueError("Recovered protocol/base/patch differs")
    if head.get("head") != task["base_commit"]:
        proof_path = Path(new.get("base_source_identity_proof_path", "")).absolute()
        if proof_path != new_path.parent / "base_source_identity/proof.json":
            raise ValueError("Recovered setup HEAD lacks its bound source proof")
        proof = sources.json(proof_path)
        image = sources.json(new_path.parent / "image_receipt.json")
        validation = proof.get("validation") or {}
        if (new.get("base_source_identity_sha256") != _digest(sources.read(proof_path))
                or new.get("base_source_identity_schema") != "repair50_official_setup_source_identity_v1"
                or proof.get("schema") != "repair50_official_setup_source_identity_v1"
                or proof.get("expected_base_commit") != task["base_commit"]
                or proof.get("actual_head") != head["head"] or proof.get("instance_id") != task["instance_id"]
                or proof.get("image_reference") != task["image_reference"]
                or image.get("reference") != task["image_reference"]
                or proof.get("runtime_image_id") != image.get("image_id")
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", image.get("image_id", ""))
                or proof.get("official_eval_script_sha256") != protocol.get("official_eval_script_sha256")
                or validation.get("clean") is not True or validation.get("business_source_matches_base") is not True
                or validation.get("source_mutated") is not False):
            raise ValueError("Recovered setup source proof binding differs")
    derived = copy.deepcopy(original)
    for key in ("status", "resolved", "test_completed", "official_verdict", "environment_error", "error_type", "test_seconds", "apply_ok"):
        derived[key] = new.get(key)
    derived.update(raw_end_to_end_seconds=original.get("end_to_end_seconds"), end_to_end_seconds=None,
        analysis_end_to_end_seconds=None, recovery_evaluation_elapsed_seconds=new.get("elapsed_seconds"),
        recovery_provenance={"binding": str(Path(binding_path).absolute()), "original_status": original["status"],
            "original_record_sha256": old["arm_record"]["sha256"], "original_eval_sha256": old["evaluation_result"]["sha256"],
            "new_eval_sha256": binding["recovered"]["evaluation_result"]["sha256"],
            "original_generation_usage_and_cost_unchanged": True})
    return derived, new_path


def billing_summary(ledger):
    totals = {"known_actual_estimate_nano_usd": 0, "unknown_upper_nano_usd": 0, "reserved_upper_nano_usd": 0}
    counts = {}
    for row in ledger["reservations"].values():
        state = row["status"]
        if state in ("UNKNOWN_COST", "RESERVED") and row.get("charge_nano_usd") is not None:
            raise ValueError("Unsettled ledger charge must remain unknown")
        counts[state] = counts.get(state, 0) + 1
        field, value = ({"SETTLED": ("known_actual_estimate_nano_usd", row.get("charge_nano_usd")),
                         "UNKNOWN_COST": ("unknown_upper_nano_usd", row.get("upper_nano_usd")),
                         "RESERVED": ("reserved_upper_nano_usd", row.get("upper_nano_usd")),
                         "RELEASED": (None, 0)}).get(state, (None, None))
        if type(value) is not int or value < 0:
            raise ValueError("Unknown/invalid ledger status or amount")
        if field:
            totals[field] += value
    return {**totals, "budget_occupancy_upper_nano_usd": sum(totals.values()), "status_counts": counts,
        "unknown_actual_cost_usd": None if counts.get("UNKNOWN_COST", 0) else 0,
        "historical_costs_added_by_exporter": False,
        "historical_reuse_note": "Only current ledger rows counted; historical reuse costs are never added. Duplicate-charge independence was not re-audited by this exporter.",
        "fee_scope": "Whole supplied incremental ledger, not account invoice reconciliation; SETTLED.old upper excluded."}


def finalize(*, run, roster, ledger, output, terminal_log, recovery_bindings=(), maintenance_metadata=None,
             n_bootstrap=BOOTSTRAP_REPLICATES):
    run, output = Path(run).absolute(), Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise FileExistsError("Final output must be a completely new nonlinked directory")
    if output.is_relative_to(run / "cases"):
        raise ValueError("Delivery output cannot be created inside original case evidence")
    sources = Sources()
    selected = sources.json(roster)
    tasks = _roster(selected)
    terminal = terminal_evidence(terminal_log, sources)
    budget = billing_summary(sources.json(ledger))
    bindings = {}
    for path in recovery_bindings:
        b = sources.json(path)
        key = (b.get("instance_id"), b.get("arm"))
        if key in bindings:
            raise ValueError("Duplicate recovery binding for one arm")
        bindings[key] = path
    maintenance = sources.json(maintenance_metadata) if maintenance_metadata else None
    if maintenance and (maintenance.get("instance_id") != "alibaba__opensandbox-816" or maintenance.get("arm") != "A"
            or maintenance.get("controller_parent_paused_during_existing_worker_wait") is not True
            or maintenance.get("original_automatic_end_to_end_may_include_maintenance") is not True):
        raise ValueError("Unsupported maintenance timing metadata")
    records, audits, contexts, groups, raw_count, used_bindings = [], [], {}, {}, 0, set()
    for task in tasks:
        iid = task["instance_id"]
        case = run / "cases" / iid
        prepared = sources.json(case / "prepared.json") if (case / "prepared.json").exists() else None
        if prepared is not None:
            audit = prepared["context_audit"]
            if audit.get("instance_id") != iid or audit.get("base_commit") != task["base_commit"]:
                raise ValueError("Prepared context identity differs")
            audits.append(audit)
        contexts[iid] = prepared
        groups[iid] = input_group(prepared)
        for arm in ("A", "B"):
            path = case / arm / "arm_record.json"
            if not path.exists():
                continue
            raw_count += 1
            record = copy.deepcopy(sources.json(path))
            if record.get("instance_id") != iid or record.get("arm") != arm or prepared is None:
                raise ValueError("Original arm/prepared identity differs")
            generation = record.get("generation_identity") or {}
            if generation.get("task_sha256") != _task_digest(task):
                raise ValueError("Original generation task differs")
            if generation.get("messages_sha256") != _task_digest(prepared["pair_inputs"][arm]["messages"]):
                raise ValueError("Original generation messages differ from prepared inputs")
            eval_path = case / arm / "evaluation/result.json"
            if (iid, arm) in bindings:
                record, eval_path = _recovery(bindings[(iid, arm)], sources, task, arm, record, case)
                used_bindings.add((iid, arm))
            ev = sources.json(eval_path) if eval_path.exists() else {}
            if ev and (ev.get("instance_id") != iid or ev.get("arm") != arm):
                raise ValueError("Evaluation result arm identity differs")
            if record.get("test_completed") is True and (ev.get("test_completed") is not True
                    or ev.get("resolved") is not record.get("resolved")
                    or ev.get("official_verdict") is not record.get("official_verdict")):
                raise ValueError("Original aggregate disagrees with actual evaluation")
            original_paths = record.get("paths") or {}
            paths = {"request": original_paths.get("request", case / arm / "provider/calls/repair/request.json"),
                     "response": original_paths.get("response", case / arm / "candidate_response.json"),
                     "patch": original_paths.get("patch", case / arm / "edit_artifacts/patch.diff"),
                     "eval_result": eval_path if ev else None,
                     "test_output": (ev.get("logpaths") or {}).get("test_output", eval_path.parent / "test_output.txt") if ev else None,
                     "eval_script": (ev.get("logpaths") or {}).get("eval_script", eval_path.parent / "eval.sh") if ev else None}
            actual = {k: sources.optional(v) for k, v in paths.items()}
            if actual["request"]:
                request = sources.json(actual["request"])
                if request["request"]["messages"] != prepared["pair_inputs"][arm]["messages"]:
                    raise ValueError("Actual request differs from frozen prepared messages")
            elif record.get("patch_generated") is True:
                raise ValueError("Generated candidate has no actual request")
            record["paths"] = {**original_paths, **actual, "test_log": actual["test_output"], "report": actual["eval_result"]}
            record["raw_end_to_end_seconds"] = record.get("raw_end_to_end_seconds", record.get("end_to_end_seconds"))
            record["analysis_end_to_end_seconds"] = record.get("end_to_end_seconds")
            if maintenance and (iid, arm) == (maintenance["instance_id"], maintenance["arm"]):
                record.update(end_to_end_seconds=None, analysis_end_to_end_seconds=None,
                    maintenance_timing_reason=maintenance["final_analysis_policy"])
            records.append(record)
    if set(bindings) != used_bindings:
        raise ValueError("Unmatched recovery binding")
    if maintenance and not any((r["instance_id"], r["arm"]) == (maintenance["instance_id"], maintenance["arm"]) for r in records):
        raise ValueError("Maintenance metadata has no original arm")
    if terminal["state"] == "COMPLETE" and raw_count != 100:
        raise ValueError("COMPLETE requires all100 original arm records")
    if terminal["event"].get("records", raw_count) != raw_count:
        raise ValueError("Terminal record count disagrees with original records")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    summary = reporting.build_report(selected, records, audits, output, n_bootstrap=n_bootstrap)
    strict_groups = {}
    delivery = []
    for row in summary["rows"]:
        iid = row["instance_id"]
        flat = {"instance_id": iid, "repo": row["repo"], "base_commit": row["base_commit"], "input_intervention_group": groups[iid]}
        for arm in ("A", "B"):
            rec = row[arm]
            present = rec.get("record_present", False)
            reason = None if present else "BUDGET_STOP_NO_PERSISTED_ARM_RECORD; not a model failure"
            for k in ("status", "resolved", "patch_generated", "parse_ok", "apply_ok", "test_completed", "official_verdict", "environment_error", "generation_seconds", "test_seconds", "cost_usd", "raw_end_to_end_seconds", "analysis_end_to_end_seconds", "recovery_evaluation_elapsed_seconds", "maintenance_timing_reason"):
                flat[arm + "_" + k] = rec.get(k)
            flat[arm + "_record_present"] = present
            flat[arm + "_outcome_category"] = reporting.outcome_category(rec)
            flat[arm + "_not_executed_reason"] = reason or (rec.get("error_type") or rec["status"] if rec.get("patch_generated") is not True else None)
            flat[arm + "_no_formal_test_reason"] = None if reporting.official_outcome(rec) is not None else reason or rec["status"]
            for k in ("request", "response", "patch", "eval_result", "test_output", "eval_script"):
                flat[arm + "_" + k + "_path"] = (rec.get("paths") or {}).get(k)
            flat[arm + "_raw_response_paths"] = ";".join(sources.optional(p) for p in sorted((run / "cases" / iid / arm / "provider/calls/repair").glob("attempt_*_response.json")))
        delivery.append(flat)
    for label in sorted(set(groups.values())):
        subset = [r for r in summary["rows"] if groups[r["instance_id"]] == label]
        strict_groups[label] = {"selected_n": len(subset), "paired_official": paired_statistics([
            {"instance_id": r["instance_id"], "A": reporting.official_outcome(r["A"]), "B": reporting.official_outcome(r["B"])}
            for r in subset], n_bootstrap=n_bootstrap)}
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(delivery[0]), lineterminator="\n")
    writer.writeheader(); writer.writerows(delivery)
    (output / "per_issue_delivery.csv").write_bytes(buf.getvalue().encode("utf-8-sig"))
    result = {"schema": "repair50_offline_delivery_v1", "terminal": terminal, "selected_n": 50,
        "original_arm_record_count": raw_count, "derived_recovery_count": len(used_bindings),
        "paired_official": summary["paired_official"], "arms": summary["arms"], "input_intervention_groups": strict_groups,
        "group_caution": "MESSAGES_IDENTICAL is distinct from SOURCE_SAME_HINTS_DIFFERENT; never call their union a pure position intervention.",
        "billing": budget, "recovery_provenance": [r["recovery_provenance"] for r in records if "recovery_provenance" in r],
        "missing_arms": [{"instance_id": r["instance_id"], "arm": a, "reason": "BUDGET_STOP_NO_PERSISTED_ARM_RECORD"}
                         for r in summary["rows"] for a in ("A", "B") if not r[a].get("record_present")],
        "maintenance_metadata": maintenance, "unknowns_are_not_model_failures_or_zero_cost": True,
        "source_hash_manifest": "source_hash_manifest.json", "new_model_network_container_or_test_calls": 0}
    (output / "delivery_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    note = ["\n## 离线交付补充：严格输入分组\n\n", "源码相同的各组不能统称仅位置差异；全messages相同与提示不同必须分开。\n\n"]
    for label, group in strict_groups.items():
        note.append(f"- {label}：入选{group['selected_n']}，双臂正式可判定{group['paired_official']['paired_n']}。\n")
    note.append("\n原始整臂时间保留于delivery CSV；维护/恢复无法重建的analysis e2e为未知，未修改resolved。费用仅来源于当前增量账本；UNKNOWN实际为未知，预算占用只加SETTLED实际+UNKNOWN上界+RESERVED上界。\n")
    with (output / "实验报告_定位辅助修复配对.md").open("a") as handle:
        handle.write("".join(note))
    (output / "source_hash_manifest.json").write_text(json.dumps({"schema": "repair50_offline_source_hashes_v1",
        "sources": sources.manifest(), "input_files_never_written": True}, ensure_ascii=False, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "roster", "ledger", "output", "terminal-log"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--recovery-binding", action="append", default=[], type=Path)
    parser.add_argument("--maintenance-metadata", type=Path)
    args = vars(parser.parse_args())
    args["recovery_bindings"] = args.pop("recovery_binding")
    result = finalize(**args)
    print(json.dumps({"output": str(args["output"]), "terminal": result["terminal"]["state"],
                      "paired_official_n": result["paired_official"]["paired_n"]}))


if __name__ == "__main__":
    main()
