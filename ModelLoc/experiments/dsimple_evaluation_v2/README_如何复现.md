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

## 本次实际执行入口

已完成新增215题，1505次HTTP200/stop、无传输重试/思考内容，原共享账本保守扣账3.24130776美元，usage估算1.62065388美元。新筛选子集不足300仓，未启动模型推理。原追加200仍暂停。入口命令记录如下，**这些是已执行命令，不构成再次付费或重置预算的授权**；已有结果由原重放检查跳过，任何缺失/不明在途调用不得语义重抽。

```bash
"$PY" -m dsimple_v2.lite_prepare --workers 4
"$PY" -m dsimple_v2.lite_prepare --repair-failed
"$PY" -m dsimple_v2.lite_runtime --phase tests
"$PY" -m dsimple_v2.lite_runtime --phase freeze
"$PY" -m dsimple_v2.lite_runtime --phase probe
"$PY" -m dsimple_v2.lite_runtime --phase run --scope smoke --execute
"$PY" -m dsimple_v2.lite_runtime --phase run --scope full --execute
```

`--repair-failed`在首个API之前仅修正同一个xarray任务过严的Gitblob校验，按Git归档export-subst的原方法语义验证，不改源码内容、不换任务。先后manifest与首次失败全部保留。运行入口通过真实bwrap探针：资格筛选、gold、原始行、完整manifest、历史结果、主仓及home缓存都不可读，两个离线tokenizer显式挂载。code/config/data/source及55历史结果冻结SHA结束复核通过。

评价器r2修复前代码文档已发布恢复点`b4e94266dd89a1b99efe73081be517a30e8fe611`并核验30个远端Gitblob。r2仅允许完整旧hunk上下文的唯一精确偏移定位；拒绝fuzz、多匹配或缺上下文，不更换base。全部370题统一重评，7题恢复，其他363题状态、目标、逐行证据、fixed文本/line_map与索引字节等价；保留原r1快照。`git apply`只做参考补丁静态文本核验，不是运行修复测试。当前60项CPU测试通过。

## 永久归档与临时目录恢复

永久交付目录：`/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_evaluation_v2_delivery/`。本目录保留代码、文档、逐题CSV和SHA回执，`archives/`保存三个私有归档：

1. `dsimple_evaluation_v2_inputs_20261022.tar.zst`：新215个快照、在线job/index/structure、资源、配置和manifest。341,448份冻结输入SHA逐个匹配；507,312,489字节，SHA256 `40d0f7645075a33bdc6b00ab6f7e3e5d7daf895afd2f7d282fc7dfbf741a4aa0`。
2. `dsimple_evaluation_v2_evidence_20261022.tar.zst`：本批代码、报告、全部新调用原始回执和私有离线评价/修订证据，最终SHA见delivery_receipt.json。
3. `dsimple_old200_state_20261022.tar.zst`：原暂停追加200的代码、manifest、资格审计、运行状态与共享预算账本；原snapshots/jobs/mirrors三个缓存symlink不打包、可按原冻结SHA重建，不表示旧200已运行。12,918,419字节，SHA256 `0ad908c467c25809b468d9b99223f6685fff326e90b1f4a514a2b3ed121575b2`。

本批原始调用及参考补丁只作服务器私有归档，不上传GitHub。GitHub仅提交代码、Markdown和上游MIT许可证。所有档案由本次生成、路径和文件SHA核验通过，未含封存pruner test或密钥。旧P1/原外部100的数据和源码仍在原服务器持久位置，不重复复制其历史目录。

/tmp若因重启丢失，可按下列顺序恢复到原物理路径；保留原逻辑symlink，不要将归档解到系统根目录。先用delivery_receipt.json核验三个归档SHA。`zstd`工具版本1.5.7，输入归档使用long=27，解压需约128MiB字典内存和约20GiB工作盘空间。

```bash
DELIVERY=/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_evaluation_v2_delivery
mkdir -p /tmp/dsimple_evaluation_v2_20261022/project
mkdir -p /tmp/modelloc_swerebench300_20261022/project
tar -I /home/wdt/miniconda3/bin/zstd -xf "$DELIVERY/archives/dsimple_evaluation_v2_inputs_20261022.tar.zst" -C /tmp/dsimple_evaluation_v2_20261022/project
tar -I /home/wdt/miniconda3/bin/zstd -xf "$DELIVERY/archives/dsimple_evaluation_v2_evidence_20261022.tar.zst" -C /tmp/dsimple_evaluation_v2_20261022/project
tar -I /home/wdt/miniconda3/bin/zstd -xf "$DELIVERY/archives/dsimple_old200_state_20261022.tar.zst" -C /tmp/modelloc_swerebench300_20261022/project
```

恢复后的离线评分/CPU测试无需新API。付费运行另有原共享预算目录inode完整性锁；跨重启/迁移后可能主动拒绝付费启动，这项财务保护不能通过重置账本或修改cap绕过。本批已经完成，恢复不需要重新付费。

原smoke5按阶段复用：前6阶段来自nonthinking_v1，最终4题来自v2、1题来自v3。175份跨目录原件逐字节一致，Prompt/模型/参数/base均符合冻结契约，详见reports/Lite270最终统计与费用独立核验.md。每笔历史调用保留真实run_id；当前新增1505请求与历史385/700分别计账，不重复收费。
