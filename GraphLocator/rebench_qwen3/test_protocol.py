"""Synthetic CPU-only protocol/identity boundaries: no model or network."""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.error import URLError

import networkx as nx
from rebench_qwen3 import compat, transport


class Response:
    status=200
    def __init__(self,value): self.value=value
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def read(self): return json.dumps(self.value).encode()


def reply(content='OK'):
    return {'model':'qwen3-8b','choices':[{'message':{'role':'assistant','content':content},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':3,'total_tokens':13}}


class TransportTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):
        transport._state=None
        self.temp.cleanup()
    def setup(self,responses):
        self.payloads=[]
        def opener(request,timeout):
            self.payloads.append((request.full_url,json.loads(request.data),timeout))
            item=responses.pop(0)
            if isinstance(item,Exception): raise item
            return Response(item)
        return transport.configure(self.path,opener=opener)
    def test_endpoint_remote_credentials_and_wrong_model_rejected(self):
        for endpoint in ('https://api.deepseek.com/v1','http://user:pass@localhost:7353/v1','http://localhost/v1?key=x'):
            with self.assertRaises(ValueError): transport.configure(self.path,endpoint)
        with self.assertRaises(ValueError): transport.configure(self.path,model='llama3')
    def test_original_tuple_and_explicit_nonthinking_precise_tools_count(self):
        self.setup([{'count':200,'max_model_len':65536},reply()])
        tools=[{'type':'function','function':{'name':'finish'}}]
        decoded,reason,usage=transport.get_llm_response('ignored',[{'role':'user','content':'issue'}],True,tools)
        self.assertEqual(decoded[0]['content'],'OK');self.assertEqual(reason,['stop']);self.assertEqual(usage['total_tokens'],13)
        for _,payload,_ in self.payloads:
            self.assertEqual(payload['model'],'qwen3-8b');self.assertFalse(payload['chat_template_kwargs']['enable_thinking'])
            self.assertEqual(payload['tools'],tools)
        self.assertEqual(self.payloads[1][1]['max_completion_tokens'],8192)
        self.assertEqual(self.payloads[1][1]['temperature'],0)
        self.assertEqual([p[2] for p in self.payloads],[120,600])
        self.assertEqual(transport.summary_usage()['known_total_tokens'],13)
        self.assertTrue(list(self.path.glob('*_response.json.gz')))
    def test_relevance_schema_exact_n_with_identical_full_tokenize_and_generation_input(self):
        self.setup([{'count':200,'max_model_len':65536},reply('[true,false]')])
        messages=[{'role':'user','content':'issue full text\nfirst source\nsecond source'}]
        transport.get_llm_response('x',messages,relevance_count=2)
        schema=self.payloads[1][1]['response_format']
        self.assertEqual(schema,{'type':'json_schema','json_schema':{'name':'relevance_flags','strict':True,
            'schema':{'type':'array','items':{'type':'boolean'},'minItems':2,'maxItems':2}}})
        self.assertEqual(self.payloads[0][1]['messages'],messages)
        self.assertEqual(self.payloads[1][1]['messages'],messages)
        self.assertEqual(transport.summary_usage()['completion_requests'],1)
    def test_nonrelevance_request_has_no_schema_and_schema_never_applies_to_tools(self):
        self.setup([{'count':200,'max_model_len':65536},reply()])
        transport.get_llm_response('x',[{'role':'user','content':'Unchanged CIG Mermaid instruction'}])
        self.assertNotIn('response_format',self.payloads[1][1])
        before=len(self.payloads)
        with self.assertRaises(transport.ProtocolError):
            transport.get_llm_response('x',[],with_tool=True,tools=[],relevance_count=2)
        self.assertEqual(len(self.payloads),before)
    def test_output_shrinks_but_input_is_not_truncated(self):
        self.setup([{'count':60000,'max_model_len':65536},reply()])
        messages=[{'role':'user','content':'keep entire source'}]
        transport.get_llm_response('x',messages)
        self.assertEqual(self.payloads[1][1]['max_completion_tokens'],5472)
        self.assertEqual(self.payloads[1][1]['messages'],messages)
    def test_context_overflow_never_sends_generation(self):
        self.setup([{'count':65472,'max_model_len':65536}])
        with self.assertRaises(transport.ContextBudgetExceeded): transport.get_llm_response('x',[])
        self.assertEqual(len(self.payloads),1);self.assertEqual(transport.summary_usage()['http_attempts'],0)
    def test_one_transport_retry_preserves_unknown_receipt(self):
        self.setup([{'count':100,'max_model_len':65536},URLError('connection lost'),reply()])
        transport.get_llm_response('x',[])
        usage=transport.summary_usage()
        self.assertEqual(usage['http_attempts'],2);self.assertEqual(usage['completion_requests'],1)
        self.assertEqual(usage['unknown_usage_requests'],1);self.assertIsNone(usage['total_tokens'])
        self.assertEqual(usage['known_total_tokens'],13)
    def test_semantic_malformed_choice_is_not_resampled(self):
        self.setup([{'count':100,'max_model_len':65536},{'choices':[],'usage':reply()['usage']}])
        with self.assertRaises(transport.ProtocolError): transport.get_llm_response('x',[])
        self.assertEqual(len(self.payloads),2)
        self.assertEqual(transport.summary_usage()['known_total_tokens'],13)
    def test_unfinished_attempt_survives_worker_termination_as_unknown(self):
        self.setup([])
        transport.record('http_started',phase='generation',stem='00001_attempt_1')
        usage=transport.summary_usage(self.path)
        self.assertIsNone(usage['total_tokens']);self.assertEqual(usage['unknown_usage_requests'],1)
    def test_unparseable_tail_is_not_exact_zero_usage(self):
        self.setup([])
        (self.path/'events.jsonl').write_text('{"event":')
        self.assertIsNone(transport.summary_usage()['total_tokens'])


class BooleanTests(unittest.TestCase):
    def test_fenced_plain_and_json_booleans_keep_same_decisions(self):
        for text in ('True\nFalse','```\nTrue\nFalse\n```','[true,false]','```json\n[true,false]\n```'):
            self.assertEqual(compat.strict_booleans(text,2),[True,False])
    def test_ambiguous_wrong_count_and_nonbooleans_never_become_all_false(self):
        for text in ('True\nFalse\nTrue','[true]','[1,0]','True because important\nFalse','{"answer":[true,false]}',''):
            with self.assertRaises(compat.RelevanceFormatError): compat.strict_booleans(text,2)


class CompatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import causal_agent,search_agent,utils.execute_search
        cls.original_bytes={str(Path(m.__file__)):hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                            for m in (causal_agent,search_agent,utils.execute_search)}
        cls.receipt=compat.install_compat({})
    def node(self,kind,name,line,path='/source/file.py'):
        from rdfs.dependency_graph.models.graph_data import Node,NodeType,Location
        return Node(NodeType(kind),name,Location(Path(path),line,0,line+1,0),content=f'def {name}(): pass')
    def test_method_and_function_type_queries_search_both_existing_kinds(self):
        from utils.execute_search import search_node
        graph=nx.MultiDiGraph();graph.add_nodes_from([self.node('METHOD','f',2),self.node('FUNCTION','g',5)])
        for kind in ('METHOD','FUNCTION'):
            text=search_node(graph,kind,'*')
            self.assertIn('"name": "f"',text);self.assertIn('"name": "g"',text)
    def test_constructor_family_in_body_and_both_edge_endpoints_keeps_raw_types(self):
        from utils.execute_search import search_node,search_edge
        from rdfs.dependency_graph.models.graph_data import Edge,EdgeRelation
        constructor=self.node('CONSTRUCTOR','inner',7);method=self.node('METHOD','f',2)
        field=self.node('FIELD','field',10);klass=self.node('CLASS','C',1)
        graph=nx.MultiDiGraph();graph.add_nodes_from([constructor,method,field,klass])
        graph.add_edge(constructor,method,relation=Edge(EdgeRelation.UsedBy))
        for requested in ('FUNCTION','METHOD','CONSTRUCTOR'):
            text=search_node(graph,requested,'*')
            self.assertIn('"name": "inner"',text);self.assertIn('"name": "f"',text)
            self.assertNotIn('"name": "field"',text);self.assertNotIn('"name": "C"',text)
            edge=search_edge(graph,requested,'inner','UsedBy',requested,'f')
            pair=json.loads(edge)
            self.assertEqual(json.loads(pair['src_node'])['name'],'inner')
            self.assertEqual(json.loads(pair['trg_node'])['name'],'f')
        self.assertIn('"name": "inner"',search_node(graph,'BODY','inner'))
        self.assertEqual(str(constructor.type),'CONSTRUCTOR')
    def test_useby_typo_repaired_without_prompt_method_replacement(self):
        import search_agent
        self.assertNotIn("edge_type='UseBy'",search_agent.SearchEdgeTool['function']['description'])
        self.assertIn("edge_type='UsedBy'",search_agent.SearchEdgeTool['function']['description'])
    def test_relevance_keeps_same_issue_candidates_order_and_one_request(self):
        import search_agent
        agent=search_agent.SearchAgent.__new__(search_agent.SearchAgent)
        agent.model_name='qwen3-8b';agent.messages=[]
        candidates=['#Node 1: full source FIRST','#Node 2: full source SECOND']
        calls=[]
        def fake(model,messages,**kwargs):
            calls.append((model,copy.deepcopy(messages),kwargs))
            return ([{'content':'[true,false]'}],['stop'],{'total_tokens':10})
        namespace=search_agent.SearchAgent.is_relevant.__globals__
        with mock.patch.dict(namespace,{'get_llm_response':fake}):
            self.assertEqual(agent.is_relevant(candidates,'UNCHANGED ISSUE'),[True,False])
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][2]['relevance_count'],2)
        context=calls[0][1][-1]['content']
        self.assertIn('UNCHANGED ISSUE',context)
        self.assertIn('\n'.join(candidates),context)
        self.assertEqual(agent.messages,[])
        instruction=calls[0][1][-2]['content']
        self.assertIn('otherwise return **True**',instruction)
        self.assertNotIn('Results should be separated by new lines',instruction)
    def test_cig_runtime_patch_is_identical_to_frozen_v1(self):
        self.assertEqual(self.receipt['patches']['mermaid_target_placeholder_definition']['after'],
            '93a2da475255d1a10c8a27b94ddae0e3bb4de80398e24fc733ff6d55293e2c22')
        root=Path(__file__).resolve().parents[1]
        for name,expected in {
            'causal_agent.py':'40b57d637774054681278605277f78e2cf6ec9157a72f85ad88605de5a6604de',
            'prompts/causal_agent_prompt.py':'c5c886ac0824f58d23e9ec9b855566104925727873d8f2a63eaa1acb1869fc4a'}.items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),expected)
    def test_mermaid_target_then_definition_restores_exact_model_binding(self):
        import causal_agent
        agent=causal_agent.CausalAgent('local',None)
        a,b=self.node('FUNCTION','a',2),self.node('FUNCTION','b',5)
        text='B[Cause B<br>Code Elements: [2]] -->|0.8| A\nA[Cause A<br>Code Elements: [1]] -->|0.9| I[Issue]'
        graph,_,selected=agent.parse_mermaid_to_networkx(text,[a,b])
        self.assertEqual(graph.nodes['A']['name'],'Cause A')
        self.assertEqual(graph.nodes['A']['code_element'],[a])
        self.assertEqual(selected,[b,a])
    def test_mermaid_normal_binding_and_one_based_indices_unchanged(self):
        import causal_agent
        agent=causal_agent.CausalAgent('local',None);node=self.node('FUNCTION','f',2)
        graph,_,selected=agent.parse_mermaid_to_networkx('A[Cause<br>Code Elements: [1]] -->|0.9| I[Issue]',[node])
        self.assertEqual(graph.nodes['A']['code_element'],[node]);self.assertEqual(selected,[node])
        bad,_,_=agent.parse_mermaid_to_networkx('A[Cause<br>Code Elements: [0]] -->|0.9| I[Issue]',[node])
        self.assertEqual(bad.nodes['A']['code_element'],[])
    def test_exact_ast_nested_qname_preserves_order_and_no_class_expansion(self):
        graph=SimpleNamespace(repo_path=Path('/source'));cig=nx.DiGraph()
        c=self.node('CLASS','C',1);method=self.node('METHOD','f',2);nested=self.node('CONSTRUCTOR','inner',7)
        cig.add_node('B',code_element=[method,c,nested])
        inventory={'file.py':[{'kind':'class','qualified_name':'C','start_line':1,'end_line':4},
            {'kind':'function','qualified_name':'C.f','start_line':2,'end_line':3},
            {'kind':'function','qualified_name':'outer.inner','start_line':7,'end_line':8}]}
        value=compat.standardize_result({},graph,cig,inventory)
        self.assertEqual(value['found_entities'],['file.py::C.f','file.py::outer.inner'])
        self.assertEqual(value['found_modules'],['file.py::C'])
        self.assertEqual(value['found_files'],['file.py'])
    def test_unknown_or_ambiguous_function_stays_invalid_slot(self):
        graph=SimpleNamespace(repo_path=Path('/source'));cig=nx.DiGraph()
        wrong=self.node('FUNCTION','missing',2);right=self.node('FUNCTION','good',4)
        cig.add_node('A',code_element=[wrong,right])
        inv={'file.py':[{'kind':'function','qualified_name':'good','start_line':4,'end_line':5}]}
        value=compat.standardize_result({},graph,cig,inv)
        self.assertIn('unresolved_ast',value['found_entities'][0]);self.assertEqual(value['found_entities'][1],'file.py::good')
        self.assertEqual(value['identity_validation'][0]['status'],'invalid_ast_identity')
    def test_source_repo_name_in_path_is_not_redacted_or_globally_removed(self):
        node=self.node('FUNCTION','f',2,'/source/source/utils.py');cig=nx.DiGraph();cig.add_node('A',code_element=[node])
        inv={'source/utils.py':[{'kind':'function','qualified_name':'f','start_line':2,'end_line':3}]}
        value=compat.standardize_result({},SimpleNamespace(repo_path=Path('/source')),cig,inv)
        self.assertEqual(value['found_entities'],['source/utils.py::f'])
    def test_original_agent_files_are_byte_unchanged(self):
        for path,digest in self.original_bytes.items(): self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)


if __name__=='__main__': unittest.main()
