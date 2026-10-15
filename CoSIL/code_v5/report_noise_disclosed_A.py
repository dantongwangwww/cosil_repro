"""Report actual paired train/val assessments without reading test or adding predictions."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from code_v5.noise_disclosed_policy import ROOT, DERIVED, sha, read_json, write_json


def percent(value):
    return "NA" if value is None else f"{value * 100:.2f}%"


def diagnose(train_accuracy, val_accuracy, auc):
    # These are the user's requested operational heuristics; neither proves a
    # unique cause. In particular low train accuracy can also arise from noise,
    # task visibility, optimization or the base's limitations.
    if train_accuracy < .70:
        return {"user_route": "a", "interpretation": "训练准确率<0.70，按用户路线视作待扩数据信号；单一指标不能证明只有数据不足。", "automatic_expansion_started": False}
    if train_accuracy > .85 and val_accuracy < .70:
        return {"user_route": "b", "interpretation": "训练>0.85、验证<0.70，符合过拟合操作判据；需独立一轮正则/早停调整，尚未自动重训。", "automatic_expansion_started": False}
    if val_accuracy >= .80 and auc is not None and auc >= .85:
        return {"user_route": "validation_qualified", "interpretation": "满足原验证资格acc≥0.80且AUC≥0.85；真实训练准确率另列。用户(c)未另给train达标数值，不擅自填造。", "automatic_expansion_started": False}
    return {"user_route": "intermediate_unqualified", "interpretation": "处于a/b/c未穷尽的中间或边界情况，且未达原验证资格，诚实保留结果；未自动扩数据或开test。", "automatic_expansion_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-dir", type=Path, required=True)
    parser.add_argument("--race-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    pair = read_json(args.training_dir / "pair_status.json")
    if pair["stage"] != "complete":
        raise RuntimeError("Actual complete two-base summaries are required")
    stats = read_json(DERIVED / "statistics.json")
    rows = {}
    for kind in ("reranker", "instruct"):
        summary = read_json(args.training_dir / kind / "training_summary.json")
        if summary.get("data_policy") != "noise-disclosed-v3" or summary.get("test_opened") is not False:
            raise RuntimeError("Different policy or a test opening detected")
        assessments = summary["checkpoint_assessments"]
        best = assessments["best"]
        train_acc, val_acc, auc = best["train"]["overall"]["accuracy"], best["val"]["overall"]["accuracy"], best["val"]["overall"]["auc"]
        rows[kind] = {"training_summary_path": str((args.training_dir / kind / "training_summary.json").resolve()),
                      "training_summary_sha256": sha(args.training_dir / kind / "training_summary.json"),
                      "epochs_completed": summary["epochs_completed"], "early_stopped": summary["early_stopped"],
                      "best": best, "last": assessments["last"], "diagnosis": diagnose(train_acc, val_acc, auc)}
    race = read_json(args.race_dir / "race_report.json")
    if race.get("test_opened", False) or race["test_used_for_selection"]:
        raise RuntimeError("No test performance may enter the exploratory report")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "track": "exploratory", "data_policy": "noise-disclosed-v3", "formal_data_gate_passed": False,
              "dataset_statistics_sha256": sha(DERIVED / "statistics.json"), "counts": stats["selected"],
              "original_noise_disclosure": "E类估计噪声~10%（三族各10条的分层抽检3/30，非总体噪声率或静态地板证明）",
              "models": rows, "validation_race": race, "test_opened": False,
              "test_performance": None, "end_to_end_localization_accuracy": None,
              "new_matrix_columns": 0, "historical_Qwen_baseline_rerun": False, "Decision_1_run": False,
              "limitations": stats["limitations"] + ["Best/last train assessment uses fitting samples and measures memorization/fit, not generalization.", "Val still contains unreviewed mechanical labels and can retain noise.", "Without test/end-to-end runs no downstream localization improvement is claimed."]}
    # The B queue treats the final JSON as A's completion receipt. Publish it
    # atomically only after the Markdown report is completely written.
    pending_report = args.output_dir / "assessment_report.json.pending"
    write_json(pending_report, report)
    lines = ["# v5 A线：v3 噪声披露 exploratory 双底座", "", "本报告只使用本轮实际训练与验证结果；test 继续封存，没有新的端到端定位准确率。", "",
             "原 v3 的 30 条审阅为 3 错、正式质量门失败，历史签注与统计保留。新授权仅从 TRAIN 剔除 3 个确认反例；正例 1,542，负例 3,081，E 2,997。train/val/test 为 3,921/363/339，val/test 与原 v3 字节完全相同。", "",
             "**E 类估计噪声 ~10%（三族各10条的分层抽检3/30，非总体噪声率或静态地板证明）**。其余标签仍可能含噪声；剔除3条不能证明剩余数据正确。", "",
             "| 底座 | best epoch | train accuracy | val accuracy | val AUC | val E正确剔除率 | 完成epoch | 判读 |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for kind, row in rows.items():
        best = row["best"]
        lines.append(f"| {kind} | {best['epoch']} | {percent(best['train']['overall']['accuracy'])} | {percent(best['val']['overall']['accuracy'])} | {best['val']['overall']['auc']} | {percent(best['val']['E_correct_rejection_rate'])} | {row['epochs_completed']} | {row['diagnosis']['user_route']} |")
    lines += ["", "train 与 val 使用同一 best checkpoint，train accuracy 来自全部真实 TRAIN 样本的 eval 推理，未用 loss 代替。", "", "| 底座 | last epoch | last train accuracy | last val accuracy | last val AUC |", "|---|---:|---:|---:|---:|"]
    for kind, row in rows.items():
        last = row["last"]
        lines.append(f"| {kind} | {last['epoch']} | {percent(last['train']['overall']['accuracy'])} | {percent(last['val']['overall']['accuracy'])} | {last['val']['overall']['auc']} |")
    lines += ["", "以下混淆矩阵、gold保留率与混合剔除precision均来自对应checkpoint的全部363条验证预测。", "",
              "| 底座 | 快照 | epoch | TP | FN | FP | TN | gold保留率 | 混合剔除precision |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for kind, row in rows.items():
        for role in ("best", "last"):
            assessment = row[role]
            overall = assessment["val"]["overall"]
            matrix = overall["confusion"]
            lines.append(f"| {kind} | {role} | {assessment['epoch']} | {matrix['TP']} | {matrix['FN']} | {matrix['FP']} | {matrix['TN']} | {percent(overall['gold_retention_recall'])} | {percent(overall['reject_precision'])} |")
    lines += ["", "混合剔除precision=TN/(TN+FN)，有真实正/负例混合；E正确剔除率=E的TN/(TN+FP)，二者含义不同。", "",
              "| 底座 | 快照 | 来源membership | 样本数 | 正例保留recall | 负例正确剔除率 |", "|---|---|---|---:|---:|---:|"]
    for kind, row in rows.items():
        for role in ("best", "last"):
            for source in ("A", "B", "C", "D", "e_log", "e_bm25", "e_anchor", "E"):
                group = row[role]["val"]["groups"][source]
                lines.append(f"| {kind} | {role} | {source} | {group['pairs']} | {percent(group['retain_recall'])} | {percent(group['negative_rejection_rate'])} |")
    lines += ["", "来源按label_sources的membership分组，存在交叠（例如B可同时属于A，D可同时属于E）；各组不能相加当总样本数。E一行是去重并集。分组差距可能与输入可见性、任务难度、来源/项目偏差或残留噪声有关，不能直接断言都是噪声。", "",
              "更高E剔除率也可能伴随更低gold保留率，应一起审视；满足单一E目标不等于满足原acc/AUC资格或端到端定位目标。"]
    lines += ["", "验证赛马：" + race["selection"]["status"] + "；" + race["selection"]["reason"] + "。", ""]
    for kind, row in rows.items():
        lines.append(f"- {kind}：{row['diagnosis']['interpretation']}")
    lines += ["", "固定配置：LoRA rank16、all-linear、lr5e-5、最多3 epoch、effective batch8、micro batch2、BF16、cutoff4096；按既有验证E下降规则早停。", "",
              "D-only 仅84条（负例的2.73%），E占约97.27%；来源/项目/有名类别分布偏差仍在。训练准确率低不唯一证明数据不足，训练高验证低亦需结合噪声、输入可见性与issue分布差异分析。", "",
              "test未开箱，未重跑Qwen基线，Decision-1维持取消，未生成任何新的定位对照表列。", "",
              f"结构化记录：`{(args.output_dir / 'assessment_report.json').relative_to(ROOT)}`；训练：`{args.training_dir.relative_to(ROOT)}`；验证赛马：`{args.race_dir.relative_to(ROOT)}`。"]
    path = ROOT / "docs/v5-pruner/实验报告_v5_A线_v3噪声披露exploratory.md"
    with path.open("x") as stream:
        stream.write("\n".join(lines) + "\n")
    pending_report.rename(args.output_dir / "assessment_report.json")
    print(json.dumps({"report": str(path), "json": str(args.output_dir / "assessment_report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
