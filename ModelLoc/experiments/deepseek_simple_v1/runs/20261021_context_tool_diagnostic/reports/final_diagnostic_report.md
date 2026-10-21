# 函数签名与工具协议开发诊断

生成时间：2026-10-21T15:57:24.672056+00:00。本报告仅依据现有落盘产物；未运行项保留分配数并标注 NOT_RUN。

## 一页结果

A严格主分母：签名 35/41 → 完整源码 37/41，Hit@5差 +4.88 pp；Hit@1差 +9.76 pp。Hit@5精确McNemar p=0.625，issue 95%CI [-4.88, +14.63] pp；当前不能认定显著改善，也不能因未显著而认为等效。

| 方法 | 分配/观测/完成 | 严格N | Hit@1 | Hit@3 | Hit@5 | Macro-Recall@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | 50/50/50 | 41 | 85.37% | 90.24% | 92.68% | 90.24% | 87.80% | 88.23% |
| D-COSIL | 50/50/48 | 41 | 73.17% | 78.05% | 82.93% | 80.89% | 78.05% | 76.83% |
| Q-COSIL | 50/50/40 | 41 | 21.95% | 26.83% | 26.83% | 26.83% | 26.83% | 24.39% |
| Q-PRUNER | 50/50/39 | 41 | 21.95% | 26.83% | 26.83% | 26.83% | 26.83% | 24.39% |
| A-SIGNATURE | 50/50/50 | 41 | 68.29% | 82.93% | 85.37% | 84.15% | 82.93% | 75.28% |
| A-FULL | 50/50/47 | 41 | 78.05% | 87.80% | 90.24% | 89.02% | 87.80% | 83.48% |
| D-COSIL-ADAPTER | 50/0/0 | 41 | NA | NA | NA | NA | NA | NA |
| D-COSIL-STRUCTURED | 20/20/20 | 17 | 82.35% | 94.12% | 94.12% | 91.18% | 88.24% | 88.24% |
| Q-COSIL-STRUCTURED | 20/20/16 | 17 | 29.41% | 35.29% | 35.29% | 32.35% | 29.41% | 32.35% |
| Q-PRUNER-STRUCTURED | 20/20/16 | 17 | 29.41% | 35.29% | 35.29% | 32.35% | 29.41% | 32.35% |

未完成批次的 all_allocated 数字将待运行题暂记零，属于当前累计下界；配对推断在存在 NOT_RUN 时不计算。context_overflow、上游失败及实际请求失败计入主分母。7道部分可映射题的辅助指标只评分可映射函数子集，不代表该题完整gold召回；2道不可映射题标NA。41题严格主分母包含实际运行失败。

历史最终评价器由 analysis/evaluation_extension.py 提供精确 path::qualified_name 身份；同名property多span共享ID，重复和无效预测占原排名槽，评分集合交集不去除槽位。未调用任何会覆盖旧报告的历史入口。

历史原始输出离线复算：D-SIMPLE 38/41；D-COSIL 34/41；Q-COSIL 11/41；Q-PRUNER 11/41。

## 甲：完整源码相对签名的增量

A严格主分母：签名 35/41 → 完整源码 37/41，Hit@5差 +4.88 pp；Hit@1差 +9.76 pp。Hit@5精确McNemar p=0.625，issue 95%CI [-4.88, +14.63] pp；当前不能认定显著改善，也不能因未显著而认为等效。

上游固定原50题D-SIMPLE的实际 loaded_whole_files，不按gold、grep或原最终预测补选。两臂相同候选、路径顺序、排名指令、模型和采样；仅完整源码块有无不同。全部grep来源块都排除，即使原complete_file=true。AST保留nested/async/property/重复定义；默认值和注解表达式统一160字符长度限制，原始源码不截断。

80K o200k cap约束路径+候选+源码context，不含共同system和Issue。A共分配100个最终排序臂，预登记97个可发送请求、3个FULL上下文溢出；溢出仍保留在主分母。

