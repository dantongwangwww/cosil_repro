"""Prepare only the 270 unsealed Lite IDs, reusing 55 validated P1 results.

Public Arrow is projected to IDs first; protected rows are excluded before any
Python benchmark-row object is materialized. Test/harness columns are never read.
Online indexes are the unchanged P1 Python-3.11 AST implementation.
"""
import argparse
import collections
import concurrent.futures
import fcntl
import fnmatch
import io
import tarfile
import tempfile
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from . import common as C

PRIVATE=C.ROOT/'evaluator_private/lite'
DATA=C.COSIL/'swebench_local/SWE-bench_Lite_test/data-00000-of-00001.arrow'
OLD_RUN=C.FROZEN/'runs/20261021_nonthinking_v3'
SAFE_FIELDS=('instance_id','repo','base_commit','problem_statement','patch')
FORBIDDEN={'gold','patch','test_patch','FAIL_TO_PASS','PASS_TO_PASS','hints_text'}


def digest(value):return hashlib.sha256(value.encode() if isinstance(value,str) else value).hexdigest()
def stable(iid):return digest(str(C.SEED)+'|lite_remaining_v2|'+iid)
def once(path,value):
    previous=C.load(path)
    if previous is not None:
        if previous!=value:raise RuntimeError('Immutable preparation drift: '+str(path))
    else:C.write(path,value)


def load_projected_rows():
    import pyarrow as pa,pyarrow.ipc as ipc
    excluded=C.load(C.FROZEN/'manifests/excluded_ids.json')
    protected=set(excluded['ids'])
    with pa.memory_map(str(DATA),'r') as stream:schema=ipc.open_stream(stream).schema
    with pa.memory_map(str(DATA),'r') as stream:
        ids=ipc.open_stream(stream,options=ipc.IpcReadOptions(included_fields=[schema.get_field_index('instance_id')])).read_all().column(0).to_pylist()
    if len(ids)!=300 or len(set(ids))!=300:raise RuntimeError('Frozen Lite ID universe differs from 300')
    allowed=[i for i,iid in enumerate(ids) if iid not in protected]
    if len(set(ids)&protected)!=30 or len(allowed)!=270:raise RuntimeError('Expected exact30 protected Lite overlap')
    # Keep protected row values out of Python. Column buffers are memory-mapped;
    # Arrow take selects only allowed rows before conversion to Python values.
    with pa.memory_map(str(DATA),'r') as stream:
        table=ipc.open_stream(stream,options=ipc.IpcReadOptions(included_fields=[schema.get_field_index(k) for k in SAFE_FIELDS])).read_all()
        rows=table.take(pa.array(allowed,type=pa.int64())).to_pylist()
    if any(set(r)!=set(SAFE_FIELDS) or r['instance_id'] in protected for r in rows):raise RuntimeError('Unsafe projection')
    return rows,{'total_lite_ids':300,'protected_union_n':len(protected),'protected_lite_n':30,'eligible_n':270,
        'id_projection_only_before_exclusion':True,'projected_columns':list(SAFE_FIELDS),'test_harness_columns_read':False,
        'protected_rows_materialized':False,'protected_id_metadata_sha256':C.sha(C.FROZEN/'manifests/excluded_ids.json'),
        'historical_dataset_pin':C.load(C.FROZEN/'manifests/dataset_pin.json'),'full_arrow_rehashed':False}


def source_compatibility():
    config=C.load(C.FROZEN/'configs/resolved_config.json');checked={}
    names=['__init__.py','common.py','code_index.py','simple_pipeline.py','providers.py','execution.py','token_counter.py','dataset_adapter.py']
    for name in names:
        path=C.FROZEN/'src'/name;actual=C.sha(path)
        if config['source_sha256'].get(str(path))!=actual:raise RuntimeError('Frozen P1 source changed: '+str(path))
        checked[str(path)]=actual
    for name in ['file_selection','query_planning','function_localization']:
        path=C.FROZEN/'prompts'/(name+'.txt');actual=C.sha(path)
        if config['source_sha256'].get(str(path))!=actual:raise RuntimeError('Frozen prompt changed')
        checked[str(path)]=actual
    prior=C.load(C.ADDITIONAL_RUN/'online_freeze.json')
    for path,expected in prior['online_sha256'].items():
        if C.sha(path)!=expected:raise RuntimeError('Old200 frozen online source changed: '+path)
    return checked


