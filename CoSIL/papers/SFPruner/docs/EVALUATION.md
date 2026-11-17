# 离线评分、抽样与函数金标重建

所有命令在 SpecPrune 包根目录运行。本模块仅用 Python 标准库，不加载 GPU、模型、API 密钥或封存 test。训练/推理进程不得读取 `assets/evaluation/` 或 R2 重建输出。先完成并冻结预测，再运行离线评分。

## 一、复算论文 100 题

此机准备的离线资产位于 `assets/evaluation/`；为遵守仅发布代码与文档的约定，它们不随 Git 发布。该目录有：

| 文件 | 内容 |
|---|---|
| `predictions.json` | 两臂模型原始有序身份输出、真实执行状态；未修正/删除错误候选 |
| `gold.json` | 100 题独立 R2 目标及可评价状态，不含补丁或测试内容 |
| `inventory.json` | base 快照所有文件路径与函数身份，用于拒绝幻觉身份 |
| `expected_metrics.json` | 原冻结结果的聚合指标，仅用于比对，不作为评分输入 |
| `ASSET_MANIFEST.json` | 原文件与导出文件 SHA256，来源版本、范围及隔离说明 |

```bash
python -m specprune.evaluation --help
python -m specprune.evaluation \
  --predictions assets/evaluation/predictions.json \
  --gold assets/evaluation/gold.json \
  --inventory assets/evaluation/inventory.json \
  --output outputs/paper100_recomputed
python -m unittest discover -s tests -p 'test_evaluation*.py' -v
```

输出目录必须尚不存在，产生 `evaluation.json`（完整汇总与逐题指标）及 `per_issue.csv`。重跑应选择新输出目录。原始结果不改写。

如果持有原作者运行资产，可执行一次白名单导出：

```bash
python scripts/export_evaluation_assets.py \
  --source-run /path/to/qwen3_rr4_rebench100_20261110 \
  --output assets/evaluation \
  --sampling-output provenance/sampling_manifest.json
```

导出器只读取该运行目录的四个固定结果文件，不读取训练/验证/封存数据、不读取日志、不连接服务；剔除旧本机路径、保留原 rank slot。`paper_results/` 的派生统计另可独立复算与绘图，无需私有资产；那是聚合表校验，并非从原始预测重新评分。没有原始资产时，相关单元测试会明确 `skip`。

已核验的论文结果：固定 100 题、函数完整非空目标 92 题、完整执行配对 99 题。函数 Hit@1/3/5：baseline 为 36/92、47/92、49/92；hybrid_safe 为 37/92、48/92、49/92。配对 Hit@5 四格为均命中 48、仅基线 1、仅剪枝 1、均未命中 42。不是“全部 100 题都可做函数评价”。

### 评分口径

- 函数身份严格为 `path::qualified_name`。限定名、大小写必须一致；`./`、路径分隔符采用历史评分器的规范化；绝对路径与 `..` 不接受。
- 只评价 Python 业务源码：排除 tests/testing/doc/docs/documentation 目录及 `test_*.py`/`*_test.py`；所有预测还必须在该 base 的完整身份清单中。
- 原始前 10 位逐一验证，非法位置留 `null`，不压紧排名、不按 gold 修正预测；重复项占位但命中集合不重复计数。
- Hit@1/3/5 为至少命中一个目标；Precision@5 的分母固定为 **5**，即使仅输出两项；Recall@5 为命中唯一目标数/该题唯一目标数。F1 逐题计算后宏平均，不能由宏 P/R 再算 F1。
- AllCoverage@5 为覆盖该题全部既有目标函数；MRR@10 按原始排名位置。文件级使用同一集合与占位逻辑。
- 函数主分母限 `COMPLETE_NONEMPTY` 且 `set_complete=true` 的非空目标集合；`COMPLETE_EMPTY`/`INCOMPLETE` 记 NA，不当成定位失败。文件分母为非空 gold 文件集。
- 固定可评价名单内，运行失败、尚未运行/不完整均保留分母并按没有预测计 miss，执行状态独立报告，不混淆模型失败和未执行；有预测却标记未完成会报错。另列 `completed_only_secondary` 供诊断，不能用它替代主表。
- Hit 95% 区间为 Wilson。宏指标、同题 B−A 差为按 issue 重采样的 5,000 次 percentile bootstrap，seed=20261110；沿用历史索引约定。McNemar 使用二项精确双侧检验。不显著不等于等效或已证明非劣。

### 新预测输入格式

三份 JSON 必须含完全相同的任务 ID；不能把失败题从预测名单删掉。`--arms` 可替换默认的两个条件名。

