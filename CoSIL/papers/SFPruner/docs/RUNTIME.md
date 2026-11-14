# 独立运行与隔离

本包包含论文使用的真实 CoSIL 搜索循环、Prompt、工具分派、源码身份校验和两臂接入代码。`vendor/SOURCE_MANIFEST.json` 记录逐文件 SHA；`specprune` 包只提供可移动路径、输入导出、服务与隔离入口。默认不会启动 GPU 服务、调用模型或续跑历史实验。

## 1. 先做零 GPU 链路检查

在包根目录、安装本包依赖后运行：

```bash
python -m specprune.runner --help
python -m specprune.runner dry-run --out /tmp/specprune-smoke-new
```

此命令创建一个独立合成 Python 仓库，经过真实的 baseline / hybrid agent、工具参数解析、base 源码提取、源码送达、共享文件阶段和剪枝接入，但所有模型回答均为确定性 stub。`dry_run_receipt.json` 明确记为 `real_model_calls=0`、`gpu_used=false`、`not_benchmark_result=true`。这些输出不可加入论文成绩。需要 Linux `bubblewrap`；不可用时退出，不降级到非隔离运行。

## 2. 准备数据

论文 100 题的可移动输入位于 `assets/runtime/manifest.json`。每题 `job.json` 只有九个字段：`instance_id/repo/base_commit/problem_statement/cohort/snapshot/paths/code_index/structure`。其中三个路径相对 `job.json` 所在目录解析；整个包搬家后无需改作者服务器路径。源码快照仅包含修复前 `.py` 文件，缓存来自完整 base Python 库存。文件与函数金标单独放在评测资产中，搜索进程看不到它们。

这些运行资产不包含在仅代码的 GitHub 发布范围；完整本地投稿包包含。若需从已有干净准备结果导出：

```bash
python -m specprune.prepare_runtime \
  --export-manifest /path/to/sampling_manifest.json \
  --input-root /path/to/clean/inputs --out /path/to/new/runtime
```

导出依据既定 `selected_issue_ids` 原顺序，逐个校验 base 源文件 SHA；不重抽样、不读取预测或 gold、不复制补丁、训练记录或历史日志。也可以使用只含四个公共字段的 issue JSON 和本地 Git 仓库重建：

```bash
python3.12 -m specprune.prepare_runtime \
  --issue-json /path/to/issue.json --repo /path/to/repository \
  --out /path/to/new/prepared/issue_id
```

重建从指定 `base_commit` 的 Git blob 读取，忽略工作树修改。索引要求 Python 3.12，与原实验的函数 AST 索引一致。调用图会按运行 Python 的 AST 实现生成，因此复现原缓存优先使用随包提供的 byte-preserved 缓存。

## 3. 用户明确启动模型服务

准备两个公开模型的固定版本，模型权重不从本入口自动下载：

- Qwen/Qwen3-8B：`b968826d9c46dd6066d109eabc6255188de91218`。
- Qwen/Qwen3-Reranker-4B：`22e683669bc0f0bd69640a1354a6d0aebcfeede5`；加载随包 `checkpoints/specprune_epoch1`。

下载后先显式做一次 CPU SHA 校验，约读取 16.4GB 主模型与 8.1GB 剪枝底座文件；不会每题重新扫描主模型权重：

```bash
python scripts/verify_models.py --agent-dir /path/to/Qwen3-8B \
  --pruner-dir /path/to/Qwen3-Reranker-4B --receipt /path/to/new/model-verification.json
```

随后必须把同一已校验目录用于服务启动。`/v1/models` 返回的名字只是别名，不能据此证明权重身份；外部 vLLM 的启动命令、目录和此校验回执需要一同保存。剪枝服务加载前还会自行核验冻结底座与 LoRA SHA。

先检查 GPU 所有者和剩余显存，再选择空闲卡。原实验总计两张卡：Qwen TP2，常驻 4B scorer 与其中一张共存。以下 `0,1` 是示例，必须按实际空闲资源选择。

```bash
CUDA_VISIBLE_DEVICES=0,1 python -m vllm.entrypoints.openai.api_server \
  --model /path/to/Qwen3-8B --tokenizer /path/to/Qwen3-8B \
  --served-model-name qwen3-8b --host 127.0.0.1 --port 7343 \
  --tensor-parallel-size 2 --dtype bfloat16 --max-model-len 65536 \
  --hf-overrides '{"max_position_embeddings":65536,"rope_parameters":{"rope_type":"yarn","factor":2.0,"original_max_position_embeddings":32768,"rope_theta":1000000.0}}' \
  --max-num-seqs 1 --gpu-memory-utilization 0.59 --enforce-eager \
  --seed 0 --generation-config vllm
```

