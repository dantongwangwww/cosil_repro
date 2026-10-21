"""CPU-only preregistration. Reads only the explicitly authorized Lite-50 jobs."""
import hashlib,importlib.metadata,json,subprocess
from pathlib import Path
from .common import *
METHODS=['D-COSIL','Q-COSIL','Q-PRUNER']

def frozen_subset(recs):
    ordered=sorted(recs,key=lambda r:digest(r['instance_id']))
    smoke=[r['instance_id'] for r in ordered[:5]]; chosen=list(smoke)
    # Include smoke then at least one per repository; fill by plain SHA order.
    represented={r['repo'] for r in ordered if r['instance_id'] in chosen}
    for r in ordered:
        if r['repo'] not in represented:
            chosen.append(r['instance_id']);represented.add(r['repo'])
    for r in ordered:
        if len(chosen)==20:break
        if r['instance_id'] not in chosen:chosen.append(r['instance_id'])
    if len(chosen)!=20:raise RuntimeError('Expected fixed20')
    return ordered,smoke,chosen

def snapshot_upstream(rec,method,inventory):
    src=OLD/'lite_pilot'/method/rec['instance_id']; dest=RUN/'upstream'/method/rec['instance_id']
    events=[json.loads(s) for s in (src/'events.jsonl').read_text().splitlines()] if (src/'events.jsonl').exists() else []
    file_end=[e for e in events if e.get('event')=='file_stage_end']; start=[e for e in events if e.get('event')=='search_start']
    nodes=sorted((src/'calls').glob('*_node_selection/request.json'))
    initials=sorted((src/'calls').glob('*_initial_selection/request.json'))
    status={'status':'upstream_failure','reason':'historical_file_stage_failed','files':[],'historical_method':method}
    if file_end and start:
        files=file_end[-1]['found_files'][:5]
        if files!=start[0]['files']:raise RuntimeError('Frozen starting files differ')
        status.update(files=files,reason='historical_initial_selection_failed')
        if nodes and initials and (initials[0].parent/'result.json').exists():
            status.update(status='ready',reason=None)
            for p in [nodes[0],initials[0],initials[0].parent/'result.json']:
                rel=p.relative_to(src);write(dest/rel,read(p));inventory[str(p)]=sha(p)
        subset=events[:events.index(start[0])+1]
    else:subset=[e for e in events if e.get('event') in ('file_stage_end','search_start')]
    # Only pre-search events; no historical decisions, source, or final predictions.
    p=dest/'events.jsonl';p.parent.mkdir(parents=True,exist_ok=True)
    text=''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in subset)
    if p.exists() and p.read_text()!=text:raise RuntimeError('Upstream immutable drift')
    if not p.exists():p.write_text(text)
    write(dest/'upstream_status.json',status)
    return status

def prepare():
    manifest=read(ROOT/'manifests/lite_pilot.json')
    recs,smoke,b2=frozen_subset(manifest['records'])
    if len(recs)!=50 or len({r['instance_id'] for r in recs})!=50:raise RuntimeError('Lite50 cohort drift')
    RUN.mkdir(parents=True,exist_ok=True)
    pin={'records':recs,'smoke_ids':smoke,'b2_ids':b2,'selection_rule':'plain SHA256(instance_id); first5 smoke, all repos represented then fill SHA order to20',
         'created_at':utc(),'pre_change_github_commit':BACKUP,'old_run':str(OLD),'gold_not_used_for_sampling':True}
    if not (RUN/'run_manifest.json').exists():write(RUN/'run_manifest.json',pin)
    else:
        prior=read(RUN/'run_manifest.json')
        if any(prior[k]!=pin[k] for k in ('records','smoke_ids','b2_ids','selection_rule','pre_change_github_commit')):raise RuntimeError('Cohort/preregistration drift')
    cfg=read(ROOT/'configs/resolved_config.json')
    config={k:cfg[k] for k in ('deepseek','qwen','pruner','price_snapshot','tokenizer')}
    config.update(run_id=RUN_ID,cohort='lite_pilot',budget_usd=3.,thinking='disabled',semantic_retry_limit=0,transport_retries=3,
       ablation={'context_o200k_cap':80000,'cap_boundary':'context = paths + signatures + optional full sources; system/issue excluded as historical source-context cap',
         'annotation_default_expression_chars':160,'max_output_tokens':4096,'temperature':0,'json_object':True,
         'pair_order':'SHA256(instance_id) final hex parity alternates which arm goes first'},
       b1={'status':'BLOCKED_FAIRNESS','reason':'old DSL accepts prose+single call; strict full-response DSL changes more than accept_strict_dsml; no relaxation or online run'},
       b2={'protocol':'strict_text_json','native_tools':False,'max_issues':20,'semantic_retries':0,'schema':'actual original tool signatures','each_method_own_start':True},
       pre_change_github_commit=BACKUP)
    write(RUN/'resolved_config.json',config)
    import yaml
    (RUN/'resolved_config.yaml').write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False))
    deps={}
    for name in ['openai','httpx','tiktoken','tokenizers','transformers','torch','peft','numpy','scipy','PyYAML']:
        try:deps[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:deps[name]=None
    write(RUN/'dependency_lock.json',deps)
    inventory={str(ROOT/'manifests/lite_pilot.json'):sha(ROOT/'manifests/lite_pilot.json')}
    statuses={m:{} for m in METHODS}
    for rec in recs:
        job=read(rec['job'])
        if set(job)&{'gold','patch','test_patch','FAIL_TO_PASS','PASS_TO_PASS','hints_text'}:raise RuntimeError('Unsafe job keys')
        if job['instance_id']!=rec['instance_id'] or job['base_commit']!=rec['base_commit']:raise RuntimeError('Job identity drift')
        inventory[rec['job']]=sha(rec['job']);inventory[job['code_index']]=sha(job['code_index']);inventory[job['structure']]=sha(job['structure'])
        for m in METHODS:statuses[m][rec['instance_id']]=snapshot_upstream(rec,m,inventory)
        # Hash old output files only as a preservation inventory, never feed them to models.
        for m in ['D-SIMPLE',*METHODS]:
            case=OLD/'lite_pilot'/m/rec['instance_id']
            for p in [case/'result.json',case/'context.json',case/'events.jsonl']:
                if p.exists():inventory[str(p)]=sha(p)
    write(RUN/'history_preservation_sha256.json',inventory)
    write(RUN/'upstream_inventory.json',statuses)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=COSIL,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=COSIL,text=True).splitlines()
    write(RUN/'local_git_state.json',{'native_cosil_head':head,'tracked_changes':dirty,'independent_publishing':True,'remote_backup':BACKUP})
    write(RUN/'budget.json',{'stage_cap_usd':3.,'cases':{},'attempts':{}}) if not (RUN/'budget.json').exists() else None
    print(json.dumps({'prepared':len(recs),'smoke':smoke,'b2':b2,'upstream_ready':{m:sum(v['status']=='ready' for v in d.values()) for m,d in statuses.items()}},ensure_ascii=False))
    return config

if __name__=='__main__':prepare()
