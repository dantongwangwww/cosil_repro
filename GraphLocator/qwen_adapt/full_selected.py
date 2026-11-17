"""Run the development-selected condition with unchanged frozen inference code."""
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import shutil

from qwen_adapt.runner import ROOT,WORK,prepare,version,run_case,aggregate,atomic,sha


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--gpus',default='0,1,2,3')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    gpu_ids=[int(g) for g in args.gpus.split(',')]
    assert gpu_ids and len(gpu_ids)==len(set(gpu_ids))
    rows,inputs=prepare();frozen=version()
    gate=json.loads((WORK/'full_gate.json').read_text())
    assert gate['passed'] and gate['version_hash']==frozen['hash']
    variant=gate['selected_variant'];assert variant in ('B1','B2','B3')
    ids=inputs['validation']+inputs['development'];root=WORK/'full';folder=root/variant
    lock=(WORK/'run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest=dict(**frozen,phase='full',instances=ids,variants=[variant],model='Qwen2.5-Coder-7B-Instruct',
        temperature=0,seed=0,context_limit=65536,gpus=args.gpus,workers_per_gpu=2,
        max_search_turn=5,max_causal_updates=21,search_pages=4,
        causal_budget='legacy unbounded neighbor input; transport rejects context over 65536' if variant!='B3' else '48k source batching',
        started_at=datetime.now().astimezone().isoformat(),orchestrator_file='qwen_adapt/full_selected.py',
        orchestrator_sha256=sha(Path(__file__)),development_review='development/'+frozen['hash']+'/review.json')
    mp=root/'manifest.json'
    if args.resume:
        old=json.loads(mp.read_text())
        assert old['hash']==frozen['hash'] and old['instances']==ids and old['variants']==[variant]
        old.setdefault('resume_history',[]).append(dict(resumed_at=manifest['started_at'],gpus=args.gpus,
            workers_per_gpu=2,orchestrator_sha256=manifest['orchestrator_sha256'],reason='用户要求释放GPU3，改变计算资源，不改变模型、提示词或推理参数。'))
        atomic(mp,old)
        target=root/'resume_code'/manifest['orchestrator_sha256']/'full_selected.py';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(Path(__file__),target)
    else:
        assert not mp.exists(),'Never overwrite an existing frozen full run'
        atomic(mp,manifest)
        for source in frozen['sources']:
            target=root/'code_snapshot'/source;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/source,target)
        shutil.copy2(Path(__file__),root/'code_snapshot/qwen_adapt/full_selected.py')
    existing=set()
    for iid in ids:
        paths=[folder/d/f'{iid}.json' for d in ('cases','failures')]
        saved=next((p for p in paths if p.exists()),None)
        if saved:
            assert json.loads(saved.read_text())['version_hash']==frozen['hash']
            existing.add(iid)
    mapping={r['instance_id']:r for r in rows};routes=[(g,'http://127.0.0.1:'+str(7333+g)+'/v1') for g in gpu_ids]
    pools=[ProcessPoolExecutor(max_workers=2) for _ in routes];iterator=iter([i for i in ids if i not in existing]);pending={};completed=len(existing)
    def submit(index):
        iid=next(iterator,None)
        if iid is None:return
        gpu,endpoint=routes[index]
        pending[pools[index].submit(run_case,(mapping[iid],str(folder),gpu,endpoint,variant,frozen))]=index
    for _ in range(2):
        for index in range(len(routes)):submit(index)
    try:
        while pending:
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                index=pending.pop(future);result=future.result();completed+=1
                print(json.dumps(result,ensure_ascii=False),flush=True);submit(index)
            status=dict(phase='full',variant=variant,version_hash=frozen['hash'],completed_attempts=completed,
                total_attempts=300,gpus=args.gpus,updated_at=datetime.now().astimezone().isoformat(),folder=str(root))
            atomic(WORK/'run_status.json',status)
            (ROOT/'docs/qwen-300/执行进度_适配v2.md').write_text('# GraphLocator Qwen适配v2执行进度\n\n'+json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    finally:
        for pool in pools:pool.shutdown(wait=True)
    aggregate(folder,ids)
    atomic(root/'completion.json',dict(completed=completed,total=300,variant=variant,version_hash=frozen['hash'],finished_at=datetime.now().astimezone().isoformat()))


if __name__=='__main__':main()
