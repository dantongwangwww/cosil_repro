# 静态图库存的既有目标函数覆盖核验

full280全终态后连接同协议最终评价，纯CPU读取既有静态图与worker公开AST库存。零新增模型调用、零工具重放，不改预测。

仅FUNCTION/METHOD/CONSTRUCTOR节点按文件路径、函数定义起点和原叶名唯一对齐公开AST限定名。类、文件与近似拼写不扩成目标函数。

## 目标级精确核验

| 状态 | 目标数 |
|---|---:|
| NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET | 4 |
| PRESENT_EXACT_GRAPH_AST_ANCHOR | 362 |

## 逐题覆盖

| 状态 | 题数 |
|---|---:|
| NO_TARGET_EXACTLY_VERIFIED | 1 |
| ALL_TARGETS_PRESENT | 276 |
| PARTLY_PRESENT | 3 |

## 未能全部精确验证的题目

### neurostuff__NiMARE-939

- 最终函数Hit@5：0；图库存状态：NO_TARGET_EXACTLY_VERIFIED。
- nimare/io.py::convert_nimads_to_dataset._analysis_to_dict：NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET。

### owkin__PyDESeq2-349

- 最终函数Hit@5：0；图库存状态：PARTLY_PRESENT。
- pydeseq2/utils.py::nbinomGLM：PRESENT_EXACT_GRAPH_AST_ANCHOR。
- pydeseq2/utils.py::nbinomGLM.df：NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET。

### python-babel__babel-1163

- 最终函数Hit@5：1；图库存状态：PARTLY_PRESENT。
- babel/dates.py::format_timedelta：PRESENT_EXACT_GRAPH_AST_ANCHOR。
- babel/dates.py::format_timedelta._iter_patterns：NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET。

### SciTools__iris-6754

- 最终函数Hit@5：0；图库存状态：PARTLY_PRESENT。
- lib/iris/fileformats/netcdf/loader.py::_translate_constraints_to_var_callback：PRESENT_EXACT_GRAPH_AST_ANCHOR。
- lib/iris/fileformats/netcdf/loader.py::_translate_constraints_to_var_callback.inner：NO_EXACT_FUNCTION_NODE_FOR_PUBLIC_AST_TARGET。

## 解释边界

- No exact function node is a graph-inventory constraint, not proof target source is absent from all class/file content.
- A graph node present does not certify search recall, source use or repair reasoning.
- Missing/ambiguous public AST target remains UNVERIFIED, never asserted graph absent.
- Definition coordinates identify functions; graph end ranges/content completeness are not revalidated.
