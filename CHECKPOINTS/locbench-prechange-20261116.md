# LocBench 实验开始前的恢复检查点

本检查点继承用户仓库提交 `2af251c5c01d16e92db3b707d0caa471cff962e7`。在新增 LocBench 数据适配与评测代码前，核对当前 CoSIL 控制器、SFPruner 源码/配置/原始工具 API 模块、依赖准备器、合成测试与既有说明均可按原字节恢复。

原快照已完整覆盖144个当前文件。本次只补归档两个现有运行指纹 JSON：`papers/SFPruner/provenance/main_model_files.json` 和 `model_files.json`。其内容为模型 ID、固定 revision、所需文件 SHA 与尺寸，没有模型权重。所有146项文件的本地 SHA256、Git blob SHA 和模式记录于同名 JSON。没有修改算法、模型参数、旧源码或历史报告。

此提交仅为实验前的代码/文档恢复点，不包含 LocBench 数据、新实验代码、候选或金标、结果/日志、模型权重、凭据、封存测试或论文，不代表任何新模型实验已经执行。前置、执行和最终结果旧分支及 CoSIL 原上游 Git 均保留。
