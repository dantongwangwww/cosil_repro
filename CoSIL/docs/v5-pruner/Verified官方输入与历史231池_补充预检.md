本次仅完成免费官方输入核证，未挖矿、生成标签、训练或执行数据集中的 `eval_script`。旧预检的“尚无官方元数据”属于当时事实，旧收据保留；现在已保存 [SWE-bench 官方 Verified 快照](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified/tree/78f471bf655a3137b2e8a75af1501690ec009ec3)，revision 固定为 `78f471bf655a3137b2e8a75af1501690ec009ec3`。

原 parquet 为 6,304,616 字节，SHA256 `030cfd7f2a704c4c0226e7f104c725a3b41230b1d3517f9c915ad7ea5be3fa25`。完整原列按 `instance_id` 排序导出为 [verified500_full_metadata.jsonl](../../results/v5_pruner/external_sources/verified_official/verified500_full_metadata.jsonl)，SHA256 `87a3d67eb9108386b0a3406ebd1ada9543cb160cd96cfdb792f82de40cd8bcb8`。它保留500题的 issue、repo、base commit、version、patch、test patch、FAIL_TO_PASS、PASS_TO_PASS等原始字段。首次下载发生 TLS 超时，随后在同一固定 revision URL 添加 `download=true` 后下载成功；没有更换数据版本。

| ID 核证项 | 结果 |
|---|---:|
| 官方行数 / 唯一 ID 数 | 500 / 500 |
| 与历史 `evaluation/gt_verified.json` 的 ID 差集 | 0 |
| 与固定 Lite300 的交集 | 93 |
| 官方 Verified 中不属于 Lite 的题 | 407 |
| 93题 repo/base commit/version/issue/patch/test patch/FTP/PTP 输入不一致 | 0 |

“231题无名 OOD 保留池”的身份仍未确认。本次核查 CoSIL 的代码、文档、全部现存 Git 历史，同级 CoSIL_new/GraphLocator 文档，以及 cosil_repro 下针对 v4、231题、无名池的文件与内容，没有找到该旧池的 ID 清单、真实 v4 算法或来源 manifest。不能从407题中任取231题作为替代，也不能把名称包含231的 issue 或数量相近的分类当作身份证据。

为检查能否从既有规则唯一重构，另执行了已存在于 `code_v3b/analyze_experiment_300.py` 的 `normalize/issue_mentions` 两个函数：调用形式与反引号标识符提取，配合历史 `gt_verified` 的目标叶名作分类。这只是名称规则调查；历史目标可能混合函数/类名称，本次没有按 AST 重建其金标类型。调查结果如下，不能当作 v4 保留池。

| 调查分类 | 全部500 | Lite交集93 | 非Lite407 |
|---|---:|---:|---:|
| 提及历史目标叶名 `gold_named` | 168 | 30 | 138 |
| 存在显式名称但未匹配历史目标 `other_named` | 300 | 59 | 241 |
| 没有该正则识别的显式名称 `no_explicit_name` | 32 | 4 | 28 |

现有规则给出的非Lite无显式名称仅28题；241题的另一分类也不能解释成231题。分类算法的源码 SHA、500题调查记录、官方 URL/revision、输入 SHA、交集 ID 和逐字段一致性记录保存在 [来源与身份收据](../../results/v5_pruner/external_sources/verified_official/official_verified500_provenance_and_identity_receipt.json)，SHA256 `fd648dcfead981743c775c532bd27a3792bd0c182ede502c2a23f66bdec4fac3`。因此官方输入缺口已消除，指定历史 OOD 池缺口仍保留；实际扩挖还需处方结果与新的执行协议、保留池身份证据及独立数据/覆盖/审阅冻结。Lite B 线可独立继续。

本次没有读取任何封存 `pruner_test.jsonl` 的 JSON 或标签，没有操作 GPU、vLLM/CSRSE 或他人进程，也没有更新历史预测或跨实验结果矩阵。
