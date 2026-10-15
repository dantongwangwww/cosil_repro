"""Evidence-backed native and CoSIL-aligned evaluation; no inference edits."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import ast
import hashlib
import gzip
import importlib.util
import json
import math
import re
import statistics
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.with_name('CoSIL')
OUT = ROOT/'results/qwen_300'
FULL = OUT/'full'
DOCS = ROOT/'docs/qwen-300'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def pct(hit, den):
    return f'{hit}/{den}（{100*hit/den:.2f}%）' if den else 'NA'


def native_score(pred, gold, key):
    target = set(gold[key]); found = set(pred.get(key, [])); correct = target & found
    if not target:
        return None
    return dict(precision=len(correct)/len(found) if found else 0,
                recall=len(correct)/len(target),
                f1=2*len(correct)/(len(target)+len(found)),
                success_location=int(target <= found), any_hit=int(bool(correct)),
                gold_count=len(target), predicted_count=len(found), hits=sorted(correct))


def body(text):
    """Count a Python function with an executable/body line, not just a signature."""
    if not isinstance(text, str):
        return False
    try:
        tree=ast.parse(textwrap.dedent(text))
    except (SyntaxError,ValueError):
        return False
    return any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and bool(n.body) for n in ast.walk(tree))


def json_node_body(text, body_only=True):
    if not isinstance(text,str):return False
    for line in text.splitlines():
        start=line.find('{')
        if start<0:continue
        try:node,_=json.JSONDecoder().raw_decode(line[start:])
        except ValueError:continue
        if isinstance(node,dict):
            if str(node.get('type')) in ('FILE','DIRECTORY','REPO','PACKAGE','VIRTUAl_PACKAGE'):
                continue  # These nodes carry names, not file contents.
            content=node.get('content')
            if body(content) if body_only else isinstance(content,str) and bool(content.strip()):return True
    return False


def actual_prompt_sources(requests):
    flags={'main':False,'relevance':False,'causal':False,'main_any':False,'relevance_any':False,'causal_any':False}
    for event in requests:
        with gzip.open(event['prompt_file'],'rt',encoding='utf-8') as stream:prompt=json.load(stream)
        for message in prompt['messages']:
            text=message.get('content') or ''
            if event['caller']=='get_seed_location' and message.get('role')=='tool':
                flags['main']=flags['main'] or json_node_body(text)
                flags['main_any']=flags['main_any'] or json_node_body(text,False)
            if event['caller']=='is_relevant' and '### Code Elements List ###' in text:
                flags['relevance']=flags['relevance'] or json_node_body(text.split('### Code Elements List ###',1)[1])
                flags['relevance_any']=flags['relevance_any'] or json_node_body(text.split('### Code Elements List ###',1)[1],False)
            if event['caller']=='generate_causal_graph':
                for marker in ('# Code Element List:','# New Code Element List:'):
                    if marker not in text:continue
                    section=text.split(marker,1)[1].strip()
                    elements=ast.literal_eval(section)
                    assert isinstance(elements,list)
                    flags['causal']=flags['causal'] or any(json_node_body(element) for element in elements)
                    flags['causal_any']=flags['causal_any'] or any(json_node_body(element,False) for element in elements)
    return flags


def leaf(name):
    return name.rsplit('.', 1)[-1]


def source_key(node, repo_name):
    file = str(node.get('file') or node.get('location', {}).get('file_path') or '')
    prefix = f'/worktrees/{node.get("instance_id", "")}/'
    marker = '/'+repo_name+'/'
    if '/worktrees/' in file:
        file = file.split('/worktrees/', 1)[1].split('/', 2)[-1]
    elif marker in file:
        file = file.split(marker, 1)[-1]
    return file, leaf(node.get('name', ''))


def exact_test(a_only, b_only):
    n=a_only+b_only
    return min(1.0, 2*sum(math.comb(n, i) for i in range(min(a_only,b_only)+1))/2**n) if n else 1.0


def main():
    spec=importlib.util.spec_from_file_location('matrix', OLD/'code_v3b/build_result_matrix.py')
    matrix=importlib.util.module_from_spec(spec);spec.loader.exec_module(matrix)
    gold=read(OLD/'ground_truth_300.json')
    native_gold=read(ROOT/'datasets/swe_bench_lite_gt_entities_3levels.json')
    bugs={r['instance_id']:r for r in map(json.loads,(ROOT/'datasets/swe_bench_lite.jsonl').read_text().splitlines())}
    ids=read(OUT/'full_manifest.json')['instances']
    rows={r['instance_id']:r for r in map(json.loads,(FULL/'loc_results.jsonl').read_text().splitlines())}
    assert len(rows)==300 and set(ids)==set(rows)==set(gold)==set(native_gold)
    all_native=read(FULL/'loc_results.json')
    old_store=read(OLD/'results/comparison/逐题定位对照数据.json')
    historical={p['column']:p for p in old_store['projects'] if p['column'].startswith('CoSIL/')}
    prior_hashes={name:hashlib.sha256(json.dumps(p['records'],sort_keys=True,ensure_ascii=False).encode()).hexdigest() for name,p in historical.items()}
    cases={}; detail=[]
    for iid in ids:
        row=rows[iid];g=gold[iid];bug=bugs[iid];failed=row.get('status')=='failed'
        value=read(FULL/('failures' if failed else 'cases')/(iid+'.json'))
        events=[json.loads(t) for t in (FULL/'events'/(iid+'.jsonl')).read_text().splitlines()]
        responses=[e for e in events if e['event']=='model_response']
        requests=[e for e in events if e['event']=='model_request']
        queries=[e for e in events if e['event']=='search_query']
        contexts=[e for e in events if e['event']=='causal_context']
        parses=[e for e in events if e['event']=='causal_parse']
        nodes=[n for e in events if e['event']=='search_result' for n in e.get('nodes', [])]
        tool_body=any(body(n.get('content')) for n in nodes)
        tool_any=any(str(n.get('type')) not in ('FILE','DIRECTORY','REPO','PACKAGE','VIRTUAl_PACKAGE') and isinstance(n.get('content'),str) and bool(n['content'].strip()) for n in nodes)
        feedback_body=any(body(m.get('content')) for m in value.get('search_messages', []) if m.get('role')=='tool')
        # Tool bodies are JSON escaped, so decode each observation node before checking.
        for m in value.get('search_messages', []):
            if m.get('role')!='tool':continue
            for line in (m.get('content') or '').splitlines():
                try:feedback_body = feedback_body or body(json.loads(line).get('content'))
                except (ValueError,AttributeError):pass
        prompt_sources=actual_prompt_sources(requests)
        search_body=prompt_sources['main'];causal_body=prompt_sources['causal']
        target={(f,leaf(n)) for f,names in g['gold_functions_by_file'].items() for n in names}
        seed_nodes=value.get('seed_locations', [])
        seeds={source_key(n,bug['repo'].split('/')[-1]) for n in seed_nodes}
        seen_causal={source_key(n,bug['repo'].split('/')[-1]) for e in contexts for n in e['nodes']}
        common=matrix.score(row,g)
        ranks=[j for j,pos in enumerate(common['positions'],1) if pos['kind']=='function' and (pos['file'],pos['normalized_name']) in target]
        final_any=bool(ranks) if target else None
        files=row.get('found_files', []) if not failed else []
        native={key:native_score(all_native.get(iid, {}),native_gold[iid],key)
                for key in ('found_files','found_modules','found_functions')}
        invalid_ids=0; parsed_lines=0
        pattern=re.compile(r'\w+\[[^<]+<br>Code Elements: \[([^\]]*)\]\]\s*-->\|[\d.]+\|\s*\w+')
        for context in contexts:
            for match in pattern.finditer(context['raw_response'] or ''):
                parsed_lines+=1
                try:
                    members=ast.literal_eval('['+match[1]+']')
                    invalid_ids+=sum(not isinstance(n,int) or isinstance(n,bool) or not 1<=n<=len(context['nodes']) for n in members)
                except (ValueError,SyntaxError):invalid_ids+=1
        verts=value.get('causal_graph', {}).get('nodes', [])
        empty_factors=sum(not n['code_elements'] and n['id']!='I' for n in verts)
        has_output=bool(files or common['positions'])
        times=[datetime.fromisoformat(e['time']) for e in events]
        item=dict(instance_id=iid,repo=bug['repo'],status=row['status'],common=common,
            file_hits={f'top{k}':bool(set(files[:k]) & set(g['gold_files'])) for k in (1,3,5)},
            native=native,tool_any_source=tool_any,main_any_source=prompt_sources['main_any'],relevance_any_source=prompt_sources['relevance_any'],causal_any_source=prompt_sources['causal_any'],common_final_any_hit=final_any,first_target_rank=min(ranks,default=None),tool_function_body=tool_body,search_agent_function_body=search_body,tool_feedback_function_body=feedback_body,relevance_agent_function_body=prompt_sources['relevance'],
            causal_agent_function_body=causal_body,has_output=has_output,
            seed_gold_hit=bool(seeds & target) if target else None,
            causal_candidate_gold_hit=bool(seen_causal & target) if target else None,
            seed_count=len(seed_nodes),query_count=len(queries),model_calls=len(responses),
            format_retries=sum(e['event']=='native_format_retry' for e in events),tool_errors=sum(e['event']=='search_tool_error' for e in events),
            model_errors=sum(e['event']=='model_error' for e in events),length_finishes=sum('length' in e.get('finish_reasons',[]) for e in responses),
            input_tokens=sum(e.get('usage',{}).get('prompt_tokens',0) or 0 for e in responses),
            output_tokens=sum(e.get('usage',{}).get('completion_tokens',0) or 0 for e in responses),
            max_prompt=max([e.get('input_tokens',0) for e in requests],default=0),
            reduced_output_budgets=sum(e['max_output_tokens']<e['requested_output_tokens'] for e in requests),
            causal_rounds=max(0,len(contexts)-1),initial_cig_empty=bool(parses and parses[0]['vertices']==0),
            invalid_code_element_ids=invalid_ids,mermaid_matching_lines=parsed_lines,
            final_factor_count=len(verts)-int(any(n['id']=='I' for n in verts)),
            empty_association_factors=empty_factors,
            example_factor_copy=any(label in ((contexts[0]['raw_response'] or '') if contexts else '') for label in
                ('Inaccurate recursive check','Incorrect handling of commutative factors','Dependency on Product')),
            elapsed_seconds=(times[-1]-times[0]).total_seconds(),
            model_seconds=sum(e.get('seconds',0) for e in responses))
        cases[iid]=item
        conclusion=[]
        if failed:conclusion.append('运行失败，按对应有效真值计未命中，保留异常而非伪装空预测。')
        elif not common['positions']:conclusion.append('定位实体为空；文件输出见下方原生结果。')
        elif common['top5'] is True:conclusion.append('对齐口径函数 Top-5 命中。')
        elif target:
            if final_any:conclusion.append(f'目标函数在最终实体中，但首次位于第 {min(ranks)} 位，超出 Top-5。')
            elif item['seed_gold_hit']:conclusion.append('搜索种子已含目标函数，最终 Top-5 未保留该命中。')
            elif item['causal_candidate_gold_hit']:conclusion.append('因果扩展输入出现过目标函数，最终 Top-5 未命中。')
            else:conclusion.append('种子和已记录因果候选均未包含目标函数；当前可观察瓶颈在候选覆盖。')
        else:conclusion.append('无函数真值，函数指标为 NA。')
        if item['initial_cig_empty']:conclusion.append('初始因果图解析为空。')
        if invalid_ids:conclusion.append(f'检测到 {invalid_ids} 次越界或无效代码元素编号，已拒绝映射。')
        if item['example_factor_copy']:conclusion.append('初始回答出现提示词示例因子标签；这是输出观察，不能据此单独认定成败原因。')
        if has_output and not tool_body:conclusion.append('输出了定位，但查询工具未取到函数体。')
        if has_output and not search_body:conclusion.append('输出了定位，但主搜索模型实际输入未包含函数体（以压缩请求为准，而非仅凭 messages 缓冲区）。')
        if has_output and not causal_body:conclusion.append('输出了定位，但因果 agent 的候选输入未包含函数体。')
        d=[f'## {iid}', '', f"状态：{row['status']}；GPU {value.get('gpu')}；耗时 {item['elapsed_seconds']/60:.1f} 分钟；模型调用 {len(responses)} 次。", '',
            '### Issue', '', bug['problem_statement'], '',
            '### 真值与结果', '', '共同真值：', '```json',json.dumps({k:g[k] for k in ('gold_files','gold_functions_by_file','target_kind')},ensure_ascii=False,indent=2),'```', '',
            '仓库原生真值：', '```json',json.dumps(native_gold[iid],ensure_ascii=False,indent=2),'```','',
            '完整原生定位：','```json',json.dumps(all_native.get(iid,{}),ensure_ascii=False,indent=2),'```','',
            'Excel 中的实体顺序：','```json',json.dumps(row,ensure_ascii=False,indent=2),'```','',
            f"共同函数 Top1/3/5：{common['top1']} / {common['top3']} / {common['top5']}；文件 Top1/3/5：{list(item['file_hits'].values())}。",'',
            '### 过程与分析','', ' '.join(conclusion),'',
            f"函数体证据：工具提取={tool_body}；主搜索模型实际收到={search_body}；工具反馈已写入缓冲区={feedback_body}；相关性判别模型收到={prompt_sources['relevance']}；因果 agent 收到={causal_body}。类头/文件名不计作函数体。",'',
            f"种子 {len(seed_nodes)}；种子目标命中={item['seed_gold_hit']}；因果候选目标命中={item['causal_candidate_gold_hit']}；因果更新 {item['causal_rounds']} 次；最终空关联因子 {empty_factors} 个。",'',
            f"输入/输出 token：{item['input_tokens']} / {item['output_tokens']}；最长输入 {item['max_prompt']}；格式修复 {item['format_retries']}；请求错误 {item['model_errors']}。",'',
            '查询记录：','```json',json.dumps([{'name':e['name'],'arguments':e['arguments']} for e in queries],ensure_ascii=False,indent=2),'```','',
            '种子节点：','```json',json.dumps([{k:n.get(k) for k in ('name','type','file','start_line','end_line')} for n in seed_nodes],ensure_ascii=False,indent=2),'```','',
            '最终因果图节点和边：','```json',json.dumps(value.get('causal_graph',{}),ensure_ascii=False,indent=2),'```','',
            f"[原始记录](../../results/qwen_300/full/{'failures' if failed else 'cases'}/{iid}.json) · [请求/查询/候选轨迹](../../results/qwen_300/full/events/{iid}.jsonl) · [运行日志](../../results/qwen_300/full/logs/{iid}.log)",'']
        if failed:d.extend(['异常：','```text',value.get('traceback',row.get('message','')),'```',''])
        detail.extend(d)
    metrics=dict(issues=300,completed=sum(v['status']=='complete' for v in cases.values()),
        failed=sum(v['status']=='failed' for v in cases.values()),
        empty_entities=sum(v['status']=='complete' and not v['common']['positions'] for v in cases.values()))
    metrics['common_function']={f'top{k}':sum(v['common'][f'top{k}'] is True for v in cases.values()) for k in (1,3,5)}
    metrics['common_function']['any_hit']=sum(v['common_final_any_hit'] is True for v in cases.values())
    metrics['common_function']['denominator']=sum(v['common']['top5'] is not None for v in cases.values())
    metrics['common_file']={f'top{k}':sum(v['file_hits'][f'top{k}'] for v in cases.values()) for k in (1,3,5)}
    metrics['native']={}
    for key in ('found_files','found_modules','found_functions'):
        applicable=[v['native'][key] for v in cases.values() if v['native'][key] is not None]
        metrics['native'][key]={'denominator':len(applicable),**{name:sum(v[name] for v in applicable)/len(applicable) for name in ('precision','recall','f1','success_location','any_hit')}}
    metrics['audit']={key:sum(v[key] for v in cases.values()) for key in
        ('format_retries','tool_errors','model_errors','length_finishes','input_tokens','output_tokens','reduced_output_budgets','invalid_code_element_ids','empty_association_factors')}
    metrics['audit'].update({key:sum(v[key] for v in cases.values()) for key in ('initial_cig_empty','example_factor_copy')})
    metrics['audit']['output_without_tool_body']=sum(v['has_output'] and not v['tool_function_body'] for v in cases.values())
    metrics['audit']['output_without_search_body']=sum(v['has_output'] and not v['search_agent_function_body'] for v in cases.values())
    metrics['audit']['output_without_causal_body']=sum(v['has_output'] and not v['causal_agent_function_body'] for v in cases.values())
    metrics['audit']['feedback_written_but_main_not_received']=sum(v['has_output'] and v['tool_feedback_function_body'] and not v['search_agent_function_body'] for v in cases.values())
    metrics['audit']['output_without_any_search_model_body']=sum(v['has_output'] and not (v['search_agent_function_body'] or v['relevance_agent_function_body']) for v in cases.values())
    metrics['audit'].update(output_without_tool_any_source=sum(v['has_output'] and not v['tool_any_source'] for v in cases.values()),output_without_main_any_source=sum(v['has_output'] and not v['main_any_source'] for v in cases.values()),output_without_search_any_source=sum(v['has_output'] and not (v['main_any_source'] or v['relevance_any_source']) for v in cases.values()),output_without_causal_any_source=sum(v['has_output'] and not v['causal_any_source'] for v in cases.values()))
    metrics['audit']['maximum_prompt_tokens']=max(v['max_prompt'] for v in cases.values())
    metrics['timing']={'median_seconds':statistics.median(v['elapsed_seconds'] for v in cases.values()),
                       'summed_case_seconds':sum(v['elapsed_seconds'] for v in cases.values()),
                       'summed_model_seconds':sum(v['model_seconds'] for v in cases.values())}
    paired={}
    for name,project in historical.items():
        pairs=[(cases[i]['common']['top5'],matrix.score(project['records'][i],gold[i])['top5']) for i in ids if cases[i]['common']['top5'] is not None]
        a=sum(x and not y for x,y in pairs);b=sum(y and not x for x,y in pairs)
        paired[name]={'graphlocator_only':a,'cosil_only':b,'both_hit':sum(x and y for x,y in pairs),'both_miss':sum(not x and not y for x,y in pairs),'mcnemar_exact_p':exact_test(a,b)}
    metrics['paired_top5']=paired
    per_repo={}
    for repo in sorted({v['repo'] for v in cases.values()}):
        subset=[v for v in cases.values() if v['repo']==repo];valid=[v for v in subset if v['common']['top5'] is not None]
        per_repo[repo]={'n':len(subset),'function_n':len(valid),'function_top5':sum(v['common']['top5'] is True for v in valid),'failed':sum(v['status']=='failed' for v in subset)}
    metrics['per_repo']=per_repo
    save(OUT/'metrics.json',metrics);save(OUT/'per_issue_analysis.json',cases)
    m=metrics;a=m['audit'];den=m['common_function']['denominator']
    overview=['# GraphLocator + Qwen2.5-Coder-7B-Instruct：SWE-bench Lite 300 题总览','',
        f"实验完成 {m['completed']}/300；失败 {m['failed']}；成功运行但实体定位为空 {m['empty_entities']}。所有 300 题均有独立状态记录。",'',
        '## 定位结果与口径','',
        '| 对齐指标 | Top-1 | Top-3 | Top-5 |','|---|---:|---:|---:|',
        '| 文件（300题） | '+' | '.join(pct(m['common_file'][f'top{k}'],300) for k in (1,3,5))+' |',
        '| 函数（共同真值） | '+' | '.join(pct(m['common_function'][f'top{k}'],den) for k in (1,3,5))+' |','',
        '对齐评分直接调用 CoSIL 表格维护脚本：文件 + 函数末段名称匹配，类/变量占实体位置，按已有 Top-k 去重口径；失败计未命中，无函数真值计 NA。函数重载/同名方法依旧存在该共同评分口径的区分限制。GraphLocator 原生输出是集合，作者代码没有候选置信度排名；本表 Top-k 使用原生因果图遍历转实体后、按文件分组的记录顺序，属于兼容比较，不能称为论文原生 Top-k。','',
        '| 原生层级 | 有真值题数 | 宏平均 Precision | 宏平均 Recall | 宏平均 F1 | 全部目标覆盖 SuccLoc | 至少一目标命中 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for key,v in m['native'].items():overview.append('| '+key+' | '+str(v['denominator'])+' | '+' | '.join(f"{100*v[n]:.2f}%" for n in ('precision','recall','f1','success_location','any_hit'))+' |')
    overview.extend(['','原生指标按仓库自带 3 层级真值逐题去重并宏平均，SuccLoc 要求覆盖该题全部目标；不等于至少命中一个目标。原生函数真值与共同真值的适用题数不同，不能混用分母。 离线真值核验发现 47 题的函数目标集合不同（含适用题数差异）；其中 pytest-5413、pytest-5692 的作者函数真值使用单冒号且无仓库前缀，与其输出转换器的路径::函数格式不一致。原生评分逐字保留这些目标，不静默修正；共同评分另用已验证真值。详见 [真值差异审计](../../deployment/gold_alignment_audit.json)。','',
        '## 与历史 CoSIL 对照','', '| 实验列 | 函数 Top-1 | Top-3 | Top-5 |','|---|---:|---:|---:|'])
    for name,p in historical.items():
        scored=[matrix.score(p['records'][i],gold[i]) for i in ids]
        overview.append('| '+name+' | '+' | '.join(pct(sum(v[f'top{k}'] is True for v in scored),den) for k in (1,3,5))+' |')
    overview.append('| GraphLocator/Qwen | '+' | '.join(pct(m['common_function'][f'top{k}'],den) for k in (1,3,5))+' |')
    overview.extend(['', '框架、候选生成和输入源码范围均不同，这是同题同模型的复现对照，不能把差异归因于某个单独组件。单次温度 0 运行不能估计跨种子稳定性；多 GPU 的种子、权重和服务配置固定，额外保留副本一致性验证。',''])
    for name,p in paired.items():overview.append(f"与 {name} 配对 Top-5：GraphLocator 独有命中 {p['graphlocator_only']}，CoSIL 独有命中 {p['cosil_only']}，共同命中 {p['both_hit']}，共同未命中 {p['both_miss']}；双侧精确 McNemar p={p['mcnemar_exact_p']:.6g}。")
    overview.extend(['','## 源码与因果图审计','',
        f"输出定位但工具未提取任何节点源码：{a['output_without_tool_any_source']}；主搜索模型实际请求没有节点源码：{a['output_without_main_any_source']}；主搜索及相关性判别都没有节点源码：{a['output_without_search_any_source']}；因果模型没有节点源码：{a['output_without_causal_any_source']}。这里源码可含类头/变量赋值，下方再单独检查完整函数体。",'',
        f"输出定位但工具未获取函数体：{a['output_without_tool_body']} 题；主搜索模型实际请求未收到函数体：{a['output_without_search_body']} 题；因果 agent 候选未收到函数体：{a['output_without_causal_body']} 题。最后一轮工具返回可能写入 messages 但没有下一次主搜索模型调用，因此按真实请求核验。工具反馈写入但主模型未再次收到的题数 {a['feedback_written_but_main_not_received']}；主搜索与相关性模型都未收到函数体仍输出 {a['output_without_any_search_model_body']}。 只统计函数体，不把类定义头、文件名、变量节点算作函数源码；因而不能把这些计数直接称作模型完全没有任何代码。",'',
        f"初始因果图解析为空 {a['initial_cig_empty']} 题；初始回答包含提示词中预置的示例因子名称 {a['example_factor_copy']} 题；无效或越界代码元素编号 {a['invalid_code_element_ids']} 次；最终无代码关联因子总计 {a['empty_association_factors']}。这些为日志观察，不足以单独证明因果关系。",'',
        '生成和解析分开记录：模型文字可能描述了函数，但只有满足作者 Mermaid 行格式的因子和有效的 1-based Code Elements 编号才能进入定位；旧因子代码关联沿用原实现，既有因子不能直接通过新编号重绑定；初始解析为空时队列为空，推理立即结束。', '',
        '候选覆盖统计（共同函数真值）：', '',
        f"最终不限位置至少命中一个目标：{m['common_function']['any_hit']}/{den}；种子包含目标：{sum(v['seed_gold_hit'] is True for v in cases.values())}/{den}；因果候选输入出现目标：{sum(v['causal_candidate_gold_hit'] is True for v in cases.values())}/{den}。具体覆盖丢失位置逐题记录，真值仅用于离线审计，从未加入模型提示词。",'',
        '## 请求与运行成本','',
        f"输入 token 合计 {a['input_tokens']:,}，输出 {a['output_tokens']:,}；最长输入 {a['maximum_prompt_tokens']:,}；达到输出长度预算 {a['length_finishes']} 次；超出剩余上下文而下调输出预算 {a['reduced_output_budgets']} 次。未裁剪 issue 或函数源码。",'',
        f"工具格式重试 {a['format_retries']} 次；无效工具查询反馈 {a['tool_errors']} 次；记录的模型请求错误 {a['model_errors']} 次。各题耗时中位数 {m['timing']['median_seconds']/60:.1f} 分钟；题级耗时总和 {m['timing']['summed_case_seconds']/3600:.2f} 小时（并行执行，不等于墙钟）。模型请求耗时总和 {m['timing']['summed_model_seconds']/3600:.2f} 小时。",'',
        '## 按项目分布','', '| 项目 | 题数 | 函数适用 | 函数 Top-5 | 失败 |','|---|---:|---:|---:|---:|'])
    for repo,v in per_repo.items():overview.append(f"| {repo} | {v['n']} | {v['function_n']} | {pct(v['function_top5'],v['function_n'])} | {v['failed']} |")
    overview.extend(['','## 复现配置、部署问题与证据','',
        '上游仓库：[oceaneLIU/GraphLocator](https://github.com/oceaneLIU/GraphLocator)，固定提交 `2bb137cd946f0d29521d2277d6e0f636314e49c0`。模型实际为本地 Qwen2.5-Coder-7B-Instruct；API 名称 `llama3` 仅为当前服务兼容别名。所有 SearchAgent / relevance / CausalAgent 调用均经 localhost，未调用 OpenAI 或 Anthropic 外部模型。','',
        '非流式请求等待 1800 秒；OpenAI/LiteLLM SDK 隐式重试设为 0，只有带记录的外层传输重试。金丝雀曾观察到 600 秒超时后 SDK 重新生成同一请求，已修复并重新验证。保留作者搜索 5 轮、top_k=5 和因果 max_turn=20 参数；作者条件 `turn > max_turn` 实际最多 21 次更新，报告记录实际次数。固定温度 0、seed 0、PYTHONHASHSEED 0；最大输出 8192，服务上下文 65536。种子集合和邻居集合保留作者实现，不通过真值调整检索或推理。','',
        '独立 Python 3.11 客户端环境兼容旧 tree-sitter 插件；README 建议 3.13，该差异及依赖锁、实际版本、GPU/模型启动参数均留档。模型服务环境保持原有 CoSIL 配置。','',
        '金丝雀发现新建 Location 路径为字符串而反序列化为 Path，节点显示相同却不相等，已统一路径类型；无效工具参数改为工具错误反馈并在原轮数内继续搜索，失败验证原样保留。修复作者返回值元组与 `.choices` 解析不一致、工具参数转码、工具响应历史顺序、空结果、路径前缀/实体序列化/节点哈希修改、空出边优先级和无效编号映射。查询执行改为已声明图工具的字面量 AST 调用；Qwen 若只输出工具 JSON 文字，允许一次原生调用格式修复，作为模型协议适配记账。依赖图只读阶段改为每进程绑定一次图，等价边比较和耗时留档。','',
        '[部署与修复说明](部署与复现记录.md) · [完整补丁](../../deployment/local_changes.patch) · [金丝雀准入](../../results/qwen_300/canary_gate.json) · [正式版本清单](../../results/qwen_300/full_manifest.json) · [机器可读指标](../../results/qwen_300/metrics.json) · [逐题分析](实验报告_GraphLocator_Qwen300_逐题分析.md)','',
        '正式实验与金丝雀结果分开存储；失败、空预测和 NA 分别保留。Excel 以 issue ID 追加 GraphLocator/Qwen 列，保留原有 CoSIL/on、CoSIL/off 历史预测。',''])
    DOCS.mkdir(parents=True,exist_ok=True)
    (DOCS/'实验报告_GraphLocator_Qwen300_总览.md').write_text('\n'.join(overview))
    (DOCS/'实验报告_GraphLocator_Qwen300_逐题分析.md').write_text('# GraphLocator + Qwen：300 题逐题分析\n\n与总览使用同一共同真值及原生真值。True=命中，False=未命中，None=无函数真值 NA；诊断为可观察过程，未用真值指导推理。\n\n'+'\n'.join(detail))
    column=next((p for p in old_store['projects'] if p['column']=='GraphLocator/Qwen'),None)
    if column:
        assert column['source_sha256']==sha(FULL/'loc_results.jsonl'),'Existing historical column differs; refuse overwrite'
    else:
        subprocess.run([str(OLD.parent.parent/'miniconda3/envs/cosil/bin/python'),str(OLD/'code_v3b/build_result_matrix.py'),
            '--add','GraphLocator/Qwen','--input',str(FULL/'loc_results.jsonl'),'--model','Qwen2.5-Coder-7B-Instruct',
            '--description','GraphLocator原生图搜索与因果图推理；同题300；实体按原生遍历后按文件分组的顺序兼容Top-k，并非论文置信度排名'],check=True)
    after=read(OLD/'results/comparison/逐题定位对照数据.json')
    for name,digest in prior_hashes.items():
        p=next(p for p in after['projects'] if p['column']==name)
        assert hashlib.sha256(json.dumps(p['records'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()==digest
    save(OUT/'final_verification.json',{'issues':300,'unique_ids':300,'matrix_column':'GraphLocator/Qwen','prior_cosil_records_unchanged':True,'prior_record_sha256':prior_hashes,'results_sha256':sha(FULL/'loc_results.jsonl'),'reported_metrics':metrics,'timestamp':datetime.now().astimezone().isoformat()})
    print(json.dumps(metrics,ensure_ascii=False))


if __name__=='__main__':
    main()
