"""Pre-training v6 gate definitions. No test or model-loading entry points."""
from collections import defaultdict
import random

SEED=20261016
REPLICATES=4000

def protocol():
    return {'version':'v6_offline_gate_20261016_v1','scope':'train_val_only; freeze before T3; user confirmation required',
        'probability':'sigmoid(yes_minus_no_logit / positive val-fitted temperature); no textual confidence',
        'calibration':'fit scalar temperature on unweighted full frozen val binary NLL; low/high never tuned',
        'same_val_calibration_and_evaluation':True,'same_val_selection_intervals_are_exploratory':True,
        'low':.6,'high':.9,'boundary_policy':'p<=0.6 direct reject; p>=0.9 direct retain; otherwise gray -> Qwen',
        'gold_group':'positive with source A or B; C-only proxies are not gold',
        'gold_direct_reject':'number gold p<=0.6 / all gold; gray stays in denominator and is NOT counted as retained',
        'separate_gold_routes':['direct_retain','direct_reject','gray_to_Qwen'],
        'mixed_rejection_precision':'true-negative direct rejects / ALL direct rejects on unweighted mixed val, p<=0.6',
        'secondary_legacy_rejection_precision':'p<0.5; report only, not substituted for actual hybrid direct rejects',
        'E_correct_reject':'E negatives p<=0.6 / all E negatives; report separately from mixed precision',
        'bootstrap':{'unit':'instance_id; resample all val issues with replacement, keeping all their rows',
                     'replicates':REPLICATES,'seed':SEED,'interval':'two-sided percentile 95%, empirical quantiles 2.5/97.5',
                     'temperature':'frozen val-fitted T within replicates; intervals conditional on fitted T, do not capture fitting/selection uncertainty',
                     'undefined_replicates':'not discarded silently: any undefined denominator -> gate inconclusive',
                     'zero_variance':'report degenerate CI but cannot certify a gate from an empirical zero-width interval'},
        'hard_gates':{'gold_direct_reject_CI_upper_max':.15,'mixed_direct_rejection_precision_CI_lower_min':.85,
                      'requires_defined_non_degenerate_intervals':True},
        'Qwen_anchor':{'gate_enabled':False,'reason':'T0 historical coverage B37/363 and C37/714 below50%; biased adaptive evidence',
             'historical_subset_accuracy':26/37,'anchor_plus2pp':26/37+.02,'use':'report-only; new val/input not same population'},
        'accuracy_and_AUC':'unweighted continuous p_yes AUROC and binary p>=0.5 accuracy report-only; do not compare binary-Qwen AUROC as continuous',
        'training_weight_policy':'use frozen per-example sample_weight, mean normalized to 1; training loss = sum(w_i*per_example_loss_i)/sum(w_i); generative loss first mean over each response tokens',
        'checkpoint_order':'gold protection first: lowest gold direct-reject CI upper, then highest mixed reject precision CI lower, then val accuracy; gates must both pass; never select by accuracy alone',
        'max_rounds':'at most two per T3 large base; 0.6B anchor one round, no extra tuning',
        'end_to_end_authority':'offline gates screen only; final authority is paired canary noninferiority, not McNemar nonsignificance',
        'T3_execution_allowed_by_this_file':False,'test_access_allowed':False}

def summarize(rr):
    gold=[r for r in rr if r['group']=='gold_AB'];reject=[r for r in rr if r['p_yes']<=.6]
    e=[r for r in rr if r['group']=='E_negative']
    return {'gold_direct_reject':sum(r['p_yes']<=.6 for r in gold)/len(gold) if gold else None,
       'mixed_rejection_precision':sum(not r['label'] for r in reject)/len(reject) if reject else None,
       'E_correct_reject':sum(r['p_yes']<=.6 for r in e)/len(e) if e else None}

def intervals(rr,replicates=REPLICATES):
    grouped=defaultdict(list)
    for r in rr:grouped[r['instance_id']].append(r)
    ids=sorted(grouped);rng=random.Random(SEED);point=summarize(rr);draws={k:[] for k in point}
    if not ids:raise ValueError('Empty validation set')
    for _ in range(replicates):
        sample=[r for iid in rng.choices(ids,k=len(ids)) for r in grouped[iid]]
        for k,v in summarize(sample).items():draws[k].append(v)
    result={}
    for k,v in draws.items():
        valid=sorted(x for x in v if x is not None)
        def q(f):
            h=(len(valid)-1)*f;lo=int(h);hi=min(lo+1,len(valid)-1)
            return valid[lo]+(valid[hi]-valid[lo])*(h-lo)
        result[k]={'point':point[k],'lower':q(.025) if valid else None,'upper':q(.975) if valid else None,
            'undefined_replicates':len(v)-len(valid),'degenerate':bool(valid and valid[0]==valid[-1])}
    def valid(k):return result[k]['undefined_replicates']==0 and not result[k]['degenerate']
    result['qualified']=bool(valid('gold_direct_reject') and valid('mixed_rejection_precision')
        and result['gold_direct_reject']['upper']<=.15 and result['mixed_rejection_precision']['lower']>=.85)
    return result
