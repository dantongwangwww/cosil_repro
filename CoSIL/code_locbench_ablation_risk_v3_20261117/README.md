# LocBench消融：Gold访问与直接剪除的离线修订v3

此包独立于正在推理的冻结24个Python源码。它不被worker、controller或reporter导入；不训练、不调用模型、不用GPU、不发进程信号，不修改原预测、概率、路由、Gold及封存报告。

原风险表把`path::qualified_name@def_line`运行时ID直接同`path::qualified_name`金标比较，导致Gold访问及直接拒绝假零。该错误不影响原严格文件/函数定位指标及调用账。此包在原报告封存后独立校验身份，再归因Gold；历史错误表保持原样，由新目录明确更正。

身份映射必须精确命中冻结render-cache，校验同base、缓存/index/图生成代码SHA、唯一文件和限定名、AST的`def_line/end_line`、原文件SHA及完整函数正文SHA。装饰器起点不能代替`def_line`，保留`__init__`和嵌套限定名。映射不读取Gold；只有验证完成后才判断Gold。未知、歧义或源码冲突记NA，不能当非Gold；未知存在时只报已验证下界，不伪造完整风险值。若共同访问比较任一条件归因不完整，两边风险、差值与全部区间也均为NA，只保留明确命名的已验证下界计数，防止同一函数先保留后未知拒绝被误记为零风险。

机器`protocol.json`的文件SHA与controller派生协议digest具有不同含义。验证链为执行冻结→run的`user_protocol_sha256`、manifest/authority/controller源码SHA→按原canonical JSON重算run digest→所有term/group/checkpoint同一派生digest；同时核其字节仍受sealed报告输入SHA绑定，不能把两种SHA强行设成同一个值。

首先独立核当前前缀全部三臂终态、整题闭合、`REPORT_COMPLETE`及封存输出SHA，之后才打开该前缀既有Gold。绝不使用旧report入口重新遍历58GB authority；仅核实际消费的缓存、库存、事件、函数源文件和封存输出。每个输出目录必须全新；没有对应封存报告的前缀直接拒绝，不能看未来标签。

```bash
.venv-v5/bin/python -B -m unittest discover \
  -s code_locbench_ablation_risk_v3_20261117 -t . -p 'test_*.py' -v
.venv-v5/bin/python -B -m code_locbench_ablation_risk_v3_20261117.analysis \
  --root results/locbench_qwen3_sfpruner_ablation_20261117_preflight_v2 \
  --n 100 \
  --out results/locbench_qwen3_sfpruner_ablation_20261117_preflight_v2/reports/risk_revision_v3/cumulative100
```

实际运行须先完成本包独立审阅与源码发布；这里的命令不是已执行声明。允许前缀为100/200/300/400/500/560。不轮询、不后台重算、不覆盖累计报告。

输出为`corrected_risk.json`、`逐事件身份与风险.csv`、`Gold直剪逐题.csv`、中文说明及输入/输出SHA清单。baseline无本地剪枝器，相关风险为NA。四个本地条件分别报告事件、唯一Gold身份及任务级访问/拒绝分母、灰区与类/技术兜底。未访问Gold不表示安全保留。Gold直剪逐题CSV附原封存定位Hit仅作描述，直接拒绝不必然导致最终失败，也不能推断Qwen复核的反事实选择。

身份条件风险采用预先说明的issue-bootstrap：5000次、seed20261110、每次按题重采样后计算计数和之比。共同访问Gold集合的比较仅作探索，不进入9项主检验。零事件bootstrap可退化`[0,0]`，不能证明真实零风险，因此另报“发生任一Gold直剪的已访问Gold任务/所有已访问Gold任务”的Clopper–Pearson二项95%描述区间。后者是在首100诊断后新增的辅助描述，不伪称原预注册检验。SciPy可用时使用beta分位；当前环境无SciPy，使用等价二项尾方程二分求解，边界解析；不安装依赖。两种区间均未校正同仓相关。
