# SpecPrune 训练与判别器复现

本包提供两条路线：直接加载论文使用的 `Qwen3-Reranker-4B` epoch 1 LoRA 适配器；或用冻结 train/val 重新训练。主定位智能体使用 `Qwen3-8B`，与剪枝判别器分开加载。旧 `SweRank` 第二轮、Qwen2.5 主定位配置和后续候选训练不是本论文适配器的来源。

## 文件与授权边界

- `specprune/training.py`：可搬运训练入口，输入是已经冻结的 train/val JSONL。
- `specprune/{input_format,codec,model_ops}.py`：与原实验相同的 v6 输入、原生 yes/no 评分、二分类损失和左侧 padding。
- `specprune/{metrics,assessment,qualification}.py`：验证集温度校准、逐 epoch 评价与原选择规则；没有读取或开启封存 test 的接口。
- `assets/training/{train,val}.jsonl` 与 `manifest.json`：本地导出的冻结训练资产。不包含 test，也不是 100 题评测集。
- `checkpoints/specprune_epoch1/`：原适配器文件，字节不改写；不包括 4B 基座权重。
- `configs/{training,deployment}.json`：训练处方和论文部署参数。

训练数据与适配器由独立本地资产包提供，不随 GitHub 的代码/文档提交自动上传。复制本包时须保留对应资产目录，或另取作者提供的资产包；仅克隆代码仓库不能凭空恢复未公开的数据文件。再分发源代码片段、数据与模型时，应同时遵守各原仓库、SWE-bench 数据源和 Qwen 模型的许可；本包的代码许可不会覆盖它们。

## 训练数据是什么

训练单元为 `(issue, function, direct-call-neighbor-summary, label)`。`True` 表示与缺陷因果路径相关，`False` 表示应排除。它是相关性判别任务；部署时按校准概率决定直留、直剪或交回 CoSIL 判断。

| 划分 | issue 数 | 样本对数 | SWE-bench Lite | Verified 非 Lite |
|---|---:|---:|---:|---:|
| train | 359 | 8,556 | 217 个 issue / 3,029 对 | 142 个 issue / 5,527 对 |
| val | 44 | 487 | 27 个 issue / 311 对 | 17 个 issue / 176 对 |

train 与 val 按 `instance_id` 隔离。已有切分保持冻结，不能为提高验证成绩重新分配。仓库可能同时出现在两个划分中，因此这是 issue 隔离，不是跨仓库泛化切分。

| 组别 | 含义 | train 对数 | val 对数 | train 单样本权重 |
|---|---|---:|---:|---:|
| gold_AB | 由补丁实际改动行及 AST 映射得到的既有目标函数正例 | 574 | 76 | 1.586624893859983 |
| C_positive | 直接调用图相关的扩展正例 | 3,899 | 162 | 0.4978910774363605 |
| D_only_negative | 原数据构建规则中的 D 类负例 | 2,339 | 33 | 0.32319444515986134 |
| E_negative | 静态保守排除并通过运行时覆盖资格过滤的 E 负例 | 1,744 | 216 | 2.8371835967724106 |

train 原始正负样本数为 4,473 / 4,083；权重和为 **2,852 : 5,704 = 1 : 2**。val 的 `sample_weight` 全为 1，评价和温度拟合不套训练权重。覆盖缺失不是“不相关”的证明；静态图和有限失败测试覆盖也不能证明绝对无关。数据构建代码及历史审阅出处见 `provenance/` 的原实验来源归档。

导出脚本只保留白名单字段，去掉 `graph`、`runtime_filter`、`source_provenance` 和 `provenance` 等含服务器机器路径的附加证据结构。issue/函数/邻居文本、`model_input`、`input_sha256`、标签、样本权重和行顺序完全不变。原文件与导出文件 SHA 不同，`manifest.json` 同时记录二者及按原顺序汇总的输入哈希；训练器逐行复核文本 SHA。

原冻结输入文件 SHA256：

```text
train ae02ff2d6ad1dd7410e77de9fbd155097103b4a47147f5e087857434b111f15e
val   5233302cbdc4e4f86bf7e3be02ab80d0f2aeb1e283604a6bd86a4e4f47f61942
```

## 模型与数值处方

基座为 `Qwen/Qwen3-Reranker-4B`，冻结 Hugging Face revision：

