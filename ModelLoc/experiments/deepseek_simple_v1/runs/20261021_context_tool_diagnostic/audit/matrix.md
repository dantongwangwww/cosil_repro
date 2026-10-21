# B0 历史工具零 API 审计

历史输出只解析、不重新执行；旧 run 和 reports 未写入。

| 方法 | 动作 | 原解析失败 | 执行 | 成功/源码返回 | 主裁判完整源码 | 小裁判函数文本/完整源码 | 任一裁判完整源码(并集) | Agent完整源码 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D-COSIL | 411 | 81 | 301 | 298 | 298 | 0/0 | 298 | 185 |
| Q-COSIL | 400 | 33 | 367 | 233 | 233 | 0/0 | 233 | 107 |
| Q-PRUNER | 392 | 34 | 358 | 201 | 28 | 193/161 | 172 | 119 |

68 段 DSML 中，43 段只在旧审计将重复竖线归一化后结构/签名完整；严格 canonical 格式接受 0/68。未修复分隔符、未执行历史候选、未追认定位收益。

与旧报告的送达计数差异：D 主裁判 296→298、Q 主裁判 231→233、Q Agent 105→107，来自按已记录返回 SHA 恢复 getter/setter 同限定名多 span 的真实返回文本；旧审计缺少唯一 retrieved_block 就未能核验。新增计数均附原始 HTTP 200 证据，未重放调用。Q-PRUNER 旧 judge=200 是任意函数文本口径；本次核验 200 次任意函数文本。完整原工具返回源码并集为 172 次：主裁判 28 + 小裁判 161 − 两者完整重叠 17 = 172。小裁判另有 32 次部分或不同 span；其中部分经主裁判升级获得完整源码，不能直接从并集扣除。逐 action 差异见 summary.methods.<method>.delivery_count_differences。

小裁判输入哈希有效仅证明保存的输入一致。逐条比较 <function> 字节与真实工具返回，单列完整、前缀裁剪及不同源码 span；未将 token_budget_trimmed=False 当作未发生字符裁剪。

主裁判和 Agent 送达证据必须有后续 HTTP 200 receipt，并核对 request SHA 与 response SHA；Agent 还要求真实 context_accept 及后续 user 消息中完整源码。长度截断响应也证明收到输入，但保留其失败 finish_reason。

每 action 的类别/原因、原文、源码 SHA、HTTP 证据与事件路径见 CSV。未读取 gold；gold_direct_prune 为不可用，实际 reject 不能直接视为误剪。

B1 在线暂停：严格整段 DSL 会改变旧 parser 对外围解释正文的兼容行为。B2 采用严格文本 JSON，绝不称为原生 tool_calls。
