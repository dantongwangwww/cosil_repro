# 单题时长、token与真实工具使用审计

> CPU报告层校正：原自动稿永久归档；评分与推理不变。完整证据与边界见[外部验证验收与勘误](external_验收与勘误.md)。冻结CPU原生成器运行后，须再运行`python -m audit_tools.postprocess_report --apply`。

集合：external；run：20261021_external_nonthinking_v1。按instance_id关联，每题每臂仅一份结果。

“通常一题多久”以**中位数与P25–P75区间**为主，均值、P95揭示长尾。处理墙钟从worker开始处理到落盘，包含本题CPU/模型/网络；worker排队另列。客户端无法再把一次请求分成网络、服务端排队和纯模型计算，不伪造这三项。

token为实际usage累计，重复发送上下文会重复计入。Q-PRUNER另加专职裁判实际前向输入token，裁判只评分、不生成文本，因此其生成token为0。接口缺失的reasoning/cache字段不补0。

## 1. 单题典型耗时与token

| 方法 | 群体 | N | 均值秒 | 中位秒 | 通常P25–P75秒 | P95秒 | 平均累计输入 | 中位累计输入 | 平均输出 | 中位输出 | 平均总token | 中位总token | 总token P25–P75 |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| D-SIMPLE | all_executed | 100 | 7.58 | 7.33 | 6.66–8.49 | 9.94 | 46648 | 35328 | 541 | 530 | 47188 | 35802 | 22500–71290 |
| D-SIMPLE | completed | 100 | 7.58 | 7.33 | 6.66–8.49 | 9.94 | 46648 | 35328 | 541 | 530 | 47188 | 35802 | 22500–71290 |
| D-COSIL | all_executed | 100 | 29.90 | 23.40 | 20.19–26.98 | 35.97 | 76103 | 63307 | 1516 | 1472 | 77619 | 65040 | 52488–90916 |
| D-COSIL | completed | 94 | 31.30 | 23.52 | 20.51–26.98 | 37.94 | 76994 | 63936 | 1548 | 1478 | 78542 | 65732 | 53833–91642 |
| Q-COSIL | all_executed | 100 | 83.90 | 81.43 | 43.85–110.65 | 163.26 | 52712 | 53048 | 1063 | 1094 | 53775 | 54137 | 5334–71795 |
| Q-COSIL | completed | 70 | 104.51 | 98.46 | 75.28–121.43 | 168.12 | 73538 | 63040 | 1327 | 1282 | 74865 | 63876 | 52399–85522 |
| Q-PRUNER | all_executed | 100 | 86.34 | 83.84 | 46.58–107.73 | 172.25 | 51548 | 52642 | 1031 | 1064 | 52579 | 53656 | 5334–73178 |
| Q-PRUNER | completed | 66 | 107.49 | 100.20 | 80.45–121.14 | 192.89 | 74637 | 64484 | 1295 | 1254 | 75932 | 65840 | 54520–86839 |

all_executed包含真实失败和预算停止；completed为成功完成子组。两者并报以防删除慢题/失败题造成偏差。本外部集独立运行；恢复/复用次数逐题单列。通常耗时以本外部集实际执行记录为准，不混入Lite金丝雀或开发集。

## 2. 分阶段请求账

