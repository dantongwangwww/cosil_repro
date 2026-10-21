# 强模型简单流程与复杂定位对照实验报告

更新：2026-10-21T10:38:16.938162+00:00。本报告集合：**lite_pilot**；总授权P0五题＋P1五十题；run：`20261021_nonthinking_v3`。当前集合状态：四组均已执行完成。

本轮新增用户要求已落实：每题/每阶段耗时与输入输出token；模型提出的工具调用、真实执行、参数/返回核验，以及源码是否送进裁判和搜索agent。详见[完整工具与时延审计](lite_pilot_单题时长_token与工具使用审计.md)。

一页结论

- **D-SIMPLE**：函数Hit@5 92.68%，Macro-Recall@5 90.24%；严格可映射N=41；状态{'complete': 50}。
- **D-COSIL**：函数Hit@5 82.93%，Macro-Recall@5 80.89%；严格可映射N=41；状态{'complete': 48, 'failed': 2}。
- **Q-COSIL**：函数Hit@5 26.83%，Macro-Recall@5 26.83%；严格可映射N=41；状态{'complete': 40, 'failed': 10}。
- **Q-PRUNER**：函数Hit@5 26.83%，Macro-Recall@5 26.83%；严格可映射N=41；状态{'complete': 39, 'failed': 11}。

D-SIMPLE是**CQ2-inspired simple baseline**：保留论文的五次文件选择、哈希分组、交集回退与整文件输入，增加一次函数级排序。当前是定位开发对照，不能据此声称复刻论文修复率，或用未运行的修复成绩支持替代结论。

表A：数据与执行完整性

| 集合 | 预选题数 | 实际仓库数 | 文件gold有效 | 函数完全映射 | 部分映射 | 不可映射 | 修复验证 |
|---|---:|---:|---:|---:|---:|---:|---|
| smoke | 5 | 4 | 5 | 2 | 2 | 1 | 仅1题空/gold补丁执行链通过 |
| lite_pilot | 50 | 12 | 50 | 41 | 7 | 2 | NOT_RUN |

P0/P1互不重叠；先排除30个既有封存holdout issue ID，再按仓分层确定性抽样，不按预测好坏选题。公开Lite数据的test split为本轮基准，不等于被封存的pruner test。后者不读取、不哈希。

数据本地精确版本：`local-sha256:ff0e6c3b63c8c2237f3d3d29e7d11904a9cd075df7e9348b6001c207c88eabed`。上游revision只记录来源，不冒称与本地harness附加列逐字相同。逐题base commit、金标映射证据和失败记录已落盘。

表B：文件级结果（全体预选题，失败保留分母）

| 方法 | N | Hit@1 | Hit@3 | Hit@5 | Macro-Recall@5 | Precision@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | 50 | 82.00% | 98.00% | 98.00% | 98.00% | 19.60% | 32.67% | 98.00% | 88.67% |
| D-COSIL | 50 | 82.00% | 94.00% | 94.00% | 94.00% | 18.80% | 31.33% | 94.00% | 87.67% |
| Q-COSIL | 50 | 40.00% | 48.00% | 50.00% | 50.00% | 10.00% | 16.67% | 50.00% | 44.07% |
| Q-PRUNER | 50 | 38.00% | 46.00% | 48.00% | 48.00% | 9.60% | 16.00% | 48.00% | 42.07% |

表C：函数级严格主表

| 方法 | 严格N | Hit@1 | Hit@3 | Hit@5 [95%CI] | Macro-Recall@5 | Precision@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| D-SIMPLE | 41 | 85.37% | 90.24% | 92.68% [82.93%, 100.00%] | 90.24% | 20.00% | 32.26% | 87.80% | 88.23% |
| D-COSIL | 41 | 73.17% | 78.05% | 82.93% [70.73%, 92.68%] | 80.89% | 17.56% | 28.51% | 78.05% | 76.83% |
| Q-COSIL | 41 | 21.95% | 26.83% | 26.83% [14.63%, 41.46%] | 26.83% | 5.85% | 9.52% | 26.83% | 24.39% |
| Q-PRUNER | 41 | 21.95% | 26.83% | 26.83% [14.63%, 41.46%] | 26.83% | 5.85% | 9.52% | 26.83% | 24.39% |

函数主分母仅完全可映射题。部分可映射的可映射目标辅助Hit@5分别为：D-SIMPLE 85.71% (N=7)；D-COSIL 85.71% (N=7)；Q-COSIL 0.00% (N=7)；Q-PRUNER 0.00% (N=7)。全部k=1/3/5/10指标保存在method_summary.csv。

