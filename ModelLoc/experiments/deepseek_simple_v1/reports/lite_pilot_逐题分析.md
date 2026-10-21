# ModelLoc 逐题逐方法分析

集合lite_pilot，run=20261021_nonthinking_v3。严格/部分/不可映射分列，不按结果好坏删题。

## sympy__sympy-17630

仓库：sympy/sympy；base：`58e78209c8577b9890e957b624466e5beed7eb08`；映射：fully_mappable。

gold文件：`sympy/matrices/expressions/matexpr.py`。

可映射gold函数：`sympy/matrices/expressions/matexpr.py::get_postprocessor._postprocessor`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 0.00%/0.00% | 144.87 | 82272/737 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 50.92 | 129231/1879 | 6/6 | 6/3 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 134.28 | 163134/1131 | 9/9 | 9/9 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 243.36 | 167567/1121 | 9/9 | 9/9 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/matrices/expressions/blockmatrix.py::BlockMatrix.colblocksizes`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix._blockmul`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix.rowblocksizes`, `sympy/matrices/expressions/blockmatrix.py::bc_matmul`, `sympy/matrices/expressions/matmul.py::any_zeros`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-17630`。
- D-COSIL：`sympy/matrices/expressions/blockmatrix.py::BlockMatrix._blockmul`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix.colblocksizes`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix.rowblocksizes`, `sympy/matrices/expressions/matmul.py::any_zeros`, `sympy/matrices/expressions/blockmatrix.py::bc_matmul`。解析失败4，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-17630`。
- Q-COSIL：`sympy/matrices/expressions/blockmatrix.py::BlockMatrix._blockmul`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix.colblocksizes`, `sympy/core/numbers.py::Zero._eval_power`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix.blocks`, `sympy/utilities/iterables.py::flatten`。解析失败1，工具错误0，重复输入5，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-17630`。
- Q-PRUNER：`sympy/matrices/expressions/blockmatrix.py::BlockMatrix._blockmul`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix.colblocksizes`, `sympy/core/numbers.py::Zero._eval_power`, `sympy/matrices/expressions/blockmatrix.py::BlockMatrix.blocks`, `sympy/utilities/iterables.py::flatten`。解析失败1，工具错误0，重复输入5，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-17630`。

## django__django-11049

仓库：django/django；base：`17455e924e243e7a55e8a38f45966d8cbb27c273`；映射：unmappable。

gold文件：`django/db/models/fields/__init__.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NOT_RUN/NA/NOT_RUN/NA | 10.49 | 109486/342 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | NOT_RUN/NA/NOT_RUN/NA | 311.87 | 114506/1797 | 5/5 | 5/3 |
| Q-COSIL | failed | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 191.33 | 17402/2403 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 209.96 | 17402/2403 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/models/fields/__init__.py::DurationField.to_python`, `django/forms/fields.py::DurationField.to_python`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-11049`。
- D-COSIL：`None`, `None`, `django/forms/fields.py::DurationField.to_python`, `django/db/models/fields/__init__.py::DurationField.to_python`, `django/db/models/fields/__init__.py::DurationField.formfield`。解析失败5，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-11049`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；Truncated or rejected model response。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-11049`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；Truncated or rejected model response。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-11049`。

## scikit-learn__scikit-learn-15512

仓库：scikit-learn/scikit-learn；base：`b8a4da8baa1137f173e7035f104067c7d2ffde22`；映射：fully_mappable。

gold文件：`sklearn/cluster/_affinity_propagation.py`。

可映射gold函数：`sklearn/cluster/_affinity_propagation.py::AffinityPropagation.predict`, `sklearn/cluster/_affinity_propagation.py::affinity_propagation`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.25 | 59352/367 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 26.85 | 75374/1716 | 7/7 | 7/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 86.53 | 85084/973 | 9/10 | 9/4 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 98.68 | 115124/940 | 10/10 | 10/9 |

各臂原始预测与问题：

- D-SIMPLE：`sklearn/cluster/_affinity_propagation.py::affinity_propagation`, `sklearn/cluster/_affinity_propagation.py::AffinityPropagation.fit`, `sklearn/cluster/_affinity_propagation.py::AffinityPropagation.predict`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/scikit-learn__scikit-learn-15512`。
- D-COSIL：`sklearn/cluster/_affinity_propagation.py::affinity_propagation`, `sklearn/cluster/_affinity_propagation.py::AffinityPropagation.fit`, `None`, `None`, `sklearn/cluster/_affinity_propagation.py::AffinityPropagation.predict`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/scikit-learn__scikit-learn-15512`。
- Q-COSIL：`sklearn/cluster/_affinity_propagation.py::AffinityPropagation.fit`, `sklearn/cluster/_affinity_propagation.py::affinity_propagation`, `sklearn/cluster/_affinity_propagation.py::AffinityPropagation.predict`, `sklearn/cluster/_affinity_propagation.py::AffinityPropagation.fit_predict`, `sklearn/utils/validation.py::check_is_fitted`。解析失败0，工具错误1，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/scikit-learn__scikit-learn-15512`。
- Q-PRUNER：`sklearn/cluster/_affinity_propagation.py::AffinityPropagation.fit`, `sklearn/cluster/_affinity_propagation.py::AffinityPropagation.predict`, `sklearn/cluster/_affinity_propagation.py::affinity_propagation`, `sklearn/utils/validation.py::check_array`, `sklearn/cluster/_affinity_propagation.py::AffinityPropagation.fit_predict`。解析失败0，工具错误0，重复输入3，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/scikit-learn__scikit-learn-15512`。

## django__django-12284

仓库：django/django；base：`c5e373d48cbdd923575956fed477b63d66d9603f`；映射：fully_mappable。

gold文件：`django/db/models/fields/__init__.py`。

可映射gold函数：`django/db/models/fields/__init__.py::Field.contribute_to_class`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 12.16 | 119094/374 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 181.98 | 139787/1498 | 9/9 | 9/4 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 145.67 | 65594/1628 | 3/10 | 3/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 168.26 | 66490/1618 | 3/10 | 3/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/models/fields/__init__.py::Field.contribute_to_class`, `django/db/models/base.py::Model._get_FIELD_display`, `django/db/models/fields/__init__.py::Field._get_flatchoices`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-12284`。
- D-COSIL：`django/db/models/fields/__init__.py::Field.contribute_to_class`, `django/db/models/base.py::Model._get_FIELD_display`, `django/db/models/fields/__init__.py::Field._get_flatchoices`, `django/db/models/base.py::ModelBase.__new__`, `django/db/models/fields/__init__.py::Field.get_choices`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-12284`。
- Q-COSIL：`django/db/models/options.py::Options._prepare`, `django/db/models/options.py::Options.add_field`, `None`, `None`, `None`。解析失败0，工具错误7，重复输入4，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-12284`。
- Q-PRUNER：`django/db/models/options.py::Options._prepare`, `django/db/models/options.py::Options.add_field`, `None`, `None`, `None`。解析失败0，工具错误7，重复输入4，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-12284`。

## scikit-learn__scikit-learn-13584

仓库：scikit-learn/scikit-learn；base：`0e3c1879b06d839171b7d0a607d71bbb19a966a9`；映射：fully_mappable。

gold文件：`sklearn/utils/_pprint.py`。

可映射gold函数：`sklearn/utils/_pprint.py::_changed_params`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.61 | 49701/249 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 23.10 | 55150/1665 | 5/5 | 5/5 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 71.79 | 74638/833 | 10/10 | 10/3 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 80.51 | 82551/806 | 10/10 | 10/6 |

各臂原始预测与问题：

- D-SIMPLE：`sklearn/utils/_pprint.py::_changed_params`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/scikit-learn__scikit-learn-13584`。
- D-COSIL：`sklearn/utils/_pprint.py::_changed_params`, `sklearn/utils/_pprint.py::_EstimatorPrettyPrinter._pprint_estimator`, `sklearn/utils/_pprint.py::_safe_repr`, `sklearn/base.py::BaseEstimator.__repr__`, `sklearn/utils/_pprint.py::_EstimatorPrettyPrinter._format_params`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/scikit-learn__scikit-learn-13584`。
- Q-COSIL：`sklearn/utils/_pprint.py::_EstimatorPrettyPrinter._format_params`, `sklearn/utils/_pprint.py::_EstimatorPrettyPrinter._format_params_or_dict_items`, `sklearn/utils/_pprint.py::_EstimatorPrettyPrinter._format_items`, `None`, `sklearn/linear_model/logistic.py::LogisticRegressionCV.fit`。解析失败0，工具错误0，重复输入4，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/scikit-learn__scikit-learn-13584`。
- Q-PRUNER：`sklearn/utils/_pprint.py::_EstimatorPrettyPrinter._format_params_or_dict_items`, `None`, `None`, `None`, `None`。解析失败0，工具错误0，重复输入6，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/scikit-learn__scikit-learn-13584`。

## sympy__sympy-17139

仓库：sympy/sympy；base：`1d3327b8e90a186df6972991963a5ae87053259d`；映射：fully_mappable。

gold文件：`sympy/simplify/fu.py`。

可映射gold函数：`sympy/simplify/fu.py::_TR56._f`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 11.56 | 125848/533 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 50.01 | 88461/1716 | 6/6 | 6/4 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 100.67 | 95774/861 | 5/10 | 5/4 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 162.59 | 98174/855 | 5/10 | 5/5 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/simplify/fu.py::_TR56._f`, `sympy/simplify/fu.py::_TR56`, `sympy/simplify/fu.py::TR6`, `sympy/simplify/fu.py::TR5`, `sympy/simplify/trigsimp.py::_futrig`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-17139`。
- D-COSIL：`sympy/simplify/fu.py::_TR56`, `sympy/simplify/fu.py::TR6`, `sympy/simplify/trigsimp.py::_futrig`, `sympy/simplify/trigsimp.py::futrig`, `sympy/core/expr.py::Expr.__lt__`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-17139`。
- Q-COSIL：`sympy/simplify/fu.py::_TR56`, `sympy/simplify/fu.py::TR6`, `None`, `None`, `None`。解析失败0，工具错误5，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-17139`。
- Q-PRUNER：`None`, `None`, `sympy/simplify/trigsimp.py::futrig`, `sympy/simplify/simplify.py::bottom_up`, `sympy/utilities/misc.py::filldedent`。解析失败0，工具错误5，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-17139`。

