# Java128最终独立核验

`code_multiswe_java_final_audit_20261117`只运行CPU核验，不训练、不调用模型。两个独立实现分别验证指标和原始/派生产物血缘；监督入口只在全128题、384臂终态及原/规范化报告流程闭合后运行。命令退出码0不能替代PASS，PENDING不算通过。

## 指标核验

`metrics_audit.py`不调用生产评价器的指标函数。先核源码/终态/分析完成及来源绑定，才能读取对应Java Gold；独立重算文件125/方法117分母、原排名槽、失败保留、Hit@1/3/5、宏P/R/F1@5、AllCoverage、MRR及95%区间，与JSON、CSV逐项对照。另列同题配对描述统计，不能把不显著解读为等效。

```bash
JAVA_ROOT=results/multiswe_java_qwen3_20261117_v2
.venv-v5/bin/python -B -m code_multiswe_java_final_audit_20261117.metrics_audit \
  --root "$JAVA_ROOT" --evaluation-dir "$JAVA_ROOT/reports/signature_v2_evaluation" \
  --view-root "$JAVA_ROOT/evaluation_views/signature_format_v2" \
  --out "$JAVA_ROOT/audits/独立指标复查_新名字.json"
```

原解析评价使用`reports/final128`且省略`--view-root`。输出路径必须是全新文件；不会覆盖失败回执。该审计复用冻结Java Gold，不能宣称另作人工全量金标裁决或重训模型。

## 血缘与资源复用

`lineage_audit.py`不打开Gold标签。穷尽核384终态；view manifest仅需精确对应实际存在原result的条件，合法无result失败须原/新同时缺失、终态一致并保留分母，不能补造预测。验证原始结果SHA、公开库存与base字节、原始回答未改、规范化重放、MRR、全部状态/usage/时延不变，以及calls/tools/judge RPC和资源表确实属于同一次物理推理。规范化视图不是额外模型实验，资源不能重复相加。

```bash
.venv-v5/bin/python -B -m code_multiswe_java_final_audit_20261117.lineage_audit \
  --root "$JAVA_ROOT" --out "$JAVA_ROOT/audits/独立血缘复查_新名字.json"
```

该核验不重新逐字节核全部模型权重，不读取项目封存test；模型版本/权重绑定与原始Java金标边界另有对应回执。每份审计均声明实际覆盖范围，不能用局部检查宣称整台服务器所有资产不变。

## 自动监督

本轮`independent_audit_supervisor/`等待规范化报告闭合，然后依次运行原解析指标、规范化指标、血缘资源三项独立核验。所有回执均为PASS才生成`ALL_THREE_INDEPENDENT_AUDITS_PASS`；任一错误保留现场，交根代理处理。它不会自动重跑模型、修改预测或替根代理宣布整个目标完成。

最后仍由根代理检查自有GPU服务/子进程退出、受保护历史范围、最终代码/聚合报告发布，并通知用户。逐题CSV、Gold、模型请求日志、权重和密钥只保留本地，不随源码快照上传。
