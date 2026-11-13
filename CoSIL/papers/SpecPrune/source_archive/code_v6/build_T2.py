"""Rebuild train/val only from reviewed C; reuse strict runtime evidence and labels."""
from collections import Counter,defaultdict
import csv
import hashlib
import json
from pathlib import Path

from code_v5.metrics import _sources
from code_v5.verify_review_evidence import source_file
from code_v5.runtime_filtered_policy import assess_result,official_runtime_metadata
from code_v5_verified.expanded_policy import assess_new_result
from code_v6.audit_visibility import neighbor_preview,edge_key,line_span
from code_v6.common import ROOT,BASE,OUT,DOCS,COHORTS,read,rows,sha,digest,write,status,now,test_stats,verify_files,pair
from code_v6.input_format import *

TARGET=OUT/'T2_dataset_v6'

def category(r):
    sources=_sources(r)
    if r['label']:
        if sources&{'A','B'}:return 'gold_AB'
        if 'C' in sources:return 'C_positive'
    else:
        if sources&{'e_log','e_bm25','e_anchor'}:return 'E_negative'
        if sources=={'D'}:return 'D_only_negative'
    raise ValueError('Unspecified source group: '+str(sources))

def distribution(rr,weighted=False):
    mass=Counter()
    for r in rr:mass[category(r)]+=r['sample_weight'] if weighted else 1
    positive=mass['gold_AB']+mass['C_positive'];negative=mass['E_negative']+mass['D_only_negative']
    return {'mass':dict(mass),'gold_AB_within_positive':mass['gold_AB']/positive,
            'C_within_positive':mass['C_positive']/positive,'D_only_within_negative':mass['D_only_negative']/negative,
            'positive_fraction':positive/(positive+negative)}

def write_jsonl(path,rr):
    with path.open('x') as f:
        for r in rr:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')