| FULL−SIGNATURE指标 | 配对严格N | 差值(pp) | issue bootstrap95%(pp) | 仓cluster95%(pp) | 精确McNemar p |
|---|---:|---:|---|---|---:|
| hit_1 | 41 | +9.76 pp | [+2.44, +19.51] pp | [+0.00, +21.44] pp | NA |
| hit_3 | 41 | +4.88 pp | [-7.32, +17.07] pp | [-6.25, +16.67] pp | NA |
| hit_5 | 41 | +4.88 pp | [-4.88, +14.63] pp | [-6.25, +16.67] pp | 0.625 |
| recall_5 | 41 | +4.88 pp | [-4.88, +14.63] pp | [-6.25, +16.67] pp | NA |
| all_coverage_5 | 41 | +4.88 pp | [-4.88, +14.63] pp | [-6.25, +16.67] pp | NA |
| mrr_10 | 41 | +8.19 pp | [+1.18, +16.67] pp | [+0.45, +18.18] pp | NA |

Hit@5同题四格：{"both_correct": 34, "SIGNATURE_win": 1, "both_wrong": 3, "FULL_win": 3}。条件双方成功子表见 paired_comparisons.csv 的 completed，严格取同题双方完成交集，不能替代全体分母。method_summary.csv 的单臂completed各用自身完成题分母，不作为配对效应。10,000次重采样，seed=20261021；多个指标均为探索性，不因p>0.05或区间跨零声称等效。

全分配50题资源：SIGNATURE输入token 256,856，FULL 1,385,428，总量FULL/SIGNATURE=5.394×；FULL有3题未发送，输入和费用记零，这个总量比包含该分配策略代价。
双方成功同题47对（其中严格40对）的输入token：SIGNATURE 225,820，FULL 1,385,428，FULL/SIGNATURE=6.135×。下面把这组同题资源与全分配口径分开列出；严格条件定位指标仍只用双方成功严格交集。

| 资源群体 | 臂 | N/有请求记录 | 输入token 总/mean/median | 输出token 总/mean/median | 费率推算USD 总/mean/median | 最终阶段处理秒 mean/median |
|---|---|---:|---:|---:|---:|---:|
| 全分配50题（含未发送） | A-SIGNATURE | 50/50 | 256856/5137.12/5073 | 9956/199.12/224.5 | 0.044426736/0.000888535/0.000892575 | 2.0086/1.61743 |
| 全分配50题（含未发送） | A-FULL | 50/47 | 1.38543e+06/27708.6/25792.5 | 8851/177.02/220 | 0.206896704/0.004137934/0.003936768 | 2.35487/2.16092 |
| 双方成功47同题对 | A-SIGNATURE | 47/47 | 225820/4804.68/4257 | 9245/196.702/224 | 0.039344736/0.000837122/0.000766950 | 2.00092/1.60441 |
| 双方成功47同题对 | A-FULL | 47/47 | 1.38543e+06/29477.2/26982 | 8851/188.319/221 | 0.206896704/0.004402058/0.004104000 | 2.48641/2.19115 |

全分配均值以每臂全部分配题为分母；未发送溢出的输入/费用为零，处理墙钟仍可能有准备开销。双方成功均值/中位数严格使用同一批issue，不把单臂各自completed样本混作配对。

严格41题（实际41）候选gold Macro覆盖率 97.56%，整文件gold Macro覆盖率 97.56%；所有gold均在候选内的题数 40/41。
有gold仅完整出现在被排除grep证据的题数 0；身份和源码span证据仅在私有离线coverage_offline_audit.csv中列出，未反馈给模型或候选构建。

FULL实际成功送达请求的整文件gold覆盖（溢出/未发送记零）Macro均值：97.56%。
任务提交顺序按SHA奇偶交替，但4线程并发不能保证真实wire先后平衡；按首次attempt receipt开始时间记录：{"FULL_first": 21, "SIGNATURE_first": 26, "no_paired_wire_receipt": 3}。
完整源码天生增加输入token；这里只能解释为增加完整源码信息的增量及其代价，不能直接归因于深层语义理解或等token预算。按仓库和单/多函数gold分组见 grouped_metrics.csv。

## 乙：工具格式、参数与真实收益

同一固定20题的严格可映射子集比较：D-COSIL 16/17 → 16/17（精确p=1）；Q-COSIL 5/17 → 6/17（精确p=1）；Q-PRUNER 5/17 → 6/17（精确p=1）。
D侧源码取回增加而Hit@5未增加；Q/Q-PRUNER各增加一个命中，三项精确McNemar p均为1.0，没有显著配对证据。严格格式检查率上升不能推导工具更有效或稳定定位收益，尤其Q侧执行与源码传递可能下降；现有证据不足以归因工具能力改善。

