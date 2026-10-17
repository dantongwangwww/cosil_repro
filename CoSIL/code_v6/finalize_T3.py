"""After all first-round processes end, publish the gold-first comparison and stop."""
import shutil,time
from code_v6.common import ROOT,OUT,DOCS,read,rows,write,status,sha,now,test_stats,verify_files
from code_v6.train_T3 import RACE,SPECS,DATA

def rank_summary(key,summary):
    a=summary['selected']['assessment'];risk=a['risk']
    u=risk['gold_direct_reject']['upper'];lo=risk['mixed_rejection_precision']['lower']
    order=['anchor06B','reranker4B','swerank7B']
    return (u if u is not None else float('inf'),-(lo if lo is not None else -1),-a['uncalibrated']['overall']['accuracy'],order.index(key))

def run():
    while not (RACE/'scheduler_complete.json').exists():time.sleep(45)
    verify_files(read(DATA/'freeze_manifest.json')['artifacts_sha256']);verify_files(read(RACE/'protocol.json')['code_sha256'])
    assert test_stats()==read(RACE/'protocol.json')['sealed_test_stat_only']
    for key in SPECS:
        folder=RACE/key
        if not (folder/'training_summary.json').exists() and (folder/'process_exit.json').exists():
            exit_record=read(folder/'process_exit.json')
            status(folder/'status.json',{'time':now(),'stage':'failed','reason':'Process ended without complete training summary',
                                       'exit_code':exit_record['exit_code'],'test_opened':False})
    snapshot=RACE/'first_report_snapshot';snapshot.mkdir(exist_ok=False)
    for name in ['实验报告_v6_T3_首轮底座赛马.md','实验报告_v6_T3_逐题验证分析.md']:
        shutil.copyfile(DOCS/name,snapshot/name)
    summaries={k:read(RACE/k/'training_summary.json') for k in SPECS if (RACE/k/'training_summary.json').exists()}
    all_complete=len(summaries)==len(SPECS)
    qualified={k:r for k,r in summaries.items() if r['selected']['qualified']}
    winner=min(qualified,key=lambda k:rank_summary(k,qualified[k])) if qualified and all_complete else None
    diagnostic=min(summaries,key=lambda k:rank_summary(k,summaries[k])) if summaries else None
    decision={'time':now(),'all_three_bases_completed':all_complete,'qualified_bases':list(qualified),
        'first_round_risk_qualified_recommendation':winner,'diagnostic_candidate_only':diagnostic if winner is None else None,
        'rule':'same frozen gold-first order across bases; exact ties favor smaller base; no train/test selection',
        'recommendation_is_not_pipeline_deployment':True,'awaiting_user_interpretation':True,'T4_started':False,'test_opened':False}
    write(RACE/'race_recommendation.json',decision)
    from code_v6.report_T3 import run as report
    from code_v6.report_progress import run as progress
    report();progress()
    main=DOCS/'实验报告_v6_T3_首轮底座赛马.md'
    extra=['','## 首轮判读交接','']
    if winner:extra.append(f'按冻结风险门及gold优先顺序，首轮建议候选为`{winner}`；这只是离线候选，尚未部署或证明端到端非劣效。')
    elif all_complete:extra.append('三底座已完整跑完，但没有可自动推荐的风险合格赢家；仅保留诊断候选，不能绕过资格门接管管线。')
    else:extra.append('首轮存在未完成/失败底座，不能宣布完整赛马赢家；已完成底座成绩保留，不用缺失填0。')
    extra += ['','| 底座 | gold风险/precision门的具体状态 |','|---|---|']
    for key,r in summaries.items():
        risk=r['selected']['assessment']['risk'];reasons=[]
        for metric in ['gold_direct_reject','mixed_rejection_precision']:
            x=risk[metric]
            if x['undefined_replicates']:reasons.append(metric+'分母不足')
            if x['degenerate']:reasons.append(metric+'经验区间退化，证据不足以自动认证')
        if risk['gold_direct_reject']['upper'] is not None and risk['gold_direct_reject']['upper']>.15:reasons.append('gold风险CI上界>15%')
        if risk['mixed_rejection_precision']['lower'] is not None and risk['mixed_rejection_precision']['lower']<.85:reasons.append('混合precision CI下界<85%')
        extra.append('| '+key+' | '+('；'.join(reasons) if reasons else '两个风险门通过')+' |')
    extra += ['','| 底座 | train gold直留/直剪/灰区 | train E正确直剪率 | train混合直剪precision |','|---|---|---:|---:|']
    for key,r in summaries.items():
        t=r['train_assessments'][str(r['selected']['epoch'])];g=t['gold_route_fractions'];m=t['hybrid_route_point_metrics']
        f=lambda v:'NA' if v is None else f'{v:.2%}'
        extra.append(f'| {key} | {f(g["retain"])}/{f(g["reject"])}/{f(g["gray"])} | {f(m["E_correct_reject"])} | {f(m["mixed_rejection_precision"])} |')
    extra += ['','train路由使用对应epoch的val拟合温度，没有在train上另拟合温度。按执行序列，现在停在“**T3 首轮赛马结果判读**”，不自动第二轮、不打开test、不执行T4。']
    with main.open('a') as f:f.write('\n'.join(extra)+'\n')
    provenance=read(DATA/'provenance.json');verify_files(provenance['historical_sha256'])
    write(RACE/'final_delivery_receipt.json',{'time':now(),'race_recommendation_sha256':sha(RACE/'race_recommendation.json'),
        'T2_freeze_sha256':sha(DATA/'freeze_manifest.json'),'T3_protocol_sha256':sha(RACE/'protocol.json'),
        'reports_sha256':{str(DOCS/n):sha(DOCS/n) for n in ['实验报告_v6_T3_首轮底座赛马.md','实验报告_v6_T3_逐题验证分析.md']},
        'live_overview_and_progress_not_frozen':True,
        'finalizer_code_sha256':sha(ROOT/'code_v6/finalize_T3.py'),'test_stat_only':test_stats(),'test_contents_opened':False,
        'historical_files_unchanged':True,'further_execution_requires_user_first_round_interpretation':True})

if __name__=='__main__':run()