def run():
    auth=read(OUT/'user_execution_authorization.json');assert auth['T2_allowed'] and not auth['test_open_allowed'] and not auth['T3_allowed']
    TARGET.mkdir(parents=True,exist_ok=False)
    test_before=test_stats();history=read(OUT/'T0_visibility/start_receipt.json')['historical_sha256'];verify_files(history)
    source=COHORTS['C'];split_manifest=read(source/'split_manifest.json');splits=split_manifest['splits']
    assert not set(splits['train'])&set(splits['val']) and not (set(splits['train'])|set(splits['val']))&set(splits['test'])
    paths=[Path(__file__),ROOT/'code_v6/input_format.py',ROOT/'code_v6/common.py',ROOT/'code_v6/qualification.py',
       ROOT/'code_v6/audit_visibility.py',ROOT/'code_v5/verify_review_evidence.py',ROOT/'code_v5/runtime_filtered_policy.py',ROOT/'code_v5_verified/expanded_policy.py',
       OUT/'user_execution_authorization.json',OUT/'T0_visibility/audit.json',OUT/'T0_Qwen_anchor/anchor.json']
    paths += [source/n for n in ['pruner_train.jsonl','pruner_val.jsonl','split_manifest.json','reviewed_train_derivation.json','human_review_codex_reviewed.jsonl','runtime_manifest.json']]
    paths += [COHORTS['B']/n for n in ['pruner_train.jsonl','pruner_val.jsonl','reviewed_train_derivation.json']]
    paths += [ROOT/'ground_truth_300.json',BASE/'runtime_coverage_verified_v1/input_audit/verified_gold_files_index.json',
              ROOT.parent/'GraphLocator/datasets/swe_bench_lite.jsonl',BASE/'external_sources/verified_official/verified500_full_metadata.jsonl']
    bindings={str(p):sha(p) for p in paths}
    raw={s:rows(source/f'pruner_{s}.jsonl') for s in ['train','val']}
    all_ids={r['instance_id'] for rr in raw.values() for r in rr}
    lite_metadata,lite_receipt=official_runtime_metadata()
    bindings.update(lite_receipt['file_sha256'])
    official={iid:r for iid,r in lite_metadata.items() if iid in all_ids}
    for p in [ROOT.parent/'GraphLocator/datasets/swe_bench_lite.jsonl',BASE/'external_sources/verified_official/verified500_full_metadata.jsonl']:
        for r in rows(p):
            iid=r['instance_id']
            if iid in all_ids:
                old=official.setdefault(iid,r)
                assert all(old[k]==r[k] for k in ['repo','base_commit','problem_statement'])
                if 'test_patch' in r:assert old['test_patch']==r['test_patch']
    assert all_ids==set(official)
    lite_gold=read(ROOT/'ground_truth_300.json')
    verified_gold=read(BASE/'runtime_coverage_verified_v1/input_audit/verified_gold_files_index.json')['gold_files_index']
    masks={tuple(t[:2]) for t in read(source/'reviewed_train_derivation.json')['excluded_training_pairs']}
    masks|={pair(r) for r in read(COHORTS['B']/'reviewed_train_derivation.json')['removed_train_errors']}
    selected={s:[] for s in raw};excluded={s:[] for s in raw};runtime_bindings={};runtime_cache={}
    write(TARGET/'start_receipt.json',{'started_at':now(),'source_sha256':bindings,'test_stat_only':test_before,
         'historical_sha256':history,'training_started':False,'new_model_calls':0,'labels_changed':0,
         'authoritative_pool':'reviewed C; do not restore six B rows already removed by later C review'})
    for split,rr in raw.items():
        assert len({pair(r) for r in rr})==len(rr)
        for r in rr:
            iid=r['instance_id'];assert r['split']==split and iid in splits[split] and pair(r) not in masks
            assert type(r['label']) is bool
            issue=official[iid];assert (issue['repo'],issue['base_commit'],issue['problem_statement'][:2000])==(r['repo'],r['base_commit'],r['issue'])
            if r['label']:selected[split].append(r);continue
            rf=r['runtime_filter']
            if not rf['qualified']:
                excluded[split].append({**r,'v6_exclusion_reason':'pure_static_runtime_unavailable_not_training_or_validation'});continue
            assert rf['static_v3_eligible'] is True and rf['eligibility_basis']=='static_and_runtime_absent' and rf['status']=='runtime_qualified'
            rp=Path(rf['result_path']);key=str(rp)
            if key not in runtime_cache:
                assert sha(rp)==rf['result_sha256'];v=read(rp)
                if iid in lite_gold:gt=lite_gold[iid]
                else:
                    g=verified_gold[iid];assert sha(g['path'])==g['sha256'];bindings[g['path']]=g['sha256'];gt=read(g['path'])
                a=(assess_result if iid in lite_gold else assess_new_result)(v,rp,issue,gt)
                if not a['qualified']:raise ValueError('Runtime requalification failed '+iid+': '+str(a['unavailable_reasons']))
                runtime_cache[key]=(v,a)
                runtime_bindings[key]=rf['result_sha256']
                for t in v['trace_files']:runtime_bindings[t['path']]=t['sha256']
            v,a=runtime_cache[key]
            assert a['result_sha256']==rf['result_sha256'] and a['input_fingerprint']==rf['input_fingerprint']
            assert r['function_id'] not in a['covered'] and r['function_file'] not in v.get('runtime_unavailable_function_files',[])
            selected[split].append(r)
    for split in raw:write_jsonl(TARGET/f'archived_static_fallback_{split}.jsonl',excluded[split])
    write(TARGET/'eligibility_audit.json',{'input_counts':{s:len(rr) for s,rr in raw.items()},
        'selected_counts':{s:len(rr) for s,rr in selected.items()},'static_fallback_archived':{s:len(rr) for s,rr in excluded.items()},
        'known_review_error_mask_count':len(masks),'restored_review_errors':0,
        'runtime_result_count':len(runtime_cache),'runtime_artifact_sha256':runtime_bindings,'full_assess_result_replayed':True,
        'runtime_absence_proves_causal_irrelevance':False,'new_runtime_tests':0,'new_labels':0})
    print(json.dumps({'time':now(),'stage':'runtime_requalification_complete','issues':len(runtime_cache),'pairs':{s:len(rr) for s,rr in selected.items()}}),flush=True)
    from transformers import AutoTokenizer
    tokenizers={
       'Qwen3-Reranker-0.6B':(AutoTokenizer.from_pretrained(ROOT/'models_v5/Qwen3-Reranker-0.6B',local_files_only=True),'reranker'),
       'Qwen2.5-Coder-7B-Instruct':(AutoTokenizer.from_pretrained('/home/wdt/models/qwen25coder7b',local_files_only=True),'instruct')}
    tokenizer_hashes={}
    for name,(tok,_) in tokenizers.items():
        path=Path(tok.name_or_path)
        tokenizer_hashes[name]={str(p):sha(p) for p in sorted(path.glob('*')) if p.is_file() and (p.suffix=='.json' or p.name in {'merges.txt','vocab.json'})}
    grouped=defaultdict(list)
    for split,rr in selected.items():
        for r in rr:grouped[r['instance_id']].append((split,r))
    output={s:[] for s in selected};visibility=[];graph_bindings={};blob_bindings={}
    for i,(iid,members) in enumerate(sorted(grouped.items()),1):
        first=members[0][1];gp=Path(first['graph']['graph_path']);assert sha(gp)==first['graph']['graph_sha256'];graph=read(gp)
        assert (graph['instance_id'],graph['repo'],graph['base_commit'])==(iid,first['repo'],first['base_commit'])
        graph_bindings[str(gp)]=first['graph']['graph_sha256'];funcs={f['id']:f for f in graph['functions']}
        cache={};hydrated={}
        class FullFunctions:
            def __getitem__(self,fid):
                if fid not in hydrated:
                    node=funcs[fid];text,definitions,blob,matched=source_file(graph,node['file'],cache)
                    assert matched and definitions[node['qualified_name'],node['def_line']]==node['end_line']
                    full=''.join(text.splitlines(keepends=True)[node['start_line']-1:node['end_line']])
                    assert digest(full)==node['source_sha256'] and len(full)==node['source_characters'] and full[:len(node['source'])]==node['source']
                    hydrated[fid]={**node,'source':full,'git_blob_sha1':blob}
                    blob_bindings[f'{iid}:{node["file"]}']=blob
                return hydrated[fid]
        ff=FullFunctions();incoming=defaultdict(list);outgoing=defaultdict(list)
        for e in graph['edges']:incoming[e['callee']].append(e);outgoing[e['caller']].append(e)
        edges={edge_key(e) for e in graph['edges']}
        for split,r in members:
            fn=ff[r['function_id']];assert digest(fn['source'])==r['full_function_source_sha256'] and fn['source'][:1500]==r['function']
            summary,chosen=neighbor_preview(fn['id'],incoming[fn['id']],outgoing[fn['id']],ff,NEIGHBORS_PER_DIRECTION)
            fitted=fit_input(tokenizers,official[iid]['problem_statement'],fn['source'],summary)
            assert fitted['issue'][:2000]==r['issue'] and fitted['function'][:1500]==r['function']
            new={**r,**fitted,'legacy_input_sha256':r['input_sha256'],'input_sha256':digest(fitted['model_input']),
                 'distribution_group':category(r),'source_cohort':'reviewed_C','sample_weight':1.0,
                 'source_provenance':{'legacy_data_file':str(source/f'pruner_{split}.jsonl'),
                     'legacy_data_sha256':bindings[str(source/f'pruner_{split}.jsonl')],'git_blob_sha1':fn['git_blob_sha1']}}
            output[split].append(new)
            if r['label'] and 'C' in _sources(r):
                witnesses={edge_key(e):e for p in r['provenance'] if p['source']=='C' for e in p['one_hop_call_edges']}
                assert witnesses and all(k in edges for k in witnesses)
                own=any(e['caller']==fn['id'] and line_span(fn,e['line'])['line_end_char']<=len(fitted['function']) for e in witnesses.values())
                # neighbor_preview lines and chosen edges have the same insertion order.
                all_lines=summary.splitlines()[1:];kept=set(fitted['neighbors'].splitlines()[1:])
                selected_edges=[]
                for direction,ee in [('caller',incoming[fn['id']]),('callee',outgoing[fn['id']])]:
                    seen=set()
                    for e in sorted(ee,key=lambda x:(x[direction],x['file'],x['line'],x.get('column',0))):
                        if e[direction] in seen:continue
                        seen.add(e[direction])
                        if len(seen)>NEIGHBORS_PER_DIRECTION:break
                        selected_edges.append(e)
                assert len(all_lines)==len(selected_edges)
                visible_keys={edge_key(e) for e,line in zip(selected_edges,all_lines) if line in kept}
                neighbor=bool(visible_keys&set(witnesses))
                visibility.append({'split':split,'instance_id':iid,'function_id':fn['id'],'own_call_line_visible':own,
                    'witness_in_rendered_neighbor_line':neighbor,'any_evidence_visible':own or neighbor,
                    'function_chars':len(fitted['function']),'neighbor_chars':len(fitted['neighbors']),
                    'full_neighbor_chars':len(summary),'token_budget_trimmed':fitted['token_budget_trimmed']})
        if i%10==0 or i==len(grouped):
            x={'time':now(),'stage':'materializing_inputs','issues_completed':i,'issues_total':len(grouped),'pairs_completed':sum(len(rr) for rr in output.values())}
            status(TARGET/'status.json',x);print(json.dumps(x),flush=True)
    # Check canonical exact input collisions, without opening sealed test.
    index=defaultdict(list)
    for split,rr in output.items():
        for r in rr:index[r['input_sha256']].append((split,r))
    removed=[];bad=set()
    for h,rr in index.items():
        if len(rr)>1:
            labels={r['label'] for _,r in rr};sp={s for s,_ in rr}
            # A conflict cannot be resolved by relabeling; drop the whole group.
            keep=rr if len(labels)>1 else [(s,r) for s,r in rr if s=='train'] if len(sp)>1 else rr[1:]
            for s,r in keep:bad.add((s,*pair(r)));removed.append({'split':s,'instance_id':r['instance_id'],'function_id':r['function_id'],'input_sha256':h,'reason':'conflicting_labels' if len(labels)>1 else 'cross_split_exact_input' if len(sp)>1 else 'within_split_duplicate'})
    for split in output:output[split]=[r for r in output[split] if (split,*pair(r)) not in bad]
    mass=Counter(category(r) for r in output['train']);valmass=Counter(category(r) for r in output['val'])
    total=len(output['train']);valP=valmass['gold_AB']+valmass['C_positive'];valN=valmass['E_negative']+valmass['D_only_negative']
    weights={g:total*(1/3 if g in ['gold_AB','C_positive'] else 2/3)*valmass[g]/(valP if g in ['gold_AB','C_positive'] else valN)/mass[g] for g in mass}
    for r in output['train']:r['sample_weight']=weights[category(r)]
    assert abs(sum(r['sample_weight'] for r in output['train'])-total)<1e-6
    dtrain=distribution(output['train']);dw=distribution(output['train'],True);dv=distribution(output['val'])
    gaps={k:abs(dw[k]-dv[k]) for k in ['gold_AB_within_positive','C_within_positive','D_only_within_negative']}
    assert all(v<=.10000001 for v in gaps.values())
    assert len({r['input_sha256'] for r in output['train']+output['val']})==len(output['train'])+len(output['val'])
    for split in output:
        for r in output[split]:
            assert_v6_row(r);assert type(r['label']) is bool
            old=next(x for x in raw[split] if pair(x)==pair(r));assert r['label']==old['label']
        write_jsonl(TARGET/f'pruner_{split}.jsonl',sorted(output[split],key=pair))
    write_jsonl(TARGET/'C_rendered_visibility.jsonl',visibility)
    write(TARGET/'split_manifest.json',split_manifest)
    write(TARGET/'deduplication_audit.json',{'exact_train_val_input_duplicates_after':0,'removed':removed,'test_contents_checked':False,
         'test_protection':'instance_id split unchanged; both old text prefixes preserved; inherited prior cross-split exact-input gate. No new test scan or test semantic-near-duplicate certification.'})
    statistics={'completed_at':now(),'pairs':{s:len(rr) for s,rr in output.items()},
         'issues':{s:len({r['instance_id'] for r in rr}) for s,rr in output.items()},
         'raw_distribution':dtrain,'weighted_training_distribution':dw,'validation_distribution':dv,
         'alignment_absolute_gaps':gaps,'alignment_gate_passed':all(v<=.1 for v in gaps.values()),'training_weights':weights,
         'weight_policy':'Mean train sample weight 1; preserve P:N=1:2 by weighted mass; match val gold/C and E/D shares within label. Every eligible train pair retained unless exact-input collision. Val unweighted.',
         'raw_three_alignment_gate_passed':all(abs(dtrain[k]-dv[k])<=.1 for k in gaps),
         'input_recipe':{'input_version':INPUT_VERSION,'issue_chars':ISSUE_CHARS,'function_chars':FUNCTION_CHARS,'neighbors_each_direction':NEIGHBORS_PER_DIRECTION,'neighbor_chars':SUMMARY_CHARS,'token_cutoff':TOKEN_CUTOFF,'body_token_budget':BODY_BUDGET},
         'C_visibility':{s:{'rows':sum(v['split']==s for v in visibility),'visible':sum(v['split']==s and v['any_evidence_visible'] for v in visibility)} for s in output},
         'token_budget_trimmed_pairs':sum(r['token_budget_trimmed'] for rr in output.values() for r in rr),
         'actual_max_prompt_tokens':{name:max(r['token_counts'][name]['native_prompt'] for rr in output.values() for r in rr) for name in tokenizers},
         'labels_changed':0,'new_model_calls':0,'training_started':False,'test_opened':False,'qualification_passed':None,
         'fresh_30_review_performed':False,'semantic_cleanliness_claimed':False,'static_fallback_archived':{s:len(rr) for s,rr in excluded.items()}}
    write(TARGET/'statistics.json',statistics)
    from code_v6.qualification import protocol
    write(TARGET/'qualification_protocol.json',protocol())
    allbind={**bindings,**runtime_bindings,**graph_bindings}
    write(TARGET/'provenance.json',{'source_sha256':allbind,'tokenizer_sha256':tokenizer_hashes,'base_blob_sha1':blob_bindings,
           'parent_review_masks_preserved':True,'test_stat_only':test_before,'historical_sha256':history})
    verify_files(allbind);verify_files(history)
    for x in tokenizer_hashes.values():verify_files(x)
    assert test_stats()==test_before
    artifacts={str(p):sha(p) for p in sorted(TARGET.glob('*')) if p.is_file() and p.name!='status.json'}
    write(TARGET/'freeze_manifest.json',{'frozen_at':now(),'artifacts_sha256':artifacts,'test_contents_decoded_or_hashed':False,
          'T3_started':False,'awaiting_user_confirmation_of_T2':True,'historical_files_unchanged':True})
    status(TARGET/'status.json',{'stage':'frozen_awaiting_T2_confirmation','time':now(),'training_started':False,'test_opened':False})
    print(json.dumps({'stage':'T2_frozen','statistics':statistics},ensure_ascii=False),flush=True)

if __name__=='__main__':run()
