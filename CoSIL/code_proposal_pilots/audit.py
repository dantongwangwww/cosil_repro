"""Independent arithmetic/read-only checks and per-issue coverage rate table."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from .common import ROOT, OUT, DOCS, read, write, csvfile, textfile, protected, inputs, ratio, sha, now, targets, leaf


def wilson(n, d):
    if not d:
        return None
    z = 1.959963984540054
    p = n/d; a = 1+z*z/d
    center = (p+z*z/(2*d))/a
    half = z*math.sqrt(p*(1-p)/d+z*z/(4*d*d))/a
    return [center-half, center+half]


def main():
    frozen = read(OUT/'frozen_protocol.json')
    assert protected() == frozen['protected']
    gold, metrics, baseline, _, _ = inputs()
    historical_counts={}
    for arm in ['off','on','shuffled']:
        hit=eligible=0
        for c in metrics['cases'][arm]:
            gt=targets(gold[c['instance_id']])
            if not gt:continue
            eligible+=1
            actual=any(tuple(p) in gt for p in c['predictions'][:5])
            assert actual==c['function_top5']
            hit+=actual
        historical_counts[arm]={'function_top5_hits':hit,'function_scorable_cases':eligible}
    assert historical_counts['off']=={'function_top5_hits':111,'function_scorable_cases':293}
    availability = {}
    import csv
    with (OUT/'coverage/per_issue_availability.csv').open() as f:
        for r in csv.DictReader(f):availability[r['instance_id']] = r
    pp = read(OUT/'coverage/per_prediction.json')
    misses=[]
    for r in pp:
        if not r['gold_hit'] or r['failed_covered']:continue
        g=gold[r['instance_id']];key=(r['file'],r['name'])
        base={(v['file'],leaf(v['name'])) for v in g['existing_gold_function_regions']}
        new={(s.rsplit('::',1)[0],leaf(s.rsplit('::',1)[1])) for s in g['new_functions']}
        misses.append({**r,'gold_present_in_base':key in base,'gold_new_only':key in new and key not in base})
    write(OUT/'coverage/gold_hit_but_not_covered_audit.json',misses)
    grouped = defaultdict(list)
    for r in pp:grouped[(r['instance_id'],r['arm'])].append(r)
    rows=[]
    for arm in ['off','on','shuffled']:
        for case in metrics['cases'][arm]:
            iid=case['instance_id'];data=grouped[(iid,arm)]
            available=availability[iid]['available']=='True'
            function_scorable=bool(gold[iid]['gold_functions_by_file'])
            counts=Counter()
            for r in data:
                if r['kind']!='function':continue
                group='gold_hit' if r['gold_hit'] else 'non_gold'
                counts[group+'_predictions']+=1
                counts[group+'_failed_covered']+=int(r['failed_covered'])
                counts[group+'_union_covered']+=int(r['union_covered'])
            top=next((r for r in data if r['rank']==1),None)
            row={'instance_id':iid,'arm':arm,'coverage_available':available,
                 'function_truth_available':function_scorable,
                 'anchor':case['anchor'],'B_eligible':availability[iid]['B_eligible'],
                 'original_top5_locations':len(case['predictions'][:5]),
                 'empty_original_output':not bool(case['predictions']),
                 'top1_is_function':bool(case['predictions']) and case['predictions'][0][1]=='function',
                 'top1_gold_hit':top['gold_hit'] if top and top['kind']=='function' else None,
                 'top1_failed_covered':top['failed_covered'] if top and top['kind']=='function' else None}
            for group in ['gold_hit','non_gold']:
                n=counts[group+'_predictions']
                row[group+'_predictions']=n if available and function_scorable else None
                row[group+'_failed_covered']=counts[group+'_failed_covered'] if available and function_scorable else None
                row[group+'_failed_coverage_rate']=ratio(counts[group+'_failed_covered'],n) if available and function_scorable else None
                row[group+'_union_coverage_rate']=ratio(counts[group+'_union_covered'],n) if available and function_scorable else None
            rows.append(row)
    csvfile(OUT/'coverage/per_issue_rates.csv',rows)
    coverage=read(OUT/'coverage/summary.json')
    independent={}
    for arm in ['off','on','shuffled']:
        sub=[r for r in rows if r['arm']==arm and r['coverage_available']]
        valid=[r for r in sub if r['top1_is_function'] and r['top1_gold_hit'] is not None]
        tp=sum(r['top1_gold_hit'] and r['top1_failed_covered'] for r in valid)
        fp=sum(not r['top1_gold_hit'] and r['top1_failed_covered'] for r in valid)
        fn=sum(r['top1_gold_hit'] and not r['top1_failed_covered'] for r in valid)
        tn=sum(not r['top1_gold_hit'] and not r['top1_failed_covered'] for r in valid)
        old=coverage['summary'][arm]['primary']['top1_validator']
        assert [tp,fp,fn,tn]==[old[k] for k in ['TP','FP','FN','TN']]
        independent[arm]={'issues':len(sub),'function_top1':len(valid),
                          'empty_outputs':sum(r['empty_original_output'] for r in sub),
                          'nonfunction_top1':sum(not r['empty_original_output'] and not r['top1_is_function'] for r in sub),
                          'precision_wilson95':wilson(tp,tp+fp),'recall_wilson95':wilson(tp,tp+fn),
                          'covered_name_ambiguous_predictions':sum(r['covered_name_identity_ambiguous'] for r in pp if r['arm']==arm),
                          'top1_FN_issue_ids':[r['instance_id'] for r in valid if r['top1_gold_hit'] and not r['top1_failed_covered']]}
    ppr=read(OUT/'ppr/summary.json')
    assert ppr['master_cases']==300 and len(ppr['artifacts'])==300
    menus={p.stem:read(p) for p in (OUT/'ppr/menus').glob('*.json')}
    assert set(menus)==set(gold)
    universe_audit=read(OUT/'structural_universe_independent_audit.json')
    universe_hashes={r['instance_id']:r['universe_sha256'] for r in universe_audit['rows']}
    assert len(universe_hashes)==300 and set(universe_hashes)==set(gold)
    def tokens(text):
        import re
        calls=re.findall(r'\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(',text)
        ids=[s for s in re.findall(r'`([^`\n]+)`',text) if re.fullmatch(r'\w+(?:\.\w+)*',s.strip())]
        return {s.rsplit('.',1)[-1] for s in calls+ids}
    def match(files,targets):return bool(set(files)&set(targets))
    independently=defaultdict(list)
    mmr_changes=[]
    for iid,m in menus.items():
        uh=hashlib.sha256(json.dumps(m['universe_files'],ensure_ascii=False).encode()).hexdigest()
        assert uh==universe_hashes[iid], 'File universe differs from independent traversal'
        assert m['base_commit']==gold[iid]['base_commit']
        assert m['current']==list(dict.fromkeys(baseline[iid]))
        assert len(set(m['mmr_top20']))==len(m['mmr_top20'])
        assert set(m['mmr_top20']) <= {r['file'] for r in m['file_menu'][:100]}
        assert (not m['seed_function_ids']) == (m['ppr']['status']=='no_seed')
        if not m['seed_function_ids']:assert not m['file_menu']
        paths=[r['file'] for r in m['file_menu']]
        before=paths[:5];after=m['mmr_top20'][:5]
        oldhit=match(before,gold[iid]['gold_files']);newhit=match(after,gold[iid]['gold_files'])
        mmr_changes.append({'instance_id':iid,'ranking_changed':before!=after,
                            'membership_changed':set(before)!=set(after),
                            'ppr_top5_gold_hit':oldhit,'mmr_top5_gold_hit':newhit,
                            'gold_hit_delta':int(newhit)-int(oldhit),
                            'ppr_top5':json.dumps(before,ensure_ascii=False),
                            'mmr_top5':json.dumps(after,ensure_ascii=False)})
        for method,seq in [('current',m['current']),('ppr',paths),('mmr',m['mmr_top20'])]:
            for k in [5,10,20]:independently[(method,k)].append(match(seq[:k],gold[iid]['gold_files']))
    for (m,k),v in independently.items():
        assert abs(sum(v)/300-ppr['aggregate_all300'][m][f'any@{k}'])<1e-12
    csvfile(OUT/'ppr/mmr_top5_changes.csv',sorted(mmr_changes,key=lambda r:r['instance_id']))
    checks={'time':now(),'all_900_issue_arm_rows':len(rows)==900,
            'historical_function_scores_reproduced':historical_counts,
            'coverage_arithmetic':independent,'ppr_300_menus_verified':True,
            'off_gold_hit_not_covered_new_only':sum(r['arm']=='off' and r['gold_new_only'] for r in misses),
            'PPR_any_hit_recomputed':True,'no_seed_not_padded':True,
            'MMR_unique_subset_of_top100':True,'protected_inputs_unchanged':protected()==frozen['protected'],
            'all300_file_universes_equal_independent_path_traversal':True,
            'gold_file_universe_missing_cases':universe_audit['missing_gold_cases'],
            'MMR_top5_change_counts':{'ranking_changed':sum(r['ranking_changed'] for r in mmr_changes),
                                     'membership_changed':sum(r['membership_changed'] for r in mmr_changes),
                                     'hit_gained':sum(r['gold_hit_delta']==1 for r in mmr_changes),
                                     'hit_lost':sum(r['gold_hit_delta']==-1 for r in mmr_changes)},
            'test_content_opened':False,'GPU_used':False,'new_test_executions':0,
            'code_sha256':{str(p):sha(p) for p in sorted((ROOT/'code_proposal_pilots').glob('*.py'))}}
    write(OUT/'final_cpu_audit.json',checks)
    textfile(DOCS/'预研三_逐题统计与核验补充.md',
             '# 预研三逐题统计与核验补充\n\n'
             '[逐题两组覆盖比例（300题×3臂）](../../results/proposal_pilots/20261017/coverage/per_issue_rates.csv)。'
             '不可用覆盖留空，无命中预测组的比例记NA，不用0替代。\n\n'
             '独立重算Top-1混淆计数与PPR文件命中率均一致；覆盖只按失败测试调用上下文，bootstrap并集另列。'
             '全部300个PPR菜单、MMR唯一性/前100子集、无种子不补榜、原候选一致性与历史输入/封存test状态均核验。\n\n'
             'Wilson区间仅是逐题Top-1二项描述，不用于替代v6的issue聚类CI资格门。\n\n'
             'off组5条“命中gold但失败覆盖未观察到”的预测中，3条是补丁新增函数，在base commit上不存在；'
             '不能把这3条解释成覆盖采集遗漏。其余2条是base已有函数，未新增执行解释其缺失原因。'
             '[逐条核验](../../results/proposal_pilots/20261017/coverage/gold_hit_but_not_covered_audit.json)。\n\n'
             '[核验收据（含逐臂缺失、歧义、Top-1漏拒列表和区间）](../../results/proposal_pilots/20261017/final_cpu_audit.json)\n')
    print(json.dumps(checks,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
