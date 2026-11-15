# GraphLocator＋Qwen3-8B：280题定位失败分析

> 本页为已定稿综合审计的文档副本，只调整本地证据链接以适应docs位置；分析与预测不变。原件SHA256：`e608414a747634df238c1400d5b7f3edc98b6161080a99417ff0b94dd7ea4709`。以下result/HTTP链接仅本地可用，原始数据和日志不随Git公开。

本报告仅在280题推理、runner回执及正式离线评价全部完成后生成。全部使用同一V3协议；未重放工具、未新增模型调用、未根据金标改预测。金标只由最终离线评价提供给事后归因。

## 分类总结

函数Hit@1/3/5分别为51/280（18.21%）、88/280（31.43%）、100/280（35.71%）；文件Hit@1/3/5为112/280（40.00%）、162/280（57.86%）、166/280（59.29%）。以下分析180道函数Top-5未命中题，所有执行失败保留分母。

| 可观察阶段 | 题数 | 占180道未命中题 |
|---|---:|---:|
| 图中未发现可精确对应的显式目标函数节点 | 1 | 0.56% |
| 图中有目标函数节点，但检索候选未见显式目标函数 | 120 | 66.67% |
| 显式目标函数已送CIG，但最终未绑定 | 36 | 20.00% |
| 显式目标曾召回，但相关性过滤后未进入种子 | 3 | 1.67% |
| 上下文容量限制 | 7 | 3.89% |
| 目标已输出，但排名在Top5之后 | 12 | 6.67% |
| 单题1800秒预算终止 | 1 | 0.56% |

这些类别按最后可核验的阶段互斥统计，并非单一因果结论。120题的图中已有至少一个目标函数节点，但检索原候选未出现显式目标函数；这不等于模型从未见过含目标的类或文件。36题中至少一个目标函数Node及其content确实进入CIG模型请求，最终没有保留该函数绑定，因此不能统一归咎于“工具不会用”。12题已有目标输出，只是顺序未进入Top-5。

## 工具、输入和资源契约

- 1264次声明的检索工具调用均成功解析并实际执行；未发现未知工具名、参数JSON错误或工具执行异常。
- 353次工具结果经过定长JSON布尔相关性判断，909次按原算法小于top-k直接采用；另2次在相关性请求的上下文预检处终止，不能当成全False。
- 1064份过滤后工具观测可在后续搜索HTTP请求中逐项核验；200份没有后续搜索请求，其中包含搜索末轮结束和上述容量终止。原流程先过滤，再将观测送搜索；没有要求把被过滤的全部原文继续发送。
- 相关性候选顺序、JSON长度、过滤后观测、CIG候选文本与绑定、显式非思考、实际采样及图源绑定检查均未发现差异。文本确实送达不等于模型有效使用，也不证明每个content都是完整AST函数体。
- 3763次generation HTTP尝试，已知输入16,515,005 token、输出951,723 token，合计至少17,466,728 token；pypa__auditwheel-568有1次在1800秒终止时未结束的请求，用量未知，不能记零或声称精确总量。
- 所有请求调用方仍传原temperature=0，transport实际统一采用已冻结的非思考采样temperature=0.7、top_p=0.8、top_k=20、min_p=0、seed=0；并非声称温度0运行。
- 272题自然完成、7题超过65536上下文容量、1题达到1800秒单题预算；未发现本轮工具接口/输出定长契约失败。容量和预算失败不能证明模型必然不会定位。
- 55项运行源码SHA与冻结协议逐项一致。CIG最终排名沿用原factor/binding插入顺序，没有事后按置信度或金标重排。

## 静态图库存能否表示目标

366个既有目标函数中，362个能由静态图函数族节点按公开base AST的路径、定义起点和原叶名精确映射；4个缺少可精确对应的显式函数节点，涉及4题：276题目标全有、3题部分有、1题全部未精确验证。4个都是外层函数内的嵌套函数。

未发现精确函数节点是图表示层面的限制，不能断言源码不在图内：类、完整文件或外层函数正文仍可能包含目标函数定义。没有将这些外层节点扩展为函数预测，也没有利用金标补节点或别名。

- neurostuff__NiMARE-939：nimare/io.py::convert_nimads_to_dataset._analysis_to_dict。
- owkin__PyDESeq2-349：pydeseq2/utils.py::nbinomGLM.df。
- python-babel__babel-1163：babel/dates.py::format_timedelta._iter_patterns。
- SciTools__iris-6754：lib/iris/fileformats/netcdf/loader.py::_translate_constraints_to_var_callback.inner。

## 逐题分析（180道函数Top-5未命中）

下列“候选/送达/绑定”均只指可由公开AST精确识别的显式函数Node，不替代对全部类/文件正文的完整可见性认证。具体语义原因证据不足时保留不确定。

### neurostuff__NiMARE-939

- 分类：图中未发现可精确对应的显式目标函数节点。执行状态：complete。
- 既有目标函数：nimare/io.py::convert_nimads_to_dataset._analysis_to_dict。
- 图中精确目标节点：0/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：nimare/meta/kernel.py::ALEKernel._transform；nimare/meta/kernel.py::ALEKernel._generate_description。
- 无精确图函数节点/待核身份：nimare/io.py::convert_nimads_to_dataset._analysis_to_dict [NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET]。外层代码正文仍可能含其源码。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/neurostuff__NiMARE-939/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/neurostuff__NiMARE-939/http/events.jsonl)。

### radomirbosak__duden-87

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：duden/main.py::DudenWord.meaning_overview。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：duden/common.py::clear_text。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/radomirbosak__duden-87/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/radomirbosak__duden-87/http/events.jsonl)。

### Toblerity__rtree-141

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：rtree/index.py::Index.nearest。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：tests/test_index.py::IndexNearest.test_nearest_object；rtree/index.py::Index.get_coordinate_pointers；tests/test_index.py::IndexContainer.test_container；rtree/index.py::RtreeContainer.insert；rtree/index.py::RtreeContainer.nearest。
- 已实际送入CIG候选的显式目标函数：rtree/index.py::Index.nearest。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Toblerity__rtree-141/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Toblerity__rtree-141/http/events.jsonl)。

### pangeo-data__xESMF-78

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：xesmf/frontend.py::_get_lon_lat_bounds。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：xesmf/frontend.py::SpatialAverager.__init__；xesmf/frontend.py::_get_lon_lat；xesmf/frontend.py::ds_to_ESMFlocstream；xesmf/frontend.py::BaseRegridder.__init__；xesmf/frontend.py::Regridder.__init__。
- 观察到False的目标函数：xesmf/frontend.py::_get_lon_lat_bounds（并不表示该目标在所有调用中始终被剔除）。
- 已实际送入CIG候选的显式目标函数：xesmf/frontend.py::_get_lon_lat_bounds。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pangeo-data__xESMF-78/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pangeo-data__xESMF-78/http/events.jsonl)。

### huggingface__smolagents-285

- 分类：显式目标曾召回，但相关性过滤后未进入种子。执行状态：complete。
- 既有目标函数：src/smolagents/local_python_executor.py::evaluate_ast；src/smolagents/local_python_executor.py::evaluate_augassign。
- 图中精确目标节点：2/2；原检索显式候选中目标：1；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 观察到False的目标函数：src/smolagents/local_python_executor.py::evaluate_ast（并不表示该目标在所有调用中始终被剔除）。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/huggingface__smolagents-285/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/huggingface__smolagents-285/http/events.jsonl)。

### pypest__pyemu-588

- 分类：上下文容量限制。执行状态：ContextBudgetExceeded。
- 既有目标函数：pyemu/utils/pst_from.py::PstFrom._dict_get_xy。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 资源证据：完整候选/代码输入超过冻结上下文容量，未偷偷裁剪、删候选或追加调用救分。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pypest__pyemu-588/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pypest__pyemu-588/http/events.jsonl)。

### owkin__PyDESeq2-349

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：pydeseq2/utils.py::nbinomGLM；pydeseq2/utils.py::nbinomGLM.df。
- 图中精确目标节点：1/2；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：pydeseq2/inference.py::Inference.lfc_shrink_nbinom_glm；pydeseq2/inference.py::Inference.irls；pydeseq2/inference.py::Inference.lin_reg_mu；pydeseq2/inference.py::Inference.fit_rough_dispersions；pydeseq2/inference.py::Inference.alpha_mle。
- 已实际送入CIG候选的显式目标函数：pydeseq2/utils.py::nbinomGLM。
- 无精确图函数节点/待核身份：pydeseq2/utils.py::nbinomGLM.df [NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET]。外层代码正文仍可能含其源码。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/owkin__PyDESeq2-349/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/owkin__PyDESeq2-349/http/events.jsonl)。

### facultyai__marshmallow-dataframe-19

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/marshmallow_dataframe/split.py::SplitDataFrameSchema.validate_index_data_length；src/marshmallow_dataframe/split.py::SplitDataFrameSchemaMeta.get_fields。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/test_split.py::split_sample_schema；tests/test_split.py::test_split_schema_index_data_length_mismatch；tests/test_split.py::split_serialized_df；tests/test_split.py::test_split_schema_str_index。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/facultyai__marshmallow-dataframe-19/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/facultyai__marshmallow-dataframe-19/http/events.jsonl)。

### aiidateam__aiida-quantumespresso-1136

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：src/aiida_quantumespresso/workflows/protocols/utils.py::ProtocolMixin.get_protocol_inputs。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：tests/workflows/protocols/pw/test_base.py::test_parameter_overrides；src/aiida_quantumespresso/workflows/pw/base.py::PwBaseWorkChain.get_builder_from_protocol；src/aiida_quantumespresso/workflows/protocols/utils.py::recursive_merge；tests/workflows/protocols/pw/test_base.py::test_pseudos_overrides_raises；src/aiida_quantumespresso/workflows/pw/relax.py::PwRelaxWorkChain.get_builder_from_protocol。
- 已实际送入CIG候选的显式目标函数：src/aiida_quantumespresso/workflows/protocols/utils.py::ProtocolMixin.get_protocol_inputs。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/aiidateam__aiida-quantumespresso-1136/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/aiidateam__aiida-quantumespresso-1136/http/events.jsonl)。

### lovasoa__marshmallow_dataclass-85

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：marshmallow_dataclass/__init__.py::field_for_schema。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/lovasoa__marshmallow_dataclass-85/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/lovasoa__marshmallow_dataclass-85/http/events.jsonl)。

### Textualize__textual-4313

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/textual/app.py::App._broker_event。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Textualize__textual-4313/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Textualize__textual-4313/http/events.jsonl)。

### pycqa__isort-2491

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：isort/output.py::_with_from_imports。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/unit/test_regressions.py::test_isort_should_leave_non_import_from_lines_alone_issue_1488。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pycqa__isort-2491/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pycqa__isort-2491/http/events.jsonl)。

