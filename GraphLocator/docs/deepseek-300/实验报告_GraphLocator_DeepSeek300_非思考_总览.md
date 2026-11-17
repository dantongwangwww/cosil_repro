# GraphLocator DeepSeek-V4.1-Flash 全量实验总览

生成时间：2026-10-12T18:46:18.571523+08:00。本次使用 DeepSeek 官方 API，模型 ID `deepseek-flash`，关闭思考模式 `thinking=disabled`，temperature=0，当前批准的累计费用上限 **69.93 元**。

本阶段计划 300 题，完成 299，运行失败 1，缺少结果 0。

本次保留此前 120 题的最终结果，继续原来未完成的 180 题；续跑前后逐文件 SHA-256 核查，既有结果未重跑或改写。此前20元限额的阶段报告和Excel实验列仍保留，完整300题另加新列。

## 流程与可比范围

沿用最终 Qwen 适配v2 的 B2：同一 SWE-bench Lite issue ID、同一 base commit、仓库图、搜索规则、候选分页、相关性判定与原版 Mermaid 因果流程。源码批次仍用 Qwen 分词器估算大小，它只参与分页，不执行 Qwen 推理。

本次同时更换模型与供应商、关闭思考、保留与 Qwen B2 相同的答案输出上限，并使用官方 1M 上下文。搜索/相关性采用 DeepSeek `json_object` 和显式 schema 提示，再经过原有客户端校验；它不等同于 Qwen 服务的强制 JSON Schema 解码。因此结果衡量的是这套 DeepSeek 部署配置，不能把所有差异归因于模型权重。

七个既有固定金丝雀只检查工程可运行性，不按命中率挑选题目或方案。同一冻结版本的金丝雀结果复用于全量，避免重复付费；提示、原始响应、用量及指纹全部保留。评分阶段才读取真值。

## 论文与本次复现的集合指标对照（SWE-bench Lite）

以下选取论文表2中与本次实验相同的SWE-bench Lite基准，论文计划300题，本次也计划300题。论文行直接抄录论文汇总值；复现行使用作者仓库提供的三层实体真值。指标按逐题计算后宏平均，F1不是表中宏平均P、R再次取调和平均。

| 来源 / 模型（均为GraphLocator） | 层级 | 该层级评分题数 | 精确率 PRE | 召回率 REC | F1 | SL |
|---|---|---:|---:|---:|---:|---:|
| 论文 / GPT-4o | 文件 | 300 | 48.90% | 83.67% | 56.76% | 83.67% |
| 论文 / Claude-3.5 | 文件 | 300 | 45.81% | 89.33% | 55.17% | 89.33% |
| 本次复现 / DeepSeek-V4.1-Flash 非思考 | 文件 | 300 | 49.83% | 87.67% | 58.94% | 87.67% |
| 论文 / GPT-4o | 模块/类 | 表2未单列 | 41.01% | 71.78% | 47.83% | 70.67% |
| 论文 / Claude-3.5 | 模块/类 | 表2未单列 | 38.63% | 81.78% | 46.82% | 80.44% |
| 本次复现 / DeepSeek-V4.1-Flash 非思考 | 模块/类 | 225 | 45.56% | 80.89% | 53.42% | 79.56% |
| 论文 / GPT-4o | 函数 | 表2未单列 | 20.82% | 63.18% | 27.29% | 60.65% |
| 论文 / Claude-3.5 | 函数 | 表2未单列 | 20.51% | 73.23% | 27.73% | 70.76% |
| 本次复现 / DeepSeek-V4.1-Flash 非思考 | 函数 | 277 | 27.92% | 72.44% | 35.84% | 69.68% |

