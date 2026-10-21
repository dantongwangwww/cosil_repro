# 外部验证终期验收与报告勘误

本文件针对 `20261021_external_nonthinking_v1` 的独立只读复算及报告层校正。推理已结束，400个题×方法结果齐全。报告展示修正的执行状态与原/新SHA以 `external_report_audit_overlay.json` 为准；原始自动报告21个文件的副本及SHA清单永久保留在评测私有审计目录。冻结方法源码、模型配置、原始预测和金标不修改，不重跑任何答案。

## 1. 完整性与主评分

同一预选100题、100个仓库，四臂各100结果；逐项核对instance_id、repo、base_commit、method、cohort、run_id，400/400匹配，无缺题、多题或串题。成功完成330，真实失败69，单题预算停止1，均保留。文件有效gold为99题；函数full46、partial38、unmappable16。严格46题内包含D-COSIL失败3题、Q-COSIL失败14题、Q-PRUNER失败17题，均以空预测0计入，不能缩小分母。

| 方法 | complete/failed/budget | 文件Hit@5，N99 | 严格函数Hit@5，N46 | Macro-Recall@5 | 部分映射Hit@5，N38 |
|---|---:|---:|---:|---:|---:|
| D-SIMPLE | 100/0/0 | 87/99 | 37/46（80.43%） | 75.00% | 33/38 |
| D-COSIL | 94/5/1 | 86/99 | 35/46（76.09%） | 70.29% | 31/38 |
| Q-COSIL | 70/30/0 | 55/99 | 18/46（39.13%） | 29.65% | 13/38 |
| Q-PRUNER | 66/34/0 | 51/99 | 13/46（28.26%） | 21.92% | 12/38 |

独立实现直接比较原始预测与gold集合，保留无效/重复排名槽，Precision固定除k；四臂文件/函数Hit@1/5、Recall@5、Precision@5、MRR@10与自动报告逐值一致（差小于1e-12）。唯一文件NA题 `plone__cookieplone-templates-308` 仅改news和模板.gitignore，不是定位失败。其余NA及部分映射均按既有规则分开。

D-SIMPLE相对D-COSIL的严格Hit@5仅多2题：差4.35pp，精确McNemar经Holm修正p=0.5，不能据此断言稳定优于或等效。Q-PRUNER相对Q-COSIL少5题（−10.87pp，Holm p=0.125），本轮不支持宣称剪枝提升，也不把未预设非劣界的p>0.05当非劣证明。两套模型的上下文上限、流程与工具行为有差异，跨系统分差不是纯模型能力因果效应。

## 2. 已核对的报告展示问题

| 项目 | 原自动口径 | 校正及解释 |
|---|---|---|
| 文件分母 | 执行100/100，表B没明确评分N | 标注文件评分N99；执行数不变 |
| Recall配对胜负 | 复用Hit胜负 | D-SIMPLE/D-COSIL为4/2/40平；D-SIMPLE/Q-PRUNER为26/0/20平；Q-PRUNER/Q-COSIL为0/5/41平，N46；均值差、CI及Hit检验不变 |
| 极小p显示 | 0.0000 | 标为3.58e-7，原精确值3.5762786865234375e-7，不是p=0 |
| D-SIMPLE无源码定位 | 99条逐题句子误标True，runtime通用判据漏掉function_localization | 100个最终请求均真实含非空完整拼接context且有成功回执，通用agent已收源码=True、无源码定位=False；自由DSL工具字段不适用 |
| 完整gold函数可见率 | 名称易理解为改动实现体已完整阅读 | 实际是84题full+partial中gold限定名任一定义span完整覆盖的宏平均；未绑定真正改动实现span，多overload/property可能产生歧义，结构化span漏绑定还可能低估 |
| 源码返回/收到 | 自动span导出器漏同名多定义 | 保留自动送达计数为下界，来源补审与实际送达分列，见下节 |

D-SIMPLE主评分CSV与结果JSON的通用无源码定位字段原本均正确，受影响的是runtime审计字段和逐题描述；时延/token汇总没有受污染。固定装载/grep流程不能按CoSIL自由动作事件缺失来判断“没看到代码”。

## 3. 工具真实执行及证据边界

