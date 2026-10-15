from copy import deepcopy
import fnmatch
import json
import os
import re

from llms import record
from prompts.search_agent_prompt import SearchNodeTool, SearchEdgeTool, FinishTool, IS_RELEVANT_INSTRUCTION
from utils.action import ActionType
from utils.action import IPythonRunCellAction
from utils.action_parser import ResponseParser
from utils.construct_graph import IncremantalRDFS
from utils.execute_search import string_distance, parse_search_expression
from qwen_adapt.common import batches, canonical, parse_json, relevance_values, token_count, render_elements
from qwen_adapt.transport import get_llm_response, request

TYPES = ['DIRECTORY','PACKAGE','FILE','CLASS','METHOD','FUNCTION','FIELD','VARIABLE','GLOBAL_VAR','BODY','*']
RELATIONS = ['ImportedBy','BaseClassOf','UsedBy','HasMember','ImplementedBy','Imports','*']
SEARCH_TASK = '''Localize the code that requires modification for this GitHub issue using the repository graph.
Use issue identifiers, exception names and relevant filenames as search keywords, one tool call at a time.
Use literal symbol names from the issue or observed source; do not invent a conceptual name such as constructor.
For a Python constructor issue, search the named class first; constructors are often __new__ or __init__.
If unsure of a symbol's type, use node_type * with that specific name. If no symbol is named, BODY can search a literal error-message keyword.
For CLASS/METHOD/FUNCTION queries use the declared simple symbol name, not a dotted module path; FILE names may include .py and BODY text may include dots.
Search exact symbol names first; METHOD and FUNCTION include Python methods and functions.
The wildcard * matches an arbitrary value; *name* matches names containing name.
BODY searches source text. Broad queries are paginated and have a documented processing budget;
use specific keywords to narrow an incomplete query. Use the actual tool parameter enums.
Use finish when the search is complete or no useful search keyword remains.
Never claim that an unexecuted search has returned source code.'''


def action_schema():
    branches = []
    node_args = {'node_type':{'type':'string','enum':TYPES},'node_name':{'type':'string','maxLength':256}}
    edge_args = {k:({'type':'string','enum':TYPES} if k.endswith('_type') and k != 'edge_type' else
        {'type':'string','enum':RELATIONS} if k == 'edge_type' else {'type':'string','maxLength':256})
        for k in ('src_node_type','src_node_name','edge_type','trg_node_type','trg_node_name')}
    for action,props in [('search_node',node_args),('search_edge',edge_args),('finish',{})]:
        branches.append({'type':'object','properties':{'action':{'type':'string','const':action},
            'arguments':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}},
            'required':['action','arguments'],'additionalProperties':False})
    return {'oneOf':branches}


def tools():
    values = deepcopy([SearchNodeTool, SearchEdgeTool, FinishTool])
    for tool in values:
        f = tool['function']
        f['description'] = f['description'].replace('UseBy', 'UsedBy')
        f['description'] += '\nEmbedded * in names is a glob pattern; broad queries are paginated. Use specific names.'
        for name, prop in f['parameters'].get('properties', {}).items():
            if name == 'node_type' or name.endswith('node_type'):
                prop['enum'] = TYPES
            elif name == 'edge_type':
                prop['enum'] = RELATIONS
    return values


def match_type(node, value):
    if value == '*':
        return True
    if value in ('METHOD', 'FUNCTION'):
        return str(node.type) in ('METHOD', 'FUNCTION')
    return str(node.type) == value


def match_name(node, value):
    if value == '*':
        return True
    if '*' in value:
        return fnmatch.fnmatchcase(node.name.lower(), value.lower())
    return node.name == value or node.name.split('.')[0] == value


