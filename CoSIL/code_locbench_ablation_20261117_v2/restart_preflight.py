"""Metadata-only bridge after a witnessed zero-benchmark preflight failure.

Never copies public input trees, run state, calls, status, or Gold; never starts
or signals a process. All algorithm parameters and the lifetime launch budget
are inherited, while the old execution remains immutable.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import shutil

from . import common as c

OLD_PROTOCOL_SHA='9b33ca9d339be81e044d8f1e8368336014263633fed8539689083f9840ef5d00'
FAILURE='Controller heartbeat stale for over180s; no semantic retry'
PRECHANGE='audits/preflight_v2_prechange_publication_receipt.json'
STOP='audits/verified_preflight_heartbeat_failure_stop.json'
REVIEW='audits/independent_review/runtime_canary_observation.json'
CLEAN={'instance_id','repo','base_commit','problem_statement','cohort','snapshot','paths','code_index','structure'}
SHARED={'instance_id','base_commit','files','raw_file_responses'}


def bind(path, mapping):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('Missing/unsafe immutable bridge evidence: '+str(path))
    mapping[str(path.resolve())]=c.sha(path)
    return c.read(path)


def same_saved_process(saved, observed):
    if not observed or observed.get('state')=='Z':return False
    keys=('pid','uid','start_ticks','pgid','sid')
    return all(saved.get(k)==observed.get(k) for k in keys)


def no_benchmark_work(old):
    run=Path(old)/'run'
    if any(run.rglob('started.json')):raise ValueError('Old experiment has a started benchmark arm')
    for path in run.rglob('*'):
        if path.is_symlink():raise ValueError('Unsafe old run symlink')
        if path.is_file() and any(part in ('calls','judge_rpc') for part in path.relative_to(run).parts):
            raise ValueError('Old experiment has benchmark HTTP/judge artifacts')
    reports=Path(old)/'reports'
    for pattern in ('**/evaluation.json','**/route_risk.json','**/逐题*.csv'):
        if any(reports.glob(pattern)):raise ValueError('Old experiment contains Gold-bearing scored output')


def validate_prior_sessions(old, records=None):
    old=Path(old).resolve();directories=sorted(p for p in (old/'controller/service_queue/sessions').glob('*') if p.is_dir())
    if not 1<=len(directories)<3:raise ValueError('Missing or exhausted prior model service session allowance')
    expected=[]
    for ordinal,directory in enumerate(directories,1):
        path=directory/'lifetime_admission.json';v=c.read(path)
        if (v.get('session_ordinal')!=ordinal or v.get('previous_session_count')!=ordinal-1
                or v.get('maximum_cumulative_infrastructure_launches')!=3
                or Path(v.get('root','')).resolve()!=old or v.get('semantic_retry') is not False):
            raise ValueError('Invalid prior lifetime admission/budget')
        expected.append({'session_directory':str(directory.resolve()),'lifetime_admission_path':str(path.resolve()),
                         'lifetime_admission_sha256':c.sha(path)})
    if records is not None:
        if not isinstance(records,list) or len({r.get('session_directory') for r in records})!=len(records) or records!=expected:
            raise ValueError('Missing, duplicated or unbound prior service session')
    return expected


def validate_old(old, *, observe=None):
    old=Path(old).resolve(strict=True);observe=observe or c.original.current_process;files={}
    protocol=bind(old/'protocol.json',files);manifest=bind(old/'manifest.json',files)
    authority=bind(old/'authority.json',files);frozen=bind(old/'controller/execution_freeze.json',files)
    stop=bind(old/STOP,files);review=bind(old/REVIEW,files);prechange=bind(old/PRECHANGE,files)
    if c.sha(old/'protocol.json')!=OLD_PROTOCOL_SHA:raise ValueError('Wrong v1 machine protocol')
    if (protocol.get('root')!=str(old) or protocol.get('n')!=560 or protocol.get('allocated')!=560
            or protocol.get('arms')!=list(c.ARMS) or protocol.get('Gold_or_reference_patch_sent_to_model') is not False
            or protocol.get('sealed_project_test_opened') is not False):raise ValueError('Wrong v1 scope or Gold isolation')
    rows=manifest.get('records',[])
    if (manifest.get('n')!=560 or manifest.get('allocated')!=560 or manifest.get('arms')!=list(c.ARMS)
            or len(rows)!=560 or len({r.get('instance_id') for r in rows})!=560
            or [r.get('rank') for r in rows]!=list(range(1,561))):raise ValueError('Full original560 ordered manifest required')
    counts={key:sum(r.get('upstream_status')==key for r in rows) for key in
            ('ready','source_preparation_blocked','upstream_file_stage_unavailable')}
    if counts!={'ready':557,'source_preparation_blocked':2,'upstream_file_stage_unavailable':1}:
        raise ValueError('Availability changed; no resampling or retry')
    if (authority.get('manifest_sha256')!=c.sha(old/'manifest.json')
            or authority.get('protocol_sha256')!=c.sha(old/'protocol.json') or authority.get('Gold_parsed') is not False
            or authority.get('models_called') is not False or authority.get('availability')!=counts):
        raise ValueError('Old preparation authority/Gold isolation mismatch')
    if (frozen.get('status')!='EXECUTION_FROZEN_READY' or frozen.get('manifest_sha256')!=c.sha(old/'manifest.json')
            or frozen.get('protocol_sha256')!=c.sha(old/'protocol.json') or frozen.get('authority_sha256')!=c.sha(old/'authority.json')
            or frozen.get('Gold_scored') is not False):raise ValueError('Old execution freeze changed')
    for path,wanted in frozen['files_sha256'].items():
        if c.sha(path)!=wanted:raise ValueError('Old frozen source/evidence changed')
        files[path]=wanted
    if (not str(prechange.get('status','')).endswith('PASS') or prechange.get('commit')!=frozen.get('commit')
            or prechange.get('current_source_changes')!=[] or prechange.get('remote_all_109_blobs_match_current_bytes') is not True):
        raise ValueError('Recoverable remote prechange verification missing')
    if (stop.get('status')!='ENGINEERING_PREFLIGHT_HEARTBEAT_FAILURE_PRESERVED'
            or stop.get('observed_failure')!=FAILURE or stop.get('benchmark_started_arms')!=0
            or stop.get('benchmark_model_calls')!=0 or stop.get('condition_parameters_changed') is not False
            or stop.get('historical_controls_changed') is not False or stop.get('stop_receipt',{}).get('leader_exited') is not True):
        raise ValueError('Not the verified zero-call 180s heartbeat failure')
    if (review.get('status')!='RUNTIME_ENGINEERING_FAIL_BEFORE_BENCHMARK_CANARY'
            or review.get('failure',{}).get('message')!=FAILURE
            or review.get('observed_benchmark_started_arms')!=0 or review.get('observed_benchmark_main_request_files')!=0
            or review.get('observed_benchmark_judge_start_receipts')!=0 or review.get('benchmark_Gold_parsed') is not False):
        raise ValueError('Independent runtime failure/zero-call evidence missing')
    exits=review.get('owned_process_exit',{})
    if (exits.get('all_recorded_service_leaders_exited') is not True
            or exits.get('all_recorded_positive_CUDA_processes_exited') is not True
            or {x.get('role') for x in exits.get('leaders',[])}!={'controller','main','judge'}
            or not exits.get('positive_cuda_processes')):raise ValueError('Verified owned service/CUDA exit evidence missing')
    for item in exits['leaders']+exits['positive_cuda_processes']:
        if item.get('leader_exited') is not True or same_saved_process(item['saved_identity'],observe(item['saved_identity']['pid'])):
            raise ValueError('An old owned service process remains live')
    # Include launchers/reporters, not merely the three model service leaders.
    owners=list((old/'controller').rglob('ownership.json'))+list((old/'controller').glob('*_ownership.json'))
    for path in owners:
        v=bind(path,files)
        saved=v.get('identity')
        if saved and same_saved_process(saved,observe(saved['pid'])):
            raise ValueError('An old supervised launcher/reporter remains live')
    cleanup=old/'audits/remaining_owned_CPU_stop_before_v2.json'
    if cleanup.exists():
        cleaned=bind(cleanup,files)
        if (cleaned.get('status')!='EXACT_OWNED_CPU_CLEANUP' or cleaned.get('other_processes_signaled') is not False
                or any(x.get('shutdown',{}).get('leader_exited') is not True for x in cleaned.get('records',[]))):
            raise ValueError('Remaining owned CPU cleanup evidence invalid')
    no_benchmark_work(old)
    for row in rows:
        if row['upstream_status']!='ready':
            if row.get('no_model_dispatch') is not True:raise ValueError('Blocked task dispatch contradiction')
            continue
        if row.get('no_model_dispatch') is not False:raise ValueError('Ready dispatch contradiction')
        public=Path(row['public_input_path']);job=c.read(public/'job.json');shared=c.read(public/'shared.json')
        if set(job)!=CLEAN or set(shared)!=SHARED:raise ValueError('Gold/private fields in public inputs')
        for name in ('job.json','shared.json'):
            path=public/name;wanted=row['public_files_sha256'].get(name)
            if not wanted or authority['files_sha256'].get(str(path))!=wanted or c.sha(path)!=wanted:
                raise ValueError('Public identity/shared bytes changed from frozen authority')
        if (any(job.get(k)!=row[k] for k in ('instance_id','repo','base_commit'))
                or shared.get('instance_id')!=row['instance_id'] or shared.get('base_commit')!=row['base_commit']):
            raise ValueError('Public input identity/base mismatch')
    prior=validate_prior_sessions(old)
    extra_cleanup=old/'audits/remaining_owned_CPU_stop_before_v2.json'
    if extra_cleanup.exists():
        cleanup=bind(extra_cleanup,files)
        if cleanup.get('status')!='EXACT_OWNED_CPU_CLEANUP' or any(x.get('same_process_before') is not True
                or x.get('shutdown',{}).get('leader_exited') is not True for x in cleanup.get('records',[])):
            raise ValueError('Additional CPU cleanup proof invalid')
    inventory=None
    if len(prior)>1:
        inventory=bind(old/'audits/post_stop_actual_session_inventory.json',files)
        release=inventory.get('service_release',{})
        if (inventory.get('status')!='POST_STOP_ACTUAL_SESSION_INVENTORY_PASS'
                or inventory.get('actual_prior_session_count')!=len(prior)
                or inventory.get('remaining_session_allowance')!=3-len(prior)
                or inventory.get('benchmark_started_arms')!=0 or inventory.get('benchmark_HTTP_requests')!=0
                or inventory.get('benchmark_judge_attempts')!=0 or inventory.get('all_prior_CPU_launchers_stopped') is not True
                or release.get('all_owned_services_and_CUDA_children_exited') is not True
                or release.get('missing_evidence')!=[]):
            raise ValueError('Actual multiple-session inventory/exit proof invalid')
        if [x.get('session') for x in inventory.get('sessions',[])]!=[Path(x['session_directory']).name for x in prior]:
            raise ValueError('Actual prior session inventory omits/duplicates admission')
    for ordinal,item in enumerate(prior,1):
        directory=Path(item['session_directory']);bind(item['lifetime_admission_path'],files)
        failure=bind(directory/'failure.json',files)
        if ordinal==1:
            if FAILURE not in json.dumps(failure):raise ValueError('Primary failure differs from verified heartbeat failure')
        elif (failure.get('error_type')!='SystemExit' or failure.get('error')!='143'
                or failure.get('controller_launched') is not False or failure.get('semantic_retry') is not False):
            raise ValueError('Additional session was not the witnessed controlled pre-benchmark stop')
        roles=[p.parent for p in directory.glob('*/ownership.json')]
        if ordinal==1 and not roles:
            roles=[directory/x for x in ('controller','main','judge')]
        for role in roles:bind(role/'actual_exit_verification.json',files)
        for path in directory.glob('cuda_ownership*.json'):bind(path,files)
    return protocol,manifest,authority,files,prior


def bridge(from_root,root,*,observe=None):
    old=Path(from_root).resolve(strict=True);new=Path(root).resolve()
    if new==old or old in new.parents or new in old.parents:raise ValueError('Independent new result root required')
    if new.exists():raise FileExistsError('Never overwrite an existing v2 root')
    protocol,manifest,authority,bindings,prior=validate_old(old,observe=observe)
    amendment={'kind':'preflight_validation_heartbeat_propagation_only','old_root':str(old),
        'old_protocol_sha256':c.sha(old/'protocol.json'),'old_manifest_sha256':c.sha(old/'manifest.json'),
        'old_authority_sha256':c.sha(old/'authority.json'),'old_execution_freeze_sha256':c.sha(old/'controller/execution_freeze.json'),
        'failure_observation_path':str(old/REVIEW),'failure_observation_sha256':c.sha(old/REVIEW),
        'failure_stop_path':str(old/STOP),'failure_stop_sha256':c.sha(old/STOP),
        'prechange_receipt_path':str(old/PRECHANGE),'prechange_receipt_sha256':c.sha(old/PRECHANGE),
        'prior_service_sessions':prior,'maximum_cumulative_infrastructure_launches':3,
        'prior_used_service_sessions':len(prior),'remaining_infrastructure_launches':3-len(prior),
        'condition_or_algorithm_parameters_changed':False,'old_benchmark_started_arms':0,'old_benchmark_model_calls':0,
        'manifest_bytes_and_original_public_input_references_preserved':True,'bridge_source_sha256':c.sha(__file__)}
    derived=copy.deepcopy(protocol);derived['root']=str(new);derived['engineering_amendment']=amendment
    if {k:v for k,v in derived.items() if k not in ('root','engineering_amendment')}!={k:v for k,v in protocol.items() if k!='root'}:
        raise ValueError('Algorithm parameter mutation during bridge')
    new.mkdir(parents=True,exist_ok=False)
    with (new/'manifest.json').open('xb') as f:f.write((old/'manifest.json').read_bytes())
    c.write(new/'protocol.json',derived,immutable=True)
    files=copy.deepcopy(authority['files_sha256']);files.update(bindings)
    files[str(old/'manifest.json')]=c.sha(old/'manifest.json');files[str(old/'authority.json')]=c.sha(old/'authority.json')
    files[str(new/'manifest.json')]=c.sha(new/'manifest.json');files[str(new/'protocol.json')]=c.sha(new/'protocol.json')
    newauthority=copy.deepcopy(authority);newauthority.update(protocol_sha256=c.sha(new/'protocol.json'),files_sha256=files,engineering_bridge=amendment)
    c.write(new/'authority.json',newauthority,immutable=True)
    validate_prior_sessions(old,derived['engineering_amendment']['prior_service_sessions'])
    for path,wanted in bindings.items():
        if c.sha(path)!=wanted:raise ValueError('Old immutable evidence changed while bridging')
    receipt={'status':'METADATA_ONLY_ZERO_BENCHMARK_PREFLIGHT_V2_BRIDGE_PASS','old_root':str(old),'new_root':str(new),
        'allocated':560,'availability':authority['availability'],'protocol_sha256':c.sha(new/'protocol.json'),
        'manifest_sha256':c.sha(new/'manifest.json'),'authority_sha256':c.sha(new/'authority.json'),
        'prior_used_service_sessions':len(prior),'remaining_infrastructure_launches':3-len(prior),
        'old_immutable_evidence_sha256':bindings,'algorithm_parameters_equal_except_root_and_engineering_amendment':True,
        'public_input_trees_copied':0,'Gold_read':False,'model_calls':0,'GPU_used':False,'old_files_changed':False}
    c.write(new/'audits/restart_preflight_bridge.json',receipt,immutable=True)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--from-root',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();print(json.dumps(bridge(a.from_root,a.root),ensure_ascii=False))
if __name__=='__main__':main()
