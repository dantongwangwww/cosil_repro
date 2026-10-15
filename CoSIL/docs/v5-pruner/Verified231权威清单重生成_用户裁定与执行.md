# Verified OOD 权威清单重生成

依据：2026-10-14 用户对缺失旧 v4 的 231 个 issue ID 清单作出的新裁定。旧清单不再是启动依赖；本轮按下列确定性规则重新生成，真实数量可以不等于 231。

1. 使用已归档的 SWE-bench Verified 官方固定 revision 的 500 题，按 instance_id 剔除与 Lite 300 的交集。交集实测 93 题，剩余 407 题。
2. 金标沿用补丁实际改动行加前后 AST，包括新增函数与插入行映射到已有函数的情况。hunk 标题不作为金标。
3. 对每题 problem_statement 与 gold 函数名作忽略大小写匹配，包含 `def` 的简单定义名。按用户“出现任何函数名”的字面使用子串匹配，不自行加入词边界；保存命中名、文本位置与上下文。无函数金标的题单独标记，不进入训练挖矿。
4. 未出现任何 gold 函数名的题归入 OOD；是否点名 gold 文件名仅作元信息，不改变上述筛选条件。
5. 权威产物为 `results/v5_pruner/verified_regenerated_ood/verified231_manifest.json`，保存 instance_id、repo、文件点名信息、gold 文件及函数，另归档脚本、SHA、输入 revision 与逐题源码证据。文件名保留 231 以对应用户指定产物，数量按实际结果报告。

该 manifest 将同时作为新 Verified 挖矿的排除清单与正式 OOD 集依据。旧脚本生成的 231 不是硬数量门，也不通过挑题凑数复刻。实际数量、差异说明与独立核验在生成后补齐。

现有 A 处方的真实 val accuracy 为 267/363=73.55%，低于 0.80，扩挖触发已成立。新扩挖使用 A/C/D/e_bm25/e_anchor 五条产线；新题没有历史日志，不制造 B 或 e_log 标签。之后与运行时覆盖过滤、30 条源码证据审阅及同配置重训衔接。

现有 Lite B 双底座训练继续运行，冻结数据、训练代码与旧分支收据保持原样。旧报告中的“等待缺失历史 231 清单”是本裁定前的状态；新的扩挖执行授权与数据版本将另行落盘。exploratory 阶段继续封存 test，不重跑 Qwen 基线，不改 vLLM/CSRSE；GPU 和预算纪律沿用既有要求。

## 实际生成结果

407 题全部成功从本地 Git base commit 与官方补丁派生金标，没有把源码缺失误判为无名。按上述规则保留 **221 题 OOD**，其余 **186 题可挖矿**。221 中有函数 gold 的是 208 题；另 13 题仅有类或模块级改动，没有函数 gold，已显式保留并标记，未来函数级评估须列为 NA。

与旧 231 相差 **−10**。新结果由冻结的官方快照、真实改动行＋AST 和显式名称匹配规则确定；旧生成脚本与清单缺失，无法把这 10 题的差异定量归因于某项旧规则，不虚构差异来源。

- [权威 manifest](../../results/v5_pruner/verified_regenerated_ood/verified231_manifest.json)：SHA256 `05a898c1b9f5dff7edc321e2f3d0e5872b701f2828d6ae6ea4a501f28da8f05d`。
- [生成脚本](../../code_v5_verified/regenerate_ood_manifest.py)：SHA256 `36a4615e98dd76d5bc6bbc5ac523f2d63a7e0d472fb66989d3ccb1393d06cc37`。
- [root 独立名称与 AST 审计](../../results/v5_pruner/Verified_regenerated_OOD_root_independent_audit.json)：407 题、1,058 份前后源码、879 个 gold 函数对通过；SHA256 `b1ef69f6b66dc3f06dd1f56c2da47b02fafb411df36ae6a353cda39daa4a4d0e`。独立 Git blob 复核与新执行入口冻结另行记录。
- [独立真实 Git 重放审计](../../results/v5_pruner/runtime_coverage_verified_v1/input_audit/regenerated_OOD_real_Git_source_independent_audit.json)：407 题 Git commit/blob、独立应用补丁、前后源码及完整 base def 行映射均通过；SHA256 `bfca8d002e9e11f1530b0b024ec04e457c84cbec2867a730aaf0c519354b76bb`。不是把旧历史 hunk 金标复用为新真值。
- [221 题可读 CSV](../../results/v5_pruner/verified_regenerated_ood/verified231_manifest_逐题可读表.csv)：直接显示 issue 是否点名 gold 文件名、gold 文件／函数及函数 NA 标记；按 instance_id 导出，不改 manifest。另有[导出与 SHA 收据](../../results/v5_pruner/verified_regenerated_ood/verified231_manifest_readable_export_receipt.json)。

