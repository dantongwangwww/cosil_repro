# 冻结两臂协议的独立续跑控制器

`controller.py` 仅包装已冻结的 `papers/SFPruner/specprune.runner` 的公开输入准备、隔离和 `_worker`。它不抽样、不训练、不启动或停止 vLLM/剪枝服务、不访问金标或封存 test。新增代码前已发布恢复快照：`d6d3502152eb75da3b922aac4cb5bc220a344e44`，分支 `snapshots/sfpruner-pre-300-20261114`。

**当前验证状态：12项CPU工程测试通过，并对一个已有真实任务做过无模型的准备烟测；尚未进行本控制器的真实GPU点火验证。** CPU fixture 的输出均标记 `simulation=true`，不可记入实验结果。当前目录没有正式300题名单；补题来源、隔离条件与函数可评价规模必须先由单独的抽样协议确定。

## 输入格式

运行清单必须具有 `n` 和 `records`，每条至少包含：

```json
{"schema":1,"n":1,"records":[{"instance_id":"owner__repo-123","repo":"owner/repo","base_commit":"40位SHA","job":"task/job.json","job_sha256":"job文件SHA256"}]}
```

`job` 必须是相对清单父目录的包含路径，不能为绝对路径或越级路径。`job.json` 使用论文包九键公开协议：`instance_id/repo/base_commit/problem_statement/cohort/snapshot/paths/code_index/structure`。源码快照只允许 `.py`，需要与索引完整匹配并逐文件核验；代码索引、结构和渲染缓存来自 base revision。原始抽样审计可以单独保存，不能把 gold/patch/label 字段塞入运行记录或 job。

控制器不要求恰好300题；必须保持真实分母。它不根据历史预测、金标或运行结果补题/换题。`sample.py` 的资格与容量审计不是运行清单，仍须将选中的公共任务准备成上述 clean-job 清单。

## CPU准备与真实运行

在 CoSIL 根目录执行：

```bash
.venv-v5/bin/python -B code_sfpruner300_20261114/controller.py \
  --prepare-only --manifest /path/to/runtime/manifest.json --out /path/to/new/run

.venv-v5/bin/python -B code_sfpruner300_20261114/controller.py \
  --run --manifest /path/to/runtime/manifest.json --out /path/to/new/run \
  --main-model-dir /path/to/pinned/Qwen3-8B \
  --judge-socket /path/to/already-running-judge/score.sock
```

`--prepare-only` 不联网、不加载模型、零GPU；固定输入、代码、协议和 staged 源码哈希。`--run` 要求同一份清单及代码，先验证全部准备结果，然后检查已存在的本地主Qwen和常驻剪枝服务。主模型权重按论文包的固定SHA做CPU校验，worker只挂载逐文件白名单复制的同版本tokenizer，不挂载整个模型目录。外部模型服务的固定启动命令与目录回执仍须保存；`/v1/models` 名字本身不能证明服务端权重身份。

真实运行严格沿用两臂 `baseline/hybrid_safe`、原Prompt与agent、64K输入、2048输出、BF16/TP2主模型配置、非思考、seed=0和既有温度及阈值。服务启动与GPU选择仍按论文包 `docs/RUNTIME.md` 执行；当前显存不足时应等待空闲资源，不由本控制器降低精度、上下文或切换CPU评分器。

## 恢复、失败和进程保护

- 完整结果按哈希核验后跳过；不会重新发送已完成请求。
- baseline有完整结果、hybrid尚未启动时，只恢复hybrid。共享文件输入从baseline原始文件阶段结果重建并核验，不根据评价答案修正。
- 文件阶段是否可复用与冻结 `runner.run_pair` 一致：baseline必须有 `ranked_edit_files`；缺失时hybrid记 `dependency_blocked`，不发模型请求。
- `started.json`存在、`result.json`缺失且原进程已消失时记 `interrupted`，保留所有已产生的调用，不自动重抽整个臂。进程仍在时拒绝重复启动。
- 未运行、worker返回失败、控制器失败、超时、中断、依赖阻塞分别记录；所有选中题保留分母。`worker_failed`保留原始错误且不擅自归因为模型能力不足，环境/输入/模型原因由后续审计依据日志区分。
- 每臂deadline为原协议3600秒；心跳及PID/UID/进程组/session/start-ticks/命令哈希证明归属。只给当前控制器创建且身份仍吻合的独立进程组发SIGTERM；PID复用或身份未知时不发信号。
- `freeze.json`、逐题 `prepared.json`、逐臂 `started.json/process.json/result.json/terminal.json`、`shared_receipt.json`、`pair_terminal.json`及 `progress.json` 保存全部状态；锁禁止同目录两个控制器并发运行。

控制器不自动修复或重试已失败的模型输出。变更输入、代码或协议需要新目录和明确的新运行说明；不得通过覆盖状态来救分。

## 已完成的CPU验证

```bash
.venv-v5/bin/python -B -m unittest discover \
  -s code_sfpruner300_20261114 -p 'test_controller.py' -v
```

12项测试覆盖：真实stage+fake执行与完成后不重跑、只续未启动hybrid、文件依赖失败、精确ranked_edit_files资格门、已启动中断不重抽、job/协议漂移拒绝、源码及私有文件污染拒绝、共享结果篡改拒绝、已完成预测不变、越界/私有字段/重复ID拒绝、未知或复用PID不误杀，以及fake/real协议隔离。

真实旧任务准备烟测位于 `results/sfpruner300_controller_cpu_smoke_20261114/`，仅确认源码、索引、缓存和隔离输入准备可复用；没有新定位预测或正式题单。
