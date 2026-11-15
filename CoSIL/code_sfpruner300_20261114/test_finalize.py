"""Synthetic CPU evaluation fixtures, never measured localization results."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parent))
import finalize as f


class ScoringTests(unittest.TestCase):
    def test_invalid_and_duplicate_slots_are_not_repaired_or_compressed(self):
        inventory=['m.py::f','m.py::other']
        raw=[{'path':'tests/test_m.py','qualified_name':'f'},
             {'path':'wrong.py','qualified_name':'f'},
             {'path':'m.py','qualified_name':'f'},
             {'path':'m.py','qualified_name':'f'}]
        score=f.e.metrics(raw,['m.py::f'],inventory,functions=True)
        self.assertEqual(score['slots'],[None,None,'m.py::f','m.py::f'])
        self.assertEqual(score['hit1'],0);self.assertEqual(score['hit3'],1)
        self.assertEqual(score['precision5'],.2);self.assertEqual(score['recall5'],1.)

    def test_unrun_stays_in_fixed_function_denominator_and_empty_gold_is_na(self):
        records=[{'instance_id':'a','repo':'a/a','base_commit':'a'*40,'arms':{}},
                 {'instance_id':'b','repo':'b/b','base_commit':'b'*40,'arms':{}}]
        gold={'a':{'status':'COMPLETE_NONEMPTY','set_complete':True,'targets':['m.py::f'],'gold_files':['m.py']},
              'b':{'status':'COMPLETE_EMPTY','set_complete':True,'targets':[],'gold_files':['m.py']}}
        inventory={iid:{'paths':['m.py'],'function_identities':['m.py::f']} for iid in gold}
        result=f.e.evaluate(records,gold,inventory,draws=40)
        self.assertEqual(result['summary']['allocated'],2)
        self.assertEqual(result['summary']['function_denominator'],1)
        self.assertEqual(result['summary']['file_denominator'],2)
        self.assertEqual(result['summary']['metrics']['baseline']['function']['hit5_numerator'],0)
        self.assertEqual(result['summary']['statuses']['baseline'],{'NOT_RUN':2})

    def test_reference_gate_rejects_count_or_hit_drift(self):
        summary={'allocated':100,'function_denominator':92,'metrics':{
            arm:{'function':{f'hit{k}_numerator':n for k,n in counts.items()}}
            for arm,counts in f.OLD_COUNTS.items()}}
        self.assertTrue(f.reference_gate({'summary':summary})['passed'])
        changed=copy.deepcopy(summary);changed['metrics']['baseline']['function']['hit1_numerator']=35
        with self.assertRaisesRegex(ValueError,'merge forbidden'):f.reference_gate({'summary':changed})
        changed=copy.deepcopy(summary);changed['function_denominator']=100
        with self.assertRaisesRegex(ValueError,'cardinality'):f.reference_gate({'summary':changed})

    def test_exact_paired_four_cells_and_denominator_are_preserved(self):
        result=f.e.paired([1,1,0,0],[1,0,1,0],draws=40)
        self.assertEqual([result[k] for k in ('both_success','only_a','only_b','both_failure')],[1,1,1,1])
        self.assertEqual(result['n'],4);self.assertEqual(result['exact_mcnemar_p'],1.)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='sfpruner-finalize-fixture-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.base={'instance_id':'fixture__repo-1','repo':'fixture/repo','base_commit':'a'*40}
        self.arm=self.root/'baseline';self.provenance={}

    def collect(self):return f.read_new_arm(self.arm,self.base,'baseline','protocol',self.provenance)

    def complete(self):
        self.arm.mkdir()
        result={**self.base,'status':'complete','predicted_files':['m.py'],
                'predicted_functions':[{'path':'m.py','qualified_name':'f'}],
                'stage_resources':{},'elapsed_seconds':1.2}
        f.c.write(self.arm/'result.json',result)
        f.c.write(self.arm/'terminal.json',{**self.base,'arm':'baseline','protocol_sha256':'protocol',
                'status':'complete','result_sha256':f.c.sha(self.arm/'result.json')})

    def test_missing_and_unsealed_result_are_not_fabricated_model_failures(self):
        pred,detail=self.collect();self.assertEqual(pred['status'],'NOT_RUN');self.assertFalse(detail['terminal_verified'])
        self.complete();(self.arm/'terminal.json').unlink()
        pred,detail=self.collect();self.assertEqual(pred['status'],'EXECUTION_INCOMPLETE')
        self.assertEqual(pred['predicted_functions'],[]);self.assertFalse(detail['terminal_verified'])

    def test_real_terminal_validates_sha_identity_and_rejects_simulation(self):
        self.complete();pred,detail=self.collect()
        self.assertEqual(pred['status'],'complete');self.assertTrue(detail['terminal_verified'])
        result=self.arm/'result.json';result.write_text(result.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):self.collect()

    def test_environment_terminal_stays_environment_and_no_partial_prediction(self):
        self.complete()
        terminal=f.c.read(self.arm/'terminal.json');terminal['status']='interrupted';terminal.pop('result_sha256')
        f.c.write(self.arm/'terminal.json',terminal)
        pred,detail=self.collect()
        self.assertEqual(pred['status'],'EXECUTION_INCOMPLETE');self.assertEqual(pred['predicted_functions'],[])
        self.assertEqual(detail['execution_status'],'interrupted');self.assertTrue(detail['terminal_verified'])

    def test_unknown_usage_is_not_zero_and_pending_attempt_is_counted(self):
        calls=self.arm/'calls/0001_pruner';calls.mkdir(parents=True)
        f.c.write(calls/'attempt_0_receipt.json',{'usage':{'prompt_tokens':12,'completion_tokens':3}})
        f.c.write(calls/'attempt_1_start.json',{'started':True})
        resource,_=f.resource_record(self.arm,{},'EXECUTION_INCOMPLETE',self.provenance)
        self.assertEqual(resource['known_prompt_tokens'],12)
        self.assertEqual(resource['unknown_usage_attempts'],1)
        self.assertIsNone(resource['main_tokens']);self.assertEqual(resource['http_attempts_recorded'],2)

    def test_unavailable_resource_is_none_and_not_a_free_completed_task(self):
        resource,_=f.resource_record(self.arm,{},'NOT_RUN',self.provenance)
        self.assertFalse(resource['resource_available']);self.assertIsNone(resource['main_tokens'])
        resource,_=f.resource_record(self.arm,{'status':'complete'},'complete',self.provenance)
        self.assertTrue(resource['resource_available']);self.assertIsNone(resource['main_tokens'])

    def test_explicit_dependency_block_has_zero_calls_without_fabricating_prediction(self):
        self.arm.mkdir()
        f.c.write(self.arm/'terminal.json',{**self.base,'arm':'baseline','protocol_sha256':'protocol',
                'status':'dependency_blocked','model_called':False})
        pred,detail=self.collect()
        self.assertEqual(pred['status'],'DEPENDENCY_BLOCKED');self.assertEqual(pred['predicted_functions'],[])
        self.assertEqual(detail['resource']['main_tokens'],0)
        self.assertEqual(detail['resource']['usage_source'],'terminal_explicit_no_model_call')


class GoldAndMergeTests(unittest.TestCase):
    def test_r2_gold_whitelist_ignores_patch_evidence_and_rejects_revision_drift(self):
        base={'instance_id':'i','repo':'r/r','base_commit':'a'*40}
        raw={**base,'status':'COMPLETE_NONEMPTY','existing_function_target_set_complete':True,
             'existing_function_targets':['m.py::f'],'gold_files':['m.py'],
             'evaluation_revision':'r2_exact_context_offsets','changed_line_evidence':['PRIVATE OMITTED']}
        gold=f.normalize_gold(raw,base)
        self.assertEqual(gold['targets'],['m.py::f']);self.assertNotIn('changed_line_evidence',gold)
        with self.assertRaisesRegex(ValueError,'revision'):
            f.normalize_gold({**raw,'evaluation_revision':'old'},base)

    def bundle(self,iid,repo):
        return {'records':[{'instance_id':iid,'repo':repo,'base_commit':'a'*40}],
                'gold':{iid:{}},'inventory':{iid:{}},'details':{}}

    def test_merge_rejects_old_new_issue_and_repository_overlap(self):
        old=self.bundle('i','a/a')
        with self.assertRaisesRegex(ValueError,'issue ID overlap'):f.merge(old,self.bundle('i','b/b'))
        with self.assertRaisesRegex(ValueError,'repository overlap'):f.merge(old,self.bundle('j','A/A'))
        self.assertEqual(len(f.merge(old,self.bundle('j','b/b'))['records']),2)

    def test_complete_new_roster_gate_preserves_unrun_and_checks_qualification_sha(self):
        with tempfile.TemporaryDirectory(prefix='finalizer-roster-fixture-') as d:
            root=Path(d);runtime=root/'runtime';task=runtime/'task';task.mkdir(parents=True)
            base={'instance_id':'fixture__repo-1','repo':'fixture/repo','base_commit':'a'*40}
            index=task/'index.json';f.c.write(index,{'m.py':{'definitions':[{'kind':'function','qualified_name':'f'}]}})
            job=task/'job.json';f.c.write(job,{**base,'problem_statement':'Fixture only','cohort':'CPU fixture',
                    'snapshot':'snapshot','paths':['m.py'],'code_index':'index.json','structure':'structure.json'})
            manifest=runtime/'manifest.json';f.c.write(manifest,{'n':1,'records':[{**base,'job':'task/job.json','job_sha256':f.c.sha(job)}]})
            run=root/'run';f.c.write(run/'freeze.json',{'manifest_sha256':f.c.sha(manifest),'protocol_sha256':'protocol'})
            f.c.write(run/'pairs'/base['instance_id']/'prepared.json',{'protocol_sha256':'protocol',
                'source':{'job_sha256':f.c.sha(job),'index_sha256':f.c.sha(index)}})
            qualified=root/'qualified';folder=qualified/base['instance_id'];folder.mkdir(parents=True)
            gold=folder/'gold_v2.json';f.c.write(gold,{**base,'evaluation_revision':'r2_exact_context_offsets',
                'status':'COMPLETE_NONEMPTY','existing_function_target_set_complete':True,
                'existing_function_targets':['m.py::f'],'gold_files':['m.py']})
            qualification=folder/'qualification.private.json';f.c.write(qualification,{**base,
                'status':'QUALIFIED','complete':True,'nonempty':True,'source_id':'rebench_full_89cdfbab',
                'R2_gold_path':'gold_v2.json','R2_gold_sha256':f.c.sha(gold)})
            with self.assertRaisesRegex(ValueError,'lack terminal evidence'):
                f.read_new(manifest,run,qualified,allow_partial=False,expected_n=1)
            partial=f.read_new(manifest,run,qualified,allow_partial=True,expected_n=1)
            self.assertFalse(partial['final']);self.assertEqual(len(partial['pending']),2)
            self.assertEqual(partial['records'][0]['arms']['baseline']['status'],'NOT_RUN')
            scored=f.evaluate_subset(partial,[base['instance_id']],40)
            self.assertEqual(scored['summary']['function_denominator'],1)
            self.assertEqual(scored['summary']['metrics']['baseline']['function']['hit5_numerator'],0)
            gold.write_text(gold.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'R2 bytes changed'):
                f.read_new(manifest,run,qualified,allow_partial=True,expected_n=1)

    def test_report_and_csv_generation_is_explicitly_not_final_for_fixtures(self):
        with tempfile.TemporaryDirectory(prefix='finalize-report-fixture-') as d:
            root=Path(d);bundle={'records':[],'gold':{},'inventory':{},'details':{}}
            for index,group in enumerate(('original100','new208')):
                iid=f'fixture{index}__repo-1';base={'instance_id':iid,'repo':f'fixture{index}/repo','base_commit':'a'*40}
                arms={arm:{'status':'complete','predicted_files':['m.py'],
                           'predicted_functions':[{'path':'m.py','qualified_name':'f'}]} for arm in f.ARMS}
                bundle['records'].append({**base,'arms':arms})
                bundle['gold'][iid]={'status':'COMPLETE_NONEMPTY','set_complete':True,'targets':['m.py::f'],'gold_files':['m.py']}
                bundle['inventory'][iid]={'paths':['m.py'],'function_identities':['m.py::f']}
                for arm in f.ARMS:
                    resource,_=f.resource_record(root/'missing',{'stage_resources':{},'elapsed_seconds':1.},'complete',{})
                    bundle['details'][(iid,arm)]={'source_id':'fixture_only','group':group,
                        'resource':resource,'local_events':[],'execution_status':'complete',
                        'terminal_verified':True,'result_sha256':'fixture-only'}
            ids=[r['instance_id'] for r in bundle['records']]
            groups={'original100':f.evaluate_subset(bundle,ids[:1],40),
                    'new208':f.evaluate_subset(bundle,ids[1:],40),
                    'combined308':f.evaluate_subset(bundle,ids,40)}
            summary={'status':'NOT_FINAL','source_counts':{'fixture_only':2},'new_pending_arms':[['fixture','baseline','NOT_RUN']],
                     'resources':{key:f.resources_for(bundle,value) for key,value in
                                  [('original100',ids[:1]),('new208',ids[1:]),('combined308',ids)]}}
            f.write_outputs(root/'output',summary,groups,bundle,{'fixture_only':True},{},final=False)
            report=(root/'output/定位评测_合并总览.md').read_text()
            self.assertIn('NOT_FINAL',report)
            with (root/'output/逐题定位与资源.csv').open(encoding='utf-8-sig') as stream:
                rows=list(f.csv.DictReader(stream))
            self.assertEqual(len(rows),2)
            self.assertEqual([r['instance_id'] for r in rows],ids)
            self.assertTrue((root/'output/output_sha256.json').exists())
            self.assertIn('时间分布差异',report)
            self.assertIn('不能主张对模型未见问题的去污染泛化能力',report)

    def test_time_profile_is_descriptive_only_and_bound_to_selected_ids(self):
        with tempfile.TemporaryDirectory(prefix='time-profile-fixture-') as d:
            root=Path(d);iid='fixture__full-1';base={'instance_id':iid,'repo':'fixture/full','base_commit':'a'*40}
            new={'records':[base],'details':{(iid,'baseline'):{'source_id':'rebench_full_89cdfbab'}}}
            path=root/'profile.json';profile={'scope':'CPU fixture only','selection_influenced_by_dates':False,
                'full_source_tasks':1,'date_field':'PR created_at, not a model training cutoff',
                'earliest':'2020-01-01 00:00:00','latest':'2020-01-01 00:00:00','year_counts':{'2020':1},
                'records':[{**base,'created_at':'2020-01-01 00:00:00'}]}
            f.c.write(path,profile);before=copy.deepcopy(new)
            summary=f.source_time_profile(path,new,{})
            self.assertFalse(summary['pretraining_overlap_excluded']);self.assertEqual(new,before)
            profile['records'][0]['instance_id']='unselected__task-1';f.c.write(path,profile)
            with self.assertRaisesRegex(ValueError,'roster differs'):f.source_time_profile(path,new,{})


if __name__=='__main__':unittest.main()
