import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from filtered265 import prepare as P


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.patches = [patch.object(P.C, 'ROOT', self.root), patch.object(P, 'PRIVATE', self.root / 'evaluator_private/filtered265')]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in self.patches[::-1]: item.stop()
        self.temporary.cleanup()

    def row(self, iid='org__repo-1'):
        return dict(instance_id=iid, repo='org/repo', base_commit='a'*40, problem_statement='issue')

    def screen_record(self, iid='org__repo-1', **updates):
        r=dict(self.row(iid), sampling_hash=P.digest(f'{P.NAMESPACE}|{P.C.SEED}|{iid}'), qualified=True,
               four_filter_pass=True, history_pass=True, four_filter_reasons=[], history_reasons=[],
               all_reasons=['one_issue_per_repository_after_four_and_history'])
        r.update(updates);return r

    def test_all_qualified_keep_repeated_repository_and_obsolete_suggestion(self):
        rs=[self.screen_record('org__repo-2'),self.screen_record()]
        out=P.qualified_records({'records':rs},2)
        self.assertEqual({r['instance_id']for r in out},{r['instance_id']for r in rs})
        self.assertEqual([r['sampling_hash']for r in out],sorted(r['sampling_hash']for r in rs))

    def test_qualified_requires_all_four_and_history(self):
        for change in ({'history_pass':False},{'four_filter_reasons':['files_gt1']},{'history_reasons':['protected_split_id']}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                P.qualified_records({'records':[self.screen_record(**change)]},1)

    def test_wrong_hash_and_duplicate_identity_rejected(self):
        with self.assertRaises(RuntimeError):P.qualified_records({'records':[self.screen_record(sampling_hash='wrong')]},1)
        with self.assertRaises(RuntimeError):P.qualified_records({'records':[self.screen_record(),self.screen_record()]},2)

    def test_clean_job_rejects_patch_and_keeps_sorted_exact_menu(self):
        row=self.row();j=dict(row,cohort='c',snapshot='s',paths=['a.py','b.py'],code_index='i',structure='t')
        P.check_clean_job(j,row)
        with self.assertRaises(RuntimeError):P.check_clean_job(dict(j,patch='label'),row)
        with self.assertRaises(RuntimeError):P.check_clean_job(dict(j,paths=['b.py','a.py']),row)

    def test_immutable_write_refuses_old_root_and_content_change(self):
        p=self.root/'snapshots/a.py';P.write_bytes(p,b'old');P.write_bytes(p,b'old')
        with self.assertRaises(RuntimeError):P.write_bytes(p,b'new')
        with self.assertRaises(PermissionError):P.write_bytes(self.root.parent/'outside.py',b'x')

    def test_cached_snapshot_copies_all_python_including_unparseable(self):
        old=self.root/'old';old.mkdir();(old/'a.py').write_bytes(b'def f(:\n');(old/'b.py').write_bytes(b'x=1\n')
        paths=['a.py','b.py','readme.md'];q={'snapshot_python_sha256':{p:P.digest((old/p).read_bytes())for p in paths if p.endswith('.py')}}
        out,hashes=P.copied_snapshot({'snapshot':str(old),'paths':paths},q,self.root/'new')
        self.assertEqual(out,paths);self.assertEqual(len(hashes),2);self.assertEqual((old/'a.py').read_bytes(),b'def f(:\n')
        (old/'b.py').write_bytes(b'x=2\n')
        with self.assertRaises(RuntimeError):P.copied_snapshot({'snapshot':str(old),'paths':paths},q,self.root/'other')

    def archive(self):
        p=self.root/'base.tar.gz'
        with tarfile.open(p,'w:gz')as tf:
            for name,data in [('repo-sha/a.py',b'def f():\n    return 1\n'),('repo-sha/README.md',b'text'),('repo-sha/../evil.py',b'bad'),('repo-sha/vendor/x.py',b'bad')]:
                info=tarfile.TarInfo(name);info.size=len(data);tf.addfile(info,io.BytesIO(data))
            info=tarfile.TarInfo('repo-sha/link.py');info.type=tarfile.SYMTYPE;info.linkname='/etc/passwd';tf.addfile(info)
        return {'status':'ready','transport':'github_codeload_base_sha','archive':str(p),'sha256':P.C.sha(p)}

    def test_safe_snapshot_preserves_nonpython_inventory_but_extracts_only_safe_python(self):
        transport=self.archive();valid=lambda p:bool(p)and not p.startswith('/')and'..'not in Path(p).parts and'vendor'not in Path(p).parts
        paths,hashes,index=P.extract_snapshot(transport,self.root/'snap',valid,1000,lambda b:b.decode(),lambda p,t:{'path':p,'text':t})
        self.assertEqual(paths,['README.md','a.py']);self.assertFalse((self.root/'snap/README.md').exists());self.assertEqual(set(index),{'a.py'});self.assertEqual(len(hashes),1)

    def test_archive_sha_and_frozen_size_cap_are_enforced(self):
        t=self.archive();valid=lambda p:True
        with self.assertRaises(RuntimeError):P.extract_snapshot(dict(t,sha256='bad'),self.root/'s',valid,1000,lambda b:b.decode(),lambda p,t:{})
        with self.assertRaises(RuntimeError):P.extract_snapshot(t,self.root/'s',valid,1,lambda b:b.decode(),lambda p,t:{})

    def test_resume_verifies_all_receipted_bytes(self):
        p=self.root/'a';p.write_bytes(b'one');r={'data_sha256':{str(p):P.C.sha(p)},'snapshot_sha256':{}}
        P.verify_hashes(r);p.write_bytes(b'two')
        with self.assertRaises(RuntimeError):P.verify_hashes(r)

    def test_failed_preparation_retains_identity_and_writes_explicit_failure(self):
        record={'instance_id':'org__repo-1','job':str(self.root/'j.json'),'origin':'new221'}
        with patch.object(P,'space_guard',side_effect=RuntimeError('guard')):
            value=P.prepare_one(record,self.row())
        self.assertEqual(value['instance_id'],record['instance_id']);self.assertEqual(value['preparation_status'],'failed')
        receipt=P.C.load(P.PRIVATE/'preparation/org__repo-1.json')
        self.assertTrue(receipt['retained_in_manifest']);self.assertEqual(receipt['model_calls'],0)

    def test_patch_never_enters_worker_preparation(self):
        record={'instance_id':'org__repo-1','job':str(self.root/'j.json')}
        with patch.object(P,'space_guard'):
            value=P.prepare_one(record,dict(self.row(),patch='secretlabel'))
        self.assertIn('Only identity/issue',value['preparation_error_message'])

    def test_disk_guard_only_actual_project_volume_and_tmp_at_10GiB(self):
        class Space:free=10*1024**3
        with patch.object(P.shutil,'disk_usage',return_value=Space()) as disk:
            P.space_guard()
        self.assertEqual([c.args[0] for c in disk.call_args_list],[self.root.resolve(),Path('/tmp')])
        self.assertNotIn(P.C.COSIL,[c.args[0] for c in disk.call_args_list])

    def test_disk_guard_does_not_reduce_10GiB_threshold(self):
        class Space:free=10*1024**3-1
        with patch.object(P.shutil,'disk_usage',return_value=Space()),self.assertRaises(RuntimeError):P.space_guard()

    def test_no_execution_qualification_claimed(self):
        r=P.execution_qualification()
        self.assertEqual(r['gold_patch_pass'],'NOT_CHECKED');self.assertEqual(r['empty_patch_fail'],'NOT_CHECKED')
        self.assertFalse(r['cq2_complete_qualification_claimed'])

    def test_worker_limit_rejected_before_any_preparation(self):
        for n in (0,5):
            with self.assertRaises(ValueError):P.prepare(n)


if __name__=='__main__':unittest.main()
