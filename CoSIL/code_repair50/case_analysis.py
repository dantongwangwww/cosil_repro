"""Offline evidence-bounded repair diagnostics, without models or execution.

Only persisted model patch artifacts and official evaluation summaries/status
maps are read. Reference patches, benchmark rows, hidden test source, and
repository source are deliberately outside this reader's filename whitelist.
"""
from __future__ import annotations

import csv
from collections import Counter
import io
import json
import os
from pathlib import Path

from .executor import diff_target_paths
from .reporting import _normalize, _write_once, official_outcome


ALLOWED_JSON = frozenset({"evaluation_record.json", "result.json", "official_report.json", "parsed_test_statuses.json"})
KNOWN_PIPELINE_FAILURES = frozenset({"PARSE_FAILURE", "APPLY_FAILURE", "INTEGRITY_REJECTED", "OUTPUT_TRUNCATED"})
LABELS = {
    "RESOLVED": "正式测试解决", "NOT_EXECUTED": "未执行/缺记录", "BUDGET_NOT_EXECUTED": "预算限制未执行或重试停止",
    "INTEGRITY_REJECTED": "触犯评分文件保护规则", "OUTPUT_TRUNCATED": "模型输出截断",
    "PARSE_FAILURE": "补丁结构不可解析", "APPLY_FAILURE": "精确编辑或正式补丁应用失败",
    "GENERATION_FAILURE": "生成协议/传输失败", "ENVIRONMENT_FAILURE": "明确环境故障",
    "TEST_REQUIREMENTS_UNSATISFIED": "完整观测下正式测试要求未满足",
    "INCOMPLETE_TEST_OBSERVATIONS": "正式未解决但测试观测不完整",
    "UNDETERMINED": "原因不确定/待完成",
}
PAIR_LABELS = {
    "ONLY_B_WITH_ADDED_SOURCE": "仅B正式成功，伴随额外目标源码",
    "ONLY_B_WITH_IDENTICAL_SOURCE": "仅B正式成功，源码内容相同",
    "ONLY_B_OTHER": "仅B正式成功，源码差异证据不足",
    "BOTH_FORMAL_UNRESOLVED": "两组正式测试均未解决",
    "ONLY_B_PIPELINE_DELIVERED": "仅B交付成功，A有明确格式/应用/完整性失败",
    "ONLY_A_FORMAL_RESOLVED": "仅A正式成功", "ONLY_A_PIPELINE_DELIVERED": "仅A交付成功，B有明确流程失败",
    "BOTH_RESOLVED": "两组均正式成功", "UNPAIRED_OR_UNDETERMINED": "未执行/环境/未知，不作双失败判断",
}


class ArtifactReader:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.warnings = []

    def read(self, path, *, patch=False):
        if not path:
            return None
        supplied = Path(path)
        supplied = supplied if supplied.is_absolute() else self.root / supplied
        allowed = supplied.name == "patch.diff" if patch else supplied.name in ALLOWED_JSON
        try:
            if not allowed or not supplied.resolve().is_relative_to(self.root):
                raise ValueError("outside artifact filename/root whitelist")
            current = self.root
            for part in supplied.absolute().relative_to(self.root).parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError("symlink artifact refused")
            if not supplied.is_file():
                self.warnings.append("MISSING_ARTIFACT:" + str(supplied))
                return None
            text = supplied.read_text(encoding="utf-8")
            return text if patch else json.loads(text)
        except (OSError, ValueError, UnicodeError) as exc:
            self.warnings.append("UNREADABLE_OR_FORBIDDEN_ARTIFACT:" + str(supplied) + ":" + type(exc).__name__)
            return None


def _relative(path, destination):
    return os.path.relpath(Path(path).absolute(), Path(destination).absolute()).replace(os.sep, "/") if path else None


