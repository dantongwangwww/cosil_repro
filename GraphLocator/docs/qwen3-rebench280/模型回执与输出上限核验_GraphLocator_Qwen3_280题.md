# 实际模型回执与输出上限补充核验

280题终态后，只读原HTTP事件：3762份已完成模型回执均返回actual_model=qwen3-8b；另1次请求在1800秒终止前未结束，其返回模型、结束原因和用量均不补零。

结束原因：tool_calls=1344、stop=2384、length=34。34次输出达到8192 token上限，涉及24题，阶段分布为{'generate_causal_graph': 34}。

length是请求级预算标记，不自动等于整题失败，也不能仅凭它断定最终未命中的唯一原因。原算法可能从部分Mermaid中提取已有绑定或继续下一轮；本审计未补全输出、未重新调用，也未将其另择更好版本。所有原始预测与最终分类保持不变。

## 逐请求记录

| issue | 请求 | 阶段 | 完成token | 最终执行状态 |
|---|---:|---|---:|---|
| neurostuff__NiMARE-939 | 10 | generate_causal_graph | 8192 | complete |
| zalando-stups__senza-278 | 18 | generate_causal_graph | 8192 | complete |
| googleapis__python-automl-110 | 13 | generate_causal_graph | 8192 | complete |
| VirtusLab__git-machete-327 | 9 | generate_causal_graph | 8192 | complete |
| equinor__ert-12275 | 20 | generate_causal_graph | 8192 | complete |
| openai__openai-agents-python-2144 | 10 | generate_causal_graph | 8192 | complete |
| openai__openai-agents-python-2144 | 13 | generate_causal_graph | 8192 | complete |
| openai__openai-agents-python-2144 | 15 | generate_causal_graph | 8192 | complete |
| openai__openai-agents-python-2144 | 18 | generate_causal_graph | 8192 | complete |
| pypa__twine-369 | 17 | generate_causal_graph | 8192 | complete |
| astanin__python-tabulate-21 | 9 | generate_causal_graph | 8192 | complete |
| kootenpv__access_points-22 | 16 | generate_causal_graph | 8192 | complete |
| encode__httpx-1002 | 12 | generate_causal_graph | 8192 | complete |
| encode__httpx-1002 | 14 | generate_causal_graph | 8192 | complete |
| ARMmbed__greentea-243 | 12 | generate_causal_graph | 8192 | complete |
| iterative__datachain-206 | 10 | generate_causal_graph | 8192 | complete |
| google__flax-4681 | 11 | generate_causal_graph | 8192 | complete |
| google__flax-4681 | 13 | generate_causal_graph | 8192 | complete |
| zwicker-group__py-pde-683 | 13 | generate_causal_graph | 8192 | complete |
| juju__python-libjuju-497 | 9 | generate_causal_graph | 8192 | complete |
| gotcha__ipdb-224 | 23 | generate_causal_graph | 8192 | complete |
| neuroinformatics-unit__movement-432 | 15 | generate_causal_graph | 8192 | complete |
| scrapy__scrapy-7351_interface | 9 | generate_causal_graph | 8192 | complete |
| pypa__auditwheel-568 | 10 | generate_causal_graph | 8192 | runner_timeout |
| pypa__auditwheel-568 | 15 | generate_causal_graph | 8192 | runner_timeout |
| pypa__auditwheel-568 | 16 | generate_causal_graph | 8192 | runner_timeout |
| pypa__auditwheel-568 | 17 | generate_causal_graph | 8192 | runner_timeout |
| pypa__auditwheel-568 | 18 | generate_causal_graph | 8192 | runner_timeout |
| pypa__auditwheel-568 | 19 | generate_causal_graph | 8192 | runner_timeout |
| ilevkivskyi__com2ann-35 | 18 | generate_causal_graph | 8192 | complete |
| reata__sqllineage-503 | 11 | generate_causal_graph | 8192 | complete |
| hazelcast__hazelcast-python-client-380 | 8 | generate_causal_graph | 8192 | complete |
| pimutils__khal-969 | 16 | generate_causal_graph | 8192 | complete |
| olofk__fusesoc-724 | 9 | generate_causal_graph | 8192 | complete |
