"""Synthetic view isolation, slot and immutable-source regression tests."""
from pathlib import Path
import tempfile
import unittest
from .view import normalize_cosil,normalize_locagent,build_view,unique_inventory
from code_multiswe_java_20261117.common import write,read,sha

INDEX={'C.java':{'definitions':[{'kind':'function','qualified_name':'C.f(int,String)',
    'canonical_id':'C.java::C.f(int,String)','name':'f','start_line':1,'end_line':3}]}}


class ViewTests(unittest.TestCase):
    def test_failed_task_is_not_salvaged_by_replaying_a_sample(self):
        failed={'status':'failed','ranked_files':[],'ranked_functions':[],
            'samples':[{'raw_location':'C.java\nfunction: C.f(int, String)'}]}
        derived,proof=normalize_locagent(failed,INDEX)
        self.assertEqual(derived,failed);self.assertFalse(proof['view_applied'])
    def test_duplicate_inventory_cannot_certify_locagent_identity(self):
        duplicate={'C.java':{'definitions':INDEX['C.java']['definitions']*2}}
        with self.assertRaisesRegex(ValueError,'Ambiguous public inventory'):unique_inventory(duplicate)
    def test_unknown_and_duplicate_slots_never_disappear(self):
        original={'predicted_functions':[{'path':'C.java','qualified_name':None},
            {'path':'C.java','qualified_name':'C.f(int, String)'},
            {'path':'C.java','qualified_name':'C.f(int, String)'},
            {'path':'C.java','qualified_name':'C.f(AB, C)'}]}
        derived,audit=normalize_cosil(original,INDEX)
        self.assertEqual(len(derived['predicted_functions']),4)
        self.assertIsNone(derived['predicted_functions'][0]['qualified_name'])
        self.assertEqual(derived['predicted_functions'][1]['qualified_name'],'C.f(int,String)')
        self.assertEqual(derived['predicted_functions'][2]['qualified_name'],'C.f(int,String)')
        self.assertEqual(derived['predicted_functions'][3]['qualified_name'],'C.f(AB, C)')
        self.assertEqual(original['predicted_functions'][1]['qualified_name'],'C.f(int, String)')
        self.assertFalse(audit['Gold_read'])

    def test_pending_never_builds_partial_view(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);root=p/'root';root.mkdir()
            with self.assertRaisesRegex(RuntimeError,'every full128'):build_view(root,p/'view')
            self.assertFalse((p/'view').exists())

    def test_full_view_references_raw_calls_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'root';rows=[{'instance_id':f'i{i}','repo':'toy/java','base_commit':'a'*40} for i in range(128)]
            write(root/'allocation.json',{'n':128,'records':rows})
            (root/'evaluator_private').mkdir();secret=root/'evaluator_private/never_read.patch';secret.write_text('not an inference input')
            original_sha={}
            for row in rows:
                iid=row['instance_id'];write(root/'public'/iid/'code_index.json',INDEX)
                for arm in ('cosil','sfpruner','locagent'):
                    out=root/'run'/iid/arm;out.mkdir(parents=True)
                    terminal={'instance_id':iid,'arm':arm,'status':'preparation_blocked','keep_in_denominator':True}
                    if iid=='i0':
                        value={**row,'status':'complete','usage':{'prompt_tokens':5},'elapsed_seconds':1,
                            'predicted_functions':[{'path':'C.java','qualified_name':'C.f(int, String)'}],
                            'samples':[{'status':'complete','raw_location':'C.java\nfunction: C.f(int, String)'}],
                            'ranked_files':['C.java'],'ranked_functions':[]}
                        write(out/'result.json',value);write(out/'calls/actual_receipt.json',{'usage':'original'})
                        terminal.update(status='complete',result_sha256=sha(out/'result.json'))
                        original_sha[str(out/'result.json')]=sha(out/'result.json')
                    write(out/'terminal.json',terminal)
            write(root/'run/completion.json',{'status':'COMPLETE','allocated':128,'groups':128})
            view=build_view(root,Path(td)/'view')
            for path,expected in original_sha.items():self.assertEqual(sha(path),expected)
            result=read(view/'run/i0/locagent/result.json')
            self.assertEqual(result['samples'][0]['raw_location'],'C.java\nfunction: C.f(int, String)')
            self.assertEqual(result['ranked_functions'][0]['qualified_name'],'C.f(int,String)')
            self.assertEqual(result['usage'],{'prompt_tokens':5})
            self.assertTrue((view/'run/i0/cosil/calls').is_symlink())
            self.assertEqual(len(read(view/'allocation.json')['records']),128)
            self.assertFalse(read(view/'view_manifest.json')['normalization_uses_Gold'])
            self.assertEqual(read(view/'view_manifest.json')['new_model_calls'],0)


if __name__=='__main__':unittest.main()