D-COSIL：整段严格合约 71.34%→91.57%；真实执行/动作 125/157→153/178；成功返回源码 124→152；Agent完整源码题 20/20→20/20。
Q-COSIL：整段严格合约 48.75%→62.50%；真实执行/动作 148/160→100/160；成功返回源码 82→43；Agent完整源码题 8/20→6/20。
Q-PRUNER：整段严格合约 48.75%→62.50%；真实执行/动作 148/160→100/160；成功返回源码 79→42；Agent完整源码题 9/20→6/20。

[DeepSeek官方DSML编码约定](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/encoding/README.md)规定单U+FF5C分隔标签；本轮严格遵照原文，不归一化重复分隔符。

B0零API静态审计复现历史动作。DSML候选 68，严格官方单U+FF5C标签可接受 0；旧43段是重复双U+FF5C标签被旧审计正则归一化后的宽松结构诊断，不能追认为严格可解析或历史执行。

| 历史方法 | 动作 | 原解析失败 | 执行/成功 | 严格DSL可接受 | 源码返回 | Agent有效请求见完整源码 |
|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | 411 | 81 | 301/298 | 275 | 298 | 185 |
| Q-COSIL | 400 | 33 | 367/233 | 197 | 233 | 107 |
| Q-PRUNER | 392 | 34 | 358/201 | 196 | 201 | 119 |

B1状态 BLOCKED_FAIRNESS，未进行在线D-COSIL-ADAPTER。原历史解析允许自由文本夹带一次DSL；新严格完整响应DSL仅275条可接受，原解析通过330条（含退出）。把严格DSL和DSML同时换入会改变超过accept_strict_dsml一个开关，构成混杂；68段DSML又全部不符合严格标签，不能自动修复后称为纯格式兼容。B1不能提供在线定位增益结论。

B2预登记同一固定20题，三个方法各自复用对应历史方法的文件起点及初始状态，不能声称不同模型统一了文件起点。实际协议是严格文本JSON，native tool_calls=False；约束由prompt加本地parser实现，provider json_mode=False且未发送response_format，未启用服务端JSON-schema/grammar constrained decoding。不能据fence失败断言Qwen不支持服务器JSON模式；服务器约束能力仍需另行独立验证。本轮是接口方案对照，轨迹变化不能全部归因parser。

| 方法/群体 | 分配/群体/完成 | Hit@5 | 语法合约率 | 目标存在率 | 执行成功率 | Agent收到源码题数 | 起点同自身历史 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D-COSIL-STRUCTURED/all_allocated | 20/20/20 | 94.12% | 91.57% | 99.35% | 99.35% | 20 | 100.00% |
| D-COSIL-STRUCTURED/entered_search | 20/20/20 | 94.12% | 91.57% | 99.35% | 99.35% | 20 | 100.00% |
| D-COSIL-STRUCTURED/completed | 20/20/20 | 94.12% | 91.57% | 99.35% | 99.35% | 20 | 100.00% |
| Q-COSIL-STRUCTURED/all_allocated | 20/20/16 | 35.29% | 62.50% | 43.00% | 43.00% | 6 | 100.00% |
| Q-COSIL-STRUCTURED/entered_search | 20/16/16 | 42.86% | 62.50% | 43.00% | 43.00% | 6 | 100.00% |
| Q-COSIL-STRUCTURED/completed | 20/16/16 | 42.86% | 62.50% | 43.00% | 43.00% | 6 | 100.00% |
| Q-PRUNER-STRUCTURED/all_allocated | 20/20/16 | 35.29% | 62.50% | 42.00% | 42.00% | 6 | 100.00% |
| Q-PRUNER-STRUCTURED/entered_search | 20/16/16 | 42.86% | 62.50% | 42.00% | 42.00% | 6 | 100.00% |
| Q-PRUNER-STRUCTURED/completed | 20/16/16 | 42.86% | 62.50% | 42.00% | 42.00% | 6 | 100.00% |

