# LocBench 100题：CoSIL与SFPruner定位结果

日期：2026-11-16。状态：100题、200个实验臂全部运行完成；零任务执行失败、零补题、零整臂或整题重跑。原冻结文件阶段含5次格式纠正调用，单独记录并计入真实token。本文是结果报告，不修改论文或历史实验。

## 1. 主要结果

本轮在预先冻结的同一100道LocBench任务上比较CoSIL与SFPruner。两组均采用本地Qwen3-8B作为定位模型；SFPruner额外使用已有Qwen3-Reranker-4B剪枝模型。函数评价采用严格的`path::qualified_name`，100题均具有完整、非空、经base版本AST核验的既有目标函数集合，函数指标分母为100题。

| 条件 | 函数Hit@1 | 函数Hit@3 | 函数Hit@5 | Macro-Precision@5 | Macro-Recall@5 | Macro-F1@5 |
|---|---:|---:|---:|---:|---:|---:|
| CoSIL | 41/100（41.00%） | 53/100（53.00%） | 56/100（56.00%） | 14.40% | 47.33% | 20.04% |
| SFPruner | 43/100（43.00%） | 54/100（54.00%） | 56/100（56.00%） | 14.20% | 48.11% | 20.08% |
| SFPruner−CoSIL | +2.00pp | +1.00pp | 0.00pp | −0.20pp | +0.78pp | +0.05pp |

观察到的是Top-1与Top-3的小幅改善、Top-5持平，尚无统计显著的定位增益。Precision@5略降，不能概括为所有指标均提高。两组Top-5逐题去重命中的目标数之和分别为72与71；Recall的宏平均略升，来自不同目标集合大小任务的权重变化，不能解释为总共找到了更多目标函数。

### 配对统计与95%置信区间

| 指标 | CoSIL的95%CI | SFPruner的95%CI | 两组均命中 | 仅CoSIL命中 | 仅SFPruner命中 | 两组均未命中 | SF−CoSIL配对95%CI | 精确McNemar p |
|---|---|---|---:|---:|---:|---:|---|---:|
| Hit@1 | [31.87%, 50.80%] | [33.73%, 52.78%] | 40 | 1 | 3 | 56 | [−2.00pp, +6.00pp] | 0.625 |
| Hit@3 | [43.29%, 62.49%] | [44.26%, 63.44%] | 53 | 0 | 1 | 46 | [0.00pp, +3.00pp] | 1.000 |
| Hit@5 | [46.23%, 65.33%] | [46.23%, 65.33%] | 55 | 1 | 1 | 43 | [−3.00pp, +3.00pp] | 1.000 |

单组Hit使用Wilson区间；配对差与宏平均指标使用冻结种子的issue bootstrap（5,000次）。本轮100题来自64个仓库，区间未校正同仓任务相关性。未显著不等于已证明两组等效，也未形成非劣效认证。

### 文件级结果

| 条件 | 文件Hit@1 | 文件Hit@3 | 文件Hit@5 | Macro-Precision@5 | Macro-Recall@5 | Macro-F1@5 |
|---|---:|---:|---:|---:|---:|---:|
| CoSIL | 49/100（49.00%） | 65/100（65.00%） | 71/100（71.00%） | 14.80% | 68.17% | 24.01% |
| SFPruner | 49/100（49.00%） | 65/100（65.00%） | 71/100（71.00%） | 14.80% | 68.17% | 24.01% |

文件指标使用文件智能体的实际候选排名。SFPruner复用同一道题的CoSIL文件阶段，文件结果相同符合本轮设计；它们不能作为两个独立文件检索方法的比较。

## 2. 数据与冻结抽样