### AzureAD__microsoft-authentication-library-for-python-280

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：msal/token_cache.py::TokenCache.modify。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：msal/token_cache.py::SerializableTokenCache.deserialize；tests/test_token_cache.py::SerializableTokenCacheTestCase.setUp。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/AzureAD__microsoft-authentication-library-for-python-280/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/AzureAD__microsoft-authentication-library-for-python-280/http/events.jsonl)。

### nolar__kopf-1225

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：kopf/_core/reactor/observation.py::is_deleted；kopf/_core/reactor/observation.py::revise_namespaces。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：examples/12-embedded/example.py::delete_fn。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/nolar__kopf-1225/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/nolar__kopf-1225/http/events.jsonl)。

### invenia__TagBotGitLab-17

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：tagbotgitlab/changelog.py::Changelog._collect_data；tagbotgitlab/changelog.py::Changelog._issues；tagbotgitlab/changelog.py::Changelog._merge_requests。
- 图中精确目标节点：3/3；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/test_version.py::test_version_string。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/invenia__TagBotGitLab-17/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/invenia__TagBotGitLab-17/http/events.jsonl)。

### django__daphne-406

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：daphne/http_protocol.py::WebRequest.__init__；daphne/http_protocol.py::WebRequest.process。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：daphne/http_protocol.py::WebRequest.connectionLost。
- 已实际送入CIG候选的显式目标函数：daphne/http_protocol.py::WebRequest.process。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/django__daphne-406/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/django__daphne-406/http/events.jsonl)。

### macbre__sql-metadata-625_interface

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：sql_metadata/nested_resolver.py::NestedResolver._body_sql。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：sql_metadata/table_extractor.py::_collect_node_parts；sql_metadata/table_extractor.py::_ident_str；sql_metadata/table_extractor.py::_bracketed_full_name；sql_metadata/utils.py::UniqueList.append。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/macbre__sql-metadata-625_interface/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/macbre__sql-metadata-625_interface/http/events.jsonl)。

### scoutapp__scout_apm_python-299

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/scout_apm/core/__init__.py::install。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/scout_apm/api/__init__.py::WebTransaction.start；src/scout_apm/api/__init__.py::WebTransaction.__enter__；src/scout_apm/api/__init__.py::Transaction.tag；src/scout_apm/api/__init__.py::Transaction.start。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/scoutapp__scout_apm_python-299/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/scoutapp__scout_apm_python-299/http/events.jsonl)。

### tianocore__edk2-pytool-extensions-608

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：edk2toolext/environment/extdeptypes/web_dependency.py::WebDependency.unpack。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/tianocore__edk2-pytool-extensions-608/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/tianocore__edk2-pytool-extensions-608/http/events.jsonl)。

### Fatal1ty__mashumaro-159

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：mashumaro/jsonschema/schema.py::on_type_with_overridden_serialization。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Fatal1ty__mashumaro-159/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Fatal1ty__mashumaro-159/http/events.jsonl)。

### tensorflow__addons-2467

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：tensorflow_addons/optimizers/novograd.py::NovoGrad._resource_apply_dense；tensorflow_addons/optimizers/novograd.py::NovoGrad._resource_apply_sparse。
- 图中精确目标节点：2/2；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：tensorflow_addons/optimizers/yogi.py::Yogi._resource_apply_dense；tensorflow_addons/optimizers/yogi.py::_solve；tensorflow_addons/optimizers/rectified_adam.py::RectifiedAdam._resource_apply_dense。
- 已实际送入CIG候选的显式目标函数：tensorflow_addons/optimizers/novograd.py::NovoGrad._resource_apply_dense。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/tensorflow__addons-2467/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/tensorflow__addons-2467/http/events.jsonl)。

### pyvista__pyvista-7258

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：pyvista/core/dataobject.py::DataObject.save。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pyvista__pyvista-7258/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pyvista__pyvista-7258/http/events.jsonl)。

### GoogleCloudPlatform__cloud-sql-python-connector-1221

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：google/cloud/sql/connector/connector.py::Connector.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：google/cloud/sql/connector/connector.py::create_async_connector。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/GoogleCloudPlatform__cloud-sql-python-connector-1221/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/GoogleCloudPlatform__cloud-sql-python-connector-1221/http/events.jsonl)。

### RobinL__fuzzymatcher-50

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：fuzzymatcher/data_getter_sqlite.py::DataGetter._tokens_to_matches。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：fuzzymatcher/matcher.py::Matcher._match_processed_data；fuzzymatcher/record.py::RecordToMatch.find_and_score_potential_matches；fuzzymatcher/matcher.py::Matcher.initiate_records；fuzzymatcher/matcher.py::Matcher.match_all；fuzzymatcher/data_getter_sqlite.py::DataGetter.add_data。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/RobinL__fuzzymatcher-50/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/RobinL__fuzzymatcher-50/http/events.jsonl)。

### zalando-stups__senza-278

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：senza/components/elastic_load_balancer.py::component_elastic_load_balancer。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：tests/test_manaus/test_iam.py::test_get_certificates；tests/test_manaus/test_acm.py::test_get_certificates；senza/manaus/iam.py::IAMServerCertificate.get_by_name；senza/manaus/iam.py::IAMServerCertificate.arn_is_server_certificate；senza/manaus/iam.py::IAM.get_certificates。
- 首个目标函数真实排名：7。
- 已实际送入CIG候选的显式目标函数：senza/components/elastic_load_balancer.py::component_elastic_load_balancer。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/zalando-stups__senza-278/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/zalando-stups__senza-278/http/events.jsonl)。

### pybel__pybel-384

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/pybel/parser/parse_concept.py::ConceptParser.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/pybel/dsl/node_classes.py::BaseAbundance.identifier；src/pybel/dsl/namespaces.py::hgnc。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pybel__pybel-384/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pybel__pybel-384/http/events.jsonl)。

### googlefonts__glyphsLib-1060

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：Lib/glyphsLib/builder/glyph.py::to_ufo_glyph。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/googlefonts__glyphsLib-1060/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/googlefonts__glyphsLib-1060/http/events.jsonl)。

### ICB-DCM__pyPESTO-676

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：pypesto/profile/validation_intervals.py::validation_profile_significance。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：pypesto/objective/amici_util.py::add_sim_hess_to_opt_hess；pypesto/objective/amici_calculator.py::calculate_function_values；pypesto/objective/amici_util.py::sim_sres_to_opt_sres；pypesto/objective/amici_util.py::add_sim_grad_to_opt_grad；pypesto/objective/amici_util.py::par_index_slices。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/ICB-DCM__pyPESTO-676/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/ICB-DCM__pyPESTO-676/http/events.jsonl)。

### raullenchai__rapid-mlx-228

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：vllm_mlx/output_router.py::OutputRouter.feed；vllm_mlx/output_router.py::OutputRouter.from_tokenizer。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：vllm_mlx/reasoning/think_parser.py::BaseThinkingReasoningParser.extract_reasoning；vllm_mlx/reasoning/deepseek_r1_parser.py::DeepSeekR1ReasoningParser.finalize_streaming；vllm_mlx/reasoning/deepseek_r1_parser.py::DeepSeekR1ReasoningParser.extract_reasoning；vllm_mlx/reasoning/qwen3_parser.py::Qwen3ReasoningParser.extract_reasoning。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/raullenchai__rapid-mlx-228/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/raullenchai__rapid-mlx-228/http/events.jsonl)。

### fabfuel__circuitbreaker-67

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：circuitbreaker.py::CircuitBreaker.__str__。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：circuitbreaker.py::CircuitBreaker.__init__。
- 已实际送入CIG候选的显式目标函数：circuitbreaker.py::CircuitBreaker.__str__。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/fabfuel__circuitbreaker-67/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/fabfuel__circuitbreaker-67/http/events.jsonl)。

### dstackai__gpuhunt-197

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/gpuhunt/_internal/constraints.py::matches。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/gpuhunt/providers/oci.py::OCIProvider.get；src/gpuhunt/providers/cloudrift.py::generate_instances；src/gpuhunt/providers/oci.py::shape_to_resources。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/dstackai__gpuhunt-197/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/dstackai__gpuhunt-197/http/events.jsonl)。

### meerk40t__svgelements-58

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：svgelements/svgelements.py::CubicBezier.length；svgelements/svgelements.py::Length.str。
- 图中精确目标节点：2/2；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：svgelements/svgelements.py::Path.length；svgelements/svgelements.py::QuadraticBezier.length。
- 已实际送入CIG候选的显式目标函数：svgelements/svgelements.py::CubicBezier.length。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/meerk40t__svgelements-58/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/meerk40t__svgelements-58/http/events.jsonl)。

### nipy__nipype-2597

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：nipype/pipeline/engine/utils.py::generate_expanded_graph。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：nipype/pipeline/engine/nodes.py::JoinNode._override_join_traits；nipype/pipeline/engine/nodes.py::MapNode._create_dynamic_traits；nipype/pipeline/engine/nodes.py::JoinNode._slot_value；nipype/pipeline/engine/nodes.py::Node._copyfiles_to_wd；nipype/pipeline/engine/nodes.py::Node._load_results。
- 已实际送入CIG候选的显式目标函数：nipype/pipeline/engine/utils.py::generate_expanded_graph。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/nipy__nipype-2597/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/nipy__nipype-2597/http/events.jsonl)。

### keras-team__keras-nlp-131

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：keras_nlp/layers/preprocessing/mlm_mask_generator.py::MLMMaskGenerator.call。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/keras-team__keras-nlp-131/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/keras-team__keras-nlp-131/http/events.jsonl)。

### apache__iceberg-python-2797

- 分类：上下文容量限制。执行状态：ContextBudgetExceeded。
- 既有目标函数：pyiceberg/schema.py::_SchemaCompatibilityVisitor.field。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：pyiceberg/schema.py::_SchemaCompatibilityVisitor.field。
- 资源证据：完整候选/代码输入超过冻结上下文容量，未偷偷裁剪、删候选或追加调用救分。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/apache__iceberg-python-2797/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/apache__iceberg-python-2797/http/events.jsonl)。

### sodafoundation__delfin-323

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：delfin/drivers/dell_emc/vmax/client.py::VMAXClient.list_volumes。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/sodafoundation__delfin-323/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/sodafoundation__delfin-323/http/events.jsonl)。

### Duke-GCB__lando-194

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：lando/worker/staging.py::DownloadDukeDSFile.run。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Duke-GCB__lando-194/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Duke-GCB__lando-194/http/events.jsonl)。

