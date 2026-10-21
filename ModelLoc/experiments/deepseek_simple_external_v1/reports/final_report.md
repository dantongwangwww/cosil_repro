# 强模型简单流程与复杂定位：独立外部验证报告

更新：2026-10-21T14:38:16.860496+00:00。集合：**external**；run：`20261021_external_nonthinking_v1`；实际落盘400/400个“题×方法”结果。四臂均已执行，真实失败仍计分母。

本轮仅执行P2外部定位验证；P3修复与High思考诊断均为 **NOT_RUN**。函数定位不是修复成功率，未执行的测试与修复不填0。

## 主要观察

- **D-SIMPLE**：函数Hit@5 80.43%，Macro-Recall@5 75.00%；已执行100/100，严格可映射已执行/分配46/46；状态`{'complete': 100}`。
- **D-COSIL**：函数Hit@5 76.09%，Macro-Recall@5 70.29%；已执行100/100，严格可映射已执行/分配46/46；状态`{'complete': 94, 'failed': 5, 'budget_exceeded': 1}`。
- **Q-COSIL**：函数Hit@5 39.13%，Macro-Recall@5 29.65%；已执行100/100，严格可映射已执行/分配46/46；状态`{'failed': 30, 'complete': 70}`。
- **Q-PRUNER**：函数Hit@5 28.26%，Macro-Recall@5 21.92%；已执行100/100，严格可映射已执行/分配46/46；状态`{'failed': 34, 'complete': 66}`。

## 表A：数据来源、独立性与执行完整性

| 集合 | 预选题数 | 实际唯一仓数 | 文件gold有效 | 函数完全映射 | 部分映射 | 不可映射 | 已落盘/分配 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 外部验证 | 100 | 100 | 99 | 46 | 38 | 16 | 400/400 |

| 冻结数据项 | 实际值 |
|---|---|
| Hugging Face repo | `nebius/SWE-rebench-leaderboard` |
| revision | `34d5a58864acf91613740a09ec5d205228dcfa39` |
| config / split | `default` / `test` |
| 原始行数 / 仓库数 | 860 / 413 |
| Parquet SHA256 | `1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf` |
| external manifest SHA256 | `fc43ba005b6aafbc784b4a98a1a472c2c4c6f5a507769f66a5c2ed3326154a07` |
| resolved config SHA256 | `d0f904c788df524ae5a7eabc4b84509d23e4036a3a4e8953f961a23aa07ea0e0` |
| 既有公开历史 ID 联合（隔离依据） | 707 |
| 既有开发/实验仓库排除数 | 12 |
| HiFL 既往 CPU 公开PR核验对象 | 30；仅加精确repo#PR、repo@base排除，不称训练样本 |
| split manifest 中封存test ID联合 | 48；只读manifest ID，不读test内容 |
| 当前选中题历史仓库 / ID重叠 | 0 / 0 |
| 候选审计状态计数 | {'selected': 100, 'excluded': 78, 'not_selected_prefetched': 3, 'not_examined': 679} |
| 候选排除原因计数（可重叠） | {'history_repository': 56, 'one_issue_per_repository': 22, 'cohort_complete': 682} |
| PR时间范围 | 2025-01-03 02:20:50 至 2026-05-07 19:33:12 |

707历史ID是Lite/Verified公开题元数据的联合，不表示707题全部训练过；它们用于保守隔离。同样，HiFL的30个对象是此前**CPU数据总览/公开PR证据核验**，没有用于训练、验证或模型开发，不把整仓误标为训练仓。实际剔除与资格失败明细在私有候选审计表，不能将多重原因计数相加当不同题数。

本题集按独立仓库选取，每仓一题；不属于CQ2论文原始题集。仓库、base commit、来源记录与筛选规则以本目录冻结manifest和资格审计为准。`created_at`为**PR时间**，不能写成issue创建时间。跨仓独立用于减少既有实验仓库重叠，**不保证基础模型预训练未见过这些仓库或PR**。

文件gold仅既有非测试Python源文件；函数gold用补丁实际改动行＋base/fixed AST，新增函数和模块级修改单列。完全可映射作为严格主分母；部分/不可映射不混入主表。失败保留已执行分母；未执行为NOT_RUN。每臂同一题集与评估器，不按结果换题。

## 冻结方法与比较边界

模型、提示词、工具分派解析器（包括既有DSML不兼容处理）、semantic retry=0、上下文与预算上限均沿用已冻结方案，不根据外部结果改动。DeepSeek显式`thinking.disabled`且不传reasoning_effort；别名、API返回名与文档版本分别留档。Qwen为Qwen2.5-Coder-7B-Instruct。

D-SIMPLE是**CQ2-inspired simple baseline**：五次同提示文件选择、哈希角色、交集与回退、整文件阅读、一次函数级排名；最多5整文件、80K参考token，一轮最多4固定查询与12K证据，超长整文件跳过。新增函数级输出，不复刻论文修复率。

