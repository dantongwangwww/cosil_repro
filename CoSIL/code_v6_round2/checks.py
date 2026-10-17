"""CPU checks of the one-field intervention and inclusive safety boundary."""
import math
from unittest.mock import patch
from code_v6_round2.common import *
from code_v6_round2.prepare import derive_weights
from code_v6_round2.diagnostics import safety_diagnostic


def run():
    preserve_history()
    before=rows(PARENT_DATA/'pruner_train.jsonl');after=rows(DATA/'pruner_train.jsonl')
    assert len(before)==len(after)==8556
    for a,b in zip(before,after):
        assert {k:v for k,v in a.items() if k!='sample_weight'}=={k:v for k,v in b.items() if k!='sample_weight'}
        assert math.isclose(b['sample_weight']/a['sample_weight'],1.5 if a['label'] else .75,rel_tol=1e-12)
    val=rows(DATA/'pruner_val.jsonl');weights=derive_weights(before,val)
    assert sha(DATA/'pruner_val.jsonl')==sha(PARENT_DATA/'pruner_val.jsonl')
    assert sha(DATA/'split_manifest.json')==sha(PARENT_DATA/'split_manifest.json')
    assert all(math.isclose(r['sample_weight'],weights[r['distribution_group']],rel_tol=1e-12) for r in after)
    pos=sum(r['sample_weight'] for r in after if r['label']);neg=sum(r['sample_weight'] for r in after if not r['label'])
    assert math.isclose(pos,neg,rel_tol=1e-12)
    for positive,groups in [(True,['gold_AB','C_positive']),(False,['D_only_negative','E_negative'])]:
        denom=sum(r['label']==positive for r in val);mass=pos if positive else neg
        for g in groups:
            actual=sum(r['sample_weight'] for r in after if r['distribution_group']==g)/mass
            target=sum(r['distribution_group']==g for r in val)/denom
            assert math.isclose(actual,target,rel_tol=1e-12)
    fixture=[{'instance_id':'toy','function_id':'gold','distribution_group':'gold_AB','label':True,'p_yes':.2},
             {'instance_id':'toy','function_id':'irrelevant','distribution_group':'E_negative','label':False,'p_yes':.1}]
    with patch('code_v6_round2.diagnostics.apply_temperature',lambda pp,t:pp):
        d=safety_diagnostic(fixture,1.)
        assert d['safe']['gold_direct_reject_count']==0 and d['safe']['rejected_count']==1
        assert math.nextafter(d['low_star'],math.inf)==.2 and d['default']['gold_direct_reject_count']==1
        high=[{**r,'p_yes':.95 if r['label'] else .91} for r in fixture]
        assert safety_diagnostic(high,1.)['low_star']<.9
        zero=[{**r,'p_yes':0. if r['label'] else .1} for r in fixture]
        assert not safety_diagnostic(zero,1.)['safe_threshold_feasible']
    verify_files(read(RACE/'protocol.json')['code_sha256'])
    write(CONTROL/'CPU_verification.json',{'time':now(),'all_8556_train_rows_only_weight_changed':True,
        'P_N_weighted_mass_equal':True,'conditional_source_mix_matches_val':True,'val_split_bytes_unchanged':True,
        'safe_threshold_inclusive_boundary_and_zero_case_passed':True,'fictional_threshold_fixtures_only':True,
        'history_and_frozen_code_verified':True,'test_stat_only':test_stats(),'test_contents_opened':False})
    print('All CPU checks passed; no GPU, model generation, or sealed-test access.')


if __name__=='__main__':run()
