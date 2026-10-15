# 实验计划 v3c：文件定位后的函数节点功能说明对照（Qwen，300 题）

> 2026-10-06 修订。研究目标：文件定位 agent 确定候选文件后，给这些文件中的函数节点增加 `description` 功能说明，检验模型结合 issue、函数名和功能说明，是否更准确地选择需要查看的函数及最终故障位置。
> 注释生成、函数搜索、pruner 均使用本地 Qwen2.5-Coder-7B-Instruct；服务路由名为 `llama3`。
> 当前状态：2026-10-07 已完成。75,628 条节点功能说明生成完成，质量抽检 48/50，三次金丝雀及 27 次小规模重复验收通过；三臂各 300 题，共 900 条完整定位结果，双报告已生成并归档。一次正式请求超时按原冻结配置恢复，失败证据单列于《运行故障与恢复审计》。

## 一、论文依据与干预位置

论文原文：[Issue Localization via LLM-Driven Iterative Code Graph Searching, arXiv:2503.22424v3](https://arxiv.org/abs/2503.22424v3)，本地文件 `CoSIL_arXiv2025_2503.22424.pdf`，17 页。

论文 §III-A2 将函数级定位分为三步：

1. 用文件级候选构造类、成员函数、静态函数的结构目录，结合 issue 选择起始节点。
2. agent 选择节点并查询源码；pruner 判断相关性，控制源码是否加入搜索上下文及后续探索。
3. 综合已获取的上下文，输出并排序可疑位置。

本实验在**第一步产生的函数节点目录**增加功能说明，并在后续读取该目录时保持这一字段。该字段属于节点元数据，不改动项目源码或函数标识符。

```text
issue → 固定文件级 Top-5 候选 → 文件内函数节点目录
                                  ↓
                     name + 可选 description
                                  ↓
                       选择节点 → 查询源码
                                  ↓
                           pruner → 最终排序
```

例如同一节点在三臂中的表示为：

```json
{"name": "_cstack"}
{"name": "_cstack", "description": "将两个模型的输入输出关联矩阵按列组合。"}
{"name": "_cstack", "description": "同文件另一函数的功能说明。"}
```

示例说明仅用于展示格式，正式文本以 Qwen 依据源码生成并冻结的注释表为准。工具参数始终使用 `_cstack`，不包含说明文字。

此设计衡量函数级定位管线的整体增益。说明在初始选择、后续节点目录及最终目录中可见，因此“最终命中提高”不能单独证明搜索方向改善，必须结合查询轨迹判断。

## 二、三臂设计与共同基底

| 臂 | 节点字段 | 检验目的 |
|---|---|---|
| off | `name` | 名称目录基线 |
| on | `name`、正确对应的 `description` | 功能说明的整体作用 |
| shuffled | `name`、文件内错配的 `description` | 控制新增字段格式和说明文本总量，检验对应关系的作用 |

- SWE-bench Lite 全部 300 题；每题每臂一次，共 **900 次新运行**。
- 文件级输入固定为 `results/full/loc_out_full.jsonl` 的每题 Top-5，三臂完全共享。
- 三臂统一使用 `code_v3b/AFL_插桩版_分派修复.py`，实际类为 `code_v3b.fixed_search.AFL`；函数级入口是已修复的 `localize_with_p()`。
- 旧 `results/full/loc_func_full.jsonl` 保留为历史协议锚，不作为新 off 臂结果。
- 温度 0.0，搜索最多 10 轮，每次响应上限 2048 tokens，上下文上限统一为 65536。
- 模型请求固定 seed=0；vLLM 开启 `VLLM_BATCH_INVARIANT=1`，使用 `TRITON_ATTN`、eager 执行。设置用于三臂和注释生成，权重保持同一 Qwen 模型。详见 [vLLM 批次不变说明](https://docs.vllm.ai/en/latest/features/batch_invariance/) 与 `results/qwen_300/runtime_configuration.json`。
- 节点以文件、类名、函数名定位；同名类不会将其他文件的方法混入目录。
- shuffled 使用固定的文件内错位排列；文件内只有一条注释时保持该条不变，并单列数量。若不同函数说明本身相同，错配后文本也可能不变。
- shuffled 保持文件内说明文本集合，不保证每个节点长度或每次提示 token 数相同，也不作为严格的中性安慰剂。

## 三、共同实现修复及与原版的差异

以下改动在三臂中完全一致，必须在报告中单列，避免把共同基底变化误当作注释收益：

1. 分派修复作用于实际调用的 `localize_with_p()` 和 `localize()`：支持 markdown 前缀、代码围栏、尾随说明、字符串参数及关键词参数；每轮只执行第一个合法调用。使用 AST 解析字面参数，不执行模型输出的 Python 代码。
2. 兼容已观察到的 `get_code_of_static_function` 命名，映射为 `get_code_of_file_function`；其他不支持的调用反馈给模型重新选择。
3. `exit()`、分派错误、源码查询失败、API 故障、上下文预算停止分别记录；格式错误不会自动当作主动退出。
4. 判决仅接受可识别的 True/False；缺失或矛盾判决记为 unknown，并给予一次格式重试，不再对 None 调用 `.strip()`。
5. 按论文 §III-B 和附录 Fig.11 的正文约定，True 接收源码，False 排除源码。论文附录 Algorithm 2 的布尔分支与正文/提示词方向不一致，本实现采用正文和 Fig.11 的定义。
6. pruner 只接收 issue、原始源码和规范化工具调用，不接收节点功能说明或搜索 agent 的额外理由。目录查询属于元数据，不作为源码送入 pruner。
7. 采用本地 Qwen tokenizer 统计实际对话 token 数，包括 API 添加的系统消息，不再将历次完整 prompt 的 tokens 累加当作当前上下文长度。保留最终总结预算，记录预算导致的提前停止。
   初始函数目录只给出一次，后续轮次引用对话中的目录，避免相同功能说明每轮重复占用上下文。
8. 恢复查询、实际返回、判决、源码接收/排除及每次模型调用的日志。格式修复、查询量、上下文接收量及最终选择可分别审计。

该基底命名为 `function_description_fixed_v1`。它是在当前旧仓库上的共同修复版本；论文流程用于确定干预位置，历史协议结果与修复版本结果分别报告。

## 四、Qwen 功能说明生成

入口：`code_v3b/gen_annotations_300.py`。

- 从 `repo_structures_verified/<instance_id>.json` 提取每题候选文件的静态函数和类方法。
- 键为 `file.py::Class.method` 或 `file.py::function`，避免跨文件同名冲突。
- 输入包含节点身份与实际函数体；移除占据大量输入的文档字符串，较长函数保留实现头尾，正文上限 8000 字符。中间截断会明确标记，报告说明其局限。
- Qwen 用一句中文描述职责、输入输出或关键变换；不输入 issue、gold 或补丁，不要求诊断 bug、推荐修复或判断相关性。
- 注释最长 120 字符；失败空文本不会作为完成记录。相同节点身份与相同源码复用同一份已冻结的 Qwen 说明。
- 输出采用嵌套结构：`{instance_id: {file_qualified_function: description}}`。
- 完成要求为覆盖全部 300 个题目，且**每个应生成的函数节点均有非空说明**。无函数节点的候选文件、缺失文件及重复定义分别记录，不能仅看顶层字典有 300 个键。
- 全量表完成后抽查说明是否忠实于代码，记录截断和泛化问题；质量修改在正式结果揭晓前完成，再冻结输入 SHA-256。

输出：`annotations_300.json`；进度和来源：`results/qwen_300/annotation_status.json`、`annotation_provenance.json`、`annotation_manifest.json`。

## 五、金丝雀门槛与执行顺序

首先通过离线回归检查，再在固定环境下单并发运行 off 的 `astropy__astropy-12907` 三次。三个输出目录必须独立，分别保存于 `results/qwen_300/canary/repeat_{1,2,3}/`。

预先约定验收条件：

- 三次均完成，均有实际源码查询。
- 分派及 API 错误为零。
- 去除空条目并展开换行后的 Top-5 位置集合，两两 Jaccard ≥ 0.8；集合比较允许顺序变化。
- 任一条件失败即停止进入全量阶段，保留失败轨迹；不能不断重试直到恰好出现三次一致。

该门槛仅检查此题的运行链路，不证明全部 300 题稳定。正式研究需另设代表性小样本的重复三臂检查，估计温度 0 下的轨迹变化。

在正式结果产生前指定三题 `astropy__astropy-12907`、`astropy__astropy-6938`、`django__django-11848`，每臂独立重复三次，共 27 次，保存于 `results/qwen_300/pilot/{arm}/repeat_{1,2,3}/`。记录同题同臂 Top-5 集合两两 Jaccard、查询量和分派错误，不按 gold 命中或探索次数筛掉任何臂。空集合对空集合仅在稳定性比较中记 1，不能视为成功定位；验收、稳定性与正式 900 次定位分开计数。

以下是对应的执行入口；已启动的阶段由进度和锁文件管理，不应重复启动：

```bash
cd /home/wdt/cosil_repro/CoSIL

# 1. CPU 离线检查与 300 题候选准备
/home/wdt/miniconda3/envs/cosil/bin/python code_v3b/test_fixed_search.py -v
bash code_v3b/qwen300.sh prepare

# 2. 检查本机 Qwen 服务，然后跑三次独立金丝雀
curl -sS http://127.0.0.1:7333/v1/models --max-time 5
bash code_v3b/qwen300.sh canary

# 3. 金丝雀通过后，在 tmux 中生成并检查全部 Qwen 注释
tmux new-session -d -s qwen300-annot -c /home/wdt/cosil_repro/CoSIL \
  'bash code_v3b/qwen300.sh annotations --workers 4 > results/qwen_300/annotation_runner.log 2>&1'

# 4. 完成注释质量检查、300 题真值审核及小规模三臂验收后，冻结输入并运行
tmux new-session -d -s qwen300-fixed -c /home/wdt/cosil_repro/CoSIL \
  'bash code_v3b/qwen300.sh run --workers 2 > results/qwen_300/fixed_runner.log 2>&1'
```

定位结果：`results/qwen_300/fixed/{off,on,shuffled}/loc_{arm}.jsonl`；逐题结果和事件分别在相应臂的 `cases/`、`events/`、`logs/` 子目录中。失败样本保留在 `failures/`，不会伪造为空成功结果。旧十题数据不混入这些目录。

## 六、真值与评测口径——全量正式起跑前须完善

`ground_truth_v2.json` 只覆盖十题，不能直接评估另外 290 题。`evaluation/gt.json` 覆盖 300 题，但混合了函数、类和文件标签，需对照官方 patch 审核并统一口径。

应建立冻结的 `ground_truth_300.json`，每题记录：gold 文件集合、按文件组织的 gold 函数/类、目标类别、修复前是否存在及证据来源。原十题真值用于交叉核验；配置变量、新增函数、类属性、非 Python 文件和多文件修改须单列。

运行器要求顶层键与 300 个 instance_id 完全一致，每条至少包括 `gold_files`、`gold_functions_by_file`、`target_kind`、`evidence`、`base_commit`；缺失或基准提交不一致时拒绝正式起跑。真值只用于评测和验收，不传给模型。

不能仅从增删的 def 行确定真值，会漏掉函数体修改；也不能仅把 hunk 头中的 def 当作 gold：配置改动可能对应前面的邻近函数，新增方法可能对应前一个方法。应结合实际改动区间与修复前后函数边界审核。

评测分开给出：

1. 300 题总体的 Top-1/3/5、MAP、MRR、空结果率，明确使用的目标标签和分母，以便与历史协议锚比较。
2. 有函数级 gold 的题目子集，单独报告严格的文件+函数命中。
3. gold 函数在初始菜单内且修复前存在的子集，观察功能说明对节点选择的直接效果。

300 题历史协议表原样使用 `evaluation/FLEvalNew.py` 与 `evaluation/gt.json`，并列既有 `loc_func_full.jsonl` 和三臂新结果；该表混合类/函数标签，按名称匹配而不保留文件约束，只有文件标签的题目在节点指标中记未命中。严格函数表及经 AST 校验的函数/类联合表保留文件身份，并使用展开后前五个位置计算 MAP@5/MRR@5。这些评测输入哈希与口径已在正式结果产生前冻结于 `results/qwen_300/evaluation_manifest.json`。

文件级输入不重新改变。按现有 `evaluation/gt.json`，缓存 Top-1 为 141/300=47.0%，Top-5 为 191/300=63.7%；本地论文 v3 Table II 的 Qwen-7B 数值为 41.0%/63.7%。历史版本或标注口径需进一步核对，当前不能称其完全复现了这版论文。

## 七、主要指标、分层与结论边界

| 指标 | 定义与解释 |
|---|---|
| gold 查询率 | 实际成功返回 gold 源码；工具请求、目录查询和不存在的符号不计作成功读取 |
| gold 接收率 | gold 源码经过 pruner 并实际进入主搜索上下文；与查询率分开 |
| 最终命中 | 输出位置与已冻结真值匹配；明确全部输出与 Top-5 的区别 |
| 起步失败率 | 无实际源码查询的样本，进一步分显式 exit、格式错误、工具错误、API/预算停止 |
| 剪枝分布 | True/False/unknown；成功读取 gold 后的判决另列 |
| 探索量与成本 | 有效源码查询、重复查询、API 次数、输入/输出 tokens、预算停止和耗时 |

分层规则在正式结果揭晓前固定：

- 至少一个/全部 gold 文件进入 Top-5 分开统计。Top-5 外不等于绝对无法定位；若查询了跨文件邻居，记录该路径。
- issue 明确提到 gold 函数、明确提到其他函数但未提到 gold、未明确提到函数名三组。以程序标识符/调用形式作为明确提及的操作定义，并抽查歧义。
- “未点名 gold”不能叫“没有症状锚”：12907 提到 `separability_matrix`，但 gold 是 `_cstack`，属于点名其他函数的情形。
- 注释覆盖、源代码截断、单条说明无法错配、变量/新增函数等目标类别分别统计。

主比较为同题 on−off，其次为 on−shuffled；报告配对差值、置信区间及预先指定的配对检验。单次运行的差异不直接证明判决随机性；无显著提升不等于普遍无效；on≈shuffled 也不能直接证明只有长度在起作用。

## 八、报告产出与待完成事项

最终报告写入本目录：

- `docs/qwen-300/实验报告_v3c_Qwen三臂总表.md`：300×3 对照表、总体及子组指标、主要发现、机制复核、局限。
- `docs/qwen-300/实验报告_v3c_逐题逐臂.md`：每题 issue 前 1500 字符、真值证据、三臂轨迹、gold 查询/接收时刻、原始最终输出、诊断及判分附录。

原始结果与注释保持在项目根目录和 `results/qwen_300/` 中；报告数字必须能追溯到这些文件及输入哈希。

当前已完成：节点独立字段、实际入口分派修复、判决保护、False 源码排除、统一预算和完整日志，以及相应离线测试。

执行审计：两组此前失败的金丝雀已完整归档；第二组分派错误为零但同一输入输出不一致。启用批次不变推理后，三次输出集合 Jaccard 均为 1.0，分派/API 错误均为零。300 题真值来自对应 base_commit 的 git blob 和官方 patch，存在行号偏移时要求完整 hunk 上下文唯一匹配，再按实际改动行和前后 AST 归属定位；十题参考全部一致。

注释目录实际需覆盖 75,628 个节点；相同节点身份与注释输入复用 Qwen 说明，以减少重复请求。质量检查预先选定随机 50 条、源码忠实性达到 90% 的门槛，使用同一 Qwen 作代码独立审阅，其同模型偏好须在报告中注明。小规模三臂只要求完整运行，不将探索量、提前退出或命中率作为放行条件，以免筛除干预效果。

`code_v3b/pipeline_300.py` 将监督后续生成、验收、三臂和最终报告；任一阶段失败即保留证据并停止，进度写入本目录 `执行进度.md`。最终报告只在所有 900 次完成后生成。