| 方法 | 阶段 | 到达题数 | 平均请求数/到达题 | 请求累计均值秒 | 请求累计中位秒 | 平均输入token | 平均输出token |
|---|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | file_selection_and_import_reflection | 100 | 1.95 | 5.18 | 3.66 | 6288 | 603 |
| D-COSIL | final_function_ranking | 94 | 1.00 | 1.15 | 1.11 | 8074 | 104 |
| D-COSIL | relevance_judge_main_model | 90 | 6.48 | 8.31 | 5.15 | 8626 | 34 |
| D-COSIL | search_navigation | 95 | 9.97 | 13.28 | 11.76 | 57329 | 826 |
| D-SIMPLE | file_selection_5_draws | 100 | 5.00 | 4.81 | 4.70 | 24781 | 340 |
| D-SIMPLE | final_function_ranking | 100 | 1.00 | 1.50 | 1.41 | 20986 | 148 |
| D-SIMPLE | query_planning | 100 | 1.00 | 0.90 | 0.91 | 881 | 52 |
| Q-COSIL | file_selection_and_import_reflection | 100 | 1.71 | 27.80 | 26.11 | 4845 | 373 |
| Q-COSIL | final_function_ranking | 70 | 1.00 | 6.42 | 6.30 | 7092 | 84 |
| Q-COSIL | relevance_judge_main_model | 68 | 7.37 | 3.67 | 3.77 | 7883 | 35 |
| Q-COSIL | search_navigation | 71 | 10.86 | 63.91 | 56.32 | 52877 | 856 |
| Q-PRUNER | file_selection_and_import_reflection | 100 | 1.71 | 27.25 | 26.77 | 4845 | 373 |
| Q-PRUNER | final_function_ranking | 66 | 1.00 | 6.62 | 6.62 | 7048 | 85 |
| Q-PRUNER | relevance_judge_main_model | 42 | 2.62 | 1.20 | 0.86 | 2733 | 12 |
| Q-PRUNER | search_navigation | 71 | 10.51 | 63.63 | 54.73 | 50999 | 840 |

分阶段均值按实际到达该阶段的题计算；未到达不伪填为成功的0秒。D-SIMPLE的五次文件选择合为一阶段，CoSIL文件选择与导入关系反思合并。裁判前向、CPU图构建和工具执行详见逐题CSV，非同一计时口径不能直接相减称纯GPU秒。

D-SIMPLE使用固定加载器，不采用CoSIL自由DSL工具或相关性裁判。其100个最终function_localization请求均含完整非空context且有成功回执；通用“agent未收到源码仍定位”为false。工具专用布尔字段为null/NA，原CoSIL工具计数0仅表示无该类调用，不表示源码未装载。

## 3. 模型到底有没有使用工具

**这里的CoSIL采用文本DSL调用，经白名单AST解析后由框架执行；不是API原生tool_calls。** 下面只把有真实执行事件的调用计为执行，exit单列。模型说“我读了”而无事件不算。D-SIMPLE是固定文件装载/一次grep流程，不能将它的文件数当成自由工具调用数。

| 方法 | 动作响应 | 解析通过(含exit) | 严格单调用文本 | 实际执行 | 执行成功 | 真正返回源码 | 裁判收到源码 | 搜索agent收到源码 | 工具错误 | 重复输入 | exit/读源码前exit | 无agent源码仍定位题 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D-COSIL | 852 | 643 | 640 | 591 | 583 | 583 | 578 | 331 | 8 | 2 | 52/0 | 7 |
| Q-COSIL | 700 | 680 | 680 | 680 | 501 | 501 | 487 | 174 | 179 | 178 | 0/0 | 22 |
| Q-PRUNER | 675 | 642 | 642 | 642 | 468 | 468 | 464 | 197 | 174 | 166 | 0/0 | 18 |

补审边界：表内保留自动绑定数字作为下界。D-COSIL自动裁判/agent计数578/331，五例原始payload补审后为583/332；题级取回/送达90/88、无源码仍定位5/7不变。全部1552次成功源码返回（D-COSIL583、Q-COSIL501、Q-PRUNER468）已由独立CPU补审核验返回SHA及base来源；原自动1529条绑定之外为5+14+4条。Q两臂14/4条的源码来源核验不自动证明裁判或agent收到；相应送达栏仍按已记录证据列下界。D五例中四例是首个overload声明、一例是property getter，来源真实不代表读取了运行实现体。

小裁判gold直剪0只统计高置信直接reject。验收另确认2个gold灰区升级主Qwen后被判False的整管线拒绝事件，应单列而不改写小裁判直剪字段；事件数不能直接当作唯一题数，详见验收文档。

“解析通过”仅证明调用语法可绑定；参数还必须对应真实文件/类/函数。执行成功也可能只是节点目录，只有source才算源码。pruner拒绝会导致“已取回、裁判已看见、搜索agent没看见”，三者分别统计。文件阶段由框架隐式读import行，不冒充模型主动函数源码调用。

