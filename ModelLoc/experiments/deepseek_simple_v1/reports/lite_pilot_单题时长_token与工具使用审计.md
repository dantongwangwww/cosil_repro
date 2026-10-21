# 单题时长、token与真实工具使用审计

集合：lite_pilot；run：20261021_nonthinking_v3。按instance_id关联，每题每臂仅一份结果。

“通常一题多久”以**中位数与P25–P75区间**为主，均值、P95揭示长尾。处理墙钟从worker开始处理到落盘，包含本题CPU/模型/网络；worker排队另列。客户端无法再把一次请求分成网络、服务端排队和纯模型计算，不伪造这三项。

token为实际usage累计，重复发送上下文会重复计入。Q-PRUNER另加专职裁判实际前向输入token，裁判只评分、不生成文本，因此其生成token为0。接口缺失的reasoning/cache字段不补0。

## 1. 单题典型耗时与token

| 方法 | 群体 | N | 均值秒 | 中位秒 | 通常P25–P75秒 | P95秒 | 平均累计输入 | 中位累计输入 | 平均输出 | 中位输出 | 平均总token | 中位总token | 总token P25–P75 |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| D-SIMPLE | all_executed | 50 | 11.39 | 8.36 | 7.58–9.47 | 12.13 | 90357 | 92050 | 432 | 380 | 90789 | 92380 | 70432–111282 |
| D-SIMPLE | completed | 50 | 11.39 | 8.36 | 7.58–9.47 | 12.13 | 90357 | 92050 | 432 | 380 | 90789 | 92380 | 70432–111282 |
| D-COSIL | all_executed | 50 | 83.76 | 40.32 | 24.14–172.27 | 192.34 | 91338 | 87810 | 1487 | 1484 | 92825 | 89224 | 63276–120121 |
| D-COSIL | completed | 48 | 86.61 | 41.40 | 26.17–172.60 | 192.54 | 94384 | 88390 | 1488 | 1484 | 95873 | 89996 | 66018–121578 |
| Q-COSIL | all_executed | 50 | 100.92 | 102.09 | 73.00–132.12 | 155.19 | 79199 | 79072 | 1077 | 1078 | 80276 | 80210 | 52920–109198 |
| Q-COSIL | completed | 40 | 110.18 | 111.97 | 87.31–133.00 | 146.82 | 97297 | 86658 | 1144 | 1122 | 98441 | 87640 | 70857–121256 |
| Q-PRUNER | all_executed | 50 | 127.06 | 122.22 | 77.13–162.47 | 220.50 | 80127 | 79226 | 1044 | 1018 | 81171 | 80540 | 50302–111831 |
| Q-PRUNER | completed | 39 | 138.18 | 139.03 | 100.55–165.42 | 212.19 | 100379 | 88349 | 1101 | 1078 | 101480 | 89688 | 72653–124223 |

all_executed包含真实失败和预算停止；completed为成功完成子组。两者并报以防删除慢题/失败题造成偏差。P0存在前序请求重放与结果复用，不用其续跑墙钟估计稳定单题耗时；正式典型时长以未重放的P1为准。

## 2. 分阶段请求账

| 方法 | 阶段 | 到达题数 | 平均请求数/到达题 | 请求累计均值秒 | 请求累计中位秒 | 平均输入token | 平均输出token |
|---|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | file_selection_and_import_reflection | 50 | 1.98 | 51.84 | 3.72 | 9895 | 442 |
| D-COSIL | final_function_ranking | 48 | 1.00 | 1.14 | 1.11 | 9530 | 99 |
| D-COSIL | relevance_judge_main_model | 49 | 6.08 | 4.86 | 5.10 | 7065 | 49 |
| D-COSIL | search_navigation | 49 | 9.39 | 11.36 | 11.43 | 66705 | 920 |
| D-SIMPLE | file_selection_5_draws | 50 | 5.00 | 7.62 | 4.91 | 58840 | 237 |
| D-SIMPLE | final_function_ranking | 50 | 1.00 | 1.59 | 1.48 | 30797 | 141 |
| D-SIMPLE | query_planning | 50 | 1.00 | 0.93 | 0.90 | 720 | 54 |
| Q-COSIL | file_selection_and_import_reflection | 50 | 1.84 | 26.84 | 26.89 | 8679 | 342 |
| Q-COSIL | final_function_ranking | 40 | 1.00 | 6.59 | 6.75 | 9099 | 80 |
| Q-COSIL | relevance_judge_main_model | 36 | 6.47 | 3.04 | 3.07 | 6584 | 30 |
| Q-COSIL | search_navigation | 42 | 10.52 | 59.60 | 51.74 | 69643 | 774 |
| Q-PRUNER | file_selection_and_import_reflection | 50 | 1.84 | 26.59 | 27.56 | 8679 | 342 |
| Q-PRUNER | final_function_ranking | 39 | 1.00 | 6.45 | 6.20 | 9547 | 80 |
| Q-PRUNER | relevance_judge_main_model | 15 | 1.87 | 0.99 | 0.66 | 2381 | 9 |
| Q-PRUNER | search_navigation | 42 | 10.33 | 58.76 | 52.29 | 70377 | 759 |

