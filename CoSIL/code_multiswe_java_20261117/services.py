"""Owned-service supervisor. No service starts at import or without --run.

Only exact newly spawned process identities may be stopped. Existing GPU
contexts are observed and never signalled. Java experiment data stays local.
"""
from pathlib import Path
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

from .common import ROOT, RUN, PACKAGE, read, write, sha, event
from code_sfpruner300_20261114 import service_queue as base

MAIN_MODEL=Path('/tmp/cosil_rebench_qwen3_8b_20261023/model')
JUDGE_MODEL=ROOT/'models_v6/Qwen3-Reranker-4B'
ADAPTER=ROOT/'papers/SFPruner/checkpoints/specprune_epoch1'


def free_observation():
    rows=base.gpu_inventory()
    selected={r['index']:r for r in rows}
    # TP2 main takes fully idle cards2/3. Judge reserves only free memory on1;
    # the observed small unrelated context is never killed or reclassified.
    if any(selected[i]['has_compute_process'] or selected[i]['used_mib']>256 or selected[i]['utilization'] for i in (2,3)):
        raise RuntimeError('Main cards2/3 are no longer fully idle; no displacement')
    if selected[1]['free_mib']<20000 or selected[1]['utilization']:
        raise RuntimeError('Insufficient unused capacity for the separate judge; no displacement')
    return rows


def stop_spawned(receipt):
    """Initial exact argv plus unchanged birth identity tolerates API retitling."""
    saved=receipt['identity']
    def observe():
        try:
            raw=Path('/proc',str(saved['pid']),'stat').read_text();f=raw[raw.rfind(')')+2:].split()
            return {'pid':saved['pid'],'uid':Path('/proc',str(saved['pid'])).stat().st_uid,
                'state':f[0],'pgid':int(f[2]),'sid':int(f[3]),'start_ticks':int(f[19])}
        except (FileNotFoundError,ProcessLookupError):return None
    current=observe()
    if current is None or current['state']=='Z' or current['start_ticks']!=saved['start_ticks']:
        return {'leader_exited':True,'signal_sent':False}
    if saved['uid']!=os.getuid() or saved['pid']!=saved['pgid'] or saved['pid']!=saved['sid'] or any(current[k]!=saved[k] for k in ('pid','uid','pgid','sid','start_ticks')):
        return {'leader_exited':False,'signal_sent':False,'reason':'Birth identity mismatch; never signal'}
    os.killpg(saved['pgid'],signal.SIGTERM)
    end=time.monotonic()+40
    while time.monotonic()<end:
        current=observe()
        if current is None or current['state']=='Z' or current['start_ticks']!=saved['start_ticks']:
            return {'leader_exited':True,'signal_sent':'SIGTERM','forced_kill':False}
        time.sleep(.5)
    return {'leader_exited':False,'signal_sent':'SIGTERM','forced_kill':False,'reason':'Graceful shutdown deadline'}


def main_health():
    with urllib.request.urlopen('http://127.0.0.1:7343/v1/models',timeout=5) as response:
        value=json.load(response)
    if 'qwen3-8b' not in {r['id'] for r in value['data']}:raise RuntimeError('Unexpected main service')
    return value


