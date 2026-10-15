# v5 A线：rank8、dropout0.1 正则处方 exploratory

用户将原训练/验证23.93个百分点的差距裁定为过拟合，本轮执行一次独立正则处方。原A数据、模型、签注、预测和报告保留。

rank16→8、dropout0→0.1；alpha维持32，所以alpha/r从2→4，这也是同时变化的因素。其余lr5e-5、最多3epoch、batch8/micro2、BF16、cutoff4096及E下降早停沿用原配置。

新checkpoint按已完成epoch的验证accuracy峰值选择，依次以AUC、E剔除率、较早epoch打破并列；原reranker的3轮accuracy峰值是epoch3，恰与其原best一致。赛马仍采用acc≥0.80、AUC≥0.85资格及E/2pp偏好规则，原instruct沿原E-best，不改其symlink。

| 条件 | epoch | train accuracy | val accuracy | val AUC | val E剔除率 | val gold保留 | 混合剔除precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_regularization | 3 | 99.41% | 75.48% | 0.8328666074721672 | 90.64% | 58.82% | 77.03% |
| post_regularization_peak | 3 | 99.36% | 73.55% | 0.8254217608086879 | 88.94% | 55.88% | 76.26% |
| post_regularization_last | 3 | 99.36% | 73.55% | 0.8254217608086879 | 88.94% | 55.88% | 76.26% |

| 条件 | TP | FN | FP | TN |
|---|---:|---:|---:|---:|
| pre_regularization | 56 | 65 | 24 | 218 |
| post_regularization_peak | 55 | 66 | 30 | 212 |
| post_regularization_last | 55 | 66 | 30 | 212 |

| 条件 | 来源membership | 样本数 | 正例保留recall | 负例正确剔除 |
|---|---|---:|---:|---:|
| pre_regularization | A | 34 | 58.82% | NA |
| pre_regularization | B | 18 | 66.67% | NA |
| pre_regularization | C | 87 | 41.38% | NA |
| pre_regularization | D | 21 | NA | 71.43% |
| pre_regularization | e_log | 21 | NA | 71.43% |
| pre_regularization | e_bm25 | 110 | NA | 87.27% |
| pre_regularization | e_anchor | 112 | NA | 98.21% |
| pre_regularization | E | 235 | NA | 90.64% |
| post_regularization_peak | A | 34 | 55.88% | NA |
| post_regularization_peak | B | 18 | 66.67% | NA |
| post_regularization_peak | C | 87 | 41.38% | NA |
| post_regularization_peak | D | 21 | NA | 61.90% |
| post_regularization_peak | e_log | 21 | NA | 47.62% |
| post_regularization_peak | e_bm25 | 110 | NA | 86.36% |
| post_regularization_peak | e_anchor | 112 | NA | 97.32% |
| post_regularization_peak | E | 235 | NA | 88.94% |
| post_regularization_last | A | 34 | 55.88% | NA |
| post_regularization_last | B | 18 | 66.67% | NA |
| post_regularization_last | C | 87 | 41.38% | NA |
| post_regularization_last | D | 21 | NA | 61.90% |
| post_regularization_last | e_log | 21 | NA | 47.62% |
| post_regularization_last | e_bm25 | 110 | NA | 86.36% |
| post_regularization_last | e_anchor | 112 | NA | 97.32% |
| post_regularization_last | E | 235 | NA | 88.94% |

来源membership有交叠，不能相加；E行是去重并集。gold保留率为未校准p≥0.5的二分类召回，包含所有普通正判，不能称为high-confidence保留，更不是已执行灰区Qwen的最终召回。

验证赛马：unqualified；Neither base satisfies val accuracy>=.80, AUC>=.85 and an evaluable E group。

处方峰值val accuracy仍<0.80，按用户最新裁定触发Verified＋B融合扩挖条件；root负责后续实际扩挖。

原3/30分层抽检不是总体噪声率或静态噪声地板证明；train为拟合样本表现，尚不能宣称泛化或端到端定位提升。test仍封存、Qwen基线未重跑、Decision-1取消、没有新增定位对照列。

结构化结果：`results/v5_pruner/A_rank8_dropout01_exploratory/outcome/assessment_report.json`。

## 完成后补充说明

本轮真实 train accuracy 为 99.3624%，val 为 73.5537%，差距为 25.8087 个百分点。原 rank16 的 val 为 75.4821%，本轮少命中 7/363 个验证样本，下降 1.9284 个百分点；训练表现依然接近满分。这一轮 rank8＋dropout0.1 的具体处方没有缓解已观察到的过拟合，不能据此认定所有正则方法均无效，也不能把差距全部归因于标签噪声。

epoch2 与 epoch3 的 val accuracy 同为 267/363；epoch3 的 AUC 更高，所以按已冻结并列规则选择 epoch3，best 与 last 相同。原 instruct 仍使用原 E-best epoch2 参加赛马。两底座均未达原 accuracy/AUC 资格，没有合格胜者，未执行 test 或管线定位。

本轮峰值的 [gold 三分路由诊断](../../results/v5_pruner/A_post_regularization_peak_gold_routes_exploratory/gold_route_report.md) 将未校准二分类召回与直留／灰区／直剪分别列出。raw 阈值 L=0.6、H=0.9 时，34 个 gold 中直留17、直剪15、灰区2；19/34=55.88% 是 p≥0.5 的普通二分类召回。校准与 val-safety 路由仍是验证诊断，灰区未调用 Qwen，不是最终 hybrid 召回。

处方 val<0.80 满足最新用户规定的扩挖触发条件，但历史 OOD231 的确切 issue 身份清单尚未找到，Verified＋B 融合扩挖未执行。根分支收据只放行既有 Lite300 范围的 B runtime 过滤独立对照；这次 B 不能称为 Verified 扩容或零噪声实验。公开 Verified 元数据的取得不等于完成所要求的排除与挖矿。

资源终态中的 `peer_processes_changed:false` 只表示本实验没有停止或修改他人进程；他人的仿真 PID 可以自然变化。本轮自己的训练进程已退出并释放显存，没有停止 GPU0 的 vLLM 或其他常驻服务。

后续用户已明确授权重生成权威 OOD manifest：先从官方 Verified500 排除与 Lite 的93题交集，再对余407题按 AST gold 函数简单名称在 issue 中是否出现（忽略大小写）判定，真实题数允许不等于231。因此，上述“缺历史231身份”的说明记录的是本轮完成时的历史依赖；新来源重建、扩挖与 runtime 核验现以独立 C 轨道准备，原 A/B 冻结记录保持不变。本轮 A 报告不将后续尚未完成的 C 数据或训练记为已经完成。
