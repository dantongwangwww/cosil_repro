# SpecPrune：面向代码定位智能体的函数剪枝方法与可靠性评测

这是论文实验的独立代码与复现材料包。SpecPrune 在 CoSIL 搜索智能体取得候选函数后，以经过相关性训练的 **Qwen3-Reranker-4B + LoRA** 判断函数：高置信无关时剪掉，高置信相关时保留，灰区继续交由 CoSIL 原判断流程处理。CoSIL 使用 **Qwen3-8B**。类请求保留原处理路径。

本目录同时提供**训练代码、推理集成、评测器、论文统计代码、冻结配置及使用说明**。本地完整交付还附有训练/验证集和论文实际使用的 LoRA 权重；完整 4B/8B 底座单独下载。仅有 LoRA 权重不能独立运行。

## 从哪里开始

| 需求 | 入口 | GPU / 下载 |
|---|---|---|
| 检查代码包与资产是否齐全 | `python -m specprune.doctor`、`verify` | 不需要 |
| 重算论文表格和图 | `paper_results/scripts/analyze.py` | CPU；仅绘图依赖 |
| 从原始预测重新评测 100 题 | `python -m specprune.evaluation` | CPU；需本地评测资产 |
| 验证搜索→剪枝→排名工程链路 | `python -m specprune.runner dry-run` | CPU；合成模型响应，不代表真实推理 |
| 使用训练好的 SpecPrune 定位 | `runner judge-server` 与 `runner run-pair` | 本地 4B 判别器和 Qwen3-8B 服务 |
| 重新训练剪枝模型 | `python -m specprune.training` | GPU；冻结 train/val 和 4B 底座 |
| 重建新任务的源码索引与金标 | `prepare_runtime`、隔离的 `gold` | CPU、Git、Python 3.12 |

详细操作：[训练说明](docs/TRAINING.md) · [运行说明](docs/RUNTIME.md) · [评测说明](docs/EVALUATION.md) · [交付范围与历史对应](docs/REPRODUCIBILITY.md)。

整理验证：整个目录搬到原仓库之外后，36 项工程测试和 7 项论文统计测试通过；20 题剪枝输入与原实现逐字一致；原 100 题指标重算一致。详情见 [VALIDATION.md](docs/VALIDATION.md)。这不替代一次新的 GPU 训练或真实推理实验。

## 1. 环境与完整性

Linux 是真实推理环境；标准库统计和单元测试也可在其他平台运行。训练和推理工作进程使用 Python 3.11；源码索引与 R2 金标解析另需 **Python 3.12**。推理隔离需要 `bubblewrap` (`bwrap`) 及可用的 Linux 用户命名空间。入口不会自动启动模型、占用 GPU 或请求付费 API。

```bash
cd SpecPrune
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e . --no-deps
python -m specprune.doctor
python -m specprune.verify
```

**使用整个目录并采用 editable 安装。** 配置、vendor、数据和模型在目录中以相对路径关联；不要只复制 `specprune/` 子目录或只安装一个不含附件的 wheel。

完整本地包可进一步检查所有附件：

```bash
python -m specprune.verify --require-assets
python -m pip install -r requirements-agent.txt
python -m unittest discover -s tests -v
python -m unittest discover -s paper_results/tests -v
```

完整运行链路测试需要 agent 导入依赖及 `bwrap`；纯统计复算不需要这些依赖。训练损失测试在安装 PyTorch 后运行，未安装时明确标记跳过。不要把跳过测试写成已通过。

GitHub 只发布代码、文档、冻结配置和派生统计，不发布权重、训练/验证原始样本、离线金标或实验日志。因此**GitHub 克隆不等于完整资产包**。需要训练或重新评分时，将交付的 `SpecPrune-assets.tar.gz` 在代码目录的父目录解压；其中只补充 `SpecPrune/assets/` 和 `SpecPrune/checkpoints/`。包内不包含封存 test，也没有任何 API 密钥。打包与资产校验命令见下文。

## 2. 最快复核论文结果：仅 CPU

```bash
python -m pip install -r requirements-analysis.txt
python paper_results/scripts/analyze.py --output outputs/paper_analysis
```

输出为三幅统计图（PDF/PNG）、阈值回放 CSV 和选定阈值 JSON。输入来自 `paper_results/data/`；不会回读原服务器上的历史目录，不会改写历史结果。

若完整资产已解压，可从两臂逐题原始预测重新计算定位指标及置信区间：

```bash
python -m specprune.evaluation \
  --predictions assets/evaluation/predictions.json \
  --gold assets/evaluation/gold.json \
  --inventory assets/evaluation/inventory.json \
  --output outputs/evaluation
```

原实验共 100 题、100 个仓库，其中 **92 题具有完整且非空的既有函数目标**。1 题因目录上下文超限失败，仍保留在适用指标的分母中。应得到：

| 指标 | CoSIL-Qwen3 基线 | CoSIL + SpecPrune |
|---|---:|---:|
| 函数 Hit@1 | 36/92 | 37/92 |
| 函数 Hit@3 | 47/92 | 48/92 |
| 函数 Hit@5 | 49/92 | 49/92 |
| 主模型 token，含等价文件阶段成本 | 8,313,354 | 7,927,200 |
| 主模型判断相关 token | 964,727 | 597,941 |

