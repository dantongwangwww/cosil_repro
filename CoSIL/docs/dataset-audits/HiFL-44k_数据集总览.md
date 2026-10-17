# HiFL-44k 数据集总览

核验日期：2026-10-17（Asia/Shanghai）。本任务仅下载和CPU分析，未训练、未使用GPU、未执行测试；T3第二轮训练持续运行。
数据固定版本：`lapsel/HiFL-44k@28177c9e423c8abf551892bc39b98e3bbeecd8c5`；官方实现固定commit：`1fe079f3f97556f6289321c030db7e9c3d9d1d5d`。

## 已核验结论

- 发布集实际 **44,002行**：文件级27,425、函数级9,193、行级7,384。JSONL与Parquet全部行、全部字段语义一致。
- 它是候选答案选择训练集：标签为`candidate N`，没有结构化repo/issue ID/PR/base commit/patch/test_patch/FAIL_TO_PASS。不能直接当成44k个独立bug或函数因果路径True/False样本。
- 30行源仓均可访问；29条在线issue正文精确匹配。28条找到明确针对问题的已合并PR，1条仅关联、1条未确认修复来源。
- 明确关联的28个修复PR中，测试相关文件修改 **15/28＝53.57%**。尚无运行时FAIL_TO_PASS或函数覆盖验证，已具备运行时双证据的样本数为0。
- 与Lite/Verified/Full **test评测仓库**的抽样交集均为0；与Full **全部split并集**有6/30行、5仓交集。不可笼统声称与整个SWE-bench全家零交集。

## 下载与完整性

