"""Offline fixed-Git-tree recovery of selected tasks whose tar transport failed.

No substitute tar or non-Python placeholder files are created. The complete
regular-path menu comes from the frozen full tree; every ordinary Python blob
is copied byte-for-byte after Git-object and SHA256 verification. Model identity
continues to use the original repo; a canonical rename is transport metadata.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_runtime as b
import recover_archive_links as links
import cache_decode_guard as cache_guard


def git_blob_sha(raw):
    return hashlib.sha1(('blob ' + str(len(raw)) + '\0').encode() + raw).hexdigest()


def cache_bytes(reference):
    path, receipt = Path(reference['cache_body']), Path(reference['cache_receipt'])
    meta = b.read(receipt); raw = b.stable_bytes(path)
    if meta.get('status') != 'complete' or meta.get('blob_sha') != reference['blob_sha']:
        raise ValueError('Blob cache completion or expected identity mismatch')
    if len(raw) != reference['blob_size'] or meta.get('bytes') != len(raw):
        raise ValueError('Blob byte length mismatch')
    if git_blob_sha(raw) != reference['blob_sha'] or b.digest(raw) != meta.get('sha256'):
        raise ValueError('Git blob SHA or raw SHA256 mismatch')
    return raw


def check_cache(plan):
    missing, invalid = [], []
    for row in plan['records']:
        if not Path(row['cache_body']).is_file() or not Path(row['cache_receipt']).is_file():
            missing.append(row['blob_sha']);continue
        try:cache_bytes(row)
        except (OSError,ValueError,KeyError) as error:invalid.append({'blob_sha':row['blob_sha'],'error':str(error)})
    return {'ready':not missing and not invalid,'unique_blobs':len(plan['records']),
            'missing':missing,'invalid':invalid}


def validate_plan(plan_path, selection, preparations):
    plan = b.read(plan_path);selected, prep = b.load_inputs(selection, preparations)
    if plan['selection_sha256'] != b.sha(selection) or plan['preparations_sha256'] != b.sha(preparations):
        raise ValueError('Git fetch plan has different frozen inputs')
    selected_map={r['instance_id']:r for r in selected['records']}
    cases={};references={}
    for ref in plan['file_references']:
        iid=ref['instance_id'];path=b.relative_path(ref['path'])
        cache_root=Path(plan_path).resolve().parent/'git_blob_cache'
        if (Path(ref['cache_body']).resolve()!=cache_root/(ref['blob_sha']+'.raw') or
                Path(ref['cache_receipt']).resolve()!=cache_root/(ref['blob_sha']+'.json')):
            raise ValueError('Blob cache path escaped the content-addressed source cache')
        if path in references.setdefault(iid,{}):raise ValueError('Duplicate Python path in fetch plan')
        references[iid][path]=ref
    for case in plan['cases']:
        iid=case['instance_id']
        if iid in cases or iid not in selected_map:raise ValueError('Unknown/duplicate Git recovery case')
        if case['identity_repo'] != prep[iid]['repo'] or case['base_commit'] != prep[iid]['base_commit']:
            raise ValueError('Git tree source identity/base mismatch')
        if b.sha(case['tree_path']) != case['tree_sha256']:raise ValueError('Frozen full Git tree SHA changed')
        tree=b.read(case['tree_path'])
        if tree.get('truncated') is not False:raise ValueError('Incomplete Git tree cannot establish inventory')
        ordinary=[e for e in tree['tree'] if e['type']=='blob' and e['mode'] in ('100644','100755')]
        paths=sorted(b.relative_path(e['path']) for e in ordinary)
        if len(paths)!=len(set(paths)) or paths!=case['regular_file_paths']:
            raise ValueError('Full regular Git path menu mismatch')
        expected={e['path']:(e['sha'],e['size']) for e in ordinary if e['path'].endswith('.py')}
        actual=references.get(iid,{})
        if set(expected)!=set(actual):raise ValueError('Python blob inventory is incomplete')
        for path,(blob,size) in expected.items():
            ref=actual[path]
            if (ref['blob_sha'],ref['blob_size'])!=(blob,size) or ref['base']!=case['base_commit'] or ref['identity_repo']!=case['identity_repo']:
                raise ValueError('Tree/blob reference mismatch')
        cases[iid]=case
    if set(references)!=set(cases):raise ValueError('Fetch references and Git cases differ')
    return plan,selected,prep,cases,references


def build_case(record,row,case,references,runtime,private,plan_sha,python_ast):
    iid=row['instance_id'];runtime=Path(runtime);private=Path(private)
    binding={'selection_record_sha256':b.digest(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()),
             'preparation_projection_sha256':b.digest(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()),
             'plan_sha256':plan_sha,'provider_sha256':b.sha(__file__),
             'index_builder_sha256':b.sha(b.__file__),'cache_adapter_sha256':b.sha(cache_guard.__file__)}
    receipt_path=private/'cases'/(iid+'.json');final=runtime/'tasks'/iid
    if receipt_path.exists():
        old=b.read(receipt_path)
        if old['binding']!=binding:raise ValueError('Completed Git source binding changed')
        for rel,wanted in old['runtime_files_sha256'].items():
            if b.sha(runtime/rel)!=wanted:raise ValueError('Completed Git source asset changed')
        return old['record']
    if final.exists():raise ValueError('Unreceipted final task directory retained')
    work=final.with_name('.'+iid+'.gitbuilding.'+uuid.uuid4().hex);snapshot=work/'snapshot';snapshot.mkdir(parents=True)
    blob_evidence=[]
    for path,ref in sorted(references.items()):
        raw=cache_bytes(ref);target=snapshot/b.relative_path(path);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
        blob_evidence.append({'path':path,'git_blob_sha':ref['blob_sha'],'raw_sha256':b.digest(raw),
                              'cache_receipt':ref['cache_receipt'],'cache_receipt_sha256':b.sha(ref['cache_receipt'])})
    b.verify_qualified(snapshot,row['base_files_sha256'])
    spec={'snapshot':str(snapshot),'iid':iid,'repo':row['repo'],'base':row['base_commit'],'task':str(work)}
    process=subprocess.run([str(python_ast),'-B',str(Path(b.__file__).resolve()),'--internal-index'],
        input=json.dumps(spec),text=True,capture_output=True,
        env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
    if process.returncode:raise RuntimeError('Python3.12 index failure: '+process.stderr[-1500:])
    index=b.read(work/'code_index.json');b.verify_qualified(snapshot,row['base_files_sha256'],index)
    job={key:row[key] for key in ('instance_id','repo','base_commit','problem_statement')}
    job.update(cohort=b.COHORT,snapshot='snapshot',paths=case['regular_file_paths'],code_index='code_index.json',
               structure='repo_structures/'+iid+'.json')
    b.validate_clean_job(job);b.write(work/'job.json',job)
    cache_guard.build(b.load_job(work/'job.json'),work/'render_cache.json')
    os.rename(work,final)
    public={key:row[key] for key in ('instance_id','repo','base_commit')}
    public.update(job='tasks/'+iid+'/job.json',job_sha256=b.sha(final/'job.json'),source=record['source'],
                  revision=row['source_revision'],source_sha256=row['source_sha256'],source_files=len(index),
                  source_bytes=sum((final/'snapshot'/p).stat().st_size for p in index))
    receipt={'binding':binding,'record':public,'tree_path':case['tree_path'],'tree_sha256':case['tree_sha256'],
             'transport_repo':case['transport_repo'],'identity_repo_unchanged':row['repo'],
             'source_scope':'complete regular base Git paths as menu; every ordinary Python blob byte-exact; non-Python bodies not downloaded',
             'python_blob_evidence':blob_evidence,'qualification_business_source_sha_matched':True,
             'runtime_files_sha256':{p.relative_to(runtime).as_posix():b.sha(p) for p in final.rglob('*') if p.is_file()},
             'model_calls':0,'gpu_used':False,'repository_code_executed':False}
    b.write(receipt_path,receipt);return public


def finalize(plan_path,selection,preparations,runtime,v1_private,links_private,private,*,expected_count=208,python_ast='/usr/bin/python3.12'):
    plan_path,selection,preparations,runtime,v1_private,links_private,private=map(
        lambda p:Path(p).resolve(),(plan_path,selection,preparations,runtime,v1_private,links_private,private))
    plan,selected,prep,cases,refs=validate_plan(plan_path,selection,preparations)
    if selected['n']!=expected_count:raise ValueError('Frozen count mismatch')
    if private.is_relative_to(runtime) or runtime.is_relative_to(private):
        raise ValueError('Private Git provenance must stay outside model runtime')
    original_contract=b.read(v1_private/'contract.json')
    if original_contract['selection_sha256']!=b.sha(selection) or original_contract['preparations_sha256']!=b.sha(preparations):
        raise ValueError('V1 frozen source selection/preparation differs')
    ready=check_cache(plan)
    if not ready['ready']:return {'status':'WAIT_CACHE','cache':ready,'manifest_written':False}
    records,progress,v1_evidence=links.inspect_v1(runtime,v1_private,selected,prep)
    network={iid for iid,error in progress['blocked'].items() if error['error'].startswith('BLOCKED_ARCHIVE_DOWNLOAD:')}
    link_ids={iid for iid,error in progress['blocked'].items() if error['error'].startswith('BLOCKED_PYTHON_LINK:')}
    if network!=set(cases) or network|link_ids!=set(progress['blocked']):
        raise ValueError('Recovery source types do not cover exactly the original failures')
    contract={'provider_sha256':b.sha(__file__),'plan_sha256':b.sha(plan_path),'selection_sha256':b.sha(selection),
              'preparations_sha256':b.sha(preparations),'v1_contract_sha256':b.sha(v1_private/'contract.json'),
              'v1_progress_sha256':b.sha(v1_private/'progress.json'),'expected_count':expected_count,
              'cache_adapter_sha256':b.sha(cache_guard.__file__)}
    b.write(private/'contract.json',contract)
    recovered=[]
    for record in selected['records']:
        iid=record['instance_id']
        if iid in network:
            records[iid]=build_case(record,prep[iid],cases[iid],refs[iid],runtime,private,b.sha(plan_path),python_ast)
            receipt=private/'cases'/(iid+'.json')
            recovered.append({'instance_id':iid,'type':'verified_git_tree_python_source','receipt':str(receipt),'receipt_sha256':b.sha(receipt)})
        elif iid in link_ids:
            receipt=links_private/'cases'/(iid+'.json');saved=b.read(receipt)
            expected={'preparation_projection_sha256':b.digest(json.dumps(prep[iid],sort_keys=True,ensure_ascii=False).encode()),
                      'builder_sha256':b.sha(b.__file__),
                      'selected_record_sha256':b.digest(json.dumps(record,sort_keys=True,ensure_ascii=False).encode())}
            if saved['binding']!=expected:raise ValueError('Completed link recovery binding mismatch')
            for rel,wanted in saved['runtime_files_sha256'].items():
                if b.sha(runtime/rel)!=wanted:raise ValueError('Completed link recovery asset drift')
            archive=saved['origin']['archive'];normal=Path(archive['normalization_receipt'])
            if b.sha(normal)!=archive['normalization_receipt_sha256'] or not b.read(normal)['ordinary_bytes_and_paths_preserved']:
                raise ValueError('Link-normalization proof drift')
            job=b.load_job(runtime/saved['record']['job']);b.verify_qualified(job['snapshot'],prep[iid]['base_files_sha256'],b.read(job['code_index']))
            records[iid]=saved['record'];recovered.append({'instance_id':iid,'type':'links_normalization',
                'receipt':str(receipt),'receipt_sha256':b.sha(receipt),'normalization':str(normal),'normalization_sha256':b.sha(normal)})
        print(json.dumps({'source_ready':iid,'ready':len(records),'total':expected_count}),flush=True)
    if len(records)!=expected_count or set(records)!={r['instance_id'] for r in selected['records']}:
        raise ValueError('Incomplete final source matrix')
    manifest={'schema':1,'n':expected_count,'records':[records[r['instance_id']] for r in selected['records']]}
    # Compute exact serialized manifest digest before its final publication.
    manifest_sha=b.digest((json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
    ledger={'status':'READY','n':expected_count,**contract,'manifest_sha256':manifest_sha,
            'verified_successful_v1_tasks':v1_evidence,'recovered_tasks':recovered,
            'selected_identities_unchanged':True,'original_failures_preserved':True,'model_calls':0,'gpu_used':False}
    ledger_path=private/'finalization_ledger.json';b.write(ledger_path,ledger)
    pointer={'status':'READY','n':expected_count,'manifest_sha256':manifest_sha,'recovery_ledger_path':str(ledger_path),
             'recovery_ledger_sha256':b.sha(ledger_path),'selected_identities_unchanged':True,'new_model_requests':0,'gpu_used':False}
    b.write(v1_private/'finalization_receipt.json',pointer)
    b.write(runtime/'manifest.json',manifest)
    if b.sha(runtime/'manifest.json')!=manifest_sha:raise ValueError('Manifest serialization differs')
    b.write(links_private/'recovery_plan.json',{'status':'READY','recovery_pending':False,**pointer},immutable=False)
    return {'status':'READY','n':expected_count,'manifest':str(runtime/'manifest.json'),'manifest_sha256':manifest_sha,
            'recovery_ledger_path':str(ledger_path)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','selection','preparations','runtime','v1-private','links-private','private'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--validate-cache-only',action='store_true');parser.add_argument('--python-ast',default='/usr/bin/python3.12')
    args=parser.parse_args()
    if args.validate_cache_only:
        result=check_cache(b.read(args.plan));print(json.dumps(result));return 0 if result['ready'] else 2
    result=finalize(args.plan,args.selection,args.preparations,args.runtime,args.v1_private,args.links_private,args.private,python_ast=args.python_ast)
    print(json.dumps(result));return 0 if result['status']=='READY' else 2


if __name__=='__main__':raise SystemExit(main())
