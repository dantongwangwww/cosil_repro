# repair50执行产物与可复现命令

2026-10-26更新：本轮已结束并完成同原候选的Spike A基础设施补测。[最终总览](实验报告_50题配对修复_总览.md)：固定50题A17/50、B21/50；92份正常响应、89组正式测试、8组API无候选、3组编辑协议／应用失败。原100条记录与旧报告保持原样，Spike A的新正式True通过独立绑定进入最终派生交付。没有新增模型候选。

[全部50题CSV](逐题配对修复结果.csv) · [失败分类与逐题分析](修复失败分析_先分类再逐题.md) · [冻结50题清单](冻结50题清单.csv) · [配置与产物索引](冻结配置与产物索引.json)。`paired_run_v1/latest_report.json`保留原100条的历史汇总，原Spike A仍是ENV；最终成绩读取 `final_delivery_v1/`，避免把两版范围混用。

运行时代码恢复点为用户GitHub仓库的 `5a3bc0e879f4a6de702ac2d666a77d2e630a9d6f`，隔离全套514项CPU测试通过，当次远端83份代码与文档逐文件核验一致。本批只增加[离线终态交付导出器](离线终态交付导出_用法与恢复绑定.md)及13项合成测试，运行中的控制器和评测器未改。此前的501项恢复点 `86d940c76d6b7c03e0894abe5696802b6844168c` 修正了[已加载镜像的容量误判](已加载镜像容量误判_实现与验证.md)，没有修改模型、输入、参数、候选名单、评分或计费规则。官方API续跑进程的直连环境见[代理TLS故障与恢复](代理TLS故障与官方API直连恢复.md)。早先磁盘、网络与镜像身份阻塞的历史证据继续保留。

最终提交还逐字归档了 `locator.py` 直接依赖的历史 `ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1_delivery/paper_params_retest93_20261023/project/paper_retest93/pipeline.py` 和该目录的三个prompt文件。四文件SHA与现场及`locator.py`固定常量一致，未修改历史源码或方法；本轮只导入其定位实现，不导入旧93题的选择／重测策略。取消路径子串替换的通用规则只作用于本轮独立加载的模块，见`code_repair50/locator.py`。

## 当前正式产物

下表均相对于 `results/repair50_20261024/`：

| 内容 | 路径 |
|---|---|
| 固定候选顺序、资格与排除记录 | `candidate_order.csv`、`qualification_live/candidates/` |
| 已通过资格的50题、官方执行器版本、不可变镜像身份 | `qualification_live/qualified50.json` |
| 共同输入/输出上限、修复参数及50对输入长度 | `paired_run_v1/repair_input_freeze.json` |
| 固定前3题工程冒烟回执 | `paired_run_v1/smoke_gate.json` |
| 每题两组输入、请求响应、补丁和正式测试 | `paired_run_v1/cases/<issue>/` |
| 本轮唯一新增API授权账本 | `budget/ledger.json` |
| 最新阶段报告位置 | `paired_run_v1/latest_report.json` |
| 最终派生报告、三端点统计与真实产物路径 | `final_delivery_v1/` |
| 同原候选补测及绑定、独立清理 | `same_candidate_recovery_20261026/SpikeInterface__spikeinterface-3934/A/` |
| 最终失败分类索引与原证据SHA | `runtime_preflight/case_synthesis_final_20261026/` |
| 独立输入、源码与函数可见性核验 | `runtime_preflight/all50_input_source_audit_20261026/` |
| 已完成配对的离线证据审阅 | `runtime_preflight/completed_pair_failure_reviews_20261026/` |

正式名单SHA256为 `a5255d0a2449627c7bca4a642e8c7c5be11bc271ad60202e4e417b200b4fce83`。50题来自固定265题范围中的235道既有函数目标完整且非空任务，经资格检查和每仓最多一题约束选出，属于开发诊断实验，不代表全部SWE-rebench任务。

## 只读查看进度与结果

以下命令只读本地文件，不调用模型、不启动容器、不改变账本：

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/CoSIL
cat results/repair50_20261024/paired_run_v1/latest_report.json
cat results/repair50_20261024/paired_run_v1/smoke_gate.json
sha256sum results/repair50_20261024/qualification_live/qualified50.json
```

打开 `latest_report.json` 的 `report_dir` 后，可查看其中的 `实验报告_定位辅助修复配对.md`、`per_issue.csv`、`summary.json`、`修复失败分析_先分类再逐题.md`。所有阶段报告分别落盘，不覆盖之前的快照。深度证据审阅另行核对实际源码、模型补丁和正式测试日志，证据不足时保留未知；任何审阅结果都不回传修复模型。

## 离线复现最终统计

以下命令不调用模型、容器或测试，不改原始记录及latest指针。输出目录必须全新，已有目录会被拒绝；命令先建立独立临时父目录，再向尚不存在的report子目录导出，可重复执行而不覆盖旧报告。

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/CoSIL
repair50_rebuild_parent=$(mktemp -d /tmp/repair50_rebuild.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m code_repair50.finalize_report \
  --run "$PWD/results/repair50_20261024/paired_run_v1" \
  --roster "$PWD/results/repair50_20261024/qualification_live/qualified50.json" \
  --ledger "$PWD/results/repair50_20261024/budget/ledger.json" \
  --terminal-log "$PWD/results/repair50_20261024/paired_run_v1/controller_9_direct_deepseek.log" \
  --maintenance-metadata "$PWD/results/repair50_20261024/runtime_preflight/spike_cached_capacity_prechange_20261026/maintenance_timing_scope.json" \
  --recovery-binding "$PWD/results/repair50_20261024/same_candidate_recovery_20261026/SpikeInterface__spikeinterface-3934/A/recovery_binding.json" \
  --output "$repair50_rebuild_parent/report"
```

