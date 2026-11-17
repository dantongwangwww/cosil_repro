# 隔离GPU判别器的系统运行依赖

`judge_launcher.py`保留已发布SpecPrune包的原评分器、模型、LoRA、长输入格式和阈值，只包装隔离命令的生成过程。GPU判别器需要Triton首次编译CUDA运行接口；Triton通过`/sbin/ldconfig -p`查找libcuda。原隔离配置已只读挂入系统库和链接缓存，但缺少该可执行文件。

本部署层仅补入两个只读文件：宿主`/usr/sbin/ldconfig`到隔离环境`/sbin/ldconfig`，以及Debian入口脚本使用的`ldconfig.real`。CPU定位工作进程不增加任何挂载。不挂载用户主目录、密钥或评价金标；冻结`papers/SFPruner/specprune`和vendor源码字节不变。

队列方案记录launcher SHA；启动后变更launcher会停止方案核验。每次服务的受限环境写入独立session中的`runtime_environment.json`，明确保留原100题实际使用的`VLLM_USE_FLASHINFER_SAMPLER=0`、cu13工具链及`MAX_JOBS=2`。HF、Triton、FlashInfer缓存使用本轮目录。

本轮前置失败均发生于真实题目启动前，原目录及RPC错误保留。新增题不会因为预测失败而重跑。新增代码前检查点为用户GitHub提交`808d71386a3b30d0dcadad17a6edddb7e2bc21ad`，远端文件与本地逐字核验一致。

针对性检查命令：

```bash
.venv-v5/bin/python -B -m unittest \
  code_sfpruner300_20261114.test_judge_launcher \
  code_sfpruner300_20261114.test_service_queue \
  code_sfpruner300_20261114.test_pipeline
```

32项通过。另在同隔离环境执行了零GPU烟测：ldconfig查询、真实Triton driver.c编译、libcuda链接发现全部通过；未加载生成模块或模型。实际回执另存`results/sfpruner300_20261114/judge_isolation_cpu_smoke_receipt.json`。CPU烟测不代表GPU模型健康检查已通过，后者由服务队列实际请求验证。

本轮最新监督入口由`results/sfpruner300_20261114/active_execution.json`确定。不要在已有监督器存活时另启同端口服务或重复控制整批输出。

## 独立判别器显存与续跑

实际长输入健康检查后，判别器保留的显存会挤占共卡主模型的prefill空间。主模型的TP2/BF16/64K/0.59等原参数不变；可用`pipeline --judge-gpu 1`把同一判别器部署到第三张卡的剩余显存。主模型两卡仍要求完全无计算进程的90秒稳定门。

第三卡的保守准入由`gpu_spare.py`实现：至少16GiB剩余、利用率0、无任何宿主可见计算PID、连续90秒稳定。仅允许事先核验的NVML残留PID1632241，要求名字[Not Found]且宿主/proc明确不存在；查询或权限错误一律拒绝。它不证明整卡独占或残留所有权，不发送信号、不重置显卡、不清理残留。启动main及judge前均复查。

`controller_continuation.py`不改原controller源码与协议。它仅允许旧runtime回执的judge_socket变化，把新绑定追加到`runtime_continuations`；主模型revision、verified文件数、tokenizer库存与字节必须一致。已started的臂保持其真实终态，从不重放。首次运行没有旧runtime时直接使用原controller。

本轮首题基线因共卡OOM中断，输出与usage不完整，保留分母并单独标为环境事件；没有据此换题或重新抽模型输出。新监督目录为`pipeline_sparejudge`与`service_queue_sparejudge`。新增资源门、续跑及集成检查共64项通过，论文另存稿分开披露原100与新增208的硬件范围。
