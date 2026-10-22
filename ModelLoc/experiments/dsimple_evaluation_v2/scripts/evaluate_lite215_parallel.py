"""Run only after root confirms final lite215/lite270 manifests are frozen."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'
import concurrent.futures
import collections
import hashlib
import json
from pathlib import Path
import sys
import re
sys.path.insert(0,'/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_evaluation_v2')
from dsimple_v2 import gold


def one(row):
    iid=row['instance_id']
    result=gold.evaluate_case(row['job'],row['private_row'],gold.ROOT/'evaluator_private/eval_v2/lite270'/iid,row.get('v1_gold'))
    return {'instance_id':iid,'status':result['status'],'target_n':len(result['existing_function_targets']),'errors':result['errors']}


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--execute-frozen',action='store_true');args=parser.parse_args()
    if not args.execute_frozen:
        raise SystemExit('Dry-run only: requires explicit --execute-frozen after root freeze notification')
    newpath=gold.ROOT/'manifests/lite215.json';allpath=gold.ROOT/'manifests/lite270.json'
    before={str(p):gold.digest(p.read_bytes())for p in (newpath,allpath)}
    new=gold.read_json(newpath)['records'];allrows=gold.read_json(allpath)['records']
    if len(new)!=215 or len(allrows)!=270:raise RuntimeError('Expected exact frozen 215/270 allocation')
    ids=[r['instance_id']for r in new];allids=[r['instance_id']for r in allrows]
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+',iid)or iid in ('.','..')for iid in allids):raise RuntimeError('Unsafe issue ID')
    code_sha=gold.digest(Path(gold.__file__).read_bytes())
    if len(set(ids))!=215 or len(set(allids))!=270 or not set(ids)<=set(allids):raise RuntimeError('Duplicate or mismatched cohort IDs')
    if any(r['origin']!='new215'for r in new):raise RuntimeError('Only new215 jobs may enter CPU workers')
    if {r['instance_id']for r in allrows if r['origin']=='new215'}!=set(ids):raise RuntimeError('215/270 origin disagreement')
    byid={r['instance_id']:r for r in allrows}
    for row in new:
        if any(row.get(k)!=byid[row['instance_id']].get(k)for k in ('job','private_row','v1_gold','result_dir','origin')):raise RuntimeError('Descriptor mismatch')
    ordered=sorted(new,key=lambda r:(-sum(p.endswith('.py')for p in gold.read_json(r['job'])['paths']),r.get('repo',''),r['instance_id']))
    done=[];failures=[];started=gold.utc()
    def progress(status='RUNNING'):
        gold.write_json(gold.ROOT/'evaluator_private/eval_v2/lite270/new215_parallel_progress.json',{'status':status,'started_utc':started,'updated_utc':gold.utc(),'pid':os.getpid(),'workers':4,'gpu_used':False,'API_called':False,'allocated_n':215,'completed_n':len(done),'failed_n':len(failures),'manifest_sha256':before,'gold_module_sha256':code_sha,'completed':done,'failures':failures})
    progress()
    with concurrent.futures.ProcessPoolExecutor(max_workers=4)as pool:
        futures={pool.submit(one,row):row['instance_id']for row in ordered}
        for future in concurrent.futures.as_completed(futures):
            iid=futures[future]
            try:
                result=future.result();done.append(result);print(json.dumps(result),flush=True)
            except Exception as error:
                failures.append({'instance_id':iid,'exception_type':type(error).__name__,'message':str(error)});print(json.dumps({'failed':iid,'type':type(error).__name__}),flush=True)
            progress()
    receipt={'schema_version':2,'new_allocated_n':215,'workers':4,'gpu_used':False,'API_called':False,'manifest_sha256_before':before,'gold_module_sha256':code_sha,'completed_cases':done,'worker_failures':failures}
    gold.write_json(gold.ROOT/'evaluator_private/eval_v2/lite270/new215_parallel_receipt.json',receipt)
    if failures:raise RuntimeError('Unexpected CPU failures retained; no complete270 summary written')
    if any(gold.digest(Path(p).read_bytes())!=sha for p,sha in before.items()):raise RuntimeError('Frozen manifest changed')
    if gold.digest(Path(gold.__file__).read_bytes())!=code_sha:raise RuntimeError('Gold module changed during frozen CPU evaluation')
    results=[]
    for row in allrows:
        iid=row['instance_id'];directory=gold.ROOT/'evaluator_private/eval_v2/lite270'/iid
        result=gold.read_json(directory/'gold_v2.json');job=gold.read_json(row['job']);private=gold.read_json(row['private_row'])
        if any(result[k]!=job[k]for k in ('instance_id','repo','base_commit'))or result['instance_id']!=iid:raise RuntimeError('Gold/job identity mismatch')
        if result['job_sha256']!=gold.digest(Path(row['job']).read_bytes())or result['production_patch_sha256']!=gold.digest(private['patch']):raise RuntimeError('Gold no longer binds frozen job/patch')
        index=gold.read_json(result['code_index_v2_path'])
        for identity in result['existing_function_targets']:
            path,qn=identity.split('::',1)
            if not gold.source_file(path)or not any(d['kind']=='function'and d['qualified_name']==qn for d in index.get(path,{}).get('definitions',[])):raise RuntimeError('Gold target absent from full v2 base index')
        result['origin']=row['origin'];results.append(result)
    summary={'schema_version':2,'policy_version':gold.POLICY,'generated_utc':gold.utc(),'cohort':'lite270','descriptor_path':str(allpath),'descriptor_sha256':before[str(allpath)],'allocated_n':270,'statuses':dict(collections.Counter(r['status']for r in results)),'v1_statuses':dict(collections.Counter(r['v1_mapping_status']for r in results)),'existing_function_identity_count':sum(len(r['existing_function_targets'])for r in results),'v1_to_v2_changed_issues':[r['instance_id']for r in results if r['v1_to_v2_added']or r['v1_to_v2_removed']],'records':[{'instance_id':r['instance_id'],'origin':r['origin'],'status':r['status'],'v1_mapping_status':r['v1_mapping_status'],'target_n':len(r['existing_function_targets']),'added':r['v1_to_v2_added'],'removed':r['v1_to_v2_removed'],'errors':r['errors'],'gold_v2':str(gold.ROOT/'evaluator_private/eval_v2/lite270'/r['instance_id']/'gold_v2.json'),'code_index_v2':r['code_index_v2_path']}for r in results],'model_or_API_called':False,'old_gold_or_prediction_changed':False,'new215_parallel_receipt':str(gold.ROOT/'evaluator_private/eval_v2/lite270/new215_parallel_receipt.json')}
    gold.write_json(gold.ROOT/'evaluator_private/eval_v2/lite270/mapping_summary.json',summary)
    progress('COMPLETE')
    print(json.dumps({'cohort':'lite270','allocated_n':270,'statuses':summary['statuses']}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        gold.write_json(gold.ROOT/'evaluator_private/eval_v2/lite270/new215_parallel_failure.json',{'status':'FAILED','updated_utc':gold.utc(),'pid':os.getpid(),'exception_type':type(error).__name__,'message':str(error),'gpu_used':False,'API_called':False})
        raise
