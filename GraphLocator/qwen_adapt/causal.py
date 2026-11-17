import json
import networkx as nx
from llms import record
from qwen_adapt.common import batches, canonical, parse_json, token_count, render_elements
from copy import deepcopy
from qwen_adapt.transport import request

TASK = '''Analyze this issue and the supplied repository source to discover a causal issue graph.
Describe concrete causes specific to this issue, with a short source-grounded explanation.
Use at most one code_id for each factor. Never invent a code_id or treat a filename as a function body.
Code IDs are stable: keep an existing association unless you explicitly replace or clear it.
create makes a new factor; keep updates an existing factor without changing its code association;
replace updates an existing factor with the given code_id; clear removes its code association.
Use unique factor_id strings F1, F2, etc.; I represents the issue. Edges point from cause to effect,
with probability in [0,1]. Do not create extra factors when current factors already explain the issue.
Each factor's causes list gives target and probability; the edge source is that factor_id.
Targets must be I or an already existing factor, never the factor itself.
It is acceptable to return an empty factors list when the supplied source provides no justified cause.
Return only JSON with factors, each containing causes. Do not return a separate edges list, Mermaid or an example.'''


def schema(allowed, existing=()):
    value = {'type':'object','properties':{
        'factors':{'type':'array','maxItems':8,'items':{'type':'object','properties':{
            'factor_id':{'type':'string','pattern':'^F[0-9]{1,3}$'},
            'description':{'type':'string','maxLength':400},
            'association':{'type':'string','enum':['create','keep','replace','clear'] if existing else ['create']},
            'code_id':{'type':['string','null'],'enum':[None,*sorted(allowed)]},
            'evidence':{'type':'string','maxLength':400},
            'causes':{'type':'array','maxItems':4,'items':{'type':'object','properties':{
                'target':{'type':'string','enum':['I',*[f['factor_id'] for f in existing]]},
                'probability':{'type':'number','minimum':0,'maximum':1}},
                'required':['target','probability'],'additionalProperties':False}}},
            'required':['factor_id','description','association','code_id','evidence','causes'],'additionalProperties':False}}},
        'required':['factors'],'additionalProperties':False}
    original = value['properties']['factors']['items']
    existing_ids = [f['factor_id'] for f in existing]
    next_number = max((int(f[1:]) for f in existing_ids),default=0)+1
    new_ids = ['F'+str(i) for i in range(next_number,next_number+8)]
    creation = deepcopy(original)
    creation['properties']['factor_id'] = {'type':'string','enum':new_ids}
    creation['properties']['association'] = {'type':'string','const':'create'}
    creation['properties']['causes']['minItems'] = 1
    if existing_ids:
        updates = []
        for identity in existing_ids:
            branch = deepcopy(original)
            branch['properties']['factor_id'] = {'type':'string','const':identity}
            branch['properties']['association'] = {'type':'string','enum':['keep','replace','clear']}
            branch['properties']['causes']['items']['properties']['target'] = {
                'type':'string','enum':['I',*[f for f in existing_ids if f != identity]]}
            updates.append(branch)
        value['properties']['factors']['items'] = {'oneOf':[creation,*updates]}
    else:
        value['properties']['factors']['items'] = creation
    return value


