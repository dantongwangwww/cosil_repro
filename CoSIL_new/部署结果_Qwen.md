# 新版 CoSIL + Qwen 部署结果

2026-10-07 部署完成。新版位于 `/home/wdt/cosil_repro/CoSIL_new`，与现有 `/home/wdt/cosil_repro/CoSIL` 同级。旧项目的代码、300 题实验结果和报告保持原样。

来源：[作者仓库 ZhonghaoJiang/CoSIL](https://github.com/ZhonghaoJiang/CoSIL/tree/0568e423735b399d5b089996961fea9ae142e4c7)，上游提交 `0568e423735b399d5b089996961fea9ae142e4c7`。本次是含 Qwen 协议适配的部署版本，补丁保存在 `deployment/local_changes.patch`。

## 环境与文件

- 复用 conda `cosil`，新增 LiteLLM 1.103.3 及缺失依赖；安装前后核对全部已有包的版本，未升级或降级已有包。新增依赖清单为 `deployment/added_requirements.txt`。
- `repo_structures` 和 `CoSIL/repo_structures` 软链到旧项目的 `repo_structures_verified`；本地 SWE-bench Lite 数据集覆盖 300 题，全部对应结构文件存在。
- 模型仍为本地 Qwen2.5-Coder-7B-Instruct，路由 `openai/llama3`，端口 7333；温度 0，上下文上限 65536。
- 包名冲突通过 `CoSIL.py` 改名 `CoSIL_core.py`、更新导入和补齐包标识修复；核心模块内改用完整包导入。
- 用 `COSIL_MAX_CONTEXT_TOKENS=65536` 覆盖未知模型别名的 100000 默认值，使预算与实际服务一致。
- 项目环境变量集中于 `scripts/qwen_env.sh`，未追加到用户全局 `.bashrc`。

## 原生工具调用与适配

原服务没有开启自动工具调用，实际请求返回 HTTP 400。核验服务空闲后，保留旧启动配置并重启同一个 Qwen 模型，追加 `--enable-auto-tool-choice --tool-call-parser hermes`，继续使用 GPU 0、相同模型权重及批次不变推理设置。当前 tmux 会话为 `llm-qwen-native`，日志为 `results/service/vllm_native.log`，启动脚本为 `scripts/start_qwen_native_tools.sh`。Qwen2.5 的 Hermes 配置依据 [vLLM 官方工具调用文档](https://docs.vllm.ai/en/latest/features/tool_calling/#qwen-models)。

原始单题验证发现：模型把工具调用写成 Markdown 中的 JSON，响应中没有实际 `tool_calls`，上游循环因此直接结束。完整原始函数级记录保留在 `results/canary/attempt_1_original_auto_func/`。

为使 Qwen 的原生调用链能够执行，启用 `COSIL_RETRY_TEXT_TOOL_CALLS=1`：仅当 `auto` 返回描述现有工具的 JSON 文本、却没有结构化调用时，适配层追加一次格式纠正请求，使用原生 `tool_choice=required` 和单工具调用。实际执行只依据服务返回的结构化 `tool_calls`，不解析或执行文本中的伪调用。正常原生调用、普通文本停止和最终总结保持原行为；每次最多纠正一次，第二次仍无结构化调用则报错。重试的原始文本和两次请求用量会被保留。将该变量设为 0 可关闭适配，检查中已验证此开关。

这项适配属于当前部署版本的额外改动，后续对照实验应注明，不能称为完全未经修改的上游结果。它解决调用协议问题，不保证模型选择的函数正确。

## 单题验证

题目为 `astropy__astropy-12907`，新版自行生成文件候选，再送入新版函数搜索；未读取旧版文件定位结果。

- 文件级：`results/canary/file/loc_f.jsonl`，恰好一条目标题记录，首个文件为 `astropy/modeling/separable.py`。
- 函数级：`results/canary/func/loc_func.jsonl`，恰好一条目标题记录，包含 `separable.py` 的函数定位。
- 主搜索实际执行一次原生源码查询，取得 `separability_matrix`；pruner 发起一次侦查工具调用并返回 True，原始源码随后进入搜索及最终总结上下文。pruner 的侦查调用指定了不存在的类，返回查询错误反馈，这属于本题模型选择行为，不能称为无工具错误运行。
- 最终推荐未命中 gold `_cstack`。部署验收依据入口、路由、原生调用、源码传递、pruner 与输出解析是否运行，未用定位准确率筛选验证结果。
- 已核验指定工具调用与普通聊天可用；格式纠正的 5 项检查通过，覆盖正常调用不重试、普通文本可停止、关闭适配恢复原行为、纠正失败不无限重试及 token 用量合计。

证据集中于 `deployment/deployment_manifest.json`、`offline_checks.json`、`native_tool_health.json`、`native_format_checks.json`、`native_compatibility_audit.json`，以及各阶段原始日志。

## 运行命令

单题验证：

```bash
cd /home/wdt/cosil_repro/CoSIL_new
bash scripts/run_qwen.sh canary
```

全量 300 题文件级，再运行 300 题函数级：

```bash
cd /home/wdt/cosil_repro/CoSIL_new
bash scripts/run_qwen.sh full
```

也可以分别运行 `bash scripts/run_qwen.sh file` 和 `bash scripts/run_qwen.sh func`。默认两个 worker，可通过 `COSIL_THREADS=8 bash scripts/run_qwen.sh full` 调整；实际并发仍受模型服务限制。

文件级输出为 `results/full/file/loc_out_full.jsonl`；函数级输出为 `results/full/func/loc_func_full.jsonl`。进入函数级前，脚本检查文件级结果是否完整覆盖相同的 300 个唯一题目。输出和日志均保存在新版目录，支持跳过已完成记录。

2026-10-07 全量运行检查已完成：文件级成功 300 题，函数级成功 299 题、上下文超限失败 1 题。过程从单卡两 worker 切换四卡各两 worker，临时三张卡已释放。报告见 [全量总表](docs/qwen-300/实验报告_新版Qwen300_总表.md) 和 [逐题逐臂记录](docs/qwen-300/实验报告_新版Qwen300_逐题逐臂.md)。