- 官方来源：[czlll/Loc-Bench_V1](https://huggingface.co/datasets/czlll/Loc-Bench_V1)。冻结revision：`c44cf3b74e07ca642cec841b471a9939907c12a7`。
- 官方母数据为560题、165仓库。原始Parquet SHA256：`8df0833c2c1276c5837aab923d489ab97d7654529abe759d0f59242c4978a662`。
- 抽样种子为`20261116`。对全部560题按`SHA256(UTF8(str(seed)+":"+instance_id))`及instance_id稳定排序，取前100题。抽样发生在推理之前，不依据预测、成绩或是否容易定位；不设置每仓一题限制。
- 本次100题涉及64仓库、98个独立repo/base归档、113个目标文件和199个既有目标函数；类别为45 Bug、27 Performance、24 Feature、4 Security。
- 使用官方`edit_functions`识别既有目标；`added_functions`不计入修复前版本的既有函数目标。所有199个目标均核对base源码与运行时库存，未通过新增函数推测补齐金标。
- 与本项目既有微调train/val的instance_id无交集。100题中12题来自微调曾出现过的仓库，另88题来自训练异仓；这不等于已排除基础模型预训练接触。
- 未打开本项目封存test；LocBench公开评测数据属于本轮用户授权范围。未混入原Lite结果矩阵，未修改Rebench历史结果。

| 准备与执行状态 | 数量 |
|---|---:|
| 固定分配任务 | 100 |
| 源码准备可运行 | 100 |
| 文件可评价 | 100 |
| 函数可评价 | 100 |
| CoSIL执行完成 | 100 |
| SFPruner执行完成 | 100 |
| 完整配对 | 100 |
| 源码准备失败 / 任务执行失败 / 缺失结果 | 0 / 0 / 0 |

“执行完成”仅表示工程运行结束，不表示定位正确。各类未命中任务全部保留在100题分母中。

## 3. 模型、集成与指标定义

定位模型：`Qwen/Qwen3-8B`，revision `b968826d9c46dd6066d109eabc6255188de91218`；BF16、TP=2、上下文65,536、单次输出上限2,048、temperature=0、seed=0、显式关闭思考，搜索最多10轮。

剪枝模型：`Qwen3-Reranker-4B`及已有epoch1 LoRA；本轮不训练。温度校准值为`2.9846201034621833`，安全下阈值`0.12947567721292427`，上阈值`0.9`。低分直接剪枝，高分直接保留，其余交由Qwen判断；类请求仍交由Qwen。issue、函数源码、邻居摘要及工具协议沿用冻结SFPruner实现。

固定两道题并行调度，每道题先CoSIL、后SFPruner；仅共享同题文件阶段，不跨题共享会话、判断或预测。主模型服务`max_num_seqs=1`。temperature=0不保证不同调度下逐位确定性。本次使用三张可用卡：GPU2/3用于主模型、GPU1用于剪枝模型；GPU0原有他人进程保留。

Hit@k为Top-k至少命中一个既有目标函数。Precision@k的分母固定为k；Recall@k除以该题完整目标函数数；F1逐题计算后宏平均。无效、重复或身份不匹配的预测不通过压缩排名、改名或金标纠正获得额外命中。主表未把`Class.__init__`折叠为类名。

官方LocAgent兼容评价另行保存在`official_compatible.json`，保持固定官方源码的Acc、Recall、初始化器处理及重复槽位语义。官方Acc不是本报告的any-hit，不能直接混用；其文件排名来自函数docs投影，也不替代主表实际文件候选排名。

### 训练同仓 / 异仓描述性分组

| 范围 | 条件 | 函数Hit@1 | 函数Hit@3 | 函数Hit@5 |
|---|---|---:|---:|---:|
| 训练同仓12题 | CoSIL | 7/12 | 9/12 | 10/12 |
| 训练同仓12题 | SFPruner | 8/12 | 9/12 | 9/12 |
| 训练异仓88题 | CoSIL | 34/88 | 44/88 | 46/88 |
| 训练异仓88题 | SFPruner | 35/88 | 45/88 | 47/88 |

以上分组仅作描述，样本量和任务组成不同，不用于挑选最终报告题目。

## 4. 资源与工具执行

全部推理为本地模型，外部API费用为0；GPU电耗、折旧及服务器成本未测量。

| 账目 | CoSIL | SFPruner |
|---|---:|---:|
| 本轮实际主模型输入＋输出token | 10,583,899 | 8,341,908 |
| 主模型usage未知任务数 | 0 | 0 |
| worker平均耗时 | 62.91秒 | 49.06秒 |
| worker中位耗时 | 59.66秒 | 46.13秒 |
| 任务内剪枝模型输入token | 0 | 744,686 |

SFPruner物理账不重复扣入复用的文件阶段。用于公平对照时补计同题文件阶段的1,720,485 token，SFPruner主模型等效合计为10,062,393 token，相对CoSIL减少约4.93%；不能把物理账的差额全部解释为剪枝节省。任务内剪枝模型另消耗744,686输入token，启动合成探针另计8,128输入token；其计算不能用不同模型的token数直接抵扣。worker耗时包含本轮服务调用的等待，不含下载、CPU准备和服务启动；SFPruner还复用了文件阶段，因此上述耗时不是独立端到端加速比。

SFPruner共记录588次本地判决：41次直接剪枝、158次直接保留、389次交Qwen；这只是路由事件，不等于41个互不重复函数或41个已证实无关的目标。工具审计分别记录CoSIL 789次调用事件（691次执行成功、98次工具错误），SFPruner 756次（648次执行成功、108次工具错误）。工具错误与任务执行失败分开：本轮两组均完成100题，但存在工具身份或参数错误事件，不能宣称所有工具调用均正确。

共保留3,451个主模型调用receipt。其中5次为原冻结文件阶段自带的`file_format_retry`，HTTP状态200、receipt标记`semantic_retry=true`；它们用于格式纠正，全部发生在baseline文件阶段，其实际usage已计入本轮及共享文件阶段账目。没有整臂或整题重跑，不能把这一事实写成“全部模型调用均未重试”。

## 5. 复现问题、核验与结束状态

源码准备阶段遇到归档内部Python软链接。采用对所有任务一致的安全适配器，在归档同根内解析链接到原始普通文件字节，不创建宿主软链接；拒绝越根、循环及资源超限。真实4个归档的25个Python链接已核对，7,698个非链接Python文件字节与原归档一致。静态索引由四个CPU进程构建，不执行第三方仓库代码。早期失败和中断记录保留，均发生在正式模型调用前。

本次代码通过75项单元测试；正式执行冻结提交为`fc0463d78a98dd7df1d09d46b425197baa4e1e9f`。最终独立评价核验确认100题抽样、199个目标、200个终态与逐题CSV一致，逐项槽位/指标核验及固定官方评价器CPU对照通过。

关闭服务时出现一条`Owned service cleanup incomplete`告警，保留于原session日志。队列最终退出码0，所有200臂已完成，未因该告警重新执行任何已开始的实验臂。独立核验进一步确认本次主服务、剪枝服务、controller及实际CUDA子进程均退出，7343端口关闭，显存恢复运行前水平：GPU0/1/2/3分别为10,925/826/19/19 MiB；既有GPU0进程及GPU1 NVML残留未动。这条告警不计为模型任务失败，也未删除以隐藏异常。

## 6. 真实产物与复现入口

所有逐题预测、数据、金标、模型和日志仅保留服务器，不上传代码/文档发布仓库。

相对于CoSIL根目录：

```text
code_locbench_sfpruner_20261116/                         # 冻结执行与评价代码
results/locbench_qwen3_sfpruner_20261116/pilot100/
  selection/selection.json                             # 种子、算法和候选顺序
  allocation.json                                      # 固定100题名单
  protocol.json                                        # 冻结协议
  controller/launch_ready.json                          # 正式启动及源码哈希
  controller/report_freeze.json                         # 评分前冻结
  paired_run/pairs/                                     # 两组原始结果及终态
  completion.json                                      # 全部结束
  reports/final/LocBench_定位总览.md                      # 自动完整报告
  reports/final/all100_逐题定位与资源.csv                  # 主逐题表，保留全部100题
  reports/final/all100_evaluation.json                   # 所有k、CI及配对统计
  reports/final/summary.json                            # 聚合、状态与资源
  reports/final/official_compatible.json                # 独立官方兼容口径
  reports/final/input_sha256.json                       # 评分输入哈希
  reports/final/output_sha256.json                      # 评分输出哈希
  audits/independent_results_gate.json                   # 独立指标核验
  audits/independent_resource_and_service_release.json   # 独立资源/释放核验
```

离线重算仅需CPU，不新增模型请求；输出目录必须是全新路径，不覆盖历史报告：

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/CoSIL
.venv-v5/bin/python -B -m code_locbench_sfpruner_20261116.report \
  --freeze-file results/locbench_qwen3_sfpruner_20261116/pilot100/controller/report_freeze.json \
  --out /tmp/locbench100_rescore_NEW
```

完整数据准备、模型入口及测试命令见`code_locbench_sfpruner_20261116/README.md`。本轮只完成授权的100题，不自动启动剩余460题，不重新训练、不生成补丁、不执行修复测试、不改论文或旧矩阵。