## astropy__astropy-12907

仓库：astropy/astropy；base：`d16bfe05a744909de4b27f5875fe0d4ed41ce607`；映射：fully_mappable。

gold文件：`astropy/modeling/separable.py`。

可映射gold函数：`astropy/modeling/separable.py::_cstack`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.88 | 68718/393 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 39.88 | 161922/1919 | 9/9 | 9/5 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 57.39 | 78441/625 | 0/1 | 0/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 67.48 | 78441/625 | 0/1 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`astropy/modeling/separable.py::_cstack`, `astropy/modeling/separable.py::_separable`, `astropy/modeling/separable.py::_coord_matrix`, `astropy/modeling/separable.py::separability_matrix`, `astropy/modeling/separable.py::_compute_n_outputs`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/astropy__astropy-12907`。
- D-COSIL：`astropy/modeling/separable.py::_cstack`, `astropy/modeling/separable.py::_separable`, `astropy/modeling/separable.py::_coord_matrix`, `astropy/modeling/separable.py::separability_matrix`, `astropy/modeling/separable.py::_compute_n_outputs`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/astropy__astropy-12907`。
- Q-COSIL：`astropy/modeling/separable.py::separability_matrix`, `None`, `None`, `None`, `None`。解析失败9，工具错误1，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/astropy__astropy-12907`。
- Q-PRUNER：`astropy/modeling/separable.py::separability_matrix`, `None`, `None`, `None`, `None`。解析失败9，工具错误1，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/astropy__astropy-12907`。

## sympy__sympy-12481

仓库：sympy/sympy；base：`c807dfe7569692cad24f02a08477b70c1679a4dd`；映射：fully_mappable。

gold文件：`sympy/combinatorics/permutations.py`。

可映射gold函数：`sympy/combinatorics/permutations.py::Permutation.__new__`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 10.02 | 107282/295 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 32.37 | 70083/1390 | 4/4 | 4/1 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 25.04 | 3883/311 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 50.58 | 3883/311 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/combinatorics/permutations.py::Permutation.__new__`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-12481`。
- D-COSIL：`sympy/combinatorics/permutations.py::Permutation.__new__`, `sympy/combinatorics/permutations.py::Cycle.__call__`, `sympy/combinatorics/permutations.py::Cycle.__init__`, `sympy/combinatorics/permutations.py::Permutation._af_new`, `sympy/combinatorics/permutations.py::Cycle.list`。解析失败4，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-12481`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-12481`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-12481`。

## sympy__sympy-18189

仓库：sympy/sympy；base：`1923822ddf8265199dbd9ef9ce09641d3fd042b9`；映射：fully_mappable。

gold文件：`sympy/solvers/diophantine.py`。

可映射gold函数：`sympy/solvers/diophantine.py::diophantine`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.55 | 94190/209 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 170.60 | 87302/1329 | 4/4 | 4/2 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 129.35 | 145960/1214 | 10/10 | 10/1 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 178.67 | 158867/1010 | 4/10 | 4/4 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/solvers/diophantine.py::diophantine`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-18189`。
- D-COSIL：`sympy/solvers/diophantine.py::diophantine`, `sympy/solvers/diophantine.py::_diop_general_sum_of_even_powers`, `sympy/solvers/diophantine.py::diop_general_sum_of_even_powers`, `sympy/solvers/diophantine.py::diop_solve`, `sympy/solvers/diophantine.py::classify_diop`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-18189`。
- Q-COSIL：`sympy/solvers/diophantine.py::diophantine`, `sympy/solvers/diophantine.py::_diop_general_sum_of_even_powers`, `sympy/solvers/diophantine.py::_diop_general_sum_of_squares`, `sympy/solvers/diophantine.py::_diop_general_pythagorean`, `sympy/solvers/diophantine.py::_diop_ternary_quadratic_normal`。解析失败0，工具错误0，重复输入8，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-18189`。
- Q-PRUNER：`sympy/solvers/diophantine.py::diophantine`, `sympy/solvers/diophantine.py::_diop_general_sum_of_even_powers`, `sympy/solvers/diophantine.py::power_representation`, `sympy/solvers/diophantine.py::pow_rep_recursive`, `None`。解析失败0，工具错误6，重复输入5，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-18189`。

## sympy__sympy-18698

仓库：sympy/sympy；base：`3dff1b98a78f28c953ae2140b69356b8391e399c`；映射：partially_mappable。

gold文件：`sympy/polys/polytools.py`。

可映射gold函数：`sympy/polys/polytools.py::_symbolic_factor_list`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 0.00%/0.00% | 12.88 | 139936/725 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 191.24 | 103787/1857 | 7/7 | 7/4 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 123.43 | 108463/1184 | 0/10 | 0/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 197.91 | 108463/1184 | 0/10 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/polys/sqfreetools.py::dup_sqf_list`, `sympy/polys/sqfreetools.py::dmp_sqf_list`, `sympy/polys/polytools.py::Poly.sqf_list`, `sympy/polys/polytools.py::_generic_factor_list`, `sympy/polys/polytools.py::sqf_list`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-18698`。
- D-COSIL：`sympy/polys/sqfreetools.py::dup_sqf_list`, `sympy/polys/sqfreetools.py::dmp_sqf_list`, `sympy/polys/euclidtools.py::dup_inner_gcd`, `sympy/polys/euclidtools.py::dmp_inner_gcd`, `sympy/polys/polytools.py::Poly.sqf_list`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-18698`。
- Q-COSIL：`None`, `sympy/polys/sqfreetools.py::dup_sqf_list`, `sympy/polys/sqfreetools.py::dmp_sqf_list`, `sympy/core/mul.py::Mul.as_ordered_factors`, `None`。解析失败0，工具错误10，重复输入9，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-18698`。
- Q-PRUNER：`None`, `sympy/polys/sqfreetools.py::dup_sqf_list`, `sympy/polys/sqfreetools.py::dmp_sqf_list`, `sympy/core/mul.py::Mul.as_ordered_factors`, `None`。解析失败0，工具错误10，重复输入9，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-18698`。

## pylint-dev__pylint-6506

仓库：pylint-dev/pylint；base：`0a4204fd7555cfedd43f43017c94d24ef48244a5`；映射：fully_mappable。

gold文件：`pylint/config/config_initialization.py`。

可映射gold函数：`pylint/config/config_initialization.py::_config_initialization`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.40 | 88150/552 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 19.35 | 45674/1443 | 5/5 | 5/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 100.22 | 69144/1366 | 4/10 | 4/2 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 105.05 | 68919/1330 | 4/10 | 4/1 |

各臂原始预测与问题：

- D-SIMPLE：`pylint/config/config_initialization.py::_config_initialization`, `pylint/lint/run.py::Run.__init__`, `pylint/__init__.py::run_pylint`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/pylint-dev__pylint-6506`。
- D-COSIL：`pylint/config/config_initialization.py::_config_initialization`, `pylint/lint/run.py::Run.__init__`, `pylint/__init__.py::run_pylint`, `pylint/config/exceptions.py::_UnrecognizedOptionError.__init__`, `pylint/config/arguments_manager.py::_ArgumentsManager._parse_command_line_configuration`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/pylint-dev__pylint-6506`。
- Q-COSIL：`pylint/config/config_initialization.py::_config_initialization`, `None`, `None`, `pylint/config/option_manager_mixin.py::OptionsManagerMixIn.load_configuration_from_config`, `None`。解析失败0，工具错误6，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/pylint-dev__pylint-6506`。
- Q-PRUNER：`pylint/config/config_initialization.py::_config_initialization`, `pylint/lint/run.py::Run.__init__`, `None`, `None`, `None`。解析失败0，工具错误6，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/pylint-dev__pylint-6506`。

## sympy__sympy-21847

仓库：sympy/sympy；base：`d9b18c518d64d0ebe8e35a98c2fb519938b9b151`；映射：fully_mappable。

gold文件：`sympy/polys/monomials.py`。

可映射gold函数：`sympy/polys/monomials.py::itermonomials`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.18 | 74111/286 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 303.36 | 50979/1264 | 2/2 | 2/1 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 160.73 | 79704/1649 | 8/10 | 8/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 228.80 | 79581/1601 | 8/10 | 8/0 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/polys/monomials.py::itermonomials`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-21847`。
- D-COSIL：`sympy/polys/monomials.py::itermonomials`, `sympy/polys/monomials.py::monomial_count`, `sympy/polys/monomials.py::monomial_mul`, `sympy/polys/monomials.py::monomial_pow`, `sympy/polys/orderings.py::monomial_key`。解析失败3，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-21847`。
- Q-COSIL：`None`, `sympy/polys/monomials.py::Monomial.__init__`, `sympy/polys/orderings.py::MonomialOrder.__call__`, `sympy/polys/orderings.py::GradedLexOrder.__call__`, `sympy/polys/orderings.py::ReversedGradedLexOrder.__call__`。解析失败0，工具错误2，重复输入3，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-21847`。
- Q-PRUNER：`None`, `sympy/polys/monomials.py::Monomial.__init__`, `sympy/polys/orderings.py::MonomialOrder.__call__`, `sympy/polys/orderings.py::GradedLexOrder.__call__`, `sympy/polys/orderings.py::ReversedGradedLexOrder.__call__`。解析失败0，工具错误2，重复输入3，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-21847`。

## django__django-11815

仓库：django/django；base：`e02f67ef2d03d48128e7a118bf75f0418e24e8ac`；映射：fully_mappable。

gold文件：`django/db/migrations/serializer.py`。

