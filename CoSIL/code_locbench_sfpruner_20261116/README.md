# Loc-Bench V1：CoSIL / SFPruner 100题先导评测

当前用户范围为**先测100题**。官方全560题的数据和CPU准备保留，不能在100题结束后自动继续剩余460题。只运行本地Qwen3-8B的CoSIL与既有4B剪枝模型的SFPruner；不训练、不生成补丁、不运行修复测试。

## 数据与抽样

官方数据为 `czlll/Loc-Bench_V1`，冻结revision `c44cf3b74e07ca642cec841b471a9939907c12a7`；Parquet SHA256为`8df0833c2c1276c5837aab923d489ab97d7654529abe759d0f59242c4978a662`。全量为560题、165仓库、1149个既有目标函数，另外的新增函数不作base版本既有函数目标。

先导100题按seed=20261116及`SHA256(UTF8(str(seed)+":"+instance_id))`升序固定，取前100题，不按预测或成绩挑题，不要求每仓只选一道。官方真实路径中的仓库短名组件原样保留，禁止剥前缀或将其脱敏成其他名称。单冒号只作官方字段的路径/限定名分隔符，转为严格的`path::qualified_name`身份。

实际先导样本为100题、64仓、98个repo/base归档键、199个既有目标函数，其中12题来自训练中出现过的仓库。父560协议中继承的68题同仓统计仅描述父池；本轮范围以`allocation.json`及`audits/pilot_scope_resolution.json`为准。

全560与本项目微调train/val的issue无交集；68题来自训练中出现过的6个仓库。报告应记录先导100中实际同仓数量，并另列描述性分组，不能称全部为跨仓未见任务。不打开本项目封存test；官方LocBench的公开`test` split是用户明确授权的评测数据。原Lite逐题矩阵、历史预测和论文不改。

## 方法与执行

Qwen3-8B与Reranker-4B+LoRA epoch1沿用原冻结权重。主模型BF16、TP=2、64K上下文、输出2048、temperature=0、seed=0、关闭思考，最多10轮搜索。剪枝模型参数为T=2.9846201034621833、low=0.12947567721292427、high=0.9。源码、issue、邻居渲染和工具协议复用原SFPruner工程。

本次固定两题并行调度以重叠CPU处理和4B判别等待；每道题仍为CoSIL先运行、SFPruner只复用同题文件候选，两个题目不共享对话、判断或预测。主模型服务仍为max_num_seqs=1。并行调度不是新模型、提示词或采样参数，temperature=0也不保证跨调度逐bit一致。调度器源码与worker数另行绑定SHA。

当前三张可用卡的计划为GPU2/3运行主模型、GPU1运行剪枝模型，GPU0他人任务保留。沿用90秒稳定准入、启动前复核、完整权重SHA检查、最长输入容量探针、逐臂3600秒上限。模型进程只读允许的base源码/结构，不能读`patch`、`test_patch`、`hints_text`、`edit_functions`或其他答案侧车。

同一repo/base可能对应多个issue：先对唯一归档键预热下载，成功缓存才交并行构建，避免同一`.part`竞态。不同issue不能因此合并或共享预测。准备失败、空输出、模型失败均单独标记；可评价但失败的题仍计入分母，不换题。网络沿用原固定生命周期次数，模型答案不作语义重试。监督程序最多启动3次基础设施队列，只继续未开始的臂，所有已开始记录和终态必须保持原字节。

源码准备使用4个独立CPU进程调用原`build_one`及同一静态图算法，避免Python线程的GIL串行化。新归档适配器仅将归档内部、同根且最终指向普通成员的Python链接解析为对应原始字节，不创建宿主软链接；外部路径、越根、循环和资源超限均拒绝。原tar SHA、链接链条、逻辑字节SHA和适配器SHA均落盘。首次线程构建的成功件只读核验后复用，失败与中断现场保留；这些均发生在任何模型请求之前。

## 指标

主表分别给出文件级和函数级Hit@1/3/5、宏平均Precision/Recall/F1@5；逐题数据还保留各k的P/R/F1、完整目标覆盖率和置信区间。Hit表示Top-k命中至少一个目标；Precision@k的分母固定k，Recall按整题完整既有目标函数集合计算，F1先逐题计算后宏平均。无效或重复排名不压缩。

官方兼容表单独运行固定版本的LocAgent评价函数，固定k=[1,3,5,10]，保留其初始化器归并、重复计数及Acc/Recall定义。不能把官方Acc直接标作本项目any-hit，不能把两个口径混为同一结果。新增函数不可能出现在base中，不并入既有函数主指标。

## 运行与复现

在CoSIL根目录，代码使用`.venv-v5/bin/python`；静态AST解析使用`/usr/bin/python3.12`。本地数据根目录：

```text
results/locbench_qwen3_sfpruner_20261116/           # 官方560下载与CPU准备
results/locbench_qwen3_sfpruner_20261116/pilot100/  # 只允许100题的独立运行
```

按以下顺序检查各入口：

```bash
.venv-v5/bin/python -B -m unittest discover -s code_locbench_sfpruner_20261116 -t . -p 'test_*.py' -v
.venv-v5/bin/python -B -m code_locbench_sfpruner_20261116.prepare --help
.venv-v5/bin/python -B -m code_locbench_sfpruner_20261116.pilot --help
.venv-v5/bin/python -B -m code_locbench_sfpruner_20261116.runtime --help
.venv-v5/bin/python -B -m code_locbench_sfpruner_20261116.parallel_controller --help
.venv-v5/bin/python -B -m code_locbench_sfpruner_20261116.report --help
```

正式模型执行前需有远端可恢复的代码发布回执、完整来源核验、controller prepare与报告输入冻结。主进程仅在`controller/launch_ready.json`明确READY且全部SHA匹配后启动：

```bash
.venv-v5/bin/python -B -m code_locbench_sfpruner_20261116.supervise \
  --wait --work results/locbench_qwen3_sfpruner_20261116/pilot100 \
  --poll-seconds 10 --max-infra-launches 3
```

监督状态写入`pilot100/controller/status.json`；队列状态写入`pilot100/service_queue/status.json`；完成后写`pilot100/completion.json`及`pilot100/reports/final/`。在全部可运行题的两臂和配对终态核验之前，报告不得读取离线目标评分。准备失败在固定allocation账中保留，不以缺少预测为由删行。服务结束仅清理具有完整身份回执的本次进程。

历史代码修改前恢复点：`8422b498669a87e4d902835500f594253211c357`（`snapshots/locbench-prechange-20261116`）。正式执行快照另记录。GitHub只发布代码、合成测试与说明，不上传数据、金标、模型、密钥、原始日志或封存test。
