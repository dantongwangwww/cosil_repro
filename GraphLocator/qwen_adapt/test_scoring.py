import unittest
from unittest.mock import patch
from qwen_adapt.evaluate import set_score,macro,native_metrics,common_metrics


class ScoringChecks(unittest.TestCase):
    def test_multiple_targets_and_overprediction(self):
        value=set_score({'a','c','d'},{'a','b'})
        self.assertAlmostEqual(value['precision'],1/3)
        self.assertAlmostEqual(value['recall'],1/2)
        self.assertAlmostEqual(value['f1'],2/5)
        self.assertEqual(value['sl'],0)

    def test_f1_is_averaged_per_issue(self):
        value=macro([set_score({'a','b'},{'a'}),set_score({'a'},{'a','b'})])
        self.assertAlmostEqual(value['precision'],0.75)
        self.assertAlmostEqual(value['recall'],0.75)
        self.assertAlmostEqual(value['f1'],2/3)

    def test_failed_missing_and_na_are_not_excluded_as_successes(self):
        keys=['found_files','found_modules','found_functions']
        gold={iid:{k:[iid] for k in keys} for iid in ['good','failed']}
        gold['na']={k:[] for k in keys}
        predictions={'good':{k:['good'] for k in keys}}
        value=native_metrics(predictions,gold,['good','failed','na'])['found_functions']
        self.assertEqual(value['denominator'],2)
        self.assertEqual(value['recall'],0.5)

    def test_ambiguous_prediction_is_not_resolved_using_gold(self):
        gold={'iid':dict(repo='owner/project',base_commit='base',gold_functions_by_file={'x.py':['foo']},
            existing_gold_function_regions=[dict(file='x.py',def_line=10)])}
        rows={'iid':dict(instance_id='iid',status='complete',found_related_locs={'x.py':['function: foo']})}
        definitions=[dict(name='A.foo',line=10,end=15),dict(name='B.foo',line=20,end=25)]
        with patch('qwen_adapt.evaluate.definitions',return_value=definitions):
            value=common_metrics(rows,gold,['iid'])
        self.assertEqual(value['strict']['recall'],0)
        self.assertEqual(value['leaf']['recall'],1)
        self.assertEqual(value['details']['iid']['unresolved'][0]['reason'],'ambiguous')


if __name__=='__main__':
    unittest.main(verbosity=2)
