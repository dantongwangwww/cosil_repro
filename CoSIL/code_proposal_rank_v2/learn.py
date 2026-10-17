"""Fixed logistic/GBDT models; every prediction is out of repository group."""
import time
import warnings
import joblib
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier

from .common import *


def main():
    frozen=freeze();ids=sorted(read(OUT/'extraction_manifest.json')['case_meta_sha256'])
    metas=[read(case_dir(i)/'meta.json') for i in ids]
    blocks=[];ys=[];weights=[];slices=[];offset=0
    for iid in ids:
        d=np.load(case_dir(iid)/'features.npz',allow_pickle=False);x,y=d['X'],d['y']
        assert np.isfinite(x).all() and 0<y.sum()<len(y)
        w=np.where(y,.5/y.sum(),.5/(len(y)-y.sum()))
        blocks.append(x);ys.append(y);weights.append(w);slices.append(slice(offset,offset+len(y)));offset+=len(y)
    X=np.concatenate(blocks);y=np.concatenate(ys);w=np.concatenate(weights)
    groups=[m['repo'] for m in metas]
    predictions={name:np.full(len(y),np.nan) for name in LTR};folds=[];warning_log=[]
    fold_iter=GroupKFold(n_splits=5).split(np.arange(len(ids)),groups=groups)
    for fold,(train,test) in enumerate(fold_iter):
        trrepos=sorted({groups[i] for i in train});terepos=sorted({groups[i] for i in test})
        assert not set(trrepos)&set(terepos)
        tr=np.concatenate([np.arange(slices[i].start,slices[i].stop) for i in train])
        te=np.concatenate([np.arange(slices[i].start,slices[i].stop) for i in test])
        trainw=w[tr]/w[tr].mean()
        folds.append({'fold':fold,'train_repos':trrepos,'test_repos':terepos,'train_issues':[ids[i] for i in train],
                      'test_issues':[ids[i] for i in test],'train_candidate_rows':len(tr),'test_candidate_rows':len(te),
                      'group_intersection':[],'heldout_labels_used_for_fit':False})
        for name in LTR:
            start=time.monotonic();cols=list(range(1,8)) if name.endswith('noPPR') else list(range(8))
            trainx=X[tr][:,cols];testx=X[te][:,cols];scaler=None
            if name.startswith('LR'):
                scaler=StandardScaler().fit(trainx);trainx=scaler.transform(trainx);testx=scaler.transform(testx)
                model=LogisticRegression(C=1.0,solver='lbfgs',max_iter=1000,random_state=SEED)
            else:
                model=HistGradientBoostingClassifier(learning_rate=.1,max_iter=100,max_depth=3,
                    max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1.,early_stopping=False,random_state=SEED)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always');model.fit(trainx,y[tr],sample_weight=trainw)
            messages=[str(v.message) for v in caught]
            warning_log.append({'fold':fold,'model':name,'warnings':messages})
            predictions[name][te]=model.predict_proba(testx)[:,1]
            dest=OUT/'fold_models';dest.mkdir(exist_ok=True)
            joblib.dump({'model':model,'scaler':scaler,'feature_columns':cols,'feature_names':[FEATURES[j] for j in cols],
                         'train_repos':trrepos,'test_repos':terepos},dest/f'fold{fold}_{name}.joblib',compress=3)
            status('LTR_fit',fold=fold,model=name,seconds=round(time.monotonic()-start,1),warnings=messages)
    for name,p in predictions.items():assert np.isfinite(p).all() and ((p>=0)&(p<=1)).all()
    seen=[i for f in folds for i in f['test_issues']]
    assert len(seen)==300 and len(set(seen))==300 and set(seen)==set(ids)
    write(OUT/'grouped_fivefold_manifest.json',{'time':now(),'folds':folds,'all300_exactly_once_OOF':True,
          'features':FEATURES,'group_column':'repo','warnings':warning_log,'random_state':SEED,
          'global_training_scaler_or_feature_selection':False})
    for i,iid in enumerate(ids):
        np.savez_compressed(case_dir(iid)/'LTR_OOF_probabilities.npz',**{name:p[slices[i]] for name,p in predictions.items()})
    assert protected()==frozen['protected'];status('LTR_OOF_complete',cases=300)


def rerank():
    frozen=freeze();ids=sorted(read(OUT/'extraction_manifest.json')['case_meta_sha256'])
    for i,iid in enumerate(ids,1):
        meta=read(case_dir(iid)/'meta.json');tfidf=sparse.load_npz(case_dir(iid)/'content_vectors.npz')
        probs=np.load(case_dir(iid)/'LTR_OOF_probabilities.npz',allow_pickle=False)
        rankings={m:rank(probs[m]) for m in LTR};values={m:probs[m] for m in LTR};cache={}
        for model in ['LR','GBDT']:
            base=f'{model}_withPPR'
            for lam in LAMBDAS:
                name=f'{base}_MMR_{lam:.1f}';rankings[name]=mmr(probs[base],tfidf,lam,cache);values[name]=probs[base]
        record_rankings(iid,rankings,values,meta,'LTR_rankings')
        if i%25==0 or i==1:status('LTR_MMR',completed=i,total=300)
    assert protected()==frozen['protected'];status('all20_rankings_complete',cases=300)
