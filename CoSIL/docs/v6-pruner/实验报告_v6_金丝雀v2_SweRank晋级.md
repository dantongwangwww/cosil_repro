# v6 金丝雀v2：SweRank-7B 晋级可行性报告

更新：2026-10-19T17:20:49.289301+08:00。执行状态：**stop_loss**；服务已关闭：**True**。test封存未动。

**结论：本轮未晋级。**默认臂第15题触发>3pp止损，所有后续执行立即停止；安全臂仅完成前14题，没有运行触发止损的题，不能据此前14题无下降宣称安全臂通过。共完成29/40个新臂运行，余11个标记未运行，未补跑、未调阈值。

[逐题预测与行为分析](实验报告_v6_金丝雀v2_逐题行为分析.md) · [逐题对照CSV](实验报告_v6_金丝雀v2_逐题对照.csv) · [执行协议与代码改动](金丝雀v2_执行协议与代码改动_2026-10-19.md)

修改前可恢复备份：[GitHub 5861dd1](https://github.com/dantongwangwww/cosil_repro/commit/5861dd1b8aee480c772d53f97bc85aaee0569964)。
执行授权为2026-10-19用户消息；所提同名2026-10-18指令文件未在服务器发现，以该消息完整规格为控制协议。

## CPU准备与部署冻结

SweRankLLM-Small 7B，1:1训练权重，选中epoch1，temperature=1.740597553206586（仅val拟合）。默认low/high=0.6/0.9；安全low*=0.28219746942684304，binary64=0x1.20f85f98cf1adp-2。
本val最小gold概率=0.2821974694268431；low*=nextafter(min_gold_p,-∞)，是严格小于该值的最大可表示binary64阈值。路由p≤low剪、p≥0.9留、其余交Qwen。比较前不做float32转换。

| val画像（487对，gold76，E216） | 默认 | 安全 |
|---|---:|---:|
| gold直剪率 | 10.53% | 0.00% |
| 整体灰区占比 | 9.45% | 15.61% |
| E直剪率 | 95.37% | 90.74% |
| 混合集实际直剪precision | 87.64% | 93.25% |

温度和安全阈值都由同一val选取，安全臂val零gold直剪是构造结果，不能作为独立安全证明。既有T3置信区间安全门未通过的裁定不变。

部署采用v6训练同一Codec：issue≤8000字符、函数≤8192字符、每方向≤16个直接调用邻居、native token cutoff8192。CPU抽20对逐条核验issue/函数/邻居/body/hash与native评分token序列完全一致，全部通过后才点火。
摘要由该题base commit结构文件当场AST重建调用关系，复用训练同一通用稳定邻居渲染规则；不读gold/标签选择邻居。结构序列化丢失的换行由已验证base git blob恢复，并逐行与结构校验。没有调用v5短输入JudgeCodec或v5 pruner接入。

格式核对的20对来自9题，其中train19对/val1对，含长issue5对、长函数7对、非空邻居15对；实际最长issue6760字符、函数4631字符。核对仅检验格式一致性，不是独立效果评测。实际运行还观察到原始463229字符的`inverse_trig`函数，仅按配方截取8192字符、附16条邻居、评分输入5242 token；v6仍为有上限的输入，不能宣称完整阅读了巨型函数。

| val gold路由（分母76） | 默认 | 安全 |
|---|---:|---:|
| 直接保留 | 54/76=71.05% | 54/76=71.05% |
| 直接剪掉 | 8/76=10.53% | 0/76=0.00% |
| 灰区交Qwen | 14/76=18.42% | 22/76=28.95% |

完整val中，安全阈值把额外30对转入灰区，其中17个正例、13个负例；这属于同val构造后的路由描述，未构成对外部题目的安全认证。

## 同题配对主终点

沿用T1冻结20题（seed20261016）。off的源码/生成协议/候选文件/issue与base commit逐项一致，20题全部可复用，无补跑。判断按issue ID配对；未完成留NA，不按0计。

| 臂 | 完成/20 | 同题off命中 | 新臂命中 | 差pp | 胜/负 | McNemar双侧p | 3pp非劣效认证 |
|---|---:|---:|---:|---:|---:|---:|---|
| hybrid_default | 15/20 | 8 | 7 | -6.67 | 0/1 | 1.0000 | False |
| hybrid_safe | 14/20 | 7 | 7 | 0.00 | 0/0 | 1.0000 | False |

**已触发止损**：hybrid_default 在 matplotlib__matplotlib-24149 后同题配对下降超过3pp，立即停止所有后续题与臂，保留现场。没有扩大题集或调整阈值补救。

McNemar未显著不等于非劣效获证；20题分辨率5pp，通常不能认证3pp边界。保留Bonferroni成对不一致二项界计算的保守单侧95%差值下界，详见paired_results.json。

本次“未显著下降”的McNemar表象不能覆盖点估计止损纪律：默认臂只有1个不一致题，exact双侧p=1，但15对中少命中1题即下降6.67pp，已超过预设3pp。安全臂少运行了难题，也没有取得3pp非劣效认证。全20题历史off为10/20，仅作背景，不替换表中15题/14题的同题分母。

## 路由、token与延迟

| 臂 | 函数判决（留/剪/灰） | 灰区占比 | 本地延迟中位/p95秒 | 本地处理输入token | class回退调用/输入/输出token |
|---|---:|---:|---:|---:|---:|
| hybrid_default | 47/41/9 | 9.28% | 0.2847/1.1359 | 123268 | 1/13002/5 |
| hybrid_safe | 41/27/16 | 19.05% | 0.2681/0.7760 | 96883 | 1/13002/5 |

| 臂（各自已完成同题集合） | v3c off pruner Qwen输入/输出 | T1 B hybrid pruner Qwen输入/输出 | v2 pruner Qwen输入/输出 | v3c off全流程Qwen输入/输出 | v2全流程Qwen输入/输出 |
|---|---:|---:|---:|---:|---:|
| hybrid_default | 117621/452 | 68357/253 | 21188/47 | 1604875/12110 | 1571234/11821 |
| hybrid_safe | 96609/432 | 65633/243 | 27316/71 | 1428338/11011 | 1376851/10535 |

所有pruner token均含类请求，类请求始终由Qwen判决并另列账。SweRank没有生成输出token，但本地处理输入与评分位置不计为免费，也不与Qwen token按同价相加。灰区升级可能因原上下文预算在HTTP前中断，亦可能触发格式重试；升级数、成功调用与HTTP尝试数分别落盘。
单次本地延迟包含该次输入渲染/词表处理和同步评分，不含初始模型加载与每题AST建图；这两项另存。原配置Qwen在GPU0、单卡Transformers SweRank在GPU3；执行顺序与warm cache影响延迟，不作严格冷启动对比。

按各臂自己完成的同题集合，pruner Qwen输入＋输出token较off减少82.02%/71.78%，全流程Qwen token只减少2.10%/3.61%。默认臂的节省伴随定位退化，不能据此判成功。为了公平比较两阈值，另提供共同完成的前14题：

| 同一14题 | off | 默认 | 安全 |
|---|---:|---:|---:|
| pruner Qwen输入/输出token | 96609/432 | 21188/47 | 27316/71 |
| 全流程Qwen输入/输出token | 1428338/11011 | 1426772/10755 | 1376851/10535 |

共同14题中默认臂全流程token仅较off减少约0.13%；主搜索仍占主要token开销。安全臂虽然灰区调用更多，其总开销还受搜索轨迹及原预算边界影响，不能仅按灰区次数推断全流程开销。

| 实际判决范围 | 默认：中位/p95秒 | 安全：中位/p95秒 |
|---|---:|---:|
| 本地函数judge（97/84次） | 0.2847/1.1359 | 0.2681/0.7760 |
| 函数完整pruner，含灰区Qwen（97/84次） | 0.3188/1.2634 | 0.2968/1.0292 |
| 类Qwen回退（各1次） | 4.3690/4.3690 | 0.5666/0.5666 |

首次本地模型加载8.249秒计入默认臂首题；新建AST图合计351.124秒也集中在每题先执行的默认臂，安全臂复用同题现场图。不能将两个臂的整题耗时差解释为阈值的纯速度效应。另新增一个7B模型占GPU3，pruner token下降不等价于硬件、时间或货币成本按同等比例下降。

## gold直接误剪实际事件

直剪是拒绝该次源码进入搜索上下文，不是从最终候选目录删除节点。多次请求可重复，事件数不冒充独立gold函数风险率；gold直剪后仍可能Top5命中。

| 臂 | issue | step | 函数 | p_yes | 终选Top5命中 |
|---|---|---:|---|---:|---|
| 本次已完成轨迹无事件 | — | — | — | — | — |

Qwen灰区或class误剪单独保存在逐题审计，不能混记成本地直接误剪。完整事件含工具参数、输入hash和事件文件路径，见post_run_audit.json。

独立核验中，两臂各有20次包含gold区域的本地候选判决，全部直留，均只覆盖6个不同的“包含gold源码区域的候选函数”；重复请求不是20个独立gold函数试验。没有判到的gold不进入这个分母。该口径沿用T1的AST源码范围包含判定，不能据0次直剪推出所有gold都被保护。

## 止损题：零gold直剪仍发生端到端退化

`matplotlib__matplotlib-24149`的gold为`lib/matplotlib/axes/_axes.py::Axes._convert_dx`。off前5包含`bar/_convert_dx/relim/update_datalim`；默认臂仅输出`bar/relim/update_datalim`，漏掉gold，前15题从off 8/15变为7/15。

| step | 请求源码 | off Qwen判决 | 默认本地p/判决 |
|---|---|---|---|
| 5 | `_AxesBase.relim` | True，进入上下文 | 0.06555070136137202，False |
| 6 | `_AxesBase.update_datalim` | True，进入上下文 | 0.3438170933332751，False |

前几个工具选择与判决一致，首个可观察的判决差异出现在step5，随后搜索消息与轨迹发生变化。两个候选本身都不是gold，也不在本轮冻结train/val的样本对中，不能据此宣称它们被错标成了E负例。日志支持“非gold源码路由变化与后续定位退化同时出现”；尚未用受控反事实试验隔离哪一项是决定原因。

另一个共有瓶颈是工具选择：off在step0/2/9、默认臂在step0/2/8都尝试把`Axes._convert_dx`当作文件函数，用`get_code_of_file_function`读取；工具按现有接口返回错误，因为它属于`Axes`，需类方法读取工具。两边均未成功提取到gold函数本身的源码，故gold未进入本地判决，“0次gold直剪”不能捕捉这一失败。该错误在off和新臂中都存在，不能单独解释两者最终差异。

按**已记录的默认臂概率**推导安全阈值，`relim`仍会直剪，`update_datalim`会进入灰区。但安全臂在这道题上根本没有执行，后续轨迹与最终质量未知；没有补跑这个反事实，也不能声称安全阈值能挽回它。

这组证据表明，val AUC、gold直接误剪与真实搜索质量不是同一件事。暂未发现所核查的长输入、权重、温度或路由接入异常；本轮仍应按端到端止损判为不晋级。后续若开展工具选择修复或上下文消融，须另开版本与对照，不能改写本次结果。

## 逐题行为与边界

| issue | 臂 | off/新Top5 | 工具源码/进入搜索 | 本地判决 | gold直剪 |
|---|---|---:|---:|---:|---:|
| sympy__sympy-14317 | hybrid_default | 0/0 | 1/1 | 1 | 0 |
| sympy__sympy-14317 | hybrid_safe | 0/0 | 1/1 | 1 | 0 |
| django__django-14672 | hybrid_default | 1/1 | 4/4 | 4 | 0 |
| django__django-14672 | hybrid_safe | 1/1 | 4/4 | 4 | 0 |
| django__django-11583 | hybrid_default | 0/0 | 9/9 | 9 | 0 |
| django__django-11583 | hybrid_safe | 0/0 | 9/9 | 9 | 0 |
| django__django-13551 | hybrid_default | 1/1 | 10/10 | 10 | 0 |
| django__django-13551 | hybrid_safe | 1/1 | 10/10 | 10 | 0 |
| sympy__sympy-13146 | hybrid_default | 0/0 | 9/4 | 9 | 0 |
| sympy__sympy-13146 | hybrid_safe | 0/0 | 6/6 | 6 | 0 |
| django__django-17051 | hybrid_default | 1/1 | 10/6 | 10 | 0 |
| django__django-17051 | hybrid_safe | 1/1 | 10/6 | 10 | 0 |
| sympy__sympy-12171 | hybrid_default | 1/1 | 7/0 | 7 | 0 |
| sympy__sympy-12171 | hybrid_safe | 1/1 | 7/0 | 7 | 0 |
| sympy__sympy-14774 | hybrid_default | 0/0 | 4/1 | 4 | 0 |
| sympy__sympy-14774 | hybrid_safe | 0/0 | 1/0 | 1 | 0 |
| django__django-13220 | hybrid_default | 1/1 | 8/0 | 8 | 0 |
| django__django-13220 | hybrid_safe | 1/1 | 8/0 | 8 | 0 |
| sympy__sympy-15308 | hybrid_default | 0/0 | 2/2 | 2 | 0 |
| sympy__sympy-15308 | hybrid_safe | 0/0 | 2/2 | 2 | 0 |
| sympy__sympy-12419 | hybrid_default | 0/0 | 5/0 | 5 | 0 |
| sympy__sympy-12419 | hybrid_safe | 0/0 | 5/0 | 5 | 0 |
| django__django-13590 | hybrid_default | 1/1 | 9/3 | 9 | 0 |
| django__django-13590 | hybrid_safe | 1/1 | 9/3 | 9 | 0 |
| django__django-16527 | hybrid_default | 0/0 | 8/2 | 7 | 0 |
| django__django-16527 | hybrid_safe | 0/0 | 8/2 | 7 | 0 |
| mwaskom__seaborn-3407 | hybrid_default | 1/1 | 5/3 | 5 | 0 |
| mwaskom__seaborn-3407 | hybrid_safe | 1/1 | 5/3 | 5 | 0 |
| matplotlib__matplotlib-24149 | hybrid_default | 1/0 | 7/5 | 7 | 0 |
| matplotlib__matplotlib-24149 | hybrid_safe | NA（未完成） | NA | NA | NA |
| pytest-dev__pytest-7432 | hybrid_default | NA（未完成） | NA | NA | NA |
| pytest-dev__pytest-7432 | hybrid_safe | NA（未完成） | NA | NA | NA |
| sphinx-doc__sphinx-8273 | hybrid_default | NA（未完成） | NA | NA | NA |
| sphinx-doc__sphinx-8273 | hybrid_safe | NA（未完成） | NA | NA | NA |
| sympy__sympy-13895 | hybrid_default | NA（未完成） | NA | NA | NA |
| sympy__sympy-13895 | hybrid_safe | NA（未完成） | NA | NA | NA |
| sphinx-doc__sphinx-8627 | hybrid_default | NA（未完成） | NA | NA | NA |
| sphinx-doc__sphinx-8627 | hybrid_safe | NA（未完成） | NA | NA | NA |
| django__django-16820 | hybrid_default | NA（未完成） | NA | NA | NA |
| django__django-16820 | hybrid_safe | NA（未完成） | NA | NA | NA |

## 披露与裁定

- 本实验为可行性证据：温度与安全阈值同val拟合，20题与训练同源，部分题属于train，存在偏乐观；单训练seed0/固定题集seed20261016。
- SweRank底座与主agent同属Qwen系，不能解释为跨模型家族独立验证。底座许可CC-BY-NC-4.0，使用范围须符合非商业条款。
- 不改CSRSE/vLLM配置；只启动并关闭本次拥有的原配置7333服务；不停止或修改他人进程。未改历史数据、旧报告与跨实验矩阵。
- test未读取、未哈希、未推理，仅核对封存文件stat及未开箱标记；未重跑全300 Qwen基线。

完整计划题集为train18题/val2题；实际默认臂为train14题/val1题，安全臂train13题/val1题。止损题属于train issue，但上述两个被拒绝候选不在冻结训练样本对中。同源性与小样本局限均保留，不将其当独立泛化结果。

## 故障、修复与终态核验

CPU准备在点火前修复了归档路径迁移和历史结构缓存的根目录`setup.py`错误挂载，仅修改本次运行视图；20条输入格式门全部通过才启动服务。原结构、历史结果和金标未改。

触发止损后于17:16:29完成本次7333服务关闭；GPU0和3已释放，GPU1既有PID1632241仍在，未发送任何信号给他人进程。其后首次自动报表因旧日志“未知HTTP次数=None”参与Counter相加而失败（进程退出码1），这发生在停止推理与服务关闭之后。只修复报表数值聚合，并通过独立report-only版本回执重建报告，未知HTTP次数仍为未知；没有重跑定位、改阈值或改原始逐题结果。

报表修复前代码另有[91fac85备份](https://github.com/dantongwangwww/cosil_repro/commit/91fac85a8dfe6f1e7afa0919db9aa0a9a4657fcd)。原运行freeze和8个源文件归档完整保留；仅报告代码在实验结束后修订。独立核验重算29个新臂结果与20个历史off、配对McNemar、实际Qwen成功usage、class账、每条v6输入hash及token上限，均一致。0个逐题定位运行失败、0个已完成空定位、11个新臂未运行分别记录；20题都具有函数真值，没有将缺失或NA计0。

核验证据：`independent_final_audit.json`、`stop_loss_case_evidence.json`、`common14_cost_comparison.json`、`report_only_revision.json`、`reporting_revision_verification.json`、`GPU_after_shutdown_snapshot.json`。封存test仅stat核对，历史代码/数据/矩阵SHA一致。按止损约定停在此处，不启动后续全量或反事实实验，等待用户新指令。

原始现场：`/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v6_pruner/20261019/T1_canary_v2`。部署参数、冻结manifest、20条格式一致性、val诊断、逐题结果、token/行为审计与服务关闭回执均保留。