可映射gold函数：`django/db/migrations/serializer.py::EnumSerializer.serialize`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.33 | 117883/390 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 173.08 | 119711/1683 | 5/5 | 5/4 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 99.22 | 84558/1089 | 2/9 | 2/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 119.02 | 84446/1084 | 2/9 | 2/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/migrations/serializer.py::EnumSerializer.serialize`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-11815`。
- D-COSIL：`django/db/migrations/serializer.py::EnumSerializer.serialize`, `django/db/migrations/serializer.py::serializer_factory`, `django/db/migrations/writer.py::MigrationWriter.serialize`, `django/db/models/fields/__init__.py::Field.deconstruct`, `django/db/migrations/serializer.py::DeconstructableSerializer.serialize_deconstructed`。解析失败5，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-11815`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败1，工具错误7，重复输入1，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-11815`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败1，工具错误7，重复输入1，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-11815`。

## sphinx-doc__sphinx-8713

仓库：sphinx-doc/sphinx；base：`3ed7590ed411bd93b26098faab4f23619cdb2267`；映射：fully_mappable。

gold文件：`sphinx/ext/napoleon/docstring.py`。

可映射gold函数：`sphinx/ext/napoleon/docstring.py::GoogleDocstring._parse_other_parameters_section`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.52 | 66871/270 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 23.52 | 63819/1322 | 5/5 | 5/4 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 74.44 | 70057/916 | 1/10 | 1/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 75.46 | 70174/911 | 1/10 | 1/0 |

各臂原始预测与问题：

- D-SIMPLE：`sphinx/ext/napoleon/docstring.py::GoogleDocstring._parse_other_parameters_section`, `sphinx/ext/napoleon/docstring.py::GoogleDocstring._parse_parameters_section`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sphinx-doc__sphinx-8713`。
- D-COSIL：`sphinx/ext/napoleon/docstring.py::GoogleDocstring._parse_other_parameters_section`, `sphinx/ext/napoleon/docstring.py::GoogleDocstring._parse_parameters_section`, `sphinx/ext/napoleon/docstring.py::GoogleDocstring._format_docutils_params`, `sphinx/ext/napoleon/docstring.py::GoogleDocstring._format_fields`, `None`。解析失败5，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sphinx-doc__sphinx-8713`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误9，重复输入3，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sphinx-doc__sphinx-8713`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误9，重复输入3，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sphinx-doc__sphinx-8713`。

## django__django-11848

仓库：django/django；base：`f0adf3b9b7a19cdee05368ff0c0c2d087f011180`；映射：fully_mappable。

gold文件：`django/utils/http.py`。

可映射gold函数：`django/utils/http.py::parse_http_date`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.29 | 87662/149 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 28.02 | 33030/689 | 3/3 | 3/2 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 115.47 | 59315/1274 | 6/10 | 6/2 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 134.43 | 61053/1226 | 5/10 | 5/4 |

各臂原始预测与问题：

- D-SIMPLE：`django/utils/http.py::parse_http_date`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-11848`。
- D-COSIL：`django/utils/http.py::parse_http_date`, `django/utils/http.py::parse_http_date_safe`, `django/utils/http.py::http_date`, `django/utils/dateparse.py::parse_date`, `django/utils/dateparse.py::parse_datetime`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-11848`。
- Q-COSIL：`django/utils/http.py::parse_http_date`, `django/utils/http.py::parse_http_date_safe`, `django/utils/dateparse.py::parse_date`, `django/utils/dateparse.py::parse_datetime`, `django/utils/dateparse.py::parse_time`。解析失败0，工具错误4，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-11848`。
- Q-PRUNER：`django/utils/http.py::parse_http_date`, `django/utils/http.py::parse_http_date_safe`, `django/utils/dateparse.py::parse_date`, `django/utils/dateparse.py::parse_datetime`, `django/utils/dateparse.py::parse_time`。解析失败0，工具错误5，重复输入4，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-11848`。

## django__django-13551

仓库：django/django；base：`7f9e4524d6b23424cf44fbe1bf1f4e70f6bb066e`；映射：fully_mappable。

gold文件：`django/contrib/auth/tokens.py`。

可映射gold函数：`django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_hash_value`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.56 | 87806/531 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 172.43 | 65361/1226 | 7/7 | 7/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 103.51 | 88232/992 | 10/10 | 10/8 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 115.92 | 84443/878 | 4/9 | 4/4 |

各臂原始预测与问题：

- D-SIMPLE：`django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_hash_value`, `django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_token_with_timestamp`, `django/contrib/auth/tokens.py::PasswordResetTokenGenerator.check_token`, `django/contrib/auth/base_user.py::AbstractBaseUser.get_email_field_name`, `django/contrib/auth/forms.py::PasswordResetForm.save`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-13551`。
- D-COSIL：`django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_hash_value`, `django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_token_with_timestamp`, `django/contrib/auth/tokens.py::PasswordResetTokenGenerator.check_token`, `django/contrib/auth/base_user.py::AbstractBaseUser.get_email_field_name`, `django/contrib/auth/base_user.py::AbstractBaseUser.get_session_auth_hash`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-13551`。
- Q-COSIL：`django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_hash_value`, `django/contrib/auth/tokens.py::PasswordResetTokenGenerator.make_token`, `django/contrib/auth/tokens.py::PasswordResetTokenGenerator.check_token`, `None`, `django/utils/crypto.py::salted_hmac`。解析失败0，工具错误0，重复输入4，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-13551`。
- Q-PRUNER：`django/contrib/auth/tokens.py::PasswordResetTokenGenerator._make_hash_value`, `django/contrib/auth/tokens.py::PasswordResetTokenGenerator.make_token`, `None`, `None`, `django/utils/crypto.py::salted_hmac`。解析失败1，工具错误5，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-13551`。

## django__django-14382

仓库：django/django；base：`29345aecf6e8d53ccb3577a3762bb0c263f7558d`；映射：fully_mappable。

gold文件：`django/core/management/templates.py`。

可映射gold函数：`django/core/management/templates.py::TemplateCommand.handle`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.85 | 81460/307 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 174.68 | 64967/1343 | 4/4 | 4/3 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 55.64 | 41156/587 | 1/1 | 1/1 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 74.66 | 41092/582 | 1/1 | 1/1 |

各臂原始预测与问题：

- D-SIMPLE：`django/core/management/templates.py::TemplateCommand.handle`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-14382`。
- D-COSIL：`django/core/management/templates.py::TemplateCommand.handle`, `django/core/management/templates.py::TemplateCommand.validate_name`, `django/core/management/commands/startapp.py::Command.handle`, `django/core/management/base.py::BaseCommand.execute`, `django/core/management/base.py::BaseCommand.run_from_argv`。解析失败6，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-14382`。
- Q-COSIL：`django/core/management/templates.py::TemplateCommand.validate_name`, `django/core/management/commands/startapp.py::Command.handle`, `django/core/management/templates.py::TemplateCommand.handle_template`, `django/core/management/templates.py::TemplateCommand.add_arguments`。解析失败9，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-14382`。
- Q-PRUNER：`django/core/management/templates.py::TemplateCommand.validate_name`, `django/core/management/commands/startapp.py::Command.handle`, `django/core/management/templates.py::TemplateCommand.handle_template`, `django/core/management/templates.py::TemplateCommand.add_arguments`。解析失败9，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-14382`。

## matplotlib__matplotlib-23987

仓库：matplotlib/matplotlib；base：`e98d8d085e8f53ec0467422b326f7738a2dd695e`；映射：fully_mappable。

gold文件：`lib/matplotlib/figure.py`。

可映射gold函数：`lib/matplotlib/figure.py::Figure.__init__`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.03 | 130669/518 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 30.64 | 120409/1723 | 9/9 | 9/5 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 51.48 | 5528/684 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 61.59 | 5528/684 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`lib/matplotlib/figure.py::Figure.__init__`, `lib/matplotlib/figure.py::Figure.set_layout_engine`, `lib/matplotlib/figure.py::FigureBase.subplots_adjust`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/matplotlib__matplotlib-23987`。
- D-COSIL：`lib/matplotlib/figure.py::Figure.__init__`, `lib/matplotlib/figure.py::FigureBase.subplots_adjust`, `lib/matplotlib/figure.py::Figure.set_layout_engine`, `None`, `lib/matplotlib/layout_engine.py::LayoutEngine.adjust_compatible`。解析失败1，工具错误0，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/matplotlib__matplotlib-23987`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/matplotlib__matplotlib-23987`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/matplotlib__matplotlib-23987`。

## django__django-15781

仓库：django/django；base：`8d160f154f0240a423e83ffe0690e472f837373c`；映射：fully_mappable。

gold文件：`django/core/management/base.py`。

可映射gold函数：`django/core/management/base.py::BaseCommand.create_parser`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.04 | 89911/449 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 42.03 | 59013/1162 | 5/5 | 5/1 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 139.68 | 67770/1407 | 10/10 | 10/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 160.29 | 72842/1379 | 10/10 | 10/3 |

各臂原始预测与问题：

- D-SIMPLE：`django/core/management/base.py::BaseCommand.create_parser`, `django/core/management/base.py::DjangoHelpFormatter.add_usage`, `django/core/management/base.py::DjangoHelpFormatter.add_arguments`, `django/core/management/base.py::BaseCommand.print_help`, `django/core/management/base.py::DjangoHelpFormatter._reordered_actions`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-15781`。
- D-COSIL：`django/core/management/base.py::DjangoHelpFormatter.add_usage`, `django/core/management/base.py::DjangoHelpFormatter.add_arguments`, `django/core/management/base.py::DjangoHelpFormatter._reordered_actions`, `django/core/management/base.py::BaseCommand.create_parser`, `None`。解析失败5，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-15781`。
- Q-COSIL：`django/core/management/base.py::BaseCommand.print_help`, `django/core/management/base.py::DjangoHelpFormatter.add_usage`, `django/core/management/base.py::BaseCommand.handle`, `django/core/management/base.py::CommandParser.parse_args`, `django/core/management/base.py::DjangoHelpFormatter._reordered_actions`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-15781`。
- Q-PRUNER：`django/core/management/base.py::BaseCommand.print_help`, `django/core/management/base.py::DjangoHelpFormatter.add_usage`, `django/core/management/base.py::CommandParser.parse_args`, `django/core/management/base.py::BaseCommand.handle`, `django/utils/translation/trans_real.py::gettext_noop`。解析失败0，工具错误0，重复输入3，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-15781`。

## django__django-13933

仓库：django/django；base：`42e8cf47c7ee2db238bf91197ea398126c546741`；映射：fully_mappable。

gold文件：`django/forms/models.py`。

可映射gold函数：`django/forms/models.py::ModelChoiceField.to_python`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.62 | 101038/317 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 40.77 | 102759/1593 | 7/7 | 7/5 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 108.35 | 138175/1013 | 3/10 | 3/1 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 125.90 | 136080/998 | 2/10 | 2/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/forms/models.py::ModelChoiceField.to_python`, `None`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-13933`。
- D-COSIL：`django/forms/models.py::ModelChoiceField.to_python`, `None`, `django/forms/models.py::ModelChoiceField.validate`, `django/forms/fields.py::ChoiceField.validate`, `django/forms/models.py::ModelMultipleChoiceField._check_values`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-13933`。
- Q-COSIL：`None`, `django/forms/fields.py::ChoiceField.validate`, `None`, `None`, `None`。解析失败0，工具错误7，重复输入3，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-13933`。
- Q-PRUNER：`None`, `django/forms/fields.py::ChoiceField.validate`, `None`, `None`, `None`。解析失败0，工具错误8，重复输入4，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-13933`。

