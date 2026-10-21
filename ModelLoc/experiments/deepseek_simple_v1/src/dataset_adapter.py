"""CPU preparation owns labels; workers receive only clean issue/source jobs."""
import collections,io,json,math,os,subprocess,tarfile
from pathlib import Path,PurePosixPath
from datasets import load_from_disk
import httpx
from .common import *
from .code_index import decode,file_record,structure
from .gold_mapping import map_gold

def protected_ids():
    paths=list((COSIL/'results/v5_pruner').glob('data*/split_manifest.json'))
    paths+=list((COSIL/'results/v6_pruner').glob('*/T2*/**/split_manifest.json'))
    paths+=list((COSIL/'results/v6_pruner').glob('*/T3*/data/split_manifest.json'))
    all_ids=set();sources=[]
    for p in sorted(set(paths)):
        d=read(p);ids=d.get('splits',{}).get('test',[])
        all_ids.update(ids);sources.append({'path':str(p),'sha256':sha(p),'test_issue_count':len(ids)})
    if not sources:raise RuntimeError('No holdout ID manifests')
    return all_ids,sources

def sample(pool,n,namespace):
    grouped=collections.defaultdict(list)
    for row in pool:grouped[row['repo']].append(row)
    quota={k:(1 if n>=len(grouped) else 0) for k in grouped}
    while sum(quota.values())<n:
        k=max((k for k in grouped if quota[k]<len(grouped[k])),
              key=lambda k:(n*len(grouped[k])/len(pool)-quota[k],stable(namespace,k)))
        quota[k]+=1
    out=[]
    for k,v in quota.items():out.extend(sorted(grouped[k],key=lambda r:stable(namespace,r['instance_id']))[:v])
    return sorted(out,key=lambda r:stable(namespace,r['instance_id'])),quota

def safe_snapshot(row,target):
    mirror=COSIL/'mirror_cache'/(row['repo'].rsplit('/',1)[-1]+'.git')
    commit=row['base_commit']
    paths=subprocess.check_output(['git','--git-dir',str(mirror),'ls-tree','-rz','--name-only',commit]).decode().strip('\0').split('\0')
    excluded={'.git','node_modules','vendor','dist','build','target','.next'}
    paths=sorted(p for p in paths if not set(p.split('/'))&excluded and not PurePosixPath(p).is_absolute() and '..' not in p.split('/'))
    target.mkdir(parents=True,exist_ok=True);kept=[]
    proc=subprocess.Popen(['git','--git-dir',str(mirror),'archive',commit],stdout=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
        for member in archive:
            if not member.isfile() or member.name not in paths:continue
            kept.append(member.name)
            if not member.name.endswith('.py'):continue
            p=target/member.name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(archive.extractfile(member).read());p.chmod(0o444)
    if proc.wait():raise RuntimeError('git archive failed')
    return sorted(kept)

def prepare():
    manifest=ROOT/'manifests/lite_pilot.json'
    if manifest.exists():return read(manifest)
    from code_v6.common import test_stats
    seals=test_stats();heldout,hold_sources=protected_ids()
    dataset=list(load_from_disk(str(COSIL/'swebench_local/SWE-bench_Lite_test')))
    pool=[r for r in dataset if r['instance_id'] not in heldout]
    smoke,sq=sample(pool,5,'smoke');smoke_ids={r['instance_id'] for r in smoke}
    pilot,pq=sample([r for r in pool if r['instance_id'] not in smoke_ids],50,'lite-pilot')
    write(ROOT/'manifests/excluded_ids.json',{'ids':sorted(heldout),'sources':hold_sources,
        'Lite_overlap_count':len(set(r['instance_id'] for r in dataset)&heldout),
        'test_content_read_or_hashed':False})
    revision=None;error=None
    try:
        r=httpx.get('https://huggingface.co/api/datasets/princeton-nlp/SWE-bench_Lite',trust_env=False,timeout=40)
        r.raise_for_status();revision=r.json()['sha']
    except Exception as e:error=type(e).__name__
    # The exact locally used Arrow files remain authoritative even if current
    # upstream differs. Pin local bytes independently; never invent a revision.
    local=COSIL/'swebench_local/SWE-bench_Lite_test'
    pin={'official_repo':'princeton-nlp/SWE-bench_Lite','split':'test','current_upstream_revision':revision,
         'upstream_revision_error':error,'local_exact_files':{str(p.relative_to(local)):sha(p) for p in local.iterdir() if p.is_file()},
         'used_revision':'local-sha256:'+digest(json.dumps({p.name:sha(p) for p in local.iterdir() if p.is_file()},sort_keys=True)),
         'current_upstream_content_equality':'NOT_CLAIMED: local dataset has harness enrichment columns'}
    write(ROOT/'manifests/dataset_pin.json',pin)
    all_records={}
    for cohort,rows_,quota in [('smoke',smoke,sq),('lite_pilot',pilot,pq)]:
        records=[]
        for row in rows_:
            iid=row['instance_id'];folder=ROOT/'snapshots'/iid
            paths=safe_snapshot(row,folder)
            sources={};index={}
            for p in paths:
                if not p.endswith('.py'):continue
                try:source=decode((folder/p).read_bytes())
                except (SyntaxError,UnicodeError):continue
                sources[p]=source;index[p]=file_record(p,source)
            index_path=ROOT/'jobs'/iid/'code_index.json';write(index_path,index)
            structure_path=ROOT/'jobs'/iid/'repo_structures'/(iid+'.json')
            st=structure(folder,paths)
            write(structure_path,{'instance_id':iid,'repo':row['repo'],'base_commit':row['base_commit'],'structure':st})
            gold=map_gold(row['patch'],sources)
            write(ROOT/'evaluator_private'/iid/'gold.json',gold)
            write(ROOT/'evaluator_private'/iid/'benchmark_row.json',dict(row))
            public={k:row[k] for k in ['instance_id','repo','base_commit','problem_statement']}
            public.update(cohort=cohort,snapshot=str(folder),paths=paths,code_index=str(index_path),structure=str(structure_path))
            write(ROOT/'jobs'/iid/'job.json',public)
            records.append({'instance_id':iid,'repo':row['repo'],'base_commit':row['base_commit'],
                'sampling_hash':stable('smoke' if cohort=='smoke' else 'lite-pilot',iid),'job':str(ROOT/'jobs'/iid/'job.json')})
            print(json.dumps({'prepared':iid,'cohort':cohort,'paths':len(paths)},ensure_ascii=False),flush=True)
        obj={'cohort':cohort,'n':len(records),'records':records,'quota_by_repo':quota,
             'selection_uses_outcomes':False,'protected_test_ids_excluded':True,'dataset_pin':pin['used_revision']}
        write(ROOT/'manifests'/f'{cohort}.json',obj);all_records[cohort]=obj
    if test_stats()!=seals:raise RuntimeError('Test seal stat changed')
    write(RUN/'test_stat_before.json',seals)
    write(RUN/'data_preparation.json',{'created_at':utc(),'protected_test_contents_read':False,'counts':{'smoke':5,'lite_pilot':50},
        'smoke_pilot_disjoint':True,'sampling_uses_labels':False,'dataset_pin':pin})
    return all_records['lite_pilot']
