# Verified 扩挖与 B 融合：库存预检和实现依赖

状态：**只完成本地输入库存、ID 资格和新切分预检代码；没有下载、挖矿、训练或评测 test。** 本文不授权执行扩挖。原 Lite300 的 B 覆盖过滤、30 条审阅和训练不等待此支线。

## 1. 最新触发条件

最新用户裁定：A 的 reranker 先按 rank8、dropout0.1 的处方重训；处方后 val accuracy<0.80 时，Verified 扩挖成立，且必须与 B 运行时覆盖过滤合并。此前“仅 train<0.70 才扩挖”的限制已被最新裁定替代。触发须绑定真实处方报告、配置和主协议；本预检程序不会把预期成绩当作触发收据。

## 2. 已核对的本地库存

| 输入 | 当前事实 | 用途和边界 |
| --- | --- | --- |
| `evaluation/gt_verified.json` | 历史字典有 500 个唯一 issue ID，SHA256 `a73ee9fd437c5dc06b00e2afed2b21ec0d77e086cdc53e285caa268ada85dbd0` | 与冻结 Lite300 的键集合交集为 93，非 Lite 为 407；只是历史 ID 库存，不能替代官方 issue、base commit、FTP 和 test patch 元数据，也不作为新增训练金标 |
| `repo_structures_verified/` | 实际恰好 300 个 JSON，对应 Lite300，非 Lite 结构为 0 | 目录名称中的 Verified 不意味着已有 407 个新题结构 |
| `datasets/SWE-bench_Verified_test` | 不存在；旧 `get_verified_structure.py` 指向的路径也不存在 | 旧脚本不能直接执行 |
| `swebench_local/` | 目前只有已保存的 `SWE-bench_Lite_test` | 现有 Lite 元数据可供 B 继续执行；不包含 Verified 全量元数据 |
| HF datasets / hub 缓存 | 只识别到 SWE-bench Lite 的缓存目录，没有 Verified 数据集 | 未作下载；后续官方元数据应另存独立快照并记录上游 revision、文件 SHA 和 dataset fingerprint |
| 231 题无名 OOD 池 | 交接文档第 96 行、原始快照同一行提到它；尚未找到真实 ID 清单、候选池或 v4 来源 manifest | **指定的精确扩挖目前不可执行**。不得从 407 中随机挑 231 个 ID，不得用文件名里的 `2317` 或 Lite 的无名统计充数 |

已使用本仓库、同级项目文件清单，以及 `/home/wdt` 下针对 `231题/无名池/Verified/OOD` 的目标文件与文本搜索；没有把不相关项目的源码或训练数据读作此实验输入。上述“未找到”是此次本地搜索的结论，不代表这份旧池永远不存在。

## 3. 独立预检入口

新模块：`code_v5/verified_expansion_preflight.py`。没有导入 Torch、调用模型、下载数据或调用矿工；旧 A、图构建器、矿工、v3 过滤器和正式 Lite collector 均保持原字节。

```bash
python -m code_v5.verified_expansion_preflight \
  --output results/v5_pruner/verified_expansion_inventory.json
```

未来有真实本地输入后，另选新输出名：

```bash
python -m code_v5.verified_expansion_preflight \
  --verified-jsonl /path/to/frozen_official_verified.jsonl \
  --ood-pool /path/to/actual_v4_reserved_pool.jsonl \
  --output results/v5_pruner/verified_expansion_identity_precheck.json
```

这两个路径目前只是接口示例，不是已存在的文件。预检要求完整 500 条唯一 Verified 元数据、`repo/base_commit/version/FAIL_TO_PASS/test_patch/patch/problem_statement` 等字段；真实 OOD 源必须提供恰好 231 个唯一 ID、与 Lite 零交集且全部属于当前官方 Verified 输入。函数池可一题多行，按 `instance_id` 取集合，不按文件行号拼接。

程序会保存实际排除数量和 ID。来源文件的 SHA 与正确数量仍不等于它就是历史 v4 保留池，root 还须核证其来源并写入执行协议。缺少任何一项只记阻塞原因，不生成虚构的合格 ID。

