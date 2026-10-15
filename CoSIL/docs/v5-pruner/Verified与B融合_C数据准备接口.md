# Verified 与 B 融合：C 数据准备接口

本分支单独实现数据构造、审阅派生及授权，不改变已冻结 A/B 数据或训练代码。Verified 静态扩挖与独立运行时采集现均已完成 186 题；新30条源证据审阅的partial已完成；实际RAW引用签注与最终C训练授权尚未完成，C训练准入仍关闭。

- 构造入口：`python -B -m code_v5_verified.prepare_expanded_runtime_data`。默认 dry-run；未收到完整静态终态及全部 186 份正式 runtime result、最终采集审计即拒绝。`--freeze --authorization <新根构造授权>` 才创建 `results/v5_pruner/data_verified_plus_B_runtime`。
- 签审阅及派生：`python -B -m code_v5_verified.freeze_expanded_decision --review <新30条完整证据签注>`。创建独立 `data_verified_plus_B_runtime_reviewed`；原 B 历史保持。
- 冻结训练授权：以上入口另传 `--contract <最终根C协议>`。仅在真实统计、完整源码＋运行时审阅和精确删除均齐后生成 `C_Verified_plus_B_runtime_authorization_exploratory/root_exploratory_decision.json`。
- 训练 gate：`code_v5_verified.expanded_policy.validate_decision(data_dir, decision_file)` 返回 `(stats, seal, split_ids, provenance)`。`exploratory_quality_gate_passed` 表示本分支真实质量与完整性通过；历史正式数量与噪声门保持 `formal_data_gate_passed:false`。不将探索性授权写成原正式门全部通过。

构造先复制 B 已选 4,618 行（正例 1,542），保留原 Lite240/30/30 切分及所有旧输入/标签，新 186 题150/18/18 按原 seed 固定。新数据仅 A/C/D/e_bm25/e_anchor；不制造不存在的 B/e_log。静态去重和旧输入碰撞剔除已完成后，不在 runtime 过滤后再次改变正例资格，防止先前被去掉的 C 复活。

新负例须已通过 v3 原静态保守排除；只有完整 existing-gold、全部 FTP 精确测试真实 call 失败、来源和 trace 可核验时，才以失败路径＋bootstrap 覆盖补充过滤。候选若来自 test_patch 修改的测试文件，物理行映射不可借缺席作双证据，逐行降为 static-only。失败或不完整运行如实保留静态标记。覆盖缺席从不证明无因果关系或零噪声。

历史原3＋B新8个 unsafe TRAIN 身份永久排除。新 C 30 条三族各10均须真实 TRAIN 来源、完整候选及全部 base gold 源码、原静态见证和 runtime 引用，不能凑重复或只做过滤器机械通过。签注明确区分已证源码关系与条件风险；新确认 unsafe 全部从 C TRAIN 精确删除，包括新增发现的旧 Lite TRAIN 负例，不覆盖原 B 数据。标签不翻转、不补新标签，val/test及issue split字节保持。剩余22或其他数量不能作为新随机审阅通过。

源构造阶段可从源 pool 机械构建含 test-role 的候选/选中缓存，封存 `pruner_test.jsonl` 文件从不解码，模型 gate 只核构造回执、源文件 hash、train/val 与 test 字节 hash，不重放 test-role 训练标签，不评估 test 性能。共享 B/C val 按 instance_id＋function_id＋input SHA＋相同标签列出，报告完整 val 和共同子集。

目前14项早期 CPU 守卫通过，范围仅源码 schema、已冻结 Lite trace 的内存 schema fixture、合成候选及拒绝测试：原11条排除、raw/不完整 C gate关闭、封存 test 和 symlink拒读、完整金标与精确 FTP 选择、修改测试文件逐行 fallback、仅移除合格 covered negative、正例资格保持、真实负例不足数量披露。该收据不是最终 C 数据审计，实际完整数据、终态新根授权、30条签注及篡改守卫尚待完成。

C 专用模型队列要求 B 完整两底座、赛马与报告真实终态，并需根队列收据匹配 C 冻结授权。当前没有 C 模型结果，不加载权重，不使用 GPU。

## 构造前独审修复（生产数据未冻结）

独审发现原 C 草稿仅凭 `source_evidence_complete` 与 truthy Gold 字段可接受空壳审阅 packet，且 boolean note/refs 未被拒绝；真实 v2 终审文件名也与消费端不一致。反例只使用明确标记的 CPU fixture，没有生产数据、签注或模型准入通过。已修正上述问题并保留历史反例报告。

