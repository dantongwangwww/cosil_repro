"""Wait for actual report closure, then run independent CPU audit commands."""
from pathlib import Path
import argparse
import fcntl
import os
import subprocess
import sys
import time
from code_multiswe_java_20261117.common import ROOT,read,write,sha


def require_pass(result):
    # metrics_audit intentionally exits0 for PENDING; exit0 alone is not proof.
    if result.get('status')!='PASS' or result.get('errors'):
        raise ValueError('Independent evidence has not passed: '+str(result.get('status')))


def source_fence(root):
    value=read(Path(root)/'audits/final_audit_execution_freeze.json')
    if not value.get('commit') or not value.get('files_sha256'):raise ValueError('Published audit source required')
    for path,expected in value['files_sha256'].items():
        if sha(path)!=expected:raise ValueError('Independent source changed: '+path)


def run(root):
    root=Path(root).resolve();work=root/'independent_audit_supervisor';work.mkdir(exist_ok=True)
    with (work/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);source_fence(root)
        while not (root/'signature_view_supervisor/completion.json').exists():
            for folder in ('analysis_supervisor','signature_view_supervisor'):
                if (root/folder/'error.json').exists():raise RuntimeError('Prior CPU analysis needs review: '+folder)
            if read(root/'services/status.json')['phase']=='STOPPED':raise RuntimeError('Inference stopped; audit remains incomplete')
            write(work/'status.json',{'phase':'WAITING_SIGNATURE_REPORT_CLOSURE','pid':os.getpid(),'time':time.time()},immutable=False)
            time.sleep(10)
        source_fence(root)
        jobs=[('original_metrics','code_multiswe_java_final_audit_20261117.metrics_audit',
            ['--root',str(root),'--evaluation-dir',str(root/'reports/final128')],root/'audits/independent_original_metrics.json'),
            ('signature_metrics','code_multiswe_java_final_audit_20261117.metrics_audit',
            ['--root',str(root),'--evaluation-dir',str(root/'reports/signature_v2_evaluation'),
             '--view-root',str(root/'evaluation_views/signature_format_v2')],root/'audits/independent_signature_v2_metrics.json'),
            ('lineage','code_multiswe_java_final_audit_20261117.lineage_audit',
             ['--root',str(root)],root/'audits/independent_final_lineage.json')]
        env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TZ')}
        env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        passed={}
        for name,module,argv,output in jobs:
            write(work/'status.json',{'phase':name,'time':time.time()},immutable=False)
            with (work/(name+'.log')).open('xb') as log:
                proc=subprocess.run([sys.executable,'-B','-m',module,*argv,'--out',str(output)],
                    cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=7200)
            if proc.returncode:raise RuntimeError('Independent '+name+' exited nonzero; preserve log/failed receipt')
            require_pass(read(output));passed[str(output)]=sha(output)
        write(work/'completion.json',{'status':'ALL_THREE_INDEPENDENT_AUDITS_PASS','audits_sha256':passed,
            'allocated':128,'new_model_calls':0,'GPU_used':False,'final_goal_completion_not_automatically_claimed':True,
            'remaining_root_review':['Owned GPU/CUDA release','Final scope/protected-history audit','Final aggregate code/docs publication and user notification'],
            'time':time.time()})
        write(work/'status.json',{'phase':'ALL_THREE_INDEPENDENT_AUDITS_PASS','time':time.time()},immutable=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--run',action='store_true');a=p.parse_args()
    if not a.run:print('CPU-only independent audit supervisor; no process started');return
    try:run(a.root)
    except BaseException as error:
        write(a.root/'independent_audit_supervisor/error.json',{'error':type(error).__name__+': '+str(error),'time':time.time()});raise


if __name__=='__main__':main()