B2还显式声明原dispatcher已支持的第五个canonical工具 get_functions_of_class；原TOOL_REQUEST只示四个。这没有扩执行白名单，但提高了已有元数据工具可见性，属于接口表示/约束差异，不能视为纯parser因果效应。

各B2方法与自身历史的all_allocated/entered_search/completed配对差、有效工具提议率、首次源码轮次、重复错误和最终无效输出率详见 method_summary.csv / paired_comparisons.csv；进入搜索前失败保留，不用重新选文件掩盖。完整源码返回、主裁判见到、小裁判见到、搜索Agent下一次有效请求收到分别统计。原始seen事件只证明字节在某请求中可见；离线因果送达口径要求judge对应本次retrieval同轮/source_id，Agent还须同step/tool/args的context_accept及之后有效node/final请求全字节可见。较早接受的同源码或后续class正文包含旧函数，只记byte_visible观察，不算该次reject动作送达。

## B2同题机制与资源对照（固定20，历史50另保留）

| 方法 | 同题分配/观测 | 整段严格合约率 | 真实执行/动作 | 目标存在率 | 执行成功率 | Agent见源码题数 | 导航HTTP输入累计 | 导航USD实际/峰未缓存 | 导航区间秒mean/median/p90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D-COSIL | 20/20 | 71.34% | 125/157 (79.62%) | 99.20% | 99.20% | 20 | 1.50528e+06 | 0.0782681/0.467947 | 19.4805/17.8424/31.3588 |
| D-COSIL-STRUCTURED | 20/20 | 91.57% | 153/178 (85.96%) | 99.35% | 99.35% | 20 | 1.86158e+06 | 0.050292/0.571545 | 21.593/20.8471/30.1947 |
| Q-COSIL | 20/20 | 48.75% | 148/160 (92.50%) | 55.41% | 55.41% | 8 | 1.37693e+06 | NA/NA | 48.4616/47.0433/72.3014 |
| Q-COSIL-STRUCTURED | 20/20 | 62.50% | 100/160 (62.50%) | 43.00% | 43.00% | 6 | 1.3554e+06 | NA/NA | 45.4673/42.8774/57.6054 |
| Q-PRUNER | 20/20 | 48.75% | 148/160 (92.50%) | 53.38% | 53.38% | 9 | 1.3566e+06 | NA/NA | 47.4013/48.6094/65.7524 |
| Q-PRUNER-STRUCTURED | 20/20 | 62.50% | 100/160 (62.50%) | 42.00% | 42.00% | 6 | 1.32273e+06 | NA/NA | 44.0433/42.2274/56.8648 |

整段严格格式合约是离线按完整响应检查DSL或JSON；历史运行parser允许fence/prose夹带单次DSL，所以严格合约率与历史实际接受/执行率是两种口径，不能互相替代。b2_matched_method_summary.csv仅取冻结b2_ids中的同20题；旧方法全50的B0综合审计保留。all_allocated、entered_search和completed分别列出，后两者是各自条件分母；逐题配对b2_mechanism_pairwise.csv另标双方进入/完成，不把不同条件分母当同题效应。

导航资源两侧均只计node_selection/pruner/final_summary回执，排除file/initial_selection。导航墙钟从首个node attempt开始至末个final_summary回执结束；未到final时取末次已观察导航回执结束并标记边界/是否闭合。本次elapsed与旧whole-pipeline elapsed均保留但不可直接比较；模型加载、CPU构图和小裁判同步前向wall另列，不宣称相对于历史完整流程的节省。回执实际价格时段不同，峰时未缓存归一列用于区分token资源与价格折扣，不能把折扣归因于协议。区间均值/分位数只对可观察完整边界计算，CSV另列每字段observed_n。这里仅做descriptive配对，不扩大检验。

## 丙：剩余失败机制与可辨识边界

| 方法 | 进入前失败 | 调用后无源码 | 返回但Agent未见 | Agent见源码仍Hit@5错 |
|---|---:|---:|---:|---:|
| D-COSIL | 1 | 0 | 0 | 7 |
| Q-COSIL | 8 | 4 | 11 | 13 |
| Q-PRUNER | 8 | 4 | 10 | 14 |
| D-COSIL-STRUCTURED | 0 | 0 | 0 | 2 |
| Q-COSIL-STRUCTURED | 4 | 8 | 2 | 4 |
| Q-PRUNER-STRUCTURED | 4 | 8 | 2 | 4 |