208 题有函数级 gold 中，197 题至少有一个 base 已存 gold 函数，11 题只有 after 侧新增函数。OOD 名称筛选和定位判分采用前后 AST gold；训练与运行覆盖只认 base 中实际存在的物理函数，不能混用这两个分母。

186 题的新 issue 切分为 train 150 / val 18 / test 18，旧 Lite 的 240/30/30 分配保持不变。实际静态扩挖已启动，持久会话 `v5-Verified-static`、PID 890654，输出 `results/v5_pruner/verified_extension_regenerated_ood_v1`；[根执行授权](../../results/v5_pruner/Verified_regenerated_static_execution_authorization_v1.json)绑定新 manifest、真实 A 处方触发、旧 B 数据决定与 11 个代码 SHA。此阶段产物尚不是可训练版本，运行时过滤和新审阅仍待完成。

边界案例 `django__django-13406` 的 `QuerySet.query` setter **在 base 中已经存在**，def 行为 212，补丁仅往其体内插入两行；getter 的 def 行为 204，两者同限定名。该题的真实 existing gold 是 setter@212，覆盖进入它可以合法用于资格判断，进入 getter@204 则不能替代。挖矿与覆盖资格均使用真实物理函数区域。早先说明误把该 setter 写成新增函数，已依据 Git blob 更正；manifest、金标与最终独立审计原本均保留正确的 setter@212，没有因说明误读删除或重标数据。

## 运行覆盖适配与金丝雀

独立 collector 的首版真实金丝雀中，SymPy19637 与 Sphinx7462 成功复现失败且进入完整 base gold，Django17029 因测试选择器重复追加方法名而未收集到测试。三份原缓存与冻结源全部保留；该收集错误没有计作真实失败路径。

已另建 `code_v5_verified_runtime_v2` 与独立 `runtime_coverage_verified_v2` 缓存，统一命令选择器和 trace 对齐逻辑，兼容 `method(Class)` 与 `method(Class.method)`。官方 500 中的 Django 共 1,058 个 FTP 标签回归通过：旧格式 941、新格式 49、bare／描述 68。没有可唯一解析的 bare 标签明确记为 unsupported/static-only，不制造测试 ID。

新版三题金丝雀由[独立根授权](../../results/v5_pruner/runtime_coverage_verified_v2/canary_authorization_v3.json)放行；其稳定策略指纹绑定官方数据、221 OOD 排除、完整 gold、独立 Git 审计、harness、三个 collector SHA、两个 CPU worker 与跨进程环境锁。实际三题均通过[独立终审](../../results/v5_pruner/runtime_coverage_verified_v2/canary_terminal_independent_audit_v3.json)，均在真实失败的 call 阶段进入完整 base gold；SHA256 `24c6744378117d14c1e0d6bfad9d00386352ba65da6e2dceb35a9ab2a290e7c5`。

随后已另签[186 题正式采集授权](../../results/v5_pruner/runtime_coverage_verified_v2/formal_authorization_v3.json)，SHA256 `3f0538d515ff2390a4748d9ad7c4a60b4cdf15418ff0fdb9db656182def2ab5d`，与金丝雀保持相同策略指纹；已完成的三份新版缓存永久复用，不覆盖。正式全量终态尚待完成，不能把金丝雀通过等同于 186 题或 C 模型完成。旧 Lite collector、300 缓存及正在运行的 B 训练版本保持原样。两版细节见[覆盖金丝雀与执行边界](Verified运行时覆盖_金丝雀与执行边界.md)。
