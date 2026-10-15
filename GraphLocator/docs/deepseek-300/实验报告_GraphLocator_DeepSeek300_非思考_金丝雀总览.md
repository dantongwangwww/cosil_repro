# GraphLocator DeepSeek-V4.1-Flash 金丝雀实验总览

生成时间：2026-10-12T12:44:20.423961+08:00。本次使用 DeepSeek 官方 API，模型 ID `deepseek-flash`，关闭思考模式 `thinking=disabled`，temperature=0，当前批准的累计费用上限 **20 元**。

本阶段计划 7 题，完成 7，运行失败 0，缺少结果 0。

## 流程与可比范围

沿用最终 Qwen 适配v2 的 B2：同一 SWE-bench Lite issue ID、同一 base commit、仓库图、搜索规则、候选分页、相关性判定与原版 Mermaid 因果流程。源码批次仍用 Qwen 分词器估算大小，它只参与分页，不执行 Qwen 推理。

本次同时更换模型与供应商、关闭思考、保留与 Qwen B2 相同的答案输出上限，并使用官方 1M 上下文。搜索/相关性采用 DeepSeek `json_object` 和显式 schema 提示，再经过原有客户端校验；它不等同于 Qwen 服务的强制 JSON Schema 解码。因此结果衡量的是这套 DeepSeek 部署配置，不能把所有差异归因于模型权重。

七个既有固定金丝雀只检查工程可运行性，不按命中率挑选题目或方案。同一冻结版本的金丝雀结果复用于全量，避免重复付费；提示、原始响应、用量及指纹全部保留。评分阶段才读取真值。

## 论文原生集合指标

| 层级 | 评分题数 | 精确率 | 召回率 | F1 | SL |
|---|---:|---:|---:|---:|---:|
| 文件 | 7 | 58.33% | 100.00% | 70.00% | 100.00% |
| 模块/类 | 4 | 45.83% | 100.00% | 62.50% | 100.00% |
| 函数 | 6 | 24.63% | 75.00% | 33.10% | 66.67% |

原生指标按作者实体真值逐题计算后宏平均；无该层级真值的题为 NA，空定位和运行失败计 0。SL 表示完整覆盖全部该层级目标。

## 与既有实验使用相同评分口径

| 项目/条件 | 函数评分题数 | 精确率 | 召回率 | F1 | SL |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 7 | 8.57% | 42.86% | 14.29% | 42.86% |
| CoSIL/off | 7 | 2.86% | 14.29% | 4.76% | 14.29% |
| GraphLocator/Qwen | 7 | 2.86% | 14.29% | 4.76% | 14.29% |
| GraphLocator/Qwen-适配v2 | 7 | 4.76% | 14.29% | 7.14% | 14.29% |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 7 | 21.11% | 64.29% | 28.37% | 57.14% |

严格函数评分依据 base commit 的 AST 解析限定名；同名歧义预测计假阳性，不能借助真值消歧。共同完整 300 题的函数真值适用 293 题，作者原生适用 277 题；这两套分母和分数不可混用。

| 项目/条件 | Top-1 命中数 | Top-3 命中数 | Top-5 命中数 |
|---|---:|---:|---:|
| CoSIL/on | 3 | 3 | 3 |
| CoSIL/off | 1 | 1 | 1 |
| GraphLocator/Qwen | 1 | 1 | 1 |
| GraphLocator/Qwen-适配v2 | 1 | 1 | 1 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking | 4 | 5 | 5 |

Top-k 沿用对照表的文件+函数叶名兼容口径，候选中的类/变量也占排序位置。CoSIL 文件候选入口与 GraphLocator 全库检索入口不同。

## 按项目拆分

| 仓库 | 计划题数 | 函数评分题数 | 严格 P | 严格 R | 严格 F1 | SL |
|---|---:|---:|---:|---:|---:|---:|
| astropy/astropy | 1 | 1 | 0.00% | 0.00% | 0.00% | 0.00% |
| django/django | 2 | 2 | 30.56% | 100.00% | 43.33% | 100.00% |
| mwaskom/seaborn | 1 | 1 | 20.00% | 100.00% | 33.33% | 100.00% |
| scikit-learn/scikit-learn | 1 | 1 | 50.00% | 50.00% | 50.00% | 0.00% |
| sympy/sympy | 2 | 2 | 8.33% | 50.00% | 14.29% | 50.00% |
## 费用与调用证据