D/Q-COSIL保留文件选择与导入反思、节点菜单、最多10轮导航、源码相关性判断与最终排序；三组CoSIL臂共用同一基础AST目录。工具白名单只分派取源码/元数据，不执行模型任意代码。能力和上下文差异属于实际系统比较，不能称等上下文因果试验。

Q-PRUNER固定SweRank epoch1（1:1）、温度`1.740597553206586`、0.6/0.9路由和v6长输入/现场邻居摘要。该检查点此前金丝雀曾止损，本轮作为既有探索对照，不声称已验证冠军；无训练/调阈值/重新挑选checkpoint。

## 表B：文件级结果

| 方法 | 已执行/分配 | Hit@1 | Hit@3 | Hit@5 | Recall@5 | Precision@5 | F1@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | 100/100 | 73.74% | 85.86% | 87.88% | 82.79% | 20.61% | 31.86% | 76.77% | 79.87% |
| D-COSIL | 100/100 | 75.76% | 83.84% | 86.87% | 81.36% | 20.20% | 31.27% | 75.76% | 79.83% |
| Q-COSIL | 100/100 | 47.47% | 52.53% | 55.56% | 50.57% | 12.12% | 19.03% | 46.46% | 50.54% |
| Q-PRUNER | 100/100 | 44.44% | 48.48% | 51.52% | 47.04% | 11.31% | 17.73% | 43.43% | 47.00% |

## 表C：函数级严格主表

| 方法 | 严格已执行/分配N | Hit@1 | Hit@3 | Hit@5 [95%CI] | Macro-Recall@5 | Precision@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| D-SIMPLE | 46/46 | 71.74% | 80.43% | 80.43% [69.57%, 91.30%] | 75.00% | 23.91% | 33.49% | 71.74% | 76.00% |
| D-COSIL | 46/46 | 69.57% | 76.09% | 76.09% [63.04%, 86.96%] | 70.29% | 22.61% | 31.37% | 65.22% | 72.83% |
| Q-COSIL | 46/46 | 34.78% | 36.96% | 39.13% [26.09%, 54.35%] | 29.65% | 9.57% | 13.18% | 23.91% | 36.05% |
| Q-PRUNER | 46/46 | 28.26% | 28.26% | 28.26% [15.22%, 41.30%] | 21.92% | 6.96% | 9.84% | 17.39% | 28.26% |

部分可映射题辅助Hit@5：D-SIMPLE 86.84% (N=38)；D-COSIL 81.58% (N=38)；Q-COSIL 34.21% (N=38)；Q-PRUNER 31.58% (N=38)。全部k=1/3/5/10指标见CSV。

身份严格匹配`path::qualified_name`。相同限定名property getter/setter共享一个身份；无效、重复项不前移补槽，Precision@k固定除以k。沿用P1报告层的统一身份修正；不调用Lite旧gold或叶名兼容评分。

## 表D：上下文、安全与工具行为

| 方法 | Edit-set Recall | Context-file Recall | 完整gold函数可见率 | 无效输出题率 | agent未收源码仍定位题率 | 小裁判gold直剪事件 | 灰区比例 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | 83.05% | 88.86% | 85.78% | 10.00% | 0.00% | 0 | NA |
| D-COSIL | 81.36% | 70.82% | 66.14% | 31.00% | 7.00% | 0 | NA |
| Q-COSIL | 50.57% | 35.35% | 29.50% | 54.00% | 22.00% | 0 | NA |
| Q-PRUNER | 47.04% | 38.72% | 29.60% | 50.00% | 18.00% | 0 | 22.54% |

gold直剪仅计已取回的gold身份与小裁判reject事件逐条对齐；不凭最终漏召回推断误剪。即使为0，`external_gold_direct_rejection_events.csv`也保留表头。

| 方法 | 动作响应 | 解析通过 | 真实执行 | 成功/返回源码 | 裁判/agent收到源码 | 解析失败 | 工具错误 | DSML动作/离线结构完整 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D-COSIL | 852 | 643 | 591 | 583/583 | 578/331 | 209 | 8 | 215/112 |
| Q-COSIL | 700 | 680 | 680 | 501/501 | 487/174 | 20 | 179 | 0/0 |
| Q-PRUNER | 675 | 642 | 642 | 468/468 | 464/197 | 33 | 174 | 0/0 |

这些CoSIL工具为文本DSL，不是API原生tool_calls。逐条检验参数是否匹配base文件/类/函数、返回文本与base源码一致性，以及源码是否出现在之后真正发送成功的搜索请求中。DSML仅离线辨识，**不执行或救回答案**；模型提出调用、框架取回、裁判看到和搜索agent收到分别计数。

