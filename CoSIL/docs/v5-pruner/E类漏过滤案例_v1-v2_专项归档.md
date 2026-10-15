# E 类漏过滤案例 v1–v2 专项归档

本档汇总冻结审阅中确认的 **8 个保守排除遗漏：v1 3 个、v2 5 个**。证据来自对应 base commit 源码、官方修复补丁、原 issue、已存日志和调用 witness。审阅身份为 **Codex/机械证据审阅，非真人签字**。原始数据、训练标签、签注与金标均保持不变；本档不做第四轮 E 重构，也不生成新标签。

历史质量门要求每轮 30 条审阅最多 2 错；v1 为 3/30、v2 为 5/30、v3 为 3/30，历史结果均未通过。用户最新裁定允许后续按噪声披露制度开展 A/B 双线，这不把原来的失败签注改成通过。派生数据与训练协议由各自档案记录。

**v3 的 3/30 是训练 E 三族各 10 条的固定分层样本结果，不能证明全体数据有 10% 噪声，也不能证明静态过滤的误差地板是 10%。** 关于噪声是否伤害训练或定位，现阶段是待验证假设，须由后续 A/B 实测。

| 版本 | issue | 候选函数 | 漏网方式 | 证据链 |
|---|---|---|---|---|
| v1 | `django__django-14667` | `django/db/models/query.py::QuerySet.defer@1210` | 动态派发 | QuerySet.defer → clone.query.add_deferred_loading(fields) → Query.add_deferred_loading（金标） |
| v1 | `django__django-16255` | `django/contrib/sitemaps/views.py::index@54` | 动态派发 | index → site.get_latest_lastmod() → Sitemap.get_latest_lastmod（金标） |
| v1 | `matplotlib__matplotlib-23964` | `lib/matplotlib/text.py::Text.draw@707` | 别名、动态派发 | Text.draw → textrenderer.draw_text(...) → RendererPS.draw_text（金标） |
| v2 | `matplotlib__matplotlib-24149` | `lib/matplotlib/axes/_axes.py::Axes.hist@6445` | 别名、中转 | Axes.hist → _barfunc=self.bar → _barfunc(...) → Axes.bar → self._convert_dx(...)（金标） |
| v2 | `psf__requests-2148` | `requests/models.py::Response.content@691` | 中转 | Response.content → self.iter_content(...) → generate() → Response.iter_content.generate（金标） |
| v2 | `django__django-16595` | `django/db/migrations/optimizer.py::MigrationOptimizer.optimize@12` | 中转、动态派发 | MigrationOptimizer.optimize → self.optimize_inner(...) → operation.reduce(...) → AlterField.reduce（金标） |
| v2 | `sympy__sympy-14774` | `sympy/printing/latex.py::latex@2212` | 中转、动态派发、继承 | latex → LatexPrinter.doprint → Printer.doprint → Printer._print → MRO/getattr 动态选择 _print_Function（金标） |
| v2 | `sympy__sympy-16792` | `sympy/utilities/autowrap.py::ufuncify@986` | 中转、继承、动态派发 | ufuncify → make_routine / autowrap → get_code_generator → code_gen.routine(...) → 继承的 CodeGen.routine（金标） |

“确认遗漏”表示候选具有必须保守排除的源码关系或运行风险，**不等价于八个新的金标正例**。其中 hist、ufuncify 只证明可行祖先路径；原 issue 没有证明候选实际被执行。下面逐条分清确定源码证据与条件限制。

## E-v1-01：django__django-14667 / django/db/models/query.py::QuerySet.defer@1210

漏网方式：动态派发。审阅分层：`e_log`；原来源集合：`e_log / e_anchor`。

证据链：QuerySet.defer → clone.query.add_deferred_loading(fields) → Query.add_deferred_loading（金标）。

候选源码存在对 Query 方法的属性链调用，官方补丁修改同名目标；高精度静态图没有唯一解析 clone.query 的类型，导致 E 保守排除遗漏。

证据边界：源码调用表达式和官方补丁支持调用关系；本次归档没有执行该 issue 或记录新的运行轨迹，不能将候选升级成补丁金标。

