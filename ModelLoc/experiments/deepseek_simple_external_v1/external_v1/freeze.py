"""Freeze P2 integration only after deterministic external preparation is signed.

This command performs no model forward, paid request, or test execution.
"""
from pathlib import Path
import argparse,copy,hashlib,json,sys
from datetime import datetime,timezone

ROOT=Path('/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1')
FROZEN=ROOT.with_name('deepseek_simple_v1')
COSIL=ROOT.parents[2]/'CoSIL'
RUN_ID='20261021_external_nonthinking_v1'
RUN=ROOT/'runs'/RUN_ID
BACKUP='809f568eaeb221eb475ce69d2c7d9e83fe9d433f'

def sha(p):
    p=Path(p)
    if 'pruner_test' in p.name:raise PermissionError('Sealed test content forbidden')
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    p=Path(p)
    if 'pruner_test' in p.name:raise PermissionError('Sealed test content forbidden')
    return json.loads(p.read_text())

def freeze():
    sys.path.insert(0,str(COSIL))
    from code_v6.common import test_stats
    seal=test_stats();old=read(FROZEN/'configs/resolved_config.json')
    if seal!=old['test_stats_before']:raise RuntimeError('Sealed test metadata changed')
    ready_path=RUN/'preparation_freeze_ready.json'
    if not ready_path.exists():raise RuntimeError('Final preparation corrections are not signed ready')
    ready=read(ready_path)
    manifest_path=ROOT/'manifests/external.json';manifest=read(manifest_path)
    if ready.get('status')!='READY' or not ready.get('metadata_corrections_applied') or not ready.get('official_lfs_identity_verified'):
        raise RuntimeError('Final data-preparation signature is incomplete')
    if ready.get('external_manifest_sha256')!=sha(manifest_path):raise RuntimeError('Manifest differs from preparation signature')
    if manifest['n']!=100 or len(manifest['records'])!=100 or len({r['repo'].lower() for r in manifest['records']})!=100:
        raise RuntimeError('Need exactly 100 distinct repositories')
    repair=read(ROOT/'manifests/repair_subset.json')
    if repair.get('selection_namespace')!='repair-subset' or repair['n']!=30:
        raise RuntimeError('Repair ID preselection namespace mismatch')
    if ready.get('repair_manifest_sha256')!=sha(ROOT/'manifests/repair_subset.json'):
        raise RuntimeError('Repair ID manifest differs from signed preparation')
    if not read(RUN/'local_model_artifact_hashes.json')['all_match_P1']:
        raise RuntimeError('Local model fingerprints not verified against P1')
    if (ROOT/'configs/resolved_config.json').exists():
        raise RuntimeError('P2 config already frozen; do not overwrite it')
    data={}
    for rec in manifest['records']:
        job=read(rec['job'])
        for path in (rec['job'],job['code_index'],job['structure']):
            if not Path(path).resolve().is_relative_to(ROOT/'jobs'):raise RuntimeError('Job artifact outside clean directory')
            data[str(path)]=sha(path)
    code={str(p):sha(p) for p in sorted((ROOT/'external_v1').glob('*.py'))}
    for directory in ['prompts','scripts']:
        for path in sorted((ROOT/directory).iterdir()):
            if path.is_file():
                if sha(path)!=sha(FROZEN/directory/path.name):raise RuntimeError('Frozen prompt/script drift')
                code[str(path)]=sha(path)
    tokenizer=ROOT/'resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json'
    if sha(tokenizer)!=sha(FROZEN/'resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json'):
        raise RuntimeError('Tokenizer drift')
    code[str(tokenizer)]=sha(tokenizer)
    pin=read(ROOT/'manifests/dataset_pin.json')
    config=copy.deepcopy(old)
    config.update(run_id=RUN_ID,created_at=datetime.now(timezone.utc).isoformat(),
        frozen_parent_run_id=old['run_id'],frozen_parent_config_sha256=sha(FROZEN/'configs/resolved_config.json'),
        pre_change_backup_commit=BACKUP,dataset=pin,
        stage_authorization={'P0':False,'P1':False,'P2':True,'P3':False,'High':False})
    config['budget'].pop('pilot_usd',None)
    config['budget']['external_and_repair_usd']=30
    config['price_snapshot']['reverified_at']=config['created_at']
    config['price_snapshot']['version_and_rates_unchanged_from_P1']=True
    config['p2']={'run_id':RUN_ID,'cohort':'external','authorization':{'P2':True,'P3':False,'High':False},
        'user_authorization':'2026-10-21: 进行外部验证','budget_usd':30,'selected_n':100,'expected_results':400,
        'manifest_path':str(manifest_path),'manifest_sha256':sha(manifest_path),
        'repair_id_manifest_sha256':sha(ROOT/'manifests/repair_subset.json'),
        'code_sha256':code,'data_sha256':data,'backup_commit':BACKUP,
        'preparation_ready_sha256':sha(ready_path),
        'local_model_hashes_sha256':sha(RUN/'local_model_artifact_hashes.json'),
        'gpu_main':0,'gpu_judge':2,'original_methods_unchanged':True,
        'private_data_directory':str(ROOT/'evaluator_private'),'P3_test_qualification':'NOT_CHECKED'}
    path=ROOT/'configs/resolved_config.json'
    path.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    import yaml
    (ROOT/'configs/resolved_config.yaml').write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False))
    receipt={'frozen_at':config['created_at'],'config_sha256':sha(path),'manifest_sha256':sha(manifest_path),
        'integration_source_count':len(code),'clean_artifacts_frozen':len(data),'ready_receipt':ready,
        'test_metadata_unchanged':test_stats()==seal,'paid_calls':0,'GPU_forwards':0,
        'only_P2_authorized':True,'backup_commit':BACKUP}
    (RUN/'freeze_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='ready_receipt'},ensure_ascii=False))
    return config

if __name__=='__main__':freeze()
