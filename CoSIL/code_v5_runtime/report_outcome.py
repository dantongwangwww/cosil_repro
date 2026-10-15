"""B runtime-covered train/val report; no test decoder or end-to-end predictions."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from code_v5.judge_models import file_sha256

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def diagnose(train_accuracy, val_accuracy, auc):
    if train_accuracy < .70:
        return "a", "训练准确率<0.70：按用户操作路线给出扩数据候选信号；不能单独证明数据不足。"
    if train_accuracy > .85 and val_accuracy < .70:
        return "b", "训练>0.85、验证<0.70：符合指定过拟合判据；本报告未自动触发额外训练。"
    if val_accuracy >= .80 and auc is not None and auc >= .85:
        return "validation_qualified", "验证满足acc≥0.80、AUC≥0.85；实际train accuracy另列，不填造未指定的train达标数值。"
    return "intermediate_unqualified", "未达原验证资格且处于未穷尽的中间/边界分支；不擅自扩数或开test。"


def pct(value):
    return "NA" if value is None else f"{value * 100:.2f}%"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--decision-file", type=Path, required=True)
    parser.add_argument("--training-dir", type=Path, required=True)
    parser.add_argument("--race-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    from code_v5.runtime_filtered_policy import validate_decision
    stats, seal, split_ids, provenance = validate_decision(args.data_dir, args.decision_file)
    pair = read(args.training_dir / "pair_status.json")
    if pair["stage"] != "complete":
        raise RuntimeError("Complete actual B pair required")
    models = {}
    for kind in ("reranker", "instruct"):
        path = args.training_dir / kind / "training_summary.json"
        summary = read(path)
        if summary.get("data_policy") != "runtime-covered-v3" or summary.get("test_opened") is not False:
            raise RuntimeError("Different B data policy or test opening detected")
        assessments = summary["checkpoint_assessments"]
        best = assessments["best"]
        train, val = best["train"]["overall"], best["val"]["overall"]
        route, interpretation = diagnose(train["accuracy"], val["accuracy"], val["auc"])
        models[kind] = {"summary_path": str(path.resolve()), "summary_sha256": file_sha256(path),
                        "best": best, "last": assessments["last"], "epochs_completed": summary["epochs_completed"],
                        "early_stopped": summary["early_stopped"], "diagnosis": {"user_route": route, "interpretation": interpretation}}
    race_path = args.race_dir / "race_report.json"
    race = read(race_path)
    if race.get("test_opened", False) or race["test_used_for_selection"]:
        raise RuntimeError("B report refuses opened test performance")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = {"schema_version": 1, "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "track": "exploratory", "data_policy": "runtime-covered-v3", "data_dir": str(args.data_dir.resolve()),
              "decision_sha256": file_sha256(args.decision_file), "data_provenance": provenance,
              "counts": stats["selected"], "review": stats["review"], "models": models, "validation_race": race,
              "test_opened": False, "test_performance": None, "end_to_end_localization_accuracy": None,
              "new_matrix_columns": 0, "historical_Qwen_baseline_rerun": False, "Decision_1_run": False,
              "limitations": ["Runtime evidence can demonstrate a path but incomplete execution coverage does not prove irrelevance.",
                              "Review is a train-only stratified sample, not population label-noise estimation.",
                              "Cross-version aggregate accuracy can change with changed samples; compare identical val pairs separately.",
                              "Real train accuracy is fitting-sample performance; test/generalization remains unmeasured."]}
    output = args.output_dir / "assessment_report.json"
    pending_output = output.with_suffix(".json.pending")
    with pending_output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    counts = stats["selected"]
    review = stats["review"]
    lines = ["# v5 B线：runtime-covered exploratory 双底座", "",
             "本报告来自实际B双底座训练与验证；test仍封存，没有新增端到端定位准确率。", "",
             f"数据：正例{counts['positive']}，负例{counts['negative']}，E {counts.get('E_unique_union', 0)}；train/val/test封存计数为{seal['frozen_files']['train']['count']}/{seal['frozen_files']['val']['count']}/{seal['frozen_files']['test']['count']}。test计数来自封存元数据，未解码test行。", "",
             "原A/v3的3/30错误签注不改。本轮B的30条训练分层审阅与删除清单以独立B签注/派生记录为准；审阅不能证明总体无噪声。", "",
             f"B审阅记录：`{json.dumps(review, ensure_ascii=False)}`。", "",
             "| 底座 | best epoch | train accuracy | val accuracy | val AUC | val E正确剔除率 | 完成epoch | 判读 |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for kind, row in models.items():
        best = row["best"]
        lines.append(f"| {kind} | {best['epoch']} | {pct(best['train']['overall']['accuracy'])} | {pct(best['val']['overall']['accuracy'])} | {best['val']['overall']['auc']} | {pct(best['val']['E_correct_rejection_rate'])} | {row['epochs_completed']} | {row['diagnosis']['user_route']} |")
    lines += ["", "train/val按同一个best checkpoint对照；train来自全部实际TRAIN样本eval推理，未用loss替代accuracy。", "",
              "| 底座 | last epoch | last train accuracy | last val accuracy | last val AUC |", "|---|---:|---:|---:|---:|"]
    for kind, row in models.items():
        last = row["last"]
        lines.append(f"| {kind} | {last['epoch']} | {pct(last['train']['overall']['accuracy'])} | {pct(last['val']['overall']['accuracy'])} | {last['val']['overall']['auc']} |")
    lines += ["", "验证赛马：" + race["selection"]["status"] + "；" + race["selection"]["reason"] + "。", ""]
    for kind, row in models.items():
        lines.append(f"- {kind}：{row['diagnosis']['interpretation']}")
    lines += ["", "按kind保持与相应A条件一致：reranker rank8/dropout0.1/alpha32/val accuracy峰值，对照post-prescription A；instruct rank16/dropout0/alpha32/原E-best，对照原A instruct。其余all-linear、lr5e-5、最多3epoch、batch8/micro2、BF16、cutoff4096及E下降早停相同；本实验仅使用GPU2，GPU3不由本实验占用。", "",
              "运行时覆盖不完整时，未观察到调用不能推导无关；标签仍受测试覆盖、输入截断、静态/运行时遗漏及来源分布影响。跨版总体指标受样本变化影响，应配合同val pair对照。", "",
              "test未开箱、Qwen基线未重跑、Decision-1取消，未新增定位表列。", "",
              f"结构化结果：`{output.relative_to(ROOT)}`。"]
    report = ROOT / "docs/v5-pruner/实验报告_v5_B线_runtime覆盖exploratory.md"
    with report.open("x") as stream:
        stream.write("\n".join(lines) + "\n")
    pending_output.rename(output)
    print(json.dumps({"report": str(report), "json": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