```text
22e683669bc0f0bd69640a1354a6d0aebcfeede5
```

下载到任意本地目录后，通过 `--model-dir` 显式指定。所有加载器使用 `local_files_only=True` 和 `trust_remote_code=False`。正式训练和评分还会按 `provenance/model_files.json` 所列 SHA256 校验权重分片、配置和 tokenizer，不能只靠目录名字声称 revision 一致。本训练器不联网、不自动申请 GPU、不启动或改动 vLLM。

| 参数 | 本论文使用的设置 |
|---|---|
| LoRA | rank 16；alpha 32；dropout 0.05；all-linear；bias none |
| 优化器 | AdamW；lr 5e-5；weight decay 0；恒定学习率 |
| 训练轮数 | 3 epoch，逐 epoch 保存与验证；原最终选择 epoch 1 |
| 精度与注意力 | BF16，SDPA，gradient checkpointing（use_reentrant=False） |
| 批处理 | 每次 forward 1 对；每 8 对做一次 optimizer step；尾组保留 |
| 损失 | 最后一个位置的 `no`/`yes` 两个 logits 上做二分类交叉熵 |
| 权重归一化 | 每组 `sum(weight_i * CE_i) / sum(weight_i)` |
| 梯度裁剪 | norm 1.0 |
| 种子 | torch/CUDA seed 0；第 e 轮用 `random.Random(e)` 打乱原索引 |
| 输入处理 | 不拼接多个训练样本，不重新截断冻结 `model_input` |
| 训练前检查 | 最长样本 forward/backward，不更新参数；恢复 RNG 后开始训练 |

原运行记录的软件版本为 Python `3.11.17`、torch `2.13.0+cu130`、transformers `5.18.0`、peft `0.21.2`。包内环境文件记录部署所需版本；若迁移到不同 CUDA、硬件或库版本，应另记运行指纹。相同 seed 不等于跨设备逐 bit 一致。建议使用 Python 3.11；Python 3.12+ 的浮点 `sum` 实现变化会令重新拟合的温度发生约 1e-7 量级差别，原 Python 3.11.17 可精确复算记录的温度/阈值。部署直接加载冻结参数，不需重新拟合。

原模板中的空 `<think>\n\n</think>` 是 reranker 的固定 answer-logit 包装，不进行思考文本生成。推理不调用 `generate()`，只读取两个 answer logits；`generated_output_tokens=0` 不能解释为剪枝模型没有计算或没有输入 token 成本。

## 输入契约与校准

v6 文本结构严格为：

```text
<issue>
{issue}
</issue>
<function>
{function}
</function>
<direct_call_context>
{neighbors}
</direct_call_context>
```

issue 初始上限 8,000 字符，函数 8,192 字符，每个方向最多 16 个调用邻居，摘要最多 12,288 字符。`fit_input` 同时使用两套历史 tokenizer 检查预算：正文不超过 7,680 token，原生输入不超过 8,128 token，总边界 8,192。超限先移除末尾邻居行，再以 256 字符缩减函数、最后缩减 issue；保护 issue 前 2,000 字符和函数前 1,500 字符，仍不满足则报错，不静默破坏保护区。训练入口接收最终冻结文本，禁止套用旧 v5 的 2,000/1,500 短输入 codec。

两套历史 tokenizer 只用于保持输入预算口径，目录为 `assets/tokenizers/reranker06b` 与 `assets/tokenizers/qwen25coder`，不需要对应 0.6B / 7B 旧模型权重。实际剪枝评分使用 4B 基座 tokenizer。

原 epoch 1 val 原始 accuracy 为 429/487 = 88.09%，AUC 为 0.9470。温度通过 val 二分类 NLL 拟合：`T=2.9846201034621833`。原选择规则先筛满足默认 0.6/0.9 风险门的 epoch；若均不满足，按 gold 直剪风险 CI 上界、混合剔除 precision CI 下界、accuracy 和 epoch 顺序选择诊断模型。**原 epoch 1 没有通过默认 0.6 阈值的完整风险资格门**，不能把“选择 epoch 1”表述成“已证明所有部署剪枝安全”。

论文部署另用保守经验阈值：

```text
p = sigmoid((logit_yes - logit_no) / 2.9846201034621833)
p <= 0.12947567721292427  -> reject
p >= 0.9                  -> retain
otherwise                 -> qwen (由 CoSIL 原判断流程处理)
```

