"""Persistent canary controller: owned service lifetime, immediate paired stop loss."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,TimeoutError
import contextlib
import fcntl
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
from .common import *
from code_v6.run_T1 import paired_stats,evaluate_case,legacy_pruner_usage,service_health,descendants,proc_identity

_JUDGE=None


def inventory():
    r=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    g={}
    for line in r.splitlines():
        index,uuid,free,util=[s.strip() for s in line.split(',')]
        g[int(index)]={'uuid':uuid,'free_mib':int(free),'utilization':int(util),'compute_pids':[]}
    apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
    for line in apps.splitlines():
        uuid,pid=[s.strip() for s in line.split(',')]
        for v in g.values():
            if v['uuid']==uuid:v['compute_pids'].append(int(pid))
    return g


def worker_init():
    os.environ.update(CUDA_VISIBLE_DEVICES='3',TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2')
    import torch
    torch.set_num_threads(2)
    from code_v5.run_pipeline import attach_http_audit
    from code_v3b import qwen_model
    original=qwen_model.make_model
    def factory(*a,**k):return attach_http_audit(original(*a,**k))
    qwen_model.make_model=factory


def case(task):
    global _JUDGE
    iid,row,files,arm,config,version=task
    if set(row)!={'instance_id','repo','base_commit','problem_statement'}:raise ValueError('Inference payload is not label-free')
    from .judge import Judge
    from .pipeline import AFL
    from afl.util.preprocess_data import filter_none_python,filter_out_test_files
    from afl.util.utils import setup_logger
    from code_v5.run_pipeline import instrument_agent,trace_stats,_CONTEXT
    folder=OUT/arm
    for name in ['cases','failures','events','logs']:(folder/name).mkdir(parents=True,exist_ok=True)
    if any((folder/n/(iid+'.json')).exists() for n in ['cases','failures']):raise FileExistsError('No overwriting completed/failed cases')
    event_path=folder/'events'/('off_'+iid+'.jsonl')
    if event_path.exists():raise FileExistsError('Interrupted trace is immutable; preserve before retry')
    os.environ.update(NODE_ANNOTATION='off',V3B_LOG_DIR=str(folder/'events'),COSIL_CONTEXT_LIMIT='65536')
    start=time.perf_counter();agent=None;cached=_JUDGE is not None
    try:
        if _JUDGE is None:_JUDGE=Judge(config['temperature'])
        began=time.perf_counter();_JUDGE.renderer.load(iid,row['repo'],row['base_commit'])
        structure_seconds=time.perf_counter()-began
        record=read(ROOT/'repo_structures_verified'/(iid+'.json'));structure=record['structure']
        filter_none_python(structure)
        if not iid.startswith('pytest'):filter_out_test_files(structure)
        logger=setup_logger(str(folder/'logs'/(iid+'.log')))
        low=config['default_low'] if arm=='hybrid_default' else config['safe_low_star']
        agent=AFL(iid,structure,row['problem_statement'],'llama3','openai',logger,
            context_limit=65536,judge=_JUDGE,low=low,high=config['high'])
        _CONTEXT.update(agent=agent,purpose=None,pruner_scope=None);instrument_agent(agent)
        with (folder/'logs'/(iid+'.stdout.log')).open('x') as stream:
            with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
                agent._record_event('run_start',protocol='v6_canary_v2_long_input',mode=arm,version_sha256=version,found_files=files,
                    structure_graph_seconds=structure_seconds,structure_sha256=_JUDGE.renderer.structure_sha,
                    graph_functions=len(_JUDGE.renderer.graph.functions),graph_edges=len(_JUDGE.renderer.graph.edges))
                agent._record_event('small_judge_load',cached=cached,model_load_seconds=0. if cached else _JUDGE.model_load_seconds,
                    definition='Single GPU3 transformers model load; graph rendering and prediction timed separately')
                locations,raw,trajectory=agent.localize_with_p(file=files,max_retry=10)
                agent._record_event('run_end',found_related_locs=locations)
        events=rows(event_path)
        assert sum(e['event']=='run_start' for e in events)==sum(e['event']=='run_end' for e in events)==1
        result={'instance_id':iid,'arm':arm,'status':'complete','protocol':'v6_canary_v2_long_input',
            'found_files':files,'found_related_locs':locations,'raw_output':raw,'func_traj':trajectory,
            'elapsed_seconds':time.perf_counter()-start,'statistics':trace_stats(events),
            'structure_graph_seconds':structure_seconds,'version_sha256':version,'base_commit':row['base_commit']}
        write(folder/'cases'/(iid+'.json'),result)
        return {'instance_id':iid,'arm':arm,'status':'complete'}
    except Exception as error:
        if agent is not None:agent._record_event('run_error',error=type(error).__name__,message=str(error)[:500])
        failure={'instance_id':iid,'arm':arm,'status':'failed','error':type(error).__name__,
            'message':str(error),'traceback':traceback.format_exc(),'elapsed_seconds':time.perf_counter()-start}
        write(folder/'failures'/(iid+'.json'),failure);return failure
    finally:_CONTEXT.clear()


def shutdown(child):
    tracked=descendants(child.pid);signals=[]
    def same(x):
        p=proc_identity(x['pid'])
        return p and p['start_ticks']==x['start_ticks'] and p['uid']==os.getuid()
    for sig,wait_seconds in [(signal.SIGTERM,30),(signal.SIGTERM,15)]:
        for p in tracked:
            if same(p):
                try:os.kill(p['pid'],sig);signals.append({'pid':p['pid'],'signal':sig.name})
                except ProcessLookupError:pass
        deadline=time.monotonic()+wait_seconds
        while time.monotonic()<deadline and any(same(x) for x in tracked):time.sleep(.5)
    child.poll();remaining=[x for x in tracked if same(x)]
    r={'time':now(),'service_pid':child.pid,'tracked_owned_processes':tracked,'signals':signals,
       'remaining_owned_processes':remaining,'closed':not remaining and not service_health(),
       'other_processes_modified':False,'force_kill_used':False}
    status(OUT/'service_shutdown.json',r)
    if not r['closed']:raise RuntimeError('Owned service cleanup incomplete')
    return r


def run():
    freeze=verify();config=read(OUT/'deployment_parameters.json')
    auth=read(OUT/'user_authorization.json')
    assert auth['restart_original_vllm7333'] and auth['shutdown_on_completion_stop_or_failure']
    lock=(OUT/'execution.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (OUT/'execution_started.json').exists():raise FileExistsError('Execution already started; never silently rerun')
    write(OUT/'execution_started.json',{'time':now(),'freeze_sha256':sha(OUT/'freeze.json'),'pid':os.getpid()})
    sample=read(OUT/'sample_and_off_reuse.json');ids=sample['selected_issue_ids']
    issues=read(OUT/'inference_issues.json');gold=read(ROOT/'ground_truth_300.json')
    prepared=read(ROOT/'results/qwen_300/prepared_inputs.json')
    off={};new={arm:{} for arm in ARMS}
    for row in sample['records']:
        iid=row['instance_id'];actual=read(row['historical_off_case']);ev=rows(row['historical_off_events'])
        score=evaluate_case(issues[iid],gold[iid],actual,ev)
        assert score['function_top5']==row['historical_off_top5']
        calls=[e for e in ev if e['event']=='model_call']
        score.update(reused=True,usage=legacy_pruner_usage(ev),
          total_usage={'qwen_prompt_tokens':sum(e.get('usage',{}).get('prompt_tokens',0) for e in calls),
                       'qwen_completion_tokens':sum(e.get('usage',{}).get('completion_tokens',0) for e in calls)})
        off[iid]=score
    state={'started_at':now(),'stage':'waiting_for_empty_GPU0_and_GPU3','test_opened':False,
           'service_started':False,'other_processes_modified':False}
    def publish():
        paired={}
        for arm,records in new.items():
            matched=[iid for iid in ids if iid in records]
            # paired_stats needs n>0 for its interval routine.
            paired[arm]=paired_stats([off[i]['function_top5'] for i in matched],[records[i]['function_top5'] for i in matched]) if matched else {'pairs':0,'delta':None}
        state.update(time=now(),completed_by_arm={a:len(r) for a,r in new.items()},paired=paired)
        status(OUT/'status.json',state)
        status(OUT/'paired_results.json',{'off':off,'new_arms':new,'paired':paired,'test_opened':False})
        return paired
    service=None;pool=None;log=None;publish()
    try:
        if service_health():raise RuntimeError('An unowned service already occupies7333; do not adopt or stop it')
        quiet=None;began=time.monotonic()
        while True:
            gpu=inventory();state['GPU_observation']=gpu
            enough=all(not gpu[k]['compute_pids'] for k in [0,3]) and gpu[0]['free_mib']>=23000 and gpu[3]['free_mib']>=21000
            quiet=(quiet or time.monotonic()) if enough else None
            state['continuous_empty_seconds']=round(time.monotonic()-quiet,1) if quiet else 0
            if quiet and time.monotonic()-quiet>=90:break
            if time.monotonic()-began>6*3600:raise RuntimeError('No empty GPU0/GPU3 window within6h')
            publish();time.sleep(10)
        log=(OUT/'qwen_service.log').open('x')
        service=subprocess.Popen(['bash',str(SERVICE_SCRIPT)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state.update(stage='loading_original_Qwen7333',service_started=True,service_pid=service.pid);publish()
        deadline=time.monotonic()+900
        while not service_health():
            if service.poll() is not None:raise RuntimeError('Original Qwen service failed to load; preserve unchanged configuration')
            if time.monotonic()>deadline:raise TimeoutError('Original Qwen loading exceeded15min')
            publish();time.sleep(5)
        state.update(stage='running_canary_v2',service_ready_at=now());publish()
        pool=ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'),initializer=worker_init)
        stop=False
        for iid in ids:
            for arm in ARMS:
                state.update(active_issue=iid,active_arm=arm);publish()
                future=pool.submit(case,(iid,issues[iid],prepared['candidates'][iid][:5],arm,config,sha(OUT/'freeze.json')))
                while True:
                    try:r=future.result(timeout=30);break
                    except TimeoutError:publish()
                if r['status']!='complete':raise RuntimeError('Case failed: '+str(r))
                folder=OUT/arm;actual=read(folder/'cases'/(iid+'.json'));events=rows(folder/'events'/('off_'+iid+'.jsonl'))
                score=evaluate_case(issues[iid],gold[iid],actual,events)
                local=[e for e in events if e['event']=='small_judge']
                score.update(usage=actual['statistics']['pruner']['all'],pruner_by_scope=actual['statistics']['pruner'],
                    total_usage=actual['statistics']['total'],small_routes=dict(Counter(e['route'] for e in local)),
                    local_latency_seconds=[e['wall_seconds'] for e in local],
                    scoring_latency_seconds=[e['scoring_seconds'] for e in local],
                    graph_render_seconds=actual['structure_graph_seconds'],
                    case_elapsed_seconds=actual['elapsed_seconds'],case_sha256=sha(folder/'cases'/(iid+'.json')))
                new[arm][iid]=score;assessment=publish()[arm]
                print({'time':now(),'issue':iid,'arm':arm,'top5':score['function_top5'],'paired':assessment},flush=True)
                if assessment['delta']<-.03-1e-12:
                    state.update(stage='stop_loss',stop_arm=arm,stop_issue=iid,stop_reason='Completed same-ID paired function Top5 dropped more than3pp')
                    stop=True;publish();break
            if stop:break
        if not stop:state.update(stage='complete')
    except BaseException as error:
        state.update(stage='failed',error_type=type(error).__name__,error=str(error));raise
    finally:
        try:
            if pool is not None:pool.shutdown(wait=True)
        finally:
            try:
                if service is not None:state['service_shutdown']=shutdown(service)
            finally:
                if log:log.close()
                state['ended_at']=now();publish();verify()
                from .report import run as report
                report()


if __name__=='__main__':run()
