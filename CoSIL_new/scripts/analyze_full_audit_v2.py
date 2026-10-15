"""Analyze the 300-case audited run without modifying inference or filtering accuracy."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import hashlib
import json
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'results/full'
DOCS = ROOT/'docs/qwen-300'
OLD = ROOT.with_name('CoSIL')


def load(path):
    return json.loads(Path(path).read_text())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def locations(row):
    result=[]
    for file, entries in row.get('found_related_locs', {}).items():
        for entry in [entries] if isinstance(entries,str) else entries:
            for line in entry.replace('\\n','\n').splitlines():
                match=re.match(r'\s*(function|class|variable):\s*(.+?)\s*$',line)
                if match:
                    item=(file,match[1],match[2].split('.')[-1].strip())
                    if item not in result:
                        result.append(item)
    return result


def raw_locations(text, files):
    result=[]
    for block in re.findall(r'<location>(.*?)</location>',text,re.S):
        f=re.search(r'<file>(.*?)</file>',block,re.S)
        name=re.search(r'<name>(.*?)</name>',block,re.S)
        kind=re.search(r'<type>(.*?)</type>',block,re.S)
        if not f or not name or (files and f.group(1).strip() not in files):
            continue
        k=kind.group(1).strip() if kind else 'function'
        if k not in ('function','class','variable'):k='function'
        item=(f.group(1).strip(),k,name.group(1).strip().split('.')[-1])
        if item not in result:result.append(item)
    return result


def verdict(text):
    match=re.search(r'```(?:.*?)\n(.*?)```',text,re.S)
    value=(match.group(1) if match else text).strip()
    return value if value in ('True','False') else 'unknown'


def ratio(n,d):
    return f'{n}/{d}（{n/d*100:.1f}%）' if d else 'NA'


def exact_p(wins,losses):
    n=wins+losses
    return min(1.,2*sum(math.comb(n,k) for k in range(min(wins,losses)+1))/2**n) if n else 1.


def main():
    sys.path.insert(0,str(ROOT))
    from datasets import load_from_disk
    manifest=load(WORK/'audit_manifest.json')
    for name,sha in manifest['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    gold=load(manifest['gold_file'])
    assert hashlib.sha256(Path(manifest['gold_file']).read_bytes()).hexdigest()==manifest['gold_sha256']
    data={row['instance_id']:row for row in load_from_disk(manifest['dataset'])}
    ids=manifest['instances']
    assert len(ids)==300 and set(data)==set(gold)==set(ids)
    old_metrics=load(OLD/'results/qwen_300/metrics.json')
    old_cases={arm:{row['instance_id']:row for row in old_metrics['cases'][arm]}
               for arm in ('off','on','shuffled')}
    histories={}
    for arm in old_cases:
        zero_delivered=zero_delivered_output=0
        for iid in ids:
            events=jsonl(OLD/'results/qwen_300/fixed'/arm/'events'/f'{arm}_{iid}.jsonl')
            no_delivery=not any(e['event']=='context_accept' for e in events)
            zero_delivered+=no_delivery
            zero_delivered_output+=no_delivery and not old_cases[arm][iid]['empty']
        histories[arm]=dict(function_top5=old_metrics['summary'][arm]['function_top5'],
            zero_source_output=sum(c['zero_source_queries'] and not c['empty'] for c in old_cases[arm].values()),
            zero_delivery=zero_delivered,zero_delivery_output=zero_delivered_output)
    cases=[]
    raw_rows={}
    traces={}
    for iid in ids:
        phase_rows={}
        phase_events={}
        phase_failure={}
        for phase in ('file','func'):
            cp=WORK/phase/'cases'/f'{iid}.json'
            fp=WORK/phase/'failures'/f'{iid}.json'
            ep=WORK/phase/'events'/f'{iid}.jsonl'
            assert cp.exists() or fp.exists(),(phase,iid,'never attempted')
            phase_rows[phase]=load(cp) if cp.exists() else {}
            phase_failure[phase]=load(fp) if fp.exists() else None
            phase_events[phase]=jsonl(ep)
            starts=sum(e['event']=='run_start' for e in phase_events[phase])
            ends=sum(e['event']=='run_end' for e in phase_events[phase])
            assert starts==1 and ends==(1 if cp.exists() else 0),(phase,iid,'mixed trace')
        f,g=phase_rows['file'],phase_rows['func']
        e=phase_events['func']
        predicted=locations(g)
        wanted={(file,'function',name.split('.')[-1])
                for file,names in gold[iid]['gold_functions_by_file'].items() for name in names}
        ranks=[i for i,item in enumerate(predicted[:5],1) if item in wanted]
        queries=[t for t in e if t['event']=='tool_request' and t['name']!='exit']
        reads=[t for t in e if t['event']=='tool_result' and t['usable_source']]
        deliveries=[t for t in e if t['event']=='context_delivery' and t['usable_source'] and t['scope']=='main']
        main_reads=[t for t in reads if t['scope']=='main']
        pruner_reads=[t for t in reads if t['scope']=='pruner']
        read_nodes={(node['file'],node['type'],node['name']) for t in deliveries for node in t['nodes']}
        final_functions=[item for item in predicted[:5] if item[1]=='function']
        not_read=[item for item in final_functions if item not in read_nodes]
        messages=[t for t in e if t['event']=='model_result']
        requests=[t for t in e if t['event']=='model_request']
        summary_requests=[t for t in requests if t['purpose']=='final_summary']
        native_turns=g.get('func_traj',{}).get('tool_trajs',[])
        no_call_stop=bool(native_turns) and not native_turns[-1].get('message',{}).get('tool_calls')
        explicit_exit=any(t['event']=='tool_request' and t['scope']=='main' and t['name']=='exit' for t in e)
        log_path=WORK/'func/localization_logs'/f'{iid}.log'
        log=log_path.read_text() if log_path.exists() else ''
        decision_counter=Counter()
        for t in messages:
            if t['purpose']=='pruner_verdict':
                decision_counter.update(verdict(str(reply.get('content') or '')) for reply in t['replies'])
        errors=[t for phase in phase_events.values() for t in phase if t['event']=='model_error']
        api_bad_context=[t for t in errors if any(word in t['message'].lower()
            for word in ('context length','maximum context','max_model_len','context window','too many tokens'))]
        tool_errors=[t for t in e if t['event']=='tool_exception' or
            t['event']=='tool_result' and t['name']!='exit' and not t['usable_source']]
        bad_prune=[t for t in e if t['event']=='prune_input' and t['name']!='exit' and not t['usable_source']]
        kept_bad=[t for t in e if t['event']=='prune_return' and t['name']!='exit'
                  and not t['original_usable'] and t['original_kept']]
        malformed_auto=[]
        for t in messages:
            if t['purpose'] not in ('search_tools','pruner_tools'):continue
            for reply in t['replies']:
                if not reply.get('tool_calls') and re.search(
                    r'"name"\s*:\s*"(?:get_code_of_class|get_code_of_class_function|get_code_of_file_function|exit)"',
                    reply.get('content') or ''):
                    malformed_auto.append(t)
        src_requests=Counter((t['scope'],t['name'],json.dumps(t['arguments'],sort_keys=True)) for t in queries)
        prompt_tokens=sum((t.get('usage') or {}).get('prompt_tokens',0) or 0 for t in messages)
        completion_tokens=sum((t.get('usage') or {}).get('completion_tokens',0) or 0 for t in messages)
        full_prompt=sum((t.get('usage') or {}).get('prompt_tokens',0) or 0
                        for ev in phase_events.values() for t in ev if t['event']=='model_result')
        full_completion=sum((t.get('usage') or {}).get('completion_tokens',0) or 0
                            for ev in phase_events.values() for t in ev if t['event']=='model_result')
        raw=g.get('func_traj',{}).get('response','')
        xml_order=raw_locations(raw,g.get('found_files',[]))
        record=dict(instance_id=iid,file_complete=bool(f),function_complete=bool(g),
            failures=phase_failure,function_scorable=bool(wanted),
            file_top1=any(file in gold[iid]['gold_files'] for file in f.get('found_files',[])[:1]),
            file_top3=any(file in gold[iid]['gold_files'] for file in f.get('found_files',[])[:3]),
            file_top5=any(file in gold[iid]['gold_files'] for file in f.get('found_files',[])[:5]),
            function_top1=bool(wanted) and any(rank<=1 for rank in ranks),
            function_top3=bool(wanted) and any(rank<=3 for rank in ranks),
            function_top5=bool(ranks),predictions=predicted,
            function_ap=sum(i/rank for i,rank in enumerate(ranks,1))/len(wanted) if wanted else None,
            function_rr=1/ranks[0] if ranks else 0,
            main_queries=sum(t['scope']=='main' for t in queries),
            pruner_queries=sum(t['scope']=='pruner' for t in queries),
            all_successful_source_reads=len(reads),main_successful_source_reads=len(main_reads),
            pruner_successful_source_reads=len(pruner_reads),main_source_deliveries=len(deliveries),
            nonempty_final=bool(predicted),
            no_any_source_output=bool(g) and bool(predicted) and not reads,
            no_main_source_output=bool(g) and bool(predicted) and not main_reads,
            no_main_delivery_output=bool(g) and bool(predicted) and not deliveries,
            final_summary_no_known_source=bool(summary_requests) and not summary_requests[-1]['known_source_shas_in_prompt'],
            explicit_exit=explicit_exit,no_native_call_stop=no_call_stop,
            zero_main_source_exit=not main_reads and (explicit_exit or no_call_stop),
            budget_stop='exceeds budget' in log,
            tool_errors=len(tool_errors),model_errors=len(errors),context_api_errors=len(api_bad_context),
            prune_input_errors=len(bad_prune),prune_kept_error_input=len(kept_bad),
            pruner_verdicts=dict(decision_counter),native_text_responses=len(malformed_auto),
            native_required_format_requests=sum(t.get('tool_choice')=='required' for t in requests),
            repeated_queries=sum(n-1 for n in src_requests.values()),
            function_model_requests=len(requests),function_prompt_tokens=prompt_tokens,
            function_completion_tokens=completion_tokens,all_phase_prompt_tokens=full_prompt,
            all_phase_completion_tokens=full_completion,
            final_functions_without_delivered_definition=not_read,
            parsed_order_differs_from_xml=xml_order!=predicted,
            top5_set_differs_from_xml=set(xml_order[:5])!=set(predicted[:5]))
        cases.append(record)
        raw_rows[iid]=phase_rows
        traces[iid]=phase_events
    nfunc=sum(c['function_scorable'] for c in cases)
    assert nfunc==293
    sums={key:sum(c[key] for c in cases) for key in (
        'file_complete','function_complete','file_top1','file_top3','file_top5',
        'function_top1','function_top3','function_top5','no_any_source_output',
        'no_main_source_output','no_main_delivery_output','final_summary_no_known_source',
        'zero_main_source_exit','budget_stop','tool_errors','model_errors','context_api_errors',
        'prune_input_errors','prune_kept_error_input','native_text_responses',
        'native_required_format_requests','repeated_queries','main_queries','pruner_queries',
        'all_successful_source_reads','main_successful_source_reads','pruner_successful_source_reads',
        'main_source_deliveries','function_model_requests','function_prompt_tokens',
        'function_completion_tokens','all_phase_prompt_tokens','all_phase_completion_tokens',
        'parsed_order_differs_from_xml','top5_set_differs_from_xml')}
    sums.update(function_cases=nfunc,empty_final=sum(c['function_complete'] and not c['nonempty_final'] for c in cases),
        final_function_unread_cases=sum(bool(c['final_functions_without_delivered_definition']) for c in cases),
        function_map=sum(c['function_ap'] or 0 for c in cases)/nfunc,
        function_mrr=sum(c['function_rr'] for c in cases if c['function_scorable'])/nfunc)
    decisions=Counter()
    for c in cases:decisions.update(c['pruner_verdicts'])
    sums['pruner_verdicts']=dict(decisions)
    pairs={}
    for arm in old_cases:
        valid=[c for c in cases if c['function_scorable']]
        wins=sum(c['function_top5'] and not old_cases[arm][c['instance_id']]['function_top5'] for c in valid)
        losses=sum(not c['function_top5'] and old_cases[arm][c['instance_id']]['function_top5'] for c in valid)
        pairs[arm]=dict(new_wins=wins,new_losses=losses,
            delta_percentage_points=(wins-losses)/nfunc*100,mcnemar_exact_p=exact_p(wins,losses))
    result=dict(summary=sums,cases=cases,historical=histories,paired=pairs,
                inference_manifest=manifest,generated_at=datetime.now().astimezone().isoformat())
    (WORK/'audit_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    DOCS.mkdir(parents=True,exist_ok=True)
    report='# 实验报告：新版 Qwen 300 题总表与问题检查\n\n'
    report+=f"生成：{result['generated_at']}。新版自行完成文件级与函数级各 300 个目标题，完整结果分别为 {sums['file_complete']}/300、{sums['function_complete']}/300。\n\n"
    report+='本轮使用 Qwen2.5-Coder-7B-Instruct、温度 0、65536 上下文及已部署的单次原生格式纠正适配；固定代码和输入哈希见 `results/full/audit_manifest.json`。单题验证不混入全量结果。\n\n'
    report+='## 一、定位结果\n\n| 阶段 | Top-1 | Top-3 | Top-5 | MAP@5 | MRR@5 |\n|---|---|---|---|---|---|\n'
    report+=f"| 新版文件级 | {ratio(sums['file_top1'],300)} | {ratio(sums['file_top3'],300)} | {ratio(sums['file_top5'],300)} | — | — |\n"
    report+=f"| 新版函数级 | {ratio(sums['function_top1'],293)} | {ratio(sums['function_top3'],293)} | {ratio(sums['function_top5'],293)} | {sums['function_map']:.4f} | {sums['function_mrr']:.4f} |\n\n"
    report+='真值来自同一 300 题 base_commit 与官方 patch/AST 校验表。函数评分保留文件身份、归一化叶方法名，按解析后推荐顺序跨文件展开前五个位置；类/变量仍占推荐位置，但不作为函数命中。无函数真值的 7 题为 NA。运行失败作为端到端未命中，同时单列，未伪造空成功结果。\n\n'
    report+='## 二、没有源码仍输出定位\n\n'
    report+='三种口径分别区分全体工具、主搜索工具和真正进入主搜索上下文的代码。所有“仍输出”要求该题具有完整且非空的解析定位结果。\n\n'
    report+='| 现象 | 题数 |\n|---|---|\n'
    for title,key in [('主搜索及 pruner 工具均未成功读取源码，仍输出定位','no_any_source_output'),
                      ('主搜索工具未成功读取源码，仍输出定位','no_main_source_output'),
                      ('搜索 agent 未收到任何可用工具源码，仍输出定位','no_main_delivery_output')]:
        report+=f'| {title} | {ratio(sums[key],300)} |\n'
    report+=f"\n主搜索未成功读取源码便显式 exit 或以无原生调用结束：{sums['zero_main_source_exit']} 题。预算停止：{sums['budget_stop']} 题。最终总结请求不含已知实际工具源码：{sums['final_summary_no_known_source']} 题，含空输出与失败尝试，不与“非空输出”混用。\n\n"
    report+='源码“未收到”以实际工具源码是否被送入主搜索对话为准；issue 自带的示例、模型已有知识和说明性文本不算工具读取。调查式 pruner 使用独立上下文，看到源码并不意味着主搜索 agent 看到。正常文本结束、剪枝拒绝和预算限制仍按部署版原行为保留；本轮没有强制所有最终推荐必须读取过源码。\n\n'
    report+='## 三、与已有旧版三臂对照\n\n| 运行 | 函数 Top-5 | 未读到任何源码仍输出 | 主搜索未接收源码仍输出 |\n|---|---|---|---|\n'
    for arm in histories:
        h=histories[arm]
        report+=f"| 旧版 {arm} | {ratio(h['function_top5'],293)} | {ratio(h['zero_source_output'],300)} | {ratio(h['zero_delivery_output'],300)} |\n"
    report+=f"| 新版当前部署 | {ratio(sums['function_top5'],293)} | {ratio(sums['no_any_source_output'],300)} | {ratio(sums['no_main_delivery_output'],300)} |\n\n"
    report+='旧版是已经完成的历史结果，新版函数级使用新版重新生成的文件候选。因此差异同时包含文件定位、原生调用、调查式 pruner、总结流程与格式适配的变化，不能单独归因为 pruner 或原生调用。\n\n'
    for arm,p in pairs.items():
        report+=f"- 新版对旧版 {arm}：独有命中/独有未命中 {p['new_wins']}/{p['new_losses']}，差值 {p['delta_percentage_points']:+.2f} 个百分点，McNemar 精确 p={p['mcnemar_exact_p']:.4f}。\n"
    report+='\n## 四、其他问题、探索与成本\n\n| 指标 | 观测值 |\n|---|---|\n'
    labels=[('主搜索源码请求','main_queries'),('pruner 侦查源码请求','pruner_queries'),
        ('主搜索成功源码读取','main_successful_source_reads'),('pruner 成功源码读取','pruner_successful_source_reads'),
        ('源码真正送入主搜索上下文','main_source_deliveries'),('工具查询错误或异常','tool_errors'),
        ('模型请求错误，含被上游捕获的错误','model_errors'),('其中上下文 API 错误','context_api_errors'),
        ('读取失败信息仍被交给 pruner 判相关性','prune_input_errors'),('失败信息被 pruner 原样保留','prune_kept_error_input'),
        ('返回伪调用文本而未返回结构化调用','native_text_responses'),('实际原生 required 格式纠正请求','native_required_format_requests'),
        ('重复源码请求','repeated_queries'),('最终包含未送入主上下文的函数定义','final_function_unread_cases'),
        ('XML 原始顺序与解析顺序不同','parsed_order_differs_from_xml'),('排序改变前五个位置的集合','top5_set_differs_from_xml'),
        ('完整但空的最终定位','empty_final')]
    for title,key in labels:report+=f'| {title} | {sums[key]} |\n'
    report+=f"\nPruner 判决：{dict(decisions)}。未知格式与 False 分开统计；部署代码对非 True 文本均按排除处理。\n\n"
    report+='“推荐函数未读”的操作口径是文件+叶定义名是否出现在实际送入主搜索的源码中；整类源码包含的方法计已读。同文件同名函数、旧语法导致 AST 解析失败等情况需要逐题核对，不能仅凭此指标断言模型凭空猜测。\n\n'
    report+='XML 解析按文件分组，会改变交错文件位置的输出顺序；主评分遵循实际解析结果，原始回答保留以便复核。这类排序差异与模型选择本身分开记录。\n\n'
    report+=f"函数阶段实际请求 {sums['function_model_requests']} 次，prompt/completion tokens={sums['function_prompt_tokens']}/{sums['function_completion_tokens']}；两个阶段全部成功响应合计 tokens={sums['all_phase_prompt_tokens']}/{sums['all_phase_completion_tokens']}。包含 pruner 侦查、判决及格式纠正；失败请求未返回 usage 的消耗不能计量。上游 `func_traj.usage` 不包括全部 pruner 请求，本报告使用独立请求事件汇总。\n\n"
    report+='## 五、300 题对照总表\n\n| 题目 | 新版文件 Top-5 | 新版函数 Top-5 | 全体工具源码读取 | 主搜索源码接收 | 旧 off/on/shuffled 函数 Top-5 |\n|---|---|---|---|---|---|\n'
    for c in cases:
        iid=c['instance_id'];old=' / '.join('✓' if old_cases[a][iid]['function_top5'] else '—' for a in old_cases)
        hit='NA' if not c['function_scorable'] else '✓' if c['function_top5'] else '—'
        report+=f"| {iid} | {'✓' if c['file_top5'] else '—'} | {hit} | {c['all_successful_source_reads']} | {c['main_source_deliveries']} | {old} |\n"
    report+='\n## 六、审计与局限\n\n正式输出和事件逐题保存，完成轨迹各一组 run_start/run_end，原始失败轨迹独立保留。使用当前部署版，含已公开的 Qwen 格式纠正；没有新增注释生成或重新运行旧版三臂。每题单次运行，不能替代全量重复，也不声称完全未经修改地复现论文。\n'
    (DOCS/'实验报告_新版Qwen300_总表.md').write_text(report)
    detail='# 实验报告：新版 Qwen 300 题逐题逐臂记录\n\n'
    detail+='本轮正式运行是新版一个条件的文件级与函数级各 300 题；旧 off/on/shuffled 为已完成的历史对照。原始回答、实际查询、源码交付、pruner 和 API 错误均按事件记录。\n\n'
    for index,c in enumerate(cases,1):
        iid=c['instance_id'];r=raw_rows[iid];ev=traces[iid]
        detail+=f'## {index}. {iid}\n\n'
        detail+='\n'.join('> '+line for line in data[iid]['problem_statement'][:2000].splitlines())+'\n\n'
        detail+='真值：`'+json.dumps({k:gold[iid].get(k) for k in ('gold_files','gold_functions_by_file','gold_classes_by_file','target_kind')},ensure_ascii=False)+'`\n\n'
        detail+='旧版历史三臂：'+json.dumps({a:{'function_top5':old_cases[a][iid]['function_top5'],
            'source_queries':old_cases[a][iid]['source_queries'],'zero_source_queries':old_cases[a][iid]['zero_source_queries']}
            for a in old_cases},ensure_ascii=False)+'\n\n'
        detail+='**新版文件级**：'+json.dumps(r['file'].get('found_files',[]),ensure_ascii=False)+'\n\n'
        detail+='原始文件级最终回答：\n\n````text\n'+r['file'].get('file_traj',{}).get('response','无完整输出')+'\n````\n\n'
        detail+='**新版函数级**：'+json.dumps({k:c[k] for k in ('function_complete','function_top5',
            'main_queries','pruner_queries','all_successful_source_reads','main_source_deliveries',
            'no_any_source_output','no_main_delivery_output','tool_errors','model_errors','budget_stop',
            'explicit_exit','no_native_call_stop','parsed_order_differs_from_xml')},ensure_ascii=False)+'\n\n'
        if any(c['failures'].values()):detail+='运行异常：\n\n````json\n'+json.dumps(c['failures'],ensure_ascii=False,indent=2)+'\n````\n\n'
        for t in ev['func']:
            if t['event'] in ('tool_request','tool_result','tool_exception','prune_input','prune_return',
                               'prune_error','context_delivery','model_error'):
                detail+='- '+t['event']+'：`'+json.dumps(t,ensure_ascii=False).replace('`','\\`')+'`\n'
        detail+='\n模型原始最终回答：\n\n````text\n'+r['func'].get('func_traj',{}).get('response','无完整输出')+'\n````\n\n'
        detail+='已解析定位输出：\n\n````json\n'+json.dumps(r['func'].get('found_related_locs'),ensure_ascii=False,indent=2)+'\n````\n\n'
        detail+='未在主搜索收到的源码定义中观察到的前五位置函数：`'+json.dumps(c['final_functions_without_delivered_definition'],ensure_ascii=False)+'`\n\n'
    (DOCS/'实验报告_新版Qwen300_逐题逐臂.md').write_text(detail)
    print(json.dumps({'summary':sums,'reports':['实验报告_新版Qwen300_总表.md','实验报告_新版Qwen300_逐题逐臂.md']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
