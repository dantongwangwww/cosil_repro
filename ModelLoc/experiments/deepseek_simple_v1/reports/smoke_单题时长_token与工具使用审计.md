# 单题时长、token与真实工具使用审计

集合：smoke；run：20261021_nonthinking_v3。按instance_id关联，每题每臂仅一份结果。

“通常一题多久”以**中位数与P25–P75区间**为主，均值、P95揭示长尾。处理墙钟从worker开始处理到落盘，包含本题CPU/模型/网络；worker排队另列。客户端无法再把一次请求分成网络、服务端排队和纯模型计算，不伪造这三项。

token为实际usage累计，重复发送上下文会重复计入。Q-PRUNER另加专职裁判实际前向输入token，裁判只评分、不生成文本，因此其生成token为0。接口缺失的reasoning/cache字段不补0。

## 1. 单题典型耗时与token

| 方法 | 群体 | N | 均值秒 | 中位秒 | 通常P25–P75秒 | P95秒 | 平均累计输入 | 中位累计输入 | 平均输出 | 中位输出 | 平均总token | 中位总token | 总token P25–P75 |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| D-SIMPLE | all_executed | 5 | 84.43 | 138.62 | 2.59–139.58 | 139.81 | 109425 | 108045 | 434 | 436 | 109858 | 108638 | 88886–127045 |
| D-SIMPLE | completed | 5 | 84.43 | 138.62 | 2.59–139.58 | 139.81 | 109425 | 108045 | 434 | 436 | 109858 | 108638 | 88886–127045 |
| D-COSIL | all_executed | 5 | 171.93 | 183.22 | 20.34–305.55 | 326.26 | 89954 | 91857 | 1476 | 1473 | 91429 | 93277 | 56420–127209 |
| D-COSIL | completed | 5 | 171.93 | 183.22 | 20.34–305.55 | 326.26 | 89954 | 91857 | 1476 | 1473 | 91429 | 93277 | 56420–127209 |
| Q-COSIL | all_executed | 5 | 84.24 | 96.48 | 91.73–105.01 | 118.10 | 74487 | 86356 | 866 | 1004 | 75353 | 87509 | 57250–97848 |
| Q-COSIL | completed | 4 | 103.65 | 100.75 | 95.29–109.10 | 118.92 | 91578 | 91600 | 1068 | 1078 | 92646 | 92678 | 79944–105380 |
| Q-PRUNER | all_executed | 5 | 108.47 | 116.58 | 92.02–139.22 | 171.65 | 76703 | 96965 | 852 | 1003 | 77556 | 98062 | 57250–98629 |
| Q-PRUNER | completed | 4 | 131.89 | 127.90 | 110.44–149.35 | 173.67 | 94347 | 97296 | 1052 | 1050 | 95399 | 98346 | 87859–105885 |

all_executed包含真实失败和预算停止；completed为成功完成子组。两者并报以防删除慢题/失败题造成偏差。P0存在前序请求重放与结果复用，不用其续跑墙钟估计稳定单题耗时；正式典型时长以未重放的P1为准。

## 2. 分阶段请求账

| 方法 | 阶段 | 到达题数 | 平均请求数/到达题 | 请求累计均值秒 | 请求累计中位秒 | 平均输入token | 平均输出token |
|---|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | file_selection_and_import_reflection | 5 | 2.00 | 138.47 | 139.02 | 11669 | 449 |
| D-COSIL | final_function_ranking | 5 | 1.00 | 1.11 | 1.08 | 9301 | 90 |
| D-COSIL | relevance_judge_main_model | 4 | 7.25 | 5.56 | 5.34 | 7384 | 29 |
| D-COSIL | search_navigation | 5 | 9.40 | 10.76 | 11.09 | 63076 | 914 |
| D-SIMPLE | file_selection_5_draws | 5 | 5.00 | 58.54 | 5.03 | 68083 | 224 |
| D-SIMPLE | final_function_ranking | 5 | 1.00 | 83.51 | 137.38 | 40666 | 159 |
| D-SIMPLE | query_planning | 5 | 1.00 | 0.88 | 0.90 | 676 | 51 |
| Q-COSIL | file_selection_and_import_reflection | 5 | 1.80 | 24.06 | 27.52 | 9689 | 309 |
| Q-COSIL | final_function_ranking | 4 | 1.00 | 6.14 | 6.25 | 8061 | 80 |
| Q-COSIL | relevance_judge_main_model | 3 | 6.33 | 3.06 | 2.97 | 5392 | 31 |
| Q-COSIL | search_navigation | 4 | 11.00 | 45.11 | 45.13 | 68893 | 592 |
| Q-PRUNER | file_selection_and_import_reflection | 5 | 1.80 | 23.05 | 26.36 | 9689 | 309 |
| Q-PRUNER | final_function_ranking | 4 | 1.00 | 6.27 | 6.45 | 8368 | 82 |
| Q-PRUNER | relevance_judge_main_model | 2 | 3.00 | 1.33 | 1.33 | 1812 | 15 |
| Q-PRUNER | search_navigation | 4 | 11.00 | 44.65 | 44.77 | 70650 | 589 |

