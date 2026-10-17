"""After T1 exits, audit real routing/grounding/cost without changing the canary."""
from collections import Counter
import statistics,time
from code_v6.common import ROOT,OUT,DOCS,read,rows,write,sha,now,test_stats,verify_files

TARGET=OUT/'T1_execution'
def build():
    state=read(TARGET/'status.json');p=read(TARGET/'paired_results.json')
    sample=read(OUT/'T1_canary_preparation/sampling_manifest.json');records={r['instance_id']:r for r in sample['analysis_only_records']}
    data={};details=[]
    for mode,completed in p['new_arms'].items():
        usage=Counter();routes=Counter();event_counts=Counter();latency=[];baseusage=Counter();totals=Counter();basetotal=Counter()
        no_tool=[];no_search=[];fallback=0;budget=0;false_gold=[]
        for iid,case in completed.items():
            actual=read(TARGET/mode/'cases'/f'{iid}.json');events=rows(TARGET/mode/'events'/f'off_{iid}.jsonl')
            assert actual['status']=='complete' and sum(e['event']=='run_start' for e in events)==sum(e['event']=='run_end' for e in events)==1
            usage.update(case['usage']);routes.update(case['small_routes']);event_counts.update(e['event'] for e in events);latency.extend(case['local_latency_seconds'])
            totals.update(actual['statistics']['total'])
            fetched=[e for e in events if e['event']=='tool_result' and e.get('kind')=='source' and e.get('success')]
            accepted=[e for e in events if e['event']=='context_accept']
            if not fetched:no_tool.append(iid)
            if not accepted:no_search.append(iid)
            fallback+=sum(e['event']=='pruner_class_fallback' for e in events)
            budget+=sum(e['event']=='context_budget' and e.get('purpose','').startswith('pruner') for e in events)
            false_gold.extend({'instance_id':iid,**e} for e in case['gold_prune_events'] if e['origin']=='small' and e['decision']=='False')
            old=rows(records[iid]['historical_off_events']);baseusage.update({k:v for k,v in p['off'][iid]['usage'].items() if isinstance(v,(int,float))})
            for e in old:
                if e['event']=='model_call':basetotal.update(e.get('usage',{}))
            details.append({'mode':mode,'instance_id':iid,'Top5':case['function_top5'],'offTop5':p['off'][iid]['function_top5'],
                'source_fetch_events':len(fetched),'source_accept_events':len(accepted),'small_judge_events':sum(e['event']=='small_judge' for e in events),
                'class_fallback_events':sum(e['event']=='pruner_class_fallback' for e in events),'gold_direct_small_false_events':case['gold_direct_small_false'],
                'gold_Qwen_false_events':case['gold_Qwen_false']})
        data[mode]={'completed':len(completed),'pruner_usage':dict(usage),'routes':dict(routes),'event_counts':dict(event_counts),
            'all_Qwen_usage':dict(totals),'matched_off_pruner_usage':dict(baseusage),'matched_off_all_Qwen_usage':dict(basetotal),
            'no_successful_tool_source':no_tool,'no_source_in_search_context':no_search,'class_fallback_events':fallback,
            'gray_or_class_pruner_context_budget_events':budget,'gold_direct_small_false_events':false_gold,
            'local_median_seconds':statistics.median(latency) if latency else None,'local_max_seconds':max(latency) if latency else None}
    shutdown=read(TARGET/'service_shutdown.json') if (TARGET/'service_shutdown.json').exists() else {'closed':not state['service_started']}
    result={'time':now(),'stage':state['stage'],'paired':p['paired'],'arms':data,'issue_details':details,'service_cleanup':shutdown,
            'test_opened':False,'new_model_calls_for_audit':0,'inference_protocol_changed':False}
    write(TARGET/'post_run_behavior_audit.json',result)
    lines=['# T1 金丝雀结果与行为审计','',f'生成：{now()}。状态：**{state["stage"]}**；本次Qwen服务已关闭：**{shutdown["closed"]}**。','',
        '固定20题、B版epoch1/温度2.71922708771811、hybrid0.6/0.9与small0.5均未改变。off复用原v3c；各臂只在已完成同题集合上配对，缺失不计0。第一轮共享显存OOM没有完整新臂成绩，另行归档。','',
        '| 臂 | 完成/计划 | 同题off命中 | 新臂命中 | 差pp | 胜/负 | McNemar双侧p | 3pp非劣效认证 |', '|---|---:|---:|---:|---:|---:|---:|---|']
    for mode,a in p['paired'].items():
        delta='NA' if a['delta'] is None else f'{a["delta"]*100:.2f}'
        lines.append(f'| {mode} | {a["pairs"]}/20 | {a["off_hits"]} | {a["new_hits"]} | {delta} | {a["wins"]}/{a["losses"]} | {a["mcnemar_exact_two_sided_p"]:.4f} | {a["noninferiority_certified"]} |')
    lines += ['', 'McNemar未显著不等于非劣效获证；20题分辨率5pp，通常不能证明3pp边界。全量111/293=37.88%只是背景，不能替代同题off分母。20题与原训练轨迹同源、单seed、同val校准，仅作可行性证据。若触发>3pp止损，后续题保持未完成，不扩大样本补救。','',
       '| 臂 | 小模型函数判决 | 小模型直留/直剪/灰区 | 类回退 | 工具无源码的题数 | 搜索上下文无源码的题数 |', '|---|---:|---:|---:|---:|---:|']
    for mode,x in data.items():
        route=x['routes'];lines.append(f'| {mode} | {sum(route.values())} | {route.get("retain",0)}/{route.get("reject",0)}/{route.get("qwen",0)} | {x["class_fallback_events"]} | {len(x["no_successful_tool_source"])} | {len(x["no_source_in_search_context"])} |')
    lines += ['', '工具成功提取源码按tool_result(kind=source, success=True)计；搜索agent真正收到源码按context_accept计。issue里自带的示例代码不冒充工具读取的仓库源码。两个事件集不同，不能用工具提取成功推断源码已经进入搜索上下文。', '',
       '| 臂 | 同题off pruner Qwen输入/输出token | 新臂pruner Qwen输入/输出token | 本地处理输入token | 新臂Qwen HTTP尝试/成功调用 | 本地判决延迟中位数 |', '|---|---:|---:|---:|---:|---:|']
    for mode,x in data.items():
        u=x['pruner_usage'];b=x['matched_off_pruner_usage'];ms=x['local_median_seconds']
        lines.append(f'| {mode} | {b.get("qwen_prompt_tokens",0)}/{b.get("qwen_completion_tokens",0)} | {u.get("qwen_prompt_tokens",0)}/{u.get("qwen_completion_tokens",0)} | {u.get("small_input_tokens",0)} | {u.get("qwen_http_request_attempts",0)}/{u.get("qwen_successful_calls",0)} | {ms if ms is not None else "NA"}s |')
    lines += ['', '本地reranker没有生成输出token；其输入处理量不能与Qwen生成token当成同价相加。类请求仍交Qwen，全部费用计入。灰区升级次数也不必等于HTTP调用数：可能在发请求之前被上下文预算挡住，或一次逻辑判决触发格式重试。旧日志不记录HTTP尝试数，不能冒充可比较的HTTP账。', '',
       '| 臂 | 同题off全流程Qwen输入/输出token | 新臂全流程Qwen输入/输出token | gold本地直剪事件 | Qwen gold误剪事件 | pruner上下文预算中断 |', '|---|---:|---:|---:|---:|---:|']
    for mode,x in data.items():
        u=x['all_Qwen_usage'];b=x['matched_off_all_Qwen_usage'];goldQ=sum(r['gold_Qwen_false_events'] for r in details if r['mode']==mode)
        lines.append(f'| {mode} | {b.get("prompt_tokens",0)}/{b.get("completion_tokens",0)} | {u.get("qwen_prompt_tokens",0)}/{u.get("qwen_completion_tokens",0)} | {len(x["gold_direct_small_false_events"])} | {goldQ} | {x["gray_or_class_pruner_context_budget_events"]} |')
    lines += ['', 'gold误剪按实际请求事件计，可包含重复函数请求；不是独立gold函数风险率。自适应轨迹不同，各臂实际访问集合也可不同，不能把事件数差当作固定候选集误剪率差。pruner节省token也不必带来全流程节省，需同时看主搜索调用。模型首次加载与warm cache、同卡T3训练及时间顺序影响延迟，不能据此作严格冷启动速度排名。','',
       '观察到的预算边界：`sympy__sympy-14774`曾在灰区升级时因原pruner完整源码prompt达182771 token超过65536而在HTTP前中断。该边界按既有搜索实现保留并计账，不能把它记成一次已完成Qwen判决，也不能写成服务漏传源码。', '',
       '| issue | 臂 | off/新Top5 | 工具提取/搜索接收源码次数 | 小模型判决 | gold本地直剪 |', '|---|---|---:|---:|---:|---:|']
    for r in details:lines.append(f'| {r["instance_id"]} | {r["mode"]} | {int(r["offTop5"])}/{int(r["Top5"])} | {r["source_fetch_events"]}/{r["source_accept_events"]} | {r["small_judge_events"]} | {r["gold_direct_small_false_events"]} |')
    lines += ['', '此处不改变原有早退、源码预算或class策略，目的是验证固定B模型接入。T1成绩不代表v6新底座成绩；T3独立使用冻结v6数据训练。未开test、未重跑Qwen300基线、未改历史结果与定位矩阵。', '',
        '[完整行为审计JSON](../../results/v6_pruner/20261016/T1_execution/post_run_behavior_audit.json) · [原始T1配对结果](../../results/v6_pruner/20261016/T1_execution/paired_results.json) · [服务关闭回执](../../results/v6_pruner/20261016/T1_execution/service_shutdown.json)']
    (DOCS/'实验报告_v6_T1_结果与行为审计.md').write_text('\n'.join(lines)+'\n')
    write(TARGET/'behavior_audit_delivery.json',{'time':now(),'data_sha256':sha(TARGET/'post_run_behavior_audit.json'),'report_sha256':sha(DOCS/'实验报告_v6_T1_结果与行为审计.md'),'code_sha256':sha(ROOT/'code_v6/report_T1_audit.py'),'test_stat_only':test_stats(),'new_model_calls':0})

def main():
    while True:
        state=read(TARGET/'status.json')
        if state['stage'] in ['complete','stop_loss','failed','resource_unavailable']:break
        time.sleep(30)
    build()

if __name__=='__main__':main()
