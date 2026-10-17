"""T0-b: verify saved real Qwen decisions on val; no queries, tests or new labels."""
from collections import Counter, defaultdict
import csv
import json
import random

from code_v3b.tool_dispatch import parse_verdict
from code_v5.metrics import evaluate_predictions, _sources
from code_v6.common import (ROOT,BASE,OUT,COHORTS,now,read,rows,write,sha,test_stats,
                            historical_files,verify_files,pair)


def consensus(observations):
    verdicts={r['native_parsed_response'] for r in observations if r['response_verified']}
    if not observations:return 'missing',None
    if len(verdicts)>1:return 'contradictory',None
    if any(not r['response_verified'] for r in observations):return 'invalid',None
    if len(verdicts)!=1: return 'invalid',None
    v=next(iter(verdicts))
    if v not in ['True','False']: return 'invalid',None
    return 'consensus',v=='True'


def interval(values):
    if not values:return None
    v=sorted(values)
    def quantile(p):
        index=(len(v)-1)*p; a=int(index); b=min(a+1,len(v)-1)
        return v[a]+(v[b]-v[a])*(index-a)
    return [quantile(.025),quantile(.975)]


def clustered_intervals(predictions):
    grouped=defaultdict(list)
    for r in predictions:grouped[r['instance_id']].append(r)
    keys=sorted(grouped);rng=random.Random(20261016);acc=[];gold_false=[]
    if not keys:return {'accuracy_CI95':None,'gold_misprune_CI95':None}
    for _ in range(2000):
        sampled=[r for _ in keys for r in grouped[rng.choice(keys)]]
        acc.append(sum((r['p_yes']>=.5)==r['label'] for r in sampled)/len(sampled))
        gold=[r for r in sampled if r['label'] and _sources(r)&{'A','B'}]
        if gold:gold_false.append(sum(r['p_yes']<.5 for r in gold)/len(gold))
    return {'method':'issue-cluster bootstrap, multiplicity retained','seed':20261016,'iterations':2000,
            'issues_with_observed_predictions':len(keys),'accuracy_CI95':interval(acc),
            'gold_misprune_CI95':interval(gold_false),'independent_test':False}