原训练标签保持 `false`；已有审阅记 `label_error=true`。base commit：`6a970a8b4600eb91be25f38caed0a52269d6303d`；候选完整源码 SHA256：`b432817635e91070ce4c3b9130ead83589bc5a558ca7f2e4a00b6734a88ea661`。

证据文件（按 `instance_id`＋`function_id` 对应，不按行号拼接）：[human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/human_review.jsonl)、[human_review_codex_corrected.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/human_review_codex_corrected.jsonl)、[review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_evidence_checks.json)、[review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_benchmark_patches.json)、[review_causal_risk_classification.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_causal_risk_classification.json)。

## E-v1-02：django__django-16255 / django/contrib/sitemaps/views.py::index@54

漏网方式：动态派发。审阅分层：`e_log`；原来源集合：`e_log / e_bm25`。

证据链：index → site.get_latest_lastmod() → Sitemap.get_latest_lastmod（金标）。

候选源码和 issue traceback 都出现 site.get_latest_lastmod；traceback 落到 sitemaps/__init__.py 的金标函数。site 来自 sitemaps 参数，静态类型未唯一解析。

证据边界：这是原 issue 提供的报错调用链与冻结 base 源码交叉证据；未新增运行复现，候选自身并非被修复函数。

原训练标签保持 `false`；已有审阅记 `label_error=true`。base commit：`444b6da7cc229a58a2c476a52e45233001dc7073`；候选完整源码 SHA256：`fe1ac047f3b6af8b0a097fa410f3a810457babf877c42107f75f6cce53bd8a94`。

证据文件（按 `instance_id`＋`function_id` 对应，不按行号拼接）：[human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/human_review.jsonl)、[human_review_codex_corrected.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/human_review_codex_corrected.jsonl)、[review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_evidence_checks.json)、[review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_benchmark_patches.json)、[review_causal_risk_classification.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_causal_risk_classification.json)。

## E-v1-03：matplotlib__matplotlib-23964 / lib/matplotlib/text.py::Text.draw@707

漏网方式：别名、动态派发。审阅分层：`e_anchor`；原来源集合：`e_log / e_anchor`。

证据链：Text.draw → textrenderer.draw_text(...) → RendererPS.draw_text（金标）。

textrenderer 在分支中取 renderer 或 PathEffectRenderer，接收者依后端变化；issue traceback 明确 Text.draw → PostScript RendererPS.draw_text，静态图未收录该动态派发。

证据边界：报错 traceback 支持该 issue 的后端派发关系；没有据此断言所有 renderer 分支必经 RendererPS，也不更改补丁金标。

原训练标签保持 `false`；已有审阅记 `label_error=true`。base commit：`269c0b94b4fcf8b1135011c1556eac29dc09de15`；候选完整源码 SHA256：`c2910fd0d405da2745de60aaa635aee5ef31838ba3b309bb9be0d83a2955c26d`。

证据文件（按 `instance_id`＋`function_id` 对应，不按行号拼接）：[human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/human_review.jsonl)、[human_review_codex_corrected.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/human_review_codex_corrected.jsonl)、[review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_evidence_checks.json)、[review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_benchmark_patches.json)、[review_causal_risk_classification.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_causal_risk_classification.json)。

## E-v2-04：matplotlib__matplotlib-24149 / lib/matplotlib/axes/_axes.py::Axes.hist@6445

漏网方式：别名、中转。审阅分层：`e_log`；原来源集合：`e_log / e_bm25 / D`。

证据链：Axes.hist → _barfunc=self.bar → _barfunc(...) → Axes.bar → self._convert_dx(...)（金标）。

局部函数别名把 hist 的调用目标藏在 _barfunc；Axes.bar 再调用 _convert_dx。v2 仅比对候选与金标的直接调用叶名，遗漏这条多跳路径。

证据边界：完整源码确定存在可行分支祖先关系，足以触发保守排除；原 issue 主要报告 ax.bar，并没有证明本次故障执行了 hist，不能声称 hist 已被运行证实为相关正例。

原训练标签保持 `false`；已有审阅记 `label_error=true`。base commit：`af39f1edffcd828f05cfdd04f2e59506bb4a27bc`；候选完整源码 SHA256：`d3c1cd4ecb1493920d47676a97c10af94c93f017108b9b97fe78e41e1df53c60`。

