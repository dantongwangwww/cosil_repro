# v5 A/B：噪声披露版与运行时覆盖过滤版

本表使用真实同checkpoint train与val结果，test继续封存。B沿用户命名可称‘干净版’，其准确含义为覆盖过滤版，尚未证明无噪声。

| 底座 | 数据版本 | train acc | val样本数 | val acc | val AUC | E正确剔除率 | 混合集剔除precision |
|---|---|---:|---:|---:|---:|---:|---:|
| reranker | A | 99.36% | 363 | 73.55% | 0.8254217608086879 | 88.94% | 76.26% |
| reranker | B | 95.15% | 363 | 78.79% | 0.8776210641349634 | 82.13% | 86.34% |
| instruct | A | 93.88% | 363 | 72.73% | 0.8475513967625162 | 95.32% | 72.70% |
| instruct | B | 99.00% | 363 | 78.79% | 0.866778225531043 | 90.64% | 80.67% |

混合集剔除precision=TN/(TN+FN)，E正确剔除率=TN/(TN+FP)；两者分别计算，不互换。

不同val组成会改变全量指标，因此另报输入、标签相同的共同issue/function pair：

| 底座 | 共同val样本数 | A accuracy | B accuracy | A剔除precision | B剔除precision | accuracy差值B−A（百分点） |
|---|---:|---:|---:|---:|---:|---:|
| reranker | 345 | 74.49% | 78.26% | 75.37% | 85.31% | 3.77 |
| instruct | 345 | 72.46% | 77.97% | 71.43% | 79.37% | 5.51 |

按issue簇重采样的accuracy差值区间：

- reranker：-4.81 至 12.34 个百分点；仅探索性验证对照。
- instruct：0.62 至 11.63 个百分点；仅探索性验证对照。

A的E类估计噪声~10%来自三族各10条分层抽检3/30，不是总体噪声率或静态地板证明。B覆盖失败的题仍采用纯静态规则，须结合B数据统计中的覆盖成功比例和新30条审阅解释。

没有test或新端到端定位成绩；不能据此宣称定位准确率已提高。训练数据规模和组成发生变化，共同val对照也不能单独证明改善来源完全是噪声。

结构化指标、共同pair和哈希：[comparison.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/A_post_vs_B_runtime_comparison_exploratory/comparison.json)。
