# 统一280题的只读工具与失败审计

这里保存已实际执行的两个分析脚本的字节副本，原件位于正式run的`audits/final_tool_failure_audit/`；不修改任何推理、规范化或评分代码。主审计须在全部280题ready后执行，只读取既有raw日志和已评分结果，不重放模型或检索工具。

需要先取得同源run资产及原始日志；这些数据、审计JSON和CSV不随代码快照发布。在LocAgent根目录使用以下命令，明确设置`PYTHONPATH`以使用当前checkout；脚本保留作者服务器的原SOURCE常量，其他机器也应通过当前checkout路径完成导入。

```bash
source .venv/bin/activate
PYTHONPATH="$PWD" python -B reproduction/audits280/analysis_wrapper.py \
  --run-dir experiments/qwen3_rebench280_unified_v2_20261115 \
  --evaluation-json experiments/qwen3_rebench280_unified_v2_20261115/reports/final_delivery/evaluation.json \
  --output /tmp/locagent280_audit_REPLAY_NEW

PYTHONPATH="$PWD" python -B reproduction/audits280/analysis_wrapper.py --self-test

python -B reproduction/audits280/reproduce_error_counts.py \
  --audit-dir experiments/qwen3_rebench280_unified_v2_20261115/audits/final_tool_failure_audit
```

`--self-test`包含5项独立CPU边界测试，已经通过；工具错误重计已实际PASS。完整工程173项测试与这5项单独审计测试分别记账，未声称178项整套复跑。

主分类使用统一found_files/found_entities，不依据历史prediction_status判空。301次工具错误是调用事件，涉及题目可重叠，不能当作301题定位失败；参数结构合法、运行时取值可接受、实际工具成功和最终定位正确是不同事实。代码不以金标补候选、不按测试或命中重新生成答案，不修改历史产物。
