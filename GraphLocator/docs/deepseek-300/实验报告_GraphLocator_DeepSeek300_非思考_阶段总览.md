# GraphLocator DeepSeek-V4.1-Flash 阶段实验总览

生成时间：2026-10-12T13:00:31.559040+08:00。本次使用 DeepSeek 官方 API，模型 ID `deepseek-flash`，关闭思考模式 `thinking=disabled`，temperature=0，当前批准的累计费用上限 **20 元**。

本阶段计划 300 题，完成 120，运行失败 0，缺少结果 180。 **尚未完成 300 题，以下包含缺失题的指标不能作为完整实验最终成绩。**

## 流程与可比范围

沿用最终 Qwen 适配v2 的 B2：同一 SWE-bench Lite issue ID、同一 base commit、仓库图、搜索规则、候选分页、相关性判定与原版 Mermaid 因果流程。源码批次仍用 Qwen 分词器估算大小，它只参与分页，不执行 Qwen 推理。

本次同时更换模型与供应商、关闭思考、保留与 Qwen B2 相同的答案输出上限，并使用官方 1M 上下文。搜索/相关性采用 DeepSeek `json_object` 和显式 schema 提示，再经过原有客户端校验；它不等同于 Qwen 服务的强制 JSON Schema 解码。因此结果衡量的是这套 DeepSeek 部署配置，不能把所有差异归因于模型权重。

七个既有固定金丝雀只检查工程可运行性，不按命中率挑选题目或方案。同一冻结版本的金丝雀结果复用于全量，避免重复付费；提示、原始响应、用量及指纹全部保留。评分阶段才读取真值。

## 论文原生集合指标

| 层级 | 评分题数 | 精确率 | 召回率 | F1 | SL |
|---|---:|---:|---:|---:|---:|
| 文件 | 300 | 20.57% | 35.67% | 24.43% | 35.67% |
| 模块/类 | 225 | 18.60% | 35.56% | 22.67% | 35.56% |
| 函数 | 277 | 10.92% | 29.66% | 14.68% | 28.88% |

原生指标按作者实体真值逐题计算后宏平均；无该层级真值的题为 NA，空定位和运行失败计 0。SL 表示完整覆盖全部该层级目标。

## 与既有实验使用相同评分口径

| 项目/条件 | 函数评分题数 | 精确率 | 召回率 | F1 | SL |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 293 | 7.77% | 28.61% | 11.69% | 25.94% |
| CoSIL/off | 293 | 8.57% | 28.85% | 12.57% | 25.94% |
| GraphLocator/Qwen | 293 | 4.79% | 7.41% | 5.28% | 7.17% |
| GraphLocator/Qwen-适配v2 | 293 | 10.71% | 17.24% | 12.06% | 16.04% |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 293 | 10.10% | 27.02% | 13.42% | 25.94% |

严格函数评分依据 base commit 的 AST 解析限定名；同名歧义预测计假阳性，不能借助真值消歧。共同完整 300 题的函数真值适用 293 题，作者原生适用 277 题；这两套分母和分数不可混用。

上述全300题集合指标将缺失题按空预测计算，只是已确认覆盖下界，不能据此给模型排名。下面只比较本次已有最终结果或明确失败的 120 个相同 issue ID；它们按固定题序加既有金丝雀进入，属于非随机观察集，不能当作完整300题结论。

| 相同已提供题目上的项目/条件 | 函数评分题数 | 精确率 | 召回率 | F1 | SL |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 116 | 8.09% | 30.03% | 12.28% | 29.31% |
| CoSIL/off | 116 | 8.72% | 27.44% | 12.50% | 26.72% |
| GraphLocator/Qwen | 116 | 1.98% | 3.45% | 2.17% | 3.45% |
| GraphLocator/Qwen-适配v2 | 116 | 14.33% | 23.13% | 16.38% | 22.41% |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 116 | 25.51% | 68.25% | 33.89% | 65.52% |

