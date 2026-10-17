"""All300 base-commit Python corpora, BM25, PPR and content-vector MMR."""
from collections import Counter,defaultdict
import hashlib
import math
import time
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfTransformer

from .common import *
from code_proposal_pilots.common import mentions,leaf
from code_proposal_pilots.ppr import pagerank


def lexical_scores(files,documents,query):
    content=[Counter(tokenize(doc)) for doc in documents]
    combined=[c+Counter(tokenize(path)) for c,path in zip(content,files)]
    q=set(tokenize(query));df=Counter()
    for c in combined:df.update(q.intersection(c))
    lengths=np.array([sum(c.values()) for c in combined],dtype=float)
    avg=lengths.mean() if lengths.size else 1.
    n=len(files);idf={w:math.log(1+(n-v+.5)/(v+.5)) for w,v in df.items()}
    bm=np.array([sum(idf[w]*c[w]*2.2/(c[w]+1.2*(.25+.75*dl/max(avg,1e-12))) for w in sorted(q.intersection(c))) for c,dl in zip(combined,lengths)])
    freq=Counter()
    for c in content:freq.update(c)
    vocabulary=[w for w,_ in sorted(freq.items(),key=lambda kv:(-kv[1],kv[0]))[:50000]]
    index={w:i for i,w in enumerate(vocabulary)};rr=[];cc=[];data=[]
    for i,c in enumerate(content):
        for w,v in c.items():
            if w in index:rr.append(i);cc.append(index[w]);data.append(v)
    counts=sparse.csr_matrix((np.asarray(data,dtype=np.float32),(rr,cc)),shape=(n,max(1,len(vocabulary))))
    tfidf=TfidfTransformer(norm='l2',smooth_idf=True,sublinear_tf=True).fit_transform(counts).astype(np.float32)
    return bm,tfidf,{'vocabulary_size':len(vocabulary),'empty_content_files':sum(not bool(c) for c in content),'nonzero_vector_entries':tfidf.nnz}


def main():
    frozen=freeze();gold,metrics,baseline,issues,_=inputs()
    anchors={r['instance_id']:r['anchor'] for r in metrics['cases']['off']}
    allmeta=[];start=time.monotonic()
    for i,(iid,g) in enumerate(sorted(gold.items()),1):
        target=case_dir(iid);done=target/'extraction_complete.json'
        if done.exists():allmeta.append(read(target/'meta.json'));continue
        target.mkdir(parents=True,exist_ok=False)
        sp=ROOT/'repo_structures_verified'/(iid+'.json');gp=ROOT/'results/v5_pruner/graphs'/(iid+'.json')
        structure=read(sp);graph=read(gp)
        assert structure['base_commit']==graph['base_commit']==g['base_commit']
        corpus=walk_python(structure['structure']);files=list(corpus);lookup={f:j for j,f in enumerate(files)}
        assert files and set(g['gold_files'])<=set(files),'Missing gold file in full Python universe'
        query=issues[iid]['problem_statement'];named=mentions(query)
        fn=[f for f in graph['functions'] if f['file'] in lookup]
        ids=[f['id'] for f in fn]
        seed_path=PARENT/'ppr/menus'/(iid+'.json');seed_menu=read(seed_path)
        assert seed_menu['base_commit']==g['base_commit'] and seed_menu['anchor']==anchors[iid]
        seeds=seed_menu['seed_function_ids'];assert set(seeds)<=set(ids)
        values,ppr_state=pagerank(ids,graph['edges'],seeds)
        n=len(files);mx=np.zeros(n);sm=np.zeros(n);fc=np.zeros(n);ni=np.zeros(n);no=np.zeros(n)
        idfile={f['id']:f['file'] for f in fn};names=defaultdict(set)
        for f,v in zip(fn,values):
            j=lookup[f['file']];mx[j]=max(mx[j],v);sm[j]+=v;fc[j]+=1;names[f['file']].add(leaf(f['qualified_name']))
        for caller,callee in {(e['caller'],e['callee']) for e in graph['edges']}:
            if caller in idfile and callee in idfile:
                no[lookup[idfile[caller]]]+=1;ni[lookup[idfile[callee]]]+=1
        bm,tfidf,vector_info=lexical_scores(files,list(corpus.values()),query)
        name_hits=np.array([len(named & names[f]) for f in files],dtype=float)
        X=np.column_stack([unitmax(mx),unitmax(bm),np.log1p(name_hits),np.log1p(fc),np.log1p(ni),np.log1p(no),
                           [len(Path(f).parts) for f in files],[int(test_file(f)) for f in files]]).astype(np.float32)
        y=np.array([f in g['gold_files'] for f in files],dtype=np.uint8)
        seed=int.from_bytes(hashlib.sha256(('ranking-v2-random:'+iid).encode()).digest()[:8],'big')
        rankings={'BM25':rank(bm),'PPR_max':rank(mx),'PPR_sum':rank(sm),
                  'random':np.random.default_rng(seed).permutation(n).astype(np.int32)}
        vals={'BM25':bm,'PPR_max':mx,'PPR_sum':sm};cache={}
        for base,base_scores in [('BM25',bm),('PPR_max',mx)]:
            for lam in LAMBDAS:
                name=f'{base}_MMR_{lam:.1f}';rankings[name]=mmr(base_scores,tfidf,lam,cache);vals[name]=base_scores
        meta={'instance_id':iid,'repo':g['repo'],'base_commit':g['base_commit'],'files':files,'gold_files':g['gold_files'],
              'original_CoSIL_candidates':baseline[iid],'anchor':anchors[iid],'seed_function_ids':seeds,'ppr_state':ppr_state,
              'existing_seed_json':str(seed_path),'existing_seed_json_sha256':sha(seed_path),
              'vector_info':vector_info,'feature_names':FEATURES,'random_seed':seed,
              'file_content_normalized_sha256':{f:hashlib.sha256(doc.encode()).hexdigest() for f,doc in corpus.items()},
              'source_structure_sha256':sha(sp),'source_graph_sha256':sha(gp),
              'issue_sha256':hashlib.sha256(query.encode()).hexdigest(),'all_Python_files_include_tests':True}
        np.savez_compressed(target/'features.npz',X=X,y=y,BM25=bm,PPR_max=mx,PPR_sum=sm)
        sparse.save_npz(target/'content_vectors.npz',tfidf,compressed=True)
        write(target/'meta.json',meta);record_rankings(iid,rankings,vals,meta,'retrieval_rankings')
        write(done,{'at':now(),'candidate_files':n,'feature_sha256':sha(target/'features.npz'),
                    'vectors_sha256':sha(target/'content_vectors.npz'),'meta_sha256':sha(target/'meta.json')})
        allmeta.append(meta)
        if i%10==0 or i==1:status('extract',completed=i,total=300,seconds=round(time.monotonic()-start,1))
        del structure,graph,corpus,tfidf,fn
    write(OUT/'extraction_manifest.json',{'time':now(),'cases':len(allmeta),'total_candidate_rows':sum(len(m['files']) for m in allmeta),
          'seeded_cases':sum(bool(m['seed_function_ids']) for m in allmeta),'repos':dict(Counter(m['repo'] for m in allmeta)),
          'case_meta_sha256':{m['instance_id']:sha(case_dir(m['instance_id'])/'meta.json') for m in allmeta}})
    assert protected()==frozen['protected'];status('extraction_complete',cases=300)


if __name__=='__main__':main()