### equinor__ert-12275

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/everest/config/simulator_config.py::SimulatorConfig.default_local_queue；src/everest/config/simulator_config.py::SimulatorConfig.validate_max_memory。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/everest/config/control_config.py::ControlConfig.to_ert_parameter_config；src/everest/config/control_config.py::ControlConfig.check_for_autoscale_flag；src/everest/config/control_config.py::ControlConfig.formatted_control_names；src/everest/config/control_config.py::ControlConfig.validate_variables；src/everest/config/control_config.py::ControlConfig.__hash__。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/equinor__ert-12275/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/equinor__ert-12275/http/events.jsonl)。

### asottile__dead-204

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：dead.py::Visitor.visit_ClassDef。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/asottile__dead-204/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/asottile__dead-204/http/events.jsonl)。

### openai__openai-agents-python-2144

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/agents/extensions/models/litellm_model.py::LitellmModel._fetch_response。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/agents/models/openai_provider.py::OpenAIProvider.get_model；src/agents/run.py::AgentRunner._get_model；src/agents/models/multi_provider.py::MultiProvider.get_model；tests/test_config.py::test_set_default_openai_api；tests/test_config.py::test_cc_set_default_openai_key。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/openai__openai-agents-python-2144/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/openai__openai-agents-python-2144/http/events.jsonl)。

### frictionlessdata__frictionless-py-1149

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：frictionless/plugins/pandas/parser.py::PandasParser.write_row_stream。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：frictionless/resource/resource.py::Resource.write；frictionless/resource/resource.py::Resource.to_pandas。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/frictionlessdata__frictionless-py-1149/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/frictionlessdata__frictionless-py-1149/http/events.jsonl)。

### happyleavesaoc__python-snapcast-55

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：snapcast/control/group.py::Snapgroup.friendly_name。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：snapcast/control/client.py::Snapclient.name；snapcast/control/group.py::Snapgroup.name。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/happyleavesaoc__python-snapcast-55/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/happyleavesaoc__python-snapcast-55/http/events.jsonl)。

### RedHatInsights__insights-core-4219

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：insights/combiners/lspci.py::LsPci.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/RedHatInsights__insights-core-4219/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/RedHatInsights__insights-core-4219/http/events.jsonl)。

### pypa__twine-369

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：twine/utils.py::get_config。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：twine/commands/upload.py::upload；twine/package.py::PackageFile.sign；twine/settings.py::Settings._handle_repository_options；twine/repository.py::Repository.set_client_certificate；twine/settings.py::Settings.create_repository。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pypa__twine-369/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pypa__twine-369/http/events.jsonl)。

### cool-RR__PySnooper-147

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：pysnooper/tracer.py::Tracer.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：pysnooper/utils.py::get_shortish_repr；pysnooper/utils.py::get_repr_function；pysnooper/tracer.py::get_local_reprs；pysnooper/tracer.py::Tracer.trace。
- 已实际送入CIG候选的显式目标函数：pysnooper/tracer.py::Tracer.__init__。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/cool-RR__PySnooper-147/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/cool-RR__PySnooper-147/http/events.jsonl)。

### DiCarloLab-Delft__PycQED_py3-651

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：pycqed/instrument_drivers/physical_instruments/ZurichInstruments/UHFQuantumController.py::UHFQC._add_extra_parameters。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：pycqed/instrument_drivers/pq_parameters.py::InstrumentParameter.get_instr。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/DiCarloLab-Delft__PycQED_py3-651/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/DiCarloLab-Delft__PycQED_py3-651/http/events.jsonl)。

### radiasoft__pykern-228

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：pykern/pkio.py::read_text；pykern/pkio.py::write_text。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/radiasoft__pykern-228/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/radiasoft__pykern-228/http/events.jsonl)。

### python-pillow__Pillow-6819

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/PIL/PngImagePlugin.py::_save。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/PIL/Image.py::Image.save；src/PIL/Image.py::Image._repr_png_；src/PIL/Image.py::Image._dump；src/PIL/Image.py::preinit。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/python-pillow__Pillow-6819/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/python-pillow__Pillow-6819/http/events.jsonl)。

### keras-team__keras-22138

- 分类：上下文容量限制。执行状态：ContextBudgetExceeded。
- 既有目标函数：keras/src/ops/nn.py::depth_to_space；keras/src/ops/nn.py::space_to_depth。
- 图中精确目标节点：2/2；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：2；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：keras/src/ops/nn.py::depth_to_space；keras/src/ops/nn.py::space_to_depth。
- 资源证据：完整候选/代码输入超过冻结上下文容量，未偷偷裁剪、删候选或追加调用救分。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/keras-team__keras-22138/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/keras-team__keras-22138/http/events.jsonl)。

### oxan__djangorestframework-dataclasses-84

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：rest_framework_dataclasses/serializers.py::DataclassSerializer.to_internal_value。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：rest_framework_dataclasses/serializers.py::DataclassSerializer.build_composite_field；rest_framework_dataclasses/serializers.py::DataclassSerializer.create。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/oxan__djangorestframework-dataclasses-84/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/oxan__djangorestframework-dataclasses-84/http/events.jsonl)。

### kootenpv__access_points-22

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：access_points/__init__.py::OSXWifiScanner.parse_output。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：access_points/__init__.py::WifiScanner.call_subprocess；access_points/__init__.py::WifiScanner.get_access_points；access_points/__init__.py::NetworkManagerWifiScanner.parse_output。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/kootenpv__access_points-22/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/kootenpv__access_points-22/http/events.jsonl)。

### googleapis__python-pubsub-1318

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：google/cloud/pubsub_v1/publisher/_batch/thread.py::Batch._commit。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：google/cloud/pubsub_v1/publisher/_batch/thread.py::Batch._commit。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/googleapis__python-pubsub-1318/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/googleapis__python-pubsub-1318/http/events.jsonl)。

### sphinx-gallery__sphinx-gallery-480

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：sphinx_gallery/gen_rst.py::rst_blocks。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/sphinx-gallery__sphinx-gallery-480/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/sphinx-gallery__sphinx-gallery-480/http/events.jsonl)。

### getsentry__responses-736

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：responses/__init__.py::RequestsMock._on_request。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：responses/tests/test_responses.py::TestShortcuts.test_patch.run；responses/tests/test_matchers.py::test_body_match_post；responses/tests/test_responses.py::TestShortcuts.test_options.run；responses/tests/test_responses.py::test_auto_calculate_content_length_doesnt_work_for_buffered_reader_body；responses/tests/test_responses.py::TestShortcuts.test_post。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/getsentry__responses-736/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/getsentry__responses-736/http/events.jsonl)。

### Lucas-C__pre-commit-hooks-98

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：pre_commit_hooks/insert_license.py::try_update_year_range。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：pre_commit_hooks/insert_license.py::try_update_year_range。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Lucas-C__pre-commit-hooks-98/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Lucas-C__pre-commit-hooks-98/http/events.jsonl)。

### SpikeInterface__spikeinterface-3934

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：src/spikeinterface/preprocessing/motion.py::compute_motion；src/spikeinterface/preprocessing/motion.py::correct_motion。
- 图中精确目标节点：2/2；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：src/spikeinterface/preprocessing/motion.py::correct_motion。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/SpikeInterface__spikeinterface-3934/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/SpikeInterface__spikeinterface-3934/http/events.jsonl)。

### darosior__python-bip32-10

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：bip32/bip32.py::BIP32.get_extended_pubkey_from_path；bip32/bip32.py::BIP32.get_pubkey_from_path。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：bip32/utils.py::_hardened_index_in_path；bip32/utils.py::_deriv_path_str_to_list；bip32/utils.py::_privkey_to_pubkey。
- 已实际送入CIG候选的显式目标函数：bip32/bip32.py::BIP32.get_extended_pubkey_from_path。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/darosior__python-bip32-10/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/darosior__python-bip32-10/http/events.jsonl)。

### zulip__zulip-terminal-928

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：zulipterminal/ui_tools/boxes.py::WriteBox.autocomplete_users。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：zulipterminal/helper.py::notify；zulipterminal/model.py::Model.notify_user。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/zulip__zulip-terminal-928/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/zulip__zulip-terminal-928/http/events.jsonl)。

### encode__httpx-1002

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：httpx/_client.py::BaseClient.redirect_url。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/models/test_url.py::test_origin_from_url_string；httpx/_models.py::URL.port；httpx/_models.py::URL.scheme；tests/models/test_url.py::test_idna_url；tests/models/test_url.py::test_url。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/encode__httpx-1002/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/encode__httpx-1002/http/events.jsonl)。

### scikit-rf__scikit-rf-1256

- 分类：上下文容量限制。执行状态：ContextBudgetExceeded。
- 既有目标函数：skrf/network.py::Network.plot_attribute。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：skrf/network.py::Network.plot_attribute。
- 资源证据：完整候选/代码输入超过冻结上下文容量，未偷偷裁剪、删候选或追加调用救分。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/scikit-rf__scikit-rf-1256/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/scikit-rf__scikit-rf-1256/http/events.jsonl)。

### IAMconsortium__nomenclature-456

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：nomenclature/codelist.py::CodeList.check_illegal_characters；nomenclature/codelist.py::CodeList.check_illegal_characters._check_string。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：2；最终CIG绑定：0。
- 最终函数Top-5：nomenclature/cli.py::cli_validate_scenarios；nomenclature/definition.py::DataStructureDefinition.validate；nomenclature/error.py::log_error；nomenclature/codelist.py::CodeList.validate_data；nomenclature/codelist.py::CodeList.validate_items。
- 已实际送入CIG候选的显式目标函数：nomenclature/codelist.py::CodeList.check_illegal_characters；nomenclature/codelist.py::CodeList.check_illegal_characters._check_string。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/IAMconsortium__nomenclature-456/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/IAMconsortium__nomenclature-456/http/events.jsonl)。

### home-assistant__core-134506

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：homeassistant/components/backup/manager.py::CoreBackupReaderWriter.async_receive_backup。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/home-assistant__core-134506/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/home-assistant__core-134506/http/events.jsonl)。

### dask__dask-12096

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：dask/dataframe/dask_expr/_concat.py::Concat._meta。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：dask/bag/tests/test_bag.py::test_concat_after_map；dask/bag/core.py::concat；dask/delayed.py::Delayed.__dask_keys__；dask/bag/core.py::Item.__dask_keys__；dask/bag/core.py::Bag.__dask_keys__。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/dask__dask-12096/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/dask__dask-12096/http/events.jsonl)。

### iterative__shtab-36

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：shtab/__init__.py::complete_bash。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/test_shtab.py::test_custom_complete；tests/test_shtab.py::test_prog_scripts；tests/test_shtab.py::test_prefix_override；tests/test_shtab.py::test_bash_compgen；tests/test_shtab.py::test_positional_choices。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/iterative__shtab-36/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/iterative__shtab-36/http/events.jsonl)。

