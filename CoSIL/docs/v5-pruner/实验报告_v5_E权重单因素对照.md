# v5 E训练权重单因素对照

完成时间：2026-10-15T19:00:19.138201+08:00。exploratory；仅train/val，test继续封存。

**本次E=0.5没有带来一致收益。**按原规则选择best后，reranker AUC由0.84635降至0.78681，gold直剪28→29；instruct AUC由0.82059降至0.79833，gold直剪33→32。两者gold直剪率变化的配对区间均跨0；不能将相差1条解释为稳定改善，也不能据此量化标签噪声的独立伤害。

使用与C阶段完全相同的train13,411、val714；训练E并集4,378条从1.0降为0.5，其余样本权重1.0。未删样本、翻标签、改采样、分词、截断、底座或训练处方。

每个底座沿用原选模/早停规则。主表比较各自按原规则选择的best，另列同epoch对照；没有按gold指标重新挑epoch。

| 底座/条件 | best epoch | train acc | val acc | val AUC | E剔除率(p<0.5) | 混合集剔除precision | gold召回(p≥0.5) |
|---|---:|---:|---:|---:|---:|---:|---:|
| reranker / 原C E=1.0 | 2 | 98.75% | 77.87% | 0.84635 | 88.92% | 79.34% | 63.16% |
| reranker / E=0.5 | 3 | 99.61% | 75.49% | 0.78681 | 82.67% | 79.34% | 61.84% |
| instruct / 原C E=1.0 | 3 | 99.36% | 79.69% | 0.82059 | 94.60% | 80.04% | 64.47% |
| instruct / E=0.5 | 3 | 99.41% | 78.29% | 0.79833 | 92.61% | 79.56% | 60.53% |

## 固定阈值的gold直留、直剪、灰区

使用未校准概率与原low=0.6/high=0.9：p≤0.6直剪、p≥0.9直留，其余灰区。没有运行灰区Qwen；这些是路由诊断，不是最终定位召回率。

| 底座/条件 | gold直留 | gold直剪 | gold灰区 |
|---|---:|---:|---:|
| reranker / E=1.0 | 44/76（57.89%） | 28/76（36.84%） | 4/76（5.26%） |
| reranker / E=0.5 | 45/76（59.21%） | 29/76（38.16%） | 2/76（2.63%） |
| instruct / E=1.0 | 33/76（43.42%） | 33/76（43.42%） | 10/76（13.16%） |
| instruct / E=0.5 | 26/76（34.21%） | 32/76（42.11%） | 18/76（23.68%） |

## 配对变化与不确定性

差值均为E=0.5减原C；AUC上升、gold直剪率下降为期望方向。95%区间按issue聚类配对bootstrap2,000次，重复抽中的issue保留重复权重；这不是独立test。

- reranker：ΔAUC=-0.05954（95%区间-0.10701至-0.00161）；Δgold直剪=+1.32pp（-7.15至+10.81pp）。验证资格：未同时达到accuracy≥0.80、AUC≥0.85。
- instruct：ΔAUC=-0.02227（95%区间-0.06781至+0.01955）；Δgold直剪=-1.32pp（-11.86至+6.85pp）。验证资格：未同时达到accuracy≥0.80、AUC≥0.85。

## 同epoch对照

| 底座/epoch | 原AUC | E=.5 AUC | 原gold直剪 | E=.5 gold直剪 |
|---|---:|---:|---:|---:|
| reranker / 1 | 0.80725 | 0.78396 | 25.00% | 27.63% |
| reranker / 2 | 0.84635 | 0.76569 | 36.84% | 39.47% |
| reranker / 3 | 0.78360 | 0.78681 | 39.47% | 38.16% |
| instruct / 1 | 0.83015 | 0.81833 | 30.26% | 22.37% |
| instruct / 2 | 0.82509 | 0.80952 | 53.95% | 42.11% |
| instruct / 3 | 0.82059 | 0.79833 | 43.42% | 42.11% |

## 判读与局限

- reranker：两项主要目标未同时改善，E降权这一项干预不足以解决当前问题。
  从原直剪中恢复6条，新增直剪7条，仍直剪22条；恢复包含转入灰区，不假定Qwen必然纠正。
- instruct：gold直剪降低，但AUC未提高；不能把概率/判决倾向变化当作排序能力改善。
  从原直剪中恢复6条，新增直剪5条，仍直剪27条；恢复包含转入灰区，不假定Qwen必然纠正。

这项对照测的是E训练信号的影响，不能直接估计“标签噪声造成多少损失”：正确与错误E一起降权，reranker的有效负正样本权重比也由2.0变为约1.51；instruct保留原响应token归一化。验证E标签仍有弱监督不确定性。

仅一个预先固定的权重0.5和seed0，未搜索更多权重；GPU调度可能与历史不同，未改变训练数值配置，也不作耗时因果比较。早停规则保持，实际完成epoch数量若不同单列披露。

没有新增E重构、扩挖、LLM造标签、温度校准、阈值搜索、test开箱、金丝雀或全量定位。现有定位预测和跨实验矩阵保持。

