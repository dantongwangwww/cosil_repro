import unittest
import contextlib
import csv
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock,patch
from code_repair50 import executor as E
from code_repair50 import qualification as Q
from code_repair50.qualification import qualifies,system_failure

class QualificationTests(unittest.TestCase):
    def good(self):
        return {'test_completed':True,'resolved':True,'environment_error':False}
    def empty(self):
        return {'test_completed':True,'resolved':False,'environment_error':False,'fail_to_pass_actually_failed':1}
    def test_actual_gold_pass_and_observed_base_failure_required(self):
        self.assertTrue(qualifies(self.good(),self.empty()))
    def test_missing_or_unobserved_tests_cannot_qualify(self):
        for change in [{'test_completed':False},{'resolved':None},{'environment_error':True},{'fail_to_pass_actually_failed':0}]:
            self.assertFalse(qualifies(self.good(),{**self.empty(),**change}))
    def test_gold_failure_or_empty_success_cannot_qualify(self):
        self.assertFalse(qualifies({**self.good(),'resolved':False},self.empty()))
        self.assertFalse(qualifies(self.good(),{**self.empty(),'resolved':True}))
    def test_empty_patch_application_failure_does_not_qualify(self):
        self.assertFalse(qualifies(self.good(),{'resolved':False,'status':'PATCH_APPLICATION_FAILED'}))
    def test_pins_must_be_official_digest_references(self):
        self.assertTrue(E.valid_image_reference('swerebench/task@sha256:'+'a'*64))
        for value in ['swerebench/task:latest','untrusted/task@sha256:'+'a'*64,'swerebench/task@sha256:abc']:
            self.assertFalse(E.valid_image_reference(value))
    def test_preexisting_or_used_images_are_never_removed(self):
        client=Mock();image=Mock();image.id='sha256:original';client.images.get.return_value=image
        result=E.safe_remove_reference(client,'ref',{'sha256:original'},True)
        self.assertFalse(result['removed']);client.images.remove.assert_not_called()
        client.containers.list.return_value=[Mock(attrs={'Image':image.id})]
        result=E.safe_remove_reference(client,'ref',set(),True)
        self.assertFalse(result['removed']);client.images.remove.assert_not_called()
    def test_only_new_unused_image_reference_removed_without_force(self):
        client=Mock();client.images.get.return_value=Mock(id='new');client.containers.list.return_value=[]
        result=E.safe_remove_reference(client,'official@digest',set(),True)
        self.assertTrue(result['removed'])
        client.images.remove.assert_called_once_with('official@digest',force=False,noprune=True)
    def test_not_pulled_here_never_deleted(self):
        client=Mock();self.assertFalse(E.safe_remove_reference(client,'ref',set(),False)['removed'])
        client.images.get.assert_not_called()
    def test_limits_exclude_network_privilege_and_gpu(self):
        self.assertTrue(E.LIMITS['network_disabled']);self.assertEqual(E.LIMITS['cap_drop'],['ALL'])
        self.assertIn('no-new-privileges:true',E.LIMITS['security_opt'])
        self.assertNotIn('volumes',E.LIMITS);self.assertNotIn('device_requests',E.LIMITS)
    def test_scoring_nonconventional_path_is_private_and_protected(self):
        tests='diff --git a/pkg/checks.py b/pkg/checks.py\n--- a/pkg/checks.py\n+++ b/pkg/checks.py\n@@ -1 +1 @@\n-old\n+new\n'
        guard=E.scoring_test_guard('A',tests,tests)
        self.assertFalse(guard['passed']);self.assertEqual(guard['blocked_path_count'],1)
        self.assertNotIn('pkg/checks.py',json.dumps(guard))
        business='diff --git a/pkg/business.py b/pkg/business.py\n--- a/pkg/business.py\n+++ b/pkg/business.py\n@@ -1 +1 @@\n-old\n+new\n'
        self.assertTrue(E.scoring_test_guard('B',business,tests)['passed'])
        self.assertTrue(E.scoring_test_guard('QUAL_GOLD',tests,tests)['passed'])
        self.assertTrue(E.scoring_test_guard('QUAL_EMPTY','',tests)['passed'])
    def test_scoring_added_deleted_renamed_and_quoted_identities_checked(self):
        tests='diff --git "a/pkg/checks odd.py" "b/pkg/checks odd.py"\n'
        for header in ['diff --git "a/pkg/checks odd.py" b/pkg/renamed.py\n',
                       'diff --git a/pkg/other.py "b/pkg/checks odd.py"\n']:
            self.assertFalse(E.scoring_test_guard('A',header,tests)['passed'])
        self.assertEqual(E.diff_target_paths('diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\n'),{'café.py'})
        with self.assertRaises(ValueError):E.scoring_test_guard('A','--- a/x\n+++ b/x\n',tests)
        self.assertTrue(E.scoring_test_guard('A','',tests)['passed'])
    def test_capacity_permission_pull_failure_is_a_system_stop(self):
        for error in ['SYSTEM_DISK_CAPACITY: no room','permission denied','SYSTEM_IMAGE_PULL: offline']:
            self.assertTrue(system_failure({'error':error}))
        self.assertFalse(system_failure({'resolved':False,'status':'TEST_COMPLETED'}))
        self.assertTrue(system_failure({'error_type':'SYSTEM_IMAGE_IDENTITY','underlying_error_type':'ImageNotFound'}))
    def test_unqualified_or_wrong_arm_never_launches_formal_worker(self):
        with patch.object(E,'launch_worker') as run:
            with self.assertRaises(RuntimeError):
                E.run_evaluation('x','A','unused',task={'instance_id':'x','qualification_passed':False})
            with self.assertRaises(ValueError):
                E.run_evaluation('x','OTHER','unused',task={'instance_id':'x','qualification_passed':True})
            run.assert_not_called()
    def test_failed_candidate_does_not_reserve_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary);live=out/'qualification_live'
            rows=[{'instance_id':'x1','repo':'same/repo','candidate_rank':'1'},
                  {'instance_id':'x2','repo':'same/repo','candidate_rank':'2'},
                  {'instance_id':'y','repo':'other/repo','candidate_rank':'3'},
                  {'instance_id':'z','repo':'third/repo','candidate_rank':'4'}]
            with (out/'candidate_order.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            def qualify(row,**kwargs):
                return {'instance_id':row['instance_id'],'task':row,'qualification_passed':row['instance_id']!='x1',
                        'gold_receipt':'g','empty_receipt':'e','system_blocked':False}
            with patch.object(E,'OUT',out),patch.object(E,'LIVE',live),patch.object(Q,'qualify_task',side_effect=qualify),contextlib.redirect_stdout(io.StringIO()):
                result=Q.run(3)
            status=json.loads((live/'live_status.json').read_text())
            self.assertEqual([x['instance_id'] for x in status['selected']],['x2','y','z'])
            self.assertEqual(result['qualified_count'],3)
            self.assertFalse((live/'qualified50.json').exists())

if __name__=='__main__':unittest.main()
