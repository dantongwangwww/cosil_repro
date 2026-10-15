# v5 B线：runtime-covered exploratory 双底座

本报告来自实际B双底座训练与验证；test仍封存，没有新增端到端定位准确率。

数据：正例1542，负例3076，E 2992；train/val/test封存计数为3916/363/339。test计数来自封存元数据，未解码test行。

原A/v3的3/30错误签注不改。本轮B的30条训练分层审阅与删除清单以独立B签注/派生记录为准；审阅不能证明总体无噪声。

B审阅记录：`{"passed": false, "historical_threshold_only": true, "review_complete": true, "noise_disclosure_policy": true, "status": "reviewed_full30_noise_disclosed", "review_path": "/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v3_runtime_filtered_reviewed/human_review_codex_reviewed.jsonl", "review_sha256": "7470ac520db723560296ebc92a7e7473bf9d1b7e798b7c857602f415af770071", "reviewed_records": 30, "label_errors": 8, "observed_stratified_fraction": 0.26666666666666666, "reviewer_kind": "Codex/机械证据审阅; not a human signature", "family_counts": {"e_log": 10, "e_bm25": 10, "e_anchor": 10}, "interpretation": "Full original stratified sample retained. Removing confirmed errors does not make remaining samples random or certify zero remaining noise."}`。

| 底座 | best epoch | train accuracy | val accuracy | val AUC | val E正确剔除率 | 完成epoch | 判读 |
|---|---:|---:|---:|---:|---:|---:|---|
| reranker | 1 | 95.15% | 78.79% | 0.8776210641349634 | 82.13% | 3 | intermediate_unqualified |
| instruct | 3 | 99.00% | 78.79% | 0.866778225531043 | 90.64% | 3 | intermediate_unqualified |

train/val按同一个best checkpoint对照；train来自全部实际TRAIN样本eval推理，未用loss替代accuracy。

| 底座 | last epoch | last train accuracy | last val accuracy | last val AUC |
|---|---:|---:|---:|---:|
| reranker | 3 | 99.00% | 78.24% | 0.8737620381121508 |
| instruct | 3 | 99.00% | 78.79% | 0.866778225531043 |

验证赛马：unqualified；Neither base satisfies val accuracy>=.80, AUC>=.85 and an evaluable E group。

- reranker：未达原验证资格且处于未穷尽的中间/边界分支；不擅自扩数或开test。
- instruct：未达原验证资格且处于未穷尽的中间/边界分支；不擅自扩数或开test。

按kind保持与相应A条件一致：reranker rank8/dropout0.1/alpha32/val accuracy峰值，对照post-prescription A；instruct rank16/dropout0/alpha32/原E-best，对照原A instruct。其余all-linear、lr5e-5、最多3epoch、batch8/micro2、BF16、cutoff4096及E下降早停相同；本实验仅使用GPU2，GPU3不由本实验占用。

运行时覆盖不完整时，未观察到调用不能推导无关；标签仍受测试覆盖、输入截断、静态/运行时遗漏及来源分布影响。跨版总体指标受样本变化影响，应配合同val pair对照。

test未开箱、Qwen基线未重跑、Decision-1取消，未新增定位表列。

结构化结果：`results/v5_pruner/B_runtime_reviewed_regularized_exploratory/outcome/assessment_report.json`。

## 完成后的审阅与指标补充

B新30条是 train-only、每族10条的分层证据审阅；8条属于保守排除的不安全E：7条有源码关系证据，另1条保留条件visitor执行风险。不能写成“总体26.67%噪声”，也不能称8条全部已证明标签错误。原始30条签注与raw归档保留，仅在B reviewed train中精确删除8个身份，val/test与B raw相比保持原字节；A与B的val成员有变化，不能将“同为363行”理解为同一批函数pair。

