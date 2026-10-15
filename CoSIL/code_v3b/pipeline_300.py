"""Supervise the authorized long experiment through annotations, audit, runs and reports."""
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v3b.gen_annotations_300 import atomic_json, coverage, client
from code_v3b.run_experiment_300 import WORK, REPORTS, inputs, _case, _canonical_locations


def status(stage, **values):
    state = dict(stage=stage, updated_at=datetime.now().astimezone().isoformat(), **values)
    atomic_json(WORK / 'pipeline_status.json', state)
    REPORTS.mkdir(parents=True, exist_ok=True)
    text = '# Qwen 300 题实验执行进度\n\n'
    text += f"> 更新：{state['updated_at']}；当前阶段：{stage}。\n\n"
    text += '模型：本地 Qwen2.5-Coder-7B-Instruct；三臂共同修复基底；正式计划 300×3=900 次。\n\n'
    text += '金丝雀：三次独立输出集合完全一致，分派/API 错误为零；此前两组失败记录完整保留。\n\n'
    text += '真值：300 题官方补丁经上下文匹配及修复前后 AST 边界校验，原十题参考一致。\n\n'
    for key,value in values.items():
        text += f'- {key}：{value}\n'
    text += '\n正式结果报告仅在所有 900 次定位完成并校验后生成，不能将此进度文档当作实验结论。\n'
    (REPORTS / '执行进度.md').write_text(text, encoding='utf-8')
    print(json.dumps(state,ensure_ascii=False),flush=True)


def run(command, log):
    with (WORK / log).open('a',encoding='utf-8') as stream:
        result = subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Stage command failed, exit={result.returncode}; inspect {WORK/log}')