## 4. 输入/输出是否符合工具约定

| 方法 | 非exit提议(含解析失败) | base目标与工具作用域有效 | 提议→真实成功 | 已执行→成功 | 源码返回与base逐行一致 | 源码返回不一致 |
|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | 800 | 583 | 72.88% | 98.65% | 578 | 0 |
| Q-COSIL | 700 | 501 | 71.57% | 73.68% | 487 | 0 |
| Q-PRUNER | 675 | 468 | 69.33% | 72.90% | 464 | 0 |

| 方法 | 已有结果题数 | 至少一次源码工具成功题 | 搜索agent真实收到源码题 | 工具无源码仍定位题 | agent无源码仍定位题 | DSML动作/结构完整/目标有效 |
|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | 100 | 90 | 88 | 5 | 7 | 215/112/110 |
| Q-COSIL | 100 | 68 | 48 | 2 | 22 | 0/0/0 |
| Q-PRUNER | 100 | 68 | 51 | 2 | 18 | 0/0/0 |

搜索agent收到源码需同时有context_accept事件，并在之后有成功API回执的搜索/总结请求中找到完整原文。context插入、实际送达分别落盘。小裁判需有真实评分事件及已保存的v6输入哈希核验；不把框架取到源码直接等同于agent读到。

DSML仅做离线语法/参数诊断，绝不执行、纠正或重跑。官方V4.1使用`<｜DSML｜ calls>`；重复竖线等偏离单列，结构缺失直接记失败。输出DSML不符合本实验请求的Python式调用；能辨识调用意图也不等于原框架执行成功。依据：[DeepSeek官方编码说明](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/encoding/README.md)。

get_code_of_file_function要求文件内独立函数，get_code_of_class_function要求文件/类/方法分开传参，get_code_of_class返回类源码；get_functions_of_class返回节点元数据，不应当作源码。裸类名可由框架在候选文件中唯一推断时，另标file_argument_inferred_by_framework；别名归一和多调用文本也单列。

## 5. 代表调用（原始完整记录见tool_io_per_call.csv及calls）