def run():
    target=OUT/'T0_Qwen_anchor';target.mkdir(parents=True,exist_ok=False)
    before_tests=test_stats();history=historical_files()
    inventory=BASE/'historical_qwen_pair_reuse_v1'
    receipt=read(inventory/'inventory_report.json');old_sources=read(inventory/'source_fingerprints.json')['paths']
    files={str(inventory/'inventory_report.json'):sha(inventory/'inventory_report.json'),
           str(inventory/'source_fingerprints.json'):sha(inventory/'source_fingerprints.json'),
           str(ROOT/'code_v6/historical_anchor.py'):sha(ROOT/'code_v6/historical_anchor.py'),
           str(ROOT/'code_v3b/tool_dispatch.py'):sha(ROOT/'code_v3b/tool_dispatch.py')}
    for name,expected in receipt['artifacts_sha256'].items():
        p=inventory/name;assert sha(p)==expected;files[str(p)]=expected
    observations=rows(inventory/'actual_historical_observations.jsonl')
    cohorts={name:rows(COHORTS[name]/'pruner_val.jsonl') for name in ['B','C']}
    val_keys={pair(r) for values in cohorts.values() for r in values}
    selected=[r for r in observations if pair(r) in val_keys]
    event_cache={};by_pair=defaultdict(list)
    for obs in selected:
        assert obs['split']=='val'
        path=obs['path']
        if path not in event_cache:
            actual=sha(path);assert actual==old_sources[path]==obs['event_file_sha256']
            files[path]=actual;event_cache[path]=rows(path)
        events=event_cache[path];event=events[obs['line']-1]
        assert event['event']=='prune' and event['llm_raw_response']==obs['llm_raw_response']
        assert parse_verdict(event['llm_raw_response'])==obs['native_parsed_response']
        if obs['response_verified']:
            fetch=events[obs['fetch_event_line']-1];call=events[obs['historical_model_call_line']-1]
            assert fetch['event']=='tool_result' and fetch['success'] and fetch['kind']=='source'
            assert call['event']=='model_call' and call['purpose'] in ['pruner','pruner_format_retry']
            assert obs['fetch_event_line']<obs['historical_model_call_line']<obs['line']
            assert event['decision']==obs['native_parsed_response']
        by_pair[(*pair(obs),obs['arm'])].append(obs)
    reports={};detail=[]
    B_predict_path=BASE/'B_runtime_reviewed_regularized_exploratory/training/reranker/val_epoch_1.jsonl'
    B_predictions={pair(r):r for r in rows(B_predict_path)};files[str(B_predict_path)]=sha(B_predict_path)
    for cohort,truth in cohorts.items():
        path=COHORTS[cohort]/'pruner_val.jsonl';files[str(path)]=sha(path)
        if cohort=='B':assert files[str(path)]==old_sources[str(path)]
        arms={}
        for arm in ['off','on','shuffled']:
            counts=Counter();pred=[]
            for r in truth:
                obs=by_pair.get((*pair(r),arm),[]);state,verdict=consensus(obs);counts[state]+=1
                detail.append({'cohort':cohort,'arm':arm,'instance_id':r['instance_id'],'function_id':r['function_id'],
                    'label':r['label'],'label_sources':'|'.join(sorted(_sources(r))),'status':state,'Qwen_verdict':verdict,
                    'actual_response_count':len(obs),'refs':json.dumps([{'path':o['path'],'line':o['line']} for o in obs],ensure_ascii=False)})
                if verdict is not None:pred.append({**r,'p_yes':float(verdict)})
            metrics=evaluate_predictions(pred) if pred else None
            all_gold=[r for r in truth if r['label'] and _sources(r)&{'A','B'}]
            gold=[r for r in pred if r['label'] and _sources(r)&{'A','B'}]
            gold_false=sum(r['p_yes']==0 for r in gold)
            coverage=len(pred)/len(truth)
            arms[arm]={'total_val_pairs':len(truth),'verified_consensus_pairs':len(pred),'coverage':coverage,
                'status_counts':dict(counts),'metrics_observed_only':metrics,
                'accuracy_observed_only':metrics['overall']['accuracy'] if metrics else None,
                'continuous_score_AUC':None,'binary_verdict_AUROC':metrics['overall']['auc'] if metrics else None,
                'gold_observed':len(gold),'gold_total':len(all_gold),'gold_directly_rejected':gold_false,
                'gold_misprune_rate_observed_only':gold_false/len(gold) if gold else None,
                'qualification_anchor':'partial_observation_report_only' if coverage<.5 else 'observed_subset_with_selection_bias',
                'intervals':clustered_intervals(pred)}
            if cohort=='B' and arm=='off':
                paired=[B_predictions[pair(r)] for r in pred]
                assert all(x['label'] is y['label'] and _sources(x)==_sources(y) for x,y in zip(pred,paired))
                arms[arm]['B_reranker_same_observed_pairs']=evaluate_predictions(paired)
        reports[cohort]=arms
    with (target/'val_pair_coverage.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(detail[0]));w.writeheader();w.writerows(detail)
    verify_files(files);verify_files(history);assert test_stats()==before_tests
    result={'completed_at':now(),'status':'complete','reports':reports,'source_sha256':files,
        'primary_arm':'off','new_model_calls':0,'test_decoded_or_hashed':False,
        'history_unchanged':True,'missing_decisions_are_NA':True,
        'AUC_limitation':'Only historical True/False answers exist. Binary-verdict AUROC is balanced accuracy, not a continuous ranking-score AUC; no scores or confidence are fabricated.',
        'selection_limitation':'B/e_log labels partly selected from historical Qwen; logged candidates are adaptively retrieved; observed subset is not an independent random validation exam.',
        'input_limitation':'Historical Qwen used full issue and fetched source; v5 local judges used 2000/1500 character prefixes.'}
    write(target/'anchor.json',result)
    print(json.dumps({'completed':True,'off':{k:v['off'] for k,v in reports.items()}},ensure_ascii=False))
    return result


if __name__=='__main__':run()
