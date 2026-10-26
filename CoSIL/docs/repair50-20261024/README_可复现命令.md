# repair50执行产物与可复现命令

2026-10-26更新：正式修复实验已经启动。50题的参考补丁/空补丁资格验证、全部50对输入冻结和固定前3题的6份补丁工程冒烟均已完成；其余题目按冻结顺序继续生成单次补丁并进行官方测试。当前进度见[执行进度](执行进度.md)，逐题正式结果以 `arm_record.json` 为准；运行中的阶段报告不代表50题最终成绩。

当前代码恢复点为用户GitHub仓库的 `86d940c76d6b7c03e0894abe5696802b6844168c`，隔离全套501项CPU测试通过，远端78份代码与文档逐文件核验一致。此前的468项快照仍保留；本批只修正[已加载镜像的容量误判](已加载镜像容量误判_实现与验证.md)，没有修改模型、输入、参数、候选名单、评分或计费规则。随后仅调整续跑进程的官方API直连环境，见[代理TLS故障与恢复](代理TLS故障与官方API直连恢复.md)。早先磁盘、网络与镜像身份阻塞的历史证据继续保留。

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

## CPU检查与既有运行的恢复

已验收的全套CPU检查入口是隔离测试运行器，使用模块形式：

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/CoSIL
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m code_repair50.run_isolated_transport_tests --full
```

这不是正式修复评价；不要因实验仍在运行而重复执行全部检查。官方修复评分只来自固定执行器对干净base独立容器的实际测试。

仅在确认原控制器已退出、检查其终态和未完成记录之后，既有授权运行可沿原目录与原账本恢复：

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