### ultraplot__ultraplot-696

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：ultraplot/figure.py::Figure._effective_share_level。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：ultraplot/tests/test_legend.py::test_geo_legend_helper_with_axes_legend；ultraplot/tests/test_legend.py::test_legend_best_axis_fallback_empty_iterable_ref.LegendProxy.legend；ultraplot/tests/test_legend.py::test_external_mode_toggle_enables_auto；ultraplot/axes/base.py::Axes.legend；ultraplot/axes/base.py::Axes._update_guide。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/ultraplot__ultraplot-696/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/ultraplot__ultraplot-696/http/events.jsonl)。

### sqlfluff__sqlfluff-5317

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：src/sqlfluff/core/templaters/jinja.py::JinjaTemplater._extract_macros_from_config；src/sqlfluff/core/templaters/jinja.py::JinjaTemplater._extract_macros_from_template。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：2；最终CIG绑定：0。
- 最终函数Top-5：test/core/templaters/jinja_test.py::test__templater_jinja；src/sqlfluff/core/templaters/jinja.py::JinjaTemplater.process。
- 已实际送入CIG候选的显式目标函数：src/sqlfluff/core/templaters/jinja.py::JinjaTemplater._extract_macros_from_config；src/sqlfluff/core/templaters/jinja.py::JinjaTemplater._extract_macros_from_template。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/sqlfluff__sqlfluff-5317/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/sqlfluff__sqlfluff-5317/http/events.jsonl)。

### tefra__xsdata-687

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：xsdata/formats/dataclass/serializers/xml.py::XmlSerializer.write_tokens。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：xsdata/formats/dataclass/serializers/xml.py::XmlSerializer.write_list；xsdata/formats/dataclass/serializers/xml.py::XmlSerializer.write_value；xsdata/formats/dataclass/serializers/xml.py::XmlSerializer.write_elements；xsdata/utils/collections.py::is_array；xsdata/formats/dataclass/serializers/xml.py::XmlSerializer.write_choice。
- 已实际送入CIG候选的显式目标函数：xsdata/formats/dataclass/serializers/xml.py::XmlSerializer.write_tokens。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/tefra__xsdata-687/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/tefra__xsdata-687/http/events.jsonl)。

### google__adk-python-3088

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/google/adk/tools/_function_parameter_parse_util.py::_parse_schema_from_parameter；src/google/adk/tools/_function_parameter_parse_util.py::_raise_if_schema_unsupported。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/unittests/tools/test_base_toolset.py::test_prefixed_tools_in_llm_request；src/google/adk/tools/base_tool.py::BaseTool.process_llm_request；src/google/adk/tools/load_artifacts_tool.py::LoadArtifactsTool.process_llm_request；src/google/adk/tools/base_tool.py::BaseTool._get_declaration；src/google/adk/tools/load_artifacts_tool.py::LoadArtifactsTool._append_artifacts_to_llm_request。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/google__adk-python-3088/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/google__adk-python-3088/http/events.jsonl)。

### mozilla__django-csp-236

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：csp/contrib/rate_limiting.py::RateLimitedCSPMiddleware.build_policy；csp/contrib/rate_limiting.py::RateLimitedCSPMiddleware.build_policy_ro。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/mozilla__django-csp-236/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/mozilla__django-csp-236/http/events.jsonl)。

### Lightning-AI__litdata-499

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：src/litdata/streaming/reader.py::_get_folder_size。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：src/litdata/streaming/reader.py::_get_folder_size。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Lightning-AI__litdata-499/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Lightning-AI__litdata-499/http/events.jsonl)。

### cal-itp__benefits-3198

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：benefits/core/admin/transit.py::TransitAgencyAdmin.get_exclude；benefits/core/admin/transit.py::TransitAgencyAdmin.get_readonly_fields。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：2；最终CIG绑定：2。
- 最终函数Top-5：benefits/core/models/transit.py::TransitAgency.switchio_config；benefits/core/models/transit.py::TransitAgency.littlepay_config；benefits/core/models/transit.py::TransitAgency.clean；benefits/core/models/transit.py::TransitAgency.in_person_enrollment_index_route；benefits/core/models/transit.py::TransitAgency.enrollment_index_route。
- 首个目标函数真实排名：6。
- 已实际送入CIG候选的显式目标函数：benefits/core/admin/transit.py::TransitAgencyAdmin.get_exclude；benefits/core/admin/transit.py::TransitAgencyAdmin.get_readonly_fields。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/cal-itp__benefits-3198/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/cal-itp__benefits-3198/http/events.jsonl)。

### mesonbuild__meson-14291

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：mesonbuild/options.py::OptionStore.get_value_object_for。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/mesonbuild__meson-14291/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/mesonbuild__meson-14291/http/events.jsonl)。

### automl__DEHB-57

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：src/dehb/optimizers/de.py::DEBase.configspace_to_vector；src/dehb/optimizers/de.py::DEBase.vector_to_configspace。
- 图中精确目标节点：2/2；原检索显式候选中目标：2；保留后：2；种子：2；CIG实际候选：2；最终CIG绑定：1。
- 最终函数Top-5：src/dehb/optimizers/dehb.py::DEHB.vector_to_configspace；src/dehb/optimizers/dehb.py::DEHB._save_incumbent；src/dehb/optimizers/dehb.py::DEHB._get_next_job；src/dehb/optimizers/dehb.py::DEHB.run；src/dehb/optimizers/dehb.py::DEHB.submit_job。
- 首个目标函数真实排名：6。
- 已实际送入CIG候选的显式目标函数：src/dehb/optimizers/de.py::DEBase.configspace_to_vector；src/dehb/optimizers/de.py::DEBase.vector_to_configspace。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/automl__DEHB-57/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/automl__DEHB-57/http/events.jsonl)。

### nose-devs__nose2-370

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：nose2/plugins/layers.py::LayerReporter.describeTest。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/nose-devs__nose2-370/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/nose-devs__nose2-370/http/events.jsonl)。

### DCC-Lab__RayTracing-192

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：raytracing/imagingpath.py::ImagingPath.chiefRay。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：raytracing/tests/testsLagrangeInvariant.py::TestLagrange.testLagrangeImagingPathNoFieldStop；raytracing/imagingpath.py::ImagingPath.lagrangeInvariant；raytracing/tests/testsLagrangeInvariant.py::TestLagrange.testLagrangeInvariantOpticalPath；raytracing/imagingpath.py::ImagingPath.apertureStop；raytracing/imagingpath.py::ImagingPath.fieldStop。
- 首个目标函数真实排名：7。
- 已实际送入CIG候选的显式目标函数：raytracing/imagingpath.py::ImagingPath.chiefRay。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/DCC-Lab__RayTracing-192/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/DCC-Lab__RayTracing-192/http/events.jsonl)。

### careamics__careamics-688

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/careamics/dataset_ng/image_stack/czi_image_stack.py::CziImageStack.extract_channel_patch。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/careamics/lvae_training/dataset/multich_dataset.py::MultiChDloader._crop_img_with_padding；src/careamics/lvae_training/dataset/multich_dataset.py::MultiChDloader._crop_img；src/careamics/lvae_training/dataset/multich_dataset.py::MultiChDloader.get_begin_end_padding；src/careamics/dataset_ng/image_stack/zarr_image_stack.py::ZarrImageStack.extract_patch。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/careamics__careamics-688/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/careamics__careamics-688/http/events.jsonl)。

### iris-hep__func_adl-185

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：func_adl/type_based_replacement.py::_fill_in_default_arguments。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/iris-hep__func_adl-185/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/iris-hep__func_adl-185/http/events.jsonl)。

### iterative__datachain-206

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：src/datachain/lib/dc.py::DataChain.limit。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：src/datachain/lib/dc.py::DataChain.select；src/datachain/cli.py::show；src/datachain/cli.py::query；tests/unit/lib/test_datachain.py::test_from_csv_tab_delimited；tests/unit/lib/test_datachain.py::test_pandas_conversion。
- 首个目标函数真实排名：12。
- 已实际送入CIG候选的显式目标函数：src/datachain/lib/dc.py::DataChain.limit。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/iterative__datachain-206/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/iterative__datachain-206/http/events.jsonl)。

### zarr-developers__zarr-python-2629

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：src/zarr/api/asynchronous.py::open。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：src/zarr/core/array.py::AsyncArray.chunks；src/zarr/api/synchronous.py::create；src/zarr/core/array.py::AsyncArray.dtype；src/zarr/core/array.py::create_array；src/zarr/core/group.py::Group.create。
- 已实际送入CIG候选的显式目标函数：src/zarr/api/asynchronous.py::open。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/zarr-developers__zarr-python-2629/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/zarr-developers__zarr-python-2629/http/events.jsonl)。

### duo-labs__py_webauthn-120

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：webauthn/helpers/structs.py::BytesLike.validate。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/test_bytes_subclass_support.py::CustomBytes.__new__；webauthn/helpers/parse_client_data_json.py::parse_client_data_json；webauthn/authentication/verify_authentication_response.py::verify_authentication_response；tests/test_bytes_subclass_support.py::TestWebAuthnBytesSubclassSupport.test_handles_bytes_subclasses；webauthn/helpers/bytes_to_base64url.py::bytes_to_base64url。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/duo-labs__py_webauthn-120/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/duo-labs__py_webauthn-120/http/events.jsonl)。

### somm15__PyViCare-132

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：PyViCare/PyViCareService.py::ViCareService.setProperty。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/somm15__PyViCare-132/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/somm15__PyViCare-132/http/events.jsonl)。

### sktime__sktime-8937

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：sktime/benchmarking/benchmarks.py::BaseBenchmark._run；sktime/benchmarking/benchmarks.py::BaseBenchmark.run；sktime/benchmarking/benchmarks.py::_BenchmarkingResults.__post_init__；sktime/benchmarking/benchmarks.py::_BenchmarkingResults.save。
- 图中精确目标节点：4/4；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：sktime/benchmarking/forecasting.py::ForecastingBenchmark.add_task；sktime/benchmarking/forecasting.py::ForecastingBenchmark._run_validation。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/sktime__sktime-8937/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/sktime__sktime-8937/http/events.jsonl)。

### reframe-hpc__reframe-3553

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：reframe/core/pipeline.py::RegressionTest._setup_paths。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：unittests/test_pipeline.py::test_sourcesdir_build_system；unittests/resources/checks/hellocheck.py::HelloTest.validate；unittests/test_ci.py::test_ci_gitlab_pipeline；reframe/frontend/loader.py::RegressionCheckLoader.load_all；reframe/frontend/ci.py::emit_pipeline。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/reframe-hpc__reframe-3553/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/reframe-hpc__reframe-3553/http/events.jsonl)。

