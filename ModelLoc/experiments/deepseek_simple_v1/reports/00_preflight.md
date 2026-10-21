# 强模型简单流程与复杂定位对照实验报告

本报告阶段：smoke；run_id：20261021_nonthinking_v3。实际状态截至 2026-10-21T08:50:26.392782+00:00。

## 1. 一页结论

当前只执行 P0/P1。外部100题、修复30题和可选High诊断均为 **NOT_RUN，待独立阶段放行**。函数定位结果不能证明修复能力。

D-SIMPLE 为 CQ2-inspired simple baseline；整文件流程取自论文算法1和附录B，增加函数级排序。模型、题集、提示词与上下文细节不同，不复刻论文修复率。

## 2. 环境、数据和复现信息

冻结题集 5 题、12 个仓库。按仓分层、SHA256确定性抽样；5题冒烟与50题开发集不重叠，排除所有已发现封存test manifest中的issue。test未读取或哈希。

数据版本：`local-sha256:ff0e6c3b63c8c2237f3d3d29e7d11904a9cd075df7e9348b6001c207c88eabed`；当前上游revision仅记录来源，不冒称与带harness附加列的本地Arrow逐字相同。

正式文件gold限已有非测试Python源文件。函数gold按改动行和base/fixed AST映射，新增函数、模块级改动单列；主表仅完全可映射题，部分映射另报。所有方法同一gold和分母。无效预测、重复预测保留原排名槽位，Precision@k分母固定k。

## 3. 方法与实际参数

DeepSeek官方别名deepseek-flash，文档对应DeepSeek-V4.1-Flash-1017；/models返回较宽泛的DeepSeek-V4.1-Flash，分别留档。每次请求显式thinking=disabled且不传reasoning_effort；若返回思考内容则停。

D-SIMPLE：5独立同提示请求、哈希L0/L1/L2、交集空则L0；最多5整文件、80K o200k参考token，跳过超长整文件；一轮至多4固定字符串查询，每条至多2新文件、证据总12K。源码正文不插行号，外部标题记录路径、行范围和SHA。

D/Q-COSIL：保留文件反思、节点目录、至多10轮工具/剪枝、最终Top5；D侧全角色换同一个DeepSeek，Q侧7333原配置Qwen。语义格式重采样按本方案禁用，失败计入，未修补答案。上下文能力差异属于实际系统比较，不能解读为等上下文因果实验。

Q-PRUNER：沿用最新已冻结SweRank epoch1，温度1.74059755321、0.6/0.9默认路由及v6长输入/现场邻居摘要。该检查点此前金丝雀止损，作为既有探索方案对照，不称已验证优胜者；本轮不重新选择。

## 4. 文件级定位结果

| 方法 | 已运行/分配 | Hit@1 | Hit@3 | Hit@5 | Recall@5 | Precision@5 | F1@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | 5/5 | 80.00% | 80.00% | 80.00% | 80.00% | 16.00% | 26.67% | 80.00% | 80.00% |
| D-COSIL | 5/5 | 60.00% | 80.00% | 80.00% | 80.00% | 16.00% | 26.67% | 80.00% | 70.00% |
| Q-COSIL | 5/5 | 40.00% | 40.00% | 40.00% | 40.00% | 8.00% | 13.33% | 40.00% | 40.00% |
| Q-PRUNER | 5/5 | 40.00% | 40.00% | 40.00% | 40.00% | 8.00% | 13.33% | 40.00% | 40.00% |

## 5. 函数级定位结果

| 方法 | 严格N/部分N | Hit@1 | Hit@3 | Hit@5 [95%CI] | Recall@5 | Precision@5 | F1@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| D-SIMPLE | 2/2 | 50.00% | 100.00% | 100.00% [100.00%, 100.00%] | 100.00% | 20.00% | 33.33% | 100.00% | 75.00% |
| D-COSIL | 2/2 | 50.00% | 100.00% | 100.00% [100.00%, 100.00%] | 100.00% | 20.00% | 33.33% | 100.00% | 75.00% |
| Q-COSIL | 2/2 | 0.00% | 0.00% | 0.00% [0.00%, 0.00%] | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| Q-PRUNER | 2/2 | 0.00% | 0.00% | 0.00% [0.00%, 0.00%] | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

部分可映射题只在辅助表计其可映射目标；不与完全可映射主分母混合。更多k=1/3/5/10指标见method_summary.csv。

## 6. 单次补丁生成与测试结果

| 上游方案 | 统一修复器 | 预选N | Resolved@1 | 状态 |
|---|---|---:|---|---|
| D-SIMPLE / D-COSIL / Q-PRUNER | DeepSeek非思考（计划） | NOT_RUN | NOT_RUN | P3未授权启动；Docker socket无权限 |

P0单题执行链只核验原生兼容环境可否运行FAIL_TO_PASS（空补丁失败、gold补丁通过），不计为模型修复成果，不替代后续官方容器判定。

## 7. Token、费用、计算量和时延