## psf__requests-3362

仓库：psf/requests；base：`36453b95b13079296776d11b09cab2567ea3e703`；映射：fully_mappable。

gold文件：`requests/utils.py`。

可映射gold函数：`requests/utils.py::stream_decode_response_unicode`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.35 | 17958/246 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 22.52 | 62098/557 | 9/9 | 9/4 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 78.09 | 49604/1078 | 3/10 | 3/3 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 78.57 | 49940/1063 | 3/10 | 3/3 |

各臂原始预测与问题：

- D-SIMPLE：`requests/models.py::Response.iter_content`, `requests/utils.py::stream_decode_response_unicode`, `requests/models.py::Response.text`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/psf__requests-3362`。
- D-COSIL：`requests/models.py::Response.iter_content`, `requests/utils.py::stream_decode_response_unicode`, `requests/models.py::Response.text`, `requests/utils.py::get_encoding_from_headers`, `requests/models.py::Response.apparent_encoding`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/psf__requests-3362`。
- Q-COSIL：`requests/models.py::Response.iter_content`, `None`, `requests/packages/urllib3/response.py::HTTPResponse.stream`, `requests/packages/urllib3/response.py::HTTPResponse.read`, `requests/sessions.py::Session.request`。解析失败0，工具错误7，重复输入7，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/psf__requests-3362`。
- Q-PRUNER：`requests/models.py::Response.iter_content`, `None`, `requests/packages/urllib3/response.py::HTTPResponse.stream`, `requests/packages/urllib3/response.py::HTTPResponse.read`, `requests/sessions.py::Session.request`。解析失败0，工具错误7，重复输入7，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/psf__requests-3362`。

## sympy__sympy-22840

仓库：sympy/sympy；base：`d822fcba181155b85ff2b29fe525adbafb22b448`；映射：fully_mappable。

gold文件：`sympy/simplify/cse_main.py`。

可映射gold函数：`sympy/simplify/cse_main.py::tree_cse`, `sympy/simplify/cse_main.py::tree_cse._find_repeated`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/50.00% | 9.25 | 98279/794 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/50.00% | 193.25 | 137728/1465 | 8/8 | 8/5 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 116.89 | 147432/930 | 5/10 | 5/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 210.34 | 190936/912 | 4/10 | 4/1 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/simplify/cse_main.py::tree_cse`, `sympy/simplify/cse_main.py::opt_cse`, `sympy/simplify/cse_main.py::cse`, `sympy/matrices/expressions/matexpr.py::MatrixExpr.__getitem__`, `sympy/matrices/expressions/matexpr.py::MatrixSymbol._entry`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-22840`。
- D-COSIL：`sympy/simplify/cse_main.py::tree_cse`, `sympy/simplify/cse_main.py::opt_cse`, `sympy/simplify/cse_main.py::cse`, `sympy/matrices/expressions/matexpr.py::MatrixExpr.__getitem__`, `sympy/matrices/expressions/matexpr.py::MatrixSymbol._entry`。解析失败2，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-22840`。
- Q-COSIL：`None`, `None`, `sympy/printing/codeprinter.py::CodePrinter.doprint`, `sympy/utilities/lambdify.py::lambdify`, `None`。解析失败0，工具错误5，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-22840`。
- Q-PRUNER：`None`, `sympy/printing/codeprinter.py::CodePrinter._get_expression_indices`, `None`, `sympy/utilities/lambdify.py::lambdify`, `None`。解析失败0，工具错误6，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-22840`。

## django__django-14855

仓库：django/django；base：`475cffd1d64c690cdad16ede4d5e81985738ceb4`；映射：fully_mappable。

gold文件：`django/contrib/admin/helpers.py`。

可映射gold函数：`django/contrib/admin/helpers.py::AdminReadonlyField.get_admin_url`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.88 | 106050/295 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 171.26 | 66388/1186 | 5/5 | 5/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 128.53 | 92970/1384 | 10/10 | 10/2 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 149.07 | 88349/1339 | 9/10 | 9/1 |

各臂原始预测与问题：

- D-SIMPLE：`django/contrib/admin/helpers.py::AdminReadonlyField.get_admin_url`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-14855`。
- D-COSIL：`django/contrib/admin/helpers.py::AdminReadonlyField.get_admin_url`, `django/contrib/admin/helpers.py::AdminReadonlyField.contents`, `django/contrib/admin/options.py::ModelAdmin.response_add`, `None`, `django/urls/base.py::reverse`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-14855`。
- Q-COSIL：`django/contrib/admin/helpers.py::AdminReadonlyField.get_admin_url`, `None`, `None`, `django/urls/resolvers.py::URLResolver.reverse`。解析失败0，工具错误0，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-14855`。
- Q-PRUNER：`django/contrib/admin/helpers.py::AdminReadonlyField.get_admin_url`, `django/contrib/admin/sites.py::AdminSite.get_urls`, `django/contrib/admin/options.py::ModelAdmin.response_add`, `django/urls/resolvers.py::URLResolver.reverse`。解析失败0，工具错误1，重复输入3，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-14855`。

## pydata__xarray-5131

仓库：pydata/xarray；base：`e56905889c836c736152b11a7e6117a229715975`；映射：fully_mappable。

gold文件：`xarray/core/groupby.py`。

可映射gold函数：`xarray/core/groupby.py::GroupBy.__repr__`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.72 | 27722/247 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 14.26 | 58248/949 | 3/3 | 3/1 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 96.88 | 109689/1193 | 9/10 | 9/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 102.42 | 110028/1147 | 9/10 | 9/0 |

各臂原始预测与问题：

- D-SIMPLE：`xarray/core/groupby.py::GroupBy.__repr__`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/pydata__xarray-5131`。
- D-COSIL：`xarray/core/groupby.py::GroupBy.__repr__`, `None`, `None`, `None`, `xarray/core/formatting.py::format_array_flat`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/pydata__xarray-5131`。
- Q-COSIL：`None`, `xarray/core/groupby.py::DatasetGroupBy.reduce`, `xarray/core/groupby.py::DatasetGroupBy.map`, `xarray/core/groupby.py::DatasetGroupBy.apply`, `xarray/core/groupby.py::DatasetGroupBy._combine`。解析失败0，工具错误1，重复输入5，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/pydata__xarray-5131`。
- Q-PRUNER：`None`, `xarray/core/groupby.py::DatasetGroupBy.reduce`, `xarray/core/groupby.py::DatasetGroupBy.map`, `xarray/core/groupby.py::DatasetGroupBy.apply`, `xarray/core/groupby.py::DatasetGroupBy._combine`。解析失败0，工具错误1，重复输入5，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/pydata__xarray-5131`。

## django__django-11133

仓库：django/django；base：`879cc3da6249e920b8d54518a0ae06de835d7373`；映射：fully_mappable。

gold文件：`django/http/response.py`。

可映射gold函数：`django/http/response.py::HttpResponseBase.make_bytes`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.05 | 86900/198 | 0/0 | 0/0 |
| D-COSIL | failed | 0.00% | 0.00%/0.00% | 6.75 | 5063/740 | 0/0 | 0/0 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 146.74 | 79981/1610 | 8/10 | 6/5 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 125.01 | 23475/1173 | 2/2 | 1/1 |

各臂原始预测与问题：

- D-SIMPLE：`django/http/response.py::HttpResponseBase.make_bytes`, `django/http/response.py::HttpResponse.content`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-11133`。
- D-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-11133`。
- Q-COSIL：`django/utils/encoding.py::force_bytes`, `django/http/response.py::HttpResponse.content`, `None`, `django/utils/encoding.py::smart_bytes`。解析失败0，工具错误2，重复输入4，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-11133`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；Cannot bind exact source function。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-11133`。

## mwaskom__seaborn-2848

仓库：mwaskom/seaborn；base：`94621cef29f80282436d73e8d2c0aa76dab81273`；映射：fully_mappable。

gold文件：`seaborn/_oldcore.py`。

可映射gold函数：`seaborn/_oldcore.py::HueMapping._lookup_single`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.95 | 47343/571 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 23.27 | 83034/1083 | 9/10 | 9/6 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 126.27 | 57864/1771 | 1/10 | 1/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 139.03 | 58428/1771 | 1/10 | 1/0 |

各臂原始预测与问题：

- D-SIMPLE：`seaborn/_oldcore.py::HueMapping._lookup_single`, `seaborn/_oldcore.py::HueMapping.categorical_mapping`, `seaborn/_oldcore.py::HueMapping.__init__`, `seaborn/axisgrid.py::PairGrid._plot_bivariate`, `seaborn/axisgrid.py::PairGrid._plot_bivariate_iter_hue`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/mwaskom__seaborn-2848`。
- D-COSIL：`seaborn/axisgrid.py::PairGrid._plot_bivariate_iter_hue`, `seaborn/_oldcore.py::VectorPlotter.comp_data`, `seaborn/_oldcore.py::VectorPlotter.iter_data`, `seaborn/axisgrid.py::PairGrid.__init__`, `seaborn/_oldcore.py::HueMapping.categorical_mapping`。解析失败0，工具错误1，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/mwaskom__seaborn-2848`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误9，重复输入3，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/mwaskom__seaborn-2848`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误9，重复输入3，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/mwaskom__seaborn-2848`。

## django__django-13265

仓库：django/django；base：`b2b0711b555fa292751763c2df4fe577c396f265`；映射：fully_mappable。

gold文件：`django/db/migrations/autodetector.py`。

可映射gold函数：`django/db/migrations/autodetector.py::MigrationAutodetector._detect_changes`, `django/db/migrations/autodetector.py::MigrationAutodetector.generate_created_models`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/50.00% | 12.09 | 115316/852 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 42.97 | 102210/1478 | 8/9 | 8/6 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 136.71 | 100165/1364 | 10/10 | 10/9 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 153.89 | 102586/1297 | 10/10 | 10/9 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/migrations/autodetector.py::MigrationAutodetector.generate_added_indexes`, `django/db/migrations/autodetector.py::MigrationAutodetector.generate_altered_order_with_respect_to`, `django/db/migrations/autodetector.py::MigrationAutodetector._sort_migrations`, `django/db/migrations/autodetector.py::MigrationAutodetector.check_dependency`, `django/db/migrations/autodetector.py::MigrationAutodetector.generate_created_models`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-13265`。
- D-COSIL：`django/db/migrations/autodetector.py::MigrationAutodetector.generate_added_indexes`, `django/db/migrations/autodetector.py::MigrationAutodetector.generate_altered_order_with_respect_to`, `django/db/migrations/autodetector.py::MigrationAutodetector.check_dependency`, `django/db/migrations/autodetector.py::MigrationAutodetector._sort_migrations`, `django/db/migrations/autodetector.py::MigrationAutodetector.add_operation`。解析失败1，工具错误1，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-13265`。
- Q-COSIL：`django/db/migrations/operations/models.py::AlterOrderWithRespectTo.__init__`, `django/db/migrations/operations/models.py::AlterOrderWithRespectTo.state_forwards`, `django/db/migrations/operations/models.py::AlterOrderWithRespectTo.database_forwards`, `django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.add_index`, `django/db/migrations/executor.py::MigrationExecutor.apply_migration`。解析失败0，工具错误0，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-13265`。
- Q-PRUNER：`django/db/migrations/operations/models.py::AlterOrderWithRespectTo.state_forwards`, `django/db/migrations/operations/models.py::AlterOrderWithRespectTo.database_forwards`, `django/db/backends/base/schema.py::BaseDatabaseSchemaEditor.add_index`, `django/db/migrations/executor.py::MigrationExecutor.apply_migration`, `django/db/migrations/executor.py::MigrationExecutor.migrate`。解析失败0，工具错误0，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-13265`。

