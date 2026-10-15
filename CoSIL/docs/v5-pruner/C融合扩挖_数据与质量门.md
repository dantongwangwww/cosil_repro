# C融合扩挖：数据与质量门

C分支在保持既有Lite数据历史和切分的基础上，合并Verified静态扩挖、独立失败路径覆盖过滤和新的30条TRAIN E证据审阅。最终独立训练派生数据为 **4,950正例、9,892负例，E三族并集5,047条**。已按完整签注精确删除8条TRAIN不安全负例；标签没有翻转，没有补造新标签。本文记录数据与质量门，不提供模型效果或test性能结论。

[最终冻结统计](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/statistics.json) · [最终数据独立审计（51项）](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_final_reviewed_data_independent_audit.json)

## 1. 数据量、来源与封存边界

| 数据角色 | 正例P | 负例N | E并集 | 行数 | 读取边界 |
|---|---:|---:|---:|---:|---|
| TRAIN | 4,473 | 8,938 | 4,378 | 13,411 | 训练/验证程序可读取 |
| VAL | 238 | 476 | 352 | 714 | 体检、选checkpoint和赛马可读取 |
| 封存TEST | 239 | 478 | 317 | 717 | 本报告仅使用统计和seal元信息，未解码test文件 |
| 合计 | 4,950 | 9,892 | 5,047 | 14,842 | test性能保持封存 |

E是`e_log/e_bm25/e_anchor`的去重并集，属于负例子集，不能与N相加。最终N/P=1.9984，E/N=51.02%。旧Lite固定issue切分240/30/30保持；新增186题按同seed=20261013固定为150/18/18，合并issue分配390/48/48。部分题没有可选函数对，实际有行issue数为TRAIN359、VAL44、TEST47；这些不是重新切分的题目数量。

官方Verified500与Lite300重叠93题，非Lite407题按新权威的实际改动行＋AST函数金标/issue函数名匹配划出221题保留OOD，另186题进入扩挖。`verified231_manifest.json`是历史文件名，真实数量不强制231。新增仅使用A/C/D/e_bm25/e_anchor；没有新题日志，未制造B/e_log。原1542个正例和原4个不合格C排除资格保持，历史原3＋B新8个unsafe TRAIN pair不可重入。

[实际切分](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/split_manifest.json) · [封存TEST与全部输入字节seal](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/test_file_seal.json) · [权威OOD及eligible清单](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/verified_regenerated_ood/verified231_manifest.json)

## 2. 原比例门失败与合法联合TRAIN补齐

首轮真实融合预览只有P4,950/N8,848，N/P=1.7875，低于原1.8下界。这一质量失败没有被追认为通过；失败预览、C3代码与独审、第一版C4预览及37项守卫均保持历史归档。根代理另签采样修正实施裁定，沿用原联合1:2目标：`2 × 4,473 TRAIN正例 − 7,894 TRAIN负例 = 1,052`。

补齐只从**旧B冻结eligible pool已有、未选中的D-only TRAIN机械负例**取样。原pool的未选TRAIN负例4,988条中，严格D-only为3,859条；任何失败路径或bootstrap实测覆盖均排除，即使整题不具完整runtime资格也不借回退保留该已观测函数，实际排除493条，剩3,366条。全供给深审核184个真实Git文件、184份图、185题runtime；供给中1,756条有完整runtime资格，1,610条仍纯静态回退。它们是原规则的机械代理负例，不是已证明的因果无关。

从3,366条按原`stable_key(20261013, instance_id + '/' + function_id)`及规范身份tie-break选1,052条，必须精确复现根授权绑定的独立身份顺序与Git/AST见证。任何E成员、known11/原4C、现有已选身份与input SHA、跨新矿池输入碰撞、非TRAIN或test_patch移动行风险均排除。不借VAL/TEST，不改标签，不调整E top15/anchor/原排除规则，不再重构静态E；已有全部行、E成员、新30样本及完整逐条packet保持。

补齐后RAW为P4,950/N9,900/E5,055，TRAIN4,473/8,946；随后只删除新签8条TRAIN E，得到本报告最终数。历史B仍是4,618行，独立C的旧Lite组先增加1,052行再删除6条，最终为5,664行/P1,542/N4,122/E2,986；新Verified组删除2条后为9,178行/P3,408/N5,770/E2,061。不能把补齐后的旧Lite组改写为历史B本身。

[原比例失败预览](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_preconstruction_actual/context_summary.json) · [根采样修正裁定](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C4_joint_TRAIN_sampling_implementation_decision.json) · [独立供给审计](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_D_only_TRAIN_supply_independent_audit.json) · [全3366来源深审](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_old_B_TRAIN_D_supply_deep_readonly_audit.json) · [实际1052补齐ledger](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime/joint_TRAIN_sampling_ledger.json)

## 3. 三族30条证据审阅及8条精确删除