def frozen_modules():
    if str(C.FROZEN) not in sys.path:sys.path.insert(0,str(C.FROZEN))
    from src.code_index import decode,file_record,structure
    from src.dataset_adapter import safe_snapshot
    from src.simple_pipeline import inventory
    from src.common import redact
    return decode,file_record,structure,safe_snapshot,inventory,redact


def verify_reuse(row,old_record,cohort):
    decode,_,_,_,inventory,redact=frozen_modules()
    iid=row['instance_id'];job=C.load(old_record['job']);folder=OLD_RUN/cohort/'D-SIMPLE'/iid
    if FORBIDDEN&set(job) or any(job[k]!=row[k] for k in ['instance_id','repo','base_commit','problem_statement']):raise RuntimeError('Reuse clean-job identity mismatch')
    result=C.load(folder/'result.json')
    if not result or result['status']!='complete':raise RuntimeError('Previous D-SIMPLE result is not complete')
    selection=C.load(folder/'file_selection.json');context=C.load(folder/'context.json');issue=redact(row['problem_statement'],job)
    shown,_=inventory(job['paths'],issue)
    prompt=lambda n:(C.FROZEN/'prompts'/(n+'.txt')).read_text()
    file_message=prompt('file_selection')+'\n<issue>\n'+issue+'\n</issue>\n<paths>\n'+'\n'.join(shown)+'\n</paths>'
    selected=selection['ranked_edit_files']
    planner=prompt('query_planning')+'\n<issue>\n'+issue+'\n</issue>\n<selected_files>\n'+json.dumps(selected)+'\n</selected_files>'
    for block in context['blocks']:
        source=decode((Path(job['snapshot'])/block['path']).read_bytes())
        span=''.join(source.splitlines(keepends=True)[block['start_line']-1:block['end_line']])
        if span!=block['text'] or digest(span)!=block['sha256']:raise RuntimeError('Historical source block differs from base snapshot')
    final=prompt('function_localization')+'\n<issue>\n'+issue+'\n</issue>\n<context>\n'+'\n\n'.join(b['header']+b['text'] for b in context['blocks'])+'\n</context>'
    expected=[('file_draw_'+str(i),2048,1.,file_message) for i in range(5)]+[('query_planning',1024,0.,planner),('function_localization',4096,0.,final)]
    requests=sorted((folder/'calls').glob('*/request.json'))
    if len(requests)!=7:raise RuntimeError('Reuse requires exactly seven historical semantic requests')
    hashes={str(folder/n):C.sha(folder/n) for n in ['result.json','file_selection.json','context.json','inventory.json']}
    for number,(path,(stage,limit,temp,message)) in enumerate(zip(requests,expected),1):
        saved=C.load(path);request=saved['request']
        if path.parent.name!=str(number).zfill(4)+'_'+stage:raise RuntimeError('Historical stage order differs')
        if request['messages']!=[{'role':'user','content':message}] or request['max_tokens']!=limit or request['temperature']!=temp:raise RuntimeError('Historical prompt/sampling contract differs')
        if request['model']!='deepseek-flash' or request.get('thinking')!={'type':'disabled'} or request.get('response_format')!={'type':'json_object'}:raise RuntimeError('Historical nonthinking/JSON model contract differs')
        if saved['sha256']!=digest(json.dumps(request,sort_keys=True,ensure_ascii=False)):raise RuntimeError('Historical request SHA differs')
        answer=C.load(path.parent/'result.json');receipt=answer['receipt']
        if receipt.get('http_status')!=200 or receipt.get('finish_reason')!='stop' or receipt.get('reasoning_content_present') or not answer.get('usage'):raise RuntimeError('Historical request has no complete nonthinking usage receipt')
        if receipt['request_sha256']!=saved['sha256'] or receipt['thinking_mode']!='disabled':raise RuntimeError('Historical receipt contract differs')
        hashes[str(path)]=C.sha(path);hashes[str(path.parent/'result.json')]=C.sha(path.parent/'result.json')
    if C.load(requests[-1].parent/'result.json')['content']!=result['raw_output']:raise RuntimeError('Historical final raw output differs')
    once(PRIVATE/'reuse_contracts'/(iid+'.json'),{'instance_id':iid,'cohort':cohort,'validated':True,'requests':7,
        'model':'deepseek-flash','thinking':'disabled','prompt_and_sampling_exact':True,'base_source_blocks_exact':True,
        'historical_artifact_sha256':hashes,'model_calls':0,'historical_files_modified':False})
    return job,folder


