"""Small hermetic CPU fixtures; no real dataset/Gold/model is read."""
from contextlib import contextmanager
from pathlib import Path
import tempfile,unittest
from unittest import mock

from . import prepare as p


@contextmanager
def fixture():
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);stage=root/'old_public';stage.mkdir();iid='org__pkg-1'
  row={'instance_id':iid,'repo':'org/pkg','base_commit':'a'*40,'train_repo_seen':False}
  job={**{k:row[k] for k in p.IDENTITY},'problem_statement':'Public issue','cohort':'fixture','snapshot':str(root/'snapshot'),'paths':['pkg.py'],'code_index':str(root/'index.json'),'structure':str(root/'structure.json')}
  snapshot=root/'snapshot';snapshot.mkdir();(snapshot/'pkg.py').write_text('def f():\n    return 1\n')
  index={'pkg.py':{'raw_sha256':p.sha(snapshot/'pkg.py'),'definitions':[{'kind':'function','qualified_name':'f'}]}}
  p.write(root/'index.json',index);p.write(root/'structure.json',{'pkg.py':{}})
  public=dict(job,snapshot='/snapshot',code_index='/input/code_index.json',structure='/input/repo_structures/'+iid+'.json')
  p.write(stage/'job.json',public);p.write(stage/'code_index.json',index);p.write(stage/'repo_structures'/(iid+'.json'),{})
  p.write(stage/'render_cache.json',{'format':'fixture','functions':{},'edges':[]})
  source={'job_sha256':'b'*64,'snapshot':str(snapshot)}
  p.write(stage/'public_receipt.json',{'original_job_sha256':source['job_sha256'],'source_snapshot':str(snapshot),'base_commit':row['base_commit'],'index_sha256':p.sha(stage/'code_index.json'),'render_cache_sha256':p.sha(stage/'render_cache.json'),'gold_or_patch_read':False})
  result={**{k:row[k] for k in p.IDENTITY},'ranked_edit_files':[],'file_rank_after_reflection':['pkg.py'],'raw_file_responses':['pkg.py'],'predicted_functions':[{'path':'DO_NOT_COPY','qualified_name':'secret'}]}
  p.write(stage/'shared.json',p.shared_payload(result,row))
  prepared={'source':source,'staged_sha256':{str(f.relative_to(stage)):p.sha(f) for f in stage.rglob('*') if f.is_file() and f.name!='shared.json'}}
  yield root,stage,row,job,prepared,result


