"""T1 CPU preparation only: fixed B checkpoint, temperature and safe 20-ID sample.

Does not load a model, start/stop vLLM, decode test, or run any issue pipeline.
"""
from collections import Counter
import hashlib
import json
import math

from code_v5.metrics import fit_temperature, apply_temperature, _sources
from code_v5_runtime.race_and_calibrate import load_candidate, routing_risks
from code_v5.run_pipeline import inference_core
from code_v6.common import (ROOT,BASE,OUT,DOCS,INSTRUCTION,COHORTS,read,rows,write,sha,
                            now,test_stats,historical_files,verify_files,pair)


def run():
    target=OUT/'T1_canary_preparation';target.mkdir(parents=True,exist_ok=False)
    before_tests=test_stats();history=historical_files()
    data=COHORTS['B'];truth={pair(r):r for r in rows(data/'pruner_val.jsonl')}
    run_dir=BASE/'B_runtime_reviewed_regularized_exploratory/training/reranker'
    candidate=load_candidate(run_dir,'reranker',data_seal_sha=sha(data/'test_file_seal.json'),val_truth=truth,track='exploratory')
    assert candidate['best_epoch']==1
    manifest=read(run_dir/'training_manifest.json')
    assert (manifest['rank'],manifest['dropout'])==(8,.1)
    calibration=fit_temperature(candidate['predictions'],split='val')
    calibrated=apply_temperature(candidate['predictions'],calibration['temperature'])
    risks=routing_risks(calibrated,low=.6,high=.9)
    write(target/'val_temperature_calibration.json',calibration)
    write(target/'val_fixed_route_risks.json',risks)
    splits=read(data/'split_manifest.json')['splits']
    sealed_issues=set(splits['test'])
    allowed_issues=set(splits['train'])|set(splits['val'])
    metrics=read(ROOT/'results/qwen_300/metrics.json')
    cases=metrics['cases']['off'];assert len(cases)==300
    full_groups=Counter(r['anchor'] for r in cases)
    # Primary issue Top5 requires function gold. Never run held-out test issues.
    eligible=[r for r in cases if r['instance_id'] in allowed_issues and r['function_scorable']]
    quota={k:math.floor(20*v/300) for k,v in full_groups.items()}
    while sum(quota.values())<20:
        best=max(quota,key=lambda k:(20*full_groups[k]/300-quota[k],k));quota[best]+=1
    seed=20261016
    key=lambda iid:hashlib.sha256(f'{seed}:{iid}'.encode()).hexdigest()
    selected=[]
    for group,n in sorted(quota.items()):
        values=sorted([r for r in eligible if r['anchor']==group],key=lambda r:key(r['instance_id']))
        assert len(values)>=n
        selected.extend(values[:n])
    selected.sort(key=lambda r:key(r['instance_id']))
    assert len(selected)==20 and not {r['instance_id'] for r in selected}&sealed_issues
    core,core_sha=inference_core()
    prepared=read(ROOT/'results/qwen_300/prepared_inputs.json')
    bindings={str(INSTRUCTION):sha(INSTRUCTION),str(run_dir/'training_manifest.json'):sha(run_dir/'training_manifest.json'),
              str(run_dir/'training_summary.json'):sha(run_dir/'training_summary.json'),
              str(data/'pruner_val.jsonl'):sha(data/'pruner_val.jsonl'),
              str(data/'split_manifest.json'):sha(data/'split_manifest.json'),
              str(ROOT/'results/qwen_300/prepared_inputs.json'):sha(ROOT/'results/qwen_300/prepared_inputs.json'),
              str(ROOT/'results/qwen_300/metrics.json'):sha(ROOT/'results/qwen_300/metrics.json')}
    bindings.update({str(ROOT/name):h for name,h in core['original_sha256'].items()})
    records=[]
    for case in selected:
        iid=case['instance_id'];path=ROOT/f'results/qwen_300/fixed/off/cases/{iid}.json'
        old=read(path)
        if (old.get('protocol')!=prepared['configuration']['protocol'] or old.get('status')!='complete'
                or old['found_files']!=prepared['candidates'][iid]):
            raise RuntimeError('Historical off protocol mismatch; reuse not allowed: '+iid)
        bindings[str(path)]=sha(path)
        event_path=ROOT/f'results/qwen_300/fixed/off/events/off_{iid}.jsonl'
        bindings[str(event_path)]=sha(event_path)
        # Labels/scores in this analysis ledger must never enter worker payloads.
        records.append({'instance_id':iid,'anchor':case['anchor'],'historical_off_case':str(path),
                        'historical_off_events':str(event_path),'historical_off_top5':case['function_top5'],
                        'source_split':'train' if iid in splits['train'] else 'val','off_reuse_protocol_checked':True})
    write(target/'sampling_manifest.json',{'seed':seed,'method':'SHA256(seed:instance_id), stratified largest remainder',
        'full300_strata':dict(full_groups),'quota':quota,'sample_count':20,
        'eligible_count':len(eligible),'excluded_test_issue_count':len(sealed_issues),
        'exclusion_reason':'No inference on sealed pruner test issues; primary Top5 denominator requires function_scorable',
        'selected_issue_ids':[r['instance_id'] for r in records], 'analysis_only_records':records})
    write(target/'protocol.json',{'created_at':now(),'scope':'T1_canary_only_user_authorized_20261016',
        'pipeline_execution_started':False,'new_model_calls':0,'test_open_allowed':False,
        'T2_or_T3_allowed':False,'new_training_allowed':False,'canary_arms':['off','hybrid','small'],
        'runs':60,'off_policy':'reuse protocol-consistent historical off20; no new Qwen baseline300',
        'model_kind':'Qwen3-Reranker-0.6B rank8/dropout0.1 B reviewed runtime-filtered',
        'adapter_dir':candidate['adapter_dir'],'best_epoch':1,'model_dir':candidate['model_dir'],
        'temperature':calibration['temperature'],'low':.6,'high':.9,
        'class_policy_from_original_function_only_integration':core['class_policy'],
        'small_function_verdict_threshold':.5,'full300_baseline_reference':{'hits':111,'denominator':293},
        'paired_primary_comparator':'same20 historical off, joined by instance_id; 111/293 is context only',
        'McNemar':'exact paired two-sided discordant issue test; nonsignificance is not proof of noninferiority',
        'stop_loss':'stop if completed matched-pair Top5 delta below -0.03 for either new arm; incomplete cases remain NA',
        'noninferiority_margin':.03,'single_seed':seed,'statistics_power_warning':'20 cases have 5pp resolution and cannot generally certify a 3pp noninferiority margin',
        'calibration_and_route_report_use_same_val':True,'canary_same_Lite300_origin_as_training':True,
        'gray_zone_results_never_imputed':True,'all_gray_fallback_limit':'Exact baseline equivalence only if every function decision is routed to Qwen; fixed low/high is not a guaranteed safety lower bound.',
        'original_inference_core':core,'original_inference_core_sha256':core_sha,
        'source_sha256':bindings,'formal_winner_published':False})
    verify_files(bindings);verify_files(history);assert test_stats()==before_tests
    result={'prepared_at':now(),'stage':'prepared_not_executed','sampling_manifest':str(target/'sampling_manifest.json'),
        'temperature':calibration['temperature'],'fixed_route_gold_direct_reject':risks['gold_direct_rejection_fraction'],
        'val_route_risks':risks,'test_decoded_or_hashed':False,'models_loaded':False,
        'blocker_to_check':'Original local Qwen7333 service was deliberately stopped earlier; do not restart/change vLLM under this instruction without resolving the explicit do-not-touch constraint.'}
    write(target/'preparation_receipt.json',result)
    print(json.dumps({'prepared_not_executed':True,'temperature':calibration['temperature'],
                      'val_route_risks':risks,'sampled_strata':quota},ensure_ascii=False))
    return result


if __name__=='__main__':run()
