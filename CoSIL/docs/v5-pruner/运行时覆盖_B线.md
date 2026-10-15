# Lite 300 运行时覆盖：B线

更新时间：2026-10-14T15:10:47.157772+08:00。已永久落盘 300/300 题，可用于双证据过滤 133 题。其余已完成题保持纯静态标记；未完成题尚无覆盖证据。

实际启动测试 runner 299 题；1 题在准备阶段止步。完成数、runner 启动数、全部预期失败成功复现数和双证据可用数是不同统计口径。

## 采集与资格

可启动的题在隔离的 base commit clone 中仅应用 benchmark test_patch，未应用生产修复。FAIL_TO_PASS 按原测试身份执行；Django 使用原生 unittest runner，其他项目使用 pytest；SymPy 使用精确测试函数选择的 pytest 兼容后端，区别于官方 bin/test，差异逐题记录。依赖、checkout、test_patch 或 runner 准备失败的题会在相应阶段止步；落盘数不代表全部题的测试都成功启动。

证据来自实际 Python 解释器的 sys.setprofile call 事件。pytest/unittest 记录测试身份与真实阶段，只接受 FAIL_TO_PASS 在 test call 中失败；Django 非断言错误还必须有项目生产 traceback。setup/teardown、collection、依赖、导入、timeout、硬退出、未覆盖现存金标等分别保留，不能冒充成功覆盖。

覆盖函数集是实际失败测试上下文的进入函数与进程 bootstrap 函数的保守并集。AST 只把已观察到的 entry 映射为 base commit 的 path::Qualified.name@def_line，不会生成运行时事件。正式资格要求所有预期失败测试被复现、现存函数金标覆盖完整、源码导入来自隔离 base clone、test_patch 未碰生产源码、测试完整退出。

Docker 客户端存在但 socket 实际权限不足（包括已审批的执行检查），因此采用隔离本地环境。官方 SWE-bench harness 固定为 v4.1.0 / 726c5461e2ef52d83cf1ea2107870a8bb3328d57；本地 Python 与兼容依赖差异写入每题环境记录。所有测试使用 CPU；BLAS 线程1，构建线程最多2，CPU worker 最多2，不修改 vLLM/CSRSE 或其环境。

每题结果只落盘一次，复用绑定 base_commit、test_patch、FAIL_TO_PASS 列表、collector/probe/plugin 代码 SHA 与实际 Python/依赖指纹。正式目录为 results/v5_pruner/runtime_coverage/cases_final；cases、cases_v2、cases_verified 是保留的旧金丝雀版本，仅用于追溯，不能混用。

## 覆盖不等于因果证明

**该线只能生成“运行时覆盖过滤版本”，不能保证零噪声。** 未观察到进入某函数，不足以证明函数与 issue 无关。范围是完成 runner 与正常 atexit 子进程中观察到的 Python 函数进入；原生 C/C++、硬退出子进程、外部解释器及未执行的分支没有完备覆盖保证。

实际反例：django__django-12983 的失败测试 TestUtilsText.test_slugify 直接调用 django/utils/text.py::slugify@394，成功覆盖金标，却没有执行 django/template/defaultfilters.py::slugify@212。后者已由源码证明通过 _slugify 别名调用金标，仍与问题有关。因此 A 线已确认的三条错误负例必须持续排除，不能因本次未覆盖而加入 B。

另一个边界是 matplotlib__matplotlib-23913：FTP 测试因 Legend.__init__ 缺少 draggable 参数而真实失败，但 Python 在函数体进入前的参数绑定阶段抛出 TypeError，gold 函数没有 call-entry 事件。这属于真实故障而非环境失败，仍按 gold 未完整观察保持 static-only；不能从“未进入函数体”推出无关。

B 数据线只允许“v3 静态保守资格 ∧ 不在有效的该题覆盖集”，并显式保留 static_only/runtime_unavailable。运行不通和覆盖不完整题绝不声称额外干净证据；重新抽样审阅与 val 对照是下一阶段，本文件不打开 pruner test 标签，不包含模型结果。

## 项目完成情况

