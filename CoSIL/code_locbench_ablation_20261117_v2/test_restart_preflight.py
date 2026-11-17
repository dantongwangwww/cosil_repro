"""Hermetic metadata bridge tests; no model, Gold, GPU, or signal operations."""
from pathlib import Path
import copy,json,os,tempfile,unittest
from unittest import mock
from . import restart_preflight as b


def put(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


class Bridge(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.old=self.base/'v1';self.old.mkdir();self.new=self.base/'v2'
  proto={'root':str(self.old),'n':560,'allocated':560,'arms':list(b.c.ARMS),'Gold_or_reference_patch_sent_to_model':False,'sealed_project_test_opened':False,'deployment':{'temperature':2.9846201034621833,'low':.12947567721292427,'high':.9},'algorithm':'unchanged'}
  put(self.old/'protocol.json',proto);rows=[];files={str(self.old/'protocol.json'):b.c.sha(self.old/'protocol.json')}
  for k in range(560):
   iid='synthetic-'+str(k);status='ready' if k<557 else 'source_preparation_blocked' if k<559 else 'upstream_file_stage_unavailable'
   row={'instance_id':iid,'repo':'org/pkg','base_commit':'a'*40,'rank':k+1,'upstream_status':status,'no_model_dispatch':status!='ready','public_input_path':str(self.old/'inputs'/iid),'public_files_sha256':{}}
   if status=='ready':
    p=Path(row['public_input_path']);job={**{x:row[x] for x in ('instance_id','repo','base_commit')},'problem_statement':'public issue','cohort':'fixture','snapshot':'/snapshot','paths':['pkg.py'],'code_index':'/input/index.json','structure':'/input/structure.json'}
    shared={'instance_id':iid,'base_commit':row['base_commit'],'files':['pkg.py'],'raw_file_responses':['pkg.py']}
    for name,value in [('job.json',job),('shared.json',shared)]:
     put(p/name,value);row['public_files_sha256'][name]=b.c.sha(p/name);files[str(p/name)]=b.c.sha(p/name)
   rows.append(row)
  put(self.old/'manifest.json',{'schema':1,'n':560,'allocated':560,'arms':list(b.c.ARMS),'records':rows})
  files[str(self.old/'manifest.json')]=b.c.sha(self.old/'manifest.json')
  authority={'manifest_sha256':b.c.sha(self.old/'manifest.json'),'protocol_sha256':b.c.sha(self.old/'protocol.json'),'Gold_parsed':False,'models_called':False,'availability':{'ready':557,'source_preparation_blocked':2,'upstream_file_stage_unavailable':1},'files_sha256':files}
  put(self.old/'authority.json',authority)
  put(self.old/'controller/execution_freeze.json',{'status':'EXECUTION_FROZEN_READY','commit':'synthetic-commit','manifest_sha256':b.c.sha(self.old/'manifest.json'),'protocol_sha256':b.c.sha(self.old/'protocol.json'),'authority_sha256':b.c.sha(self.old/'authority.json'),'Gold_scored':False,'files_sha256':{}})
  put(self.old/b.PRECHANGE,{'status':'REMOTE_PASS','commit':'synthetic-commit','current_source_changes':[],'remote_all_109_blobs_match_current_bytes':True})
  put(self.old/b.STOP,{'status':'ENGINEERING_PREFLIGHT_HEARTBEAT_FAILURE_PRESERVED','observed_failure':b.FAILURE,'benchmark_started_arms':0,'benchmark_model_calls':0,'condition_parameters_changed':False,'historical_controls_changed':False,'stop_receipt':{'leader_exited':True}})
  self.identities=[{'pid':9900000+k,'uid':os.getuid(),'start_ticks':123,'pgid':9900000+k,'sid':9900000+k} for k in range(6)]
  exits={'all_recorded_service_leaders_exited':True,'all_recorded_positive_CUDA_processes_exited':True,
    'leaders':[{'role':role,'leader_exited':True,'saved_identity':self.identities[k]} for k,role in enumerate(('controller','main','judge'))],
    'positive_cuda_processes':[{'leader_exited':True,'saved_identity':x} for x in self.identities[3:]]}
  put(self.old/b.REVIEW,{'status':'RUNTIME_ENGINEERING_FAIL_BEFORE_BENCHMARK_CANARY','failure':{'message':b.FAILURE},'observed_benchmark_started_arms':0,'observed_benchmark_main_request_files':0,'observed_benchmark_judge_start_receipts':0,'benchmark_Gold_parsed':False,'owned_process_exit':exits})
  self.session=self.old/'controller/service_queue/sessions/one'
  put(self.session/'lifetime_admission.json',{'session_ordinal':1,'previous_session_count':0,'maximum_cumulative_infrastructure_launches':3,'root':str(self.old),'semantic_retry':False})
  put(self.session/'failure.json',{'error':b.FAILURE})
  for role in ('controller','main','judge'):put(self.session/role/'actual_exit_verification.json',{'exited':True})
  self.patch=mock.patch.object(b,'OLD_PROTOCOL_SHA',b.c.sha(self.old/'protocol.json'));self.patch.start()
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def execute(self):return b.bridge(self.old,self.new,observe=lambda pid:None)
 def test_metadata_bridge_exact_manifest_and_parameters_budget(self):
  before={str(p):b.c.sha(p) for p in self.old.rglob('*') if p.is_file()};value=self.execute()
  self.assertEqual(value['remaining_infrastructure_launches'],2)
  self.assertEqual((self.new/'manifest.json').read_bytes(),(self.old/'manifest.json').read_bytes())
  p=b.c.read(self.new/'protocol.json');original=b.c.read(self.old/'protocol.json')
  self.assertEqual({k:v for k,v in p.items() if k not in ('root','engineering_amendment')},{k:v for k,v in original.items() if k!='root'})
  self.assertEqual(len(p['engineering_amendment']['prior_service_sessions']),1)
  self.assertFalse((self.new/'inputs').exists());self.assertFalse((self.new/'run').exists())
  self.assertEqual(before,{str(p):b.c.sha(p) for p in self.old.rglob('*') if p.is_file()})
 def test_refuses_existing_or_same_root(self):
  with self.assertRaises(ValueError):b.bridge(self.old,self.old)
  self.new.mkdir()
  with self.assertRaises(FileExistsError):self.execute()
 def test_started_or_http_cannot_be_reset_by_new_root(self):
  for rel in ['run/pairs/x/a/started.json','run/pairs/x/a/calls/1/attempt_0_start.json','run/pairs/x/a/judge_rpc/id_start.json']:
   p=self.old/rel;put(p,{})
   with self.assertRaisesRegex(ValueError,'benchmark'):self.execute()
   p.unlink()
  self.assertFalse(self.new.exists())
 def test_gold_exposure_rejected(self):
  p=self.old/'inputs/synthetic-0/job.json';v=b.c.read(p);v['gold']='poison';put(p,v)
  with self.assertRaisesRegex(ValueError,'Gold/private'):self.execute()
 def test_wrong_failure_or_nonzero_calls_rejected(self):
  p=self.old/b.STOP;original=b.c.read(p)
  for key,value in [('observed_failure','different'),('benchmark_model_calls',1)]:
   v=copy.deepcopy(original);v[key]=value;put(p,v)
   with self.assertRaisesRegex(ValueError,'heartbeat failure'):self.execute()
  self.assertFalse(self.new.exists())
 def test_live_old_owned_process_rejected(self):
  saved=self.identities[0]
  with self.assertRaisesRegex(ValueError,'remains live'):
   b.bridge(self.old,self.new,observe=lambda pid:dict(saved,state='S') if pid==saved['pid'] else None)
 def test_missing_verified_exit_rejected(self):
  p=self.old/b.REVIEW;v=b.c.read(p);v['owned_process_exit']['all_recorded_positive_CUDA_processes_exited']=False;put(p,v)
  with self.assertRaisesRegex(ValueError,'exit evidence'):self.execute()
 def test_prior_lifetime_records_cannot_be_missing_or_duplicated(self):
  records=b.validate_prior_sessions(self.old)
  for bad in [[],records+records,[dict(records[0],lifetime_admission_sha256='0'*64)]]:
   with self.assertRaisesRegex(ValueError,'prior service'):b.validate_prior_sessions(self.old,bad)
 def test_infrastructure_cap_not_reset(self):
  p=self.session/'lifetime_admission.json';v=b.c.read(p);v['maximum_cumulative_infrastructure_launches']=99;put(p,v)
  with self.assertRaisesRegex(ValueError,'lifetime admission'):self.execute()
 def test_two_actual_admissions_leave_one_not_two(self):
  session=self.old/'controller/service_queue/sessions/two'
  put(session/'lifetime_admission.json',{'session_ordinal':2,'previous_session_count':1,'maximum_cumulative_infrastructure_launches':3,'root':str(self.old),'semantic_retry':False})
  put(session/'failure.json',{'error_type':'SystemExit','error':'143','controller_launched':False,'semantic_retry':False})
  identity=self.identities[0];put(session/'main/ownership.json',{'identity':identity});put(session/'main/actual_exit_verification.json',{'exited':True})
  put(self.old/'audits/post_stop_actual_session_inventory.json',{'status':'POST_STOP_ACTUAL_SESSION_INVENTORY_PASS','actual_prior_session_count':2,'remaining_session_allowance':1,'benchmark_started_arms':0,'benchmark_HTTP_requests':0,'benchmark_judge_attempts':0,'all_prior_CPU_launchers_stopped':True,'sessions':[{'session':'one'},{'session':'two'}],'service_release':{'all_owned_services_and_CUDA_children_exited':True,'missing_evidence':[]}})
  value=self.execute();self.assertEqual(value['prior_used_service_sessions'],2);self.assertEqual(value['remaining_infrastructure_launches'],1)
  protocol=b.c.read(self.new/'protocol.json');self.assertEqual(len(protocol['engineering_amendment']['prior_service_sessions']),2)
 def test_three_admissions_are_exhausted(self):
  for ordinal,name in [(2,'two'),(3,'three')]:
   put(self.old/'controller/service_queue/sessions'/name/'lifetime_admission.json',{'session_ordinal':ordinal})
  with self.assertRaisesRegex(ValueError,'exhausted'):self.execute()
 def test_wrong560_or_changed_frozen_authority_rejected(self):
  p=self.old/'manifest.json';v=b.c.read(p);v['n']=559;put(p,v)
  with self.assertRaisesRegex(ValueError,'560'):self.execute()

if __name__=='__main__':unittest.main()
