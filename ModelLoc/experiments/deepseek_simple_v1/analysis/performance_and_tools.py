"""Read-only inference artifacts -> CPU timing, token and actual-tool-use audit.

No training, inference, test execution or historical-table mutation occurs here.
"""
from pathlib import Path
import collections,csv,json,math,re,statistics,sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),'/mnt/skygruop0/home/wdt/cosil_repro/CoSIL']
from src.common import RUN,COSIL,read,write,norm,digest
from src.metrics import normalize_functions,scores
from src.code_index import decode
from code_v3b.tool_dispatch import parse_tool_call,DispatchError,SIGNATURES,ToolCall
from audit_semantics import inspect_dsml

METHODS=['D-SIMPLE','D-COSIL','Q-COSIL','Q-PRUNER']

def load_rows(path):return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
def average(v):return sum(v)/len(v) if v else None
def stats(values):
    v=[float(x) for x in values if x is not None]
    if not v:return dict(n=0,mean=None,median=None,p25=None,p75=None,p95=None)
    return dict(n=len(v),mean=average(v),median=statistics.median(v),
        p25=float(np.quantile(v,.25)),p75=float(np.quantile(v,.75)),p95=float(np.quantile(v,.95)))
def fmt(v,d=2):return 'NA' if v is None else f'{v:.{d}f}'
def cell(s,n=180):return str(s).replace('`','｀').replace('|','\\|').replace('\n',' ↵ ')[:n]
def csv_out(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})

def stage_group(stage):
    if stage.startswith('file_draw_'):return 'file_selection_5_draws'
    if stage=='file_stage':return 'file_selection_and_import_reflection'
    if stage in ('node_selection','initial_selection'):return 'search_navigation'
    if stage.startswith('pruner'):return 'relevance_judge_main_model'
    if stage in ('function_localization','final_summary'):return 'final_function_ranking'
    return stage

def semantic_target(call,index,candidates):
    args=call.arguments
    if call.name=='exit':return True,False,'exit'
    if call.name=='get_functions_of_class':
        cls,path=args
        paths=[path] if path is not None else candidates
        found=[(p,d) for p in paths for d in index.get(p,{}).get('definitions',[]) if d['kind']=='class' and d['qualified_name']==cls]
        return len(found)==1, bool(path is None), 'class_catalog'
    path=args[0]
    if path not in index:return False,False,'path_not_literal_base_python_path'
    if call.name=='get_code_of_class':kind='class';qn=args[1]
    elif call.name=='get_code_of_class_function':kind='function';qn=args[1]+'.'+args[2]
    elif call.name=='get_code_of_file_function':kind='function';qn=args[1]
    else:return None,False,'unknown'
    found=[d for d in index[path]['definitions'] if d['kind']==kind and d['qualified_name']==qn]
    if not found:return False,False,'definition_not_in_supplied_file_or_class'
    if call.name=='get_code_of_file_function' and '.' in qn:
        return False,False,'class_or_nested_function_sent_to_file_function_tool'
    if len(found)>1:return True,False,'same_qualified_name_multiple_source_spans'
    return True,False,'exact_base_definition'