现在 prepare/derive/freeze 都重读真实 base Git blob，核 SHA1、Python 编码声明、AST 限定名＋物理 def 行、完整候选及全部 existing Gold 源码与特征、官方全文/patch、真实 graph 和 runtime 资格/静态标记。机械回执不代替逐条标签审阅。模型 gate 只核冻结回执、30条 TRAIN typed packet、train/val 和源/test字节 hash，不重放 test-role 矿池。

签注 note 必须非空字符串，refs 必须是绑定实际 packet 文件 SHA、具体记录 SHA 与 candidate/gold/runtime/graph/static 五类证据的结构对象。来源不完整、boolean 伪签、记录 SHA 不一致、缺证据章节、改变历史标签均拒绝。历史11个 unsafe 以 issue＋function pair 永久排除，不能更换 input SHA 复活。

正式运行时准入采用 `runtime_coverage_verified_v2/final_completion_independent_audit.json`，要求 formal 阶段、实际 completed=expected=186、errors为空，且与 formal plan/terminal/root授权/core/audit代码/collector代码、全部 case/result/trace SHA 一致。金丝雀的 passed 不能冒充全量终审。原 Lite split 与新增 split 都须精确重现冻结计划；raw 文件清单与完整源文件清单不能缩减成任意单个文件。

原 B 先完整复制，新增发现的旧 Lite TRAIN unsafe 仅在 C 新版本精确 mask；逐行删除 ledger 与全 source/repo/anchor 计数均重算。统计同时列 raw-before-review 和 reviewed-after-exclusion 的新题、旧 B 计数。旧 val/test/split 与 B 历史数据保持，不能用 train/val 重算冒充 test 开箱。

P8000 可按用户裁定待探索性重定标；E3000 不设泛豁免。E 数量若实际达标，不允许挂一个备用豁免；若因完整30条精确 TRAIN E 删除而略低，须单独记录 raw_E/deleted_E/derived_E、原审阅 SHA 与根特定授权，源供给不足不算此理由。D-only、1:2 比例、E比例、切分、去重、泄漏和完整审阅均不得混进数量豁免名单。

16项修复 targeted CPU 守卫已通过，包含空壳完整 flag、typed notes/refs、证据绑定/章节、历史 pair 复活、label翻转、泛 E/D/比例豁免、真实 passed 金丝雀冒充186终态、封存 test拒读与完整计数重算。当前真实冻结 B30 TRAIN 源码 schema 兼容也已逐 Git/AST/Gold/graph/runtime 核验；这仅证明新审计器兼容现有真实证据，不是 C 新30条标签结论。生产 C 构造、独立终态审计、Codex逐条证据结论（非真人签字）和训练仍须实际完成后单独签注。

## C4：按原 1:2 规则补齐联合 TRAIN（只修采样，不放宽质量门）

实际扩后源构造预览为 P4,950/N8,848，N/P=1.7875，低于原 1.8 下界；该失败预览、C3 helper 与原51项独审已完整归档，不能改成通过。根代理随后签署仅实现阶段的 `C4_joint_TRAIN_sampling_implementation_decision.json`，允许从原 B 已冻结 eligible pool 增加未选中的 D-only TRAIN 样本，保持当前已选所有行、E成员、正例、val/test与切分。

联合 TRAIN 的目标仍为原始 1:2：`2 × 4,473 − 7,894 = 1,052`。严格 D-only 供给为3,859条；排除493条已有失败路径或 bootstrap 观测（即使整题未获完整覆盖资格也排除），余3,366条。独立全供给核验对应184个真实Git文件、185题runtime结果与184份图；其中1,756条有完整runtime资格，1,610条仍为static-only。它们只具有原规则的机械负例资格，不是已证明的因果无关。

新增 `joint_train_sampling.py` 沿原 `stable_key(20261013, issue/function)` 顺序选1,052条，必须精确重现根授权绑定的独立身份及真实Git/AST源码见证。任意E成员、历史11个unsafe pair、原4个不合格C、当前已选身份、跨新增矿池inputSHA碰撞、非TRAIN、任何已观测覆盖和test_patch移动行风险均排除。旧池仅解码TRAIN行；其余role只扫描外层split/inputSHA，不解码函数、标签或封存test文件。模型gate只核冻结ledger、完整源hash和TRAIN行，不重放旧池。

