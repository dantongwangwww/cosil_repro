# C exploratory 完成后的独立评测入口

本目录只准备后续接口。它不更改原 C 的 `test_open_allowed=false`、原 C4/C6、共享资源 v2/v3、A/B 数据或历史授权。模型、checkpoint、温度与三路阈值必须来自实际完成的 C resources v3 验证赛马。准备阶段不读任何真实封存 test JSONL、不导入 Torch、不加载模型、不产生定位成绩。

`authority.py prepare-authorization` 要求实际 sequence、pair、outcome 全部完成，逐一复核真实 best/last checkpoint、train/val 保存概率、处方配置、共享 GPU 身份、赛马、val 温度与安全阈值。仅 val accuracy≥0.80 且 AUC≥0.85 的既定赛马赢家能生成关闭状态的模板。root 复核后另签 `results/v5_pruner/C_postexploratory_evaluation_root_authorization.json`，开启后续评测权限；不把探索性训练或既有审阅失败追认成正式通过。

后续调用按顺序执行，以下命令现在不自动启动：

```bash
.venv-v5/bin/python -B -m code_v5_postexploratory.authority prepare-authorization \
  --output results/v5_pruner/C_postexploratory_evaluation_disabled_TEMPLATE.json

# root 核验模板、另签 canonical root authorization 后，先以 check 复核。
.venv-v5/bin/python -B -m code_v5_postexploratory.authority check

.venv-v5/bin/python -B -m code_v5_postexploratory.test_once --execute
.venv-v5/bin/python -B -m code_v5_postexploratory.historical_comparison --execute
.venv-v5/bin/python -B -m code_v5_postexploratory.run_pipeline_sequence \
  --execute --through-full --workers 2
```

`test_once` 使用既有 `metrics.run_test_once` 全局 `O_EXCL` 标记，跨输出目录仍不允许第二次开箱。原生 `JudgeModel` 在标记消耗后的无标签 callback 内加载，输入仅 ID、issue、function；T=1 产出原始分数，保存接口只应用一次冻结温度。异常会永久消耗本次开箱，保留证据，不自动重测或改变模型/阈值。保存整体、A/B/C/D/E 与 E 三族指标，二分类 gold 召回和直留/直剪/灰区，加载时间、冷/热/全部预测延迟与实际 input/scoring 工作。共享 GPU 耗时不能与独占 B 条件做因果比较。

`historical_comparison` 只读取已经开箱并保存的 test 预测及无标签输入指纹，不重读原 test。旧 off 判决须有成功源码 fetch、精确 base graph/函数身份、fetch 后且 prune 前的真实 pruner 模型调用、原解析器可确认响应；同时检查小裁判真实截断输入指纹。重复共识计一个 pair，矛盾、无效、缺失保留 NA。新 Verified 题没有旧 Lite off 日志，不能补造响应。报告同一观测 pair 上的判决一致率、E 三族正确剔除率与混合集剔除 precision；不调用 Decision-1、不假设灰区 Qwen 正确、不产出新定位成绩。

`run_pipeline.py` 是既有 runner 的独立副本。12 个原函数（输入、模型/HTTP 审计、缓存原生裁判、函数/类路由、token、实际 case、聚合、固定金丝雀与稳定性判断）在 CPU 守卫中要求 AST 完全相同。改动限于新授权、来源标识、资源选择、独立输出。`code_v5.pruner_pipeline.AFL` 原样复用：只替换函数判决，class 继续旧 Qwen；P(相关)≤low 直剪、≥high 直留、其余才调用 Qwen；small 模式阈值0.5。

金丝雀沿用 `results/v3b_dataset_ten.json` 的固定十题，三模式各两遍共60次；全量仅 small/hybrid 各300题，qwen300 复用 v3c off。技术门沿用已准备原 runner 的全部60次完成、版本一致、Top5集合稳定、Jaccard 和 Qwen 调用下降门，不依据金丝雀 gold 重新选模型。每次实际请求（包括 SDK retry）、Qwen usage、本地 input/scored positions，以及 class 回落，分别落盘。

新 root 资源授权允许 GPU0..3 中有≥12GiB空闲显存的一卡共享，不因其他任务上下文暂停，不停止或修改任何进程。双 worker 仍各自单卡原生推理；资源元数据写实际物理卡，不伪称 GPU2 或预留 GPU3。模型/API/CLI 失败保留 partial case 和日志，不自动换模型、batch、阈值或重跑挑好结果。

后续总览/逐题报告与矩阵仍须依据真实完成的 `full/{small,hybrid}/loc_results.jsonl`。评分沿用改动行＋AST金标、文件＋函数叶名与既有 Top5 去重口径，按同 Lite300 ID 对齐，分别展示全300、原 held-out60及锚点三组；val曾用于选择，所以60中 val30 与纯 test30还应拆开披露。不得把分类 accuracy 写进定位矩阵；只有真实 LOC 结果才用 `code_v3b/build_result_matrix.py --add ...` 追加，不改历史 off/on。权威 OOD 清单是重生成221题，不把旧231或只有现存 base gold 的197改作默认评分分母；本入口不自动扩大 OOD 工作。

CPU 守卫：

```bash
.venv-v5/bin/python -B -m code_v5_postexploratory.check_interfaces \
  --receipt results/v5_pruner/C_postexploratory_CPU_preparation_v2.json
```

检查中的两个手写 synthetic fixture 仅存在于 `/tmp`，用于验证全局一次标记、无标签 callback、温度一次应用、权限/来源漂移等接口。它们不是 benchmark 数据、模型输出或实验结果。
