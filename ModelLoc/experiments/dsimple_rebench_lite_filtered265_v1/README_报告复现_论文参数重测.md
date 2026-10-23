# 论文参数定向重测：离线报告复现

本说明只包含CPU报告命令，不启动推理、下载、修复测试或GPU服务。报告代码为`paper_retest93/reporting.py`，合成测试为项目根目录的`tests/test_reporting.py`。推理协议与本批修改前GitHub检查点见[本轮协议](README_论文参数复核与本轮协议.md)。

固定题集仍为原265题。原200个完整结果中，函数Top5未命中24题、文件Top5未命中18题，交集14题；其并集28题加原未运行61题和预算中止4题，构成本轮93题。主表复用另外172题，并对这93题**一律采用新结果，即使新结果比旧结果差**。旧预测和报告保留原路径，不做best-of。

主表名称为“旧正确复用＋论文参数定向重测/补全”。它不是265题全量采用论文参数的成绩：协议混合，而且重测对象由旧结果选出，不能将总体改善解释为无偏的参数增益或独立泛化结果。本轮共同调整文件/规划输出限额、提示词和默认采样、可读取文本与证据范围、装箱，并重新抽样；不能只归因于60K截断或取消五文件限制。

本轮继续使用非思考DeepSeek及函数Top10扩展，函数输出上限4,096是本实验约定，不是论文的补丁输出参数。没有生成修复补丁或执行官方harness，因此不报告论文修复率。

## 输入与计分

- 原manifest：`manifests/filtered265.json`。新93题manifest：`manifests/paper_retest93/manifest.json`，由issue ID对应，不能按结果行号拼接。
- 新结果：`runs/20261023_paper_params_retest93_nonthinking_v1/paper_params_retest93/D-SIMPLE/<instance_id>/`。旧172题仍从原manifest指向的历史路径读取。
- 离线R2金标及Python3.12索引：`evaluator_private/eval_v2/filtered265/<instance_id>/`。它们不进入推理worker；报告进程只读，不重新提取或修改金标。
- 严格函数身份、原始排名槽位、重复身份集合规则、P@k固定除k与原评价一致。COMPLETE_EMPTY题函数指标为NA，文件评价独立保留；完整结果时合并函数分母235、文件分母265，新93题函数分母82、函数NA11。
- 新源码块先以base文件SHA和精确原文前缀核验，再重建精确元数据脱敏后的context，与成功最终HTTP请求比较。最后被token截断的半行不计完整函数覆盖。同限定名多span共享评分身份，但任一同名span可见不等于真实修改实现已完整送达。
- 非Python源码可以合法进入模型上下文，其真实性按新准备回执的raw SHA核验；原文件/函数评价仍限既有业务Python范围。范围外但真实存在的路径与虚构路径在诊断中分列，不改变旧评分规则。

## 单一报告入口

等待新run的`full_complete.json`记录阶段结束、93题均有终态，且付费worker已退出后，再执行正式报告。报告会检查两个manifest、原R2金标与新财务基线；有未运行或评价缺失时拒绝生成正式报告。报告不会补跑缺失题。

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' PYTHONPATH="$PWD" \
  /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python \
  -m paper_retest93.reporting
```

输出只写入`reports/paper_retest93/`，不覆盖原`reports/filtered265/`。运行中的账本可能尚未与请求产物同时落盘，正式汇总须等worker结束，不以瞬时的未关联记录判断丢失请求。

`--allow-incomplete`仅供离线进度检查，不调用模型；未运行逐题指标保持NA，allocation汇总只能称完成信用下界，不能称这些题已被模型判错。最终交付应使用上面的正式命令。

### 冷恢复时使用本轮最终财务快照

恢复输入、原R2金标和新run证据后，若原共享财务目录只恢复到了旧批次2613条，不要把它当作本轮最终账本，也不要回写或替换实际共享账本。本轮最终只读副本为`reports/paper_retest93/finance_final_snapshot.json`（3264条），SHA以同目录`finance_final_snapshot_receipt.json`为准。以下仅在报告进程内更换读取路径，然后调用同一个报告入口：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' PYTHONPATH="$PWD" \
  /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -B - <<'PY'
from paper_retest93 import reporting as R
snapshot = R.C.ROOT / 'reports/paper_retest93/finance_final_snapshot.json'
receipt = R.C.load(snapshot.with_name('finance_final_snapshot_receipt.json'))
assert R.C.sha(snapshot) == receipt['sha256']
assert len(R.C.load(snapshot)['attempts']) == 3264
R.C.SHARED_BUDGET = snapshot
R.B.C.SHARED_BUDGET = snapshot
R.main([])
PY
```

