"""Adopt only identified own live workers; retry7B once, keep all first-round gates."""
import os,subprocess,time
from pathlib import Path
from code_v6.common import ROOT,OUT,read,write,status,now,test_stats,verify_files,sha
from code_v6.train_T3 import RACE,SPECS

def identity(pid):
    try:
        p=Path('/proc')/str(pid);stat=(p/'stat').read_text().rsplit(')',1)[1].split()
        if stat[0] in ['Z','X']:return None
        return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':stat[19],'command_args':(p/'cmdline').read_bytes().split(b'\0')[:-1]}
    except (FileNotFoundError,ProcessLookupError):return None

def run():
    protocol=read(RACE/'protocol.json');verify_files(protocol['code_sha256']);before=test_stats();known={}
    for key in ['anchor06B','reranker4B']:
        r=read(RACE/key/'process_receipt.json');who=identity(r['pid'])
        assert who and who['uid']==os.getuid() and b'code_v6.train_T3' in who['command_args'] and key.encode() in who['command_args']
        known[key]={k:v for k,v in who.items() if k!='command_args'}
    folder=RACE/'swerank7B';log=(folder/'runner.log').open('x');env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='3'
    child=subprocess.Popen([str(ROOT/'.venv-v5/bin/python'),'-u','-m','code_v6.recover_T3_swerank'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    who=identity(child.pid);known['swerank7B']={k:v for k,v in who.items() if k!='command_args'}
    write(folder/'process_receipt.json',{'time':now(),'pid':child.pid,'physical_gpu':3,'resource_recovery':True})
    write(RACE/'scheduler_recovery_start.json',{'time':now(),'pid':os.getpid(),'adopted_own_worker_identities':known,
        'old_CPU_scheduler_only_stopped':True,'training_workers_stopped':False,'test_opened':False})
    from code_v6.report_T3 import run as report
    done=set()
    while len(done)<3:
        for key,who in known.items():
            if key in done:continue
            current=identity(who['pid']);alive=current and current['uid']==who['uid'] and current['start_ticks']==who['start_ticks']
            folder=RACE/key
            if not alive:
                done.add(key)
                if key=='swerank7B':code=child.wait();log.close()
                else:code=0 if (folder/'training_summary.json').exists() else None
                if not (folder/'process_exit.json').exists():write(folder/'process_exit.json',{'time':now(),'exit_code':code,'observed_by_recovery_monitor':True})
                if not (folder/'training_summary.json').exists():status(folder/'status.json',{'time':now(),'stage':'failed','error':'worker exited without completed summary','test_opened':False})
        report()
        if len(done)<3:time.sleep(30)
    assert test_stats()==before;verify_files(protocol['code_sha256'])
    write(RACE/'scheduler_complete.json',{'time':now(),'test_opened':False,'T4_started':False,'first_round_finished_processes':sorted(done),'user_interpretation_required':True,'resource_recovery_applied':True})

if __name__=='__main__':run()
