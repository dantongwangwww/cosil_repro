# LocBench：GPU续跑与CPU核对并行

2026-11-16用户补充要求：每完成100题核对结果时，后续推理继续，不等待核对完成。

本包只调整报告调度。`code_locbench_sfpruner_20261116`、`code_locbench_full_20261116`及原100题、所有已开始的输入/预测均不改写。Qwen3-8B、Reranker4B与既有LoRA、提示词、阈值、搜索上限、每题CoSIL→SFPruner顺序、两题并行和主服务max_num_seqs1保持冻结。

## 执行方式

GPU总监督器复用原`launch_queue`及进程身份保护；每批所有可运行题两臂和pair终态完整、该批自有GPU服务实际释放后，写`batch*/controller/gpu_completion.json`并立即准备/启动下一批。此标记仅表示GPU批次结束，不冒充报告完成。

独立CPU报告进程按固定顺序消费上述标记，先核全部终态、protocol/arm/result绑定与来源SHA，才读取该批离线金标承载评价文件。随后输出当批及累计200/300/400/500/560题报告。原100题只读复用，准备失败保留分母；未来未结束批次不提前评分。

报告进程使用`CUDA_VISIBLE_DEVICES=''`，状态写`reports/async_status.json`，不覆盖GPU进度。只有报告完成才写各批`completion.json`；全部GPU与全部报告均完成后，才写总`completion.json`为`COMPLETE_REPORT_READY`。报告结果不控制后续选题、阈值或模型。

后续GPU不等待报告任务；批次间仍保留原资格校验、GPU空闲准入和模型服务切换所需间隔。这些间隔不是等待统计结果。并发CPU核对可能影响磁盘与worker耗时，报告应披露这一调度变化，不将不同调度阶段的时延差直接解释成方法加速比。

## 正在运行任务的接管

改动前恢复点为`156f63f190d8d8140f000456be3cbda0210d8a62`。现有10份续跑文件及69项继承绑定已与远端重新核对，本包另行测试、发布和冻结，旧execution/report freeze保持原字节。

旧总监督器的SIGTERM异常清理会停止队列，因此接管使用系统Python3.12的pidfd接口，仅向完整UID/PID/start_ticks/argv/cwd/session匹配的旧顶层监视进程发送SIGKILL；不使用killpg，不向GPU队列、模型或worker发送信号。当前队列是独立session，新监督器精确接管它；接管前后核对队列身份和已存在started/result/terminal字节。接管意图、源绑定与结果均落盘，PID复用或未知身份一律拒绝。

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/CoSIL
.venv-v5/bin/python -B -m unittest discover -s code_locbench_async_20261116 -t . -p 'test_*.py' -v

# 完成远端恢复验证与独立代码门后，先做仅监视器接管：
.venv-v5/bin/python -B -m code_locbench_async_20261116.supervise \
  --handoff --root results/locbench_qwen3_sfpruner_20261116/continuation460

# 然后通过已存在recovery.start_or_adopt持久启动以下命令：
.venv-v5/bin/python -B -m code_locbench_async_20261116.supervise \
  --root results/locbench_qwen3_sfpruner_20261116/continuation460
```

新发布回执放`audits/async_execution_publication/publication_receipt.json`；新监督/报告源码与原来源的联合冻结放`controller/async_execution_freeze.json`；接管前后证据放`controller/async_handoff*.json`。以上均在本次continuation460根目录，不上传数据/预测/日志/金标/模型到GitHub。

## 异常与恢复

完整报告只读验证复用；中断的报告目录保留原字节后仅CPU重算，不重跑模型。普通报告I/O错误最多进行三次CPU尝试，独立记录，不能算作模型失败；来源/终态/名单完整性错误单列`FATAL_INTEGRITY_ERROR`并阻止新批启动。已开始实验臂遵从原never-replay规则，任何失败都不通过换题或模型答案重抽消除。

本轮只运行当前两臂，不训练、不增加消融、不修复补丁、不读取封存test、不改论文或旧Lite矩阵、不影响他人进程。
