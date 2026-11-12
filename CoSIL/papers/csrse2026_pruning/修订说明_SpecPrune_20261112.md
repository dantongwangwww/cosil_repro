# SpecPrune名称与剪枝方法表述修订

日期：2026-11-12（UTC+8）。修订前33个已发布文本文件全部与GitHub提交 `032d7221f5e8c6f8587bd2679ff230458607dc66` 的Git blob SHA一致，旧版可由该提交恢复。

1. 题目统一为《面向代码定位智能体的函数剪枝方法与可靠性评测》，英文为 *Function Pruning for Code Localization Agents: Design and Reliability Evaluation*。
2. 方法名统一为SpecPrune（Specialized Function Pruning）；图表展示组名使用CoSIL-SpecPrune。历史原始运行标识baseline/hybrid_safe不改。
3. 摘要第二句明确“函数相关性剪枝判断”的双重作用；4B组件统一称“相关性剪枝判别器”或“剪枝模型”。
4. 正文以专项训练的剪枝模型为方法重点，解释与CoSIL基线的区别：基线同一底座承担搜索与提示式剪枝判断，本方法训练独立的函数相关性判别器并保留不确定性回退。CoSIL既有搜索模型不是本文新增方法。
5. 比较结论依据实测：主模型判断token减少38.02%，两组函数Hit@5均49/92。专项训练被表述为任务针对性，不直接声称定位准确率更好，也不把集成对照当作训练效果的单独消融。

训练数据/参数、17篇引用、四图三表、六项函数定位指标、局限性中的小模型输入开销保留。没有新增推理、训练或API调用，没有改动实验原始数据、历史报告、对照矩阵或封存test。论文、图和Word均从更新后的源码重建；页数及哈希以validation.json和validation_chinese.json为准。