分类描述可观测事件链，不能仅凭执行成功宣称定位改善。gold_direct_prune只计实际源码返回、源码SHA可核且真实reject对应gold path::QN身份；另列裁判完整收到源码子集，并按小裁判router reject、gray→主裁判reject、直接主裁判reject区分。源未取回、文件选择漏召回均不是误剪。重复QN只说明gold身份被拒，未核实gold修改span，不称实际修改实现被剪。hash有效不等于源码完整；小裁判部分/不同span输入单列。对于“Agent见了某些源码仍选错”，现有证据通常不能区分模型推断、搜索策略或未读到真正根因；目前不能区分。

## gold身份实际reject：离线归因边界

当前观察到1个gold身份实际reject；零次观察不代表裁判安全：gold可能根本未被选择/取回，或传递证据不足，无法据此评价见到真实修改源码后的误剪风险。

| 方法 | 小router reject | gray→主reject | 主judge reject | 其中完整judge送达 |
|---|---:|---:|---:|---:|
| D-COSIL | 0 | 0 | 1 | 1 |
| Q-COSIL | 0 | 0 | 0 | 0 |
| Q-PRUNER | 0 | 0 | 0 | 0 |
| D-COSIL-STRUCTURED | 0 | 0 | 0 | 0 |
| Q-COSIL-STRUCTURED | 0 | 0 | 0 | 0 |
| Q-PRUNER-STRUCTURED | 0 | 0 | 0 | 0 |

## 费用、时间与计算范围

本轮新增请求 850；按usage/缓存/时段费率推算API USD $0.301615467，峰时未缓存归一USD $1.086799；未知计费请求 0，保守已记/预约上界 $0.603231，独立硬限 $3.00。这是费用推算而非逐笔账单；旧run费用未并入cost_ledger.csv。

| 方法 | 计时范围 | 秒mean/median/p90 | HTTP输入token mean/median/p90 | HTTP输出token mean/median/p90 | 费率推算USD | 峰时未缓存USD |
|---|---|---:|---:|---:|---:|---:|
| D-SIMPLE | historical_whole_localization_pipeline | 11.3854/8.36496/11.3795 | 90357.2/92050.5/126330 | 431.68/379.5/739 | 0.699747 | 1.38126 |
| D-COSIL | historical_whole_localization_pipeline | 83.7636/40.324/183.079 | 91338/87810/145265 | 1486.52/1483.5/1919.4 | 0.460094 | 1.45926 |
| Q-COSIL | historical_whole_localization_pipeline | 100.925/102.094/145.773 | 79199.2/79072.5/148237 | 1077.22/1078.5/1611.8 | NA | NA |
| Q-PRUNER | historical_whole_localization_pipeline | 127.062/122.219/206.39 | 75957.5/74818/150387 | 1044.2/1018/1498.4 | NA | NA |
| A-SIGNATURE | final_ranking_only | 2.0086/1.61743/2.30398 | 5137.12/5073/9494.4 | 199.12/224.5/266.5 | 0.0444267 | 0.089004 |
| A-FULL | final_ranking_only | 2.35487/2.16092/3.10668 | 27708.6/25792.5/56576.8 | 177.02/220/253.9 | 0.206897 | 0.42625 |
| D-COSIL-ADAPTER | frozen_initial_state_to_final_ranking | NA/NA/NA | NA/NA/NA | NA/NA/NA | NA | NA |
| D-COSIL-STRUCTURED | frozen_initial_state_to_final_ranking | 22.6525/21.1394/31.467 | 93078.9/93266.5/131793 | 544.65/508.5/765.6 | 0.050292 | 0.571545 |
| Q-COSIL-STRUCTURED | frozen_initial_state_to_final_ranking | 37.7353/40.1763/58.9171 | 67770/69228.5/117650 | 385.5/443.5/567.9 | NA | NA |
| Q-PRUNER-STRUCTURED | frozen_initial_state_to_final_ranking | 60.4329/51.0752/131.103 | 66136.6/68577/113283 | 377.95/432/558.7 | NA | NA |