def retrieve(graph, kind, arguments, top_k=5):
    if kind == 'search_node':
        if set(arguments) - {'node_type','node_name'}:
            raise ValueError('Unexpected search_node arguments')
        t, name = arguments.get('node_type','*'), arguments.get('node_name','*')
        if t not in TYPES or not isinstance(name,str) or not name or (t == name == '*'):
            raise ValueError('Provide a valid node type and at least one specific type or name')
        if t == 'BODY':
            if name == '*':
                raise ValueError('BODY requires a source-text keyword')
            candidates = [n for n in graph.nodes if match_type(n,'FUNCTION')]
            result = [n for n in candidates if name in (n.content or '')]
            if not result:
                result = sorted(candidates,key=lambda n:string_distance(n.content or '',name))[:top_k]
        else:
            candidates = [n for n in graph.nodes if match_type(n,t)]
            result = [n for n in candidates if match_name(n,name)]
            if not result and '*' not in name:
                result = sorted(candidates,key=lambda n:string_distance(n.name,name))[:top_k]
        return result, []
    keys = ('src_node_type','src_node_name','edge_type','trg_node_type','trg_node_name')
    if kind != 'search_edge' or set(arguments) - set(keys):
        raise ValueError('Invalid search tool or arguments')
    st, sn, relation, tt, tn = [arguments.get(k,'*') for k in keys]
    if st not in TYPES or tt not in TYPES or relation not in RELATIONS or not all(isinstance(n,str) and n for n in (sn,tn)):
        raise ValueError('Invalid node/edge enum or name')
    if all(x == '*' for x in (st,sn,relation,tt,tn)):
        raise ValueError('An edge query must have at least one specific argument')
    if tt == 'BODY' and relation == 'HasMember':
        if tn == '*':
            raise ValueError('BODY requires a source-text keyword')
        nodes = [n for n in graph.nodes if match_type(n,'FUNCTION') and match_name(n,sn) and tn in (n.content or '')]
        return nodes, [dict(source=n.name,target=n.name,relation='HasMember') for n in nodes]
    nodes, edges = [], []
    for source,target,data in graph.edges(data='relation'):
        r = data.relation.value
        if str(source.type) == 'VIRTUAL_CLASS':
            parents = list(graph.predecessors(source))
            if not parents:
                continue
            source = parents[0]
        if str(target.type) == 'VIRTUAL_CLASS':
            children = list(graph.neighbors(target))
            if not children:
                continue
            target = children[0]
        if match_type(source,st) and match_name(source,sn) and (relation == '*' or relation == r):
            if (tt == 'BODY' and (tn == '*' or tn in (target.content or ''))) or (match_type(target,tt) and match_name(target,tn)):
                nodes.extend((source,target))
                edges.append(dict(source=source.name,target=target.name,relation=r))
    return nodes, edges