新题切分仅在完整输入与保留池身份同时满足预检时给出**未冻结的提案**：按 repo 分层，沿用 seed20261013，以 issue ID 的 SHA256 排序；新题 val/test 各 floor(N/10)，其余 train。原 Lite train/val/test=240/30/30 的所有 issue 归属保持不变。新提案不自行授权训练，也不替换原 `split_manifest.json`。若今后指定 anchor 分层，须另签方法并重新预检，不改既有 Lite 归属。

## 4. 真正扩挖的实现依赖

1. 完整官方 Verified 快照：冻结 revision、全部行 ID、输入文件 SHA、repo/base/version、FTP 和 test patch。先算与 Lite300 的实际交集，再排除来源已核证的 OOD231 池；历史 gold 键的 93 只是此次预核对，官方快照对齐必须重新计算。
2. base commit 源码及镜像：逐题确认 commit 对象存在，缺失提交才在已授权执行时拉取。独立新入口可复用只读 `static_calls.build_one(task)`；旧 CLI 直接读 `ground_truth_300.json`，不能照旧跑以假装 Verified 已处理。
3. 金标：可复用只读 `build_ground_truth_300.derive(row)` 的补丁实际改动行＋AST 机械提取，保存 base/patch/blob/源 SHA；历史 `gt_verified.json` 的函数字符串不作为训练金标。直接金标、灰区与 C 关系的口径由 root 在新执行协议中确认；本预检不另定标签。
4. 新题只开 `A/C/D/e_bm25/e_anchor`：可用 `mine_issue(...)` 的逐题接口，但日志入口必须隔离为空且断言没有 `B/e_log` 标签或证据。不伪造查找 agent 日志，不把 issue 文本冒充日志。BM25 仍用全 issue 和核验后的完整 base 函数源码。
5. E/D 静态资格：复用 `refine_pruner_data_v3.refine_issue(...)` 的原保守规则、完整 AST 别名和定向 UP/DOWN 排除；不改第四轮静态规则、不把风险闭包翻成正标签。旧 CLI 的 Lite300、240/30/30 校验保留，用独立入口处理新集合。
6. 运行时融合：为新增题另建 collector 版本和新结果目录，不能修改 Lite 正式 collector 或混用其缓存。指纹至少绑定 repo/base/version、FTP/test patch、probe/plugin/collector SHA、真实环境、test selection 和 trace 文件。负例须“静态已合格且不在合格失败路径覆盖并集中”；跑不通或覆盖不完整的题保留纯静态负例，逐行写 `runtime_unavailable` 及原因。覆盖缺席不证明没有因果关系，不能称零噪声。
7. 合并与去重：固定原 Lite split；已确认的原三条及 B 新签错样不得重入。新增输入与旧 train/val/test 角色做截断输入重复／相反标签检查；发生碰撞不移动旧 issue、不恢复原已排除的 4 条 C 候选、不人为补数量。完整身份、来源和实际减少计数入新报告。
8. 新审阅与冻结：保持原 B30 全签注；扩后另抽 TRAIN E 审阅并披露真实比例及纯静态 fallback 占比，新题没有 e_log 族时如实披露而不凑虚假族。确认错误精确剔除、保留原标签和签注，不将去错后的剩余抽样称随机通过。新扩展决策和独立训练包绑定自己的数据、代码、协议 SHA。

## 5. test 边界和预期

不解码既有封存的 `pruner_test.jsonl`，不运行任何 test split 模型性能。构建阶段若按固定候选池规则机械生成新 test 角色行，须明确记录这是构建而非 test 性能开箱，立即封存；训练入口仅读冻结收据与 train/val。沿用完整性门、no LLM 标签和 GPU 纪律。

扩挖可能增加 repo、issue 和真实 A/C 正例覆盖，但没有真实矿工计数前不能承诺达 8000。运行覆盖可能减少漏过滤负例，也会压缩 D/E 供给；实际正负比例、E 数量、静态 fallback 和审阅噪声均须原数披露。是否改善由同处方配置下的 train/val 及后续获准阶段指标判断，不用数量增长或“覆盖过滤”名称代替模型效果。

在官方元数据、OOD 来源或处方触发仍缺失时，此支线保持不可执行；原 Lite300 的 B 重建、30 条审阅和处方对照继续推进。