| 方法 | 动作响应/解析通过 | 真实执行/成功源码 | 工具错误 | 重复输入 | 工具取回源码题/agent收到源码题 | agent未收源码仍定位题 |
|---|---:|---:|---:|---:|---:|---:|
| D-COSIL | 852/643 | 591/583 | 8 | 2 | 90/88 | 7 |
| Q-COSIL | 700/680 | 680/501 | 179 | 178 | 68/48 | 22 |
| Q-PRUNER | 675/642 | 642/468 | 174 | 166 | 68/51 | 18 |

三臂成功返回源码合计1552次；所有返回SHA/长度均能由同题base源码span重现。3017个上下文span条目逐字节匹配snapshot。自动唯一span绑定只有1529次（578/487/464），差23次主要为同限定名多定义，不能将自动未绑定误称源码不一致。

D-COSIL五个未唯一绑定案例另从真实付费pruner payload恢复完整返回文本，各自SHA一致且唯一匹配具体base span。因此D裁判实际收到583次；本次调用可直接归因的搜索agent送达332次，自动578/331只是保守导出计数。其余Q两臂的自动裁判/agent送达487/174、464/197保留为已证实下界；全1552次来源核验不能直接搬作裁判/agent送达次数。

五例中四例返回第一个 `@overload` 声明，一例返回property getter；工具取到了正确base源码，也可能未取到运行实现体。`Container.get` 的声明与实现共享评分身份，但该题更早读取的完整Container类已覆盖真实实现；不能凭声明判断“实现未读”，也不能将仅有声明称为实现已读。

D的209次解析失败包括DSML不兼容；215段DSML中仅离线识别112段结构完整、110段目标有效，绝不追认历史执行或恢复成绩。Q的语法通过率较高，但179/680及174/642次执行失败，约四分之一，说明错误路径、类/函数作用域等目标问题不能靠“JSON格式正确”自动解决。重复输入不是全部重复错误，仍需逐动作分类。工具成功、相关性裁判看到、搜索agent实际后续成功请求看到、最后定位正确是不同事件。

## 4. gold安全：小裁判直剪0，灰区主Qwen拒绝2

100题中67题实际触发457次小裁判：166直接留、188直接剪、103灰区；另有7次类请求回退。103灰区+7类的110次回退均有真实主Qwen请求、完整源码、HTTP200回执与usage。

gold实际受检74次、39个唯一issue/函数对：72次直接留，2次灰区，小裁判直接剪gold为0。该范围不覆盖未取回的gold，不等于全管线保留100%。

| issue | 已送裁判gold | p | 主Qwen与上下文 | 最终函数Top5 |
|---|---|---:|---|---|
| asottile__dead-204 | dead.py::Visitor.visit_ClassDef@105 | 0.82919279013451 | False，context_reject | 严格未命中；原输出另有未限定的visit_ClassDef |
| scott-huberty__eyelinkio-22 | src/eyelinkio/edf/read.py::_read_raw_edf@157 | 0.8742410635117825 | False，context_reject | 仍命中_read_raw_edf和_handle_end |

两例均为partial题，不直接改变严格46主表。拒绝事件与最终未命中不能互相替代，不能将asottile的多重机制失败仅归因于拒绝。原 `external_gold_direct_rejection_events.csv` 的小裁判计数0保持；两事件单列 [灰区回退拒绝CSV](external_gold_gray_fallback_rejections.csv)。

457次模型、温度、阈值、logit校准、长输入布局/哈希、base函数前缀、结构SHA与现场邻居摘要逐条一致。457次输入均遵守issue≤8000/函数≤8192字符上限；其中7次issue、5次函数因字符上限截断；无额外token预算截短，不能称“所有输入无截断”。每方向邻居最多16，最长4946输入token。全457事件稳定索引SHA256 `5da5623915fd23de90e106597af7a77597d328d330e7b48eb4457662c1ca0188`，索引序列为按issue字典序及events原行序的 `[instance_id,line,step,function_id,input_sha256]`，UTF8紧凑JSON、无末尾换行。

## 5. 费用、token、时延与资源

2519份唯一API回执全部结算，未知计费0；D-SIMPLE实际USD0.450233748，D-COSIL实际USD0.392109342，共 **USD0.842343090**。全在闲时，峰时保守账USD1.684686180；与USD30授权共用上限分别披露，P0/P1不混入。1820个D-COSIL request工件中的1个在400K token预约门处未发送，无回执不计费。所有DeepSeek请求显式非思考，无reasoning_effort，响应无非空reasoning；没有High重试。

