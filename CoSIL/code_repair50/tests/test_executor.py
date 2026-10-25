import unittest
import contextlib
import csv
import io
import json
import hashlib
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
    def test_old_newline_changed_patch_is_infrastructure_not_task_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);(folder/'gold').mkdir()
            (folder/'gold.diff').write_bytes(b'original\r\n')
            (folder/'gold/patch.diff').write_bytes(b'original\n')
            result={'gold_receipt':str(folder/'gold/result.json'),'qualification_passed':False,'system_blocked':False}
            corrected=Q.audit_gold_patch_identity(result)
            self.assertTrue(corrected['system_blocked'])
            self.assertEqual(corrected['reason'],'SYSTEM_PATCH_ARTIFACT_INTEGRITY')
            self.assertFalse(result['system_blocked'])
            self.assertEqual(Q.audit_gold_patch_identity(result),corrected)
            (folder/'gold/patch.diff').write_bytes(b'original\r\n')
            self.assertEqual(Q.audit_gold_patch_identity(result),result)
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
    def test_initial_base_status_is_exactly_empty_and_never_mutated(self):
        with tempfile.TemporaryDirectory() as temporary:
            container=Mock();container.exec_run.return_value=Mock(exit_code=0,output=b'')
            result=E.check_base_worktree(container,temporary)
            self.assertTrue(result['clean']);self.assertFalse(result['base_tree_mutated'])
            self.assertEqual((Path(temporary)/'base_worktree_status.txt').read_bytes(),b'')
            container.exec_run.assert_called_once_with(['git','status','--porcelain','--untracked-files=normal'],workdir='/testbed')
    def test_modified_untracked_or_unverifiable_base_stops_without_repair(self):
        for code,raw in [(0,b' M pkg/business.py\n'),(0,b'?? generated.py\n'),(128,b'fatal: unsafe repository\n')]:
            with self.subTest(returncode=code,status=raw),tempfile.TemporaryDirectory() as temporary:
                container=Mock();container.exec_run.return_value=Mock(exit_code=code,output=raw)
                with self.assertRaisesRegex(RuntimeError,'SYSTEM_BASE_WORKTREE_DIRTY'):
                    E.check_base_worktree(container,temporary)
                self.assertFalse(json.loads((Path(temporary)/'base_worktree_status.json').read_text())['clean'])
                self.assertEqual((Path(temporary)/'base_worktree_status.txt').read_bytes(),raw)
                self.assertEqual(container.exec_run.call_count,1)
    def test_old_clean_base_audit_binds_exact_empty_log_and_head(self):
        with tempfile.TemporaryDirectory() as temporary:
            live=Path(temporary);folder=live/'task/empty';folder.mkdir(parents=True)
            task={'instance_id':'task','base_commit':'a'*40,'image_reference':'pinned','empty_receipt':str(folder/'result.json')}
            E.save(folder/'result.json',{'image_reference':'pinned'})
            E.save(folder/'base_head.json',{'returncode':0,'head':'a'*40})
            (folder/'test_output.txt').write_text('+ git status\nHEAD detached\nnothing to commit, working tree clean\n+ git show\ncommit text\n>>>>> Start Test Output\n')
            with patch.object(E,'LIVE',live):
                saved=Q.audit_initial_base_identity(task)
                self.assertEqual(Q.audit_initial_base_identity(task),saved)
                self.assertTrue(E.read(saved)['before_business_and_test_patches'])
                (folder/'test_output.txt').write_text('+ git status\n?? unknown.py\n+ git show\nnothing to commit, working tree clean\n>>>>> Start Test Output\n')
                with self.assertRaisesRegex(RuntimeError,'SYSTEM_BASE_WORKTREE_DIRTY'):Q.audit_initial_base_identity(task)
                (folder/'test_output.txt').write_text('+ git reset --hard HEAD\n+ git status\nnothing to commit, working tree clean\n+ git show\n>>>>> Start Test Output\n')
                with self.assertRaisesRegex(RuntimeError,'SYSTEM_BASE_WORKTREE_DIRTY'):Q.audit_initial_base_identity(task)
    def test_explicit_clean_base_audit_does_not_accept_wrong_commit_or_raw_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            live=Path(temporary);folder=live/'task/empty';folder.mkdir(parents=True)
            task={'instance_id':'task','base_commit':'a'*40,'image_reference':'pinned','empty_receipt':str(folder/'result.json')}
            E.save(folder/'result.json',{'image_reference':'pinned','base_worktree_clean':True})
            E.save(folder/'base_head.json',{'returncode':0,'head':'a'*40})
            container=Mock();container.exec_run.return_value=Mock(exit_code=0,output=b'')
            E.check_base_worktree(container,folder)
            with patch.object(E,'LIVE',live):
                saved=Q.audit_initial_base_identity(task)
                self.assertEqual(E.read(saved)['evidence'],'EXPLICIT_PRE_BUSINESS_PATCH_PORCELAIN')
                (folder/'base_worktree_status.txt').write_bytes(b'?? new.py\n')
                with self.assertRaisesRegex(RuntimeError,'SYSTEM_BASE_WORKTREE_DIRTY'):Q.audit_initial_base_identity(task)
                with self.assertRaisesRegex(RuntimeError,'SYSTEM_BASE_COMMIT_MISMATCH'):
                    Q.audit_initial_base_identity({**task,'base_commit':'b'*40})
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
        for error in ['SYSTEM_DISK_CAPACITY: no room','permission denied','SYSTEM_IMAGE_PULL: offline',
                      'SYSTEM_BASE_COMMIT_MISMATCH','SYSTEM_BASE_WORKTREE_DIRTY']:
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
                frozen_review=(live/'first3_engineering_review.json').read_bytes()
                self.assertEqual(Q.run(3),result)
                self.assertEqual((live/'first3_engineering_review.json').read_bytes(),frozen_review)
            status=json.loads((live/'live_status.json').read_text())
            self.assertEqual([x['instance_id'] for x in status['selected']],['x2','y','z'])
            self.assertEqual(result['qualified_count'],3)
            self.assertFalse((live/'qualified50.json').exists())
    def test_fifty_successful_tests_cannot_freeze_without_clean_base_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary);live=out/'qualification_live'
            rows=[{'instance_id':f'task{i}','repo':f'repo{i}/project','candidate_rank':str(i+1)} for i in range(50)]
            with (out/'candidate_order.csv').open('w',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            def qualify(row,**kwargs):
                return {'instance_id':row['instance_id'],'task':row,'qualification_passed':True,
                        'gold_receipt':'g','empty_receipt':'e','system_blocked':False}
            with patch.object(E,'OUT',out),patch.object(E,'LIVE',live),patch.object(Q,'qualify_task',side_effect=qualify),patch.object(Q,'audit_initial_base_identity',side_effect=RuntimeError('SYSTEM_BASE_WORKTREE_DIRTY')),contextlib.redirect_stdout(io.StringIO()):
                result=Q.run(50)
            self.assertEqual(result['status'],'SYSTEM_BASE_IDENTITY_AUDIT_BLOCKED')
            self.assertFalse((live/'qualified50.json').exists())
            self.assertTrue((live/'base_identity_freeze_block.json').exists())

class ImageStorageSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        from code_repair50 import image_transport as T
        self.T=T
        for name,part in [('TRANSPORT_ROOT','legacy'),('DATA_TRANSPORT_ROOT','data'),('STORAGE_POLICY_ROOT','storage_policy'),('FRESH_POLICY_ROOT','dom_policy')]:
            p=self.root/part
            if part=='legacy':p.mkdir(mode=0o700)
            patched=patch.object(T,name,p);patched.start();self.addCleanup(patched.stop)
        manifest={'schemaVersion':2,'mediaType':T.DOCKER_MANIFEST,'config':{'mediaType':T.DOCKER_CONFIG,'digest':'sha256:'+'a'*64,'size':50},
                  'layers':[{'mediaType':T.DOCKER_GZIP_LAYER,'digest':'sha256:'+'b'*64,'size':10}]}
        digest='sha256:'+hashlib.sha256(json.dumps(manifest,separators=(',',':')).encode()).hexdigest()
        self.record={'manifest':manifest,'digest':digest,'image_reference':'swerebench/storage-test@'+digest}
        self.manifest=self.root/'manifest.json';self.manifest.write_text(json.dumps(self.record))
        self.task={'instance_id':'synthetic_storage','image_reference':self.record['image_reference'],'compressed_layer_bytes':10,'image_manifest_path':str(self.manifest)}

    def test_acquire_freezes_data_placement_before_calling_transport(self):
        T=self.T;T.activate_run_data_disk_image_policy();client=Mock();client.images.get.return_value.id='verified-runtime'
        def verified(*args,workdir):
            self.assertEqual(workdir.parent,T.DATA_TRANSPORT_ROOT)
            self.assertTrue(T._placement_path(workdir.name).is_file());self.assertTrue((workdir/'storage_placement.json').is_file())
            return {'runtime_image_reference':'verified-runtime','new_to_daemon':False,'loaded_by_this_run':False}
        with patch.object(E.shutil,'disk_usage',return_value=Mock(free=2**50)),patch.object(E,'digest',return_value='stage-source'),patch.object(T,'ensure_verified_image',side_effect=verified) as transport:
            _,owned,_=E.acquire_image(client,self.task,self.root/'receipt')
        self.assertFalse(owned);transport.assert_called_once()

    def test_acquire_keeps_existing_failed_legacy_scope_under_active_storage_policy(self):
        T=self.T;T.activate_run_data_disk_image_policy();old=T.TRANSPORT_ROOT/self.record['digest'].split(':')[1];old.mkdir(mode=0o700)
        (old/'initial_cache').mkdir();(old/'initial_cache/failure_receipt.json').write_text('{}')
        def failed(*args,workdir):
            self.assertEqual(workdir,old);raise ValueError('Preserved old failure')
        with patch.object(E.shutil,'disk_usage',return_value=Mock(free=2**50)),patch.object(E,'digest',return_value='stage-source'),patch.object(T,'ensure_verified_image',side_effect=failed):
            with self.assertRaisesRegex(ValueError,'old failure'):E.acquire_image(Mock(),self.task,self.root/'receipt')
        self.assertFalse((T.DATA_TRANSPORT_ROOT/old.name).exists())

    def test_acquire_duplicate_scopes_stops_before_transport(self):
        T=self.T;T.activate_run_data_disk_image_policy();name=self.record['digest'].split(':')[1]
        (T.TRANSPORT_ROOT/name).mkdir(mode=0o700);(T.DATA_TRANSPORT_ROOT/name).mkdir(mode=0o700)
        with patch.object(E.shutil,'disk_usage',return_value=Mock(free=2**50)),patch.object(E,'digest',return_value='stage-source'),patch.object(T,'ensure_verified_image') as transport:
            with self.assertRaisesRegex(ValueError,'Duplicate'):E.acquire_image(Mock(),self.task,self.root/'receipt')
        transport.assert_not_called()


if __name__=='__main__':unittest.main()
