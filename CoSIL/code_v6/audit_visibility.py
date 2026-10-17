"""T0-a: full-source evidence diagnostics, without new labels or model inference."""
from collections import Counter, defaultdict
import csv
import json
import re
from pathlib import Path

from code_v5.metrics import _sources
from code_v5.verify_review_evidence import source_file
from code_v6.common import (ROOT, BASE, OUT, DOCS, INSTRUCTION, COHORTS, now, sha, digest,
                            read, rows, write, status, test_stats, historical_files, verify_files, pair)

LIMITS = [1500, 2048, 4096, 8192, 16384]
SYMPTOM_PATTERNS = {
    'traceback': r'Traceback \(most recent call last\)',
    'exception_name': r'\b[A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning)\b',
    'assertion': r'\bassert\b|AssertionError',
    'expected_actual_language': r'\b(?:expected|actual|instead|incorrect|wrong|fails?|failure)\b',
}


def edge_key(edge):
    return tuple(edge.get(k) for k in ['caller', 'callee', 'file', 'line', 'column', 'expression'])


def line_span(fn, absolute_line):
    lines = fn['source'].splitlines(keepends=True)
    i = absolute_line - fn['start_line']
    if not 0 <= i < len(lines):
        raise ValueError('Recorded callsite is outside its caller source')
    start = sum(map(len, lines[:i])); end = start + len(lines[i])
    return {'line_start_char': start, 'line_end_char': end, 'text': lines[i].rstrip('\r\n')}


def diagnose(fn, fid, evidence):
    internal, external = [], []
    for edge in evidence:
        if edge['caller'] == fid:
            internal.append({**edge, **line_span(fn, edge['line'])})
        elif edge['callee'] == fid:
            external.append(edge)
        else:
            raise ValueError('C witness does not involve the candidate')
    visible = any(e['line_end_char'] <= 1500 for e in internal)
    cause = 'visible' if visible else 'A_truncated_own_callsite' if internal else 'B_external_caller'
    return {'cause': cause, 'internal_calls': internal, 'external_calls': external,
            'also_external_relation': bool(external),
            'visible_by_function_limit': {str(n): any(e['line_end_char'] <= n for e in internal) for n in LIMITS},
            'full_source_visible': bool(internal)}


def neighbor_preview(fid, incoming, outgoing, functions, count=8):
    """Generic summaries select by stable graph order, never gold/label membership."""
    chosen = []
    for direction, edges in [('caller', incoming), ('callee', outgoing)]:
        # Bound by neighbor, retaining a reproducible first concrete callsite.
        seen = set()
        for e in sorted(edges, key=lambda x: (x[direction], x['file'], x['line'], x.get('column', 0))):
            other = e[direction]
            if other in seen: continue
            seen.add(other)
            if len(seen) > count: break
            chosen.append(e)
    lines = ['[Direct static call context; incomplete, not causal labels]']
    for e in chosen:
        witness = line_span(functions[e['caller']], e['line'])['text'].strip()[:160]
        lines.append(f"{e['caller']} -> {e['callee']} | {e['file']}:{e['line']} | {witness}")
    return '\n'.join(lines), {edge_key(e) for e in chosen}


def checks():
    fn = {'source': 'def f():\n    g()\n', 'start_line': 1}
    outgoing = {'caller': 'f', 'callee': 'g', 'file': 'a.py', 'line': 2, 'column': 4, 'expression': 'g'}
    assert diagnose(fn, 'f', [outgoing])['cause'] == 'visible'
    long_fn = {'source': 'def f():\n' + '    # x\n' * 300 + '    g()\n', 'start_line': 1}
    late = dict(outgoing, line=302)
    assert diagnose(long_fn, 'f', [late])['cause'] == 'A_truncated_own_callsite'
    inbound = dict(outgoing, caller='g', callee='f')
    assert diagnose(fn, 'f', [inbound])['cause'] == 'B_external_caller'
    both_fn = {'source': 'def f():\n    g()\n' + '    # x\n' * 300 + '    g()\n', 'start_line': 1}
    assert diagnose(both_fn, 'f', [outgoing, dict(outgoing, line=303)])['cause'] == 'visible'
    for action in [rows, read, sha]:
        try: action(BASE / 'data_verified_plus_B_runtime_reviewed/pruner_test.jsonl')
        except PermissionError: pass
        else: raise AssertionError('Sealed test not rejected before opening')
    return ['own_call_visible', 'own_late_call_A', 'inbound_same_file_B',
            'any_visible_witness_suffices', 'test_decode_and_hash_refused']