### cloud-custodian__cloud-custodian-5715

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：c7n/resources/cloudtrail.py::Status.process。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：c7n/filters/core.py::ValueFilter.match；c7n/filters/core.py::ValueFilter.get_resource_value。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/cloud-custodian__cloud-custodian-5715/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/cloud-custodian__cloud-custodian-5715/http/events.jsonl)。

### spdx__tools-python-855

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/spdx_tools/spdx/parser/json/json_parser.py::parse_from_file。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/spdx__tools-python-855/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/spdx__tools-python-855/http/events.jsonl)。

### kofferdahl__bme590hrm-34

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：HRM_Processor.py::HRM_Processor.write_outputs_to_dict。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：DataReader.py::DataReader.validate_duration。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/kofferdahl__bme590hrm-34/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/kofferdahl__bme590hrm-34/http/events.jsonl)。

### tox-dev__sphinx-autodoc-typehints-607

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/sphinx_autodoc_typehints/__init__.py::process_docstring；src/sphinx_autodoc_typehints/__init__.py::process_signature。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/tox-dev__sphinx-autodoc-typehints-607/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/tox-dev__sphinx-autodoc-typehints-607/http/events.jsonl)。

### level12__keg-elements-71

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：keg_elements/forms/validators.py::ValidateUnique.__call__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：keg_elements/tests/test_forms/test_validators.py::Form.get_object_by_field。
- 已实际送入CIG候选的显式目标函数：keg_elements/forms/validators.py::ValidateUnique.__call__。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/level12__keg-elements-71/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/level12__keg-elements-71/http/events.jsonl)。

### statsmodels__statsmodels-9468

- 分类：上下文容量限制。执行状态：ContextBudgetExceeded。
- 既有目标函数：statsmodels/tsa/vector_ar/svar_model.py::SVAR.__init__；statsmodels/tsa/vector_ar/svar_model.py::SVAR._solve_AB；statsmodels/tsa/vector_ar/svar_model.py::SVAR.hessian；statsmodels/tsa/vector_ar/svar_model.py::SVAR.score。
- 图中精确目标节点：4/4；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 资源证据：完整候选/代码输入超过冻结上下文容量，未偷偷裁剪、删候选或追加调用救分。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/statsmodels__statsmodels-9468/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/statsmodels__statsmodels-9468/http/events.jsonl)。

### mozilla__bleach-721

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：bleach/html5lib_shim.py::BleachHTMLTokenizer.__iter__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：bleach/_vendor/html5lib/_tokenizer.py::HTMLTokenizer.consumeEntity；bleach/_vendor/html5lib/_tokenizer.py::HTMLTokenizer.entityDataState；bleach/_vendor/html5lib/_tokenizer.py::HTMLTokenizer.attributeValueUnQuotedState；bleach/_vendor/html5lib/_tokenizer.py::HTMLTokenizer.processEntityInAttribute；bleach/_vendor/html5lib/_tokenizer.py::HTMLTokenizer.attributeValueDoubleQuotedState。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/mozilla__bleach-721/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/mozilla__bleach-721/http/events.jsonl)。

### graphql-python__graphene-django-842

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：graphene_django/types.py::construct_fields。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：graphene_django/types.py::construct_fields。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/graphql-python__graphene-django-842/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/graphql-python__graphene-django-842/http/events.jsonl)。

### numpy__numpydoc-500

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：numpydoc/validate.py::Validator.source_file_def_line；numpydoc/validate.py::Validator.source_file_name。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/numpy__numpydoc-500/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/numpy__numpydoc-500/http/events.jsonl)。

### oasis-open__cti-python-stix2-348

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：stix2/base.py::_Observable._generate_id；stix2/base.py::_recursive_stix_to_dict。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/oasis-open__cti-python-stix2-348/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/oasis-open__cti-python-stix2-348/http/events.jsonl)。

### conan-io__conan-19750

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：conan/internal/api/profile/profile_loader.py::_ProfileValueParser.get_profile。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：conan/internal/graph/graph_builder.py::DepsGraphBuilder._create_new_node；conan/internal/graph/graph.py::Node.propagate_downstream；conan/internal/graph/graph.py::Node.propagate_closing_loop。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/conan-io__conan-19750/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/conan-io__conan-19750/http/events.jsonl)。

### Duke-GCB__DukeDSClient-283

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：ddsc/core/download.py::ProjectDownload.get_files_to_download；ddsc/core/download.py::ProjectDownload.run。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：ddsc/core/download.py::FileHashStatus.raise_for_status；ddsc/core/download.py::FileHashStatus.get_status_line；ddsc/core/tests/test_download.py::TestFileHashStatus.test_raise_for_status；ddsc/sdk/client.py::File.download_to_path。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Duke-GCB__DukeDSClient-283/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Duke-GCB__DukeDSClient-283/http/events.jsonl)。

### pybamm-team__PyBaMM-602

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：pybamm/expression_tree/independent_variable.py::SpatialVariable.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：pybamm/expression_tree/concatenations.py::Concatenation.__init__；pybamm/expression_tree/concatenations.py::Concatenation.get_children_domains。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pybamm-team__PyBaMM-602/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pybamm-team__PyBaMM-602/http/events.jsonl)。

### holoviz__holoviews-6783

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：holoviews/operation/element.py::interpolate_curve._get_dtype。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：holoviews/element/__init__.py::ElementConversion.curve；holoviews/operation/element.py::interpolate_curve.pts_to_poststep。
- 已实际送入CIG候选的显式目标函数：holoviews/operation/element.py::interpolate_curve._get_dtype。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/holoviz__holoviews-6783/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/holoviz__holoviews-6783/http/events.jsonl)。

### materialsproject__custodian-379

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/custodian/utils.py::backup。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/custodian/custodian.py::Custodian._load_checkpoint。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/materialsproject__custodian-379/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/materialsproject__custodian-379/http/events.jsonl)。

### mwouts__jupytext-1175

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/jupytext/cell_reader.py::DoublePercentScriptCellReader.find_cell_end；src/jupytext/cell_reader.py::MarkdownCellReader.find_cell_end。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/jupytext/formats.py::format_name_for_ext；src/jupytext/jupytext.py::reads；tests/functional/simple_notebooks/test_ipynb_to_myst.py::test_matches_mystnb。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/mwouts__jupytext-1175/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/mwouts__jupytext-1175/http/events.jsonl)。

### altair-viz__altair-2874

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：altair/vegalite/v5/api.py::_check_if_can_be_layered。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：altair/vegalite/v5/api.py::TopLevelMixin.__add__；altair/vegalite/v5/api.py::layer；altair/vegalite/v5/api.py::TopLevelMixin.__or__；altair/vegalite/v5/api.py::TopLevelMixin.to_html；altair/vegalite/v5/api.py::_remove_duplicate_params。
- 首个目标函数真实排名：9。
- 已实际送入CIG候选的显式目标函数：altair/vegalite/v5/api.py::_check_if_can_be_layered。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/altair-viz__altair-2874/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/altair-viz__altair-2874/http/events.jsonl)。

### zwicker-group__py-pde-683

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：pde/trackers/base.py::TrackerBase.initialize。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：pde/solvers/controller.py::Controller.run；pde/solvers/controller.py::Controller.__init__；tests/pdes/test_pdes_mpi.py::test_pde_complex_mpi；pde/pdes/base.py::PDEBase.solve。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/zwicker-group__py-pde-683/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/zwicker-group__py-pde-683/http/events.jsonl)。

### geopandas__geopandas-1566

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：geopandas/tools/clip.py::_clip_line_poly。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：geopandas/array.py::_check_crs；geopandas/tools/clip.py::clip；geopandas/array.py::GeometryArray.bounds；geopandas/tests/test_crs.py::TestGeometryArrayCRS.test_rename；geopandas/array.py::_crs_mismatch_warn。
- 已实际送入CIG候选的显式目标函数：geopandas/tools/clip.py::_clip_line_poly。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/geopandas__geopandas-1566/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/geopandas__geopandas-1566/http/events.jsonl)。

### beever-ai__beever-atlas-102

- 分类：上下文容量限制。执行状态：ContextBudgetExceeded。
- 既有目标函数：src/beever_atlas/agents/ingestion/preprocessor.py::_resolve_cross_batch_parent。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：src/beever_atlas/agents/ingestion/preprocessor.py::_resolve_cross_batch_parent。
- 资源证据：完整候选/代码输入超过冻结上下文容量，未偷偷裁剪、删候选或追加调用救分。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/beever-ai__beever-atlas-102/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/beever-ai__beever-atlas-102/http/events.jsonl)。

### canonical__charmcraft-866

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：charmcraft/reactive_plugin.py::ReactivePluginEnvironmentValidator.validate_environment。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：charmcraft/version.py::_get_version。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/canonical__charmcraft-866/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/canonical__charmcraft-866/http/events.jsonl)。

### psd-tools__psd-tools-551

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/psd_tools/psd/bin_utils.py::read_unicode_string；src/psd_tools/psd/bin_utils.py::write_unicode_string。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/psd_tools/api/layers.py::TypeLayer.text；src/psd_tools/api/psd_image.py::PSDImage.open；src/psd_tools/api/smart_object.py::SmartObject.open。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/psd-tools__psd-tools-551/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/psd-tools__psd-tools-551/http/events.jsonl)。

### WPI-MMR__gym_solo-12

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：gym_solo/core/rewards.py::RewardFactory.get_reward。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：gym_solo/envs/test_solo8v2vanilla.py::SimpleReward.compute。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/WPI-MMR__gym_solo-12/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/WPI-MMR__gym_solo-12/http/events.jsonl)。

### mmornati__home-assistant-csnet-home-132

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：custom_components/csnet_home/api.py::CSNetHomeAPI.get_temperature_limits。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：tests/test_api.py::test_get_temperature_limits_zone5_heating；tests/test_api.py::test_get_temperature_limits_zone6_cooling；tests/test_api.py::test_get_temperature_limits_zone3_dhw；tests/test_api.py::test_get_temperature_limits_no_heating_status；tests/test_api.py::test_get_temperature_limits_zone2_cooling。
- 首个目标函数真实排名：13。
- 已实际送入CIG候选的显式目标函数：custom_components/csnet_home/api.py::CSNetHomeAPI.get_temperature_limits。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/mmornati__home-assistant-csnet-home-132/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/mmornati__home-assistant-csnet-home-132/http/events.jsonl)。

### jlowin__fastmcp-1425

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/fastmcp/experimental/utilities/openapi/schemas.py::_combine_schemas_and_map_params。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/fastmcp/utilities/openapi.py::generate_example_from_schema；src/fastmcp/utilities/openapi.py::format_description_with_responses；src/fastmcp/server/openapi.py::FastMCPOpenAPI._create_openapi_tool；src/fastmcp/server/openapi.py::FastMCPOpenAPI._create_openapi_template；src/fastmcp/server/openapi.py::FastMCPOpenAPI._create_openapi_resource。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/jlowin__fastmcp-1425/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/jlowin__fastmcp-1425/http/events.jsonl)。

