"""CPU-only independent aggregation and scorer replay after an ended canary."""
from collections import Counter
import math
import statistics
from .common import *
from .finalize_reporting import verify_report_revision


def run():
    verify_report_revision()
    state=read(OUT/'status.json');pairs=read(OUT/'paired_results.json')
    sample=read(OUT/'sample_and_off_reuse.json');ids=sample['selected_issue_ids']
    official=read(OUT/'inference_issues.json');gold=read(ROOT/'ground_truth_300.json')
    from code_v3b.analyze_experiment_300 import predictions,expected,contains_gold
    frame={r['instance_id']:r for r in sample['records']}
    stages={};blobs={};case_rows=[]
    for arm in ['off']+ARMS:
        scores={};usage=Counter();routes=Counter();goldroutes=Counter();cold=[];all_latency=[]
        local_latency=[];function_latency=[];class_latency=[];longest=None;tools=Counter()
        source_absent=[];empty=[];Qwen_gold_false=[];distinct_gold=set();prune_attempts=0
        for iid in ids:
            if arm=='off':
                cp=frame[iid]['historical_off_case'];ep=frame[iid]['historical_off_events'];record=read(cp)
            else:
                cp=OUT/arm/'cases'/(iid+'.json');ep=OUT/arm/'events'/('off_'+iid+'.jsonl')
                if not cp.exists():continue
                record=read(cp)
            events=rows(ep);blobs[str(cp)]=sha(cp);blobs[str(ep)]=sha(ep)
            if arm!='off':
                inputs={(e['step'],e['function_id']):e for e in events if e['event']=='v6_judge_input'}
                judges=[e for e in events if e['event']=='small_judge']
                assert len(inputs)==len(judges)
                for e in judges:
                    inp=inputs[e['step'],e['function_id']]
                    assert digest(inp['model_input'])==inp['input_sha256']==e['input_sha256']
                    assert e['input_tokens']<=8192 and e['input_version']==inp['input_version']
            pp=predictions(record['found_related_locs']);gg=expected(gold[iid],'function')
            assert gg
            hit=bool(set(pp[:5])&gg);scores[iid]=hit
            reference=pairs['off'][iid] if arm=='off' else pairs['new_arms'][arm][iid]
            assert hit==reference['function_top5']
            assert [list(p) for p in pp]==[list(p) for p in reference['predictions']]
            if not pp:empty.append(iid)
            if not any(e['event']=='context_accept' for e in events):source_absent.append(iid)
            numeric=Counter();pruner_numeric=Counter();class_numeric=Counter()
            for e in events:
                kind=e['event']
                if kind in {'tool_error','verdict_parse_error','context_budget','context_reject','context_accept'}:tools[kind]+=1
                if kind=='model_call':
                    for k in ['prompt_tokens','completion_tokens']:
                        numeric['Qwen_'+k]+=e.get('usage',{}).get(k,0)
                        if str(e.get('purpose','')).startswith('pruner'):pruner_numeric[k]+=e.get('usage',{}).get(k,0)
                if kind=='v5_query_usage' and e.get('pruner_scope')=='class' and str(e.get('purpose','')).startswith('pruner'):
                    for k in ['prompt_tokens','completion_tokens']:class_numeric[k]+=e.get('usage',{}).get(k,0)
                    class_numeric['calls']+=1
                if kind=='v5_http_request' and str(e.get('purpose','')).startswith('pruner'):prune_attempts+=1
                if kind=='small_judge_load' and not e.get('cached'):cold.append(e['model_load_seconds'])
                if kind=='small_judge':
                    routes[e['route']]+=1;local_latency.append(e['wall_seconds'])
                    if contains_gold(official[iid],gold[iid],e):
                        goldroutes[e['route']]+=1;distinct_gold.add((iid,e['function_id']))
                    if longest is None or e['original_code_chars']>longest['original_code_chars']:
                        longest={'instance_id':iid,**{k:e[k] for k in ['function_id','original_code_chars','judge_code_chars','input_tokens','neighbor_edges_selected']}}
                if kind=='v5_pruner_latency':
                    all_latency.append(e['elapsed_seconds'])
                    (class_latency if e['pruner_scope']=='class' else function_latency).append(e['elapsed_seconds'])
                if kind=='prune' and e['decision']=='False' and e.get('decision_origin')!='small' and contains_gold(official[iid],gold[iid],e):
                    Qwen_gold_false.append({'instance_id':iid,'step':e['step'],'tool':e['tool'],'arguments':e['arguments']})
            usage.update(numeric)
            if arm!='off':
                expected_usage=record['statistics']['pruner']['all']
                assert pruner_numeric['prompt_tokens']==expected_usage['qwen_prompt_tokens']
                assert pruner_numeric['completion_tokens']==expected_usage['qwen_completion_tokens']
                assert numeric['Qwen_prompt_tokens']==record['statistics']['total']['qwen_prompt_tokens']
                assert numeric['Qwen_completion_tokens']==record['statistics']['total']['qwen_completion_tokens']
                assert class_numeric['prompt_tokens']==record['statistics']['pruner']['class']['qwen_prompt_tokens']
            case_rows.append({'arm':arm,'instance_id':iid,'function_top5':hit,'empty_localization':not pp,
                'function_scorable':True,'predictions':pp,'pruner_Qwen_usage':dict(pruner_numeric),'class_Qwen_usage':dict(class_numeric)})
        def latency(values):
            return {'n':len(values),'median_seconds':statistics.median(values) if values else None,
                'p95_seconds':sorted(values)[math.ceil(.95*len(values))-1] if values else None,
                'sum_seconds':sum(values)}
        stages[arm]={'completed':len(scores),'scores':scores,'Top5_hits':sum(scores.values()),
            'overall_Qwen_usage':dict(usage),'local_routes':dict(routes),'gold_local_routes':dict(goldroutes),
            'distinct_gold_containing_candidate_functions_judged':len(distinct_gold),'model_cold_load_seconds':cold,
            'gold_event_definition':'Requested base source spans containing existing gold AST regions, identical to T1; repeated calls are not independent gold-function trials.',
            'class_Qwen_scope_recorded':arm!='off',
            'local_latency':latency(local_latency),'full_pruner_latency':latency(all_latency),
            'full_function_pruner_latency':latency(function_latency),'full_class_pruner_latency':latency(class_latency),
            'model_or_tool_events':dict(tools),'longest_function':longest,
            'search_received_no_source_issues':source_absent,'empty_localization_issues':empty,
            'Qwen_gold_false_events':Qwen_gold_false,'pruner_HTTP_attempts':prune_attempts if arm!='off' else None}
    for arm in ARMS:
        rr=stages[arm]['scores'];b=stages['off']['scores'];matched=[i for i in ids if i in rr]
        wins=sum(rr[i] and not b[i] for i in matched);losses=sum(b[i] and not rr[i] for i in matched);n=wins+losses
        p=min(1.,2*sum(math.comb(n,j) for j in range(min(wins,losses)+1))/(2**n)) if n else 1.
        assert wins==pairs['paired'][arm]['wins'] and losses==pairs['paired'][arm]['losses']
        assert p==pairs['paired'][arm]['mcnemar_exact_two_sided_p']
        stages[arm]['independent_mcnemar']={'wins':wins,'losses':losses,'p':p}
    status(OUT/'independent_final_audit.json',{'time':now(),'stage':state['stage'],'all_scores_and_token_accounts_replayed':True,
        'stages':stages,'per_case':case_rows,'result_and_event_sha256':blobs,
        'as_run_freeze_sha256':sha(OUT/'freeze.json'),'report_only_revision_sha256':sha(OUT/'report_only_revision.json'),
        'test_stat_only':test_stats(),'test_opened':False,'historical_predictions_and_matrix_unchanged':True})
    lines=['# v6 金丝雀v2：逐题预测与行为核验','',f'更新：{now()}。状态：{state["stage"]}。',
        '题目沿用T1冻结20题；off复用历史结果，两新臂为SweRank epoch1默认/安全阈值。以下预测次序沿用原结果，不按gold重排。',
        'gold误剪为请求源码包含现有gold AST区域却被拒绝进入上下文，遵循T1同一判定；重复请求逐条保留，未完成标NA。','']
    per={(r['arm'],r['instance_id']):r for r in case_rows}
    gold_events=read(OUT/'post_run_audit.json')['gold_direct_reject_events']
    for iid in ids:
        lines += [f'## {iid}','', '| 臂 | Top5命中 | 本地留/剪/灰 | 工具源码/搜索接收 | Qwen pruner输入/输出token | gold本地直剪 |',
            '|---|---:|---:|---:|---:|---:|']
        for arm in ['off']+ARMS:
            item=per.get((arm,iid))
            if item is None:lines.append(f'| {arm} | NA（未完成） | NA | NA | NA | NA |');continue
            ep=Path(frame[iid]['historical_off_events']) if arm=='off' else OUT/arm/'events'/('off_'+iid+'.jsonl')
            ev=rows(ep);rc=Counter(e['route'] for e in ev if e['event']=='small_judge')
            fetched=sum(e['event']=='tool_result' and e.get('kind')=='source' and e.get('success') is True for e in ev)
            accepted=sum(e['event']=='context_accept' for e in ev)
            u=item['pruner_Qwen_usage'];local='—' if arm=='off' else f"{rc['retain']}/{rc['reject']}/{rc['qwen']}"
            rejects='—' if arm=='off' else str(pairs['new_arms'][arm][iid]['gold_direct_small_false'])
            lines.append(f"| {arm} | {int(item['function_top5'])} | {local} | {fetched}/{accepted} | {u.get('prompt_tokens',0)}/{u.get('completion_tokens',0)} | {rejects} |")
        lines += ['', '**原始前5定位**','']
        for arm in ['off']+ARMS:
            item=per.get((arm,iid))
            values='；'.join(f'`{f}::{kind}:{name}`' for f,kind,name in item['predictions'][:5]) if item else 'NA（未完成）'
            lines.append(f'- {arm}：{values or "空定位（已完成）"}')
        events=[e for e in gold_events if e['instance_id']==iid]
        lines += ['', '**本地gold直剪事件**：'+('无（仅本次已访问轨迹）。' if not events else '')]
        for e in events:lines.append(f"- {e['arm']}，step={e['step']}，`{e['function_id']}`，p={e['p_yes']!r}，终选Top5={e['final_function_top5']}。")
        lines.append('')
    lines += ['独立核验逐项重算了逐题分数、配对McNemar和Qwen成功usage，并核对每条实际v6输入hash、版本与token上限。',
        f'证据目录：`{OUT}`。未读取或哈希封存test，未改历史矩阵。','']
    (DOCS/'实验报告_v6_金丝雀v2_逐题行为分析.md').write_text('\n'.join(lines))
    print({a:(s['completed'],s['Top5_hits'],s['gold_local_routes']) for a,s in stages.items()},flush=True)


if __name__=='__main__':run()
