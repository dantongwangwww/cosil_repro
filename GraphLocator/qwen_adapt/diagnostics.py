"""Post-hoc source provenance and pipeline loss analysis; no model calls."""
from collections import Counter
from ast import literal_eval
import json
from pathlib import Path
import re
import statistics
import networkx as nx

from qwen_adapt.evaluate import common_targets,source_function_keys
from qwen_adapt.runner import atomic


def function_keys(nodes,truth):
    return source_function_keys(nodes,truth['repo'],truth['base_commit'])


def analyze(folder, ids, gold, details, audits):
    per_issue = {}
    counts = Counter()
    totals = Counter()
    durations,probabilities,prediction_sizes,seed_sizes = [],[],[],[]
    for iid in ids:
        cp,fp=folder/'cases'/f'{iid}.json',folder/'failures'/f'{iid}.json'
        path=cp if cp.exists() else fp
        if not path.exists():
            counts['missing']+=1;continue
        case=json.loads(path.read_text());audit=audits[iid];detail=details[iid]
        events=[json.loads(line) for line in (folder/'events'/f'{iid}.jsonl').read_text().splitlines()]
        targets=common_targets(gold[iid])
        stages={
            'search_received':function_keys(audit['search_received_nodes'],gold[iid]),
            'seeds':function_keys(case.get('seed_locations',[]),gold[iid]),
            'causal_received':function_keys(audit['causal_received_nodes'],gold[iid]),
            'final':set(map(tuple,detail['strict_predictions']))}
        search_nodes={n['node_id']:n for n in audit['search_received_nodes']}
        role_function_counts={
            'main_search':len(function_keys([search_nodes[i] for i in audit['main_search_received_ids'] if i in search_nodes],gold[iid])),
            'relevance':len(function_keys([search_nodes[i] for i in audit['relevance_received_ids'] if i in search_nodes],gold[iid])),
            'causal':len(stages['causal_received'])}
        if detail['strict_predictions']:
            counts['function_predictions_with_no_main_function_source']+=role_function_counts['main_search']==0
            counts['function_predictions_with_no_causal_function_source']+=role_function_counts['causal']==0
        covered={stage:sorted(targets&nodes) for stage,nodes in stages.items()}
        for stage,hits in covered.items():
            if targets:
                counts[stage+'_any_target']+=bool(hits)
                counts[stage+'_all_targets']+=set(hits)==targets
        if not targets: reason='NA'
        elif case['status']=='failed':reason='运行失败'
        elif covered['final']:reason='最终覆盖全部目标' if set(covered['final'])==targets else '最终覆盖部分目标'
        elif covered['causal_received']:reason='因果收到目标实体但未保留'
        elif covered['search_received']:reason='搜索收到目标实体但未进入因果'
        else:reason='目标函数实体未送达模型'
        counts[reason]+=1
        counters=Counter(e['event'] for e in events)
        legacy_parses=sum(e['event']=='causal_parse' for e in events)
        if case.get('variant')!='B3':
            counts['legacy_actual_update_limit']+=legacy_parses>=22
            counts['legacy_causal_issues']+=1
            old=set();bad_bindings=0
            pattern=re.compile(r'(?P<source>\w+)\[(?P<name>[^<]+)<br>Code Elements: \[(?P<code>[^\]]*)\]\]\s*-->\|(?P<weight>[\d.]+)\|\s*(?P<target>\w+)(?:\[[^\]]*\])?')
            for event in events:
                if event['event']=='causal_context':
                    for line in (event.get('raw_response') or '').splitlines():
                        match=pattern.match(line.strip())
                        if not match or match['source'] in old or not match['code']:continue
                        try:
                            values=literal_eval('['+match['code']+']')
                            valid=all(type(i) is int and 1<=i<=len(event['nodes']) for i in values)
                        except (ValueError,SyntaxError,TypeError):valid=False
                        bad_bindings+=not valid
                elif event['event']=='causal_parse':old.update(event.get('new_factors',[]))
            totals['legacy_invalid_new_binding_rows']+=bad_bindings
            counts['issues_with_legacy_invalid_binding']+=bad_bindings>0
        for name,count in counters.items():totals[name]+=count
        unprocessed=sum(e.get('unprocessed_count',0) for e in events if e['event']=='search_page_summary')
        counts['issues_with_unprocessed_matches']+=unprocessed>0
        totals['unprocessed_matches_across_queries']+=unprocessed
        counts['issues_with_unknown_relevance']+=audit['unknown_relevance']>0
        counts['issues_with_causal_unresolved']+=counters['causal_unresolved']>0
        counts['issues_with_search_tool_error']+=counters['search_tool_error']>0
        counts['issues_with_search_action_error']+=counters['search_action_error']>0
        counts['causal_update_limit']+=case.get('causal_stop_reason')=='causal_update_limit'
        counts['empty_function_predictions']+=case['status']=='complete' and not detail['strict_predictions']
        prediction_sizes.append(len(detail['strict_predictions']));seed_sizes.append(len(case.get('seed_locations',[])))
        durations.append(case.get('seconds',0))
        graph=case.get('causal_graph',{});nodes=graph.get('nodes',[]);edges=graph.get('edges',[])
        association_counts=Counter(n['node_id'] for f in nodes for n in f.get('code_elements',[]))
        associated=[n for f in nodes for n in f.get('code_elements',[])]
        for n in associated:
            totals['association_type_'+str(n.get('type','UNKNOWN'))]+=1
            totals['associations_without_file']+=not bool(n.get('file'))
            totals['associations_without_source']+=not bool(n.get('source'))
        counts['issues_with_only_unlocated_associations']+=bool(associated) and not any(n.get('file') for n in associated)
        repeated=sum(n-1 for n in association_counts.values())
        counts['issues_with_duplicate_code_factors']+=repeated>0
        totals['duplicate_code_associations']+=repeated
        totals['causal_factors']+=max(0,len(nodes)-1)
        totals['causal_edges']+=len(edges)
        probabilities.extend(e['weight'] for e in edges)
        causal_network=nx.DiGraph((e['source'],e['target']) for e in edges)
        counts['issues_with_causal_cycles']+=not nx.is_directed_acyclic_graph(causal_network)
        per_issue[iid]=dict(reason=reason,coverage=covered,search_unprocessed_matches=unprocessed,
            event_counts=dict(counters),duplicate_code_associations=repeated,
            source_function_counts_by_role=role_function_counts,
            predicted_function_count=len(detail['strict_predictions']),seconds=case.get('seconds',0))
    def summary(values):
        return dict(total=sum(values),minimum=min(values),median=statistics.median(values),
            mean=statistics.mean(values),maximum=max(values)) if values else {}
    result=dict(counts=dict(counts),event_totals=dict(totals),seconds=summary(durations),
        seed_count=summary(seed_sizes),predicted_function_count=summary(prediction_sizes),
        causal_probabilities=summary(probabilities),coverage_definition='实际返回请求中显式函数节点与完整def源码的实体覆盖；函数身份以base commit源码AST及节点起始行还原，不靠真值补全输入节点名。类整体源码中的隐含方法未算作单独函数实体。',
        interpretation='语法/来源可靠性和语义正确性分别测量；概率是模型输出，不是校准置信度。')
    atomic(folder/'pipeline_diagnostics.json',result)
    atomic(folder/'pipeline_per_issue.json',per_issue)
    return result,per_issue
