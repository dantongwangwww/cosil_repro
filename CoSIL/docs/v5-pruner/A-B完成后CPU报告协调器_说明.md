协调器已经准备并在持久 tmux 会话 `v5-ab-report-coordinator` 中运行。当前任务只是等待真实A/B完成后生成CPU报告，不代表B已跑完、test已开箱、端到端定位已执行或整个v5完成。

计划收据：[plan.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/AB_final_report_coordinator_v1/plan.json)，SHA256 `28f3bab91932668bf4cb74d84e3c2c3c2c7ec2e7d2e3ec6ea07b1a49430274be`。当前状态与追加日志分别见 [status.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/AB_final_report_coordinator_v1/status.json)、[journal.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/AB_final_report_coordinator_v1/journal.jsonl)；协调器 stdout/stderr 保存在 [driver.log](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/AB_final_report_coordinator_v1/driver.log)。

启动时已经独立核验原A reranker/instruct与处方A rank8的实际best/last checkpoint：manifest、真实adapter rank/alpha/dropout/target_modules、checkpoint完成收据及binary SHA、保存train/val预测与原指标重算全部一致。三个CPU入口守卫也检查了test路径拒绝、错误adapter拒绝、snapshot相对链接迁移及缺失链接拒绝。没有载入Torch/Transformers/PEFT或任何模型。

循环每30秒检查已冻结代码、协议、A/B train/val/test字节SHA和真实执行状态。test仅二进制hash，不解码JSON或标签。若B失败、complete却没有真实summary/outcome、输入指纹漂移或链接目标不存在，会保存failure_receipt并停止；不补指标、不追认新指纹、不覆盖已有结果。

B 的 `B_runtime_reviewed_regularized_exploratory/sequence_status.json` 与 outcome、双底座pair状态全部真实完成后，按顺序执行：

1. 独立核B两底座真实best/last summary、adapter配置、完整checkpoint与train/val预测重算；rank8取已完成epoch的val accuracy峰值，instruct保持原规则。
2. 调用root `compare_noise_runtime`，使用处方A reranker＋原A instruct，对照配置匹配的B reranker/instruct；输出新 `A_post_vs_B_runtime_comparison_exploratory` 与此前不存在的A/B报告。
3. 取各自真实best epoch的保存B val概率生成reranker和instruct两份GoldRoutes诊断。不运行灰区Qwen，也不将默认阈值装入管线。
4. 重算root作图与总览接口，全部输出到本work下新的 `final_snapshot`。保留既有rolling总览和图；snapshot的本地链接按原 `docs/v5-pruner` 上下文转成真实绝对文件路径，figures指向新snapshot图，并逐一校验。
5. 写入 `final_report_receipt.json`，包括模型证据、共同val数量、全部新文件SHA、链接核验、未调用模型/GPU/API/test解码、矩阵未动与待root独立审核状态。

Verified完整500条官方输入已可用，但历史231题OOD保留池缺真实ID/source manifest，协调器末收据明确扩挖未执行。生成A/B验证对照也不能据此声称新定位准确率或v5成功。

[协调器源码](../../code_v5/coordinate_completed_AB_reports.py)位于独立新模块，未修改A/B冻结11/7文件。进程自然退出后，可以读取末收据；若失败则保留全部已生成证据，重新工作需另建新目录，不能覆写历史输出。