```json
{
  "records": [{
    "instance_id": "org__repo-1", "repo": "org/repo", "base_commit": "FULL_SHA",
    "arms": {
      "baseline": {"status": "complete", "predicted_files": ["src/a.py"],
        "predicted_functions": [{"path": "src/a.py", "qualified_name": "Class.method"}]},
      "hybrid_safe": {"status": "NOT_RUN", "predicted_files": [], "predicted_functions": []}
    }
  }]
}
```

Gold 格式：`{ID: {status, set_complete, targets:["src/a.py::Class.method"], gold_files:["src/a.py"]}}`。Inventory 格式：`{ID: {function_identities:[所有 base 函数身份], paths:[所有 base 文件路径]}}`，必须源于代码索引，不能只放预测或 gold 来伪装完整清单。

## 二、复现固定抽样

```bash
python -m specprune.sampling \
  --input provenance/sampling_manifest.json \
  --output outputs/sampling_recomputed.json \
  --seed 20261110 --count 100
```

已公开 `provenance/sampling_manifest.json` 中全部 265 个候选的顺序、repo/base、选中/排除理由和原来源哈希。该池有 173 个不同仓库。算法按 `SHA256(UTF-8(str(seed)+":"+instance_id))`，再按 instance ID 打破平手；按 `repo.casefold()` 每仓最多选一道，取前 100 道。样本选择只使用身份、仓库和 base，不读 gold、历史定位或模型表现；乱序输入产生同一选中名单。

此入口复现的是**已冻结合格池上的抽样**，不擅自重新构建 265 题筛选池。其 revision 为 `34d5a58864acf91613740a09ec5d205228dcfa39`。该开发诊断池已被历史实验观察，不应称为从未见过的封存测试集。

## 三、从 base 源码与业务补丁重建 R2 gold

`specprune.gold` 移植自原 ModelLoc 的 R2 离线评价器；原文已备份到发布提交 `777020b21bee37990e8ea12d562f9f9e228a3dee`。原 SHA256 见模块头部，AST 与映射逻辑保持一致，仅去除服务器硬路径并增加显式 CLI/I/O 入口。

严格使用 **Python 3.12 AST**，不会悄悄换版本。普通评分不需要 3.12；只有重建 R2 需要。此程序不执行仓库代码、不运行测试、不调用模型。补丁仅用于离线目标提取，不得传给定位器。

```bash
python -m specprune.gold --help
python -m specprune.gold \
  --snapshot /path/to/clean/base_snapshot \
  --patch /path/to/business_patch.diff \
  --instance-id org__repo-1 --repo org/repo --base-commit FULL_BASE_SHA \
  --python-ast /path/to/python3.12 \
  --output outputs/offline_gold --cohort reconstructed
```

若快照含 `.git`，入口检查 HEAD 等于完整 base SHA、所有已跟踪文件干净；不含 `.git` 的发布快照需由准备者通过来源 manifest/文件 SHA 核实 base，不把“有一个目录”当作版本证明。入口冻结每个 Python 文件字节哈希，输出独立 `_offline_inputs`，原快照和补丁均不改动。

输出含逐题 `gold_v2.json`、`code_index_v2.json`、逐文件证据、`mapping_summary.json`，并提供可直接送入评分器的 `scoring_gold.json` 与 `scoring_inventory.json`。保持这些产物只在离线评测侧。

批量输入也支持：

```bash
python -m specprune.gold --manifest /path/to/offline_manifest.json \
  --cohort my_cohort --python-ast python3.12 --output outputs/offline_gold_batch
```

Manifest 是 `{ "records": [{"instance_id": ID, "job": "/path/to/job.json", "private_row": "/path/to/private_row.json"}] }`。Job 需有 `instance_id/repo/base_commit/snapshot/paths/code_index`；`code_index` 中每个 base 文件需有解码源码的 SHA256。Private row 需有同一身份字段与 `patch`，只给离线评测器。支持旧版金标路径用于差异审计，但不需要它评分。

R2 映射承认完整 diff 上下文唯一匹配时的坐标偏移，禁止 fuzz、空白更改或选择“最近匹配”。删除行映射到原函数；新增行通过新旧函数连续性映射回既有函数。新增文件、新增且 base 中不存在的函数、类/模块范围变更不冒充既有函数目标；任何无法可靠解析/对齐的情况标 `INCOMPLETE`。因此函数评价可能是 92/100，不能人为把全部任务变成函数金标。

## 来源与适配范围

- 抽样：`code_qwen3_rr4_rebench100/config.py:select`。
- 评分：`code_qwen3_rr4_rebench100/report.py` 与 `code_rebench_qwen/reporting.py`；统计增加显式状态与固定名单配对区间，原评分定义不变。
- 金标：`ModelLoc/experiments/dsimple_evaluation_v2_delivery/dsimple_v2/gold.py`，R2 revision `r2_exact_context_offsets`。
- `scripts/export_evaluation_assets.py` 是新白名单导出接口。旧运行、历史预测、训练数据与封存数据均未改写。

