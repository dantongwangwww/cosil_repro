"""Actual prescription result versus preserved original A; all metrics train/val."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from code_v5.noise_disclosed_policy import ROOT, DERIVED, sha
from code_v5_regularized.policy import ORIGINAL_RERANKER, validate_decision


def read(path):
    return json.loads(Path(path).read_text())


def pct(value):
    return "NA" if value is None else f"{100 * value:.2f}%"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-dir", type=Path, required=True)
    parser.add_argument("--race-dir", type=Path, required=True)
    parser.add_argument("--decision-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    stats, seal, ids, provenance = validate_decision(DERIVED, args.decision_file)
    original = read(ORIGINAL_RERANKER / "training_summary.json")
    summary = read(args.training_dir / "training_summary.json")
    race = read(args.race_dir / "race_report.json")
    if summary["test_opened"] or race.get("test_opened", False) or race["test_used_for_selection"]:
        raise RuntimeError("Prescription report cannot include test performance")
    comparison = {"pre_regularization": original["checkpoint_assessments"]["best"],
                  "post_regularization_peak": summary["checkpoint_assessments"]["best"],
                  "post_regularization_last": summary["checkpoint_assessments"]["last"]}
    val = comparison["post_regularization_peak"]["val"]["overall"]
    result = {"schema_version": 1, "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "track": "exploratory", "experiment_condition": "rank8_dropout0.1_alpha32",
              "provenance": provenance, "data_counts": stats["selected"], "comparison": comparison,
              "selected_peak_epoch": summary["selected_peak_epoch"], "epochs_completed": summary["epochs_completed"],
              "race": race, "test_opened": False, "end_to_end_localization_accuracy": None,
              "user_corrected_diagnosis": "The measured 23.93pp pre-regularization gap is treated as overfitting by explicit user decision; original report and all original artifacts remain intact.",
              "expansion_trigger_val_accuracy_lt_0_80": val["accuracy"] < .8,
              "expansion_requested_condition": "Verified plus runtime-filtered B, delegated to root; not triggered automatically by this reporter",
              "qualification_unchanged": val["accuracy"] >= .8 and val["auc"] is not None and val["auc"] >= .85,
              "alpha_r_confounding": "alpha remains32; effective alpha/r scales from2 to4 when rank changes16 to8",
              "models": {"reranker": {"training_summary_path": str((args.training_dir / 'training_summary.json').resolve()),
                                      "summary_sha256": sha(args.training_dir / "training_summary.json")}}}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    pending = args.output_dir / "assessment_report.json.pending"
    with pending.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    lines = ["# v5 A线：rank8、dropout0.1 正则处方 exploratory", "",
             "用户将原训练/验证23.93个百分点的差距裁定为过拟合，本轮执行一次独立正则处方。原A数据、模型、签注、预测和报告保留。", "",
             "rank16→8、dropout0→0.1；alpha维持32，所以alpha/r从2→4，这也是同时变化的因素。其余lr5e-5、最多3epoch、batch8/micro2、BF16、cutoff4096及E下降早停沿用原配置。", "",
             "新checkpoint按已完成epoch的验证accuracy峰值选择，依次以AUC、E剔除率、较早epoch打破并列；原reranker的3轮accuracy峰值是epoch3，恰与其原best一致。赛马仍采用acc≥0.80、AUC≥0.85资格及E/2pp偏好规则，原instruct沿原E-best，不改其symlink。", "",
             "| 条件 | epoch | train accuracy | val accuracy | val AUC | val E剔除率 | val gold保留 | 混合剔除precision |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, row in comparison.items():
        metrics = row["val"];overall = metrics["overall"]
        lines.append(f"| {name} | {row['epoch']} | {pct(row['train']['overall']['accuracy'])} | {pct(overall['accuracy'])} | {overall['auc']} | {pct(metrics['E_correct_rejection_rate'])} | {pct(overall['gold_retention_recall'])} | {pct(overall['reject_precision'])} |")
    lines += ["", "| 条件 | TP | FN | FP | TN |", "|---|---:|---:|---:|---:|"]
    for name, row in comparison.items():
        m = row["val"]["overall"]["confusion"]
        lines.append(f"| {name} | {m['TP']} | {m['FN']} | {m['FP']} | {m['TN']} |")
    lines += ["", "| 条件 | 来源membership | 样本数 | 正例保留recall | 负例正确剔除 |", "|---|---|---:|---:|---:|"]
    for name, row in comparison.items():
        for source in ("A", "B", "C", "D", "e_log", "e_bm25", "e_anchor", "E"):
            group = row["val"]["groups"][source]
            lines.append(f"| {name} | {source} | {group['pairs']} | {pct(group['retain_recall'])} | {pct(group['negative_rejection_rate'])} |")
    lines += ["", "来源membership有交叠，不能相加；E行是去重并集。gold保留率为未校准p≥0.5的二分类召回，包含所有普通正判，不能称为high-confidence保留，更不是已执行灰区Qwen的最终召回。", "",
              "验证赛马：" + race["selection"]["status"] + "；" + race["selection"]["reason"] + "。", "",
              ("处方峰值val accuracy仍<0.80，按用户最新裁定触发Verified＋B融合扩挖条件；root负责后续实际扩挖。" if result["expansion_trigger_val_accuracy_lt_0_80"] else "处方峰值val accuracy达到0.80；是否通过原AUC资格及安全路由以实际赛马记录为准。"), "",
              "原3/30分层抽检不是总体噪声率或静态噪声地板证明；train为拟合样本表现，尚不能宣称泛化或端到端定位提升。test仍封存、Qwen基线未重跑、Decision-1取消、没有新增定位对照列。", "",
              f"结构化结果：`{(args.output_dir / 'assessment_report.json').relative_to(ROOT)}`。"]
    report = ROOT / "docs/v5-pruner/实验报告_v5_A线_rank8_dropout01正则处方.md"
    with report.open("x") as stream:
        stream.write("\n".join(lines) + "\n")
    pending.rename(args.output_dir / "assessment_report.json")
    print(json.dumps({"report": str(report), "outcome": str(args.output_dir / 'assessment_report.json'),
                      "expansion_trigger": result["expansion_trigger_val_accuracy_lt_0_80"]}, ensure_ascii=False))
