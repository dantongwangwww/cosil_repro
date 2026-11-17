# 208题新增定位的持久串联

`pipeline.py` 将CPU准备检查、冻结控制器、冻结GPU服务队列和最终报告依次连接。它不会启动新的研究组、训练、解封test、修改Word或向外部发送通知。必须使用已冻结的208题selection；原100题复用，合计308任务、300个函数可评价任务。

在CoSIL根目录、具备宿主GPU可见性的既有环境中，由root协调者启动：

```bash
.venv-v5/bin/python -B -m code_sfpruner300_20261114.pipeline \
  --work results/sfpruner300_20261114 \
  --manifest results/sfpruner300_20261114/runtime/manifest.json \
  --builder-private results/sfpruner300_20261114/evaluator_private/runtime_build \
  --builder-identity results/sfpruner300_20261114/evaluator_private/runtime_build/process_identity.json \
  --archive-cache results/sfpruner300_20261114/archive_cache \
  --run-dir results/sfpruner300_20261114/paired_run \
  --queue-dir results/sfpruner300_20261114/service_queue \
  --reports results/sfpruner300_20261114/reports \
  --poll-seconds 20
```

由调用者使用`Popen(..., start_new_session=True)`持久启动并保存pipeline自身身份。脚本本身持有独占锁；每个子阶段同样使用独立session，记录PID、UID、start ticks、argv、cwd和控制台日志。`pipeline/status.json`和`events.jsonl`持续落盘。

准备门先检查全部208项manifest，再在CPU中核对选题、R2出处SHA、每个新目标是否存在于runtime索引、业务源码SHA、308个独立仓及300函数分母。原100题的200份输出先同冻结导出逐一比较位置/限定名/状态，并在整个流程中重复核对其原始SHA及8份评价/抽样出处SHA。控制器随后自己执行完整公开库存与隔离校验。

大型归档的`.part`活动计入准备活跃度；超过600秒没有完成计数但builder仍存活时显示陈旧警示，不杀builder。明确源错误或已记录builder身份消失时停止。已记录的正规化恢复计划/后继进程可等待；保留的v1失败不等同当前失败。恢复完成时须提供`runtime_build/finalization_receipt.json`，其READY/208/manifest SHA及独立恢复ledger SHA全部匹配才通过。未覆盖或删除v1阻塞证据。

控制器准备好后，service_queue仍按原规则等待两张真正空闲的卡稳定90秒。pipeline不会放宽显存、精度或上下文参数，也不会干预他人任务。queue维持此前已冻结的最多两次**真实题调用前**基础设施尝试；controller或真实题请求开始后不整批重试。pipeline自身每个阶段只启动一次，已启动但失败的stage留下证据并停止，正常错误答案不重抽。

仅当208×2个臂均有合法终结记录、配对进度完整且自有模型服务退出后才调用`finalize.py`。明确运行失败保留分母；缺终态不会被当作最终成绩。报告失败不会修改原预测，且不会自动重跑模型。最终状态`COMPLETE_REPORT_READY`还要求报告本身是FINAL、308任务/300函数，并通过其全部输出SHA核对。Word后续由root人工视觉核验后另行更新。

中断时只对本pipeline创建且UID/PID/start-ticks/命令/cwd/session仍匹配的子进程组发SIGTERM，由service_queue正常关闭其自有模型。不使用SIGKILL，不接管或终止别人进程；身份不符或清理超时会明确记录。

CPU检查：

```bash
.venv-v5/bin/python -B -m unittest code_sfpruner300_20261114.test_pipeline -v
```

10项测试已通过，包括真实普通CPU子进程session/身份、失败不重试、旧SHA漂移、精确目标身份、活跃大归档、陈旧但存活的builder、复用PID不误杀、正常退出与进程观察竞态、恢复ledger及历史阻塞区分。测试没有GPU或模型调用，也不产生真实实验报告。
