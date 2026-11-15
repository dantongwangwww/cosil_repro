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
