import json
from pathlib import Path
import tempfile
import unittest

from specprune import evaluation as e
from specprune import sampling

ROOT = Path(__file__).resolve().parents[1]

class EvaluationTests(unittest.TestCase):
    def test_invalid_and_duplicate_positions_are_not_compacted(self):
        raw = [{'path':'p.py','qualified_name':'wrong'}, {'path':'p.py','qualified_name':'f'},
               {'path':'p.py','qualified_name':'f'}, {'path':'tests/t.py','qualified_name':'f'}]
        result = e.metrics(raw, ['p.py::f'], ['p.py::f', 'tests/t.py::f'], functions=True)
        self.assertEqual(result['slots'], [None, 'p.py::f', 'p.py::f', None])
        self.assertEqual(result['hit1'], 0)
        self.assertEqual(result['hit3'], 1)
        self.assertEqual(result['precision5'], .2)
        self.assertEqual(result['recall5'], 1)
        self.assertEqual(result['mrr10'], .5)
        self.assertEqual(e.slots([{'path':'../p.py','qualified_name':'f'}], ['../p.py::f'], functions=True), [None])

    def test_missing_and_failed_remain_in_fixed_denominator_na_does_not(self):
        records = [{'instance_id': 'one', 'arms': {'baseline': {'status':'error'}}}, {'instance_id':'two'}]
        gold = {'one':dict(status='COMPLETE_NONEMPTY',set_complete=True,targets=['p.py::f'],gold_files=['p.py']),
                'two':dict(status='COMPLETE_EMPTY',set_complete=True,targets=[],gold_files=['p.py'])}
        inv = {i:dict(function_identities=['p.py::f'],paths=['p.py']) for i in gold}
        r=e.evaluate(records,gold,inv,draws=40)['summary']
        self.assertEqual(r['function_denominator'],1)
        self.assertEqual(r['file_denominator'],2)
        self.assertEqual(r['metrics']['baseline']['function']['hit5'],0)
        self.assertEqual(r['statuses']['baseline'],{'error':1,'NOT_RUN':1})
        self.assertEqual(r['completed_only_secondary']['baseline']['function']['n'],0)
        with self.assertRaises(ValueError):
            e.evaluate(records,gold,{'one':inv['one']},draws=40)

    def test_macro_recall_and_precision_use_different_denominators(self):
        r=e.metrics(['a.py'],['a.py','b.py'],['a.py','b.py'],functions=False)
        self.assertEqual(r['precision5'],.2)
        self.assertEqual(r['recall5'],.5)
        self.assertEqual(r['all_coverage5'],0)
        self.assertAlmostEqual(r['f15'],2*.2*.5/.7)

    def test_paired_exact_statistics_and_empty(self):
        p=e.paired([1,0,0,1],[1,1,0,0],draws=40)
        self.assertEqual([p[k] for k in ('both_success','only_a','only_b','both_failure')],[1,1,1,1])
        self.assertEqual(p['exact_mcnemar_p'],1)
        self.assertEqual(e.paired([0]*6,[1]*6,draws=40)['exact_mcnemar_p'],.03125)
        self.assertEqual(e.wilson(0,0),[None,None])
        self.assertFalse(p['noninferiority_certified'])

    def test_sample_exact_frozen_100(self):
        frozen=json.loads((ROOT/'provenance/sampling_manifest.json').read_text())
        actual=sampling.manifest(frozen['rows'])
        self.assertEqual(actual['rows'],frozen['rows'])
        self.assertEqual(actual['selected_issue_ids'],frozen['selected_issue_ids'])
        self.assertEqual(len({r['repo'].casefold() for r in actual['rows'] if r['decision']=='selected'}),100)
        self.assertEqual(sampling.manifest(list(reversed(frozen['rows'])))['selected_issue_ids'],actual['selected_issue_ids'])
        with self.assertRaises(ValueError):
            sampling.select([frozen['rows'][0]]*2,n=1)

    @unittest.skipUnless((ROOT/'assets/evaluation/predictions.json').is_file(), 'Optional private offline assets absent')
    def test_paper100_raw_predictions_reproduce_frozen_metrics(self):
        path=ROOT/'assets/evaluation'
        read=lambda name:json.loads((path/name).read_text())
        r=e.evaluate(read('predictions.json'),read('gold.json'),read('inventory.json'),draws=40)
        expected=read('expected_metrics.json')
        self.assertEqual(r['summary']['complete_pairs'],99)
        self.assertEqual(r['summary']['function_denominator'],92)
        for arm in e.DEFAULT_ARMS:
            for unit in ('file','function'):
                for key,value in expected[arm][unit].items():
                    if not key.endswith('_ci95'):
                        self.assertAlmostEqual(r['summary']['metrics'][arm][unit][key],value,msg=f'{arm}/{unit}/{key}')
        p=r['summary']['paired_function_hit5']
        self.assertEqual([p[k] for k in ('both_success','only_a','only_b','both_failure')],[48,1,1,42])

if __name__=='__main__':
    unittest.main()