e_log/e_bm25/e_anchor各10条，全部原始TRAIN负例。完整候选与全部base gold的Git blob、物理AST定义、完整源码、图和真实运行证据先机械核验，再由Codex逐条证据审阅，不冒称真人核验签字。实际RAW与预览sample字节和逐条record SHA完全相同后，三份immutable partial结论才绑定actual RAW文件、记录及五类typed证据refs。

| 产线 | 审阅 | 有限证据保留 | 确认源码关系 | 条件风险 | 保守删除 |
|---|---:|---:|---:|---:|---:|
| e_log | 10 | 4 | 4 | 2 | 6 |
| e_bm25 | 10 | 9 | 1 | 0 | 1 |
| e_anchor | 10 | 9 | 1 | 0 | 1 |
| 合计 | 30 | 22 | 6 | 2 | 8 |

**8/30=26.67%是这一三族分层样本的保守排除观察，不是总体噪声率。**6条确认源码关系也不等于已定位到6条根因；2条条件风险不是确定标签错误。22条保留只是现有证据下未建立明确关系，不能认证全程序无关，也不能把删除后的22条作为新的随机审阅通过。

实际删除按规范instance_id区分为**旧Lite6条＋新Verified2条**。全部从独立C TRAIN精确删除，不翻转为正例，不删除VAL/TEST或正例，不回写B历史数据：

| 来源 | 产线 | issue | 物理函数身份 | 审阅分类 |
|---|---|---|---|---|
| 旧 Lite | e_log | `sphinx-doc__sphinx-7686` | `sphinx/ext/autosummary/__init__.py::Autosummary.get_items@285` | 条件风险 |
| 旧 Lite | e_log | `pytest-dev__pytest-5103` | `src/_pytest/assertion/rewrite.py::AssertionRewriter.visit_Assert@814` | 确认源码关系 |
| 旧 Lite | e_log | `django__django-11019` | `django/forms/widgets.py::Media.__add__@152` | 确认源码关系 |
| 旧 Lite | e_log | `sympy__sympy-19007` | `sympy/matrices/expressions/matexpr.py::MatrixElement.doit@716` | 条件风险 |
| 旧 Lite | e_log | `django__django-14238` | `django/db/models/base.py::ModelBase._prepare@330` | 确认源码关系 |
| 旧 Lite | e_log | `sympy__sympy-16792` | `sympy/utilities/autowrap.py::CythonCodeWrapper._partition_args@409` | 确认源码关系 |
| 新 Verified | e_bm25 | `django__django-12276` | `django/forms/fields.py::Field.__init__@56` | 确认源码关系 |
| 新 Verified | e_anchor | `sympy__sympy-13878` | `sympy/integrals/transforms.py::IntegralTransform.function@57` | 确认源码关系 |

[完整30条逐条说明](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/docs/v5-pruner/C融合扩挖_30条逐条审阅与签注.md) · [实际完整签注](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/human_review_codex_reviewed.jsonl) · [actual RAW身份绑定收据](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_TRAIN30_source_review_partials/C_full30_actual_RAW_binding_receipt.json) · [逐行删除ledger](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/reviewed_train_derivation.json)

## 4. 质量门的真实结论

| 门或完整性要求 | 实测/处理 | 结论 |
|---|---|---|
| P≥8,000 | P=4,950 | 原数量门未通过；依用户裁定待exploratory重定标 |
| E≥3,000 | E=5,047 | 通过；没有E数量豁免 |
| N/P在[1.8,2.2] | 1.9984 | 通过；原1.8下界保持 |
| E/N≥1/3 | 51.02% | 通过 |
| D-only保留 | 4,845条，TRAIN4,560条 | 通过 |
| 历史审阅≤2/30 | 本轮8/30保守剔除 | 历史门仍false，不追认正式通过 |
| 完整30签注、精确TRAIN删错 | 30/30，精确8条，无翻标签/替补造标签 | 独立完整性核验通过 |
| 同issue固定切分、去重/输入来源、known排除 | 原split不变，新增split与冻结提案完全相同 | 独立完整性核验通过 |
| 历史B/原数据保持、C RAW→reviewed VAL/TEST/split字节 | 独审逐项核SHA；旧B VAL363行输入、标签与顺序保留 | 通过；test文件仅hash |

数据统计保持`passed:false`及历史正式门失败；本授权下的`exploratory_quality_gate_passed:true`只表示该探索性分支完整审阅、删除、来源和完整性通过，不等于原正式数量/历史≤2门全部通过。审阅采用明确噪声披露与保守排除制度；比例、E占比、切分、去重、泄漏和完整审阅没有数量豁免。

来源inventory绑定真实root构造授权、静态186终态、runtime186终态、旧pool与B冻结manifest、全部369项补齐graph/runtime来源和1052精确ledger。standalone来源map为空、缺项、增加自洽伪源或改SHA均拒绝。准备/派生/冻结阶段重读Git/AST完整源码；模型gate只核已冻结构造回执、typed TRAIN30、train/val与源/test字节hash，不重放test-role矿池或解码封存test文件。

