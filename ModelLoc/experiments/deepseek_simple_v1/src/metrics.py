"""Fixed ranking slots: malformed/duplicate entries are not compacted away."""
from .common import norm

def scores(predictions,gold,k):
    if not gold:return {v:None for v in ('hit','recall','precision','f1','all_coverage')}
    hit=len(set(v for v in predictions[:k] if v is not None)&set(gold))
    recall=hit/len(set(gold));precision=hit/k
    return dict(hit=int(hit>0),recall=recall,precision=precision,
                f1=2*recall*precision/(recall+precision) if hit else 0,
                all_coverage=int(hit==len(set(gold))))

def mrr(predictions,gold):
    if not gold:return None
    return next((1/(i+1) for i,p in enumerate(predictions[:10]) if p in gold),0)

def normalize_functions(raw,index):
    result=[];invalid=0
    for item in raw[:10]:
        if not isinstance(item,dict):result.append(None);invalid+=1;continue
        path=norm(item.get('path',''));qn=item.get('qualified_name')
        matches=[d for d in index.get(path,{}).get('definitions',[]) if d['kind']=='function' and d['qualified_name']==qn]
        if len(matches)!=1:result.append(None);invalid+=1
        else:result.append(path+'::'+qn)
    return result,invalid

def normalize_files(raw,paths):
    out=[];invalid=0
    for p in raw[:10]:
        p=norm(p) if isinstance(p,str) else None
        if p not in paths:out.append(None);invalid+=1
        else:out.append(p)
    return out,invalid
