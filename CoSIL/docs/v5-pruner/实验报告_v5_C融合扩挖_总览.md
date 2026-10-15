# v5 C融合扩挖：双底座训练与验证总览

C阶段于 **2026-10-15 01:58（北京时间）**完成双底座训练、验证选模和赛马。两个底座均完成3轮，正常退出；完整验证集714对上仍无合格赢家。test保持封存，未执行60次金丝雀、small/hybrid全300定位、OOD评测或新增定位矩阵列。

这是函数相关性分类验证成绩，不能当作issue Top5定位准确率。C使用P4,950/N9,892/E5,047；TRAIN13,411、VAL714、封存TEST717。原Lite切分及旧B的363对VAL保持，新增Verified VAL351对。

| 底座/选中epoch | train accuracy | VAL accuracy | VAL AUC | E正确剔除率 | gold召回（原始p≥0.5） | train−val |
|---|---:|---:|---:|---:|---:|---:|
| reranker / epoch2 | 98.75% | 77.87% | 0.84635 | 88.92% | 48/76=63.16% | 20.88pp |
| instruct / epoch3 | 99.36% | 79.69% | 0.82059 | 94.60% | 49/76=64.47% | 19.67pp |

预定资格为VAL accuracy≥0.80且AUC≥0.85。reranker为556/714，instruct为569/714，均未通过；instruct不能因接近80%而四舍五入放行，AUC也未过门。训练拟合接近99%而验证仍低约20个百分点，扩挖后仍有明显过拟合/泛化不足迹象；这不是train<0.70的原(a)分支，也不能只凭这些数字断言唯一成因。

## 与扩前B同一批旧Lite验证对照

完整C VAL714和B VAL363成员不同，应在原样保留的旧363对上比较：

| 底座 | B旧363 accuracy | C旧363 accuracy | C−B | B→C旧gold保留（p≥0.5） | B→C旧E剔除 |
|---|---:|---:|---:|---|---|
| reranker | 78.79% | 76.31% | -2.48pp | 88.24%→70.59% | 82.13%→87.66% |
| instruct | 78.79% | 82.09% | +3.31pp | 67.65%→61.76% | 90.64%→95.32% |

instruct在旧Lite accuracy为82.09%、AUC0.85134，但这只是完整冻结验证集的事后子集，不能替代VAL714的既定资格门。其净增加12个正确判决来自TN净增加14、TP净减少2；gold净少留2个（23/34→21/34）。更会剔除负例不等于更好保留gold。reranker在旧363对正确数净减少9个（286→277）。

27个issue聚类、2,000次bootstrap的C−B accuracy区间：reranker −11.07pp至+3.28pp；instruct −0.90pp至+9.36pp。两区间都跨0，不能据这次验证选择认定稳定改善或纯数据因果收益。

## 新旧域差异与来源偏差

| 底座 | 旧Lite363 accuracy / AUC | 新Verified351 accuracy / AUC |
|---|---|---|
| reranker | 76.31% / 0.83900 | 79.49% / 0.85326 |
| instruct | 82.09% / 0.85134 | 77.21% / 0.79003 |

instruct的新增Verified部分更弱，且全体AUC不达门槛；reranker在新Verified AUC较高，但旧域下降。来源结构可能参与这种差异：TRAIN C正例占87.17%、VAL68.07%；TRAIN D-only负例占51.02%、VAL26.05%。相同总正负比不能消除来源偏差，当前证据不足以在数据噪声、截断输入、底座能力和训练配方之间作唯一归因。

30条TRAIN E审阅为6条确认源码关系、2条条件风险、22条有限证据保留，8条不安全TRAIN负例已删；26.67%是三族分层保守排除观察，不是总体噪声率。另TRAIN30样本有8个函数字段、13个issue字段超固定输入字符上限，完整源码中的关系未必进入模型输入。详见[数据与质量门](C融合扩挖_数据与质量门.md)。

## gold直留、直剪和灰区分开报告

以下只以保存的原始VAL概率做默认low=0.6/high=0.9诊断：p≤low直剪、p≥high直留、中间才是拟交Qwen灰区。未运行灰区Qwen，也没有部署这些阈值。上表p≥0.5 gold召回发生在分层路由之前。

| 完整VAL714 | gold直留 | gold直剪 | gold灰区 |
|---|---:|---:|---:|
| reranker | 44/76（57.89%） | 28/76（36.84%） | 4/76（5.26%） |
| instruct | 33/76（43.42%） | 33/76（43.42%） | 10/76（13.16%） |

默认阈值的gold直剪风险很高，不能把二分类未保留都解释成灰区，也不能假设灰区Qwen一定纠正。温度校准不改变正温度下分数排序及p=0.5判决，不能靠它把当前accuracy/AUC变成达标。模型未通过验证资格，因此未启动test或生产推理。

## 运行与报告修复

两底座均按冻结处方在GPU1顺序运行：reranker rank8/dropout0.1/alpha32、instruct rank16/dropout0/alpha32，lr5e-5、最多3epoch、有效batch8/micro2、BF16、cutoff4096。reranker选epoch2，末轮accuracy从77.87%降到72.97%；早停标志在第3轮触发，实际仍完成全部3轮。共享观察期间未停止任何peer或vLLM/CSRSE。周期自身显存样本最高约2404/2202 MiB，不是allocator峰值保证；共卡耗时不能与独占B作算法延迟因果比较。

自动CPU报告在真实训练完成后因队列schema适配错误退出：v3使用completed_B_pair_sha256/completed_B_sequence_sha256/B_assessment_report_sha256，旧reader却取v2的actual_complete_B_receipts_sha256。原失败日志、授权、代码和模型输出保留。新CPU-only报告namespace按实际v3字段核验同三份B终态和B决议，7项定向守卫通过；重新绑定真实B/C best/last、checkpoint、保存概率、source inputSHA、旧363/新351身份后报告成功。修复没有重训、修改预测、读取test或降低资格门。

## 结论及原始证据

本轮A/B、处方与Verified融合C训练链已完成，扩数据后仍无满足既定验证门的裁判。后续test、历史Qwen test对线、金丝雀和全量定位均未解锁；历史CoSIL off 111/293=37.88%及已有定位矩阵保持。下一步若研究方案改变，应另记新条件，不能改写本轮结果或把未通过模型当合格赢家。

- [B/C完整同口径验证报告](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/B_C_resources_v3_completed_comparison_recovered_exploratory/B-C扩后验证对照.md)
- [结构化比较与bootstrap](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/B_C_resources_v3_completed_comparison_recovered_exploratory/comparison.json)
- [实际C训练/赛马终态](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_Verified_plus_B_runtime_resources_v3_exploratory/outcome/assessment_report.json)
- [模型及数据复核、报告恢复审计](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_completed_report_recovery_20261015/root_recovery_and_completed_metrics_audit.json)
- [原自动汇总失败证据](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/C_completed_B_C_reporting_supervisor_v1/status.json)
- [修复后报告执行收据](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/B_C_resources_v3_completed_comparison_recovered_exploratory/report_receipt.json)
