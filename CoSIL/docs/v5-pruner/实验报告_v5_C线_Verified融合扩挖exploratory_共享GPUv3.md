# v5 C线：Verified＋B runtime融合扩挖 exploratory 双底座

本报告来自实际C融合数据双底座训练与验证；test仍封存，没有新增端到端定位准确率。

本轮 exploratory_quality_gate_passed 表示新的授权质量、切分、去重、泄漏和来源完整性通过；formal_data_gate_passed 保持 false。原 v3 审阅失败不追认通过，8000数量门仍按用户规定待重定标。

数据：正例4950，负例9892，E 5047；train/val/test封存计数为13411/714/717。test计数来自封存元数据，未解码test行。

原A/v3的3/30错误签注不改。本轮C的30条训练分层审阅与精确不安全E删除清单以独立C签注/派生记录为准；保守排除并非全部已证实错误，分层抽检比例也不是总体噪声率。

C审阅记录：`{"review_complete": true, "passed": false, "historical_threshold_only_not_current_veto": true, "reviewed_records": 30, "label_errors": 8, "unsafe_negative_count": 8, "classification_counts": {"retained_limited_evidence": 22, "conditional_risk": 2, "confirmed_source_relation": 6}, "observed_stratified_conservative_exclusion_fraction": 0.26666666666666666, "family_counts": {"e_log": 10, "e_bm25": 10, "e_anchor": 10}, "review_sha256": "72b2bc46412110281ede8d8c4bbd28927f1fa14589488fdcb7e32e132734978b", "reviewer_kind": "Codex source/runtime evidence review, not human signature", "human_signature": false, "interpretation": "Full30 family-stratified conservative exclusion observation, not population noise, zero-noise certification or 30 certain causal errors. Conditional risks remain explicitly distinct."}`。

| 底座 | best epoch | train accuracy | val accuracy | val AUC | val E正确剔除率 | 完成epoch | 判读 |
|---|---:|---:|---:|---:|---:|---:|---|
| reranker | 2 | 98.75% | 77.87% | 0.8463473624744016 | 88.92% | 3 | intermediate_unqualified |
| instruct | 3 | 99.36% | 79.69% | 0.8205944142362828 | 94.60% | 3 | intermediate_unqualified |

train/val按同一个best checkpoint对照；train来自全部实际TRAIN样本eval推理，未用loss替代accuracy。

| 底座 | last epoch | last train accuracy | last val accuracy | last val AUC |
|---|---:|---:|---:|---:|
| reranker | 3 | 99.40% | 72.97% | 0.7836002047877975 |
| instruct | 3 | 99.36% | 79.69% | 0.8205944142362828 |

验证赛马：unqualified；Neither base satisfies val accuracy>=.80, AUC>=.85 and an evaluable E group。

- reranker：未达原验证资格且处于未穷尽的中间/边界分支；不擅自扩数或开test。
- instruct：未达原验证资格且处于未穷尽的中间/边界分支；不擅自扩数或开test。

按kind保持与相应A条件一致：reranker rank8/dropout0.1/alpha32/val accuracy峰值，对照post-prescription A；instruct rank16/dropout0/alpha32/原E-best，对照原A instruct。其余all-linear、lr5e-5、最多3epoch、batch8/micro2、BF16、cutoff4096及E下降早停相同。

资源按用户最新裁定从GPU0..3中选择至少12GiB空闲显存的单卡，允许与既有任务并行共用；双底座仍顺序运行，不预留其他卡，不因非本child上下文停止训练。实际各底座使用的物理GPU为 {"reranker": 1, "instruct": 1}；完整CSV/XML进程、显存/利用率与加载前余量复查均落盘，不停止或修改vLLM、CSRSE及其他人的进程。共享GPU会影响训练与推理耗时，不能把本轮与B独占条件的耗时差解释为模型或数据的因果效果。

运行时覆盖不完整时，未观察到调用不能推导无关；标签仍受测试覆盖、输入截断、静态/运行时遗漏及来源分布影响。跨版总体指标受样本变化影响，应配合同val pair对照。

test未开箱、Qwen基线未重跑、Decision-1取消，未新增定位表列。

结构化结果：`results/v5_pruner/C_Verified_plus_B_runtime_resources_v3_exploratory/outcome/assessment_report.json`。
