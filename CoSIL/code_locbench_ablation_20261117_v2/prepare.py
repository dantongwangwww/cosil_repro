"""CPU-only projection of frozen LocBench inputs and upstream file evidence.

This module never opens an evaluation Gold file, trains, downloads, calls a
model, or reconstructs a graph.  Historical prepared public files are copied
only after their original source and byte receipts pass validation.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil

from code_sfpruner300_20261114 import controller as c
from code_locbench_sfpruner_20261116 import pilot

ARMS=('ablation_no_lora','ablation_no_neighbors','ablation_no_defer')
SOURCE='czlll/Loc-Bench_V1'
REVISION='c44cf3b74e07ca642cec841b471a9939907c12a7'
PARQUET_SHA='8df0833c2c1276c5837aab923d489ab97d7654529abe759d0f59242c4978a662'
CLEAN_KEYS={'instance_id','repo','base_commit','problem_statement','cohort','snapshot','paths','code_index','structure'}
IDENTITY=('instance_id','repo','base_commit')
SHARED_KEYS={'instance_id','base_commit','files','raw_file_responses'}


def read(path):return c.read(Path(path))
def sha(path):return c.sha(Path(path))
def write(path,value):return c.write(Path(path),value,immutable=True)
def hash_key(row):return hashlib.sha256(('20261116:'+row['instance_id']).encode()).hexdigest(),row['instance_id']


def identity(value,row,label):
    if not isinstance(value,dict) or any(value.get(k)!=row[k] for k in IDENTITY):
        raise ValueError(label+' identity/base mismatch')


def shared_payload(result,row):
    """The unchanged historical file-stage eligibility rule and exact whitelist."""
    identity(result,row,'baseline result')
    if 'ranked_edit_files' not in result:return None
    if 'file_rank_after_reflection' not in result or 'raw_file_responses' not in result:
        raise ValueError('Successful file-stage marker lacks required raw evidence')
    files,responses=result['file_rank_after_reflection'],result['raw_file_responses']
    if not isinstance(files,list) or not all(isinstance(p,str) for p in files) or not isinstance(responses,list):
        raise ValueError('Malformed file-stage evidence')
    return {'instance_id':row['instance_id'],'base_commit':row['base_commit'],
            'files':files,'raw_file_responses':responses}


def validate_shared(value,result,row):
    if not isinstance(value,dict) or set(value)!=SHARED_KEYS:
        raise ValueError('Shared input accepts exactly four public fields')
    expected=shared_payload(result,row)
    if expected is None or value!=expected:raise ValueError('Shared evidence identity/content mismatch')
    return value


def public_files(stage,iid):
    stage=Path(stage)
    expected={'job.json','code_index.json','public_receipt.json','render_cache.json',
              'repo_structures/'+iid+'.json','shared.json'}
    actual={}
    for p in stage.rglob('*'):
        if p.is_symlink():raise ValueError('Symlink in public staging')
        if p.is_file():actual[p.relative_to(stage).as_posix()]=sha(p)
        elif p.is_dir() and p.relative_to(stage).as_posix()!='repo_structures':
            raise ValueError('Unexpected public staging directory')
    if set(actual)!=expected:raise ValueError('Unexpected/private public staging file inventory')
    return actual


def validate_stage(stage,row,source_job,prepared,result):
    """No Gold/patch fields can be added to the clean job or file-stage payload."""
    stage=Path(stage);files=public_files(stage,row['instance_id']);job=read(stage/'job.json')
    if not isinstance(job,dict) or set(job)!=CLEAN_KEYS:raise ValueError('Expected exactly nine clean job fields')
    identity(job,row,'public job');identity(source_job,row,'base job')
    expected=dict(source_job,snapshot='/snapshot',code_index='/input/code_index.json',
                  structure='/input/repo_structures/'+row['instance_id']+'.json')
    if job!=expected:raise ValueError('Relocated public job differs from the exact source job')
    original=dict(prepared['staged_sha256'])
    if {k:v for k,v in files.items() if k!='shared.json'}!=original:
        raise ValueError('Original staged public file bytes changed')
    validate_shared(read(stage/'shared.json'),result,row)
    receipt=read(stage/'public_receipt.json')
    if (set(receipt)!={'original_job_sha256','source_snapshot','base_commit','index_sha256','render_cache_sha256','gold_or_patch_read'}
            or receipt.get('original_job_sha256')!=prepared['source']['job_sha256']
            or receipt.get('source_snapshot')!=prepared['source']['snapshot']
            or receipt.get('gold_or_patch_read') is not False or receipt.get('base_commit')!=row['base_commit']
            or receipt.get('index_sha256')!=files['code_index.json']
            or receipt.get('render_cache_sha256')!=files['render_cache.json']):
        raise ValueError('Original public source receipt drift')
    return files


def copy_public(source,target,files):
    source,target=Path(source),Path(target)
    if target.exists():
        actual=public_files(target,target.name)
        if actual!=files:raise ValueError('Existing new public projection differs; never overwrite')
        return
    target.mkdir(parents=True,exist_ok=False)
    for relative,wanted in files.items():
        origin=source/relative;dest=target/relative
        if origin.is_symlink() or sha(origin)!=wanted:raise ValueError('Source changed before copy')
        dest.parent.mkdir(parents=True,exist_ok=True)
        with origin.open('rb') as a,dest.open('xb') as b:shutil.copyfileobj(a,b)
        if sha(dest)!=wanted:raise ValueError('Copied public bytes differ')


def load_sources(parent,*,expected_total=560):
    parent=Path(parent).resolve(strict=True);protocol=read(parent/'protocol.json')
    if protocol.get('dataset')!=SOURCE or protocol.get('revision')!=REVISION or protocol.get('allocated')!=expected_total:
        raise ValueError('Wrong official parent scope/revision')
    allocation=read(parent/'allocation.json');rows=allocation['records']
    if len(rows)!=expected_total or len({r['instance_id'] for r in rows})!=expected_total:
        raise ValueError('Full frozen official roster required')
    if expected_total==560:
        if sha(parent/'allocation.json')!=pilot.PARENT_ALLOCATION_SHA or sha(parent/'dataset_download/data/test-00000-of-00001.parquet')!=PARQUET_SHA:
            raise ValueError('Frozen parent allocation/dataset bytes changed')
    plan=read(parent/'continuation460/plan.json');works=[parent/'pilot100']+[Path(b['work']) for b in plan['batches']]
    origins={};evidence={};source_hashes={}
    for work in works:
        work=Path(work).resolve(strict=True);ar=read(work/'allocation.json')['records']
        runtime={r['instance_id']:r for r in read(work/'runtime/runnable_manifest.json')['records']}
        statuses={r['instance_id']:r for r in read(work/'runtime/allocation_status.json')['records']}
        if set(statuses)!={r['instance_id'] for r in ar}:raise ValueError('Missing original preparation states')
        for row in ar:
            iid=row['instance_id']
            if iid in origins:raise ValueError('Repeated historical task identity')
            origins[iid]=(work,runtime.get(iid),statuses[iid]);evidence[iid]=row
        report_dir=work/'reports/final';report_manifest=read(report_dir/'output_sha256.json')
        for name,wanted in report_manifest.items():
            if Path(name).name!=name or sha(report_dir/name)!=wanted:raise ValueError('Historical batch report drift')
            source_hashes[str(report_dir/name)]=wanted
        gate=read(report_dir/'terminal_gate.json')
        if gate.get('passed') is not True or gate.get('gold_opened_during_gate') is not False:
            raise ValueError('Original closed terminal gate invalid')
        for path,wanted in gate['public_input_sha256'].items():
            if sha(path)!=wanted:raise ValueError('Historical staged input changed after scoring')
            source_hashes[path]=wanted
        for relative in ('protocol.json','allocation.json','runtime/runnable_manifest.json','runtime/allocation_status.json','controller/report_freeze.json','reports/final/output_sha256.json'):
            source_hashes[str(work/relative)]=sha(work/relative)
    ordered=sorted(rows,key=hash_key)
    if set(origins)!={r['instance_id'] for r in rows} or any(evidence[r['instance_id']]!=r for r in rows):
        raise ValueError('Historical origin rosters differ from parent identity/metadata')
    final=parent/'continuation460/reports/cumulative560';manifest=read(final/'output_sha256.json')
    for name,wanted in manifest.items():
        if Path(name).name!=name or sha(final/name)!=wanted:raise ValueError('Historical report output drift')
        source_hashes[str(final/name)]=wanted
    summary=read(final/'summary.json')
    if summary.get('allocated')!=expected_total:raise ValueError('Historical full report scope drift')
    source_hashes[str(final/'output_sha256.json')]=sha(final/'output_sha256.json')
    source_hashes[str(parent/'allocation.json')]=sha(parent/'allocation.json')
    return ordered,origins,source_hashes


def prepare_one(root,row,rank,origin):
    root=Path(root);work,runtime,status=origin;iid=row['instance_id']
    record={k:row[k] for k in IDENTITY}
    record.update(rank=rank,original_work=str(work),source_job_path=None,source_snapshot=None,
        public_input_path=None,public_files_sha256={},upstream_files_sha256={},
        prepared_receipt_path=str(root/'prepared_receipts'/(iid+'.json')),train_repo_seen=row.get('train_repo_seen',False))
    if runtime is None:
        if status.get('status')!='PREPARATION_BLOCKED' or not status.get('errors'):
            raise ValueError('Missing runtime must have explicit source failure evidence')
        record.update(upstream_status='source_preparation_blocked',no_model_dispatch=True,
                      upstream_reason=status)
        write(record['prepared_receipt_path'],{'status':'NO_MODEL_DISPATCH','record':record,'Gold_read':False})
        return record
    identity(runtime,row,'original runtime')
    job_path=(work/'runtime'/runtime['job']).resolve(strict=True);job=c.load_job(job_path);identity(job,row,'source job')
    record.update(source_job_path=str(job_path),source_snapshot=job['snapshot'])
    pair=work/'paired_run/pairs'/iid;result_path=pair/'baseline/result.json';term_path=pair/'baseline/terminal.json'
    term=read(term_path)
    if (term.get('instance_id')!=iid or term.get('base_commit')!=row['base_commit'] or term.get('arm')!='baseline'
            or term.get('protocol_sha256')!=read(work/'paired_run/freeze.json')['protocol_sha256']
            or term.get('simulation') is not False):raise ValueError('Original baseline terminal identity/protocol mismatch')
    result=read(result_path)
    if term.get('result_sha256')!=sha(result_path):raise ValueError('Historical baseline result SHA mismatch')
    identity(result,row,'baseline result')
    record['upstream_files_sha256']={str(result_path):sha(result_path),str(term_path):sha(term_path)}
    shared=shared_payload(result,row)
    if shared is None:
        record.update(upstream_status='upstream_file_stage_unavailable',no_model_dispatch=True,
                      upstream_reason={'terminal_status':term['status'],'result_status':result.get('status'),
                                       'reason':'Original shared-file eligibility gate did not pass'})
        write(record['prepared_receipt_path'],{'status':'NO_MODEL_DISPATCH','record':record,'Gold_read':False})
        return record
    prepared=read(pair/'prepared.json');source=c.source_receipt(job_path)
    if prepared.get('source')!=source or prepared.get('protocol_sha256')!=term['protocol_sha256']:
        raise ValueError('Original preparation/source receipt differs')
    original=pair/'_public_inputs';files=validate_stage(original,row,job,prepared,result)
    receipt_path=pair/'shared_receipt.json';receipt=read(receipt_path)
    if (receipt.get('baseline_result_sha256')!=sha(result_path) or receipt.get('shared_sha256')!=files['shared.json']
            or receipt.get('protocol_sha256')!=term['protocol_sha256']):raise ValueError('Original shared receipt binding drift')
    target=root/'inputs'/iid;copy_public(original,target,files)
    if validate_stage(target,row,job,prepared,result)!=files:raise ValueError('New public projection validation drift')
    record['upstream_files_sha256'].update({str(pair/'prepared.json'):sha(pair/'prepared.json'),str(receipt_path):sha(receipt_path),str(job_path):sha(job_path)})
    record.update(upstream_status='ready',no_model_dispatch=False,public_input_path=str(target),public_files_sha256=files)
    write(record['prepared_receipt_path'],{'status':'PREPARED','record':record,'source_receipt':source,
          'original_public_input_path':str(original),'Gold_read':False,'graphs_recomputed':False})
    return record


def prepare(root,parent,*,workers=4,expected_total=560):
    root,parent=Path(root).resolve(),Path(parent).resolve(strict=True)
    if root==parent or parent in root.parents:raise ValueError('Use an independent new experiment root')
    if workers not in range(1,5):raise ValueError('CPU projection workers must be1..4')
    protocol_path=root/'protocol.json';protocol=read(protocol_path)
    if protocol.get('arms')!=list(ARMS) or protocol.get('allocated',expected_total)!=expected_total:
        raise ValueError('New frozen protocol must declare the exact three arms/scope')
    if (root/'manifest.json').exists():raise FileExistsError('Never overwrite a frozen preparation manifest')
    rows,origins,source_hashes=load_sources(parent,expected_total=expected_total)
    results={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(prepare_one,root,row,i+1,origins[row['instance_id']]):row['instance_id'] for i,row in enumerate(rows)}
        for future in as_completed(futures):results[futures[future]]=future.result()
    records=[results[r['instance_id']] for r in rows]
    counts={k:sum(r['upstream_status']==k for r in records) for k in ('ready','source_preparation_blocked','upstream_file_stage_unavailable')}
    if expected_total==560 and counts!={'ready':557,'source_preparation_blocked':2,'upstream_file_stage_unavailable':1}:
        raise ValueError('Historical availability changed; do not silently alter the experiment')
    manifest={'schema':1,'n':expected_total,'allocated':expected_total,'arms':list(ARMS),'records':records,
              'order':'SHA256(20261116:instance_id), then IID; original fixed560','availability':counts}
    write(root/'manifest.json',manifest)
    files={str(protocol_path):sha(protocol_path),str(root/'manifest.json'):sha(root/'manifest.json')}
    files.update(source_hashes)
    for r in records:
        files[r['prepared_receipt_path']]=sha(r['prepared_receipt_path'])
        files.update(r['upstream_files_sha256'])
        for relative,wanted in r['public_files_sha256'].items():files[str(Path(r['public_input_path'])/relative)]=wanted
    authority={'status':'FROZEN_BEFORE_NEW_MODEL_CALLS','parent':str(parent),'allocated':expected_total,
       'manifest_sha256':sha(root/'manifest.json'),'protocol_sha256':sha(protocol_path),'availability':counts,
       'files_sha256':files,'prepare_source_sha256':sha(__file__),'Gold_parsed':False,'models_called':False,
       'graphs_recomputed':False,'downloads':0}
    for path,wanted in files.items():
        if sha(path)!=wanted:raise ValueError('Projection/source changed during preparation: '+path)
    write(root/'authority.json',authority)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--parent',type=Path,required=True);p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();m=prepare(a.root,a.parent,workers=a.workers)
    print(json.dumps({'allocated':m['allocated'],'availability':m['availability'],'models_called':False}))
if __name__=='__main__':main()