证据文件（按 `instance_id`＋`function_id` 对应，不按行号拼接）：[human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review.jsonl)、[human_review_codex_reviewed.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review_codex_reviewed.jsonl)、[review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_evidence_checks.json)、[review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_benchmark_patches.json)、[review_call_evidence.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_call_evidence.json)、[review_multihop_counterexamples.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_multihop_counterexamples.json)。

完整源码 witness：

| 函数 | base Git blob SHA1 | 完整函数源码 SHA256 |
|---|---|---|
| `lib/matplotlib/axes/_axes.py::Axes.hist@6445` | `fdac0f3560f4b129ddd8e61c77a8edf44e6c8069` | `d3c1cd4ecb1493920d47676a97c10af94c93f017108b9b97fe78e41e1df53c60` |
| `lib/matplotlib/axes/_axes.py::Axes.bar@2206` | `fdac0f3560f4b129ddd8e61c77a8edf44e6c8069` | `119dc6c10047bf70451e865d34e05cf33c61e8587b148641dddd6213cc81fbeb` |
| `lib/matplotlib/axes/_axes.py::Axes._convert_dx@2153` | `fdac0f3560f4b129ddd8e61c77a8edf44e6c8069` | `24519da2ff6b8dd56754713fbaf9c39d7ea8310e12dc55b5ad8f0a6d62bdb38a` |

## E-v2-05：psf__requests-2148 / requests/models.py::Response.content@691

漏网方式：中转。审阅分层：`e_log`；原来源集合：`e_log / e_bm25 / D`。

证据链：Response.content → self.iter_content(...) → generate() → Response.iter_content.generate（金标）。

content 调用外层 iter_content，外层创建嵌套 generate 生成器并返回；金标是该嵌套函数。v2 未把 nested gold 风险传播至外层和祖先；issue traceback 也从 content 到 generate。

证据边界：调用及生成器消费条件由源码说明，原 issue traceback 佐证故障链；这仍不等于 content 本身就是官方修复点。

原训练标签保持 `false`；已有审阅记 `label_error=true`。base commit：`fe693c492242ae532211e0c173324f09ca8cf227`；候选完整源码 SHA256：`dd9269ef0bfa504bfb578378d526bb9e6122811b0093ef757f838a082ce84a58`。

证据文件（按 `instance_id`＋`function_id` 对应，不按行号拼接）：[human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review.jsonl)、[human_review_codex_reviewed.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review_codex_reviewed.jsonl)、[review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_evidence_checks.json)、[review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_benchmark_patches.json)、[review_call_evidence.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_call_evidence.json)、[review_multihop_counterexamples.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_multihop_counterexamples.json)。

完整源码 witness：

| 函数 | base Git blob SHA1 | 完整函数源码 SHA256 |
|---|---|---|
| `requests/models.py::Response.content@691` | `0dc5556838c734e0a24d4795dcf16cd6003871c5` | `dd9269ef0bfa504bfb578378d526bb9e6122811b0093ef757f838a082ce84a58` |
| `requests/models.py::Response.iter_content@623` | `0dc5556838c734e0a24d4795dcf16cd6003871c5` | `7d414e93af9b716a3537ed33eac07331e849ff4cb5e6532d7598041a2841ec33` |
| `requests/models.py::Response.iter_content.generate@633` | `0dc5556838c734e0a24d4795dcf16cd6003871c5` | `a1bbb476f78e3b970ef14734c503bb9fb4aaf3b13ab7bec4b2a093bdef532e0d` |

## E-v2-06：django__django-16595 / django/db/migrations/optimizer.py::MigrationOptimizer.optimize@12

漏网方式：中转、动态派发。审阅分层：`e_log`；原来源集合：`e_log / e_anchor`。

证据链：MigrationOptimizer.optimize → self.optimize_inner(...) → operation.reduce(...) → AlterField.reduce（金标）。

optimize 先进入 optimize_inner，再按 operations 元素动态派发 reduce；issue 明确 operations[1:] 是多条 AlterField，因此金标 AlterField.reduce 可被调用。直接叶名比对未传播多跳风险。