class Supervisor:
    def __init__(self,root):
        self.root=Path(root).resolve();self.work=self.root/'services';self.work.mkdir(parents=True,exist_ok=True)
        self.children=[]

    def status(self,phase,**extra):
        value={'phase':phase,'pid':os.getpid(),'time':time.time(),**extra}
        write(self.work/'status.json',value,immutable=False);event(self.work/'events.jsonl',value)

    def spawn(self,role,argv,env):
        folder=self.work/role;folder.mkdir(exist_ok=False)
        stream=(folder/'console.log').open('xb')
        proc=subprocess.Popen(argv,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        owner=base.identity(proc.pid)
        if owner is None or not base.owned(owner,owner,argv,ROOT):raise RuntimeError('New process ownership not witnessed')
        receipt={'role':role,'identity':owner,'command':argv,'cwd':str(ROOT),'time':time.time()}
        write(folder/'ownership.json',receipt);self.children.append((role,proc,receipt,stream))
        return proc

    def verify_code(self):
        frozen=read(self.root/'execution_freeze.json')
        for path,expected in frozen['files_sha256'].items():
            if sha(path)!=expected:raise RuntimeError('Execution source/config drift: '+path)
        if not frozen.get('commit'):raise RuntimeError('Recoverable source publication required')

    def run(self):
        self.verify_code();initial=free_observation();self.status('idle_observation',gpus=initial)
        with socket.socket() as sock:
            sock.settimeout(.2)
            if sock.connect_ex(('127.0.0.1',7343))==0:raise RuntimeError('Port7343 already in use; no duplicate service')
        # Two fresh observations separated by90s; individual sleeps stay small.
        for _ in range(9):time.sleep(10);free_observation()
        sockdir=Path('/tmp')/('java128_judge_'+str(os.getpid()))
        mainenv,_=base.service_environment(self.work,(2,3))
        judgeenv,_=base.service_environment(self.work,(1,))
        # New entry wrappers are not needed: the frozen original judge accepts
        # the exact original six-field rendered input for both languages.
        mainproc=self.spawn('main',base.main_command(MAIN_MODEL),mainenv)
        judgeproc=self.spawn('judge',base.judge_command(JUDGE_MODEL,ADAPTER,sockdir),judgeenv)
        began=time.monotonic();score=sockdir/'score.sock'
        while True:
            if mainproc.poll() is not None or judgeproc.poll() is not None:
                raise RuntimeError('Owned model service exited during loading')
            try:
                health=main_health()
                if score.is_socket() and (sockdir/'ready.json').is_file():break
            except (OSError,ValueError):pass
            if time.monotonic()-began>900:raise RuntimeError('Model loading deadline exceeded')
            self.status('model_loading',seconds=time.monotonic()-began);time.sleep(5)
        write(self.work/'ready.json',{'main':health,'judge_socket':str(score),
            'judge_ready':read(sockdir/'ready.json'),'main_gpus':[2,3],'judge_gpu':1,
            'initial_other_contexts_preserved':initial,'time':time.time()})
        env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1'}
        common=[sys.executable,'-B','-m','code_multiswe_java_20261117.controller','--root',str(self.root),
            '--main-model',str(MAIN_MODEL),'--judge-socket',str(score)]
        canary=self.spawn('canary',common+['--canary-only'],env)
        self.monitor(canary,mainproc,judgeproc,'canary')
        if canary.returncode:raise RuntimeError('Canary controller failed; preserve all attempts')
        self.status('awaiting_canary_engineering_gate')
        waiting=time.monotonic()
        while not (self.root/'audits/canary_engineering_gate.json').exists():
            if mainproc.poll() is not None or judgeproc.poll() is not None:raise RuntimeError('Model service exited while awaiting engineering gate')
            if time.monotonic()-waiting>7200:raise RuntimeError('No engineering gate within2h; release owned services')
            self.status('awaiting_canary_engineering_gate');time.sleep(10)
        self.verify_code()
        if read(self.root/'audits/canary_engineering_gate.json').get('status')!='PASS':
            raise RuntimeError('Canary engineering gate failed')
        full=self.spawn('full',common,env)
        self.monitor(full,mainproc,judgeproc,'full')
        if full.returncode:raise RuntimeError('Full controller failed; no automatic semantic replay')
        self.status('inference_complete')

    def monitor(self,proc,main,judge,phase):
        began=time.monotonic()
        while proc.poll() is None:
            if main.poll() is not None or judge.poll() is not None:raise RuntimeError('Owned service died during '+phase)
            self.status(phase,seconds=time.monotonic()-began)
            if time.monotonic()-began>86400:raise RuntimeError('24h phase watchdog')
            time.sleep(10)

    def shutdown(self):
        outcomes={}
        for role,proc,receipt,stream in reversed(self.children):
            result=stop_spawned(receipt);outcomes[role]=result
            write(self.work/role/'shutdown.json',result)
            stream.close()
        write(self.work/'owned_shutdown.json',outcomes)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=RUN)
    p.add_argument('--run',action='store_true');args=p.parse_args()
    if not args.run:print(json.dumps({'main_gpus':[2,3],'judge_gpu':1,'model_services_started':False}));return
    s=Supervisor(args.root)
    try:s.run()
    except BaseException as error:
        s.status('STOPPED',error=type(error).__name__+': '+str(error));raise
    finally:s.shutdown()


if __name__=='__main__':main()