统一身份为精确`path::qualified_name`；重复或无效预测占原槽位，Precision@k固定除以k。同限定名的property getter/setter共享这一身份，不要求只有一个源码span；叶名歧义仍无效。报告层补正初版“必须唯一span”的过严判定，并按方案拒绝测试/文档Python路径；保留原始预测，所有方法同一规则。

既有口径兼容辅助表（原gold、叶名＋分组/去重；不混入严格主表）

| 方法 | 同一预选题中原gold有效N | 原口径函数Top5 |
|---|---:|---:|
| D-SIMPLE | 49 | 91.84% |
| D-COSIL | 49 | 83.67% |
| Q-COSIL | 49 | 30.61% |
| Q-PRUNER | 49 | 32.65% |

原111/293只作300题历史背景；这里重新评分同一50题的本轮预测，不将两个不同题集的百分比直接相减。

表D：上下文与错误分解

| 方法 | Edit-set Recall | Context-file Recall | 完整gold函数可见率 | 无效输出题率 | agent无源码仍定位题率 | gold直剪实际事件 | 参考代码token均值 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | 98.00% | 98.00% | 97.92% | 2.00% | 0.00% | 0 | 28527 |
| D-COSIL | 94.00% | 92.00% | 82.64% | 22.00% | 0.00% | 0 | NA |
| Q-COSIL | 50.00% | 32.00% | 27.08% | 60.00% | 30.00% | 0 | NA |
| Q-PRUNER | 48.00% | 34.00% | 27.08% | 62.00% | 28.00% | 0 | NA |

已取回后误剪必须由gold目标与对应拒绝事件逐条对齐；单凭最终没命中无法归因误剪。上表gold直剪专指小裁判reject；本轮观测到的gold直剪事件为0；空事件表见lite_pilot_gold_direct_rejection_events.csv。源码返回、裁判看过、进入搜索请求三种事件在工具审计分列。

工具实际使用（全部动作与真实执行，exit单列；不是API原生tool_calls）

| 方法 | 动作响应 | 解析通过 | 真实执行 | 执行成功 | 返回源码 | 裁判收到 | agent收到 | 解析失败 | 工具错误 | DSML离线完整/全部 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D-COSIL | 411 | 330 | 301 | 298 | 298 | 296 | 185 | 81 | 3 | 43/68 |
| Q-COSIL | 400 | 367 | 367 | 233 | 233 | 231 | 105 | 33 | 134 | 0/0 |
| Q-PRUNER | 392 | 358 | 358 | 201 | 201 | 200 | 119 | 34 | 157 | 0/0 |

DeepSeek确有成功源码工具调用，也有DSML文本漏出；请求的CoSIL接口要求Python式文本，原解析器不支持DSML。其中结构完整、重复竖线偏离、缺标签、无效目标分别归档；离线辨识不追认成真实执行。Qwen也会调用，但可能给错文件、混用独立函数/类方法工具、重复同一错误参数。格式合格不保证目标存在，调用成功不保证定位正确。

表E：统一修复器与正式测试

| 上游 | 统一修复器 | N | 补丁解析 | 应用率 | Resolved@1 | 环境失败 | 单题总费 |
|---|---|---|---|---|---|---|---|
| D-SIMPLE / D-COSIL / Q-PRUNER | DeepSeek非思考（计划） | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

P0执行链为一题空补丁失败、gold补丁通过，只证明原生兼容测试可运行。Docker socket无权限，不冒充官方隔离harness的Resolved。P2外部100题/P3修复30题均不自动启动。

表F：定位成本与典型时延（修复未运行）

| 方法 | API USD/题（实际） | USD/题（峰时无缓存） | 平均输入/输出token | 平均请求数 | 平均秒 | 中位秒 [P25–P75] | P95秒 | GPU秒/题 |
|---|---:|---:|---:|---:|---:|---|---:|---|
| D-SIMPLE | 0.01399 | 0.02763 | 90357/432 | 7.00 | 11.39 | 8.36 [7.58–9.47] | 12.13 | NA |
| D-COSIL | 0.00920 | 0.02919 | 91338/1487 | 18.10 | 83.76 | 40.32 [24.14–172.27] | 192.34 | NA |
| Q-COSIL | NA | NA | 79199/1077 | 16.14 | 100.92 | 102.09 [73.00–132.12] | 155.19 | NA |
| Q-PRUNER | NA | NA | 80127/1044 | 11.86 | 127.06 | 122.22 [77.13–162.47] | 220.50 | NA |

Qwen本地GPU成本不视为0美元，只是本轮未折算；Q-PRUNER输入token包含专职裁判。成功完成子组、总token通常区间、各阶段请求时延、排队、首次加载、构图和传输重试见审计报告。客户端墙钟不能拆成纯GPU秒。P0有恢复重放，典型单题性能以新跑P1为准。

