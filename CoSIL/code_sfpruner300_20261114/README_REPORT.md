# 原100＋新增208的离线合并报告

`finalize.py` 为纯CPU后处理：读取原100真实输出、新208终态、R2既有函数目标及base AST库存，调用冻结的 `papers/SFPruner/specprune/evaluation.py`。它不训练、调用模型、生成补丁、执行测试或修改Word；不改历史预测。

## 必须先通过原100口径门

```bash
.venv-v5/bin/python -B code_sfpruner300_20261114/finalize.py \
  --audit-old-only \
  --out results/sfpruner300_20261114/reference_audit_new
```

程序从 `results/qwen3_rr4_rebench100_20261110/run/{baseline,hybrid_safe}/ID/result.json` 重新收集预测，逐槽与冻结公开导出核验，再按原R2资产重新评分。必须复现：

| 条件 | 函数Hit@1 | Hit@3 | Hit@5 |
|---|---:|---:|---:|
| baseline | 36/92 | 47/92 | 49/92 |
| hybrid_safe | 37/92 | 48/92 | 49/92 |

原100仍为100个任务，其中92函数可评价、8个函数NA；不把这8题变成不存在的函数答案。任一历史资格、SHA、预测位置或命中数漂移都会阻止合并。此门不读取旧分数来替代重新评分，也不重新运行原100的模型。

## 最终完整报告

默认路径与当前本轮布局一致，可显式覆盖：

```bash
.venv-v5/bin/python -B code_sfpruner300_20261114/finalize.py \
  --new-root results/sfpruner300_20261114 \
  --manifest results/sfpruner300_20261114/runtime/manifest.json \
  --run-root results/sfpruner300_20261114/paired_run \
  --qualified-root results/sfpruner300_20261114/qualified_prefix/cases \
  --out results/sfpruner300_20261114/final_reports
```

新增名单必须为208个完整非空R2既有函数目标任务，与原100的issue和仓库均不重叠；来源必须5题旧冻结版＋203题新增完整源。最终为308任务、300函数可评价任务（92＋208），文件指标按各组实际文件资格作分母。

报告还会读取已存在的 `selection/source_time_profile.private.json`（可用 `--source-time-profile`显式指定）。该画像只在选题冻结后描述上游PR `created_at`，不会参与过滤/补换题。当前已核验203题完整源日期为2014-12-23至2025-01-29；这不是模型训练截止时间，不能称为时间去污染评测或排除预训练覆盖。程序核对时间画像与原先固定的完整源ID/base完全一致，发现差异会拒绝报告，绝不根据日期改变题单。来源与这一局限均写入最终总览。

金标从各题 `qualification.private.json` 的 `R2_gold_path/R2_gold_sha256` 指针读取，兼容既有参考R2路径；评价只提取状态、完整性、既有目标身份与gold文件白名单。函数库存来自runtime每个job的code_index，并与paired-run准备回执SHA核验。原始patch和隐藏测试不传入任何模型；这个后处理进程没有模型入口。

完成门是新增208题×两臂均有可核验 `terminal.json`。明确的环境失败、超时、中断、worker失败及文件依赖阻塞可以成为终态，保持原始原因和固定分母，不伪装为模型能力结论。`complete/worker_failed`还必须有匹配的result SHA。缺terminal、仅有started或未封口result时不能自动出FINAL。

`--allow-partial`仅用于进度诊断：报告显著标记 `NOT_FINAL`，未执行和未完成分别为 `NOT_RUN/EXECUTION_INCOMPLETE`，不给未完成结果冒充最终预测。此模式也不写Word；不能把这种进度成绩作为最终300函数题成绩引用。输出目录必须全新，拒绝覆盖历史报告。

## 输出与口径

- `定位评测_合并总览.md`：中文总览，分原100、新208、合计308，另按新增来源各存独立评价。
- `summary.json`、各组 `*_evaluation.json`：文件/函数Hit@1/3/5、Macro Precision/Recall/F1@5、全既有目标覆盖@5、MRR@10及95%区间；同题四格、B−A配对区间、精确McNemar。
- `逐题定位与资源.csv`：原始排名位置验证后的槽位、评分资格、状态、出处、每题实际token/耗时及工具事件审计。
- `reference_audit.json`、`input_sha256.json`、`output_sha256.json`：旧口径门与完整输入/输出证据链。

无效函数身份占据原排名槽位，不补位或利用金标纠正。Precision@5分母固定5；Recall按各题完整既有目标集计算。Hit区间沿用Wilson；均值/配对差沿用原seed20261110、5000次issue bootstrap。区间不显著不能证明等效。

旧100资源为历史引用，不计为本轮新增消耗；新208为新增真实计算。资源优先读取每次API attempt回执，未知usage和未结束attempt不能记零；与worker阶段资源交叉核验。可比主模型token/时间为hybrid补记同题baseline文件阶段，物理调用不重复计算。平均耗时和token同时给实际记录数。外部API均为本地Qwen调用，费用0；GPU电费/折旧未测量，不能从token直接推导总成本下降。

工具指标取真实tool_io/source_returned/agent_seen/local_judge事件，不把非gold当语义负例；重复事件不当独立题。没有记录的资源与未知项保持NA。模型加载、GPU排队和CPU准备不包含在worker耗时内。

## 工程验证

```bash
.venv-v5/bin/python -B -m unittest discover \
  -s code_sfpruner300_20261114 -p 'test_finalize.py' -v
```

测试使用临时CPU fixtures，不产生可冒充实测结果的交付报告；实际原100口径回算单独落盘。新208未运行完时，不会生成虚构FINAL或改论文中的实验数字。
