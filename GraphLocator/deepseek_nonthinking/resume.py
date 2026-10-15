"""Resume an unchanged frozen run after explicitly authorized account funding."""
import argparse
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import shutil

from deepseek_nonthinking import runner,transport

ROOT,WORK=runner.ROOT,runner.WORK
FROZEN='3a033e3a692aa67b'


def funding_update(previous,current_balance):
    state=deepcopy(previous)
    if state['reservations']:
        raise RuntimeError('Previous paid requests still have unresolved reservations')
    current=Decimal(str(current_balance));last=Decimal(str(state['last_balance_cny']))
    added=current-last
    if added<=Decimal('0.01'):
        raise RuntimeError('No increased account balance detected; preserve the existing budget')
    state.setdefault('original_initial_balance_cny',state['initial_balance_cny'])
    state['initial_balance_cny']=float(Decimal(str(state['initial_balance_cny']))+added)
    state['limit_cny']=float(Decimal(str(state['limit_cny']))+added)
    state['last_balance_cny']=float(current)
    state['observed_spend_cny']=float(max(Decimal(0),Decimal(str(state['initial_balance_cny']))-current))
    state.setdefault('funding_history',[]).append(dict(
        authorized_at=datetime.now().astimezone().isoformat(),
        authorization='User explicitly said account recharged and requested continuation',
        previous_observed_balance_cny=float(last),current_observed_balance_cny=float(current),
        net_balance_increase_cny=float(added),new_cumulative_budget_cny=state['limit_cny'],
        accounting='Net observed balance increase, not a claim of exact recharge amount; late billing may be included. Original receipts and usage counters remain unchanged.'))
    state.pop('stop_reason',None)
    return state


