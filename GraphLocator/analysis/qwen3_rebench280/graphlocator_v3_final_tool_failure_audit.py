#!/usr/bin/env python3
"""Independent log-only GraphLocator audit; never imports agents or executes tools.

All ranking/Gold joins are behind the selected scope's full terminal barrier.
The evidence path explicitly includes relevance filtering: raw tool candidates
are not expected to be sent unfiltered to the search agent.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

PROFILE={'temperature':0.7,'top_p':0.8,'top_k':20,'min_p':0.0,'seed':0}
EXAMPLE_NAMES=('Inaccurate recursive check','Incorrect handling of commutative factors','Dependency on Product')


def sha_bytes(raw): return hashlib.sha256(raw).hexdigest()
def canon(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


class Reader:
    def __init__(self): self.hashes={};self.errors=[]
    def data(self,path,*,jsonl=False,zipped=False):
        path=Path(path)
        if not path.is_file(): return [] if jsonl else None
        raw=path.read_bytes();self.hashes[str(path)]=sha_bytes(raw)
        try:
            if zipped: raw=gzip.decompress(raw)
            if not jsonl: return json.loads(raw)
            result=[]
            for n,line in enumerate(raw.decode().splitlines(),1):
                try: result.append(json.loads(line))
                except ValueError as error:self.errors.append({'path':str(path),'line':n,'error':str(error)})
            return result
        except (ValueError,UnicodeError,OSError,EOFError) as error:
            self.errors.append({'path':str(path),'error':str(error)})
            return [] if jsonl else None


def node_key(node):
    """Exact entity/source payload key; graph relationship attributes may grow."""
    if not isinstance(node,dict): return None
    return sha_bytes(canon({k:node.get(k) for k in ('type','name','location','content')}).encode())


def visible_key(node):
    """The exact original node_to_json projection, also valid for full Nodes.

    GraphLocator intentionally serializes location as file_path only in edge
    relevance/CIG prompts. Missing coordinates are not missing source text.
    """
    if not isinstance(node,dict):return None
    location=node.get('location')
    path=location.get('file_path') if isinstance(location,dict) else location
    return sha_bytes(canon({'type':node.get('type'),'name':node.get('name'),
                           'location':path,'content':node.get('content')}).encode())


def node_metadata(node):
    return {'payload_sha256':node_key(node),'type':node.get('type'),'name':node.get('name'),
            'location':node.get('location'),'source_characters':len(node.get('content') or ''),
            'source_sha256':sha_bytes((node.get('content') or '').encode())}


def raw_candidates(text):
    nodes=[];errors=[]
    for number,line in enumerate((text or '').splitlines(),1):
        if not line.strip():continue
        try:
            value=json.loads(line)
            is_edge=isinstance(value,dict) and 'src_node' in value and 'trg_node' in value
            if is_edge:
                values=[value['src_node'],value['trg_node']]
                values=[json.loads(v) if isinstance(v,str) else v for v in values]
            else: values=[value]
            for node in values:
                if not isinstance(node,dict) or 'type' not in node or 'name' not in node:
                    raise ValueError('Not a serialized graph Node')
                # Original search_node preserves the result list. search_edge
                # deduplicates endpoint Nodes by full value, including attrs.
                # Do not collapse distinct graph objects merely because their
                # identity/source payloads happen to be equal.
                if not is_edge or canon(node) not in {canon(n) for n in nodes}:nodes.append(node)
        except (ValueError,TypeError) as error:errors.append({'line':number,'error':str(error)})
    return nodes,errors


def judge_candidates(messages):
    text=(messages[-1].get('content') or '') if messages else ''
    nodes=[]
    for match in re.finditer(r'(?m)^#Node\s+\d+:\s*',text):
        try: value,_=json.JSONDecoder().raw_decode(text[match.end():])
        except ValueError:return [],False
        if not isinstance(value,dict):return [],False
        nodes.append(value)
    return nodes,bool(nodes)


def causal_candidates(messages):
    if not messages:return [],False
    text=messages[-1].get('content') or ''
    match=re.search(r'# (?:New )?Code Element List:\n(.*)\Z',text,re.S)
    if not match:return [],False
    try:
        values=ast.literal_eval(match.group(1).strip())
        if not isinstance(values,list):return [],False
        nodes=[]
        for value in values:
            if not isinstance(value,str):return [],False
            m=re.match(r'^#Code element \d+:\s*(.*)\Z',value,re.S)
            if not m:return [],False
            nodes.append(json.loads(m.group(1)))
        return nodes,True
    except (SyntaxError,ValueError,TypeError):return [],False


def booleans(content,expected):
    try: values=json.loads(content or '')
    except ValueError:return None
    return values if isinstance(values,list) and len(values)==expected and all(type(v) is bool for v in values) else None


def call_identity(code):
    try:
        value=ast.parse(code).body[0].value
        if isinstance(value,ast.Call) and isinstance(value.func,ast.Name) and value.func.id=='print':value=value.args[0]
        if not isinstance(value,ast.Call) or not isinstance(value.func,ast.Name):return None,None
        args={}
        for kw in value.keywords:
            if kw.arg=='graph':continue
            parsed=ast.literal_eval(kw.value)
            if kw.arg is None:args.update(parsed)
            else:args[kw.arg]=parsed
        return value.func.id,args
    except (ValueError,SyntaxError,TypeError,AttributeError,IndexError):return None,None


def usage_from_events(events,malformed_lines=0):
    attempts={}
    for event in events:
        if event.get('phase')!='generation' or event.get('event') not in {'http_started','http_finished'}:continue
        attempts.setdefault(event['stem'],{})[event['event']]=event
    pp=cc=unknown=0
    for pair in attempts.values():
        end=pair.get('http_finished',{});usage=end.get('usage')
        known=isinstance(usage,dict) and end.get('usage_known') is True and all(type(usage.get(k)) is int and usage[k]>=0 for k in ('prompt_tokens','completion_tokens'))
        if known:pp+=usage['prompt_tokens'];cc+=usage['completion_tokens']
        else:unknown+=1
    unknown=max(unknown,malformed_lines)
    return {'http_attempts':len(attempts),'http_attempt_count_exact':malformed_lines==0,
        'completion_requests':len({s.split('_attempt_')[0] for s in attempts}),
        'known_prompt_tokens':pp,'known_completion_tokens':cc,'known_total_tokens':pp+cc,
        'unknown_usage_requests':unknown,'total_tokens':None if unknown else pp+cc}


def status_scope(run,scope,reader):
    full=reader.data(run/'selection/manifest.json')
    selected=reader.data(run/'selection/pilot20.json') if scope=='pilot20' else full
    records=selected['records'];expected=20 if scope=='pilot20' else 280
    if len(records)!=expected or len({r['instance_id'] for r in records})!=expected:raise ValueError('Invalid frozen scope roster')
    outputs={r['instance_id']:reader.data(run/'outputs'/r['instance_id']/'result.json') for r in records}
    terminal=[iid for iid,value in outputs.items() if value and value.get('terminal') is True]
    return records,outputs,{'status':'FINAL_SCOPE_READY' if len(terminal)==expected else 'STATUS_ONLY',
        'scope':scope,'expected_tasks':expected,'terminal_tasks':len(terminal),'pending_tasks':expected-len(terminal),
        'gold_read':False,'scoring_joined':False,'new_model_calls':0,'tool_replays':0}


def phase_category(result,score,facts):
    if result['status']=='failed':
        status=result.get('execution_status','unknown')
        if 'Context' in status:return '上下文容量限制'
        if 'RelevanceFormat' in status:return '相关性布尔契约失败'
        if 'timeout' in status.lower() or 'ModelHTTP' in status:return '传输或任务预算终止；不能直接归模型能力'
        if 'operator' in status.lower():return '操作者中断；不计为模型能力错误'
        return '执行或环境异常：'+status
    if score and score['graphlocator_function']['hit5']:return '函数Top5命中'
    if not result.get('found_files') and not result.get('found_entities'):
        if facts['seed_count']==0:return '搜索结束无种子，最终无有效候选'
        if facts['final_cig_binding_count']==0:return '已有种子但最终CIG未保留代码绑定'
        return 'CIG有绑定但最终规范身份为空'
    if not result.get('found_entities'):return '仅文件或类候选，未输出函数候选'
    if score:
        if not score['graphlocator_file']['hit5']:return '文件Top5未命中；检索/过滤/判断原因未定'
        return '文件Top5命中但函数Top5未命中；排序/身份/判断原因未定'
    return '已有函数输出，未连接最终评分'


def audit_case(run,record,result,protocol,reader):
    iid=record['instance_id'];work=run/'outputs'/iid
    events=reader.data(work/'http/events.jsonl',jsonl=True)
    event_parse_errors=sum(e.get('path')==str(work/'http/events.jsonl') for e in reader.errors)
    requests=[];request_by_id={}
    for event in events:
        if event['event']!='model_request':continue
        rid=event['request_id'];payload=None;response=None;attempts=[]
        for end in [e for e in events if e.get('phase')=='generation' and e.get('stem','').startswith(f'{rid:05d}_attempt_') and e['event']=='http_finished']:
            attempts.append(end)
            candidate=reader.data(work/'http'/(end['stem']+'_request.json.gz'),zipped=True)
            if payload is None:payload=candidate
            if end.get('status')==200:
                response=reader.data(work/'http'/(end['stem']+'_response.json.gz'),zipped=True);payload=candidate
        if payload is None:
            paths=sorted((work/'http').glob(f'{rid:05d}_attempt_*_request.json.gz'))
            if paths:payload=reader.data(paths[0],zipped=True)
        item={'event':event,'payload':payload or {},'response':response,'attempts':attempts,'request_id':rid}
        requests.append(item);request_by_id[rid]=item
    def content(request):
        try:return request['response']['choices'][0]['message'].get('content') or ''
        except (KeyError,TypeError,IndexError):return ''
    def exact_profile(request):return all(request['payload'].get(k)==v for k,v in PROFILE.items())
    reqfacts=[]
    for request in requests:
        payload=request['payload'];event=request['event'];n=event.get('relevance_count')
        schema=payload.get('response_format',{}).get('json_schema',{}).get('schema')
        judged,parsed=judge_candidates(payload.get('messages',[])) if n is not None else ([],False)
        flags=booleans(content(request),n) if n is not None else None
        declared=[]
        if request['response']:
            for call in request['response']['choices'][0].get('message',{}).get('tool_calls') or []:
                function=call.get('function',{});arguments=function.get('arguments')
                try:arguments=json.loads(arguments) if isinstance(arguments,str) else arguments
                except ValueError:arguments=None
                declared.append({'tool_call_id':call.get('id'),'function':function.get('name'),
                                 'arguments_json_object':isinstance(arguments,dict),'arguments':arguments})
        reqfacts.append({'instance_id':iid,'request_id':request['request_id'],'caller':event.get('caller'),
            'actual_sampling_matches':exact_profile(request),'actual_sampling':{k:payload.get(k) for k in PROFILE},
            'caller_requested_temperature':event.get('caller_requested_temperature'),
            'thinking_false':payload.get('chat_template_kwargs',{}).get('enable_thinking') is False,
            'relevance_count':n,'schema_exact_n':schema=={'type':'array','items':{'type':'boolean'},'minItems':n,'maxItems':n} if n is not None else None,
            'judge_input_candidate_count':len(judged) if parsed else None,'judge_output_boolean_count':len(flags) if flags is not None else None,
            'judge_response_state':('valid_exact_array' if flags is not None else
                'http200_but_invalid_boolean_contract' if request['response'] else 'no_confirmed_http200') if n is not None else None,
            'schema_absent_for_other_phases':not payload.get('response_format') if n is None else None,
            'http_attempts':len(request['attempts']),'has_http200_response':request['response'] is not None,
            'declared_native_tool_calls':declared,
            'max_output_tokens':payload.get('max_completion_tokens')})
    seed_event=next((e for e in events if e['event']=='seed_locations'),{})
    seed_keys={node_key(n) for n in seed_event.get('nodes',[])}
    tools=[]
    for pos,event in enumerate(events):
        if event['event']!='tool_finished':continue
        next_tool=next((e['time'] for e in events[pos+1:] if e['event']=='tool_started'),float('inf'))
        raw,parse_errors=raw_candidates(event.get('return_text','')) if event.get('status')=='success' else ([],[])
        name,args=call_identity(event.get('code',''))
        judges=[r for r in requests if r['event'].get('caller')=='is_relevant' and event['time']<r['event']['time']<next_tool]
        judge=judges[0] if len(judges)==1 else None
        judged,parsed=judge_candidates(judge['payload'].get('messages',[])) if judge else ([],False)
        flags=booleans(content(judge),len(judged)) if judge and parsed else None
        projected_order_matches=parsed and [visible_key(n) for n in judged]==[visible_key(n) for n in raw]
        if judge and flags is not None and projected_order_matches:
            # The decisions refer to candidate positions, not to richer fields
            # absent from the original compact prompt. Map those same indices
            # back onto the raw candidate objects before checking observation.
            accepted=[n for n,yes in zip(raw,flags) if yes];filter_mode='model_boolean_filter'
        elif not judge and len(raw)<5 and event.get('status')=='success':accepted=raw;filter_mode='official_under_topk_no_judge'
        else:accepted=None;filter_mode='judge_or_preflight_not_completed'
        # Retrieve the real native tool_call_id from its preceding model reply.
        preceding=[r for r in requests if r['event'].get('caller')=='get_seed_location' and r['event']['time']<event['time'] and r['response']]
        call_ids=[]
        if preceding:
            message=preceding[-1]['response']['choices'][0].get('message',{})
            for call in message.get('tool_calls') or []:
                fn=call.get('function',{})
                try:arguments=json.loads(fn.get('arguments','{}'))
                except (ValueError,TypeError):arguments=None
                if fn.get('name')==name and arguments==args:call_ids.append(call.get('id'))
        observed=None;later_search_response=False
        if len(call_ids)==1:
            for request in requests:
                if request['event']['time']<=event['time'] or request['event'].get('caller')!='get_seed_location' or not request['response']:continue
                for message in request['payload'].get('messages',[]):
                    if message.get('role')=='tool' and message.get('tool_call_id')==call_ids[0]:
                        text=message.get('content','')
                        if text.startswith('OBSERVATION:\n'):
                            observed,_=raw_candidates(text[len('OBSERVATION:\n'):]);later_search_response=True;break
                if later_search_response:break
        expected_keys=[node_key(n) for n in accepted] if accepted is not None else None
        tools.append({'instance_id':iid,'tool_sequence':len(tools)+1,'function':name,'arguments':args,
            'status':event.get('status'),'error':event.get('message'),'code':event.get('code'),
            'raw_candidate_count':len(raw),'raw_candidate_parse_errors':parse_errors,
            'judge_request_count':len(judges),'judge_input_matches_raw_candidate_order':
                projected_order_matches if parsed else None,
            'judge_coordinates_visible':all(isinstance(n.get('location'),dict) for n in judged) if parsed else None,
            'judge_payload_rule':'Original type/name/file_path/content projection; boolean indices mapped to raw candidate order',
            'judged_count':len(judged) if parsed else None,'accepted_after_filter_count':len(accepted) if accepted is not None else None,
            'filter_mode':filter_mode,'tool_call_id':call_ids[0] if len(call_ids)==1 else None,
            'filtered_observation_received_by_later_search_http200':later_search_response,
            'filtered_observation_exact_payload_order':expected_keys==[node_key(n) for n in observed] if expected_keys is not None and observed is not None else None,
            'accepted_payloads_present_in_final_seed_set':sum(k in seed_keys for k in expected_keys) if expected_keys is not None else None,
            'raw_payload_sha256':event.get('output_sha256'),'full_function_source_verified':None,
            'delivery_policy':'Judge-filtered observation is expected; no requirement to deliver the unfiltered raw tool text to search'})
    cig=[];known_payloads=set();pending=None
    for event in events:
        if event['event']=='causal_parse_started':pending=event;continue
        if event['event']!='causal_parse_finished' or pending is None:continue
        candidates=pending.get('candidates',[])
        preceding=[r for r in requests if r['event'].get('caller')=='generate_causal_graph' and r['event']['time']<pending['time'] and r['response']]
        request=preceding[-1] if preceding else None
        delivered,parsed=causal_candidates(request['payload'].get('messages',[])) if request else ([],False)
        known_payloads.update(node_key(n) for n in candidates)
        bindings=[n for factor in (event.get('causal_graph') or {}).get('nodes',[]) for n in factor.get('code_elements',[])]
        raw=pending.get('raw_response','');selected=event.get('selected',[])
        cig.append({'instance_id':iid,'parse_sequence':len(cig)+1,'candidate_count':len(candidates),
            'http_request_id':request['request_id'] if request else None,
            'candidate_payloads_match_actual_model_context':parsed and [visible_key(n) for n in candidates]==[visible_key(n) for n in delivered],
            'context_encoding':'Original node_to_json: type/name/location=file_path/content, no definition coordinates or graph attributes',
            'selected_current_candidates':len(selected),'selected_current_payloads_in_current_context':all(node_key(n) in {node_key(c) for c in candidates} for n in selected),
            'binding_count_in_returned_graph':len(bindings),'bindings_from_any_seen_candidate_payload':all(node_key(n) in known_payloads for n in bindings),
            'contains_three_original_example_names':all(name in raw for name in EXAMPLE_NAMES),
            'raw_response_sha256':sha_bytes(raw.encode()),'graph_nodes':event.get('graph_nodes'),'graph_edges':event.get('graph_edges'),
            'classification_note':'Example-name echo is a shape flag, never automatically a localization miss'})
        pending=None
    inventory=reader.data(work/'public_inventory.json') or {};parser=inventory.get('parser',{})
    graph_receipt=reader.data(run/record['graph_receipt']) or {}
    fields=('instance_id','repo','base_commit','snapshot_tree_sha256')
    graph_bound=all(graph_receipt.get(k)==record[k] for k in fields) and graph_receipt.get('status')=='success'
    if result.get('graph_sha256'):graph_bound=graph_bound and result['graph_sha256']==graph_receipt.get('graph_sha256')
    validations=result.get('identity_validation',[])
    facts={'instance_id':iid,'status':result['status'],'execution_status':result.get('execution_status'),
        'declared_retrieval_calls':sum(d['function'] in {'search_node','search_edge'} for q in reqfacts for d in q['declared_native_tool_calls']),
        'declared_finish_calls':sum(d['function']=='finish' for q in reqfacts for d in q['declared_native_tool_calls']),
        'unrecognized_tool_names':sum(d['function'] not in {'search_node','search_edge','finish'} for q in reqfacts for d in q['declared_native_tool_calls']),
        'unparseable_tool_arguments':sum(not d['arguments_json_object'] for q in reqfacts for d in q['declared_native_tool_calls']),
        'tool_started_events':sum(e['event']=='tool_started' for e in events),
        'tool_started_without_finished':max(0,sum(e['event']=='tool_started' for e in events)-len(tools)),
        'seed_count':seed_event.get('count',0),'tool_calls':len(tools),'tool_success':sum(t['status']=='success' for t in tools),
        'judge_calls':sum(r['relevance_count'] is not None for r in reqfacts),'causal_parse_calls':len(cig),
        'final_cig_binding_count':sum(len(n.get('code_elements',[])) for n in (result.get('causal_graph') or {}).get('nodes',[])),
        'final_identity_valid':sum(v.get('status') in {'valid_exact_ast_anchor','valid_file'} for v in validations),
        'final_identity_invalid':sum(v.get('status') not in {'valid_exact_ast_anchor','valid_file'} for v in validations),
        'public_ast_inventory_present':bool(inventory),
        'graph_source_receipt_bound':graph_bound,'ast312':str(parser.get('parser_version','')).startswith('3.12.'),
        'ast_helper_bound':parser.get('helper_sha256')==protocol['source_sha256'].get('rebench_qwen3/public_ast.py'),
        'ast_parse_error_files':len(inventory.get('parse_errors',[])),
        'initial_cig_example_names_flag':bool(cig and cig[0]['contains_three_original_example_names']),
        'max_output_length_responses':sum(e['event']=='model_response' and 'length' in e.get('finish_reasons',[]) for e in events),
        'transport_error_attempts':sum(e['event']=='http_finished' and e.get('phase')=='generation' and e.get('status')!=200 for e in events),
        'raw_result_path':str(work/'result.json'),'raw_result_sha256':reader.hashes.get(str(work/'result.json')),
        **usage_from_events(events,event_parse_errors)}
    return facts,tools,reqfacts,cig


def csv_write(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:canon(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)


def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def build(run,scope,output,evaluation_path=None):
    reader=Reader();records,results,status=status_scope(run,scope,reader)
    if output.exists():raise FileExistsError('Use a new audit output directory; history is never overwritten')
    output.mkdir(parents=True)
    if status['status']=='STATUS_ONLY':
        dump(output/'状态_未终态不评分.json',status)
        return status
    # The final evaluation JSON is opened only after the above terminal barrier.
    protocol=reader.data(run/'protocol.json');scores={}
    if evaluation_path is not None:
        evaluation=reader.data(evaluation_path)
        if (not evaluation or evaluation['summary'].get('status')!='FINAL' or evaluation['summary'].get('scope')!=scope
                or {r['instance_id'] for r in evaluation['records']}!={r['instance_id'] for r in records}):
            raise ValueError('Only the exact final same-scope evaluation may be joined')
        if evaluation['summary'].get('protocol_sha256')!=reader.hashes[str(run/'protocol.json')]:
            raise ValueError('Final evaluation belongs to another frozen protocol')
        expected_hashes=evaluation['summary'].get('worker_result_sha256',{})
        for record in records:
            path=str(run/'outputs'/record['instance_id']/'result.json')
            if expected_hashes.get(path)!=reader.hashes.get(path):
                raise ValueError('Final evaluation/source-result SHA binding differs')
        scores={r['instance_id']:r for r in evaluation['records']}
    tasks=[];tools=[];requests=[];cig=[]
    for record in records:
        iid=record['instance_id'];facts,t,q,c=audit_case(run,record,results[iid],protocol,reader)
        score=scores.get(iid)
        facts['stage_category']=phase_category(results[iid],score,facts)
        facts['file_hit5']=score['graphlocator_file']['hit5'] if score else None
        facts['function_hit5']=score['graphlocator_function']['hit5'] if score else None
        facts['found_files_top5']=results[iid].get('found_files',[])[:5]
        facts['found_functions_top5']=results[iid].get('found_entities',[])[:5]
        tasks.append(facts);tools+=t;requests+=q;cig+=c
    summary={**status,'status':'FINAL','protocol':'Qwen3 official non-thinking sampling profile; GraphLocator original search/CIG',
        'scoring_joined':bool(scores),'private_gold_opened':False,'source_modified':False,'ranking':'CIG factor/binding insertion order; no confidence-ranked rewrite',
        'analysis_carrier_revision':'v2 recognizes original node_to_json compact location strings; no inference/prediction change',
        'stage_categories':dict(Counter(t['stage_category'] for t in tasks)),
        'tool_calls':len(tools),'tool_success':sum(t['status']=='success' for t in tools),
        'declared_retrieval_calls':sum(t['declared_retrieval_calls'] for t in tasks),
        'tool_started_events':sum(t['tool_started_events'] for t in tasks),
        'tool_started_without_finished':sum(t['tool_started_without_finished'] for t in tasks),
        'unrecognized_tool_names':sum(t['unrecognized_tool_names'] for t in tasks),
        'unparseable_tool_arguments':sum(t['unparseable_tool_arguments'] for t in tasks),
        'tools_with_model_boolean_filter':sum(t['filter_mode']=='model_boolean_filter' for t in tools),
        'tools_with_under_topk_bypass':sum(t['filter_mode']=='official_under_topk_no_judge' for t in tools),
        'tools_judge_payload_order_mismatch':sum(t['judge_input_matches_raw_candidate_order'] is False for t in tools),
        'filtered_observations_delivered_to_search':sum(t['filtered_observation_received_by_later_search_http200'] for t in tools),
        'filtered_observation_payload_mismatch':sum(t['filtered_observation_exact_payload_order'] is False for t in tools),
        'model_requests':len(requests),'sampling_profile_mismatch':sum(not q['actual_sampling_matches'] for q in requests),
        'caller_requested_temperature_counts':dict(Counter(str(q['caller_requested_temperature']) for q in requests)),
        'actual_sampling_profile':PROFILE,
        'thinking_enabled_or_not_explicitly_false':sum(not q['thinking_false'] for q in requests),
        'relevance_schema_count_mismatch':sum(q['schema_exact_n'] is False for q in requests),
        'relevance_without_confirmed_http200':sum(q['relevance_count'] is not None and not q['has_http200_response'] for q in requests),
        'relevance_candidate_or_output_length_issues':sum(q['relevance_count'] is not None and q['has_http200_response'] and
            (q['judge_input_candidate_count']!=q['relevance_count'] or q['judge_output_boolean_count']!=q['relevance_count']) for q in requests),
        'cig_context_payload_mismatch':sum(not c['candidate_payloads_match_actual_model_context'] for c in cig),
        'cig_unknown_payload_bindings':sum(not c['bindings_from_any_seen_candidate_payload'] for c in cig),
        'example_label_echo_tasks':sum(t['initial_cig_example_names_flag'] for t in tasks),
        'graph_source_receipt_unbound':sum(not t['graph_source_receipt_bound'] for t in tasks),
        'ast_inventory_missing_tasks':sum(not t['public_ast_inventory_present'] for t in tasks),
        'ast312_or_helper_unbound':sum(t['public_ast_inventory_present'] and (not t['ast312'] or not t['ast_helper_bound']) for t in tasks),
        'known_total_tokens':sum(t['known_total_tokens'] for t in tasks),
        'unknown_usage_requests':sum(t['unknown_usage_requests'] for t in tasks),
        'http_attempts':sum(t['http_attempts'] for t in tasks),'read_errors':reader.errors,
        'source_files_sha256':reader.hashes,'analysis_script_sha256':sha_bytes(Path(__file__).read_bytes()),
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'limits':['Judge/CIG comparisons use the original node_to_json projection: type/name/file_path/content; compact prompts intentionally omit coordinates and attributes',
            'Comparisons certify supplied source text, not full AST-function completeness or effective model use',
            'No later search observation is expected after finish/max-turn; retained seeds may still enter CIG',
            'Judge intentionally filters irrelevant nodes; raw unfiltered text is not required in later search requests',
            'Template echo and stage categories are observable flags, not unique causal explanations or automatic wrong predictions',
            'Graph/source is checked through existing identity/hash receipts; this audit does not rehash all repository source files']}
    dump(output/'统一工具与失败审计.json',summary)
    for name,rows in [('逐题阶段分析.csv',tasks),('逐工具候选过滤与观测.csv',tools),('逐请求schema与采样.csv',requests),('逐CIG候选与绑定.csv',cig)]:csv_write(output/name,rows)
    lines=['# GraphLocator工具与失败阶段审计','',f"范围{scope}，全部{len(tasks)}题终态；最终评分已连接={bool(scores)}。只读原始日志，无新模型/工具调用，不打开private Gold。",'',
        '## 总体分类','', '| 可观察阶段 | 题数 |','|---|---:|']
    lines += [f'| {key} | {value} |' for key,value in summary['stage_categories'].items()]
    lines += ['', '## 工具与上下文证据链','',
        f"模型声明检索调用{summary['declared_retrieval_calls']}次，执行wrapper启动{summary['tool_started_events']}次；完成事件{len(tools)}次（成功{summary['tool_success']}），启动后无完成回执{summary['tool_started_without_finished']}次，后者不能解释成从未执行。未知工具名/参数JSON对象不可解析{summary['unrecognized_tool_names']}/{summary['unparseable_tool_arguments']}次。",
        f"模型布尔过滤{summary['tools_with_model_boolean_filter']}次，小于top-k直接采用{summary['tools_with_under_topk_bypass']}次。",
        f"judge输入原候选顺序不匹配{summary['tools_judge_payload_order_mismatch']}次；已送回后续搜索的过滤后观测{summary['filtered_observations_delivered_to_search']}次，其已知内容不匹配{summary['filtered_observation_payload_mismatch']}次。",
        'GraphLocator先将完整候选送给相关性判断，再把筛选后的节点交回搜索模型；未筛中的原始全文不应被要求重复送给搜索模型。最后一轮后无后续搜索请求也不等同源码丢失，须同时看种子和CIG输入。',
        f"CIG候选与真实模型输入不匹配{summary['cig_context_payload_mismatch']}次；出现未在任何已见候选中的绑定{summary['cig_unknown_payload_bindings']}次。按原node_to_json的type/name/文件路径/content投影核对；原实现故意省略定义坐标和属性，不能把位置dict变路径字符串误判为丢源码。judge的布尔结果按原候选索引映回完整Node再核对观测。以上不认证完整AST函数体。",'',
        '## 协议与运行状态','',
        f"请求{len(requests)}次；固定actual采样或显式非思考不匹配{summary['sampling_profile_mismatch']}/{summary['thinking_enabled_or_not_explicitly_false']}次。caller默认0与actual .7分别保留。",
        f"相关性schema数量不符{summary['relevance_schema_count_mismatch']}次，HTTP200后的候选/布尔契约异常{summary['relevance_candidate_or_output_length_issues']}次；无确认HTTP200的judge请求{summary['relevance_without_confirmed_http200']}次另列，不能伪装成布尔缺项。截断/HTTP失败仍按失败保留，不自动重抽。",
        f"已知token下界{summary['known_total_tokens']}，usage未知尝试{summary['unknown_usage_requests']}；图source无成功绑定{summary['graph_source_receipt_unbound']}题，公共AST库存未生成{summary['ast_inventory_missing_tasks']}题；已生成库存中AST312/helper失配{summary['ast312_or_helper_unbound']}题。",
        f"初始CIG包含全部三示例因子名的题数{summary['example_label_echo_tasks']}；只作形态flag，不自动判定位错误。排名仍是CIG因子与绑定插入顺序，没有事后置信度排序。",'',
        '## 逐题分析','']
    for t in tasks:
        lines += [f"### {t['instance_id']}",'',f"- 阶段：{t['stage_category']}；运行状态{t['status']}/{t['execution_status']}。",
            f"- 工具{t['tool_calls']}次（成功{t['tool_success']}），种子{t['seed_count']}，CIG解析{t['causal_parse_calls']}，最终绑定{t['final_cig_binding_count']}。",
            f"- 文件/函数Hit@5：{t['file_hit5']}/{t['function_hit5']}；函数身份有效/无效{t['final_identity_valid']}/{t['final_identity_invalid']}。",
            '- 只有阶段证据时保留具体原因未定，不把未命中一概归为不会工具。','']
    (output/'工具与失败阶段审计.md').write_text('\n'.join(lines),encoding='utf-8')
    return {k:summary[k] for k in ('status','scope','terminal_tasks','model_requests','tool_calls','stage_categories','read_errors')}


class BoundaryTests(unittest.TestCase):
    def test_bool_filter_not_unfiltered_delivery(self):
        raw=[{'type':'FUNCTION','name':'a','location':{},'content':'def a(): pass'},
             {'type':'FUNCTION','name':'b','location':{},'content':'def b(): pass'}]
        flags=booleans('[true,false]',2)
        retained=[n for n,yes in zip(raw,flags) if yes]
        self.assertEqual([node_key(n) for n in retained],[node_key(raw[0])])
        self.assertNotEqual([node_key(n) for n in raw],[node_key(n) for n in retained])
    def test_bad_bool_contract_not_filled(self):
        self.assertIsNone(booleans('[true]',2));self.assertIsNone(booleans('[1,false]',2))
    def test_actual_cig_python_list_carrier_roundtrips_node_source(self):
        node={'type':'FUNCTION','name':'f','location':{'file_path':'/source/f.py'},'content':'def f():\n    return "q"'}
        value=['#Code element 1: '+json.dumps(node)]
        parsed,valid=causal_candidates([{'role':'user','content':'# Code Element List:\n'+str(value)}])
        self.assertTrue(valid);self.assertEqual(parsed,[node])
    def test_original_compact_location_carrier_is_not_source_loss(self):
        raw={'type':'FUNCTION','name':'f','location':{'file_path':'/source/a.py','start_line':10},
             'attribute':{'calls':['x']},'content':'def f():\n    return x()'}
        compact={'type':raw['type'],'name':raw['name'],'location':'/source/a.py','content':raw['content']}
        self.assertNotEqual(node_key(raw),node_key(compact))
        self.assertEqual(visible_key(raw),visible_key(compact))
        retained=[n for n,keep in zip([raw],[True]) if keep]
        self.assertEqual(node_key(retained[0]),node_key(raw))
    def test_tool_json_and_edge_nodes_keep_order(self):
        a={'type':'FUNCTION','name':'a','content':'x'};b={'type':'METHOD','name':'b','content':'y'}
        text=json.dumps({'src_node':json.dumps(a),'trg_node':json.dumps(b)})
        nodes,errors=raw_candidates(text);self.assertEqual(nodes,[a,b]);self.assertEqual(errors,[])
    def test_distinct_graph_attributes_do_not_fabricate_candidate_loss(self):
        a={'type':'FUNCTION','name':'f','location':{},'content':'def f():pass','attribute':{'v':1}}
        b={**a,'attribute':{'v':2}}
        self.assertEqual(node_key(a),node_key(b))
        nodes,_=raw_candidates(json.dumps(a)+'\n'+json.dumps(b))
        self.assertEqual(nodes,[a,b])
        endpoints,_=raw_candidates(json.dumps({'src_node':json.dumps(a),'trg_node':json.dumps(b)}))
        self.assertEqual(endpoints,[a,b])
    def test_ast_literal_search_arguments_are_read_not_executed(self):
        name,args=call_identity("print(search_node(**{'node_type':'FUNCTION','node_name':'f'},graph=graph))")
        self.assertEqual(name,'search_node');self.assertEqual(args,{'node_type':'FUNCTION','node_name':'f'})
        self.assertEqual(call_identity("__import__('os').system('false')"),(None,None))
    def test_partial_scope_returns_status_without_opening_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'selection').mkdir();rows=[{'instance_id':str(i)} for i in range(280)]
            (root/'selection/manifest.json').write_text(json.dumps({'records':rows}))
            result=build(root,'full280',root/'audit',root/'MUST_NOT_OPEN.json')
            self.assertEqual(result['status'],'STATUS_ONLY');self.assertFalse(result['gold_read'])
    def test_unfinished_generation_usage_remains_unknown(self):
        value=usage_from_events([{'event':'http_started','phase':'generation','stem':'00001_attempt_1'}])
        self.assertEqual(value['unknown_usage_requests'],1);self.assertIsNone(value['total_tokens'])
    def test_malformed_ledger_tail_is_not_exact_zero_usage(self):
        value=usage_from_events([],malformed_lines=1)
        self.assertIsNone(value['total_tokens']);self.assertFalse(value['http_attempt_count_exact'])
    def test_same_ids_from_another_protocol_evaluation_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'selection').mkdir()
            rows=[{'instance_id':str(i)} for i in range(280)]
            (root/'selection/manifest.json').write_text(json.dumps({'records':rows}))
            (root/'selection/pilot20.json').write_text(json.dumps({'records':rows[:20]}))
            (root/'protocol.json').write_text('{}')
            for row in rows[:20]:
                path=root/'outputs'/row['instance_id'];path.mkdir(parents=True)
                (path/'result.json').write_text(json.dumps({'terminal':True,'status':'complete'}))
            evaluation=root/'evaluation.json'
            evaluation.write_text(json.dumps({'summary':{'status':'FINAL','scope':'pilot20','protocol_sha256':'wrong'},'records':rows[:20]}))
            with self.assertRaisesRegex(ValueError,'another frozen protocol'):
                build(root,'pilot20',root/'audit',evaluation)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',type=Path)
    p.add_argument('--scope',choices=['pilot20','full280'],default='full280');p.add_argument('--output',type=Path)
    p.add_argument('--evaluation-json',type=Path);p.add_argument('--self-test',action='store_true');args=p.parse_args()
    if args.self_test:
        test=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryTests))
        raise SystemExit(0 if test.wasSuccessful() else 1)
    if args.run_dir is None or args.output is None:p.error('--run-dir and --output are required')
    print(json.dumps(build(args.run_dir.resolve(),args.scope,args.output.resolve(),args.evaluation_json),ensure_ascii=False))


if __name__=='__main__':main()
