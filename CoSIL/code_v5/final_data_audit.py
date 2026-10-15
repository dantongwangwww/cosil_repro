"""Export the final 300-issue v5 data audit without opening sealed judge test rows.

This is a provenance/count report. It reuses the unchanged historical CoSIL
scorer and baseline, writes isolated reports, and never produces predictions.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v3b.build_result_matrix import read_experiment, score

TITLE = "实验报告_v5_逐题数据审计"
SOURCES = ("A", "B", "C", "D", "e_log", "e_bm25", "e_anchor")


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def sources(row):
    return set(row.get("label_sources", [])) | {row["label_source"]} if row.get("label_source") else set(row.get("label_sources", []))


def printable(value):
    return "NA（封存未读）" if value is None else str(value)


def hit_label(value):
    return "NA（无函数真值）" if value is None else "命中" if value else "未命中"


def escape(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def baseline_text(result):
    if result["state"] == "missing":
        return "缺少结果"
    if result["state"] == "failed":
        return "运行失败"
    if not result["positions"]:
        return "定位为空"
    return "; ".join(f'{position["file"]}::{position["kind"]}:{position["name"]}'
                     for position in result["positions"][:5])


def run(args):
    data = Path(args.data_dir).resolve()
    result_dir, document_dir = Path(args.result_dir).resolve(), Path(args.document_dir).resolve()
    result_json, result_jsonl = result_dir / "final_data_audit_300.json", result_dir / "final_data_audit_300.jsonl"
    document_md, document_csv = document_dir / f"{TITLE}.md", document_dir / f"{TITLE}.csv"
    outputs = (result_json, result_jsonl, document_md, document_csv)
    if any(path.exists() for path in outputs):
        raise FileExistsError("Preserve existing generated audit; use a new output directory")
    statistics_path, split_path, seal_path = (data / name for name in ("statistics.json", "split_manifest.json", "test_file_seal.json"))
    review_path = Path(args.review_file).resolve() if args.review_file else data / "human_review_codex_reviewed.jsonl"
    if not review_path.exists():
        review_path = data / "human_review.jsonl"
    proof_path = data / "review_final_counterexamples.json"
    store_path = ROOT / "results/comparison/逐题定位对照数据.json"
    gold_path, baseline_path = ROOT / "ground_truth_300.json", ROOT / "results/qwen_300/fixed/off/loc_off.jsonl"
    input_paths = [statistics_path, split_path, seal_path, review_path, proof_path, store_path,
                   gold_path, baseline_path, data / "pruner_train.jsonl", data / "pruner_val.jsonl",
                   data / "pruner_test.jsonl", data / "negative_exclusions.jsonl"]
    inputs_before = {str(path): digest(path) for path in input_paths}
    statistics, split, seal, store = map(read_json, (statistics_path, split_path, seal_path, store_path))
    if statistics.get("passed") is not False or statistics.get("training_started") is not False:
        raise ValueError("This final report requires an honestly failed data gate and zero actual training")
    if statistics.get("test_performance_opened") is not False or seal.get("test_performance_opened") is not False:
        raise ValueError("Judge test must remain sealed")
    test_file = data / "pruner_test.jsonl"
    if test_file.with_name(test_file.name + ".v5_opened_once.json").exists():
        raise ValueError("Judge test opening was consumed; this provenance-only report assumes no test inference")
    if statistics["split_manifest_sha256"] != inputs_before[str(split_path)] or statistics["seal"] != seal:
        raise ValueError("Statistics split/seal provenance drift")
    for name in ("train", "val", "test"):
        path = data / f"pruner_{name}.jsonl"
        if (Path(seal["frozen_files"][name]["path"]).resolve() != path or
                inputs_before[str(path)] != seal["frozen_files"][name]["sha256"]):
            raise ValueError(f"Frozen {name} binary hash/path mismatch")
    assigned = {iid: name for name, ids in split["splits"].items() for iid in ids}
    ids = store["issue_order"]
    if (len(ids) != 300 or len(set(ids)) != 300 or set(assigned) != set(ids) or
            sum(len(group) for group in split["splits"].values()) != 300 or
            {name: len(group) for name, group in split["splits"].items()} != {"train": 240, "val": 30, "test": 30}):
        raise ValueError("Exactly the fixed 300 unique issue IDs and 240/30/30 assignments are required")
    projects = store["projects"]
    if len(projects) != 6:
        raise ValueError("Expected the unchanged six historical comparison columns")
    gold = read_json(gold_path)
    if set(gold) != set(ids) or store["gold_sha256"] != inputs_before[str(gold_path)]:
        raise ValueError("Historical localization gold differs from the preserved comparison scorer")
    historical = read_experiment(baseline_path, set(ids))
    if set(historical) != set(ids):
        raise ValueError("Historical CoSIL/off must contain the same 300 IDs")
    off = [project for project in projects if project["column"] == "CoSIL/off"]
    if (len(off) != 1 or off[0]["source_sha256"] != inputs_before[str(baseline_path)] or
            off[0]["records"] != historical):
        raise ValueError("Comparison CoSIL/off provenance disagrees with the frozen raw baseline")
    scores = {iid: score(historical[iid], gold[iid]) for iid in ids}
    hits = sum(result["top5"] is True for result in scores.values())
    scorable = sum(result["top5"] is not None for result in scores.values())
    if (hits, scorable, 300 - scorable) != (111, 293, 7):
        raise ValueError("Historical scorer must reproduce 111/293 Top5 with seven NA issues")

    # Only train/val JSON records are decoded. Test contributes binary hash and
    # prepublished aggregate metadata, never per-row labels or function input.
    selected = defaultdict(Counter)
    for name in ("train", "val"):
        seen = set()
        for row in jsonl(data / f"pruner_{name}.jsonl"):
            iid = row["instance_id"]
            pair = iid, row["function_id"]
            if assigned[iid] != name or row["split"] != name or pair in seen:
                raise ValueError("Selected train/val pair identity/split drift")
            seen.add(pair)
            counter = selected[iid]
            counter["pairs"] += 1
            counter["positive" if row["label"] else "negative"] += 1
            counter["primary_" + row["label_source"]] += 1
            for source in sources(row): counter["source_" + source] += 1
            if sources(row) & {"e_log", "e_bm25", "e_anchor"}: counter["E_union"] += 1
        aggregate = Counter()
        own = {iid: counter for iid, counter in selected.items() if assigned[iid] == name}
        for counter in own.values(): aggregate.update(counter)
        published = statistics["selected"]["by_split"][name]
        if (aggregate["positive"] != published["positive"] or aggregate["negative"] != published["negative"] or
                aggregate["E_union"] != published["E_unique_union"] or len(own) != published["issues_with_rows"] or
                len(seen) != seal["frozen_files"][name]["count"]):
            raise ValueError("Selected train/val counts disagree with published statistics/seal")
        for source in SOURCES:
            if aggregate["source_" + source] != published.get("source_" + source, 0):
                raise ValueError(f"Published {name}/{source} membership count drift")
    test_aggregate = statistics["selected"]["by_split"]["test"]
    if (test_aggregate["positive"] + test_aggregate["negative"] != seal["frozen_files"]["test"]["count"] or
            test_aggregate["issues_with_rows"] != len(split["splits"]["test"])):
        raise ValueError("Sealed aggregate does not prove that every assigned test issue has data")

    exclusion_counts, exclusion_sources, exclusion_kinds = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    seen_exclusions = set()
    for row in jsonl(data / "negative_exclusions.jsonl"):
        iid, fid = row["instance_id"], row["function_id"]
        if iid not in assigned or (iid, fid) in seen_exclusions:
            raise ValueError("Excluded negative pair identity duplicate/outside fixed benchmark")
        seen_exclusions.add((iid, fid))
        exclusion_counts[iid]["negative_pairs"] += 1
        for source in set(row["label_sources"]): exclusion_sources[iid][source] += 1
        for kind in {reason["kind"] for reason in row["reasons"]}: exclusion_kinds[iid][kind] += 1
        exclusion_counts[iid]["overapproximation_pairs"] += any(reason.get("overapproximation") is True for reason in row["reasons"])
    if len(seen_exclusions) != statistics["excluded_negative_unique_pairs"]:
        raise ValueError("Exclusion union differs from final statistics")
    overall_kinds = Counter()
    for counter in exclusion_kinds.values(): overall_kinds.update(counter)
    if dict(overall_kinds) != statistics["exclusion_reason_pair_counts"]:
        raise ValueError("Exclusion reason counts differ from final statistics")

    review_rows = list(jsonl(review_path))
    if len(review_rows) != 30 or any(assigned[row["instance_id"]] != "train" for row in review_rows):
        raise ValueError("QC must be the original 30 training E records")
    proofs = read_json(proof_path)
    qc, proof_by_pair = defaultdict(list), {}
    for proof in proofs["proofs"]:
        identity = proof["identity"]
        key = identity["instance_id"], identity["function_id"], identity["input_sha256"]
        proof_by_pair[key] = proof["kind"]
    for row in review_rows:
        key = row["instance_id"], row["function_id"], row["input_sha256"]
        confirmed = key in proof_by_pair or row.get("label_error") is True
        qc[row["instance_id"]].append({"function_id": row["function_id"], "review_family": row["review_family"],
                                       "review_status": row.get("review_status"), "label_error": True if confirmed else row.get("label_error"),
                                       "confirmed_counterexample_kind": proof_by_pair.get(key),
                                       "review_note": row.get("review_note")})
    qc_errors = sum(record["label_error"] is True for records in qc.values() for record in records)
    if qc_errors < 3 or proofs["errors_lower_bound"] < 3:
        raise ValueError("The final stopping decision requires at least three confirmed QC false negatives")
    if statistics["review"].get("status") == "reviewed":
        if statistics["review"].get("label_errors") != qc_errors or statistics["review"].get("passed") is not False:
            raise ValueError("Final signed statistics disagree with the recorded failed QC")

    rows = []
    for iid in ids:
        name = assigned[iid]
        counter = selected[iid] if name != "test" else None
        has_data = bool(counter["pairs"]) if counter is not None else True
        mining = statistics["per_issue_refinement"][iid]
        result = scores[iid]
        rows.append({"instance_id": iid, "repo": gold[iid]["repo"], "assigned_split": name,
                     "has_selected_data": has_data, "selected_count_scope": "decoded train/val only" if counter is not None else "sealed; per-issue counts not read",
                     "selected_pairs": counter["pairs"] if counter is not None else None,
                     "selected_positive": counter["positive"] if counter is not None else None,
                     "selected_negative": counter["negative"] if counter is not None else None,
                     "selected_E_union": counter["E_union"] if counter is not None else None,
                     "selected_source_counts": {source: counter["source_" + source] for source in SOURCES} if counter is not None else None,
                     "selected_primary_source_counts": {source: counter["primary_" + source] for source in SOURCES} if counter is not None else None,
                     "v3_raw_candidate_pairs": mining["raw_pairs"], "v3_raw_positive_pairs": mining["raw_positive"],
                     "v3_raw_negative_pairs": mining["raw_negative"], "v3_excluded_negative_pairs": exclusion_counts[iid]["negative_pairs"],
                     "v3_remaining_negative_candidates": mining["remaining_negative"],
                     "v3_exclusion_source_counts": dict(exclusion_sources[iid]), "v3_exclusion_reason_counts": dict(exclusion_kinds[iid]),
                     "v3_overapproximation_excluded_pairs": exclusion_counts[iid]["overapproximation_pairs"],
                     "QC_reviewed_candidate_count": len(qc[iid]), "QC_confirmed_false_negative_count": sum(record["label_error"] is True for record in qc[iid]),
                     "QC_records": qc[iid], "historical_CoSIL_off": result,
                     "historical_CoSIL_off_top5_text": hit_label(result["top5"]),
                     "v5_status": "not_executed_D2_failed", "actual_gradient_training": False,
                     "actual_gradient_training_rows": 0, "v5_localization_state": "not_executed",
                     "v5_found_related_locs": None, "v5_top1": None, "v5_top3": None, "v5_top5": None,
                     "v5_model_accuracy": None, "v5_model_auc": None, "v5_model_E_rejection_rate": None})
    inputs_after = {str(path): digest(path) for path in input_paths}
    if inputs_after != inputs_before:
        raise RuntimeError("Concurrent input/signature change; discard this attempt and rerun after final hashes freeze")
    summary = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "producer": "code_v5/final_data_audit.py",
               "producer_sha256": digest(Path(__file__)), "status": "D2_failed; no training or v5 localization",
               "same_300_instance_id_join": True, "historical_scorer": "code_v3b.build_result_matrix.score",
               "historical_baseline": {"project": "CoSIL/off", "top5_hits": hits, "scorable_issues": scorable,
                                       "NA_no_function_gold": 7, "top5_accuracy": hits / scorable,
                                       "result_state_counts": dict(Counter(result["state"] for result in scores.values()))},
               "data_version": statistics.get("dataset_version"), "assigned_issue_counts": {name: len(group) for name, group in split["splits"].items()},
               "issues_with_selected_data": {name: statistics["selected"]["by_split"][name]["issues_with_rows"] for name in ("train", "val", "test")},
               "selected_aggregate_counts": statistics["selected"], "failed_quality_gates": [key for key,value in statistics["quality_gates"].items() if value is not True],
               "quality_gates": statistics["quality_gates"], "review": statistics["review"],
               "QC_confirmed_errors": qc_errors, "QC_errors_lower_bound": proofs["errors_lower_bound"],
               "QC_review_path": str(review_path), "actual_issues_used_for_gradient_training": 0, "actual_gradient_training_steps": 0,
               "actual_canary_runs": 0, "actual_full_localization_runs": 0, "v5_new_prediction_metrics": None,
               "test_rows_decoded": False, "test_per_issue_selected_counts": "NA; frozen binary hash and published aggregate only",
               "historical_localization_gold_scope": "Prior benchmark truth used only to reproduce the historical off score; sealed v5 judge test labels are never opened",
               "comparison_store_columns_preserved": [project["column"] for project in projects],
               "comparison_store_sha256_before": inputs_before[str(store_path)], "comparison_store_sha256_after": inputs_after[str(store_path)],
               "inputs": {path: {"sha256": checksum} for path,checksum in inputs_before.items()},
               "rows": rows}
    header = ["issue", "项目", "分配集合", "有样本", "实际梯度训练题", "选中样本", "正样本", "负样本", "E并集",
              *["来源" + source for source in SOURCES], "v3排除负例", "v3剩余负候选", "排除风险类型", "QC抽检数", "QC确认错负例",
              "历史CoSIL/off状态", "历史CoSIL/off Top5", "历史CoSIL/off前5定位", "v5阶段", "v5新Top5", "v5模型Accuracy/AUC/E"]
    export = []
    for row in rows:
        export.append([row["instance_id"], row["repo"], row["assigned_split"], "是" if row["has_selected_data"] else "否", 0,
                       *[printable(row[key]) for key in ("selected_pairs", "selected_positive", "selected_negative", "selected_E_union")],
                       *[printable(row["selected_source_counts"][source] if row["selected_source_counts"] is not None else None) for source in SOURCES],
                       row["v3_excluded_negative_pairs"], row["v3_remaining_negative_candidates"], json.dumps(row["v3_exclusion_reason_counts"],ensure_ascii=False,sort_keys=True),
                       row["QC_reviewed_candidate_count"], row["QC_confirmed_false_negative_count"], row["historical_CoSIL_off"]["state"],
                       row["historical_CoSIL_off_top5_text"], baseline_text(row["historical_CoSIL_off"]), "D2失败；未训练/未定位", "NA（未执行）", "NA（未执行）"])
    body = [f"# {TITLE}", "", "v5最终数据质量门失败，实际梯度训练、金丝雀与全量新定位均为0。本报告保留同300题的数据准备审计及历史CoSIL/off定位，所有v5新定位和模型性能均为NA（未执行）。", "",
            f"历史基线按现有评分函数复核：Top5 = {hits}/{scorable} = {hits/scorable:.2%}，另7题无函数真值（NA）。空定位、失败、缺少结果由历史状态字段分别保留；不能将v5未执行视为定位未命中。", "",
            "分配集合为train240/val30/test30；最终拥有选中样本的题数为217/27/30。217题表示已有数据行，实际用于梯度训练仍是0题。正样本1542不足原定8000，30条训练E质检至少3条源码确证错负例，超过最多2条的门限，因此不启动训练。", "",
            "仅解码train/val样本。test30题每题选中个数及来源计数标为封存未读；test汇总339条（正113/负226，E220）和30题均有数据来自已公布statistics，并只核对封存文件二进制SHA。历史定位金标仅用于复核既有基线，与未打开的v5 judge test标签分开。", "",
            "来源A/B/C/D及三族E可能重叠，来源计数不能直接求和当成样本总数。风险类型是保守负例排除证据，possible/overapproximation不代表精确因果调用图。质检由Codex核对源码/补丁/调用链，不能写作真人签字；未用模型制造标签。", "",
            "| 分配集合 | 分配题数 | 有选中数据题数 | 选中样本 | 正/负 | 实际梯度训练题数 |", "|---|---:|---:|---:|---:|---:|"]
    for name in ("train", "val", "test"):
        counts = statistics["selected"]["by_split"][name]
        body.append(f'| {name} | {len(split["splits"][name])} | {counts["issues_with_rows"]} | {counts["positive"]+counts["negative"]} | {counts["positive"]}/{counts["negative"]} | 0 |')
    body += ["", f"最终statistics SHA256：`{inputs_before[str(statistics_path)]}`；QC文件：`{review_path.relative_to(ROOT) if review_path.is_relative_to(ROOT) else review_path}`。", "",
             "| issue | 集合 | 有数据 | 选中数(正/负) | A/B/C | D/E并集 | v3排除负例 | QC错负/抽检 | 历史off Top5 | v5新Top5 |", "|---|---|---|---|---|---|---:|---|---|---|"]
    for row in rows:
        counter=row["selected_source_counts"]
        quantities="封存未读" if counter is None else f'{row["selected_pairs"]}({row["selected_positive"]}/{row["selected_negative"]})'
        abc="封存未读" if counter is None else "/".join(str(counter[source]) for source in ("A","B","C"))
        de="封存未读" if counter is None else f'{counter["D"]}/{row["selected_E_union"]}'
        body.append(f'| {row["instance_id"]} | {row["assigned_split"]} | {"是" if row["has_selected_data"] else "否"} | {quantities} | {abc} | {de} | {row["v3_excluded_negative_pairs"]} | {row["QC_confirmed_false_negative_count"]}/{row["QC_reviewed_candidate_count"]} | {row["historical_CoSIL_off_top5_text"]} | NA（未执行） |')
    body += ["", "逐题抽检证据：", ""]
    for row in rows:
        if row["QC_records"]:
            body.append(f'- `{row["instance_id"]}`：' + "; ".join(f'`{record["function_id"]}`（{record["review_family"]}，' + ("确认错负例" if record["label_error"] is True else "未记错负例" if record["label_error"] is False else "尚未签注") + (f'；{record["confirmed_counterexample_kind"]}' if record["confirmed_counterexample_kind"] else "") + '）' for record in row["QC_records"]))
    body += ["", "同名CSV包含全部来源计数、风险类型、历史前5定位及新实验NA状态；JSON/JSONL保留详细QC证据与输入哈希。六个既有比较列及历史预测未改写，未向结果矩阵追加虚构v5列。", ""]
    for path in outputs: path.parent.mkdir(parents=True, exist_ok=True)
    with result_json.open("x",encoding="utf-8") as stream: json.dump(summary,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write("\n")
    with result_jsonl.open("x",encoding="utf-8") as stream:
        for row in rows: stream.write(json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n")
    with document_csv.open("x",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream);writer.writerow(header);writer.writerows(export)
    with document_md.open("x",encoding="utf-8") as stream: stream.write("\n".join(body))
    if digest(store_path) != inputs_before[str(store_path)]:
        raise RuntimeError("Historical comparison store changed during export")
    return {"status":summary["status"],"rows":len(rows),"historical_top5":f"{hits}/{scorable}","test_rows_decoded":False,
            "statistics_sha256":inputs_before[str(statistics_path)],"QC_errors":qc_errors,
            "outputs":{str(path):digest(path) for path in outputs}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,default=ROOT/"results/v5_pruner/data_v3")
    parser.add_argument("--review-file",type=Path)
    parser.add_argument("--result-dir",type=Path,default=ROOT/"results/v5_pruner")
    parser.add_argument("--document-dir",type=Path,default=ROOT/"docs/v5-pruner")
    args=parser.parse_args()
    print(json.dumps(run(args),ensure_ascii=False,indent=2,allow_nan=False))


if __name__=="__main__":main()
