"""Synthetic, CPU-only contracts; no real issue, model, or secret is loaded."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rebench_qwen3 import evaluate as e


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run=Path(self.tmp.name);self.frozen,_=e.frozen_evaluator()
        self.tasks=[dict(instance_id=f'owner__repo{i}-1',repo=f'owner/repo{i}',base_commit=str(i)*40)
                    for i in (1,2,3)]
        self.full={'n':3,'records':self.tasks}
        self.write('selection/manifest.json',self.full);self.write_pilot()
        self.gold={t['instance_id']:dict(status='COMPLETE_NONEMPTY',set_complete=True,
                    targets=['pkg/a.py::C.f'],gold_files=['pkg/a.py']) for t in self.tasks}
        self.inventory={t['instance_id']:dict(paths=['pkg/a.py','pkg/b.py'],
                    function_identities=['pkg/a.py::C.f','pkg/a.py::C.g']) for t in self.tasks}
        self.write('assets/gold.json',self.gold);self.write('assets/inventory.json',self.inventory)
        (self.run/'assets/comparison.csv').write_text('frozen,sample\n')
        predictions=[]
        for task in self.tasks:
            predictions.append(dict(task,arms={a:dict(status='complete',predicted_files=['pkg/a.py'],
                predicted_functions=[dict(path='pkg/a.py',qualified_name='C.f')]) for a in e.HISTORICAL}))
        self.reference=self.frozen.evaluate(predictions,self.gold,self.inventory,arms=e.HISTORICAL,
                                            seed=20261110,draws=40)
        for row in self.reference['records']:
            row['resources']={a:dict(known_prompt_tokens=20,known_completion_tokens=10,
                known_total_tokens=30,total_tokens=30,unknown_usage_requests=0,http_attempts=2,
                api_cost_usd=0,elapsed_seconds=4,runner_wall_seconds=None) for a in e.HISTORICAL}
        self.reference['summary'].update(status='FINAL',terminal_tasks=3,
            primary_prediction_protocol='normalized_requested_file_v1',frozen_evaluator_sha256=e.EVALUATOR_SHA256,
            source_sha256={k:e.sha(self.run/'assets'/name) for k,name in
                [('gold','gold.json'),('inventory','inventory.json'),('comparison','comparison.csv')]})
        self.write('assets/reference.json',self.reference)
        self.write_sources()

    def write(self,relative,value):
        path=self.run/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def write_pilot(self):
        self.write('selection/pilot20.json',dict(n=2,records=self.tasks[:2],
                    full_manifest_sha256=e.sha(self.run/'selection/manifest.json')))

    def write_sources(self):
        values={k:str(self.run/'assets'/name) for k,name in [('gold','gold.json'),('inventory','inventory.json'),
                    ('comparison','comparison.csv'),('reference_evaluation','reference.json')]}
        values.update({k+'_sha256':e.sha(p) for k,p in list(values.items())})
        values['evaluator_sha256']=e.EVALUATOR_SHA256
        self.write('private/evaluation_sources.json',values)

    def worker(self,index,**changes):
        task=self.tasks[index];value=dict(task,terminal=True,status='complete',execution_status='complete',
            found_files=['pkg/a.py'],found_entities=['pkg/a.py::C.f'],found_modules=[],
            native_result={'not_a_gold_fix':True},identity_validation=[],
            usage=dict(prompt_tokens=20,completion_tokens=10,total_tokens=30,known_prompt_tokens=20,
                known_completion_tokens=10,known_total_tokens=30,unknown_usage_requests=0,
                http_attempts=2,completion_requests=2,api_cost_usd=0),elapsed_seconds=3)
        value.update(changes);self.write('outputs/'+task['instance_id']+'/result.json',value);return value

    def ready(self,n=2):
        for i in range(n):self.worker(i)

    def evaluate(self,scope='pilot20'):
        return e.build_evaluation(self.run,scope,expected_full=3,expected_pilot=2,draws=40)

    def test_pending_does_not_read_any_private_asset_or_compute_accuracy(self):
        self.worker(0)
        (self.run/'private/evaluation_sources.json').unlink()
        for p in (self.run/'assets').iterdir():p.unlink()
        result=self.evaluate();s=result['summary']
        self.assertEqual((s['status'],s['terminal_tasks'],s['pending_tasks']),('PARTIAL',1,1))
        self.assertFalse(s['gold_read']);self.assertFalse(s['scoring_performed'])
        self.assertEqual(s['metrics'],{});self.assertEqual(s['paired_comparisons'],{})

    def test_pilot_projects_every_arm_to_same_fixed_prefix(self):
        self.ready();r=self.evaluate();s=r['summary']
        self.assertEqual(s['status'],'FINAL');self.assertEqual(s['allocated'],2)
        for arm in e.ARMS:
            self.assertEqual(s['metrics'][arm]['function']['n'],2)
            self.assertEqual(s['metrics'][arm]['function']['hit5_numerator'],2)
        self.assertEqual([x['instance_id'] for x in r['records']],[x['instance_id'] for x in self.tasks[:2]])

    def test_full_scope_waits_for_all_records_not_only_pilot(self):
        self.ready();s=self.evaluate('full280')['summary']
        self.assertEqual((s['allocated'],s['terminal_tasks'],s['status']),(3,2,'PARTIAL'))
        self.assertFalse(s['gold_read'])
        self.worker(2);s=self.evaluate('full280')['summary']
        self.assertEqual((s['status'],s['file_denominator'],s['function_denominator']),('FINAL',3,3))

    def test_final_failure_stays_in_all_four_arms_scope_denominator(self):
        self.ready();self.worker(1,status='failed',execution_status='timeout',found_files=[],found_entities=[])
        s=self.evaluate()['summary'];self.assertEqual(s['status'],'FINAL')
        m=s['metrics']['graphlocator']['function'];self.assertEqual((m['hit5_numerator'],m['n']),(1,2))
        self.assertEqual(s['graphlocator_terminal_statuses'],{'complete':1,'failed':1})

    def test_failed_partial_cig_is_not_silently_rescored(self):
        self.worker(0,status='failed')
        with self.assertRaisesRegex(ValueError,'partial CIG'):self.evaluate()

    def test_complete_empty_output_is_complete_and_scored_as_miss(self):
        self.ready();self.worker(0,found_files=[],found_entities=[])
        s=self.evaluate()['summary'];self.assertEqual(s['graphlocator_terminal_statuses'],{'complete':2})
        self.assertEqual(s['metrics']['graphlocator']['function']['hit5_numerator'],1)

    def test_invalid_class_and_duplicate_slots_are_not_compressed(self):
        self.ready();self.worker(0,found_entities=['pkg/a.py::C','pkg/a.py::C.f','pkg/a.py::C.f'])
        v=self.evaluate()['records'][0]['graphlocator_function']
        self.assertEqual(v['slots'],[None,'pkg/a.py::C.f','pkg/a.py::C.f'])
        self.assertEqual((v['hit1'],v['hit3'],v['precision5'],v['mrr10']),(0,1,.2,.5))

    def test_unresolved_ast_slot_is_not_gold_disambiguated(self):
        self.ready();self.worker(0,found_entities=['pkg/a.py::<unresolved_ast:METHOD:f@7>','pkg/a.py::f','C.f'])
        v=self.evaluate()['records'][0]['graphlocator_function']
        self.assertEqual(v['slots'],[None,None,None]);self.assertEqual(v['hit5'],0)

    def test_canonical_separator_conversion_is_lossless_and_alias_unused(self):
        self.ready();self.worker(0,found_entities=['pkg/a.py::C.g'],found_functions=['pkg/a.py::C.f'])
        self.assertEqual(self.evaluate()['records'][0]['graphlocator_function']['hit1'],0)
        self.assertIsNone(e.identity_item('pkg/a.py:C.f'))

    def test_reference_row_order_never_reorders_scope(self):
        self.ready();self.reference['records'].reverse();self.write('assets/reference.json',self.reference);self.write_sources()
        r=self.evaluate();self.assertEqual([x['instance_id'] for x in r['records']],
                                         [x['instance_id'] for x in self.tasks[:2]])

    def test_historical_invalid_slots_are_preserved(self):
        self.ready();row=self.reference['records'][0]
        raw=[None,dict(path='pkg/a.py',qualified_name='C.f'),dict(path='pkg/a.py',qualified_name='C.f')]
        row['locagent_function']=self.frozen.metrics(raw,['pkg/a.py::C.f'],self.inventory[row['instance_id']]['function_identities'],functions=True)
        self.write('assets/reference.json',self.reference);self.write_sources()
        v=self.evaluate()['records'][0]['locagent_function'];self.assertEqual(v['slots'],[None,'pkg/a.py::C.f','pkg/a.py::C.f'])
        self.assertEqual(v['hit1'],0)

    def test_historical_per_issue_metric_change_is_detected(self):
        self.ready();self.reference['records'][0]['baseline_function']['hit5']=0
        self.write('assets/reference.json',self.reference);self.write_sources()
        with self.assertRaisesRegex(ValueError,'per-issue metric changed'):self.evaluate()

    def test_source_sha_cannot_drift(self):
        self.ready();self.write('assets/gold.json',{})
        with self.assertRaisesRegex(ValueError,'source SHA differs'):self.evaluate()

    def test_reference_input_binding_cannot_drift(self):
        self.ready();self.reference['summary']['source_sha256']['inventory']='f'*64
        self.write('assets/reference.json',self.reference);self.write_sources()
        with self.assertRaisesRegex(ValueError,'input binding differs'):self.evaluate()

    def test_reference_protocol_or_final_state_mismatch_stops_scoring(self):
        self.ready();self.reference['summary']['status']='PARTIAL'
        self.write('assets/reference.json',self.reference);self.write_sources()
        with self.assertRaisesRegex(ValueError,'frozen complete protocol'):self.evaluate()

    def test_frozen_evaluator_byte_pin_cannot_be_replaced(self):
        path=self.run/'wrong.py';path.write_text('')
        with self.assertRaisesRegex(ValueError,'evaluator SHA'):e.frozen_evaluator(path)

    def test_pilot_prefix_or_manifest_hash_cannot_drift(self):
        self.write('selection/pilot20.json',dict(n=2,records=list(reversed(self.tasks[:2])),
            full_manifest_sha256=e.sha(self.run/'selection/manifest.json')))
        with self.assertRaisesRegex(ValueError,'fixed full-roster prefix'):self.evaluate()

    def test_worker_identity_mismatch_stops_even_before_gold(self):
        self.worker(0,base_commit='f'*40)
        with self.assertRaisesRegex(ValueError,'identity mismatch'):self.evaluate()

    def test_source_assets_require_explicit_absolute_paths(self):
        self.ready();source=e.read(self.run/'private/evaluation_sources.json');source['gold']='relative.json'
        self.write('private/evaluation_sources.json',source)
        with self.assertRaisesRegex(ValueError,'absolute paths'):self.evaluate()

    def test_unknown_usage_remains_unknown_not_zero(self):
        self.worker(0,usage=dict(prompt_tokens=None,completion_tokens=None,total_tokens=None,
            known_prompt_tokens=20,known_completion_tokens=10,known_total_tokens=30,
            unknown_usage_requests=1,http_attempts=2,api_cost_usd=0))
        r=self.evaluate()['summary']['resources']['graphlocator']
        self.assertIsNone(r['total_tokens']['sum']);self.assertEqual(r['known_total_tokens']['sum'],30)
        self.assertEqual(r['unknown_usage_requests']['sum'],1)

    def test_unknown_usage_cannot_claim_exact_total(self):
        self.worker(0,usage=dict(total_tokens=30,unknown_usage_requests=1))
        with self.assertRaisesRegex(ValueError,'Unknown HTTP usage'):self.evaluate()

    def test_runner_wall_is_distinct_from_worker_time(self):
        self.worker(0);self.write('outputs/'+self.tasks[0]['instance_id']+'/runner_receipt.json',{'wall_seconds':12})
        r=self.evaluate()['summary']['resources']['graphlocator']
        self.assertEqual((r['elapsed_seconds']['mean'],r['runner_wall_seconds']['mean']),(3,12))

    def test_partial_csv_is_bom_and_all_metric_cells_blank(self):
        self.worker(0);out=self.run/'reports/check'
        result=e.evaluate_run(self.run,'pilot20',out,expected_full=3,expected_pilot=2,draws=40)
        self.assertEqual(result['summary']['status'],'PARTIAL')
        self.assertTrue((out/'per_issue.csv').read_bytes().startswith(b'\xef\xbb\xbf'))
        with (out/'per_issue.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),2);self.assertTrue(all(r['graphlocator_function_hit5']=='' for r in rows))
        self.assertTrue(all(r['baseline_function_hit5']=='' for r in rows))
        with self.assertRaises(FileExistsError):e.evaluate_run(self.run,'pilot20',out,expected_full=3,expected_pilot=2,draws=40)

    def test_final_output_has_four_arms_and_graph_paired_stats_only(self):
        self.ready();result=e.evaluate_run(self.run,'pilot20',self.run/'reports/final',expected_full=3,expected_pilot=2,draws=40)
        self.assertEqual(set(result['summary']['metrics']),set(e.ARMS))
        self.assertEqual(set(result['summary']['paired_comparisons']),{a+'__graphlocator' for a in e.HISTORICAL})
        self.assertEqual(result['summary']['bootstrap_seed'],20261115)
        self.assertIn('公开协议回执',(self.run/'reports/final/final_report.md').read_text())

    def test_actual_sampling_model_budgets_and_protocol_sha_are_reported(self):
        protocol=dict(protocol_version='synthetic_v3',
            model=dict(id='Qwen/Qwen3-8B',revision='frozen-revision',served_name='qwen3-8b',
                       thinking_enabled=False,author_finetuned_weights=False),
            inference=dict(temperature=.7,top_p=.8,top_k=20,min_p=0,seed=0,n=1,
                one_trajectory_per_issue=True,sampling_profile='official_nonthinking_test',
                maximum_output_tokens=8192,context_capacity=65536,
                http_generation_timeout_seconds=600,runner_timeout_seconds=1800))
        self.write('protocol.json',protocol);self.ready();result=self.evaluate();s=result['summary']
        m=s['inference_metadata']
        self.assertEqual(s['protocol_sha256'],e.sha(self.run/'protocol.json'))
        self.assertEqual(s['source_sha256']['protocol'],s['protocol_sha256'])
        self.assertEqual(m['sampling']['temperature'],.7)
        self.assertEqual(m['sampling']['top_p'],.8);self.assertEqual(m['sampling']['top_k'],20)
        self.assertEqual(m['sampling']['min_p'],0);self.assertEqual(m['sampling']['seed'],0)
        self.assertEqual(m['sampling_profile'],'official_nonthinking_test')
        self.assertEqual(m['model'],protocol['model'])
        self.assertEqual(m['budgets']['http_generation_timeout_seconds'],600)
        self.assertEqual(m['budgets']['runner_timeout_seconds'],1800)
        text=e.report_text(result,self.run)
        self.assertIn('sampling.temperature | `0.7`'.replace('sampling','采样'),text)
        self.assertIn(s['protocol_sha256'],text)
        self.assertNotIn('temperature=0的单轨迹',text)

    def test_missing_protocol_or_fields_are_unknown_not_prior_defaults(self):
        self.ready();s=self.evaluate()['summary'];m=s['inference_metadata']
        self.assertIsNone(s['protocol_sha256']);self.assertNotIn('protocol',s['source_sha256'])
        self.assertEqual(m['receipt_status'],'unknown')
        self.assertTrue(all(v=='unknown' for v in m['sampling'].values()))
        self.assertTrue(all(v=='unknown' for v in m['model'].values()))
        self.write('protocol.json',dict(inference=dict(temperature=.7),model=dict(thinking_enabled=False)))
        result=self.evaluate();m=result['summary']['inference_metadata']
        self.assertEqual(m['sampling']['temperature'],.7)
        self.assertEqual(m['sampling']['top_p'],'unknown')
        self.assertEqual(m['sampling']['seed'],'unknown')
        self.assertEqual(m['sampling']['n'],'unknown')
        self.assertEqual(m['sampling_profile'],'unknown')
        self.assertEqual(m['budgets']['maximum_output_tokens'],'unknown')
        self.assertFalse(m['model']['thinking_enabled'])
        self.assertNotIn('temperature=0的单轨迹',e.report_text(result,self.run))

    def test_public_sampling_receipt_does_not_bypass_pending_gold_barrier(self):
        self.write('protocol.json',dict(inference=dict(temperature=.7,top_p=.8)))
        self.worker(0);(self.run/'private/evaluation_sources.json').unlink()
        for p in (self.run/'assets').iterdir():p.unlink()
        s=self.evaluate()['summary']
        self.assertFalse(s['gold_read']);self.assertFalse(s['scoring_performed'])
        self.assertEqual(s['inference_metadata']['sampling']['temperature'],.7)
        self.assertEqual(s['protocol_sha256'],e.sha(self.run/'protocol.json'))

    def test_sampling_metadata_cannot_change_scores_predictions_or_reference(self):
        self.ready();before=self.evaluate()
        self.write('protocol.json',dict(inference=dict(temperature=.7,top_p=.8,top_k=20,min_p=0,seed=0,n=1)))
        after=self.evaluate()
        self.assertEqual(before['records'],after['records'])
        for key in ('metrics','paired_comparisons','file_denominator','function_denominator',
                    'frozen_evaluator_sha256','bootstrap_seed','bootstrap_draws'):
            self.assertEqual(before['summary'][key],after['summary'][key])
        for key in ('gold','inventory','comparison','reference_evaluation'):
            self.assertEqual(before['summary']['source_sha256'][key],after['summary']['source_sha256'][key])

    def test_no_historical_or_worker_file_is_modified(self):
        self.ready();paths=[p for p in self.run.rglob('*') if p.is_file()]
        before={str(p):e.sha(p) for p in paths};self.evaluate()
        self.assertEqual(before,{str(p):e.sha(p) for p in paths})


if __name__=='__main__':unittest.main()
