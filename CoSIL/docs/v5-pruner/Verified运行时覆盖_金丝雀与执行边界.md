# Verified 运行时覆盖：金丝雀与执行边界

本记录只说明新扩展题的源测试运行时证据，不能据此宣称 Verified 挖矿、训练、OOD 评测或整个 v5 已完成。已冻结的 Lite 300 收集器、历史结果和 B 数据均未修改。

## 输入与身份

输入为官方 SWE-bench Verified 完整 500 题固定快照（revision `78f471bf655a3137b2e8a75af1501690ec009ec3`）。剔除 Lite 交集 93 题后，407 题均完成真实 Git 源码与 patch/AST 独立核证。按最新用户裁定，issue 全文忽略大小写后，出现任一改动函数的限定名或 `def` 简单名的题才能挖矿；未出现者保留 OOD。结果是挖矿 186 题、保留 221 题，其中 13 题无函数金标，未来函数评测应标 NA，分母为 208。221 不能被描述为恢复了历史未找到生成脚本的“231 无名池”。

权威身份与函数金标位于 [新 OOD 清单](../../results/v5_pruner/verified_regenerated_ood/verified231_manifest.json) 和 [逐题函数金标索引](../../results/v5_pruner/runtime_coverage_verified_v1/input_audit/verified_gold_files_index.json)。[独立真实 Git 核证](../../results/v5_pruner/runtime_coverage_verified_v1/input_audit/regenerated_OOD_real_Git_source_independent_audit.json) 复验全部 407 题、529 个 Python 文件的 before/after 源码（1058 份档案）和完整已有函数物理行映射。

## 金丝雀的真实结果

第一版独立收集器已实际执行三题，保留历史缓存。Django 17029 的官方测试标识采用 `method(Class.method)`，旧归一化重复追加方法名，导致 collection 错误；该题实际记录为 static-only，未当作失败路径证据。Sympy 19637 和 Sphinx 7462 真实通过覆盖资格。旧结果及 [历史终审](../../results/v5_pruner/runtime_coverage_verified_v1/canary_terminal_historical_independent_audit.json) 不覆写。

修复放在独立 `code_v5_verified_runtime_v2` 与新缓存目录。新版三源码冻结后，根代理签署 [新版金丝雀执行授权](../../results/v5_pruner/runtime_coverage_verified_v2/canary_authorization_v3.json)，于 2026-10-14 17:40:06 完成 3/3，全部合格：

| issue | 官方 FAIL_TO_PASS 实际运行 | 完整已有 base 函数真实进入 | 结果 |
|---|---|---|---|
| django__django-17029 | `apps.tests.AppsTests.test_clear_cache`，call 阶段实际失败 | `django/apps/registry.py::Apps.clear_cache@370` | runtime 可用 |
| sympy__sympy-19637 | `test_kernS`，call 阶段实际失败 | `sympy/core/sympify.py::kernS@442` | runtime 可用 |
| sphinx-doc__sphinx-7462 | 两个官方测试均在 call 阶段实际失败 | `_parse_annotation.unparse@91` 与 `unparse@61` | runtime 可用 |

[新版独立终审](../../results/v5_pruner/runtime_coverage_verified_v2/canary_terminal_independent_audit_v3.json) 不导入收集器，直接读原始 trace，并从真实 Git base AST 重建函数身份。它核对官方测试、执行授权 SHA、稳定核心、输入与环境指纹、源码导入位置、生产源码保护、全部已有金标、测试调用阶段，以及无 timeout/硬退出。三题全部通过。新版收集器主源码 SHA 为 `6891ad482c040f7a0ca5d7a837a8938567e698017ca841dd016f02f0abd2925c`；实际缓存位于 `results/v5_pruner/runtime_coverage_verified_v2/cases_final`。

## 固定边界

- CPU 两个 worker、编译并发 2；按 repo/version 的线程锁与进程 `flock` 串行保护共享隔离环境。无 GPU、新模型/API 调用或 pruner test 标签读取。
- 官方 Django 1058 个标识全部回归：旧 `method(Class)` 941 个、新 `method(Class.method)` 49 个、bare 68 个。新旧格式的命令选择与 trace 匹配共用归一化。bare 文案或无类限定标识不假定合法 test ID，不做模糊凑测试；真实选择不支持时单列 `unsupported_selector`，保留纯静态资格。
- 必须全部官方 FAIL_TO_PASS 真正在 call 阶段失败，且完整 `existing_gold_function_regions` 所指物理 base 函数进入；仅按同名函数匹配不够。insert-only 改动也包含在完整目标中。
- 修改过的测试 `.py` 文件不映射成 base 函数身份，其候选不因覆盖缺失而获得双证据负例资格。函数调用在参数绑定阶段报错、未进入函数体，也按 runtime 不完整处理。
- timeout、硬退出、环境/collection/setup/teardown 错误、导入位置或 source mapping 不可靠、完整金标未进入，均不能产生 runtime 双证据；保留原因并回退纯静态。
- 覆盖是实际 Python call entry 与失败测试 context，加保守 bootstrap 并集。C 扩展、外部解释器和未正常落盘的子进程有观测缺口；即使函数未出现，也不能证明其因果无关。所谓“干净版”仍是覆盖过滤版本，需重新审阅，不能宣称零噪声。
- 每题落盘一次；复用须精确匹配官方输入、完整金标、三源码和环境指纹。旧版本失败不覆写；新增收集器版本采用新命名空间和缓存。正式 186 题运行须由根代理另签同核心执行授权。