实际首次修正准备已测得TRAIN P4,473/N8,946，总P4,950/N9,900/E5,055。原B统计继续单列；补齐后的旧Lite统计另列为 `old_Lite_selected_with_TRAIN_replenishment`，不能把历史B4,618行改写为5,670行。后续新审阅若精确删除旧Lite TRAIN E，派生统计从补齐后的基数减去真实删除，原B档案保持。

当前只生成新的构造预览、机械源码证据与禁用授权模板；根代理签实际构造授权之前，不创建生产raw C、训练派生集或模型结果。新30条E样本及逐条源码/runtime packet须与修正前完全相同，再汇合Codex逐条证据审阅结论（非真人签名）。源hash固定绑定旧pool、根修正裁定、独立供给审计与精确1,052条ledger；最终训练授权还须独立数据守卫与根队列收据。

C4实际准备与37项定向CPU守卫已完成，收据为 `results/v5_pruner/C_preconstruction_C4_joint_TRAIN_actual/C4_actual_preparation_and_targeted_CPU_guard_audit.json`。真实统计达到上述1:2目标；原B与新增Verified已选统计、val/test源角色元信息、新30条pending字节及全部逐条packet records都保持。拒绝测试覆盖静态fallback已有实测覆盖、三类覆盖并集、E成员、非TRAIN、known pair换input、跨池碰撞、移动测试文件、真实Git特征漂移、ledger/排序篡改、禁用构造模板与泛质量豁免；封存test文件与旧池heldout body解码均拒。该收据证明实际准备及程序守卫，不代替新30条标签审阅或最终生产数据授权。C4四个data源已交独审；原C3失败预览和51项历史收据未覆盖。

### C4-v2：完整来源清单独立拒绝

独审随后发现，第一版standalone `validate_ledger` 在 `source_artifact_sha256` 为空时仍能只核固定授权/pool来源而返回；整体构造准入还受根授权中的精确ledger SHA保护，因此未声称已绕过模型准入。第一版C4源码SHA绑定预览、37守卫与禁用模板原字节保留。

当前修补要求ledger源map精确重现全3,366条深审中的184份图＋185题runtime完整来源，不能空、少键、多自洽假键或改SHA。runtime SHA还逐项与原B冻结`runtime_manifest.result_sha256`比对，1,052条拟增身份的图SHA与独立供给审计比对；runtime manifest及全供给深审自身加入固定来源hash。模型gate只读这些元信息/hash与TRAIN行，仍不解码heldout池标签/源码。新版实际预览和守卫另存`C_preconstruction_C4_v2_joint_TRAIN_actual`，最终构造需要新版实际根授权。

C4-v2实际准备及43项定向守卫现已全部通过；真实P4,950/N9,900/E5,055和TRAIN4,473/8,946保持，原E30样本字节与全部逐条packet records不变。实际收据为 `C_preconstruction_C4_v2_joint_TRAIN_actual/C4_v2_actual_preparation_and_targeted_CPU_guard_audit.json`；新根构造模板禁用，SHA为8f12dcf96ff1442be20c4d7ef434470d4f2ad11cdca6623bcc7a8d87df71c0e1。新增完整源map守卫独立拒绝空map、缺graph、缺runtime、自洽假键及改SHA。源码已稳定交独审；该准备收据阶段未创建生产C数据或模型。

### 实际 RAW 构造已完成（训练仍未授权）

根代理另签 `C4_v2_actual_data_construction_root_authorization.json`（SHA68bb010d187b2fe0e105a7de0128828c26f7b95ef1be179615eb8c69900b95f0）后，唯一一次实际构造以exit0完成，生产RAW落盘于 `results/v5_pruner/data_verified_plus_B_runtime`。构造回执SHA为b919481f1f974b6af91cf6a1e4fed8ce9827d0b2c45d471c0d2d81e55080393f；执行日志、exit与源码不变/自有进程退出证据在 `C4_v2_actual_RAW_construction_execution/execution_receipt.json`（SHAe5da25cef5a4837f7a320930c4b2fb95b76f09d79959e8df5fcbb0dd3c58231d）。CLI以及完成后的默认构造gate均通过，旧A/B、静态11源、runtime与C6训练源保持。

该授权只物化RAW；封存test只做字节hash，没有解码或性能评估。实际30条typed引用签注由根代理另行绑定，随后才能独立派生删错训练集、冻结模型授权；本次执行没有生成reviewed训练派生、加载模型或使用GPU。