另一个终端明确启动剪枝服务（前台运行，结束时 Ctrl+C）：

```bash
CUDA_VISIBLE_DEVICES=1 python -m specprune.runner judge-server \
  --model-dir /path/to/Qwen3-Reranker-4B \
  --socket-dir /tmp/specprune-judge-new --device cuda:0
```

等待该目录 `ready.json` 出现。仅此显式命令加载 4B GPU 权重；`run-pair` 不启动、停止或修改任何模型服务。剪枝服务在单独 bubblewrap 中，仅可见程序、公开模型、适配器和部署参数；客户端只允许发送六个渲染后的文本字段，拒绝 gold/label/patch 字段。

## 4. 实际运行两臂

```bash
python -m specprune.runner run-pair \
  --job assets/runtime/ISSUE_ID/job.json \
  --out /path/to/new/results/ISSUE_ID \
  --main-model-dir /path/to/Qwen3-8B \
  --judge-socket /tmp/specprune-judge-new/score.sock
```

顺序固定为 baseline 后 hybrid_safe。baseline 的文件定位与反思阶段结果冻结后供 hybrid 复用；hybrid 不重新调用文件定位。两组都保留相同源码目录身份校验、最多十轮搜索、64K 上下文、2048 输出上限、temperature=0、seed=0、显式非思考；温度为零不保证 GPU 推理位级确定性。唯一核心区别是函数相关性路由：baseline 全交主 Qwen；hybrid 使用已校准 4B 概率和固定 low/high，灰区回主 Qwen；类请求仍回主 Qwen。

所有输出写入新目录，拒绝覆盖或隐式重放。`result.json`、`events.jsonl`、`sources/`、`calls/`、`context.json` 和 controller 状态保存真实输入输出与执行状态。模型失败保留结果，文件阶段失败不编造 hybrid 分数。RPC/评分服务错误及非有限分数按历史语义终止该题并落盘，不能把环境错误计成剪枝拒绝；只有原有身份/渲染失败会回退 Qwen。

全量入口按 `assets/runtime/manifest.json` 中 `records` 顺序逐题运行，无需自己编写循环：

```bash
python -m specprune.runner run-manifest \
  --manifest assets/runtime/manifest.json --out /path/to/new/rebench100 \
  --main-model-dir /path/to/Qwen3-8B \
  --judge-socket /tmp/specprune-judge-new/score.sock
```

每题目录为 `<out>/<instance_id>`，`batch_progress.json` 记录全部完成/失败/未执行题，`batch_complete.json` 保存固定分母。本入口不自动重试失败题、不换题、不覆盖历史结果。原实验固定100题，其中99题完成配对，1题文件阶段上下文失败必须保留分母。不要只收集 complete 行，也不要用未运行状态替代失败。

## 5. 隔离与版本证据

搜索子进程使用从空根文件系统开始的 bwrap 允许清单，只挂 OS/Python 库、包代码、该题修复前源码/结构/缓存、主模型分词器、冻结参数和本题输出。`assets/evaluation`、`assets/training`、用户主目录、其他实验输出和环境密钥均不挂载；环境变量清空重设，搜索 worker 不见 GPU。RPC 只返回分数，不携带评价标签。

包装时实际 CPU 链路验证环境：Python 3.11；torch 2.13.0、transformers 5.18.0、peft 0.21.2、vllm 0.30.0、openai 2.54.0、httpx 0.28.1、anthropic 1.11.0、tiktoken 0.14.0、libcst 1.9.0、pandas 3.0.6、numpy 2.4.6。该列表来自环境包元数据，不表示包装阶段重新进行过 GPU 推理。`anthropic`/部分旧工具库只为原 CoSIL 模块导入依赖，正式请求仍由固定 localhost Qwen provider 接管，没有 Anthropic/OpenAI 外部调用。

已保留的 v6 输入预算还依赖两份旧 tokenizer（0.6B reranker / Qwen2.5-Coder）；它们仅用于冻结文本裁剪，不加载其模型权重。更换这些 tokenizer、Prompt、上下文或阈值会构成新协议，不能直接与论文结果混称同一复现。