分阶段均值按实际到达该阶段的题计算；未到达不伪填为成功的0秒。D-SIMPLE的五次文件选择合为一阶段，CoSIL文件选择与导入关系反思合并。裁判前向、CPU图构建和工具执行详见逐题CSV，非同一计时口径不能直接相减称纯GPU秒。

## 3. 模型到底有没有使用工具

**这里的CoSIL采用文本DSL调用，经白名单AST解析后由框架执行；不是API原生tool_calls。** 下面只把有真实执行事件的调用计为执行，exit单列。模型说“我读了”而无事件不算。D-SIMPLE是固定文件装载/一次grep流程，不能将它的文件数当成自由工具调用数。

| 方法 | 动作响应 | 解析通过(含exit) | 严格单调用文本 | 实际执行 | 执行成功 | 真正返回源码 | 裁判收到源码 | 搜索agent收到源码 | 工具错误 | 重复输入 | exit/读源码前exit | 无agent源码仍定位题 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D-COSIL | 42 | 32 | 32 | 29 | 29 | 29 | 29 | 16 | 0 | 1 | 3/0 | 1 |
| Q-COSIL | 40 | 40 | 40 | 40 | 19 | 19 | 19 | 12 | 21 | 15 | 0/0 | 1 |
| Q-PRUNER | 40 | 40 | 40 | 40 | 16 | 16 | 16 | 9 | 24 | 14 | 0/0 | 2 |

“解析通过”仅证明调用语法可绑定；参数还必须对应真实文件/类/函数。执行成功也可能只是节点目录，只有source才算源码。pruner拒绝会导致“已取回、裁判已看见、搜索agent没看见”，三者分别统计。文件阶段由框架隐式读import行，不冒充模型主动函数源码调用。

## 4. 输入/输出是否符合工具约定

| 方法 | 非exit提议(含解析失败) | base目标与工具作用域有效 | 提议→真实成功 | 已执行→成功 | 源码返回与base逐行一致 | 源码返回不一致 |
|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | 39 | 29 | 74.36% | 100.00% | 29 | 0 |
| Q-COSIL | 40 | 19 | 47.50% | 47.50% | 19 | 0 |
| Q-PRUNER | 40 | 16 | 40.00% | 40.00% | 16 | 0 |

| 方法 | 已有结果题数 | 至少一次源码工具成功题 | 搜索agent真实收到源码题 | 工具无源码仍定位题 | agent无源码仍定位题 | DSML动作/结构完整/目标有效 |
|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | 5 | 4 | 4 | 1 | 1 | 10/7/7 |
| Q-COSIL | 5 | 3 | 3 | 1 | 1 | 0/0/0 |
| Q-PRUNER | 5 | 3 | 2 | 1 | 2 | 0/0/0 |

搜索agent收到源码需同时有context_accept事件，并在之后有成功API回执的搜索/总结请求中找到完整原文。context插入、实际送达分别落盘。小裁判需有真实评分事件及已保存的v6输入哈希核验；不把框架取到源码直接等同于agent读到。

DSML仅做离线语法/参数诊断，绝不执行、纠正或重跑。官方V4.1使用`<｜DSML｜ calls>`；重复竖线等偏离单列，结构缺失直接记失败。输出DSML不符合本实验请求的Python式调用；能辨识调用意图也不等于原框架执行成功。依据：[DeepSeek官方编码说明](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/encoding/README.md)。

get_code_of_file_function要求文件内独立函数，get_code_of_class_function要求文件/类/方法分开传参，get_code_of_class返回类源码；get_functions_of_class返回节点元数据，不应当作源码。裸类名可由框架在候选文件中唯一推断时，另标file_argument_inferred_by_framework；别名归一和多调用文本也单列。