def validate(value, old, allowed):
    errors = []
    if not isinstance(value,dict) or not isinstance(value.get('factors'),list):
        return ['Expected factors list with per-factor causes']
    ids = set(old) | {'I'}
    new_ids = set()
    for f in value['factors']:
        if not isinstance(f,dict):
            errors.append('Invalid factor object'); continue
        identity = f.get('factor_id')
        operation = f.get('association')
        code = f.get('code_id')
        if not isinstance(identity,str) or not identity.startswith('F') or not identity[1:].isdigit() or identity in new_ids:
            errors.append('Invalid/duplicate factor_id: '+str(identity)); continue
        new_ids.add(identity)
        if not isinstance(f.get('description'),str) or not f['description'].strip() or not isinstance(f.get('evidence'),str):
            errors.append('Missing description or evidence: '+identity)
        if operation == 'create':
            if identity in old:
                errors.append('Cannot create an existing factor: '+identity)
            if code is not None and code not in allowed:
                errors.append('New factors require a displayed code_id: '+identity)
        elif operation in ('keep','replace','clear'):
            if identity not in old:
                errors.append('Update refers to unknown factor: '+identity)
            if operation == 'replace' and code not in allowed:
                errors.append('Replacement requires displayed code_id: '+identity)
            if operation == 'clear' and code is not None:
                errors.append('Clear must use null code_id: '+identity)
            if operation == 'keep' and code is not None and code not in allowed:
                errors.append('Keep contains an undisplayed code_id: '+identity)
        else:
            errors.append('Invalid association operation: '+str(operation))
        ids.add(identity)
        causes = f.get('causes')
        if not isinstance(causes,list):
            errors.append('Each factor needs a causes list: '+identity)
            continue
        if operation == 'create' and not causes:
            errors.append('A newly declared cause factor needs an outgoing causal edge: '+identity)
        for e in causes:
            if not isinstance(e,dict):
                errors.append('Invalid edge object'); continue
            probability = e.get('probability')
            if e.get('target') not in set(old)|{'I'} or e.get('target') == identity:
                errors.append('Unknown target or self edge')
            if type(probability) not in (float,int) or not 0 <= probability <= 1:
                errors.append('Invalid probability')
    return errors


