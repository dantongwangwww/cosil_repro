# LocBench560三项单因素消融

本轮只新增三种剪枝条件，复用既有CoSIL与完整SFPruner控制。数据与模型配置、评价分母及干预边界见[实验协议](../docs/locbench-sfpruner-ablation560/实验协议_三项单因素.md)和[接口约定](CONTRACT.md)。结果不能由旧事件离线重算代替。

本工程修订保留v1全部代码与启动失败现场。首次运行在基准调用开始前，因全量来源校验没有阶段心跳而触发旧180秒看门狗；v2在真实校验完成节点更新进度，不放宽180秒窗口，不修改定位或剪枝规则。新根复用同一560题的公开输入字节，继承已消耗的2次模型服务session额度，剩余最多1次启动。详见[工程修订](../docs/locbench-sfpruner-ablation560/工程修订_v2_校验阶段心跳.md)。

## 环境与前提

从CoSIL仓库根目录执行，使用既有`.venv-v5/bin/python`（Python 3.11）；不升级依赖。模型、LoRA、LocBench原快照、原文件阶段结果与Gold均留在本地，不随代码快照发布。原公开数据为`czlll/Loc-Bench_V1`，冻结revision为`c44cf3b74e07ca642cec841b471a9939907c12a7`。训练、历史控制及来源文件的配置详见`docs/locbench-qwen3-sfpruner560/实验协议与复现.md`。

主Qwen3-8B使用物理GPU2、3，4B剪枝器使用GPU1；GPU0及无法归属的既有进程不属于本轮。服务在每次启动前检查原权重、配置和空闲窗口，不会自动修改模型参数或挤占已有任务。

## 命令顺序

以下为本工作区的执行命令。`R`必须对应独立且已经创建冻结`protocol.json`的实验目录；不要指向旧控制目录。新机器需重新建立公开数据与模型路径、生成输入资格回执，不能复制旧SHA后宣称通过。

```bash
R=results/locbench_qwen3_sfpruner_ablation_20261117_preflight_v2
.venv-v5/bin/python -B -m code_locbench_ablation_20261117_v2.restart_preflight \
  --from-root results/locbench_qwen3_sfpruner_ablation_20261117 --root "$R"
.venv-v5/bin/python -B -m unittest discover \
  -s code_locbench_ablation_20261117_v2 -t . -p 'test_*.py' -v
```

准备完成后，先保存覆盖当前全部源码的测试回执、独立核验回执和远端发布回执。将下面三个占位路径替换为真实回执，资格门会拒绝缺失、过期或未绑定当前源码的文件；不会因指定了路径就视为通过。

```bash
.venv-v5/bin/python -B -m code_locbench_ablation_20261117_v2.freeze \
  --root "$R" \
  --publication-receipt <执行快照发布回执.json> \
  --test-receipt <完整CPU测试回执.json> \
  --independent-check <独立执行门回执.json>
.venv-v5/bin/python -B -m code_locbench_ablation_20261117_v2.supervise \
  --root "$R" --poll-seconds 10
```

监督器启动独立服务队列及CPU报告程序，先跑固定3题工程金丝雀，再跑其余尚未开始的臂。每题各条件独立输出，已开始臂不重抽；正常定位失败保留分母。每100题的CPU报告与后续推理并行。

## 产物与检查

- `manifest.json`、`authority.json`：冻结560题、原始来源SHA、557条可运行与3条不派发原因。
- `run/pairs/<issue>/<condition>/`：原始请求、响应、事件、worker身份、评分RPC回执及终态；`group_terminal.json`表示该题三臂闭合。
- `controller/status.json`、`run/progress.json`：真实监督状态和进度。心跳不等于实验完成。
- `reports/cumulative100`至`reports/cumulative560`：五条件逐题结果、指标、配对统计与资源账；模型失败与上游阻断均保留。
- `completion.json`：只有全部终态、各前缀报告核验通过且本轮自有服务及CUDA子进程实际退出后才生成。

需要独立复算已闭合前缀时，使用全新的输出目录，不覆盖既有报告：

```bash
.venv-v5/bin/python -B -m code_locbench_ablation_20261117_v2.report \
  --root "$R" --n 560 --out <全新的CPU复算目录>
```

外部条件名为`ablation_no_lora`、`ablation_no_neighbors`、`ablation_no_defer`；旧worker内部仍为`hybrid_safe`，两种身份同时记录。使用IID拼接，不按结果行号对齐。评分异常或断线后的未知用量不计为零；启动合成探针与基准题账分开。
