"""Synthetic projection and exact Git-archive semantics; no benchmark labels read."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from dsimple_v2 import lite_prepare as P
from dsimple_v2 import common as C


class LitePrepareTests(unittest.TestCase):
    def test_protected_rows_and_test_columns_not_materialized(self):
        import pyarrow as pa,pyarrow.ipc as ipc
        with tempfile.TemporaryDirectory(prefix='lite-projection-test-') as directory:
            root=Path(directory);old=root/'old';(old/'manifests').mkdir(parents=True)
            protected=[str(i) for i in range(30)]+['outside-'+str(i) for i in range(18)]
            (old/'manifests/excluded_ids.json').write_text(json.dumps({'ids':protected}))
            (old/'manifests/dataset_pin.json').write_text(json.dumps({'used_revision':'synthetic'}))
            rows=[{'instance_id':str(i),'repo':'r/r','base_commit':'a'*40,'problem_statement':'PROTECTED_SECRET' if i<30 else 'allowed',
                   'patch':'PROTECTED_PATCH' if i<30 else 'allowed patch','test_patch':'NEVER_PROJECT_THIS'} for i in range(300)]
            arrow=root/'data.arrow'
            table=pa.Table.from_pylist(rows)
            with pa.OSFile(str(arrow),'wb') as stream:
                with ipc.new_stream(stream,table.schema) as writer:writer.write_table(table)
            with patch.object(C,'FROZEN',old),patch.object(P,'DATA',arrow):output,receipt=P.load_projected_rows()
            self.assertEqual(len(output),270)
            serialized=json.dumps(output)
            self.assertNotIn('PROTECTED_SECRET',serialized);self.assertNotIn('PROTECTED_PATCH',serialized);self.assertNotIn('NEVER_PROJECT_THIS',serialized)
            self.assertTrue(all(set(r)==set(P.SAFE_FIELDS) for r in output))
            self.assertFalse(receipt['protected_rows_materialized']);self.assertFalse(receipt['test_harness_columns_read'])
            self.assertEqual(receipt['protected_lite_n'],30)

    def make_git(self,directory,attribute=True):
        root=Path(directory);subprocess.run(['git','init','-q',str(root)],check=True)
        (root/'f.py').write_text('COMMIT = "$Format:%H$"\ndef f():\n    return COMMIT\n')
        if attribute:(root/'.gitattributes').write_text('f.py export-subst\n')
        subprocess.run(['git','-C',str(root),'add','.'],check=True)
        subprocess.run(['git','-C',str(root),'-c','user.name=CPU fixture','-c','user.email=fixture@example.invalid','commit','-qm','base'],check=True)
        commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
        blob=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD:f.py'],text=True).strip()
        archived=subprocess.check_output(['git','--git-dir',str(root/'.git'),'archive',commit,'f.py'])
        with tarfile.open(fileobj=io.BytesIO(archived)) as stream:raw=stream.extractfile('f.py').read()
        return root/'.git',commit,blob,raw

    def test_export_subst_matches_original_archive_and_never_rewrites_blob(self):
        with tempfile.TemporaryDirectory(prefix='lite-archive-test-') as directory:
            mirror,commit,blob,raw=self.make_git(directory)
            index_before=hashlib.sha256((mirror/'index').read_bytes()).hexdigest()
            proof=P.verify_base_archive_file(mirror,commit,'f.py',raw,blob)
            self.assertIn('export-subst',proof['reason']);self.assertEqual(proof['snapshot_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertTrue(proof['attribute_witnesses'])
            self.assertEqual(hashlib.sha256((mirror/'index').read_bytes()).hexdigest(),index_before)
            self.assertNotEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),blob)

    def test_nonarchive_source_is_rejected_even_when_export_subst_is_set(self):
        with tempfile.TemporaryDirectory(prefix='lite-invalid-archive-test-') as directory:
            mirror,commit,blob,raw=self.make_git(directory)
            with self.assertRaisesRegex(RuntimeError,'differs from same-base'):P.verify_base_archive_file(mirror,commit,'f.py',raw+b'\n# injected',blob)

    def test_blob_mismatch_without_export_attribute_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='lite-no-attribute-test-') as directory:
            mirror,commit,blob,raw=self.make_git(directory,False)
            self.assertIsNone(P.verify_base_archive_file(mirror,commit,'f.py',raw,blob))
            with self.assertRaisesRegex(RuntimeError,'without verified export-subst'):P.verify_base_archive_file(mirror,commit,'f.py',raw+b'\n',blob)

    def test_same_id_repair_forbidden_after_online_freeze(self):
        with tempfile.TemporaryDirectory(prefix='lite-repair-test-') as directory:
            run=Path(directory);(run/'lite_online_freeze.json').write_text('{}')
            with patch.object(C,'RUN',run),self.assertRaisesRegex(RuntimeError,'after online source freeze'):P.repair_failed()

if __name__=='__main__':unittest.main()
