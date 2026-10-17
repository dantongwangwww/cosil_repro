"""Freeze T3 first-round implementation after CPU native-format checks."""
from pathlib import Path
from code_v6.common import ROOT,OUT,read,write,sha,now,verify_files,test_stats
from code_v6.train_T3 import SPECS,RACE,DATA

def run():
    auth=read(OUT/'T3_user_authorization.json');assert auth['T3_allowed'] and not auth['test_contents_allowed']
    verify_files(read(DATA/'freeze_manifest.json')['artifacts_sha256'])
    assert sha(DATA/'freeze_manifest.json')==auth['T2_freeze_manifest_sha256']
    cpu=read(OUT/'T3_codec_smoke_checks.json');assert len(cpu['checks'])==3 and all(r['native_SFT_scoring_boundary_passed'] for r in cpu['checks'])
    RACE.mkdir(parents=True,exist_ok=True)
    files=[ROOT/'code_v6'/n for n in ['train_T3.py','training_codec.py','assess_T3.py','common.py','input_format.py','qualification.py']]
    files += [ROOT/'code_v5/judge_models.py',ROOT/'code_v5/metrics.py']
    model_sources={}
    for key,repo in [('reranker4B','Qwen/Qwen3-Reranker-4B'),('swerank7B','Salesforce/SweRankLLM-Small')]:
        p=OUT/'T3_model_sources'/(repo.replace('/','__')+'_api.json');j=read(p)
        model_sources[key]={'repo':repo,'revision':j['sha'],'license':j['cardData']['license'],'source_api_sha256':sha(p)}
    write(RACE/'protocol.json',{'frozen_at':now(),'round':1,'user_authorization_sha256':sha(OUT/'T3_user_authorization.json'),
         'T2_freeze_sha256':sha(DATA/'freeze_manifest.json'),'qualification_protocol_sha256':sha(DATA/'qualification_protocol.json'),
         'models':SPECS,'sources':model_sources,'code_sha256':{str(p):sha(p) for p in files},'training_recipe':auth['training_recipe'],
         'micro_batch':1,'effective_batch':8,'micro_batch_reason':'Same effective batch and weighted per-example loss on single24GB GPUs; micro1 prevents padding/activation memory blowup.',
         'inference_probability':'reranker yes/no binary logits; SweRank native SFT JSON true/false conditional scores. No textual confidence or random classifier head.',
         'input_compatibility':'exact frozen T2 body/native contract, all actual tokenizer lengths checked before CUDA; fail rather than crop',
         'data_contamination':{'SweRank':'author-reported repository exclusion of SWE-bench and LocBench; no independently available full issue-level training manifest verified; residual unknown, exploratory only',
             'all_bases':'foundation-model pretraining contamination not independently cleared; no sealed test opened for auditing'},
         'SweRank_task_change':'published listwise ranker adapted to pointwise causal-path boolean task; do not label this original SweRank reproduction',
         'seed':0,'replicates':1,'calibration':'unweighted frozen val only; same-val fitting/selection intervals exploratory',
         'epoch_selection':'gate-qualified epochs first, then minimum gold direct-reject CI upper, maximum precision CI lower, accuracy. If none qualify, diagnostic best only.',
         'first_round_auto_retuning':False,'maximum_large_base_rounds_total':2,'anchor_rounds_total':1,
         'optional_third_base':'not scheduled in first round to bound card-hours; SweRank already shares main-agent Qwen2.5-Coder7B ancestry',
         'Jev_candidate':'unresolved in original instruction; no invented replacement added',
         'resource_policy':'user-approved headroom-qualified sharing; bounded own allocator; no peer signals or service changes. GPU0 original T1 service only.',
         'resumption':'own rolling adapter/optimizer/RNG checkpoint every200 updates and each complete epoch; preserve incomplete artifacts; unchanged code/data/recipe required',
         'sealed_test_stat_only':test_stats(),'T4_allowed':False,'after_first_round':'publish actual train/val reports and stop for user interpretation'})
    print('T3 first-round protocol frozen; training has not been inferred from preparation.')

if __name__=='__main__':run()