分阶段均值按实际到达该阶段的题计算；未到达不伪填为成功的0秒。D-SIMPLE的五次文件选择合为一阶段，CoSIL文件选择与导入关系反思合并。裁判前向、CPU图构建和工具执行详见逐题CSV，非同一计时口径不能直接相减称纯GPU秒。

## 3. 模型到底有没有使用工具

**这里的CoSIL采用文本DSL调用，经白名单AST解析后由框架执行；不是API原生tool_calls。** 下面只把有真实执行事件的调用计为执行，exit单列。模型说“我读了”而无事件不算。D-SIMPLE是固定文件装载/一次grep流程，不能将它的文件数当成自由工具调用数。

| 方法 | 动作响应 | 解析通过(含exit) | 严格单调用文本 | 实际执行 | 执行成功 | 真正返回源码 | 裁判收到源码 | 搜索agent收到源码 | 工具错误 | 重复输入 | exit/读源码前exit | 无agent源码仍定位题 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D-COSIL | 411 | 330 | 326 | 301 | 298 | 298 | 296 | 185 | 3 | 2 | 29/0 | 0 |
| Q-COSIL | 400 | 367 | 367 | 367 | 233 | 233 | 231 | 105 | 134 | 117 | 0/0 | 15 |
| Q-PRUNER | 392 | 358 | 358 | 358 | 201 | 201 | 200 | 119 | 157 | 124 | 0/0 | 14 |

“解析通过”仅证明调用语法可绑定；参数还必须对应真实文件/类/函数。执行成功也可能只是节点目录，只有source才算源码。pruner拒绝会导致“已取回、裁判已看见、搜索agent没看见”，三者分别统计。文件阶段由框架隐式读import行，不冒充模型主动函数源码调用。

## 4. 输入/输出是否符合工具约定

| 方法 | 非exit提议(含解析失败) | base目标与工具作用域有效 | 提议→真实成功 | 已执行→成功 | 源码返回与base逐行一致 | 源码返回不一致 |
|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | 382 | 298 | 78.01% | 99.00% | 296 | 0 |
| Q-COSIL | 400 | 233 | 58.25% | 63.49% | 231 | 0 |
| Q-PRUNER | 392 | 201 | 51.28% | 56.15% | 200 | 0 |

| 方法 | 已有结果题数 | 至少一次源码工具成功题 | 搜索agent真实收到源码题 | 工具无源码仍定位题 | agent无源码仍定位题 | DSML动作/结构完整/目标有效 |
|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | 50 | 49 | 49 | 0 | 0 | 68/43/43 |
| Q-COSIL | 50 | 36 | 25 | 4 | 15 | 0/0/0 |
| Q-PRUNER | 50 | 36 | 26 | 4 | 14 | 0/0/0 |

搜索agent收到源码需同时有context_accept事件，并在之后有成功API回执的搜索/总结请求中找到完整原文。context插入、实际送达分别落盘。小裁判需有真实评分事件及已保存的v6输入哈希核验；不把框架取到源码直接等同于agent读到。

DSML仅做离线语法/参数诊断，绝不执行、纠正或重跑。官方V4.1使用`<｜DSML｜ calls>`；重复竖线等偏离单列，结构缺失直接记失败。输出DSML不符合本实验请求的Python式调用；能辨识调用意图也不等于原框架执行成功。依据：[DeepSeek官方编码说明](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/encoding/README.md)。

get_code_of_file_function要求文件内独立函数，get_code_of_class_function要求文件/类/方法分开传参，get_code_of_class返回类源码；get_functions_of_class返回节点元数据，不应当作源码。裸类名可由框架在候选文件中唯一推断时，另标file_argument_inferred_by_framework；别名归一和多调用文本也单列。

## 5. 代表调用（原始完整记录见tool_io_per_call.csv及calls）

