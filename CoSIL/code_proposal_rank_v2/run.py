"""Persistent sequential CPU driver; a failed stage never promotes results."""
import traceback
from .common import *


def self_check():
    from .extract import lexical_scores
    from code_proposal_pilots.ppr import pagerank
    fixture={'pkg':{'functions':{'x.py':{'text':['def x(): pass']}},'tests':{'test_x.py':{'text':['def test_x(): pass']}}}}
    assert set(walk_python(fixture))=={'pkg/functions/x.py','pkg/tests/test_x.py'}
    bm,vec,_=lexical_scores(['a.py','b.py'],['uniquealpha uniquealpha','uniquebeta'],'uniquealpha')
    assert bm[0]>0 and bm[1]==0 and rank(bm).tolist()==[0,1]
    assert np.allclose((vec@vec.T).diagonal(),[1,1])
    r=mmr(np.array([1.,.5]),vec,.5);assert sorted(r)==[0,1]
    assert len(METHODS)==len(set(METHODS))==20
    assert scores(np.array([1,0]),np.array([True,False]))['MRR']==.5


def main():
    self_check();freeze();status('starting')
    from . import extract,learn,report
    try:
        if not (OUT/'extraction_manifest.json').exists():extract.main()
        if not (OUT/'grouped_fivefold_manifest.json').exists():learn.main()
        if not all((case_dir(i)/'LTR_rankings.npz').exists() for i in read(OUT/'extraction_manifest.json')['case_meta_sha256']):learn.rerank()
        if not (OUT/'summary.json').exists():report.main()
    except Exception:
        status('failed',traceback=traceback.format_exc())
        raise


if __name__=='__main__':main()