def prepare():
    runner.initialize()
    frozen=runner.version()
    if frozen['hash']!=FROZEN:raise RuntimeError('Inference changed; refusing to mix predictions')
    with (WORK/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        stamp=datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z')
        history=WORK/'resume_history'/stamp;history.mkdir(parents=True,exist_ok=False)
        folder=WORK/'full/B2'
        retained={}
        for directory in ('cases','failures'):
            for p in (folder/directory).glob('*.json'):
                d=json.loads(p.read_text())
                if d['version_hash']!=FROZEN:raise RuntimeError('Old result version mismatch')
                retained[str(p)]=runner.sha(p)
        if len(retained)!=120:raise RuntimeError('Expected the 120 completed results before this continuation')
        for name in ('run_status.json','delivery_status.json','delivery_checks.json'):
            p=WORK/name
            if p.exists():shutil.copy2(p,history/name)
        for name in ('manifest.json','completion.json'):
            p=WORK/'full'/name
            if p.exists():shutil.copy2(p,history/name)
        for p in folder.glob('*.json*'):
            (history/'phase_artifacts').mkdir(exist_ok=True)
            shutil.copy2(p,history/'phase_artifacts'/p.name)
        for p in (ROOT/'docs/deepseek-300').glob('*阶段*.md'):
            (history/'reports').mkdir(exist_ok=True)
            shutil.copy2(p,history/'reports'/p.name)
        matrix=ROOT.parent/'CoSIL'
        shutil.copy2(matrix/'docs/qwen-300/跨实验逐题定位对照表.xlsx',history/'matrix_before_resume.xlsx')
        shutil.copy2(matrix/'results/comparison/逐题定位对照数据.json',history/'matrix_before_resume.json')
        mappings=[];paused=[]
        for pause in sorted((folder/'budget_pauses').glob('*.json')):
            iid=pause.stem;paused.append(iid)
            if (folder/'cases'/pause.name).exists() or (folder/'failures'/pause.name).exists():
                raise RuntimeError('Pause also has a final result')
            for source in (pause,folder/'events'/f'{iid}.jsonl',folder/'logs'/f'{iid}.log',folder/'events/prompts'/iid):
                if not source.exists():continue
                target=history/'interrupted'/source.relative_to(folder)
                target.parent.mkdir(parents=True,exist_ok=True)
                files=[source] if source.is_file() else sorted(source.rglob('*'))
                for p in files:
                    if p.is_file():
                        dest=target if source.is_file() else target/p.relative_to(source)
                        mappings.append(dict(original_path=str(p),archived_path=str(dest),sha256=runner.sha(p)))
                source.rename(target)
        for entry in mappings:
            if runner.sha(entry['archived_path'])!=entry['sha256']:raise RuntimeError('Interrupted archive hash differs')
        with transport.locked_budget() as old:
            runner.atomic(history/'budget_before.json',old)
            current=transport.balance()
            new=funding_update(old,current)
            old.clear();old.update(new)
            runner.atomic(history/'budget_after.json',old)
        plan=dict(version_hash=FROZEN,prepared_at=datetime.now().astimezone().isoformat(),
            history_folder=str(history),retained_results_sha256=retained,rerun_interrupted=paused,
            interrupted_path_mapping=mappings,remaining=180,workers=4,
            current_balance_cny=current,cumulative_budget_cny=new['limit_cny'],
            orchestrator_sha256=runner.sha(Path(__file__)),
            note='Raw old prompt paths are preserved in archived events; use this mapping to resolve them. Interrupted issues rerun from the beginning, successful predictions stay byte-identical.')
        runner.atomic(history/'resume_manifest.json',plan)
        shutil.copy2(Path(__file__),history/'resume.py')
        runner.atomic(WORK/'resume_plan.json',plan)
        manifest=json.loads((WORK/'full/manifest.json').read_text())
        manifest.setdefault('resume_history',[]).append({k:v for k,v in plan.items() if k not in ('retained_results_sha256','interrupted_path_mapping')})
        runner.atomic(WORK/'full/manifest.json',manifest)
        for name in ('delivery_status.json',):
            p=WORK/name
            if p.exists():p.unlink()
        runner.atomic(WORK/'run_status.json',dict(phase='resume_prepared',version_hash=FROZEN,
            completed=120,failed=0,remaining=180,total=300,budget_limit_cny=new['limit_cny'],
            current_balance_cny=current,history_folder=str(history)))
        print(json.dumps({k:plan[k] for k in ('version_hash','remaining','current_balance_cny','cumulative_budget_cny','rerun_interrupted','history_folder')},ensure_ascii=False))


def run():
    inputs=runner.initialize();frozen=runner.version()
    plan=json.loads((WORK/'resume_plan.json').read_text())
    if frozen['hash']!=FROZEN or plan['version_hash']!=FROZEN:
        raise RuntimeError('Frozen inference version differs')
    with (WORK/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for p,digest in plan['retained_results_sha256'].items():
            if runner.sha(p)!=digest:raise RuntimeError('Retained prediction changed')
        original_status=runner.status
        def resumed_status(phase,folder,ids,frozen):
            value=original_status(phase,folder,ids,frozen)
            doc=ROOT/'docs/deepseek-300/执行进度_非思考.md'
            doc.write_text('# GraphLocator DeepSeek 非思考续跑进度\n\n'
                f'保留原120题，继续剩余180题；当前累计授权额度 {value["budget"]["limit_cny"]:g} 元。\n\n'
                '```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```\n')
            return value
        runner.status=resumed_status
        folder,result=runner.run_phase('full',inputs,frozen,plan['workers'])
        for p,digest in plan['retained_results_sha256'].items():
            if runner.sha(p)!=digest:raise RuntimeError('Continuation altered a retained prediction')
        from deepseek_nonthinking.reports import generate
        generate(folder,inputs['instances'],partial=result['processed']!=300)
        runner.atomic(WORK/'delivery_status.json',dict(state='complete' if result['processed']==300 else 'budget_limited',
            version_hash=FROZEN,processed=result['processed'],total=300,
            resumed=True,history_folder=plan['history_folder'],finished_at=datetime.now().astimezone().isoformat()))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');a=p.parse_args()
    prepare() if a.prepare else run()