### marimo-team__marimo-8387_interface

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：marimo/_data/get_datasets.py::_get_databases_from_duckdb_internal。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/marimo-team__marimo-8387_interface/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/marimo-team__marimo-8387_interface/http/events.jsonl)。

### juju__python-libjuju-497

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：juju/bundle.py::AddCharmChange.run。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：juju/client/_client3.py::ClientFacade.AddCharm。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/juju__python-libjuju-497/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/juju__python-libjuju-497/http/events.jsonl)。

### hgrecco__pint-877

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：pint/util.py::ParserHelper.__eq__；pint/util.py::UnitsContainer.__eq__。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：pint/registry.py::BaseRegistry.get_dimensionality；pint/registry.py::BaseRegistry._get_dimensionality；pint/registry.py::BaseRegistry._convert；pint/registry.py::BaseRegistry._get_dimensionality_ratio；pint/util.py::to_units_container。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/hgrecco__pint-877/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/hgrecco__pint-877/http/events.jsonl)。

### spack__spack-51723

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：lib/spack/spack/util/git.py::extract_git_version_str。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：lib/spack/spack/util/git.py::get_commit_sha。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/spack__spack-51723/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/spack__spack-51723/http/events.jsonl)。

### sciunto-org__python-bibtexparser-213

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：bibtexparser/bibtexexpression.py::BibtexExpression.__init__；bibtexparser/bibtexexpression.py::field_to_pair；bibtexparser/bibtexexpression.py::first_token；bibtexparser/bibtexexpression.py::remove_braces；bibtexparser/bibtexexpression.py::remove_trailing_newlines。
- 图中精确目标节点：5/5；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/sciunto-org__python-bibtexparser-213/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/sciunto-org__python-bibtexparser-213/http/events.jsonl)。

### skypilot-org__skypilot-4022

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：sky/resources.py::Resources._try_validate_labels。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/test_yaml_parser.py::test_empty_fields_resources；tests/test_yaml_parser.py::test_empty_fields_storage；sky/backends/cloud_vm_ray_backend.py::RayCodeGen.add_ray_task。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/skypilot-org__skypilot-4022/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/skypilot-org__skypilot-4022/http/events.jsonl)。

### serge-sans-paille__beniget-78

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：beniget/beniget.py::DefUseChains.extend_global。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/serge-sans-paille__beniget-78/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/serge-sans-paille__beniget-78/http/events.jsonl)。

### ipython__ipyparallel-465

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：ipyparallel/serialize/canning.py::CannedFunction.__init__；ipyparallel/serialize/canning.py::CannedFunction.get_object。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：ipyparallel/serialize/serialize.py::pack_apply_message；ipyparallel/serialize/serialize.py::serialize_object。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/ipython__ipyparallel-465/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/ipython__ipyparallel-465/http/events.jsonl)。

### SciTools__iris-6754

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：lib/iris/fileformats/netcdf/loader.py::_translate_constraints_to_var_callback；lib/iris/fileformats/netcdf/loader.py::_translate_constraints_to_var_callback.inner。
- 图中精确目标节点：1/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：lib/iris/fileformats/netcdf/loader.py::load_cubes；lib/iris/fileformats/pp.py::_load_cubes_variable_loader；lib/iris/cube.py::CubeList.concatenate；lib/iris/fileformats/pp_load_rules.py::convert；lib/iris/fileformats/um/_fast_load.py::_combine_structured_cubes。
- 已实际送入CIG候选的显式目标函数：lib/iris/fileformats/netcdf/loader.py::_translate_constraints_to_var_callback。
- 无精确图函数节点/待核身份：lib/iris/fileformats/netcdf/loader.py::_translate_constraints_to_var_callback.inner [NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET]。外层代码正文仍可能含其源码。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/SciTools__iris-6754/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/SciTools__iris-6754/http/events.jsonl)。

### lundberg__respx-260

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：respx/patterns.py::Files._normalize_file_value。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：respx/router.py::Router.patch；respx/api.py::patch。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/lundberg__respx-260/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/lundberg__respx-260/http/events.jsonl)。

### SAP__python-pyodata-264

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：pyodata/v2/service.py::EntityProxy.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/test_service_v2.py::test_navigation_from_entity；pyodata/v2/service.py::ODataHttpRequest.execute；tests/test_service_v2.py::test_total_count_exception；pyodata/v2/service.py::EntitySetProxy.get_entities；tests/test_service_v2.py::test_inlinecount。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/SAP__python-pyodata-264/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/SAP__python-pyodata-264/http/events.jsonl)。

### Davidyz__VectorCode-27

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/vectorcode/chunking.py::TreeSitterChunker.chunk。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Davidyz__VectorCode-27/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Davidyz__VectorCode-27/http/events.jsonl)。

### hynek__structlog-221

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/structlog/dev.py::ConsoleRenderer.__call__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/test_processors.py::TestKeyValueRenderer.test_random_order。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/hynek__structlog-221/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/hynek__structlog-221/http/events.jsonl)。

### gotcha__ipdb-224

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：ipdb/__main__.py::_init_pdb。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：ipdb/__main__.py::post_mortem；ipdb/__main__.py::launch_ipdb_on_exception；ipdb/stdout.py::spost_mortem；ipdb/__main__.py::run；ipdb/__main__.py::pm。
- 首个目标函数真实排名：12。
- 观察到False的目标函数：ipdb/__main__.py::_init_pdb（并不表示该目标在所有调用中始终被剔除）。
- 已实际送入CIG候选的显式目标函数：ipdb/__main__.py::_init_pdb。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/gotcha__ipdb-224/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/gotcha__ipdb-224/http/events.jsonl)。

### getsentry__sentry-python-4179

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：sentry_sdk/tracing_utils.py::_generate_sample_rand。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：sentry_sdk/tracing.py::Transaction.__init__；sentry_sdk/integrations/starlette.py::patch_exception_middleware；sentry_sdk/utils.py::Auth.__init__；sentry_sdk/integrations/asgi.py::SentryAsgiMiddleware.__init__；sentry_sdk/integrations/_wsgi_common.py::HttpCodeRangeContainer.__init__。
- 已实际送入CIG候选的显式目标函数：sentry_sdk/tracing_utils.py::_generate_sample_rand。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/getsentry__sentry-python-4179/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/getsentry__sentry-python-4179/http/events.jsonl)。

### networkx__networkx-7636

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：networkx/algorithms/distance_measures.py::harmonic_diameter。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：networkx/algorithms/tests/test_distance_measures.py::TestDistance.test_harmonic_diameter_not_strongly_connected；networkx/algorithms/tests/test_distance_measures.py::TestDistance.test_harmonic_diameter_discrete；networkx/algorithms/tests/test_distance_measures.py::TestDistance.test_harmonic_diameter_single_node；networkx/algorithms/tests/test_distance_measures.py::TestDistance.test_harmonic_diameter_empty；networkx/algorithms/tests/test_distance_measures.py::TestDistance.test_harmonic_diameter。
- 首个目标函数真实排名：6。
- 已实际送入CIG候选的显式目标函数：networkx/algorithms/distance_measures.py::harmonic_diameter。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/networkx__networkx-7636/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/networkx__networkx-7636/http/events.jsonl)。

### kblin__ncbi-genome-download-106

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：ncbi_genome_download/core.py::config_download；ncbi_genome_download/core.py::download_file_job。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/kblin__ncbi-genome-download-106/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/kblin__ncbi-genome-download-106/http/events.jsonl)。

### showyourwork__showyourwork-456

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/showyourwork/cli/commands/clean.py::clean。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/showyourwork__showyourwork-456/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/showyourwork__showyourwork-456/http/events.jsonl)。

### bids-standard__pybids-1087

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：bids/layout/index.py::BIDSLayoutIndexer._index_dir；bids/layout/index.py::BIDSLayoutIndexer._index_metadata。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：bids/layout/validation.py::validate_root；bids/layout/layout.py::BIDSLayout.__init__；bids/layout/layout.py::BIDSLayout.parse_file_entities；bids/layout/layout.py::BIDSLayout._get_layouts_in_scope；bids/layout/layout.py::BIDSLayout.build_path。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/bids-standard__pybids-1087/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/bids-standard__pybids-1087/http/events.jsonl)。

### XKNX__xknx-182

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：xknx/devices/light.py::Light.from_config。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：home-assistant-plugin/custom_components/xknx/light.py::KNXLight.color_temp。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/XKNX__xknx-182/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/XKNX__xknx-182/http/events.jsonl)。

### mpdavis__python-jose-76

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：jose/jwt.py::_validate_at_hash。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：jose/jwt.py::_validate_claims；jose/jwt.py::decode；jose/jws.py::verify。
- 已实际送入CIG候选的显式目标函数：jose/jwt.py::_validate_at_hash。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/mpdavis__python-jose-76/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/mpdavis__python-jose-76/http/events.jsonl)。

### modelcontextprotocol__python-sdk-1864

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/mcp/server/fastmcp/resources/templates.py::ResourceTemplate.matches。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/modelcontextprotocol__python-sdk-1864/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/modelcontextprotocol__python-sdk-1864/http/events.jsonl)。

### pypa__auditwheel-568

- 分类：单题1800秒预算终止。执行状态：runner_timeout。
- 既有目标函数：src/auditwheel/tools.py::dir2zip。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：src/auditwheel/tools.py::dir2zip。
- 资源证据：19次HTTP200回执提供已知168447 token，另1次请求未结束；精确总用量为null，保留1800秒预算失败，不据此推断错误定位。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pypa__auditwheel-568/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pypa__auditwheel-568/http/events.jsonl)。

### gidgethub__gidgethub-225

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：gidgethub/sansio.py::decipher_response。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/gidgethub__gidgethub-225/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/gidgethub__gidgethub-225/http/events.jsonl)。

### gammapy__gammapy-5044

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：gammapy/estimators/parameter.py::ParameterEstimator.estimate_ts。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：gammapy/estimators/map/core.py::FluxMaps.flux；gammapy/estimators/map/core.py::FluxMaps._check_quantity；gammapy/estimators/points/core.py::FluxPoints._format_table；gammapy/estimators/points/core.py::FluxPoints._energy_ref_lafferty；gammapy/estimators/points/core.py::FluxPoints._guess_format。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/gammapy__gammapy-5044/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/gammapy__gammapy-5044/http/events.jsonl)。