| 方法/issue | 原始动作 | 真实执行/返回 | 参数/返回核验 | 证据 |
|---|---|---|---|---|
| D-COSIL/sympy__sympy-17630 | `get_code_of_class_function('sympy/matrices/expressions/blockmatrix.py', 'BlockMatrix', '_blockmul')` |     def _blockmul(self, other): ↵         if (isinstance(other, BlockMatrix) and ↵                 self.colblocksizes == other.rowblocksizes): ↵             ret | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-17630/calls/0005_node_selection` |
| D-COSIL/mwaskom__seaborn-2848 | `get_code_of_class_function('seaborn/axisgrid.py', 'PairGrid', '_map_bivariate_iter_hue')` | You provide a wrong file name or class name or function name. Please try another file name again. It may be a file function. | definition_not_in_supplied_file_or_class; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/mwaskom__seaborn-2848/calls/0016_node_selection` |
| D-COSIL/sympy__sympy-17630 | `<｜｜DSML｜｜ calls> ↵ <｜｜DSML｜｜ invoke name="get_code_of_class_function"> ↵ <｜｜DSML｜｜ parameter name="file_name" string="true">sympy/matrices/e` | No supported tool call found in the model output | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-17630/calls/0004_node_selection` |
| D-COSIL/scikit-learn__scikit-learn-15512 | `I have enough information to summarize. Let me analyze the findings. ↵  ↵ Based on my inspection: ↵  ↵ 1. **｀affinity_propagation｀** (core f` | exit; prior source=7 | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/scikit-learn__scikit-learn-15512/calls/0018_node_selection` |
| Q-COSIL/sympy__sympy-17630 | `get_code_of_class_function('sympy/matrices/expressions/blockmatrix.py', 'BlockMatrix', 'colblocksizes')` |     @property ↵     def colblocksizes(self): ↵         return [self.blocks[0, i].cols for i in range(self.blockshape[1])] ↵  | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-17630/calls/0004_node_selection` |
| Q-COSIL/scikit-learn__scikit-learn-15512 | `Let's inspect the ｀pairwise_distances_argmin｀ function from the ｀sklearn/utils/extmath.py｀ file. ↵  ↵ ｀｀｀python ↵ get_code_of_file_function(` | You provide a wrong file name or function name. Please try another file name again. It may be a class function. | definition_not_in_supplied_file_or_class; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/scikit-learn__scikit-learn-15512/calls/0020_node_selection` |
| Q-COSIL/sympy__sympy-17630 | `get_code_of_file_function('sympy/matrices/expressions/blockmatrix.py', 'BlockMatrix', '_blockmul')` | Too many tool arguments | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-17630/calls/0008_node_selection` |
| Q-PRUNER/sympy__sympy-17630 | `get_code_of_class_function('sympy/matrices/expressions/blockmatrix.py', 'BlockMatrix', 'colblocksizes')` |     @property ↵     def colblocksizes(self): ↵         return [self.blocks[0, i].cols for i in range(self.blockshape[1])] ↵  | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-17630/calls/0004_node_selection` |
| Q-PRUNER/django__django-12284 | `｀｀｀python ↵ get_code_of_class_function('django/db/models/fields.py', 'Field', 'get_internal_type') ↵ ｀｀｀` | You provide a wrong file name or class name or function name. Please try another file name again. It may be a file function. | path_not_literal_base_python_path; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-12284/calls/0005_node_selection` |
| Q-PRUNER/sympy__sympy-17630 | `get_code_of_file_function('sympy/matrices/expressions/blockmatrix.py', 'BlockMatrix', '_blockmul')` | Too many tool arguments | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-17630/calls/0007_node_selection` |

这些是描述性机制证据；使用工具不等于定位正确，参数错误也不能只凭一次失败归咎框架。需要结合base定义是否存在、工具支持的作用域和实际错误响应。完整逐题/逐调用CSV保留原文、规范调用、参数、输出SHA、耗时及进入哪个上下文的证据。

## 6. 加载、队列、恢复和不可测量项

| 方法 | worker排队中位/P95秒 | 裁判加载总秒 | 每题构图均值/中位秒 | 传输失败次数 | 重放/复用题 |
|---|---:|---:|---:|---:|---:|
| D-SIMPLE | 177.19/314.08 | NA | NA/NA | 0 | 0 |
| D-COSIL | 1096.04/2155.85 | NA | NA/NA | 0 | 0 |
| Q-COSIL | 2568.43/4870.19 | NA | NA/NA | 0 | 0 |
| Q-PRUNER | 3262.48/6165.42 | 52.96 | 27.94/19.64 | 0 | 0 |

自建主Qwen服务启动至就绪：{'ready_at': '2026-10-21T08:51:23.289281+00:00', 'startup_seconds': 60.737413237802684, 'included_in_per_issue_processing_time': False, 'definition': 'Owned Qwen service process start through successful /models health check'}。该一次性过程不混入每题处理时长。HTTP冷连接调用、重试和worker队列已记账；服务端TTFT/内部排队和纯GPU核时间没有直接观测，不以客户端耗时猜测。

## 7. 复现与边界

分析命令：`python analysis/performance_and_tools.py --cohort lite_pilot`。分析脚本只读既有推理产物与base源码，不调用模型、不执行测试、不训练、不更新历史矩阵。

本报告另附完整每题时长/token、阶段统计和逐次I/O表。仅报告已经观测到的事实；未知字段保持NA。
