"""Freeze metadata-only 280/20 scopes and build official membership-only graphs."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
from pathlib import Path,PurePosixPath
import os
import shutil
import time
from rebench_qwen3.worker import instance,sha,write

ROOT=Path(__file__).resolve().parents[1]


def digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def selected(records,limit):
    if not 1<=limit<=len(records):raise ValueError('Invalid fixed-prefix scope')
    ids=[x['instance_id'] for x in records]
    if len(set(ids))!=len(ids) or len({x['repo'].casefold() for x in records})!=len(records):
        raise ValueError('Frozen parent must have unique issues and repositories')
    return records[:limit]


def metadata(source_run,run):
    source=Path(source_run).resolve(strict=True);run=Path(run).absolute()
    parent_path=source/'selection/manifest.json';parent=json.loads(parent_path.read_text());records=parent['records']
    if parent['n']!=280 or len(records)!=280:raise ValueError('Require the unchanged full280 source manifest')
    selected(records,20)
    sources_path=source/'selection/snapshot_sources.json';sources=json.loads(sources_path.read_text())
    projected=[]
    for row in records:
        iid=row['instance_id']
        if Path(iid).name!=iid:raise ValueError('Unsafe issue ID')
        p=source/row['instance'];public=instance(p)
        if any(public[k]!=row[k] for k in ['instance_id','repo','base_commit']) or sha(p)!=row['instance_sha256']:
            raise ValueError('Parent public instance identity/SHA differs')
        if digest(sources[iid]['files'])!=row['snapshot_tree_sha256']:
            raise ValueError('Parent source tree manifest differs')
        projected.append({k:row[k] for k in ['instance_id','repo','base_commit','source_id']}|{
            'instance':f'public/tasks/{iid}/instance.json','instance_sha256':row['instance_sha256'],
            'snapshot':f'public/snapshots/{iid}','snapshot_tree_sha256':row['snapshot_tree_sha256'],
            'graph':f'public/graphs/{iid}.json','graph_receipt':f'public/graphs/{iid}.receipt.json',
            'source_instance':str(p.resolve()),'source_snapshot':str((source/row['snapshot']).resolve())})
    # Prefix decisions are fixed before inspecting any evaluation metadata.
    summary_path=source/'reports/final_delivery/summary.json';summary=json.loads(summary_path.read_text())
    if summary['status']!='FINAL' or summary['allocated']!=280:raise ValueError('Source report must be frozen FINAL280')
    reference=source/'reports/final_delivery/evaluation.json'
    evaluation={name:str(source/path) for name,path in {'gold':'private/gold.json','inventory':'private/inventory.json',
        'comparison':'private/comparison_original.csv','reference_evaluation':'reports/final_delivery/evaluation.json'}.items()}
    evaluation.update({name+'_sha256':summary['source_sha256'][name] for name in ['gold','inventory','comparison']})
    evaluation.update(reference_evaluation_sha256=sha(reference),evaluator_sha256=summary['frozen_evaluator_sha256'],
                      source_run=str(source),gold_files_opened_by_prepare=0)
    run.mkdir(parents=True,exist_ok=True)
    for name in ['selection','public','private']:
        if (run/name).exists():raise FileExistsError('Refuse to overwrite frozen assets: '+name)
    (run/'selection').mkdir();(run/'private').mkdir(mode=0o700)
    for name in ['tasks','snapshots','graphs']:(run/'public'/name).mkdir(parents=True,exist_ok=True)
    shutil.copyfile(parent_path,run/'selection/parent_locagent_manifest.json')
    write(run/'selection/snapshot_sources.json',sources)
    manifest={'schema':1,'n':280,'records':projected,'source_run':str(source),
        'source_manifest_sha256':sha(parent_path),'source_snapshot_manifest_sha256':sha(sources_path),
        'selection_rule':'Unchanged full280 parent order; pilot20 is records[:20]; no outcome-based selection',
        'cohort_origin':parent['cohort_origin'],'independent_blind_test':False,
        'public_schema':['instance_id','repo','base_commit','problem_statement'],
        'graph_protocol':'Official TREE_SITTER membership skeleton; dependencies only added by original agents at runtime',
        'source_namespace':'/source','graph_dependency_prewarming':False,'new_model_calls':0,
        'prechange_commit':'3946a5a21ad2ce50f86684efc6d76d799a28c9bd'}
    write(run/'selection/manifest.json',manifest)
    write(run/'selection/pilot20.json',{'schema':1,'n':20,'records':projected[:20],
        'full_manifest_sha256':sha(run/'selection/manifest.json'),'selection_rule':'Fixed full280 prefix20; no performance access'})
    write(run/'private/evaluation_sources.json',evaluation)
    return manifest


def materialize(run,row,sources):
    run=Path(run);iid=row['instance_id'];source=Path(row['source_snapshot']).resolve(strict=True)
    for item in sources[iid]['files']:
        rel=PurePosixPath(item['path'])
        if rel.is_absolute() or '..' in rel.parts or '.git' in rel.parts or rel.suffix!='.py':raise ValueError('Unsafe source path')
        actual=(source/item['path']).resolve(strict=True)
        if not actual.is_relative_to(source) or sha(actual)!=item['sha256']:raise ValueError('Base source SHA differs: '+iid+'/'+item['path'])
    public=Path(row['source_instance']);target=run/row['instance'];target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if sha(target)!=row['instance_sha256']:raise ValueError('Public instance changed')
    else:
        shutil.copyfile(public,target);target.chmod(0o444)
    destination=run/row['snapshot']
    if destination.exists():
        if not destination.is_symlink() or destination.resolve()!=source:raise ValueError('Snapshot pointer changed')
    else:destination.symlink_to(source,target_is_directory=True)


def graph_case(run,row,sources,timeout=1800):
    locks=Path(run)/'graph_build/locks';locks.mkdir(parents=True,exist_ok=True)
    with (locks/(row['instance_id']+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _graph_case(run,row,sources,timeout)


def _graph_case(run,row,sources,timeout=1800):
    from rebench_qwen3.runner import run_case
    run=Path(run);iid=row['instance_id'];materialize(run,row,sources)
    graph=run/row['graph'];receipt=run/row['graph_receipt']
    builder=sha(ROOT/'rdfs/dependency_graph/graph_generator/tree_sitter_generator/__init__.py')
    if receipt.exists():
        value=json.loads(receipt.read_text())
        if value.get('snapshot_tree_sha256')!=row['snapshot_tree_sha256'] or value.get('builder_sha256')!=builder:
            raise ValueError('Cached graph protocol/source changed')
        if value['status']=='success' and sha(graph)!=value['graph_sha256']:raise ValueError('Cached graph bytes changed')
        return value
    started=time.monotonic()
    value={k:row[k] for k in ['instance_id','repo','base_commit']}|{'status':'failed','terminal':True,
        'snapshot_tree_sha256':row['snapshot_tree_sha256'],'builder_sha256':builder,
        'source_namespace':'/source','dependency_prewarming':False,'gold_read':False,'model_calls':0}
    try:
        execution=run_case(run,iid,phase='build_graph',timeout=timeout)
        work=run/'graph_build/cases'/iid;child=json.loads((work/'build_receipt.json').read_text())
        if execution['returncode'] or execution['timed_out'] or child['status']!='success':raise RuntimeError('Graph builder failed')
        if child['repo_path']!='/source' or child['dependency_prewarming'] is not False:raise ValueError('Graph namespace or algorithm differs')
        raw=work/'graph.json'
        if sha(raw)!=child['graph_sha256']:raise ValueError('Generated graph SHA differs')
        with raw.open('rb') as src,graph.open('xb') as dst:shutil.copyfileobj(src,dst)
        graph.chmod(0o444);value.update(child,status='success')
    except Exception as error:value.update(error_type=type(error).__name__,error=str(error))
    value['preparation_wall_seconds']=time.monotonic()-started;write(receipt,value)
    return value


def graphs(run,limit=20,workers=2,timeout=1800):
    run=Path(run).resolve(strict=True);manifest=json.loads((run/'selection/manifest.json').read_text())
    source=Path(manifest['source_run'])
    if sha(source/'selection/manifest.json')!=manifest['source_manifest_sha256']:raise ValueError('Source full manifest changed')
    sources=json.loads((run/'selection/snapshot_sources.json').read_text());rows=selected(manifest['records'],limit)
    if not 1<=workers<=4:raise ValueError('Use1-4 CPU preparation workers')
    values=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(graph_case,run,row,sources,timeout):row['instance_id'] for row in rows}
        for future in as_completed(pending):values.append(future.result())
    summary={'scope':limit,'terminal':len(values),'success':sum(x['status']=='success' for x in values),
             'failed':sum(x['status']!='success' for x in values),'workers':workers,'model_calls':0,'gold_read':False}
    print(json.dumps(summary),flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-run',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--phase',choices=['metadata','graphs','all'],default='all')
    p.add_argument('--limit',type=int,default=20);p.add_argument('--workers',type=int,default=2);p.add_argument('--timeout',type=float,default=1800)
    a=p.parse_args()
    if a.phase in ['metadata','all']:metadata(a.source_run,a.run)
    if a.phase in ['graphs','all']:graphs(a.run,a.limit,a.workers,a.timeout)


if __name__=='__main__':main()
