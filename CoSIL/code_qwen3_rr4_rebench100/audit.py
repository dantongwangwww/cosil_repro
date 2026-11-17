"""Final CPU audit of real wire requests, source spans, routing and historical integrity."""
from collections import Counter, defaultdict
import hashlib
import json
import statistics
from . import config as P
from .report import create, private, mean_ci, wilson

def events(folder):
    p = folder / 'events.jsonl'
    return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []

def run():
    P.configure()
    state = P.read(P.OUT / 'controller_status.json')
    if state['stage'] not in ('COMPLETE', 'FAILED'):
        raise RuntimeError('Final audit requires terminal controller state')
    summary = create(final=True); evaluation, _ = private()
    records = P.read(P.OUT / 'inputs/manifest.json')['records']
    wire_errors, unknown, truncated, source_errors, routing_errors = [], [], [], [], []
    requests_checked = deliveries_checked = base_spans_checked = local_count = 0
    cases = []; all_local = []; actual_total_tokens = 0
    from code_rebench_qwen.runner import resolve_source
    from code_v3b.tool_dispatch import ToolCall
    from code_rebench_qwen import common as C
    rpc = [json.loads(s) for s in (P.OUT / 'run/judge_service/rpc.jsonl').read_text().splitlines()] if (P.OUT / 'run/judge_service/rpc.jsonl').exists() else []
    rpc_scores = {r['result']['score_sequence']: r for r in rpc if r.get('operation') == 'score' and r.get('ok')}
    for item in records:
        iid = item['instance_id']; job = P.read(item['job']); index = P.read(job['code_index']); g = evaluation[iid]
        case = {'instance_id': iid, 'repo': item['repo'], 'gold_functions': g['targets'], 'gold_files': g['gold_files'], 'arms': {}}
        for arm in P.ARMS:
            folder = P.OUT / 'run' / arm / iid
            if not (folder / 'result.json').exists():
                case['arms'][arm] = {'status':'EXECUTION_INCOMPLETE' if (folder/'started.json').exists() else 'NOT_RUN'}; continue
            result = P.read(folder / 'result.json'); ev = events(folder)
            sources = [P.read(f) for f in sorted((folder / 'sources').glob('*.json'))]
            lookup = {s['source_id']:s for s in sources}; reqs = {}; prompt = output = 0
            for call in sorted((folder / 'calls').glob('*')):
                request = P.read(call / 'request.json'); requests_checked += 1
                if not (request.get('model') == 'qwen3-8b' and request.get('max_tokens') == 2048
                    and request.get('temperature') == 0 and request.get('seed') == 0 and request.get('n') == 1
                    and request.get('chat_template_kwargs',{}).get('enable_thinking') is False):
                    wire_errors.append(str(call))
                for receipt_file in call.glob('attempt_*_receipt.json'):
                    receipt = P.read(receipt_file); u = receipt.get('usage')
                    if receipt.get('request_sha256') != C.digest(request): wire_errors.append(str(receipt_file))
                    response_file = receipt_file.with_name(receipt_file.name.replace('_receipt.json','_response.json'))
                    if response_file.exists() and receipt.get('response_sha256') != C.digest(P.read(response_file)):
                        wire_errors.append(str(response_file))
                    if receipt.get('request_id'): reqs[receipt['request_id']] = request
                    if u:
                        prompt += u['prompt_tokens']; output += u['completion_tokens']
                    else: unknown.append(str(receipt_file))
                    if receipt.get('finish_reason') == 'length': truncated.append(str(receipt_file))
            if prompt != result.get('known_prompt_tokens',0) or output != result.get('known_completion_tokens',0):
                wire_errors.append(str(folder / 'result.json'))
            actual_total_tokens += prompt + output
            for s in sources:
                try:
                    raw = resolve_source(job,index,ToolCall(s['tool'],tuple(s['arguments']),s['tool']))
                    header = f"[Exact base source identity: {raw['path']}::{raw['qualified_name']}]\n"
                    if raw['sha256'] != s.get('raw_source_text_sha256') or s['text'] != header + raw['text'] or hashlib.sha256(s['text'].encode()).hexdigest() != s['sha256']:
                        raise ValueError('Source identity/header/raw span SHA mismatch')
                    base_spans_checked += 1
                except Exception as error: source_errors.append({'issue':iid,'arm':arm,'source':s['source_id'],'error':str(error)})
            accepted = set(); seen = set(); final_seen = set()
            for event in ev:
                if event['event'] == 'context_accept':
                    matched = [s for s in sources if s['step'] == event['step'] and s['tool'] == event['tool'] and s['arguments'] == event['arguments']]
                    if matched: accepted.add(matched[-1]['source_id'])
                if event['event'] == 'agent_seen':
                    sid = event['source_id']; request = reqs.get(event.get('request_id'),{})
                    if sid not in accepted or sid not in lookup or not any(lookup[sid]['text'] in m.get('content','') for m in request.get('messages',[])):
                        source_errors.append({'issue':iid,'arm':arm,'source':sid,'error':'Unproved actual source delivery'})
                    else:
                        seen.add(sid); deliveries_checked += 1
                        if event.get('stage') == 'final_summary': final_seen.add(sid)
            local = [e for e in ev if e['event'] == 'local_judge']; local_count += len(local); all_local.extend(local)
            for event in local:
                receipt = rpc_scores.get(event['score_sequence']); correct = hashlib.sha256(event['model_input'].encode()).hexdigest() == event['input_sha256']
                correct &= event['route'] == P.route(event['p_yes'], event['low'], event['high'])
                correct &= bool(receipt and receipt['input_sha256'] == event['input_sha256'] and receipt['result']['p_yes'] == event['p_yes'])
                if not correct: routing_errors.append({'issue':iid,'step':event['step'],'sequence':event['score_sequence']})
            def covered(s, r):
                return s['path'] == r['path'] and any(span['start_line'] <= r['start_line'] and span['end_line'] >= r['end_line'] for span in s['spans'])
            evidence = []
            predicted = result.get('predicted_functions',[])[:10]
            ids = [p.get('path','')+'::'+p['qualified_name'] if isinstance(p.get('qualified_name'),str) else None for p in predicted]
            selected = result.get('file_rank_after_reflection',[])[:5]
            for fid in g['targets']:
                regions = [r for r in g['regions'] if r['identity'] == fid]
                retrieved = all(any(covered(s,r) for s in sources) for r in regions)
                visible = all(any(s['source_id'] in seen and covered(s,r) for s in sources) for r in regions)
                local_reject = [dict(step=e['step'],p_yes=e['p_yes']) for e in local if e['route']=='reject' and e['function_id'].rsplit('@',1)[0]==fid]
                rank = next((k+1 for k,x in enumerate(ids) if x==fid),None)
                if rank and rank <= 5: cause = 'Top5命中'
                elif rank: cause = '排在Top6至10'
                elif local_reject and not visible: cause = '4B直接剪掉目标且无完整送达证据'
                elif visible: cause = '目标源码已送达但最终排序遗漏或身份不符'
                elif retrieved: cause = '已提取目标源码但未完整送达搜索agent'
                elif fid.split('::',1)[0] not in selected: cause = '目标文件未入候选'
                else: cause = '文件已选但未检索目标函数'
                evidence.append({'identity':fid,'rank':rank,'retrieved_all_base_spans':retrieved,'agent_seen_all_base_spans':visible,
                    'local_reject_events':local_reject,'cause':cause})
            hit = bool(set(ids[:5]) & set(g['targets']))
            failures = sorted({e['cause'] for e in evidence if e['rank'] is None or e['rank'] > 5})
            case['arms'][arm] = {'status':result['status'],'raw_top5':predicted[:5], 'function_hit5':hit if g['targets'] else None,
                'source_evidence':evidence,'failure_categories':failures, 'routes':dict(Counter(e['route'] for e in local)),
                'tool_errors':[e for e in ev if e['event']=='tool_io_audit' and not e.get('success')],
                'source_reads':len(sources),'source_deliveries':sum(e['event']=='agent_seen' for e in ev),
                'main_prompt_tokens':prompt,'main_completion_tokens':output}
        cases.append(case)
    frozen = P.read(P.OUT / 'freeze.json'); integrity = {}
    for key in ('code_sha256','input_sha256','protected_sha256'):
        integrity[key] = [path for path,digest in frozen[key].items() if P.sha(path)!=digest]
    from code_v6.common import test_stats
    integrity['sealed_test_stat_unchanged'] = test_stats() == frozen['test_stat_only']
    completed_path = P.OUT / 'run/judge_service/completed.json'
    resident = P.read(completed_path) if completed_path.exists() else None
    if state['stage']=='COMPLETE' and (not resident or resident['score_count'] != local_count+3 or resident['model_load_count']!=1):
        routing_errors.append({'error':'Resident score count mismatch','local_count':local_count,'resident':resident})
    pair_values = [(c['arms']['hybrid_safe'].get('function_hit5') or False) - (c['arms']['baseline'].get('function_hit5') or False)
                   for c in cases if evaluation[c['instance_id']]['targets']]
    # Both endpoints share file candidates; compare actual final raw output, not post-hoc fixed identities.
    exact_safety = []
    for c in cases:
        for e in c['arms'].get('hybrid_safe',{}).get('source_evidence',[]):
            for reject in e['local_reject_events']: exact_safety.append({'instance_id':c['instance_id'],'identity':e['identity'],**reject})
    audit = {'state':state['stage'],'summary':summary,'requests_checked':requests_checked,'source_deliveries_checked':deliveries_checked,
        'base_spans_checked':base_spans_checked,'local_scores_checked':local_count,'actual_batch_main_tokens':actual_total_tokens,
        'wire_errors':wire_errors,'source_errors':source_errors,'routing_errors':routing_errors,'unknown_usage':unknown,'output_truncations':truncated,
        'paired_delta_bootstrap_ci95':mean_ci(pair_values),'gold_direct_reject_events':exact_safety,
        'local_latency_seconds':{'median':statistics.median(e['latency_seconds'] for e in all_local) if all_local else None,
            'p95':sorted(e['latency_seconds'] for e in all_local)[math_index(len(all_local),.95)] if all_local else None},
        'integrity':integrity,'resident':resident,'cases':cases}
    P.write(P.OUT / 'independent_audit.json',audit)
    counts = {a:dict(Counter(t['cause'] for c in cases for t in c['arms'][a].get('source_evidence',[])
              if c['arms'][a].get('function_hit5') is False)) for a in P.ARMS}
    text = '# Rebench100定位失败：分类与逐题证据\n\n分类描述已记录的流程缺口，不自动等同于唯一根因；本轮没有对单个剪枝事件进行反事实重跑。函数NA与运行失败单列。\n\n'
    text += '```json\n'+json.dumps(counts,ensure_ascii=False,indent=2)+'\n```\n\n'
    for c in cases:
        if all(c['arms'][a].get('function_hit5') is True for a in P.ARMS): continue
        text += '## '+c['instance_id']+'\n\n'
        text += '金标既有目标：`'+json.dumps(c['gold_functions'],ensure_ascii=False)+'`。\n\n'
        for a in P.ARMS:
            v=c['arms'][a]; text += f"{a}：{v['status']}，Hit@5={v.get('function_hit5')}，路由={v.get('routes')}。\n\n"
            for e in v.get('source_evidence',[]): text += '- `'+e['identity']+'`：'+e['cause']+'；`'+json.dumps(e,ensure_ascii=False)+'`。\n'
            text += '\n原始Top5：`'+json.dumps(v.get('raw_top5',[]),ensure_ascii=False)+'`。\n\n'
    (P.DOCS / '定位失败分类与逐题分析.md').write_text(text)
    print(json.dumps({k:v for k,v in audit.items() if k not in ('cases','summary')},ensure_ascii=False,indent=2))
    if wire_errors or source_errors or routing_errors or any(integrity[k] for k in ('code_sha256','input_sha256','protected_sha256')) or not integrity['sealed_test_stat_unchanged']:
        raise RuntimeError('Independent audit findings require review; preserve all artifacts')
    return audit

def math_index(n,q):
    import math
    return min(n-1,max(0,math.ceil(n*q)-1))

if __name__ == '__main__': run()
