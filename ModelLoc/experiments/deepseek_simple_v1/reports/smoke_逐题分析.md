# ModelLoc 逐题逐方法分析

集合smoke，run=20261021_nonthinking_v3。严格/部分/不可映射分列，不按结果好坏删题。

## django__django-13768

仓库：django/django；base：`965d2d95c630939b53eb60d9c169f5dfc77ee0c6`；映射：partially_mappable。

gold文件：`django/dispatch/dispatcher.py`。

可映射gold函数：`django/dispatch/dispatcher.py::Signal.send_robust`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 138.62 | 88705/181 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 305.55 | 42439/940 | 6/6 | 6/2 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 91.73 | 56398/852 | 0/10 | 0/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 116.58 | 56398/852 | 0/10 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/dispatch/dispatcher.py::Signal.send_robust`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-SIMPLE/django__django-13768`。
- D-COSIL：`django/dispatch/dispatcher.py::Signal.send_robust`, `None`, `django/dispatch/dispatcher.py::Signal.send`, `django/utils/log.py::log_response`, `django/utils/log.py::configure_logging`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-COSIL/django__django-13768`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误10，重复输入4，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-COSIL/django__django-13768`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误10，重复输入4，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-PRUNER/django__django-13768`。

## sympy__sympy-18621

仓库：sympy/sympy；base：`b17ef6effe278d5b861d65896cc53442a6370d8f`；映射：fully_mappable。

gold文件：`sympy/matrices/expressions/blockmatrix.py`。

可映射gold函数：`sympy/matrices/expressions/blockmatrix.py::BlockDiagMatrix.blocks`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 139.58 | 108045/593 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 331.44 | 125736/1473 | 10/10 | 10/4 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 105.01 | 96844/1004 | 2/10 | 2/1 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 179.75 | 97626/1003 | 3/10 | 3/0 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/matrices/expressions/blockmatrix.py::BlockMatrix._entry`, `sympy/matrices/expressions/blockmatrix.py::BlockDiagMatrix.blocks`, `sympy/matrices/expressions/blockmatrix.py::BlockDiagMatrix.__new__`, `sympy/matrices/expressions/matexpr.py::MatrixExpr.as_explicit`, `sympy/matrices/matrices.py::MatrixBase._handle_creation_inputs`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-SIMPLE/sympy__sympy-18621`。
- D-COSIL：`sympy/matrices/expressions/blockmatrix.py::BlockDiagMatrix.blocks`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix._entry`, `sympy/matrices/expressions/blockmatrix.py::BlockDiagMatrix.__new__`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix.blocks`, `sympy/matrices/expressions/blockmatrix.py::BlockDiagMatrix.blockshape`。解析失败0，工具错误0，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-COSIL/sympy__sympy-18621`。
- Q-COSIL：`None`, `sympy/matrices/expressions/matexpr.py::MatrixExpr.as_explicit`, `None`, `sympy/utilities/iterables.py::flatten`, `sympy/matrices/expressions/blockmatrix.py::BlockDiagMatrix.__new__`。解析失败0，工具错误8，重复输入5，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-COSIL/sympy__sympy-18621`。
- Q-PRUNER：`sympy/matrices/expressions/blockmatrix.py::BlockDiagMatrix.__new__`, `None`, `sympy/matrices/expressions/matexpr.py::MatrixExpr.as_explicit`, `None`, `sympy/utilities/iterables.py::flatten`。解析失败0，工具错误7，重复输入5，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-PRUNER/sympy__sympy-18621`。

## django__django-15213

仓库：django/django；base：`03cadb912c78b769d6bf4a943a2a35fc1d952960`；映射：unmappable。

gold文件：`django/db/models/fields/__init__.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 2.59 | 126391/654 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 183.22 | 134911/1951 | 9/9 | 9/6 |
| Q-COSIL | complete | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 121.37 | 126712/1263 | 7/10 | 7/4 |
| Q-PRUNER | complete | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 139.22 | 126400/1254 | 7/10 | 7/3 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/models/sql/where.py::WhereNode.as_sql`, `django/db/models/expressions.py::ExpressionWrapper.as_sql`, `django/db/models/expressions.py::ExpressionWrapper.get_group_by_cols`, `django/db/models/query_utils.py::Q.resolve_expression`, `django/db/models/sql/query.py::Query._add_q`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-SIMPLE/django__django-15213`。
- D-COSIL：`django/db/models/sql/where.py::WhereNode.as_sql`, `django/db/models/expressions.py::ExpressionWrapper.as_sql`, `django/db/models/sql/compiler.py::SQLCompiler.get_select`, `django/db/models/sql/where.py::NothingNode.as_sql`, `django/db/models/query_utils.py::Q.resolve_expression`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-COSIL/django__django-15213`。
- Q-COSIL：`None`, `None`, `django/db/models/expressions.py::ExpressionWrapper.as_sql`, `django/db/models/query.py::QuerySet.annotate`, `django/db/models/expressions.py::Combinable._combine`。解析失败0，工具错误3，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-COSIL/django__django-15213`。
- Q-PRUNER：`django/db/models/expressions.py::ExpressionWrapper.as_sql`, `None`, `None`, `django/db/models/expressions.py::ExpressionWrapper.get_group_by_cols`, `django/db/models/expressions.py::ExpressionWrapper.set_source_expressions`。解析失败0，工具错误3，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-PRUNER/django__django-15213`。

