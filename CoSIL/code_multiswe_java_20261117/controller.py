"""Durable full-roster controller, no Gold reads and no semantic retries."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import json
import os
import subprocess
import threading
import time
import traceback

from .common import ROOT, RUN, ARMS, read, write, sha, event
from . import backend


class Controller:
    def __init__(self, root, main_model, judge_socket):
        self.root=Path(root).resolve();self.main_model=Path(main_model).resolve();self.judge_socket=Path(judge_socket).resolve()
        self.allocation=read(self.root/'allocation.json');self.rows=self.allocation['records']
        if self.allocation['n']!=128 or len(self.rows)!=128:raise ValueError('Full Java128 allocation required')
        self.lock=threading.RLock();self.completed=set()

    def progress(self,phase,**extra):
        with self.lock:
            write(self.root/'run/progress.json',{'phase':phase,'completed':len(self.completed),'allocated':128,
                'time':time.time(),'pid':os.getpid(),**extra},immutable=False)

    def run_arm(self,row,arm,stage,public,shared=None):
        out=self.root/'run'/row['instance_id']/arm;out.mkdir(parents=True,exist_ok=True)
        terminal=out/'terminal.json'
        if terminal.exists():return read(terminal)
        if (out/'controller_started.json').exists():raise RuntimeError('Already-started arm never automatically replayed: '+str(out))
        argv=backend.command(arm,stage,public,out,main_model=self.main_model,judge_socket=self.judge_socket,shared=shared)
        # Real mount check occurs before any model call.
        probe=subprocess.run(backend.probe_command(argv),capture_output=True,text=True,timeout=45)
        if probe.returncode:raise RuntimeError('Isolation probe: '+probe.stdout[-1500:]+probe.stderr[-1500:])
        write(out/'isolation.json',json.loads(probe.stdout.strip().splitlines()[-1]))
        write(out/'controller_started.json',{'instance_id':row['instance_id'],'arm':arm,'time':time.time(),
            'job_sha256':sha(stage/'job.json'),'command':argv})
        began=time.monotonic()
        with (out/'console.log').open('xb') as log:
            proc=subprocess.Popen(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            from code_sfpruner300_20261114.controller import current_process,signal_owned
            owner=current_process(proc.pid);write(out/'process.json',owner)
            timeout=3600 if arm!='locagent' else 2000
            timed_out=False
            while proc.poll() is None:
                elapsed=time.monotonic()-began
                write(out/'heartbeat.json',{'pid':proc.pid,'elapsed_seconds':elapsed,'time':time.time()},immutable=False)
                if elapsed>timeout:
                    cleanup=signal_owned(owner);write(out/'timeout_cleanup.json',cleanup);timed_out=True
                    try:proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:raise RuntimeError('Owned worker failed to stop; no forced kill')
                    break
                time.sleep(2)
        result=read(out/'result.json') if (out/'result.json').exists() else {}
        status=('timed_out' if timed_out else 'complete' if proc.returncode==0 and result.get('status') in ('complete','completed','success')
            else 'partial' if result.get('status')=='partial' else 'worker_failed')
        value={'instance_id':row['instance_id'],'arm':arm,'status':status,'exit_code':proc.returncode,
            'elapsed_seconds':time.monotonic()-began,'keep_in_denominator':True,
            'result_sha256':sha(out/'result.json') if result else None}
        write(terminal,value);event(self.root/'run/events.jsonl',value);return value

    def pair(self,row):
        iid=row['instance_id'];public=self.root/'public'/iid;group=self.root/'run'/iid
        group.mkdir(parents=True,exist_ok=True)
        marker=group/'group_terminal.json'
        if marker.exists():
            with self.lock:self.completed.add(iid)
            return read(marker)
        wait_began=time.monotonic()
        receipt=self.root/'preparation'/(iid+'.json')
        while not receipt.exists():
            progress=read(self.root/'preparation_progress.json')
            if progress['done']==128 or time.monotonic()-wait_began>3600:
                arms={arm:{'instance_id':iid,'arm':arm,'status':'preparation_blocked',
                    'model_called':False,'keep_in_denominator':True,
                    'reason':'Public base preparation did not complete; see immutable CPU errors'} for arm in ARMS}
                for arm,value in arms.items():write(group/arm/'terminal.json',value)
                value={'instance_id':iid,'status':'group_terminal','arms':arms};write(marker,value)
                with self.lock:self.completed.add(iid)
                self.progress('running',last=iid);return value
            self.progress('waiting_public_preparation',current=iid);time.sleep(5)
        stage=group/'input';backend.stage(public,stage)
        results={}
        results['cosil']=self.run_arm(row,'cosil',stage,public)
        raw=read(group/'cosil/result.json') if (group/'cosil/result.json').exists() else {}
        if 'file_rank_after_reflection' in raw and 'raw_file_responses' in raw:
            shared=group/'shared.json';write(shared,{'instance_id':iid,'base_commit':row['base_commit'],
                'files':raw['file_rank_after_reflection'],'raw_file_responses':raw['raw_file_responses']})
            results['sfpruner']=self.run_arm(row,'sfpruner',stage,public,shared)
        else:
            results['sfpruner']={'instance_id':iid,'arm':'sfpruner','status':'dependency_blocked',
                'reason':'Shared CoSIL file stage absent','model_called':False,'keep_in_denominator':True}
            write(group/'sfpruner/terminal.json',results['sfpruner'])
        results['locagent']=self.run_arm(row,'locagent',stage,public)
        value={'instance_id':iid,'status':'group_terminal','arms':results};write(marker,value)
        with self.lock:self.completed.add(iid)
        self.progress('running',last=iid);return value

    def run(self,*,canary_only=False):
        from code_sfpruner300_20261114.controller import lock_output
        with lock_output(self.root/'run'):
            # Canary membership is fixed before source availability or outcomes.
            for row in self.rows[:3]:
                self.progress('canary',current=row['instance_id']);self.pair(row)
            write(self.root/'run/canary_terminal.json',{'ids':[r['instance_id'] for r in self.rows[:3]],
                'completed':True,'accuracy_used_for_method_selection':False})
            if canary_only:return
            if not (self.root/'audits/canary_engineering_gate.json').exists():
                self.progress('awaiting_canary_engineering_audit');return
            gate=read(self.root/'audits/canary_engineering_gate.json')
            if gate.get('status')!='PASS':raise RuntimeError('Canary engineering gate not passed')
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures={pool.submit(self.pair,r):r for r in self.rows[3:]}
                for f in as_completed(futures):
                    row=futures[f]
                    try:f.result()
                    except Exception:
                        event(self.root/'run/errors.jsonl',{'instance_id':row['instance_id'],'traceback':traceback.format_exc()})
                        self.progress('controller_error',current=row['instance_id']);raise
            write(self.root/'run/completion.json',{'status':'COMPLETE','allocated':128,'groups':len(self.completed),'time':time.time()})
            self.progress('complete')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=RUN)
    p.add_argument('--main-model',type=Path,required=True);p.add_argument('--judge-socket',type=Path,required=True)
    p.add_argument('--canary-only',action='store_true');args=p.parse_args()
    Controller(args.root,args.main_model,args.judge_socket).run(canary_only=args.canary_only)


if __name__=='__main__':main()