[C4-v2实际准备43项守卫](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_preconstruction_C4_v2_joint_TRAIN_actual/C4_v2_actual_preparation_and_targeted_CPU_guard_audit.json) · [C4-v2独审51项](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C4_v2_independent_actual_preconstruction_audit.json) · [最终reviewed独审51项](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_final_reviewed_data_independent_audit.json)

## 5. 数据与输入局限

TRAIN和VAL的标签来源分布明显不同。D-only使用primary D口径；`source_D`成员计数含来源重叠，不能代替D-only。

| 来源比例 | TRAIN | VAL | 实际差异 |
|---|---:|---:|---:|
| C类正例/全部正例 | 3,899/4,473＝87.17% | 162/238＝68.07% | TRAIN高19.10个百分点 |
| D-only/全部负例 | 4,560/8,938＝51.02% | 124/476＝26.05% | TRAIN高24.97个百分点 |

因此扩后增加数量不等于消除分布偏差；相同模型配置下训练/验证差距仍可能受来源结构影响。完整VAL和原B共同VAL子集应分别报告，不能把改变样本组成后的总体数直接当数据清理的因果收益。共同VAL按instance_id＋function_id＋input SHA＋相同标签核对。

覆盖资格也不等于函数无关：原Lite300中133题具双证据资格、167题回退；新增Verified186中88题具资格、98题回退（85 incomplete、11 unsupported、1环境失败、1timeout）。候选若在test_patch修改的测试文件中，不能把移动后行号的缺席作为双证据阴性；逐行保留runtime不可用标记。观测不到hard-exit/foreign interpreter/native C等路径的边界真实披露。本次30条按证据packet的**题级 `runtime_evidence.qualified`**计数为10条合格、20条回退，保守删除分别1/10与7/20。按实际候选行**`runtime_filter.qualified`**则是9条合格、21条回退，保守删除分别1/9与7/21。差异来自#17 `django__django-14434 / tests/schema/tests.py::SchemaTests.get_constraints_count@175`：整题合格，但候选所在文件被test_patch修改，候选行标记`candidate_test_patch_file_physical_mapping_unavailable`而回退；不能将题级资格当成这个候选的双证据阴性。上述比例都是分层审阅观察，不是覆盖机制的因果比较或零噪声证明。

固定模型输入只取issue前2,000字符和候选函数前1,500字符。**本次TRAIN30样本中8条样本的函数字段、13条样本的issue字段超限**，这一计数不外推为全数据比例。#16 `django__django-12276 / django/forms/fields.py::Field.__init__@56`完整函数3,083字符，`self.required`/`self.initial`状态赋值起始偏移1,869/1,896，`widget.is_required`在2,496，实际`self.widget = widget`赋值在**零基字符偏移2,738**。这些均位于1500字符输入之外；`self.widget`第一次文本出现2,127不能冒充实际赋值位置。完整证据可查到FileField→Field状态保存→BoundField/widget路径，而固定候选输入缺少这些状态关系。本例已按审阅结论从C训练中精确剔除，保留此诊断用于说明原固定输入的可见性限制；尚不能据此认定任何模型误判原因。

[固定输入可见性审计](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_TRAIN30_source_review_partials/C_TRAIN30_fixed_input_visibility_audit.json) · [完整候选/base gold/runtime证据](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime/review_source_runtime_evidence.json) · [B/C共同VAL身份表](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/comparison_B_C_val_shared_pairs.json)

## 6. 原始回执与可复核入口

| 证据 | 入口 | SHA256 |
|---|---|---|
| 实际RAW构造 | [construction_receipt.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime/construction_receipt.json) | `b919481f1f974b6af91cf6a1e4fed8ce9827d0b2c45d471c0d2d81e55080393f` |
| 最终数据统计 | [statistics.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/statistics.json) | `bfe26e7f7827c93196c317eabcd38e993ffcbc3c2c7c351db27ad2c2eeaacd2a` |
| 最终30签注 | [human_review_codex_reviewed.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/human_review_codex_reviewed.jsonl) | `72b2bc46412110281ede8d8c4bbd28927f1fa14589488fdcb7e32e132734978b` |
| 精确8条派生删除 | [reviewed_train_derivation.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_verified_plus_B_runtime_reviewed/reviewed_train_derivation.json) | `c41857c9b221fd7d56885eeaf9dc4a9490ce395d887cb98ea7679a80d3236409` |
| 最终数据独审 | [C_final_reviewed_data_independent_audit.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_final_reviewed_data_independent_audit.json) | `2ffe5d8233a777f078bc6c5d3b4a1205e64f4c34fc1f97cc74ed7104d167dd69` |

[官方Verified快照与身份对齐来源](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/external_sources/verified_official/official_verified500_provenance_and_identity_receipt.json) · [静态扩挖186真实终态](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/verified_extension_regenerated_ood_v1/static_preparation_receipt.json) · [Verified运行时186独立终态](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/runtime_coverage_verified_v2/final_completion_independent_audit.json) · [实际RAW根构造授权](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C4_v2_actual_data_construction_root_authorization.json) · [执行日志与exit/资源收尾](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C4_v2_actual_RAW_construction_execution/execution_receipt.json)
