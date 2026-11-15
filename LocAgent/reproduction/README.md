# LocAgent同题复现与离线评价

本目录在固定上游LocAgent源码上适配本地Qwen3-8B及已冻结的SWE-rebench任务。先执行准备和金丝雀；只有真实运行终态才能形成最终成绩。Gold、历史预测和比较资源位于`run/private/`，不提供给推理工作进程。

## 评价入口

从LocAgent仓库根目录执行，CPU即可，无需加载torch或启动模型：

```bash
python -m unittest reproduction.test_evaluate -v
python -m reproduction.evaluate \
  --run experiments/qwen3_rebench100_20261115 \
  --output experiments/qwen3_rebench100_20261115/reports/evaluation_NEW
```

程序接口为`reproduction.evaluate.evaluate_run(run_dir, output_dir=None)`。不指定输出时在`run/reports/`下新建带UTC时间戳的目录；任何已有输出目录都不覆盖。每次输出`final_report.md`、`per_issue.csv`、`summary.json`和完整`evaluation.json`。

## 冻结输入与评分

- `selection/manifest.json`：固定题目与顺序；只按instance_id连接。
- `private/gold.json`、`private/inventory.json`：相同名册的R2既有目标和base库存。全部任务须有完整且非空的既有函数目标。
- `private/comparison_original.csv`：同题CoSIL基线与剪枝历史结果；先从冻结槽位重新评分，再逐指标核对原值，禁止按预测胜负另选历史版本。
- `outputs/<instance_id>/result.json`：LocAgent实际终态，包含`terminal=true`、身份、状态、官方MRR融合后的`found_files`/`found_entities`、真实usage和耗时。

直接调用已冻结的`CoSIL/papers/SFPruner/specprune/evaluation.py`，SHA256为`22b6c4c8c24da8b88bc09c0191ffe830d5ba375183e1d98c00577007adffe5aa`。迁移时可用`--evaluator`指定同字节文件，不能静默换评分器。函数只转换明确的`file.py:Qualified.name`为`file.py::Qualified.name`并在base库存中校验，不使用gold消歧、叶名猜测、类方法扩展或构造函数补入。无效或重复的最终槽位不压缩，P@5固定除以5。

LocAgent原生后处理在MRR融合前已经过滤不支持的图节点、合并重复并做自己的实体解析。本评价器保持的是官方**最终融合排名**，不能声称原始模型输出全过程都保留无效槽位。上游图及后处理的表示局限需要随结果披露。

本地推理环境为Python3.12.3（官方README同样要求Python3.12），LiteLLM由官方1.52.1兼容固定为1.53.1。通过`openai/locagent-native`逻辑别名启用上游原生工具调用分支，实际请求仍送往本地Qwen3-8B；这与上游按qwen名称自动选中的文本/XML工具分支存在协议差异，应明确说明，不能将源函数AST未改等同于所有运行行为逐项未变。

原生v1工程金丝雀暴露了无参finish可合法结束却没有结果文本的问题。修复前源码已发布到恢复点`f7ba4a29e4b4b04c5f02f62eb13f832ca1f65185`；后续使用独立run `qwen3_rebench100_native_payload_v2_20261115`。v2只给finish补必填`final_response:string`，继续由原FinishAction接收，三检索工具、任务提示词、搜索、原生后处理与MRR不变。前3题6个首请求逐字对照、实际payload与raw_location逐字匹配的证据在`audits/finish_channel_audit.json`；未注入旧答案或使用gold修输出。`complete`只表示两个loop均返回非空finish文本，不代表格式有效或定位正确；`prediction_status`另列非空函数/仅文件/后处理空预测。

v1的3题／6样本消耗72次HTTP、771132个已知token（输入766999、输出4133），属于前置工程阶段，报告与正式v2开销分列。它们不参与v2正式指标，也不作为新预测复用。v2名册、base快照、图和服务资产复用，但3题均在统一v2协议下生成新输出，正式100题只使用v2预测；工程开销没有被抹去。