## 表E：统一修复与正式测试

| 上游 | 统一修复器 | N | 补丁解析 | 补丁应用 | Resolved@1 | 环境失败 | 状态 |
|---|---|---|---|---|---|---|---|
| D-SIMPLE / D-COSIL / Q-PRUNER | DeepSeek非思考（计划） | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | P3未启动 |

外部定位阶段没有执行修复器或测试。既有执行链自检不能替代外部模型修复成绩。

## 表F：单题成本、token与典型耗时

| 方法 | API实际USD/题 | 峰时无缓存USD/题 | 平均输入/输出token | 平均总token | 总token中位[P25–P75] | 平均秒 | 中位秒[P25–P75] | P95秒 |
|---|---:|---:|---:|---:|---|---:|---|---:|
| D-SIMPLE | 0.00450 | 0.01464 | 46648/541 | 47188 | 35802 [22500–71290] | 7.58 | 7.33 [6.66–8.49] | 9.94 |
| D-COSIL | 0.00392 | 0.02465 | 76103/1516 | 77619 | 65040 [52488–90916] | 29.90 | 23.40 [20.19–26.98] | 35.97 |
| Q-COSIL | NA | NA | 52712/1063 | 53775 | 54137 [5334–71795] | 83.90 | 81.43 [43.85–110.65] | 163.26 |
| Q-PRUNER | NA | NA | 51548/1031 | 52579 | 53656 [5334–73178] | 86.34 | 83.84 [46.58–107.73] | 172.25 |

“大多时候”用中位数与P25–P75，长尾用均值/P95。实际usage累计包含反复发送的上下文；Q-PRUNER另计小裁判实际前向输入token。完成子组和全部执行子组、每阶段请求时延、队列/首次加载/CPU构图与传输错误另见[审计](external_单题时长_token与工具使用审计.md)。客户端墙钟不是纯GPU运算秒；本地GPU成本未货币化，不伪称0成本。

仅外部P2回执按request_id去重：已知实际费用 **$0.842343**，预算汇率7折合¥5.896；保守已计/预约$1.684686，本地ledger上限30.0 USD；授权P2/P3共用上限为 **$30**。未知计费尝试0次，缺实际成本回执0份，未知余额不释放。P0/P1不混入本账。

