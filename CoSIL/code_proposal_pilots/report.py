"""One-page proposal-pilot overview from audited artifacts; no inference."""
from collections import defaultdict
import csv

from .common import ROOT, OUT, DOCS, read, write, textfile, pct, now, protected


def main():
    c=read(OUT/'coverage/summary.json');p=read(OUT/'ppr/summary.json')
    a=read(OUT/'final_cpu_audit.json');s=read(OUT/'structural_universe_independent_audit.json')
    assert a['protected_inputs_unchanged'] and s['cases']==300
    assert protected()==read(OUT/'frozen_protocol.json')['protected']
    with (OUT/'ppr/per_issue.csv').open() as f:rows=list(csv.DictReader(f))
    strata=defaultdict(list)
    for r in rows:strata[r['anchor']].append(r)
    stat={}
    for name,rs in strata.items():
        stat[name]={'cases':len(rs),'seeded':sum(int(r['seed_functions'])>0 for r in rs),
                    'current_top5':sum(float(r['current_any@5']) for r in rs)/len(rs),
                    'ppr_top5':sum(float(r['ppr_any@5']) for r in rs)/len(rs)}
    write(OUT/'ppr/posthoc_anchor_strata.json',{'time':now(),'scope':'descriptive posthoc strata; no parameter selection','strata':stat})
    off=c['summary']['off']['primary'];v=off['top1_validator'];agg=p['aggregate_all300']
    approved=(OUT/'anchor/user_approval.json').exists()
    anchor_status='提示词与既有真值口径已批准，尚未启动推理' if approved else '按用户要求提示词先报审，尚未启动'
    lines=['# 开题预研三小实验：阶段总览', '',f'截至{now()}：预研三、二完成；预研一{anchor_status}。T3第二轮已先行完成，本阶段零GPU、零新增测试执行、未改vLLM/CSRSE、训练数据、历史预测或对照矩阵；pruner test封存。', '',
           '| 预研 | 实测结果 | 预设判定与下一步 |','|---|---|---|',
           f'| 三：失败覆盖验证 | 覆盖可用{c["available_without_gold_condition"]}/300题，其中函数可评分{c["function_scorable_available"]}题；off命中gold预测覆盖{pct(off["gold_hit"]["micro_coverage"])}，未命中组{pct(off["non_gold_prediction"]["micro_coverage"])}；Top-1验证precision={pct(v["precision"])}, recall={pct(v["recall"])} | '+('通过' if c['preregistered_success_passed'] else '未通过')+'；下一步拟把覆盖作为可达性特征，结合其他证据验证因果相关性 |',
           f'| 二：PPR与MMR | 全300题，种子可映射{p["seeded_cases"]}题；PPR@5={pct(agg["ppr"]["any@5"])}，MMR@5={pct(agg["mmr"]["any@5"])} | PPR'+('通过' if p['ppr_success_passed'] else '未通过')+'；MMR'+('通过' if p['mmr_success_passed'] else '未通过')+'；下一步拟检查种子缺失、歧义与静态连通性，另立实验而不在本轮调参 |',
           f'| 一：issue锚点三分类 | {anchor_status}；混淆矩阵、宏F1、无名召回均尚未测 | 未执行，不能记为通过或失败；择空闲GPU窗口运行 |','',
           '| 文件菜单（至少一个gold文件命中） | @5 | @10 | @20 |','|---|---|---|---|']
    for name,key in [('现状原候选','current'),('现状同文件宇宙','current_same_universe'),('PPR','ppr'),('PPR＋MMR','mmr'),('随机精确期望','random_expected')]:
        row=agg[key];lines.append(f'| {name} | {pct(row["any@5"])} | {pct(row["any@10"])} | {pct(row["any@20"])} |')
    delta=p['mmr_minus_ppr_top5'];ci=p['ppr_minus_current_top5']
    lines += ['',f'MMR相对PPR Top-5变化{delta["difference"]*100:+.2f}pp；PPR相对现状{ci["difference"]*100:+.2f}pp，配对bootstrap95%CI [{ci["lower"]*100:+.2f}, {ci["upper"]*100:+.2f}]pp。原候选只有5个，@10/20为候选耗尽；当前归档金标每题一个文件，故本轮any-hit、all-hit与文件召回数值相同。', '',
              '预设探索线先于结果冻结：预研三off两组覆盖差≥10pp且Top-1 precision/recall均≥0.80；PPR较现状@5≥+5pp且@20不下降；MMR较PPR@5≥+2pp。它们是本次探索筛查线，不替代v6资格门。', '',
              '覆盖主分析不以gold已覆盖为条件；旧B线133题子集单列敏感性结果，避免选择偏差。无函数真值的4题为NA。off未覆盖的5个gold命中预测中3个是补丁新增函数，base上不能执行；其余2个未另跑测试追查。', '',
              f'PPR按固定无向直接调用图、damping0.85、函数分求和与MMR lambda0.7运行。独立路径遍历核对300题文件宇宙，gold文件不在宇宙的题数为{s["missing_gold_cases"]}；不填零分菜单、不用gold选种子。既有锚点JSON只含类别，种子按原标识符规则确定性重建，不能冒称已找到原始种子清单。', '',
              '预研一口径差异：既有v3c标签gold_named82 / other_named199 / no_explicit_name19，多数类accuracy为66.33%；用户提供的76%作为待核参考保留。机械“点名gold”与真正根因命名、other_named与真实症状命名均不完全等价，提示词审阅问题已明确披露。未改真值。', '',
              '执行中修正两处脚本问题并保存失效初稿：覆盖初算将无函数真值题纳入负组；PPR初次遍历误认同名目录。最终统计只认修正后目录，参数与成功线未变。代码/文档先备份后新增，原始结果不上传GitHub。', '',
              '- [预研三报告](预研三_失败路径覆盖与Top5定位验证.md) / [逐题统计补充](预研三_逐题统计与核验补充.md)',
              '- [预研二一页报告](预研二_PPR全300题与MMR文件召回.md)',
              '- [待审提示词与冻结协议](执行协议与预研一提示词_2026-10-17.md) / [代码改动与复现说明](代码改动与复现说明_2026-10-17.md)',
              '- [CPU核验收据](../../results/proposal_pilots/20261017/final_cpu_audit.json) / [独立文件宇宙核验](../../results/proposal_pilots/20261017/structural_universe_independent_audit.json) / [描述性锚点分层](../../results/proposal_pilots/20261017/ppr/posthoc_anchor_strata.json)','']
    textfile(DOCS/'开题预研三小实验_阶段总览.md','\n'.join(lines))
    print('Wrote proposal-pilot stage overview; anchor inference still pending explicit prompt review')


if __name__=='__main__':main()
