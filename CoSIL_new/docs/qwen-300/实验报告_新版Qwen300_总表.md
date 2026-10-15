# 实验报告：新版 Qwen 300 题总表与问题检查

生成：2026-10-07T21:18:02.487337+08:00。新版对文件级与函数级各 300 个目标题进行运行，完整结果分别为 300/300、299/300。

本轮使用 Qwen2.5-Coder-7B-Instruct、温度 0、65536 上下文及已部署的单次原生格式纠正适配；固定代码和输入哈希见 `results/full/audit_manifest.json`。单题验证不混入全量结果。

## 一、定位结果

| 阶段 | Top-1 | Top-3 | Top-5 | MAP@5 | MRR@5 |
|---|---|---|---|---|---|
| 新版文件级 | 142/300（47.3%） | 182/300（60.7%） | 191/300（63.7%） | — | — |
| 新版函数级 | 48/293（16.4%） | 74/293（25.3%） | 84/293（28.7%） | 0.1925 | 0.2109 |

真值来自同一 300 题 base_commit 与官方 patch/AST 校验表。函数评分保留文件身份、归一化叶方法名，按解析后推荐顺序跨文件展开前五个位置；类/变量仍占推荐位置，但不作为函数命中。无函数真值的 7 题为 NA。运行失败作为端到端未命中，同时单列，未伪造空成功结果。

## 二、没有源码仍输出定位

三种口径分别区分全体工具、主搜索工具和真正进入主搜索上下文的代码。所有“仍输出”要求该题具有完整且非空的解析定位结果。

| 现象 | 题数 |
|---|---|
| 主搜索及 pruner 工具均未成功读取源码，仍输出定位 | 35/300（11.7%） |
| 主搜索工具未成功读取源码，仍输出定位 | 37/300（12.3%） |
| 搜索 agent 未收到任何可用工具源码，仍输出定位 | 115/300（38.3%） |

主搜索未成功读取源码便显式 exit 或以无原生调用结束：44 题。预算停止：0 题。最终总结请求不含已知实际工具源码：136 题，含空输出与失败尝试，不与“非空输出”混用。

源码“未收到”以实际工具源码是否被送入主搜索对话为准；issue 自带的示例、模型已有知识和说明性文本不算工具读取。调查式 pruner 使用独立上下文，看到源码并不意味着主搜索 agent 看到。正常文本结束、剪枝拒绝和预算限制仍按部署版原行为保留；本轮没有强制所有最终推荐必须读取过源码。

## 三、与已有旧版三臂对照

| 运行 | 函数 Top-5 | 未读到任何源码仍输出 | 主搜索未接收源码仍输出 |
|---|---|---|---|
| 旧版 off | 111/293（37.9%） | 21/300（7.0%） | 84/300（28.0%） |
| 旧版 on | 106/293（36.2%） | 15/300（5.0%） | 71/300（23.7%） |
| 旧版 shuffled | 113/293（38.6%） | 20/300（6.7%） | 83/300（27.7%） |
| 新版当前部署 | 84/293（28.7%） | 35/300（11.7%） | 115/300（38.3%） |

旧版是已经完成的历史结果，新版函数级使用新版重新生成的文件候选。因此差异同时包含文件定位、原生调用、调查式 pruner、总结流程与格式适配的变化，不能单独归因为 pruner 或原生调用。

- 新版对旧版 off：独有命中/独有未命中 21/48，差值 -9.22 个百分点，McNemar 精确 p=0.0016。
- 新版对旧版 on：独有命中/独有未命中 22/44，差值 -7.51 个百分点，McNemar 精确 p=0.0092。
- 新版对旧版 shuffled：独有命中/独有未命中 20/49，差值 -9.90 个百分点，McNemar 精确 p=0.0006。

## 四、其他问题、探索与成本

| 指标 | 观测值 |
|---|---|
| 主搜索源码请求 | 722 |
| pruner 侦查源码请求 | 1045 |
| 主搜索成功源码读取 | 556 |
| pruner 成功源码读取 | 426 |
| 源码真正送入主搜索上下文 | 237 |
| 工具查询错误或异常 | 785 |
| 模型请求错误，含被上游捕获的错误 | 5 |
| 其中上下文 API 错误 | 5 |
| 读取失败信息仍被交给 pruner 判相关性 | 166 |
| 失败信息被 pruner 原样保留 | 20 |
| 返回伪调用文本而未返回结构化调用 | 1546 |
| 实际原生 required 格式纠正请求 | 1546 |
| 重复源码请求 | 593 |
| 最终包含未送入主上下文的函数定义 | 232 |
| XML 原始顺序与解析顺序不同 | 77 |
| 排序改变前五个位置的集合 | 0 |
| 完整但空的最终定位 | 36 |

