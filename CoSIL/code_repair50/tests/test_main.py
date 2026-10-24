import tempfile
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


if __name__=='__main__':unittest.main()