[官方数据页](https://huggingface.co/datasets/lapsel/HiFL-44k/tree/28177c9e423c8abf551892bc39b98e3bbeecd8c5)由[官方实现README](https://github.com/SZU-ZJW/HiFL-Method/blob/1fe079f3f97556f6289321c030db7e9c3d9d1d5d/README.md)直接链接。四个发布文件全部落盘，大文件逐个核对官方LFS SHA256。

| 文件 | 字节 | SHA256 |
|---|---:|---|
| README.md | 1,757 | `0fa1872666963bf1b420c8cd9f5fee56fd25d1c0146472ebdc0cd14acf3132bf` |
| .gitattributes | 2,556 | `1e24363cd4c32ad1a9d3a1b145345579755b44a3f22786fe9ea611efac58a185` |
| HiFL-44k.parquet | 574,554,661 | `b8613b6140d96604f61431b5d1efe9f50083d37b1142c9db36ed0f656989a223` |
| HiFL-44k.jsonl | 1,745,870,044 | `b701ba5c064c366b78ccd053c9c76dc11f931e74068168f1d18bdee85d140526` |

总计2,320,429,018字节；目录：`/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/dataset_audits/HiFL44k_20261017/raw/`。文件清单亦见[CSV](HiFL-44k_下载文件清单.csv)。
下载采用单流≤8MiB/s、CPU nice19/空CUDA可见列表、idle I/O；预留18GiB磁盘给优先训练。原始JSONL不导入现有train/val。

## 字段与标签结构

| 字段 | 实际类型/数量 | 含义与限制 |
|---|---|---|
| problem | string，44,002非空行 | 完整任务提示，包含issue文字、目录/代码上下文及候选答案；未保留可靠的结构化源仓标识 |
| solution | string，44,002行 | JSON文本中的`answer: candidate N`，表示最佳选项序号；不是布尔因果标签，也不是独立patch |
| messages | list<struct<content:string,role:string>>，每行2条 | user/assistant聊天表示；全量与problem/solution精确对应，是重复序列化而非新增证据 |

| 任务 | 实测行数 |
|---|---:|
| 文件级：相关文件 | 13,715 |
| 文件级：不相关目录 | 13,710 |
| 函数/类/全局变量相关元素 | 9,193 |
| 行级（亦允许函数/类名定位） | 7,384 |
| 合计 | 44,002 |

全量恰有4种任务模板；44,002条problem均不同，提取后的issue文字块有13,407种。后者是文字去重数量，尚未逐一映射GitHub ID，不能当成已核验的独立issue数。候选序号解析失败0条；序号分布见本地统计JSON。
同一issue文字会出现在不同任务或候选组合中。以后如使用此集训练，需要先恢复来源并按issue/PR切分，不能用44k行随机划分来宣称无泄漏。

## 与论文数量的差异

论文Table1（PDF第5页/印刷页17786）列文件27,425、函数9,193、行7,484，合计44,102；本次两个发布格式均为44,002，差异全在行级：7,384对7,484。已同时核对PDF原页与实际任务模板计数。差异是发布版本变化、论文笔误还是其他原因，**待查**，不猜测为转换丢数据。[原论文Table1](https://aclanthology.org/2025.findings-emnlp.966.pdf#page=5)

## 源仓清单、分布与时间

**全量真实源仓列表及逐仓样本数：待查。** 发布集无repo/instance_id/PR字段，文本中的GitHub链接还可能指向依赖、示例项目或附件，不能拿URL提及频数冒充源仓分布。论文称近100仓，但没有可核对的逐行来源manifest。
确定性抽样30行（文件/函数/行各10）已识别21个源仓，下表只代表该30行。完整抽样分布与时间见[CSV](HiFL-44k_抽样源仓分布.csv)。

| 已核验抽样源仓 | 抽样行数 |
|---|---:|
| [Avaiga/taipy](https://github.com/Avaiga/taipy) | 1 |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | 1 |
| [apache/airflow](https://github.com/apache/airflow) | 1 |
| [dask/dask](https://github.com/dask/dask) | 1 |
| [dask/distributed](https://github.com/dask/distributed) | 1 |
| [frappe/erpnext](https://github.com/frappe/erpnext) | 1 |
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 1 |
| [holoviz/holoviews](https://github.com/holoviz/holoviews) | 1 |
| [huggingface/transformers](https://github.com/huggingface/transformers) | 2 |
| [keras-team/keras](https://github.com/keras-team/keras) | 4 |
| [letta-ai/letta](https://github.com/letta-ai/letta) | 1 |
| [localstack/localstack](https://github.com/localstack/localstack) | 2 |
| [numpy/numpy](https://github.com/numpy/numpy) | 1 |
| [openai/openai-python](https://github.com/openai/openai-python) | 1 |
| [pandas-dev/pandas](https://github.com/pandas-dev/pandas) | 1 |
| [pymc-devs/pymc](https://github.com/pymc-devs/pymc) | 1 |
| [pyscript/pyscript](https://github.com/pyscript/pyscript) | 1 |
| [python/mypy](https://github.com/python/mypy) | 5 |
| [ranger/ranger](https://github.com/ranger/ranger) | 1 |
| [searxng/searxng](https://github.com/searxng/searxng) | 1 |
| [wagtail/wagtail](https://github.com/wagtail/wagtail) | 1 |

全量文本出现802种GitHub owner/repo形状的URL词元，详见[URL提及清单](HiFL-44k_全量URL提及清单.csv)。其中甚至包括`user-attachments/assets`这类附件路径；该表不是源仓清单。
没有结构化时间字段。可在线核验的29条样本issue创建记录范围为2012-10-19T15:11:01Z至2024-11-16T20:28:38Z；所查候选PR合并记录范围为2015-07-03T10:19:26Z至2024-11-17T17:14:23Z。这些是抽样范围，不能外推全库时间范围。HF版本更新时间也不是issue时间。

## 代码版本能否重建

结构化base_commit/SHA字段为0/44,002；不能直接按行checkout出作者构造上下文时的版本。原始JSONL也没有比Parquet多出的元数据。
自由文本并非完全没有版本线索：6,016行出现40位十六进制串，3,712行含40位SHA固定的GitHub blob链接，204行含“Last Commit ID/SHA”字样。它们可能来自依赖或示例，不能统一解释为该样本base commit。
例：行19923的freqtrade issue文本报告`66415d48d4d9d42aaeec6beb1b8fc58dd58cf022`，本次确认该Git对象可访问。[报告的commit](https://github.com/freqtrade/freqtrade/commit/66415d48d4d9d42aaeec6beb1b8fc58dd58cf022)。
明确关联的修复PR可以补取base/head/merge SHA，逐条核验表已列出。这提供重建候选版本的入口；本次没有检验数据集展示的代码上下文是否与该PR base完全一致，因此仍不能认证作者实际使用的版本。

## 测试证据与采集标准

全量结构化`test_patch`、`FAIL_TO_PASS`、`PASS_TO_PASS`、patch以及“PR修改测试”标记均为0。唯一字面`test_patch`出现在代码标识符`_test_patches`，不是测试补丁字段。
论文§4的采集条件原文为：

> relevant issues must have been resolved and closed via a single merged Pull Request

[出处：论文§4，PDF第5页](https://aclanthology.org/2025.findings-emnlp.966.pdf#page=5)。README、论文正文/附录及固定版本公开代码中，未找到“PR必须修改测试”的强制条款。公开实现主要包含定位、仓库结构和patch解析，没有找到可重放上述筛选规则的HiFL issue/PR采集程序；实际完整采集脚本的过滤条件**待查**。
因此能确认的是“公开材料没有写明此要求”，不能据此断言作者私有流水线绝对没有测试过滤。实际样本也确有只改生产代码的针对性修复PR，例如[ranger#2818](https://github.com/ranger/ranger/pull/2818)、[freqtrade#2790](https://github.com/freqtrade/freqtrade/pull/2790)。
PR描述的勾选项不能替代文件清单：[distributed#4997](https://github.com/dask/distributed/pull/4997)勾选了“Tests added / passed”，实际只改`distributed/dashboard/components/scheduler.py`，没有测试文件改动。本报告以完整PR changed-files清单为准。

## 30行核验与双证据初评

抽样规则固定为每级10行，按`SHA256(HiFL44k:20261017:zero_based_row)`最小者选取，没有按能否找到PR或是否有测试挑样。本次30行涉及30个不同issue URL。
- 仓库访问：30/30；在线issue正文精确匹配：29/30。PyScript仓库当前Issues API返回410，来源由数据自链接、原issue页面缓存和针对该issue的合并PR交叉核验。
- 明确针对性合并PR：28/30；仅关联PR：1/30（Keras3703，次级错误修复）；未确认修复PR：1/30（mypy4794按设计关闭）。
- 明确修复PR的测试相关文件修改比例：15/28＝53.57%；若加入Keras弱关联候选则15/29＝51.72%。以全部30行为分母，已确认至少15/30有此痕迹，其余不能都当作已确认负例。
- 测试痕迹按`tests/`、`test-data/`、测试文件命名等路径规则及非零改动计数，包含fixture；不等于新增了可执行失败测试。每个PR均核对文件数与changed_files一致，没有静默截断。
- 当前可用运行时双证据：0/30。仅能说部分样本有可进一步恢复测试diff的入口；未验证失败前/修复后测试结果、FAIL_TO_PASS清单或函数覆盖集。
这是按层等额抽样且有来源回溯缺失后的描述比例，不是44k全库的测试修改率估计。样本逐条证据、SHA与测试路径见[30行核验表](HiFL-44k_30行逐条核验.md)。

## SWE-bench全家交集的两个口径

论文的排除声明包含以下片段：

> repositories included in SWE-Bench or its sub-benchmarks were excluded

[出处：论文§4](https://aclanthology.org/2025.findings-emnlp.966.pdf#page=5)。仓库名单提取仅使用HF官方聚合统计，没有下载基准样本文件，也未读取本地封存pruner test。
| 基准口径 | 仓库数 | 30行源仓交集 |
|---|---:|---:|
| Lite test300 | 12 | 0/30 |
| Verified test500 | 12 | 0/30 |
| Full test2294 | 12 | 0/30 |
| Full train19008＋dev225＋test2294 | 53 | **6/30，涉及5仓** |

5仓为：`apache/airflow`, `huggingface/transformers`, `numpy/numpy`, `pandas-dev/pandas`, `wagtail/wagtail`。这6行落在Full的train仓库范围；按“所有split”解释，不能报告零交集。此次只查仓库级重叠，没有验证同一issue/PR是否属于Full训练题，也不据此判定Lite/Verified题目泄漏。
官方逐仓频数和分split名单见[CSV](HiFL-44k_SWE-bench仓库名单.csv)；统计来源为[Full官方聚合统计](https://datasets-server.huggingface.co/statistics?dataset=princeton-nlp/SWE-bench&config=default&split=test)、[Lite](https://datasets-server.huggingface.co/statistics?dataset=princeton-nlp/SWE-bench_Lite&config=default&split=test)、[Verified](https://datasets-server.huggingface.co/statistics?dataset=princeton-nlp/SWE-bench_Verified&config=default&split=test)，各split响应均归档，频数总和与样本数一致。

## 对后续数据使用的判断与待查项

本集可以作为候选定位答案选择任务的公开来源。若要用于当前函数因果剪枝，需要先恢复issue→修复PR→确定版本→改动行/AST，再获得可运行失败测试与覆盖，不能直接把候选答案或PR改测试标记当成E类“无关函数”标签。本侧任务没有做这些转换或加入任何训练数据。
待查项：全量逐行源仓/PR/base manifest；行级少100条的原因；完整采集脚本及其测试过滤；28条明确PR的上下文版本一致性与实际运行时双证据。没有对这些空白填造数值。

## 复现与版本记录

新增分析代码前已保存并发布现有代码/文档：[5671921](https://github.com/dantongwangwww/cosil_repro/commit/5671921842f8828443a60e6eeaa20ea8202075e9)；深化核验前又保存初始下载/分析代码：[5748843](https://github.com/dantongwangwww/cosil_repro/commit/5748843271c0a90bef844f296c1272b8f745bd24)。
新增`code_dataset_audits/`，与T3代码/数据完全分开。流程为固定版本下载→流式字段/模板统计→原始格式逐行比对→确定性抽样→公开issue/PR逐条核验→报告；公开API查询与响应摘要缓存于独立结果目录。
初次下载会话未继承批准的代理环境，改用独立tmux socket恢复；GitHub原始文本TLS超时后，改用连接器读取固定commit并核Git blob。分析器补齐Skeleton标题分界后重新统计，初次产物留档；原始文件未改。只停止过自有侧任务下载重试，没有向T3、vLLM、CSRSE或他人进程发信号。
本地证据目录：`/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/dataset_audits/HiFL44k_20261017`。关键账本：[数据下载清单](../../results/dataset_audits/HiFL44k_20261017/dataset_download_manifest.json)、[全量统计](../../results/dataset_audits/HiFL44k_20261017/analysis/statistics.json)、[原始格式等价核验](../../results/dataset_audits/HiFL44k_20261017/analysis/raw_equivalence.json)、[30行证据](../../results/dataset_audits/HiFL44k_20261017/analysis/sample30_verified.json)。