def verify_base_archive_file(mirror,commit,rel,raw,blob_oid):
    actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if actual==blob_oid:return None
    # Git archive is the frozen P1 source definition. export-subst may legally
    # expand placeholders, so validate the attribute and two exact base archives.
    enabled=False;witnesses=[];parts=Path(rel).parts
    for depth in range(len(parts)):
        prefix='/'.join(parts[:depth]);attribute=(prefix+'/' if prefix else '')+'.gitattributes'
        result=subprocess.run(['git','--git-dir',str(mirror),'show',commit+':'+attribute],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        if result.returncode:continue
        local='/'.join(parts[depth:])
        for line in result.stdout.decode().splitlines():
            values=line.strip().split()
            if len(values)<2 or values[0].startswith('#'):continue
            candidate=local if '/' in values[0] else Path(local).name
            if not fnmatch.fnmatchcase(candidate,values[0]):continue
            if 'export-subst' in values[1:]:enabled=True;witnesses.append({'path':attribute,'line':line,'sha256':digest(result.stdout)})
            if '-export-subst' in values[1:] or '!export-subst' in values[1:]:enabled=False
    if not enabled:raise RuntimeError('Base Git blob mismatch without verified export-subst: '+rel)
    archives=[subprocess.check_output(['git','--git-dir',str(mirror),'archive',commit,rel]) for _ in range(2)]
    if archives[0]!=archives[1]:raise RuntimeError('Repeated base git archives differ: '+rel)
    with tarfile.open(fileobj=io.BytesIO(archives[0])) as archive:
        member=archive.getmember(rel)
        if not member.isfile() or archive.extractfile(member).read()!=raw:raise RuntimeError('P1 source differs from same-base git archive: '+rel)
    return {'path':rel,'reason':'base .gitattributes export-subst; unchanged P1 git-archive semantics',
            'attribute_witnesses':witnesses,'git_blob_oid':blob_oid,'snapshot_sha256':digest(raw),'repeated_git_archive_sha256':digest(archives[0])}


def prepare_one(record,row):
    iid=row['instance_id'];receipt_path=PRIVATE/'preparation'/(iid+'.json')
    cached=C.load(receipt_path)
    if cached and cached.get('status')=='complete':
        for path,expected in {**cached['data_sha256'],**cached['snapshot_sha256']}.items():
            if C.sha(path)!=expected:raise RuntimeError('Previously prepared Lite input changed: '+path)
        return record
    try:
        if shutil.disk_usage(C.ROOT.resolve()).free<2*1024**3:raise RuntimeError('Preparation volume below 2GiB')
        decode,file_record,structure,safe_snapshot,_,_=frozen_modules()
        target=C.ROOT/'snapshots'/iid;reused_existing=False
        if target.exists() and any(target.iterdir()):
            temp_parent=PRIVATE/'archive_repair_checks';temp_parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=temp_parent) as temporary:
                check=Path(temporary)/'snapshot';paths=safe_snapshot(row,check)
                for rel in paths:
                    if rel.endswith('.py') and ((not (target/rel).is_file()) or (target/rel).read_bytes()!=(check/rel).read_bytes()):
                        raise RuntimeError('Existing preparation source differs from same-base P1 archive: '+rel)
            reused_existing=True
        else:paths=safe_snapshot(row,target)
        mirror=C.COSIL/'mirror_cache'/(row['repo'].rsplit('/',1)[-1]+'.git')
        raw_tree=subprocess.check_output(['git','--git-dir',str(mirror),'ls-tree','-rz','-r',row['base_commit']])
        blobs={entry.split(b'\t',1)[1].decode():entry.split(b'\t',1)[0].split()[2].decode() for entry in raw_tree.split(b'\0') if entry}
        index={};source_hashes={};archive_transforms=[]
        for rel in paths:
            if not rel.endswith('.py'):continue
            path=target/rel;raw=path.read_bytes()
            transformation=verify_base_archive_file(mirror,row['base_commit'],rel,raw,blobs[rel])
            if transformation:archive_transforms.append(transformation)
            source_hashes[str(path)]=digest(raw)
            try:text=decode(raw)
            except (SyntaxError,UnicodeError):continue
            index[rel]=file_record(rel,text)
        index_path=C.ROOT/'jobs'/iid/'code_index.json';structure_path=C.ROOT/'jobs'/iid/'repo_structures'/(iid+'.json')
        C.write(index_path,index)
        C.write(structure_path,{'instance_id':iid,'repo':row['repo'],'base_commit':row['base_commit'],'structure':structure(target,paths)})
        public={k:row[k] for k in ['instance_id','repo','base_commit','problem_statement']}
        public.update(cohort=C.COHORT,snapshot=str(target),paths=paths,code_index=str(index_path),structure=str(structure_path))
        C.write(record['job'],public)
        data={p:C.sha(p) for p in [record['job'],str(index_path),str(structure_path)]}
        C.write(receipt_path,{'status':'complete','instance_id':iid,'source':'read-only frozen P1 git archive','base_commit':row['base_commit'],
            'git_cache_modified':False,'existing_snapshot_reused_readonly':reused_existing,'online_ast_python':sys.version.split()[0],'source_index_implementation':'unchanged P1 src.code_index',
            'data_sha256':data,'snapshot_sha256':source_hashes,'verified_archive_export_subst':archive_transforms,'patch_or_labels_used_for_online_job':False,'gpu_used':False})
        return record
    except Exception as error:
        C.write(PRIVATE/'preparation_errors'/(iid+'.json'),{'status':'failed','error_type':type(error).__name__,'error_message':str(error),'traceback':traceback.format_exc()})
        return dict(record,preparation_status='failed',preparation_error_type=type(error).__name__,preparation_error_message=str(error))


