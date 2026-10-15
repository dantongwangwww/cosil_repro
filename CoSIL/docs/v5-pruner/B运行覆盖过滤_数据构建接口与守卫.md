# B 覆盖过滤版：数据构建接口与守卫

本模块只准备 B 数据、完整审阅和独立授权，不启动训练，不修改 A 的冻结代码、合同或数据。正式运行证据仅使用 `results/v5_pruner/runtime_coverage/cases_final/`；旧金丝雀目录保留作审计。

## 顺序与接口

1. 在 300 个逐题结果未齐时执行 dry-run，只生成规划摘要，不写训练数据：

   ```bash
   python -m code_v5.prepare_runtime_filtered_data --dry-run --plan-output results/v5_pruner/runtime_filtered_dry_run_plan.json
   ```

2. 同一 Lite300 的结果全部完成后，冻结新覆盖过滤集：

   ```bash
   python -m code_v5.prepare_runtime_filtered_data --freeze
   ```

   默认输出 `results/v5_pruner/data_v3_runtime_filtered/`。`human_review.jsonl` 是新抽取的 TRAIN E 三族各 10 条；`review_source_runtime_evidence.json` 提供完整候选/金标源码、官方 issue/修复补丁、原静态来源及运行证据。此时审阅仍 pending，不能训练。若某族供给不足，报告真实缺口，不能复制样本凑 30 条。

3. 全部 30 条完成 Codex 证据审阅后，保存完整签注为独立 JSONL；冻结器保留 30 条签注、按唯一身份精准删除所有已确认 TRAIN 错样：

   ```bash
   python -m code_v5.freeze_runtime_filtered_decision --contract results/v5_pruner/B_runtime_filtered_execution_contract.json --review results/v5_pruner/data_v3_runtime_filtered/human_review_codex_reviewed.jsonl --output-dir results/v5_pruner/B_runtime_filtered_authorization_exploratory
   ```

   新训练目录为 `results/v5_pruner/data_v3_runtime_filtered_reviewed/`；val/test/split 字节与原始 B 集一致。原标签不翻转、不补造标签、原始 B 集和完整签注保留。已确认错误数量按原始 30 条报告，不能把删错后的余样当成新的随机审阅通过。

## 数据规则

- 先用冻结原始 raw pool、原去重和原采样算法重放 v3 selected、sampling、train/val 字节及 test 哈希。原 1,542 个正例资格保留，原始 1,546 个正例候选中已失去资格的 4 条不能重新进入训练。
- 负例须先满足原 v3 静态资格。有效运行要求 FTP 测试全部真实在 call 阶段失败、选择精确、既存金标覆盖完整、导入来自 base clone、生产代码未被 test patch 修改、无 timeout/硬退出、输入和 trace 指纹完整。有效覆盖包含失败测试上下文和保守 bootstrap 并集。
- 已覆盖函数排除；运行失败/不完整保留原静态资格，并在每行 `runtime_filter` 明确标 `pure_static_runtime_unavailable`。原 v3 已签的 3 个训练错误无论是否被实际测试覆盖，均永久排除。
- 保持原 issue 切分、seed 和真实采样规则；正负例、E 和 D-only 数量均报告实际值。数量不足不造样本，完整性、切分、去重、源证据和封存均不豁免。
- 完整审阅改为噪声披露；历史 ≤2 门结果仍如实记录，不作为新的完整审阅一票否决。允许的数量目标失败仅限独立 B 合同明确列出的 P8000、E3000、N:P2，不扩展到其他质量门。

## test 边界与构建收据

准备和冻结阶段会从已经存在的候选池机械重建含 test 分配的行，以核验原采样并生成新 B 封存文件。**旧封存 `pruner_test.jsonl` 只读取字节哈希，不解码；没有 test 性能评估，也不向模型提供 test。**

冻结时生成 `construction_receipt.json`，绑定原始来源、完整 300 个运行结果、trace、统计、split 和数据文件哈希。后续模型训练守卫只校验构建收据、元数据和 train/val，不再重放 test-role 候选池标签。只有准备/冻结审计执行完整构建重放。新 B test 在构建后立即封存，当前授权 `test_open_allowed=false`。

## 比较与局限

`comparison_A_B_val_shared_pairs.json` 按 issue＋function＋input SHA 对齐共同 val pair，并要求标签相同。全 val 组成可能变化，应同时报告全 val 与共同 pair 指标。

“覆盖过滤版”不代表无噪声。未执行的分支、导入别名、动态派发、native 扩展和未观测子进程仍可能造成遗漏；coverage absence 不能证明无因果关系。失败测试没有经过 Django12983 的 defaultfilters.slugify 包装器，即使金标函数已执行，也不能替该包装器负标签作证。参数绑定阶段发生 TypeError 时，金标函数可能尚未 entry；这种情况属于运行证据不足，不能简单说成环境失败。详见 [运行时覆盖_B线.md](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/docs/v5-pruner/运行时覆盖_B线.md)。

真实 B 30 条审阅结果另行披露；原 A 的 3/30 是固定分层样本，不能证明总体噪声率 10% 或静态过滤的不可降低误差地板。噪声伤害须由后续实际模型结果检验。

## 已验证的 CPU 守卫

实际冻结输入结合 `/tmp` 合成 runtime 子集验证覆盖排除、static fallback、原 3 错排除和正例资格保留；合成签注只验证完整性与精确删错，未冒充真实审阅。

- `results/v5_pruner/B_runtime_filtered_data_cpu_audit.json`：数据规则与封存拒读。
- `results/v5_pruner/B_runtime_filtered_review_guard_cpu_audit.json`：完整 30 条签注、拒绝改标签/源码/运行证据及精确删错。
- `results/v5_pruner/B_runtime_construction_receipt_gate_cpu_audit.json`：训练守卫使用构建收据；完整候选池重放仅用于构建审计。

全量数据与真实审阅的冻结结果以各自文件中的实际状态为准，CPU 合成回归不代表实验准确率或真实噪声率。