class PublicProjectionTests(unittest.TestCase):
 def test_four_field_projection_never_copies_function_prediction(self):
  with fixture() as (_,_,row,_,_,result):
   value=p.shared_payload(result,row)
   self.assertEqual(set(value),p.SHARED_KEYS);self.assertNotIn('DO_NOT_COPY',str(value))
 def test_file_stage_presence_gate_not_correctness_filter(self):
  with fixture() as (_,_,row,_,_,result):
   result['file_rank_after_reflection']=[]
   self.assertEqual(p.shared_payload(result,row)['files'],[])
   del result['ranked_edit_files'];self.assertIsNone(p.shared_payload(result,row))
 def test_wrong_base_same_iid_refused(self):
  with fixture() as (_,_,row,_,_,result):
   result['base_commit']='c'*40
   with self.assertRaisesRegex(ValueError,'identity/base'):p.shared_payload(result,row)
 def test_private_shared_field_refused(self):
  with fixture() as (_,stage,row,_,_,result):
   value=p.read(stage/'shared.json');value['gold_functions']=['pkg.py::f']
   with self.assertRaisesRegex(ValueError,'four public'):p.validate_shared(value,result,row)
 def test_wrong_shared_base_or_candidate_list_refused(self):
  with fixture() as (_,stage,row,_,_,result):
   value=p.read(stage/'shared.json');value['base_commit']='c'*40
   with self.assertRaises(ValueError):p.validate_shared(value,result,row)
 def test_clean_stage_and_copy_exact_bytes(self):
  with fixture() as (root,stage,row,job,prepared,result):
   files=p.validate_stage(stage,row,job,prepared,result)
   target=root/'inputs'/row['instance_id'];p.copy_public(stage,target,files)
   self.assertEqual(p.public_files(target,row['instance_id']),files)
   p.copy_public(stage,target,files)
 def test_toxic_job_field_refused_even_rehashed(self):
  with fixture() as (_,stage,row,job,prepared,result):
   v=p.read(stage/'job.json');v['ground_truth']=['pkg.py::f'];(stage/'job.json').unlink();p.write(stage/'job.json',v)
   prepared['staged_sha256']['job.json']=p.sha(stage/'job.json')
   with self.assertRaisesRegex(ValueError,'nine clean'):p.validate_stage(stage,row,job,prepared,result)
 def test_toxic_public_receipt_refused_even_rehashed(self):
  with fixture() as (_,stage,row,job,prepared,result):
   v=p.read(stage/'public_receipt.json');v['patch']='hidden';(stage/'public_receipt.json').unlink();p.write(stage/'public_receipt.json',v)
   prepared['staged_sha256']['public_receipt.json']=p.sha(stage/'public_receipt.json')
   with self.assertRaisesRegex(ValueError,'receipt drift'):p.validate_stage(stage,row,job,prepared,result)
 def test_extra_private_file_or_symlink_refused(self):
  with fixture() as (_,stage,row,job,prepared,result):
   (stage/'gold.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'inventory'):p.validate_stage(stage,row,job,prepared,result)
   (stage/'gold.json').unlink();(stage/'leak.py').symlink_to(stage/'job.json')
   with self.assertRaisesRegex(ValueError,'Symlink'):p.validate_stage(stage,row,job,prepared,result)
 def test_foreign_shared_key_and_missing_raw_evidence(self):
  with fixture() as (_,_,row,_,_,result):
   result.pop('raw_file_responses')
   with self.assertRaisesRegex(ValueError,'raw evidence'):p.shared_payload(result,row)


class FrozenManifestTests(unittest.TestCase):
 def test_prepare_uses_fixed_order_and_no_dispatch_denominator(self):
  with tempfile.TemporaryDirectory() as tmp:
   parent=Path(tmp)/'old';parent.mkdir();root=Path(tmp)/'new';root.mkdir()
   p.write(root/'protocol.json',{'arms':list(p.ARMS),'allocated':3})
   rows=[{'instance_id':'i'+str(k),'repo':'org/pkg','base_commit':'a'*40} for k in range(3)]
   origins={r['instance_id']:None for r in rows}
   def one(root,row,rank,origin):
    rp=root/'prepared_receipts'/(row['instance_id']+'.json');p.write(rp,{'public_only':True})
    return {**row,'rank':rank,'upstream_status':'ready' if rank==1 else ('source_preparation_blocked' if rank==2 else 'upstream_file_stage_unavailable'),'no_model_dispatch':rank!=1,'prepared_receipt_path':str(rp),'public_files_sha256':{},'upstream_files_sha256':{},'public_input_path':None}
   with mock.patch.object(p,'load_sources',return_value=(rows,origins,{})),mock.patch.object(p,'prepare_one',side_effect=one):
    value=p.prepare(root,parent,expected_total=3,workers=2)
   self.assertEqual([r['instance_id'] for r in value['records']],[r['instance_id'] for r in rows])
   self.assertEqual(value['allocated'],3);self.assertEqual(sum(r['no_model_dispatch'] for r in value['records']),2)
   authority=p.read(root/'authority.json');self.assertFalse(authority['Gold_parsed']);self.assertFalse(authority['models_called'])
   self.assertEqual(authority['manifest_sha256'],p.sha(root/'manifest.json'))
   with self.assertRaises(FileExistsError):p.prepare(root,parent,expected_total=3)
 def test_historical_root_and_wrong_arm_set_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p.write(root/'protocol.json',{'arms':['baseline'],'allocated':560})
   with self.assertRaises(ValueError):p.prepare(root,root)
   child=root/'new';child.mkdir();p.write(child/'protocol.json',{'arms':['baseline'],'allocated':560})
   with self.assertRaises(ValueError):p.prepare(child,root)


if __name__=='__main__':unittest.main()