Excel 的“实验信息”页按已提供且有函数真值的题目计算 Top-k 分母，缺失题不算未命中；全300题下界与该页百分比也不能混用。

| 项目/条件 | Top-1 命中数 | Top-3 命中数 | Top-5 命中数 |
|---|---:|---:|---:|
| CoSIL/on | 80 | 103 | 106 |
| CoSIL/off | 75 | 105 | 111 |
| GraphLocator/Qwen | 15 | 24 | 25 |
| GraphLocator/Qwen-适配v2 | 33 | 53 | 57 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking-20元限额 | 43 | 70 | 80 |

Top-k 沿用对照表的文件+函数叶名兼容口径，候选中的类/变量也占排序位置。CoSIL 文件候选入口与 GraphLocator 全库检索入口不同。

## 按项目拆分

| 仓库 | 计划题数 | 函数评分题数 | 严格 P | 严格 R | 严格 F1 | SL |
|---|---:|---:|---:|---:|---:|---:|
| astropy/astropy | 6 | 6 | 22.22% | 41.67% | 27.78% | 33.33% |
| django/django | 114 | 110 | 24.90% | 67.42% | 33.20% | 65.45% |
| matplotlib/matplotlib | 23 | 23 | 0.00% | 0.00% | 0.00% | 0.00% |
| mwaskom/seaborn | 4 | 4 | 5.00% | 25.00% | 8.33% | 25.00% |
| pallets/flask | 3 | 3 | 0.00% | 0.00% | 0.00% | 0.00% |
| psf/requests | 6 | 6 | 0.00% | 0.00% | 0.00% | 0.00% |
| pydata/xarray | 5 | 5 | 0.00% | 0.00% | 0.00% | 0.00% |
| pylint-dev/pylint | 6 | 6 | 0.00% | 0.00% | 0.00% | 0.00% |
| pytest-dev/pytest | 17 | 16 | 0.00% | 0.00% | 0.00% | 0.00% |
| scikit-learn/scikit-learn | 23 | 23 | 2.17% | 2.17% | 2.17% | 0.00% |
| sphinx-doc/sphinx | 16 | 16 | 0.00% | 0.00% | 0.00% | 0.00% |
| sympy/sympy | 77 | 75 | 0.22% | 1.33% | 0.38% | 1.33% |
## 费用与调用证据

本次模型切换的累计官方 CNY 余额差为 **19.8400 元**，最新余额 0.1600 元；包括此前修复和已停止 high 模式的费用，也可能包含同账户期间其他调用，作为共同 20 元预算的保守扣减证据。它不是单独的非思考条件费用。

本阶段返回 1988 次模型响应，输入 7,754,726 token（缓存命中 2,126,074），输出 782,415 token，其中思考 0。按官方美元高峰单价计算的用量费用上界为 $2.6403，不是实际人民币账单。

本阶段非思考调用按人民币单价计算的费用上界合计 12.0472 元；修复前其他版本和 high 模式单独保留在共享累计预算中。单题费用集中情况如下，包含预算中断题已经返回的调用。

| issue | 返回调用数 | 因果调用数 | 输入 token | 输出 token | 单次最大输入 | 人民币费用上界 |
|---|---:|---:|---:|---:|---:|---:|
| django__django-12470 | 29 | 19 | 191,173 | 22,160 | 41,754 | 0.4620 |
| django__django-12113 | 32 | 22 | 182,788 | 19,941 | 21,113 | 0.4160 |
| django__django-11283 | 26 | 18 | 156,135 | 21,570 | 19,818 | 0.4068 |
| django__django-11742 | 20 | 12 | 181,822 | 8,689 | 121,844 | 0.3993 |
| django__django-11797 | 27 | 19 | 165,576 | 23,821 | 12,791 | 0.3534 |
| django__django-11999 | 17 | 8 | 152,725 | 5,640 | 122,606 | 0.3277 |
| django__django-11910 | 22 | 18 | 132,045 | 17,863 | 20,753 | 0.3255 |
| django__django-14997 | 31 | 22 | 346,433 | 22,699 | 21,947 | 0.3139 |
| sympy__sympy-12481 | 22 | 8 | 163,617 | 6,492 | 66,408 | 0.2989 |
| django__django-15738 | 28 | 22 | 267,553 | 28,163 | 26,637 | 0.2914 |