def _failure_counts(verdict, statuses, family):
    tests = verdict.get("tests_status") if isinstance(verdict, dict) else None
    group = tests.get(family) if isinstance(tests, dict) else None
    failure = group.get("failure") if isinstance(group, dict) else None
    if not isinstance(failure, list) or any(not isinstance(test, str) for test in failure):
        return {"official_failure_n": None, "observed_failure_n": None}
    observed = None if not isinstance(statuses, dict) else sum(statuses.get(test) in {"FAILED", "ERROR"} for test in failure)
    return {"official_failure_n": len(failure), "observed_failure_n": observed}


def arm_evidence(record, reader):
    paths = record.get("paths") or {}
    patch_path = paths.get("patch")
    patch = reader.read(patch_path, patch=True)
    modified = None
    if patch is not None:
        try:
            modified = sorted(diff_target_paths(patch))
        except ValueError:
            reader.warnings.append("MODEL_DIFF_IDENTITIES_UNPARSEABLE:" + str(patch_path))
    directories = []
    if paths.get("directory"):
        directories.append(Path(paths["directory"]))
    if patch_path:
        directories.append(Path(patch_path).parent.parent / "evaluation")
    if paths.get("response"):
        directories.append(Path(paths["response"]).parent / "evaluation")
    evaluation, evaluation_path = {}, None
    for directory in dict.fromkeys(directories):
        candidates = [directory.parent / "evaluation_record.json", directory / "result.json"]
        for candidate in candidates:
            loaded = reader.read(candidate)
            if isinstance(loaded, dict):
                evaluation, evaluation_path = loaded, str(candidate)
                break
        if evaluation_path:
            break
    if evaluation.get("instance_id") not in (None, record.get("instance_id")) or evaluation.get("arm") not in (None, record.get("arm")):
        raise ValueError("Official artifact belongs to another IID/arm")
    verdict = evaluation.get("official_result") or {}
    status_map, status_path, official_path = None, None, None
    for directory in dict.fromkeys(directories):
        loaded = reader.read(directory / "parsed_test_statuses.json")
        if isinstance(loaded, dict):
            status_map, status_path = loaded, str(directory / "parsed_test_statuses.json")
        if not verdict:
            loaded = reader.read(directory / "official_report.json")
            if isinstance(loaded, dict):
                verdict = loaded.get(record.get("instance_id"), {})
                official_path = str(directory / "official_report.json")
        if status_map is not None and verdict:
            break
    return {"modified_files": modified, "fully_observed_expected_tests": evaluation.get("fully_observed_expected_tests"),
            "F2P": _failure_counts(verdict, status_map, "FAIL_TO_PASS"),
            "P2P": _failure_counts(verdict, status_map, "PASS_TO_PASS"),
            "evaluation_path": evaluation_path, "status_path": status_path,
            "official_report_path": official_path, "patch_path": patch_path,
            "test_log_path": paths.get("test_log") or paths.get("test_output")}


def classify_arm(record, evidence):
    status = record.get("status", "")
    if not record.get("record_present"):
        return "NOT_EXECUTED"
    if "INTEGRITY" in status:
        return "INTEGRITY_REJECTED"
    if "BUDGET" in status:
        return "BUDGET_NOT_EXECUTED"
    if record.get("environment_error") is True:
        return "ENVIRONMENT_FAILURE"
    if official_outcome(record) is True:
        return "RESOLVED"
    if "TRUNCATED" in status:
        return "OUTPUT_TRUNCATED"
    if record.get("parse_ok") is False:
        return "PARSE_FAILURE"
    if record.get("apply_ok") is False and record.get("environment_error") is False:
        return "APPLY_FAILURE"
    if official_outcome(record) is False:
        return ("TEST_REQUIREMENTS_UNSATISFIED" if evidence["fully_observed_expected_tests"] is True
                else "INCOMPLETE_TEST_OBSERVATIONS")
    if record.get("patch_generated") is False and "GENERATION" in status:
        return "GENERATION_FAILURE"
    return "UNDETERMINED"