### kedro-org__kedro-3716

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：kedro/pipeline/modular_pipeline.py::_validate_datasets_exist；kedro/pipeline/modular_pipeline.py::_validate_inputs_outputs。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：2；最终CIG绑定：0。
- 最终函数Top-5：kedro/pipeline/modular_pipeline.py::_is_single_parameter；kedro/pipeline/modular_pipeline.py::pipeline；kedro/pipeline/pipeline.py::Pipeline.outputs。
- 已实际送入CIG候选的显式目标函数：kedro/pipeline/modular_pipeline.py::_validate_datasets_exist；kedro/pipeline/modular_pipeline.py::_validate_inputs_outputs。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/kedro-org__kedro-3716/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/kedro-org__kedro-3716/http/events.jsonl)。

### asottile__pyupgrade-147

- 分类：显式目标曾召回，但相关性过滤后未进入种子。执行状态：complete。
- 既有目标函数：pyupgrade.py::FindPy3Plus.visit_Call；pyupgrade.py::FindPy3Plus.visit_ClassDef。
- 图中精确目标节点：2/2；原检索显式候选中目标：1；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：pyupgrade.py::_replace_call；pyupgrade.py::_fix_py3_plus；pyupgrade.py::_parse_call_args；tests/pyupgrade_test.py::test_fix_six_noop；pyupgrade.py::_get_tmpl。
- 观察到False的目标函数：pyupgrade.py::FindPy3Plus.visit_Call（并不表示该目标在所有调用中始终被剔除）。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/asottile__pyupgrade-147/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/asottile__pyupgrade-147/http/events.jsonl)。

### pyro-ppl__numpyro-1792

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：numpyro/contrib/funsor/infer_util.py::_enum_log_density。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：test/test_handlers.py::test_scale；numpyro/infer/util.py::log_density；numpyro/handlers.py::scale.__init__；test/test_handlers.py::test_subsample_gradient；numpyro/infer/util.py::initialize_model。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pyro-ppl__numpyro-1792/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pyro-ppl__numpyro-1792/http/events.jsonl)。

### hhatto__autopep8-466

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：autopep8.py::parse_args。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/hhatto__autopep8-466/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/hhatto__autopep8-466/http/events.jsonl)。

### GoogleCloudPlatform__django-cloud-deploy-358

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：django_cloud_deploy/skeleton/source_generator.py::_YAMLFileGenerator.generate_new。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：django_cloud_deploy/workflow/_deploygke.py::DeploygkeWorkflow.deploy_new_app_sync；django_cloud_deploy/workflow/deploy_workflow.py::DeployWorkflow.deploy_gke_app。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/GoogleCloudPlatform__django-cloud-deploy-358/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/GoogleCloudPlatform__django-cloud-deploy-358/http/events.jsonl)。

### robotframework__PythonLibCore-73

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/robotlibcore.py::KeywordBuilder.build。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/robotframework__PythonLibCore-73/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/robotframework__PythonLibCore-73/http/events.jsonl)。

### learningequality__ricecooker-329

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：ricecooker/classes/nodes.py::CustomNavigationChannelNode.__init__；ricecooker/classes/nodes.py::CustomNavigationNode.__init__。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/learningequality__ricecooker-329/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/learningequality__ricecooker-329/http/events.jsonl)。

### BrianPugh__cyclopts-609

- 分类：显式目标曾召回，但相关性过滤后未进入种子。执行状态：complete。
- 既有目标函数：cyclopts/core.py::App._parse_known_args；cyclopts/core.py::_get_help_flag_index。
- 图中精确目标节点：2/2；原检索显式候选中目标：1；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：cyclopts/loader.py::_suppress_app_execution；cyclopts/loader.py::load_app_from_script。
- 观察到False的目标函数：cyclopts/core.py::App._parse_known_args（并不表示该目标在所有调用中始终被剔除）。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/BrianPugh__cyclopts-609/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/BrianPugh__cyclopts-609/http/events.jsonl)。

### cerfacs-globc__icclim-283

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：icclim/generic_indices/generic_indicators.py::fraction_of_total。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：icclim/main.py::_build_history；icclim/main.py::_compute_climate_index；icclim/main.py::_add_ecad_index_metadata。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/cerfacs-globc__icclim-283/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/cerfacs-globc__icclim-283/http/events.jsonl)。

### ipython__ipython-11718

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：IPython/core/inputtransformer2.py::TransformerManager.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：IPython/lib/demo.py::Demo.run_cell；IPython/lib/demo.py::IPythonDemo.run_cell。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/ipython__ipython-11718/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/ipython__ipython-11718/http/events.jsonl)。

### PlasmaFAIR__sdf-xarray-37

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/sdf_xarray/__init__.py::SDFPreprocess.__call__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/sdf_xarray/__init__.py::open_mfdataset；src/sdf_xarray/__init__.py::combine_datasets；src/sdf_xarray/__init__.py::make_time_dims；src/sdf_xarray/__init__.py::SDFEntrypoint.open_dataset；src/sdf_xarray/__init__.py::SDFDataStore.open。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/PlasmaFAIR__sdf-xarray-37/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/PlasmaFAIR__sdf-xarray-37/http/events.jsonl)。

### learningequality__kolibri-5951

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：kolibri/utils/cli.py::update。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：kolibri/utils/sanity_checks.py::check_other_kolibri_running；kolibri/utils/server.py::get_status。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/learningequality__kolibri-5951/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/learningequality__kolibri-5951/http/events.jsonl)。

### numba__numba-5557

- 分类：上下文容量限制。执行状态：ContextBudgetExceeded。
- 既有目标函数：numba/core/types/function_type.py::FunctionType.get_call_type。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 资源证据：完整候选/代码输入超过冻结上下文容量，未偷偷裁剪、删候选或追加调用救分。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/numba__numba-5557/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/numba__numba-5557/http/events.jsonl)。

### vyperlang__vyper-4801

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：vyper/venom/memory_allocator.py::MemoryAllocator.allocate。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/vyperlang__vyper-4801/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/vyperlang__vyper-4801/http/events.jsonl)。

### marshmallow-code__marshmallow-960

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：marshmallow/fields.py::Dict._add_to_schema；marshmallow/fields.py::List._add_to_schema。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/marshmallow-code__marshmallow-960/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/marshmallow-code__marshmallow-960/http/events.jsonl)。

### eerimoq__bincopy-41

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：bincopy.py::Segment.chunks；bincopy.py::Segments.chunks。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：bincopy.py::Segments.add；bincopy.py::Segment.add_data。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/eerimoq__bincopy-41/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/eerimoq__bincopy-41/http/events.jsonl)。

### iterative__dvc-10844

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：dvc/repo/diff.py::_diff。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：dvc/repo/index.py::Index.update；dvc/repo/diff.py::diff；dvc/repo/index.py::IndexView.data_keys；dvc/repo/index.py::Index.used_objs；dvc/repo/index.py::collect_files。
- 已实际送入CIG候选的显式目标函数：dvc/repo/diff.py::_diff。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/iterative__dvc-10844/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/iterative__dvc-10844/http/events.jsonl)。

### sanic-org__sanic-2525

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：sanic/app.py::Sanic._startup。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：sanic/touchup/service.py::TouchUp.register；sanic/blueprints.py::Blueprint.register。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/sanic-org__sanic-2525/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/sanic-org__sanic-2525/http/events.jsonl)。

### tianocore__edk2-pytool-library-698

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：edk2toollib/uefi/edk2/parsers/base_parser.py::BaseParser.ReplaceVariables；edk2toollib/uefi/edk2/parsers/base_parser.py::BaseParser.__init__。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/tianocore__edk2-pytool-library-698/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/tianocore__edk2-pytool-library-698/http/events.jsonl)。

### lyft__cartography-331

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：cartography/intel/aws/iam.py::load_roles。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：cartography/intel/aws/s3.py::parse_policy。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/lyft__cartography-331/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/lyft__cartography-331/http/events.jsonl)。

### reata__sqllineage-503

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：sqllineage/utils/helpers.py::split。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：sqllineage/core/parser/sqlfluff/analyzer.py::SqlFluffLineageAnalyzer._list_specific_statement_segment；sqllineage/core/parser/sqlfluff/analyzer.py::SqlFluffLineageAnalyzer.split_tsql。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/reata__sqllineage-503/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/reata__sqllineage-503/http/events.jsonl)。

### PermutaTriangle__Tilings-308

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：tilings/strategies/fusion/constructor.py::FusionConstructor._init_checked。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tilings/strategies/fusion/constructor.py::ReverseFusionConstructor.get_terms；tilings/strategies/factor.py::Interleaving.get_terms；tilings/strategies/fusion/constructor.py::FusionConstructor.get_terms；tilings/strategies/fusion/constructor.py::ReverseFusionConstructor.a_map；tilings/strategies/fusion/constructor.py::ReverseFusionConstructor.forward_map。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/PermutaTriangle__Tilings-308/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/PermutaTriangle__Tilings-308/http/events.jsonl)。

### Point72__ccflow-24

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：ccflow/callable.py::FlowOptions.__call__.wrapper；ccflow/callable.py::_CallableModel.__call__。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：ccflow/callable.py::Flow.call。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Point72__ccflow-24/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Point72__ccflow-24/http/events.jsonl)。

### koxudaxi__datamodel-code-generator-2389

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：src/datamodel_code_generator/parser/base.py::Parser.__change_field_name。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：src/datamodel_code_generator/parser/base.py::Parser.__set_default_enum_member；src/datamodel_code_generator/parser/base.py::Parser.__init__；src/datamodel_code_generator/model/enum.py::Enum.find_member。
- 已实际送入CIG候选的显式目标函数：src/datamodel_code_generator/parser/base.py::Parser.__change_field_name。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/koxudaxi__datamodel-code-generator-2389/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/koxudaxi__datamodel-code-generator-2389/http/events.jsonl)。

### PyCQA__flake8-bugbear-424

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：bugbear.py::BugBearVisitor.check_for_b005；bugbear.py::BugBearVisitor.check_for_b017。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：bugbear.py::BugBearVisitor._is_assertRaises_like。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/PyCQA__flake8-bugbear-424/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/PyCQA__flake8-bugbear-424/http/events.jsonl)。

### magpylib__magpylib-430

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：magpylib/_src/display/disp_utility.py::draw_arrow；magpylib/_src/display/disp_utility.py::draw_arrow_from_vertices。
- 图中精确目标节点：2/2；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：2；最终CIG绑定：1。
- 最终函数Top-5：magpylib/_src/style.py::Line.width；magpylib/_src/display/plotly_draw.py::make_Line；magpylib/_src/style.py::Arrow.show；magpylib/_src/fields/field_BH_line.py::field_BH_line；magpylib/_src/fields/field_BH_line.py::field_BH_line_from_vert。
- 首个目标函数真实排名：6。
- 已实际送入CIG候选的显式目标函数：magpylib/_src/display/disp_utility.py::draw_arrow；magpylib/_src/display/disp_utility.py::draw_arrow_from_vertices。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/magpylib__magpylib-430/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/magpylib__magpylib-430/http/events.jsonl)。