低阈值为 `nextafter(val 最小 gold_AB 校准概率, -inf)`。温度与阈值来自同一个 val，零 val gold 直剪是阈值构造结果，不是独立测试保证。类请求与函数身份/渲染校验失败按原运行集成规则交回 CoSIL；评分服务异常或非有限 logit 会记录错误并终止该任务，不伪造拒绝或保留判断。

## 可运行命令

以下命令从本包根目录运行。Python 依赖安装方式见总 README。

无 GPU、无大模型依赖的资产校验：

```bash
python -m specprune.training --validate-only
python -m specprune.scoring --validate-only
python -m unittest discover -s tests -p 'test_training*.py' -v
python -m unittest discover -s tests -p 'test_scoring*.py' -v
```

安装 transformers 后，可额外核对 9,043 条输入的真实 tokenizer 结果，不加载模型权重：

```bash
CUDA_VISIBLE_DEVICES='' python -m specprune.training --validate-only \
  --model-dir /path/to/Qwen3-Reranker-4B
```

CPU 核验得到 train 最长 5,514 token，val 最长 4,952 token，与原训练记录一致。

从头训练（先确认所选 GPU 空闲，输出目录必须不存在）：

```bash
CUDA_VISIBLE_DEVICES=0 python -m specprune.training \
  --model-dir /path/to/Qwen3-Reranker-4B \
  --train assets/training/train.jsonl \
  --val assets/training/val.jsonl \
  --config configs/training.json \
  --out outputs/retrained
```

此入口保持原损失、输入、优化器与 epoch 选择的数值语义；仅去除原服务器的 GPU 自动排队、远端状态路径和滚动恢复机制。中断运行留在原输出目录，不覆盖；需完整重训时换新输出目录。原服务器调度/恢复代码作为来源归档保留。运行结束输出逐 epoch adapter/val 预测、原选择规则结果、选中及最后 epoch 的 train 诊断和完整 `derived_deployment.json`；该配置包含所选新适配器配置/权重 SHA，可传给评分器的 `--deployment`，并用 `--adapter-dir` 显式指定新 epoch 目录。不会自动将新 adapter 替换成论文冻结 adapter。

用冻结 adapter 对已渲染输入评分：

```bash
CUDA_VISIBLE_DEVICES=0 python -m specprune.scoring \
  --model-dir /path/to/Qwen3-Reranker-4B \
  --adapter-dir checkpoints/specprune_epoch1 \
  --deployment configs/deployment.json \
  --input /path/to/rendered_v6_inference_rows.jsonl \
  --output outputs/pruner_scores.jsonl
```

`scoring` 输入不需要 label。代码仅白名单传递 issue/function/neighbors/model_input/input_version/input_sha256；训练标签、gold 和 provenance 不进入模型输入。结果记录概率、路由、原始 logit 差、输入 token、实际单次 forward 时延和生成 token 数。

适配器 SHA256：

```text
903cf41341d5455381d8b713e6505b696be62d4a7d9a2a386421642985c30736
```

原 `adapter_config.json` 内的历史绝对路径保留原字节，但不会被加载器使用：先按命令行显式加载基座，再通过 `PeftModel.from_pretrained(base, adapter_dir)` 载入 LoRA。不能直接依赖旧路径启动 `AutoPeftModel`。

## 重新导出允许共享的本地资产

该命令只用于拥有原冻结训练资产的复现者；严格指定 train/val 文件，不扫描或读取 test。目标文件已存在会拒绝覆盖。

```bash
python scripts/export_training_assets.py \
  --train /path/to/T2_dataset_v6/pruner_train.jsonl \
  --val /path/to/T2_dataset_v6/pruner_val.jsonl \
  --checkpoint /path/to/T3_round1_exploratory/reranker4B/epoch_1 \
  --reranker-tokenizer /path/to/Qwen3-Reranker-0.6B \
  --instruct-tokenizer /path/to/Qwen2.5-Coder-7B-Instruct \
  --destination /path/to/empty_artifact_assets_root
```

迁移包已执行 CPU 文本/哈希/切分/权重检查、全部输入 tokenizer 预算检查、单元测试与原实现关键函数核对。未为打包目的重新训练或重新运行 GPU 推理，不能把这些 CPU 检查描述成一次新的训练复现实验。