class CausalAgent:
    def __init__(self, repo_graph, registry, max_turn=20):
        self.repo_graph = repo_graph
        self.registry = registry
        self.max_turn = max_turn
        self.causal_graph = nx.DiGraph()
        self.causal_graph.add_node('I',name='Issue',code_element=[])
        self.messages = []
        self.seen = set()
        self.stop_reason = 'not_started'

    def state(self):
        return {'factors':[dict(factor_id=k,description=v['name'],
            code_id=self.registry.id(v['code_element'][0]) if v['code_element'] else None,
            evidence=v.get('evidence','')) for k,v in self.causal_graph.nodes(data=True) if k != 'I'],
            'edges':[dict(source=a,target=b,probability=d.get('weight',0)) for a,b,d in self.causal_graph.edges(data=True)]}

    def apply(self, value):
        new, selected = [], []
        for f in value['factors']:
            identity, operation, code = f['factor_id'], f['association'], f['code_id']
            if operation == 'create':
                new.append(identity)
                self.causal_graph.add_node(identity,name=f['description'],evidence=f['evidence'],code_element=[])
            self.causal_graph.nodes[identity].update(name=f['description'],evidence=f['evidence'])
            if operation in ('create','replace'):
                previous = self.causal_graph.nodes[identity]['code_element']
                node = self.registry.nodes[code] if code is not None else None
                self.causal_graph.nodes[identity]['code_element'] = [node] if node is not None else []
                if node is not None:
                    selected.append(node)
                    if operation == 'replace' and previous != [node]:
                        new.append(identity)
            elif operation == 'clear':
                self.causal_graph.nodes[identity]['code_element'] = []
            for e in f['causes']:
                self.causal_graph.add_edge(identity,e['target'],weight=e['probability'])
        return new, selected

    def discover(self, issue, nodes, factor=None):
        items = [self.registry.describe(n) for n in nodes]
        current = self.state()
        allowed = self.seen | {i['node_id'] for i in items}
        errors = []
        for attempt in range(2):
            context = {
                'issue':issue,'existing_causal_graph':current,'factor_to_expand':factor,
                'validation_errors':errors,
                'initial_graph':not current['factors'],
                'association_rule':'Use create for new factors; use keep/replace/clear ONLY for factor IDs already in existing_causal_graph.',
                'next_new_factor_id':'F'+str(1+max((int(f[1:]) for f in self.causal_graph if f != 'I'),default=0))}
            instruction = TASK + '\nTrace source calls from symptom code into newly supplied neighbor source. '\
                'A function that merely delegates computation can be a symptom location; identify a deeper cause only if the supplied source supports it. '\
                'When refining a factor, new causes should associate with the relevant newly observed code, not automatically repeat the seed function. '\
                'Keep existing factors if justified; do not force a cause when evidence is absent. '\
                'Every newly created factor needs an outgoing edge to I (initial) or to an already existing factor (refinement). '
            messages = [{'role':'system','content':instruction},{'role':'user','content':canonical(context)+
                '\nNew code elements (complete source):\n'+render_elements(items)}]
            raw = request(messages,schema=schema(allowed,current['factors']),role='causal_json' if not attempt else 'causal_repair',limit=4096)[0][0].get('content') or ''
            self.messages.extend([*messages,{'role':'assistant','content':raw}])
            self.seen.update(i['node_id'] for i in items)
            self.registry.requested.update(i['node_id'] for i in items)
            record('causal_context',nodes=items,raw_response=raw,factor=factor,attempt=attempt)
            try:
                value = parse_json(raw)
                errors = validate(value,set(self.causal_graph.nodes)-{'I'},allowed)
            except (ValueError,TypeError) as exc:
                errors = [str(exc)]
            record('causal_validation',errors=errors,factor=factor,attempt=attempt)
            if not errors:
                new, selected = self.apply(value)
                record('causal_parse',vertices=self.causal_graph.number_of_nodes(),edges=self.causal_graph.number_of_edges(),
                    selected=[self.registry.describe(n) for n in selected],new_factors=new,state=self.state())
                return new, selected
        record('causal_unresolved',errors=errors,factor=factor)
        return [], []

    def generate_causal_graph(self, issue, seeds):
        if not seeds:
            self.stop_reason = 'empty_seeds'
            record('causal_stop',reason=self.stop_reason)
            return self.causal_graph
        visited, queue = set(), []
        overhead = token_count(issue) + 3000
        for page, batch in enumerate(batches(seeds,self.registry,48000,overhead,maximum=8,role='causal_initial')):
            if page >= 4:
                record('causal_page_limit',stage='initial',remaining_seed_count=len(seeds)-len(visited))
                break
            new,selected = self.discover(issue,batch)
            visited.update(self.registry.id(n) for n in selected)
            queue.extend(new)
        updates = 0
        expanded = set()
        while queue and updates < self.max_turn + 1:
            queue.sort(key=lambda f:(-max((d.get('weight',0) for _,_,d in self.causal_graph.out_edges(f,data=True)),default=0),f))
            factor = queue.pop(0)
            association = tuple(self.registry.id(n) for n in self.causal_graph.nodes[factor]['code_element'])
            expansion_key = (factor,association)
            if expansion_key in expanded:
                continue
            expanded.add(expansion_key)
            neighbors = []
            for node in self.causal_graph.nodes[factor]['code_element']:
                self.repo_graph.incremental_add_dependency(node)
                self.registry.graph = self.repo_graph.repo_graph
                graph = self.repo_graph.repo_graph.graph
                neighbors.extend(n for n in set(graph.predecessors(node)) | set(graph.successors(node)) if self.registry.id(n) not in visited)
            overhead = token_count(issue) + token_count(self.state()) + 3000
            for page,batch in enumerate(batches(neighbors,self.registry,48000,overhead,maximum=8,role='causal_neighbors')):
                if page >= 4 or updates >= self.max_turn + 1:
                    record('causal_page_limit',stage='neighbors',factor=factor,total_neighbors=len(neighbors))
                    break
                new,selected = self.discover(issue,batch,factor)
                updates += 1
                visited.update(self.registry.id(n) for n in selected)
                queue.extend(new)
        self.stop_reason = 'causal_update_limit' if queue else 'causal_queue_empty'
        if self.causal_graph.number_of_nodes() == 1:
            self.stop_reason = 'empty_causal_graph'
        elif not any(d['code_element'] for f,d in self.causal_graph.nodes(data=True) if f != 'I'):
            self.stop_reason = 'unassociated_causal_graph'
        record('causal_stop',reason=self.stop_reason,updates=updates)
        return self.causal_graph
