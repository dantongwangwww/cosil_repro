# D-SIMPLE：指定 Lite 式条件的 SWE-rebench 265 题定位评测

用户于 2026-10-22 确认：四项筛选条件不放宽，只运行全部合格 265 题，允许同一仓库出现多题。不补充 35 题，不变更冻结数据版本，不因函数可映射性或预测结果重新选题。本集合来自 173 个仓库，与原外部 100 题及 SWE-bench Lite 续评分别报告；不能称为 CQ2-CARE 原论文 300 题，也不能据筛选条件宣称与 Lite 难度相同。

本批新增代码前恢复点：[bb0fd82](https://github.com/dantongwangwww/cosil_repro/commit/bb0fd82bf8374a62f8ec550c611941e76cdcbf52)。现有 40 份代码、文档远端 Git blob 已逐个核验。保留 CoSIL 原上游 Git，不改历史预测、既有报告、跨实验矩阵或封存 test。

## 名单和方法

数据源为 `nebius/SWE-rebench-leaderboard`，revision `34d5a58864acf91613740a09ec5d205228dcfa39`。原始 860 行 Parquet SHA256 为 `1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf`。

完整业务 `patch` 同时满足：修改文件数不超过 1、统一 diff 的 hunk 数不超过 3、不新增或删除文件、`len(problem_statement.split()) >= 40`。不把 `test_patch` 混入统计，不先删掉部分修改文件再计数。历史训练／开发仓库及保护 ID 继续排除。旧每仓一题的容量建议不再是本批资格门。

四项通过 283 题，历史隔离后 265 题。全部纳入后以原 `sampling_hash`、`instance_id` 排序，哈希为 SHA256 UTF-8(`rebench_lite_filtered_v1|20261022|<instance_id>`)。`manifests/filtered265_roster.json` 保存原始资格字段、固定顺序和来源 SHA；`reports/名单独立核验.json` 逐字段核验了 3,975 项。筛选不读取预测，也不根据函数映射结果挑题。

44 题满足原外部结果复用契约；其余 221 题重新运行，其中 58 题复用已准备的 base commit 输入缓存，163 题新准备。复用输入缓存不等于复用预测。完整 gold 补丁通过、空补丁失败资格检查均标记 `NOT_CHECKED`；本任务不执行修复测试。

线上沿用原 `deepseek_simple_v1/src` 的 D-SIMPLE：官方 DeepSeek `deepseek-flash`、显式 `thinking: {type: disabled}`、五次文件选择、原哈希角色与交集／回退、有限 grep、完整文件上下文、最终函数 Top-10。Prompt、温度、请求上限、每题 token 上限、传输重试与语义重试规则不变。最多 4 个并发 API 操作，不占 GPU，不启动 vLLM、CoSIL、训练或补丁生成。

推理 worker 通过 bwrap 仅获得 issue、base 源码、原方法资源和指定输出目录；参考补丁、gold、资格筛选、完整 manifest、旧运行结果及封存数据不可读。独立 Python 3.12 R2 函数评价器不会进入模型上下文。函数身份严格为 `path::qualified_name`；完整且非空的既有函数目标集合才进入函数主表。

## 原共享预算

所有新增请求继续写入唯一账本：

`../deepseek_simple_external300_v1/runs/20261022_external_add200_nonthinking_v1/budget.json`

上限仍为 5 美元。开始本批前已有 1,505 笔已结算请求、保守扣账 3.24130776 美元、硬账本余量 1.75869224 美元。此前按实际 usage 和时段估算费用为 1.62065388 美元；这不是可以重置预算的理由。新旧费用分列，复用不重复收费。原始未筛选追加 200 题仍保留暂停标记。

金融 guard 保留原路径、父目录 inode/device、case key、锁与停止标记。遇到额度停止时保留已发调用和完整状态，不换题、不为提高分数语义重跑。报告分别给实际运行成绩与固定分配范围的完成覆盖；未运行不能冒充模型定位失败，亦不能从原分配规模中悄悄删除。

## CPU 与运行入口

以下入口用于同一冻结工程；已付费结果应从原回执复用，不能删除账本后重跑。

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1
DSIMPLE_PY=/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python
export PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES=''
"$DSIMPLE_PY" -m unittest discover -s tests
"$DSIMPLE_PY" -m filtered265.prepare --workers 4
"$DSIMPLE_PY" -m filtered265.runtime --phase freeze
"$DSIMPLE_PY" -m filtered265.runtime --phase probe
"$DSIMPLE_PY" -m filtered265.evaluate --execute-frozen --workers 4
"$DSIMPLE_PY" -m filtered265.runtime --phase run --scope smoke --execute
"$DSIMPLE_PY" -m filtered265.runtime --phase run --scope full --execute
"$DSIMPLE_PY" -m filtered265.report
```

准备、单元测试、评价和报告均为 CPU 工作，不调用模型。付费两步须通过冻结 SHA、真实 bwrap 探针、首五题工程验收和原共享金融合同。工程验收检查输入输出契约及账费，不以定位正确率决定继续或换题。

主要交付包括：正式 manifest、复用与新增明细、逐题结果 CSV、文件和函数 Hit@1/3/5、Macro-Recall@5、全部既有目标覆盖率@5、95% 置信区间、重复仓库聚类区间、token／费用／时延统计、逐题未命中证据及中文总览。具体输出和报告复现见 `README_报告复现.md`。

工作缓存位于 `/tmp/dsimple_rebench_lite_filtered265_v1_20261022/project`，逻辑项目目录为其 symlink；最终永久归档及 SHA 回执将在交付时注明。密钥仅从原受限环境文件读取，不复制到工程或 GitHub。GitHub 只发布代码、Markdown 和许可证。
