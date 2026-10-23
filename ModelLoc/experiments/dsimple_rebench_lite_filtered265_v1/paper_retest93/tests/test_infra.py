import copy,hashlib,importlib,io,json,os,sys,tarfile,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from paper_retest93 import bootstrap as B,common as C,prepare as P,runtime as R,transport as T

class FinanceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.finance=self.root/'finance';self.finance.mkdir();self.run=self.root/'run';self.run.mkdir();self.bp=self.finance/'budget.json'
  self.old={'key':'D-SIMPLE|i0','status':'usage_received','charged_upper_usd':6.,'total_tokens_upper':500000,'usage':{'prompt_tokens':499999,'completion_tokens':1}}
  self.ledger={'stage_cap_usd':5.,'attempts':{'historical':copy.deepcopy(self.old)},'cases':{'D-SIMPLE|i0':{'charged_upper_usd':6.,'total_tokens_upper':500000,'soft_triggered':True}}}
  self.bp.write_text(json.dumps(self.ledger));(self.finance/'budget.lock').write_text('')
  for name in ['budget_stop.json','user_pause.json']:(self.finance/name).write_text(json.dumps({'reason':'historic marker preserved'}))
  self.patches=[patch.object(C,'SHARED_BUDGET',self.bp),patch.object(C,'RUN',self.run)]
  for p in self.patches:p.start()
  st=self.finance.stat();self.policy={'shared_budget_contract':{'logical_budget':str(self.bp),'resolved_budget':str(self.bp.resolve()),'parent_device':st.st_dev,'parent_inode':st.st_ino},'no_total_cap':True,'no_per_case_cap':True,'no_token_cap':True,'allowed_ids':['i'+str(i) for i in range(93)],'baseline_attempt_sha256':{'historical':B.digest(self.old)},'protected_case_sha256':{},'ignored_historic_budget_stop_sha256':C.sha(self.finance/'budget_stop.json'),'protected_old200_pause_sha256':C.sha(self.finance/'user_pause.json'),'configuration_sha256':'fakeconfig'}
  B.set_policy(self.policy);(self.run/'activation.json').write_text(json.dumps({'authorized':True,'remove_all_fee_and_token_caps':True,'fresh_seven_calls_for93':True,'configuration_sha256':'fakeconfig'}));self.provider=types.SimpleNamespace(BudgetExceeded=type('BudgetExceeded',(RuntimeError,),{}))
 def tearDown(self):
  B._POLICY=None
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def test_removed_total_percase_and_400k_caps_preserve_old_entries(self):
  stopsha=C.sha(self.finance/'budget_stop.json');B.reserve(self.provider,'D-SIMPLE|i0','fresh',2000000,6144,token_upper=1000000)
  x=json.loads(self.bp.read_text());self.assertEqual(x['attempts']['historical'],self.old);self.assertEqual(x['stage_cap_usd'],5.);self.assertGreater(x['cases']['D-SIMPLE|i0']['charged_upper_usd'],6);self.assertGreater(x['cases']['D-SIMPLE|i0']['total_tokens_upper'],400000);self.assertEqual(C.sha(self.finance/'budget_stop.json'),stopsha)
 def test_missing_activation_never_mutates_finance(self):
  before=self.bp.read_bytes();(self.run/'activation.json').unlink()
  with self.assertRaises(PermissionError):B.reserve(self.provider,'D-SIMPLE|i0','fresh',1000,6144,token_upper=1000)
  self.assertEqual(before,self.bp.read_bytes())
 def test_original_attempt_tamper_rejected(self):
  x=copy.deepcopy(self.ledger);x['attempts']['historical']['charged_upper_usd']=0
  with self.assertRaises(B.BudgetIntegrityError):B.validate_ledger(x)
 def test_selected_case_prior_charge_cannot_be_erased(self):
  x=copy.deepcopy(self.ledger);x['cases']['D-SIMPLE|i0']['charged_upper_usd']=0
  with self.assertRaises(B.BudgetIntegrityError):B.validate_ledger(x)
 def test_fixed93_whitelist(self):
  before=self.bp.read_bytes()
  with self.assertRaises(B.BudgetIntegrityError):B.reserve(self.provider,'D-SIMPLE|outside','fresh',1000,6144,token_upper=1000)
  self.assertEqual(before,self.bp.read_bytes())
 def test_actual_safety_and_changed_historic_marker_stop(self):
  (self.run/'emergency_stop.json').write_text('{}');self.assertTrue(B.stopped());(self.run/'emergency_stop.json').unlink();(self.finance/'budget_stop.json').write_text('{}')
  with self.assertRaises(B.BudgetIntegrityError):B.stopped()
 def test_readonly_budget_context_does_not_rewrite(self):
  before=self.bp.stat();data=self.bp.read_bytes()
  with B.strict_shared_budget():pass
  self.assertEqual(data,self.bp.read_bytes());self.assertEqual(before.st_ino,self.bp.stat().st_ino)

