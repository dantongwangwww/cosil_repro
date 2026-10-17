# E训练权重单因素对照：方案与冻结口径

2026-10-15用户授权：使用现有train/val，仅调整E训练权重，其余条件保持；重点看gold直接剪掉比例与AUC。test继续封存。

本次为exploratory。条件预先固定为E=0.5，相比既有C阶段E=1.0；不搜索更多权重，不按看到的val成绩追加条件。两个底座各重训一次，基线直接复用完整C结果。

## 数据与唯一干预

- 固定 `data_verified_plus_B_runtime_reviewed`：train13,411、val714。train/val文件SHA与C双底座manifest逐一核对。
- E是e_log/e_bm25/e_anchor证据的并集；包括与D重叠的样本，每条只降权一次。train E共4,378条，均保留原False标签。
- E训练损失系数1→0.5；其余9,033条仍为1。没有删行、改标签、重采样、改变顺序、重新生成E或扩数据。
- reranker使用原样本数归一化，instruct使用原有效响应token数归一化；只改分子中的E系数，不改成按权重和归一化，也不把instruct改成样本平均。
- 训练正例4,473、负例8,938；降低E后，按样本计的负例有效权重变为6,749，负正权重比约1.51。这属于E降权的直接后果，不能据改善结果单独证明标签噪声的因果损失。

## 保持的训练配置

| 项目 | reranker | instruct |
|---|---|---|
| 本地底座 | Qwen3-Reranker-0.6B | Qwen2.5-0.5B-Instruct |
| LoRA rank/dropout | 8 / 0.1 | 16 / 0.0 |
| alpha / target | 32 / all-linear | 32 / all-linear |
| lr / 最大epoch / seed | 5e-5 / 3 / 0 | 5e-5 / 3 / 0 |
| 有效batch / microbatch | 8 / 2 | 8 / 2 |
| dtype / cutoff | BF16 / 4096 | BF16 / 4096 |
| issue / function字符 | 2,000 / 1,500 | 2,000 / 1,500 |
| 优化器 / weight decay / clipping | 原AdamW / 0 / 1.0 | 原AdamW / 0 / 1.0 |

沿用原loss定义、原codec、原LoRA范围、epoch顺序与原验证选模/早停规则。reranker按val accuracy/AUC/E排序取best；instruct沿用资格/E/accuracy/AUC顺序。E剔除率下降触发原早停，实际epoch数若不同如实披露；因此另报共同完成的同epoch对照。

新namespace单独保存模型、日志、每epoch概率和train体检，既有C代码、checkpoint、预测与报告保持。库版本与本地模型指纹必须匹配C。GPU可用显存至少12GiB时最多两卡并行，不控制其他任务、vLLM或CSRSE；硬件调度差异仅作运行背景，不作耗时因果比较。

## 主要指标与判读

1. 原始未校准VAL AUC，越高越好。
2. gold A/B正例在固定low=0.6/high=0.9的直剪率，越低越好：p≤0.6直剪、p≥0.9直留，其余灰区；三部分分别报告。没有运行灰区Qwen。
3. 同时报告train/val accuracy、原p≥0.5 gold召回、E正确剔除率、混合集剔除precision，以及旧Lite363/新Verified351子集。
4. 各自原规则best为主表，同epoch为辅助；按issue聚类配对bootstrap2,000次、seed20261015，区间不当作独立test确认。

若gold直剪减少而AUC不提高，优先解释为概率/决策倾向改变，不能声称排序能力已改善。两者改善可支持E训练信号有实质影响；仍不能量化噪声独立伤害，因为干净与错误E同时降权，且有效类别权重随之变化。单seed与同val用于选模的局限必须保留。

## 边界与产物

本轮不做校准、阈值搜索、赢家部署、test开箱、定位金丝雀或全量定位，即使验证数值达标也不自动解锁test。维持原accuracy≥0.80且AUC≥0.85的资格口径，不把分类验证成绩加入定位矩阵。

- 执行协议：`results/v5_pruner/E_weight05_ablation_authorization_exploratory/protocol.json`
- 训练与对照：`results/v5_pruner/E_weight05_C_frozen_trainval_exploratory/`
- 最终报告：`docs/v5-pruner/实验报告_v5_E权重单因素对照.md`
- 配对概率与gold逐条路由变化：运行目录的 `comparison/`。

启动前完成E=1损失/梯度与原实现等价、E=.5仅缩放E梯度、instruct响应token归一化、非整microbatch累积、原helper AST一致、baseline指标复算和test拒绝检查。冻结源代码、数据、基线预测、旧矩阵与检查收据SHA，再启动真实训练。
