"""Offline Git-object recovery verification; no HTTP, GPU or model requests."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import recover_git_sources as g
import build_runtime as b
from test_build_runtime import prep,selection


class GitSourceTests(unittest.TestCase):
    def fixture(self,root,include_bad=True):
        row=prep();row['base_files_sha256']={'module.py':b.digest(b'def f():\n    return 1\n')}
        record=selection(row);selected={'status':'READY','selection_frozen':True,'n':1,'records':[record]}
        b.write(root/'selection.json',selected);b.write(root/'preparations.json',{'records':[row]})
        raws={'module.py':b'def f():\n    return 1\n','empty.py':b''}
        if include_bad:raws['bad.py']=b'# coding: zlatin-1\nprint(1)\n'
        entries=[];refs=[];cache=root/'git_blob_cache';cache.mkdir()
        for path,raw in raws.items():
            blob=g.git_blob_sha(raw);body=cache/(blob+'.raw');receipt=cache/(blob+'.json')
            body.write_bytes(raw);b.write(receipt,{'status':'complete','blob_sha':blob,'sha256':b.digest(raw),'bytes':len(raw),'transport':'fixture'})
            entries.append({'path':path,'type':'blob','mode':'100644','sha':blob,'size':len(raw)})
            refs.append({'instance_id':row['instance_id'],'identity_repo':row['repo'],'repo':row['repo'],
                         'base':row['base_commit'],'path':path,'blob_sha':blob,'blob_size':len(raw),
                         'cache_body':str(body.resolve()),'cache_receipt':str(receipt.resolve())})
        entries.extend([{'path':'README.md','type':'blob','mode':'100644','sha':g.git_blob_sha(b'public readme'),'size':13},
                        {'path':'linked.py','type':'blob','mode':'120000','sha':g.git_blob_sha(b'module.py'),'size':9}])
        tree=root/'tree.json';b.write(tree,{'truncated':False,'tree':entries})
        paths=sorted(list(raws)+['README.md'])
        case={'instance_id':row['instance_id'],'identity_repo':row['repo'],'transport_repo':row['repo'],
              'base_commit':row['base_commit'],'tree_path':str(tree.resolve()),'tree_sha256':b.sha(tree),
              'regular_file_paths':paths,'python_files':len(raws)}
        plan={'selection_sha256':b.sha(root/'selection.json'),'preparations_sha256':b.sha(root/'preparations.json'),
              'records':refs,'file_references':refs,'cases':[case]}
        b.write(root/'plan.json',plan)
        private=root/'v1_private'
        b.write(private/'contract.json',{'builder_sha256':b.sha(b.__file__),
                'selection_sha256':b.sha(root/'selection.json'),'preparations_sha256':b.sha(root/'preparations.json')})
        b.write(private/'progress.json',{'selected':1,'complete':0,'blocked':{
                row['instance_id']:{'error':'BLOCKED_ARCHIVE_DOWNLOAD: fixture timeout'}}})
        return row,plan,raws

    def test_git_header_object_sha_and_empty_blob_are_exact(self):
        self.assertEqual(g.git_blob_sha(b''),'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);row,plan,raws=self.fixture(root)
            self.assertTrue(g.check_cache(plan)['ready'])
            empty=next(r for r in plan['records'] if r['blob_size']==0)
            self.assertEqual(g.cache_bytes(empty),b'')

    def test_raw_and_receipt_tampering_refuse_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,plan,_=self.fixture(root);ref=plan['records'][0]
            Path(ref['cache_body']).write_bytes(b'changed')
            self.assertFalse(g.check_cache(plan)['ready'])
            self.assertTrue(g.check_cache(plan)['invalid'])

    def test_truncated_tree_missing_inventory_and_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,plan,_=self.fixture(root)
            tree=b.read(root/'tree.json');tree['truncated']=True
            b.write(root/'tree.json',tree,immutable=False);plan['cases'][0]['tree_sha256']=b.sha(root/'tree.json')
            b.write(root/'plan.json',plan,immutable=False)
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                g.validate_plan(root/'plan.json',root/'selection.json',root/'preparations.json')
            tree['truncated']=False;b.write(root/'tree.json',tree,immutable=False)
            plan['cases'][0]['tree_sha256']=b.sha(root/'tree.json');plan['file_references']=plan['file_references'][:-1]
            b.write(root/'plan.json',plan,immutable=False)
            with self.assertRaisesRegex(ValueError,'inventory'):
                g.validate_plan(root/'plan.json',root/'selection.json',root/'preparations.json')

    def test_actual_cpu_build_has_complete_menu_only_python_bodies_and_frozen_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);row,plan,raws=self.fixture(root)
            old_progress=b.sha(root/'v1_private/progress.json')
            result=g.finalize(root/'plan.json',root/'selection.json',root/'preparations.json',root/'runtime',
                              root/'v1_private',root/'links_private',root/'git_private',expected_count=1)
            self.assertEqual(result['status'],'READY')
            task=root/'runtime/tasks'/row['instance_id'];job=b.read(task/'job.json')
            self.assertEqual(job['paths'],plan['cases'][0]['regular_file_paths'])
            self.assertFalse((task/'snapshot/README.md').exists())
            self.assertFalse((task/'snapshot/linked.py').exists())
            for path,raw in raws.items():self.assertEqual((task/'snapshot'/path).read_bytes(),raw)
            self.assertEqual(b.read(task/'render_cache.json')['preparation_adapter']['decode_error_files'],1)
            self.assertEqual(b.sha(root/'v1_private/progress.json'),old_progress)
            proof=b.read(root/'v1_private/finalization_receipt.json')
            self.assertEqual(proof['manifest_sha256'],b.sha(root/'runtime/manifest.json'))
            again=g.finalize(root/'plan.json',root/'selection.json',root/'preparations.json',root/'runtime',
                              root/'v1_private',root/'links_private',root/'git_private',expected_count=1)
            self.assertEqual(again,result)
            receipt=b.read(root/'git_private/cases'/(row['instance_id']+'.json'))
            self.assertIn('non-Python bodies not downloaded',receipt['source_scope'])
            self.assertFalse(list(root.rglob('*.tar.gz')))

    def test_missing_cache_never_writes_partial_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,plan,_=self.fixture(root)
            Path(plan['records'][0]['cache_body']).unlink()
            result=g.finalize(root/'plan.json',root/'selection.json',root/'preparations.json',root/'runtime',
                              root/'v1_private',root/'links_private',root/'git_private',expected_count=1)
            self.assertEqual(result['status'],'WAIT_CACHE')
            self.assertFalse((root/'runtime/manifest.json').exists())

    def test_cache_locations_and_original_input_binding_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,plan,_=self.fixture(root)
            changed=copy.deepcopy(plan);changed['file_references'][0]['cache_body']=str(root/'outside.raw')
            b.write(root/'bad_plan.json',changed)
            with self.assertRaisesRegex(ValueError,'escaped'):
                g.validate_plan(root/'bad_plan.json',root/'selection.json',root/'preparations.json')
            contract=b.read(root/'v1_private/contract.json');contract['selection_sha256']='0'*64
            b.write(root/'v1_private/contract.json',contract,immutable=False)
            with self.assertRaisesRegex(ValueError,'selection/preparation'):
                g.finalize(root/'plan.json',root/'selection.json',root/'preparations.json',root/'runtime',
                           root/'v1_private',root/'links_private',root/'git_private',expected_count=1)


if __name__=='__main__':unittest.main()