Pruner 判决：{'True': 257, 'False': 282, 'unknown': 181}。未知格式与 False 分开统计；部署代码对非 True 文本均按排除处理。

“推荐函数未读”的操作口径是文件+叶定义名是否出现在实际送入主搜索的源码中；整类源码包含的方法计已读。同文件同名函数、旧语法导致 AST 解析失败等情况需要逐题核对，不能仅凭此指标断言模型凭空猜测。

XML 解析按文件分组，会改变交错文件位置的输出顺序；主评分遵循实际解析结果，原始回答保留以便复核。这类排序差异与模型选择本身分开记录。

函数阶段实际请求 5133 次，prompt/completion tokens=18929952/1025283；两个阶段全部成功响应合计 tokens=21826904/1068670。包含 pruner 侦查、判决及格式纠正；失败请求未返回 usage 的消耗不能计量。上游 `func_traj.usage` 不包括全部 pruner 请求，本报告使用独立请求事件汇总。

## 五、300 题对照总表

| 题目 | 新版文件 Top-5 | 新版函数 Top-5 | 全体工具源码读取 | 主搜索源码接收 | 旧 off/on/shuffled 函数 Top-5 |
|---|---|---|---|---|---|
| astropy__astropy-12907 | ✓ | — | 1 | 1 | — / — / ✓ |
| astropy__astropy-14182 | ✓ | — | 3 | 0 | — / — / — |
| astropy__astropy-14365 | ✓ | ✓ | 8 | 1 | — / — / ✓ |
| astropy__astropy-14995 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| astropy__astropy-6938 | ✓ | — | 12 | 0 | — / — / — |
| astropy__astropy-7746 | ✓ | — | 3 | 1 | ✓ / — / ✓ |
| django__django-10914 | ✓ | NA | 2 | 1 | — / — / — |
| django__django-10924 | — | — | 0 | 0 | — / — / — |
| django__django-11001 | ✓ | — | 4 | 0 | — / — / — |
| django__django-11019 | ✓ | — | 9 | 0 | ✓ / ✓ / ✓ |
| django__django-11039 | ✓ | — | 2 | 0 | ✓ / ✓ / ✓ |
| django__django-11049 | — | NA | 5 | 0 | — / — / — |
| django__django-11099 | ✓ | NA | 2 | 1 | — / — / — |
| django__django-11133 | ✓ | — | 4 | 0 | — / — / — |
| django__django-11179 | ✓ | ✓ | 3 | 1 | ✓ / ✓ / ✓ |
| django__django-11283 | ✓ | ✓ | 0 | 0 | ✓ / ✓ / ✓ |
| django__django-11422 | ✓ | — | 0 | 0 | — / — / — |
| django__django-11564 | — | — | 7 | 0 | — / — / — |
| django__django-11583 | ✓ | — | 3 | 0 | — / — / — |
| django__django-11620 | ✓ | — | 1 | 0 | ✓ / ✓ / ✓ |
| django__django-11630 | — | — | 1 | 1 | — / ✓ / — |
| django__django-11742 | ✓ | — | 8 | 0 | — / — / — |
| django__django-11797 | — | — | 16 | 0 | — / — / — |
| django__django-11815 | — | — | 1 | 0 | — / — / — |
| django__django-11848 | ✓ | ✓ | 1 | 0 | ✓ / ✓ / ✓ |
| django__django-11905 | ✓ | — | 10 | 0 | ✓ / — / ✓ |
| django__django-11910 | ✓ | — | 3 | 0 | — / — / — |
| django__django-11964 | — | — | 1 | 0 | — / — / — |
| django__django-11999 | — | — | 2 | 0 | — / — / — |
| django__django-12113 | — | — | 10 | 0 | — / — / — |
| django__django-12125 | — | — | 7 | 0 | — / — / — |
| django__django-12184 | — | — | 0 | 0 | — / — / — |
| django__django-12284 | — | — | 6 | 0 | — / — / — |
| django__django-12286 | ✓ | — | 9 | 2 | — / — / — |
| django__django-12308 | — | — | 3 | 1 | ✓ / ✓ / ✓ |
| django__django-12453 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / ✓ |
| django__django-12470 | ✓ | — | 1 | 1 | — / — / — |
| django__django-12497 | — | — | 5 | 0 | — / — / — |
| django__django-12589 | — | — | 13 | 0 | — / — / — |
| django__django-12700 | ✓ | ✓ | 5 | 1 | ✓ / ✓ / ✓ |
| django__django-12708 | ✓ | — | 3 | 0 | — / — / — |
| django__django-12747 | ✓ | ✓ | 28 | 2 | — / — / — |
| django__django-12856 | — | — | 2 | 0 | — / — / — |
| django__django-12908 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| django__django-12915 | ✓ | — | 5 | 1 | — / ✓ / ✓ |
| django__django-12983 | ✓ | ✓ | 3 | 2 | ✓ / ✓ / ✓ |
| django__django-13028 | — | — | 4 | 1 | — / — / ✓ |
| django__django-13033 | ✓ | — | 0 | 0 | — / ✓ / ✓ |
| django__django-13158 | — | — | 11 | 0 | — / — / — |
| django__django-13220 | ✓ | — | 10 | 0 | ✓ / — / — |
| django__django-13230 | ✓ | ✓ | 3 | 0 | — / — / — |
| django__django-13265 | — | — | 8 | 0 | — / — / — |
| django__django-13315 | — | — | 0 | 0 | — / — / — |
| django__django-13321 | ✓ | — | 4 | 0 | ✓ / ✓ / ✓ |
| django__django-13401 | — | — | 0 | 0 | — / — / — |
| django__django-13447 | — | — | 4 | 0 | ✓ / ✓ / ✓ |
| django__django-13448 | — | — | 0 | 0 | — / — / ✓ |
| django__django-13551 | ✓ | ✓ | 4 | 2 | ✓ / ✓ / ✓ |
| django__django-13590 | ✓ | ✓ | 8 | 4 | ✓ / ✓ / ✓ |
| django__django-13658 | ✓ | ✓ | 7 | 0 | ✓ / — / — |
| django__django-13660 | ✓ | ✓ | 5 | 3 | ✓ / ✓ / ✓ |
| django__django-13710 | ✓ | ✓ | 3 | 1 | — / — / ✓ |
| django__django-13757 | — | — | 1 | 1 | — / — / — |
| django__django-13768 | ✓ | ✓ | 2 | 0 | — / — / — |
| django__django-13925 | ✓ | — | 0 | 0 | — / — / — |
| django__django-13933 | — | — | 0 | 0 | — / — / — |
| django__django-13964 | — | — | 7 | 0 | — / — / — |
| django__django-14016 | — | — | 0 | 0 | — / — / — |
| django__django-14017 | ✓ | — | 13 | 4 | — / — / — |
| django__django-14155 | — | — | 0 | 0 | — / — / — |
| django__django-14238 | — | — | 0 | 0 | — / — / — |
| django__django-14382 | ✓ | ✓ | 2 | 1 | — / — / — |
| django__django-14411 | — | — | 0 | 0 | — / — / — |
| django__django-14534 | ✓ | ✓ | 4 | 1 | ✓ / ✓ / ✓ |
| django__django-14580 | — | — | 2 | 1 | — / — / — |
| django__django-14608 | ✓ | — | 0 | 0 | ✓ / — / — |
| django__django-14667 | — | — | 3 | 1 | — / — / — |
| django__django-14672 | ✓ | — | 2 | 0 | ✓ / — / — |
| django__django-14730 | — | — | 0 | 0 | — / — / — |
| django__django-14752 | ✓ | ✓ | 2 | 0 | ✓ / ✓ / ✓ |
| django__django-14787 | ✓ | — | 1 | 1 | — / — / — |
| django__django-14855 | ✓ | — | 3 | 0 | ✓ / ✓ / ✓ |
| django__django-14915 | — | — | 19 | 3 | — / — / — |
| django__django-14997 | — | — | 3 | 0 | — / — / — |
| django__django-14999 | — | — | 4 | 0 | ✓ / — / ✓ |
| django__django-15061 | ✓ | ✓ | 3 | 1 | — / ✓ / ✓ |
| django__django-15202 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / ✓ |
| django__django-15213 | — | — | 5 | 0 | — / — / — |
| django__django-15252 | — | — | 4 | 2 | — / — / — |
| django__django-15320 | — | — | 0 | 0 | — / — / — |
| django__django-15347 | ✓ | ✓ | 4 | 2 | — / — / — |
| django__django-15388 | — | — | 1 | 1 | — / — / — |
| django__django-15400 | ✓ | — | 2 | 1 | ✓ / ✓ / ✓ |
| django__django-15498 | — | — | 2 | 0 | — / — / — |
| django__django-15695 | — | — | 2 | 1 | — / — / — |
| django__django-15738 | — | — | 2 | 0 | — / — / — |
| django__django-15781 | ✓ | — | 8 | 0 | — / — / — |
| django__django-15789 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / ✓ |
| django__django-15790 | — | — | 4 | 0 | ✓ / ✓ / ✓ |
| django__django-15814 | ✓ | — | 1 | 0 | — / — / — |
| django__django-15819 | — | — | 0 | 0 | — / — / — |
| django__django-15851 | ✓ | — | 3 | 3 | ✓ / ✓ / ✓ |
| django__django-15902 | ✓ | NA | 8 | 0 | — / — / — |
| django__django-15996 | ✓ | ✓ | 8 | 0 | ✓ / ✓ / — |
| django__django-16041 | ✓ | — | 12 | 0 | ✓ / ✓ / ✓ |
| django__django-16046 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / ✓ |
| django__django-16139 | — | — | 0 | 0 | ✓ / — / ✓ |
| django__django-16229 | — | — | 5 | 0 | — / — / — |
| django__django-16255 | ✓ | ✓ | 0 | 0 | ✓ / ✓ / ✓ |
| django__django-16379 | ✓ | ✓ | 2 | 0 | ✓ / ✓ / ✓ |
| django__django-16400 | — | — | 2 | 0 | — / — / — |
| django__django-16408 | ✓ | — | 1 | 1 | — / — / — |
| django__django-16527 | ✓ | — | 0 | 0 | — / ✓ / ✓ |
| django__django-16595 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| django__django-16816 | — | — | 2 | 0 | — / — / — |
| django__django-16820 | — | — | 2 | 0 | — / — / — |
| django__django-16873 | ✓ | ✓ | 8 | 4 | ✓ / ✓ / ✓ |
| django__django-16910 | — | — | 14 | 3 | — / — / — |
| django__django-17051 | ✓ | — | 1 | 0 | ✓ / — / — |
| django__django-17087 | — | — | 3 | 0 | — / — / — |
| matplotlib__matplotlib-18869 | ✓ | — | 3 | 0 | — / — / — |
| matplotlib__matplotlib-22711 | ✓ | — | 0 | 0 | ✓ / ✓ / ✓ |
| matplotlib__matplotlib-22835 | ✓ | — | 2 | 1 | ✓ / — / ✓ |
| matplotlib__matplotlib-23299 | — | — | 1 | 1 | — / — / — |
| matplotlib__matplotlib-23314 | — | — | 4 | 0 | — / — / — |
| matplotlib__matplotlib-23476 | ✓ | — | 13 | 5 | — / — / — |
| matplotlib__matplotlib-23562 | ✓ | — | 2 | 0 | — / — / — |
| matplotlib__matplotlib-23563 | — | — | 2 | 0 | — / — / — |
| matplotlib__matplotlib-23913 | ✓ | ✓ | 3 | 2 | ✓ / ✓ / ✓ |
| matplotlib__matplotlib-23964 | ✓ | — | 3 | 2 | ✓ / ✓ / ✓ |
| matplotlib__matplotlib-23987 | ✓ | — | 2 | 1 | — / — / — |
| matplotlib__matplotlib-24149 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| matplotlib__matplotlib-24265 | — | — | 0 | 0 | — / — / — |
| matplotlib__matplotlib-24334 | ✓ | ✓ | 4 | 2 | — / — / ✓ |
| matplotlib__matplotlib-24970 | ✓ | — | 1 | 1 | ✓ / ✓ / ✓ |
| matplotlib__matplotlib-25079 | — | — | 0 | 0 | — / — / — |
| matplotlib__matplotlib-25311 | — | — | 4 | 1 | — / — / — |
| matplotlib__matplotlib-25332 | — | — | 1 | 1 | — / — / — |
| matplotlib__matplotlib-25433 | ✓ | — | 2 | 1 | — / — / — |
| matplotlib__matplotlib-25442 | ✓ | ✓ | 1 | 1 | ✓ / — / — |
| matplotlib__matplotlib-25498 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / ✓ |
| matplotlib__matplotlib-26011 | — | — | 1 | 0 | — / — / — |
| matplotlib__matplotlib-26020 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| mwaskom__seaborn-2848 | — | — | 0 | 0 | — / — / — |
| mwaskom__seaborn-3010 | ✓ | — | 2 | 1 | — / — / ✓ |
| mwaskom__seaborn-3190 | ✓ | ✓ | 1 | 1 | — / ✓ / ✓ |
| mwaskom__seaborn-3407 | ✓ | — | 3 | 0 | ✓ / ✓ / ✓ |
| pallets__flask-4045 | ✓ | — | 3 | 0 | ✓ / ✓ / ✓ |
| pallets__flask-4992 | ✓ | ✓ | 2 | 2 | ✓ / ✓ / ✓ |
| pallets__flask-5063 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / — |
| psf__requests-1963 | ✓ | ✓ | 3 | 1 | ✓ / ✓ / ✓ |
| psf__requests-2148 | ✓ | — | 1 | 0 | — / — / — |
| psf__requests-2317 | ✓ | — | 0 | 0 | ✓ / ✓ / ✓ |
| psf__requests-2674 | ✓ | — | 3 | 2 | ✓ / — / ✓ |
| psf__requests-3362 | ✓ | ✓ | 6 | 1 | ✓ / — / ✓ |
| psf__requests-863 | ✓ | — | 6 | 1 | ✓ / ✓ / ✓ |
| pydata__xarray-3364 | ✓ | ✓ | 1 | 1 | — / ✓ / — |
| pydata__xarray-4094 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| pydata__xarray-4248 | — | — | 1 | 1 | — / — / — |
| pydata__xarray-4493 | ✓ | — | 2 | 1 | — / — / — |
| pydata__xarray-5131 | ✓ | ✓ | 5 | 1 | ✓ / ✓ / ✓ |
| pylint-dev__pylint-5859 | — | — | 2 | 1 | — / — / — |
| pylint-dev__pylint-6506 | ✓ | — | 2 | 1 | ✓ / ✓ / ✓ |
| pylint-dev__pylint-7080 | — | — | 0 | 0 | — / — / — |
| pylint-dev__pylint-7114 | — | — | 2 | 1 | — / — / — |
| pylint-dev__pylint-7228 | — | — | 2 | 1 | — / — / — |
| pylint-dev__pylint-7993 | ✓ | — | 2 | 1 | — / ✓ / — |
| pytest-dev__pytest-11143 | ✓ | — | 1 | 1 | — / — / — |
| pytest-dev__pytest-11148 | — | — | 0 | 0 | — / — / — |
| pytest-dev__pytest-5103 | ✓ | — | 4 | 0 | — / — / — |
| pytest-dev__pytest-5221 | — | — | 4 | 0 | — / — / — |
| pytest-dev__pytest-5227 | ✓ | NA | 7 | 3 | — / — / — |
| pytest-dev__pytest-5413 | — | — | 1 | 1 | — / — / — |
| pytest-dev__pytest-5495 | — | — | 1 | 1 | — / — / — |
| pytest-dev__pytest-5692 | ✓ | — | 2 | 0 | — / — / — |
| pytest-dev__pytest-6116 | — | — | 4 | 0 | — / ✓ / ✓ |
| pytest-dev__pytest-7168 | ✓ | — | 1 | 1 | — / — / — |
| pytest-dev__pytest-7220 | — | — | 5 | 2 | — / — / — |
| pytest-dev__pytest-7373 | ✓ | ✓ | 4 | 1 | ✓ / ✓ / ✓ |
| pytest-dev__pytest-7432 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| pytest-dev__pytest-7490 | — | — | 3 | 3 | — / — / — |
| pytest-dev__pytest-8365 | ✓ | ✓ | 1 | 1 | ✓ / — / ✓ |
| pytest-dev__pytest-8906 | ✓ | — | 2 | 0 | — / — / — |
| pytest-dev__pytest-9359 | ✓ | — | 9 | 0 | — / — / — |
| scikit-learn__scikit-learn-10297 | ✓ | ✓ | 9 | 1 | — / — / — |
| scikit-learn__scikit-learn-10508 | ✓ | ✓ | 3 | 1 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-10949 | ✓ | ✓ | 10 | 3 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-11040 | ✓ | ✓ | 4 | 2 | ✓ / — / ✓ |
| scikit-learn__scikit-learn-11281 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-12471 | ✓ | — | 2 | 1 | ✓ / ✓ / — |
| scikit-learn__scikit-learn-13142 | ✓ | ✓ | 4 | 1 | ✓ / — / ✓ |
| scikit-learn__scikit-learn-13241 | ✓ | ✓ | 4 | 2 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-13439 | ✓ | — | 3 | 3 | — / ✓ / ✓ |
| scikit-learn__scikit-learn-13496 | ✓ | — | 0 | 0 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-13497 | ✓ | ✓ | 2 | 1 | — / — / — |
| scikit-learn__scikit-learn-13584 | — | — | 6 | 0 | — / — / — |
| scikit-learn__scikit-learn-13779 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-14087 | ✓ | ✓ | 3 | 2 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-14092 | ✓ | — | 2 | 1 | — / — / — |
| scikit-learn__scikit-learn-14894 | ✓ | ✓ | 6 | 2 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-14983 | ✓ | ✓ | 9 | 1 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-15512 | ✓ | ✓ | 8 | 6 | ✓ / ✓ / ✓ |
| scikit-learn__scikit-learn-15535 | ✓ | — | 2 | 1 | — / — / — |
| scikit-learn__scikit-learn-25500 | ✓ | — | 2 | 1 | ✓ / — / ✓ |
| scikit-learn__scikit-learn-25570 | ✓ | — | 2 | 1 | — / ✓ / — |
| scikit-learn__scikit-learn-25638 | ✓ | — | 2 | 1 | — / — / — |
| scikit-learn__scikit-learn-25747 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| sphinx-doc__sphinx-10325 | — | — | 1 | 0 | — / — / — |
| sphinx-doc__sphinx-10451 | ✓ | ✓ | 11 | 1 | ✓ / ✓ / — |
| sphinx-doc__sphinx-11445 | — | — | 3 | 1 | — / — / — |
| sphinx-doc__sphinx-7686 | ✓ | ✓ | 3 | 0 | ✓ / ✓ / ✓ |
| sphinx-doc__sphinx-7738 | ✓ | ✓ | 3 | 1 | — / — / — |
| sphinx-doc__sphinx-7975 | ✓ | ✓ | 3 | 1 | ✓ / ✓ / ✓ |
| sphinx-doc__sphinx-8273 | ✓ | ✓ | 2 | 0 | ✓ / ✓ / ✓ |
| sphinx-doc__sphinx-8282 | — | — | 1 | 0 | — / — / — |
| sphinx-doc__sphinx-8435 | — | — | 3 | 0 | — / — / — |
| sphinx-doc__sphinx-8474 | ✓ | — | 3 | 0 | ✓ / — / — |
| sphinx-doc__sphinx-8506 | — | — | 4 | 1 | — / ✓ / ✓ |
| sphinx-doc__sphinx-8595 | — | — | 1 | 0 | — / — / — |
| sphinx-doc__sphinx-8627 | ✓ | ✓ | 20 | 6 | — / — / — |
| sphinx-doc__sphinx-8713 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / ✓ |
| sphinx-doc__sphinx-8721 | ✓ | ✓ | 3 | 2 | ✓ / ✓ / ✓ |
| sphinx-doc__sphinx-8801 | ✓ | — | 2 | 1 | ✓ / ✓ / — |
| sympy__sympy-11400 | ✓ | — | 0 | 0 | — / — / — |
| sympy__sympy-11870 | ✓ | — | 2 | 1 | — / — / — |
| sympy__sympy-11897 | ✓ | — | 0 | 0 | — / — / — |
| sympy__sympy-12171 | ✓ | — | 0 | 0 | ✓ / ✓ / ✓ |
| sympy__sympy-12236 | — | — | 2 | 0 | — / — / — |
| sympy__sympy-12419 | — | — | 4 | 0 | — / — / — |
| sympy__sympy-12454 | ✓ | ✓ | 2 | 1 | — / — / — |
| sympy__sympy-12481 | ✓ | ✓ | 1 | 1 | — / ✓ / ✓ |
| sympy__sympy-13031 | ✓ | — | 2 | 1 | — / — / — |
| sympy__sympy-13043 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| sympy__sympy-13146 | — | — | 1 | 0 | — / — / — |
| sympy__sympy-13177 | ✓ | — | 0 | 0 | ✓ / ✓ / ✓ |
| sympy__sympy-13437 | ✓ | ✓ | 8 | 1 | — / — / — |
| sympy__sympy-13471 | ✓ | ✓ | 8 | 4 | ✓ / ✓ / ✓ |
| sympy__sympy-13480 | ✓ | — | 4 | 0 | ✓ / ✓ / ✓ |
| sympy__sympy-13647 | ✓ | — | 3 | 0 | — / — / — |
| sympy__sympy-13773 | ✓ | — | 2 | 1 | — / — / — |
| sympy__sympy-13895 | — | — | 1 | 1 | — / — / — |
| sympy__sympy-13915 | ✓ | — | 2 | 1 | ✓ / — / — |
| sympy__sympy-13971 | — | — | 5 | 2 | — / — / — |
| sympy__sympy-14024 | — | — | 15 | 6 | — / — / — |
| sympy__sympy-14308 | ✓ | — | 1 | 1 | — / — / — |
| sympy__sympy-14317 | ✓ | ✓ | 2 | 1 | — / — / — |
| sympy__sympy-14396 | ✓ | — | 1 | 1 | — / — / — |
| sympy__sympy-14774 | ✓ | ✓ | 1 | 1 | — / ✓ / — |
| sympy__sympy-14817 | ✓ | — | 0 | 0 | — / — / — |
| sympy__sympy-15011 | ✓ | — | 2 | 1 | — / — / — |
| sympy__sympy-15308 | ✓ | — | 2 | 0 | — / — / — |
| sympy__sympy-15345 | ✓ | NA | 13 | 2 | — / — / — |
| sympy__sympy-15346 | — | — | 1 | 1 | — / — / — |
| sympy__sympy-15609 | ✓ | — | 2 | 1 | ✓ / — / — |
| sympy__sympy-15678 | — | — | 2 | 0 | — / — / — |
| sympy__sympy-16106 | ✓ | — | 1 | 0 | — / — / — |
| sympy__sympy-16281 | ✓ | — | 3 | 1 | ✓ / ✓ / ✓ |
| sympy__sympy-16503 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| sympy__sympy-16792 | — | — | 1 | 1 | — / — / — |
| sympy__sympy-16988 | ✓ | — | 5 | 1 | — / — / — |
| sympy__sympy-17022 | — | — | 1 | 1 | — / — / — |
| sympy__sympy-17139 | ✓ | — | 4 | 2 | — / ✓ / ✓ |
| sympy__sympy-17630 | — | — | 10 | 5 | — / — / — |
| sympy__sympy-17655 | ✓ | — | 2 | 1 | — / — / — |
| sympy__sympy-18057 | ✓ | ✓ | 0 | 0 | ✓ / ✓ / ✓ |
| sympy__sympy-18087 | — | — | 1 | 1 | — / — / — |
| sympy__sympy-18189 | ✓ | ✓ | 2 | 1 | ✓ / ✓ / ✓ |
| sympy__sympy-18199 | — | — | 3 | 0 | ✓ / ✓ / ✓ |
| sympy__sympy-18532 | — | — | 1 | 1 | ✓ / ✓ / ✓ |
| sympy__sympy-18621 | ✓ | — | 2 | 1 | — / — / ✓ |
| sympy__sympy-18698 | — | — | 2 | 0 | ✓ / ✓ / — |
| sympy__sympy-18835 | — | — | 10 | 0 | — / — / — |
| sympy__sympy-19007 | — | — | 1 | 1 | — / — / — |
| sympy__sympy-19254 | ✓ | ✓ | 4 | 0 | ✓ / ✓ / ✓ |
| sympy__sympy-19487 | ✓ | — | 0 | 0 | — / — / — |
| sympy__sympy-20049 | — | — | 0 | 0 | — / — / — |
| sympy__sympy-20154 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / ✓ |
| sympy__sympy-20212 | ✓ | ✓ | 2 | 1 | — / — / — |
| sympy__sympy-20322 | — | — | 2 | 0 | — / — / — |
| sympy__sympy-20442 | — | — | 0 | 0 | — / — / — |
| sympy__sympy-20590 | — | NA | 2 | 1 | — / — / — |
| sympy__sympy-20639 | ✓ | — | 4 | 1 | ✓ / — / — |
| sympy__sympy-21055 | ✓ | — | 2 | 0 | — / — / — |
| sympy__sympy-21171 | ✓ | — | 1 | 1 | — / ✓ / ✓ |
| sympy__sympy-21379 | — | — | 1 | 1 | — / — / — |
| sympy__sympy-21612 | — | — | 0 | 0 | — / — / — |
| sympy__sympy-21614 | — | — | 4 | 2 | — / — / — |
| sympy__sympy-21627 | — | — | 2 | 1 | — / — / — |
| sympy__sympy-21847 | — | — | 1 | 1 | — / — / — |
| sympy__sympy-22005 | ✓ | ✓ | 1 | 0 | ✓ / ✓ / ✓ |
| sympy__sympy-22714 | ✓ | — | 10 | 0 | ✓ / ✓ / — |
| sympy__sympy-22840 | — | — | 7 | 0 | — / — / — |
| sympy__sympy-23117 | ✓ | — | 0 | 0 | — / ✓ / — |
| sympy__sympy-23191 | ✓ | — | 0 | 0 | — / — / — |
| sympy__sympy-23262 | ✓ | — | 5 | 1 | — / — / — |
| sympy__sympy-24066 | — | — | 5 | 0 | — / — / — |
| sympy__sympy-24102 | ✓ | — | 2 | 1 | ✓ / — / ✓ |
| sympy__sympy-24152 | ✓ | ✓ | 1 | 1 | ✓ / ✓ / ✓ |
| sympy__sympy-24213 | — | — | 1 | 1 | ✓ / ✓ / ✓ |
| sympy__sympy-24909 | ✓ | — | 2 | 2 | ✓ / ✓ / ✓ |

