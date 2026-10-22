# D-SIMPLE追加200题与离线300题报告

本目录沿用原SWE-rebench同一860题数据版本及固定revision。旧100题预测、源码、gold和报告只读引用；新增200题使用独立manifest、run和USD5硬上限，旧费用不计入该上限。D-SIMPLE保持原五次文件选择、交集/回退、最多5整文件、80K o200k源码context、一次grep取证与最终Top10排序，不加入函数签名候选或工具协议增强。原方法是CQ2-inspired诊断扩展，不能称为论文官方函数定位或修复率实验。

模型推理和CPU评价必须使用不同进程。推理worker仅看clean jobs/base源码，不能看到新旧evaluator_private或reports。job/snapshot可能是指向`/tmp`的临时缓存软链接，重启后不保证保留；永久manifest、预测、请求/回执及报告位于新ModelLoc工程。缓存缺失时先报告证据缺口，从固定数据revision/base commit恢复缓存并核SHA，不能凭空重建预测或自动重新请求模型。

## CPU测试

从本工程根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m unittest tests.test_report -v
```

测试只创建临时合成源码、标签、请求及回执，不读真实gold/封存测试，不访问API/GPU。

## 独立离线报告

等待所有新增分配题有结果（包括失败/预算停止）后：

```bash
PYTHONDONTWRITEBYTECODE=1 /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m supplement_v1.report
```

仅查看中间检查点可显式加`--allow-incomplete`，NOT_RUN保留单独状态，不能把当前累计下界称为200题完整模型成绩。此命令不会启动推理、下载、修复或测试，也不会运行旧报告main；不覆盖旧100任何产物。

评分直接使用冻结P1的`analysis/evaluation_extension.py`精确`path::qualified_name`身份，以及`src.metrics.scores/mrr`。重复/无效输出保留原槽，Precision@k固定除以k；k=1/3/5/10的Hit/P/R/F1/AllCoverage及MRR@10、issue与repo cluster bootstrap CI分别报告旧100、新200和合并300。严格主分母只含fully_mappable；partial只评分可映射子集，不能称完整gold召回；unmappable为NA。

## 归因与交付

`reports/per_issue.csv`保留排名、状态、计费估计、token、墙钟、CPU秒、主因与多标签。`failure_targets.csv`逐gold目标记录inventory/选择/整文件/80K溢出/5文件上限/grep/精确rank与源码span证据；`source_delivery_audit.csv`核base文本SHA及原span，最终HTTP请求必须包含逐字相同的context并有成功回执。

`strict_hit5_failures.csv`与`strict_recall5_gaps.csv`区分严格未命中和已命中但召回不全；`partial_auxiliary_misses.csv`单列辅助结果。`未命中逐题归因.md`给中文关键词/证据概述、原Issue摘录和证据路径，不冒称自动语义根因裁决。返回外层函数而gold为nested方法、gold位于第6–10位均单独标注，不放宽strict匹配追回分数。grep能救回未选择文件；同名任一property/overload定义span覆盖不等于实际修改实现已完整看到。

`cost_ledger.csv`按request_id去重；USD来自usage/缓存/时段费率推算，不是逐笔账单。旧100费用与新增预算分开，未知计费保留保守预约。本轮D-SIMPLE不用本地GPU；CPU进程秒与含API等待的墙钟分别列，未测得则NA，不能宣称CPU免费。

尽可能验证gold补丁通过/empty补丁失败的资格，仅引用单独准备阶段实际产物。环境不支持或未检查必须记NOT_CHECKED及原因，不能声称已完成验证，也不因此按gold可映射程度挑题或称完整CQ2抽样。报告不执行gold/empty补丁或任何测试。封存test、历史矩阵及原100结果保持原样。
