"""Fixed-order, pre-model official gold/base qualification; zero model API calls."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time
from . import executor as E
from .official_runtime import registry_manifest

def qualifies(gold,empty):
    return bool(gold.get('test_completed') is True and gold.get('resolved') is True
        and gold.get('environment_error') is False and empty.get('test_completed') is True
        and empty.get('resolved') is False and empty.get('environment_error') is False
        and empty.get('fail_to_pass_actually_failed',0)>0)

def system_failure(record):
    message=str(record.get('error','')).upper()
    return any(value in message for value in ['SYSTEM_DISK_CAPACITY','NO SPACE LEFT ON DEVICE',
        'PERMISSION DENIED','CANNOT CONNECT TO THE DOCKER','SYSTEM_IMAGE_PULL']) or record.get('error_type') in ['ImageTransportError','SYSTEM_IMAGE_IDENTITY']

def qualify_task(candidate,retry_infrastructure=False):
    iid=candidate['instance_id'];folder=E.LIVE/'candidates'/iid
    prior=folder/'qualification.json'
    if prior.exists():
        old=E.read(prior)
        if retry_infrastructure and old.get('system_blocked'):
            number=2;original_folder=folder
            while True:
                folder=original_folder/('infrastructure_attempt_'+str(number))
                if not (folder/'qualification.json').exists():break
                previous=E.read(folder/'qualification.json')
                if not previous.get('system_blocked'):return previous
                number+=1
        else:return old
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    row=E.private_row(iid)
    pin=folder/'image_manifest.json'
    if not pin.exists():
        original_pin=E.LIVE/'candidates'/iid/'image_manifest.json'
        if original_pin.exists():E.save(pin,E.read(original_pin))
        else:E.save(pin,registry_manifest(row['docker_image'],probe_layers=False))
    manifest=E.read(pin)
    task={**candidate,'image_digest':manifest['digest'],'image_reference':manifest['image_reference'],
        'compressed_layer_bytes':manifest['compressed_layer_bytes'],
        'image_manifest_path':str(pin),
        'eval_row_private_path':str(E.LIVE/'private_rows'/iid/'benchmark_row.json')}
    for name,text in [('gold',row['patch']),('empty','')]:
        path=folder/(name+'.diff')
        if not path.exists():path.write_text(text);path.chmod(0o600)
    # Always two fresh containers. Gold test outcomes never reach any repair prompt.
    gold=E.launch_worker(task,'QUAL_GOLD',folder/'gold.diff',folder/'gold')
    if system_failure(gold):
        result={'instance_id':iid,'task':task,'qualification_passed':False,'system_blocked':True,
                'reason':'SYSTEM_RUNTIME_FAILURE','gold_receipt':gold['path'],'empty_receipt':None}
        E.save(folder/'qualification.json',result);return result
    empty=E.launch_worker(task,'QUAL_EMPTY',folder/'empty.diff',folder/'empty')
    passed=qualifies(gold,empty)
    result={'instance_id':iid,'task':task,'qualification_passed':passed,
        'system_blocked':system_failure(empty),'reason':'QUALIFIED' if passed else 'GOLD_OR_EMPTY_QUALIFICATION_FAILED',
        'gold_receipt':gold['path'],'empty_receipt':empty['path'],
        'gold_resolved':gold['resolved'],'empty_resolved':empty['resolved'],
        'actual_empty_fail_to_pass_failures':empty.get('fail_to_pass_actually_failed',0)}
    E.save(folder/'qualification.json',result);return result

def run(limit=50,inspect_first=3,retry_infrastructure=False):
    order=E.OUT/'candidate_order.csv'
    with order.open(encoding='utf-8-sig',newline='') as handle:candidates=list(csv.DictReader(handle))
    selected=[];repos=set();audit=[];failures=0
    E.LIVE.mkdir(parents=True,exist_ok=True,mode=0o700)
    protocol={'schema':'repair50_qualification_v1','harness_commit':E.COMMIT,
        'candidate_order_sha256':E.digest(order),'resource_limits':E.LIMITS,'timeout_seconds':E.TIMEOUT,
        'concurrency':1,'gold_required_resolved':True,'base_required_real_ftp_failed_or_error':True,
        'private_test_data_never_model_input':True,'model_requests':0,'target':50,
        'cleanup':'Only newly pulled image reference if no container uses it; no force/prune; all baseline IDs preserved'}
    protocol_path=E.LIVE/'protocol.json'
    if protocol_path.exists() and E.read(protocol_path)!=protocol:
        previous=E.read(protocol_path)
        allowed={**previous,'resource_limits':{**previous['resource_limits'],'runtime':'runc'}}
        if allowed!=protocol:raise RuntimeError('Unexpected frozen qualification protocol drift')
        E.save(E.LIVE/'protocol_explicit_runc.json',protocol)
    else:E.save(protocol_path,protocol)
    if retry_infrastructure:E.save(E.LIVE/'transport_repair_protocol.json',{
        'authorized_checkpoint':E.CHECKPOINT,'same_registry_manifest_digest':True,
        'original_attempt_preserved':True,'fix':'Verified official image archive transfer via existing user proxy; no shared daemon configuration change',
        'model_calls':0})
    for candidate in candidates:
        if len(selected)>=limit:break
        iid=candidate['instance_id'];repo=candidate['repo'].casefold()
        if repo in repos:
            audit.append({'instance_id':iid,'reason':'REPOSITORY_ALREADY_HAS_QUALIFIED_TASK'})
            continue
        print(json.dumps({'event':'qualification_started','instance_id':iid,'rank':candidate['candidate_rank'],
                          'qualified':len(selected)},ensure_ascii=False),flush=True)
        try:result=qualify_task(candidate,retry_infrastructure=retry_infrastructure)
        except Exception as exc:
            result={'instance_id':iid,'qualification_passed':False,'system_blocked':True,
                    'reason':'PREPARATION_OR_RUNTIME_EXCEPTION','error_type':type(exc).__name__,'error':str(exc)}
        audit.append(result)
        if result.get('qualification_passed'):
            task={**result['task'],'qualification_passed':True,'gold_receipt':result['gold_receipt'],
                  'empty_receipt':result['empty_receipt']}
            selected.append(task);repos.add(repo);failures=0
        else:failures+=1
        print(json.dumps({'event':'qualification_finished','instance_id':iid,'passed':result.get('qualification_passed'),
                          'qualified':len(selected),'system_blocked':result.get('system_blocked')},ensure_ascii=False),flush=True)
        # Per-candidate immutable evidence plus an explicitly live status document.
        status={'updated_at':E.utc(),'qualified_count':len(selected),'target':limit,'audit':audit,'selected':selected,
                'frozen':False,'model_requests':0}
        live=E.LIVE/'live_status.json';temporary=E.LIVE/'live_status.pending'
        temporary.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n');temporary.replace(live)
        if result.get('system_blocked') or failures>=3:
            suffix=('_transport_retry_'+str(len(list(E.LIVE.glob('stop_*transport_retry*.json')))+1)) if retry_infrastructure else ''
            E.save(E.LIVE/('stop_'+str(candidate['candidate_rank'])+suffix+'.json'),{
                **status,'reason':'SYSTEM_BLOCK_OR_THREE_CONSECUTIVE_QUALIFICATION_FAILURES_REQUIRES_AUDIT'})
            return status
        if len(audit)==inspect_first:
            E.save(E.LIVE/'first3_engineering_review.json',{'reviewed_at':E.utc(),'records':audit,
                'scope':'Engineering chain check only; no model outcomes or prompt adjustment',
                'all_artifact_receipts_present':all(x.get('gold_receipt') and x.get('empty_receipt') for x in audit),
                'qualification_count':len(selected),'model_requests':0})
    if len(selected)==50:
        E.save(E.LIVE/'qualified50.json',{'frozen':True,'frozen_at':E.utc(),'tasks':selected,
            'candidate_order_sha256':E.digest(order),'dataset_sha256':E.DATASET_SHA,
            'harness_commit':E.COMMIT,'scope':'Existing-function-target development diagnostic; 50 different repositories',
            'qualification_audit':audit,'model_generation_calls_before_freeze':0})
    return {'qualified_count':len(selected),'frozen':len(selected)==50}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--target',type=int,default=50)
    parser.add_argument('--retry-infrastructure',action='store_true')
    args=parser.parse_args()
    if args.target not in [3,50]:raise ValueError('Only fixed first3 engineering check or full50 qualification allowed')
    print(json.dumps(run(args.target,retry_infrastructure=args.retry_infrastructure)),flush=True)

if __name__=='__main__':main()