| 项目 | 已完成 | 双证据可用 | 其余保持静态 |
|---|---:|---:|---:|
| astropy/astropy | 6 | 1 | 5 |
| django/django | 114 | 50 | 64 |
| matplotlib/matplotlib | 23 | 6 | 17 |
| mwaskom/seaborn | 4 | 3 | 1 |
| pallets/flask | 3 | 2 | 1 |
| psf/requests | 6 | 1 | 5 |
| pydata/xarray | 5 | 3 | 2 |
| pylint-dev/pylint | 6 | 4 | 2 |
| pytest-dev/pytest | 17 | 2 | 15 |
| scikit-learn/scikit-learn | 23 | 4 | 19 |
| sphinx-doc/sphinx | 16 | 10 | 6 |
| sympy/sympy | 77 | 47 | 30 |

## 失败与不完整记录

| 原因 | 数量 |
|---|---:|
| no_existing_gold_or_gold_not_all_observed | 51 |
| runner_initialization_or_missing_test_report | 34 |
| source_import_or_build_failure | 28 |
| base_FAIL_TO_PASS_did_not_all_fail | 24 |
| pytest_collection_error | 16 |
| test_setup_or_teardown_error | 6 |
| unattributed_test_error | 5 |
| base_AST_mapping_failure | 1 |
| dependency_environment_failure | 1 |
| timeout_or_hard_exit | 1 |

## 逐题结果