| 方法/issue | 原始动作 | 真实执行/返回 | 参数/返回核验 | 证据 |
|---|---|---|---|---|
| D-COSIL/lincc-frameworks__nested-pandas-190 | `get_code_of_file_function('src/nested_pandas/series/packer.py', 'view_sorted_series_as_list_array')` | def view_sorted_series_as_list_array( ↵     series: pd.Series, offset: np.ndarray \| None = None, unique_index: np.ndarray \| None = None ↵ ) -> pd.Series: ↵    | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/lincc-frameworks__nested-pandas-190/calls/0004_node_selection` |
| D-COSIL/django-guardian__django-guardian-904 | `get_code_of_class_function('guardian/core.py', 'ObjectPermissionChecker', '_get_pks_model_and_ctype')` | You provide a wrong file name or class name or function name. Please try another file name again. It may be a file function. | definition_not_in_supplied_file_or_class; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/django-guardian__django-guardian-904/calls/0006_node_selection` |
| D-COSIL/tox-dev__tox-3846 | `<｜｜DSML｜｜ calls> ↵ <｜｜DSML｜｜ invoke name="get_code_of_class_function"> ↵ <｜｜DSML｜｜ parameter name="file_name" string="true">src/tox/tox_env/` | No supported tool call found in the model output | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/tox-dev__tox-3846/calls/0004_node_selection` |
| D-COSIL/yt-project__unyt-560 | `I have enough information. The bug is clearly in ｀from_hdf5｀, where ｀data = dataset[:]｀ fails for scalar (0-dimensional) datasets. The fix i` | exit; prior source=7 | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/D-COSIL/yt-project__unyt-560/calls/0018_node_selection` |
| Q-COSIL/tox-dev__tox-3846 | `｀｀｀python ↵ get_code_of_file_function('src/tox/session/cmd/version_flag.py', 'get_version_info') ↵ ｀｀｀` | def get_version_info() -> str: ↵     out = [f"{version} from {Path(tox.__file__).absolute()}"] ↵     plugin_info = MANAGER.manager.list_plugin_distinfo() ↵      | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/tox-dev__tox-3846/calls/0006_node_selection` |
| Q-COSIL/tox-dev__tox-3846 | `｀｀｀python ↵ get_code_of_file_function('src/tox/config/source/toml_tox.py', 'get_version_info') ↵ ｀｀｀` | You provide a wrong file name or function name. Please try another file name again. It may be a class function. | definition_not_in_supplied_file_or_class; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/tox-dev__tox-3846/calls/0004_node_selection` |
| Q-COSIL/hkuds__openharness-217 | `Let's examine the ｀subprocess.Popen｀ call within the ｀DeviceCodeFlow._try_open_browser｀ method in ｀src/openharness/auth/flows.py｀. ↵  ↵ ｀｀｀p` | Too many tool arguments | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-COSIL/hkuds__openharness-217/calls/0006_node_selection` |
| Q-PRUNER/tox-dev__tox-3846 | `｀｀｀python ↵ get_code_of_file_function('src/tox/session/cmd/version_flag.py', 'get_version_info') ↵ ｀｀｀` | def get_version_info() -> str: ↵     out = [f"{version} from {Path(tox.__file__).absolute()}"] ↵     plugin_info = MANAGER.manager.list_plugin_distinfo() ↵      | exact_base_definition; base_match=True | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/tox-dev__tox-3846/calls/0006_node_selection` |
| Q-PRUNER/tox-dev__tox-3846 | `｀｀｀python ↵ get_code_of_file_function('src/tox/config/source/toml_tox.py', 'get_version_info') ↵ ｀｀｀` | You provide a wrong file name or function name. Please try another file name again. It may be a class function. | definition_not_in_supplied_file_or_class; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/tox-dev__tox-3846/calls/0004_node_selection` |
| Q-PRUNER/hkuds__openharness-217 | `Let's examine the ｀subprocess.Popen｀ call within the ｀DeviceCodeFlow._try_open_browser｀ method in ｀src/openharness/auth/flows.py｀. ↵  ↵ ｀｀｀p` | Too many tool arguments | ; base_match=None | `/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1/runs/20261021_external_nonthinking_v1/external/Q-PRUNER/hkuds__openharness-217/calls/0005_node_selection` |

这些是描述性机制证据；使用工具不等于定位正确，参数错误也不能只凭一次失败归咎框架。需要结合base定义是否存在、工具支持的作用域和实际错误响应。完整逐题/逐调用CSV保留原文、规范调用、参数、输出SHA、耗时及进入哪个上下文的证据。

## 6. 加载、队列、恢复和不可测量项

| 方法 | worker排队中位/P95秒 | 裁判加载总秒 | 每题构图均值/中位秒 | 传输失败次数 | 重放/复用题 |
|---|---:|---:|---:|---:|---:|
| D-SIMPLE | 185.93/358.24 | NA | NA/NA | 0 | 0 |
| D-COSIL | 584.84/1519.08 | NA | NA/NA | 0 | 0 |
| Q-COSIL | 3713.89/7810.61 | NA | NA/NA | 0 | 0 |
| Q-PRUNER | 3814.86/8064.66 | 21.43 | 4.32/1.40 | 0 | 0 |

自建主Qwen服务启动至就绪：{'ready_at': '2026-10-21T12:13:48.222251+00:00', 'startup_seconds': 40.700964448042214, 'included_in_per_issue_processing_time': False, 'definition': 'Owned Qwen launch through successful /models health check'}。该一次性过程不混入每题处理时长。HTTP冷连接调用、重试和worker队列已记账；服务端TTFT/内部排队和纯GPU核时间没有直接观测，不以客户端耗时猜测。

## 7. 复现与边界

分析命令：`python -m external_v1.report`。分析脚本只读既有推理产物与base源码，不调用模型、不执行测试、不训练、不更新历史矩阵。

本报告另附完整每题时长/token、阶段统计和逐次I/O表。仅报告已经观测到的事实；未知字段保持NA。