本次模型切换的累计官方 CNY 余额差为 **18.5800 元**，最新余额 1.4200 元；包括此前修复和已停止 high 模式的费用，也可能包含同账户期间其他调用，作为共同 20 元预算的保守扣减证据。它不是单独的非思考条件费用。

本阶段返回 109 次模型响应，输入 684,289 token（缓存命中 198,269），输出 45,595 token，其中思考 0。按官方美元高峰单价计算的用量费用上界为 $0.2017，不是实际人民币账单。

本阶段非思考调用按人民币单价计算的费用上界合计 1.3447 元；修复前其他版本和 high 模式单独保留在共享累计预算中。单题费用集中情况如下，包含预算中断题已经返回的调用。

| issue | 返回调用数 | 因果调用数 | 输入 token | 输出 token | 单次最大输入 | 人民币费用上界 |
|---|---:|---:|---:|---:|---:|---:|
| django__django-11910 | 22 | 18 | 132,045 | 17,863 | 20,753 | 0.3255 |
| sympy__sympy-12481 | 22 | 8 | 163,617 | 6,492 | 66,408 | 0.2989 |
| sympy__sympy-21055 | 16 | 8 | 129,305 | 3,192 | 58,445 | 0.2508 |
| scikit-learn__scikit-learn-25638 | 13 | 4 | 137,515 | 3,763 | 33,995 | 0.1922 |
| astropy__astropy-12907 | 14 | 7 | 53,987 | 9,680 | 12,825 | 0.1631 |
| mwaskom__seaborn-3190 | 15 | 9 | 54,504 | 3,508 | 5,767 | 0.0922 |
| django__django-11848 | 7 | 5 | 13,316 | 1,097 | 3,244 | 0.0221 |

B2 的因果更新会反复发送已有图的关联代码，1M 上下文使原来可能被 Qwen 64K 拒绝的长请求继续执行，费用不能按普通短聊天估计。上表基于实际返回 token，不将相关性过滤、图解析损失或预测质量归因于费用本身。

独立 token 费用保护上界为 16.4613 元（含修复前及 high 调用），采用它与余额差的较大值保护 20 元额度，防止官方余额刷新延迟。它是保守停止门槛，不是实际账单。

现已核查官方中文单价，人民币预算无需汇率换算：高峰输入缓存命中 0.04 元/百万、未命中 2 元/百万，输出 8 元/百万；空闲时段减半。此前 high 调用按高峰单价计上界，非思考调用按请求时间与响应时间覆盖的时段计费上界；跨时段采用较高价格，法定节假日仍按普通工作日判断，属于保守预估。每个请求先检查官方人民币余额，再按高峰单价为并发请求保留费用余量。单次输入按 UTF-8 字节上界预估，返回用量以 API 为准。预算不足保留中断证据，缺失题不伪装成运行失败。超时后的不确定账单保留预留额，不自动重试付费请求。

本次显式 thinking=disabled、temperature=0；API 没有使用 Qwen 专用 seed 或 `/tokenize`，低温度也不保证多次运行完全相同。

## 问题、阶段损失与其他发现

- 失败类型：`{}`。
- 空种子：0；空原生定位：0。
- 未解决的相关性判定：0；输出函数未收到源码：0。
- 达到答案输出上限的题：1；按冻结 Qwen B2 同口径，将原始响应交给原解析器并保留截断标记。JSON 仍有一次格式修复，Mermaid 可能只留下部分图；流程 complete 不代表所有模型响应完整。
- B2 保留原版 Mermaid 解析器；`causal_validation_errors=0` 不表示通过 B3 的 JSON 因果校验。原版一基序号错误、无绑定因子和优先级计算限制继续在下面的审计中暴露。

源码送达审计匹配已返回请求中的独立函数实体、限定名和定义位置；“未收到独立函数节点源码”不是仅凭该计数就断言所有类/文件文本中都没有嵌入函数代码，疑似案例需结合原始提示全文复核。GraphLocator 原生结果没有显式的函数置信度排序，Top-k 使用图因子与代码绑定的插入顺序作为兼容顺序，不等同于模型单独输出的排名列表。

