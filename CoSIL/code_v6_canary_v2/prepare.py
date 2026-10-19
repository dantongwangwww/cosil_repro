"""CPU gate: val-only calibration freeze and 20-row exact training/deployment parity."""
from collections import Counter
import math
from pathlib import Path
from .common import *


def run():
    OUT.mkdir(parents=True,exist_ok=False)
    before=test_stats();history=protected()
    write(OUT/'user_authorization.json',{
        'recorded_at':now(),'source':'User message 2026-10-19 explicitly authorizes canary v2 and original7333 service restart/shutdown',
        'named_document':'指令_v6_金丝雀v2_SweRank晋级_2026-10-18.md',
        'named_document_found':False,'controlling_protocol':'Complete execution specification in current user message',
        'restart_original_vllm7333':True,'shutdown_on_completion_stop_or_failure':True,
        'test_opened':False,'modify_CSRSE_or_peer_processes':False,'historical_matrix_updates':False})
    summary=read(RACE/'training_summary.json');assert summary['selected']['epoch']==1
    predictions=rows(RACE/'val_epoch_1.jsonl')
    complete=read(RACE/'epoch_1/checkpoint_complete.json')
    assert complete['adapter_sha256']==sha(RACE/'epoch_1/adapter_model.safetensors')
    assert complete['val_predictions_sha256']==sha(RACE/'val_epoch_1.jsonl')
    from code_v5.metrics import apply_temperature
    from code_v6_round2.diagnostics import safety_diagnostic
    temperature=summary['selected']['assessment']['calibration']['temperature']
    diagnostic=safety_diagnostic(predictions,temperature)
    assert diagnostic['safe_threshold_feasible']
    low=diagnostic['low_star'];minimum=diagnostic['gold_min_p']
    assert low<minimum and math.nextafter(low,math.inf)==minimum
    calibrated=apply_temperature(predictions,temperature)
    # The default and safety thresholds are IEEE754 binary64 throughout routing.
    write(OUT/'val_route_diagnostic.json',diagnostic)
    write(OUT/'calibration.json',summary['selected']['assessment']['calibration'])
    sampling=read(OLD/'T1_canary_preparation/sampling_manifest.json');ids=sampling['selected_issue_ids']
    split=read(DATA/'split_manifest.json')['splits']
    assert sampling['seed']==20261016 and len(ids)==len(set(ids))==20
    assert not set(ids)&set(split['test'])
    clean_keys=['instance_id','repo','base_commit','problem_statement']
    official={r['instance_id']:{k:r[k] for k in clean_keys} for r in rows(ROOT.parent/'GraphLocator/datasets/swe_bench_lite.jsonl') if r['instance_id'] in ids}
    assert set(official)==set(ids)
    write(OUT/'inference_issues.json',official)
    prepared=read(ROOT/'results/qwen_300/prepared_inputs.json')
    # Reuse is permitted only after checking all original code, generation
    # protocol, candidate files, issue identities and base commits against T1.
    from code_v5.run_pipeline import inference_core
    core,core_sha=inference_core();p=read(OLD/'T1_canary_preparation/protocol.json')
    assert core==p['original_inference_core'] and core_sha==p['original_inference_core_sha256']
    off=[];bindings={};relocated={}
    for name,expected in p['source_sha256'].items():
        path=Path(name)
        if not path.exists() and path.name.startswith('指令_'):
            path=ROOT.parent/'交接指令'/path.name
            relocated[name]=str(path)
        if sha(path)!=expected:raise ValueError('T1 source changed: '+str(path))
        bindings[str(path)]=expected
    write(OUT/'relocated_source_paths.json',relocated)
    for r in sampling['analysis_only_records']:
        iid=r['instance_id'];old=read(r['historical_off_case'])
        assert old['status']=='complete' and old['protocol']==prepared['configuration']['protocol']
        assert old['found_files']==prepared['candidates'][iid]
        sp=ROOT/'repo_structures_verified'/(iid+'.json');st=read(sp)
        assert (st['repo'],st['base_commit'])==(official[iid]['repo'],official[iid]['base_commit'])
        for path in [Path(r['historical_off_case']),Path(r['historical_off_events']),sp]:bindings[str(path)]=sha(path)
        off.append({**r,'off_reuse_protocol_checked_v2':True})
    write(OUT/'sample_and_off_reuse.json',{'seed':20261016,'selected_issue_ids':ids,'records':off,'all20_reuse_compatible':True})
    dataset=rows(DATA/'pruner_train.jsonl')+rows(DATA/'pruner_val.jsonl')
    pool=[r for r in dataset if r['instance_id'] in ids]
    # Deterministic 20 unique pairs, with long source/issue and nonempty context
    # as coverage targets; selection does not inspect labels or gold status.
    ranked=sorted(pool,key=lambda r:digest('v6-canary-v2-parity:'+r['instance_id']+':'+r['function_id']))
    selected=[]
    for condition in [lambda r:len(r['function'])>1500,lambda r:len(r['issue'])>2000,
                      lambda r:len(r['neighbors'].splitlines())>1,lambda r:True]:
        cap=min(20,len(selected)+5)
        for row in ranked:
            if condition(row) and (row['instance_id'],row['function_id']) not in {(r['instance_id'],r['function_id']) for r in selected}:
                selected.append(row)
                if len(selected)>=cap:break
    selected=selected[:20];assert len(selected)==20
    from .inputs import Renderer
    from code_v6.training_codec import Codec
    from code_v6.input_format import assert_v6_row
    renderer=Renderer();codec=Codec(renderer.swe_tokenizer,'instruct');checks=[]
    for row in sorted(selected,key=lambda r:(r['instance_id'],r['function_id'])):
        iid=row['instance_id'];o=official[iid]
        renderer.load(iid,o['repo'],o['base_commit'])
        deployed=renderer.render(o['problem_statement'],row['function_id'])
        before_feature=codec.encode(row)
        after_feature=codec.encode({**deployed,'label':False})
        exact=all(deployed[k]==row[k] for k in ['issue','function','neighbors','model_input','input_version','input_sha256'])
        token_exact=before_feature['score_input_ids']==after_feature['score_input_ids'] and before_feature['candidates']==after_feature['candidates']
        check={'instance_id':iid,'function_id':row['function_id'],'split':row['split'],
            'exact_render_match':exact,'native_score_token_ids_match':token_exact,
            'training_input_sha256':row['input_sha256'],'deployment_input_sha256':deployed['input_sha256'],
            'issue_chars':len(deployed['issue']),'function_chars':len(deployed['function']),
            'neighbor_chars':len(deployed['neighbors']),'neighbor_edges_selected':deployed['neighbor_edges_selected'],
            'native_input_tokens':len(after_feature['score_input_ids']),
            'structure_sha256':deployed['structure_sha256'],'base_blob_sha1':deployed['base_blob_sha1']}
        checks.append(check)
        status(OUT/'input_parity_progress.json',{'time':now(),'checked':len(checks),'records':checks})
        if not exact or not token_exact:raise ValueError('Deployment/training v6 input mismatch: '+str(check))
        print({'parity':len(checks),'issue':iid,'match':True},flush=True)
    write(OUT/'input_parity_20.json',{'time':now(),'all20_passed':True,'selection':'SHA256 deterministic, explicit long-input/context coverage, no labels',
        'records':checks,'training_data_changed':False,'source_summaries_rebuilt_from_structure':True,
        'source_newlines_restored_from_verified_base_blob':True,'graph_or_label_lookups_for_neighbors':False})
    freeze_paths=list(Path(__file__).parent.glob('*.py'))+[SERVICE_SCRIPT,DATA/'pruner_train.jsonl',DATA/'pruner_val.jsonl',DATA/'split_manifest.json',
        RACE/'val_epoch_1.jsonl',RACE/'epoch_1/adapter_model.safetensors',RACE/'epoch_1/adapter_config.json',
        RACE/'epoch_1/checkpoint_complete.json',RACE/'training_summary.json',RACE/'training_manifest.json',
        OUT/'input_parity_20.json',OUT/'val_route_diagnostic.json',OUT/'calibration.json',OUT/'sample_and_off_reuse.json',OUT/'inference_issues.json']
    # Base/tokenizer provenance is validated byte-for-byte once on CPU, not on GPU.
    receipt=read(ROUND2/'T3_model_sources/swerank7B_download_receipt.json')
    for name,v in receipt['files'].items():
        if sha(MODEL/name)!=v['sha256']:raise ValueError('Base model changed '+name)
        bindings[str(MODEL/name)]=v['sha256']
    bindings.update({str(p):sha(p) for p in freeze_paths})
    write(OUT/'deployment_parameters.json',{'model':'Salesforce/SweRankLLM-Small','adapter_dir':str(RACE/'epoch_1'),
        'epoch':1,'training_positive_negative_total_weight':'1:1','temperature':temperature,'fitted_split':'val',
        'default_low':.6,'high':.9,'safe_low_star':low,'safe_low_star_hex':low.hex(),
        'minimum_val_gold_probability':minimum,'p_le_low_reject':True,'p_ge_high_retain':True,
        'otherwise_Qwen':True,'class_always_Qwen':True,'input_version':'v6_issue8000_fn8192_neighbors16_8192tokens_v1',
        'judge_backend':'single GPU3 transformers BF16/SDPA, fixed true/false likelihoods; no generation',
        'same_val_optimism':True,'same_training_origin_canary':True,'single_seed':0,
        'license':receipt['license'],'original_qwen_service_script':str(SERVICE_SCRIPT),
        'service_script_sha256':sha(SERVICE_SCRIPT),'Qwen_physical_GPU':0,'judge_physical_GPU':3})
    bindings[str(OUT/'deployment_parameters.json')]=sha(OUT/'deployment_parameters.json')
    f={'time':now(),'stage':'CPU_ready','pre_change_github_commit':PRE_COMMIT,
        'source_sha256':bindings,'protected_sha256':history,'test_stat_only':before,
        'test_opened':False,'new_GPU_calls':0,'canary_arms':ARMS,
        'stop_loss':'Immediately stop all arms if completed same-ID paired function Top5 delta < -0.03 in either arm; incomplete is NA',
        'threshold_tuning_after_canary':False,'protocol_sha256':core_sha}
    write(OUT/'freeze.json',f);verify();assert test_stats()==before
    status(OUT/'status.json',{'time':now(),'stage':'CPU_ready','all20_input_parity_passed':True,'off_reuse20_checked':True,'test_opened':False})
    print({'CPU_ready':True,'temperature':temperature,'low_star':low},flush=True)


if __name__=='__main__':run()
