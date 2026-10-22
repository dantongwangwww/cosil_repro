"""Synthetic CPU tests: no real API transport, GPU, historical runs or labels."""
import concurrent.futures
import contextlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from supplement_v1 import common as C
from supplement_v1 import bootstrap as B
from supplement_v1 import runtime as R


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='supp-runtime-test-')
        self.root=Path(self.tmp.name);self.run=self.root/'runs/synthetic'
        self.run.mkdir(parents=True)
        self.patches=[patch.object(C,'ROOT',self.root),patch.object(C,'RUN',self.run)]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in self.patches[::-1]:p.stop()
        self.tmp.cleanup()

    def ledger(self,cap=None):
        if cap is None:cap=C.BUDGET_USD
        C.write(self.run/'budget.json',{'stage_cap_usd':cap,'cases':{},'attempts':{}})

    def provider(self):
        # Load the actual frozen transport under a fixture-only module name.
        if str(C.FROZEN) not in sys.path:sys.path.insert(0,str(C.FROZEN))
        spec=importlib.util.spec_from_file_location('src.supplement_cpu_provider_fixture',C.FROZEN/'src/providers.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.RUN=self.run
        B.install_provider_guard(module)
        return module

    def test_missing_or_wrong_ledger_is_refused_without_creation(self):
        with self.assertRaises(B.BudgetIntegrityError):
            with B.strict_budget():pass
        self.assertFalse((self.run/'budget.json').exists())
        for obsolete_cap in [3,10,30]:
            self.ledger(obsolete_cap)
            with self.assertRaises(B.BudgetIntegrityError):
                with B.strict_budget():pass
            self.assertEqual(C.load(self.run/'budget.json')['stage_cap_usd'],obsolete_cap)

    def test_real_frozen_reservations_are_atomic_and_stop_at_new_cap(self):
        self.ledger();p=self.provider()
        def reserve(i):
            try:p.reserve('case'+str(i),'rid'+str(i),300000,1024);return True
            except p.BudgetExceeded:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:accepted=list(pool.map(reserve,range(80)))
        value=C.load(self.run/'budget.json');amount=sum(a['charged_upper_usd'] for a in value['attempts'].values())
        expected=int(C.BUDGET_USD/((300000*.3+1024*1.2)/1e6))
        self.assertEqual(sum(accepted),expected)
        self.assertLessEqual(amount,C.BUDGET_USD)
        self.assertEqual(len(value['attempts']),expected)
        self.assertTrue((self.run/'budget_stop.json').exists())
        p.settle('rid0',status='billing_unknown')
        self.assertEqual(sum(a['charged_upper_usd'] for a in C.load(self.run/'budget.json')['attempts'].values()),amount)

    def test_original_per_case_limits_and_tokens_remain(self):
        self.ledger();p=self.provider()
        p.reserve('case','first',300000,1000)
        with self.assertRaisesRegex(p.BudgetExceeded,'400000'):p.reserve('case','second',110000,1000)
        self.assertFalse((self.run/'budget_stop.json').exists())
        with self.assertRaisesRegex(p.BudgetExceeded,'CNY1.50'):p.reserve('expensive','third',800000,4096,token_upper=10)
        self.assertFalse((self.run/'budget_stop.json').exists())

    def test_only_original_dsimple_request_settings_are_permitted(self):
        self.ledger();p=self.provider()
        with self.assertRaises(PermissionError):p.Provider('Q-COSIL','iid',self.run/'issue')
        p._CLIENTS[True]=types.SimpleNamespace()
        provider=p.Provider('D-SIMPLE','iid',self.run/'issue')
        with self.assertRaisesRegex(RuntimeError,'settings changed'):
            provider.ask([{'role':'user','content':'x'}],'file_draw_0',max_tokens=2048,json_mode=True,temperature=0.)
        self.assertEqual(C.load(self.run/'emergency_stop.json')['reason'],'provider_or_model_contract_failure')
        self.assertEqual(len(C.load(self.run/'budget.json')['attempts']),0)

    def test_actual_frozen_transport_cached_request_and_unknown_transmission(self):
        self.ledger();p=self.provider();calls=[]
        usage={'prompt_tokens':8,'completion_tokens':2,'prompt_cache_hit_tokens':0}
        def fake_create(**wire):
            calls.append(wire)
            self.assertEqual(wire['extra_body'],{'thinking':{'type':'disabled'}})
            return types.SimpleNamespace(model='deepseek-flash',usage=types.SimpleNamespace(model_dump=lambda **kw:usage),
                choices=[types.SimpleNamespace(finish_reason='stop',message=types.SimpleNamespace(content='{"ranked_files":[]}',reasoning_content=None))],
                model_dump=lambda **kw:{'usage':usage,'model':'deepseek-flash'})
        p._CLIENTS[True]=types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=fake_create)))
        import src.token_counter
        out=self.run/'issue';messages=[{'role':'user','content':'Synthetic request'}]
        with patch.object(src.token_counter,'prompt_upper',return_value=1024):
            response=p.Provider('D-SIMPLE','iid',out).ask(messages,'file_draw_0',max_tokens=2048,json_mode=True,temperature=1.)
            cached=p.Provider('D-SIMPLE','iid',out).ask(messages,'file_draw_0',max_tokens=2048,json_mode=True,temperature=1.)
            self.assertEqual(response,cached);self.assertEqual(len(calls),1)
            (out/'calls/0001_file_draw_0/result.json').unlink()
            with self.assertRaises(p.AmbiguousPriorRequest):
                p.Provider('D-SIMPLE','iid',out).ask(messages,'file_draw_0',max_tokens=2048,json_mode=True,temperature=1.)
        self.assertEqual(len(calls),1)
        self.assertTrue((self.run/'emergency_stop.json').exists())

    def test_config_rejects_wrong_method_budget_retry_or_thinking(self):
        config={'methods':['D-SIMPLE'],'run_id':C.RUN_ID,'cohort':C.COHORT,'budget_usd':C.BUDGET_USD,'api_concurrency':4,
                'transport_retries':3,'semantic_retries':0,'deepseek':{'thinking':'disabled','reasoning_effort':None,'model':'deepseek-flash'},
                'budget':{'per_case_soft_cny':.5,'per_case_hard_cny':1.5,'cumulative_tokens_per_case':400000},'gpu_used':False}
        R.config_guard(config)
        for key,value in [('budget_usd',10),('api_concurrency',8),('semantic_retries',1),('gpu_used',True),('methods',['Q-COSIL'])]:
            with self.subTest(key=key),self.assertRaises(PermissionError):R.config_guard(dict(config,**{key:value}))

    def test_full_reuses_fixed_smoke_and_never_reselects_failed_result(self):
        records=[{'instance_id':str(i),'job':'unused'} for i in range(200)]
        frozen={'records':records,'smoke_ids':[str(i) for i in range(5)]}
        for i in range(5):C.write(self.run/C.COHORT/'D-SIMPLE'/str(i)/'result.json',{'status':'parse_error' if i==0 else 'complete'})
        self.assertEqual(R.tasks_for_scope(frozen,'smoke'),[])
        self.assertEqual(len(R.tasks_for_scope(frozen,'full')),195)
        self.assertEqual([r['instance_id'] for r in R.tasks_for_scope(frozen,'full')][:2],['5','6'])

    def test_sandbox_binds_only_selected_clean_snapshot_and_no_weights(self):
        jobdir=self.root/'jobs/iid';jobdir.mkdir(parents=True)
        actual=self.root/'clean_snapshot/iid';actual.mkdir(parents=True)
        job={'instance_id':'iid','snapshot':str(actual)};C.write(jobdir/'job.json',job)
        batch={'tasks':[{'job':str(jobdir/'job.json')}]}
        argv=R.sandbox_argv(self.run/'batch.json',batch,probe=True)
        joined='\n'.join(argv)
        self.assertIn('--probe',argv)
        self.assertIn(str(actual),argv)
        self.assertIn(str(self.root/'snapshots/iid'),argv)
        self.assertNotIn('start_qwen',joined)
        self.assertNotIn('Qwen2.5',joined)
        self.assertNotIn(str(C.PREVIOUS),argv)
        mounts=[argv[i+1] for i,x in enumerate(argv) if x=='--ro-bind']
        self.assertNotIn(str(self.root),mounts)
        self.assertNotIn(str(self.root/'configs'),mounts)
        self.assertNotIn(str(self.root/'evaluator_private'),mounts)
        self.assertNotIn(str(actual.parent),mounts)
        self.assertEqual(R.worker_env()['CUDA_VISIBLE_DEVICES'],'')
        self.assertEqual(R.worker_env()['OMP_NUM_THREADS'],'2')

    def test_launcher_detaches_without_gpu_or_inherited_stdin(self):
        frozen={'records':[],'smoke_ids':[]}
        with patch.object(R,'verify',return_value=frozen),patch.object(R.subprocess,'Popen',return_value=types.SimpleNamespace(pid=123)) as start:
            result=R.launch('smoke',execute=True)
        self.assertTrue(result['new_session']);self.assertEqual(result['pid'],123)
        self.assertTrue(start.call_args.kwargs['start_new_session'])
        self.assertEqual(start.call_args.kwargs['stdin'],R.subprocess.DEVNULL)
        self.assertIn('--execute',start.call_args.args[0])

    def test_dry_run_never_starts_worker(self):
        with patch.object(R,'verify',return_value={'records':[],'smoke_ids':[]}),patch.object(R.subprocess,'Popen') as process:
            plan=R.launch('smoke',execute=False)
        self.assertTrue(plan['dry_run']);process.assert_not_called()


    def test_ordinary_case_failure_is_saved_and_next_case_runs(self):
        from supplement_v1 import worker as W
        tasks=[{'job':'unused/'+iid,'instance_id':iid,'data_sha256':{},'snapshot_sha256':{}} for iid in ['first','second']]
        batch=self.run/'batch.json';C.write(batch,{'tasks':tasks,'config':{}})
        calls=[]
        def run_one(item):
            iid=Path(item[0]).name;calls.append(iid)
            result={'instance_id':iid,'method':'D-SIMPLE','status':'failed' if iid=='first' else 'complete'}
            C.write(self.run/C.COHORT/'D-SIMPLE'/iid/'result.json',result)
            return result
        fake=types.SimpleNamespace(run_one=run_one)
        with patch.object(W,'probe',return_value={'passed':True}),patch.object(W,'verify_batch',return_value=True),patch.object(B,'install',return_value=(fake,None)),patch.object(W.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10*1024**3)):
            W.work(batch,execute=True)
        self.assertEqual(calls,['first','second'])
        self.assertEqual(C.load(self.run/C.COHORT/'D-SIMPLE/first/result.json')['status'],'failed')
        self.assertFalse((self.run/'emergency_stop.json').exists())
        self.assertIn('process_cpu_seconds',C.load(self.run/C.COHORT/'D-SIMPLE/second/result.json'))

    def test_disk_guard_checks_actual_output_volume_and_keeps_two_gib(self):
        from supplement_v1 import worker as W
        batch=self.run/'batch.json';C.write(batch,{'tasks':[{'job':'unused','instance_id':'first','data_sha256':{},'snapshot_sha256':{}}],'config':{}})
        execution=types.SimpleNamespace(run_one=unittest.mock.Mock())
        with patch.object(W,'probe',return_value={'passed':True}),patch.object(W,'verify_batch',return_value=True),patch.object(B,'install',return_value=(execution,None)),patch.object(W.shutil,'disk_usage',return_value=types.SimpleNamespace(free=1024**3)) as disk:
            W.work(batch,execute=True)
        self.assertEqual(disk.call_args.args[0],self.run.resolve())
        execution.run_one.assert_not_called()
        self.assertEqual(C.load(self.run/'resource_pause.json')['free_bytes'],1024**3)

    def test_paid_worker_probe_failure_stops_before_provider_import(self):
        from supplement_v1 import worker as W
        batch=self.run/'batch.json';C.write(batch,{'tasks':[]})
        with patch.object(W,'probe',side_effect=RuntimeError('visibility failed')),patch.object(B,'install') as install:
            with self.assertRaisesRegex(RuntimeError,'visibility failed'):W.work(batch,execute=True)
        install.assert_not_called()
        self.assertEqual(C.load(self.run/'emergency_stop.json')['reason'],'worker_isolation_failure')

    def test_finish_length_is_per_case_but_usage_violation_is_global(self):
        self.ledger();p=self.provider()
        self.assertFalse(B.fatal_provider_error(p,RuntimeError('Truncated or rejected model response')))
        self.assertFalse(B.fatal_provider_error(p,RuntimeError('API request failed: APITimeoutError; HTTP None')))
        self.assertTrue(B.fatal_provider_error(p,RuntimeError('Missing API usage')))
        self.assertTrue(B.fatal_provider_error(p,RuntimeError('API request failed: BadRequestError; HTTP 402')))
        self.assertTrue(B.fatal_provider_error(p,p.UnexpectedThinking('unexpected reasoning')))
        self.assertTrue(B.fatal_provider_error(p,p.ModelMismatch('wrong model')))

    def test_freeze_accepts_readme_in_inventory_with_python_only_source_receipt(self):
        iid='synthetic';snapshot=self.root/'snapshots'/iid;snapshot.mkdir(parents=True)
        (snapshot/'a.py').write_text('def f(): return 1\n')
        jobdir=self.root/'jobs'/iid;jobdir.mkdir(parents=True)
        index=jobdir/'index.json';structure=jobdir/'structure.json';C.write(index,{});C.write(structure,{})
        job={'instance_id':iid,'repo':'example/example','base_commit':'base','cohort':C.COHORT,'paths':['README.md','pyproject.toml','a.py'],
             'snapshot':str(snapshot),'code_index':str(index),'structure':str(structure)}
        jobpath=jobdir/'job.json';C.write(jobpath,job)
        row={k:job[k] for k in ['instance_id','repo','base_commit']};row['job']=str(jobpath)
        receipt=self.root/'evaluator_private/preparation/qualification'/str(iid+'.json')
        C.write(receipt,{'qualified':True,'snapshot_python_sha256':{'a.py':C.sha(snapshot/'a.py')}})
        for name in R.CONTROLLER_NAMES:
            path=self.root/'supplement_v1'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('# fixture\n')
        config=self.root/'configs/resolved_config.json';C.write(config,{})
        for name in ['additional200.json','combined300.json']:C.write(self.root/'manifests'/name,{})
        frozen=self.run/'online_freeze.json'
        with patch.object(R,'CONFIG',config),patch.object(R,'FREEZE',frozen),patch.object(R,'install_assets',return_value=({},{})),patch.object(R,'manifests',return_value=([row],[])),patch.object(R,'history_inventory',return_value={}),patch.object(R,'verify',side_effect=lambda:C.load(frozen)):
            result=R.freeze()
        self.assertEqual(result['snapshot_sha256'],{str(snapshot/'a.py'):C.sha(snapshot/'a.py')})
        self.assertIn(str(jobpath),result['data_sha256'])
        self.assertEqual(C.load(self.run/'budget.json')['stage_cap_usd'],C.BUDGET_USD)

if __name__=='__main__':unittest.main()
