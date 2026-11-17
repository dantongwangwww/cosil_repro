# GraphLocator DeepSeek-V4.1-Flash 金丝雀实验总览

生成时间：2026-10-12T11:17:33.033664+08:00。本次使用 DeepSeek 官方 API，模型 ID `deepseek-flash`，开启思考模式 `high`，费用上限 **20 元**。

本阶段计划 7 题，完成 3，运行失败 0，缺少结果 4。

## 流程与可比范围

沿用最终 Qwen 适配v2 的 B2：同一 SWE-bench Lite issue ID、同一 base commit、仓库图、搜索规则、候选分页、相关性判定与原版 Mermaid 因果流程。源码批次仍用 Qwen 分词器估算大小，它只参与分页，不执行 Qwen 推理。

本次同时更换模型与供应商、开启思考、扩大含思考的输出上限，并使用官方 1M 上下文。搜索/相关性采用 DeepSeek `json_object` 和显式 schema 提示，再经过原有客户端校验；它不等同于 Qwen 服务的强制 JSON Schema 解码。因此结果衡量的是这套 DeepSeek 部署配置，不能把所有差异归因于模型权重。

七个既有固定金丝雀只检查工程可运行性，不按命中率挑选题目或方案。同一冻结版本的金丝雀结果复用于全量，避免重复付费；提示、原始响应、用量及指纹全部保留。评分阶段才读取真值。

## 论文原生集合指标

| 层级 | 评分题数 | 精确率 | 召回率 | F1 | SL |
|---|---:|---:|---:|---:|---:|
| 文件 | 7 | 21.43% | 42.86% | 28.57% | 42.86% |
| 模块/类 | 4 | 25.00% | 25.00% | 25.00% | 25.00% |
| 函数 | 6 | 19.44% | 41.67% | 26.11% | 33.33% |

原生指标按作者实体真值逐题计算后宏平均；无该层级真值的题为 NA，空定位和运行失败计 0。SL 表示完整覆盖全部该层级目标。

## 与既有实验使用相同评分口径

| 项目/条件 | 函数评分题数 | 精确率 | 召回率 | F1 | SL |
|---|---:|---:|---:|---:|---:|
| CoSIL/on | 7 | 8.57% | 42.86% | 14.29% | 42.86% |
| CoSIL/off | 7 | 2.86% | 14.29% | 4.76% | 14.29% |
| GraphLocator/Qwen | 7 | 2.86% | 14.29% | 4.76% | 14.29% |
| GraphLocator/Qwen-适配v2 | 7 | 4.76% | 14.29% | 7.14% | 14.29% |
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 7 | 16.67% | 35.71% | 22.38% | 28.57% |

严格函数评分依据 base commit 的 AST 解析限定名；同名歧义预测计假阳性，不能借助真值消歧。共同完整 300 题的函数真值适用 293 题，作者原生适用 277 题；这两套分母和分数不可混用。

| 项目/条件 | Top-1 命中数 | Top-3 命中数 | Top-5 命中数 |
|---|---:|---:|---:|
| CoSIL/on | 3 | 3 | 3 |
| CoSIL/off | 1 | 1 | 1 |
| GraphLocator/Qwen | 1 | 1 | 1 |
| GraphLocator/Qwen-适配v2 | 1 | 1 | 1 |
| GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high | 1 | 3 | 3 |

Top-k 沿用对照表的文件+函数叶名兼容口径，候选中的类/变量也占排序位置。CoSIL 文件候选入口与 GraphLocator 全库检索入口不同。

## 费用与调用证据

官方 CNY 余额差记录本实验已消耗 **3.4000 元**，最新余额 16.6000 元；该余额差还会包含同一账户期间的其他调用，因此它作为保守预算扣减证据。

本阶段返回 78 次模型响应，输入 329,604 token（缓存命中 86,016），输出 431,173 token，其中思考 423,770。按官方美元高峰单价计算的用量费用上界为 $0.5910，不是实际人民币账单。

独立 token 费用保护上界为 6.6010 元（含修复前调用），采用它与余额差的较大值保护 20 元额度，防止官方余额刷新延迟。它是保守停止门槛，不是实际账单。

每个请求先检查官方人民币余额，再为并发请求保留费用余量。预留换算系数 10 CNY/USD 是保守系数，不是声称的实时汇率；单次输入按 UTF-8 字节上界预估，返回用量以 API 为准。预算不足保留中断证据，缺失题不伪装成运行失败。超时后的不确定账单保留预留额，不自动重试付费请求。