## 六、审计与局限

正式输出和事件逐题保存，完成轨迹各一组 run_start/run_end，原始失败轨迹独立保留。使用当前部署版，含已公开的 Qwen 格式纠正；没有新增注释生成或重新运行旧版三臂。每题单次运行，不能替代全量重复，也不声称完全未经修改地复现论文。

## 七、核验补充：耗时、四卡切换与解析问题

全部 300 题均有两个阶段的运行证据。文件级 300 条成功，函数级 299 条成功、1 条真实失败。失败题 `pydata__xarray-4493` 的最终总结输入加 4096 输出预留超过 65536 上限；另两题 `matplotlib__matplotlib-23563`、`matplotlib__matplotlib-26011` 在 pruner 调查和判决各发生一次上下文错误，被上游捕获后仍完成输出。因此 5 次 API 错误对应一条完整运行失败，未将失败伪造为空成功结果，也未混入改参数重跑结果。

181 次 unknown 判决中有 42 次是单行代码围栏内的明确布尔值，True=42、False=0。例如 `django__django-16379` 返回单行围栏包裹的 True，却未被解析器识别，随后按非 True 排除。这是格式解析缺陷；其余 unknown 包含 XML 等非预期格式。建议采用明确、无矛盾的布尔解析，并为 unknown 单独纠正格式。

