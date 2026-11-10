import unittest
from pathlib import Path
from unittest.mock import patch
from code_qwen3_rr4_rebench100.continue_run import dependency_result, record_dependency_block
from code_qwen3_rr4_rebench100.continuation_report import create
from code_qwen3_rr4_rebench100 import config as P

class ContinuationTests(unittest.TestCase):
    def item(self): return {'instance_id':'a__b-1','repo':'a/b','base_commit':'a'*40}
    def test_file_failure_is_explicit_nonmodel_dependency_not_fake_prediction(self):
        r=dependency_result(self.item(),{'status':'failed','error':'file_initial exceeds 65536 Qwen tokens'})
        self.assertFalse(r['model_called']);self.assertEqual(r['status'],'BLOCKED_SHARED_FILE_STAGE')
        self.assertEqual(r['http_attempts'],0);self.assertEqual(r['predicted_functions'],[])
    def test_valid_file_stage_cannot_be_replaced(self):
        for result in [{'status':'complete'},{'status':'failed','file_rank_after_reflection':['a.py']}]:
            with self.assertRaises(ValueError): dependency_result(self.item(),result)
    def test_existing_prediction_worker_is_never_replaced(self):
        with patch.object(Path,'exists',return_value=True),patch.object(P,'write') as writer:
            with self.assertRaises(RuntimeError):record_dependency_block(self.item(),{'status':'failed'})
            writer.assert_not_called()
    def test_derived_report_redirect_preserves_original_state_and_restores_reader(self):
        from code_qwen3_rr4_rebench100 import report
        before=P.read
        def original_create(**kwargs):
            self.assertIsNot(P.read,before);return 42
        with patch.object(report,'create',side_effect=original_create):self.assertEqual(create(),42)
        self.assertIs(P.read,before)

if __name__=='__main__':unittest.main()