来源：[用户提供PDF，第12页表2](../GraphLocator_Graph-Guided_Causal_Reasoning_for_Issue_Localization_FSE2026_2512.22469.pdf)；[arXiv论文表2及第4节评测设置](https://arxiv.org/html/2512.22469v1)。论文模型版本按原文记录为 `gpt-4o-2024-1120` 和 `claude-3-5-sonnet-20241022`，temperature=0。

本次无该层级真值的题为NA，空定位和运行失败计0；SL表示完整覆盖全部该层级目标。本次作者实体真值中模块/类适用225题、函数适用277题；论文表2未单列这两个层级的有效分母及无真值处理细节，因此未把本次分母直接填入论文行。

从汇总数值看，本次函数F1为 35.84%，比论文GPT-4o的27.29%高 **8.55个百分点**，比Claude-3.5的27.73%高 **8.11个百分点**。本次函数召回率 72.44% 略低于论文Claude-3.5的73.23%，精确率 27.92% 高于其20.51%，所以并非所有指标都更高。

该表用于文献汇总值与复现值的参考对比。模型、上下文与结构化输出协议、工程适配及有效评分分母尚未完全对齐；论文声明因果阶段最多20轮，本次冻结B2代码实际允许21次更新，另有初始图生成。论文只提供汇总分，当前没有对应逐题预测，无法按下面的293题严格口径重评分或做配对显著性检验。上述数值差不构成DeepSeek本身优于GPT-4o或Claude-3.5的受控实验结论。

论文表2没有提供本报告口径的Top-1/3/5成绩，其SL是全部真值被预测集合覆盖，与Top-k命中率含义不同。下面的293题严格函数表和Top-k表继续比较本地实验；论文汇总值单列于本表。

## 与既有实验使用相同评分口径

| 项目/条件 | 函数评分题数 | 精确率 | 召回率 | F1 | SL |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 293 | 7.77% | 28.61% | 11.69% | 25.94% |
| CoSIL/off | 293 | 8.57% | 28.85% | 12.57% | 25.94% |
| GraphLocator/Qwen | 293 | 4.79% | 7.41% | 5.28% | 7.17% |
| GraphLocator/Qwen-适配v2 | 293 | 10.71% | 17.24% | 12.06% | 16.04% |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 293 | 25.73% | 66.50% | 32.79% | 62.12% |

严格函数评分依据 base commit 的 AST 解析限定名；同名歧义预测计假阳性，不能借助真值消歧。共同完整 300 题的函数真值适用 293 题，作者原生适用 277 题；这两套分母和分数不可混用。

| 项目/条件 | Top-1 命中数 | Top-3 命中数 | Top-5 命中数 |
|---|---:|---:|---:|
| CoSIL/on | 80 | 103 | 106 |
| CoSIL/off | 75 | 105 | 111 |
| GraphLocator/Qwen | 15 | 24 | 25 |
| GraphLocator/Qwen-适配v2 | 33 | 53 | 57 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 102 | 165 | 191 |

Top-k 沿用对照表的文件+函数叶名兼容口径，候选中的类/变量也占排序位置。CoSIL 文件候选入口与 GraphLocator 全库检索入口不同。

相对 Qwen 适配v2，严格函数 F1 配对平均差 **+20.73%**，bootstrap 5000 次（seed 0）95% 区间 [+16.86%, +24.49%]；改善 166 题，退化 33 题，不变 94 题。

| 固定子集 | Qwen B2 函数 F1 | DeepSeek 非思考函数 F1 | 配对差及 95% 区间 |
|---|---:|---:|---|
| 既有开发30题 | 12.62% | 34.62% | +22.00% [+8.76%, +34.39%] |
| 既有验证270题 | 12.00% | 32.58% | +20.59% [+16.43%, +24.73%] |

Qwen B2 由既有开发30题选定；本次模型参数依据用户选择、费用与工程兼容性确定，没有按这300题最终命中率优化提示。验证270题提供独立于既有Qwen开发选择的比较。

## 按项目拆分

| 仓库 | 计划题数 | 函数评分题数 | 严格 P | 严格 R | 严格 F1 | SL |
|---|---:|---:|---:|---:|---:|---:|
| astropy/astropy | 6 | 6 | 22.22% | 41.67% | 27.78% | 33.33% |
| django/django | 114 | 110 | 25.17% | 69.24% | 33.65% | 67.27% |
| matplotlib/matplotlib | 23 | 23 | 21.83% | 73.19% | 28.55% | 69.57% |
| mwaskom/seaborn | 4 | 4 | 36.25% | 100.00% | 51.67% | 100.00% |
| pallets/flask | 3 | 3 | 63.33% | 100.00% | 74.60% | 100.00% |
| psf/requests | 6 | 6 | 24.14% | 66.67% | 29.25% | 66.67% |
| pydata/xarray | 5 | 5 | 26.78% | 80.00% | 31.86% | 80.00% |
| pylint-dev/pylint | 6 | 6 | 35.00% | 91.67% | 49.21% | 83.33% |
| pytest-dev/pytest | 17 | 16 | 30.64% | 83.33% | 41.27% | 75.00% |
| scikit-learn/scikit-learn | 23 | 23 | 33.40% | 71.74% | 38.88% | 60.87% |
| sphinx-doc/sphinx | 16 | 16 | 30.58% | 68.75% | 37.20% | 56.25% |
| sympy/sympy | 77 | 75 | 20.84% | 50.67% | 24.97% | 46.67% |

相对 Qwen B2 变化最大的例子：

| issue | Qwen F1 | DeepSeek F1 | 差值 |
|---|---:|---:|---:|
| django__django-16139 | 0.00% | 100.00% | +100.00% |
| pydata__xarray-5131 | 0.00% | 100.00% | +100.00% |
| pytest-dev__pytest-7432 | 0.00% | 100.00% | +100.00% |
| scikit-learn__scikit-learn-14087 | 0.00% | 100.00% | +100.00% |
| sphinx-doc__sphinx-8506 | 0.00% | 100.00% | +100.00% |
| django__django-12453 | 100.00% | 22.22% | -77.78% |
| django__django-16046 | 100.00% | 22.22% | -77.78% |
| sympy__sympy-20154 | 100.00% | 25.00% | -75.00% |
| sympy__sympy-18189 | 100.00% | 28.57% | -71.43% |
| django__django-13658 | 66.67% | 0.00% | -66.67% |

具体预测、真值和源代码送达阶段见逐题分析，差值本身不能单独证明因果归因。

## 费用与调用证据

本次模型切换的累计官方 CNY 余额差为 **68.4600 元**，最新余额 1.4700 元；包括此前修复和已停止 high 模式的费用，也可能包含同账户期间其他调用，作为共同 69.93 元预算的保守扣减证据。它不是单独的非思考条件费用。

续跑前根据用户明确充值并继续的指示，累计授权额度按新观察到的净余额增量扩展；`initial_balance_cny` 作为累计资金基准，原始20元余额、此前用量和费用均保留。净余额增量不等同于准确充值账单，可能含延迟扣费；该调整不会把旧支出清零。

```json
[
  {
    "authorized_at": "2026-10-12T15:47:59.127517+08:00",
    "authorization": "User explicitly said account recharged and requested continuation",
    "previous_observed_balance_cny": 0.16,
    "current_observed_balance_cny": 50.09,
    "net_balance_increase_cny": 49.93,
    "new_cumulative_budget_cny": 69.93,
    "accounting": "Net observed balance increase, not a claim of exact recharge amount; late billing may be included. Original receipts and usage counters remain unchanged."
  }
]
```

本阶段返回 5015 次模型响应，输入 30,397,707 token（缓存命中 6,998,903），输出 2,293,211 token，其中思考 0。按官方美元高峰单价计算的用量费用上界为 $9.8135，不是实际人民币账单。

本阶段非思考调用按人民币单价计算的费用上界合计 60.2671 元；修复前其他版本和 high 模式单独保留在共享累计预算中。单题费用集中情况如下，统计当前最终尝试的返回调用；续跑前归档的中断尝试费用计入共享累计预算，不重复加入这些逐题用量。

| issue | 返回调用数 | 因果调用数 | 输入 token | 输出 token | 单次最大输入 | 人民币费用上界 |
|---|---:|---:|---:|---:|---:|---:|
| sympy__sympy-13915 | 32 | 22 | 1,064,958 | 36,787 | 128,027 | 1.9255 |
| sympy__sympy-21379 | 33 | 22 | 888,669 | 30,739 | 86,487 | 1.7380 |
| sympy__sympy-14024 | 29 | 22 | 894,677 | 23,640 | 142,215 | 1.6927 |
| sympy__sympy-13895 | 29 | 22 | 820,558 | 23,519 | 163,344 | 1.5822 |
| sympy__sympy-16988 | 34 | 22 | 726,411 | 33,528 | 143,941 | 1.5632 |
| sympy__sympy-12419 | 29 | 22 | 695,393 | 26,188 | 86,491 | 1.3888 |
| sympy__sympy-13146 | 36 | 22 | 600,312 | 27,745 | 84,749 | 1.3252 |
| sympy__sympy-21627 | 30 | 22 | 624,147 | 32,965 | 211,114 | 1.2943 |
| sympy__sympy-18087 | 27 | 22 | 609,495 | 30,919 | 124,300 | 1.1176 |
| sympy__sympy-11897 | 31 | 20 | 458,442 | 25,041 | 79,379 | 1.0113 |

B2 的因果更新会反复发送已有图的关联代码，1M 上下文使原来可能被 Qwen 64K 拒绝的长请求继续执行，费用不能按普通短聊天估计。上表基于实际返回 token，不将相关性过滤、图解析损失或预测质量归因于费用本身。

独立 token 费用保护上界为 66.1453 元（含修复前及 high 调用），采用它与余额差的较大值保护 69.93 元额度，防止官方余额刷新延迟。它是保守停止门槛，不是实际账单。

现已核查官方中文单价，人民币预算无需汇率换算：高峰输入缓存命中 0.04 元/百万、未命中 2 元/百万，输出 8 元/百万；空闲时段减半。此前 high 调用按高峰单价计上界，非思考调用按请求时间与响应时间覆盖的时段计费上界；跨时段采用较高价格，法定节假日仍按普通工作日判断，属于保守预估。每个请求先检查官方人民币余额，再按高峰单价为并发请求保留费用余量。单次输入按 UTF-8 字节上界预估，返回用量以 API 为准。预算不足保留中断证据，缺失题不伪装成运行失败。超时后的不确定账单保留预留额，不自动重试付费请求。

本次显式 thinking=disabled、temperature=0；API 没有使用 Qwen 专用 seed 或 `/tokenize`，低温度也不保证多次运行完全相同。

## 问题、阶段损失与其他发现

- 失败类型：`{"ContextBudgetExceeded": 1}`。
- `sympy__sympy-22840` 在因果更新时被客户端的UTF-8字节上界检查拒绝，该次请求未发送给官方API。字节上界较保守，不能据此断言实际DeepSeek token已经超过1M；本轮保持冻结检查规则，明确保留该失败并计0。
- 空种子：1；空原生定位：2。
- 未解决的相关性判定：0；输出函数未收到源码：4。
- 达到答案输出上限的题：56；按冻结 Qwen B2 同口径，将原始响应交给原解析器并保留截断标记。JSON 仍有一次格式修复，Mermaid 可能只留下部分图；流程 complete 不代表所有模型响应完整。
- B2 保留原版 Mermaid 解析器；`causal_validation_errors=0` 不表示通过 B3 的 JSON 因果校验。原版一基序号错误、无绑定因子和优先级计算限制继续在下面的审计中暴露。

源码送达审计匹配已返回请求中的独立函数实体、限定名和定义位置；“未收到独立函数节点源码”不是仅凭该计数就断言所有类/文件文本中都没有嵌入函数代码，疑似案例需结合原始提示全文复核。GraphLocator 原生结果没有显式的函数置信度排序，Top-k 使用图因子与代码绑定的插入顺序作为兼容顺序，不等同于模型单独输出的排名列表。

```json
{
  "counts": {
    "function_predictions_with_no_main_function_source": 20,
    "function_predictions_with_no_causal_function_source": 0,
    "search_received_any_target": 188,
    "search_received_all_targets": 161,
    "seeds_any_target": 194,
    "seeds_all_targets": 166,
    "causal_received_any_target": 240,
    "causal_received_all_targets": 218,
    "final_any_target": 207,
    "final_all_targets": 182,
    "因果收到目标实体但未保留": 32,
    "legacy_actual_update_limit": 25,
    "legacy_causal_issues": 300,
    "issues_with_legacy_invalid_binding": 13,
    "issues_with_unprocessed_matches": 81,
    "issues_with_unknown_relevance": 0,
    "issues_with_causal_unresolved": 0,
    "issues_with_search_tool_error": 1,
    "issues_with_search_action_error": 16,
    "causal_update_limit": 0,
    "empty_function_predictions": 12,
    "issues_with_only_unlocated_associations": 0,
    "issues_with_duplicate_code_factors": 113,
    "issues_with_causal_cycles": 1,
    "最终覆盖部分目标": 25,
    "最终覆盖全部目标": 182,
    "NA": 7,
    "目标函数实体未送达模型": 53,
    "运行失败": 1
  },
  "event_totals": {
    "legacy_invalid_new_binding_rows": 52,
    "run_start": 300,
    "search_round": 1413,
    "search_history_compaction": 1413,
    "request_preflight": 5015,
    "model_request": 5015,
    "model_response": 5015,
    "search_query": 1343,
    "search_matches": 1343,
    "search_result": 1804,
    "search_page_summary": 1343,
    "source_receipt": 1014,
    "relevance_attempt": 1014,
    "relevance_decisions": 1014,
    "seed_locations": 300,
    "causal_context": 2570,
    "causal_parse": 2570,
    "output_truncated": 85,
    "run_end": 299,
    "unprocessed_matches_across_queries": 22799,
    "association_type_FUNCTION": 1989,
    "associations_without_file": 244,
    "associations_without_source": 21,
    "association_type_GLOBAL_VAR": 36,
    "duplicate_code_associations": 172,
    "causal_factors": 2571,
    "causal_edges": 2580,
    "association_type_FILE": 90,
    "association_type_CLASS": 376,
    "association_type_FIELD": 244,
    "association_type_PACKAGE": 4,
    "search_action_error": 27,
    "search_tool_error": 1,
    "run_error": 1
  },
  "seconds": {
    "total": 41791.75880743191,
    "minimum": 18.859486201778054,
    "median": 119.21805622056127,
    "mean": 139.3058626914397,
    "maximum": 481.42136640660465
  },
  "seed_count": {
    "total": 1716,
    "minimum": 0,
    "median": 5.0,
    "mean": 5.72,
    "maximum": 25
  },
  "predicted_function_count": {
    "total": 1836,
    "minimum": 0,
    "median": 4.0,
    "mean": 6.12,
    "maximum": 58
  },
  "causal_probabilities": {
    "total": 1857.370000000002,
    "minimum": 0.01,
    "median": 0.8,
    "mean": 0.7199108527131783,
    "maximum": 0.99
  },
  "coverage_definition": "实际返回请求中显式函数节点与完整def源码的实体覆盖；函数身份以base commit源码AST及节点起始行还原，不靠真值补全输入节点名。类整体源码中的隐含方法未算作单独函数实体。",
  "interpretation": "语法/来源可靠性和语义正确性分别测量；概率是模型输出，不是校准置信度。"
}
```

原始 Mermaid 解析器还有可用两行合法图复现的顺序问题：当 A 先作为 `B --> A` 的目标创建时，它先被赋予 Issue 名称和空代码绑定；后续 `A[原因<br>Code Elements: [1]] --> I` 的有效绑定不会填回已有 A。另一个情况是同一响应给同一新因子重复声明并改变绑定，解析器仍保留第一次声明，可能包含中间草稿。它们属于既有 B2 实现行为，本轮保持算法冻结，未改写预测。审计统计如下；仅修解析器后的完整运行收益不能从这些计数直接推出。

```json
{
  "events": {
    "responses_with_multiple_graph_headers": 200,
    "duplicate_new_source_binding_changed": 31
  },
  "affected_issues": {
    "responses_with_multiple_graph_headers": 120,
    "duplicate_new_source_binding_changed": 8
  },
  "interpretation": "Legacy parser keeps the first new source binding in each response. A node first introduced as an edge target is created with Issue/empty code attributes, and a later valid source declaration is ignored. Changed duplicate declarations likewise do not replace that first binding. These are parser facts, not estimated improvement from rerunning the algorithm."
}
```

预算余额不足时停止是成本限制；HTTP、上下文、格式及输出截断分别记录。模型成绩仍可能受候选未召回、相关性过滤和因果最终保留影响，不能仅凭两模型总分推断是哪一步造成。

## 来源

[官方模型与人民币价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)；[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)；[Chat API 与 JSON 输出参数](https://api-docs.deepseek.com/api/create-chat-completion/)。

结果目录：`results/deepseek_v41_flash_nonthinking/full/B2`；完整原始证据、版本快照和结果 JSONL 保留。后续未读取结果真值来修改提示词。