def prepare(workers=4):
    if not 1<=workers<=4:raise ValueError('CPU preparation workers must be 1..4')
    PRIVATE.mkdir(parents=True,exist_ok=True)
    with (PRIVATE/'prepare.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        source_sha=source_compatibility();rows,projection=load_projected_rows();by_id={r['instance_id']:r for r in rows}
        old={};reuse=[]
        for cohort,origin in [('smoke','reused_smoke5'),('lite_pilot','reused_pilot50')]:
            records=C.load(C.FROZEN/'manifests'/(cohort+'.json'))['records']
            for record in records:
                iid=record['instance_id']
                if iid in old or iid not in by_id:raise RuntimeError('Prior55 overlap or protected/outside Lite')
                old[iid]=(record,cohort,origin)
        if len(old)!=55:raise RuntimeError('Expected 55 distinct prior results')
        records=[];new=[]
        for row in sorted(rows,key=lambda r:(stable(r['instance_id']),r['instance_id'])):
            iid=row['instance_id'];private=PRIVATE/'rows'/(iid+'.json');once(private,row)
            base={k:row[k] for k in ['instance_id','repo','base_commit']}
            base.update(private_row=str(private),benchmark_row_path=str(private),sampling_hash=stable(iid))
            if iid in old:
                oldrec,cohort,origin=old[iid];job,folder=verify_reuse(row,oldrec,cohort)
                base.update(origin=origin,job=oldrec['job'],snapshot=job['snapshot'],result_dir=str(folder),v1_gold=str(C.FROZEN/'evaluator_private'/iid/'gold.json'))
                reuse.append(base)
            else:
                base.update(origin='new215',job=str(C.ROOT/'jobs'/iid/'job.json'),snapshot=str(C.ROOT/'snapshots'/iid),
                    result_dir=str(C.RUN/C.COHORT/'D-SIMPLE'/iid),v1_gold=None)
                new.append(base)
            records.append(base)
        if len(new)!=215 or len(reuse)!=55:raise RuntimeError('Exact remaining215/reused55 allocation changed')
        plan={'cohort':'lite270','n':270,'records':records,'reuse_n':55,'new_n':215,'protected_n':30,'selection_uses_outcomes':False,'projection':projection}
        once(C.ROOT/'manifests/lite270_plan.json',plan)
        once(C.ROOT/'manifests/lite_reuse55.json',{'cohort':'lite_reuse55','n':55,'records':reuse})
        C.write(C.RUN/'lite_preparation_progress.json',{'status':'preparing','target':215,'prepared':0,'reused':55,'api_calls':0})
        completed={};failed=[]
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            future_map={pool.submit(prepare_one,record,{k:by_id[record['instance_id']][k] for k in ['instance_id','repo','base_commit','problem_statement']}):record for record in new}
            for future in concurrent.futures.as_completed(future_map):
                value=future.result();completed[value['instance_id']]=value
                if value.get('preparation_status')=='failed':failed.append(value['instance_id'])
                C.write(C.RUN/'lite_preparation_progress.json',{'status':'preparing','target':215,'prepared':len(completed),'failed':len(failed),'reused':55,'last':value['instance_id'],'api_calls':0})
        final=[completed.get(r['instance_id'],r) for r in records]
        manifest={**plan,'records':final,'preparation_failed_n':len(failed),'complete':True}
        once(C.ROOT/'manifests/lite270.json',manifest)
        once(C.ROOT/'manifests/lite215.json',{'cohort':C.COHORT,'n':215,'records':[completed[r['instance_id']] for r in new],
            'protected_test_ids_excluded':True,'selection_uses_outcomes':False})
        C.write(PRIVATE/'preparation_summary.json',{'status':'complete','n':270,'reused':55,'new':215,'failed':len(failed),'source_sha256':source_sha,
            'online_ast_python':'3.11 unchanged P1','offline_gold_ast_python':'3.12 independent evaluator','gpu_used':False,'model_calls':0})
        C.write(C.RUN/'lite_preparation_progress.json',{'status':'complete','target':215,'prepared':215,'failed':len(failed),'reused':55,'api_calls':0})
        print(json.dumps({'prepared_new':215,'reused':55,'failed':len(failed),'manifest':str(C.ROOT/'manifests/lite270.json')},ensure_ascii=False),flush=True)
        return manifest


def repair_failed():
    # Explicit pre-API engineering repair of the same allocated IDs, no reselection.
    if (C.RUN/'lite_online_freeze.json').exists():raise RuntimeError('Cannot revise inputs after online source freeze')
    ledger=C.load(C.SHARED_BUDGET)
    if ledger is None or ledger.get('stage_cap_usd')!=5. or ledger.get('attempts'):raise RuntimeError('Input repair is permitted only before any shared paid attempt')
    manifest_path=C.ROOT/'manifests/lite270.json';new_path=C.ROOT/'manifests/lite215.json'
    manifest=C.load(manifest_path);new=C.load(new_path)
    if not manifest or not manifest.get('complete'):raise RuntimeError('Initial preparation must finish before targeted repair')
    with (PRIVATE/'prepare.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before270=C.sha(manifest_path);before215=C.sha(new_path);fixed={};evidence=[]
        for record in new['records']:
            if record.get('preparation_status')!='failed':continue
            iid=record['instance_id'];failure=C.load(PRIVATE/'preparation_errors'/(iid+'.json'))
            once(PRIVATE/'preparation_repair_history'/iid/'first_failure.json',failure)
            clean={k:v for k,v in record.items() if k not in ['preparation_status','preparation_error_type','preparation_error_message']}
            source=C.load(record['private_row']);row={k:source[k] for k in ['instance_id','repo','base_commit','problem_statement']}
            result=prepare_one(clean,row);fixed[iid]=result
            evidence.append({'instance_id':iid,'first_failure':failure['error_message'],'repaired':result.get('preparation_status')!='failed',
                'same_repo_base_and_id':True,'model_calls':0,'source_implementation_changed':False,'receipt':str(PRIVATE/'preparation'/(iid+'.json'))})
        once(PRIVATE/'manifest_revisions'/('lite270_before_'+before270+'.json'),manifest)
        once(PRIVATE/'manifest_revisions'/('lite215_before_'+before215+'.json'),new)
        for target in [manifest,new]:
            original=[r['instance_id'] for r in target['records']]
            target['records']=[fixed.get(r['instance_id'],r) for r in target['records']]
            assert [r['instance_id'] for r in target['records']]==original
        manifest['preparation_failed_n']=sum(r.get('preparation_status')=='failed' for r in manifest['records'])
        C.write(manifest_path,manifest);C.write(new_path,new)
        C.write(PRIVATE/'preparation_repair_summary.json',{'evidence':evidence,'before_manifest_sha256':before270,'after_manifest_sha256':C.sha(manifest_path),'model_calls':0,'replacement_issues':0})
        summary=C.load(PRIVATE/'preparation_summary.json');summary['failed']=manifest['preparation_failed_n'];summary['same_id_engineering_repairs']=len(evidence);C.write(PRIVATE/'preparation_summary.json',summary)
        C.write(C.RUN/'lite_preparation_progress.json',{'status':'complete','target':215,'prepared':215,'failed':manifest['preparation_failed_n'],'reused':55,'api_calls':0,'same_id_engineering_repairs':len(evidence)})
        return {'same_id_repairs':len(evidence),'still_failed':manifest['preparation_failed_n'],'model_calls':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workers',type=int,default=4);p.add_argument('--repair-failed',action='store_true');a=p.parse_args();print(json.dumps(repair_failed(),ensure_ascii=False)) if a.repair_failed else prepare(a.workers)

if __name__=='__main__':main()