| 底座/角色 | epoch | TP | FN | FP | TN | raw gold保留 | 混合剔除precision | train-val差距(pp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| reranker/best | 1 | 90 | 31 | 46 | 196 | 30/34=88.24% | 86.34% | 16.3602 |
| reranker/last | 3 | 66 | 55 | 24 | 218 | 26/34=76.47% | 79.85% | 20.7672 |
| instruct/best | 3 | 69 | 52 | 25 | 217 | 23/34=67.65% | 80.67% | 20.2162 |
| instruct/last | 3 | 69 | 52 | 25 | 217 | 23/34=67.65% | 80.67% | 20.2162 |

| 底座/角色 | 来源membership | 样本数 | 正例保留recall | 负例正确剔除 |
|---|---|---:|---:|---:|
| reranker/best | A | 34 | 88.24% | NA |
| reranker/best | B | 18 | 100.00% | NA |
| reranker/best | C | 87 | 68.97% | NA |
| reranker/best | D | 17 | NA | 35.29% |
| reranker/best | e_log | 11 | NA | 18.18% |
| reranker/best | e_bm25 | 114 | NA | 71.93% |
| reranker/best | e_anchor | 115 | NA | 95.65% |
| reranker/best | E | 235 | NA | 82.13% |
| reranker/last | A | 34 | 76.47% | NA |
| reranker/last | B | 18 | 94.44% | NA |
| reranker/last | C | 87 | 45.98% | NA |
| reranker/last | D | 17 | NA | 64.71% |
| reranker/last | e_log | 11 | NA | 36.36% |
| reranker/last | e_bm25 | 114 | NA | 86.84% |
| reranker/last | e_anchor | 115 | NA | 100.00% |
| reranker/last | E | 235 | NA | 91.49% |
| instruct/best | A | 34 | 67.65% | NA |
| instruct/best | B | 18 | 66.67% | NA |
| instruct/best | C | 87 | 52.87% | NA |
| instruct/best | D | 17 | NA | 58.82% |
| instruct/best | e_log | 11 | NA | 45.45% |
| instruct/best | e_bm25 | 114 | NA | 84.21% |
| instruct/best | e_anchor | 115 | NA | 100.00% |
| instruct/best | E | 235 | NA | 90.64% |
| instruct/last | A | 34 | 67.65% | NA |
| instruct/last | B | 18 | 66.67% | NA |
| instruct/last | C | 87 | 52.87% | NA |
| instruct/last | D | 17 | NA | 58.82% |
| instruct/last | e_log | 11 | NA | 45.45% |
| instruct/last | e_bm25 | 114 | NA | 84.21% |
| instruct/last | e_anchor | 115 | NA | 100.00% |
| instruct/last | E | 235 | NA | 90.64% |

来源membership可重叠，不能相加；E行是去重并集。函数pair与issue定位任务是不同统计单位。本表全部gold recall使用未校准p≥0.5，不含Qwen灰区处理。

reranker的epoch1/2 accuracy并列，epoch1 AUC更高，按冻结峰值规则选1；epoch3 E剔除率虽更高，accuracy较低，保留为last诊断。instruct沿原qualified/E-best规则选3，best与last相同，真实train评估文件复用。两底座均为286/363=78.7879%，距离acc≥0.80至少还差5个正确验证pair；AUC通过不能替代accuracy门。实际赛马无合格胜者。

[reranker选峰三分路由诊断](../../results/v5_pruner/B_reranker_selected_peak_gold_routes_exploratory/gold_route_report.md)与普通二分类分开：raw L=.6/H=.9时34个gold为28直留、4直剪、2灰；val-safety校准候选为5直留、0直剪、29灰。灰区未调用Qwen，候选阈值没有部署；不能把88.24%或“验证gold零直剪”称为最终hybrid/生产安全结果。

本JSON中的旧diagnosis分支名称保留初始(a)/(b)阈值的运行记录，不能据intermediate_unqualified推翻用户后来对大拟合差距与扩数据的裁定。原A处方峰值<0.80已触发用户批准的扩挖路线；后续C根据独立新官方/OOD来源与授权构建Verified＋B数据。当前B仅为原Lite300范围的独立runtime过滤对照，不包含Verified新题，不冒称扩后实验已完成。

最终真实postflight见 `results/v5_pruner/B_actual_training_postflight_audit.json`：30检查通过，包括6个val预测文件、三个实际train评估文件、完整source/code绑定、双次自然空闲GPU preflight及封存test字节。两训练子进程均正常退出；本实验未停止或修改他人的进程，GPU3未由本实验加载模型。
