# CHECKPOINT: multiswe-java128-closure-locbench-prechange-20261117

## 本快照目的

Java128 三模型实验全链路闭合后的发布快照，同时作为下一批实验（LocAgent 在 LocBench 全量560题上的定位实验）新增代码前的基线（AGENTS.md 要求：大改/新增实验代码前先发布远端可恢复点）。

## Java128 闭合状态（发布时已核验）

- `results/multiswe_java_qwen3_20261117_v2/run/completion.json`: status=COMPLETE，128组/384臂终态（complete 320 / partial 55 / worker_failed 9，全部保留分母）。
- 原解析统计、签名格式规范化v2评价、三项独立审计（原解析指标 / 规范化v2指标 / 最终血缘）全部 PASS，errors=[]。
- 自有主模型与剪枝器服务有序退出（SIGTERM、无 forced kill），GPU 上无本次实验进程；他人任务未触碰。
- 保护资产核验：`protected_assets_midrun_checkpoint.json` 中 841 条 SHA256 逐一复算一致；5 条封存 test 仅 stat 比对（bytes/mtime_ns/inode 一致），内容未打开。
- 最终交付文档（聚合口径）已加入本快照：三模型总览（规范化v2）、原解析与规范化v2同题对照、时间与token开销（规范化v2）。逐题 CSV 与逐题错例明细按发布边界不上传。
- 新增派生视图代码 `CoSIL/map5_derived_view_20261117.py`：按用户要求补算 MAP@5（离线、零模型调用），并按用户指定口径重算方法级全指标（分母128、失败与11题方法NA计为未命中）。其输出（JSON）留在本地 results 派生目录，不上传。

## 下一批实验计划（尚未实现代码）

LocAgent 在官方 LocBench V1（`czlll/Loc-Bench_V1`，revision `c44cf3b74e07ca642cec841b471a9939907c12a7`）全量560题上的定位实验：

- 协议沿用 Java128 的 LocAgent 臂：原生3工具+finish、2样本MRR、temperature=1、top_p=0.8、repetition_penalty=1.05、每样本900秒、21请求硬上限、整臂2000秒；主模型 Qwen3-8B（同 revision），服务带 `--enable-auto-tool-choice --tool-call-parser hermes`。
- 复用既有基础：LocBench560 的冻结分配与165仓源码缓存（`results/locbench_qwen3_sfpruner_20261116`）、LocAgent 的 Python 原生管线前例（`LocAgent/experiments/qwen3_rebench280_unified_v2_20261115`）、GraphLocator 本地 LocBench 数据与 gold 参照。
- 不训练、不生成修复补丁、不运行修复测试；不修改论文/历史矩阵；封存 test 保持封存。