### ets-labs__python-dependency-injector-852

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/dependency_injector/wiring.py::_bind_injections；src/dependency_injector/wiring.py::_locate_dependent_closing_args。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/ets-labs__python-dependency-injector-852/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/ets-labs__python-dependency-injector-852/http/events.jsonl)。

### arrow-py__arrow-868

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：arrow/arrow.py::Arrow.humanize。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：tests/test_arrow.py::TestArrowHumanize.test_arrow；tests/test_arrow.py::TestArrowHumanize.test_minutes；tests/test_arrow.py::TestArrowHumanize.test_minute；arrow/arrow.py::Arrow.shift；tests/test_arrow.py::TestArrowHumanize.test_hours。
- 首个目标函数真实排名：6。
- 已实际送入CIG候选的显式目标函数：arrow/arrow.py::Arrow.humanize。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/arrow-py__arrow-868/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/arrow-py__arrow-868/http/events.jsonl)。

### python-metar__python-metar-55

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：metar/Metar.py::Metar.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：metar/Metar.py::Metar._handleSnowDepthRemark；test/test_metar.py::MetarTest.test_041_parseModifier；test/test_metar.py::MetarTest.test_141_parseWind_nonstd；test/test_metar.py::MetarTest.test_not_strict_mode；test/test_metar.py::MetarTest.test_150_parseVisibility.report。
- 已实际送入CIG候选的显式目标函数：metar/Metar.py::Metar.__init__。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/python-metar__python-metar-55/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/python-metar__python-metar-55/http/events.jsonl)。

### trinodb__trino-python-client-564

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：trino/dbapi.py::Connection.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/trinodb__trino-python-client-564/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/trinodb__trino-python-client-564/http/events.jsonl)。

### hazelcast__hazelcast-python-client-380

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：hazelcast/cp.py::_without_default_group_name。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：hazelcast/cp.py::CPProxyManager._create_fenced_lock；hazelcast/cp.py::CPProxyManager.get_or_create；hazelcast/cp.py::CPSubsystem.get_lock。
- 已实际送入CIG候选的显式目标函数：hazelcast/cp.py::_without_default_group_name。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/hazelcast__hazelcast-python-client-380/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/hazelcast__hazelcast-python-client-380/http/events.jsonl)。

### scipp__plopp-428

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：src/plopp/plotting/common.py::to_data_array。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：src/plopp/backends/matplotlib/image.py::Image。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/scipp__plopp-428/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/scipp__plopp-428/http/events.jsonl)。

### tornadoweb__tornado-2549

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：tornado/http1connection.py::HTTP1Connection.write。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tornado/web.py::RequestHandler.finish；tornado/web.py::_HandlerDelegate.finish。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/tornadoweb__tornado-2549/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/tornadoweb__tornado-2549/http/events.jsonl)。

### scrapinghub__shub-53

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：shub/login.py::cli。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：shub/login.py::cli。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/scrapinghub__shub-53/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/scrapinghub__shub-53/http/events.jsonl)。

### pydata__sparse-870

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：sparse/numba_backend/_utils.py::check_zero_fill_value；sparse/numba_backend/_utils.py::equivalent。
- 图中精确目标节点：2/2；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：sparse/numba_backend/_sparse_array.py::SparseArray.conj；sparse/numba_backend/_sparse_array.py::SparseArray._make_shallow_copy_of；sparse/numba_backend/_coo/core.py::COO.transpose。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/pydata__sparse-870/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/pydata__sparse-870/http/events.jsonl)。

### BerriAI__litellm-16315

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：litellm/llms/bedrock/chat/invoke_transformations/anthropic_claude3_transformation.py::AmazonAnthropicClaudeConfig.transform_request。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/BerriAI__litellm-16315/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/BerriAI__litellm-16315/http/events.jsonl)。

### PyPSA__PyPSA-784

- 分类：目标已输出，但排名在Top5之后。执行状态：complete。
- 既有目标函数：pypsa/io.py::import_from_netcdf。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：1。
- 最终函数Top-5：pypsa/components.py::Network.__init__；pypsa/io.py::ImporterNetCDF.__init__；pypsa/io.py::_retrieve_from_url；pypsa/io.py::ImporterNetCDF.__enter__；pypsa/io.py::import_from_pypower_ppc。
- 首个目标函数真实排名：6。
- 已实际送入CIG候选的显式目标函数：pypsa/io.py::import_from_netcdf。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/PyPSA__PyPSA-784/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/PyPSA__PyPSA-784/http/events.jsonl)。

### aesara-devs__aesara-972

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：aesara/link/c/cmodule.py::GCC_compiler.compile_args。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/aesara-devs__aesara-972/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/aesara-devs__aesara-972/http/events.jsonl)。

### andycasey__ads-74

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：ads/search.py::SearchQuery.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：ads/search.py::SearchQuery.execute。
- 观察到False的目标函数：ads/search.py::SearchQuery.__init__（并不表示该目标在所有调用中始终被剔除）。
- 已实际送入CIG候选的显式目标函数：ads/search.py::SearchQuery.__init__。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/andycasey__ads-74/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/andycasey__ads-74/http/events.jsonl)。

### optuna__optuna-6428

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：optuna/samplers/_tpe/sampler.py::TPESampler.sample_relative。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：optuna/trial/_fixed.py::FixedTrial.suggest_float；optuna/trial/_base.py::BaseTrial.suggest_float；tests/trial_tests/test_trial.py::test_check_distribution_suggest_loguniform；tests/trial_tests/test_trial.py::test_check_distribution_suggest_float；tests/trial_tests/test_trial.py::test_suggest_low_equals_high。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/optuna__optuna-6428/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/optuna__optuna-6428/http/events.jsonl)。

### Eyepea__aiosip-111

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：aiosip/transaction.py::FutureTransaction._result。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：tests/test_sip_scenario.py::test_cancel.Dialplan.subscribe；tests/test_sip_scenario.py::test_authentication；tests/test_sip_scenario.py::test_authentication.Dialplan.subscribe；tests/test_sip_scenario.py::test_cancel.Dialplan.resolve；tests/test_sip_scenario.py::test_notify.Dialplan.subscribe。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/Eyepea__aiosip-111/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/Eyepea__aiosip-111/http/events.jsonl)。

### jdb78__pytorch-forecasting-1577

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：pytorch_forecasting/models/nhits/__init__.py::NHiTS.__init__。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：pytorch_forecasting/models/deepar/__init__.py::DeepAR.create_log；pytorch_forecasting/utils.py::to_list；pytorch_forecasting/models/temporal_fusion_transformer/__init__.py::TemporalFusionTransformer.plot_prediction；pytorch_forecasting/models/temporal_fusion_transformer/__init__.py::TemporalFusionTransformer._log_interpretation；pytorch_forecasting/models/temporal_fusion_transformer/__init__.py::TemporalFusionTransformer.interpret_output。
- 已实际送入CIG候选的显式目标函数：pytorch_forecasting/models/nhits/__init__.py::NHiTS.__init__。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/jdb78__pytorch-forecasting-1577/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/jdb78__pytorch-forecasting-1577/http/events.jsonl)。

### PyCQA__flake8-1726

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：src/flake8/checker.py::Manager.report。
- 图中精确目标节点：1/1；原检索显式候选中目标：1；保留后：1；种子：1；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：src/flake8/checker.py::FileChecker.report；src/flake8/main/application.py::Application.report_errors。
- 已实际送入CIG候选的显式目标函数：src/flake8/checker.py::Manager.report。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/PyCQA__flake8-1726/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/PyCQA__flake8-1726/http/events.jsonl)。

### mkdocs__mkdocs-2852

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：mkdocs/structure/files.py::get_files。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/mkdocs__mkdocs-2852/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/mkdocs__mkdocs-2852/http/events.jsonl)。

### BlueBrain__atlas-splitter-12

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：atlas_splitter/utils.py::id_from_acronym。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：空。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/BlueBrain__atlas-splitter-12/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/BlueBrain__atlas-splitter-12/http/events.jsonl)。

### FactoryBoy__factory_boy-1067

- 分类：图中有目标函数节点，但检索候选未见显式目标函数。执行状态：complete。
- 既有目标函数：factory/declarations.py::Maybe.evaluate_pre。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：0；最终CIG绑定：0。
- 最终函数Top-5：factory/base.py::BaseFactory.create；factory/base.py::BaseFactory.create_batch；factory/base.py::BaseFactory._generate；factory/base.py::BaseFactory.stub。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/FactoryBoy__factory_boy-1067/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/FactoryBoy__factory_boy-1067/http/events.jsonl)。

### xarg__kuku-4

- 分类：显式目标函数已送CIG，但最终未绑定。执行状态：complete。
- 既有目标函数：kuku/dump.py::dump。
- 图中精确目标节点：1/1；原检索显式候选中目标：0；保留后：0；种子：0；CIG实际候选：1；最终CIG绑定：0。
- 最终函数Top-5：空。
- 已实际送入CIG候选的显式目标函数：kuku/dump.py::dump。
- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。
- 原始证据：[result.json](../../experiments/qwen3_rebench280_v3_20261116/outputs/xarg__kuku-4/result.json)、[HTTP/工具/CIG事件](../../experiments/qwen3_rebench280_v3_20261116/outputs/xarg__kuku-4/http/events.jsonl)。

## 技术签注与后续使用

本次工具与解析链路可供正式报告使用：全部280题终态，真实输入输出、相关性定长契约、源码文本送达及图源绑定可核验，源码55项冻结一致。已知7个容量失败和1个时间预算终止明确计入分母，未知用量保留。该签注只确认工程契约与证据完整性，不保证定位正确或结论能够外推。

本题集沿用既有结果选择后的280题池（删除基线表现更优的18题及双方失败的2题），不是独立盲抽测试；比较和泛化结论必须保留该选择偏差披露。未把本轮较低分数用作再次改提示词、改采样或挑版本的依据。

优先可研究的方向由这些观察限定：图区分嵌套函数表示、在既有候选图上的检索策略、相关性判断的目标保留以及CIG绑定与输出顺序。它们是后续独立实验假设，不是本轮已经证明有效的修复方案。

## 可复现产物

- 本目录逐题CSV包含全部280题，以函数Hit@5区分命中与未命中；JSON保存所有阶段集合、图覆盖证据、原始路径及SHA。
- 工具审计：../final280_tool_failure_audit/；图库存核验：../final280_graph_inventory_coverage/；逐阶段证据：../final280_failure_stage_evidence/。
- analysis/内4个纯CPU脚本与复现说明可重新产生独立输出目录；不会触发模型、工具或评分测试。