B2 的因果更新会反复发送已有图的关联代码，1M 上下文使原来可能被 Qwen 64K 拒绝的长请求继续执行，费用不能按普通短聊天估计。上表基于实际返回 token，不将相关性过滤、图解析损失或预测质量归因于费用本身。

独立 token 费用保护上界为 17.5270 元（含修复前及 high 调用），采用它与余额差的较大值保护 20 元额度，防止官方余额刷新延迟。它是保守停止门槛，不是实际账单。

现已核查官方中文单价，人民币预算无需汇率换算：高峰输入缓存命中 0.04 元/百万、未命中 2 元/百万，输出 8 元/百万；空闲时段减半。此前 high 调用按高峰单价计上界，非思考调用按请求时间与响应时间覆盖的时段计费上界；跨时段采用较高价格，法定节假日仍按普通工作日判断，属于保守预估。每个请求先检查官方人民币余额，再按高峰单价为并发请求保留费用余量。单次输入按 UTF-8 字节上界预估，返回用量以 API 为准。预算不足保留中断证据，缺失题不伪装成运行失败。超时后的不确定账单保留预留额，不自动重试付费请求。

本次显式 thinking=disabled、temperature=0；API 没有使用 Qwen 专用 seed 或 `/tokenize`，低温度也不保证多次运行完全相同。

## 问题、阶段损失与其他发现

- 失败类型：`{}`。
- 空种子：1；空原生定位：1。
- 未解决的相关性判定：0；输出函数未收到源码：3。
- 达到答案输出上限的题：20；按冻结 Qwen B2 同口径，将原始响应交给原解析器并保留截断标记。JSON 仍有一次格式修复，Mermaid 可能只留下部分图；流程 complete 不代表所有模型响应完整。
- B2 保留原版 Mermaid 解析器；`causal_validation_errors=0` 不表示通过 B3 的 JSON 因果校验。原版一基序号错误、无绑定因子和优先级计算限制继续在下面的审计中暴露。

源码送达审计匹配已返回请求中的独立函数实体、限定名和定义位置；“未收到独立函数节点源码”不是仅凭该计数就断言所有类/文件文本中都没有嵌入函数代码，疑似案例需结合原始提示全文复核。GraphLocator 原生结果没有显式的函数置信度排序，Top-k 使用图因子与代码绑定的插入顺序作为兼容顺序，不等同于模型单独输出的排名列表。

