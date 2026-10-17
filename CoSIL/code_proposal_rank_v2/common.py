from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import numpy as np
from scipy import sparse

from code_proposal_pilots.common import ROOT, DOCS, OUT as PARENT, read, write, sha, now, protected, inputs, textfile, csvfile

OUT=PARENT/'file_ranking_v2'
FEATURES=['PPR_max','BM25','name_hits','function_count','in_degree','out_degree','path_depth','test_file']
LAMBDAS=[.3,.5,.7]
PRIMITIVES=['BM25','PPR_max','PPR_sum','random']
BASE_MMR=[f'{b}_MMR_{v:.1f}' for b in ['BM25','PPR_max'] for v in LAMBDAS]
LTR=[f'{model}_{variant}' for model in ['LR','GBDT'] for variant in ['noPPR','withPPR']]
COMBOS=[f'{model}_withPPR_MMR_{v:.1f}' for model in ['LR','GBDT'] for v in LAMBDAS]
METHODS=PRIMITIVES+BASE_MMR+LTR+COMBOS
SEED=20261017


def status(stage,**kwargs):
    OUT.mkdir(parents=True,exist_ok=True)
    data={'time':now(),'stage':stage,'GPU_used':False,'pruner_test_opened':False,**kwargs}
    p=OUT/'status.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
    print(json.dumps(data,ensure_ascii=False),flush=True)


def freeze():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='', 'CPU tournament requires an explicitly empty CUDA mask'
    import scipy,sklearn,joblib,threadpoolctl,sys
    files=list((ROOT/'code_proposal_rank_v2').glob('*.py'))+[ROOT/'code_proposal_rank_v2/requirements.txt',ROOT/'code_proposal_pilots/ppr.py',ROOT/'code_proposal_pilots/common.py']
    protocol=DOCS/'文件排序擂台_v2_预注册协议.md'
    record={'created_at':now(),'pre_change_commit':'340c6178b345d066f4ff971bd3f690a203638e59',
            'code_sha256':{str(p):sha(p) for p in files},'protocol_sha256':sha(protocol),
            'protected':protected(),'methods':METHODS,'features':FEATURES,'lambdas':LAMBDAS,
            'environment':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,
                           'sklearn':sklearn.__version__,'joblib':joblib.__version__,'threadpoolctl':threadpoolctl.__version__},
            'GPU_allowed':False,'sealed_pruner_test_read_allowed':False,'folds':5,'group':'repo'}
    record['seed_menu_sha256']={p.stem:sha(p) for p in sorted((PARENT/'ppr/menus').glob('*.json'))}
    assert len(record['seed_menu_sha256'])==300
    record['previous_pilot_summaries_sha256']={str(PARENT/s/'summary.json'):sha(PARENT/s/'summary.json') for s in ['coverage','ppr','anchor']}
    p=OUT/'frozen_protocol.json'
    if not p.exists():write(p,record)
    else:
        old=read(p)
        for k in ['code_sha256','protocol_sha256','protected','methods','features','lambdas','environment','seed_menu_sha256','previous_pilot_summaries_sha256']:assert old[k]==record[k],f'Frozen {k} changed'
    return read(p)


def walk_python(structure):
    todo=[('',structure)];result={}
    while todo:
        prefix,node=todo.pop()
        for name,value in node.items():
            path=prefix+name
            if name.endswith('.py'):
                text=value.get('text',[]) if isinstance(value,dict) else []
                result[path]='\n'.join(text) if isinstance(text,list) else str(text)
            elif isinstance(value,dict):todo.append((path+'/',value))
    return dict(sorted(result.items()))


def tokenize(text):
    text=re.sub(r'([A-Z]+)([A-Z][a-z])',r'\1 \2',text)
    text=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',text)
    return re.findall(r'[a-z]+|\d+', ' '.join(re.findall(r'[A-Za-z_][A-Za-z_0-9]*',text)).replace('_',' ').lower())


def test_file(path):
    p=Path(path)
    return any(v.lower() in {'test','tests'} for v in p.parts[:-1]) or p.name=='conftest.py' or p.name.startswith('test_') or p.name.endswith('_test.py')


def rank(score):
    return np.argsort(-np.asarray(score),kind='stable').astype(np.int32)


def unitmax(a):
    a=np.asarray(a,dtype=np.float64)
    return a/a.max() if a.size and a.max()>0 else np.zeros_like(a)


def mmr(score,matrix,lam,cosine_cache=None):
    n=len(score);cache={} if cosine_cache is None else cosine_cache
    relevance=unitmax(score);maxsim=np.zeros(n);selected=[];available=np.ones(n,dtype=bool)
    for _ in range(min(20,n)):
        values=lam*relevance-(1-lam)*maxsim;values[~available]=-np.inf
        i=int(np.argmax(values));selected.append(i);available[i]=False
        if i not in cache:
            cache[i]=np.clip((matrix@matrix.getrow(i).T).toarray().reshape(-1),0,1)
        maxsim=np.maximum(maxsim,cache[i])
    return np.array(selected+[int(i) for i in rank(score) if available[i]],dtype=np.int32)


def scores(ranking,positive):
    positions=np.flatnonzero(np.asarray(positive)[ranking])
    first=int(positions[0])+1 if positions.size else None
    d={f'hit@{k}':float(first is not None and first<=k) for k in [1,5,10,20]}
    d.update(MRR=1/first if first else 0.,MRR20=1/first if first and first<=20 else 0.,first_gold_rank=first)
    return d


def case_dir(iid):return OUT/'cases'/iid


def record_rankings(iid,rankings,score_values,metadata,filename):
    p=case_dir(iid)
    np.savez_compressed(p/(filename+'.npz'),**{m:r.astype(np.int32) for m,r in rankings.items()})
    top={m:[{'file':metadata['files'][int(j)],'score':float(score_values[m][int(j)]) if m in score_values else None} for j in r[:20]] for m,r in rankings.items()}
    write(p/(filename+'_top20.json'),{'instance_id':iid,'rankings':top})