- [冻结方案](E训练权重单因素对照_方案与冻结口径.md)
- [结构化比较](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/E_weight05_C_frozen_trainval_exploratory/comparison/comparison.json)
- [全部配对验证预测](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/E_weight05_C_frozen_trainval_exploratory/comparison/paired_val_predictions.csv)
- [gold逐条路由变化](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/E_weight05_C_frozen_trainval_exploratory/comparison/gold_route_transitions.csv)
- [冻结执行协议](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/E_weight05_ablation_authorization_exploratory/protocol.json)

## 补充核对：相同阈值与数据来源

以下为训练结束后的描述性拆分，未改变预先冻结的主比较、选模或阈值。主表的混合集剔除precision使用二分类p<0.5；这里另列管线路由直剪p≤0.6，避免混用。

| 底座/条件 | 直剪总数（全部val） | 直剪precision（按现有标签） |
|---|---:|---:|
| reranker / E=1.0 | 546 | 78.94% |
| reranker / E=0.5 | 517 | 78.92% |
| instruct / E=1.0 | 566 | 78.80% |
| instruct / E=0.5 | 563 | 78.69% |

| 底座/子集 | 原AUC | E=.5 AUC | 原gold直剪 | E=.5 gold直剪 |
|---|---:|---:|---:|---:|
| reranker / old_Lite（363对） | 0.83900 | 0.79762 | 10/34 | 11/34 |
| reranker / new_Verified（351对） | 0.85326 | 0.77643 | 18/42 | 18/42 |
| instruct / old_Lite（363对） | 0.85134 | 0.83790 | 17/34 | 17/34 |
| instruct / new_Verified（351对） | 0.79003 | 0.76558 | 16/42 | 15/42 |

旧Lite子集363对、新Verified子集351对，按issue身份划分；它们来自同一val，不能当作新增独立测试。

| 底座/负例来源（与全部238正例比较） | 原AUC | E=.5 AUC |
|---|---:|---:|
| reranker / all_P_vs_E | 0.84456 | 0.76914 |
| reranker / all_P_vs_D_only | 0.85142 | 0.83696 |
| instruct / all_P_vs_E | 0.83155 | 0.79629 |
| instruct / all_P_vs_D_only | 0.78949 | 0.80411 |

该来源拆分沿用既有弱标签；E与D重叠的样本归E，D-only是不含E证据的其余负例，不按组名重复计数。它描述模型在哪里改变排序，不判定具体哪条E标签错误。

两个底座对E负例与正例的排序区分均变差；instruct对D-only的区分反而改善。按当前val标签，整体AUC下降主要来自E这一部分。降权同时削弱了E中正确负例的训练信号，不能把这项净变化等同于错误标签本身的影响。

| 负例来源占比 | 原train（按样本） | E=.5有效train权重（按样本） | 原val（按样本） |
|---|---:|---:|---:|
| E并集 | 48.98% | 32.43% | 73.95% |
| D-only | 51.02% | 67.57% | 26.05% |

E降权同时扩大训练与验证负例来源的有效权重差异；这可能影响结果，但不能凭本次对照确定它是唯一原因。上表按样本权重总量计算，instruct损失仍按原响应token数归一化。

训练正例中gold A/B占574/4,473（12.83%），val占76/238（31.93%），其余主要是调用邻接C正例。该构成在两条件完全一致；降低E不能单独解决正例代理标签与gold保护目标之间的差别。

同epoch结果也没有一致收益：reranker第3轮AUC比原第3轮高0.00321、gold直剪少1条，但原第2轮按既定规则选出的best仍优于新best。instruct第1/2轮曾少剪gold，第3轮优势缩至1条，各轮AUC均下降。因此不能用某个中间轮次替代冻结的主比较。

instruct的gold直剪33→32，同时直留33→26、灰区10→18；减少1条直剪并不代表整体gold保留能力明显改善。reranker直剪28→29。该结果不支持把“E权重过大”当作当前问题的充分解释，也不能反推E标签已经没有噪声。

本轮仅一个seed、一个预定E权重；没有独立重复训练。配对区间只反映本val的issue抽样波动，不覆盖训练随机性，也不消除在同一val选checkpoint的偏差。

## 执行核对

两底座均完成3轮。对照manifest的差异仅为物理GPU、带E权重的独立代码路径/指纹，以及E权重实验的溯源字段；原模型指纹、库版本、数据SHA、采样、截断、优化器与训练处方匹配C。

独立使用正负分数两两比较复算val AUC；逐条核对1,428行配对预测、152行gold路由、真实train预测体检，以及原/新各epoch的adapter与状态文件哈希。封存test仅核对stat与开箱标记，没有解码、推理或评分。冻结旧预测和跨实验矩阵哈希保持。

启动时发现计划引用的旧Excel路径已不存在；守卫在模型加载前拦住。改用当前真实文件的只读哈希并重新冻结后才实际训练；第一次报错单独留档，未额外试训模型、未改Excel。

训练完成后GPU进程自然退出；没有停止其他用户进程，没有修改vLLM/CSRSE。

- [终态独立核对收据](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/E_weight05_C_frozen_trainval_exploratory/comparison/final_verification.json)
- [补充来源拆分数据](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/E_weight05_C_frozen_trainval_exploratory/comparison/supplementary_descriptive_metrics.json)
