# 交付验证记录（2026-11-13）

此次操作是代码与材料整理，不是新一轮模型实验。没有启动 GPU 服务、重新训练、调用模型 API 或读取封存 test。

| 验证项目 | 实际结果 |
|---|---|
| 目录搬迁 | 完整目录复制到原仓库之外的 `/tmp`，从新目录执行；没有依赖原代码目录导入 |
| 工程单元/集成测试 | 37 项通过，无跳过；包含真实 torch CPU 损失/梯度、实际 bwrap 合成双臂链路与打包目录回归 |
| 论文统计测试 | 7 项通过，无跳过 |
| CLI、资产验证、图表与重新评分 | 15 条命令均退出 0；包括全部公开模块 `--help` |
| editable 安装 | 使用 `--no-index --no-build-isolation --no-deps` 成功构建并安装至独立临时前缀 |
| 原100题预测重新评分 | file 分母100、函数分母92；全部点估计与历史一致，CI最大差异 <3e-16 |
| 既有训练资产 | 8,556 train + 487 val 的文本SHA、顺序、split、权重与真实tokenizer预算通过 |
| 既有 LoRA 与底座 | adapter/config 与固定基座核心文件 SHA 核验通过；未载入模型执行 forward |
| 原/迁移输入渲染 | 固定前20题，各选第一个可渲染函数，完整返回内容20/20逐字一致；10例含邻居，裁剪另有单元测试 |
| 原论文数据保护 | 104 份历史来源文件重新核对SHA，0处变化 |
| 原 CoSIL Git | HEAD 保持 `86dacd7d18c1198ff20da64595b7f1222d93281e`；发布使用独立 GitHub 快照 |

主要执行环境：Python 3.11.17，torch 2.13.0（CPU测试），transformers 5.18.0，peft 0.21.2；R2 AST 使用 Python 3.12。固定部署温度不重新计算。不同 Python 浮点求和版本可能产生极微小的统计/重拟合差异。

打包校验曾发现通用目录排除规则误跳过任务源码内部的 `models/`、`build/`、`dist/`。已将排除规则限于包的顶层缓存目录，并添加回归测试和冻结清单与打包清单的一致性检查；正式资产包保留这些合法源码。原始任务文件和历史实验没有变化。

## 验证命令

在完整包根目录，已安装依赖的环境中运行：

```bash
CUDA_VISIBLE_DEVICES='' python -m unittest discover -s tests -v
python -m unittest discover -s paper_results/tests -v
python -m specprune.training --validate-only
python -m specprune.scoring --validate-only
python -m specprune.runner dry-run --out /path/to/new/smoke
python -m specprune.evaluation \
  --predictions assets/evaluation/predictions.json \
  --gold assets/evaluation/gold.json \
  --inventory assets/evaluation/inventory.json \
  --output /path/to/new/evaluation
python paper_results/scripts/analyze.py --output /path/to/new/figures
python -m specprune.verify --require-assets
```

合成链路的模型回复来自明确标记的 stub；它证明组件接线和隔离可运行，不产生论文实验分数。没有重训或真实新推理，因此不能保证另一台机器生成逐字相同的回答或逐位相同的新权重。

细项回执：`provenance/training_scoring_cpu_checks.json`、`training_assets_validation.json`、`training_tokenizer_validation.json`、`runtime_input_equivalence.json`；完整交付 SHA 在 `provenance/artifact_manifest.json`。