证据边界：源码与 issue 传入类型支持该分支的目标；本次归档没有新增执行轨迹，也没有把所有 operation.reduce 都视为 AlterField.reduce。

原训练标签保持 `false`；已有审阅记 `label_error=true`。base commit：`f9fe062de5fc0896d6bbbf3f260b5c44473b3c77`；候选完整源码 SHA256：`591b6883c2affd681862627c7a19f431b3da7647a934d599c012db6aa0ed7cdb`。

证据文件（按 `instance_id`＋`function_id` 对应，不按行号拼接）：[human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review.jsonl)、[human_review_codex_reviewed.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review_codex_reviewed.jsonl)、[review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_evidence_checks.json)、[review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_benchmark_patches.json)、[review_call_evidence.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_call_evidence.json)、[review_multihop_counterexamples.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_multihop_counterexamples.json)。

完整源码 witness：

| 函数 | base Git blob SHA1 | 完整函数源码 SHA256 |
|---|---|---|
| `django/db/migrations/optimizer.py::MigrationOptimizer.optimize@12` | `7e5dea23774326fb95afdde051a58bc55b45ca25` | `591b6883c2affd681862627c7a19f431b3da7647a934d599c012db6aa0ed7cdb` |
| `django/db/migrations/optimizer.py::MigrationOptimizer.optimize_inner@40` | `7e5dea23774326fb95afdde051a58bc55b45ca25` | `784a080663219d647120a09107b0f6a4c3bbf4fd270a1168e3155804b3d3d680` |
| `django/db/migrations/operations/fields.py::AlterField.reduce@249` | `cd3aab43addefabd131c0ddc480f3ef6525d48d1` | `e8f947ddd3eeb47a6ace8d6d99c7c9166884f0bffb31626fd0f2224ffdc021ef` |

## E-v2-07：sympy__sympy-14774 / sympy/printing/latex.py::latex@2212

漏网方式：中转、动态派发、继承。审阅分层：`e_log`；原来源集合：`e_log / e_bm25 / e_anchor / D`。

证据链：latex → LatexPrinter.doprint → Printer.doprint → Printer._print → MRO/getattr 动态选择 _print_Function（金标）。

打印器按表达式类的 MRO 构造方法名并 getattr；acsc/asec 继承 InverseTrigonometricFunction → Function，冻结类 witness 与完整调用源码支持金标路径。v2 没有多跳派发闭包。

证据边界：这是基于源码、类继承和 issue 表达式的可行派发链；未重放 SymPy 运行，也没有把 MRO 中每个方法视为实际调用或新正例。

原训练标签保持 `false`；已有审阅记 `label_error=true`。base commit：`8fc63c2d71752389a44367b8ef4aba8a91af6a45`；候选完整源码 SHA256：`1220c05a9843e04ecaeb4e29005f3ec8b9079167238271d326282c2ba8a78c09`。

证据文件（按 `instance_id`＋`function_id` 对应，不按行号拼接）：[human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review.jsonl)、[human_review_codex_reviewed.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review_codex_reviewed.jsonl)、[review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_evidence_checks.json)、[review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_benchmark_patches.json)、[review_call_evidence.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_call_evidence.json)、[review_multihop_counterexamples.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_multihop_counterexamples.json)。

完整源码 witness：

| 函数 | base Git blob SHA1 | 完整函数源码 SHA256 |
|---|---|---|
| `sympy/printing/latex.py::latex@2212` | `a3ead157c1aefec7c2a469cf9f9b38bf5c891d27` | `1220c05a9843e04ecaeb4e29005f3ec8b9079167238271d326282c2ba8a78c09` |
| `sympy/printing/latex.py::LatexPrinter.doprint@187` | `a3ead157c1aefec7c2a469cf9f9b38bf5c891d27` | `be28c3884644221cf191db87011680691dc9a4280d02ba6d8a22001ab3d59bc9` |
| `sympy/printing/printer.py::Printer._print@238` | `93578d095007b0c739f6582f129b464564535fc2` | `cefa073037401894eca3a31803f66794f84b3de69f66d4d927e4f21b286841f9` |
| `sympy/printing/printer.py::Printer.doprint@234` | `93578d095007b0c739f6582f129b464564535fc2` | `98c9c517b59c10f56cb56dd6aa93a1b6f2030125b28303a7e6668c6979ed3a51` |
| `sympy/printing/latex.py::LatexPrinter._print_Function@715` | `a3ead157c1aefec7c2a469cf9f9b38bf5c891d27` | `9a7895573101a7517b8c36b9fd2057756fa263191f57f52faddeb3adc560f0f4` |

