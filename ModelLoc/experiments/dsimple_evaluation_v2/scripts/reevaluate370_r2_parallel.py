"""Uniform offline r2 evaluation of external100 and all Lite270; no APIs."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['OMP_NUM_THREADS']='1'
import concurrent.futures,collections,json,re,sys
from pathlib import Path
sys.path.insert(0,'/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_evaluation_v2')
from dsimple_v2 import gold
E=gold.ROOT/'evaluator_private/eval_v2'
H=E/'_history/r1_declared_coordinates_20261022'


def one(row):
    cohort,iid=row['evaluation_cohort'],row['instance_id']
    result=gold.evaluate_case(row['job'],row['private_row'],E/cohort/iid,row.get('v1_gold'))
    return {'cohort':cohort,'instance_id':iid,'status':result['status'],'target_n':len(result['existing_function_targets']),'errors':result['errors']}


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--execute-frozen',action='store_true');args=parser.parse_args()
    if not args.execute_frozen:raise RuntimeError('Explicit frozen CPU execution flag required')
    if gold.EVALUATION_REVISION!='r2_exact_context_offsets':raise RuntimeError('Wrong revision')
    manifests={c:gold.ROOT/'manifests'/f'{c}.json'for c in ('external100','lite270')}
    frozen={str(p):gold.digest(p.read_bytes())for p in manifests.values()}
    source_sha=gold.digest(Path(gold.__file__).read_bytes());rows=[]
    for c,n in [('external100',100),('lite270',270)]:
        part=gold.read_json(manifests[c])['records']
        if len(part)!=n or len({r['instance_id']for r in part})!=n:raise RuntimeError('Allocation mismatch')
        for row in part:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+',row['instance_id'])or row['instance_id']in('.','..'):raise RuntimeError('Unsafe ID')
            if not (H/c/row['instance_id']/'gold_v2.json').is_file():raise RuntimeError('Missing immutable r1 snapshot')
            rows.append({**row,'evaluation_cohort':c})
    ordered=sorted(rows,key=lambda r:(-sum(p.endswith('.py')for p in gold.read_json(r['job'])['paths']),r['evaluation_cohort'],r['instance_id']))
    done=[];fail=[];started=gold.utc()
    def progress(status='RUNNING'):
        gold.write_json(E/'r2_progress.json',{'status':status,'revision':gold.EVALUATION_REVISION,'pid':os.getpid(),'workers':4,'GPU_used':False,'API_called':False,'started_utc':started,'updated_utc':gold.utc(),'allocated_n':370,'completed_n':len(done),'failed_n':len(fail),'manifest_sha256':frozen,'gold_module_sha256':source_sha,'cases':done,'failures':fail})
    progress()
    with concurrent.futures.ProcessPoolExecutor(max_workers=4)as pool:
        jobs={pool.submit(one,row):(row['evaluation_cohort'],row['instance_id'])for row in ordered}
        for future in concurrent.futures.as_completed(jobs):
            key=jobs[future]
            try:result=future.result();done.append(result);print(json.dumps(result),flush=True)
            except Exception as error:fail.append({'cohort':key[0],'instance_id':key[1],'type':type(error).__name__,'message':str(error)})
            progress()
    if fail:raise RuntimeError('Unexpected CPU failures; cases retained and no final summary')
    if gold.digest(Path(gold.__file__).read_bytes())!=source_sha or any(gold.digest(Path(p).read_bytes())!=sha for p,sha in frozen.items()):raise RuntimeError('Frozen code or manifest changed')
    bycohort=collections.defaultdict(list);changes=[];equivalence=[];offsets=[]
    for row in rows:
        c,iid=row['evaluation_cohort'],row['instance_id'];base=E/c/iid;result=gold.read_json(base/'gold_v2.json');before=gold.read_json(H/c/iid/'gold_v2.json');job=gold.read_json(row['job']);private=gold.read_json(row['private_row'])
        if result['evaluation_revision']!=gold.EVALUATION_REVISION or any(result[k]!=job[k]for k in ('instance_id','repo','base_commit'))or result['instance_id']!=iid:raise RuntimeError('Revision/identity binding failed')
        if result['job_sha256']!=gold.digest(Path(row['job']).read_bytes())or result['production_patch_sha256']!=gold.digest(private['patch']):raise RuntimeError('Job/production patch binding failed')
        index=gold.read_json(result['code_index_v2_path'])
        for identity in result['existing_function_targets']:
            path,qn=identity.split('::',1)
            if not gold.source_file(path)or not any(d['kind']=='function'and d['qualified_name']==qn for d in index.get(path,{}).get('definitions',[])):raise RuntimeError('Target absent from full base AST')
        placed=[{'cohort':c,'instance_id':iid,'path':f['path'],**p}for f in result['file_evidence']for p in f.get('hunk_placements',[])]
        nonzero=[p for p in placed if p['offset_lines']];offsets.extend(nonzero)
        difference={'cohort':c,'instance_id':iid,'before_status':before['status'],'after_status':result['status'],'added_targets':sorted(set(result['existing_function_targets'])-set(before['existing_function_targets'])),'removed_targets':sorted(set(before['existing_function_targets'])-set(result['existing_function_targets'])),'actual_nonzero_offsets':nonzero,'r1_gold':str(H/c/iid/'gold_v2.json'),'r2_gold':str(base/'gold_v2.json')}
        if before['status']!=result['status']or difference['added_targets']or difference['removed_targets']:changes.append(difference)
        if not nonzero:
            fields=('status','existing_function_targets','gold_files','changed_line_evidence','scope_exempt_changes','errors')
            mismatch=[k for k in fields if before[k]!=result[k]]
            index_equal=gold.digest((H/c/iid/'code_index_v2.json').read_bytes())==gold.digest((base/'code_index_v2.json').read_bytes())
            evidence_ok=True
            for oldpath in (H/c/iid/'evidence').glob('*.json'):
                newpath=base/'evidence'/oldpath.name
                old=gold.read_json(oldpath);new=gold.read_json(newpath)
                for field in ('targets','fixed_sha256','unchanged_line_map','changed_line_evidence','scope_exempt_changes','errors'):
                    if old.get(field)!=new.get(field):evidence_ok=False
            check={'cohort':c,'instance_id':iid,'changed_gold_fields':mismatch,'base_index_byte_equal':index_equal,'fixed_text_linemap_and_owner_evidence_equal':evidence_ok}
            equivalence.append(check)
            if mismatch or not index_equal or not evidence_ok:raise RuntimeError('Zero-offset equivalence failed: '+c+'/'+iid)
        result['origin']=row.get('origin');bycohort[c].append(result)
    for c,results in bycohort.items():
        summary={'schema_version':2,'policy_version':gold.POLICY,'evaluation_revision':gold.EVALUATION_REVISION,'generated_utc':gold.utc(),'cohort':c,'descriptor_path':str(manifests[c]),'descriptor_sha256':frozen[str(manifests[c])],'allocated_n':len(results),'statuses':dict(collections.Counter(r['status']for r in results)),'v1_statuses':dict(collections.Counter(r['v1_mapping_status']for r in results)),'existing_function_identity_count':sum(len(r['existing_function_targets'])for r in results),'v1_to_v2_changed_issues':[r['instance_id']for r in results if r['v1_to_v2_added']or r['v1_to_v2_removed']],'records':[{'instance_id':r['instance_id'],'origin':r['origin'],'status':r['status'],'v1_mapping_status':r['v1_mapping_status'],'target_n':len(r['existing_function_targets']),'added':r['v1_to_v2_added'],'removed':r['v1_to_v2_removed'],'errors':r['errors'],'gold_v2':str(E/c/r['instance_id']/'gold_v2.json'),'code_index_v2':r['code_index_v2_path']}for r in results],'model_or_API_called':False,'old_gold_or_prediction_changed':False,'r1_snapshot':str(H),'uniform_370_revision_receipt':str(E/'r2_revision_comparison.json')}
        gold.write_json(E/c/'mapping_summary.json',summary)
    comparison={'revision':gold.EVALUATION_REVISION,'generated_utc':gold.utc(),'all_370_recomputed':True,'allocated_n':370,'workers':4,'GPU_used':False,'API_called':False,'manifest_sha256':frozen,'gold_module_sha256':source_sha,'r1_snapshot':str(H),'zero_offset_equivalence_cases':len(equivalence),'zero_offset_equivalence_checks':equivalence,'changed_case_count':len(changes),'changes':changes,'nonzero_hunk_count':len(offsets),'actual_offsets':offsets,'cohort_statuses':{c:dict(collections.Counter(r['status']for r in rs))for c,rs in bycohort.items()}}
    gold.write_json(E/'r2_revision_comparison.json',comparison);progress('COMPLETE');print(json.dumps({'complete370':True,'statuses':comparison['cohort_statuses'],'changed_cases':len(changes),'zero_offset_equivalent':len(equivalence)}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        gold.write_json(E/'r2_failure.json',{'status':'FAILED','pid':os.getpid(),'utc':gold.utc(),'type':type(error).__name__,'message':str(error),'API_called':False})
        raise