def audit_case(folder,rec,method):
    result=read(folder/'result.json') if (folder/'result.json').exists() else None
    events=load_rows(folder/'events.jsonl');job=read(rec['job']);index=read(job['code_index'])
    candidates=next((e['found_files'] for e in events if e['event']=='file_stage_end'),[])
    context=read(folder/'context.json') if (folder/'context.json').exists() else {'blocks':[]}
    retrieved=context.get('retrieved_blocks',context.get('blocks',[]));blocks=context.get('blocks',[])
    selections=[];receipts=[];errors=[];native=0;by_stage=collections.defaultdict(list);observed_inputs=[]
    for callfolder in sorted(folder.glob('calls/*')):
        if not (callfolder/'request.json').exists():continue
        request=read(callfolder/'request.json');stage=callfolder.name.split('_',1)[1]
        if list(callfolder.glob('attempt_*_receipt.json')):
            observed_inputs.append((int(callfolder.name.split('_',1)[0]),stage,'\n'.join(m.get('content','') for m in request['request']['messages'])))
        for p in sorted(callfolder.glob('attempt_*_receipt.json')):
            r=read(p);receipts.append(r);by_stage[stage_group(stage)].append(r)
        errors.extend(read(p) for p in callfolder.glob('attempt_*_error.json'))
        for p in callfolder.glob('attempt_*_response.json'):
            raw=read(p);native+=sum(len(c.get('message',{}).get('tool_calls',[]) or []) for c in raw.get('choices',[]))
        if stage=='node_selection' and (callfolder/'result.json').exists():
            response=read(callfolder/'result.json');raw=response['content']
            selections.append((callfolder,raw))
    requests=[];executions=[e for e in events if e['event']=='tool_call']
    io_events=[e for e in events if e['event']=='tool_io_audit']
    success_by_step={e['step']:e for e in events if e['event']=='tool_result'}
    errors_by_step={e['step']:e for e in events if e['event']=='tool_error'}
    accepted={e['step'] for e in events if e['event']=='context_accept'}
    judged=set();latest=None
    for e in events:
        if e['event']=='tool_call':latest=e['step']
        if e['event']=='small_judge':judged.add(e['step'])
        if e['event']=='model_call' and e.get('purpose','').startswith('pruner') and latest is not None:judged.add(latest)
    execution_cursor=0;seen_inputs=set();source_before=0;accepted_before=0;exit_before_read=0;exit_without_agent=0
    for number,(callfolder,raw) in enumerate(selections):
        row={'method':method,'instance_id':rec['instance_id'],'node_request_number':number+1,
             'raw_model_output':raw,'raw_artifact_path':str(callfolder),'native_API_tool_call':False,
             'strict_one_call_text':len(re.findall(r'\b(?:get_\w+|exit)\s*\(',raw))==1}
        row.update(inspect_dsml(raw))
        try:
            call=parse_tool_call(raw);row.update(parsed=True,canonical_tool=call.name,original_tool=call.original_name,
                arguments=list(call.arguments),alias_normalized=call.name!=call.original_name)
        except DispatchError as e:
            row.update(parsed=False,executed=False,error_type='dispatch_parse',error_message=str(e))
            if row.get('dsml_structure_and_signature_valid'):
                hypothetical=ToolCall(row['dsml_tool'],tuple(row['dsml_arguments']),row['dsml_original_tool'])
                v,i,c=semantic_target(hypothetical,index,candidates)
                row.update(dsml_offline_base_target_valid=v,dsml_offline_argument_category=c)
            requests.append(row);continue
        if call.name=='exit':
            row.update(executed=False,exit=True,source_reads_before_exit=source_before,accepted_sources_before_exit=accepted_before)
            exit_before_read+=source_before==0;exit_without_agent+=accepted_before==0;requests.append(row);continue
        valid,inferred,category=semantic_target(call,index,candidates)
        row.update(base_target_and_scope_valid=valid,file_argument_inferred_by_framework=inferred,argument_category=category)
        key=(call.name,call.arguments);row['repeated_same_input']=key in seen_inputs;seen_inputs.add(key)
        if execution_cursor>=len(executions):row.update(executed=False,error_type='no_execution_record');requests.append(row);continue
        e=executions[execution_cursor];execution_cursor+=1;step=e['step']
        # Evidence binding must match actual dispatch, not just temporal order.
        bound=e['tool']==call.name and tuple(e['arguments'])==call.arguments
        actual=success_by_step.get(step);error=errors_by_step.get(step)
        io=io_events[execution_cursor-1] if execution_cursor<=len(io_events) else None
        source=bool(actual and actual.get('success') and actual.get('kind')=='source')
        row.update(step=step,executed=True,dispatch_binding_matches=bound,execution_success=bool(actual and actual.get('success')),
            returned_kind=actual.get('kind') if actual else None,source_returned=source,
            judge_received_source=source and step in judged,context_insertion_record=source and step in accepted,search_agent_received_source=False,
            tool_error=error.get('error') if error else None)
        if io:
            row.update(returned_chars=io.get('returned_chars'),returned_sha256=io.get('returned_sha256'),
                returned_head=io.get('returned_head',io.get('returned_error_text')),
                output_matches_base_source=io.get('output_matches_base_source_splitlines'),
                metadata_schema_valid=io.get('metadata_json_schema_valid'),tool_elapsed_s=io.get('wall_seconds'),
                full_output_artifact=io.get('full_output_artifact'))
        elif source:
            matching=[b for b in retrieved if b.get('tool')==call.name and tuple(b.get('arguments',[]))==call.arguments]
            if matching:
                b=matching[0];text=''.join(decode((Path(job['snapshot'])/b['path']).read_bytes()).splitlines(keepends=True)[b['start_line']-1:b['end_line']])
                row.update(returned_chars=len(b['text']),returned_sha256=digest(b['text']),returned_head=b['text'][:300],
                    output_matches_base_source=b['text']==text,full_output_artifact=str(folder/'context.json'))
        if source:
            matches=[b for b in retrieved if b.get('tool')==call.name and tuple(b.get('arguments',[]))==call.arguments]
            exact_source=matches[-1]['text'] if matches else None
            seq=int(callfolder.name.split('_',1)[0])
            # Successful API receipts prove a later search request carried the exact source.
            row['search_agent_payload_contains_exact_source']=bool(exact_source and any(n>seq and stage in ('node_selection','final_summary') and exact_source in body for n,stage,body in observed_inputs))
            row['search_agent_received_source']=bool(step in accepted and row['search_agent_payload_contains_exact_source'])
            row['judge_api_payload_contains_exact_source']=bool(exact_source and any(n>seq and stage.startswith('pruner') and exact_source in body for n,stage,body in observed_inputs))
            vi=next((ev for ev in events if ev['event']=='v6_judge_input' and ev.get('step')==step),None)
            row['small_judge_saved_input_hash_valid']=bool(vi and digest(vi['model_input'])==vi['input_sha256']) if vi else None
            row['judge_received_source']=bool(row['judge_api_payload_contains_exact_source'] or row['small_judge_saved_input_hash_valid'])
        source_before+=source;accepted_before+=row.get('search_agent_received_source',False);requests.append(row)
    usage=[r['usage'] for r in receipts if r.get('usage')]
    small=[e for e in events if e['event']=='small_judge'];setup=[e for e in events if e['event']=='local_judge_setup']
    judge_input=sum(e.get('input_tokens') or 0 for e in small)
    input_tokens=sum(u.get('prompt_tokens',0) for u in usage);output_tokens=sum(u.get('completion_tokens',0) for u in usage)
    row={'method':method,'instance_id':rec['instance_id'],'repo':rec['repo'],
        'status':result['status'] if result else 'NOT_RUN','processing_seconds':result.get('elapsed_seconds') if result else None,
        'worker_queue_seconds':result.get('worker_queue_seconds') if result else None,
        'resumed_or_reused':bool(result and (result.get('resumed_exact_receipts') or result.get('run_id')!=RUN.name)),
        'search_model_input_tokens':input_tokens,'search_model_output_tokens':output_tokens,
        'judge_input_tokens':judge_input,'judge_generated_tokens':sum(e.get('generated_output_tokens') or 0 for e in small),
        'all_model_input_tokens':input_tokens+judge_input,'all_model_total_tokens':input_tokens+output_tokens+judge_input,
        'api_calls_successful':len(receipts),'transport_failed_attempts':len(errors),
        'successful_request_seconds':sum(r.get('attempt_elapsed_seconds',r.get('elapsed_seconds',0)) for r in receipts),
        'failed_attempt_seconds':sum(r.get('attempt_elapsed_seconds',0) for r in errors),
        'cold_client_calls':sum(r.get('cold_http_client') is True for r in receipts),
        'judge_model_load_seconds':sum(e['judge_load_seconds'] for e in setup) if setup else None,
        'judge_graph_setup_seconds':sum(e['base_graph_and_render_setup_seconds'] for e in setup) if setup else None,
        'judge_forward_sync_wall_seconds':sum(e.get('forward_seconds') or 0 for e in small),
        'tool_execution_seconds':sum(e['wall_seconds'] for e in io_events) if io_events and all('wall_seconds' in e for e in io_events) else None,
        'node_action_responses':len(selections),'parsed_responses':sum(bool(x.get('parsed')) for x in requests),
        'strict_one_call_responses':sum(x['strict_one_call_text'] and x.get('parsed',False) for x in requests),
        'tool_executions':len(executions),'successful_executions':sum(bool(x.get('execution_success')) for x in requests),
        'source_successes':sum(bool(x.get('source_returned')) for x in requests),
        'judge_received_source_count':sum(bool(x.get('judge_received_source')) for x in requests),
        'agent_received_source_count':sum(bool(x.get('search_agent_received_source')) for x in requests),
        'tool_errors':len(errors_by_step),'parse_errors':sum(not x.get('parsed',False) for x in requests),
        'repeated_inputs':sum(bool(x.get('repeated_same_input')) for x in requests),
        'exit_requests':sum(bool(x.get('exit')) for x in requests),'exit_before_any_source':exit_before_read,
        'exit_without_agent_source':exit_without_agent,'native_API_tool_calls':native,
        'agent_no_source_but_prediction':bool(result and result.get('predicted_functions')) and not any(x.get('search_agent_received_source') for x in requests),
        'tool_no_source_but_prediction':bool(result and result.get('predicted_functions')) and not any(x.get('source_returned') for x in requests),
        'context_inserted_source_count':sum(x.get('context_insertion_record',False) for x in requests),
        'any_source_returned':any(x.get('source_returned') for x in requests),
        'any_agent_received_source':any(x.get('search_agent_received_source') for x in requests),
        'dsml_responses':sum(x.get('dsml_detected',False) for x in requests),
        'dsml_offline_wellformed_actions':sum(x.get('dsml_structure_and_signature_valid',False) for x in requests),
        'dsml_offline_valid_target_actions':sum(x.get('dsml_offline_base_target_valid',False) for x in requests),
        'base_verified_returns':sum(x.get('output_matches_base_source') is True for x in requests),
        'base_mismatched_returns':sum(x.get('output_matches_base_source') is False for x in requests),
        'raw_artifact_path':str(folder)}
    stage_rows=[]
    for stage,values in by_stage.items():
        stage_rows.append({'method':method,'instance_id':rec['instance_id'],'stage':stage,
            'calls':len(values),'request_seconds':sum(r.get('attempt_elapsed_seconds',r.get('elapsed_seconds',0)) for r in values),
            'input_tokens':sum(r['usage']['prompt_tokens'] for r in values),
            'output_tokens':sum(r['usage']['completion_tokens'] for r in values)})
    return row,requests,stage_rows

