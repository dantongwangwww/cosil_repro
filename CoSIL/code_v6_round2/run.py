"""Persistent second-round race, registered promotion, conditional seed checks."""
import fcntl
import os
import subprocess
import time
from code_v6_round2.common import *
from code_v6_round2.diagnostics import safety_diagnostic, point_pass
from code_v6_round2.report import run as report
from code_v6_round2.train import SPECS, gpu_free


def launch(key,seed=0):
    folder=(RACE if seed==0 else CONTROL/f'stability_seed{seed}')/key;folder.mkdir(parents=True,exist_ok=True)
    log=(folder/'runner.log').open('x');env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=str(SPECS[key]['gpu'])
    child=subprocess.Popen([str(ROOT/'.venv-v5/bin/python'),'-u','-m','code_v6_round2.train','--key',key,'--seed',str(seed)],
        cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    write(folder/'process_receipt.json',{'time':now(),'pid':child.pid,'uid':os.getuid(),'physical_gpu':SPECS[key]['gpu'],'seed':seed,'own_process':True})
    return child,log,folder


def finish(child,log,folder):
    code=child.wait();log.close();write(folder/'process_exit.json',{'time':now(),'exit_code':code})
    if not (folder/'training_summary.json').exists():
        status(folder/'status.json',{'time':now(),'stage':'failed','exit_code':code,'test_opened':False})
        return None
    summary=read(folder/'training_summary.json');selected=summary['selected']
    diagnostic=safety_diagnostic(rows(folder/f'val_epoch_{selected["epoch"]}.jsonl'),selected['assessment']['calibration']['temperature'])
    write(folder/'safety_threshold.json',diagnostic)
    return summary


def candidate_package(key,identity,summary):
    selected=summary['selected'];folder=RACE/key;checkpoint=folder/f'epoch_{selected["epoch"]}'
    safety=read(folder/'safety_threshold.json')
    sample=read(ROUND1_OUT/'T1_canary_preparation/sampling_manifest.json')
    splits=read(DATA/'split_manifest.json')['splits'];assert not set(sample['selected_issue_ids'])&set(splits['test'])
    payload={'time':now(),'identity':identity,'model_key':key,'adapter_dir':str(checkpoint),
        'adapter_sha256':sha(checkpoint/'adapter_model.safetensors'),'model_dir':SPECS[key]['model_dir'],
        'temperature':selected['assessment']['calibration']['temperature'],'input_version':'v6_issue8000_fn8192_neighbors16_8192tokens_v1',
        'default_arm':{'low':.6,'high':.9},'safety_arm':{'low':safety['low_star'],'high':.9,'feasible':safety['safe_threshold_feasible']},
        'same_val_low_star_optimism':True,'formal_CI_qualified':selected['qualified'],
        'off20_manifest':str(ROUND1_OUT/'T1_canary_preparation/sampling_manifest.json'),
        'off20_manifest_sha256':sha(ROUND1_OUT/'T1_canary_preparation/sampling_manifest.json'),
        'off_results_path':str(ROUND1_OUT/'T1_execution/paired_results.json'),
        'off_results_sha256':sha(ROUND1_OUT/'T1_execution/paired_results.json'),
        'sample_ids':sample['selected_issue_ids'],'sample_size':20,'no_baseline_rerun':True,
        'pipeline_started':False,'test_opened':False,
        'next_requirements':['v6 long-input/neighbor judge integration; do not use old v5 2000/1500 codec',
            'compatible main Qwen service under explicit no-vLLM-change constraint',
            'paired default/safety canary and NI assessment; 20 cases cannot generally certify3ppNI'],
        'service_lifecycle_authorized':False}
    write(CONTROL/'canary_candidate_parameters.json',payload)
    return payload


def run():
    lock=(CONTROL/'scheduler.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    preserve_history();protocol=read(RACE/'protocol.json');verify_files(protocol['code_sha256'])
    verify_files(read(DATA/'freeze_manifest.json')['artifacts_sha256'])
    write(CONTROL/'scheduler_start.json',{'time':now(),'pid':os.getpid(),'uid':os.getuid(),
        'protocol_sha256':sha(RACE/'protocol.json'),'test_stat_only':test_stats(),'pre_change_commit':PRE_CHANGE_COMMIT})
    processes={};done=set();summaries={}
    status(CONTROL/'status.json',{'time':now(),'stage':'training_seed0','test_opened':False})
    while len(done)<len(ORDER):
        for key in ORDER:
            if key in done:continue
            if key not in processes:
                if key=='swerank7B':
                    priority_ready=True
                    for other in ['reranker4B','anchor06B']:
                        p=RACE/other/'status.json'
                        if not p.exists() or read(p)['stage'] in ['waiting_for_headroom','loading_model','worst_length_backward_preflight','queued']:
                            priority_ready=False
                    if not priority_ready:continue
                snapshot=gpu_free(SPECS[key]['gpu'])
                if snapshot['free_mib']<SPECS[key]['minimum_free_mib']:
                    status(RACE/key/'status.json',{'time':now(),'stage':'queued','reason':'waiting_for_natural_headroom',**snapshot,'test_opened':False});continue
                processes[key]=launch(key)
            elif processes[key][0].poll() is not None:
                summary=finish(*processes[key]);done.add(key)
                if summary:summaries[key]=summary
        report()
        if len(done)<len(ORDER):time.sleep(30)
    qualified={k:s for k,s in summaries.items() if s['selected']['qualified']}
    point={k:s for k,s in summaries.items() if point_pass(s)}
    priority_complete=all(k in summaries for k in ['reranker4B','anchor06B'])
    candidate=None
    if not priority_complete:
        branch='incomplete_stop';why='优先对照臂未全部完成，不宣告完整赛马晋级。'
    elif qualified:
        candidate=min(qualified,key=lambda k:rank_selected(qualified[k]));branch='CI_qualified_pending_stability';why='双CI门通过，按原顺序选出候选，随后仅跑相同配方seed1/2。'
    elif point:
        candidate=min(point,key=lambda k:rank_selected(point[k]));branch='feasibility_canary_ready';why='只有点估计双达标，按新指令以可行性身份准备双阈值金丝雀；不冒称CI认证。'
    else:
        branch='point_estimates_failed_stop';why='无选中checkpoint满足点估计双门，按指令停赛报审，不进入管线。'
    decision={'time':now(),'branch':branch,'candidate':candidate,'explanation':why,
              'CI_qualified':list(qualified),'point_qualified':list(point),'test_opened':False,'pipeline_started':False}
    write(CONTROL/'promotion_decision_seed0.json',decision)
    if branch=='CI_qualified_pending_stability':
        replicas={}
        for seed in [1,2]:
            status(CONTROL/'status.json',{'time':now(),'stage':'CI_candidate_seed_stability','model':candidate,'seed':seed,'test_opened':False})
            child,log,folder=launch(candidate,seed)
            while child.poll() is None:report();time.sleep(30)
            replicas[str(seed)]=finish(child,log,folder)
        stable=all(s is not None and s['selected']['qualified'] for s in replicas.values())
        decision.update(time=now(),stability_seeds_completed={k:s is not None for k,s in replicas.items()},
            stability_seeds_CI_qualified={k:bool(s and s['selected']['qualified']) for k,s in replicas.items()},
            branch='CI_stable_canary_ready' if stable else 'seed_stability_failed_stop',
            explanation='seed1/2均通过冻结CI门，候选可准备金丝雀。' if stable else 'seed重复未全部通过同一风险门，稳定性不足，停止并报告。')
    if decision['branch'] in ['feasibility_canary_ready','CI_stable_canary_ready']:
        candidate_package(candidate,'feasibility' if decision['branch'].startswith('feasibility') else 'CI_stable',summaries[candidate])
        decision.update(service_or_integration_pending=True,
            explanation=decision['explanation']+' 参数已落盘；当前指令禁止变更vLLM，T1主服务已关闭，且须接入v6长输入/邻居后才能真实跑双臂。')
    write(CONTROL/'promotion_decision.json',decision)
    status(CONTROL/'status.json',{'time':now(),'stage':decision['branch'],'completed_models':list(summaries),
        'candidate':candidate,'test_opened':False,'pipeline_started':False,'T4_started':False})
    preserve_history();verify_files(protocol['code_sha256']);verify_files(read(DATA/'freeze_manifest.json')['artifacts_sha256'])
    assert test_stats()==protocol['test_stat_only'];report()
    write(CONTROL/'final_delivery_receipt.json',{'time':now(),'protocol_sha256':sha(RACE/'protocol.json'),
        'data_freeze_sha256':sha(DATA/'freeze_manifest.json'),'promotion_sha256':sha(CONTROL/'promotion_decision.json'),
        'reports_sha256':{str(DOCS/n):sha(DOCS/n) for n in ['实验报告_v6_T3第二轮_1比1权重对照.md','实验报告_v6_T3第二轮_逐题验证分析.md','实验报告_v6_T3第二轮_逐函数验证对照.csv']},
        'historical_files_unchanged':True,'test_stat_only':test_stats(),'test_contents_opened':False,
        'no_vLLM_CSRSE_or_other_process_changes':True,'T4_started':False})


if __name__=='__main__':
    try:run()
    except Exception as exc:
        status(CONTROL/'scheduler_failure.json',{'time':now(),'type':type(exc).__name__,'message':str(exc)[:1000],
            'test_opened':False,'training_workers_signaled':False})
        status(CONTROL/'status.json',{'time':now(),'stage':'scheduler_failed_inspect_receipt','test_opened':False})
        raise