模型默认开启思考，temperature 在思考模式中不生效，本次没有用 temperature=0 宣称确定性；API 没有使用 Qwen 专用 seed 或 `/tokenize`。

## 问题、阶段损失与其他发现

- 失败类型：`{}`。
- 空种子：0；空原生定位：0。
- 未解决的相关性判定：0；输出函数未收到源码：0。
- 达到含思考输出上限的题：0，不将截断响应当作有效完整定位。
- B2 保留原版 Mermaid 解析器；`causal_validation_errors=0` 不表示通过 B3 的 JSON 因果校验。原版一基序号错误、无绑定因子和优先级计算限制继续在下面的审计中暴露。

```json
{
  "counts": {
    "missing": 4,
    "function_predictions_with_no_main_function_source": 0,
    "function_predictions_with_no_causal_function_source": 0,
    "search_received_any_target": 3,
    "search_received_all_targets": 2,
    "seeds_any_target": 3,
    "seeds_all_targets": 2,
    "causal_received_any_target": 3,
    "causal_received_all_targets": 3,
    "final_any_target": 3,
    "final_all_targets": 2,
    "最终覆盖全部目标": 2,
    "legacy_actual_update_limit": 0,
    "legacy_causal_issues": 3,
    "issues_with_legacy_invalid_binding": 0,
    "issues_with_unprocessed_matches": 2,
    "issues_with_unknown_relevance": 0,
    "issues_with_causal_unresolved": 0,
    "issues_with_search_tool_error": 0,
    "issues_with_search_action_error": 1,
    "causal_update_limit": 0,
    "empty_function_predictions": 0,
    "issues_with_only_unlocated_associations": 0,
    "issues_with_duplicate_code_factors": 2,
    "issues_with_causal_cycles": 0,
    "最终覆盖部分目标": 1
  },
  "event_totals": {
    "legacy_invalid_new_binding_rows": 0,
    "run_start": 3,
    "search_round": 14,
    "search_history_compaction": 14,
    "request_preflight": 44,
    "model_request": 44,
    "model_response": 44,
    "search_query": 12,
    "search_matches": 12,
    "search_result": 22,
    "search_page_summary": 12,
    "source_receipt": 14,
    "relevance_attempt": 14,
    "relevance_decisions": 14,
    "seed_locations": 3,
    "causal_context": 15,
    "causal_parse": 15,
    "run_end": 3,
    "unprocessed_matches_across_queries": 509,
    "association_type_FUNCTION": 11,
    "associations_without_file": 0,
    "associations_without_source": 0,
    "association_type_GLOBAL_VAR": 1,
    "duplicate_code_associations": 3,
    "causal_factors": 12,
    "causal_edges": 12,
    "search_action_error": 1
  },
  "seconds": {
    "total": 1384.0371947102249,
    "minimum": 414.86998250801116,
    "median": 440.82430287171155,
    "mean": 461.345731570075,
    "maximum": 528.3429093305022
  },
  "seed_count": {
    "total": 11,
    "minimum": 2,
    "median": 4,
    "mean": 3.6666666666666665,
    "maximum": 5
  },
  "predicted_function_count": {
    "total": 8,
    "minimum": 2,
    "median": 3,
    "mean": 2.6666666666666665,
    "maximum": 3
  },
  "causal_probabilities": {
    "total": 10.0,
    "minimum": 0.5,
    "median": 0.875,
    "mean": 0.8333333333333334,
    "maximum": 0.98
  },
  "coverage_definition": "实际返回请求中显式函数节点与完整def源码的实体覆盖；函数身份以base commit源码AST及节点起始行还原，不靠真值补全输入节点名。类整体源码中的隐含方法未算作单独函数实体。",
  "interpretation": "语法/来源可靠性和语义正确性分别测量；概率是模型输出，不是校准置信度。"
}
```

预算余额不足时停止是成本限制；HTTP、上下文、格式及输出截断分别记录。模型成绩仍可能受候选未召回、相关性过滤和因果最终保留影响，不能仅凭两模型总分推断是哪一步造成。

## 来源

[官方模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)；[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)；[Chat API 与 JSON 输出参数](https://api-docs.deepseek.com/api/create-chat-completion/)。

结果目录：`/mnt/skygruop0/home/wdt/cosil_repro/GraphLocator/results/deepseek_v41_flash/canary/85611f9fb63c14e4/B2`；完整原始证据、版本快照和结果 JSONL 保留。后续未读取结果真值来修改提示词。
