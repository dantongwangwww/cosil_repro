"""Compare A/B real train/val judge predictions without accessing sealed test.

Full validation sets and their common issue/function/input pairs are reported
separately. The paired interval resamples issues, not individual functions.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random

from code_v5.metrics import evaluate_predictions

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    path = Path(path)
    if "test" in path.name.lower():
        raise PermissionError("The comparison never opens test rows")
    result = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(row.get("split") != "val" for row in result):
        raise ValueError("Comparison predictions and data must contain only explicit val rows")
    return result


def key(row):
    return row["instance_id"], row["function_id"]


def index(supplied):
    result = {key(row): row for row in supplied}
    if len(result) != len(supplied):
        raise ValueError("Repeated issue/function identities cannot be compared by row order")
    return result


def validate_predictions(predictions, data):
    found, expected = index(predictions), index(data)
    if found.keys() != expected.keys():
        raise ValueError("Actual prediction set differs from its validation dataset")
    for identity, row in found.items():
        if type(row["label"]) is not bool or row["label"] != expected[identity]["label"]:
            raise ValueError("Prediction labels differ from frozen mechanical labels")
    return found


def paired_accuracy_interval(a, b, *, repeats=2000, seed=20261014):
    by_issue = defaultdict(list)
    for identity in sorted(a):
        ar, br = a[identity], b[identity]
        by_issue[identity[0]].append(int((br["p_yes"] >= .5) == br["label"])
                                     - int((ar["p_yes"] >= .5) == ar["label"]))
    if not by_issue:
        return {"difference_B_minus_A": None, "issue_cluster_percentile_95_interval": None,
                "issue_count": 0, "pair_count": 0}
    ids = sorted(by_issue)
    total = sum(len(v) for v in by_issue.values())
    observed = sum(sum(v) for v in by_issue.values()) / total
    rng = random.Random(seed)
    samples = []
    for _ in range(repeats):
        chosen = [by_issue[rng.choice(ids)] for _ in ids]
        samples.append(sum(sum(v) for v in chosen) / sum(len(v) for v in chosen))
    samples.sort()
    return {"difference_B_minus_A": observed,
            "issue_cluster_percentile_95_interval": [samples[int(.025 * (repeats - 1))], samples[int(.975 * (repeats - 1))]],
            "issue_count": len(ids), "pair_count": total, "bootstrap_repeats": repeats, "seed": seed,
            "limitation": "Exploratory paired validation interval on surviving common pairs; neither held-out test evidence nor causal attribution."}


def pct(value):
    return "NA" if value is None else f"{100 * value:.2f}%"


CONFIG_FIELDS = ('kind', 'rank', 'alpha', 'dropout', 'target_modules', 'learning_rate',
                 'epochs', 'effective_batch', 'micro_batch', 'cutoff', 'dtype', 'seed',
                 'gradient_checkpointing', 'only_lora_trainable', 'weight_decay',
                 'max_gradient_norm', 'early_stop')


def comparison_configuration(run_dir):
    manifest_path = run_dir / 'training_manifest.json'
    manifest = read(manifest_path)
    summary = read(run_dir / 'training_summary.json')
    checkpoint = Path(summary['checkpoint_assessments']['best']['checkpoint'])
    adapter = read(checkpoint / 'adapter_config.json')
    if any(adapter.get(a) != manifest[m] for a, m in
           (('r', 'rank'), ('lora_alpha', 'alpha'), ('lora_dropout', 'dropout'))):
        raise ValueError('Actual saved LoRA configuration differs from its manifest')
    return {**{key: manifest[key] for key in CONFIG_FIELDS},
            'base_model_sha256': manifest['model']['sha256']}, manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a-training-dir", type=Path)
    parser.add_argument("--a-reranker-dir", type=Path)
    parser.add_argument("--a-instruct-dir", type=Path)
    parser.add_argument("--b-training-dir", type=Path, required=True)
    parser.add_argument("--a-data-dir", type=Path, required=True)
    parser.add_argument("--b-data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    a_runs = {kind: override or (args.a_training_dir / kind if args.a_training_dir else None)
              for kind, override in (('reranker', args.a_reranker_dir), ('instruct', args.a_instruct_dir))}
    if any(directory is None for directory in a_runs.values()):
        raise ValueError('Supply each actual A run, or an A training directory; do not substitute pre-regularization weights')
    runs = {'A': a_runs, 'B': {kind: args.b_training_dir / kind for kind in a_runs}}
    doc = ROOT / "docs/v5-pruner/实验报告_v5_A-B_噪声披露与覆盖过滤对照.md"
    if args.output_dir.exists():
        raise FileExistsError("Existing comparisons are immutable; use a new output directory")
    if doc.exists():
        raise FileExistsError("The existing model comparison report is never overwritten")
    datasets = {tag: rows(directory / "pruner_val.jsonl") for tag, directory in (("A", args.a_data_dir), ("B", args.b_data_dir))}
    data_indexes = {tag: index(data) for tag, data in datasets.items()}
    common = sorted(data_indexes["A"].keys() & data_indexes["B"].keys())
    for identity in common:
        a, b = (data_indexes[tag][identity] for tag in ("A", "B"))
        if any(a[field] != b[field] for field in ("label", "input_sha256", "issue", "function")):
            raise ValueError("Common issue/function pair has changed label or model input")
    output = {"schema_version": 1, "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "track": "exploratory", "test_opened_by_this_tool": False, "model_calls": 0,
              "noise_disclosure": "A: E类估计噪声~10%（三族各10条分层抽检3/30，非总体或地板证明）",
              "B_description": "runtime-coverage-filtered data with separately flagged pure-static fallback; not proven noise-free",
              "validation_pair_counts": {"A": len(datasets["A"]), "B": len(datasets["B"]), "common": len(common)},
              "common_validation_pairs": [list(k) for k in common], "models": {}, "artifacts": {},
              "limitations": ["Validation labels remain mechanical proxies and may be noisy.",
                              "Different validation composition and training composition prevent attributing full-set accuracy gains to noise filtering alone.",
                              "Common-pair comparison holds model input and labels fixed but still changes training data; surviving common pairs may be selected.",
                              "Coverage absence does not prove causal irrelevance; static-only fallback is not runtime-verified clean.",
                              "No model test metrics or end-to-end localization gains are inferred from validation metrics."]}
    table = ["| 底座 | 数据版本 | train acc | val样本数 | val acc | val AUC | E正确剔除率 | 混合集剔除precision |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    paired_table = ["| 底座 | 共同val样本数 | A accuracy | B accuracy | A剔除precision | B剔除precision | accuracy差值B−A（百分点） |", "|---|---:|---:|---:|---:|---:|---:|"]
    for kind in ("reranker", "instruct"):
        record = {}
        prediction_indexes = {}
        configs = {}
        for tag in ('A', 'B'):
            configs[tag], manifest_path = comparison_configuration(runs[tag][kind])
            if configs[tag]['kind'] != kind:
                raise ValueError('Explicit model directory differs from the requested base kind')
            output['artifacts'][tag + '/' + kind + '/manifest'] = {
                'path': str(manifest_path.resolve()), 'sha256': sha(manifest_path)}
        if configs['A'] != configs['B']:
            raise ValueError(f'{kind} A/B training configuration or base weights differ; this is not a matched data comparison')
        record['matched_training_configuration'] = configs['A']
        for tag in ('A', 'B'):
            directory = runs[tag][kind]
            summary_path = directory / "training_summary.json"
            summary = read(summary_path)
            if summary["track"] != "exploratory" or summary.get("test_opened") is not False:
                raise RuntimeError("Only completed exploratory train/val results can be compared")
            best = summary["checkpoint_assessments"]["best"]
            path = directory / f"val_epoch_{best['epoch']}.jsonl"
            predicted = rows(path)
            prediction_indexes[tag] = validate_predictions(predicted, datasets[tag])
            measured = evaluate_predictions(predicted)
            if measured != best["val"]:
                raise ValueError("Saved validation metrics differ from actual prediction rows")
            record[tag] = {"best_epoch": best["epoch"], "train": best["train"], "val": measured}
            output["artifacts"][tag + "/" + kind] = {"summary": str(summary_path.resolve()), "summary_sha256": sha(summary_path),
                                                        "val_predictions": str(path.resolve()), "val_prediction_sha256": sha(path)}
            metric = measured["overall"]
            table.append(f"| {kind} | {tag} | {pct(best['train']['overall']['accuracy'])} | {metric['pairs']} | {pct(metric['accuracy'])} | {metric['auc']} | {pct(measured['E_correct_rejection_rate'])} | {pct(metric['reject_precision'])} |")
        common_predictions = {tag: {k: prediction_indexes[tag][k] for k in common} for tag in ("A", "B")}
        paired = {tag: evaluate_predictions(list(common_predictions[tag].values())) for tag in ("A", "B")}
        record["common_val"] = paired
        record["paired_accuracy"] = paired_accuracy_interval(common_predictions["A"], common_predictions["B"])
        output["models"][kind] = record
        ma, mb = paired["A"]["overall"], paired["B"]["overall"]
        delta = record['paired_accuracy']['difference_B_minus_A']
        paired_table.append(f"| {kind} | {len(common)} | {pct(ma['accuracy'])} | {pct(mb['accuracy'])} | {pct(ma['reject_precision'])} | {pct(mb['reject_precision'])} | {'NA' if delta is None else f'{100 * delta:.2f}'} |")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "comparison.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    lines = ["# v5 A/B：噪声披露版与运行时覆盖过滤版", "", "本表使用真实同checkpoint train与val结果，test继续封存。B沿用户命名可称‘干净版’，其准确含义为覆盖过滤版，尚未证明无噪声。", "", *table, "", "混合集剔除precision=TN/(TN+FN)，E正确剔除率=TN/(TN+FP)；两者分别计算，不互换。", "", "不同val组成会改变全量指标，因此另报输入、标签相同的共同issue/function pair：", "", *paired_table, "", "按issue簇重采样的accuracy差值区间：", ""]
    for kind in ("reranker", "instruct"):
        interval = output["models"][kind]["paired_accuracy"]["issue_cluster_percentile_95_interval"]
        lines.append(f"- {kind}：{'NA' if interval is None else f'{100 * interval[0]:.2f} 至 {100 * interval[1]:.2f} 个百分点'}；仅探索性验证对照。")
    lines += ["", "A的E类估计噪声~10%来自三族各10条分层抽检3/30，不是总体噪声率或静态地板证明。B覆盖失败的题仍采用纯静态规则，须结合B数据统计中的覆盖成功比例和新30条审阅解释。", "", "没有test或新端到端定位成绩；不能据此宣称定位准确率已提高。训练数据规模和组成发生变化，共同val对照也不能单独证明改善来源完全是噪声。", "", f"结构化指标、共同pair和哈希：[comparison.json]({(args.output_dir / 'comparison.json').resolve()})。"]
    with doc.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print(json.dumps({"report": str(doc), "json": str(args.output_dir / 'comparison.json'), "common_val_pairs": len(common), "test_rows_decoded": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