P0＋P1及工程试跑去重已知API费用：**$1.295082**（预算换算约¥9.066）；保守已计/预约上界$1.295082 / $10。未知计费尝试0次，未释放未知余额。复制的同request_id回执只计一次。

价格按[DeepSeek官方定价](https://api-docs.deepseek.com/quick_start/pricing/)的峰闲时、缓存命中/未命中和输出分别计算；跨时界或缓存字段不全采用上界并标注。模型actual usage为最终token账，请求前用经实际回执核验的官方V4离线分词器加包裹余量；费用预约仍用UTF8字节保守上界。

表G：可选High思考诊断

| 档位 | N | 函数Hit@5 | Recall@5 | 思考token | 费用 | 时延 |
|---|---|---|---|---|---|---|
| 本轮None | 见主表 | 见主表 | 见主表 | API缺失字段为null | 见表F | 见表F |
| High配对10题 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

表H：同题配对差异

| 对比 | 指标 | 配对N | A−B | issue bootstrap95% | 按仓cluster95% | A胜/B胜 | McNemar Holm p |
|---|---|---:|---:|---|---|---:|---:|
| D-SIMPLE vs D-COSIL | function_hit_5 | 41 | 9.76% | [2.44%, 19.51%] | [0.00%, 16.67%] | 4/0 | 0.2500 |
| D-SIMPLE vs D-COSIL | function_recall_5 | 41 | 9.35% | [2.03%, 18.29%] | [3.45%, 17.33%] | 4/0 | NA |
| D-SIMPLE vs Q-PRUNER | function_hit_5 | 41 | 65.85% | [51.22%, 80.49%] | [57.45%, 82.35%] | 27/0 | 0.0000 |
| D-SIMPLE vs Q-PRUNER | function_recall_5 | 41 | 63.41% | [48.78%, 78.05%] | [55.17%, 81.82%] | 27/0 | NA |
| Q-PRUNER vs Q-COSIL | function_hit_5 | 41 | 0.00% | [0.00%, 0.00%] | [0.00%, 0.00%] | 0/0 | 1.0000 |
| Q-PRUNER vs Q-COSIL | function_recall_5 | 41 | 0.00% | [0.00%, 0.00%] | [0.00%, 0.00%] | 0/0 | NA |

每项10,000次重采样，seed20261021。三项预设Hit@5精确双侧McNemar做Holm修正。未预设非劣界，p>0.05或区间跨0不证明等效；开发题量小、仓库分布偏斜，不能推广为全300题或全新任务的定论。

实现、部署问题与结论边界

- DeepSeek所有角色固定非思考；每请求显式thinking.disabled，无reasoning_effort，发现非空思考即停。API返回别名、/models名称与文档版本分别留档。
- D/Q-COSIL共享原文件反思、10轮导航、源码相关性判别和最终排名；本轮统一基础AST目录以明确方法/异步函数身份，区别于旧结构脚本的ast.walk嵌套叶名行为。因此不声称本轮与旧300题逐位完全一致。
- 旧代码存在格式纠正请求，按本方案semantic retry=0禁用；真实格式失败保留，不重跑选更好答案。DSML格式问题也保留原始结果，不事后救回提高主表。
- Q-PRUNER加载既有冻结SweRank epoch1（1:1），温度与0.6/0.9路由不调参，v6长输入及现场邻居。此前金丝雀曾止损，本轮仅探索对照，不称已验证冠军。与主agent同宗底座、CC-BY-NC许可及开发题同源偏乐观均需披露。
- v1冒烟修复隔离挂载/临时目录，v2修复HTTP复用，v3修复过保守的400K计量；旧run、失败和全部付费回执保留。官方分词器仅读取JSON，不执行下载代码。
- 金标与benchmark patch仅独立CPU评估器可见；推理namespace隐藏evaluator、封存数据、历史运行、矩阵和原Git。源码工具为AST白名单分派，不执行模型任意代码。

逐题与复现

代码：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1`；完整调用：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot`。按instance_id拼接，同一题各臂对照，不按文件行号。

- [逐题分析](lite_pilot_逐题分析.md)
- [工具与单题时长/token审计](lite_pilot_单题时长_token与工具使用审计.md)
- `lite_pilot_per_instance.csv`、`lite_pilot_method_summary.csv`、`lite_pilot_paired_comparisons.csv`
- `lite_pilot_tool_io_per_call.csv`、`lite_pilot_per_issue_runtime_tokens.csv`、`lite_pilot_stage_runtime_tokens.csv`
- 两张函数Hit/Recall与API成本图在 `figures/lite_pilot_*_vs_api_cost.png`。

CPU复现报告：`CUDA_VISIBLE_DEVICES="" python analysis/complete_reports.py --cohort lite_pilot`。该命令不生成预测、不执行测试。P2/P3/High维持NOT_RUN。