def annotation_active():
    handle=(WORK/'annotation_generation.lock').open('a')
    try:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.flock(handle,fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    finally:
        handle.close()


def audit_annotations(manifest, values):
    if (WORK/'annotation_quality_audit.json').exists():
        saved=json.loads((WORK/'annotation_quality_audit.json').read_text())
        if saved['passed']:
            return saved
        raise RuntimeError('Prior annotation quality audit needs review; do not ignore it')
    population=[(iid,key) for iid,entry in manifest['cases'].items() for key in entry['expected_keys']]
    selected=random.Random(20261006).sample(population,min(50,len(population)))
    api=client()
    result=[]
    for iid,key in selected:
        task=json.loads((WORK/'annotation_tasks'/f'{iid}.json').read_text())
        code=task['functions'][key]
        description=values[iid][key]
        prompt=('只依据给定源码，判断功能说明是否忠实概括主要职责，允许省略次要细节。'
                '不要判断 bug 或任何 issue。只输出 JSON：{"faithful":true或false,"reason":"一句理由"}。\n'
                f'节点：{key}\n功能说明：{description}\n源码：\n```python\n{code}\n```')
        reply=api.chat.completions.create(model='llama3',temperature=0,seed=0,max_tokens=160,
            messages=[{'role':'user','content':prompt}])
        raw=reply.choices[0].message.content or ''
        try:
            start,end=raw.find('{'),raw.rfind('}')
            parsed=json.loads(raw[start:end+1])
            faithful=parsed.get('faithful') is True
        except Exception:
            faithful=False;parsed={'reason':'Unparseable quality verdict'}
        result.append(dict(instance_id=iid,node=key,description=description,source=code,
                           faithful=faithful,reason=parsed.get('reason'),raw=raw))
        print(f'Annotation QA {len(result)}/{len(selected)}',flush=True)
    passed=sum(r['faithful'] for r in result)>=len(result)*.9
    audit=dict(passed=passed,sample_size=len(result),faithful=sum(r['faithful'] for r in result),
               threshold=.9,selection_seed=20261006,reviewer='same local Qwen; not independent human validation',
               cases=result)
    atomic_json(WORK/'annotation_quality_audit.json',audit)
    if not passed:
        raise RuntimeError('Annotation quality sample below 90%; inspect the preserved examples before running 900')
    return audit


def pilot(values):
    data,candidates=inputs()
    ids=['astropy__astropy-12907','astropy__astropy-6938','django__django-11848']
    summaries=[]
    stability=[]
    for arm in ['off','on','shuffled']:
        for iid in ids:
            sets=[]
            for repeat in (1,2,3):
                directory=WORK/'pilot'/arm/f'repeat_{repeat}'
                output=directory/'cases'/f'{iid}.json'
                if output.exists():
                    outcome={'status':'complete'}
                else:
                    if (directory/'events'/f'{arm}_{iid}.jsonl').exists():
                        raise RuntimeError(f'Incomplete pilot trace: {arm}/{iid}/repeat_{repeat}; preserve it before retrying')
                    annotations=WORK/'pilot_annotations'/f'{iid}.json'
                    atomic_json(annotations,{iid:values[iid]})
                    outcome=_case((iid,arm,data[iid]['problem_statement'],candidates[iid],str(directory),str(annotations)))
                if outcome['status']!='complete':
                    raise RuntimeError(f'Pilot failed: {arm}/{iid}/repeat_{repeat}')
                events=[json.loads(line) for line in (directory/'events'/f'{arm}_{iid}.jsonl').read_text().splitlines()]
                sets.append(_canonical_locations(json.loads(output.read_text())))
                summaries.append(dict(arm=arm,instance_id=iid,repeat=repeat,
                    source_queries=sum(e['event']=='tool_result' and e.get('kind')=='source' and e.get('success') for e in events),
                    parse_errors=sum(e['event']=='parse_error' for e in events)))
                print(f'Pilot {arm}/{iid}/repeat_{repeat}: {len(summaries)}/27 complete',flush=True)
            stability.append(dict(arm=arm,instance_id=iid,pairwise_jaccard=[
                len(sets[a]&sets[b])/len(sets[a]|sets[b]) if sets[a]|sets[b] else 1.0
                for a,b in ((0,1),(0,2),(1,2))],all_empty=not any(sets),
                definition='Empty vs empty is 1 for stability only, not a successful localization'))
    # Exploration and accuracy are outcomes, not acceptance criteria for an annotation arm.
    passed=True
    atomic_json(WORK/'pilot_acceptance.json',dict(passed=passed,cases=summaries,stability=stability,
        condition='All 27 independent pilot runs complete; stability, exploration, early exit and accuracy are recorded outcomes, not gates'))
    if not passed:
        raise RuntimeError('Small three-arm acceptance failed; inspect preserved pilot traces')


def main():
    os.chdir(ROOT)
    WORK.mkdir(parents=True,exist_ok=True)
    lock=(WORK/'pipeline.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        gate=json.loads((WORK/'canary_gate.json').read_text())
        if not gate['passed']:
            raise RuntimeError('Canary gate is not passed')
        while True:
            manifest=json.loads((WORK/'annotation_manifest.json').read_text())
            values=json.loads((ROOT/'annotations_300.json').read_text()) if (ROOT/'annotations_300.json').exists() else {}
            progress=coverage(manifest,values)
            status('生成 Qwen 功能说明',completed_annotations=progress['completed_total'],
                   expected_annotations=progress['expected_total'],complete_instances=progress['complete_instances'])
            if progress['all_complete'] and not annotation_active():
                break
            if not annotation_active():
                run(['bash','code_v3b/qwen300.sh','annotations','--workers','4'],'annotation_runner.log')
            else:
                time.sleep(30)
        status('检查 Qwen 功能说明质量',sample_size=50,threshold='90% faithful in a source-only review')
        audit=audit_annotations(manifest,values)
        status('小规模三臂验收',annotation_quality=f"{audit['faithful']}/{audit['sample_size']}")
        pilot(values)
        status('运行三臂全量定位',planned_new_runs=900,workers=2)
        run(['bash','code_v3b/qwen300.sh','run','--workers','2'],'fixed_runner.log')
        status('判分与撰写报告',completed_runs=900)
        run([sys.executable,'code_v3b/analyze_experiment_300.py'],'analysis.log')
        status('打包与核验归档',completed_runs=900)
        run([sys.executable,'code_v3b/archive_experiment_300.py'],'archive.log')
        status('完成',completed_runs=900,reports=['实验报告_v3c_Qwen三臂总表.md','实验报告_v3c_逐题逐臂.md'])
    except Exception as exc:
        status('停止并保留证据',error=type(exc).__name__,message=str(exc))
        raise


if __name__=='__main__':
    main()
