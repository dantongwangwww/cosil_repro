# D-SIMPLE 分范围评价 v2

本目录独立保存 SWE-bench Lite 续评、原外部100题的离线重评，以及采用指定Lite式条件筛选的 SWE-rebench 定位评测子集资格审计。禁止把三种范围混成同一套300题。原外部追加200题仍处于用户暂停状态，工程及原始记录保留，不在本批启动。

新增/大改前的代码文档检查点已发布至用户GitHub：`dfab02c2d7cf595807c9cfed735174dbaca91e71`，远端tree逐文件Git blob校验通过。此批只增加独立CPU筛选、独立Python3.12函数评价及冻结D-SIMPLE的Lite续跑外壳；不修改原方法、历史预测、旧金标与旧报告。

## 固定范围

- SWE-rebench pin：`34d5a58864acf91613740a09ec5d205228dcfa39`；原860题Parquet SHA256：`1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf`。
- `rebench_lite_filtered_v1`四项过滤逐题审计在 `evaluator_private/rebench_lite_filtered_v1/`。过滤283题/177仓，历史隔离后265题/173仓，无法形成300个不同仓，因此正式manifest为不足状态、records为空。容量建议名单不是已经完成的评测集，不得以173题名单擅自启动推理。
- Lite公开300题先按既有保护ID排除30题；允许范围270题。原smoke5/pilot50的55题逐请求契约核验通过后复用，仅为其余215题安排新增调用。训练/开发同源风险需披露，不能称独立外部泛化证据。
- 所有新增队列共享 `deepseek_simple_external300_v1/runs/20261022_external_add200_nonthinking_v1/budget.json` 的原5美元硬上限与原锁。历史复用费用只作历史资源说明，不再次计入新增消费；禁止创建新账本、清空账本或修改cap。

## 依赖与离线命令

当前运行环境使用 CoSIL 的 `.venv-v5/bin/python`，离线AST固定 `/usr/bin/python3.12`。原在线D-SIMPLE仍用原索引与Python3.11流程，离线评价器的解析兼容性修复不注入定位模型。

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_evaluation_v2
PY=/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python
mkdir -p /tmp/external_lite_four_audit_unidiff075
cp -R resources/upstream_unidiff_v0.7.5/. /tmp/external_lite_four_audit_unidiff075/
"$PY" -m unittest discover -s tests
"$PY" -m dsimple_v2.screen --unidiff-source resources/upstream_unidiff_v0.7.5
"$PY" -m dsimple_v2.gold --manifest manifests/external100.json --cohort external100
"$PY" -m dsimple_v2.gold --manifest manifests/lite270.json --cohort lite270
"$PY" -m dsimple_v2.report --cohort all
```

离线命令只读公开任务/参考补丁并写本目录独立产物，不调用模型、不执行修复或测试。函数主表以 `COMPLETE_NONEMPTY` 为准，既有函数目标完整且非空；`COMPLETE_EMPTY`和`INCOMPLETE`单列。函数身份严格为 `path::qualified_name`，重复/无效输出占原排名槽，不补位。所有函数指标明确分母。

筛选统计完整业务 `patch`，不去掉文件再统计；`test_patch`独立记录。词数固定Python `str.split()` 后取长度，用户指定>=40，未追加其他Lite条件。官方脚本实际排除<=40，报告明确本任务的边界差异，不能宣称完整复刻Lite协议。

## 付费执行及隔离

付费入口与冻结清单、CPU准备/真实bwrap探针、启动回执见 `runs/20261022_lite_eval_v2_nonthinking/`。未通过探针、冻结SHA或共享预算完整性检查时不得启动。禁止直接绕过worker调用原provider。全部调用显式关闭thinking，固定七阶段、五次文件选择及原交集/回退、grep规划、整文件上下文和最终Top10流程。仅传issue/base源码；参考补丁、资格统计、gold、历史run、报告、封存数据不挂载给推理worker。

结果失败和预算停止留原状态，不为提高成绩换题或重试语义流程。源文件快照和大缓存位于 `/tmp`；最终永久交付副本、压缩证据、SHA与GitHub发布记录以 `delivery_receipt.json` 为准，不能依赖临时目录重启后仍存在。
