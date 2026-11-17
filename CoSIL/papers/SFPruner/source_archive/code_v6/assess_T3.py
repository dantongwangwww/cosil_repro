"""Frozen v6 validation assessment and gold-first selection, never test."""
from collections import Counter
import math
from code_v5.metrics import fit_temperature,apply_temperature,evaluate_predictions
from code_v6.qualification import intervals

def metric_report(predictions):
    result=evaluate_predictions(predictions)
    # Legacy helper's .80/.85 gates do not apply to the frozen v6 race.
    result.pop('qualification_checks',None);result.pop('qualification_pass',None)
    return result

def assess(predictions):
    if not predictions or any(r['split']!='val' for r in predictions):raise ValueError('Calibration/selection is val-only')
    cal=fit_temperature(predictions,split='val');adjusted=apply_temperature(predictions,cal['temperature'])
    rr=[{**r,'group':r['distribution_group']} for r in adjusted]
    risk=intervals(rr)
    gold=[r for r in rr if r['group']=='gold_AB'];routes=Counter('reject' if r['p_yes']<=.6 else 'retain' if r['p_yes']>=.9 else 'gray' for r in gold)
    allroutes=Counter('reject' if r['p_yes']<=.6 else 'retain' if r['p_yes']>=.9 else 'gray' for r in rr)
    legacy=[r for r in rr if r['p_yes']<.5]
    return {'calibration':cal,'uncalibrated':metric_report(predictions),'calibrated':metric_report(adjusted),
        'risk':risk,'qualified':risk['qualified'],'gold_route_counts':dict(routes),'gold_denominator':len(gold),
        'gold_route_fractions':{k:routes[k]/len(gold) for k in ['retain','reject','gray']},
        'all_route_counts':dict(allroutes),'legacy_binary_rejection_precision_p_lt_05':sum(not r['label'] for r in legacy)/len(legacy) if legacy else None,
        'intervals_conditional_on_val_fitted_temperature':True,'test_opened':False}

def select(curves):
    if not curves:raise ValueError('No completed epochs')
    eligible=[c for c in curves if c['assessment']['qualified']]
    pool=eligible or curves
    def key(c):
        a=c['assessment'];risk=a['risk'];upper=risk['gold_direct_reject']['upper'];lower=risk['mixed_rejection_precision']['lower']
        return (upper if upper is not None else float('inf'),-(lower if lower is not None else -1),-a['uncalibrated']['overall']['accuracy'],c['epoch'])
    best=min(pool,key=key)
    return {'epoch':best['epoch'],'qualified':bool(eligible),'selection':'among qualified epochs, lowest gold-risk upper, highest reject-precision lower, accuracy; if none qualify, closest diagnostic only','assessment':best['assessment']}
