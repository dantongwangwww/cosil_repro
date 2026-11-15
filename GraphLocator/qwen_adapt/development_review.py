"""Fixed-ID development comparison. Gate proposal is reviewed before full run."""
import json
from datetime import datetime

from qwen_adapt.runner import ROOT,WORK,version,atomic
from qwen_adapt.evaluate import COSIL,evaluate_folder,common_metrics,native_metrics
from qwen_adapt.diagnostics import analyze
from qwen_adapt.reports import baseline_projects,rate,metric_line,paired_interval


def main():
    frozen=version();base=WORK/'development'/frozen['hash']
    completion=json.loads((base/'completion.json').read_text())
    assert completion['completed']==completion['total']==90
    inputs=json.loads((WORK/'inputs_manifest.json').read_text());ids=inputs['development']
    gold=json.loads((COSIL/'ground_truth_300.json').read_text())
    native_gold=json.loads((ROOT/'datasets/swe_bench_lite_gt_entities_3levels.json').read_text())
    old=baseline_projects()['GraphLocator/Qwen']
    historical=common_metrics(old['records'],gold,ids)
    baseline_native=json.loads((ROOT/'results/qwen_300/full/loc_results.json').read_text())
    scores={'B0':dict(common={k:v for k,v in historical.items() if k!='details'},native=native_metrics(baseline_native,native_gold,ids))}
    details={'B0':historical['details']};pipelines={};bad=0
    for variant in ('B1','B2','B3'):
        m,d,a=evaluate_folder(base/variant,ids)
        assert m['issues']==30 and m['missing']==0
        scores[variant]=m;details[variant]=d
        pipelines[variant],_=analyze(base/variant,ids,gold,d,a)
        for iid in ids:
            p=base/variant/'cases'/f'{iid}.json'
            if not p.exists():continue
            case=json.loads(p.read_text());assert case['version_hash']==frozen['hash']
            if variant=='B3':
                events=[json.loads(line) for line in (base/variant/'events'/f'{iid}.jsonl').read_text().splitlines()]
                shown={n['node_id'] for e in events if e['event']=='causal_context' for n in e['nodes']}
                adopted={n['node_id'] for f in case['causal_graph']['nodes'] for n in f['code_elements']}
                bad+=len(adopted-shown)
    eligible=scores['B3']['failed']==0 and scores['B3']['audit']['functions_without_source_receipt']==0 and bad==0
    comparisons={v:paired_interval(details['B0'],details[v],ids) for v in ('B1','B2','B3')}
    value=dict(version_hash=frozen['hash'],created_at=datetime.now().astimezone().isoformat(),
        proposed_engineering_gate=eligible,approved_full=False,adopted_unshown_code_ids=bad,
        scores=scores,pipelines=pipelines,paired=comparisons,
        semantic_limitations='JSON与来源可靠不证明原因正确。金丝雀已发现错误迁移关联、重复原因和过多候选，均保留；开发30题成绩不能单独证明稳定提升。',
        full_selection_pending='根代理审查本记录后决定是否保持B3。禁止根据270题成绩调整方案。')
    atomic(base/'review.json',value)
    text='# GraphLocator Qwen适配v2：固定30题开发对照\n\n'
    text+='各条件使用同一组预先固定issue，B0为历史冻结预测；B1/B2/B3均完整重新运行。B1基础恢复，B2增加ID相关性输出与可读源码，B3增加中性因果提示与稳定ID JSON图。\n\n'
    text+='B1/B2保留旧CausalAgent的整批初始/邻居输入与Mermaid解析；B3同时引入因果源码分批、来源绑定及更新预算。B1/B2的上下文超限也保留计0。因此B2→B3是因果适配组合，不能把全部变化归因于输出JSON格式，亦非只改变一个变量的消融。\n\n'
    text+='| 条件 | 适用题数 | Precision | Recall | 严格宏平均F1 | SL |\n|---|---:|---:|---:|---:|---:|\n'
    for v,m in scores.items():text+=metric_line(v,m['common']['strict'])
    text+='\n| 条件 | 完成/失败 | 空种子 | 源码送达缺口 | 调用 | 相关性unknown | 因果校验错误项 |\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
    for v in ('B1','B2','B3'):
        m=scores[v];a=m['audit'];text+=f"| {v} | {m['completed']}/{m['failed']} | {a['zero_seeds']} | {a['functions_without_source_receipt']} | {a['calls']} | {a['unknown_relevance']} | {a['causal_validation_errors']} |\n"
    text+='\n逐题评分、阶段覆盖和bootstrap对照存入同版本development/review.json。本次只提出工程准入建议，正式冻结决定另记full_gate.json；未启动270题验证时不声称完成全量或效果稳定。\n\n'
    text+='| issue | B0 F1 | B1 F1 | B2 F1 | B3 F1 |\n|---|---:|---:|---:|---:|\n'
    for iid in ids:text+='| '+iid+' | '+' | '.join(rate(details[v][iid]['strict']['f1']) if details[v][iid]['strict'] else 'NA' for v in ('B0','B1','B2','B3'))+' |\n'
    (ROOT/'docs/qwen-300/开发集对照与冻结审查_适配v2.md').write_text(text)
    print(json.dumps({'eligible':eligible,'scores':{v:m['common']['strict'] for v,m in scores.items()}},ensure_ascii=False))


if __name__=='__main__':main()
