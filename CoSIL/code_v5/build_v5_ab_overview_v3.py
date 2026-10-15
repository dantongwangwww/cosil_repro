"""Render the current authorized A/B data and training report from receipts.

Read metadata only; never decode sealed test rows or load/call a model.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/v5_pruner"
OUT = ROOT / "docs/v5-pruner/实验报告_v5_总览.md"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def optional(path):
    path = Path(path)
    return read(path) if path.exists() else None


def main():
    contract = read(BASE / "execution_contract.json")
    policy = contract["noise_disclosed_exploratory_v3"]
    if policy.get("enabled") is not True:
        raise RuntimeError("The current report requires explicit noise-disclosure authorization")
    state = read(BASE / "data_problem_resolution_followup.json")
    original = read(BASE / "data_v3/statistics.json")
    signoff = read(BASE / "v3_review_final_signoff.json")
    archive = read(BASE / "e_filter_missed_cases_v1_v2.json")
    derived = optional(BASE / "data_v3_noise_disclosed/statistics.json")
    counts = derived.get("selected", {}) if derived else {}
    training = BASE / "A_v3_noise_disclosed_training_exploratory"
    pair = optional(training / "pair_status.json")
    coverage = optional(BASE / "runtime_coverage/summary.json")
    outcome = optional(BASE / "A_v3_noise_disclosed_outcome_exploratory/assessment_report.json")
    prescription = optional(BASE / "A_regularized_execution_contract.json")
    gold_routes = optional(BASE / "A_pre_regularization_reranker_gold_routes_exploratory/gold_route_report.json")
    instruct_routes = optional(BASE / "A_original_instruct_best_gold_routes_exploratory/gold_route_report.json")
    regularized_dir = BASE / "A_rank8_dropout01_exploratory"
    regularized_state = optional(regularized_dir / "sequence_status.json")
    reg_outcome = optional(regularized_dir / "outcome/assessment_report.json")
    reg_routes = optional(BASE / "A_post_regularization_peak_gold_routes_exploratory/gold_route_report.json")
    b_raw_stats = optional(BASE / "data_v3_runtime_filtered/statistics.json")
    b_reviewed_stats = optional(BASE / "data_v3_runtime_filtered_reviewed/statistics.json")
    b_parent = BASE / "B_runtime_reviewed_regularized_exploratory"
    b_sequence = optional(b_parent / "sequence_status.json")
    b_pair = optional(b_parent / "training/pair_status.json")
    if pair:
        state["A_training_stage"] = f"持久训练状态：{pair['stage']}；实际启动模型数{len(pair.get('runs', []))}"
    if regularized_state:
        state["A_training_stage"] += f"；独立处方状态：{regularized_state['stage']}"
    if coverage:
        state["B_stage"] = f"正式缓存{coverage['completed']}/300；双证据合格{coverage['dual_evidence_eligible']}；其余失败／不完整保留纯静态标记"
    timestamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    rows = []
    for name, filename in (("v1", "data"), ("v2", "data_v2"), ("v3", "data_v3")):
        stats = read(BASE / filename / "statistics.json")
        selected, review = stats["selected"], stats["review"]
        rows.append(f"| {name} | {selected['positive']:,} | {selected['negative']:,} | {selected['E_unique_union']:,} | {review['label_errors']}/30 | 历史≤2门未通过 |")
    version_table = "\n".join(rows)
    derived_text = (f"派生统计已落盘：正例{counts['positive']:,}、负例{counts['negative']:,}、E并集{counts['E_unique_union']:,}。"
                    if counts else "A线派生数据正在按精确三条排除规则生成；下表列出授权后的预期计数，实际计数以派生统计和独立审计为准。")
    reports = list(state.get("A_result_reports", []))
    reports = [str((ROOT / path).resolve()) if not Path(path).is_absolute() else str(Path(path).resolve())
               for path in reports]
    if any(not Path(path).exists() for path in reports):
        raise FileNotFoundError("A result report path does not resolve from repository root")
    a_doc = ROOT / "docs/v5-pruner/实验报告_v5_A线_v3噪声披露exploratory.md"
    if a_doc.exists() and str(a_doc) not in reports:
        reports.append(str(a_doc))
    result_links = "\n".join(f"- [{Path(path).name}]({path})" for path in reports) or "完整A线双底座结果尚未完成。"
    model_rows = []
    for kind in ("reranker", "instruct"):
        if outcome:
            model = outcome["models"][kind]
            measured = model["best"]
            va = measured["val"]
            model_rows.append(f"| {kind} | best epoch {measured['epoch']}，完整A结果 | {measured['train']['overall']['accuracy']:.2%} | {va['overall']['accuracy']:.2%} | {va['overall']['auc']:.5f} | {va['E_correct_rejection_rate']:.2%} | {va['overall']['reject_precision']:.2%} |")
        else:
            summary = optional(training / kind / "training_summary.json")
            curves = optional(training / kind / "training_curves.json")
            if summary:
                measured = summary["checkpoint_assessments"]["best"]
                va = measured["val"]
                model_rows.append(f"| {kind} | best epoch {measured['epoch']}，单底座完成 | {measured['train']['overall']['accuracy']:.2%} | {va['overall']['accuracy']:.2%} | {va['overall']['auc']:.5f} | {va['E_correct_rejection_rate']:.2%} | {va['overall']['reject_precision']:.2%} |")
            elif curves:
                measured = curves[-1]
                va = measured["val"]
                model_rows.append(f"| {kind} | epoch {measured['epoch']}，阶段val | 未完成完整train评估 | {va['overall']['accuracy']:.2%} | {va['overall']['auc']:.5f} | {va['E_correct_rejection_rate']:.2%} | {va['overall']['reject_precision']:.2%} |")
            else:
                model_rows.append(f"| {kind} | 训练／等待中 | NA | NA | NA | NA | NA |")
    reg_summary = optional(regularized_dir / "reranker/training_summary.json")
    reg_curves = optional(regularized_dir / "reranker/training_curves.json")
    if reg_summary:
        m = reg_summary['checkpoint_assessments']['best']
        va = m['val']
        model_rows.append(f"| reranker处方 rank8/dropout0.1 | val峰值epoch {m['epoch']} | {m['train']['overall']['accuracy']:.2%} | {va['overall']['accuracy']:.2%} | {va['overall']['auc']:.5f} | {va['E_correct_rejection_rate']:.2%} | {va['overall']['reject_precision']:.2%} |")
    elif reg_curves:
        m = reg_curves[-1]
        va = m['val']
        model_rows.append(f"| reranker处方 rank8/dropout0.1 | epoch {m['epoch']}阶段val | 未完成完整train评估 | {va['overall']['accuracy']:.2%} | {va['overall']['auc']:.5f} | {va['E_correct_rejection_rate']:.2%} | {va['overall']['reject_precision']:.2%} |")
    else:
        model_rows.append(f"| reranker处方 rank8/dropout0.1 | {regularized_state['stage'] if regularized_state else '准备中'} | NA | NA | NA | NA | NA |")
    model_table = "\n".join(model_rows)
    b_model_rows = []
    for kind in ('reranker', 'instruct'):
        summary = optional(b_parent / 'training' / kind / 'training_summary.json')
        curves = optional(b_parent / 'training' / kind / 'training_curves.json')
        if summary:
            m = summary['checkpoint_assessments']['best']
            va = m['val']
            b_model_rows.append(f"| {kind} | best epoch {m['epoch']}，单底座完成 | {m['train']['overall']['accuracy']:.2%} | {va['overall']['accuracy']:.2%} | {va['overall']['auc']:.5f} | {va['E_correct_rejection_rate']:.2%} | {va['overall']['gold_retention_recall']:.2%} | {va['overall']['reject_precision']:.2%} |")
        elif curves:
            m = curves[-1]
            va = m['val']
            b_model_rows.append(f"| {kind} | epoch {m['epoch']}阶段val | 尚未完整train评估 | {va['overall']['accuracy']:.2%} | {va['overall']['auc']:.5f} | {va['E_correct_rejection_rate']:.2%} | {va['overall']['gold_retention_recall']:.2%} | {va['overall']['reject_precision']:.2%} |")
        else:
            b_model_rows.append(f"| {kind} | {b_pair['stage'] if b_pair else b_sequence['stage'] if b_sequence else '未启动'} | NA | NA | NA | NA | NA | NA |")
    b_model_table = '\n'.join(b_model_rows)
    b_data_text = "B数据构建和新30条审阅尚未完成。"
    if b_raw_stats:
        bs = b_raw_stats['selected']
        br = b_raw_stats['review']
        b_data_text = (f"修后B原始数据已经生成：正例{bs['positive']:,}、负例{bs['negative']:,}、E并集{bs['E_unique_union']:,}。"
                       f"实际签注{br.get('reviewed_records', 0)}/30，审阅不安全负例数{br.get('label_errors')}（None表示尚未完成，不是零错误）。")
        if b_reviewed_stats:
            bs = b_reviewed_stats['selected']
            b_data_text += f" 审阅后精准删错派生数据：正例{bs['positive']:,}、负例{bs['negative']:,}、E并集{bs['E_unique_union']:,}。"
            b_data_text += (" 新审阅8/30是保守不安全率，包含7条明确源码关系和1条条件性AST visitor风险，"
                            "不把8条都称为已证实该issue实际执行的标签错误。抽样中10条运行覆盖合格、20条纯静态，"
                            "不安全分别1/10与7/20；不是总体噪声率或A/B因果改善证据。删除8条后剩余22条不称为重新随机抽检通过。")
        b_data_text += ("\n\n证据构建修复已归档：旧采集器只列补丁before目标，漏列补丁新增行映射到base既存函数的gold。"
                       "独立完整gold核验仍保留133个原合格case，不升级原167个不合格case。"
                       "修前B审阅包完整保留，修后包补齐gold源码；不改静态过滤规则、标签或原缓存。"
                       "[独立完整gold覆盖审计](../../results/v5_pruner/runtime_coverage/full_existing_gold_eligibility_upgrade_audit.json)。")
    routing_text = "gold 三分路由正在从真实验证预测核算。"
    if gold_routes:
        binary = gold_routes['binary_threshold_0_5']['overall']
        route_rows = []
        for key, name in (("raw_nominal", "未校准＋默认阈值"),
                          ("calibrated_nominal", "val温度校准＋默认阈值"),
                          ("calibrated_val_safety_diagnostic", "val温度校准＋安全阈值诊断")):
            if key not in gold_routes['routing_variants']:
                continue
            variant = gold_routes['routing_variants'][key]
            cells = [f"{variant['gold_routes'][r]['count']}/{variant['gold_positive_pairs']} ({variant['gold_routes'][r]['fraction']:.2%})"
                     for r in ('retain', 'reject', 'qwen')]
            route_rows.append(f"| {name} | {variant['low']:.2f}/{variant['high']:.2f} | " + ' | '.join(cells)
                              + f" | {variant['gray_fraction']:.2%} | {variant['E']['direct_correct_rejection_rate']:.2%} |")
        routing_text = (f"原 reranker 的 gold 保留率 **{binary['gold_retained_pairs']}/{binary['gold_positive_pairs']}={binary['gold_retention_recall']:.2%}** "
                        "是未校准 p≥0.5 的二分类召回，发生在灰区划分前；不是高置信直判或灰区 Qwen 后的最终召回。\n\n"
                        "| 口径（均为 val 诊断） | low/high | gold直判保留 | gold直判剪除 | gold灰区 | 全体灰区 | E直判剔除 |\n"
                        "|---|---|---:|---:|---:|---:|---:|\n" + '\n'.join(route_rows)
                        + "\n\n安全阈值的零直剪仅是同一 val 上拟合的结果；整体灰区90.36%、E直剪14.47%，尚不能证明替代成本目标。"
                          "未运行灰区 Qwen、未部署阈值、未打开 test。"
                          "[逐条gold概率、校准与三分路由收据](../../results/v5_pruner/A_pre_regularization_reranker_gold_routes_exploratory/gold_route_report.md)。")
    if instruct_routes:
        ib = instruct_routes['binary_threshold_0_5']['overall']
        rows = []
        for key, name in (("raw_nominal", "未校准＋默认阈值"),
                          ("calibrated_nominal", "val温度校准＋默认阈值"),
                          ("calibrated_val_safety_diagnostic", "val温度校准＋安全阈值诊断")):
            v = instruct_routes['routing_variants'][key]
            groups = [f"{v['gold_routes'][r]['count']}/{v['gold_positive_pairs']} ({v['gold_routes'][r]['fraction']:.2%})"
                      for r in ('retain', 'reject', 'qwen')]
            rows.append(f"| {name} | {v['low']:.2f}/{v['high']:.2f} | " + ' | '.join(groups)
                        + f" | {v['gray_fraction']:.2%} | {v['E']['direct_correct_rejection_rate']:.2%} |")
        routing_text += (f"\n\n原 instruct 的既定E-best为epoch2，二分类gold召回为{ib['gold_retained_pairs']}/{ib['gold_positive_pairs']}={ib['gold_retention_recall']:.2%}，同口径三分如下。"
                         "其accuracy峰值epoch3另作诊断，未改原best或赛马条件。\n\n"
                         "| instruct口径（均为val诊断） | low/high | gold直判保留 | gold直判剪除 | gold灰区 | 全体灰区 | E直判剔除 |\n"
                         "|---|---|---:|---:|---:|---:|---:|\n" + '\n'.join(rows)
                         + "\n\n[instruct逐条gold与校准收据](../../results/v5_pruner/A_original_instruct_best_gold_routes_exploratory/gold_route_report.md)。")
    prescription_result_text = "处方最终完整train/val与赛马尚未完成；不据阶段结果放行正式模型。"
    if reg_outcome:
        r = reg_outcome['comparison']['post_regularization_peak']
        v = r['val']
        gap = r['train']['overall']['accuracy'] - v['overall']['accuracy']
        prescription_result_text = (f"处方完成，选中epoch{r['epoch']}（第2/3轮accuracy并列，以AUC选择第3轮）："
                                    f"train{r['train']['overall']['accuracy']:.2%}、val{v['overall']['accuracy']:.2%}，差{100*gap:.2f}个百分点；"
                                    f"AUC{v['overall']['auc']:.6f}、E正确剔除{v['E_correct_rejection_rate']:.2%}，"
                                    "赛马无合格赢家。相比原75.48%，处方没有提高val accuracy。"
                                    "[处方完整报告](实验报告_v5_A线_rank8_dropout01正则处方.md)。"
                                    "\n\n按用户最新裁定，已用官方500题真实patch改动行与AST重生权威OOD身份：剔除Lite交集93题后，407题划为221题保留与186题可挖矿。"
                                    "186题静态五产线挖矿与独立CPU运行时覆盖均已实际启动；融合数据、审阅及扩后训练尚在后续阶段。当前A/B只比较Lite独立训练结果。"
                                    "[实际分支收据](../../results/v5_pruner/A_branch_processing_receipt.json)。")
    if reg_routes:
        route_rows = []
        for key, name in (("raw_nominal", "未校准＋默认阈值"),
                          ("calibrated_nominal", "val校准＋默认阈值"),
                          ("calibrated_val_safety_diagnostic", "val校准＋安全阈值诊断")):
            v = reg_routes['routing_variants'][key]
            cells = [f"{v['gold_routes'][r]['count']}/{v['gold_positive_pairs']} ({v['gold_routes'][r]['fraction']:.2%})"
                     for r in ('retain', 'reject', 'qwen')]
            route_rows.append(f"| {name} | {v['low']:.2f}/{v['high']:.2f} | " + ' | '.join(cells)
                              + f" | {v['gray_fraction']:.2%} | {v['E']['direct_correct_rejection_rate']:.2%} |")
        routing_text += ("\n\n处方reranker的最终峰值权重，采用同一定义报告：\n\n"
                         "| 处方口径（均为val诊断） | low/high | gold直判保留 | gold直判剪除 | gold灰区 | 全体灰区 | E直判剔除 |\n"
                         "|---|---|---:|---:|---:|---:|---:|\n" + '\n'.join(route_rows)
                         + "\n\n[处方逐条gold概率与路由收据](../../results/v5_pruner/A_post_regularization_peak_gold_routes_exploratory/gold_route_report.md)。"
                           "安全阈值仍使全部34个gold进入灰区，零直剪仅是拟合val的结果；未调用Qwen或发布管线阈值。")
    text = f'''# v5 exploratory 双线实验总览

更新时间：{timestamp}。仓库：旧版CoSIL；题集：同一SWE-bench Lite 300个issue。当前执行依据为**2026-10-14用户最新判读修正：E噪声披露双线继续；reranker 的23.93pp train-val差判过拟合，保留原结果并执行rank8/dropout0.1处方；处方后val<0.80则Verified扩挖与B覆盖过滤合并**。此前D2止损报告已保存为[历史归档](实验报告_v5_D2历史止损_总览.md)。历史失败签注保留，当前数据线继续。

| 工作项 | 当前落盘状态 |
|---|---|
| v3最终逐条审阅 | {signoff['completed_records']}/30完成，确认{signoff['known_label_errors']}条错误；历史≤2门失败，已签结论 |
| v1/v2八例专项归档 | 已完成3＋5个案例，含JSON、CSV、证据链与哈希 |
| A线派生数据 | {state.get('A_stage', '准备中')} |
| A线双底座训练／体检 | {state.get('A_training_stage', '尚未启动；准备数据与冻结协议、等待空闲GPU')} |
| B线失败测试覆盖 | {state.get('B_stage', '环境准备与金丝雀')} |
| 封存test／金丝雀定位／全量新定位 | {state.get('evaluation_stage', '尚未执行；test继续封存')} |

## 当前政策、签注与数据版本

原v3保持字节不变，包括标签、统计、切分和封存test。30条证据审阅签注及[独立签结论](../../results/v5_pruner/v3_review_final_signoff.json)记录3条错误，各E族10条样本中各1条。审阅者为“Codex/机械证据审阅”，不是冒用真人签名。最新授权改变后续启动政策，不把旧签注或原statistics.passed改成通过。

8,000正例数量门改判为“待exploratory重定标”；原1,542的数量不足本身不阻止当前A线。E类标签质量改为披露抽检噪声与删除已确认train错误；机械标签来源、完整30条审阅、固定切分、去重、泄漏、原数据保护与test封存仍是严格条件。新协议和历史协议快照见[执行契约](../../results/v5_pruner/execution_contract.json)，当前状态见[执行记录](../../results/v5_pruner/data_problem_resolution_followup.json)。

| 原版本 | 独立正例 | 负例 | E并集 | 分层抽检错误 | 历史审阅结论 |
|---|---:|---:|---:|---:|---|
{version_table}

报告标注：**E类估计噪声约10%（三族各10条的分层抽检3/30）**。用户将三轮结果提出为静态证据实测地板的解释，现有证据不足以证明收敛或不可降低的噪声地板：每轮候选与抽检样本不同，且每族固定10条不按实际占比加权，3/30也不等于总体负例错误率。删除已确认3条后，不把27条剩余样本的零已知错误当作重新随机抽检通过。噪声对模型及定位的实际影响留待A/B实测。

### A线：剔除已确认训练错误后的exploratory训练

仅从独立派生train删除以下三条，不翻转标签、不补造替代负例、不改变val/test字节：

| issue | 删除函数 | 原E族 |
|---|---|---|
| django__django-12983 | django/template/defaultfilters.py::slugify@212 | e_anchor |
| django__django-14238 | django/db/models/base.py::ModelBase.__new__@74 | e_log |
| scikit-learn__scikit-learn-14983 | sklearn/model_selection/tests/test_split.py::test_cross_validator_with_default_params@130 | e_bm25 |

{derived_text}

| 数据 | 正例 | 负例 | E并集 | train行 | val行 | test行 |
|---|---:|---:|---:|---:|---:|---:|
| 原v3冻结版本 | 1,542 | 3,084 | 3,000 | 3,924 | 363 | 339 |
| A授权派生计数 | 1,542 | 3,081 | 2,997 | 3,921 | 363 | 339 |

E从3,000减为2,997是用户要求删除三个E训练错样的直接结果，作为精确三条的专项授权记录，不泛化为E数量门豁免。底座为Qwen3-Reranker-0.6B与Qwen2.5-0.5B-Instruct，同数据、LoRA rank16、lr5e-5、3 epoch、原批量与截断配置；只看train/val。train accuracy必须由eval模式真实预测计算，不能用训练loss代替。

原(a)/(b)/(c)是历史操作规则。最新用户裁定明确将 reranker train99.41%−val75.48%=23.93pp 判为过拟合，取消原(b)的val<0.70窄限制。先取原3轮val accuracy峰值；峰值为epoch3，与原best相同，早停选权重不能再提高现有成绩。随后同数据独立重训一次rank8＋dropout0.1，其余配置保持，alpha32不变（alpha/r从2变4，作为同时变化披露）。赛马以处方后的reranker与原instruct结算，仍要求val accuracy≥0.80、AUC≥0.85，再按E剔除率与原2pp规则决胜。处方后val仍<0.80即触发Verified与B双证据合并扩挖，不再等待train<0.70。探索性阶段不开test。[处方独立冻结协议](../../results/v5_pruner/A_regularized_execution_contract.json)保留原A协议不变。

{result_links}

| 底座 | 结果阶段 | train accuracy | val accuracy | val AUC | val E正确剔除率 | val混合集剔除precision |
|---|---|---:|---:|---:|---:|---:|
{model_table}

阶段val来自已完成epoch的真实预测，尚不代表双底座赛马最终结论；完整A结果才用同一best checkpoint的train与val判读。混合集剔除precision为TN/(TN+FN)，E正确剔除率为TN/(TN+FP)。表中无test或定位准确率。

![真实验证曲线](figures/A_validation_learning_curves.png)

图中点线为accuracy80%与E剔除85%参考线；gold曲线为灰区之前的0.5二分类召回，三项指标分别解释。处方曲线只包含已完成轮次，尚未完成的轮次不补点；[作图数据与SHA](figures/A_validation_learning_curves_sources.json)。

上表原rank16 reranker 标记 **pre-regularization**，不再按旧report中的intermediate判读执行；处方训练成绩单独落盘，原预测和checkpoint不覆盖。

{prescription_result_text}

### gold 保留与分层口径

{routing_text}

这里的p始终为P(相关)，不是对任意verdict的置信度。默认low=0.6会直剪P(相关)接近0.6的候选，不能称为90%置信“不相关”。val温度校准不改变0.5二分类阈值下的判决；它校正概率尺度，安全分层还需另选阈值，不能把校准当作提高分类accuracy。

### B线：逐题base commit失败测试函数覆盖

对固定Lite300按各自FAIL_TO_PASS元信息执行，在隔离源码与环境中记录真实函数执行覆盖。每题结果永久缓存，成功、失败、环境／collection问题、测试未真正失败、覆盖不完整分别标记；不反复重跑已完成且指纹一致的结果。先核对跨项目金丝雀，再进行有界CPU并发的持久执行。

新负例资格为**原v3静态保守过滤合格，且不在该题经验证的失败测试函数覆盖集**。跑不通或覆盖不合格的题保持纯静态资格，逐行显式标记，不能混称为运行时证实“干净”。测试执行覆盖包含设置与辅助代码，执行过不等于致因；未覆盖也不能证明无关。覆盖过滤版保留这些证据边界。

完成后生成独立B数据版本、重新抽取30条train E审阅、同配置重训。对照表应并排给出A/B的train与val accuracy、AUC、E正确剔除率与混合集剔除precision，另在两版共同val函数pair上对照，避免将样本组成变化误称模型单独改善。A结果先落盘先报告，不等待B。

{b_data_text}

B仅进行原Lite300的独立覆盖过滤对照，尚非Verified融合扩挖。实际配置按底座匹配A：reranker rank8/dropout0.1/alpha32与val accuracy峰值，instruct rank16/dropout0/alpha32与原E-best；其余参数相同。B数据中的实际val共363对，与A有345个输入和标签相同的pair，最终分别报全val和共同pair，不能按行号或模型配置不一致来声称纯数据改善。

| B底座 | 当前真实阶段 | train accuracy | val accuracy | val AUC | E正确剔除率 | 0.5二分类gold召回 | 混合集剔除precision |
|---|---|---:|---:|---:|---:|---:|---:|
{b_model_table}

完整val与共同345个输入、标签相同pair的同底座对照见[A/B噪声披露与覆盖过滤对照](实验报告_v5_A-B_噪声披露与覆盖过滤对照.md)。该对照采用处方A reranker与B reranker相同rank8/dropout0.1，原A instruct与B instruct相同rank16/dropout0；采用真实保存概率重算，并按issue簇重采样区间。共同val改善仍是exploratory观测，不能据此证明噪声过滤的因果收益或端到端定位提升。

Verified扩挖与B融合采用2026-10-14用户授权的新权威规则：官方500题减Lite交集93题，407题逐题在真实base commit上提取patch改动行＋AST函数金标，issue全文忽略大小写包含任一金标限定名或def简单名者可挖矿；没有名称命中者保留OOD。实际保留221题，可挖矿186题；221题中13题无函数金标，未来函数评测标NA、分母208。旧文件名verified231_manifest.json保留，但数量允许变化。历史231池没有原脚本，不能声称恢复它，也不能编造差10题的定量成因。[最新用户裁定与执行](Verified231权威清单重生成_用户裁定与执行.md)、[权威逐题清单](../../results/v5_pruner/verified_regenerated_ood/verified231_manifest.json)。

官方Verified完整500条元数据按固定revision下载，93条Lite共享题的repo/base/issue/patch/test_patch/FAIL_TO_PASS等字段逐项一致。全部407题已完成独立真实Git源码／patch／AST核证，529个Python文件的1058份before/after档案可追溯。186题的A/C/D/e_bm25/e_anchor静态挖矿与独立CPU两worker运行时覆盖均已实际启动，旧Lite切分、test封存及原A/B数据不变。运行失败／selector不支持／函数未进入的题按证据回退纯静态并单列；coverage缺失不能证明因果无关，修改过的测试源码候选也不能靠缺覆盖升级。融合数据需另行重审和授权训练，当前未产生扩后模型指标或正式OOD成绩。[覆盖金丝雀、正式授权与边界](Verified运行时覆盖_金丝雀与执行边界.md)。

## 局限性与历史实证材料

原v3负例的E占97.28%，D-only84条占2.72%；带D来源的228条含与E重叠，不能全部计为D-only。原primary三族为e_log161、e_bm25 1,390、e_anchor 1,449，来自历史Qwen=True判决、文本相似和名称锚点，具有选择偏差，不能代表真实函数候选总体。原test的e_log只有9条，这个计数来自既有封存统计，未解码test样本或评测模型。

模型输入仅issue前2,000字符和候选函数前1,500字符。完整调用图中C正例的显式关系在候选输入中的可见性不同：train521/1,053、val71/87缺乏完整显式调用证据，可能位于未提供的gold源码或截断后。这是信息与分布限制，不直接证明标签错误。

前两版八例结构化档案见[E类漏过滤专项归档](E类漏过滤案例_v1-v2_专项归档.md)、[JSON](../../results/v5_pruner/e_filter_missed_cases_v1_v2.json)、[CSV](../../results/v5_pruner/e_filter_missed_cases_v1_v2.csv)。其中hist与ufuncify只证明源码可能祖先路径，不能说原issue已实际执行这些候选；八例都不新增金标或C正例。v3三条完整反例另见[反例档案](../../results/v5_pruner/data_v3/review_final_counterexamples.json)。

## 不变项与资源

Decision-1对线取消；不调用新付费API；不重跑300题Qwen基线。历史CoSIL/off的111/293=37.88%仅作既有定位基线，没有新模型定位准确率时不往结果矩阵写预测列。不动vLLM、CSRSE或他人进程；A/B训练仅在核实GPU2自然空闲后按单卡执行，GPU3保留给其他任务；B覆盖采集和新Verified覆盖采集使用有界CPU。GPU进程检查覆盖C+G，防止漏计仿真占用。

- [v3最终历史失败签注与局限性](数据重构_v3与质量门.md)
- [方案偏差与最新执行决定](方案偏差与执行决定.md)
- [执行进度](执行进度.md)
- [B线覆盖记录](运行时覆盖_B线.md)
- [B新30条逐条审阅与签注](B运行覆盖过滤_30条逐条审阅与签注.md)
- [Verified官方输入与历史231池预检归档](Verified官方输入与历史231池_补充预检.md)
- [最新权威221题OOD清单裁定](Verified231权威清单重生成_用户裁定与执行.md)
- [300题历史数据审计](实验报告_v5_逐题数据审计.md)

所有新模型结论以已落盘真实预测和训练记录为准；未完成的阶段不能据准备代码、旧基线或CPU合成检查补写成绩。
'''
    OUT.write_text(text, encoding="utf-8")
    print(json.dumps({"report": str(OUT), "current_route": contract["status"],
                      "source_v3_review_errors": signoff["known_label_errors"],
                      "derived_data_present": derived is not None, "test_rows_decoded": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