def analyze_cases(roster, arm_records, context_audits, artifact_root):
    _, frozen, rows = _normalize(roster, arm_records, context_audits or [], None)
    reader = ArtifactReader(artifact_root)
    cases = []
    for row in rows:
        audit = row["context"]
        case = {key: row[key] for key in ("instance_id", "repo", "base_commit", "A_prediction_coverage_group",
            "A_source_coverage_group", "B_added_source_group", "source_content_identical_group")}
        for key in ("gold_target_count", "A_prediction_target_hit_count", "A_target_visible_count",
                    "A_file_hit1", "A_file_hit5", "A_function_hit1", "A_function_hit5", "A_function_recall5"):
            case[key] = audit.get(key)
        for arm in ("A", "B"):
            evidence = arm_evidence(row[arm], reader)
            case[arm] = {"status": row[arm].get("status"), "resolved": official_outcome(row[arm]),
                         "category": classify_arm(row[arm], evidence), **evidence}
        a, b = case["A"]["resolved"], case["B"]["resolved"]
        pair = "UNPAIRED_OR_UNDETERMINED"
        if a is True and b is True:
            pair = "BOTH_RESOLVED"
        elif a is False and b is False:
            pair = "BOTH_FORMAL_UNRESOLVED"
        elif a is True and b is False:
            pair = "ONLY_A_FORMAL_RESOLVED"
        elif a is False and b is True:
            if case["A_source_coverage_group"] in {"NONE", "PARTIAL"} and audit.get("B_added_source") is True:
                pair = "ONLY_B_WITH_ADDED_SOURCE"
            elif audit.get("source_content_identical") is True:
                pair = "ONLY_B_WITH_IDENTICAL_SOURCE"
            else:
                pair = "ONLY_B_OTHER"
        elif b is True and case["A"]["category"] in KNOWN_PIPELINE_FAILURES:
            pair = "ONLY_B_PIPELINE_DELIVERED"
        elif a is True and case["B"]["category"] in KNOWN_PIPELINE_FAILURES:
            pair = "ONLY_A_PIPELINE_DELIVERED"
        case["pair_category"] = pair
        case["specific_logic_cause"] = "原因不确定；没有按参考补丁相似度判断正确性，也未据双失败推断代码生成能力不足"
        cases.append(case)
    return {"schema": "repair50_offline_case_diagnosis_v1", "formal_frozen": frozen,
            "task_n": len(cases), "pair_class_counts": dict(Counter(case["pair_category"] for case in cases)),
            "arm_class_counts": {arm: dict(Counter(case[arm]["category"] for case in cases)) for arm in ("A", "B")},
            "artifact_warnings": reader.warnings, "cases": cases,
            "reference_patches_or_hidden_test_source_read": False, "new_model_or_repository_execution": False}


