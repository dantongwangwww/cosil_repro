"""Synthetic CPU contracts for fixed-roster, cross-batch evaluation."""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reproduction import evaluate_extension as e
from reproduction import evaluate as common


class UnifiedEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'new';self.old=self.root/'old'
        self.run.mkdir();self.old.mkdir();self.frozen,_=common.frozen_evaluator()
        self.tasks=[dict(instance_id=f'owner__repo{i}-1',repo=f'owner/repo{i}',base_commit=str(i)*40,
            execution_origin='existing100_reuse' if i==1 else 'new180') for i in (1,2,3)]
        self.tasks[0].update(original_run=str(self.old),
            original_result=str(self.old/'outputs'/self.tasks[0]['instance_id']/'result.json'),
            requested_file_result=str(self.old/'strict'/self.tasks[0]['instance_id']/'result.json'))
        self.manifest={'n':3,'records':self.tasks}
        self.gold={t['instance_id']:dict(status='COMPLETE_NONEMPTY',set_complete=True,
            targets=['pkg/a.py::A.f'],gold_files=['pkg/a.py']) for t in self.tasks}
        self.inventory={t['instance_id']:dict(paths=['pkg/a.py','pkg/b.py'],
            function_identities=['pkg/a.py::A.f','pkg/a.py::A.g']) for t in self.tasks}
        self.write(self.run/'selection/manifest.json',self.manifest)
        self.write(self.run/'selection/extension_manifest.json',{'n':2,'records':self.tasks[1:]})
        self.write(self.run/'private/gold.json',self.gold)
        self.write(self.run/'private/inventory.json',self.inventory)
        self.historical=[]
        for t in self.tasks:
            row={k:t[k] for k in ('instance_id','repo','base_commit')}
            for arm in ('baseline','hybrid_safe'):
                row[arm+'_status']='complete';row[arm+'_file_slots']=json.dumps(['pkg/a.py'])
                row[arm+'_function_slots']=json.dumps(['pkg/a.py::A.f'])
                for unit,raw,targets,inv in [('file',['pkg/a.py'],['pkg/a.py'],['pkg/a.py','pkg/b.py']),
                    ('function',[dict(path='pkg/a.py',qualified_name='A.f')],['pkg/a.py::A.f'],
                     ['pkg/a.py::A.f','pkg/a.py::A.g'])]:
                    m=self.frozen.metrics(raw,targets,inv,functions=unit=='function')
                    for k,v in m.items():
                        if k!='slots':row[arm+'_'+unit+'_'+k]=v
                row.update({arm+'_main_tokens':30,arm+'_known_prompt_tokens':20,
                    arm+'_known_completion_tokens':10,arm+'_unknown_usage_attempts':0,
                    arm+'_http_attempts_recorded':2,arm+'_worker_elapsed_seconds':4,
                    arm+'_local_input_tokens':0})
            row['baseline_file_stage_wall_seconds']=1
            self.historical.append(row)
        self.write_history()

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def write_history(self):
        p=self.run/'private/comparison_original.csv'
        with p.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(self.historical[0]));writer.writeheader();writer.writerows(self.historical)

    def source(self,index):
        t=self.tasks[index]
        return Path(t['original_result']) if index==0 else self.run/'outputs'/t['instance_id']/'result.json'

    def raw(self,index,**updates):
        t=self.tasks[index]
        value={k:t[k] for k in ('instance_id','repo','base_commit')}
        value.update(terminal=True,status='complete',execution_status='complete',thinking_enabled=False,
            actual_request_model='qwen3-8b',num_samples=2,ranking_method='mrr',raw_output_loc=['raw'],
            found_files=[],found_entities=[],samples=[{'status':'complete'},{'status':'complete'}],
            usage=dict(prompt_tokens=20,completion_tokens=10,total_tokens=30,known_prompt_tokens=20,
                known_completion_tokens=10,known_total_tokens=30,unknown_usage_requests=0,
                http_attempts=2,completion_requests=2,api_cost_usd=0),elapsed_seconds=3,
            generation_seconds=2,tool_elapsed_seconds=.5,graph_elapsed_seconds=1)
        value.update(updates);self.write(self.source(index),value);return value

    def normalized_path(self,index):
        return self.run/'audits/unified_requested_file/outputs'/self.tasks[index]['instance_id']/'result.json'

    def receipt(self,index):
        p=self.normalized_path(index)
        value=dict(status='ready',instance_id=self.tasks[index]['instance_id'],rule_id=e.OLD_VIEW,
            source_patch_sha256=e.SOURCE_PATCH_SHA256,source_result_path=str(self.source(index)),
            source_result_sha256=common.sha(self.source(index)),normalized_result_sha256=common.sha(p))
        self.write(p.parent/'normalization_receipt.json',value)
        return value

    def normalized(self,index,raw=None,**updates):
        raw=raw if raw is not None else self.raw(index)
        value=copy.deepcopy(raw);value.update(found_files=['pkg/a.py'],found_entities=['pkg/a.py:A.f'],
            source_inference_result_sha256=common.sha(self.source(index)),postprocess_view=e.OLD_VIEW,
            postprocess_diagnostic_error=None)
        value.update(updates);p=self.normalized_path(index);self.write(p,value)
        if index==0:self.write(Path(self.tasks[0]['requested_file_result']),value)
        self.receipt(index);return value

    def evaluate(self):
        return e.build_evaluation(self.run,expected_n=3,expected_reused=1,draws=40)

    def all_ready(self):
        for i in range(3):self.normalized(i)

    def test_unified_main_uses_strict_result_for_every_batch(self):
        self.all_ready();r=self.evaluate();s=r['summary']
        self.assertEqual(s['status'],'FINAL')
        self.assertEqual(s['metrics']['locagent']['function']['hit1_numerator'],3)
        self.assertNotIn('native',s['metrics'])
        self.assertFalse(s['per_batch_accuracy_reported']);self.assertNotIn('completed_only_secondary',s)
        self.assertEqual(set(s['metrics']),{'baseline','hybrid_safe','locagent'})

    def test_ready_merge_is_by_id_not_csv_or_filesystem_order(self):
        self.all_ready();self.historical.reverse();self.write_history()
        r=self.evaluate();self.assertEqual([x['instance_id'] for x in r['records']],
            [x['instance_id'] for x in self.tasks])

    def test_pending_is_not_a_failed_model_or_final_comparison(self):
        self.normalized(0);s=self.evaluate()['summary']
        self.assertEqual((s['status'],s['terminal_tasks'],s['pending_tasks']),('PARTIAL',1,2))
        self.assertEqual(s['locagent_terminal_statuses'],{'complete':1})
        self.assertEqual(s['metrics'],{})
        self.assertEqual(s['paired_comparisons'],{})
        self.assertFalse(s['gold_read']);self.assertFalse(s['scoring_performed'])

    def test_raw_terminal_waiting_normalization_retains_real_resources(self):
        self.raw(1);r=self.evaluate();s=r['summary']
        self.assertEqual((s['inference_terminal_tasks'],s['terminal_tasks']),(1,0))
        self.assertEqual(r['records'][1]['normalization_state'],'WAITING_NORMALIZATION')
        self.assertEqual(s['resources']['locagent']['known_total_tokens']['sum'],30)

    def test_atomic_result_without_ready_receipt_is_not_scored(self):
        self.normalized(1);(self.normalized_path(1).parent/'normalization_receipt.json').unlink()
        self.assertEqual(self.evaluate()['summary']['terminal_tasks'],0)

    def test_failed_inference_remains_in_fixed_denominator(self):
        self.all_ready();raw=self.raw(2,status='failed',execution_status='step_limit',found_files=[],found_entities=[])
        self.normalized(2,raw,found_files=[],found_entities=[])
        s=self.evaluate()['summary'];self.assertEqual(s['status'],'FINAL')
        self.assertEqual((s['metrics']['locagent']['function']['hit5_numerator'],
            s['metrics']['locagent']['function']['n']),(2,3))
        self.assertEqual(s['locagent_terminal_statuses'],{'complete':2,'failed':1})

    def test_partial_inference_is_terminal_not_pending(self):
        self.all_ready();raw=self.raw(1,status='partial',execution_status='partial_samples')
        self.normalized(1,raw);self.assertEqual(self.evaluate()['summary']['status'],'FINAL')

    def test_invalid_and_duplicate_slots_never_compress_or_expand(self):
        self.all_ready()
        self.normalized(1,found_entities=['pkg/a.py:A','pkg/a.py:A.f','pkg/a.py:A.f'])
        m=self.evaluate()['records'][1]['locagent_function']
        self.assertEqual(m['slots'],[None,'pkg/a.py::A.f','pkg/a.py::A.f'])
        self.assertEqual((m['hit1'],m['hit3'],m['precision5'],m['mrr10']),(0,1,.2,.5))

    def test_output_hash_change_is_rejected(self):
        self.normalized(1);p=self.normalized_path(1);d=common.read(p);d['found_entities']=[];self.write(p,d)
        with self.assertRaisesRegex(ValueError,'Normalized result SHA'):self.evaluate()

    def test_raw_hash_change_is_rejected(self):
        self.normalized(1);p=self.source(1);d=common.read(p);d['raw_output_loc']=['different'];self.write(p,d)
        with self.assertRaisesRegex(ValueError,'raw-source SHA'):self.evaluate()

    def test_nonprediction_usage_is_never_changed_or_zero_filled(self):
        self.normalized(1,usage={'total_tokens':0});self.receipt(1)
        with self.assertRaisesRegex(ValueError,'non-prediction field: usage'):self.evaluate()

    def test_frozen_rule_digest_is_enforced(self):
        self.normalized(1);p=self.normalized_path(1).parent/'normalization_receipt.json';d=common.read(p)
        d['source_patch_sha256']='f'*64;self.write(p,d)
        with self.assertRaisesRegex(ValueError,'rule differs'):self.evaluate()

    def test_reused_prediction_must_be_byte_identical(self):
        self.normalized(0);p=self.normalized_path(0);d=common.read(p);d['found_entities']=[];self.write(p,d);self.receipt(0)
        with self.assertRaisesRegex(ValueError,'byte-identical'):self.evaluate()

    def test_raw_repo_base_identity_cannot_drift(self):
        self.raw(1,base_commit='f'*40)
        with self.assertRaisesRegex(ValueError,'Raw result identity'):self.evaluate()

    def test_wrong_model_or_thinking_mode_stops_comparison(self):
        self.raw(1,thinking_enabled=True)
        with self.assertRaisesRegex(ValueError,'model/protocol differs'):self.evaluate()

    def test_incremental_ledger_never_rebills_reused_inference(self):
        self.all_ready();r=self.evaluate()
        self.assertEqual(r['summary']['resources']['locagent']['known_total_tokens']['sum'],90)
        self.assertEqual(r['incremental_accounting']['resources']['known_total_tokens']['sum'],60)
        self.assertTrue(r['incremental_accounting']['no_reused_usage_rebilled'])

    def test_unknown_attempt_usage_stays_unknown(self):
        raw=self.raw(1,usage=dict(prompt_tokens=None,completion_tokens=None,total_tokens=None,
            known_prompt_tokens=20,known_completion_tokens=10,known_total_tokens=30,
            unknown_usage_requests=1,http_attempts=2,completion_requests=2,api_cost_usd=0))
        self.normalized(1,raw);s=self.evaluate()['summary']['resources']['locagent']
        self.assertIsNone(s['total_tokens']['sum']);self.assertEqual(s['known_total_tokens']['sum'],30)
        self.assertEqual(s['unknown_usage_requests']['sum'],1)

    def test_changed_historical_score_is_detected(self):
        self.all_ready()
        self.historical[0]['baseline_function_hit5']=0;self.write_history()
        with self.assertRaisesRegex(ValueError,'Historical scoring changed'):self.evaluate()

    def test_extension_order_and_membership_cannot_change(self):
        self.write(self.run/'selection/extension_manifest.json',{'n':2,'records':list(reversed(self.tasks[1:]))})
        with self.assertRaisesRegex(ValueError,'fixed-order'):self.evaluate()

    def test_original_result_cannot_point_to_another_issue(self):
        self.tasks[0]['original_result']=str(self.old/'outputs/wrong/result.json')
        self.write(self.run/'selection/manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'declared issue/run'):self.evaluate()

    def test_runner_time_uses_raw_source_not_normalized_copy(self):
        self.all_ready();self.write(self.source(0).parent/'runner_receipt.json',{'wall_seconds':12})
        s=self.evaluate()['summary']['resources']['locagent']
        self.assertEqual(s['runner_wall_seconds']['sum'],12);self.assertEqual(s['runner_wall_seconds']['records'],1)
        self.assertEqual(s['elapsed_seconds']['sum'],9)

    def test_extension_wall_uses_only_new_raw_terminal_timestamps(self):
        self.all_ready();self.write(self.run/'controller/full_launcher.json',{'started':100})
        for i,t in enumerate([10,120,150]):os.utime(self.source(i),(t,t))
        for i in range(3):os.utime(self.normalized_path(i),(999,999))
        wall=self.evaluate()['summary']['wall_clock']
        self.assertEqual(wall['extension_launcher_to_last_raw_terminal_seconds'],50)
        self.assertTrue(wall['not_a_continuous_280_task_wall_clock'])

    def test_new_output_dir_bom_csv_pending_blanks_and_no_batch_score_table(self):
        self.normalized(0);out=self.run/'reports/out'
        e.evaluate_run(self.run,out,expected_n=3,expected_reused=1,draws=40)
        data=(out/'per_issue.csv').read_bytes();self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        with (out/'per_issue.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),3);self.assertEqual(rows[1]['locagent_function_hit5'],'')
        self.assertEqual(rows[0]['locagent_function_hit5'],'')
        text=(out/'final_report.md').read_text();self.assertNotIn('原生主结果',text)
        self.assertNotIn('100题成绩',text);self.assertNotIn('180题成绩',text)
        with self.assertRaises(FileExistsError):e.evaluate_run(self.run,out,expected_n=3,expected_reused=1,draws=40)

    def test_no_raw_and_normalized_source_is_modified(self):
        self.all_ready();paths=[p for p in self.root.rglob('*') if p.is_file()]
        before={str(p):common.sha(p) for p in paths};self.evaluate()
        self.assertEqual(before,{str(p):common.sha(p) for p in paths})

    def test_progress_does_not_open_any_private_gold_inventory_or_history(self):
        self.normalized(0)
        for name in ['gold.json','inventory.json','comparison_original.csv']:
            (self.run/'private'/name).unlink()
        s=self.evaluate()['summary']
        self.assertEqual(s['status'],'PARTIAL');self.assertFalse(s['gold_read'])
        self.assertFalse(s['private_inventory_read']);self.assertEqual(s['metrics'],{})

    def test_parser_source_fingerprint_is_pinned(self):
        with patch.dict(e.RULE_FILES,{'reproduction/postprocess_requested_file.py':'f'*64}):
            with self.assertRaisesRegex(ValueError,'parsing-rule source changed'):self.evaluate()

    def test_frozen_original_source_manifest_hash_is_checked(self):
        self.normalized(0);self.tasks[0]['original_result_sha256']='f'*64
        self.write(self.run/'selection/manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'original-result SHA'):self.evaluate()


if __name__=='__main__':
    unittest.main()