| issue | 状态 | 失败测试均复现 | 现存金标覆盖完整 | 双证据资格 |
|---|---|---|---|---|
| astropy__astropy-12907 | runtime_evidence_incomplete | False | False | False |
| astropy__astropy-14182 | runtime_evidence_incomplete | False | False | False |
| astropy__astropy-14365 | runtime_evidence_incomplete | False | False | False |
| astropy__astropy-14995 | runtime_evidence_incomplete | False | False | False |
| astropy__astropy-6938 | runtime_evidence_usable | True | True | True |
| astropy__astropy-7746 | test_timeout | False | False | False |
| django__django-10914 | runtime_evidence_incomplete | True | False | False |
| django__django-10924 | runtime_evidence_usable | True | True | True |
| django__django-11001 | runtime_evidence_incomplete | False | True | False |
| django__django-11019 | runtime_evidence_incomplete | False | True | False |
| django__django-11039 | runtime_evidence_usable | True | True | True |
| django__django-11049 | runtime_evidence_incomplete | True | False | False |
| django__django-11099 | runtime_evidence_incomplete | False | False | False |
| django__django-11133 | runtime_evidence_usable | True | True | True |
| django__django-11179 | runtime_evidence_incomplete | True | False | False |
| django__django-11283 | runtime_evidence_usable | True | True | True |
| django__django-11422 | runtime_evidence_usable | True | True | True |
| django__django-11564 | runtime_evidence_incomplete | False | False | False |
| django__django-11583 | runtime_evidence_incomplete | False | False | False |
| django__django-11620 | runtime_evidence_usable | True | True | True |
| django__django-11630 | runtime_evidence_usable | True | True | True |
| django__django-11742 | runtime_evidence_incomplete | False | False | False |
| django__django-11797 | runtime_evidence_usable | True | True | True |
| django__django-11815 | runtime_evidence_usable | True | True | True |
| django__django-11848 | runtime_evidence_incomplete | False | False | False |
| django__django-11905 | runtime_evidence_incomplete | False | False | False |
| django__django-11910 | runtime_evidence_incomplete | True | False | False |
| django__django-11964 | runtime_evidence_incomplete | False | False | False |
| django__django-11999 | runtime_evidence_usable | True | True | True |
| django__django-12113 | runtime_evidence_incomplete | True | False | False |
| django__django-12125 | runtime_evidence_incomplete | False | False | False |
| django__django-12184 | runtime_evidence_usable | True | True | True |
| django__django-12284 | runtime_evidence_usable | True | True | True |
| django__django-12286 | runtime_evidence_incomplete | False | True | False |
| django__django-12308 | runtime_evidence_incomplete | False | False | False |
| django__django-12453 | runtime_evidence_usable | True | True | True |
| django__django-12470 | runtime_evidence_usable | True | True | True |
| django__django-12497 | runtime_evidence_usable | True | True | True |
| django__django-12589 | runtime_evidence_usable | True | True | True |
| django__django-12700 | runtime_evidence_incomplete | True | False | False |
| django__django-12708 | runtime_evidence_usable | True | True | True |
| django__django-12747 | runtime_evidence_usable | True | True | True |
| django__django-12856 | runtime_evidence_incomplete | True | False | False |
| django__django-12908 | runtime_evidence_incomplete | False | False | False |
| django__django-12915 | runtime_evidence_incomplete | True | False | False |
| django__django-12983 | runtime_evidence_usable | True | True | True |
| django__django-13028 | runtime_evidence_usable | True | True | True |
| django__django-13033 | runtime_evidence_usable | True | True | True |
| django__django-13158 | runtime_evidence_incomplete | True | False | False |
| django__django-13220 | runtime_evidence_incomplete | True | False | False |
| django__django-13230 | runtime_evidence_incomplete | False | False | False |
| django__django-13265 | runtime_evidence_incomplete | False | False | False |
| django__django-13315 | runtime_evidence_usable | True | True | True |
| django__django-13321 | runtime_evidence_incomplete | False | False | False |
| django__django-13401 | runtime_evidence_incomplete | False | False | False |
| django__django-13447 | runtime_evidence_incomplete | False | False | False |
| django__django-13448 | runtime_evidence_usable | True | True | True |
| django__django-13551 | runtime_evidence_incomplete | False | False | False |
| django__django-13590 | runtime_evidence_usable | True | True | True |
| django__django-13658 | runtime_evidence_usable | True | True | True |
| django__django-13660 | runtime_evidence_usable | True | True | True |
| django__django-13710 | runtime_evidence_usable | True | True | True |
| django__django-13757 | runtime_evidence_incomplete | True | False | False |
| django__django-13768 | runtime_evidence_incomplete | True | False | False |
| django__django-13925 | runtime_evidence_incomplete | True | False | False |
| django__django-13933 | runtime_evidence_usable | True | True | True |
| django__django-13964 | runtime_evidence_usable | True | True | True |
| django__django-14016 | runtime_evidence_usable | True | True | True |
| django__django-14017 | runtime_evidence_usable | True | True | True |
| django__django-14155 | runtime_evidence_incomplete | False | True | False |
| django__django-14238 | runtime_evidence_incomplete | False | True | False |
| django__django-14382 | runtime_evidence_incomplete | True | False | False |
| django__django-14411 | runtime_evidence_incomplete | False | False | False |
| django__django-14534 | runtime_evidence_incomplete | False | True | False |
| django__django-14580 | runtime_evidence_usable | True | True | True |
| django__django-14608 | runtime_evidence_incomplete | False | True | False |
| django__django-14667 | runtime_evidence_usable | True | True | True |
| django__django-14672 | runtime_evidence_incomplete | False | True | False |
| django__django-14730 | runtime_evidence_incomplete | True | False | False |
| django__django-14752 | runtime_evidence_usable | True | True | True |
| django__django-14787 | runtime_evidence_incomplete | False | False | False |
| django__django-14855 | runtime_evidence_usable | True | True | True |
| django__django-14915 | runtime_evidence_incomplete | False | False | False |
| django__django-14997 | runtime_evidence_usable | True | True | True |
| django__django-14999 | runtime_evidence_usable | True | True | True |
| django__django-15061 | runtime_evidence_usable | True | True | True |
| django__django-15202 | runtime_evidence_incomplete | False | False | False |
| django__django-15213 | runtime_evidence_incomplete | True | False | False |
| django__django-15252 | runtime_evidence_incomplete | False | True | False |
| django__django-15320 | runtime_evidence_usable | True | True | True |
| django__django-15347 | runtime_evidence_incomplete | False | False | False |
| django__django-15388 | runtime_evidence_incomplete | True | False | False |
| django__django-15400 | runtime_evidence_incomplete | False | False | False |
| django__django-15498 | runtime_evidence_usable | True | True | True |
| django__django-15695 | runtime_evidence_incomplete | True | False | False |
| django__django-15738 | runtime_evidence_incomplete | False | True | False |
| django__django-15781 | runtime_evidence_incomplete | False | True | False |
| django__django-15789 | runtime_evidence_incomplete | False | False | False |
| django__django-15790 | runtime_evidence_usable | True | True | True |
| django__django-15814 | runtime_evidence_incomplete | True | False | False |
| django__django-15819 | runtime_evidence_usable | True | True | True |
| django__django-15851 | runtime_evidence_usable | True | True | True |
| django__django-15902 | runtime_evidence_incomplete | False | False | False |
| django__django-15996 | runtime_evidence_usable | True | True | True |
| django__django-16041 | runtime_evidence_usable | True | True | True |
| django__django-16046 | runtime_evidence_incomplete | True | False | False |
| django__django-16139 | runtime_evidence_usable | True | True | True |
| django__django-16229 | runtime_evidence_usable | True | True | True |
| django__django-16255 | runtime_evidence_usable | True | True | True |
| django__django-16379 | runtime_evidence_usable | True | True | True |
| django__django-16400 | runtime_evidence_usable | True | True | True |
| django__django-16408 | runtime_evidence_incomplete | False | False | False |
| django__django-16527 | runtime_evidence_incomplete | False | False | False |
| django__django-16595 | runtime_evidence_incomplete | False | False | False |
| django__django-16816 | runtime_evidence_incomplete | False | False | False |
| django__django-16820 | runtime_evidence_incomplete | False | False | False |
| django__django-16873 | runtime_evidence_incomplete | False | False | False |
| django__django-16910 | runtime_evidence_incomplete | False | False | False |
| django__django-17051 | runtime_evidence_incomplete | False | False | False |
| django__django-17087 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-18869 | runtime_evidence_usable | True | True | True |
| matplotlib__matplotlib-22711 | runtime_evidence_incomplete | True | False | False |
| matplotlib__matplotlib-22835 | runtime_evidence_usable | True | True | True |
| matplotlib__matplotlib-23299 | runtime_evidence_usable | True | True | True |
| matplotlib__matplotlib-23314 | runtime_evidence_incomplete | True | False | False |
| matplotlib__matplotlib-23476 | runtime_evidence_incomplete | True | False | False |
| matplotlib__matplotlib-23562 | runtime_evidence_incomplete | True | False | False |
| matplotlib__matplotlib-23563 | runtime_evidence_incomplete | True | False | False |
| matplotlib__matplotlib-23913 | runtime_evidence_incomplete | True | False | False |
| matplotlib__matplotlib-23964 | runtime_evidence_usable | True | True | True |
| matplotlib__matplotlib-23987 | runtime_evidence_usable | True | True | True |
| matplotlib__matplotlib-24149 | runtime_evidence_incomplete | True | False | False |
| matplotlib__matplotlib-24265 | runtime_evidence_usable | True | True | True |
| matplotlib__matplotlib-24334 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-24970 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-25079 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-25311 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-25332 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-25433 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-25442 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-25498 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-26011 | runtime_evidence_incomplete | False | False | False |
| matplotlib__matplotlib-26020 | runtime_evidence_incomplete | False | False | False |
| mwaskom__seaborn-2848 | runtime_evidence_incomplete | True | False | False |
| mwaskom__seaborn-3010 | runtime_evidence_usable | True | True | True |
| mwaskom__seaborn-3190 | runtime_evidence_usable | True | True | True |
| mwaskom__seaborn-3407 | runtime_evidence_usable | True | True | True |
| pallets__flask-4045 | runtime_evidence_usable | True | True | True |
| pallets__flask-4992 | runtime_evidence_incomplete | True | False | False |
| pallets__flask-5063 | runtime_evidence_usable | True | True | True |
| psf__requests-1963 | runtime_evidence_incomplete | False | True | False |
| psf__requests-2148 | runtime_evidence_incomplete | False | False | False |
| psf__requests-2317 | runtime_evidence_incomplete | False | True | False |
| psf__requests-2674 | runtime_evidence_incomplete | False | False | False |
| psf__requests-3362 | runtime_evidence_usable | True | True | True |
| psf__requests-863 | runtime_evidence_incomplete | False | False | False |
| pydata__xarray-3364 | runtime_evidence_usable | True | True | True |
| pydata__xarray-4094 | runtime_evidence_usable | True | True | True |
| pydata__xarray-4248 | runtime_evidence_incomplete | True | False | False |
| pydata__xarray-4493 | runtime_evidence_incomplete | True | False | False |
| pydata__xarray-5131 | runtime_evidence_usable | True | True | True |
| pylint-dev__pylint-5859 | runtime_evidence_incomplete | False | False | False |
| pylint-dev__pylint-6506 | runtime_evidence_usable | True | True | True |
| pylint-dev__pylint-7080 | runtime_evidence_incomplete | False | False | False |
| pylint-dev__pylint-7114 | runtime_evidence_usable | True | True | True |
| pylint-dev__pylint-7228 | runtime_evidence_usable | True | True | True |
| pylint-dev__pylint-7993 | runtime_evidence_usable | True | True | True |
| pytest-dev__pytest-11143 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-11148 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-5103 | runtime_evidence_incomplete | True | False | False |
| pytest-dev__pytest-5221 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-5227 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-5413 | runtime_evidence_usable | True | True | True |
| pytest-dev__pytest-5495 | runtime_evidence_usable | True | True | True |
| pytest-dev__pytest-5692 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-6116 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-7168 | runtime_evidence_incomplete | False | True | False |
| pytest-dev__pytest-7220 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-7373 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-7432 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-7490 | runtime_evidence_incomplete | False | False | False |
| pytest-dev__pytest-8365 | environment_failure | False | False | False |
| pytest-dev__pytest-8906 | runtime_evidence_incomplete | False | True | False |
| pytest-dev__pytest-9359 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-10297 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-10508 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-10949 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-11040 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-11281 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-12471 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-13142 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-13241 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-13439 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-13496 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-13497 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-13584 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-13779 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-14087 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-14092 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-14894 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-14983 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-15512 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-15535 | runtime_evidence_incomplete | False | False | False |
| scikit-learn__scikit-learn-25500 | runtime_evidence_usable | True | True | True |
| scikit-learn__scikit-learn-25570 | runtime_evidence_usable | True | True | True |
| scikit-learn__scikit-learn-25638 | runtime_evidence_usable | True | True | True |
| scikit-learn__scikit-learn-25747 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-10325 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-10451 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-11445 | runtime_evidence_incomplete | False | False | False |
| sphinx-doc__sphinx-7686 | runtime_evidence_incomplete | True | True | False |
| sphinx-doc__sphinx-7738 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-7975 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-8273 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-8282 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-8435 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-8474 | runtime_evidence_incomplete | False | False | False |
| sphinx-doc__sphinx-8506 | runtime_evidence_incomplete | False | False | False |
| sphinx-doc__sphinx-8595 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-8627 | runtime_evidence_incomplete | True | False | False |
| sphinx-doc__sphinx-8713 | runtime_evidence_usable | True | True | True |
| sphinx-doc__sphinx-8721 | runtime_evidence_incomplete | False | False | False |
| sphinx-doc__sphinx-8801 | runtime_evidence_usable | True | True | True |
| sympy__sympy-11400 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-11870 | runtime_evidence_usable | True | True | True |
| sympy__sympy-11897 | runtime_evidence_usable | True | True | True |
| sympy__sympy-12171 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-12236 | runtime_evidence_usable | True | True | True |
| sympy__sympy-12419 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-12454 | runtime_evidence_usable | True | True | True |
| sympy__sympy-12481 | runtime_evidence_usable | True | True | True |
| sympy__sympy-13031 | runtime_evidence_usable | True | True | True |
| sympy__sympy-13043 | runtime_evidence_usable | True | True | True |
| sympy__sympy-13146 | runtime_evidence_usable | True | True | True |
| sympy__sympy-13177 | runtime_evidence_usable | True | True | True |
| sympy__sympy-13437 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-13471 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-13480 | runtime_evidence_usable | True | True | True |
| sympy__sympy-13647 | runtime_evidence_usable | True | True | True |
| sympy__sympy-13773 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-13895 | runtime_evidence_usable | True | True | True |
| sympy__sympy-13915 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-13971 | runtime_evidence_usable | True | True | True |
| sympy__sympy-14024 | runtime_evidence_usable | True | True | True |
| sympy__sympy-14308 | runtime_evidence_usable | True | True | True |
| sympy__sympy-14317 | runtime_evidence_usable | True | True | True |
| sympy__sympy-14396 | runtime_evidence_usable | True | True | True |
| sympy__sympy-14774 | runtime_evidence_usable | True | True | True |
| sympy__sympy-14817 | runtime_evidence_usable | True | True | True |
| sympy__sympy-15011 | runtime_evidence_usable | True | True | True |
| sympy__sympy-15308 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-15345 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-15346 | runtime_evidence_usable | True | True | True |
| sympy__sympy-15609 | runtime_evidence_usable | True | True | True |
| sympy__sympy-15678 | runtime_evidence_usable | True | True | True |
| sympy__sympy-16106 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-16281 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-16503 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-16792 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-16988 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-17022 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-17139 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-17630 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-17655 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-18057 | runtime_evidence_incomplete | False | True | False |
| sympy__sympy-18087 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-18189 | runtime_evidence_incomplete | False | False | False |
| sympy__sympy-18199 | runtime_evidence_usable | True | True | True |
| sympy__sympy-18532 | runtime_evidence_usable | True | True | True |
| sympy__sympy-18621 | runtime_evidence_usable | True | True | True |
| sympy__sympy-18698 | runtime_evidence_usable | True | True | True |
| sympy__sympy-18835 | runtime_evidence_usable | True | True | True |
| sympy__sympy-19007 | runtime_evidence_usable | True | True | True |
| sympy__sympy-19254 | runtime_evidence_usable | True | True | True |
| sympy__sympy-19487 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-20049 | runtime_evidence_usable | True | True | True |
| sympy__sympy-20154 | runtime_evidence_usable | True | True | True |
| sympy__sympy-20212 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-20322 | runtime_evidence_usable | True | True | True |
| sympy__sympy-20442 | runtime_evidence_usable | True | True | True |
| sympy__sympy-20590 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-20639 | runtime_evidence_usable | True | True | True |
| sympy__sympy-21055 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-21171 | runtime_evidence_usable | True | True | True |
| sympy__sympy-21379 | runtime_evidence_usable | True | True | True |
| sympy__sympy-21612 | runtime_evidence_usable | True | True | True |
| sympy__sympy-21614 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-21627 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-21847 | runtime_evidence_usable | True | True | True |
| sympy__sympy-22005 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-22714 | runtime_evidence_usable | True | True | True |
| sympy__sympy-22840 | runtime_evidence_usable | True | True | True |
| sympy__sympy-23117 | runtime_evidence_incomplete | True | False | False |
| sympy__sympy-23191 | runtime_evidence_usable | True | True | True |
| sympy__sympy-23262 | runtime_evidence_usable | True | True | True |
| sympy__sympy-24066 | runtime_evidence_usable | True | True | True |
| sympy__sympy-24102 | runtime_evidence_usable | True | True | True |
| sympy__sympy-24152 | runtime_evidence_usable | True | True | True |
| sympy__sympy-24213 | runtime_evidence_usable | True | True | True |
| sympy__sympy-24909 | runtime_evidence_incomplete | True | False | False |

每题 commands/logs/test.patch/traces/import_path/environment/input_fingerprint/result.json 均在正式 case 目录，可追溯原命令、源码 commit、实际结果与覆盖身份。

官方执行配置参考：[SWE-bench v4.1.0](https://github.com/SWE-bench/SWE-bench/tree/v4.1.0)。函数进入接口：[Python sys.setprofile](https://docs.python.org/3/library/sys.html#sys.setprofile)。