class SearchAgent:
    def __init__(self, graph, registry, variant='B3', max_search_turn=5, top_k=5):
        self.repo_graph = IncremantalRDFS(graph)
        self.registry = registry
        self.variant = variant
        self.max_search_turn = max_search_turn
        self.top_k = top_k
        self.messages = []
        self.search_res = set()
        self.completed_queries = set()
        self.stop_reason = 'search_round_limit'

    def is_relevant(self, nodes, issue):
        items = [self.registry.describe(n) for n in nodes]
        self.registry.shown.update(i['node_id'] for i in items)
        if self.variant == 'B1':
            messages = [{'role':'user','content':IS_RELEVANT_INSTRUCTION},
                {'role':'user','content':'# Issue Description:\n'+issue+'\n### Code Elements List ###\n'+
                 '\n'.join(f'#Node {i+1}: '+n.to_json() for i,n in enumerate(nodes))}]
            self.registry.requested.update(i['node_id'] for i in items)
            raw = request(messages,role='relevance_legacy',limit=1024)[0][0].get('content') or ''
            blocks = ''.join(re.findall(r'```(?:\w+)?\n(.*?)\n```',raw,re.S))
            lines = blocks.splitlines()
            valid = len(lines) == len(nodes) and all(x.strip() in ('True','False') for x in lines)
            values = {item['node_id']:line.strip() == 'True' for item,line in zip(items,lines)} if valid else {}
            record('relevance_decisions',variant=self.variant,raw=raw,values=values,unknown=[i['node_id'] for i in items if i['node_id'] not in values],errors=[] if valid else ['Legacy boolean format/count mismatch'])
            return values
        remaining = {i['node_id']: i for i in items}
        values, all_errors = {}, []
        for attempt in range(2):
            schema = {'type':'object','properties':{'decisions':{'type':'array','items':{
                'type':'object','properties':{'node_id':{'type':'string','enum':list(remaining)},'is_relevant':{'type':'boolean'}},
                'required':['node_id','is_relevant'],'additionalProperties':False},'minItems':len(remaining),'maxItems':len(remaining)}},
                'required':['decisions'],'additionalProperties':False}
            messages = [{'role':'system','content':
                'Judge whether each code element is a cause of the issue. Return JSON decisions, exactly once for every given node_id. '
                'Use true for potentially relevant causes and false for irrelevant elements. No examples or explanations.'},
                {'role':'user','content':'Issue:\n'+issue+'\nCode elements:\n'+render_elements(list(remaining.values()))+
                 '\nCorrection errors: '+canonical(all_errors)}]
            self.registry.requested.update(remaining)
            raw = request(messages,schema=schema,role='relevance_json' if not attempt else 'relevance_repair',limit=1024)[0][0].get('content') or ''
            record('source_receipt',role='relevance',nodes=list(remaining.values()))
            try:
                partial, errors = relevance_values(parse_json(raw),set(remaining))
            except (ValueError,TypeError) as exc:
                partial, errors = {}, [str(exc)]
            values.update(partial)
            remaining = {k:v for k,v in remaining.items() if k not in partial}
            all_errors.extend(errors)
            record('relevance_attempt',attempt=attempt,raw=raw,values=partial,errors=errors,missing=list(remaining))
            if not remaining:
                break
        record('relevance_decisions',variant=self.variant,values=values,unknown=list(remaining),errors=all_errors)
        return values

    def run_search(self, action, issue):
        observation = {}
        try:
            name,args = parse_search_expression(action.code.strip('`'))
            nodes,edges = retrieve(self.repo_graph.repo_graph.graph,name,args,self.top_k)
            nodes = self.registry.sorted(nodes)
            record('search_query',name=name,arguments=args)
            record('search_matches',name=name,total_nodes=len(nodes),total_edges=len(edges),
                   matched_ids=[self.registry.id(n) for n in nodes])
            processed, accepted = [], []
            overhead = token_count(issue) + 1500
            page_limit = int(os.environ.get('GRAPHLOCATOR_SEARCH_PAGES','4'))
            for page,batch in enumerate(batches(nodes,self.registry,12000,overhead,role='search')):
                if page >= page_limit:
                    break
                items = [self.registry.describe(n) for n in batch]
                record('search_result',name=name,page=page,nodes=items)
                processed.extend(i['node_id'] for i in items)
                decisions = self.is_relevant(batch,issue) if len(nodes) >= self.top_k else {i['node_id']:True for i in items}
                for node in batch:
                    if decisions.get(self.registry.id(node)) is True:
                        self.search_res.add(node)
                        accepted.append(self.registry.describe(node))
                        self.repo_graph.incremental_add_dependency(node)
            self.registry.graph = self.repo_graph.repo_graph
            observation = dict(total_matches=len(nodes),processed_ids=processed,accepted=accepted,
                unprocessed_count=len(nodes)-len(processed),pagination_budget=page_limit)
            if name == 'search_node' and args.get('node_name') not in (None,'*'):
                exact = [n for n in self.repo_graph.repo_graph.graph.nodes if n.name == args['node_name']]
                observation['exact_name_available_types'] = sorted({str(n.type) for n in exact})
            record('search_page_summary',**observation)
            # Return only bounded source, but keep all processed decisions in trace.
            result_batches = list(batches([self.registry.nodes[i['node_id']] for i in accepted],
                self.registry,24000,token_count(issue)+1500,maximum=32,role='search_feedback'))
            shown = [self.registry.describe(n) for n in (result_batches[0] if result_batches else [])]
            observation['accepted'] = shown
            observation['accepted_omitted_from_main_feedback'] = len(accepted)-len(shown)
            self.registry.shown.update(i['node_id'] for i in shown)
        except (ValueError,TypeError,SyntaxError) as exc:
            observation = dict(error=str(exc),instruction='Correct the query parameters and use an actual enum or symbol name.')
            record('search_tool_error',error=type(exc).__name__,message=str(exc))
        feedback = {'content':canonical(observation)}
        if action.tool_call_id:
            feedback.update(role='tool',tool_call_id=action.tool_call_id,name=action.function_name)
        else:
            feedback['role'] = 'user'
        self.messages.append(feedback)

    def get_seed_location(self, issue):
        self.messages = [{'role':'system','content':SEARCH_TASK},{'role':'user','content':issue}]
        parser = ResponseParser()
        for turn in range(self.max_search_turn):
            record('search_round',turn=turn+1)
            active = deepcopy(self.messages)
            tool_indices = [i for i,m in enumerate(active) if m.get('role') == 'user' and m.get('content','').startswith('{"observation":')]
            for i in tool_indices[:-1]:
                try:
                    body = json.loads(active[i]['content'])
                    for item in body.get('observation',{}).get('accepted',[]):
                        item.pop('source',None)
                    active[i]['content'] = canonical(body)
                except (ValueError,TypeError,AttributeError):
                    pass
            record('search_history_compaction',old_tool_sources_removed=len(tool_indices[:-1]))
            active[0]['content'] = SEARCH_TASK + '\nReturn one JSON action with action and arguments. '\
                'Available tools: search_node(node_type,node_name), search_edge(src_node_type,src_node_name,edge_type,trg_node_type,trg_node_name), finish(). '\
                'Node types: '+','.join(TYPES)+'. Edge types: '+','.join(RELATIONS)+'. '\
                'Observe actual tool results; do not repeat a completed query without a specific reason.'
            value = None
            for attempt in range(2):
                response = request(active,schema=action_schema(),role='search_action' if not attempt else 'search_action_repair',limit=512)
                raw = response[0][0].get('content') or ''
                try:
                    value = parse_json(raw)
                    if not isinstance(value,dict) or value.get('action') not in ('search_node','search_edge','finish') or not isinstance(value.get('arguments'),dict):
                        raise ValueError('Expected a supported action and arguments object')
                    if value['action'] != 'finish' and canonical(value) in self.completed_queries:
                        raise ValueError('This identical query was already completed. Choose a new keyword/type/edge or finish; its actual result is in the observations.')
                    break
                except (ValueError,TypeError) as exc:
                    record('search_action_error',attempt=attempt,error=str(exc),raw=raw)
                    value = None
                    active.append({'role':'user','content':'Correct the action JSON: '+str(exc)})
            if value is None:
                self.stop_reason = 'unresolved_action'
                break
            self.messages.append({'role':'assistant','content':canonical(value)})
            if value['action'] == 'finish':
                self.stop_reason = 'model_finish'
                break
            code = 'print('+value['action']+'(**'+repr(value['arguments'])+', graph=graph))'
            action = IPythonRunCellAction(code=code,function_name=value['action'])
            self.run_search(action,issue)
            self.completed_queries.add(canonical(value))
            feedback = self.messages[-1]
            feedback['content'] = canonical({'observation':json.loads(feedback['content'])})
        if not self.search_res:
            self.stop_reason = 'empty_seeds:' + self.stop_reason
        return self.registry.sorted(self.search_res)
