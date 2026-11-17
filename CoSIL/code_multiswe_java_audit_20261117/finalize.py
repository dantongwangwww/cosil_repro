"""CPU-only completion fence and report delivery; never starts/retries a model."""
from pathlib import Path
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import time
from code_multiswe_java_20261117.common import ROOT,read,write,sha

TERMINAL={'complete','partial','worker_failed','timed_out','dependency_blocked','preparation_blocked'}


def analysis_code_fence(root):
    frozen=read(Path(root)/'audits/analysis_execution_freeze.json')
    if not frozen.get('commit') or not frozen.get('files_sha256'):
        raise ValueError('Recoverable frozen analysis source is required')
    for path,expected in frozen['files_sha256'].items():
        if sha(path)!=expected:raise RuntimeError('Analysis source changed: '+path)


def fence(root):
    root=Path(root)
    if not (root/'run/completion.json').is_file():return False
    marker=read(root/'run/completion.json')
    if marker.get('status')!='COMPLETE' or marker.get('allocated')!=128 or marker.get('groups')!=128:
        raise ValueError('Invalid full inference completion marker')
    rows=read(root/'allocation.json')['records']
    if len(rows)!=128 or len({r['instance_id'] for r in rows})!=128:raise ValueError('Roster drift')
    for row in rows:
        for arm in ('cosil','sfpruner','locagent'):
            path=root/'run'/row['instance_id']/arm/'terminal.json'
            if not path.exists():raise ValueError('Missing allocated terminal')
            t=read(path)
            if t.get('instance_id')!=row['instance_id'] or t.get('arm')!=arm or t.get('status') not in TERMINAL or t.get('keep_in_denominator') is not True:
                raise ValueError('Terminal scope drift')
    return True


def run(root):
    root=Path(root).resolve();work=root/'analysis_supervisor';work.mkdir(exist_ok=True)
    with (work/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        analysis_code_fence(root)
        while not fence(root):
            status=read(root/'services/status.json')
            if status['phase']=='STOPPED':raise RuntimeError('Inference supervisor stopped: '+str(status.get('error')))
            write(work/'status.json',{'phase':'WAITING_FULL128_TERMINALS','time':time.time(),'pid':os.getpid()},immutable=False)
            time.sleep(10)
        analysis_code_fence(root)
        frozen=read(root/'execution_freeze.json')
        for path,expected in frozen['files_sha256'].items():
            if sha(path)!=expected:raise RuntimeError('Frozen execution code changed: '+path)
        qual=read(root/'audits/evaluator_qualification_frozen.json')
        for path,expected in qual['gold_files_sha256'].items():
            if sha(path)!=expected:raise RuntimeError('Frozen evaluator target drift')
        python=str((ROOT.parent/'LocAgent/.venv/bin/python').absolute())
        evaldir=root/'reports/final128';faildir=root/'reports/failures128';resdir=root/'reports/resources128'
        jobs=[('evaluation','code_multiswe_java_20261117.evaluate',['--root',str(root),'--out',str(evaldir)]),
            ('failures','code_multiswe_java_audit_20261117.failures',['--root',str(root),'--evaluation-dir',str(evaldir),'--out',str(faildir)]),
            ('resources','code_multiswe_java_audit_20261117.resources',['--root',str(root),'--evaluation-dir',str(evaldir),'--out',str(resdir)])]
        env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TZ')}
        env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        for name,module,args in jobs:
            write(work/'status.json',{'phase':name,'time':time.time()},immutable=False)
            with (work/(name+'.log')).open('xb') as stream:
                result=subprocess.run([python,'-B','-m',module,*args],cwd=ROOT,env=env,
                    stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=3600)
            if result.returncode:raise RuntimeError('CPU '+name+' failed; preserve outputs and inspect log')
        docs=ROOT/'docs/multiswe-java128'
        mappings={evaldir/'总览.md':docs/'实验报告_Java128_三模型总览.md',
            evaldir/'per_issue.csv':docs/'逐题_Java128_三模型定位.csv',
            faildir/'定位错例报告.md':docs/'定位失败分类与逐题分析.md',
            faildir/'per_arm.csv':docs/'逐题_三模型失败证据.csv',
            resdir/'时间与token开销.md':docs/'时间与token开销.md',
            resdir/'per_issue_resources.csv':docs/'逐题_时间与token.csv'}
        outputs={}
        for source,destination in mappings.items():
            if destination.exists():raise FileExistsError('Never overwrite delivery: '+str(destination))
            shutil.copyfile(source,destination);outputs[str(destination)]=sha(destination)
        write(work/'completion.json',{'status':'ANALYSIS_READY_FOR_INDEPENDENT_REVIEW','outputs_sha256':outputs,
            'allocated':128,'file_denominator':read(evaldir/'summary.json')['file_denominator'],
            'function_denominator':read(evaldir/'summary.json')['function_denominator'],
            'new_model_calls':0,'GPU_used':False,'time':time.time()})
        write(work/'status.json',{'phase':'ANALYSIS_READY_FOR_INDEPENDENT_REVIEW','time':time.time()},immutable=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--run',action='store_true');a=p.parse_args()
    if a.run:
        try:run(a.root)
        except BaseException as error:
            write(a.root/'analysis_supervisor/error.json',{'error':type(error).__name__+': '+str(error),'time':time.time()});raise
    else:print(json.dumps({'full_terminal_fence':fence(a.root),'models_started':False}))


if __name__=='__main__':main()