## scikit-learn__scikit-learn-14087

仓库：scikit-learn/scikit-learn；base：`a5743ed36fbd3fbc8e351bdab16561fbfca7dfa1`；映射：fully_mappable。

gold文件：`sklearn/linear_model/logistic.py`。

可映射gold函数：`sklearn/linear_model/logistic.py::LogisticRegressionCV.fit`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.85 | 66747/184 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 27.85 | 162736/1568 | 7/7 | 7/3 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 72.76 | 147814/683 | 5/10 | 5/5 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 82.47 | 145379/673 | 5/10 | 5/5 |

各臂原始预测与问题：

- D-SIMPLE：`sklearn/linear_model/logistic.py::LogisticRegressionCV.fit`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/scikit-learn__scikit-learn-14087`。
- D-COSIL：`sklearn/linear_model/logistic.py::LogisticRegressionCV.fit`, `sklearn/linear_model/logistic.py::_log_reg_scoring_path`, `sklearn/linear_model/logistic.py::_logistic_regression_path`, `sklearn/linear_model/logistic.py::_check_multi_class`, `sklearn/linear_model/logistic.py::LogisticRegression.fit`。解析失败2，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/scikit-learn__scikit-learn-14087`。
- Q-COSIL：`sklearn/linear_model/logistic.py::LogisticRegressionCV.fit`, `sklearn/linear_model/logistic.py::_log_reg_scoring_path`, `sklearn/linear_model/logistic.py::_logistic_regression_path`, `sklearn/model_selection/_validation.py::_fit_and_score`, `sklearn/utils/validation.py::check_array`。解析失败0，工具错误5，重复输入7，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/scikit-learn__scikit-learn-14087`。
- Q-PRUNER：`sklearn/linear_model/logistic.py::LogisticRegressionCV.fit`, `sklearn/linear_model/logistic.py::_log_reg_scoring_path`, `sklearn/linear_model/logistic.py::_logistic_regression_path`, `sklearn/model_selection/_validation.py::_fit_and_score`, `sklearn/utils/validation.py::check_array`。解析失败0，工具错误5，重复输入7，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/scikit-learn__scikit-learn-14087`。

## sympy__sympy-15678

仓库：sympy/sympy；base：`31c68eef3ffef39e2e792b0ec92cd92b7010eb2a`；映射：fully_mappable。

gold文件：`sympy/geometry/util.py`。

可映射gold函数：`sympy/geometry/util.py::idiff`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.42 | 61999/226 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 35.82 | 88318/1498 | 3/3 | 3/2 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 182.96 | 11925/2376 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 270.78 | 11925/2376 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/geometry/util.py::idiff`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-15678`。
- D-COSIL：`sympy/geometry/util.py::idiff`, `sympy/core/function.py::AppliedUndef._diff_wrt`, `sympy/core/relational.py::Equality.__new__`, `sympy/core/relational.py::Relational.lhs`, `sympy/solvers/solvers.py::solve`。解析失败7，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-15678`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；Truncated or rejected model response。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-15678`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；Truncated or rejected model response。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-15678`。

## django__django-14017

仓库：django/django；base：`466920f6d726eee90d5566e0a9948e92b33a122e`；映射：fully_mappable。

gold文件：`django/db/models/query_utils.py`。

可映射gold函数：`django/db/models/query_utils.py::Q._combine`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.03 | 97081/392 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 38.99 | 107474/1640 | 6/6 | 6/5 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 134.44 | 152047/1351 | 4/7 | 4/2 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 153.53 | 152027/1331 | 4/7 | 4/2 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/models/query_utils.py::Q._combine`, `django/db/models/query_utils.py::Q.__and__`, `django/db/models/expressions.py::Combinable.__rand__`, `django/db/models/expressions.py::Combinable.__and__`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-14017`。
- D-COSIL：`django/db/models/expressions.py::Combinable.__rand__`, `django/db/models/query_utils.py::Q._combine`, `django/db/models/query_utils.py::Q.__and__`, `django/db/models/expressions.py::Combinable.__and__`, `django/db/models/query_utils.py::Q.__or__`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-14017`。
- Q-COSIL：`None`, `django/db/models/query.py::QuerySet.__and__`, `django/db/models/query.py::QuerySet.__or__`, `django/db/models/query_utils.py::Q.__and__`, `django/db/models/query_utils.py::Q.__or__`。解析失败3，工具错误3，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-14017`。
- Q-PRUNER：`None`, `django/db/models/query.py::QuerySet.__and__`, `django/db/models/query.py::QuerySet.__or__`, `django/db/models/query_utils.py::Q.__and__`, `django/db/models/query_utils.py::Q.__or__`。解析失败3，工具错误3，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-14017`。

## matplotlib__matplotlib-24970

仓库：matplotlib/matplotlib；base：`a3011dfd1aaa2487cce8aa7369475533133ef777`；映射：fully_mappable。

gold文件：`lib/matplotlib/colors.py`。

可映射gold函数：`lib/matplotlib/colors.py::Colormap.__call__`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.79 | 108814/173 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 21.27 | 74335/1288 | 5/5 | 5/2 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 22.86 | 5663/283 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 34.12 | 5663/283 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`lib/matplotlib/colors.py::Colormap.__call__`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/matplotlib__matplotlib-24970`。
- D-COSIL：`lib/matplotlib/colors.py::Colormap.__call__`, `lib/matplotlib/colors.py::Colormap.__init__`, `lib/matplotlib/colors.py::Colormap._set_extremes`, `lib/matplotlib/colors.py::Colormap.set_extremes`, `lib/matplotlib/colors.py::Colormap._init`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/matplotlib__matplotlib-24970`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/matplotlib__matplotlib-24970`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/matplotlib__matplotlib-24970`。

## matplotlib__matplotlib-26020

仓库：matplotlib/matplotlib；base：`f6a781f77f5ddf1204c60ca7c544809407d4a807`；映射：partially_mappable。

gold文件：`lib/mpl_toolkits/axes_grid1/axes_grid.py`。