## matplotlib__matplotlib-24149

仓库：matplotlib/matplotlib；base：`af39f1edffcd828f05cfdd04f2e59506bb4a27bc`；映射：fully_mappable。

gold文件：`lib/matplotlib/axes/_axes.py`。

可映射gold函数：`lib/matplotlib/axes/_axes.py::Axes._convert_dx`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 139.87 | 165827/304 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 19.10 | 91857/1420 | 4/4 | 4/4 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 6.59 | 6127/56 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 14.78 | 6127/56 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`lib/matplotlib/axes/_axes.py::Axes._convert_dx`, `lib/matplotlib/axes/_axes.py::Axes.bar`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-SIMPLE/matplotlib__matplotlib-24149`。
- D-COSIL：`lib/matplotlib/cbook/__init__.py::_safe_first_finite`, `lib/matplotlib/axes/_axes.py::Axes._convert_dx`, `lib/matplotlib/axes/_axes.py::Axes.bar`, `lib/matplotlib/cbook/__init__.py::safe_first_element`, `lib/matplotlib/axes/_axes.py::Axes.barh`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-COSIL/matplotlib__matplotlib-24149`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-COSIL/matplotlib__matplotlib-24149`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-PRUNER/matplotlib__matplotlib-24149`。

## scikit-learn__scikit-learn-13241

仓库：scikit-learn/scikit-learn；base：`f8b108d0c6f2f82b2dc4e32a6793f9d9ac9cf2f4`；映射：partially_mappable。

gold文件：`sklearn/decomposition/kernel_pca.py`。

可映射gold函数：`sklearn/decomposition/kernel_pca.py::KernelPCA._fit_transform`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 1.47 | 58156/436 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 20.34 | 54825/1595 | 0/0 | 0/0 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 96.48 | 86356/1153 | 10/10 | 10/7 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 92.02 | 96965/1097 | 6/10 | 6/6 |

各臂原始预测与问题：

- D-SIMPLE：`sklearn/decomposition/kernel_pca.py::KernelPCA._fit_transform`, `sklearn/decomposition/kernel_pca.py::KernelPCA.fit_transform`, `sklearn/decomposition/kernel_pca.py::KernelPCA.fit`, `sklearn/utils/extmath.py::svd_flip`, `sklearn/utils/extmath.py::_deterministic_vector_sign_flip`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-SIMPLE/scikit-learn__scikit-learn-13241`。
- D-COSIL：`sklearn/decomposition/kernel_pca.py::KernelPCA._fit_transform`, `sklearn/decomposition/kernel_pca.py::KernelPCA.fit_transform`, `sklearn/decomposition/kernel_pca.py::KernelPCA.transform`, `sklearn/utils/extmath.py::svd_flip`, `sklearn/utils/extmath.py::_deterministic_vector_sign_flip`。解析失败10，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/D-COSIL/scikit-learn__scikit-learn-13241`。
- Q-COSIL：`sklearn/decomposition/kernel_pca.py::KernelPCA._fit_transform`, `sklearn/decomposition/kernel_pca.py::KernelPCA._get_kernel`, `sklearn/metrics/pairwise.py::pairwise_kernels`, `sklearn/utils/_pprint.py::_EstimatorPrettyPrinter._format_params`, `None`。解析失败0，工具错误0，重复输入4，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-COSIL/scikit-learn__scikit-learn-13241`。
- Q-PRUNER：`sklearn/decomposition/kernel_pca.py::KernelPCA._fit_transform`, `sklearn/metrics/pairwise.py::pairwise_kernels`, `sklearn/metrics/pairwise.py::rbf_kernel`, `sklearn/metrics/pairwise.py::euclidean_distances`, `sklearn/utils/_pprint.py::_EstimatorPrettyPrinter.format`。解析失败0，工具错误4，重复输入3，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/smoke/Q-PRUNER/scikit-learn__scikit-learn-13241`。