| 方法 | 平均/中位秒（全100含失败） | 中位总token | 成功子组中位秒 |
|---|---:|---:|---:|
| D-SIMPLE | 7.58/7.33 | 35802 | 7.33，N100 |
| D-COSIL | 29.90/23.40 | 65040 | 23.52，N94 |
| Q-COSIL | 83.90/81.43 | 54137 | 98.46，N70 |
| Q-PRUNER | 86.34/83.84 | 53656 | 100.20，N66 |

逐题表九字段的n/均值/中位/P25/P75/P95均独立重算一致。Q-PRUNER主输入4685320与小裁判469483分开累计；小裁判只评分，生成0，主生成103108，不与DeepSeek美元账混合。本地GPU未货币化，不能称零成本。源码较少不必然费用较少：本轮D-SIMPLE实际美元略高于D-COSIL，缓存命中和输出量也影响费用。

执行UTC12:13:07至14:38:01，墙钟8693.85秒，约2小时25分钟；单题处理与worker排队分列，D的较短单题时延不能直接当整个运行墙钟。自建Qwen服务UTC14:37:56关闭，实测PID2602696/2602848已消失、7333无监听，GPU2无裁判进程；没有向他人进程发信号。

## 6. 数据隔离与冻结完整性

100题gold在内存按冻结patch实际改动行+AST重算全部一致。对707历史公开题元数据的身份/指纹键及HiFL30精确PR/base隔离交集为0；只说明相对本项目历史独立，不保证预训练未见。全部冻结50份源码/集成工件、300份clean输入、manifest与配置SHA一致。28个模型工件共30484267168字节，其启动SHA承接P1并已验证；收尾仅对尺寸/mtime逐项核对，无异常，未重复哈希30GB权重。两个未单列run级SHA的传递helper也与GitHub启动前快照逐字节匹配，不能声称所有传递依赖都单列在run级freeze中。

审阅期间两份离线gold核验MD曾误放共享RUN/audits，OS进程当时可读；发现后原SHA移入隐藏的evaluator_private。终期扫描5126个请求工件、5125份响应与两MD的51条长行指纹，均无文档名/敏感路径/内容命中；所有工具实参无audits引用，1552成功源码及3017上下文条目全来自base。工具只有固定instance结构JSON等值查询及白名单Python文件读取，没有shell/任意read_file。结论为“发现存放越界，未发现可观察推理泄漏”，没有OS系统调用审计，不能声称worker从未进行任何未记录打开。此事不静默抹去。

封存裁判test仅在原P2完整性核对中检查stat，未打开内容或哈希；未开启test、P3、修复测试、训练或额外模型实验，未改P1预测、历史矩阵及本地上游Git。用户新任务仅在本轮报告校正验收后另行开展，预算独立为USD3，不借用P2/P3的USD30。

## 7. 原稿、修正与复现

新增报告核验代码前已发布并核验 [GitHub备份770efa2](https://github.com/dantongwangwww/cosil_repro/commit/770efa2bdbef8f89adf7905f7e56a950c0366372)，现有方法代码及8份Markdown远端可恢复。冻结P2生成器保留原样；其原自动报告在评测私有目录保留副本和SHA。报告层覆盖须通过独立 `audit_tools/postprocess_report.py` 执行，并记录原/新哈希及字段级差异；推理结果与主评分不改。

最终补签：独立overlay的5项stdlib单元测试、真实默认dry-run与显式apply均通过；应用后21份当前报告逐项SHA全部匹配marker。原records/summary、Hit/CI/p和所有既有时延/token聚合保持一致；100条D-SIMPLE送达布尔与逐题文案已校正。主报告SHA256为 `83b8e1bc556940ba74a68c401e8b76f76d8133cc786b3439b1f539909f013afc`。

CPU复现（不启动推理/测试或GPU；原稿归档保持只读）：

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES="" /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m external_v1.report
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES="" /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m unittest discover -s audit_tools -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES="" /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m audit_tools.postprocess_report
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES="" /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m audit_tools.postprocess_report --apply
```

重新运行原自动生成器会恢复原展示问题，须再运行独立overlay。只重新校正已有报告时运行最后两条即可，不重复模型请求。最终状态见 `external_acceptance_completion.json`，SHA校正证据见 `external_report_audit_overlay.json`。
