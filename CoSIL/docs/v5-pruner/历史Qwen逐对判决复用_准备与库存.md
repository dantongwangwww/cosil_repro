本次已完成旧Qwen三臂真实判决的只读复用库存。主基线为off，on与shuffled分别展示；按issue＋base函数身份匹配，不按结果行号拼接。范围仅为已冻结A_noise与B_runtime_reviewed的train/val：244个有样本的issue、4,393个并集函数pair，共提取1,304次真实历史响应，没有重新调用Qwen或小裁判，没有开启封存test、改训练数据或新增Excel实验列。

函数身份使用原miner的resolve_query/log_evidence，原native parse_verdict解析响应，同时要求成功源码fetch之后、prune之前存在真实pruner模型调用。历史事件本身没有base_commit字段，因此复用依据为冻结base graph、精确源码头、原run/case与候选文件一致性；不能称为日志原生记录commit。244题的graph与三臂事件/最终case均固定SHA，读取后再次核对未变。

| 臂 | 不同历史pair | 真实响应次数 | 有重复响应的pair | 单pair最多次数 | 相反判决pair |
|---|---:|---:|---:|---:|---:|
| off | 257 | 424 | 90 | 10 | 0 |
| on | 277 | 445 | 87 | 10 | 0 |
| shuffled | 266 | 435 | 84 | 10 | 0 |

所有重复响应均保留。本次选中pair在各臂内部没有相反判决或无效/未核证响应；重复相同答案只算一个pair，不提高独立样本数。程序仍严格保留矛盾、无效、缺失三种NA状态，不取第一条/最后一条/多数票或对标签有利的答案，缺失不补False。8个守卫检查已通过，包含缺失NA、矛盾NA、混入无效响应、拒绝test路径及源码身份歧义拒绝。

| 条件／集合 | 臂 | 总pair | 有真实共识pair | 覆盖率 | 缺失NA | 共识子集accuracy | 共识子集剔除precision |
|---|---|---:|---:|---:|---:|---:|---:|
| A_noise:train | off | 3921 | 216 | 5.51% | 3705 | 53.24% | 21.74% |
| A_noise:train | on | 3921 | 233 | 5.94% | 3688 | 52.79% | 22.22% |
| A_noise:train | shuffled | 3921 | 227 | 5.79% | 3694 | 54.19% | 19.23% |
| A_noise:val | off | 363 | 41 | 11.29% | 322 | 63.41% | 14.29% |
| A_noise:val | on | 363 | 44 | 12.12% | 319 | 59.09% | 0.00% |
| A_noise:val | shuffled | 363 | 39 | 10.74% | 324 | 74.36% | 50.00% |
| B_runtime_reviewed:train | off | 3916 | 195 | 4.98% | 3721 | 58.46% | 20.00% |
| B_runtime_reviewed:train | on | 3916 | 213 | 5.44% | 3703 | 57.28% | 20.75% |
| B_runtime_reviewed:train | shuffled | 3916 | 209 | 5.34% | 3707 | 57.89% | 16.00% |
| B_runtime_reviewed:val | off | 363 | 37 | 10.19% | 326 | 70.27% | 14.29% |
| B_runtime_reviewed:val | on | 363 | 39 | 10.74% | 324 | 66.67% | 0.00% |
| B_runtime_reviewed:val | shuffled | 363 | 32 | 8.82% | 331 | 90.62% | 50.00% |

**这些是同pair已观测子集上的相关性判决指标。**A/B标签含B或e_log时部分源自历史Qwen结果筛选，因此不能作为独立考试；旧Qwen看到完整issue＋提取源码，小裁判接收2,000/1,500字符截断输入，输入也不完全相同。不同臂的已观测pair子集不同，不能直接依据本表的高低给模型或注释排名。此表也不产生新的issue定位Top5成绩。

主off在A val只有41/363个pair有历史共识（11.29%），B val只有37/363（10.19%）。其余不能当作Qwen错误，也不能用假答案补全全val比较或灰区。A_noise train/val中带B/e_log来源membership分别227/39个pair，B_runtime_reviewed分别192/29个；这只是标签选择依赖的提示，不代表独立样本或自然候选分布。

另以原A rank16 reranker已经完成的epoch3／best保存val概率验证离线路由读取脚本。该诊断直接重算363条概率，确认与原training_curves中的val指标完全一致，固定未校准阈值low=0.6/high=0.9；不重新选模型、阈值或推理。p≤low直剪、p≥high直留，其余灰区。它属于旧rank16诊断，不能替代正在跑的rank8处方结果。

| 原A rank16保存概率诊断 | 直留 | 直剪 | 灰区 |
|---|---:|---:|---:|
| 全val363 | 53 | 288 | 22 |
| 机械gold（A/B来源正例）34 | 15 | 14 | 5 |

其中22个灰区在历史off里只有5个同pair真实共识，17个仍为NA。没有把这些灰区默认判正确，也没有冒充新hybrid管线已执行。后续rank8/B对照亦只能从相应完成checkpoint的已存val概率生成直留/直剪/灰分类；灰区历史Qwen不足时继续NA，若要端到端结果必须另行真实执行管线。

库存入口：[prepare_historical_qwen_pair_reuse.py](../../code_v5/prepare_historical_qwen_pair_reuse.py)。不可覆盖原库存，应使用新的输出目录。保存概率诊断入口：[analyze_historical_qwen_saved_val.py](../../code_v5/analyze_historical_qwen_saved_val.py)，要求训练summary、完整checkpoint、manifest、原val seal与实存val概率一致；仅读取完成best的val_epoch文件，硬拒test输入路径。

数据与证据：

- [库存报告](../../results/v5_pruner/historical_qwen_pair_reuse_v1/inventory_report.json)，SHA256 `5e2748f40004c91def5b5c8f40d9bf358901a1f67bb8f951232678b5e46d1746`。
- [实际逐次响应](../../results/v5_pruner/historical_qwen_pair_reuse_v1/actual_historical_observations.jsonl)、[逐条件pair库存](../../results/v5_pruner/historical_qwen_pair_reuse_v1/selected_pair_inventory.jsonl)、[源码身份未解析事件](../../results/v5_pruner/historical_qwen_pair_reuse_v1/unresolved_historical_events.jsonl)、[冻结来源SHA](../../results/v5_pruner/historical_qwen_pair_reuse_v1/source_fingerprints.json)。
- [原A rank16保存概率诊断](../../results/v5_pruner/historical_qwen_pair_reuse_A_original_r16_val_diagnostic/saved_val_observation_report.json)，SHA256 `39e2391d229aa1aec5ef099c45472ec62a0c0fe08ea832d70ff8f5306cd6d57e`。
