"""Consistency checks using only the paper's derived public artifacts."""
import csv
import importlib.util
import math
from pathlib import Path
import statistics
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('paper_analysis', ROOT/'scripts/analyze.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class DerivedStatisticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary=a.read(ROOT/'data/summary.json')
        cls.scores=a.load_scores()
        with (ROOT/'data/per_issue.csv').open(newline='',encoding='utf-8') as f:
            cls.issues=list(csv.DictReader(f))
        d=cls.summary['deployment']
        cls.replay=a.replay_thresholds(cls.scores,d['low'],d['high'])

    def test_scope_and_function_denominator(self):
        self.assertEqual(len(self.issues),100)
        self.assertEqual(len({r['repo'].casefold() for r in self.issues}),100)
        self.assertEqual(sum(r['function_scorable']=='True' for r in self.issues),92)
        self.assertEqual(sum(r['baseline_status']==r['hybrid_safe_status']=='complete' for r in self.issues),99)
        self.assertEqual(sum(r['gold_status']=='COMPLETE_EMPTY' for r in self.issues),8)

    def test_hit_and_recall_recompute_from_cases(self):
        eligible=[r for r in self.issues if r['function_scorable']=='True']
        for arm,expected in [('baseline',(36,47,49)),('hybrid_safe',(37,48,49))]:
            for k,n in zip((1,3,5),expected):
                self.assertEqual(sum(int(r[f'{arm}_function_hit{k}']) for r in eligible),n)
            actual=statistics.mean(float(r[f'{arm}_function_recall5']) for r in eligible)
            self.assertAlmostEqual(actual,self.summary['paired_summary']['metrics'][arm]['function']['recall5'])
        cells={key:0 for key in ((0,0),(0,1),(1,0),(1,1))}
        for r in eligible:
            cells[(int(r['baseline_function_hit5']),int(r['hybrid_safe_function_hit5']))]+=1
        self.assertEqual(cells,{(0,0):42,(0,1):1,(1,0):1,(1,1):48})

    def test_accounting_and_complete_pair_latency(self):
        complete=[r for r in self.issues if r['baseline_status']==r['hybrid_safe_status']=='complete']
        self.assertEqual(sum(int(r['baseline_main_tokens']) for r in self.issues),8313354)
        self.assertEqual(sum(int(r['hybrid_safe_main_tokens']) for r in self.issues),7309907)
        self.assertEqual(sum(int(r['baseline_file_tokens']) for r in self.issues),617293)
        self.assertEqual(sum(int(r['hybrid_comparable_tokens']) for r in self.issues),7927200)
        self.assertEqual(sum(int(r['hybrid_safe_local_input_tokens']) for r in self.issues),764211)
        for arm,key in [('baseline','baseline_seconds'),('hybrid_safe','hybrid_comparable_seconds')]:
            mean=statistics.mean(float(r[key]) for r in complete)
            self.assertAlmostEqual(mean,self.summary['complete99_resources'][arm]['mean_seconds'])

    def test_routing_replay_and_gold_coverage(self):
        deployed={r['population']:r for r in self.replay if r['deployed']}
        self.assertEqual([deployed['runtime'][key] for key in ('n','gold_n','retain','reject','defer','gold_rejected')],[652,73,219,104,329,0])
        self.assertEqual(self.summary['gold_visits']['unique_locally_scored'],57)
        self.assertEqual(sum(int(r['existing_target_count']) for r in self.issues),117)
        self.assertEqual(self.summary['gold_visits']['routes'],{'retain':60,'qwen':13})
        self.assertEqual(sum(r['count'] for r in self.scores if r['population']=='calibration'),487)

    def test_low_is_predecessor_of_minimum_calibration_gold(self):
        smallest=min(r['probability'] for r in self.scores if r['population']=='calibration' and r['gold_count'])
        self.assertEqual(math.nextafter(smallest,-math.inf),self.summary['deployment']['low'])
        at_point={r['population']:r for r in self.replay if r['low']==.6}
        self.assertEqual(at_point['calibration']['gold_rejected'],11)
        self.assertEqual(at_point['runtime']['gold_rejected'],4)
        self.assertTrue(all(r['positive_count'] is None for r in self.scores if r['population']=='runtime'))

    def test_monotonic_threshold_replay(self):
        for pop in ('calibration','runtime'):
            rows=[r for r in self.replay if r['population']==pop]
            for row in rows:
                self.assertEqual(row['retain']+row['reject']+row['defer'],row['n'])
            self.assertEqual(sorted(r['gold_rejected'] for r in rows),[r['gold_rejected'] for r in rows])
            self.assertEqual(sorted(r['automatic_fraction'] for r in rows),[r['automatic_fraction'] for r in rows])

    def test_failure_taxonomy_and_independent_audit(self):
        for arm in ('baseline','hybrid_safe'):
            self.assertEqual(sum(self.summary['failure_issue_counts'][arm].values()),43)
        audit=self.summary['audit']
        self.assertEqual(audit['requests_checked'],3440)
        self.assertEqual(audit['source_deliveries_checked'],4961)
        self.assertEqual(audit['base_spans_checked'],1409)
        self.assertEqual(audit['local_scores_checked'],652)
        self.assertEqual(audit['actual_batch_main_tokens'],15623261)
        for key in ('wire_errors','source_errors','routing_errors'):
            self.assertEqual(len(audit[key]),0)
        for key in ('unknown_usage','output_truncations'):
            self.assertFalse(audit[key])

if __name__=='__main__':
    unittest.main()