该入口重现核心报告、共同正式配对、模型流程敏感性、分组、原始产物路径与源哈希。固定50系统交付四格按原用户要求另由同一统计函数计算；以下为只读完整命令，输出与 `final_delivery_v1/supplemental_analysis.json` 中系统交付部分一致：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-v5/bin/python -B - <<'PY'
from pathlib import Path
import json
from code_repair50.reporting import official_outcome
from code_repair50.statistics import paired_statistics
s = json.loads(Path('results/repair50_20261024/final_delivery_v1/summary.json').read_text())
system = paired_statistics([
    {'instance_id': r['instance_id'],
     'A': official_outcome(r['A']) is True,
     'B': official_outcome(r['B']) is True}
    for r in s['rows']
], bootstrap_seed=20261024, n_bootstrap=20000)
print(json.dumps({'system_delivery_fixed50': system,
                  'joint_official': s['paired_official'],
                  'model_pipeline_sensitivity': s['paired_model_pipeline_sensitivity']},
                 ensure_ascii=False, indent=2))
PY
```

系统终点中的False表示未交付；API无响应并不因此变成模型正式判负。共同正式43题和模型流程46题保留各自分母。候选正常响应的token／费用均值为46条／臂，完整尝试序列含未知传输时为NA；不能混用各45条完整费用可知记录的均值。

逐题CSV保留实际预测文件／函数、两组目标定义完整性、source是否相同、正常响应usage／时延／费用、完整序列未知、共享定位复用及费用、empty_modification、原／现状态、真实路径及中文原因。共享定位费用每对只加一次，历史复用不重复收费；9题完整费用未知，其已知部分和保守上界仍与总账闭合。费用都是执行时费率乘usage估算，非账户发票。

最终源码可见性指完整既有定义（含装饰器），不能据此推断所有依赖接口均已提供。空补丁和仅空白改动的正式结果也留在分母。

## CPU检查与历史恢复入口

已验收的全套CPU检查入口是隔离测试运行器，使用模块形式：

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/CoSIL
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m code_repair50.run_isolated_transport_tests --full
```

这不是正式修复评价；不要因实验仍在运行而重复执行全部检查。官方修复评分只来自固定执行器对干净base独立容器的实际测试。

本轮已完结，无需再启动主控。下面保留中断期间的历史恢复命令；仅在另行核实未完成记录时沿原目录／原账本使用，不删除候选或重抽答案：

```bash
NO_PROXY="${NO_PROXY:+$NO_PROXY,}api.deepseek.com" no_proxy="${no_proxy:+$no_proxy,}api.deepseek.com" PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m code_repair50.main --phase run --wait-seconds 172800
```

控制器有独占锁；恢复复用已经保存的正常候选和兼容的上游阶段，不因测试失败重新生成答案。不能删除结果或账本以重抽答案、重置5美元上限，也不能在已经冻结50题后重跑资格流程并覆盖正式名单。当前主控仍在运行时，不另起一份控制器。

上面的域名直连只作用于该进程，保留其他服务的代理和TLS验证。因代理TLS故障而已终止的请求保持原终态；残缺SENT请求受现有防重发门保护，不能借恢复命令补抽答案。100条状态记录不等于100个正常候选或100次完成测试，最终应读取各项真实状态和正式可判定分母。Spike原A的同候选基础设施补测另行归档，不覆盖原失败。

控制器结束后，可读取既有记录并新增一份离线报告快照：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m code_repair50.main --phase report
```

`report` 不调用模型或执行测试，但会新写报告和更新指针，因此运行中直接读取最新报告即可。环境、预算未执行、正常模型输出失败和正式测试未解决必须分别报告；未知费用保留上界，不能记为零。

独立交付版本使用 `code_repair50.finalize_report`，它要求控制器真实终态，且输出目录必须不存在；运行中不能用它生成“最终报告”。其[调用参数与恢复绑定格式](离线终态交付导出_用法与恢复绑定.md)包括原记录和实际请求消息SHA校验、只对应用前环境错误的同候选补测绑定、维护影响时延标记及真实产物路径。它不会修改原始记录、旧报告或latest指针。原Spike A的补测应先完成并取得真实评测回执，再提交绑定；禁止用空绑定或未执行结果代替。

## 早期准备命令与历史证据

下面保留早期准备阶段的复现命令；它们不能替代官方资格与实际A/B评测，也不表示正式实验仍未启动。准备程序对相同产物幂等、对不同内容拒绝覆盖，读取隔离侧金标与固定parquet，未向模型传送数据：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m code_repair50.prepare
sha256sum results/repair50_20261024/candidate_order.csv
sha256sum results/repair50_20261024/official_sources/official_harness_e490_full.tar.gz
```

期望候选CSV的SHA256为 `b748e93522eeae3411ab72f736ad8a314406cc697f2cb8d88b944063f09f4f1e`，官方源码tar为 `3dfc6035ceabb319431a7e0e66fb99024e5db2aa250533cb669b44ad071e38b9`。

只读检查Docker与容量，不拉镜像、不启动容器：

```bash
sg docker -c 'docker version'
sg docker -c 'docker info --format "{{.DockerRootDir}} {{json .DriverStatus}}"'
df -h /mnt/skygruop0 /tmp
```

早期磁盘清理见[清理回执](磁盘清理记录_20261024.md)。`current_status.json` 和[准备与环境阻塞报告](执行报告_准备与环境阻塞.md)保留的是当时的证据，当前运行状态应读取本页开头列出的产物。普通pytest退出码、补丁应用成功和CPU合成检查均不能替代官方Resolved判分。
