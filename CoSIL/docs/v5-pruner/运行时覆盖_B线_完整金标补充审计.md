# B 运行时覆盖：完整 base 金标补充审计

2026-10-14。原采集代码、300 个永久 `result.json`、原始 trace、冻结执行策略和原终审报告均保留，没有重跑题目或修改历史资格字段。

独立核查发现，冻结采集器的 `base_gold_function_ids` 只取补丁 `target_regions` 的 before 侧。这会遗漏“补丁仅新增行，但新增行位于 base 已存在函数内”的金标。原 before 侧共246个函数；权威 `existing_gold_function_regions` 共321个，67题中共遗漏75个函数。原终审的金标完整性判据因此只适用于当时的 before 侧列表，不能把该字段当作全部 base 金标。

对原133个可用题另做完整金标校验：只有 Flask4045 的 `Blueprint.__init__@171`、Sphinx8273 的 `setup@113`、SymPy22840 的 `tree_cse@550` 属于额外遗漏金标；三者都已出现在原始真实覆盖函数并集中。因此完整金标复核后仍为 **133可用、167纯静态**，没有降级，也没有把旧纯静态题升级。pytest5103、sklearn10508 原来就是纯静态；补齐金标后仍有金标未观察到，保持原状态。

新B审阅源码包的同一 helper 问题导致旧30条包中9条金标源码为空，却标记 complete。数据作者在签审阅、训练前归档了旧14个原始文件，再按完整 `existing_gold_function_regions` 重建。独立核验确认：旧文件归档 SHA 全部匹配；新30条的候选及全部金标源码均与对应 base commit 的 Git blob、AST函数身份和完整源码 SHA 一致，9个空包已补齐，当前空包为0。

新旧 train、val 和30条待审阅样本的身份、输入、标签逐条相同；运行时不可用原因的诊断 metadata 有修正，因此不宣称新旧文件全部字节相等。旧、新 test 仅比较封存信息和字节 SHA，没有解码标签。30条审阅本身尚未由本审计代签，本审计不构成模型训练或能力结论。

审计收据：

- `results/v5_pruner/runtime_coverage/full_existing_gold_eligibility_upgrade_audit.json`：完整金标资格专项复核；SHA `4a07372ece3ad791216a2a8c55939063c11b29ce0142cafa87bf5d3df2e9d587`。
- `results/v5_pruner/B_full_existing_gold_packet_independent_audit.json`：由采集/审计代理核验另一代理生成的B源码包；SHA `79458ed3f3ea2f1c5effcb01505787d714b7d240b563feebb763dd46e7ccf871`。
- `results/v5_pruner/B_complete_base_gold_evidence_fix_receipt.json`：数据作者的修复与旧14文件归档记录。

运行时未观察不证明因果无关；该补充审计不改变原报告中关于函数体进入前报错、未经过上游包装函数及原生/硬退出路径的局限。