### 复制来源 SHA256

```json
[
  {
    "source": "code_qwen3_rr4_rebench100/config.py",
    "sha256": "e3fda9b4e3f8f0b34ae5abd6c28def05420b8209581e236a5f723b2ad1de26e7"
  },
  {
    "source": "code_qwen3_rr4_rebench100/report.py",
    "sha256": "d5401c9355cec1835cfb2253aae4773e6716e34fb97131750d0af5f1c77610b4"
  },
  {
    "source": "code_rebench_qwen/reporting.py",
    "sha256": "1bb3a9221ce44cf0f35fa617eb095834cc53791dc369e12d83e8508c0be37889"
  },
  {
    "source": "ModelLoc/experiments/dsimple_evaluation_v2_delivery/dsimple_v2/gold.py",
    "sha256": "c20e235367d0142fc171a3f07c204b2fc0ec0b87303c1354396ca1d0775810c8"
  }
]
```

独立核验：全部 100 题原始排名重新评分与冻结点估计完全一致；默认 5,000 次 bootstrap 的各区间端点差异小于 `3e-16`（Python 浮点求和版本差异）。R2 原始核心函数经 AST 比对保持一致，适配仅改变 `write_json`、`run_manifest`、`main` 并新增快照入口。9 项 CPU 单元测试通过；未访问封存 test。

## 四、新运行的完整闭环：run → collect → evaluation

下面使用新目录，不读取旧预测来代替新运行。先按 [RUNTIME.md](RUNTIME.md) 明确启动已有模型服务，再执行固定 runtime manifest。`run-manifest` 按其记录顺序运行，每题输出为 `<run-root>/<instance_id>/<arm>/result.json`；环境问题与模型失败保留在原题位置，不隐式重跑。

```bash
python -m specprune.runner run-manifest \
  --manifest assets/runtime/manifest.json \
  --out outputs/new_run100 \
  --main-model-dir /path/to/Qwen3-8B \
  --judge-socket /tmp/specprune-judge-new/score.sock

python -m specprune.collect \
  --manifest assets/runtime/manifest.json \
  --run-root outputs/new_run100 \
  --output outputs/new_run100_collected

python -m specprune.evaluation \
  --predictions outputs/new_run100_collected/predictions.json \
  --gold assets/evaluation/gold.json \
  --inventory assets/evaluation/inventory.json \
  --output outputs/new_run100_evaluation
```

`collect` 只读取公共 manifest 和本批结果/控制器状态，不读取 gold。输出 `predictions.json`、`collection_summary.json`、`collection_status.csv`，保留完整名单及其顺序；错误候选、重复项和无效 rank slot 均原样保留，后续由评分器验证。模拟输出会被拒绝，身份不一致会停止收集。

状态分别为原结果中的 `complete/failed/...`、控制器错误 `CONTROLLER_FAILURE`、损坏结果 `ARTIFACT_INVALID`、已启动但无终态 `EXECUTION_INCOMPLETE` 与未启动 `NOT_RUN`。baseline文件阶段失败导致 hybrid 未执行时，hybrid 记 `NOT_RUN` 并明确上游原因；不伪造一次模型调用。所有100题均保留，函数可评价分母仍由独立金标决定。已有有效终态结果但又发生控制器错误时，保留预测供审计并标 `CONTROLLER_FAILURE`，不算完整成功执行。

### 训练与部署数值的独立核验

打包时只读审查了原训练实现及实际 val 预测，没有重新训练：

- 输入契约5函数、codec2函数、val评估3函数、资格bootstrap2函数、概率/校准22函数、loss/scoring6函数经过去除import路径差异的AST比对，逻辑一致。
- 保留原每8个样本一次更新、逐例 `(loss * weight / group_weight_sum).backward()`、AdamW、梯度裁剪、每epoch种子以及warmup后恢复RNG。
- 在原 Python 3.11.17 环境，487条已保存验证预测重算温度为 `2.9846201034621833`，low为 `0.12947567721292427`，均逐位一致；accuracy `0.8809034907597536`、AUC `0.9470233876683204`，原资格门未通过。
- 系统新版Python改变浮点求和方法，重拟合温度可出现约 `1.26e-7` 差异、low约 `9e-9`；部署使用冻结参数，不重新拟合，不把跨版本浮点变化冒充模型改进。
- 原有源码身份/渲染失败回退Qwen；非有限分数或评分服务错误按历史语义终止该题，不生成剪枝拒绝。

这项核验只使用已有 val 与代码，未读取封存 test、未调用模型/API、未占用GPU。
