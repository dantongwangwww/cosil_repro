"""T1 only: own Qwen service lifecycle, paired canary stop loss, no test access."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from datetime import datetime
import json
import math
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request

from code_v6.common import ROOT,BASE,OUT,DOCS,COHORTS,read,rows,write,status,sha,now,test_stats,verify_files

TARGET=OUT/'T1_execution'
PREP=OUT/'T1_canary_preparation'
AUTH=OUT/'user_execution_authorization.json'
SERVICE_SCRIPT=ROOT.parent/'CoSIL_new/scripts/start_qwen_native_tools.sh'


def gpu_snapshot():
    r=subprocess.run(['nvidia-smi','--query-gpu=index,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
    return {int(x.split(',')[0]):{'free_mib':int(x.split(',')[1]),'utilization':int(x.split(',')[2])} for x in r.stdout.splitlines()}


def gpu0_compute_pids():
    uuid=subprocess.run(['nvidia-smi','--id=0','--query-gpu=uuid','--format=csv,noheader'],capture_output=True,text=True,check=True).stdout.strip()
    rr=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
    return [int(line.split(',')[1]) for line in rr.stdout.splitlines() if line.split(',')[0].strip()==uuid]


def service_health():
    try:
        with urllib.request.urlopen('http://127.0.0.1:7333/health',timeout=3) as r:return r.status==200
    except Exception:return False


def proc_identity(pid):
    try:
        p=Path(f'/proc/{pid}');f=(p/'stat').read_text().rsplit(')',1)[1].split()
        if f[0] in {'Z','X'}:return None
        return {'pid':pid,'ppid':int(f[1]),'start_ticks':f[19],'uid':p.stat().st_uid}
    except (FileNotFoundError,ProcessLookupError):return None


def descendants(pid):
    all_p={}
    for p in Path('/proc').glob('[0-9]*'):
        try:
            x=proc_identity(int(p.name))
            if x:all_p[x['pid']]=x
        except PermissionError:pass
    selected={pid};changed=True
    while changed:
        extra={p for p,v in all_p.items() if v['ppid'] in selected};changed=not extra<=selected;selected|=extra
    return [all_p[p] for p in sorted(selected) if p in all_p]


def stop_owned(child):
    tracked=descendants(child.pid)
    def same(x):
        p=proc_identity(x['pid']);return p and p['start_ticks']==x['start_ticks'] and p['uid']==os.getuid()
    signals=[]
    if child.poll() is None:
        child.terminate();signals.append({'pid':child.pid,'signal':'SIGTERM'})
    end=time.monotonic()+30
    while time.monotonic()<end and any(same(x) for x in tracked):time.sleep(.5)
    for x in tracked:
        if same(x):
            os.kill(x['pid'],signal.SIGTERM);signals.append({'pid':x['pid'],'signal':'SIGTERM'})
    end=time.monotonic()+15
    while time.monotonic()<end and any(same(x) for x in tracked):time.sleep(.5)
    remaining=[x for x in tracked if same(x)]
    result={'time':now(),'service_pid':child.pid,'signals':signals,'remaining_owned_processes':remaining,
            'closed':not remaining and not service_health(),'other_processes_modified':False,'force_kill_used':False}
    status(TARGET/'service_shutdown.json',result)
    if remaining:raise RuntimeError('Owned service processes did not exit; cleanup remains incomplete')
    return result


def paired_stats(before,after):
    if len(before)!=len(after):raise ValueError('Pair by explicit IDs before calling this statistic')
    n=len(before);wins=sum(not a and b for a,b in zip(before,after));losses=sum(a and not b for a,b in zip(before,after))
    k=wins+losses
    p=min(1.,2*sum(math.comb(k,i) for i in range(min(wins,losses)+1))/2**k) if k else 1.
    def lower_success(success):
        if not success:return 0.
        lo,hi=0.,1.
        for _ in range(80):
            mid=(lo+hi)/2
            tail=sum(math.comb(n,j)*mid**j*(1-mid)**(n-j) for j in range(success,n+1))
            if tail<.025:lo=mid
            else:hi=mid
        return (lo+hi)/2
    lower=lower_success(wins)-(1-lower_success(n-losses)) if n else None
    return {'pairs':n,'off_hits':sum(before),'new_hits':sum(after),'wins':wins,'losses':losses,
            'delta':(wins-losses)/n if n else None,'mcnemar_exact_two_sided_p':p,
            'conservative_one_sided_95_lower_delta':lower,
            'noninferiority_margin':.03,'noninferiority_certified':bool(n and lower>=-.03),
            'interval_method':'Bonferroni paired-discordance binomial bounds: L(wins)-U(losses); not a zero-variance empirical bootstrap'}


def legacy_pruner_usage(events):
    calls=[e for e in events if e.get('event')=='model_call' and str(e.get('purpose','')).startswith('pruner')]
    return {'qwen_successful_calls':len(calls),
            'qwen_prompt_tokens':sum(e.get('usage',{}).get('prompt_tokens',0) for e in calls),
            'qwen_completion_tokens':sum(e.get('usage',{}).get('completion_tokens',0) for e in calls),
            'qwen_http_request_attempts':None,'HTTP_attempt_note':'Historical v3c did not record SDK-level HTTP send attempts',
            'small_calls':0,'small_input_tokens':0,'small_generated_output_tokens':0,'small_scored_positions':0}


def evaluate_case(row,gold,result,events):
    from code_v3b.analyze_experiment_300 import predictions,expected,contains_gold
    targets=expected(gold,'function');pred=predictions(result['found_related_locs'])
    if not targets:raise ValueError('Canary was preselected to be function-scorable')
    prunes=[e for e in events if e.get('event')=='prune' and contains_gold(row,gold,e)]
    return {'function_top5':bool(targets&set(pred[:5])),'predictions':pred,
            'gold_prune_events':[{'step':e['step'],'tool':e['tool'],'arguments':e['arguments'],
                  'decision':e['decision'],'origin':e.get('decision_origin','Qwen'),'p_yes':e.get('p_yes')} for e in prunes],
            'gold_direct_small_false':sum(e.get('decision_origin')=='small' and e['decision']=='False' for e in prunes),
            'gold_Qwen_false':sum(e.get('decision_origin')!='small' and e['decision']=='False' for e in prunes)}


def publish(state,off,results):
    assessments={}
    for mode,records in results.items():
        ids=[iid for iid in off if iid in records]
        assessments[mode]=paired_stats([off[i]['function_top5'] for i in ids],[records[i]['function_top5'] for i in ids])
    state.update(time=now(),paired=assessments,completed_by_arm={k:len(v) for k,v in results.items()})
    status(TARGET/'status.json',state)
    status(TARGET/'paired_results.json',{'off':off,'new_arms':results,'paired':assessments,'test_opened':False})
    return assessments


def run():
    import fcntl
    auth=read(AUTH)
    if not (auth['T1_allowed'] and auth['restart_original_Qwen_service'] and auth['shutdown_Qwen_after_T1']):
        raise PermissionError('Explicit service lifecycle authorization missing')
    if auth['test_open_allowed'] or auth['T3_allowed']:raise PermissionError('Wrong stage scope')
    p=read(PREP/'protocol.json');verify_files(p['source_sha256'])
    if sha(SERVICE_SCRIPT)!=auth['original_service_script_sha256']:raise RuntimeError('Original service script changed')
    assert (p['best_epoch'],p['low'],p['high'])==(1,.6,.9)
    snapshots=test_stats();history=read(OUT/'T0_visibility/start_receipt.json')['historical_sha256']
    verify_files(history)
    TARGET.mkdir(parents=True,exist_ok=False)
    state={'started_at':now(),'stage':'waiting_for_GPU0_headroom','test_opened':False,'T2_independent':True,
           'service_started':False,'other_processes_modified':False}
    sample=read(PREP/'sampling_manifest.json');ids=sample['selected_issue_ids']
    split=read(COHORTS['B']/'split_manifest.json')['splits']
    assert len(ids)==20 and not set(ids)&set(split['test'])
    official={r['instance_id']:r for r in rows(ROOT.parent/'GraphLocator/datasets/swe_bench_lite.jsonl') if r['instance_id'] in ids}
    gold=read(ROOT/'ground_truth_300.json')
    prepared=read(ROOT/'results/qwen_300/prepared_inputs.json')
    off={};results={'hybrid':{},'small':{}}
    for r in sample['analysis_only_records']:
        iid=r['instance_id'];old=read(r['historical_off_case']);events=rows(r['historical_off_events'])
        score=evaluate_case(official[iid],gold[iid],old,events)
        assert score['function_top5']==r['historical_off_top5']
        off[iid]={**score,'usage':legacy_pruner_usage(events),'reused':True}
    write(TARGET/'source_bindings.json',{'authorization_sha256':sha(AUTH),'prep_sha256':sha(PREP/'protocol.json'),
          'code_sha256':{str(f):sha(f) for f in [Path(__file__),ROOT/'code_v6/report_T1.py',ROOT/'code_v6/common.py']},'old_sources':p['source_sha256'],
          'original_v5_pipeline_sha256':sha(ROOT/'code_v5/run_pipeline.py'),
          'original_v5_pruner_sha256':sha(ROOT/'code_v5/pruner_pipeline.py'),
          'test_stat_only':snapshots})
    publish(state,off,results)
    child=None;pool=None;service_log=None
    try:
        with (TARGET/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if service_health():raise RuntimeError('7333 already has a service; never adopt or stop an unowned process')
            quiet_since=None;wait_start=time.monotonic()
            while True:
                inventory=gpu_snapshot();state['GPU_observation']=inventory
                peers=gpu0_compute_pids();state['GPU0_peer_compute_pids']=peers
                enough=inventory[0]['free_mib']>=23000 and inventory[2]['free_mib']>=4096 and not peers
                quiet_since=(quiet_since or time.monotonic()) if enough else None
                state['continuous_empty_GPU0_seconds']=round(time.monotonic()-quiet_since,1) if quiet_since else 0
                if quiet_since and time.monotonic()-quiet_since>=90:break
                if time.monotonic()-wait_start>6*3600:
                    state.update(stage='resource_unavailable',stop_reason='No continuously empty GPU0 within6h for original .92 service');return
                publish(state,off,results);time.sleep(10)
            service_log=(TARGET/'qwen_service.log').open('x')
            child=subprocess.Popen(['bash',str(SERVICE_SCRIPT)],cwd=ROOT,stdout=service_log,stderr=subprocess.STDOUT,start_new_session=True)
            state.update(stage='loading_original_Qwen_service',service_started=True,service_pid=child.pid)
            publish(state,off,results)
            while not service_health():
                if child.poll() is not None:raise RuntimeError('Original Qwen service exited while loading; preserve log, no automatic config changes')
                time.sleep(5)
            state.update(stage='running_canary',service_ready_at=now(),physical_judge_gpu=2)
            publish(state,off,results)
            from code_v5.run_pipeline import worker_init,run_case
            winner={k:p[k] for k in ['adapter_dir','model_dir','temperature','low','high']}
            winner['track']='exploratory';winner_sha=sha(PREP/'protocol.json')
            pool=ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'),initializer=worker_init,initargs=(2,))
            stopped=False
            for iid in ids:
                for mode in ['hybrid','small']:
                    manifest={'phase':'canary','mode':mode,'repeat':1,'track':'exploratory',
                              'version_sha256':sha(PREP/'protocol.json')}
                    clean={k:official[iid][k] for k in ['instance_id','repo','base_commit','problem_statement']}
                    assert set(clean)=={'instance_id','repo','base_commit','problem_statement'}
                    folder=TARGET/mode
                    state.update(active_issue=iid,active_mode=mode);publish(state,off,results)
                    future=pool.submit(run_case,(iid,clean,prepared['candidates'][iid][:5],str(folder),manifest,winner,winner_sha))
                    while True:
                        try:r=future.result(timeout=30);break
                        except TimeoutError:publish(state,off,results)
                    if r['status']!='complete':raise RuntimeError('Canary case failed: '+mode+'/'+iid)
                    actual=read(folder/'cases'/f'{iid}.json');events=rows(folder/'events'/f'off_{iid}.jsonl')
                    score=evaluate_case(clean,gold[iid],actual,events)
                    usage=actual['statistics']['pruner']['all']
                    small=[e for e in events if e['event']=='small_judge']
                    score.update(usage=usage,small_routes=dict(Counter(e['route'] for e in small)),
                                 local_latency_seconds=[e['wall_seconds'] for e in small],
                                 all_pruner_latency_seconds=[e['elapsed_seconds'] for e in events if e['event']=='v5_pruner_latency'],
                                 case_path=str(folder/'cases'/f'{iid}.json'),case_sha256=sha(folder/'cases'/f'{iid}.json'))
                    results[mode][iid]=score
                    assessments=publish(state,off,results)
                    print(json.dumps({'time':now(),'mode':mode,'issue':iid,'Top5':score['function_top5'],'paired':assessments[mode]},ensure_ascii=False),flush=True)
                    if assessments[mode]['delta']<-.03-1e-12:
                        state.update(stage='stop_loss',stop_reason='Top5 decrease exceeds3pp on completed matched issue pairs',stop_arm=mode)
                        stopped=True;break
                if stopped:break
            if not stopped:state.update(stage='complete')
    except Exception as e:
        state.update(stage='failed',error_type=type(e).__name__,error=str(e));raise
    finally:
        if pool is not None:pool.shutdown(wait=True)
        try:
            if child is not None:state['service_shutdown']=stop_owned(child)
        finally:
            if service_log:service_log.close()
            state['ended_at']=now();publish(state,off,results)
            assert test_stats()==snapshots
            verify_files(history);verify_files(p['source_sha256'])
            from code_v6.report_T1 import build_report
            build_report()


if __name__=='__main__':
    run()
