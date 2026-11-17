import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import networkx as nx

from rdfs.dependency_graph.models.graph_data import Node, NodeType, Location
from qwen_adapt.common import Registry, relevance_values
from qwen_adapt.search import retrieve
from qwen_adapt.causal import validate, CausalAgent


class Regressions(unittest.TestCase):
    def setUp(self):
        self.graph = nx.MultiDiGraph()
        self.root = Path('/tmp/synthetic_repo')
        self.first = Node(NodeType.FUNCTION,'parse_http_date',Location(self.root/'http.py',1,0,3,0),content='def parse_http_date(value):\n    return value\n')
        self.second = Node(NodeType.FUNCTION,'other',Location(self.root/'other.py',1,0,3,0),content='def other(value):\n    return value\n')
        self.graph.add_nodes_from([self.first,self.second,Node(NodeType.FILE,'date.py',Location(self.root/'date.py'))])
        self.dependency = SimpleNamespace(repo_path=self.root,graph=self.graph,get_membership_parent=lambda n:None)
        self.registry = Registry(self.dependency,'base-commit')

    def test_embedded_wildcard_does_not_select_short_filename(self):
        selected,_ = retrieve(self.graph,'search_node',dict(node_type='*',node_name='*parse_http_date*'))
        self.assertEqual(selected,[self.first])

    def test_missing_and_conflicting_boolean_ids_do_not_shift_other_answers(self):
        result,errors = relevance_values({'decisions':[
            {'node_id':'a','is_relevant':True},{'node_id':'b','is_relevant':False},
            {'node_id':'b','is_relevant':True},{'node_id':'c','is_relevant':'True'}]}, {'a','b','c','d'})
        self.assertEqual(result,{'a':True})
        self.assertTrue(errors)

    def test_valid_factor_rebinding_and_clear_use_stable_ids(self):
        agent = CausalAgent(SimpleNamespace(repo_graph=self.dependency),self.registry)
        a,b = self.registry.id(self.first),self.registry.id(self.second)
        creation = {'factors':[dict(factor_id='F1',description='specific cause',association='create',code_id=a,
            evidence='return value',causes=[dict(target='I',probability=0.8)])]}
        self.assertEqual(validate(creation,set(),{a,b}),[])
        agent.apply(creation)
        replacement = {'factors':[dict(factor_id='F1',description='revised cause',association='replace',code_id=b,evidence='return value',causes=[])]}
        self.assertEqual(validate(replacement,{'F1'},{a,b}),[])
        pending,selected = agent.apply(replacement)
        self.assertEqual(agent.causal_graph.nodes['F1']['code_element'],[self.second])
        self.assertEqual(pending,['F1'])
        self.assertEqual(selected,[self.second])
        replacement['factors'][0].update(association='clear',code_id=None)
        self.assertEqual(validate(replacement,{'F1'},{a,b}),[])
        agent.apply(replacement)
        self.assertEqual(agent.causal_graph.nodes['F1']['code_element'],[])

    def test_undisplayed_id_and_unknown_edge_are_rejected(self):
        value = {'factors':[dict(factor_id='F1',description='cause',association='create',code_id='Nwrong',evidence='evidence',
                 causes=[dict(target='F999',probability=1.2)])]}
        errors = validate(value,set(),set())
        self.assertGreaterEqual(len(errors),3)

    def test_empty_seed_does_not_invent_a_localization(self):
        agent = CausalAgent(SimpleNamespace(repo_graph=self.dependency),self.registry)
        result = agent.generate_causal_graph('A real issue',[])
        self.assertEqual(list(result.nodes),['I'])
        self.assertEqual(agent.stop_reason,'empty_seeds')

    def test_double_wildcard_is_an_explicit_query_error(self):
        with self.assertRaises(ValueError):
            retrieve(self.graph,'search_node',{'node_type':'*','node_name':'*'})

    def test_new_cause_without_causal_edge_is_not_a_complete_graph(self):
        identity = self.registry.id(self.first)
        value = {'factors':[dict(factor_id='F1',description='A source-specific cause',
            association='create',code_id=identity,evidence='return value',causes=[])]}
        self.assertTrue(any('outgoing causal edge' in e for e in validate(value,set(),{identity})))

    def test_stable_identity_is_not_batch_position(self):
        before = self.registry.id(self.first)
        self.registry.id(self.second)
        self.assertEqual(self.registry.id(self.first),before)
        self.assertNotEqual(before,self.registry.id(self.second))

    def test_incremental_newline_boundary_duplicate_keeps_entity_identity(self):
        old=Node(NodeType.CLASS,'InternalScale',Location(self.root/'scales.py',88,0,93,58),
            attribute={'uses':['set_major_formatter']},content='class InternalScale(Base):')
        new=Node(NodeType.CLASS,'InternalScale',Location(self.root/'scales.py',88,0,93,59),
            attribute={'uses':['set_major_formatter']},content=old.content)
        first=self.registry.id(old)
        self.assertEqual(first,self.registry.id(new))
        self.assertEqual(self.registry.nodes[first],new)
        self.assertEqual(first,self.registry.id(old))
        metadata=self.registry.describe(new)
        self.assertEqual((metadata['start_line'],metadata['end_line'],metadata['start_column']),(88,93,0))

    def test_different_start_columns_are_distinct_graph_entities(self):
        a=Node(NodeType.VARIABLE,'value',Location(self.root/'data.py',1,0,1,5),content='value')
        b=Node(NodeType.VARIABLE,'value',Location(self.root/'data.py',1,10,1,15),content='value')
        self.assertNotEqual(self.registry.id(a),self.registry.id(b))

    def test_conflicting_source_for_same_entity_is_not_silently_rebound(self):
        self.registry.id(self.first)
        conflict=Node(self.first.type,self.first.name,self.first.location,content='def parse_http_date(value):\n    return 0\n')
        with self.assertRaisesRegex(RuntimeError,'Conflicting source'):
            self.registry.id(conflict)


if __name__ == '__main__':
    unittest.main(verbosity=2)