```json
{
  "counts": {
    "function_predictions_with_no_main_function_source": 11,
    "function_predictions_with_no_causal_function_source": 0,
    "search_received_any_target": 73,
    "search_received_all_targets": 67,
    "seeds_any_target": 76,
    "seeds_all_targets": 70,
    "causal_received_any_target": 94,
    "causal_received_all_targets": 91,
    "final_any_target": 82,
    "final_all_targets": 76,
    "因果收到目标实体但未保留": 12,
    "legacy_actual_update_limit": 4,
    "legacy_causal_issues": 120,
    "issues_with_legacy_invalid_binding": 7,
    "issues_with_unprocessed_matches": 37,
    "issues_with_unknown_relevance": 0,
    "issues_with_causal_unresolved": 0,
    "issues_with_search_tool_error": 1,
    "issues_with_search_action_error": 3,
    "causal_update_limit": 0,
    "empty_function_predictions": 6,
    "issues_with_only_unlocated_associations": 0,
    "issues_with_duplicate_code_factors": 39,
    "issues_with_causal_cycles": 0,
    "最终覆盖部分目标": 6,
    "最终覆盖全部目标": 76,
    "NA": 4,
    "目标函数实体未送达模型": 22,
    "missing": 180
  },
  "event_totals": {
    "legacy_invalid_new_binding_rows": 13,
    "run_start": 120,
    "search_round": 562,
    "search_history_compaction": 562,
    "request_preflight": 1936,
    "model_request": 1936,
    "model_response": 1936,
    "search_query": 534,
    "search_matches": 534,
    "search_result": 744,
    "search_page_summary": 534,
    "source_receipt": 442,
    "relevance_attempt": 442,
    "relevance_decisions": 442,
    "seed_locations": 120,
    "causal_context": 929,
    "causal_parse": 929,
    "output_truncated": 22,
    "run_end": 120,
    "unprocessed_matches_across_queries": 13709,
    "association_type_FUNCTION": 575,
    "associations_without_file": 108,
    "associations_without_source": 7,
    "association_type_GLOBAL_VAR": 8,
    "duplicate_code_associations": 56,
    "causal_factors": 842,
    "causal_edges": 843,
    "association_type_FILE": 43,
    "association_type_CLASS": 165,
    "association_type_FIELD": 108,
    "association_type_PACKAGE": 2,
    "search_action_error": 4,
    "search_tool_error": 1
  },
  "seconds": {
    "total": 18666.357001542114,
    "minimum": 46.552610555663705,
    "median": 140.84848525794223,
    "mean": 155.55297501285094,
    "maximum": 381.983965549618
  },
  "seed_count": {
    "total": 706,
    "minimum": 0,
    "median": 5.0,
    "mean": 5.883333333333334,
    "maximum": 25
  },
  "predicted_function_count": {
    "total": 528,
    "minimum": 0,
    "median": 3.0,
    "mean": 4.4,
    "maximum": 30
  },
  "causal_probabilities": {
    "total": 624.5400000000009,
    "minimum": 0.05,
    "median": 0.8,
    "mean": 0.7408540925266904,
    "maximum": 0.98
  },
  "coverage_definition": "实际返回请求中显式函数节点与完整def源码的实体覆盖；函数身份以base commit源码AST及节点起始行还原，不靠真值补全输入节点名。类整体源码中的隐含方法未算作单独函数实体。",
  "interpretation": "语法/来源可靠性和语义正确性分别测量；概率是模型输出，不是校准置信度。"
}
```

原始 Mermaid 解析器还有可用两行合法图复现的顺序问题：当 A 先作为 `B --> A` 的目标创建时，它先被赋予 Issue 名称和空代码绑定；后续 `A[原因<br>Code Elements: [1]] --> I` 的有效绑定不会填回已有 A。另一个情况是同一响应给同一新因子重复声明并改变绑定，解析器仍保留第一次声明，可能包含中间草稿。它们属于既有 B2 实现行为，本轮保持算法冻结，未改写预测。审计统计如下；仅修解析器后的完整运行收益不能从这些计数直接推出。

```json
{
  "events": {
    "responses_with_multiple_graph_headers": 66,
    "duplicate_new_source_binding_changed": 3
  },
  "affected_issues": {
    "responses_with_multiple_graph_headers": 47,
    "duplicate_new_source_binding_changed": 1
  },
  "interpretation": "Legacy parser keeps the first new source binding in each response. A node first introduced as an edge target is created with Issue/empty code attributes, and a later valid source declaration is ignored. Changed duplicate declarations likewise do not replace that first binding. These are parser facts, not estimated improvement from rerunning the algorithm."
}
```

预算余额不足时停止是成本限制；HTTP、上下文、格式及输出截断分别记录。模型成绩仍可能受候选未召回、相关性过滤和因果最终保留影响，不能仅凭两模型总分推断是哪一步造成。

## 来源

[官方模型与人民币价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)；[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)；[Chat API 与 JSON 输出参数](https://api-docs.deepseek.com/api/create-chat-completion/)。

结果目录：`results/deepseek_v41_flash_nonthinking/full/B2`；完整原始证据、版本快照和结果 JSONL 保留。后续未读取结果真值来修改提示词。