可映射gold函数：`lib/mpl_toolkits/axes_grid1/axes_grid.py::_tick_only`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 11.36 | 174917/732 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 27.46 | 174468/1784 | 7/7 | 7/5 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 50.45 | 11059/584 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 62.06 | 11059/584 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`lib/mpl_toolkits/axes_grid1/axes_grid.py::_tick_only`, `lib/mpl_toolkits/axes_grid1/axes_grid.py::Grid.set_label_mode`, `lib/mpl_toolkits/axes_grid1/axes_grid.py::Grid.__init__`, `lib/mpl_toolkits/axes_grid1/mpl_axes.py::Axes.axis`, `lib/mpl_toolkits/axes_grid1/mpl_axes.py::Axes.clear`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/matplotlib__matplotlib-26020`。
- D-COSIL：`lib/mpl_toolkits/axes_grid1/axes_grid.py::_tick_only`, `lib/mpl_toolkits/axes_grid1/axes_grid.py::Grid.set_label_mode`, `lib/mpl_toolkits/axes_grid1/axes_grid.py::Grid.__init__`, `lib/mpl_toolkits/axes_grid1/mpl_axes.py::Axes.axis`, `lib/mpl_toolkits/axes_grid1/mpl_axes.py::SimpleAxisArtist.toggle`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/matplotlib__matplotlib-26020`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/matplotlib__matplotlib-26020`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/matplotlib__matplotlib-26020`。

## django__django-16820

仓库：django/django；base：`c61219a7ae051d2baab53f041e00592011fc550c`；映射：fully_mappable。

gold文件：`django/db/migrations/operations/models.py`。

可映射gold函数：`django/db/migrations/operations/models.py::CreateModel.reduce`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 0.00%/0.00% | 9.54 | 118779/936 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 0.00%/0.00% | 47.79 | 100555/2036 | 7/8 | 7/7 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 21.36 | 5206/234 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 52.15 | 5206/234 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/migrations/autodetector.py::MigrationAutodetector.create_altered_indexes`, `django/db/migrations/autodetector.py::MigrationAutodetector._generate_removed_altered_foo_together`, `django/db/migrations/autodetector.py::MigrationAutodetector.generate_removed_altered_index_together`, `django/db/migrations/autodetector.py::MigrationAutodetector.generate_altered_index_together`, `django/db/migrations/autodetector.py::MigrationAutodetector._get_altered_foo_together_operations`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-16820`。
- D-COSIL：`None`, `django/db/migrations/operations/models.py::AlterTogetherOptionOperation.can_reduce_through`, `django/db/migrations/operations/models.py::AddIndex.reduce`, `django/db/migrations/operations/models.py::AlterTogetherOptionOperation.state_forwards`, `django/db/migrations/optimizer.py::MigrationOptimizer.optimize_inner`。解析失败1，工具错误1，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-16820`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-16820`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-16820`。

## sympy__sympy-13895

仓库：sympy/sympy；base：`4da0b64558e9551a11a99bccc63557ba34f50c58`；映射：fully_mappable。

gold文件：`sympy/core/numbers.py`。

可映射gold函数：`sympy/core/numbers.py::Integer._eval_power`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 0.00% | 0.00%/0.00% | 9.85 | 130814/757 | 0/0 | 0/0 |
| D-COSIL | failed | 0.00% | 0.00%/0.00% | 24.19 | 31390/2139 | 2/2 | 2/1 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 87.57 | 99566/1008 | 0/0 | 0/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 151.36 | 99566/1008 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/simplify/powsimp.py::powsimp`, `sympy/core/power.py::Pow._eval_power`, `sympy/simplify/simplify.py::simplify`, `sympy/core/mul.py::Mul.flatten`, `sympy/core/power.py::Pow.__new__`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-13895`。
- D-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；Semantic retry disabled。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-13895`。
- Q-COSIL：`sympy/simplify/simplify.py::simplify`, `None`, `None`, `sympy/integrals/integrals.py::integrate`, `None`。解析失败10，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-13895`。
- Q-PRUNER：`sympy/simplify/simplify.py::simplify`, `None`, `None`, `sympy/integrals/integrals.py::integrate`, `None`。解析失败10，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-13895`。

## django__django-10924

仓库：django/django；base：`bceadd2788dc2dad53eba0caae172bd8522fd483`；映射：fully_mappable。

gold文件：`django/db/models/fields/__init__.py`。

可映射gold函数：`django/db/models/fields/__init__.py::FilePathField.formfield`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.76 | 119476/512 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 179.69 | 144574/1651 | 8/8 | 8/5 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 95.98 | 60675/944 | 4/10 | 4/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 119.42 | 60986/929 | 4/10 | 4/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/models/fields/__init__.py::FilePathField.__init__`, `django/db/models/fields/__init__.py::FilePathField.deconstruct`, `django/db/models/fields/__init__.py::FilePathField.formfield`, `django/forms/fields.py::FilePathField.__init__`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-10924`。
- D-COSIL：`django/db/models/fields/__init__.py::FilePathField.__init__`, `django/forms/fields.py::FilePathField.__init__`, `django/db/models/fields/__init__.py::FilePathField.deconstruct`, `django/db/models/fields/__init__.py::FilePathField.formfield`, `django/db/migrations/serializer.py::DeconstructableSerializer.serialize_deconstructed`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-10924`。
- Q-COSIL：`None`, `None`, `django/core/checks/model_checks.py::check_all_models`, `django/utils/translation/__init__.py::gettext_noop`, `django/utils/translation/__init__.py::gettext`。解析失败0，工具错误6，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-10924`。
- Q-PRUNER：`None`, `None`, `django/core/checks/model_checks.py::check_all_models`, `django/utils/translation/__init__.py::gettext_noop`, `django/utils/translation/__init__.py::gettext`。解析失败0，工具错误6，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-10924`。

## sympy__sympy-14774

仓库：sympy/sympy；base：`8fc63c2d71752389a44367b8ef4aba8a91af6a45`；映射：fully_mappable。

gold文件：`sympy/printing/latex.py`。

可映射gold函数：`sympy/printing/latex.py::LatexPrinter._print_Function`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.47 | 79566/212 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 28.24 | 102974/1001 | 4/4 | 4/2 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 125.48 | 155840/1176 | 0/10 | 0/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 171.08 | 155840/1176 | 0/10 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/printing/latex.py::LatexPrinter._print_Function`, `sympy/physics/vector/printing.py::VectorLatexPrinter._print_Function`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-14774`。
- D-COSIL：`sympy/printing/latex.py::LatexPrinter._print_Function`, `None`, `sympy/printing/latex.py::LatexPrinter._hprint_Function`, `None`, `None`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-14774`。
- Q-COSIL：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误10，重复输入4，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-14774`。
- Q-PRUNER：`None`, `None`, `None`, `None`, `None`。解析失败0，工具错误10，重复输入4，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-14774`。

## sympy__sympy-21055

仓库：sympy/sympy；base：`748ce73479ee2cd5c861431091001cc18943c735`；映射：unmappable。

gold文件：`sympy/assumptions/refine.py`。

可映射gold函数：NA。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | NOT_RUN/NA/NOT_RUN/NA | 9.58 | 112208/548 | 0/0 | 0/0 |
| D-COSIL | complete | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 62.10 | 93624/1923 | 10/10 | 8/3 |
| Q-COSIL | complete | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 127.22 | 182567/1113 | 4/10 | 4/3 |
| Q-PRUNER | complete | 0.00% | NOT_RUN/NA/NOT_RUN/NA | 205.99 | 160508/1078 | 7/10 | 7/2 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/assumptions/refine.py::refine`, `sympy/assumptions/refine.py::refine_abs`, `sympy/functions/elementary/complexes.py::arg.eval`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-21055`。
- D-COSIL：`sympy/assumptions/handlers/calculus.py::_`, `sympy/functions/elementary/complexes.py::arg.eval`, `sympy/functions/elementary/complexes.py::Abs.eval`, `sympy/assumptions/handlers/common.py::_`, `sympy/functions/elementary/complexes.py::arg._eval_rewrite_as_atan2`。解析失败0，工具错误0，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-21055`。
- Q-COSIL：`sympy/integrals/integrals.py::Integral.doit`, `sympy/functions/elementary/trigonometric.py::sin._eval_rewrite_as_exp`, `None`, `None`, `None`。解析失败0，工具错误6，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-21055`。
- Q-PRUNER：`sympy/integrals/integrals.py::Integral.doit`, `None`, `None`, `sympy/functions/elementary/exponential.py::exp._eval_refine`, `None`。解析失败0，工具错误3，重复输入4，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-21055`。

## sympy__sympy-16281

仓库：sympy/sympy；base：`41490b75f3621408e0468b0e7b6dc409601fc6ff`；映射：fully_mappable。

gold文件：`sympy/printing/pretty/pretty.py`。

可映射gold函数：`sympy/printing/pretty/pretty.py::PrettyPrinter._print_Product`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.82 | 96505/385 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 51.14 | 111012/1272 | 7/7 | 7/6 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 132.58 | 152151/1173 | 8/10 | 8/6 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 199.01 | 159971/1169 | 8/10 | 8/8 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/printing/pretty/pretty.py::PrettyPrinter._print_Product`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-16281`。
- D-COSIL：`sympy/printing/pretty/pretty.py::PrettyPrinter._print_Product`, `sympy/printing/pretty/pretty.py::PrettyPrinter._print_Sum`, `sympy/printing/pretty/stringpict.py::stringPict.stack`, `sympy/printing/pretty/stringpict.py::stringPict.above`, `sympy/printing/pretty/pretty_symbology.py::xobj`。解析失败2，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-16281`。
- Q-COSIL：`sympy/printing/pretty/pretty.py::PrettyPrinter._print_Product`, `None`, `None`, `sympy/printing/pretty/pretty_symbology.py::pretty_use_unicode`。解析失败0，工具错误2，重复输入5，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-16281`。
- Q-PRUNER：`sympy/printing/pretty/pretty.py::PrettyPrinter._print_Product`, `None`, `sympy/printing/pretty/pretty_symbology.py::pretty_use_unicode`, `sympy/concrete/products.py::Product._eval_rewrite_as_Sum`。解析失败0，工具错误2，重复输入6，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-16281`。

## django__django-12286

仓库：django/django；base：`979f61abd322507aafced9627702362e541ec34e`；映射：partially_mappable。

gold文件：`django/core/checks/translation.py`。