## 5. 代表调用（原始完整记录见tool_io_per_call.csv及calls）

| 方法/issue | 原始动作 | 真实执行/返回 | 参数/返回核验 | 证据 |
|---|---|---|---|---|
| D-COSIL/django__django-13768 | `get_code_of_class_function('django/dispatch/dispatcher.py', 'Signal', 'send_robust')` |     def send_robust(self, sender, **named): ↵         """ ↵         Send signal from sender to all connected receivers catching errors. ↵  ↵         Arguments:  | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-COSIL/django__django-13768/calls/0004_node_selection` |
| D-COSIL/scikit-learn__scikit-learn-13241 | `<｜｜DSML｜｜ calls> ↵ <｜｜DSML｜｜ invoke name="get_code_of_class_function"> ↵ <｜｜DSML｜｜ parameter name="file_name" string="true">sklearn/decompos` | No supported tool call found in the model output | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-COSIL/scikit-learn__scikit-learn-13241/calls/0004_node_selection` |
| D-COSIL/django__django-13768 | `I have enough information. The bug report asks to add a ｀logger.exception()｀ call in the ｀except｀ clause of ｀send_robust()｀. The ｀send_robus` | exit; prior source=6 | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-COSIL/django__django-13768/calls/0016_node_selection` |
| Q-COSIL/sympy__sympy-18621 | `get_code_of_class_function('sympy/matrices/expressions/blockmatrix.py', 'BlockDiagMatrix', '__new__')` |     def __new__(cls, *mats): ↵         return Basic.__new__(BlockDiagMatrix, *mats) ↵  | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-COSIL/sympy__sympy-18621/calls/0004_node_selection` |
| Q-COSIL/django__django-13768 | `get_code_of_file_function('django/core/signals.py', 'send_robust')` | You provide a wrong file name or function name. Please try another file name again. It may be a class function. | definition_not_in_supplied_file_or_class; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-COSIL/django__django-13768/calls/0004_node_selection` |
| Q-PRUNER/sympy__sympy-18621 | `get_code_of_class_function('sympy/matrices/expressions/blockmatrix.py', 'BlockDiagMatrix', '__new__')` |     def __new__(cls, *mats): ↵         return Basic.__new__(BlockDiagMatrix, *mats) ↵  | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-PRUNER/sympy__sympy-18621/calls/0004_node_selection` |
| Q-PRUNER/django__django-13768 | `get_code_of_file_function('django/core/signals.py', 'send_robust')` | You provide a wrong file name or function name. Please try another file name again. It may be a class function. | definition_not_in_supplied_file_or_class; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-PRUNER/django__django-13768/calls/0004_node_selection` |

这些是描述性机制证据；使用工具不等于定位正确，参数错误也不能只凭一次失败归咎框架。需要结合base定义是否存在、工具支持的作用域和实际错误响应。完整逐题/逐调用CSV保留原文、规范调用、参数、输出SHA、耗时及进入哪个上下文的证据。

## 6. 加载、队列、恢复和不可测量项

| 方法 | worker排队中位/P95秒 | 裁判加载总秒 | 每题构图均值/中位秒 | 传输失败次数 | 重放/复用题 |
|---|---:|---:|---:|---:|---:|
| D-SIMPLE | 0.38/0.38 | NA | NA/NA | 0 | 5 |
| D-COSIL | NA/NA | NA | NA/NA | 0 | 5 |
| Q-COSIL | NA/NA | NA | NA/NA | 0 | 5 |
| Q-PRUNER | NA/NA | NA | NA/NA | 0 | 5 |

自建主Qwen服务启动至就绪：{'ready_at': '2026-10-21T08:51:23.289281+00:00', 'startup_seconds': 60.737413237802684, 'included_in_per_issue_processing_time': False, 'definition': 'Owned Qwen service process start through successful /models health check'}。该一次性过程不混入每题处理时长。HTTP冷连接调用、重试和worker队列已记账；服务端TTFT/内部排队和纯GPU核时间没有直接观测，不以客户端耗时猜测。

## 7. 复现与边界

分析命令：`python analysis/performance_and_tools.py --cohort smoke`。分析脚本只读既有推理产物与base源码，不调用模型、不执行测试、不训练、不更新历史矩阵。

本报告另附完整每题时长/token、阶段统计和逐次I/O表。仅报告已经观测到的事实；未知字段保持NA。