```json
{
  "counts": {
    "function_predictions_with_no_main_function_source": 0,
    "function_predictions_with_no_causal_function_source": 0,
    "search_received_any_target": 5,
    "search_received_all_targets": 4,
    "seeds_any_target": 5,
    "seeds_all_targets": 4,
    "causal_received_any_target": 6,
    "causal_received_all_targets": 6,
    "final_any_target": 5,
    "final_all_targets": 4,
    "因果收到目标实体但未保留": 1,
    "legacy_actual_update_limit": 0,
    "legacy_causal_issues": 7,
    "issues_with_legacy_invalid_binding": 1,
    "issues_with_unprocessed_matches": 2,
    "issues_with_unknown_relevance": 0,
    "issues_with_causal_unresolved": 0,
    "issues_with_search_tool_error": 0,
    "issues_with_search_action_error": 0,
    "causal_update_limit": 0,
    "empty_function_predictions": 0,
    "issues_with_only_unlocated_associations": 0,
    "issues_with_duplicate_code_factors": 3,
    "issues_with_causal_cycles": 0,
    "最终覆盖全部目标": 4,
    "最终覆盖部分目标": 1,
    "目标函数实体未送达模型": 1
  },
  "event_totals": {
    "legacy_invalid_new_binding_rows": 2,
    "run_start": 7,
    "search_round": 31,
    "search_history_compaction": 31,
    "request_preflight": 109,
    "model_request": 109,
    "model_response": 109,
    "search_query": 29,
    "search_matches": 29,
    "search_result": 37,
    "search_page_summary": 29,
    "source_receipt": 19,
    "relevance_attempt": 19,
    "relevance_decisions": 19,
    "seed_locations": 7,
    "causal_context": 59,
    "causal_parse": 59,
    "output_truncated": 1,
    "run_end": 7,
    "unprocessed_matches_across_queries": 509,
    "association_type_FUNCTION": 38,
    "associations_without_file": 5,
    "associations_without_source": 1,
    "association_type_GLOBAL_VAR": 3,
    "duplicate_code_associations": 4,
    "causal_factors": 52,
    "causal_edges": 52,
    "association_type_CLASS": 4,
    "association_type_FIELD": 5,
    "association_type_FILE": 1
  },
  "seconds": {
    "total": 802.4634207030758,
    "minimum": 46.552610555663705,
    "median": 115.28666782937944,
    "mean": 114.63763152901083,
    "maximum": 182.79867200832814
  },
  "seed_count": {
    "total": 31,
    "minimum": 1,
    "median": 4,
    "mean": 4.428571428571429,
    "maximum": 10
  },
  "predicted_function_count": {
    "total": 34,
    "minimum": 2,
    "median": 5,
    "mean": 4.857142857142857,
    "maximum": 9
  },
  "causal_probabilities": {
    "total": 38.65000000000001,
    "minimum": 0.2,
    "median": 0.8,
    "mean": 0.7432692307692308,
    "maximum": 0.95
  },
  "coverage_definition": "实际返回请求中显式函数节点与完整def源码的实体覆盖；函数身份以base commit源码AST及节点起始行还原，不靠真值补全输入节点名。类整体源码中的隐含方法未算作单独函数实体。",
  "interpretation": "语法/来源可靠性和语义正确性分别测量；概率是模型输出，不是校准置信度。"
}
```

原始 Mermaid 解析器还有可用两行合法图复现的顺序问题：当 A 先作为 `B --> A` 的目标创建时，它先被赋予 Issue 名称和空代码绑定；后续 `A[原因<br>Code Elements: [1]] --> I` 的有效绑定不会填回已有 A。另一个情况是同一响应给同一新因子重复声明并改变绑定，解析器仍保留第一次声明，可能包含中间草稿。它们属于既有 B2 实现行为，本轮保持算法冻结，未改写预测。审计统计如下；仅修解析器后的完整运行收益不能从这些计数直接推出。

```json
{
  "events": {
    "responses_with_multiple_graph_headers": 6
  },
  "affected_issues": {
    "responses_with_multiple_graph_headers": 3
  },
  "interpretation": "Legacy parser keeps the first new source binding in each response. A node first introduced as an edge target is created with Issue/empty code attributes, and a later valid source declaration is ignored. Changed duplicate declarations likewise do not replace that first binding. These are parser facts, not estimated improvement from rerunning the algorithm."
}
```

预算余额不足时停止是成本限制；HTTP、上下文、格式及输出截断分别记录。模型成绩仍可能受候选未召回、相关性过滤和因果最终保留影响，不能仅凭两模型总分推断是哪一步造成。

## 来源

[官方模型与人民币价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)；[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)；[Chat API 与 JSON 输出参数](https://api-docs.deepseek.com/api/create-chat-completion/)。

结果目录：`results/deepseek_v41_flash_nonthinking/canary/3a033e3a692aa67b/B2`；完整原始证据、版本快照和结果 JSONL 保留。后续未读取结果真值来修改提示词。
