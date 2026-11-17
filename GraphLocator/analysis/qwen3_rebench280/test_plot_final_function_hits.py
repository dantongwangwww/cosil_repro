"""Synthetic CPU-only guard tests; no experimental data is opened."""
import copy
import tempfile
import unittest
from pathlib import Path
from plot_final_function_hits import ARMS, PROTOCOL_SHA256, EVALUATOR_SHA256, validate_summary, render


def fixture():
    metric = dict(n=280)
    for k, count in [(1, 70), (3, 112), (5, 140)]:
        metric.update({f'hit{k}_numerator':count, f'hit{k}':count/280,
                       f'hit{k}_ci95':[max(0,count/280-.1), min(1,count/280+.1)]})
    return dict(status='FINAL', scope='full280', allocated=280, terminal_tasks=280,
                pending_tasks=0, scoring_performed=True, file_denominator=280,
                function_denominator=280, protocol_sha256=PROTOCOL_SHA256,
                frozen_evaluator_sha256=EVALUATOR_SHA256,
                metrics={arm:{'function':copy.deepcopy(metric)} for arm in ARMS},
                graphlocator_terminal_statuses={'complete':270,'failed':10},
                resources={'graphlocator':{'runner_wall_seconds':{
                    'records':280,'all_recorded_tasks_known':True}}},
                inference_metadata={'sampling':dict(temperature=.7,top_p=.8,top_k=20,
                                                     min_p=0,seed=0,n=1)})


class PlotContractTests(unittest.TestCase):
    def test_complete_synthetic_fixture_is_accepted(self):
        self.assertEqual(validate_summary(fixture())['allocated'],280)

    def test_partial_or_pilot_or_missing_runner_is_rejected(self):
        for key, value in [('status','PARTIAL'),('scope','pilot20'),('allocated',20),
                           ('terminal_tasks',279),('pending_tasks',1)]:
            s=fixture();s[key]=value
            with self.assertRaises(ValueError):validate_summary(s)
        s=fixture();s['resources']['graphlocator']['runner_wall_seconds']['records']=279
        with self.assertRaisesRegex(ValueError,'runner receipts'):validate_summary(s)

    def test_protocol_score_denominator_and_sampling_cannot_drift(self):
        for key, value in [('protocol_sha256','0'*64),('frozen_evaluator_sha256','0'*64),
                           ('function_denominator',279)]:
            s=fixture();s[key]=value
            with self.assertRaises(ValueError):validate_summary(s)
        s=fixture();s['inference_metadata']['sampling']['temperature']=0
        with self.assertRaisesRegex(ValueError,'sampling'):validate_summary(s)

    def test_count_rate_and_ci_must_match_without_dropping_failures(self):
        for key, value in [('hit1_numerator',71),('hit1',1.1),('hit1_ci95',[.5,.6]),('n',279)]:
            s=fixture();s['metrics']['graphlocator']['function'][key]=value
            with self.assertRaises(ValueError):validate_summary(s)
        s=fixture();s['graphlocator_terminal_statuses']['failed']=0
        with self.assertRaisesRegex(ValueError,'terminal'):validate_summary(s)

    def test_synthetic_render_is_marked_and_output_never_overwrites(self):
        try:import matplotlib
        except ImportError:self.skipTest('Optional plotting dependency unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'SYNTHETIC_ONLY'
            render(fixture(),output,synthetic_fixture=True)
            self.assertEqual({p.suffix for p in output.iterdir()},{'.png','.svg','.pdf'})
            self.assertIn('SYNTHETIC CPU TEST FIXTURE',(output/'function_hit_280.svg').read_text())
            with self.assertRaises(FileExistsError):render(fixture(),output,synthetic_fixture=True)


if __name__=='__main__':unittest.main()
