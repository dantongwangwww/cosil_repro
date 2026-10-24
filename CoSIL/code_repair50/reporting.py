"""Report only persisted arm evidence; never call a model or run a repository.

The adapter accepts one aggregate record per IID/arm. Transport attempt records
belong to the budget ledger and must not be passed as extra candidate versions.
No record is selected according to success and no missing field is invented.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
from pathlib import Path
from statistics import mean, median

from .statistics import BOOTSTRAP_REPLICATES, SEED, paired_statistics, proportion


ARMS = ("A", "B")
BOOL_OPTIONAL = ("resolved", "parse_ok", "apply_ok")
BOOL_REQUIRED_IF_PRESENT = ("patch_generated", "test_completed", "official_verdict", "environment_error")
NUMERIC_FIELDS = ("cost_usd", "generation_seconds", "test_seconds", "end_to_end_seconds")
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "cache_hit_tokens")
METRIC_FIELDS = ("A_file_hit1", "A_file_hit5", "A_function_hit1", "A_function_hit5",
                 "A_function_recall5", "A_all_target_coverage5")
TRUNCATED_STATUSES = frozenset({"OUTPUT_TRUNCATED", "MODEL_OUTPUT_TRUNCATED", "TRUNCATED"})


def _number(value, *, integer=False):
    if value is None:
        return
    if type(value) not in ((int,) if integer else (int, float)) or value < 0 or not math.isfinite(value):
        raise ValueError("Nonnegative finite numeric value or None required")


def _arm(record: dict) -> dict:
    value = dict(record)
    if value.get("arm") not in ARMS or not isinstance(value.get("status"), str):
        raise ValueError("Arm record needs A/B and an explicit status string")
    for key in BOOL_OPTIONAL:
        if value.get(key) is not None and type(value[key]) is not bool:
            raise ValueError("Invalid nullable boolean field: " + key)
    for key in BOOL_REQUIRED_IF_PRESENT:
        if key in value and type(value[key]) is not bool:
            raise ValueError("Invalid boolean field: " + key)
    for key in NUMERIC_FIELDS:
        _number(value.get(key))
    usage = value.get("usage") or {}
    if not isinstance(usage, dict):
        raise ValueError("usage must be a mapping or None")
    for key in TOKEN_FIELDS:
        _number(usage.get(key), integer=True)
    if usage.get("prompt_tokens") is not None and usage.get("cache_hit_tokens") is not None:
        if usage["cache_hit_tokens"] > usage["prompt_tokens"]:
            raise ValueError("Cache-hit tokens exceed prompt tokens")
    if value.get("official_verdict") is True and value.get("test_completed") is not True:
        raise ValueError("Official verdict without completed official tests")
    if value.get("environment_error") is True and value.get("resolved") is not None:
        raise ValueError("Environment-unknown result must not masquerade as a model verdict")
    if value.get("resolved") is True and not all(value.get(key) is True for key in (
        "patch_generated", "parse_ok", "apply_ok", "test_completed", "official_verdict",
    )):
        raise ValueError("Resolved requires a generated, parsed, applied candidate and official tests")
    value["usage"] = usage
    value["record_present"] = True
    return value


def official_outcome(record: dict) -> bool | None:
    if (record.get("test_completed") is True and record.get("official_verdict") is True
            and record.get("environment_error") is not True and type(record.get("resolved")) is bool):
        return record["resolved"]
    return None


def model_pipeline_outcome(record: dict) -> bool | None:
    """Sensitivity only: add terminal generated-candidate format/apply failures."""
    if record.get("environment_error") is True or record.get("patch_generated") is not True:
        return None
    outcome = official_outcome(record)
    if outcome is not None:
        return outcome
    if record.get("parse_ok") is False or record.get("apply_ok") is False:
        return False
    if record.get("status") in TRUNCATED_STATUSES:
        return False
    return None  # Generated-but-pending, missing parser result, or unknown test outcome.


def outcome_category(record: dict) -> str:
    """Diagnostic category supplements, and never overwrites, actual status."""
    if not record.get("record_present"):
        return "MISSING_RECORD"
    if record.get("environment_error") is True:
        return "ENVIRONMENT_UNDETERMINED"
    if official_outcome(record) is True:
        return "OFFICIAL_RESOLVED"
    if official_outcome(record) is False:
        return "OFFICIAL_TEST_UNRESOLVED"
    if record.get("patch_generated") is True:
        if record.get("status") in TRUNCATED_STATUSES:
            return "MODEL_OUTPUT_TRUNCATED"
        if record.get("parse_ok") is False:
            return "MODEL_PARSE_FAILURE"
        if record.get("apply_ok") is False:
            return "MODEL_APPLY_FAILURE"
        return "GENERATED_TEST_UNDETERMINED"
    return "NOT_GENERATED_" + record.get("status", "UNKNOWN")


def _summary(values: list) -> dict:
    known = [value for value in values if value is not None]
    return {"known_n": len(known), "unknown_n": len(values) - len(known),
            "sum_known": sum(known) if known else None,
            "mean_known": mean(known) if known else None,
            "median_known": median(known) if known else None}


def _coverage_group(audit: dict, count_field: str) -> str:
    count, total = audit.get(count_field), audit.get("gold_target_count")
    if count is None or total is None:
        return "UNKNOWN"
    _number(count, integer=True); _number(total, integer=True)
    if total < 1 or count > total:
        raise ValueError("Coverage counts must satisfy 0 <= count <= positive target count")
    return "ALL" if count == total else "NONE" if count == 0 else "PARTIAL"


def _bool_group(audit: dict, key: str) -> str:
    value = audit.get(key)
    if value is None:
        return "UNKNOWN"
    if type(value) is not bool:
        raise ValueError("Context audit booleans must be bool or None")
    return "YES" if value else "NO"


def _normalize(roster, arm_records, context_audits, formal_frozen):
    metadata = dict(roster) if isinstance(roster, dict) else {}
    if isinstance(roster, dict):
        if "tasks" in roster and "records" in roster and roster["tasks"] != roster["records"]:
            raise ValueError("Conflicting tasks/records roster aliases")
        selected = roster.get("tasks", roster.get("records", []))
        flags = [roster[key] for key in ("frozen", "formal_frozen") if key in roster]
        if any(type(value) is not bool for value in flags) or len(set(flags)) > 1:
            raise ValueError("Conflicting or invalid frozen/formal_frozen aliases")
        if formal_frozen is not None and flags and formal_frozen is not flags[0]:
            raise ValueError("Explicit formal_frozen conflicts with roster state")
    else:
        selected, flags = roster, []
    if not isinstance(selected, list):
        raise ValueError("Roster records must be a list")
    frozen = (flags[0] if flags else False) if formal_frozen is None else formal_frozen
    if type(frozen) is not bool:
        raise ValueError("formal_frozen must be an explicit boolean")
    if frozen and len(selected) != 50:
        raise ValueError("The formal diagnostic must contain exactly 50 frozen tasks")
    identities, repositories = {}, set()
    for task in selected:
        iid = task.get("instance_id")
        if not isinstance(iid, str) or not iid or iid in identities:
            raise ValueError("Unique nonempty roster instance_id required")
        if frozen:
            if not isinstance(task.get("repo"), str) or not isinstance(task.get("base_commit"), str):
                raise ValueError("Frozen task must record repository and base commit")
            if task["repo"] in repositories:
                raise ValueError("A formal roster may select at most one task per repository")
            repositories.add(task["repo"])
        identities[iid] = task
    by_key = {}
    for record in arm_records:
        iid = record.get("instance_id")
        if iid not in identities:
            raise ValueError("Arm record is not in the selected roster")
        key = (iid, record.get("arm"))
        if key in by_key:
            raise ValueError("Multiple candidate aggregate records for one IID/arm are forbidden")
        by_key[key] = _arm(record)
    audits = {}
    for audit in context_audits:
        iid = audit.get("instance_id")
        if iid not in identities or iid in audits:
            raise ValueError("Context audit must match a unique selected IID")
        if audit.get("B_added_source") is True and audit.get("source_content_identical") is True:
            raise ValueError("Added source and identical source content are contradictory")
        audits[iid] = dict(audit)
    rows = []
    for iid, task in identities.items():
        audit = audits.get(iid, {})
        row = {"instance_id": iid, "repo": task.get("repo"), "base_commit": task.get("base_commit"),
               "context": audit,
               "A_prediction_coverage_group": _coverage_group(audit, "A_prediction_target_hit_count"),
               "A_source_coverage_group": _coverage_group(audit, "A_target_visible_count"),
               "B_added_source_group": _bool_group(audit, "B_added_source"),
               "source_content_identical_group": _bool_group(audit, "source_content_identical")}
        for arm in ARMS:
            row[arm] = by_key.get((iid, arm), {"instance_id": iid, "arm": arm,
                "status": "MISSING_RECORD", "resolved": None, "record_present": False, "usage": {}})
        rows.append(row)
    return metadata, frozen, rows


def analyze(roster, arm_records: list[dict], context_audits: list[dict] | None = None,
            *, formal_frozen: bool | None = None, n_bootstrap: int = BOOTSTRAP_REPLICATES) -> dict:
    metadata, frozen, rows = _normalize(roster, arm_records, context_audits or [], formal_frozen)
    per_arm = {}
    for arm in ARMS:
        values = [row[arm] for row in rows]
        present = [value for value in values if value.get("record_present")]
        completed = [value for value in values if official_outcome(value) is not None]
        status_counts = {}
        for value in values:
            category = outcome_category(value)
            status_counts[category] = status_counts.get(category, 0) + 1
        success_n = sum(official_outcome(value) is True for value in values)
        fixed_rate = lambda n: proportion(n, 50) if frozen else None
        per_arm[arm] = {
            "record_count": len(present), "generated_n": sum(value.get("patch_generated") is True for value in values),
            "resolved_delivery_fixed50": fixed_rate(success_n),
            "parse_delivery_fixed50": fixed_rate(sum(value.get("parse_ok") is True for value in values)),
            "apply_delivery_fixed50": fixed_rate(sum(value.get("apply_ok") is True for value in values)),
            "test_completed_delivery_fixed50": fixed_rate(sum(value.get("test_completed") is True for value in values)),
            "official_decidable_n": len(completed),
            "official_resolved_rate": proportion(success_n, len(completed)) if frozen else None,
            "environment_failure_n": sum(value.get("environment_error") is True for value in values),
            "status_counts": status_counts,
            "cost_usd": _summary([value.get("cost_usd") for value in present]),
            "usage": {key: _summary([value.get("usage", {}).get(key) for value in present]) for key in TOKEN_FIELDS},
            "timing": {key: _summary([value.get(key) for value in present])
                       for key in ("generation_seconds", "test_seconds", "end_to_end_seconds")},
        }
    def pairing(subset, getter):
        return paired_statistics([{"instance_id": row["instance_id"],
            "A": getter(row["A"]), "B": getter(row["B"])} for row in subset],
            bootstrap_seed=SEED, n_bootstrap=n_bootstrap)
    # Formal rates and hypothesis tests stay unavailable before the roster gate.
    primary = pairing(rows, official_outcome) if frozen else None
    sensitivity = pairing(rows, model_pipeline_outcome) if frozen else None
    grouped = {}
    for grouping in ("A_prediction_coverage_group", "A_source_coverage_group",
                     "B_added_source_group", "source_content_identical_group"):
        groups = {}
        for label in sorted({row[grouping] for row in rows}):
            subset = [row for row in rows if row[grouping] == label]
            groups[label] = {"task_n": len(subset), "paired_official": pairing(subset, official_outcome) if frozen else None}
        grouped[grouping] = groups
    localization = {}
    for key in METRIC_FIELDS:
        entries = [row["context"].get(key) for row in rows]
        for value in entries:
            if value is not None and (type(value) not in (bool, int, float) or not 0 <= value <= 1):
                raise ValueError("Localization audit metric must be in [0,1] or None")
        localization[key] = _summary(entries)
    return {"schema": "repair50_paired_report_v1", "formal_frozen": frozen,
            "selected_n": len(rows), "expected_formal_n": 50,
            "scope": "既有函数目标任务上的开发诊断实验", "metadata": metadata,
            "arms": per_arm, "paired_official": primary, "paired_model_pipeline_sensitivity": sensitivity,
            "groups": grouped, "localization": localization, "rows": rows,
            "unknowns_are_not_zero_cost_or_model_failures": True,
            "bootstrap_seed": SEED, "bootstrap_replicates": n_bootstrap}


def _rate(value) -> str:
    if value is None or value["value"] is None:
        return "NA"
    return f'{value["numerator"]}/{value["denominator"]}（{value["value"]:.2%}）'


def _mean(value) -> str:
    return "NA" if value["mean_known"] is None else f'{value["mean_known"]:.4f}（已知n={value["known_n"]}）'


def _paired_text(value) -> str:
    if value is None or not value["paired_n"]:
        return "暂无双臂正式测试均可判定的配对结果；修复率差、置信区间与检验均为NA。\n"
    cells = value["four_cells"]
    low, high = value["B_minus_A_ci95"]
    return (f'共同可判定分母：{value["paired_n"]}；两组均成功{cells["both_success"]}，'
            f'仅A成功{cells["only_A_success"]}，仅B成功{cells["only_B_success"]}，两组均失败{cells["both_failure"]}。\n\n'
            f'B−A={value["B_minus_A"] * 100:.2f}pp，配对95%区间[{low * 100:.2f}, {high * 100:.2f}]pp；'
            f'精确McNemar双侧p={value["mcnemar"]["pvalue_two_sided"]:.6g}。'
            f'区间采用任务级配对bootstrap（seed={value["bootstrap_seed"]}，{value["bootstrap_replicates"]}次）；'
            '小差异或不显著不能解释为两组等效。\n')


def markdown(summary: dict) -> str:
    lines = ['# SWE-rebench 50题定位辅助修复配对诊断\n',
             '范围：既有函数目标任务上的开发诊断实验；不能代表全部SWE-rebench。'
             'B提供目标身份与可能额外的修复前源码，属于答案辅助诊断条件，不能视为部署方案或修复理论上界。\n']
    blocker = summary["metadata"].get("execution_blocker")
    if blocker is not None:
        lines.append('\n当前执行阻塞：' + str(blocker) + '。该问题不是模型修复失败。\n')
    evidence = summary["metadata"].get("blocker_evidence_paths")
    if evidence:
        lines.append('\n阻塞证据路径：' + '；'.join('`' + str(path) + '`' for path in evidence) + '。\n')
    if not summary["formal_frozen"]:
        lines.append(f'**正式50题名单尚未冻结**。当前记录{summary["selected_n"]}个候选/预览任务；'
                     '不报告0/50修复率，不将资格未完成冒充模型失败。\n')
    else:
        lines.append('以下交付率固定以正式50题为分母；未执行和环境无法判定仅表示未交付正式resolved结果，'
                     '不等于模型补丁测试失败。解析、应用和测试完成各自仍须查看状态分解。\n')
    lines += ['|组别|正式Resolved交付/50|可解析/50|应用/50|测试完成/50|环境无法判定|正式可判定子集修复率|\n',
              '|---|---|---|---|---|---|---|\n']
    for arm in ARMS:
        value = summary["arms"][arm]
        lines.append('|'+ '|'.join([arm, _rate(value["resolved_delivery_fixed50"]), _rate(value["parse_delivery_fixed50"]),
            _rate(value["apply_delivery_fixed50"]), _rate(value["test_completed_delivery_fixed50"]),
            str(value["environment_failure_n"]), _rate(value["official_resolved_rate"])]) + '|\n')
    lines += ['\n|组别|平均费用USD|平均输入token|平均输出token|平均生成秒|平均测试秒|平均端到端秒|\n',
              '|---|---|---|---|---|---|---|\n']
    for arm in ARMS:
        value = summary["arms"][arm]
        lines.append('|'+ '|'.join([arm, _mean(value["cost_usd"]), _mean(value["usage"]["prompt_tokens"]),
            _mean(value["usage"]["completion_tokens"]), *[_mean(value["timing"][key]) for key in
            ("generation_seconds", "test_seconds", "end_to_end_seconds")]]) + '|\n')
        lines.append(f'\n{arm}状态分解：`{json.dumps(value["status_counts"], ensure_ascii=False, sort_keys=True)}`。'
                     f'费用未知记录数={value["cost_usd"]["unknown_n"]}；均值只使用已知记录，不能当成全任务均值。\n')
    lines.append('\n## 同题配对\n\n' + _paired_text(summary["paired_official"]))
    lines.append('\n## 单候选流程敏感性口径\n\n')
    sensitivity = summary["paired_model_pipeline_sensitivity"]
    if sensitivity is None or not sensitivity["paired_n"]:
        lines.append('NA；尚无满足该口径的共同配对。\n')
    else:
        lines.append('额外纳入已生成候选的不可解析、不可应用或输出截断失败；不纳入环境未知、未生成或待测任务。'
                     '该表不是仅正式测试可判定子集，不能与主表混用。\n\n' + _paired_text(sensitivity))
    lines.append('\n## 事后分组（不用于选题或重生成）\n\n')
    lines.append('|维度|组|任务数|双臂正式可判定|A成功|B成功|B−A|\n|---|---|---|---|---|---|---|\n')
    for dimension, groups in summary["groups"].items():
        for label, group in groups.items():
            pair = group["paired_official"]
            diff = "NA" if pair is None or pair["B_minus_A"] is None else f'{100 * pair["B_minus_A"]:.2f}pp'
            lines.append('|'+ '|'.join([dimension, label, str(group["task_n"]), str(pair["paired_n"]) if pair else "NA",
                _rate(pair["A_success_rate"]) if pair else "NA", _rate(pair["B_success_rate"]) if pair else "NA", diff]) + '|\n')
    lines.append('\n预测目标覆盖与源码实际可见性分别分组，缺字段记UNKNOWN，不互相替代。'
                 'A的文件/函数Hit@1、Hit@5、函数Recall@5与全部目标覆盖率保存在summary.json的localization中；'
                 '其已知分母逐项披露，不用50补齐缺失值。\n')
    lines.append('\n## 仅B成功与两组均失败的证据边界\n\n')
    cases = 0
    for row in summary["rows"]:
        a, b = official_outcome(row["A"]), official_outcome(row["B"])
        if a is False and b in (True, False):
            cases += 1
            group = "仅B成功" if b else "两组均失败"
            lines.append(f'- `{row["instance_id"]}`：{group}；预测覆盖={row["A_prediction_coverage_group"]}，'
                         f'A目标源码覆盖={row["A_source_coverage_group"]}，B新增源码={row["B_added_source_group"]}。'
                         '正式测试只确定通过/未通过，具体逻辑原因不确定；须结合已保存补丁与测试日志复核。\n')
    if not cases:
        lines.append('目前没有可按该条件列出的正式配对案例。\n')
    lines.append('\n## 当前可支持的结论\n\n')
    pair = summary["paired_official"]
    if pair is None or not pair["paired_n"]:
        lines.append('目前没有可判定的修复增益证据，不能据此决定优先改善定位还是定位后的诊断与修复。\n')
    else:
        added = summary["groups"]["B_added_source_group"].get("YES", {}).get("paired_official")
        added_n = added["paired_n"] if added else 0
        lines.append(f'共同可判定{pair["paired_n"]}题观察到B−A={pair["B_minus_A"] * 100:.2f}pp；'
                     f'其中B新增源码的共同可判定题数为{added_n}。'
                     '差异可能同时来自位置提示、源码供给和采样波动，不能全部归因于函数排序。'
                     '仅凭本轮总体分数不足以认定剩余问题均是定位错误或代码生成能力不足；'
                     '优先方向须结合仅B成功及双失败案例的证据，结论限于本协议下的开发样本。\n')
    return ''.join(lines)


def _flat(row):
    value = {key: row[key] for key in ("instance_id", "repo", "base_commit", "A_prediction_coverage_group",
        "A_source_coverage_group", "B_added_source_group", "source_content_identical_group")}
    for key in ("gold_target_count", "A_prediction_target_hit_count", "A_target_visible_count",
                "A_all_targets_complete", "source_content_identical", "B_added_source", *METRIC_FIELDS):
        value[key] = row["context"].get(key)
    for arm in ARMS:
        record = row[arm]
        for key in ("status", "resolved", "patch_generated", "parse_ok", "apply_ok", "test_completed",
                    "official_verdict", "environment_error", "error_type", *NUMERIC_FIELDS):
            value[arm + "_" + key] = record.get(key)
        value[arm + "_category"] = outcome_category(record)
        for key in TOKEN_FIELDS:
            value[arm + "_" + key] = record.get("usage", {}).get(key)
        for key in ("request", "response", "patch", "test_log", "report"):
            value[arm + "_" + key + "_path"] = (record.get("paths") or {}).get(key)
    return value


def _write_once(path: Path, content: bytes):
    if path.is_symlink():
        raise ValueError("Report output symlinks are forbidden")
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError("Refusing to overwrite different report evidence")
        return
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(content)


def build_report(roster, arm_records, context_audits, output_dir, *, formal_frozen=None,
                 n_bootstrap=BOOTSTRAP_REPLICATES) -> dict:
    summary = analyze(roster, arm_records, context_audits, formal_frozen=formal_frozen, n_bootstrap=n_bootstrap)
    csv_rows = [_flat(row) for row in summary["rows"]]
    output = io.StringIO(newline="")
    fields = list(csv_rows[0]) if csv_rows else ["instance_id"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n", extrasaction="raise")
    writer.writeheader(); writer.writerows(csv_rows)
    destination = Path(output_dir)
    if destination.is_symlink():
        raise ValueError("Report output directory must not be a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    _write_once(destination / "per_issue.csv", output.getvalue().encode("utf-8-sig"))
    _write_once(destination / "summary.json", (json.dumps(summary, ensure_ascii=False, indent=2,
        sort_keys=True, allow_nan=False) + "\n").encode("utf-8"))
    _write_once(destination / "实验报告_定位辅助修复配对.md", markdown(summary).encode("utf-8"))
    return summary


def build_blocked_report(roster: dict, reason: str, evidence_paths: list[str], output_dir) -> dict:
    """Persist real blocked-state artifacts without manufacturing arm attempts.

    Canonical roster schema is {frozen: bool, tasks: [...]}. Legacy aliases
    formal_frozen/records are accepted only if any duplicate aliases agree.
    """
    if not isinstance(reason, str) or not reason or not isinstance(evidence_paths, list):
        raise ValueError("A real blocker reason and evidence path list are required")
    if any(not isinstance(path, str) for path in evidence_paths):
        raise ValueError("Evidence paths must be strings")
    value = {**roster, "execution_blocker": reason, "blocker_evidence_paths": list(evidence_paths)}
    return build_report(value, [], [], output_dir)
