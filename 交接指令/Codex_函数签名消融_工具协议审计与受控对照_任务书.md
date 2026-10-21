# Codex 执行任务：函数签名消融 + CoSIL 工具协议审计与受控对照

你是本项目的科研工程实现者。**先审代码/数据再执行**，不要停留在建议或伪代码；在满足安全前置条件后实现、测试、运行获批的开发对照并交付中文报告。任务重点是**因果可解释的受控实验**，不是追求看起来更高的分数。

## 0. 入口、现状与不可破坏的约束

- 工程入口（如该路径在你的机器上不存在，查找真实工程路径，不凭空重建）：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1`。
- 冻结的历史 run：`runs/20261021_nonthinking_v3/lite_pilot`。50 道 Lite 开发题（41 道严格函数可映射、7 道部分可映射、2 道不可映射）。原报告：`final_report.md`、`lite_pilot_单题时长_token与工具使用审计.md`、`lite_pilot_逐题分析.md`，以及 run 目录下 CSV/JSONL、原始请求与源码访问日志；以**实际文件、配置和代码**为准。
- 历史参照：D-SIMPLE 严格函数 Hit@5=38/41，D-COSIL=34/41；Q-COSIL=11/41，Q-PRUNER=11/41。D-SIMPLE 是 CQ2-inspired baseline，不是论文的官方函数定位方法，也未验证修复率。
- 历史工具审计：D-COSIL 411 次动作响应、81 次解析失败、301 次真实执行/298 次成功；Q-COSIL 367 次执行/233 次成功、134 次工具错误；Q-PRUNER 358 次执行/201 次成功、157 次工具错误。D-COSIL 有 68 段 DSML 候选输出，其中离线审计识别 43 段结构完整（**不得追认成历史执行**）。
- **禁止**改写旧 run、旧 predictions、既有 gold 映射表或历史指标；新的实验独立目录 `runs/YYYYMMDD_context_tool_diagnostic/`，必要时创建新分支。先保存 git HEAD、变更文件清单、依赖锁、配置快照及哈希。**不要碰既有封存的 30 道 holdout issue**，不要打开、读取、哈希或以任何方式利用先前约定封存的裁判测试对。
- 原 SWE-bench Lite 公开题与历史训练可能有重合：这次定位为**开发诊断**，不能宣称外部泛化。禁止向模型传入 gold patch、目标函数标签、隐藏测试、instance_id、评测代码、旧预测或修复提交；所有 gold 只允许在独立离线评分进程/namespace 使用。只读取每题 `base_commit` 的仓库源文件。
- DeepSeek 全程 `thinking=disabled`（每个请求显式带 `extra_body={"thinking":{"type":"disabled"}}`），不自动开 High，不改模型版本。保留原推理温度/采样与最大输出 token 配置；若原服务不能固定随机种子，记录局限，不冒称完全确定性。Qwen 用原冻结检查点/服务，勿自行切换到新模型。
- 不跑 SWE-rebench、修复测试、训练与调参。不清理或杀死他人 GPU 进程。任何无预算上限或会改动封存数据的任务立即停下报告。

## 1. 任务 A：真正可解释的“函数签名 vs 完整源码”配对消融

### A1. 冻结上游，只重跑一次最终函数排序

对同一个 `lite_pilot` 50 题的 D-SIMPLE，**复用已有的五次文件选择、交集/回退结果和实际 `loaded_whole_files` 清单**。这些文件必须来自原 run 的 manifest 和各题的 `base_commit`，不能根据 gold、原模型最终预测或 grep 命中情况改选文件。不要重跑文件选择与 query planning，也不要发生额外的文件检索。先输出 `frozen_context_manifest.jsonl`：instance_id（仅内部关联）、base SHA、固定文件列表及排序、原始内容 SHA256、原来上下文中哪些源文件被整文件加载、哪些只是 grep 证据、是否存在原始溢出/跳过。

注意：本次 **A1/A2 两臂都不提供原来的 grep 证据片段**，目的是只操纵“有无完整源码”。历史 D-SIMPLE 原始结果仍作为**观察性参考**，不是与本次 A2 严格同设置的受控对照。

### A2. 为两臂生成完全一致的候选函数清单

从上述固定的整文件集合，使用**不读取任何 gold 的 AST 程序**抽取所有可识别的 `FunctionDef`、`AsyncFunctionDef`、类方法和嵌套函数，稳定生成精确 `repository/relative/path.py::fully.qualified.name`；包括 `_TR56._f` 等嵌套定义。列表按固定文件顺序、源码位置、限定名称排序，不能按标签、Issue 关键词或历史预测调整。

每条仅展示 `path::qualified_name`、`def/async def` 签名（参数/返回标注；必要时对极长默认值做统一、无语义判断的长度限制），不展示函数体、注释、docstring、邻居代码、grep 片段。处理 property getter/setter 的身份语义应与既有**严格评价器**一致；同一限定名称多个定义不能因源码 span 不唯一而丢掉。保存抽取日志、候选数、候选 tokens、抽取失败和源码哈希。单独离线报告：**gold 是否存在于冻结的整文件集合/候选列表**，但评分前绝不能用该信息修补候选列表。

### A3. 两个实验臂（仅改变是否提供完整源文件）

- `A-SIGNATURE`：共同系统指令 + Issue + 固定文件路径顺序 + 完整候选函数签名列表；**无源码正文、无 docstring、无 grep**。
- `A-FULL`：与 `A-SIGNATURE` **相同的**系统指令、Issue、路径、完整候选签名列表，再追加对应**相同文件的完整、未截断源码**；**无 grep**。

两组相同的函数排序指令：`Given the issue and the candidate symbols, rank up to 10 functions most likely to require modification. A symptom function need not be the root-cause function. Choose only identities exactly present in the candidate list. Return JSON only: {"ranked_functions":[{"path":"...","qualified_name":"..."}]}.` 可附中文说明，但**两组逐字相同**；只允许源码区块不同。模型、版本、thinking、请求输出上限、温度、解析器、失败处理、排序规则均相同。每题每臂仅一次**成功送达的语义请求**（网络传输错误遵循原有重试和去重规则），不能失败后改提示词重抽答案。

上下文不得在一臂悄悄截断。先估计 token 预算；若 A-FULL 在原预设上下文上限下放不下固定文件 + 候选列表，记录 `context_overflow`，主表仍保留此题为失败/未成功，不按 gold 择优删除；另在条件成功子表报告。不得增加 token 上限来单方面照顾一臂。保存两臂实际 prompt 全文的脱敏哈希、候选列表哈希、源码块哈希、输入/输出token、费用与墙钟。

### A4. 评分和解释

严格复用本轮原评价器及 `path::qualified_name` 匹配口径；报告原定 50 题集合、41 题严格可映射主分母、7题部分可映射辅助结果、2题不可映射。主指标：函数 Hit@1/3/5、Macro-Recall@5、AllCoverage@5、MRR@10；主要比较 **A-FULL − A-SIGNATURE 的同题配对差异**。输出 A赢/B赢/双方对/双方错、精确 McNemar（适用 Hit@5）、按 issue bootstrap 95%CI 和按仓 cluster bootstrap CI；多指标探索性检验注明，不从小样本无显著差异推出“等效”。

另外必须报告：候选清单 gold 覆盖率、完整源码真实覆盖率、是否有某个 gold 只出现在被排除的 grep 证据里、最终请求 token 和成本差异、按仓库/单多函数 gold 分组结果。由于 A-FULL 天生有更多 token，结论只能是“**增加完整源码信息的增量效果及其代价**”，不能直接归因于深层语义理解或声称 token 预算相等。

## 2. 任务 B：CoSIL 工具约束问题，分离“格式不兼容”和“错误目标”

### B0. 先用历史日志做零 API 成本审计

读取三个历史 CoSIL 方法的逐次动作日志与 `lite_pilot_tool_io_per_call.csv`，**不要重新执行历史输出**。逐项分类并留典型原文证据：

1. 响应解析失败：不合约定的自由文本、合法 Python DSL、完整标准 DSML、畸形 DSML（含重复分隔符）、多动作/不允许的表达式、意外退出等。
2. schema 失败：工具名、参数个数、参数字段/类型错误；特别核查 `get_code_of_file_function` 与 `get_code_of_class_function` 的混用。
3. 目标失败：路径在 base 不存在、文件/类/方法不匹配、把成员当顶层函数、幻觉符号、路径别名问题；与单纯语法错误分开。
4. 多轮低效：同一错误参数重复、同一源码重复请求、10轮限制和超时；按真实工具执行记录。
5. 返回和传递：执行成功、源码真的返回、主裁判见到源码、小裁判见到源码、搜索 Agent 后续**有效请求**确实收到完整源码，分别统计；记录代码已经返回但未进入 Agent 的原因。
6. 结束和评价：早退、最终无效 `None`、最终排名失败。**gold 在搜索前根本未暴露**不得计为“裁判误剪”；只有真实 reject 且对应具体 gold 源码时才算 gold_direct_prune。

产出 `tool_failure_taxonomy.csv`（每条action有类别、原因、证据文件、实际结果）及汇总矩阵。必须能复现历史审计计数，任何口径差异写出原因，不要覆盖原报告。

### B1. 格式兼容适配器（最小变更，首先针对 D-COSIL）

新增一个**独立、可配置开关**的工具解析器（默认不影响历史行为）。严格解析原先允许的单次 Python DSL；再允许**结构完整、符合已核实官方约定**的单次 DSML 工具调用，转换成同一白名单工具、同一参数值、同一原工具返回。不得 `eval`、执行任意模型代码、猜测缺失字段、自动修正畸形 DSML、将错误参数映射到“最近存在的函数”。含有额外指令/多调用/未知工具/越界路径一律按预先规则拒绝并审计。所有源代码必须来自 base 快照。

先对原 68 段 DSML 原文**仅离线 parser 单元测试**，报告有多少格式可解析、其中目标存在多少；这些潜在可解析结果**不能直接增加历史 Hit@5**，也不能假装 agent 收到了代码。然后运行**全新在线 D-COSIL-ADAPTER**：冻结与历史 D-COSIL 每题一致的前期文件选择/初始搜索上下文、搜索步数、主模型、判别逻辑和最终排序，只开 `accept_strict_dsml=true`。没有可复用完整初始状态时记录原因，不能偷换成重新选文件。

这只检验“**兼容已有模型实际输出格式**”的帮助，不是增加新搜索算法；保存所有后续模型响应和真正执行的调用，不能用历史中原本失败的一条 DSML 来代替全新在线轨迹。

### B2. 统一结构化工具协议（和 B1 分开，不能混作同一消融）

检查 DeepSeek API、现有 Qwen 服务端以及 CoSIL 工具框架**实际**是否都可靠支持原生 `tool_calls`。若支持，在 D-COSIL 和 Q-COSIL 以及可行时 Q-PRUNER 用一致的声明和验证规则；若其中不支持，三者统一退回严格 JSON 动作 `{"tool":"get_code_of_class_function","arguments":{"file_path":"...","class_name":"...","method_name":"..."}}`（具体字段必须依据已有函数签名实际映射，不得凭示例猜测）。记录最终采用的协议和服务器配置，**绝不能把文本 JSON 伪报为原生工具调用**。

仅改变工具调用的**表示/约束层**：工具白名单、实参 schema、一次一动作、退出操作、解析错误分类；沿用现有工具执行语义、源码返回、候选仓库、搜索图、至多10轮导航、裁判及阈值、上下文保留规则、最终排序、上下文/输出上限、模型和非思考设置。语法无效明确拒绝；模型指向不存在的真实目标，仍按原错误语义计为“目标错误”，不自动纠错、不补全，不额外开放 AST 全仓候选目录。**如果加入“只让模型在真实可选符号菜单里选”之类语义约束，必须命名为独立增强实验，不得计入 B2 主对照。** 原来的 `semantic_retry_limit=0` 保持不变。

采用各方法自身对应的历史冻结前置状态（若原方法在搜索前就失败，必须保留该失败并单列），杜绝不同模型使用不同文件起点而宣称只比较工具协议。保存包括 `raw_model_tool_output`、`parsed_tool_call`、`target_resolution`、`source_returned`、`judge_seen`、`agent_seen`、最终排名的逐步事件链。不得把已取回源码等同于agent实际收到源码。

### B3. 执行顺序、比较和结论

- 先 B0 静态审计＋ B1/B2 parser/schema 单元测试：涵盖正确调用、错误数量参数、错类/错函数、重复工具、畸形 DSML、文本注入、非法路径和退出，不用 API。
- 用 `lite_pilot` 中按稳定 SHA256(`instance_id`) 排序的前5题做 A、B1、B2 冒烟；预先登记全部50题和不改变的采样规则。B2 同时测试 DeepSeek 与 Qwen 的协议能力；不要选择“模型最容易答对的5题”作冒烟。
- A 两组优先完成50题。B1 若通过冒烟并在预算内，完成 D-COSIL-ADAPTER 的50题；B2 对 D-COSIL 与 Q-COSIL（以及 Q-PRUNER 若接口可用）先完成**同一固定的20题机制诊断子集**，覆盖不同仓库且抽样规则预先冻结。除非用户明确同意扩展，否则不自动跑 B2 全50题；若B2无法可靠统一，交付完整 B0/B1和失败说明，不能用不同协议混算。
- B1 和 B2 与对应原始方法配对比较：函数 Hit@5/Recall@5、文件起点一致率、有效工具提议率、语法合约率、目标存在率、真实执行成功率、首次返回源码轮次、Agent真实收到源码题数、重复错误数、最终无效输出率、累计 token、墙钟和实际成本。区分 all_allocated 与 completed/entered_search 子表。
- 对 B1/B2 的影响作**上游条件分层**：没进入搜索、进入搜索但调用失败、取回源码但Agent未见、见了源码仍选错。说明格式修正是否只提升“工具可执行”，还是实际带来了定位收益；不因调用成功率提升就宣称定位提升。
- 由于更改调用协议本身会影响模型下一步行为，B2 应标为“接口方案对照”，不是把整条轨迹的变化全部归因到 parser。B1 单独报告离线格式兼容可解析上界和在线真实收益。

## 3. 成本、运行与验收条件

1. **先 preflight**：确认路径、50题 manifest、base commit、GPU/服务权限、模型名和版本、缓存日志、原有 evaluator、保存与安全边界、价格/usage记账可用；打印并落盘 `resolved_config.yaml`。若核心文件缺失，暂停并汇报缺口，不凭空生成 gold、上下文或历史预测。
2. 只运行新追加的定位请求；不重复付费做文件选择和 grep。DeepSeek **本次新增 API 费用总硬上限 USD $3.00**，不足以执行下一请求就停止并落盘可恢复检查点；任何未知计费必须按旧规则保守预留。`B2` 只执行20题，扩到50题需用户另行批准；若3美元上限不足，按顺序保留 A→B1→B2 的优先级。不自动动用旧 $10/$30 预算。记录本次成本与旧run成本分开。
3. 在使用本地 Qwen GPU 前核实当前 GPU 使用者和服务：优先复用原服务，不能杀其他任务或占满被人使用的卡；本地GPU时间和API USD分别统计，**没有USD账单 ≠ 零成本**。主Qwen服务无法稳定运行时可先完成DeepSeek和离线工作，但不能冒称 Qwen 验证完成。
4. 新代码应有命令行参数，如 `--cohort lite_pilot --phase ablation|audit|adapter|structured --smoke|--full --dry-run`，实际名称遵循现有 CLI 风格。幂等、可断点续跑、唯一 request_id 去重、原始输出只写一次；必要网络重试和模型语义重试要分清。默认 `--dry-run` 不花钱；真正执行须显式开关并出具逐题预算预估。
5. 新增单元测试至少覆盖：候选名单与源码的**双臂完全同ID同顺序**、nested method/properties、无gold读取、上下文不截断、strict JSON评分、多输出/重复输出、严格 DSML 白名单、工具真实存在校验、源码 SHA、source/judge/agent 已送达三种事件判别和新旧run文件隔离。先跑 CPU 测试，再冒烟，再正式开发题；任何失败保留分母和错误原因。
6. 输出目录下交付 `README_如何复现.md`、`ablation_pairwise.csv`、`tool_failure_taxonomy.csv`、`tool_protocol_per_call.csv`、`per_issue.csv`、`method_summary.csv`、`paired_comparisons.csv`、`run_manifest.json`、`cost_ledger.csv`、`final_diagnostic_report.md`。报告用中文，含对照协议、完整分母、费用/请求数、真实调用举例、四类失败机制、限制与下一步建议；附对照表或图（不因作图省略原始数据）。
7. 最终报告必须回答：**（甲）在相同候选函数和文件选择下，完整源码相对于签名列表到底带来多少增益与token代价？（乙）历史 CoSIL 的劣势中有哪些属于工具协议/工具参数失败，有多少在兼容或结构化约束后实际改善？（丙）剩余失败是在文件选择、信息传递、模型推断还是搜索策略？** 如果证据不足，就明确写“目前不能区分”。

开始执行前，先用简短文字向用户汇报：实际定位到的脚本和输入文件、两组消融冻结哪些内容、工具协议选择、预计会产生哪些模型调用和成本上限。随后按上述顺序执行，不要只给计划，也不要修改原结果来制造改善。