def main(cohort='lite_pilot'):
    from code_v6.common import test_stats
    before=test_stats();manifest=read(ROOT/'manifests'/f'{cohort}.json');out=ROOT/'reports'
    rows=[];calls=[];stages=[]
    for method in METHODS:
        for rec in manifest['records']:
            r,c,s=audit_case(RUN/cohort/method/rec['instance_id'],rec,method);rows.append(r);calls.extend(c);stages.extend(s)
    summaries=[]
    for method in METHODS:
        subset=[r for r in rows if r['method']==method and r['status']!='NOT_RUN']
        for population,items in [('all_executed',subset),('completed',[r for r in subset if r['status']=='complete'])]:
            item={'method':method,'population':population,'n':len(items)}
            for field in ['processing_seconds','worker_queue_seconds','all_model_input_tokens','search_model_output_tokens','all_model_total_tokens',
                'api_calls_successful','judge_graph_setup_seconds','judge_model_load_seconds','tool_execution_seconds']:
                for k,v in stats([r[field] for r in items]).items():item[field+'_'+k]=v
            summaries.append(item)
    stage_summaries=[]
    for (method,stage) in sorted(set((s['method'],s['stage']) for s in stages)):
        subset=[s for s in stages if s['method']==method and s['stage']==stage]
        item={'method':method,'stage':stage,'reached_issue_n':len(subset)}
        for field in ['calls','request_seconds','input_tokens','output_tokens']:
            for k,v in stats([s[field] for s in subset]).items():item[field+'_'+k]=v
        stage_summaries.append(item)
    csv_out(out/f'{cohort}_per_issue_runtime_tokens.csv',rows);csv_out(out/f'{cohort}_runtime_summary.csv',summaries)
    csv_out(out/f'{cohort}_tool_io_per_call.csv',calls);csv_out(out/f'{cohort}_stage_runtime_tokens.csv',stage_summaries)
    write(out/f'{cohort}_runtime_tools.json',{'per_issue':rows,'tool_calls':calls,'runtime_summary':summaries,'stage_summary':stage_summaries},replace=True)
    text=['# 单题时长、token与真实工具使用审计','',f'集合：{cohort}；run：{RUN.name}。按instance_id关联，每题每臂仅一份结果。','',
        '“通常一题多久”以**中位数与P25–P75区间**为主，均值、P95揭示长尾。处理墙钟从worker开始处理到落盘，包含本题CPU/模型/网络；worker排队另列。客户端无法再把一次请求分成网络、服务端排队和纯模型计算，不伪造这三项。',
        '', 'token为实际usage累计，重复发送上下文会重复计入。Q-PRUNER另加专职裁判实际前向输入token，裁判只评分、不生成文本，因此其生成token为0。接口缺失的reasoning/cache字段不补0。',
        '', '## 1. 单题典型耗时与token','',
        '| 方法 | 群体 | N | 均值秒 | 中位秒 | 通常P25–P75秒 | P95秒 | 平均累计输入 | 中位累计输入 | 平均输出 | 中位输出 | 平均总token | 中位总token | 总token P25–P75 |',
        '|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for s in summaries:
        p='processing_seconds_';it='all_model_input_tokens_';ot='search_model_output_tokens_';tt='all_model_total_tokens_'
        text.append(f'| {s["method"]} | {s["population"]} | {s["n"]} | {fmt(s[p+"mean"])} | {fmt(s[p+"median"])} | {fmt(s[p+"p25"])}–{fmt(s[p+"p75"])} | {fmt(s[p+"p95"])} | {fmt(s[it+"mean"],0)} | {fmt(s[it+"median"],0)} | {fmt(s[ot+"mean"],0)} | {fmt(s[ot+"median"],0)} | {fmt(s[tt+"mean"],0)} | {fmt(s[tt+"median"],0)} | {fmt(s[tt+"p25"],0)}–{fmt(s[tt+"p75"],0)} |')
    text+=['','all_executed包含真实失败和预算停止；completed为成功完成子组。两者并报以防删除慢题/失败题造成偏差。P0存在前序请求重放与结果复用，不用其续跑墙钟估计稳定单题耗时；正式典型时长以未重放的P1为准。',
        '', '## 2. 分阶段请求账','',
        '| 方法 | 阶段 | 到达题数 | 平均请求数/到达题 | 请求累计均值秒 | 请求累计中位秒 | 平均输入token | 平均输出token |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for s in stage_summaries:text.append(f'| {s["method"]} | {s["stage"]} | {s["reached_issue_n"]} | {fmt(s["calls_mean"])} | {fmt(s["request_seconds_mean"])} | {fmt(s["request_seconds_median"])} | {fmt(s["input_tokens_mean"],0)} | {fmt(s["output_tokens_mean"],0)} |')
    text+=['','分阶段均值按实际到达该阶段的题计算；未到达不伪填为成功的0秒。D-SIMPLE的五次文件选择合为一阶段，CoSIL文件选择与导入关系反思合并。裁判前向、CPU图构建和工具执行详见逐题CSV，非同一计时口径不能直接相减称纯GPU秒。',
        '', '## 3. 模型到底有没有使用工具','',
        '**这里的CoSIL采用文本DSL调用，经白名单AST解析后由框架执行；不是API原生tool_calls。** 下面只把有真实执行事件的调用计为执行，exit单列。模型说“我读了”而无事件不算。D-SIMPLE是固定文件装载/一次grep流程，不能将它的文件数当成自由工具调用数。',
        '', '| 方法 | 动作响应 | 解析通过(含exit) | 严格单调用文本 | 实际执行 | 执行成功 | 真正返回源码 | 裁判收到源码 | 搜索agent收到源码 | 工具错误 | 重复输入 | exit/读源码前exit | 无agent源码仍定位题 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    totals={}
    for method in METHODS[1:]:
        subset=[r for r in rows if r['method']==method];t=collections.Counter()
        fields=['node_action_responses','parsed_responses','strict_one_call_responses','tool_executions','successful_executions',
            'source_successes','judge_received_source_count','agent_received_source_count','tool_errors','repeated_inputs','exit_requests',
            'exit_before_any_source','agent_no_source_but_prediction','base_verified_returns','base_mismatched_returns','native_API_tool_calls']+['parse_errors','tool_no_source_but_prediction','context_inserted_source_count','dsml_responses','dsml_offline_wellformed_actions','dsml_offline_valid_target_actions']
        for f in fields:t[f]=sum(r[f] for r in subset)
        totals[method]=dict(t)
        vals=[str(t[f]) for f in fields[:10]]+[str(t['exit_requests'])+'/'+str(t['exit_before_any_source']),str(t['agent_no_source_but_prediction'])]
        text.append('| '+method+' | '+' | '.join(vals)+' |')
    text+=['','“解析通过”仅证明调用语法可绑定；参数还必须对应真实文件/类/函数。执行成功也可能只是节点目录，只有source才算源码。pruner拒绝会导致“已取回、裁判已看见、搜索agent没看见”，三者分别统计。文件阶段由框架隐式读import行，不冒充模型主动函数源码调用。',
        '', '## 4. 输入/输出是否符合工具约定','',
        '| 方法 | 非exit提议(含解析失败) | base目标与工具作用域有效 | 提议→真实成功 | 已执行→成功 | 源码返回与base逐行一致 | 源码返回不一致 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for method in METHODS[1:]:
        selected=[c for c in calls if c['method']==method and not c.get('exit')]
        executions=[c for c in selected if c.get('executed')];valid=sum(c.get('base_target_and_scope_valid') is True for c in selected)
        rate=sum(c.get('execution_success',False) for c in executions)/len(executions) if executions else None
        text.append(f'| {method} | {len(selected)} | {valid} | {fmt(100*sum(c.get("execution_success",False) for c in selected)/len(selected)) if selected else "NA"}% | {fmt(rate*100) if rate is not None else "NA"}% | {totals[method]["base_verified_returns"]} | {totals[method]["base_mismatched_returns"]} |')
    text+=['','| 方法 | 已有结果题数 | 至少一次源码工具成功题 | 搜索agent真实收到源码题 | 工具无源码仍定位题 | agent无源码仍定位题 | DSML动作/结构完整/目标有效 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for method in METHODS[1:]:
        rs=[r for r in rows if r['method']==method and r['status']!='NOT_RUN']
        text.append(f'| {method} | {len(rs)} | {sum(r["any_source_returned"] for r in rs)} | {sum(r["any_agent_received_source"] for r in rs)} | {sum(r["tool_no_source_but_prediction"] for r in rs)} | {sum(r["agent_no_source_but_prediction"] for r in rs)} | {totals[method]["dsml_responses"]}/{totals[method]["dsml_offline_wellformed_actions"]}/{totals[method]["dsml_offline_valid_target_actions"]} |')
    text+=['','搜索agent收到源码需同时有context_accept事件，并在之后有成功API回执的搜索/总结请求中找到完整原文。context插入、实际送达分别落盘。小裁判需有真实评分事件及已保存的v6输入哈希核验；不把框架取到源码直接等同于agent读到。',
        '', 'DSML仅做离线语法/参数诊断，绝不执行、纠正或重跑。官方V4.1使用`<｜DSML｜ calls>`；重复竖线等偏离单列，结构缺失直接记失败。输出DSML不符合本实验请求的Python式调用；能辨识调用意图也不等于原框架执行成功。依据：[DeepSeek官方编码说明](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/encoding/README.md)。',
        '', 'get_code_of_file_function要求文件内独立函数，get_code_of_class_function要求文件/类/方法分开传参，get_code_of_class返回类源码；get_functions_of_class返回节点元数据，不应当作源码。裸类名可由框架在候选文件中唯一推断时，另标file_argument_inferred_by_framework；别名归一和多调用文本也单列。',
        '', '## 5. 代表调用（原始完整记录见tool_io_per_call.csv及calls）','',
        '| 方法/issue | 原始动作 | 真实执行/返回 | 参数/返回核验 | 证据 |','|---|---|---|---|---|']
    examples=[]
    for method in METHODS[1:]:
        pool=[c for c in calls if c['method']==method]
        for predicate in [lambda c:c.get('source_returned'),lambda c:c.get('tool_error'),lambda c:c.get('error_type')=='dispatch_parse',lambda c:c.get('exit')]:
            item=next((c for c in pool if predicate(c)),None)
            if item and item not in examples:examples.append(item)
    for c in examples:
        status=c.get('tool_error') or c.get('error_message') or ('exit; prior source='+str(c.get('source_reads_before_exit')) if c.get('exit') else (c.get('returned_head') or c.get('returned_kind')))
        text.append(f'| {c["method"]}/{c["instance_id"]} | `{cell(c["raw_model_output"],140)}` | {cell(status,160)} | {c.get("argument_category","")}; base_match={c.get("output_matches_base_source")} | `{c["raw_artifact_path"]}` |')
    text+=['','这些是描述性机制证据；使用工具不等于定位正确，参数错误也不能只凭一次失败归咎框架。需要结合base定义是否存在、工具支持的作用域和实际错误响应。完整逐题/逐调用CSV保留原文、规范调用、参数、输出SHA、耗时及进入哪个上下文的证据。',
        '', '## 6. 加载、队列、恢复和不可测量项','',
        '| 方法 | worker排队中位/P95秒 | 裁判加载总秒 | 每题构图均值/中位秒 | 传输失败次数 | 重放/复用题 |','|---|---:|---:|---:|---:|---:|']
    for method in METHODS:
        subset=[r for r in rows if r['method']==method and r['status']!='NOT_RUN'];q=stats([r['worker_queue_seconds'] for r in subset]);g=stats([r['judge_graph_setup_seconds'] for r in subset])
        text.append(f'| {method} | {fmt(q["median"])}/{fmt(q["p95"])} | {fmt(sum(r["judge_model_load_seconds"] for r in subset if r["judge_model_load_seconds"] is not None) if any(r["judge_model_load_seconds"] is not None for r in subset) else None)} | {fmt(g["mean"])}/{fmt(g["median"])} | {sum(r["transport_failed_attempts"] for r in subset)} | {sum(r["resumed_or_reused"] for r in subset)} |')
    service=read(RUN/'service/startup_timing.json') if (RUN/'service/startup_timing.json').exists() else None
    text+=['',f'自建主Qwen服务启动至就绪：{service}。该一次性过程不混入每题处理时长。HTTP冷连接调用、重试和worker队列已记账；服务端TTFT/内部排队和纯GPU核时间没有直接观测，不以客户端耗时猜测。',
        '', '## 7. 复现与边界','',f'分析命令：`python analysis/performance_and_tools.py --cohort {cohort}`。分析脚本只读既有推理产物与base源码，不调用模型、不执行测试、不训练、不更新历史矩阵。',
        '', '本报告另附完整每题时长/token、阶段统计和逐次I/O表。仅报告已经观测到的事实；未知字段保持NA。']
    path=out/f'{cohort}_单题时长_token与工具使用审计.md';path.write_text('\n'.join(text)+'\n')
    write(out/f'{cohort}_tool_summary.json',totals,replace=True)
    assert test_stats()==before,'Sealed test metadata drift'
    print(json.dumps({'report':str(path),'runtime':summaries,'tools':totals},ensure_ascii=False))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--cohort',choices=['smoke','lite_pilot'],default='lite_pilot');a=p.parse_args();main(a.cohort)