def run():
    target = OUT / 'T0_visibility'
    target.mkdir(parents=True, exist_ok=False)
    before_tests = test_stats(); before_history = historical_files()
    source_paths = [INSTRUCTION, Path(__file__), ROOT/'code_v6/common.py',
                    BASE/'data_input_visibility_audit.json', ROOT/'code_v5/metrics.py',
                    ROOT/'code_v5/verify_review_evidence.py']
    source_paths += [directory/f'pruner_{split}.jsonl' for directory in COHORTS.values() for split in ['train','val']]
    sources = {str(p): sha(p) for p in source_paths}
    cohorts = {}; grouped = defaultdict(list); issues_by_id = {}; issue_entries = []
    legacy = read(BASE/'data_input_visibility_audit.json')
    legacy_index = {pair(r): r for r in legacy['C_pair_details']}
    for cohort, directory in COHORTS.items():
        for split in ['train', 'val']:
            values = rows(directory/f'pruner_{split}.jsonl')
            assert all(r['split'] == split for r in values)
            assert len({pair(r) for r in values}) == len(values)
            cohorts[cohort, split] = values
            for r in values:
                iid = r['instance_id']
                if iid in issues_by_id:
                    assert issues_by_id[iid]['issue'] == r['issue'] and issues_by_id[iid]['base_commit'] == r['base_commit']
                else: issues_by_id[iid] = r
                if r['label'] and 'C' in _sources(r): grouped[iid].append((cohort, split, r))
    lite_path = ROOT.parent/'GraphLocator/datasets/swe_bench_lite.jsonl'
    official_path = BASE/'external_sources/verified_official/verified500_full_metadata.jsonl'
    official = {}
    for p in [lite_path, official_path]:
        sources[str(p)] = sha(p)
        for r in rows(p):
            if r['instance_id'] in issues_by_id:
                old = official.setdefault(r['instance_id'], r)
                assert old['problem_statement'] == r['problem_statement'] and old['base_commit'] == r['base_commit']
    assert set(official) == set(issues_by_id)
    for iid,r in issues_by_id.items():
        full = official[iid]
        assert full['base_commit'] == r['base_commit'] and full['repo'] == r['repo']
        assert full['problem_statement'][:2000] == r['issue']
    write(target/'start_receipt.json', {'started_at': now(), 'CPU_checks':checks(), 'sources':sources,
          'test_stat_only':before_tests, 'historical_sha256':before_history,
          'new_model_calls':0, 'new_training_or_labels':False})
    details = []; previews = []; graph_receipts = {}; graph_function_names = {}; gold_names = defaultdict(set)
    for cohort_values in cohorts.values():
        for r in cohort_values:
            if r['label'] and _sources(r)&{'A','B'}:
                gold_names[r['instance_id']].add(r['function_qualified_name'].rsplit('.',1)[-1])
    for i, (iid, members) in enumerate(sorted(grouped.items()),1):
        r = members[0][2]; gp = Path(r['graph']['graph_path'])
        actual_sha=sha(gp); assert actual_sha==r['graph']['graph_sha256']
        graph=read(gp); assert graph['base_commit']==r['base_commit'] and graph['instance_id']==iid
        graph_receipts[str(gp)]=actual_sha
        funcs={f['id']:f for f in graph['functions']}
        source_cache={}; hydrated={}
        class FullFunctions:
            def __getitem__(self, fid):
                if fid not in hydrated:
                    node=funcs[fid]
                    text,definitions,blob,matched=source_file(graph,node['file'],source_cache)
                    assert matched and definitions[node['qualified_name'],node['def_line']]==node['end_line']
                    full=''.join(text.splitlines(keepends=True)[node['start_line']-1:node['end_line']])
                    assert digest(full)==node['source_sha256'] and len(full)==node['source_characters']
                    assert full[:len(node['source'])]==node['source']
                    hydrated[fid]={**node,'source':full,'git_blob_sha1':blob}
                return hydrated[fid]
        full_functions=FullFunctions()
        graph_function_names[iid]={f['qualified_name'].rsplit('.',1)[-1] for f in graph['functions']}
        incoming=defaultdict(list);outgoing=defaultdict(list)
        for edge in graph['edges']:
            incoming[edge['callee']].append(edge);outgoing[edge['caller']].append(edge)
        edge_set={edge_key(e) for e in graph['edges']}
        for cohort,split,r in members:
            fn=full_functions[r['function_id']]
            assert digest(fn['source'])==r['full_function_source_sha256']==fn['source_sha256']
            assert fn['source'][:1500]==r['function']
            evidence=[]
            for item in r['provenance']:
                if item.get('source')=='C': evidence.extend(item['one_hop_call_edges'])
            evidence=list({edge_key(e):e for e in evidence}.values())
            assert evidence and all(edge_key(e) in edge_set for e in evidence)
            d=diagnose(fn,fn['id'],evidence)
            summary,chosen=neighbor_preview(fn['id'],incoming[fn['id']],outgoing[fn['id']],full_functions)
            _,chosen16=neighbor_preview(fn['id'],incoming[fn['id']],outgoing[fn['id']],full_functions,16)
            original=legacy_index.get(pair(r))
            if cohort=='legacy_v1':
                assert original and original['full_function_sha256']==fn['source_sha256']
            original_hidden=original is not None and not any(e['candidate_input_callsite_visibility']=='visible_complete_line' for e in original['edges'])
            d.update(cohort=cohort,split=split,instance_id=iid,function_id=fn['id'],
                     full_function_characters=len(fn['source']),full_function_sha256=digest(fn['source']),
                     git_blob_sha1=fn['git_blob_sha1'],
                     graph_path=str(gp),graph_sha256=actual_sha,base_commit=graph['base_commit'],
                     legacy_hidden=original_hidden if cohort=='legacy_v1' else None,
                     neighbor8_characters=len(summary),
                     relation_in_generic_neighbor8=bool(chosen&{edge_key(e) for e in evidence}),
                     relation_in_generic_neighbor16=bool(chosen16&{edge_key(e) for e in evidence}),
                     external_caller_same_file=any(e['file']==fn['file'] for e in d['external_calls']))
            details.append(d)
            if cohort=='B' and split=='train' and d['cause']!='visible' and len(previews)<8:
                previews.append({'instance_id':iid,'function_id':fn['id'],'cause':d['cause'],
                                 'candidate_head':fn['source'][:500], 'summary':summary,
                                 'selection_rule':'first stable graph-order neighbors; no gold/label filtering'})
        if i%10==0 or i==len(grouped):
            progress={'time':now(),'stage':'full_source_audit','issues_completed':i,'issues_total':len(grouped),'C_rows':len(details),'test_decoded':False}
            status(target/'status.json',progress);print(json.dumps(progress),flush=True)
    for (cohort,split), values in cohorts.items():
        by_issue=defaultdict(list)
        for r in values:by_issue[r['instance_id']].append(r)
        for iid,members in sorted(by_issue.items()):
            full=official[iid]['problem_statement'];head=full[:2000];tail=full[2000:]
            head_names=set(re.findall(r'\b[A-Za-z_]\w*\b',head));tail_names=set(re.findall(r'\b[A-Za-z_]\w*\b',tail))
            known=graph_function_names.get(iid,set())
            evidence=[]
            for name,pattern in SYMPTOM_PATTERNS.items():
                match=re.search(pattern,tail,re.I)
                if match:
                    pos=2000+match.start()
                    evidence.append({'pattern':name,'absolute_char':pos,'matched':match.group(),
                                     'excerpt':full[max(2000,pos-80):pos+180]})
            issue_entries.append({'cohort':cohort,'split':split,'instance_id':iid,
                'full_characters':len(full),'truncated_2000':bool(tail),'fits_8000':len(full)<=8000,
                'full_issue_sha256':digest(full),'lost_gold_def_names':sorted((tail_names-head_names)&gold_names[iid]),
                'lost_known_function_names':sorted((tail_names-head_names)&known),
                'tail_file_tokens':sorted(set(re.findall(r'[\w./-]+\.py\b',tail))-set(re.findall(r'[\w./-]+\.py\b',head))),
                'tail_diagnostic_clues':evidence,
                'symptom_semantics':'mechanical diagnostic clues only; not a human-certified complete symptom label'})
    summary={}
    for (cohort,split),values in cohorts.items():
        ds=[d for d in details if d['cohort']==cohort and d['split']==split]
        issues=[d for d in issue_entries if d['cohort']==cohort and d['split']==split]
        hidden=[d for d in ds if d['cause']!='visible']
        old_hidden=[d for d in ds if d['legacy_hidden']]
        summary[cohort+':'+split]={'pairs':len(values),'issues':len(issues),'C_pairs':len(ds),
           'causes':dict(Counter(d['cause'] for d in ds)),
           'legacy_hidden_count':len(old_hidden) if cohort=='legacy_v1' else None,
           'legacy_hidden_causes':dict(Counter(d['cause'] for d in old_hidden)) if cohort=='legacy_v1' else None,
           'hidden_also_has_external_relation':sum(d['also_external_relation'] for d in hidden),
           'B_external_same_file':sum(d['cause']=='B_external_caller' and d['external_caller_same_file'] for d in ds),
           'function_limit_recovery':{str(n):{'all_C_visible':sum(d['visible_by_function_limit'][str(n)] for d in ds),
             'originally_hidden_recovered':sum(d['visible_by_function_limit'][str(n)] for d in hidden),
             'plus_generic_neighbor8':sum(d['visible_by_function_limit'][str(n)] or d['relation_in_generic_neighbor8'] for d in ds),
             'plus_generic_neighbor16':sum(d['visible_by_function_limit'][str(n)] or d['relation_in_generic_neighbor16'] for d in ds)} for n in LIMITS},
           'issue_truncated':sum(d['truncated_2000'] for d in issues),
           'issue_tail_gold_name':sum(bool(d['lost_gold_def_names']) for d in issues),
           'issue_tail_known_function_name':sum(bool(d['lost_known_function_names']) for d in issues),
           'issue_tail_file_token':sum(bool(d['tail_file_tokens']) for d in issues),
           'issue_tail_diagnostic_clue':sum(bool(d['tail_diagnostic_clues']) for d in issues),
           'issue_fits_8000':sum(d['fits_8000'] for d in issues)}
    for split,count in [('train',521),('val',71)]:
        d=summary['legacy_v1:'+split]
        assert d['legacy_hidden_count']==count
        assert d['legacy_hidden_causes'].get('visible',0)==0, 'Legacy complete-line convention differs; investigate rather than silently replace'
    write(target/'C_pair_diagnostics.json',details)
    write(target/'issue_tail_diagnostics.json',issue_entries)
    write(target/'neighbor_format_examples.json',previews)
    for filename,values in [('C_pair_diagnostics.csv',details),('issue_tail_diagnostics.csv',issue_entries)]:
        with (target/filename).open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(values[0]));writer.writeheader()
            writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in d.items()} for d in values)
    verify_files(sources);verify_files(before_history)
    assert test_stats()==before_tests
    result={'completed_at':now(),'stage':'complete','summary':summary,'source_sha256':sources,
            'graph_sha256':graph_receipts,'test_stat_unchanged':True,'test_decoded_or_hashed':False,
            'historical_reports_and_matrix_unchanged':True,'new_model_calls':0,'new_labels_or_training':False,
            'definition':'A=own complete callsite line beyond prefix; B=call located in another function, possibly same file; input visibility is not causal label correctness',
            'neighbor_selection_uses_gold_or_labels':False}
    write(target/'audit.json',result);status(target/'status.json',{'time':now(),'stage':'complete','test_decoded':False})
    print(json.dumps({'completed':True,'summary':summary},ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    run()
