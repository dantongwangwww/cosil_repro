# 统一280题：纯CPU分析与科学图复现

这些文件是冻结推理结束后的独立分析工具，不在`rebench_qwen3`运行guard中，不改变模型、工具、协议、预测或评分器。4个审计脚本逐字取自最终审计的analysis副本；绘图脚本只读取最终派生summary。原始数据、Gold、请求/响应/工具日志、CSV和模型均不随本代码发布，复核实际实验需要另行取得相同SHA绑定的本地运行归档。

## 严格评价与失败分析

在GraphLocator根目录使用既有代理环境，所有输出目录必须是新的。先等全280 worker终态且runner回执齐全，再运行：

```bash
source .venv/bin/activate
RUN=experiments/qwen3_rebench280_v3_20261116
ANALYSIS=analysis/qwen3_rebench280
EVAL=$RUN/reports/final_delivery/evaluation.json
python -m rebench_qwen3.evaluate --run "$RUN" --scope full280 \
  --output "$RUN/reports/NEW_FINAL_EVALUATION"
python -B "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" \
  --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/NEW_TOOL_AUDIT"
python -B "$ANALYSIS/graphlocator_scope_failure_stage_evidence.py" \
  --audit-script "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" \
  --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/NEW_STAGE_AUDIT"
python -B "$ANALYSIS/graphlocator_graph_inventory_coverage.py" \
  --audit-script "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" \
  --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/NEW_GRAPH_AUDIT"
```

最后的综合报告脚本还会附带分析源码副本；其原版从`/tmp`复制这3份源码，需要先将同名代码放在对应位置（若已有文件先核对，不覆盖不同内容），然后执行：

```bash
python - <<'PY'
from pathlib import Path
for name in ('graphlocator_v3_final_tool_failure_audit.py',
             'graphlocator_scope_failure_stage_evidence.py',
             'graphlocator_graph_inventory_coverage.py'):
    content = (Path('analysis/qwen3_rebench280')/name).read_bytes()
    target = Path('/tmp')/name
    if target.exists() and target.read_bytes() != content:
        raise SystemExit('Refuse to overwrite different file: '+str(target))
    if not target.exists():
        target.write_bytes(content)
PY
python -B "$ANALYSIS/graphlocator_compile_failure_report.py" \
  --run-dir "$RUN" --evaluation-json "$EVAL" \
  --tool-dir "$RUN/audits/NEW_TOOL_AUDIT" --stage-dir "$RUN/audits/NEW_STAGE_AUDIT" \
  --graph-dir "$RUN/audits/NEW_GRAPH_AUDIT" --output "$RUN/audits/NEW_FAILURE_REPORT"
```

所需`/tmp`文件名为`graphlocator_v3_final_tool_failure_audit.py`、`graphlocator_scope_failure_stage_evidence.py`、`graphlocator_graph_inventory_coverage.py`，内容即本目录的对应文件。该历史分析路径约束如实保留，没有为了发布而修改其语义。参数说明以各脚本`--help`为准；模型与工具不会重放，不打开private Gold，最终evaluation中的目标信息仅用于事后归因。

## 四臂函数Hit与95%CI科学图

单独建立CPU绘图环境，不能向冻结代理`.venv`安装绘图包。本次实际环境为CPython3.14.7、matplotlib3.10.7，完整依赖锁在`requirements-plot-locked.txt`。

```bash
python3.14 -m venv /tmp/NEW_GRAPH_PLOT_ENV
/tmp/NEW_GRAPH_PLOT_ENV/bin/python -m pip install -r analysis/qwen3_rebench280/requirements-plot-locked.txt
cd analysis/qwen3_rebench280
/tmp/NEW_GRAPH_PLOT_ENV/bin/python -m unittest test_plot_final_function_hits -v
cd ../..
/tmp/NEW_GRAPH_PLOT_ENV/bin/python analysis/qwen3_rebench280/plot_final_function_hits.py \
  --summary experiments/qwen3_rebench280_v3_20261116/reports/final_delivery/summary.json \
  --output-dir experiments/qwen3_rebench280_v3_20261116/reports/NEW_FINAL_FIGURE
```

5项合成CPU测试已全部通过，含明确SYNTHETIC标记的图片渲染和拒绝覆盖。绘图要求FINAL/full280/280终态、四臂分母280、280runner回执齐全及固定协议/评分器/采样profile；不满足即拒绝。生产图从最终summary只读生成，输出PNG/SVG/PDF及本地来源哈希回执。源码不打开Gold、原始预测或HTTP日志，不调用模型或GPU。图中柱上为命中题数、柱高为百分比、误差线为Wilson95%CI，开发池选择偏差及不同预算限制仍须随图披露。
