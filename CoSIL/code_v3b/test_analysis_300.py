import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from code_v3b.analyze_experiment_300 import predictions,paired,contains_gold,ranking_metrics,legacy_metrics,direct_gold_available,issue_mentions
from code_v3b.build_ground_truth_300 import ast_boundaries


class AnalysisTests(unittest.TestCase):
    def test_literal_newlines_file_identity_and_order(self):
        result=predictions({'a.py':['function: C.foo()\\nfunction: bar\nclass: C'],
                            'b.py':['function: foo']})
        self.assertEqual(result,[('a.py','function','foo'),('a.py','function','bar'),
                                 ('a.py','class','C'),('b.py','function','foo')])

    def test_paired_discordant_counts(self):
        left=[{'function_scorable':True,'function_top5':x} for x in [True,True,False,True]]
        right=[{'function_scorable':True,'function_top5':x} for x in [False,False,True,True]]
        result=paired(left,right)
        self.assertEqual((result['wins'],result['losses'],result['delta']),(2,1,.25))

    def test_getter_is_not_mistaken_for_changed_setter(self):
        code='class C:\n    @property\n    def value(self):\n        return 1\n    @value.setter\n    def value(self, x):\n        self.x = x\n'
        nodes=ast_boundaries(code)
        setter=[node for node in nodes if node['kind']=='function'][-1]
        row={'repo':'fixture','base_commit':'fixture'}
        gold={'existing_gold_function_regions':[dict(file='a.py',**setter)]}
        with patch('code_v3b.analyze_experiment_300.source_nodes',return_value=nodes):
            self.assertFalse(contains_gold(row,gold,{'tool':'get_code_of_class_function','arguments':['a.py','C','value']}))
            self.assertTrue(contains_gold(row,gold,{'tool':'get_code_of_class','arguments':['a.py','C']}))

    def test_rank_metrics_keep_file_and_count_multiple_targets(self):
        targets={('a.py','function','foo'),('a.py','class','C')}
        ranking=ranking_metrics([('b.py','function','foo'),('a.py','class','C'),('a.py','function','foo')],targets)
        self.assertFalse(ranking['top1'])
        self.assertTrue(ranking['top3'])
        self.assertAlmostEqual(ranking['ap'],(1/2+2/3)/2)
        self.assertEqual(ranking['rr'],.5)

    def test_legacy_denominator_includes_module_only_case(self):
        truth={'function-case':['a.py::foo'],'module-case':['settings.py']}
        outputs=[{'instance_id':'function-case','found_files':['a.py'],
                  'found_related_locs':{'a.py':['function: foo']}},
                 {'instance_id':'module-case','found_files':['settings.py'],
                  'found_related_locs':{'settings.py':['variable: SETTING']}}]
        result=legacy_metrics(outputs,truth)
        self.assertEqual(result['function_level']['TOP 1'],50)
        self.assertEqual(result['file_level']['TOP 1'],100)

    def test_nested_function_in_candidate_file_is_not_a_direct_menu_node(self):
        nodes=ast_boundaries('def outer():\n    def inner():\n        return 1\n    return inner()\n')
        row={'repo':'fixture','base_commit':'fixture'}
        inner=next(node for node in nodes if node['name']=='outer.inner')
        outer=next(node for node in nodes if node['name']=='outer')
        with patch('code_v3b.analyze_experiment_300.source_nodes',return_value=nodes):
            self.assertFalse(direct_gold_available(row,{'existing_gold_function_regions':[dict(file='a.py',**inner)]},['a.py::outer']))
            self.assertTrue(direct_gold_available(row,{'existing_gold_function_regions':[dict(file='a.py',**inner)]},['a.py::inner']))
            self.assertTrue(direct_gold_available(row,{'existing_gold_function_regions':[dict(file='a.py',**outer)]},['a.py::outer']))

    def test_setter_is_not_directly_available_via_the_getter_node(self):
        code='class C:\n    @property\n    def value(self):\n        return 1\n    @value.setter\n    def value(self, x):\n        self.x = x\n'
        nodes=ast_boundaries(code)
        setter=[node for node in nodes if node['kind']=='function'][-1]
        row={'repo':'fixture','base_commit':'fixture'}
        with patch('code_v3b.analyze_experiment_300.source_nodes',return_value=nodes):
            self.assertFalse(direct_gold_available(row,{'existing_gold_function_regions':[dict(file='a.py',**setter)]},['a.py::C.value']))

    def test_backticked_call_does_not_hide_explicit_function_name(self):
        self.assertEqual(issue_mentions('`C.foo(x)` calls bar(y); inspect `_cstack` and `separability_matrix`.'),
                         {'foo','bar','_cstack','separability_matrix'})


if __name__=='__main__':unittest.main()