本轮没有触发 exit 指令送审（0 次）；这一未触发路径不计入实测问题。另有两题文件候选为空时，XML 解析的候选过滤条件被跳过，生成候选外的位置：`matplotlib__matplotlib-24265`（包含系统安装目录）、`pylint-dev__pylint-7080`（包含不相关的 Windows 路径）。这些原始输出保留，属于当前实现的实际问题。

原 XML 对照的辅助分析先按空候选严格过滤，将上述约束失效混入排序差异；核验版已使对照遵循实际解析条件，原始分析保存在 `results/full/evaluation_v1/`，更正记录为 `evaluation_correction.json`。推理、主要得分和源码读取指标没有改变。

函数阶段平均每题 5.25 分钟，任务耗时相加为 26.26 小时（非总墙钟）；等待模型约占 83.7%，首次模型调用前准备约占 14.0%。逐类重复加载结构 JSON 是可优化的准备开销。函数阶段平均输出 3418 tokens/题，旧 off 全量约 895；输入和任务不同，此比较不作为纯性能基准。

先以 GPU 0、两个 worker 运行。原在途两题完成后，于 2026-10-07T19:20:09.539638+08:00 切换四份相同 Qwen 服务，每卡两个 worker，共八道题并行。切换前完成 148 道函数题，之后尝试余下 152 道，耗时 107.3 分钟；四卡处理题数（包含原单卡阶段）为 {'0': 182, '3': 31, '2': 42, '1': 45}。模型权重、温度、上下文、批次不变设置和推理代码未改；新增服务用一个已完成题的同一初始请求验证输出一致，此检查不替代全量重复。不同阶段题目不同，不能据此宣称严格四倍加速。

证据：`parallelism_transition.json`、`replica_verification.json`、`final_verification.json`。源代码哈希和切换前已完成记录哈希均核对通过，严格函数得分按旧报告规范独立重算一致。实验完成后释放 GPU 1、2、3 的临时副本，保留 GPU 0 服务及其他进程。
