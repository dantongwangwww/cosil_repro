"""Bind thirty completed mechanical reviews to the actual constructed C data.

Review judgments are copied from the three immutable source reviews. Nothing
is relabelled, resampled, tested or inferred by a model here.
"""
from collections import Counter
from pathlib import Path
from copy import deepcopy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/v5_pruner/data_verified_plus_B_runtime"
PREVIEW = ROOT / "results/v5_pruner/C_preconstruction_actual/review_source_runtime_evidence_TRAIN30.json"
PARTIALS = [
    ("results/v5_pruner/C_preconstruction_actual/partial_review_e_log.json", "d81a3465489f3130a23a7108b0621c6fee59d550256183da72b51442485a2342", "records", "record_sha256", "index"),
    ("results/v5_pruner/C_TRAIN30_source_review_partials/partial_review_e_bm25.json", "1f1da47a9ec8df6f60ae263d4e8e5cdfb7ad28cdcf6f7bc073e2813561c73523", "review_records", "preview_record_sha256", "index_1based"),
    ("results/v5_pruner/C_preconstruction_actual/partial_review_e_anchor.json", "2b765a4f11ce68ed29f0dd605cc1dbb59e295b06eff0a0f692d81dce7ded248e", "records", "record_sha256", "index"),
]
OUTPUT = ROOT / "results/v5_pruner/C_TRAIN30_source_review_partials/C_runtime_plus_Verified_full30_codex_reviewed.jsonl"
REPORT = ROOT / "docs/v5-pruner/C融合扩挖_30条逐条审阅与签注.md"
RECEIPT = OUTPUT.with_name("C_full30_actual_RAW_binding_receipt.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def identity(row):
    return {key: row[key] for key in ("review_family", "instance_id", "function_id", "input_sha256")}


def main():
    if any(path.exists() for path in (OUTPUT, REPORT, RECEIPT)):
        raise FileExistsError("Actual signed30 outputs are immutable; no overwrite")
    from code_v5_verified import expanded_policy as policy
    policy.validate_construction()
    packet_path = RAW / "review_source_runtime_evidence.json"
    samples_path = RAW / "human_review.jsonl"
    records = json.loads(packet_path.read_text())["records"]
    previews = json.loads(PREVIEW.read_text())["records"]
    samples = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if (records != previews or len(samples) != 30
            or sha(samples_path) != "c78b8a79f87adfc43897853aab910c63355404653b77b00703d6a41490eeef9f"
            or Counter(row["review_family"] for row in samples) != {"e_log": 10, "e_bm25": 10, "e_anchor": 10}):
        raise RuntimeError("Actual constructed C sample or full source record differs from the reviewed inputs")
    policy.audit_source_packet(samples, records, full_source=True)
    reviews = {}
    partial_hashes = {}
    for relative, expected_sha, rows_key, record_key, index_key in PARTIALS:
        path = ROOT / relative
        if sha(path) != expected_sha:
            raise RuntimeError("Original source review changed: " + relative)
        partial_hashes[str(path)] = expected_sha
        for row in json.loads(path.read_text())[rows_key]:
            index = row[index_key] - 1
            if (index in reviews or not 0 <= index < 30 or row["identity"] != identity(samples[index])
                    or records[index]["identity"] != identity(samples[index])
                    or row[record_key] != object_sha(records[index])
                    or type(row["label_error"]) is not bool
                    or row["label_error"] != (row["relation_classification"] != "retained_limited_evidence")
                    or not isinstance(row["review_note"], str) or not row["review_note"].strip()):
                raise RuntimeError("Review judgment identity/source/bool/note mismatch")
            reviews[index] = row
    if set(reviews) != set(range(30)):
        raise RuntimeError("All thirty actual source reviews are required")
    signed = []
    for index, sample in enumerate(samples):
        row = deepcopy(sample)
        review = reviews[index]
        row.update(review_status="reviewed", label_error=review["label_error"],
                   relation_classification=review["relation_classification"], review_note=review["review_note"],
                   evidence_refs=[{"artifact_path": str(packet_path), "artifact_sha256": sha(packet_path),
                                   "record_sha256": object_sha(records[index]), "section": section}
                                  for section in sorted(policy.SOURCE_SECTIONS)])
        signed.append(row)
    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("xb") as stream:
        stream.write(policy.row_bytes(signed))
    checked, unsafe = policy.validate_review(OUTPUT, audit_source=True)
    classifications = dict(Counter(row["relation_classification"] for row in checked))
    receipt = {"status": "complete30_actual_RAW_bound", "reviewer_kind": "Codex mechanical source/runtime evidence review, not human signature",
               "binding_script_path": str(Path(__file__).resolve()), "binding_script_sha256": sha(Path(__file__).resolve()),
               "signed_review_path": str(OUTPUT), "signed_review_sha256": sha(OUTPUT),
               "actual_raw_sample_sha256": sha(samples_path), "actual_raw_packet_sha256": sha(packet_path),
               "preview_records_exactly_equal_actual_records": True, "partial_review_sha256": partial_hashes,
               "classification_counts": classifications, "unsafe_count": len(unsafe),
               "unsafe_identities": [identity(row) for row in unsafe], "input_labels_changed": 0,
               "model_calls": 0, "tests_run": False, "test_opened": False,
               "interpretation": "Stratified source-risk exclusions, not population noise or certain bug causality; retained evidence is limited."}
    with RECEIPT.open("x") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    labels = {"retained_limited_evidence": "保留（有限证据）", "confirmed_source_relation": "剔除：确认源码关系", "conditional_risk": "剔除：条件风险"}
    lines = ["# C 融合扩挖：30 条逐条审阅与签注", "",
             f"已核对最终 raw 数据和实际完整源码记录，e_log/e_bm25/e_anchor 各 10 条。保守剔除 {len(unsafe)}/30，分类：{json.dumps(classifications, ensure_ascii=False)}。", "",
             "确认源码关系不等于定位根因；条件风险不等于已证错误。保留项也不是全程序无关证明。此分层抽样的剔除比例不能作为总体噪声率。全部仅为 TRAIN 负例，不修改原标签，不打开 test，不生成模型标签。", "",
             "完整审阅证据与模型输入有区别：这30条中8条函数、13条issue超过固定1500/2000字符上限。#16 Field.__init__ 的 required/initial 状态赋值、widget.is_required 与 self.widget 赋值都在函数前1500字符之后；模型不能看到这些源码关系。此为输入信息局限，不是已证明的模型误判成因。", "",
             f"[固定输入可见性审计]({ROOT / 'results/v5_pruner/C_TRAIN30_source_review_partials/C_TRAIN30_fixed_input_visibility_audit.json'})", "",
             f"[实际签注 JSONL]({OUTPUT}) · [完整 base 候选/gold 与运行时证据]({packet_path}) · [身份绑定收据]({RECEIPT})", "",
             "| 序号 | 产线 | issue | 函数 | 审阅处理 | 题级运行时资格 |", "|---:|---|---|---|---|---|"]
    for index, row in enumerate(checked):
        qualified = records[index]["runtime_evidence"]["qualified"]
        lines.append(f"| {index + 1} | {row['review_family']} | {row['instance_id']} | `{row['function_id']}` | {labels[row['relation_classification']]} | {'合格覆盖' if qualified else '纯静态回退'} |")
    for index, row in enumerate(checked):
        lines.extend(["", f"## {index + 1}. {row['instance_id']} / {row['function_id']}", "",
                      row["review_note"], "", f"金标函数：{', '.join(records[index]['gold'])}。", "",
                      f"运行时缓存：[result.json]({records[index]['runtime_evidence']['result_path']})。源码、图和静态来源见完整证据包同一 instance/function/input SHA 记录。"])
    with REPORT.open("x") as stream:
        stream.write("\n".join(lines) + "\n")
    print(json.dumps({"review_path": str(OUTPUT), "review_sha256": sha(OUTPUT), "unsafe_count": len(unsafe),
                      "classification_counts": classifications, "report_path": str(REPORT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
