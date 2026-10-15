"""Render the honest v5 D2-stop overview from actual archived statistics.

No model calls, test-row parsing, fabricated predictions or matrix writes.
Root owns this overview; the execution agent owns the 300-issue data audit.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/v5_pruner"
OUT = ROOT / "docs/v5-pruner/实验报告_v5_总览.md"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    contract = read(BASE / "execution_contract.json")
    if contract.get("noise_disclosed_exploratory_v3", {}).get("enabled") is True:
        raise RuntimeError("The user authorized A/B continuation; use code_v5.build_v5_ab_overview instead of the historical stop renderer")
    versions = [(label, name, read(BASE / name / "statistics.json"))
                for label, name in (("v1", "data"), ("v2", "data_v2"), ("v3", "data_v3"))]
    final = versions[-1][2]
    if final["passed"] is not False:
        raise RuntimeError("This renderer is only for the actual failed D2 condition")
    review = final["review"]
    errors = review.get("label_errors")
    signed = review.get("status") == "reviewed" and review.get("reviewed_records") == 30
    if errors is not None and errors <= 2:
        raise RuntimeError("D2 QC-stop overview requires the confirmed failed review, not a qualifying review")
    if not (BASE / "data_v3/review_final_counterexamples.json").exists():
        raise RuntimeError("Final stop requires concrete archived counterexamples")
    selected = final["selected"]
    graph = read(BASE / "graph_validation.json")
    lines = []
    for label, name, stats in versions:
        r = stats["review"]
        error_text = str(r["label_errors"]) if "label_errors" in r else "至少3，最终签注待归档"
        s = stats["selected"]
        lines.append(f"| {label} | {stats['candidate_pool']['unique_pairs']:,} | {stats.get('excluded_negative_unique_pairs',0):,} | {s['positive']:,} | {s['negative']:,} | {s['E_unique_union']:,} | {error_text} | 未通过 |")
    version_table = "\n".join(lines)
    source_table = "\n".join(f"| {source} | {selected.get('source_'+source,0):,} | {selected.get('primary_source_'+source,0):,} |"
                             for source in ("A", "B", "C", "D", "e_log", "e_bm25", "e_anchor"))
    gate_table = "\n".join(f"| `{key}` | {'通过' if value else '未通过'} |"
                           for key, value in final["quality_gates"].items())
    split_table = "\n".join(f"| {name} | {assigned} | {selected['by_split'][name]['issues_with_rows']} | {selected['by_split'][name]['positive']} | {selected['by_split'][name]['negative']} | {selected['by_split'][name]['E_unique_union']} |"
                            for name, assigned in (("train",240),("val",30),("test",30)))
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    review_text = (f"v3 完整30条签注记录确认 {errors} 个有证据的漏过滤错误，超过允许的2个。"
                   if signed else "v3 已有至少3个完整源码反例，止损已触发；最后30条签注与哈希归档尚在收尾。")
    text = f'''# v5 训练剪枝裁判实验总览

更新时间：{now}。载体：旧版 CoSIL；题集：同一 SWE-bench Lite 300 个 issue；状态：**D2 数据质量门未通过，按止损规则结束本条件。**

{review_text} 用户最新裁定将8,000正例数量门改为“待 exploratory 重定标”，现有1,542正例的数量不足不再单独阻止探索性训练；但审阅质量门仍不豁免。因此本轮按新路线在第一步止损。**本次没有启动真实双底座训练、验证赛马、校准、test性能评测、60次金丝雀或600次small/hybrid全量定位。** 下文记录真实数据构造、核验失败与代码修复；没有小裁判能力或端到端成绩结论。

## 最新数据处理路线与签结论

执行依据：2026-10-14用户“v5 数据问题处理指令”。第一步要求v3逐条签完30条E类样本，错误≤2才进入exploratory双底座训练；超过2则出失败报告结束数据线，等待新指令。v3最终为30/30已签、3条错误，各E族10条样本中各1条错误，**第一步失败，第二步训练和第三步Verified扩挖均未启动**。不进行第四轮E类重构，不改标签，不更换抽检样本。

签结论及证据见[最终签结论](../../results/v5_pruner/v3_review_final_signoff.json)、[30条原始样本](../../results/v5_pruner/data_v3/human_review.jsonl)、[30条签注](../../results/v5_pruner/data_v3/human_review_codex_reviewed.jsonl)和[完整反例](../../results/v5_pruner/data_v3/review_final_counterexamples.json)。审阅者为“Codex/机械证据审阅”，不冒用真人签名。

用户规定的后续判读作为未执行协议保留：train accuracy<0.70归入(a)，仅此分支启动Verified扩挖；train>0.85且val<0.70归入(b)，调整正则／早停／降低epoch重训一轮，不扩数据；train／val达标且val accuracy≥0.80归入(c)，跳过扩挖，沿用原val体检和赛马资格线再走校准、test一次开箱及管线。两底座沿用LoRA rank16、lr5e-5、3 epoch。exploratory只看train／val，test继续封存。这些是用户约定的操作判读，单凭train／val准确率不能唯一证明数据量或过拟合的因果来源；本次没有指标可归入(a)/(b)/(c)。

若将来实际进入(a)，先排除Verified与Lite300的instance_id交集及用户指定231题无名OOD保留池，采用A/C/D/e_bm25/e_anchor五产线，沿用v3排除规则与按issue的80/10/10切分，既有切分保持不变；新题不伪造B或e_log。**本次未进入该分支，未下载或扩挖Verified，也没有交集数量或扩前／扩后成绩。**

与上述分支独立的E类归档已经完成：见[八个漏过滤案例专项档案](E类漏过滤案例_v1-v2_专项归档.md)，含结构化JSON／CSV、源码关系及证据哈希。Decision-1对线维持取消；不动vLLM／CSRSE，不重跑历史Qwen基线，不发起新的付费请求。

## 执行结果与原计划目标

| 项目 | 计划／门槛 | 本次实际结果 |
|---|---|---|
| D1原料盘点 | 日志、金标、结构可追溯 | 核验通过，路径与原计划的数处误指已修正 |
| 独立正例 | 原≥8,000；现待exploratory重定标 | **1,542；保留原数量门失败记录，当前不据数量单独止损** |
| E负例并集 | ≥3,000 | **3,000，通过数量门** |
| 训练E三族抽检 | 每族10条，30条错误≤2 | **v3至少3个有证据错误，未通过** |
| 双底座LoRA | Qwen3-Reranker-0.6B／Qwen2.5-0.5B-Instruct | 官方底座已下载；真实训练未执行，无训练LoRA权重 |
| val accuracy／AUC | ≥0.80／≥0.85 | 未评测；无赢家 |
| 校准／封存test | val定温度与阈值，test一次开箱 | 未执行；没有消耗test开箱机会 |
| 金丝雀 | 10题×3模式×2重复=60 | **0/60执行** |
| 全量新定位 | 300题×small/hybrid=600 | **0/600执行** |

| 五线目标 | 门槛 | 本次新实验结果 |
|---|---|---|
| 函数Top-5 | ≥111/293（37.88%） | 未执行；111/293是历史v3c off基线 |
| 本地单次裁判延迟 | <0.3秒 | 未评测目标裁判，不用CPU合成测试代替 |
| 大Qwen pruner接口tokens减幅 | ≥80% | 未评测；本地与合计tokens也未测 |
| E正确剔除率 `TN/(TN+FP)` | ≥0.85 | 未评测；混合集剔除precision `TN/(TN+FN)`也未评测 |
| 锚点子组定位成绩 | gold_named／other_named／no_name | 新模型未执行，没有子组成绩 |

既有基线采用同一patch真实改动行＋前后AST金标，函数真值分母293，另外7题为NA。对应[历史v3c总表](../qwen-300/实验报告_v3c_Qwen三臂总表.md)。本次没有把历史37.88%记成新裁判的准确率，也没有新增虚构的逐题预测或矩阵列。

## 原料审计与口径修正

真实900条轨迹位于 `results/qwen_300/fixed/{{off,on,shuffled}}/events/`，共5,598次pruner决策；原计划所指 `results/prune_logs_annot/` 是早期十题目录。当前v3c的实际替换入口为 `code_v3b/fixed_search.py:AFL._prune`。用户确认沿用真实改动行＋AST金标，hunk头仅用于审计；不改变旧预测或评分口径。

原PPR邻接未找到，按用户确认重建base commit静态直接调用图。300份最终图同版；base中存在的321个gold函数均有映射，抽查30个Git源码与调用点见证通过。图的未解析比例为{graph['unresolved_fraction']:.2%}，其中包含内建、外部依赖及动态调用，不能解释成“仓库内部漏掉同等比例的真实调用”。完整证据见[输入审计](../../results/v5_pruner/input_audit.json)与[图验证](../../results/v5_pruner/graph_validation.json)。

用户取消Decision-1对照；Codex执行30条源码证据核验，登记为“Codex/机械证据审阅”。标签来自机械数据源，未用LLM补造标签；本次未调用新的付费模型接口。

## 三轮实际数据构造

三版保持原始issue切分和随机种子，正例资格不变；只在统一机械规则下剔除整个负例pair，不把可能调用写成C正例。候选数与选入数分别统计，三臂重复日志只保留证据，不重复增加物理函数pair。

| 版本 | 保留候选pair | 相对v1排除候选负例 | 最终正例 | 最终负例 | E并集 | 30条核验确认错误 | D2 |
|---|---:|---:|---:|---:|---:|---|---|
{version_table}

v1候选46,415对，v3保留12,605对，累计剔除33,810个候选负例。候选剔除理由可重叠，不能把UP／DOWN计数相加当总剔除数。三轮真实核验均发现规则检查器之外的漏过滤问题；检查器通过只代表与实现规则一致。

最终选入4,626对。按来源计数如下；membership可以重叠，primary互斥：

| 来源 | membership pair | primary pair |
|---|---:|---:|
{source_table}

实际负正比为2:1，E占负例{selected['E_unique_union']/selected['negative']:.2%}；D-only仅84对，占负例{selected.get('primary_source_D',0)/selected['negative']:.2%}。为了同时保留E≥3,000与1:2负正比，普通D覆盖很薄；“D仍保留”这一门只检查非零，不能说明代表性充分。e_log仅161对，其中封存test9对，不能据极小子集得到稳定的因果能力结论。

### 数据局限性：D-only塌陷与负例分布偏差

E占负例97.28%，D-only占2.72%；v3的三族primary负例分别为e_log161、e_bm25 1,390、e_anchor 1,449。它们代表日志诱饵、文本相似和函数名称锚点等特定抽样机制，不能代表真实候选函数的总体分布。e_log按历史Qwen=True筛选，存在选择偏差；30条审阅每族固定10条，属于分层质量检查，3/30不能直接当作按三族自然占比加权的总体噪声率。

D-only只有84条会限制普通无关函数的覆盖。来源membership可重叠，例如带D证据的228条包含同时属于E的样本，不能将其全部算作D-only。训练与验证的C正例证据可见性也不同，见下文输入限制。本轮没有训练或测试成绩，不能把这些风险写成已观察到的模型失效。

| 固定分配 | 分配issue | 有数据行issue | 正例 | 负例 | E并集 |
|---|---:|---:|---:|---:|---:|
{split_table}

训练分配240题中217题有数据行，但**本次实际参与梯度训练为0题**。不把未产生训练行的23题重新算成独立test。若未来进行有效训练，全300、预定held-out60及纯test30必须分别报告；val30会参与选模与校准。

## 为什么8,000正例不够

gold共有368个题目／函数对，其中321个在base commit已有，47个为补丁新增。原料中一跳C只有1,225个；A321＋C1,225恰为1,546个原始独立正例。B来源123个物理pair全部属于已有A，增加证据，不增加独立正例。截断输入去重／冲突过滤减去4个C后为1,542，短缺6,458个。

固定题集与原来源规则不足以满足原计划规模门；不能通过重复900臂日志、扩大C到多跳或由模型造标签补数量。用户现已将8,000门改判为“待exploratory重定标”，是否足以训练尚无真实模型证据。新的条件授权仍要求审阅、切分、去重、泄漏全部通过；本次因审阅失败，没有生成可供训练使用的探索性冻结决定。

## 最终三条残留调用反例

| issue／样本 | 被标为负例的函数 | 完整base源码证明的关系 | 漏过滤原因 |
|---|---|---|---|
| django__django-12983／e_anchor | defaultfilters.slugify | `slugify as _slugify`导入；`return _slugify(value)`进入gold text.slugify | 全局import alias未纳入可能调用摘要 |
| django__django-14238／e_log | ModelBase.__new__ | _prepare → Options._prepare → _get_default_pk_class → issubclass(pk_class,AutoField) → gold AutoFieldMeta.__subclasscheck__ | 元类primitive hook及多跳动态路径 |
| scikit-learn__scikit-learn-14983／e_bm25 | test_cross_validator_with_default_params | repr(KFold实例) →继承的BaseCrossValidator.__repr__ → gold _build_repr | 内建repr与继承方法派发 |

证据包含base blob SHA、完整候选／gold／中间源码、导入绑定及继承见证，见[最终反例档案](../../results/v5_pruner/data_v3/review_final_counterexamples.json)。它们有源码调用证据，不能按“图中没边”判成无关函数。前两版另外确认了defer、sitemap index、Text.draw、hist、Response.content、Optimizer.optimize、latex和ufuncify等路径，均已保留在对应失败审阅中。

前两版的3＋5个案例现已单独整理为[专项案例表](E类漏过滤案例_v1-v2_专项归档.md)，保留原issue／函数身份、漏网方式、证据链与文件哈希，作为“静态图证不了无关”的实证材料；专项归档不新增数据修复轮、不重标训练标签。

v3在运行前被定为本次最后数据修复轮。新抽检仍超过2个错误，触发D2止损；没有继续换抽样或逐题人工筛删直到通过，也没有改写已封存标签。

## 输入本身的信息限制

模型计划仅接收issue前2,000字符与候选函数前1,500字符。C正例标签来自完整调用图，其中train有521/1,053（49.5%）、val有71/87（81.6%）在候选输入中没有完整显式调用证据：调用发生在未提供的gold源码，或在截断后。这诊断输入信息与train／val分布差异，不等于标签错误；本轮未改变输入长度。证据见[输入可见性审计](../../results/v5_pruner/data_input_visibility_audit.json)。其中C正例payload三版不变，因此C计数可沿用；该审计其他负例截断计数属于v1，不混算成v3。

e_log按Qwen=True筛选。未来若做离线对线，只能比较同一真实查询pair，单独标注这种选择偏差；未被旧Qwen查询的BM25／anchor pair不能补造旧判决。没有进行实际对线，因此本次没有模型一致率或新precision／recall／F1。

## 代码、运行修复与资源

`code_v5/`已实现数据挖矿、可追溯静态图、双底座LoRA训练、原生verdict概率、val温度缩放、一次test守卫、函数small/hybrid替换、类请求原Qwen fallback、持久训练／管线驱动及报告工具。相关CPU合成回归和五条真实源反例诊断用于核验实现；不代替真实目标模型评测。

首次挖矿中途进程消失，原因未确定；保留日志后用持久tmux同脚本恢复。v3慢运行的实际profile定位到AST源码提取重复拆整文件，缓存原stdlib splitter后，同解释器切片和完整见证输出保持一致，减少CPU开销。fast入口与缓存、原v3规则、v2辅助脚本分别绑定SHA；没有更改风险规则或抽样。见[独立缓存审计](../../results/v5_pruner/refinement_v3_cache_independent_audit.json)。

保留GPU0既有vLLM与GPU1既有进程，GPU2计划用于裁判、GPU3保留空闲。数据阶段在CPU完成，没有启动真实目标模型。独立审计核对历史900case＋900event共1,800文件，SHA均无漂移；三版数据封存／旧版归档匹配，test开箱marker不存在，现有六列矩阵源匹配。收尾资源审计确认本实验活动进程／tmux均已结束，GPU2／3空闲，GPU0／1既有进程保留。见[最终资源审计](../../results/v5_pruner/final_resource_audit.json)、[训练守卫与文件保护审计](../../results/v5_pruner/final_guard_and_preservation_audit.json)及[独立终稿审计](../../results/v5_pruner/final_independent_audit.json)。

## 质量门与交付文件

| 质量门 | 实际状态 |
|---|---|
{gate_table}

上表反映冻结statistics.json中的原协议结果，文件未修改；`positive_unique_pairs_ge_8000=false`保留为历史规模记录。当前执行路线对数量门的判定是“待exploratory重定标”，真正触发本次停止的是30条核验3错超过2错门槛。

- [300题逐题数据审计](实验报告_v5_逐题数据审计.md)：按同一issue ID列出历史基线、固定split、数据来源、候选剔除与新定位未执行状态。
- [方案偏差与执行决定](方案偏差与执行决定.md)：数量门、口径修正、三轮标签修复与止损。
- [E类漏过滤八例专项归档](E类漏过滤案例_v1-v2_专项归档.md)：v1/v2原始证据的结构化表。
- [最新处理路线与保护核对](../../results/v5_pruner/data_problem_resolution_followup.json)：当前分支、原数量门的解释和数据保护结果。
- [v3统计与质量门](../../results/v5_pruner/data_v3/statistics.json)、[切分](../../results/v5_pruner/data_v3/split_manifest.json)、[test封存](../../results/v5_pruner/data_v3/test_file_seal.json)：原预测与三版数据不覆盖。
- [v1统计](../../results/v5_pruner/data/statistics.json)、[v2统计](../../results/v5_pruner/data_v2/statistics.json)：失败版本及审阅保留。

当前结论是**原计划的数据来源和负例一致性过滤未满足启动条件**。不能据本次执行判断小裁判优于或弱于Qwen-7B，也不能把源码检查器通过、修复脚本加速或旧定位基线当成新实验成功。
'''
    OUT.write_text(text, encoding="utf-8")
    print(json.dumps({"report": str(OUT), "signed_review_complete": signed,
                      "confirmed_review_errors": errors, "new_models_evaluated": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
