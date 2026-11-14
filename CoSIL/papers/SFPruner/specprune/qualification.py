"""Frozen v6 issue-group bootstrap qualification; validation only."""
from collections import defaultdict
import random
SEED=20261016
REPLICATES=4000

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
