"""Persistent first-round scheduler. No retuning, test, or T4 transition."""
import os,subprocess,time
from pathlib import Path
from code_v6.common import ROOT,OUT,read,status,write,now,sha,test_stats,verify_files
from code_v6.train_T3 import RACE,SPECS

def run():
    protocol=read(RACE/'protocol.json');verify_files(protocol['code_sha256'])
    before=test_stats();processes={};streams={};started=set();terminal=set();began=time.monotonic()
    write(RACE/'scheduler_start.json',{'time':now(),'pid':os.getpid(),'T3_protocol_sha256':sha(RACE/'protocol.json'),
        'scheduler_code_sha256':sha(Path(__file__)),'test_stat_only':before,'first_round_only':True})
    from code_v6.report_T3 import run as report
    while len(terminal)<len(SPECS):
        for key,spec in SPECS.items():
            folder=RACE/key;folder.mkdir(parents=True,exist_ok=True)
            if key in terminal:continue
            if key not in started:
                receipt=OUT/'T3_model_sources'/f'{key}_download_receipt.json'
                if key=='anchor06B' or receipt.exists():
                    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=str(spec['gpu'])
                    log=(folder/'runner.log').open('x');streams[key]=log
                    processes[key]=subprocess.Popen([str(ROOT/'.venv-v5/bin/python'),'-u','-m','code_v6.train_T3','--key',key],
                        cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
                    started.add(key)
                    write(folder/'process_receipt.json',{'time':now(),'pid':processes[key].pid,'physical_gpu':spec['gpu'],'own_process':True})
                else:
                    status(folder/'status.json',{'time':now(),'stage':'queued_waiting_for_verified_model','test_opened':False})
                    if time.monotonic()-began>4*3600:
                        status(folder/'status.json',{'time':now(),'stage':'download_failed','reason':'No verified full model within4h; partial files never loaded','test_opened':False});terminal.add(key)
            elif processes[key].poll() is not None:
                exitcode=processes[key].returncode;streams[key].close();terminal.add(key)
                write(folder/'process_exit.json',{'time':now(),'exit_code':exitcode})
        report()
        if len(terminal)<len(SPECS):time.sleep(30)
    assert test_stats()==before;report()
    write(RACE/'scheduler_complete.json',{'time':now(),'test_opened':False,'T4_started':False,'first_round_finished_processes':sorted(terminal),'user_interpretation_required':True})

if __name__=='__main__':run()
