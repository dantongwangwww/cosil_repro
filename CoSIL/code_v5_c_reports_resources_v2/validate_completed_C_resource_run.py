"""Read-only actual checkpoint and resource audit for separately authorized C resources-v2/v3.

Never imports a trainer/model or rewrites a manifest to pretend GPU2. The legacy
B validator remains untouched. Binary checkpoints are hashed, never loaded.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
from code_v5.metrics import evaluate_predictions
from code_v5.coordinate_completed_AB_reports_v3 import assert_adapter
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/v5_pruner'
C_RUN = BASE / 'C_Verified_plus_B_runtime_resources_v2_exploratory'
C_DATA = BASE / 'data_verified_plus_B_runtime_reviewed'
C_DECISION = BASE / 'C_Verified_plus_B_runtime_authorization_exploratory/root_exploratory_decision.json'
C_DECISION_SHA = '1ff55fcbe20a5525b57f5afa086f500634481945679f13740062a8af456390d4'
RESOURCE_AUTH = BASE / 'C_dynamic_GPU_resource_authorization_v2.json'
RESOURCE_POLICY = 'any_naturally_idle_gpu_no_reservation_v2'
RESOURCE_AUTH_SHA = 'bb6a424cf2e353b1309a2d4aa9ec33f3a13b4448c32e1db819958931da898680'
PACKAGE = ('__init__.py','train_judges.py','race_and_calibrate.py','run_training_pair.py','run_sequence.py','report_outcome.py')
VERSIONS={2:{'run':C_RUN,'auth':RESOURCE_AUTH,'package':'code_v5_expanded_resources_v2','policy':RESOURCE_POLICY,'queue':BASE/'C_training_queue_release.json','sharing':False,'interval':10,'pause':'terminate_own_child_preserve_completed_checkpoints'},
          3:{'run':BASE/'C_Verified_plus_B_runtime_resources_v3_exploratory','auth':BASE/'C_shared_GPU_resource_authorization_v3.json','package':'code_v5_expanded_resources_v3','policy':'shared_gpu_with_sufficient_headroom_v3','queue':BASE/'C_training_queue_release_resources_v3.json','sharing':True,'interval':30,'pause':'no_foreign_context_yield_record_failure_only'}}
OVERRIDE=BASE/'GPU_sharing_user_override_policy_v3.json'
OVERRIDE_SHA='df207093f60280035081576ed025e1966ef7e3503dea1e4a1d7c5f00f1ffdceb'
PROFILES = {'reranker':{'rank':8,'alpha':32,'dropout':.1},'instruct':{'rank':16,'alpha':32,'dropout':0.}}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def read(path):
    path=Path(path).resolve()
    if path.suffix!='.json' or re.search(r'(?:^|[/_.-])test(?:$|[/_.-])',str(path).lower()):
        raise PermissionError('CPU resource metadata reader refuses test/JSONL before open')
    return json.loads(path.read_text())

def rows(path):
    path=Path(path).resolve()
    if re.search(r'(?:^|[/_.-])test(?:$|[/_.-])',str(path).lower()) or not re.fullmatch(r'(?:pruner_(?:train|val)|(?:train|val)_epoch_[1-9][0-9]*)\.jsonl',path.name):
        raise PermissionError('CPU checkpoint audit reads exact train/val source or assessment rows only')
    split='train' if path.name.startswith(('train_','pruner_train')) else 'val'
    result=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if any(r.get('split')!=split for r in result):raise ValueError('Saved checkpoint/source split differs')
    return result

def require_sha(path,expected,message):
    if sha(path)!=expected:raise ValueError(message)

def option(command,name):
    if not isinstance(command,list) or not all(isinstance(x,str) for x in command) or command.count(name)!=1:
        raise ValueError('Ambiguous actual direct-child command option '+name)
    i=command.index(name)
    if i+1>=len(command):raise ValueError('Missing direct-child option '+name)
    return command[i+1]

def resource_root_metadata(version):
    cfg=VERSIONS[version];auth_path=cfg['auth']
    require_sha(auth_path,RESOURCE_AUTH_SHA if version==2 else '43198c2742e4a7e476955734ac220c5db397c893ea2c1b4f722901d7cea19a00','Actual root resource-v2/v3 authorization hash changed')
    auth=read(auth_path)
    expected={'root_authorized':True,'allow_C_training':True,'track':'exploratory','test_open_allowed':False,
        'data_policy':'verified-plus-B-runtime-v1','resource_policy':cfg['policy'],'allowed_gpu_ids':[0,1,2,3],
        'reserved_gpu_ids':[],'peer_processes_may_be_modified':False,'allow_sharing_busy_gpu':cfg['sharing'],
        'yield_on_foreign_gpu_use':not cfg['sharing'],'monitor_interval_seconds':cfg['interval'],
        'pause_action':cfg['pause'],'C_decision_sha256':C_DECISION_SHA,
        'adapter_profiles':PROFILES}
    if version==2:expected['C_data_dir']=str(C_DATA)
    if version==3:
        require_sha(OVERRIDE,OVERRIDE_SHA,'User shared-GPU override receipt changed')
        expected.update(minimum_free_mib=12288,user_override_receipt_sha256=OVERRIDE_SHA)
    if any(auth.get(k)!=v for k,v in expected.items()) or sha(C_DECISION)!=C_DECISION_SHA:
        raise ValueError('Actual root C resource authorization differs from frozen data/no-sharing protocol')
    old={f'code_v5_expanded/{n}':sha(ROOT/'code_v5_expanded'/n) for n in PACKAGE}
    new={f"{cfg['package']}/{n}":sha(ROOT/cfg['package']/n) for n in PACKAGE}
    if auth.get('C_original_code_sha256')!=old or auth.get('C_resources_v'+str(version)+'_code_sha256')!=new:
        raise ValueError('Actual original C6 or separately authorized resource-v2 source drift')
    files={str(auth_path):sha(auth_path),str(C_DECISION):C_DECISION_SHA,
           **{str(ROOT/k):v for k,v in old.items()},**{str(ROOT/k):v for k,v in new.items()}}
    if version==3:files[str(OVERRIDE)]=OVERRIDE_SHA
    return auth,files

def validate_pair_record(pair,kind,gpu,run,data,version=2):
    """Pure structural guard, suitable for explicitly synthetic CPU tests."""
    cfg=VERSIONS[version]
    if (pair.get('stage')!='complete' or pair.get('test_opened') is not False
            or pair.get('resource_policy')!=cfg['policy'] or pair.get('allowed_gpu_ids')!=[0,1,2,3]
            or pair.get('reserved_free_gpu_ids')!=[] or pair.get('effective_batch')!=8 or pair.get('micro_batch')!=2
            or len(pair.get('runs',[]))!=2 or {r.get('kind') for r in pair['runs']}!={'reranker','instruct'}):
        raise ValueError('C-v2 real completed pair/direct-child evidence absent or inconsistent')
    records=[r for r in pair['runs'] if r['kind']==kind]
    if len(records)!=1:raise ValueError('Repeated/favorable C direct-child selection forbidden')
    record=records[0];pre=record.get('gpu_preflight',{});monitor=record.get('resource_monitor',{})
    command=record.get('command')
    if (pre.get('assigned')!=gpu or type(pre.get('assigned')) is not int
            or pre.get('allowed_gpu_ids')!=[0,1,2,3] or pre.get('reserved_free_gpu_ids')!=[]
            or pre.get('resource_policy')!=cfg['policy'] or pre.get('peer_processes_modified_by_this_experiment') is not False
            or type(record.get('returncode')) is not int or record.get('returncode')!=0
            or type(monitor.get('returncode')) is not int or monitor.get('returncode')!=0 or monitor.get('paused') is not False
            or type(monitor.get('own_child_pid')) is not int or monitor['own_child_pid']<=0
            or monitor.get('peer_processes_stopped_or_modified') is not False
            or not isinstance(record.get('started_at'),str) or not isinstance(record.get('finished_at'),str)):
        raise ValueError('C actual pair GPU/direct-owned-child result differs from saved manifest')
    if (option(command,'-m')!=cfg['package']+'.train_judges' or option(command,'--gpu')!=str(gpu)
            or option(command,'--kind')!=kind or Path(option(command,'--output-dir')).resolve()!=run
            or Path(option(command,'--data-dir')).resolve()!=data
            or Path(option(command,'--decision-file')).resolve()!=C_DECISION
            or option(command,'--track')!='exploratory' or option(command,'--data-policy')!='verified-plus-B-runtime-v1'
            or option(command,'--effective-batch')!='8' or option(command,'--micro-batch')!='2'):
        raise ValueError('Actual C direct-child argv is not the authorized source/GPU/data/profile')
    inventory=pre.get('inventory',{})
    if (not isinstance(inventory,dict) or {str(k) for k in inventory}!={'0','1','2','3'}
            or not isinstance(pre.get('full_processes'),list) or not isinstance(pre.get('compute_apps'),list)
            or not isinstance(pre.get('snapshots'),list) or not pre['snapshots']):
        raise ValueError('Actual GPU selection lacks complete C/G/compute observation')
    card=inventory.get(str(gpu),inventory.get(gpu))
    if (not isinstance(card,dict) or not isinstance(card.get('uuid'),str) or not card['uuid']):
        raise ValueError('Recorded actual selected card missing UUID')
    if version==2:
        if (type(card.get('memory_mib')) not in (int,float) or not math.isfinite(card['memory_mib'])
                or not 0<=card['memory_mib']<=128 or type(card.get('utilization')) is not int or card['utilization']!=0):
            raise ValueError('Resource-v2 assigned card was not naturally idle')
        for process in pre['full_processes']:
            if process.get('gpu_uuid')==card['uuid'] and not (process.get('type')=='G' and Path(process.get('process_name','')).name=='Xorg'):
                raise ValueError('Resource-v2 selected GPU had a non-Xorg C/G context')
        import csv
        for app in csv.reader(pre['compute_apps']):
            if app and app[0].strip()==card['uuid']:raise ValueError('Resource-v2 GPU already had a compute process')
    else:
        if (pre.get('sharing_allowed') is not True or pre.get('minimum_free_mib')!=12288
                or type(card.get('memory_free_mib')) is not int or card['memory_free_mib']<12288
                or monitor.get('sharing_allowed') is not True or monitor.get('peer_context_causes_yield') is not False
                or monitor.get('automatic_config_change_or_resume') is not False):
            raise ValueError('Actual v3 shared GPU had insufficient headroom or wrong monitoring policy')
    return record

def audit_C_resource_execution(run,data,manifest,kind):
    run=Path(run).resolve();data=Path(data).resolve()
    matches=[v for v,cfg in VERSIONS.items() if run==cfg['run']/'training'/kind]
    if kind not in PROFILES or len(matches)!=1 or data!=C_DATA:
        raise PermissionError('Resource validator accepts only the actual authorized C-v2 run/data namespace')
    version=matches[0];cfg=VERSIONS[version];auth_path=cfg['auth'];auth,files=resource_root_metadata(version);gpu=manifest.get('physical_gpu')
    if type(gpu) is not int or gpu not in auth['allowed_gpu_ids']:
        raise ValueError('Actual physical GPU missing/outside root allowed IDs; GPU2 is not substituted')
    descriptor={'path':str(auth_path),'sha256':sha(auth_path),'policy':cfg['policy'],
        'allowed_gpu_ids':[0,1,2,3],'reserved_gpu_ids':[],'peer_processes_modified':False,
        'yield_on_foreign_gpu_use':not cfg['sharing'],'monitor_interval_seconds':cfg['interval']}
    if version==3:descriptor.update(sharing_allowed=True,minimum_free_mib=12288)
    expected_code={cfg['package']+'/train_judges.py':auth['C_resources_v'+str(version)+'_code_sha256'][cfg['package']+'/train_judges.py'],
        **{f'code_v5/{n}':sha(ROOT/'code_v5'/n) for n in ('judge_models.py','metrics.py')},
        'code_v5_verified/expanded_policy.py':sha(ROOT/'code_v5_verified/expanded_policy.py')}
    if (manifest.get('resource_authorization')!=descriptor or manifest.get('code_sha256')!=expected_code
            or manifest.get('root_decision')!=manifest['data']['root_decision']
            or manifest['data']['root_decision'].get('path')!=str(C_DECISION)
            or manifest['data']['root_decision'].get('sha256')!=C_DECISION_SHA):
        raise ValueError('C-v2 manifest is not honest about root resource/data/new source identity')
    pair_path=cfg['run']/'training/pair_status.json';pair=read(pair_path)
    record=validate_pair_record(pair,kind,gpu,run,data,version)
    monitor=record['resource_monitor']
    queue_path=cfg['queue'];queue=read(queue_path)
    if version==3:require_sha(queue_path,'1d13e7fa32aa45ea58b4eae58ac92b1005eef41e1eb78e6a21328be16597583e','Actual shared-v3 root queue changed')
    if (queue.get('allow_C_training') is not True or queue.get('test_open_allowed') is not False
            or queue.get('C_decision_sha256')!=C_DECISION_SHA or queue.get('resource_policy')!=cfg['policy']
            or queue.get('resource_authorization_sha256')!=sha(auth_path)):
        raise ValueError('C root queue/resource linkage differs')
    bparent=BASE/'B_runtime_reviewed_regularized_exploratory'
    for rel,digest in queue['actual_complete_B_receipts_sha256'].items():
        require_sha(ROOT/rel,digest,'Real completed B queue receipt drift');files[str(ROOT/rel)]=digest
    if option(record['command'],'--model-dir')!=manifest['model']['path']:
        raise ValueError('Actual child base-model path differs from manifest fingerprint')
    if version==3:
        path=Path(monitor.get('resource_observation_path','')).resolve()
        expected_path=cfg['run']/'training'/f'{kind}_shared_GPU_observations.jsonl'
        if path!=expected_path:raise PermissionError('C resource observations path escapes actual owned run')
        observations=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        first=observations[0] if observations else {}
        if (first.get('event')!='own_child_created' or first.get('own_child_pid')!=monitor['own_child_pid']
                or first.get('physical_gpu')!=gpu or first.get('sharing_allowed') is not True):
            raise ValueError('Actual owned direct-child origin does not bind shared resource log')
        count=0
        for event in observations[1:]:
            if event.get('stopped_any_process') is not False:raise ValueError('Shared resource log claims any process control')
            if event.get('event')=='shared_GPU_observation':
                if (event.get('own_child_pid')!=monitor['own_child_pid'] or event.get('physical_gpu')!=gpu
                        or event.get('sharing_allowed') is not True):raise ValueError('Shared event child/GPU drift')
                count+=1
            elif event.get('event')!='GPU_observation_unavailable_training_continues':raise ValueError('Unknown shared resource event')
        if count!=monitor.get('observations'):raise ValueError('Actual shared observation count differs from completion monitor')
        files[str(path)]=sha(path)
    files.update({str(pair_path):sha(pair_path),str(queue_path):sha(queue_path),
                  **{str(ROOT/k):v for k,v in expected_code.items()}})
    return {'resource_version':version,'physical_gpu':gpu,'actual_direct_child_pid':monitor['own_child_pid'],
        'resource_authorization':descriptor,'actual_pair_record':record,
        'files_sha256':files,'manifest_rewritten_or_GPU_substituted':False,
        'test_rows_decoded':False,'model_loaded':False}

def validate_run(run, data, *, kind, rank, dropout):
    mp = run / 'training_manifest.json'; sp = run / 'training_summary.json'
    manifest, summary = read(mp), read(sp)
    expected = {'kind': kind, 'rank': rank, 'alpha': 32, 'dropout': dropout, 'learning_rate': 5e-5,
                'epochs': 3, 'effective_batch': 8, 'micro_batch': 2, 'cutoff': 4096,
                'gradient_checkpointing': True, 'only_lora_trainable': True}
    resource = audit_C_resource_execution(run, data, manifest, kind)
    if any(manifest.get(k) != v for k, v in expected.items()): raise ValueError('Real run configuration differs: ' + str(run))
    if summary.get('test_opened') is not False or summary.get('track') != 'exploratory': raise ValueError('Completed exploratory summary required')
    if manifest['data']['test_labels_read'] is not False: raise ValueError('Training manifest reports test access')
    for field, name in (('statistics_sha256', 'statistics.json'), ('seal_sha256', 'test_file_seal.json'), ('split_manifest_sha256', 'split_manifest.json')):
        if manifest['data'][field] != sha(data / name): raise ValueError('Training data provenance differs from frozen version')
    for path, digest in manifest['code_sha256'].items():
        source = ROOT / (path if path.startswith('code_v5') else 'code_v5/' + path)
        if sha(source) != digest: raise ValueError('Trainer code changed')
    curves_path = run / 'training_curves.json'; curves = read(curves_path)
    if [c['epoch'] for c in curves] != list(range(1, summary['epochs_completed'] + 1)):
        raise ValueError('Missing real completed epochs')
    files = {str(p): sha(p) for p in (mp, sp, curves_path)}
    files.update(resource['files_sha256'])
    best = summary['checkpoint_assessments']['best']
    if Path(best['checkpoint']).resolve() != Path(summary['best']).resolve(): raise ValueError('Actual best checkpoint differs from assessment')
    if rank == 8:
        peak = max(curves, key=lambda c: (c['val']['overall']['accuracy'], c['val']['overall']['auc'], c['val']['E_correct_rejection_rate'], -c['epoch']))
        if best['epoch'] != peak['epoch']: raise ValueError('Reranker prescribed completed-epoch val peak not selected')
    measured = {}
    for role in ('best', 'last'):
        assessment = summary['checkpoint_assessments'][role]
        cp = Path(assessment['checkpoint']).resolve()
        if cp.parent != run.resolve() or cp.name != f"epoch_{assessment['epoch']}": raise ValueError('Checkpoint identity/path drift')
        complete_path = cp / 'checkpoint_complete.json'; complete = read(complete_path)
        if complete['epoch'] != assessment['epoch'] or complete['manifest_sha256'] != sha(mp): raise ValueError('Unfinished/unbound checkpoint')
        for field, name in (('adapter_sha256', 'adapter_model.safetensors'), ('training_state_sha256', 'training_state.pt'), ('judge_metadata_sha256', 'judge_metadata.json')):
            if sha(cp / name) != complete[field]: raise ValueError('Checkpoint binary artifact changed')
            files[str(cp / name)] = complete[field]
        adapter_path = cp / 'adapter_config.json'; adapter = read(adapter_path); assert_adapter(adapter, manifest)
        metadata = read(cp / 'judge_metadata.json')
        if metadata['training_manifest_sha256'] != sha(mp) or metadata['kind'] != kind: raise ValueError('Judge metadata drift')
        files[str(adapter_path)] = sha(adapter_path); files[str(complete_path)] = sha(complete_path)
        trainp = Path(assessment['train_prediction_path'])
        if trainp.resolve() != (run / f"train_epoch_{assessment['epoch']}.jsonl").resolve(): raise ValueError('Unexpected train assessment path')
        if sha(trainp) != assessment['train_prediction_sha256']: raise ValueError('Actual train assessment SHA differs')
        train_rows = rows(trainp); train_truth = rows(data / 'pruner_train.jsonl')
        tp = {(r['instance_id'], r['function_id']): r for r in train_rows}
        truth = {(r['instance_id'], r['function_id']): r for r in train_truth}
        if len(tp) != len(train_rows) or tp.keys() != truth.keys() or any(tp[k]['label'] != truth[k]['label'] for k in truth):
            raise ValueError('Actual train assessment differs from frozen train pairs/labels')
        train_metrics = evaluate_predictions(train_rows)
        if train_metrics != assessment['train']: raise ValueError('Stored train metrics do not reproduce actual probabilities')
        valp = run / f"val_epoch_{assessment['epoch']}.jsonl"; val = rows(valp); vt = rows(data / 'pruner_val.jsonl')
        vp = {(r['instance_id'], r['function_id']): r for r in val}; vi = {(r['instance_id'], r['function_id']): r for r in vt}
        if len(vp) != len(val) or vp.keys() != vi.keys() or any(vp[k]['label'] != vi[k]['label'] for k in vi):
            raise ValueError('Actual val assessment differs from frozen val pairs/labels')
        val_metrics = evaluate_predictions(val)
        if val_metrics != assessment['val'] or val_metrics != next(c['val'] for c in curves if c['epoch'] == assessment['epoch']):
            raise ValueError('Stored val metrics do not reproduce actual probabilities')
        files[str(trainp)] = sha(trainp); files[str(valp)] = sha(valp)
        measured[role] = {'epoch': assessment['epoch'], 'train_accuracy': train_metrics['overall']['accuracy'],
                          'val_accuracy': val_metrics['overall']['accuracy'], 'actual_rank': adapter['r'],
                          'actual_alpha': adapter['lora_alpha'], 'actual_dropout': adapter['lora_dropout']}
    return {'run': str(run), 'expected_configuration': expected, 'roles': measured, 'files_sha256': files,
            'best_val_prediction_path': str(run / f"val_epoch_{best['epoch']}.jsonl"), 'test_rows_decoded': False, 'resource_execution': resource}
