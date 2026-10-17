"""Every preregistered arm, all300 OOF scores, confidence intervals and audit."""
from collections import defaultdict
import math
import numpy as np

from .common import *


def interval(a,b):
    d=np.array(a)-np.array(b);rng=np.random.default_rng(SEED)
    boot=d[rng.integers(0,len(d),size=(4000,len(d)))].mean(axis=1)
    return {'delta':float(d.mean()),'lower':float(np.quantile(boot,.025)),
            'upper':float(np.quantile(boot,.975)),'bootstrap_replicates':4000}


def random_expectation(n,g,k):
    k=min(k,n)
    return 1-math.comb(n-g,k)/math.comb(n,k) if n-g>=k else 1.


def random_mrr(n,g):
    probability=g/n;total=0.
    for r in range(1,n-g+2):
        total+=probability/r
        if r<n-g+1:probability*=((n-r-g+1)/(n-r))
    return total


def main():
    frozen=freeze();manifest=read(OUT/'extraction_manifest.json');folds=read(OUT/'grouped_fivefold_manifest.json')
    ids=sorted(manifest['case_meta_sha256']);aggregate=defaultdict(lambda:defaultdict(list))
    rows=[];cosil=defaultdict(list);expected=defaultdict(list);allrankchecks=0;mmr_same={}
    allcasehashes={};rank10_by_method={m:[] for m in METHODS}
    for iid in ids:
        d=case_dir(iid);m=read(d/'meta.json');features=np.load(d/'features.npz',allow_pickle=False);positive=features['y'].astype(bool)
        assert m['seed_function_ids']==read(m['existing_seed_json'])['seed_function_ids']
        assert sha(m['existing_seed_json'])==m['existing_seed_json_sha256']
        n=len(m['files']);assert positive.sum()==len(m['gold_files'])
        rankings={}
        for f in ['retrieval_rankings.npz','LTR_rankings.npz']:
            data=np.load(d/f,allow_pickle=False)
            for method in data.files:
                assert method not in rankings;rankings[method]=data[method]
        assert set(rankings)==set(METHODS)
        for method in METHODS:
            r=rankings[method];assert np.array_equal(np.sort(r),np.arange(n)),(iid,method,'not a full permutation')
            allrankchecks+=1;measure=scores(r,positive)
            rows.append({'instance_id':iid,'repo':m['repo'],'method':method,**measure})
            for key,value in measure.items():
                if key!='first_gold_rank':aggregate[method][key].append(value)
            rank10_by_method[method].append(measure['hit@10'])
        original=m['original_CoSIL_candidates'];g=set(m['gold_files'])
        for k in [1,5,10,20]:cosil[f'hit@{k}'].append(float(bool(set(original[:k])&g)))
        for k in [1,5,10,20]:expected[f'hit@{k}'].append(random_expectation(n,int(positive.sum()),k))
        expected['MRR'].append(random_mrr(n,int(positive.sum())))
        allcasehashes[iid]={f:sha(d/f) for f in ['features.npz','retrieval_rankings.npz','LTR_rankings.npz','LTR_OOF_probabilities.npz','meta.json']}
    results={m:{key:float(np.mean(vals)) for key,vals in measures.items()} for m,measures in aggregate.items()}
    nonrandom=[m for m in METHODS if m!='random'];single=['BM25','PPR_max','PPR_sum']+BASE_MMR
    winner=max(nonrandom,key=lambda m:results[m]['hit@10'])
    bestsingle=max(single,key=lambda m:results[m]['hit@10'])
    bestLTR=max(LTR,key=lambda m:results[m]['hit@10'])
    advantage=results[winner]['hit@10']-results['BM25']['hit@10']
    spread=max(results[m]['hit@10'] for m in nonrandom)-min(results[m]['hit@10'] for m in nonrandom)
    ltr_ok={m:results[m]['hit@10']>=results[bestsingle]['hit@10']-1e-12 for m in LTR}
    intervals={'winner_minus_BM25':interval(rank10_by_method[winner],rank10_by_method['BM25']),
               'best_LTR_minus_best_single':interval(rank10_by_method[bestLTR],rank10_by_method[bestsingle])}
    outcome={'strongest_arm_plus10pp_passed':advantage>.10+1e-12,
             'LTR_ge_best_single_by_arm':ltr_ok,'any_LTR_ge_best_single':any(ltr_ok.values()),
             'nonrandom_spread_below3pp_ranking_not_bottleneck':spread<.03-1e-12}
    summary={'time':now(),'cases':300,'methods':METHODS,'candidate_rows':manifest['total_candidate_rows'],
             'seeded_cases':manifest['seeded_cases'],'metrics':results,'CoSIL_reference':{k:float(np.mean(v)) for k,v in cosil.items()},
             'random_exact_expectation':{k:float(np.mean(v)) for k,v in expected.items()},
             'winner_by_OOF_hit10':winner,'best_single':bestsingle,'best_LTR':bestLTR,
             'winner_minus_BM25_pp':advantage*100,'nonrandom_hit10_spread_pp':spread*100,
             'all_arms_including_random_hit10_spread_pp':(max(r['hit@10'] for r in results.values())-min(r['hit@10'] for r in results.values()))*100,
             'outcomes':outcome,'paired_intervals':intervals,'CV_manifest_sha256':sha(OUT/'grouped_fivefold_manifest.json'),
             'full_permutation_checks':allrankchecks,'case_artifact_sha256':allcasehashes,
             'GPU_used':False,'pruner_test_opened':False,'extra_hyperparameter_search':False,
             'postselection_note':'Winner is exploratory maximum across preregistered arms; CI is not familywise or independently confirmed.'}
    assert allrankchecks==6000 and folds['all300_exactly_once_OOF']
    assert protected()==frozen['protected']
    write(OUT/'summary.json',summary);csvfile(OUT/'per_issue_metrics.csv',rows)
    lines=['# 文件级排序擂台v2：全300题对比','',f'完成于{now()}。全部Python文件（含测试），20个预注册条件全部报告。LTR为按repo分组五折OOF，训练/预测仓零交集；纯CPU、pruner test封存。','',
           '| 条件 | @1 | @5 | @10 | @20 | MRR |','|---|---|---|---|---|---|']
    def percent(x):return f'{x:.2%}'
    for method in METHODS:
        r=results[method];lines.append('| '+method+' | '+' | '.join(percent(r[f'hit@{k}']) for k in [1,5,10,20])+f' | {r["MRR"]:.4f} |')
    r=summary['random_exact_expectation'];lines.append('| 随机精确期望 | '+' | '.join(percent(r[f'hit@{k}']) for k in [1,5,10,20])+f' | {r["MRR"]:.4f} |')
    r=summary['CoSIL_reference'];lines.append('| CoSIL既有候选覆盖（最多5项） | '+' | '.join(percent(r[f'hit@{k}']) for k in [1,5,10,20])+' | 短列表不比较 |')
    ci=intervals['winner_minus_BM25']
    lines += ['',f'主成功线①：最强臂{winner}的@10较BM25 {advantage*100:+.2f}pp；要求>10pp，'+('**通过**。' if outcome['strongest_arm_plus10pp_passed'] else '**未通过，下一步拟：先依据逐题召回/排序失败类型决定是否值得改菜单，不追加lambda或特征搜索。**'),
              f'差值按题bootstrap95%CI [{ci["lower"]*100:+.2f}, {ci["upper"]*100:+.2f}]pp；此处赢家为全部预注册臂中的探索性最大值，区间未作多重比较校正，不能当独立确认集。',
              f'成功线②：单方法最优为{bestsingle}；LTR逐臂达标={ltr_ok}。'+('至少一版通过。' if any(ltr_ok.values()) else '**未通过，下一步拟：审查跨仓泛化与8项固定特征的可迁移性，不用测试折选新配置。**'),
              f'成功线③：非随机实质排序臂@10极差{spread*100:.2f}pp。'+('小于3pp，按预设记“排序非瓶颈”。' if outcome['nonrandom_spread_below3pp_ranking_not_bottleneck'] else '未满足<3pp，不能据此判“排序非瓶颈”，也不能反推排序必然是唯一瓶颈。'),'',
              f'候选{manifest["total_candidate_rows"]:,}个issue/file对子；沿用v1种子JSON，{manifest["seeded_cases"]}/300题有种子。PPR-max主/求和对照；MMR为内容TF-IDF余弦，lambda0.3/0.5/0.7，完整候选选前20、余项按基础排名顺延，MRR按此完整排名算，MRR@20另在JSON。无种子PPR全零按路径同分顺序，不隐藏。',
              'LR/GBDT的含/不含PPR消融与组合均固定配置；缩放器仅fit训练折，未用封存pruner_test。公开Lite文件gold仅按授权用于本次LTR训练折监督与OOF评分。CoSIL只有原候选覆盖，@10/20不补排名。v1生产文件结果与本版候选全集、聚合、MMR均不同，不把跨版本差值冒称单因素效应。','',
              '[逐题指标](../../results/proposal_pilots/20261017/file_ranking_v2/per_issue_metrics.csv) / [逐题全排名NPZ及Top20 JSON](../../results/proposal_pilots/20261017/file_ranking_v2/cases) / [分组五折](../../results/proposal_pilots/20261017/file_ranking_v2/grouped_fivefold_manifest.json) / [统计与核验SHA](../../results/proposal_pilots/20261017/file_ranking_v2/summary.json) / [冻结协议](文件排序擂台_v2_预注册协议.md)','']
    textfile(DOCS/'文件排序擂台_v2_一页对比报告.md','\n'.join(lines))
    write(OUT/'final_audit.json',{'time':now(),'all20_conditions_present':True,'all6000_full_rank_permutations_verified':True,
              'no_repo_crossfold_leakage':all(not set(f['train_repos'])&set(f['test_repos']) for f in folds['folds']),
              'all300_once_OOF':True,'all_existing_seed_JSON_preserved':True,'frozen_protected_inputs_unchanged':protected()==frozen['protected'],
              'original_train_val_test_and_matrix_modified':False,'GPU_used':False,
              'no_parameter_search_beyond_preregistered':True,'summary_sha256':sha(OUT/'summary.json')})
    status('complete',winner=winner,outcomes=outcome)
