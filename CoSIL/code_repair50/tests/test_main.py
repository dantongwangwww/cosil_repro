import tempfile
import argparse
import json
from pathlib import Path
import unittest
from unittest import mock
from code_repair50 import main


class MainGuardTests(unittest.TestCase):
    def test_no_qualification_no_budget_provider_or_source_callback(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(main,'ROSTER',Path(d)/'missing.json'),mock.patch.object(main,'OUTPUT',Path(d)/'out'),mock.patch('sys.argv',['main','--phase','run']), \
                 mock.patch.object(main,'BudgetLedger') as ledger,mock.patch.object(main,'DeepSeekProvider') as provider, \
                 mock.patch.object(main.sources,'ensure_base') as source:
                with self.assertRaises(RuntimeError):main.main()
                ledger.assert_not_called();provider.assert_not_called();source.assert_not_called()

    def test_single_controller_lock_rejects_duplicate_then_releases(self):
        with tempfile.TemporaryDirectory() as d:
            with main.controller_lock(d):
                with self.assertRaises(RuntimeError):
                    with main.controller_lock(d):pass
            with main.controller_lock(d):pass

    def test_invalid_predictions_keep_rank_positions_in_audit(self):
        gold={'existing_function_targets':['a.py::f'],'gold_files':['a.py']}
        result={'predicted_functions':[None,{'path':'a.py','qualified_name':'f'}],'predicted_files':['a.py']}
        pair={'diagnostics':{'target_visibility':[{'identity':'a.py::f','A_full_definition_visible':True}]}}
        audit=main.audit_location({'instance_id':'synthetic'},gold,result,pair)
        self.assertFalse(audit['A_function_hit1']);self.assertTrue(audit['A_function_hit5'])

    def test_report_snapshot_contains_offline_diagnosis_without_model_calls(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            roster={'frozen':False,'tasks':[{'instance_id':'synthetic_task','repo':'synthetic/repo','base_commit':'a'*40}]}
            with mock.patch.object(main,'DeepSeekProvider') as provider:
                main.refresh_report(roster,out)
                provider.assert_not_called()
            import json
            target=Path(json.loads((out/'latest_report.json').read_text())['report_dir'])
            diagnosis=json.loads((target/'修复失败诊断.json').read_text())
            self.assertEqual(diagnosis['pair_class_counts'],{'UNPAIRED_OR_UNDETERMINED':1})
            self.assertFalse(diagnosis['formal_frozen'])
            self.assertTrue((target/'修复失败逐题诊断.csv').exists())
            self.assertTrue((target/'修复失败分析_先分类再逐题.md').exists())

    def test_last_task_artifact_drift_blocks_before_first_locator_or_budget(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);artifacts={}
            for name in ('job','gold','index'):
                path=root/(name+'.json');path.write_bytes(b'{}')
                artifacts.update({name+'_path':str(path),name+'_sha256':main.prepare.sha256(path)})
            tasks=[dict(artifacts,instance_id=str(i),repo='org/r'+str(i),base_commit='a'*40,
                        qualification_passed=True) for i in range(50)]
            tasks[-1]['gold_sha256']='0'*64
            roster=root/'roster.json';roster.write_text(json.dumps({'frozen':True,'tasks':tasks}))
            with mock.patch.object(main,'ROSTER',roster),mock.patch.object(main,'OUTPUT',root/'output'), \
                 mock.patch.object(main,'BudgetLedger') as ledger,mock.patch.object(main,'DeepSeekProvider') as provider, \
                 mock.patch.object(main.sources,'ensure_base') as source:
                with self.assertRaisesRegex(ValueError,'Frozen gold artifact'):
                    main.execute(argparse.Namespace(phase='run',wait_seconds=0))
                ledger.assert_not_called();provider.assert_not_called();source.assert_not_called()

    def test_callback_rechecks_gold_bytes_before_source_or_provider(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);task={'instance_id':'synthetic'}
            for name in ('job','gold','index'):
                path=root/(name+'.json');path.write_bytes(b'{}')
                task.update({name+'_path':str(path),name+'_sha256':main.prepare.sha256(path)})
            Path(task['index_path']).write_bytes(b'changed')
            with mock.patch.object(main.sources,'ensure_base') as source,mock.patch.object(main,'DeepSeekProvider') as provider:
                with self.assertRaisesRegex(ValueError,'Frozen index artifact'):
                    main.preparation_callback({},None,{})(task,root/'case')
                source.assert_not_called();provider.assert_not_called()


if __name__=='__main__':unittest.main()