## 正式采集与完成结论

根代理于 2026-10-14 签署 [正式 186 题执行授权](../../results/v5_pruner/runtime_coverage_verified_v2/formal_authorization_v3.json)（SHA `3f0538d515ff2390a4748d9ad7c4a60b4cdf15418ff0fdb9db656182def2ab5d`），与新版金丝雀的稳定核心完全一致。17:47 前已在持久 `tmux v5-verified-runtime-formal-v3` 实际启动，CPU 两个 worker；三个已有金丝雀结果按精确指纹复用，不再次执行或覆写。

[固定执行计划](../../results/v5_pruner/runtime_coverage_verified_v2/formal_pipeline_plan.json) 绑定收集器三源码、只读终审脚本、自动收尾入口与 root receipt，且保存启动时三个金丝雀结果的原始字节 SHA。自动收尾入口在真实 186 题全部完成后，核对冻结源码及金丝雀缓存没有变化，再运行独立全量终审。当前状态可查看 [CPU 执行状态](../../results/v5_pruner/runtime_coverage_verified_v2/formal_pipeline_status.json) 和 [逐题采集汇总](../../results/v5_pruner/runtime_coverage_verified_v2/summary.json)。源码或指纹漂移、执行失败、收集题数不完整时停止终审，不补造覆盖。

2026-10-14 18:57:03，正式收集器真实完成全部 186 题并以 exit 0 返回。19:02:53，独立终审完成并以 exit 0 返回，[最终覆盖终审](../../results/v5_pruner/runtime_coverage_verified_v2/final_completion_independent_audit.json) 为 `status=passed`、`passed=true`、`completed=expected=186`、错误 0；SHA `5b94033122cca1a29da5484b9130cc5c2987abc61a468f86076c064820fcce59`。[自动链路终态](../../results/v5_pruner/runtime_coverage_verified_v2/formal_pipeline_terminal_receipt.json) SHA 为 `d7e393ff4129c5922382fa94e90c9fb8c8486da32d0c4b7ec967eedfd326f736`。

| 真实终态 | 题数 | 后续负例资格 |
|---|---:|---|
| runtime 可用，官方 FTP 全部真实 call 失败且完整已有金标进入 | 88（47.31%） | 候选仍需静态合格，且不在失败路径／bootstrap 覆盖并集；修改过的测试源码候选另作 runtime 不可用 |
| runtime 不完整 | 85 | 保留纯静态并标原因 |
| 官方 Django selector 不支持 | 11 | 保留纯静态并标原因 |
| 隔离依赖环境创建失败 | 1 | 保留纯静态并标原因 |
| 实际测试超时 | 1 | 保留纯静态；不完整 trace 不能升级 |
| 合计 | 186 | 88 题可提供运行时证据，98 题回退纯静态 |

终审针对 186 题逐一核原始 trace SHA、执行 receipt 与稳定核心、完整输入／环境指纹、真实 Git base AST 物理函数身份与全部既有金标；按 issue 计数共有 415 个已有函数目标。没有用函数同名代替物理 def 行、没有将 AST 模拟成运行时覆盖、没有提升不完整或失败题。三道金丝雀的原始结果字节保持一致，cache drift sidecar 为 0。

98 道回退题的解释单独落在 [终态边界分类](../../results/v5_pruner/runtime_coverage_verified_v2/final_runtime_observation_classes.json)，没有改写原结果或资格：源码导入失败／未核证 23、完整已有金标未进入 19、FTP 选择／collection／启动不完整 15、Django selector 不支持 11、call error 未证明是真实 bug 7、无已有 base 金标 7、editable 版本元数据启动错误 6、setup／teardown 错误 6，以及 source editable 安装失败、部分 FTP 在 base 上通过、环境失败、超时各 1。每题只报一个主要解释；事前已有 base 金标为空的实际输入共 10 题，其中 3 题同时存在其他首要失败，不能将主分类中的 7 误报成输入总数。

19:07:20 的 [资源与不可变核证](../../results/v5_pruner/runtime_coverage_verified_v2/final_resource_and_immutability_receipt.json) 确认：采集／终审以及已正常落盘 trace 的 192 个已知自有 PID 均退出，相关 tmux 会话结束，临时题目工作区剩余 0，三个冻结源码与三道旧金丝雀字节不变。隔离依赖环境保留以便永久复用，没有改动其他进程、GPU、旧 Lite/B 数据，也没有调用模型或解码 pruner test。

以上只签运行时证据采集完成；Verified 静态产线、融合数据、重新审阅、模型训练和正式 OOD／端到端评测仍由其各自终态与授权决定，不能把本终审替代这些阶段。
