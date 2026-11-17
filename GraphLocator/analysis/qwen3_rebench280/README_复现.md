# 纯CPU复现

在GraphLocator根目录执行。`RUN`指本V3完整run目录，`ANALYSIS`指本报告analysis目录。先运行各脚本`--help`。输出目录必须不存在，以免覆盖历史。

```bash
RUN=experiments/qwen3_rebench280_v3_20261116
ANALYSIS=$RUN/audits/final280_failure_report/analysis
EVAL=$RUN/reports/final_delivery/evaluation.json
python -B "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/recheck_tool"
python -B "$ANALYSIS/graphlocator_scope_failure_stage_evidence.py" --audit-script "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/recheck_stage"
python -B "$ANALYSIS/graphlocator_graph_inventory_coverage.py" --audit-script "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/recheck_graph"
python -B "$ANALYSIS/graphlocator_compile_failure_report.py" --run-dir "$RUN" --evaluation-json "$EVAL" --tool-dir "$RUN/audits/recheck_tool" --stage-dir "$RUN/audits/recheck_stage" --graph-dir "$RUN/audits/recheck_graph" --output "$RUN/audits/recheck_report"
```

四个脚本只读已有产物；模型/工具不重放，不读取private金标。评价里已有的gold只在全280终态且同协议SHA校验后用于离线归因。图库存脚本对controller生成的超时终态，使用原始run_start日志三身份+图SHA核验，不补写结果字段。