原生后处理的两类问题需区分：根目录`top.py`即使遵循独立文件行格式也会被上游提取器漏掉，是普适实现局限；模型把`path.py:Class`当成文件头则不符合官方最终输出示例。二者均保留、披露，不对首3题或后续任务采用额外格式救分、不依据gold补候选。

LocAgent使用每题两个独立样本，temperature=1.0、top_p=0.8、repetition_penalty=1.05；历史CoSIL两臂各一次、temperature=0/seed=0。它是同底座、同题、同评价器的框架配置比较，未控制相同的采样次数与搜索预算。

`private/graph_coverage.json`是构图后隔离执行的只读审计：100题图均成功，但仅90题的全部既有目标均有独立函数节点，9题因官方图省略同步`__init__`节点、另1题因源码BOM导致官方AST解析跳过而缺少目标节点。缺节点不等于类/文件工具完全看不到源码；保留全部100题分母，不以gold补图或更换任务。评价器可附带该摘要，绝不能将此私有文件交给worker。

服务实际使用GPU1＋GPU3，经`nvidia-smi topo -m`核对为跨NUMA的SYS链路；历史CoSIL配置还涉及共卡评分器，因而墙钟时间不构成严格的调度/硬件加速对照。`service/model_identity_audit.json`记录对5个权重分片及7个配置/tokenizer文件的真实CPU SHA核验，报告在该回执可用时附上固定revision和匹配状态；API模型名不替代权重身份核验。

## 未完成、部分输出和失败

缺少最终回执或`terminal`不为true属于pending，不归为模型失败。此时报告整体标记PARTIAL，固定名册分数只表示暂时交付下界，不进行LocAgent对其他方法的正式配对检验；逐题CSV的pending评分留空。

`terminal=true,status=partial`表示两个样本中至少一个可解析、另一个失败；它已经终态，并使用真实官方融合输出评分，不通过新增模型请求救分。`terminal=true,status=failed`必须没有预测，按miss留在固定分母。全部任务终态后报告FINAL，执行错误、环境错误和单样本失败仍分别保留。

## 指标、资源与范围

文件及函数均报告Hit@1/3/5、Macro-P/R/F1@5、AllCoverage@5及MRR@10；Hit用Wilson区间，宏指标用任务bootstrap。正式同题Hit配对报告四格、差值、5000次配对bootstrap区间和精确McNemar检验，seed=20261110；多项探索性比较未作多重校正，不能据未显著宣称等效。

未知usage保留null；已知token下界另列，不能将未知费用或用量记为零。历史复用不重新记为本轮支出。历史剪枝组的物理token不含共享文件阶段，现有逐题比较CSV没有该阶段token分解，因此不能直接拿该列与LocAgent作全流程token优势比较；历史剪枝组可比时延补计同题文件阶段时间。模型启动、构图、worker在线及HTTP生成时间分别计账，缺项记NA。

`worker.elapsed_seconds`从模块导入和PromptManager初始化之后才开始，不能标作单题端到端。评价器另读每题真实`runner_receipt.json.wall_seconds`作为`runner_wall_seconds`，包含隔离工作进程的导入和执行，均值、中位数与nearest-rank P90单列；probe、模型启动、构图仍分别说明。全局并行墙钟由`controller/full_launcher.json.started`至最终终态文件mtime计算；首3题此前金丝雀耗时及从canary launcher至最终终态的v2总跨度另列，不把累计单题时间当成并行实验墙钟。未全终态时不给伪造的最终墙钟。历史两臂硬件与计时边界不同，只作描述。

本轮100题由指定280题父池确定性抽样；父池已按既有实验胜负排除18道基线优势题及2道双方未命中题。因此本轮属于条件化开发比较，不能表述为独立盲测，不能用其优势代替完整300题结果或推断总体优越性。不存在的LocAgent成绩必须保持待测，不能用论文原数、其他数据集或未执行任务填补。
