"""Persistent controller: freeze, isolation probe, canary, then the same 265 cases."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from . import common as C
from . import bootstrap as B


def manifest():
    value=C.read(C.INPUTS/'prepare_manifest.json')
    if not value:
        raise RuntimeError('Complete base-only preparation is required')
    records=value['records']
    if len(records)!=265 or len({r['instance_id'] for r in records})!=265:
        raise RuntimeError('Exactly the fixed 265 unique issues are required')
    for r in records:
        if not Path(r['job']).is_file():
            raise RuntimeError('Missing prepared job: '+r['instance_id'])
    return value


def ordered(records):
    return sorted(records,key=lambda r:C.digest('20261023|CoSIL-Qwen3-8B|'+r['instance_id']))


def freeze():
    source=manifest()
    model=C.read(C.WORK/'model_files.json')
    if not model:
        raise RuntimeError('Pinned model download verification is required')
    code={}
    for root in (C.ROOT/'code_rebench_qwen',C.ROOT/'code_v3b',C.ROOT/'afl',C.ROOT/'get_repo_structure'):
        for p in sorted(root.rglob('*.py')):
            if any(v.startswith('.') for v in p.relative_to(root).parts) or '__pycache__' in p.parts:
                continue
            code[str(p)]=C.sha(p)
    inputs={}
    for r in source['records']:
        job=C.read(r['job'])
        for p in (Path(r['job']),Path(job['structure']),Path(job['code_index']),Path(r['job']).parent/'source_hashes.json'):
            inputs[str(p)]=C.sha(p)
    value=dict(run_id=C.RUN_ID,created_utc=C.utc(),model_id=C.MODEL_ID,
        model_revision=model['revision'],model_files_sha256=C.sha(C.WORK/'model_files.json'),
        preparation_manifest_sha256=C.sha(C.INPUTS/'prepare_manifest.json'),
        prior_manifest_sha256=C.sha(C.SOURCE_MANIFEST),checkpoint=C.CHECKPOINT,
        conditions=dict(arm='off',thinking=False,temperature=0,seed=C.SEED,
            context_limit=C.CONTEXT_LIMIT,max_tokens=C.MAX_TOKENS,max_retry=C.MAX_RETRY,
            whole_pipeline='file search and reflection -> top5 -> function search and same-model relevance pruning',
            test_sealed=True,train=False,semantic_retries='original CoSIL format correction only'),
        code_sha256=code,input_sha256=inputs,records=source['records'],
        canary_ids=[r['instance_id'] for r in ordered(source['records'])[:5]])
    prior=C.read(C.RUN/'frozen.json')
    if prior:
        comparable=dict(value,created_utc=prior['created_utc'])
        if comparable!=prior:
            raise RuntimeError('Frozen inputs/code/model changed; preserve the old run')
        return prior
    C.write(C.RUN/'frozen.json',value,replace=False)
    return value


def verify():
    value=C.read(C.RUN/'frozen.json')
    if not value:
        raise RuntimeError('Freeze before any inference')
    for group in ('code_sha256','input_sha256'):
        for path,expected in value[group].items():
            if C.sha(path)!=expected:
                raise RuntimeError('Frozen artifact drift: '+path)
    if C.sha(C.WORK/'model_files.json')!=value['model_files_sha256']:
        raise RuntimeError('Model receipt drift')
    if C.sha(C.INPUTS/'prepare_manifest.json')!=value['preparation_manifest_sha256']:
        raise RuntimeError('Preparation manifest drift')
    if C.sha(C.SOURCE_MANIFEST)!=value['prior_manifest_sha256']:
        raise RuntimeError('Prior frozen roster drift')
    return value


def token_cache():
    target=C.WORK/'token_cache';target.mkdir(parents=True,exist_ok=True)
    for name in ('9b5ad71b2ce5302211f9c61530b329a4922fc6a4','fb374d419588a4632f3f557e76b4b70aebbca790'):
        source=Path('/tmp/data-gym-cache')/name
        if not source.is_file():
            raise RuntimeError('Existing public tiktoken cache missing: '+name)
        destination=target/name
        if not destination.exists():
            shutil.copyfile(source,destination)
        if C.sha(source)!=C.sha(destination):
            raise RuntimeError('Public token cache copy mismatch')


def isolated_probe():
    records=ordered(manifest()['records']);token_cache()
    out=C.RUN/'isolation_probe';out.mkdir(parents=True,exist_ok=True)
    completed=subprocess.run(B.argv(records[0]['job'],out,probe=True),env=B.environment(out),
        text=True,capture_output=True,timeout=180)
    C.write(out/'process.json',dict(returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr))
    result=C.read(out/'probe.json',{})
    if completed.returncode or not result.get('passed'):
        raise RuntimeError('Isolated worker probe failed; inspect isolation_probe/process.json')
    return result


def one(record):
    iid=record['instance_id'];out=C.RUN/'cases'/iid;result_path=out/'result.json'
    if result_path.exists():
        return C.read(result_path)
    if out.exists() and ((out/'started.json').exists() or (out/'calls').exists()):
        raise RuntimeError('Interrupted case requires explicit audit; no silent resampling: '+iid)
    out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    C.write(out/'started.json',dict(utc=C.utc(),instance_id=iid,job_sha256=C.sha(record['job'])),replace=False)
    process_code=None
    spawn_error=None
    try:
        with (out/'controller_process.log').open('a') as log:
            process=subprocess.run(B.argv(record['job'],out),env=B.environment(out),stdout=log,stderr=subprocess.STDOUT)
        process_code=process.returncode
    except OSError as error:
        spawn_error=dict(type=type(error).__name__,message=str(error))
    if not result_path.exists():
        C.write(result_path,dict(instance_id=iid,repo=record['repo'],base_commit=record['base_commit'],
            status='failed',error_type='IsolatedWorkerSpawnFailure' if spawn_error else 'IsolatedWorkerProcessFailure',
            spawn_error=spawn_error,returncode=process_code,
            predicted_files=[],predicted_functions=[],elapsed_seconds=time.perf_counter()-started,
            run_id=C.RUN_ID),replace=False)
    result=C.read(result_path)
    C.write(out/'controller_receipt.json',dict(ended_utc=C.utc(),returncode=process_code,spawn_error=spawn_error,
        elapsed_seconds=time.perf_counter()-started,status=result['status']),replace=False)
    return result


def progress(records):
    counts={};elapsed=[]
    for r in records:
        result=C.read(C.RUN/'cases'/r['instance_id']/'result.json')
        if result:
            status=result['status'];counts[status]=counts.get(status,0)+1
            if result.get('elapsed_seconds') is not None:elapsed.append(result['elapsed_seconds'])
    value=dict(utc=C.utc(),allocated=265,terminal=sum(counts.values()),statuses=counts,
               sum_case_processing_seconds=sum(elapsed))
    C.write(C.RUN/'progress.json',value)
    return value


def execute(phase,workers):
    frozen=verify()
    if not C.read(C.RUN/'isolation_probe/probe.json',{}).get('passed'):
        raise RuntimeError('Successful filesystem isolation probe required')
    records=ordered(frozen['records'])
    selected=records[:5] if phase=='canary' else records
    if phase=='full':
        gate=C.read(C.RUN/'canary_gate.json',{})
        if not gate.get('passed') or gate.get('frozen_sha256')!=C.sha(C.RUN/'frozen.json'):
            raise RuntimeError('Passed engineering canary for this exact freeze required')
    if not 1<=workers<=4:
        raise ValueError('Use one through four bounded CPU request workers')
    C.RUN.mkdir(parents=True,exist_ok=True)
    with (C.RUN/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        began=time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(one,r) for r in selected]
            for future in as_completed(futures):
                result=future.result();state=progress(records)
                print(json.dumps(dict(instance_id=result['instance_id'],status=result['status'],
                                      terminal=state['terminal'],allocated=265)),flush=True)
        verify()
        results=[C.read(C.RUN/'cases'/r['instance_id']/'result.json') for r in selected]
        if phase=='canary':
            # No accuracy threshold: gold and old predictions have not been read.
            bad=[r for r in results if r['status']!='complete']
            gate=dict(passed=not bad,utc=C.utc(),issues=[r['instance_id'] for r in selected],
                statuses={r['instance_id']:r['status'] for r in results},
                no_accuracy_threshold=True,wall_seconds=time.perf_counter()-began,
                frozen_sha256=C.sha(C.RUN/'frozen.json'))
            C.write(C.RUN/'canary_gate.json',gate,replace=False)
            if bad:
                raise RuntimeError('Canary did not complete; preserve evidence before full run')
            return gate
        value=dict(passed=True,utc=C.utc(),terminal=265,statuses=progress(records)['statuses'],
                   wall_seconds=time.perf_counter()-began,old_results_reused=False)
        C.write(C.RUN/'complete.json',value,replace=False)
        return value


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=('freeze','probe','canary','full','progress'),required=True)
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if args.phase=='freeze':value=freeze()
    elif args.phase=='probe':value=isolated_probe()
    elif args.phase=='progress':value=progress(manifest()['records'])
    else:value=execute(args.phase,args.workers)
    print(json.dumps({k:v for k,v in value.items() if k not in ('records','code_sha256','input_sha256')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
