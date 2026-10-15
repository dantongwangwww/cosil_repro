CPU 报告协调器 v3 已于 2026-10-14 18:08:51 完成，只使用实际完成的 A/B train/val 记录。新快照位于 [v5 总览](../../results/v5_pruner/AB_final_report_coordinator_v3/final_snapshot/实验报告_v5_总览.md)，尚待根代理独立审核与发布。它没有载入模型、调用 API、使用 GPU、解码封存 test，或新增定位预测与结果矩阵列。

[最终收据](../../results/v5_pruner/AB_final_report_coordinator_v3/final_report_receipt.json) SHA 为 `7eadc13da7314b70244040bf2718cd0a3c28b79da531f57211a0de0f4ac5f28a`，[执行计划](../../results/v5_pruner/AB_final_report_coordinator_v3/plan.json) SHA 为 `8d235c005777f7b1db9f7472144b7209d6d51ec2a127f8468ceebd2608a2db06`。13 个产物 SHA 均一致，33 个本地链接全部存在；绝对路径、仓库相对路径与原文档相对路径分别规范化，figures 指向新快照。

历史两次停止都保留真实证据。v1 错把 B outcome 的 `summary_path` 当成 A 处方 outcome 的 `training_summary_path`，见 [v1 失败收据](../../results/v5_pruner/AB_final_report_coordinator_v1/failure_receipt.json)。v2 已完成真实 A/B 对照与路由、曲线生成，但将 `docs/v5-pruner/实验报告_v5_A线_v3噪声披露exploratory.md` 再拼到文档目录，链接守卫拒绝并停止，见 [v2 失败收据](../../results/v5_pruner/AB_final_report_coordinator_v2/failure_receipt.json)。v3 没有修改两版源文件、计划、失败或部分输出，而是独立实现实际 schema 和精确路径回归。

v3 对已生成的 [A/B 对照](实验报告_v5_A-B_噪声披露与覆盖过滤对照.md) 做 SHA 核对，并从真实 summary、adapter 配置、保存概率及共同 345 个输入／标签相同的 issue/function pair 重算全 val、共同 val 与 issue 簇 bootstrap 区间，结果完全复现后只读复用，未再次调用 writer。B 两底座三分路由各用实际 best epoch，灰区 Qwen 没有运行；曲线只含真实完成 epoch。原滚动总览与图未由协调器覆写。

新快照按最新用户裁定注明：官方 Verified 500 减 Lite 93，407 题经过真实 Git／patch／AST 核证，保留 221 题（13 题无函数金标，未来函数评测 NA、分母 208），186 题静态挖矿与独立 CPU 运行时覆盖已经实际启动。历史缺来源的“231 池”没有被宣称恢复；融合数据、训练、正式 OOD 评测及端到端定位仍是后续工作。A/B 的探索性 val 差异也不能单独证明噪声过滤的因果效果。