按[DeepSeek官方定价](https://api-docs.deepseek.com/quick_start/pricing/)分别计缓存、未缓存和输出及峰闲时；字段缺失/跨边界按保守规则披露。请求前token由冻结官方V4分词器计数加包裹余量，费用预约使用UTF8字节上界。余额不是花费授权。

## 表G：可选思考诊断

| 档位 | N | 函数Hit@5 | Recall@5 | 思考token | 费用 | 时延 |
|---|---|---|---|---|---|---|
| 本轮非思考 | 见表A–C | 见表C | 见表C | 缺失字段保持null | 见表F | 见表F |
| High配对10题 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

## 表H：同题配对差异与不确定性

| 对比 | 指标 | 配对N | A−B | issue bootstrap95% | 按仓cluster95% | A胜/B胜 | McNemar Holm p |
|---|---|---:|---:|---|---|---:|---:|
| D-SIMPLE vs D-COSIL | function_hit_5 | 46 | 4.35% | [0.00%, 10.87%] | [0.00%, 10.87%] | 2/0 | 0.5000 |
| D-SIMPLE vs D-COSIL | function_recall_5 | 46 | 4.71% | [-1.45%, 11.96%] | [-1.45%, 11.96%] | 2/0 | NA |
| D-SIMPLE vs Q-PRUNER | function_hit_5 | 46 | 52.17% | [36.96%, 67.39%] | [36.96%, 67.39%] | 24/0 | 0.0000 |
| D-SIMPLE vs Q-PRUNER | function_recall_5 | 46 | 53.08% | [38.59%, 66.85%] | [38.76%, 66.85%] | 24/0 | NA |
| Q-PRUNER vs Q-COSIL | function_hit_5 | 46 | -10.87% | [-19.57%, -2.17%] | [-19.57%, -2.17%] | 0/5 | 0.1250 |
| Q-PRUNER vs Q-COSIL | function_recall_5 | 46 | -7.73% | [-15.70%, -1.21%] | [-15.94%, -1.21%] | 0/5 | NA |

10,000次配对重采样，seed20261021；三项预设Hit@5精确双侧McNemar做Holm修正。每仓一题时，按仓cluster与issue重采样代表相同抽样单位；不将两种CI称为独立证据。未预设非劣界，p>0.05或CI跨0不证明等效。尚未完成的阶段快照配对只包括两臂都已执行题，可能有进度选择偏差。

## 失败、实施问题与可推广范围

- 外部跨仓集合与Lite开发集合独立，允许检验方法在新仓上的稳定性；题目规模、来源筛选、Python限制和可映射gold规则仍限制推广。基础模型是否见过源码/PR未知，不能声称无预训练泄漏。
- 直接工具格式失败、目标不存在、源码被裁判拒绝、未传到搜索agent和最后排名错误分别保留证据；不把所有错误归为模型推理，也不把工具成功当定位成功。
- 沿用P1修正后的基础AST/异步与限定名身份；三组CoSIL一致，不冒称与旧300题上游结构脚本逐位等价。
- 旧模型、提示、冻结温度阈值和DSML解析器保持不变；不根据外部表现调参、复抽题目或重采样错误答案。SweRank与主agent同宗底座、CC-BY-NC限制和先前止损均保留披露。
- evaluator_private中的patch/gold/资格元数据不对推理worker暴露。pruner test封存、不读取或哈希；不改P1源码/提示/预测/报告、不动历史矩阵，不启动P3。

| 方法 | 已记录失败类型 |
|---|---|
| D-SIMPLE | {} |
| D-COSIL | {'ValueError': 4, 'BudgetExceeded': 1, 'RuntimeError': 1} |
| Q-COSIL | {'ValueError': 29, 'RuntimeError': 1} |
| Q-PRUNER | {'ValueError': 33, 'RuntimeError': 1} |
- `Q-COSIL/lincc-frameworks__nested-pandas-190`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/lincc-frameworks__nested-pandas-190`。
- `Q-PRUNER/lincc-frameworks__nested-pandas-190`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/lincc-frameworks__nested-pandas-190`。
- `Q-COSIL/scverse__spatialdata-822`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/scverse__spatialdata-822`。
- `Q-PRUNER/scverse__spatialdata-822`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/scverse__spatialdata-822`。
- `Q-COSIL/openai__openai-agents-python-2144`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/openai__openai-agents-python-2144`。
- `Q-PRUNER/openai__openai-agents-python-2144`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/openai__openai-agents-python-2144`。
- `D-COSIL/omni-us__jsonargparse-707`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/omni-us__jsonargparse-707`。
- `Q-COSIL/omni-us__jsonargparse-707`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/omni-us__jsonargparse-707`。
- `Q-PRUNER/omni-us__jsonargparse-707`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/omni-us__jsonargparse-707`。
- `Q-COSIL/dag-hammarskjold-library__dlx-512`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/dag-hammarskjold-library__dlx-512`。
- `Q-PRUNER/dag-hammarskjold-library__dlx-512`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/dag-hammarskjold-library__dlx-512`。
- `Q-COSIL/schemathesis__schemathesis-3405`：ValueError；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/schemathesis__schemathesis-3405`。

## 产物与复现

- [逐题逐臂分析](external_逐题分析.md)
- [真实工具I/O、单题耗时与token](external_单题时长_token与工具使用审计.md)
- `external_per_instance.csv`、`external_method_summary.csv`、`external_paired_comparisons.csv`、`external_cost_ledger.csv`
- `external_gold_direct_rejection_events.csv`、`external_per_issue_runtime_tokens.csv`、`external_tool_io_per_call.csv`、`external_stage_runtime_tokens.csv`
- 两张函数Hit/Recall对API成本图：`figures/external_*_vs_api_cost.png`。

CPU报告命令（不启动推理或测试）：`CUDA_VISIBLE_DEVICES="" python -m external_v1.report`；等待当前已授权执行收尾再报告：加`--wait`。代码根：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1`。

执行完成marker：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external_execution_completion.json`；marker内容：`{'run_id': '20261021_external_nonthinking_v1', 'cohort': 'external', 'status': 'complete', 'overall_status': 'complete', 'started_at': '2026-10-21T12:13:07.517558+00:00', 'ended_at': '2026-10-21T14:38:01.369277+00:00', 'finished_at': '2026-10-21T14:38:01.369277+00:00', 'elapsed_seconds': 8693.851736139506, 'allocated': 400, 'expected_count': 400, 'result_count': 400, 'completed_count': 400, 'completed': True, 'counts': {'D-SIMPLE/complete': 100, 'D-COSIL/complete': 94, 'Q-COSIL/failed': 30, 'Q-PRUNER/failed': 34, 'Q-COSIL/complete': 70, 'Q-PRUNER/complete': 66, 'D-COSIL/failed': 5, 'D-COSIL/budget_exceeded': 1}, 'missing': [], 'owned_service_shutdown': {'status': 'stopped', 'pid': 2602848, 'returncode': 0, 'owned_only': True, 'stopped_at': '2026-10-21T14:37:56.004402+00:00'}, 'source_verification_passed': True, 'test_stats_unchanged': True, 'P3_started': False, 'High_started': False, 'financial_stop': False, 'error_type': None, 'error_message': None}`。报告是否完整以逐题落盘统计为准，不把空marker当全完成。
