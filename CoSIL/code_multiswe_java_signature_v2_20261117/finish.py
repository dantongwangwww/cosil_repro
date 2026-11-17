"""Uniform offline identity-format correction after the unchanged full run."""
from pathlib import Path
import argparse
import fcntl
import os
import shutil
import subprocess
import time
from code_multiswe_java_20261117.common import ROOT,read,write,sha
from .view import build_view


def comparison(original,derived):
    if any(original[k]!=derived[k] for k in ('allocated','selected','file_denominator','function_denominator')):
        raise ValueError('Formatting must not change allocation or evaluability')
    lines=['# 同一批推理：原解析与签名格式规范化v2','',
        '下列两个视图来自同一批真实模型输出，不是两次模型实验；新规则没有读取Gold作身份修复。所有指标变化均展示，不以成绩选择视图。','',
        '| 系统 | 范围 | 指标 | 原解析% | 规范化v2% | 变化pp |','|---|---|---|---:|---:|---:|']
    for arm in ('cosil','sfpruner','locagent'):
        for level in ('file','function'):
            for key in ('hit1','hit3','hit5','precision5','recall5','f1_5','allcoverage5','mrr10'):
                a=original['metrics'][arm][level][key]['value'];b=derived['metrics'][arm][level][key]['value']
                values=('NA','NA','NA') if a is None or b is None else (f'{100*a:.2f}',f'{100*b:.2f}',f'{100*(b-a):+.2f}')
                lines.append(f"| {arm} | {level} | {key} | {' | '.join(values)} |")
    return '\n'.join(lines)+'\n'


def same_inference_and_gold(original,derived):
    old={r['instance_id']:r for r in original};new={r['instance_id']:r for r in derived}
    if len(old)!=128 or set(old)!=set(new):raise ValueError('Same full128 IDs required')
    for iid,a in old.items():
        b=new[iid]
        for key in ('repo','base_commit','file_evaluable','function_evaluable','gold_files','gold_functions'):
            if a[key]!=b[key]:raise ValueError('Formatting changed task/Gold scope: '+iid)
        for arm in ('cosil','sfpruner','locagent'):
            x,y=a['arms'][arm],b['arms'][arm]
            if x['status']!=y['status'] or x['result_status']!=y['result_status'] or x['resource']!=y['resource']:
                raise ValueError('Formatting must preserve original status, usage and timing: '+iid+'/'+arm)
            if x['ranking']['file']!=y['ranking']['file']:
                raise ValueError('Formatting cannot change file predictions: '+iid+'/'+arm)


def code_fence(root):
    f=read(Path(root)/'audits/signature_view_execution_freeze.json')
    if not f.get('commit') or not f.get('files_sha256'):raise ValueError('Published formatting-view source required')
    for p,expected in f['files_sha256'].items():
        if sha(p)!=expected:raise ValueError('Formatting-view source drift: '+p)