类继承 witness：`[{'class': 'TrigonometricFunction', 'line': 27, 'bases': ['Function'], 'explicit_latex_method': []}, {'class': 'InverseTrigonometricFunction', 'line': 1861, 'bases': ['Function'], 'explicit_latex_method': []}, {'class': 'asec', 'line': 2564, 'bases': ['InverseTrigonometricFunction'], 'explicit_latex_method': []}, {'class': 'acsc', 'line': 2691, 'bases': ['InverseTrigonometricFunction'], 'explicit_latex_method': []}]`；继承源 Git blob SHA1：`2307b711ef0f8809cfbcb99ee0e58061d676b637`。

## E-v2-08：sympy__sympy-16792 / sympy/utilities/autowrap.py::ufuncify@986

漏网方式：中转、继承、动态派发。审阅分层：`e_bm25`；原来源集合：`e_bm25`。

证据链：ufuncify → make_routine / autowrap → get_code_generator → code_gen.routine(...) → 继承的 CodeGen.routine（金标）。

ufuncify 的 numpy 分支调用 make_routine，其他分支调用 autowrap；它们通过工厂获得 code_gen，再调用 routine。C/F95 系列类继承 CodeGen 且不覆盖 routine，直接叶名过滤遗漏该祖先路径。

证据边界：完整源码证明存在可行祖先调用路径，应作保守风险排除；issue 的直接复现入口为 autowrap，未证明 ufuncify 实际执行，不能把 ufuncify 改成金标正例。

原训练标签保持 `false`；已有审阅记 `label_error=true`。base commit：`09786a173e7a0a488f46dd6000177c23e5d24eed`；候选完整源码 SHA256：`ea831af0c7e08dddc4d07fa856c3e53dd663e4c3e7a113fc05deda0a01144d1b`。

证据文件（按 `instance_id`＋`function_id` 对应，不按行号拼接）：[human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review.jsonl)、[human_review_codex_reviewed.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review_codex_reviewed.jsonl)、[review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_evidence_checks.json)、[review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_benchmark_patches.json)、[review_call_evidence.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_call_evidence.json)、[review_multihop_counterexamples.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_multihop_counterexamples.json)。

完整源码 witness：

| 函数 | base Git blob SHA1 | 完整函数源码 SHA256 |
|---|---|---|
| `sympy/utilities/autowrap.py::ufuncify@986` | `bd6afb12d13b85cefa488fab2da5e08cb5790462` | `ea831af0c7e08dddc4d07fa856c3e53dd663e4c3e7a113fc05deda0a01144d1b` |
| `sympy/utilities/autowrap.py::autowrap@535` | `bd6afb12d13b85cefa488fab2da5e08cb5790462` | `bf90e61f12fbaa730d771f0ed9f7ea51bbd717bfe90ffa3241e597afdfcf0bd9` |
| `sympy/utilities/codegen.py::get_code_generator@1969` | `f0befb2bd7394f9b79c0787878d67e0faeb8aaae` | `9ec99effceb5e3baf82d3412998e43e15b8788996eee0b6d72e877bd45ba51a1` |
| `sympy/utilities/codegen.py::make_routine@2146` | `f0befb2bd7394f9b79c0787878d67e0faeb8aaae` | `7ad68204a644d78df91e084641481606af4b779925bb4676f3ab0fe9102e1310` |
| `sympy/utilities/codegen.py::CodeGen.routine@577` | `f0befb2bd7394f9b79c0787878d67e0faeb8aaae` | `9bfd89f9850fe366520b59b8eca0367e46cdff12aa4c4770b6fe7a162baaefa2` |

