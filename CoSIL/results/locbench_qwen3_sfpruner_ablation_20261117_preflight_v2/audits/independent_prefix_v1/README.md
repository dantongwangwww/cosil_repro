# 已封存前缀的独立主指标与资源审计

此目录是新的离线审计辅助代码。原 `audits/checkpoint100/independent_check.py`、生产 V2 的 24 个 Python 文件、风险 V3 的 6 个文件与所有已封存报告保持不变。`metric_reference.py` 的六个纯函数从首100审计器逐字复制，测试核 AST 相同；不导入生产 evaluator、controller、模型或 GPU 库。

支持明确指定 `--n 100/200/300/400/500/560`，没有轮询或自动启动下一个前缀。必须先有该前缀的 `REPORT_COMPLETE`、相同 allocation 和三臂完整 group 终态。先核 execution→用户协议→controller 派生 digest→term/group/checkpoint，再读取封存输出。全部 `original_work` 的历史 allocation 都须完整包含在已闭合前缀中，之后才允许打开其中任一批次的既有 Gold/inventory。Gold 沿用历史冻结规范化产物，不宣称重新提取 Gold。

核对同序 IID/五条件原预测、严格 Hit@1/3/5、P/R/F1@5、全部目标覆盖与 MRR、Wilson/冻结 issue-bootstrap CI、九项精确 McNemar/Holm 与配对四格表。重复与非法排名槽位不压缩，P@5 固定除5。源码准备阻断、上游文件阶段失败、worker/环境失败、缺失/损坏产物分别记账；可评价失败保留分母，上游阻断不被算成三次新的模型能力失败。

资源来自 HTTP start/receipt 并集和独立 judge RPC journal；缺失/错误/未闭合用量记 unknown，已知和只是下界。新文件模型调用必须为0。历史控制本轮新增调用为0，基线实际共享文件阶段的归一化总账单列；缺失共享账不补0。审计不改阈值、预测、模型或调度，不发信号。

200报告真实封存后，由监督者显式运行以下命令；当前准备阶段不执行200：

```bash
.venv-v5/bin/python -B \
  results/locbench_qwen3_sfpruner_ablation_20261117_preflight_v2/audits/independent_prefix_v1/audit_prefix.py \
  --n 200 \
  --out results/locbench_qwen3_sfpruner_ablation_20261117_preflight_v2/audits/checkpoint200/independent_checkpoint200_audit.json
```

其余前缀替换 `--n` 和全新输出路径；输出仅允许在当前 R2 的 `audits/` 内，拒绝覆盖。`--check-ready-only` 只检查公开封存与三臂终态，不读 Gold/指标，不产生文件；它也不会循环等待。

默认只核实际消费的任务 index、原预测、HTTP/RPC、历史批次冻结绑定和封存输出 SHA，不遍历整份 authority 的约58GB公开输入。最终560完成后，可在一次最终审计中显式加入 `--final-authority-rehash`；其他前缀拒绝该选项。该全量重核是单独记录的工作，当前没有执行，也不把默认 used-file 核验夸称为全部输入重核。

旧 sealed `route_risk` 的已知身份假零错误不在本辅助器的主指标/资源 PASS 范围内；应使用另行发布并审阅的风险 V3 输出。此入口也不声称证明报告与 GPU 并行；使用每个前缀单独保存的真实 CPU/worker/HTTP 时间交叠证据。issue CI 没有校正同仓相关，中间前缀结果仅作描述，不新增主检验。

验证方式：

```bash
.venv-v5/bin/python -B -m unittest discover \
  -s results/locbench_qwen3_sfpruner_ablation_20261117_preflight_v2/audits/independent_prefix_v1 \
  -p 'test_*.py' -v
```

合成测试只用临时文件；真实入口验证仅使用已封存首100。准备回执记录最终源 SHA、测试结果、首100回归及未读取后续 Gold 的范围。