可映射gold函数：`django/core/checks/translation.py::check_language_settings_consistent`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.56 | 97149/372 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 176.29 | 59139/1377 | 8/8 | 8/3 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 130.75 | 48124/1360 | 2/10 | 2/0 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 152.79 | 48713/1355 | 2/10 | 2/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/core/checks/translation.py::check_language_settings_consistent`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-12286`。
- D-COSIL：`django/core/checks/translation.py::check_language_settings_consistent`, `django/utils/translation/trans_real.py::get_supported_language_variant`, `django/utils/translation/__init__.py::get_supported_language_variant`, `django/utils/translation/trans_real.py::check_for_language`, `django/utils/translation/trans_real.py::get_languages`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-12286`。
- Q-COSIL：`django/core/checks/translation.py::check_setting_language_code`, `django/utils/translation/trans_real.py::translation`, `None`, `django/middleware/locale.py::LocaleMiddleware.process_request`, `None`。解析失败0，工具错误8，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-12286`。
- Q-PRUNER：`django/core/checks/translation.py::check_setting_language_code`, `django/utils/translation/trans_real.py::translation`, `None`, `django/middleware/locale.py::LocaleMiddleware.process_request`, `None`。解析失败0，工具错误8，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-12286`。

## sympy__sympy-16792

仓库：sympy/sympy；base：`09786a173e7a0a488f46dd6000177c23e5d24eed`；映射：partially_mappable。

gold文件：`sympy/utilities/codegen.py`。

可映射gold函数：`sympy/utilities/codegen.py::CodeGen.routine`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.67 | 111232/534 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 186.52 | 136194/1543 | 7/7 | 7/6 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 143.75 | 129323/1239 | 9/10 | 9/7 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 198.52 | 125202/1170 | 7/10 | 7/7 |

各臂原始预测与问题：

- D-SIMPLE：`sympy/utilities/codegen.py::CodeGen.routine`, `sympy/utilities/codegen.py::CCodeGen.get_prototype`, `sympy/utilities/autowrap.py::CythonCodeWrapper._partition_args`, `sympy/utilities/autowrap.py::CythonCodeWrapper._prototype_arg`, `sympy/utilities/autowrap.py::CythonCodeWrapper.dump_pyx`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sympy__sympy-16792`。
- D-COSIL：`sympy/utilities/codegen.py::CodeGen.routine`, `sympy/utilities/codegen.py::CCodeGen.get_prototype`, `sympy/utilities/autowrap.py::CythonCodeWrapper._prototype_arg`, `sympy/utilities/codegen.py::Routine.__init__`, `sympy/utilities/autowrap.py::CythonCodeWrapper._declare_arg`。解析失败3，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sympy__sympy-16792`。
- Q-COSIL：`sympy/utilities/autowrap.py::autowrap`, `None`, `None`, `None`, `None`。解析失败0，工具错误1，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sympy__sympy-16792`。
- Q-PRUNER：`sympy/utilities/autowrap.py::autowrap`, `None`, `None`, `None`, `None`。解析失败0，工具错误3，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sympy__sympy-16792`。

## django__django-12747

仓库：django/django；base：`c86201b6ed4f8256b0a0520c08aa674f623d4127`；映射：fully_mappable。

gold文件：`django/db/models/deletion.py`。

可映射gold函数：`django/db/models/deletion.py::Collector.delete`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.87 | 100648/274 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 182.70 | 131411/1283 | 10/10 | 10/4 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 99.78 | 93937/975 | 10/10 | 10/3 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 111.35 | 96916/919 | 8/10 | 8/7 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/models/deletion.py::Collector.delete`, `django/db/models/query.py::QuerySet.delete`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-12747`。
- D-COSIL：`django/db/models/deletion.py::Collector.delete`, `django/db/models/deletion.py::Collector.collect`, `django/db/models/deletion.py::Collector.can_fast_delete`, `django/db/models/query.py::QuerySet.delete`, `django/db/models/deletion.py::Collector.get_del_batches`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-12747`。
- Q-COSIL：`django/db/models/query.py::QuerySet.delete`, `django/db/models/deletion.py::Collector.delete`, `django/db/models/deletion.py::Collector.collect`, `django/db/models/deletion.py::get_candidate_relations_to_delete`, `django/db/models/deletion.py::Collector.can_fast_delete`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-12747`。
- Q-PRUNER：`django/db/models/query.py::QuerySet.delete`, `django/db/models/deletion.py::Collector.delete`, `django/db/models/deletion.py::Collector.collect`, `django/db/models/deletion.py::get_candidate_relations_to_delete`, `django/dispatch/dispatcher.py::Signal.has_listeners`。解析失败0，工具错误2，重复输入2，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-12747`。

## django__django-16046

仓库：django/django；base：`ec13e801b820614ff374cb0046092caab8d67249`；映射：fully_mappable。

gold文件：`django/utils/numberformat.py`。

可映射gold函数：`django/utils/numberformat.py::format`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 7.57 | 76154/190 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 171.78 | 45065/1139 | 5/5 | 5/3 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 108.48 | 117225/929 | 10/10 | 10/10 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 118.55 | 121195/879 | 10/10 | 10/10 |

各臂原始预测与问题：

- D-SIMPLE：`django/utils/numberformat.py::format`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-16046`。
- D-COSIL：`django/utils/numberformat.py::format`, `django/utils/formats.py::number_format`, `django/contrib/admin/utils.py::display_for_field`, `django/contrib/admin/utils.py::display_for_value`, `django/utils/formats.py::localize_input`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-16046`。
- Q-COSIL：`django/utils/numberformat.py::format`, `django/contrib/admin/views/main.py::ChangeList.get_results`, `django/contrib/admin/views/main.py::ChangeList._get_deterministic_ordering`, `django/contrib/admin/views/main.py::ChangeList.get_queryset`, `django/contrib/admin/views/main.py::ChangeList.apply_select_related`。解析失败0，工具错误0，重复输入9，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-16046`。
- Q-PRUNER：`django/utils/numberformat.py::format`, `django/contrib/admin/views/main.py::ChangeList.get_results`, `django/contrib/admin/views/main.py::ChangeList._get_deterministic_ordering`, `django/contrib/admin/views/main.py::ChangeList.get_queryset`, `django/contrib/admin/views/main.py::ChangeList.apply_select_related`。解析失败0，工具错误0，重复输入9，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-16046`。

## pytest-dev__pytest-9359

仓库：pytest-dev/pytest；base：`e2ee3144ed6e241dea8d96215fcdca18b3892551`；映射：fully_mappable。

gold文件：`src/_pytest/_code/source.py`。

可映射gold函数：`src/_pytest/_code/source.py::get_statement_startend2`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.47 | 55462/680 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 23.57 | 77670/1795 | 6/6 | 6/6 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 24.20 | 2814/317 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 27.18 | 2814/317 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`src/_pytest/_code/source.py::get_statement_startend2`, `src/_pytest/_code/source.py::getstatementrange_ast`, `src/_pytest/_code/code.py::TracebackEntry.getsource`, `src/_pytest/_code/code.py::FormattedExcinfo._getentrysource`, `src/_pytest/_code/code.py::FormattedExcinfo.repr_traceback_entry`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/pytest-dev__pytest-9359`。
- D-COSIL：`src/_pytest/_code/source.py::get_statement_startend2`, `src/_pytest/_code/source.py::getstatementrange_ast`, `src/_pytest/_code/code.py::TracebackEntry.getsource`, `src/_pytest/_code/source.py::Source.getstatementrange`, `src/_pytest/_code/code.py::FormattedExcinfo.get_source`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/pytest-dev__pytest-9359`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/pytest-dev__pytest-9359`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/pytest-dev__pytest-9359`。

## django__django-16408

仓库：django/django；base：`ef85b6bf0bc5a8b194f0724cf5bbedbcee402b96`；映射：partially_mappable。

gold文件：`django/db/models/sql/compiler.py`。

可映射gold函数：`django/db/models/sql/compiler.py::SQLCompiler.get_related_selections`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.90 | 150623/891 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 55.02 | 156616/2086 | 9/9 | 9/6 |
| Q-COSIL | complete | 100.00% | 0.00%/0.00% | 148.42 | 106319/1532 | 10/10 | 10/4 |
| Q-PRUNER | complete | 100.00% | 0.00%/0.00% | 162.12 | 110563/1487 | 2/10 | 2/2 |

各臂原始预测与问题：

- D-SIMPLE：`django/db/models/sql/compiler.py::SQLCompiler.get_related_selections`, `django/db/models/query.py::ModelIterable.__iter__`, `django/db/models/sql/query.py::Query.setup_joins`, `django/db/models/sql/query.py::Query.names_to_path`, `django/db/models/sql/query.py::Query.join`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-16408`。
- D-COSIL：`django/db/models/sql/query.py::Query.names_to_path`, `django/db/models/sql/query.py::Query.setup_joins`, `django/db/models/sql/compiler.py::SQLCompiler.get_related_selections`, `django/db/models/sql/query.py::Query.join`, `django/db/models/sql/query.py::Query.table_alias`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-16408`。
- Q-COSIL：`django/db/models/query.py::QuerySet._prefetch_related_objects`, `django/db/models/query.py::QuerySet.select_related`, `django/db/models/fields/related.py::RelatedField.get_forward_related_filter`, `django/db/models/fields/related.py::RelatedField.get_reverse_related_filter`, `django/db/models/query.py::QuerySet.prefetch_related`。解析失败0，工具错误0，重复输入6，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-16408`。
- Q-PRUNER：`django/db/models/query.py::QuerySet._prefetch_related_objects`, `None`, `None`, `None`, `None`。解析失败0，工具错误8，重复输入4，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-16408`。

## django__django-15790

仓库：django/django；base：`c627226d05dd52aef59447dcfb29cec2c2b11b8a`；映射：fully_mappable。

gold文件：`django/core/checks/templates.py`。

可映射gold函数：`django/core/checks/templates.py::check_for_template_tags_with_the_same_name`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.81 | 77706/389 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 177.88 | 51202/1388 | 5/5 | 5/5 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 141.17 | 65341/1459 | 5/10 | 5/0 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 152.74 | 67178/1434 | 5/10 | 5/0 |

