"""Read-only replay of two concrete legacy binding-loss conditions."""
from ast import literal_eval
from collections import Counter
import json
from pathlib import Path
import re

PATTERN=re.compile(r'(?P<source>\w+)\[(?P<name>[^<]+)<br>Code Elements: \[(?P<codes>[^\]]*)\]\]\s*-->\|(?P<weight>[\d.]+)\|\s*(?P<target>\w+)(?:\[[^\]]*\])?')


def scan(events):
    old=set();findings=[];counts=Counter()
    for event in events:
        if event['event']=='causal_context':
            introduced={};first_codes={}
            text=event.get('raw_response') or ''
            counts['responses_with_multiple_graph_headers']+=text.count('graph TD')>1
            for line in text.splitlines():
                match=PATTERN.match(line.strip())
                if not match:continue
                source,target=match['source'],match['target']
                if source not in old:
                    try:
                        values=literal_eval('['+match['codes']+']')
                        valid=all(type(i) is int and 1<=i<=len(event['nodes']) for i in values)
                    except (ValueError,SyntaxError,TypeError):values=[];valid=False
                    if valid and values and source in introduced:
                        kind='new_source_first_created_as_target' if introduced[source]=='target' else 'duplicate_new_source_binding_changed' if values!=first_codes.get(source,[]) else None
                        if kind:
                            findings.append(dict(kind=kind,factor=source,name=match['name'].strip(),
                                node_indices=values,nodes=[event['nodes'][i-1] for i in values]))
                            counts[kind]+=1
                    if source not in introduced:
                        introduced[source]='source';first_codes[source]=values if valid else []
                if target not in introduced:introduced[target]='target'
        elif event['event']=='causal_parse':old.update(event.get('new_factors',[]))
    return dict(counts=dict(counts),findings=findings)


def analyze(folder,ids):
    totals=Counter();affected=Counter();details={}
    for iid in ids:
        path=Path(folder)/'events'/f'{iid}.jsonl'
        if not path.exists():continue
        result=scan([json.loads(t) for t in path.read_text().splitlines() if t.strip()])
        details[iid]=result
        for k,v in result['counts'].items():totals[k]+=v;affected[k]+=v>0
    return dict(events=dict(totals),affected_issues=dict(affected),
        interpretation='Legacy parser keeps the first new source binding in each response. A node first introduced as an edge target is created with Issue/empty code attributes, and a later valid source declaration is ignored. Changed duplicate declarations likewise do not replace that first binding. These are parser facts, not estimated improvement from rerunning the algorithm.'),details