A为最终排序阶段，B2为冻结初始搜索状态后至最终排序，历史为完整定位流水线；这些墙钟不能直接作等阶段速度比较。价格与版本依据2026-10-21核验的[DeepSeek官方价格页](https://api-docs.deepseek.com/quick_start/pricing/)：峰时输入miss/hit/输出分别USD0.3/0.006/1.2每百万token，off_peak乘0.5。表中USD直接使用API费率，7 CNY/USD仅沿用预算换算，不把美元结果再解释为人民币。off_peak实际费用与峰时未缓存归一费用分别保留；未知缓存/计费不伪报精确账单。Qwen/小裁判的USD空值不表示零成本，直接GPU计算秒未测得标NA，服务启动另见service记录。

## 本地小裁判计算与全部模型token

| 方法 | 分配/观测N | HTTP输入累计 | 小裁判输入累计 | 全部模型输入累计 | 小裁判输出累计 | 每题累计同步forward wall秒 总计/mean/median/p90 |
|---|---:|---:|---:|---:|---:|---:|
| D-SIMPLE | 50/50 | 4517859 | 0 | 4517859 | 0 | 0/0/0/0 |
| D-COSIL | 50/50 | 4566900 | 0 | 4566900 | 0 | 0/0/0/0 |
| Q-COSIL | 50/50 | 3959958 | 0 | 3959958 | 0 | 0/0/0/0 |
| Q-PRUNER | 50/50 | 3797873 | 208477 | 4006350 | 0 | 63.1034/1.26207/0.812786/3.07033 |
| A-SIGNATURE | 50/50 | 256856 | 0 | 256856 | 0 | 0/0/0/0 |
| A-FULL | 50/50 | 1385428 | 0 | 1385428 | 0 | 0/0/0/0 |
| D-COSIL-ADAPTER | 50/0 | 0 | 0 | 0 | 0 | 0/NA/NA/NA |
| D-COSIL-STRUCTURED | 20/20 | 1861579 | 0 | 1861579 | 0 | 0/0/0/0 |
| Q-COSIL-STRUCTURED | 20/20 | 1355400 | 0 | 1355400 | 0 | 0/0/0/0 |
| Q-PRUNER-STRUCTURED | 20/20 | 1322733 | 41975 | 1364708 | 0 | 15.1612/0.758058/0/2.63741 |

HTTP与小裁判使用各自tokenizer；累计总数是资源记账之和，不能当作同tokenizer等预算。表中mean/median/p90是每个已观测分配issue的累计forward墙钟分布，含0次判决题（历史50题、新B2 20题，N见表），不是单次prediction时延。小裁判forward_seconds包含CUDA同步前后墙钟，是已观测本地前向时间，不是GPU kernel计算秒；不把其token纳入DeepSeek美元账单。小裁判加载及CPU建图/渲染耗时在method_summary另列，不能把HTTP请求重叠耗时相加当GPU计算时间。

| 新服务阶段 | GPU0 owned进程allocated wall秒 | 启动wall秒 |
|---|---:|---:|
| smoke | 539.979 | 70.8624 |
| full | 783.509 | 34.4246 |

服务驻留范围由phase_history内自有进程开始至shutdown记录，属于allocated wall，不是GPU kernel秒。smoke/full分别归档，避免服务记录replace造成漏计。

## 复现与限制

历史D-SIMPLE 38/41包含原grep证据及旧prompt，也没有本次完全相同的显式候选函数清单，仅作观察参照；不能把它与A-FULL 37/41的差异归因于源码。D-SIMPLE是CQ2-inspired流程的函数级扩展，不是论文官方函数定位方法，也没有验证修复率。

本轮仅Lite公开开发诊断，不能宣称外部泛化或修复率。没有重跑上游文件选择/grep，不执行历史模型工具输出，不碰封存holdout/裁判test，不训练、不跑修复测试或SWE-rebench。DeepSeek显式thinking=disabled，模型别名deepseek-flash及文档版本DeepSeek-V4.1-Flash-1017保留于配置/回执。请求未固定DeepSeek seed，API别名不能独立锁定服务端权重快照；不冒称完全确定性或可逐字复现模型输出。

CPU测试56项全部通过。 本轮GPU0/2自有模型进程已关闭，服务退出归档见phase_history。

CPU测试与独立离线报告命令见 README_如何复现.md。旧预测、gold映射及历史报告均只读；本报告可重建更新当前快照。
