# 复现范围与原实验对应

本交付以论文中 CoSIL-Qwen3 与 CoSIL-SpecPrune 的 SWE-rebench 100 题对照为中心。整理工作不新增 GPU 推理或训练，不改历史预测、指标矩阵和封存 test。

## 可以独立复现什么

1. **统计复算**：从打包的原预测与离线金标计算严格 `path::qualified_name` 定位指标；从派生逐题 CSV 及分组得分重现论文统计与三幅图。该过程可在 CPU 上运行。
2. **同输入推理**：使用固定版本模型、原 LoRA、打包的干净源码与任务输入，执行共享文件阶段及两臂独立函数搜索。保存新的请求、响应、路由、源码送达与预测。非确定性推理不承诺与历史文本逐字一致。
3. **冻结 train/val 重训**：同一模型输入、标签、权重、样本顺序及优化配置。只删除机器路径类 provenance 字段；文本 SHA 和行顺序保留。选中模型的新温度/阈值应由新 val 拟合。

## 不应声称已经复现的内容

- 仅下载公开 SWE-bench 数据并不等于重建全部训练标签。训练样本还依赖历史搜索轨迹、AST 调用图、失败测试运行时覆盖、证据审阅及固定划分。`source_archive/` 保存关键生成脚本，完整重建这些上游材料需要另外准备相应证据资产；本包的可直接重训入口从最终冻结 train/val 开始。
- 本次整理不会重新训练一个完整 3 epoch，也不重跑 100 题真实模型。验证报告应区分 CPU 单元测试、历史结果重新评分和合成端到端链路测试。
- 4B 额外输入计算、两臂时延、校准样本范围和推理非确定性仍需报告。不能把主模型 token 下降写成整体 FLOPs 或时延下降。

## 来源对应

| 交付部分 | 原实现/产物 |
|---|---|
| portable training/codec/qualification | `code_v6/train_T3.py`、`training_codec.py`、`input_format.py`、`qualification.py`、`assess_T3.py` |
| 数值评分与指标 | `code_v5/judge_models.py`、`metrics.py` |
| 推理工作流、身份与渲染 | `code_qwen3_rr4_rebench100/` 及其 CoSIL 依赖 |
| 论文两臂预测 | `results/qwen3_rr4_rebench100_20261110/` |
| R2 既有函数目标提取 | `ModelLoc/experiments/dsimple_evaluation_v2_delivery/dsimple_v2/gold.py` |
| 冻结训练/验证与权重 | `results/v6_pruner/20261016/T2_dataset_v6/` 与 `T3_round1_exploratory/reranker4B/epoch_1/` |
| 论文派生数据与图表 | `papers/csrse2026_pruning/data/` 与 `scripts/analyze.py` |

整理前已验证原代码远端备份 `aef72a9c0a43d73c9baad70d1714054ffba604f6`，并单独备份更新过的 R2 原解析器 `777020b21bee37990e8ea12d562f9f9e228a3dee`。原仓库 Git 历史与所有输入文件保持原样。

## 本批改动

- 将作者机器绝对路径、授权回执和历史任务调度移出公共运行入口，改为显式参数与相对路径。
- 保留冻结 Prompt、剪枝打分、输入预算、路由阈值与评分规则；必要上游代码在 vendor 中保留原字节。
- 使用显式环境启动、干净输入准备和隔离工作进程；不自动启动 GPU 服务或联网下载。
- 将数据、模型附件和可公开代码分包，并提供 SHA256 校验、来源记录、CPU 测试及可搬迁使用说明。
- 新输出写到独立目录；若目标已存在则拒绝覆盖，避免将新结果伪装成历史结果。
