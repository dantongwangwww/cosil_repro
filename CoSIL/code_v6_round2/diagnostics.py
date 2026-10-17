"""CPU-only route diagnostics; a val-derived safety threshold is not a new gate."""
import math
from collections import Counter
from code_v5.metrics import apply_temperature


def route_metrics(rr, low, high=.9):
    assert 0 <= low < high <= 1
    gold=[r for r in rr if r['distribution_group']=='gold_AB']
    e=[r for r in rr if r['distribution_group']=='E_negative']
    rejected=[r for r in rr if r['p_yes']<=low]
    return {'low':low,'high':high,'gold_count':len(gold),
            'gold_direct_reject_count':sum(r['p_yes']<=low for r in gold),
            'gold_direct_reject_rate':sum(r['p_yes']<=low for r in gold)/len(gold),
            'gray_count':sum(low<r['p_yes']<high for r in rr),
            'gray_fraction':sum(low<r['p_yes']<high for r in rr)/len(rr),
            'E_direct_reject_rate':sum(r['p_yes']<=low for r in e)/len(e) if e else None,
            'mixed_rejection_precision':sum(not r['label'] for r in rejected)/len(rejected) if rejected else None,
            'rejected_count':len(rejected)}


def safety_diagnostic(predictions, temperature):
    rr=apply_temperature(predictions,temperature)
    gold=[r for r in rr if r['distribution_group']=='gold_AB']
    minimum=min(r['p_yes'] for r in gold)
    cap=math.nextafter(.9,0.)
    low=min(math.nextafter(minimum,-math.inf),cap)
    result={'temperature':temperature,'fitted_split':'val','gold_min_p':minimum,
            'rule':'p<=low rejects; therefore low must be strictly below minimum val gold p',
            'default':route_metrics(rr,.6),'formal_gate_unchanged':True,
            'same_val_selection_optimism':True,'out_of_sample_gold_safety_proven':False}
    if low<0:
        result.update(safe_threshold_feasible=False,low_star=None,safe=None,
                      reason='At least one gold has p=0; no admissible nonnegative threshold avoids rejection')
    else:
        safe=route_metrics(rr,low);assert safe['gold_direct_reject_count']==0
        assert low==cap or math.nextafter(low,math.inf)>=minimum
        result.update(safe_threshold_feasible=True,low_star=low,safe=safe)
    scan=sorted({0.,.6,cap,*[r['p_yes'] for r in rr if 0<=r['p_yes']<.9],*([low] if low>=0 else [])})
    result['scan']=[route_metrics(rr,x) for x in scan]
    return result


def point_pass(summary):
    risk=summary['selected']['assessment']['risk']
    g=risk['gold_direct_reject']['point'];p=risk['mixed_rejection_precision']['point']
    return g is not None and p is not None and g<=.15 and p>=.85