该命令只读财务快照并重建新报告目录，不修改原共享账本。重建会刷新自动Markdown，运行前保留已签核的最终Markdown。恢复最终归档中的3份逐题复核JSON后，再用下列离线命令把36题人工中文分析重新插入失败报告：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' PYTHONPATH="$PWD" \
  /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -B \
  -m paper_retest93.manual_review_report
```

正常顺序也是先`python -m paper_retest93.reporting`，再`python -m paper_retest93.manual_review_report`。后者只合并已归档的手工复核材料，不调用模型、不改预测或分数。

## 主要输出

| 文件 | 含义 |
|---|---|
| `合并265题_总览.md`、`merged265_per_issue.csv` | 用户要求的混合265题主表，93题无条件覆盖 |
| `new93_per_issue.csv` | 本轮独立93题，保留标准原始预测、固定槽位和指标字段 |
| `method_summary.csv` | 合并265、新93、旧失败28的新结果、补全65的新结果、旧保留172；allocation与executed分列 |
| `paired28.csv`、`paired28_summary.csv` | 原失败28题同题旧新比较，差值与按题/仓库聚类CI；只描述定向选中样本 |
| `本轮93题_资源消耗.md`、同名CSV | 所有分配、完成和已执行失败人口的token、美元费用、wall及CPU总量/均值/中位/P90 |
| `本轮93题_逐题资源.csv`、`cost_ledger.csv` | 新93题逐题资源、逐请求usage与出处 |
| `定位失败分析报告.md` | 先给互斥主分类及题数，再列每一道受影响issue、issue原文摘要、预测、源码获取及最终HTTP证据 |
| `failure_categories.csv`、`failure_issue_index.csv`、`gold_source_evidence.csv` | 分类汇总、逐题索引、逐gold身份的来源/排名/实际修改体覆盖证据 |
| `retained_old_recall_gaps.csv` | 原21道Hit5已中但召回不足的保留结果；单列诊断，不冒称本轮失败 |
| `evaluation_summary.json`、`shared_finance.json` | 完整结构化指标、合并规则及财务核验 |

文件与函数均报告Hit@1/3/5/10、P/R/F1/AllCoverage及MRR@10。95%区间使用原算法、10,000次重采样、seed=20261022，同时提供issue bootstrap与仓库聚类bootstrap。函数NA、未运行、执行失败及已完成但未命中分开，不删除失败题来缩小分母。

## 资源与失败解释

本轮93题全部步骤重新请求，不复用旧预算中止题的16个成功步骤。新财务基线保存原2613条账本记录，报告逐条检查其不变，新费用只计基线之后的新请求。费用按`request_id`去重；五次独立选文件即使request SHA相同也不能合并。费用是美元usage与缓存/冻结峰闲价格推算，不是账户逐笔账单；未知usage或费用保留NA。

本轮资源只统计新93题，不把旧172题的历史调用当新增开销。wall是每题`run_one`实测时间，包含网络等待、源码及输出处理，不含队列、全量准备、SHA预核和离线评价；进程CPU秒另列，不当作GPU秒。失败题的实际资源继续计入，未运行占位零不混入执行资源分布。

失败报告用实际源码前缀、跳过记录、文件/函数排名、非法身份及最终HTTP送达证据分类。函数Top5未命中、文件独有未命中和已Hit5但召回不足分开；合法空JSON与格式错误也分开。自动中文说明是可观测阶段事实，不能推断模型心理。排除已知旧上下文偏差后仍未命中，不足以证明模型本身不可能完成该题。

## 合成CPU测试

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' PYTHONPATH="$PWD" \
  /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python \
  -m unittest discover -s tests -p test_reporting.py -v
```

测试使用合成数据，覆盖无条件采用较差新结果、IID集合对齐、原评分槽位、源码前缀与脱敏HTTP核验、半行覆盖、非Python raw SHA、财务基线、配对指标专属胜负及输出边界，不调用模型。

当前逻辑工作目录仍指向`/tmp`工作区，不能作为唯一永久交付。最终代码/文档发布与私有结果归档由主线程另行核验；本轮永久交付receipt未发布前，不以旧批次delivery receipt冒称已包含这次新93题。