def run(root):
    root=Path(root).resolve();work=root/'signature_view_supervisor';work.mkdir(exist_ok=True)
    with (work/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);code_fence(root)
        while not (root/'analysis_supervisor/completion.json').is_file():
            if (root/'analysis_supervisor/error.json').exists():raise RuntimeError('Original CPU analysis requires review; preserve its error')
            if (root/'services/status.json').exists() and read(root/'services/status.json')['phase']=='STOPPED':
                raise RuntimeError('Inference stopped; never disguise pending tasks as evaluated')
            write(work/'status.json',{'phase':'WAITING_ORIGINAL_FULL_ANALYSIS','time':time.time(),'pid':os.getpid()},immutable=False)
            time.sleep(10)
        code_fence(root)
        original=read(root/'analysis_supervisor/completion.json')
        if original['status']!='ANALYSIS_READY_FOR_INDEPENDENT_REVIEW':raise ValueError('Original analysis closure missing')
        for p,expected in original['outputs_sha256'].items():
            if sha(p)!=expected:raise ValueError('Original delivery changed before derived view')
        view=build_view(root,root/'evaluation_views/signature_format_v2')
        # Only after all derived predictions are closed do we read private Gold
        # bytes for integrity, then let the independent evaluator use labels.
        for path,expected in read(root/'audits/evaluator_qualification_frozen.json')['gold_files_sha256'].items():
            if sha(path)!=expected:raise ValueError('Frozen Gold changed between evaluation views')
        python=str((ROOT.parent/'LocAgent/.venv/bin/python').absolute())
        evaluation=root/'reports/signature_v2_evaluation';failures=root/'reports/signature_v2_failures';resources=root/'reports/signature_v2_resources'
        tasks=[('evaluation','code_multiswe_java_20261117.evaluate',['--root',str(view),'--out',str(evaluation)]),
            ('failures','code_multiswe_java_audit_20261117.failures',['--root',str(view),'--evaluation-dir',str(evaluation),'--out',str(failures)]),
            ('resources','code_multiswe_java_audit_20261117.resources',['--root',str(view),'--evaluation-dir',str(evaluation),'--out',str(resources)])]
        env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TZ')}
        env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        for name,module,args in tasks:
            write(work/'status.json',{'phase':name,'time':time.time()},immutable=False)
            with (work/(name+'.log')).open('xb') as stream:
                p=subprocess.run([python,'-B','-m',module,*args],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                    stdout=stream,stderr=subprocess.STDOUT,timeout=3600)
            if p.returncode:raise RuntimeError('Offline formatting-view '+name+' failed; preserve all artifacts')
        same_inference_and_gold(read(root/'reports/final128/per_issue.json'),read(evaluation/'per_issue.json'))
        comparison_text=comparison(read(root/'reports/final128/summary.json'),read(evaluation/'summary.json'))
        (evaluation/'原解析与规范化v2_对照.md').write_text(comparison_text)
        docs=ROOT/'docs/multiswe-java128'
        report=evaluation/'总览.md';primary=docs/'实验报告_Java128_三模型总览_规范化v2.md'
        if primary.exists():raise FileExistsError(primary)
        explanation=('本报告采用统一的Java签名格式规范化v2，是同一批模型调用的离线评价版本。参数列表的格式空格不改变方法身份；仅对公开base库存可唯一确定的等价标识规范化，不补参数或更换类型，不读取Gold修正预测。CoSIL/SFPruner保留原槽；LocAgent重放同样两样本MRR。模型、Prompt、工具轨迹、状态、费用和时延都没有重跑。\n\n'
            '原始解析评价保存在`reports/final128`及《实验报告_Java128_三模型总览.md》，不删除、不以成绩选择版本。完整规则及格式边界见《签名格式规范化v2_协议.md》《评价口径与规范化说明.md》。\n\n')
        primary.write_text(explanation+report.read_text())
        copies={evaluation/'per_issue.csv':docs/'逐题_Java128_三模型定位_规范化v2.csv',
            failures/'定位错例报告.md':docs/'定位失败分类与逐题分析_规范化v2.md',
            failures/'per_arm.csv':docs/'逐题_三模型失败证据_规范化v2.csv',
            resources/'时间与token开销.md':docs/'时间与token开销_规范化v2.md',
            resources/'per_issue_resources.csv':docs/'逐题_时间与token_规范化v2.csv'}
        outputs={str(primary):sha(primary)}
        for source,destination in copies.items():
            if destination.exists():raise FileExistsError(destination)
            if destination.suffix=='.md':
                prefix=('本报告使用签名格式规范化v2的派生最终排名；文中Top5等排名字段不是模型新生成的答案。'
                    '原始回答、原解析和原评价均保留；同一批实际请求的token、费用及时间不能与旧视图相加重复计算。'
                    '逐项依据见派生view的normalization_provenance.json与view_manifest.json。\n\n')
                destination.write_text(prefix+source.read_text())
            else:shutil.copyfile(source,destination)
            outputs[str(destination)]=sha(destination)
        comp=docs/'原解析与规范化v2_同题对照.md'
        if comp.exists():raise FileExistsError(comp)
        comp.write_text(comparison_text);outputs[str(comp)]=sha(comp)
        write(work/'completion.json',{'status':'NORMALIZED_REPORTS_READY_FOR_INDEPENDENT_REVIEW','outputs_sha256':outputs,
            'new_model_calls':0,'Gold_read_for_normalization':False,'view_manifest_sha256':sha(view/'view_manifest.json'),
            'original_analysis_completion_sha256':sha(root/'analysis_supervisor/completion.json'),'time':time.time()})
        write(work/'status.json',{'phase':'NORMALIZED_REPORTS_READY_FOR_INDEPENDENT_REVIEW','time':time.time()},immutable=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--run',action='store_true');a=p.parse_args()
    if not a.run:print('CPU-only formatting view; no process started');return
    try:run(a.root)
    except BaseException as error:
        write(a.root/'signature_view_supervisor/error.json',{'error':type(error).__name__+': '+str(error),'time':time.time()});raise


if __name__=='__main__':main()
