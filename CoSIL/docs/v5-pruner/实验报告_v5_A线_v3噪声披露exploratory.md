# v5 A线：v3 噪声披露 exploratory 双底座

本报告只使用本轮实际训练与验证结果；test 继续封存，没有新的端到端定位准确率。

原 v3 的 30 条审阅为 3 错、正式质量门失败，历史签注与统计保留。新授权仅从 TRAIN 剔除 3 个确认反例；正例 1,542，负例 3,081，E 2,997。train/val/test 为 3,921/363/339，val/test 与原 v3 字节完全相同。

**E 类估计噪声 ~10%（三族各10条的分层抽检3/30，非总体噪声率或静态地板证明）**。其余标签仍可能含噪声；剔除3条不能证明剩余数据正确。

| 底座 | best epoch | train accuracy | val accuracy | val AUC | val E正确剔除率 | 完成epoch | 判读 |
|---|---:|---:|---:|---:|---:|---:|---|
| reranker | 3 | 99.41% | 75.48% | 0.8328666074721672 | 90.64% | 3 | intermediate_unqualified |
| instruct | 2 | 93.88% | 72.73% | 0.8475513967625162 | 95.32% | 3 | intermediate_unqualified |

train 与 val 使用同一 best checkpoint，train accuracy 来自全部真实 TRAIN 样本的 eval 推理，未用 loss 代替。

| 底座 | last epoch | last train accuracy | last val accuracy | last val AUC |
|---|---:|---:|---:|---:|
| reranker | 3 | 99.41% | 75.48% | 0.8328666074721672 |
| instruct | 3 | 98.70% | 74.66% | 0.8499590191926781 |

以下混淆矩阵、gold保留率与混合剔除precision均来自对应checkpoint的全部363条验证预测。

| 底座 | 快照 | epoch | TP | FN | FP | TN | gold保留率 | 混合剔除precision |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| reranker | best | 3 | 56 | 65 | 24 | 218 | 58.82% | 77.03% |
| reranker | last | 3 | 56 | 65 | 24 | 218 | 58.82% | 77.03% |
| instruct | best | 2 | 35 | 86 | 13 | 229 | 38.24% | 72.70% |
| instruct | last | 3 | 62 | 59 | 33 | 209 | 64.71% | 77.99% |

混合剔除precision=TN/(TN+FN)，有真实正/负例混合；E正确剔除率=E的TN/(TN+FP)，二者含义不同。

| 底座 | 快照 | 来源membership | 样本数 | 正例保留recall | 负例正确剔除率 |
|---|---|---|---:|---:|---:|
| reranker | best | A | 34 | 58.82% | NA |
| reranker | best | B | 18 | 66.67% | NA |
| reranker | best | C | 87 | 41.38% | NA |
| reranker | best | D | 21 | NA | 71.43% |
| reranker | best | e_log | 21 | NA | 71.43% |
| reranker | best | e_bm25 | 110 | NA | 87.27% |
| reranker | best | e_anchor | 112 | NA | 98.21% |
| reranker | best | E | 235 | NA | 90.64% |
| reranker | last | A | 34 | 58.82% | NA |
| reranker | last | B | 18 | 66.67% | NA |
| reranker | last | C | 87 | 41.38% | NA |
| reranker | last | D | 21 | NA | 71.43% |
| reranker | last | e_log | 21 | NA | 71.43% |
| reranker | last | e_bm25 | 110 | NA | 87.27% |
| reranker | last | e_anchor | 112 | NA | 98.21% |
| reranker | last | E | 235 | NA | 90.64% |
| instruct | best | A | 34 | 38.24% | NA |
| instruct | best | B | 18 | 22.22% | NA |
| instruct | best | C | 87 | 25.29% | NA |
| instruct | best | D | 21 | NA | 76.19% |
| instruct | best | e_log | 21 | NA | 80.95% |
| instruct | best | e_bm25 | 110 | NA | 93.64% |
| instruct | best | e_anchor | 112 | NA | 100.00% |
| instruct | best | E | 235 | NA | 95.32% |
| instruct | last | A | 34 | 64.71% | NA |
| instruct | last | B | 18 | 61.11% | NA |
| instruct | last | C | 87 | 45.98% | NA |
| instruct | last | D | 21 | NA | 52.38% |
| instruct | last | e_log | 21 | NA | 57.14% |
| instruct | last | e_bm25 | 110 | NA | 83.64% |
| instruct | last | e_anchor | 112 | NA | 97.32% |
| instruct | last | E | 235 | NA | 87.66% |

来源按label_sources的membership分组，存在交叠（例如B可同时属于A，D可同时属于E）；各组不能相加当总样本数。E一行是去重并集。分组差距可能与输入可见性、任务难度、来源/项目偏差或残留噪声有关，不能直接断言都是噪声。

更高E剔除率也可能伴随更低gold保留率，应一起审视；满足单一E目标不等于满足原acc/AUC资格或端到端定位目标。

验证赛马：unqualified；Neither base satisfies val accuracy>=.80, AUC>=.85 and an evaluable E group。

- reranker：处于a/b/c未穷尽的中间或边界情况，且未达原验证资格，诚实保留结果；未自动扩数据或开test。
- instruct：处于a/b/c未穷尽的中间或边界情况，且未达原验证资格，诚实保留结果；未自动扩数据或开test。

固定配置：LoRA rank16、all-linear、lr5e-5、最多3 epoch、effective batch8、micro batch2、BF16、cutoff4096；按既有验证E下降规则早停。

D-only 仅84条（负例的2.73%），E占约97.27%；来源/项目/有名类别分布偏差仍在。训练准确率低不唯一证明数据不足，训练高验证低亦需结合噪声、输入可见性与issue分布差异分析。

test未开箱，未重跑Qwen基线，Decision-1维持取消，未生成任何新的定位对照表列。

结构化记录：`results/v5_pruner/A_v3_noise_disclosed_outcome_exploratory/assessment_report.json`；训练：`results/v5_pruner/A_v3_noise_disclosed_training_exploratory`；验证赛马：`results/v5_pruner/A_v3_noise_disclosed_race_exploratory`。

后续用户裁定（2026-10-14）：本报告作为 pre-prescription 历史条件保留。用户将原 reranker 的 train/val 23.93 个百分点差距判为过拟合，新增独立 rank8/dropout0.1 处方；上文旧操作分支判读仅反映原先阈值，后续执行按新裁定处理。原 checkpoint、预测、签注与数据不重写。

本表 gold 保留率是未校准 p_yes≥0.5 的普通二分类召回，不含 Qwen 灰区处理，也不是 high-confidence p≥0.9 保留。具体未校准、温度校准和灰区三分审计见：

- [原 reranker Gold 路由审计](../../results/v5_pruner/A_pre_regularization_reranker_gold_routes_exploratory/gold_route_report.md)
- [原 instruct E-best Gold 路由审计](../../results/v5_pruner/A_original_instruct_best_gold_routes_exploratory/gold_route_report.md)

路由审计只使用验证预测，没有实际调用灰区 Qwen 或运行定位管线。