| 方法 | 输入/输出token | API实际USD | 统一峰时未缓存USD | 中位/P95秒 | 状态分布 |
|---|---:|---:|---:|---:|---|
| D-SIMPLE | 547124/2168 | 0.087718656 | 0.1667388 | 138.6175075666979/139.8120852738619 | {'complete': 5} |
| D-COSIL | 449768/7379 | 0.047522544 | 0.1437852 | 183.22171282488853/326.2616240205243 | {'complete': 5} |
| Q-COSIL | 372437/4328 | None | None | 96.47818732168525/118.10174059979617 | {'complete': 4, 'failed': 1} |
| Q-PRUNER | 368139/4262 | None | None | 116.57742404099554/171.64651973228902 | {'complete': 4, 'failed': 1} |

API美元按[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)：缓存/未缓存/输出分别按峰闲时计费。跨价时边界或缺缓存字段的费用单列保守上界，不伪称精确账单。7 CNY/USD只作预算换算。未知计费失败请求保留最坏预算；全阶段$10、每题每API臂¥0.5软/¥1.5硬限，累计400Ktoken；输入按UTF8字节保守预约，可能早于真实token上限触发。

GPU0用于7333主Qwen，GPU2用于冻结裁判；不使用GPU1、不动他人进程。墙钟时延含队列、CPU构图与首次模型加载，不能当GPU计算秒；未取得直接GPU计算时长则标NA，本地算力不冒称免费。

## 7.1 可选10题High思考诊断

NOT_RUN：未获额外授权，不自动启动。

## 8. 同题配对比较与不确定性

| 对比 | 指标 | 严格配对N | 均值差 | issue bootstrap95% | 按仓cluster95% | A胜/B胜 |
|---|---|---:|---:|---|---|---:|
| D-SIMPLE vs D-COSIL | function_hit_5 | 2 | 0.00% | [0.0, 0.0] | [0.0, 0.0] | 0/0 |
| D-SIMPLE vs D-COSIL | function_recall_5 | 2 | 0.00% | [0.0, 0.0] | [0.0, 0.0] | 0/0 |
| D-SIMPLE vs Q-PRUNER | function_hit_5 | 2 | 100.00% | [1.0, 1.0] | [1.0, 1.0] | 2/0 |
| D-SIMPLE vs Q-PRUNER | function_recall_5 | 2 | 100.00% | [1.0, 1.0] | [1.0, 1.0] | 2/0 |
| Q-PRUNER vs Q-COSIL | function_hit_5 | 2 | 0.00% | [0.0, 0.0] | [0.0, 0.0] | 0/0 |
| Q-PRUNER vs Q-COSIL | function_recall_5 | 2 | 0.00% | [0.0, 0.0] | [0.0, 0.0] | 0/0 |

每项10,000次同题重采样，固定seed20261021。三项预设Hit@5对比的精确双侧McNemar作Holm修正，见CSV。没有预设非劣界；区间跨0或p>0.05不能证明等效。Lite开发题与既有训练/反复分析同源，只支持可行性结论。

## 9. 失败分解和代表案例

| 方法 | Edit-set Recall | Context-file Recall | 完整gold函数可见率 | 无效输出率 | 未给agent源码仍定位 | gold直接剪掉事件 |
|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | 80.00% | 80.00% | 100.00% | 0.00% | 0.00% | 0 |
| D-COSIL | 80.00% | 60.00% | 75.00% | 20.00% | 20.00% | 0 |
| Q-COSIL | 40.00% | 20.00% | 25.00% | 80.00% | 20.00% | 0 |
| Q-PRUNER | 40.00% | 20.00% | 25.00% | 60.00% | 40.00% | 0 |
- `Q-COSIL/matplotlib__matplotlib-24149`：ValueError，CoSIL semantic format retry disabled by protocol；证据 `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-COSIL/matplotlib__matplotlib-24149`。
- `Q-PRUNER/matplotlib__matplotlib-24149`：ValueError，CoSIL semantic format retry disabled by protocol；证据 `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-PRUNER/matplotlib__matplotlib-24149`。

工具读到、裁判收到、搜索agent最终看到源码分开记录。没有逐事件证据时不将漏召回写成误剪因果。模型能根据函数名给出定位，因此源码未读而输出不代表实际检索成功。

## 10. 对后续研究的建议与结论边界

先依据同题流程差与成本判断简单流程竞争力，再在独立外部集和统一修复器上确认。文件召回、函数选择、上下文可见和测试修复是不同终点。本轮不训练、不改既有数据/历史矩阵、不解封test、不根据分数重新筛题。

## 11. 复现命令、产物路径和未完成事项

代码和提示词：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1`；原始调用和逐题结果：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke`；明细/成本/配对表：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/reports`。

复现：`python -m src.cli run-localization --cohort smoke`；报告：`python -m src.cli report --cohort smoke`。

P2/P3/High均NOT_RUN。外部数据revision/样本manifest仅在阶段准备时冻结，不将未运行外部结果混入当前表。所有分数可追溯至逐题result、calls原始响应与evaluator_private金标证据。
