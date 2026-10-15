"""Offline fixed-ID scoring; this module is never imported by inference workers."""
import argparse
import ast
from collections import Counter
from functools import lru_cache
import gzip
import json
from pathlib import Path
import re
import subprocess
import sys

from qwen_adapt.runner import ROOT,WORK,atomic

COSIL = ROOT.parent/'CoSIL'
sys.path.insert(0,str(COSIL))
from code_v3b.build_result_matrix import score as rank_score, normalize


def read_jsonl(path):
    return {r['instance_id']:r for r in (json.loads(t) for t in Path(path).read_text().splitlines() if t.strip())}


def raw_functions(row):
    if not row or row.get('status') == 'failed':
        return []
    result = []
    for file,values in row.get('found_related_locs',{}).items():
        for text in [values] if isinstance(values,str) else values:
            for line in text.replace('\\n','\n').splitlines():
                match = re.match(r'^\s*function\s*:\s*(.+)',line)
                if match:
                    name = match[1].strip().strip('`').split('(',1)[0].split('#',1)[0].strip()
                    if (file,name) not in result:
                        result.append((file,name))
    return result


@lru_cache(maxsize=4096)
def definitions(repo,commit,file):
    mirror = COSIL/'mirror_cache'/f'{repo.split("/")[-1]}.git'
    proc = subprocess.run(['git','--git-dir',str(mirror),'show',commit+':'+file],capture_output=True,text=True)
    if proc.returncode:
        return []
    try:
        tree = ast.parse(proc.stdout)
    except SyntaxError:
        return []
    result = []
    def visit(node,prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                name = prefix+child.name
                if not isinstance(child,ast.ClassDef):
                    result.append(dict(name=name,line=child.lineno,end=child.end_lineno))
                visit(child,name+'.')
            else:
                visit(child,prefix)
    visit(tree)
    return result


def resolve_prediction(repo,commit,file,name):
    options = definitions(repo,commit,file)
    exact = [n for n in options if n['name'] == name]
    if len(exact) == 1:
        return (file,name),'exact'
    if '.' not in name:
        leaf = [n for n in options if n['name'].rsplit('.',1)[-1] == name]
        if len(leaf) == 1:
            return (file,leaf[0]['name']),'unique_leaf'
        return (file,'<unresolved>:'+name),'ambiguous' if leaf else 'absent'
    return (file,'<unresolved>:'+name),'absent'


def source_function_keys(nodes,repo=None,commit=None):
    keys=set()
    for n in nodes:
        if n.get('type') not in ('METHOD','FUNCTION','CONSTRUCTOR') or not re.search(r'(?m)^\s*(?:async\s+)?def\s',n.get('source') or ''):
            continue
        name=n.get('qualified_name');file=n.get('file')
        if repo and commit and file:
            grounded=[d for d in definitions(repo,commit,file)
                if d['line']==n.get('start_line') and d['name'].rsplit('.',1)[-1]==n.get('name')]
            if len(grounded)==1:name=grounded[0]['name']
        keys.add((file,name))
    return keys


def common_targets(gold):
    result = set()
    for file,names in gold['gold_functions_by_file'].items():
        definitions_here = definitions(gold['repo'],gold['base_commit'],file)
        regions = [r for r in gold.get('existing_gold_function_regions',[]) if r['file']==file]
        for name in names:
            exact = [n for n in definitions_here if n['name']==name]
            if len(exact)==1:
                result.add((file,name)); continue
            candidates = [n for n in definitions_here if n['name'].rsplit('.',1)[-1]==normalize(name)]
            grounded = [n for n in candidates if any(r.get('def_line')==n['line'] for r in regions)]
            if grounded:
                result.update((file,n['name']) for n in grounded)
            elif len(candidates)==1:
                result.add((file,candidates[0]['name']))
            else:
                result.add((file,name))
    return result


def set_score(predicted,targets):
    if not targets:
        return None
    hit = len(set(predicted)&set(targets))
    p = hit/len(predicted) if predicted else 0.0
    r = hit/len(targets)
    return dict(precision=p,recall=r,f1=2*hit/(len(predicted)+len(targets)),sl=float(set(targets)<=set(predicted)),
        hits=hit,predictions=len(predicted),targets=len(targets))


def macro(values):
    valid = [v for v in values if v is not None]
    return dict(denominator=len(valid),**{k:sum(v[k] for v in valid)/len(valid) if valid else None for k in ('precision','recall','f1','sl')})


def native_metrics(native,gold,ids):
    return {key:macro([set_score(set(native.get(iid,{}).get(key,[])),set(gold[iid][key])) for iid in ids])
        for key in ('found_files','found_modules','found_functions')}


def common_metrics(records,gold,ids):
    details = {}
    for iid in ids:
        truth = gold[iid]
        row = records.get(iid)
        raw = raw_functions(row)
        predictions,ambiguities = set(),[]
        for file,name in raw:
            target,method = resolve_prediction(truth['repo'],truth['base_commit'],file,name)
            predictions.add(target)
            if method in ('ambiguous','absent'):
                ambiguities.append(dict(file=file,name=name,reason=method))
        targets = common_targets(truth)
        leaf_targets = {(file,normalize(name)) for file,names in truth['gold_functions_by_file'].items() for name in names}
        leaf_predictions = {(file,normalize(name)) for file,name in raw}
        ranks = rank_score(row,truth)
        details[iid] = dict(strict=set_score(predictions,targets),leaf=set_score(leaf_predictions,leaf_targets),
            strict_predictions=sorted(predictions),strict_targets=sorted(targets),unresolved=ambiguities,
            top1=ranks['top1'],top3=ranks['top3'],top5=ranks['top5'],state=ranks['state'])
    return dict(strict=macro([x['strict'] for x in details.values()]),leaf=macro([x['leaf'] for x in details.values()]),
        topk={f'top{k}':sum(bool(x[f'top{k}']) for x in details.values()) for k in (1,3,5)},
        missing=sum(x['state']=='missing' for x in details.values()),details=details)


def audit_case(folder,iid,case):
    ep = folder/'events'/f'{iid}.jsonl'
    events = [json.loads(t) for t in ep.read_text().splitlines()] if ep.exists() else []
    counters = Counter(e['event'] for e in events)
    tokens = Counter()
    roles = Counter()
    received,causal_received,search_received,main_received,relevance_received = {},{},{},{},{}
    invalid,unknown = 0,0
    factors = []
    for e in events:
        if e['event']=='model_response':
            tokens['input'] += e.get('usage',{}).get('prompt_tokens',0)
            tokens['output'] += e.get('usage',{}).get('completion_tokens',0)
            roles[e.get('caller','unknown')] += 1
            counters['output_length'] += sum(reason=='length' for reason in e.get('finish_reasons',[]))
        if e['event']=='relevance_decisions':
            unknown += len(e.get('unknown',[]))
        if e['event']=='causal_validation':
            invalid += len(e.get('errors',[]))
        if e['event']=='causal_context':
            for n in e.get('nodes',[]):
                causal_received[n['node_id']] = n
                # This event is emitted after a returned causal response, including
                # the legacy prompt that carries Node JSON without stable IDs.
                received[n['node_id']] = n
        if e['event']=='source_receipt':
            for n in e.get('nodes',[]):
                received[n['node_id']] = n
                search_received[n['node_id']] = n
                relevance_received[n['node_id']] = n
        if e['event']=='causal_parse' and e.get('state'):
            factors = e['state']['factors']
    # Only submitted requests with successful returned responses count as actual receipt.
    successful = {e['request_id'] for e in events if e['event']=='model_response'}
    registry = list(case.get('node_registry',{}).values())
    collector = received
    def walk(value):
        if isinstance(value,dict):
            if 'node_id' in value and 'source' in value:
                received[value['node_id']] = value
                collector[value['node_id']] = value
            for child in value.values():
                walk(child)
        elif isinstance(value,list):
            for child in value:
                walk(child)
        elif isinstance(value,str):
            if value.startswith('{'):
                try:
                    walk(json.loads(value))
                except ValueError:
                    pass
            # B1 passes the original Node JSON in numbered source blocks. Only
            # parse actual returned requests and match the complete source and
            # location; a tool result event alone is not proof of model receipt.
            for match in re.finditer(r'#Node \d+:\s*',value):
                try:
                    node,_ = json.JSONDecoder().raw_decode(value[match.end():])
                except ValueError:
                    continue
                location = node.get('location') or {}
                for candidate in registry:
                    if (candidate.get('source') == node.get('content')
                            and candidate.get('name') == node.get('name')
                            and candidate.get('start_line') == location.get('start_line')
                            and candidate.get('end_line') == location.get('end_line')
                            and str(location.get('file_path','')).endswith('/'+candidate.get('file',''))):
                        received[candidate['node_id']] = candidate
                        collector[candidate['node_id']] = candidate
    for e in events:
        if e['event']=='model_request' and e['request_id'] in successful and e.get('prompt_file'):
            p = Path(e['prompt_file'])
            if p.exists():
                caller=e.get('caller','')
                collector = main_received if caller.startswith('search') else relevance_received if caller.startswith('relevance') else causal_received
                with gzip.open(p,'rt',encoding='utf8') as stream:
                    walk(json.load(stream)['messages'])
    search_received.update(main_received)
    search_received.update(relevance_received)
    final_functions = raw_functions(case)
    received_keys = {(n.get('file'),n.get('qualified_name')) for n in received.values()
        if n.get('type') in ('METHOD','FUNCTION','CONSTRUCTOR') and re.search(r'(?m)^\s*(?:async\s+)?def\s',n.get('source') or '')}
    received_keys |= source_function_keys(received.values(),case.get('repo'),case.get('base_commit'))
    no_receipt=[]
    for file,name in final_functions:
        resolved=(file,name)
        if case.get('repo') and case.get('base_commit'):
            resolved,_=resolve_prediction(case['repo'],case['base_commit'],file,name)
        if (file,name) not in received_keys and resolved not in received_keys:no_receipt.append((file,name))
    return dict(events=dict(counters),tokens=dict(tokens),calls_by_role=dict(roles),unknown_relevance=unknown,
        causal_validation_errors=invalid,received_nodes=list(received.values()),causal_received_nodes=list(causal_received.values()),
        search_received_nodes=list(search_received.values()),
        main_search_received_ids=sorted(main_received),relevance_received_ids=sorted(relevance_received),
        final_functions_without_source_receipt=no_receipt,factors=factors,
        zero_seeds=case.get('status')=='complete' and not case.get('seed_locations'),
        empty_native=case.get('status')=='complete' and not any(case.get('native_result',{}).values()))


def evaluate_folder(folder,ids):
    records,raw,native,audits = {},{},{},{}
    for iid in ids:
        path = folder/'cases'/f'{iid}.json'
        failure = folder/'failures'/f'{iid}.json'
        if path.exists() or failure.exists():
            case = json.loads((path if path.exists() else failure).read_text())
            records[iid] = case
            raw[iid] = case
            if case['status']=='complete':
                native[iid] = case['native_result']
            audits[iid] = audit_case(folder,iid,case)
    gold = json.loads((COSIL/'ground_truth_300.json').read_text())
    author = json.loads((ROOT/'datasets/swe_bench_lite_gt_entities_3levels.json').read_text())
    common = common_metrics(records,gold,ids)
    metrics = dict(issues=len(ids),completed=sum(r['status']=='complete' for r in records.values()),
        failed=sum(r['status']=='failed' for r in records.values()),missing=len(ids)-len(records),
        common={k:v for k,v in common.items() if k!='details'},native=native_metrics(native,author,ids),
        failure_types=dict(Counter(r.get('error') for r in records.values() if r['status']=='failed')),
        audit=dict(zero_seeds=sum(a['zero_seeds'] for a in audits.values()),empty_native=sum(a['empty_native'] for a in audits.values()),
            functions_without_source_receipt=sum(len(a['final_functions_without_source_receipt']) for a in audits.values()),
            tokens={kind:sum(a['tokens'].get(kind,0) for a in audits.values()) for kind in ('input','output')},
            calls=sum(sum(a['calls_by_role'].values()) for a in audits.values()),
            unknown_relevance=sum(a['unknown_relevance'] for a in audits.values()),
            causal_validation_errors=sum(a['causal_validation_errors'] for a in audits.values())))
    atomic(folder/'metrics.json',metrics)
    atomic(folder/'per_issue_analysis.json',{iid:dict(**common['details'][iid],audit=audits.get(iid)) for iid in ids})
    return metrics,common['details'],audits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder',type=Path,required=True)
    args = parser.parse_args()
    manifest = json.loads((args.folder.parent/'manifest.json').read_text())
    metrics,_,_ = evaluate_folder(args.folder,manifest['instances'])
    print(json.dumps(metrics,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