各臂原始预测与问题：

- D-SIMPLE：`django/core/checks/templates.py::check_for_template_tags_with_the_same_name`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/django__django-15790`。
- D-COSIL：`django/core/checks/templates.py::check_for_template_tags_with_the_same_name`, `django/template/backends/django.py::get_template_tag_modules`, `django/template/backends/django.py::get_installed_libraries`, `django/template/backends/django.py::DjangoTemplates.get_templatetag_libraries`, `django/template/backends/django.py::get_package_libraries`。解析失败5，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/django__django-15790`。
- Q-COSIL：`None`, `django/template/backends/base.py::BaseEngine.get_template`, `None`, `None`。解析失败0，工具错误5，重复输入3，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/django__django-15790`。
- Q-PRUNER：`None`, `django/template/backends/base.py::BaseEngine.get_template`, `None`, `None`。解析失败0，工具错误5，重复输入3，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/django__django-15790`。

## sphinx-doc__sphinx-8627

仓库：sphinx-doc/sphinx；base：`332d80ba8433aea41c3709fa52737ede4405072b`；映射：partially_mappable。

gold文件：`sphinx/util/typing.py`。

可映射gold函数：`sphinx/util/typing.py::restify`, `sphinx/util/typing.py::stringify`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 9.07 | 98471/724 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/50.00% | 21.47 | 100837/1489 | 2/2 | 2/2 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 86.06 | 73622/1079 | 7/10 | 7/1 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 91.77 | 78871/1026 | 5/10 | 5/4 |

各臂原始预测与问题：

- D-SIMPLE：`sphinx/util/typing.py::_restify_py37`, `sphinx/util/typing.py::restify`, `sphinx/util/typing.py::_stringify_py37`, `sphinx/util/typing.py::stringify`, `sphinx/domains/python.py::builtin_resolver`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sphinx-doc__sphinx-8627`。
- D-COSIL：`sphinx/util/typing.py::_restify_py37`, `sphinx/util/typing.py::restify`, `sphinx/domains/python.py::type_to_xref`, `sphinx/domains/python.py::_parse_annotation`, `sphinx/ext/autodoc/typehints.py::record_typehints`。解析失败8，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sphinx-doc__sphinx-8627`。
- Q-COSIL：`None`, `sphinx/domains/python.py::_parse_annotation`, `sphinx/domains/python.py::type_to_xref`, `sphinx/util/inspect.py::Signature.format_annotation`, `sphinx/util/inspect.py::Signature.format_annotation_new`。解析失败0，工具错误3，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sphinx-doc__sphinx-8627`。
- Q-PRUNER：`None`, `sphinx/domains/python.py::_parse_annotation`, `sphinx/domains/python.py::type_to_xref`, `sphinx/util/inspect.py::signature`, `None`。解析失败0，工具错误5，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sphinx-doc__sphinx-8627`。

## pytest-dev__pytest-11143

仓库：pytest-dev/pytest；base：`6995257cf470d2143ad1683824962de4071c0eb7`；映射：fully_mappable。

gold文件：`src/_pytest/assertion/rewrite.py`。

可映射gold函数：`src/_pytest/assertion/rewrite.py::AssertionRewriter.run`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.00 | 46831/255 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 28.70 | 151486/2555 | 7/7 | 7/5 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 52.75 | 3814/671 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 54.85 | 3814/671 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`src/_pytest/assertion/rewrite.py::AssertionRewriter.run`, `src/_pytest/assertion/rewrite.py::AssertionRewriter.is_rewrite_disabled`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/pytest-dev__pytest-11143`。
- D-COSIL：`src/_pytest/assertion/rewrite.py::AssertionRewriter.run`, `src/_pytest/assertion/rewrite.py::AssertionRewriter.is_rewrite_disabled`, `src/_pytest/assertion/rewrite.py::rewrite_asserts`, `src/_pytest/assertion/rewrite.py::_rewrite_test`, `None`。解析失败2，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/pytest-dev__pytest-11143`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/pytest-dev__pytest-11143`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/pytest-dev__pytest-11143`。

## sphinx-doc__sphinx-8282

仓库：sphinx-doc/sphinx；base：`2c2335bbb8af99fa132e1573bbf45dc91584d5a2`；映射：fully_mappable。

gold文件：`sphinx/ext/autodoc/__init__.py`。

可映射gold函数：`sphinx/ext/autodoc/__init__.py::ClassDocumenter.format_signature`, `sphinx/ext/autodoc/__init__.py::FunctionDocumenter.format_signature`, `sphinx/ext/autodoc/__init__.py::MethodDocumenter.format_signature`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 8.07 | 81682/567 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/66.67% | 24.13 | 72977/1915 | 6/6 | 6/5 |
| Q-COSIL | complete | 0.00% | 0.00%/0.00% | 62.60 | 72766/758 | 9/10 | 9/1 |
| Q-PRUNER | complete | 0.00% | 0.00%/0.00% | 71.33 | 76720/734 | 9/10 | 9/2 |

各臂原始预测与问题：

- D-SIMPLE：`sphinx/ext/autodoc/__init__.py::FunctionDocumenter.format_signature`, `sphinx/ext/autodoc/__init__.py::MethodDocumenter.format_signature`, `sphinx/ext/autodoc/__init__.py::ClassDocumenter.format_signature`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/sphinx-doc__sphinx-8282`。
- D-COSIL：`sphinx/ext/autodoc/__init__.py::FunctionDocumenter.format_signature`, `sphinx/ext/autodoc/__init__.py::FunctionDocumenter.format_args`, `sphinx/ext/autodoc/__init__.py::ClassDocumenter.format_signature`, `sphinx/util/inspect.py::stringify_signature`, `sphinx/ext/autodoc/__init__.py::ClassDocumenter.get_overloaded_signatures`。解析失败1，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/sphinx-doc__sphinx-8282`。
- Q-COSIL：`sphinx/ext/autodoc/typehints.py::record_typehints`, `sphinx/domains/python.py::_parse_annotation`, `sphinx/ext/autodoc/directive.py::process_documenter_options`, `sphinx/ext/autodoc/importer.py::import_object`, `None`。解析失败0，工具错误1，重复输入1，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/sphinx-doc__sphinx-8282`。
- Q-PRUNER：`sphinx/ext/autodoc/typehints.py::record_typehints`, `None`, `sphinx/ext/autodoc/directive.py::process_documenter_options`, `sphinx/ext/autodoc/importer.py::import_module`, `sphinx/ext/autodoc/importer.py::import_object`。解析失败0，工具错误1，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/sphinx-doc__sphinx-8282`。

## pytest-dev__pytest-7432

仓库：pytest-dev/pytest；base：`e6e300e729dd33956e5448d8be9a0b1540b4e53a`；映射：fully_mappable。

gold文件：`src/_pytest/skipping.py`。

可映射gold函数：`src/_pytest/skipping.py::pytest_runtest_makereport`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.56 | 21063/184 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 12.87 | 43264/942 | 3/3 | 3/1 |
| Q-COSIL | complete | 100.00% | 100.00%/100.00% | 73.72 | 81651/917 | 9/10 | 9/9 |
| Q-PRUNER | complete | 100.00% | 100.00%/100.00% | 76.65 | 80580/899 | 9/10 | 9/9 |

各臂原始预测与问题：

- D-SIMPLE：`src/_pytest/skipping.py::pytest_runtest_makereport`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/pytest-dev__pytest-7432`。
- D-COSIL：`src/_pytest/skipping.py::pytest_runtest_makereport`, `src/_pytest/skipping.py::pytest_runtest_setup`, `src/_pytest/skipping.py::evaluate_skip_marks`, `src/_pytest/skipping.py::pytest_report_teststatus`, `src/_pytest/reports.py::TestReport.from_item_and_call`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/pytest-dev__pytest-7432`。
- Q-COSIL：`src/_pytest/skipping.py::pytest_runtest_makereport`, `None`, `None`, `None`, `None`。解析失败0，工具错误1，重复输入8，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/pytest-dev__pytest-7432`。
- Q-PRUNER：`src/_pytest/skipping.py::pytest_runtest_makereport`, `None`, `None`, `None`, `None`。解析失败0，工具错误1，重复输入8，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/pytest-dev__pytest-7432`。

## pallets__flask-5063

仓库：pallets/flask；base：`182ce3dd15dfa3537391c3efaf9c3ff407d134d4`；映射：partially_mappable。

gold文件：`src/flask/cli.py`。

可映射gold函数：`src/flask/cli.py::routes_command`。

| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |
|---|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | complete | 100.00% | 100.00%/100.00% | 6.86 | 52924/271 | 0/0 | 0/0 |
| D-COSIL | complete | 100.00% | 100.00%/100.00% | 21.72 | 83485/1342 | 8/8 | 8/4 |
| Q-COSIL | failed | 0.00% | 0.00%/0.00% | 16.54 | 792/230 | 0/0 | 0/0 |
| Q-PRUNER | failed | 0.00% | 0.00%/0.00% | 15.81 | 792/230 | 0/0 | 0/0 |

各臂原始预测与问题：

- D-SIMPLE：`src/flask/cli.py::routes_command`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=True。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-SIMPLE/pallets__flask-5063`。
- D-COSIL：`src/flask/cli.py::routes_command`, `src/flask/blueprints.py::BlueprintSetupState.add_url_rule`, `src/flask/blueprints.py::Blueprint.register`, `src/flask/app.py::Flask.add_url_rule`, `src/flask/scaffold.py::Scaffold.add_url_rule`。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/D-COSIL/pallets__flask-5063`。
- Q-COSIL：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-COSIL/pallets__flask-5063`。
- Q-PRUNER：空。解析失败0，工具错误0，重复输入0，agent无源码仍定位=False；CoSIL semantic format retry disabled by protocol。证据：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_v1/runs/20261021_nonthinking_v3/lite_pilot/Q-PRUNER/pallets__flask-5063`。