class PreparationTests(unittest.TestCase):
 def make_tar(self,folder,entries):
  p=folder/'base.tar.gz'
  with tarfile.open(p,'w:gz') as t:
   for name,raw,link in entries:
    m=tarfile.TarInfo(name)
    if link:m.type=tarfile.SYMTYPE;m.linkname='/never/follow/this';t.addfile(m)
    else:m.size=len(raw);t.addfile(m,io.BytesIO(raw))
  return {'archive':str(p),'sha256':C.sha(p),'transport':'git_depth1_base_only'}
 def test_materializes_non_python_tests_and_docs_preserving_bytes(self):
  with tempfile.TemporaryDirectory() as s:
   root=Path(s);a=self.make_tar(root,[('src/a.py',b'# coding: latin-1\nx="\xe9"\n',False),('tests/a.ts',b'function f() {}\n',False),('README.md',b'hello',False),('blob.bin',b'\x00\xff',False),('vendor/x.py',b'pass',False),('link',b'',True)])
   paths,hashes,stats=P.materialize(a,root/'snapshot');self.assertIn('blob.bin',paths);self.assertIn('tests/a.ts',paths);self.assertNotIn('vendor/x.py',paths);self.assertEqual((root/'snapshot/src/a.py').read_bytes(),b'# coding: latin-1\nx="\xe9"\n');self.assertFalse((root/'snapshot/blob.bin').exists());self.assertFalse((root/'snapshot/link').exists());self.assertEqual(len(hashes),3)
 def test_archive_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as s:
   root=Path(s);a=self.make_tar(root,[('../escape',b'bad',False)])
   with self.assertRaises(ValueError):P.materialize(a,root/'snapshot')
   self.assertFalse((root.parent/'escape').exists())
 def test_same_content_duplicate_archive_member_rejected(self):
  with tempfile.TemporaryDirectory() as s:
   root=Path(s);a=self.make_tar(root,[('a.py',b'pass',False),('a.py',b'pass',False)])
   with self.assertRaises(RuntimeError):P.materialize(a,root/'snapshot')

class TransportTests(unittest.TestCase):
 def test_real_wire_omits_sampling_and_replay_is_exact_only(self):
  with tempfile.TemporaryDirectory() as s:
   root=Path(s);out=root/'case';out.mkdir()
   if str(C.FROZEN) not in sys.path:sys.path.insert(0,str(C.FROZEN))
   original=importlib.import_module('src.providers');fake=types.ModuleType('src.providers');fake.__dict__.update(original.__dict__);captured=[];reservations=[]
   usage={'prompt_tokens':4,'completion_tokens':3,'prompt_cache_hit_tokens':0}
   message=types.SimpleNamespace(content='{"ranked_files":[]}',reasoning_content=None);choice=types.SimpleNamespace(message=message,finish_reason='stop')
   raw={'model':'deepseek-flash','usage':usage,'choices':[{'message':{'content':message.content},'finish_reason':'stop'}]}
   response=types.SimpleNamespace(model='deepseek-flash',choices=[choice],usage=types.SimpleNamespace(model_dump=lambda **kw:usage),model_dump=lambda **kw:raw)
   client=types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kw:(captured.append(kw) or response))))
   def write(p,v,replace=False):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
   fake.__dict__.update(RUN=root,write=write,reserve=lambda *a,**kw:reservations.append((a,kw)),settle=lambda *a,**kw:None,_CLIENTS={})
   tc=types.ModuleType('src.token_counter');tc.prompt_upper=lambda messages:10000
   obj=types.SimpleNamespace(seq=0,out=out,deepseek=True,client=client,method='D-SIMPLE',iid='id')
   with patch.dict(sys.modules,{'src.providers':fake,'src.token_counter':tc}):
    result=T.ask(obj,[{'role':'user','content':'issue'}],'file_draw_0',max_tokens=6144,json_mode=True,temperature=None)
    self.assertEqual(len(captured),1);self.assertEqual(len(reservations),1);self.assertNotIn('temperature',captured[0]);self.assertNotIn('top_p',captured[0]);self.assertEqual(captured[0]['extra_body'],{'thinking':{'type':'disabled'}})
    saved=json.loads((out/'calls/0001_file_draw_0/request.json').read_text())['request'];self.assertNotIn('temperature',saved);self.assertNotIn('top_p',saved)
    obj.seq=0;self.assertEqual(T.ask(obj,[{'role':'user','content':'issue'}],'file_draw_0',max_tokens=6144,json_mode=True,temperature=None),result);self.assertEqual(len(reservations),1)
    obj.seq=0
    with self.assertRaises(original.AmbiguousPriorRequest):T.ask(obj,[{'role':'user','content':'changed'}],'file_draw_0',max_tokens=6144,json_mode=True,temperature=None)

class ControllerTests(unittest.TestCase):
 def test_full_never_repeats_smoke_or_failed_saved_results(self):
  with tempfile.TemporaryDirectory() as s:
   root=Path(s);rows=[]
   for i,status in enumerate(['complete','failed',None]):
    d=root/str(i);d.mkdir();rows.append({'instance_id':str(i),'result_dir':str(d)})
    if status:(d/'result.json').write_text(json.dumps({'status':status}))
   f={'records':rows,'smoke_ids':['0','1']};self.assertEqual([r['instance_id'] for r in R.pending(f,'full')],['2']);self.assertEqual(R.pending(f,'smoke'),[])
 def test_common_refuses_old_result_writes(self):
  with self.assertRaises(PermissionError):C.permitted(C.OLD_RUN/'result.json')

if __name__=='__main__':unittest.main()
