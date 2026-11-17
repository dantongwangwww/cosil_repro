# 本地持久等待与自有服务监督

`service_queue.py` 在CPU上等待准备好的公开任务与两张真正空闲的卡，然后按原协议启动本实验的主Qwen与剪枝服务。新增监督代码前检查点：`72bc8ba69c895ce03d56cd33ccaa2a140f1f6be6`。它不修改旧agent、Prompt、64K上下文、权重、dtype或阈值；不停止他人进程。

**验证状态：17项无GPU测试通过，另做本地tokenizer的合成输入构建检查；尚未实际GPU点火。** 测试覆盖资源门、启动前复核、命令参数一致、代码漂移拒绝、PID身份、有限基础设施重试、执行阶段禁止盲目重试、清理时自然退出及局部异常，以及标准库`queue`不被本地模块遮蔽。`queue.py`已移除，不能创建同名兼容stub。

## 等待条件

1. 运行清单存在；`controller.py --prepare-only`已完成所有选中任务。源码、job、配置、代码及冻结协议一致。
2. 相同两张卡连续90秒满足：`nvidia-smi`没有任何compute PID、实际`memory.free≥23000 MiB`、GPU利用率为0。
3. 启动前再次复查这两张卡，另要求`memory.used≤256 MiB`。瞬时利用率0且有他人进程的卡不符合条件。
4. 主Qwen端口7343空闲，固定模型与适配器SHA验证通过。没有下载和自动换模型。

等待期间轮询最大30秒，`status.json`与追加式`events.jsonl`持久记录状态。默认30秒；可设20秒以留出查询开销。GPU查询失败保留错误并继续等待，不伪造空闲状态。模型启动后心跳周期2–5秒。

## 命令

以下路径是参数示例，正式清单与输出目录由本轮数据准备冻结后提供：

```bash
# 仅查看完整启动参数，不查GPU、不创建服务。
.venv-v5/bin/python -B code_sfpruner300_20261114/service_queue.py \
  --plan --manifest /path/to/runtime/manifest.json --run-dir /path/to/prepared-run \
  --queue-dir /path/to/separate/service-queue

# 仅记录一次数据与GPU状态；即使条件符合也不会启动服务。
.venv-v5/bin/python -B code_sfpruner300_20261114/service_queue.py \
  --observe-once --manifest /path/to/runtime/manifest.json --run-dir /path/to/prepared-run \
  --queue-dir /path/to/separate/service-queue

# 明确进入持久等待；条件满足后自动启动原配置并运行剩余任务。
.venv-v5/bin/python -B code_sfpruner300_20261114/service_queue.py \
  --wait --manifest /path/to/runtime/manifest.json --run-dir /path/to/prepared-run \
  --queue-dir /path/to/separate/service-queue --poll-seconds 20
```

默认模型路径为已核验的本地Qwen3-8B与Qwen3-Reranker-4B，使用`papers/SFPruner/checkpoints/specprune_epoch1`。支持显式`--main-model-dir/--judge-model-dir/--adapter-dir`；目录与模型SHA必须匹配本轮冻结计划。queue目录与paired-run目录必须分开。

主模型命令逐参数对齐既有配置：TP2、BF16、max-model-len65536、原YaRN覆盖、max-num-seqs1、gpu-memory-utilization0.59、eager、seed0。剪枝常驻其中一张卡，仍使用原LoRA/温度/阈值；搜索请求继续由冻结的provider显式关闭思考。启动时做单独记录的合成健康与容量探针，它们不是题目预测，不进入定位指标。

## 所有权、恢复与失败

每个服务/控制器在独立session中启动，保存PID、UID、PGID、SID、start ticks、完整argv、cwd和命令哈希。关闭前逐项重新核验；未知或复用PID不发信号。只给证明属于本queue的进程组发SIGTERM，不发送SIGKILL。主服务、剪枝服务与paired controller均有独立日志和shutdown回执，完成后退出自己的模型服务。

重启queue时先根据旧receipt清理仍可确证归属的自有进程；不接管其他人的服务。随后等待新的90秒空闲窗口，继续同一prepared-run；`controller.py`核验并跳过已完成结果，保留已启动中断臂，不自动重抽回答。

在paired controller尚未启动前，基础设施加载/健康检查最多尝试2次，每次失败清理自己的服务并重新经过完整资源门。只要已启动paired controller，任何服务退出、控制器异常或超过180秒的心跳失效都会持久记录失败并退出，不自动重新运行任务。操作系统SIGTERM转换为有清理流程的退出；强制SIGKILL无法执行finally，下一次显式启动会依据自有receipt恢复清理。

`COMPLETE`表示全部选中任务都有终态账本，包括保留的失败/依赖阻塞，不等于全部定位成功。基础设施错误与worker原始失败保留日志，不能直接归因为模型能力不足。监督进程的异常会写`SUPERVISOR_FAILED`，不是无日志静默退出。

```bash
.venv-v5/bin/python -B -m unittest discover \
  -s code_sfpruner300_20261114 -p 'test_service_queue.py' -v
```
