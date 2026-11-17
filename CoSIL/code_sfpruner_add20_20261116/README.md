# CoSIL / SFPruner：随机新增20题，2026-11-16

这是冻结方法的新题扩展。仅新增CPU抽样、准备与统计包装器，定位智能体、Qwen3-8B、Reranker-4B LoRA epoch1、校准温度、阈值、提示词和迭代上限沿用 `code_sfpruner300_20261114` 与 `papers/SFPruner`。不训练、不调用付费API、不改历史结果或论文。

## 抽样

从两个既有冻结SWE-rebench快照恢复全部合格候选，保留四项业务补丁过滤、训练/验证/保护数据隔离。同ID优先已有leaderboard冻结快照。排除原CoSIL/SFPruner全部308题，包括后来未纳入280题表的题目。先按 `SHA256(UTF8("20261116:" + instance_id))` 排序，再顺序完成R2既有函数金标准备；选取前20道目标集合完整且非空的任务。

仓库允许重复，原308题与新增20题合计每仓库最多3题。临时网络失败暂停顺序前缀；不能跳过难下载题或根据预测结果替换题目。抽样程序不读取模型预测与成绩。全部20题均保留，最终另报两组同对、同错与不一致情况。

## 隔离与运行

资格和参考补丁只供CPU准备/独立评价；定位进程仅接收干净base源码、issue与结构文件。`runtime build` 使用上一轮相同的解码记录适配器，保留原始字节并记录不可解码文件，不删除源码或改变模型。`runtime gate` 在首次推理之前核对R2目标身份、base源码SHA及实际结构库存。

主模型为 `Qwen/Qwen3-8B`，BF16、TP=2、64K上下文、输出2048、temperature=0、seed=0、关闭思考、最多10轮搜索；剪枝参数 T=2.9846201034621833、low=0.12947567721292427、high=0.9。两臂共享相同的上游文件候选，保留失败，不作语义重试或换题。

原队列对空闲GPU作90秒观察及启动前复核。本次计划主模型使用2/3，剪枝模型使用GPU1的空闲显存；GPU0既有服务与GPU1已知不可见残留不作终止或重置。实际设备以队列回执为准，若占用变化则等待。结束后只关闭本次具有完整身份回执的服务。

## 命令

在CoSIL根目录运行。新实验根目录为 `results/sfpruner_add20_20261116`；正式命令及每步日志另保存在该目录控制文件中。

```bash
.venv-v5/bin/python -B -m unittest discover -s code_sfpruner_add20_20261116 -t . -p 'test_*.py' -v

.venv-v5/bin/python -B -m code_sfpruner_add20_20261116.prepare \
  --run results/sfpruner_add20_20261116

.venv-v5/bin/python -B -m code_sfpruner_add20_20261116.runtime build \
  --work results/sfpruner_add20_20261116 \
  --archive-cache results/sfpruner300_20261114/archive_cache

.venv-v5/bin/python -B -m code_sfpruner_add20_20261116.runtime gate \
  --work results/sfpruner_add20_20261116 \
  --qualified results/sfpruner_add20_20261116/qualified

.venv-v5/bin/python -B -m code_sfpruner300_20261114.controller \
  --prepare-only --manifest results/sfpruner_add20_20261116/runtime/manifest.json \
  --out results/sfpruner_add20_20261116/paired_run

.venv-v5/bin/python -B -m code_sfpruner_add20_20261116.report --freeze-only \
  --freeze-file results/sfpruner_add20_20261116/controller/report_freeze_cases_v2.json \
  --manifest results/sfpruner_add20_20261116/runtime/manifest.json \
  --run-root results/sfpruner_add20_20261116/paired_run \
  --qualified-root results/sfpruner_add20_20261116/qualified/cases \
  --protocol results/sfpruner_add20_20261116/protocol.json \
  --history-evaluation ../GraphLocator/experiments/qwen3_rebench280_v3_20261116/reports/final_delivery/evaluation.json \
  --history-sha256 368e98c9ad97a9585aad3b15afebc81ecc5f9220fd7e387834d8c39f31bd9e78

PATH=/home/wdt/miniconda3/envs/cosil/lib/python3.11/site-packages/nvidia/cu13/bin:/home/wdt/miniconda3/envs/cosil/bin:/bin:/usr/bin \
CUDA_HOME=/tmp/cosil_rebench_qwen3_8b_20261023/tools/cuda13 \
FLASHINFER_NVCC=/home/wdt/miniconda3/envs/cosil/lib/python3.11/site-packages/nvidia/cu13/bin/nvcc \
.venv-v5/bin/python -B -m code_sfpruner300_20261114.service_queue --wait \
  --manifest results/sfpruner_add20_20261116/runtime/manifest.json \
  --run-dir results/sfpruner_add20_20261116/paired_run \
  --queue-dir results/sfpruner_add20_20261116/service_queue \
  --judge-gpu 1 --poll-seconds 10

# 队列完成、服务关闭且40臂/20对终态完整后，写入全新报告目录：
.venv-v5/bin/python -B -m code_sfpruner_add20_20261116.report \
  --freeze-file results/sfpruner_add20_20261116/controller/report_freeze_cases_v2.json \
  --out results/sfpruner_add20_20261116/reports/final
```

不要运行旧 `pipeline.py` 或 `finalize.py` 的主入口：它们冻结的是旧208/308/300题规模及每仓一题条件。本扩展调用原构建器、控制器、队列与评分函数，采用单独名单和输出目录。

路径说明：`runtime gate --qualified` 接收资格输出根 `qualified`；报告的 `--qualified-root` 则沿用原评分函数接口，接收直接包含各题目录的 `qualified/cases`。首次报告配置使用了上一级路径，原配置保留；`report_freeze_cases_v2.json` 仅纠正此离线报告路径，源码、名单、模型请求和评分规则均不变。

## 统计范围

主结果是新增随机20题，两臂40个终态及20对回执齐全后才打开金标评分。Hit@1/3/5、Precision/Recall、失败和逐题一致情况按原严格路径及限定名规则计算。

另外可提供“历史280＋新增20”的描述性组合300题表，保留历史逐题评分，不替换原完整300题报告。历史280曾按运行结果形成，新增20结果无关；合并结果不能宣称为独立随机300题估计。运行失败与预测为空均保留分母，不能当成已经验证的两组同错。

## 代码版本

修改前恢复点已发布至用户仓库：`efdf2a76584389599e53d0e95a75019ca5d09877`，分支 `snapshots/sfpruner-pre-add20-20261116`。新增代码与合成单元测试在本轮正式推理前独立发布；仅上传代码和说明，不上传数据、金标、密钥、模型、运行日志或封存test。
