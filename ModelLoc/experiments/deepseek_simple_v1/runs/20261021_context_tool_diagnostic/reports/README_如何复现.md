# 如何复现本轮诊断

以工程根目录为工作目录，使用原CPU环境。先执行CPU测试：

```bash
PYTHONDONTWRITEBYTECODE=1 /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m unittest discover -s context_tool_diagnostic -p 'test_*.py' -v
```

仅在A全部分配题已落盘后，在独立进程生成离线报告：

```bash
PYTHONDONTWRITEBYTECODE=1 /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m context_tool_diagnostic.evaluate
```

也可用主CLI的 `--phase report`；该命令必须由独立控制进程调用，在线worker不导入评价器。评价只读原50题既有evaluator_private/<iid>/gold.json，所有含标签派生产物只写新RUN/reports，该目录在worker中隐藏。报告运行不调用API、模型、工具执行或历史报告main。历史严格身份入口为analysis.evaluation_extension.normalize_functions，统计函数来自src.metrics。

run_manifest.json冻结50题、SHA256前5冒烟和固定20题B2子集；resolved_config.yaml冻结模型/非思考/上下文边界。A-SIGNATURE与A-FULL仅源码区块不同；FULL超80K标context_overflow且不截断。原结果仅为观察参照。41题严格主分母包含实际失败；7题partial辅助指标只评分可映射函数子集，不代表整题完整gold召回，2题unmappable为NA。DeepSeek请求未固定seed，API别名不能独立锁定服务端权重快照。B1因严格DSL与旧宽松提取不等价而BLOCKED_FAIRNESS。B2是严格文本JSON，不能称native tool_calls。

必需CSV：ablation_pairwise、per_issue、method_summary、paired_comparisons、cost_ledger、tool_failure_taxonomy、tool_protocol_per_call；另有coverage_offline_audit、grouped_metrics、gold_direct_prune_offline和baseline_reproduction.json。B2同题机制/资源比较见b2_matched_method_summary.csv和b2_mechanism_pairwise.csv，旧与新均限定同20题、导航stage回执；旧全流程和新恢复阶段elapsed不能直接作节省比较。cost_ledger只含本轮新增请求。NOT_RUN与实际失败分别记录；未完成配对不计算推断统计。完整实验调用顺序及预算遵从根CLI，不由本离线报告触发。
