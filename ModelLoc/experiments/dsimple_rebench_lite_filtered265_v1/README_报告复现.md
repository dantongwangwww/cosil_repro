# filtered265：离线报告复现

本文件只说明 CPU 评价和报告，不启动模型、不调用 API、不执行仓库测试。在线准备、预算授权和启动入口由主 README 与冻结配置管理。

本项目固定官方860题中的265个合格 issue，来自173个仓库。业务 `patch` 全文件数≤1、总 hunk≤3、无文件新增/删除、`len(problem_statement.split()) >= 40` 四项保持；`test_patch` 单独，未参与这四项过滤。历史隔离不变，用户取消每仓一题限制。原100中44题只读复用，新推理分配221题；这不是 CQ2-CARE 原论文的固定300题，也不保证与 SWE-bench Lite 难度相同。未按 gold 可映射性、函数目标数或预测表现替换题目。

## 固定入口

- 唯一正式名单：`manifests/filtered265.json`。完整发布后必须为 `n=265`，origin 为 `old100_reuse44` 的44题和 `new221` 的221题。准备中的 roster 不是最终模型结果。
- gold 入口：`filtered265/evaluate.py`，调用字节保持一致的 r2 `gold.py`。输出固定为 `evaluator_private/eval_v2/filtered265/<iid>/gold_v2.json`，与在线 job 的运行 cohort 名分开。
- 报告入口：`filtered265/report.py`；只写本项目 `reports/filtered265/`，不写旧结果或共享财务文件。
- 原共享账本：`deepseek_simple_external300_v1/runs/20261022_external_add200_nonthinking_v1/budget.json`，cap总计$5，包含上一批Lite保守占用$3.24130776。新项目不重置余额。
- 新运行的 `financial_baseline.json` 保存完整原账本快照。最终报告要求该基线存在，并确认原条目逐值不变；历史复用请求不能再次出现在当前共享账本中。

CPU测试：

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1
/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m unittest discover -s tests -p test_report.py -v
```

最终准备名单冻结后，统一离线评价：

```bash
/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m filtered265.evaluate --execute-frozen --workers 4
```

模型阶段结束后生成报告：

```bash
/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m filtered265.report --cohort filtered265
```

如果共享预算停止后仍有未运行题，或部分评价产物不可用，使用 `--allow-incomplete` 如实输出完整分配组与已执行子组。该标志不会替换题目、补造预测或把未运行题当作已执行模型失败。

直接调用接口为 `filtered265.report.run_report(manifest_path=None, allow_incomplete=False)`，无需让上层 CLI 参数流入 argparse。正式输出始终使用10000次 bootstrap 与固定 seed20261022；测试仅在合成夹具中缩小重采样次数。

## 如何读分母

`method_summary.csv` 有7行：总组、旧44、新221各有 allocation/executed 两种统计人口；新221另有 http_attempted 行。

- allocation 保留每个固定分配组内已知可评题。未运行项在逐题表为NA；汇总中的零完成信用只表示下界，不能称为真实执行准确率。Hit5另给未运行所致上下界。
- executed 只包括真实启动、HTTP尝试或执行终态的题，已执行的失败和预算中止保留在其分母。HTTP子组更窄，不包含完全未发请求的本地启动。
- 文件和函数分别有分母。函数只纳入 `COMPLETE_NONEMPTY`；`COMPLETE_EMPTY` 单列NA；`INCOMPLETE` 和 `evaluation_unavailable` 单列未解决资格，不能伪装成空函数目标或自动剔除失败。
- 缺 job/gold/index 时不声称有已核验文件或函数真值；机器表保留未知资格题数。不能把已执行子组当作真实完成全部221题。

评分保持严格 `path::qualified_name`、原始排名槽及固定k分母。无效项不删除补位；重复有效身份仍占槽，命中集合不重复计数；同QN多个定义共享身份，不做父子函数或叶名宽松追分。模块/class/新增函数共存不排整题，但只评价补丁修改的既有具名函数。文件排名来自原文件选择，不能从函数预测反推。

## 产物

`reports/filtered265/` 最终包含：

- `evaluation_summary.json`、`per_issue.csv`、`method_summary.csv`：范围、分母、状态、固定槽指标与分布统计。
- `gold_source_evidence.csv`、`未命中分析.md`：每个目标是否真正出现在成功最终HTTP的源码上下文中，包括base SHA、区间、原排名与证据分类；不推断模型心理。
- `cost_ledger.csv`、`shared_budget_summary.json`：每个真实 request_id 的来源、usage、费用估算与共享账本对齐。旧44费用单列，不重扣新预算。未知usage/费用为NA，保留已知subtotal和未知条数。
- `总览.md`：中文总览，单列已观察题和已观察仓库、预算停止/失败/未运行、函数空/不完整/不可用。

均值、中位数、P90用实际执行/HTTP尝试中的已知资源样本，并保留样本数。墙钟为原 `run_one` 内耗时，不包括排队、全量准备/SHA复核或离线评价；准备阶段的 monotonic wall 也不是进程CPU秒。费用由真实usage与冻结价格推算，不是账户账单。两个95%区间分别按issue与仓库cluster重采样，重复仓库不作为独立仓库处理。

`gold_patch_pass` 与 `empty_patch_fail` 均为 `NOT_CHECKED`。没有执行官方harness，因此不声称完全CQ2资格或修复通过率。

## CPU准备守卫的工程恢复

第一次准备错误地对主数据盘应用2GiB门槛，造成151题CPU准备失败；当时已有114题准备成功（70新题与44复用）。已完整归档427份初次产物并核SHA，然后对同151个ID在实际 `/tmp` 写入卷的10GiB守卫下恢复。没有换题、模型调用、预测或GPU工作。初次错误不能计作151次模型定位失败，也不能把历史失败覆盖为从未发生。

最终报告只按最后冻结名单、准备状态和实际运行结果评分；工程恢复的原件另行保留：[守卫修订与恢复记录](reports/preparation_guard_scope_revision.json)、[attempt1原件SHA清单](evaluator_private/filtered265/_history/attempt1_main_disk_guard/archive_manifest.json)。该清单SHA为 `1bcdf37d16092f45f86c6ccb2c002612c28e0b86eaea2b4f9949512dcf0b253b`。恢复过程中成功和失败数仍以最终准备receipt为准，本README不把中间进度当最终完成数。

工作目录的实际位置在 `/tmp`；最终持久代码、报告和证据归档以主线程交付receipt为准。无需读取封存test/holdout来复现本报告。旧Lite270、原external100和原未筛选追加200的历史文件不改写。

离线证据还会单列：同leaf不同path/QN的原槽位；同QN任一span可见与实际修改base span送达的区别；完成输出的严格miss、Top5命中但召回缺口、工程/预算/输出失败及未运行互斥人口。实际修改体证明只基于r2 matched_base_span、有效base源码区间与匹配HTTP，证据不足不补算。