主模型 token 降低约 4.65%，判断相关 token 降低约 38.02%；剪枝模型另外处理 764,211 个输入 token。完整配对 99 题的平均时延约 34.89s → 40.07s。函数 Hit@5 差值为 0，配对 95% CI 约 −3.26pp～+3.26pp，精确 McNemar p=1；不据此宣称两臂等效。逐题指标、资源与行为证据保留在派生数据中。

## 3. 使用论文权重

```bash
# 先安装与本机 CUDA/驱动匹配的 PyTorch，再安装其余固定版本。
python -m pip install -r requirements-model.txt -r requirements-agent.txt
python scripts/download_models.py --model all --output models
```

模型下载固定到以下版本，不使用浮动的 `main`：

| 用途 | 模型 | revision |
|---|---|---|
| CoSIL | Qwen/Qwen3-8B | `b968826d9c46dd6066d109eabc6255188de91218` |
| 剪枝底座 | Qwen/Qwen3-Reranker-4B | `22e683669bc0f0bd69640a1354a6d0aebcfeede5` |

论文 LoRA 在 `checkpoints/specprune_epoch1/`，权重文件 SHA256 为 `903cf41341d5455381d8b713e6505b696be62d4a7d9a2a386421642985c30736`。加载时显式传入本机底座目录，不依赖原 `adapter_config.json` 中的作者机器路径。其余两个 tokenizer 附件只用于复现输入预算，不代表额外运行两个模型。

先按 [运行说明](docs/RUNTIME.md) 做 CPU dry-run，再显式启动本机 Qwen3-8B 服务和剪枝评分服务。运行入口将推理工作进程与训练/验证、评测金标隔离；隔离不可用时停止，不自动退化为可读取答案的运行方式。

Qwen3-8B 的 vLLM 服务建议放在独立 Python 环境，使用 `requirements-service.txt` 记录的版本。`requirements-model.txt` 是训练/剪枝评分依赖，不会自动安装或启动 vLLM。可先运行 `python scripts/verify_models.py --agent-dir models/Qwen3-8B --pruner-dir models/Qwen3-Reranker-4B` 核对本地模型文件。

部署固定温度 **2.9846201034621833**，低阈值 **0.12947567721292427**，高阈值 **0.9**。完整输入为 issue ≤8000 字符、函数 ≤8192 字符、每方向最多 16 个调用邻居摘要，并遵守冻结 token 预算。`configs/deployment.json` 是唯一部署参数来源。

服务就绪后，完整 100 题实验及离线评分可按以下入口串联；具体参数见 [完整运行命令](docs/EVALUATION.md#四新运行的完整闭环run--collect--evaluation)：

```text
python -m specprune.runner run-manifest ...   # 两臂逐题推理；新输出目录
python -m specprune.collect ...               # 保留失败/未运行及原始排名
python -m specprune.evaluation ...            # 推理结束后才读取离线金标
```

## 4. 重训剪枝模型

先验证资产，不启动训练：

```bash
python -m specprune.training --validate-only
```

显式使用某张空闲 GPU 训练（示例中的 GPU 0 仅为用户运行时选择）：

```bash
CUDA_VISIBLE_DEVICES=0 python -m specprune.training \
  --model-dir models/Qwen3-Reranker-4B \
  --train assets/training/train.jsonl \
  --val assets/training/val.jsonl \
  --out outputs/retrained --device cuda:0
```

冻结训练集 8,556 对、验证集 487 对，来源为 SWE-bench Lite 与排除 Lite/OOD 重叠后的 Verified；按 issue 隔离。实际配置为 LoRA rank16/alpha32/dropout0.05、学习率 5e-5、3 epoch、micro-batch1、每 8 样本累积加权损失；正负总权重 1:2。详细的标签构建、统计、选择规则和限制见 [TRAINING.md](docs/TRAINING.md)。本包不提供或读取封存 test。

重新训练后应使用**新模型自身的 val 概率**重新选择 epoch、拟合温度与低阈值，不直接套用旧 checkpoint 的温度和阈值。相同 seed 并不保证不同 GPU/软件环境产生逐位相同的权重或模型响应。

## 5. 目录与交付

```text
SpecPrune/
  specprune/          独立训练、评分、推理、输入渲染、抽样与评测入口
  vendor/             保持原字节的必要 CoSIL 工具/Prompt/搜索依赖
  configs/            冻结训练、部署、运行和抽样配置
  tests/              数值口径、身份、数据隔离、补丁映射与运行链路测试
  docs/               训练、运行、评测及复现范围
  paper_results/      可公开的逐题派生指标与 CPU 图表程序
  source_archive/     原始研究脚本，用于追溯；不是直接运行入口
  provenance/         来源、Git 备份、抽样清单、SHA256 与验证记录
  scripts/            资产导出、模型下载与分包脚本
  assets/             本地资产：train/val、tokenizer、离线评测、干净推理输入
  checkpoints/        本地论文 LoRA，原字节保存
  outputs/            用户新运行输出（不覆盖历史记录）
```

```bash
python scripts/build_bundles.py --output ../SpecPrune-release
```

该命令产生代码包与资产包，分别校验并记录 SHA256。完整资产包只在本地交付；不要把训练数据、离线答案、权重或密钥加入代码仓库。数据/模型使用及再次分发应保留各上游材料的许可和来源，见 [NOTICE.md](NOTICE.md)。