类继承 witness：`[{'class': 'CodeGen', 'line': 539, 'bases': ['object'], 'routine_definitions': [577]}, {'class': 'CCodeGen', 'line': 862, 'bases': ['CodeGen'], 'routine_definitions': []}, {'class': 'C89CodeGen', 'line': 1084, 'bases': ['CCodeGen'], 'routine_definitions': []}, {'class': 'C99CodeGen', 'line': 1087, 'bases': ['CCodeGen'], 'routine_definitions': []}, {'class': 'FCodeGen', 'line': 1090, 'bases': ['CodeGen'], 'routine_definitions': []}]`；继承源 Git blob SHA1：`f0befb2bd7394f9b79c0787878d67e0faeb8aaae`。

## 材料与可复核范围

机器可读完整档案：[e_filter_missed_cases_v1_v2.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/e_filter_missed_cases_v1_v2.json)；八行表格：[e_filter_missed_cases_v1_v2.csv](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/e_filter_missed_cases_v1_v2.csv)。JSON 包含完整 issue、候选源码、官方补丁，以及 v2 的中转/金标源码 witness、身份选择器和原证据 SHA256。

各例机制允许多标签，计数不能相加作为独立样本数量。本档仅记录已审阅样本，不能推断其他样本都正确，也不估计总体噪声率。v1/v2 的漏过滤率不能与 v3 直接作随机抽样比较；重构改变了候选池。既有审阅所指出的“可能调用”只支持风险剔除，不能凭可能关系扩充 C 正例。

| 冻结证据文件 | SHA256 |
|---|---|
| [human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/human_review.jsonl) | `8bb17c5ece7a2166109f5a061f39635f5dc1000ac8ec9ff15e191bfc412bae41` |
| [human_review_codex_corrected.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/human_review_codex_corrected.jsonl) | `f7b499df2148b106737d3cb3489cc459bb8401c93e5a3f109dd2dd39ba29ed6a` |
| [review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_evidence_checks.json) | `b78c7ffb146b2f9188d812af771d08898a6d5ab10f89b495f66d46e8b3bf6e62` |
| [review_causal_risk_classification.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_causal_risk_classification.json) | `72c41cc9475253504b1cf88d4acd9d7ce2a5a0021d67887b1457b789cddca6b4` |
| [review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data/review_benchmark_patches.json) | `6fb0edc8f94a74c3a8ef481c313e78f6654d555091460b23772551951763a413` |
| [human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review.jsonl) | `b96cba0a3e11569736ed61441bc3f95de58c6c7a0e1d1f10fb24b265e110ae6d` |
| [human_review_codex_reviewed.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/human_review_codex_reviewed.jsonl) | `93a5ffb335b2ef5e31939ab9d5844980bf3d95d278995da11f3d9faf96e0b075` |
| [review_evidence_checks.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_evidence_checks.json) | `48542e73049c7f1898235bb53c0360f90dae0923f806ff8cb67bdfa9ed99b70d` |
| [review_call_evidence.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_call_evidence.json) | `8848dfadc7311d9783b9ce3a36c37d12d630b7ec906d8363e82babf5e0bec926` |
| [review_multihop_counterexamples.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_multihop_counterexamples.json) | `1573e6e9b7300ed2ecda15bd115d0f531ca224b596fa7400d4170a0810c6ec1f` |
| [review_benchmark_patches.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v2/review_benchmark_patches.json) | `735d49e070418fd3ef2055c681caea31415dddcb46d14503b872ea22e3a2be81` |
| [human_review.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v3/human_review.jsonl) | `29032be76cd2e5d7c60bf019331772687c3c96820caf7feb6106bcba6dc78d91` |
| [human_review_codex_reviewed.jsonl](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v3/human_review_codex_reviewed.jsonl) | `c0e181f1fe825954a2e7b086a1f3a6c53dd279ad5d2987b4cfb6f28ae39997cb` |
| [statistics.json](/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v3/statistics.json) | `2bed8571dfc5769f09f0bcb5edefb6e6a5cf981e7b91e3401241e7e859c8dbd2` |

归档验证：原证据读取前后 SHA256 一致；恰好 8 个不同 issue/function 案例，匹配 v1/v2 所有已有 `label_error=true`；所有候选及 v2 中转/金标函数源码 SHA256 已复算。封存 test 的训练评估数据未解码，未启动模型或访问 API。