def render_diagnosis(summary, output_dir):
    lines = ["# 单次修复失败诊断：先分类，再逐题\n\n",
        "本报告只读已经落盘的模型补丁、正式判分与测试状态汇总，不读取参考补丁或隐藏测试源码，不调用模型。"
        "分类说明可观测失败阶段；具体根因证据不足时保留不确定。\n\n",
        f'任务数：{summary["task_n"]}；正式名单已冻结：{summary["formal_frozen"]}。\n\n',
        "## 分类总览\n\n|同题分类|题数|\n|---|---:|\n"]
    for key, count in sorted(summary["pair_class_counts"].items()):
        lines.append(f"|{PAIR_LABELS[key]}|{count}|\n")
    lines.append("\n|组别失败阶段（按组计数）|数量|\n|---|---:|\n")
    for arm in ("A", "B"):
        for key, count in sorted(summary["arm_class_counts"][arm].items()):
            lines.append(f"|{arm}：{LABELS[key]}|{count}|\n")
    lines.append("\n仅B成功且B补源码，表示增益伴随源码供给变化，不能证明源码是单一原因。"
                 "同源码仅位置提示不同时仍有采样波动。完整观测的正式未通过只支持测试要求尚未满足；"
                 "是否遗漏联动修改、为何逻辑错误，需要更多代码与失败断言证据，不能自动推断。"
                 "部分/缺失测试观测、环境故障和预算未执行均独立保留。\n\n## 逐题分析\n\n")
    priority = lambda case: (0 if case["pair_category"].startswith("ONLY_B") else
                             1 if case["pair_category"] == "BOTH_FORMAL_UNRESOLVED" else 2, case["instance_id"])
    for case in sorted(summary["cases"], key=priority):
        lines.append(f'### {case["instance_id"]}\n\n{PAIR_LABELS[case["pair_category"]]}。'
            f'A预测目标覆盖={case["A_prediction_coverage_group"]}；A目标源码可见性={case["A_source_coverage_group"]}；'
            f'B新增源码={case["B_added_source_group"]}；源码相同={case["source_content_identical_group"]}。\n\n')
        for arm in ("A", "B"):
            value = case[arm]
            display = lambda item: "NA" if item is None else str(item)
            files = "NA（没有可核验模型diff）" if value["modified_files"] is None else ", ".join(value["modified_files"]) or "空修改"
            lines.append(f'{arm}：{LABELS[value["category"]]}（实际状态`{value["status"]}`）；修改文件：{files}。'
                f'expected测试全部观测={display(value["fully_observed_expected_tests"])}；'
                f'F2P官方失败/实际观测失败={display(value["F2P"]["official_failure_n"])}/{display(value["F2P"]["observed_failure_n"])}；'
                f'P2P官方失败/实际观测失败={display(value["P2P"]["official_failure_n"])}/{display(value["P2P"]["observed_failure_n"])}。\n\n')
            links = []
            for key, label in (("patch_path", "模型补丁"), ("evaluation_path", "正式执行记录"),
                               ("status_path", "测试状态"), ("official_report_path", "正式判分"), ("test_log_path", "测试日志")):
                if value.get(key):
                    links.append(f'[{arm}{label}](<{_relative(value[key], output_dir)}>)')
            if links:
                lines.append("；".join(links) + "。\n\n")
        if case["pair_category"] == "ONLY_B_WITH_ADDED_SOURCE":
            lines.append("已观察到A未具备全部目标完整源码、B新增源码且仅B正式成功；这是伴随源码变化的增益证据，不能单独证明因果机制。\n\n")
        lines.append(case["specific_logic_cause"] + "。\n\n")
    lines.append(f'产物缺失/拒读提示共{len(summary["artifact_warnings"])}项，明细见诊断JSON；缺失不补零。\n')
    return "".join(lines)


def build_case_report(roster, arm_records, context_audits, artifact_root, output_dir):
    summary = analyze_cases(roster, arm_records, context_audits, artifact_root)
    destination = Path(output_dir)
    if destination.is_symlink():
        raise ValueError("Diagnostic output directory must not be a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in summary["cases"]:
        row = {key: value for key, value in case.items() if key not in {"A", "B"}}
        for arm in ("A", "B"):
            for key in ("status", "resolved", "category", "fully_observed_expected_tests"):
                row[f"{arm}_{key}"] = case[arm][key]
            row[f"{arm}_modified_files"] = json.dumps(case[arm]["modified_files"], ensure_ascii=False)
            for family in ("F2P", "P2P"):
                for key, value in case[arm][family].items():
                    row[f"{arm}_{family}_{key}"] = value
            for key in ("patch_path", "evaluation_path", "status_path", "test_log_path"):
                row[f"{arm}_{key}"] = _relative(case[arm].get(key), destination)
        rows.append(row)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["instance_id"], lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    _write_once(destination / "修复失败逐题诊断.csv", stream.getvalue().encode("utf-8-sig"))
    _write_once(destination / "修复失败诊断.json", (json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())
    _write_once(destination / "修复失败分析_先分类再逐题.md", render_diagnosis(summary, destination).encode())
    return summary
