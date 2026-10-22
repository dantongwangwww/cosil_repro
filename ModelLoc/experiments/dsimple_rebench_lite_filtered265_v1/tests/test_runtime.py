"""Synthetic shared-ledger/queue/sandbox tests; never uses a live API client."""
import concurrent.futures
import importlib.util
import json
import sys
import tempfile
import threading
import time
import types
from pathlib import Path
import unittest
from unittest.mock import patch
from filtered265 import common as C,bootstrap as B,runtime as R,worker as W


class FilteredRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='filtered265-runtime-test-');self.base=Path(self.tmp.name)
        self.root=self.base/'new_project';self.root.mkdir();self.run=self.root/'runs/new';self.run.mkdir(parents=True)
        self.finance=self.base/'original_finance';self.finance.mkdir();self.shared=self.finance/'budget.json'
        self.patches=[patch.object(C,'ROOT',self.root),patch.object(C,'RUN',self.run),patch.object(C,'SHARED_BUDGET',self.shared),patch.object(B,'_CONTRACT',None),patch.object(R,'FREEZE',self.run/'online_freeze.json'),patch.object(R,'BASELINE',self.run/'financial_baseline.json')]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in self.patches[::-1]:p.stop()
        self.tmp.cleanup()
    def ledger(self,cap=5):self.shared.write_text(json.dumps({'stage_cap_usd':cap,'cases':{},'attempts':{}}))
    def provider(self):
        if str(C.FROZEN) not in sys.path:sys.path.insert(0,str(C.FROZEN))
        spec=importlib.util.spec_from_file_location('src.filtered265_cpu_provider_fixture',C.FROZEN/'src/providers.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.RUN=self.run
        B.install_provider_guard(module);return module

    def test_no_new_ledger_and_old_caps_rejected(self):
        with self.assertRaises(B.BudgetIntegrityError):
            with B.strict_shared_budget():pass
        self.assertFalse(self.shared.exists());self.assertFalse((self.run/'budget.json').exists())
        for cap in [3,10,30]:
            self.ledger(cap)
            with self.assertRaises(B.BudgetIntegrityError):
                with B.strict_shared_budget():pass
            self.assertEqual(json.loads(self.shared.read_text())['stage_cap_usd'],cap)

    def test_shared_directory_identity_is_pinned(self):
        self.ledger();contract=B.financial_contract();B.set_contract(contract)
        wrong=dict(contract,parent_inode=contract['parent_inode']+1)
        with self.assertRaises(B.BudgetIntegrityError):B.set_contract(wrong)

    def test_two_queue_reservations_share_one_five_dollar_cap(self):
        self.ledger();provider=self.provider()
        def reserve(i):
            try:provider.reserve('D-SIMPLE|iid-'+str(i),'rid-'+str(i),300000,1024);return True
            except provider.BudgetExceeded:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:accepted=list(pool.map(reserve,range(80)))
        ledger=json.loads(self.shared.read_text());self.assertEqual(sum(accepted),54)
        self.assertLessEqual(sum(a['charged_upper_usd'] for a in ledger['attempts'].values()),5)
        self.assertEqual(len(ledger['attempts']),54);self.assertTrue((self.finance/'budget_stop.json').exists())
        before=sum(a['charged_upper_usd'] for a in ledger['attempts'].values());provider.settle('rid-0',status='billing_unknown')
        self.assertEqual(sum(a['charged_upper_usd'] for a in json.loads(self.shared.read_text())['attempts'].values()),before)
        self.assertFalse((self.run/'budget.json').exists())

    def test_same_id_keeps_original_case_key_across_output_queues(self):
        self.ledger();provider=self.provider();provider.reserve('D-SIMPLE|same','queue-a',200000,1024)
        with self.assertRaisesRegex(provider.BudgetExceeded,'400000'):provider.reserve('D-SIMPLE|same','queue-b',210000,1024)
        self.assertEqual(set(json.loads(self.shared.read_text())['cases']),{'D-SIMPLE|same'})
        self.assertFalse((self.finance/'budget_stop.json').exists())

    def test_four_global_slots_across_threads(self):
        self.ledger();counts={'active':0,'max':0};lock=threading.Lock()
        def action(_):
            with B.shared_request_slot():
                with lock:counts['active']+=1;counts['max']=max(counts['max'],counts['active'])
                time.sleep(.025)
                with lock:counts['active']-=1
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:list(pool.map(action,range(16)))
        self.assertLessEqual(counts['max'],4);self.assertGreater(counts['max'],1)

    def test_exact_cached_transport_is_not_billed_again(self):
        self.ledger();provider=self.provider();calls=[];usage={'prompt_tokens':8,'completion_tokens':2,'prompt_cache_hit_tokens':0}
        def create(**wire):
            calls.append(wire);self.assertEqual(wire['extra_body'],{'thinking':{'type':'disabled'}})
            return types.SimpleNamespace(model='deepseek-flash',usage=types.SimpleNamespace(model_dump=lambda **kw:usage),
                choices=[types.SimpleNamespace(finish_reason='stop',message=types.SimpleNamespace(content='{"ranked_files":[]}',reasoning_content=None))],
                model_dump=lambda **kw:{'usage':usage,'model':'deepseek-flash'})
        provider._CLIENTS[True]=types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
        import src.token_counter
        messages=[{'role':'user','content':'synthetic'}];out=self.run/'case'
        with patch.object(src.token_counter,'prompt_upper',return_value=1024):
            one=provider.Provider('D-SIMPLE','id',out).ask(messages,'file_draw_0',max_tokens=2048,json_mode=True,temperature=1.)
            two=provider.Provider('D-SIMPLE','id',out).ask(messages,'file_draw_0',max_tokens=2048,json_mode=True,temperature=1.)
        self.assertEqual(one,two);self.assertEqual(len(calls),1);self.assertEqual(len(json.loads(self.shared.read_text())['attempts']),1)

    def test_ordinary_model_length_failure_is_not_global(self):
        self.ledger();provider=self.provider()
        self.assertFalse(B.fatal_error(provider,RuntimeError('Truncated or rejected model response')))
        self.assertFalse(B.fatal_error(provider,RuntimeError('API request failed: APITimeoutError; HTTP None')))
        self.assertTrue(B.fatal_error(provider,RuntimeError('Missing API usage')))
        self.assertTrue(B.fatal_error(provider,provider.ModelMismatch('wrong')))

    def test_pending_keeps_fixed_smoke_and_never_retries_prior_failure(self):
        records=[{'instance_id':str(i),'result_dir':str(self.run/'cases'/str(i))} for i in range(221)]
        frozen={'records':records,'smoke_ids':[str(i) for i in range(5)]}
        for record in records[:5]:C.write(Path(record['result_dir'])/'result.json',{'status':'failed'})
        self.assertEqual(R.pending(frozen,'smoke'),[]);self.assertEqual(len(R.pending(frozen,'full')),216)

    def test_sandbox_uses_only_online_code_and_masks_financial_metadata(self):
        self.ledger();(self.finance/'online_freeze.json').write_text('{"secret":"metadata"}')
        (self.finance/'audit').mkdir();(self.finance/'audit/private.json').write_text('{"gold":1}')
        jobs=self.root/'jobs/iid';jobs.mkdir(parents=True);source=self.root/'snapshots/iid';source.mkdir(parents=True)
        job={'instance_id':'iid','snapshot':str(source)};C.write(jobs/'job.json',job)
        out=self.run/'cases/iid';out.mkdir(parents=True);receipt=self.run/'receipts/worker';receipt.mkdir(parents=True)
        batch={'tasks':[{'job':str(jobs/'job.json'),'result_dir':str(out)}],'worker_receipt_dir':str(receipt)}
        argv=R.sandbox_argv(self.run/'batch.json',batch,True)
        self.assertNotIn(str(self.run),[argv[i+1] for i,v in enumerate(argv) if v=='--bind'])
        self.assertIn('/dev/null',argv);self.assertIn(str(self.finance/'online_freeze.json'),argv)
        mounts=[argv[i+1] for i,v in enumerate(argv) if v=='--ro-bind']
        self.assertNotIn(str(self.root/'filtered265'),mounts)
        self.assertNotIn(str(self.root/'filtered265/screen.py'),mounts)
        self.assertNotIn(str(C.FROZEN/'src/dataset_adapter.py'),mounts)
        self.assertEqual(R.worker_env()['CUDA_VISIBLE_DEVICES'],'')
        temporary_mounts=[argv[i+1] for i,v in enumerate(argv) if v=='--tmpfs']
        self.assertIn(str((Path.home()/'.cache').resolve()),temporary_mounts)

    def test_dry_run_does_not_start_process(self):
        with patch.object(R,'verify',return_value={'records':[],'smoke_ids':[]}),patch.object(R.subprocess,'Popen') as process:
            result=R.launch('smoke',False)
        self.assertTrue(result['dry_run']);self.assertFalse(result['new_budget_created']);process.assert_not_called()

    def roster_fixture(self):
        source=[];records=[]
        for i in range(265):
            group='old100_observed' if i<44 else 'old200_prepared_not_run' if i<102 else 'unseen'
            entry={'instance_id':'iid'+str(i),'repo':'repo'+str(i%173),'base_commit':'abc','sampling_hash':str(i).zfill(4),'observation_group':group,
                'qualified':True,'four_filter_pass':True,'history_pass':True,'four_filter_reasons':[],'history_reasons':[],
                'all_reasons':['one_issue_per_repository_after_four_and_history'] if i>=173 else [],'problem_words':40,
                'business_patch':{'files':1,'hunks':3,'added_files':0,'removed_files':0}}
            source.append(entry);records.append({k:entry[k] for k in R.IDENTITY}|{'origin':'old100_reuse44' if i<44 else 'new221'})
        roster={'n':265,'allow_repeated_repository':True,'rules_relaxed':False,'records':records}
        manifest={'n':265,'complete':True,'records':records};new={'n':221,'records':records[44:]}
        return roster,{'records':source},manifest,new

    def test_all265_including_repeated_repository_are_retained(self):
        fixture=self.roster_fixture();fresh,reused=R.validate_roster(*fixture)
        self.assertEqual((len(fresh),len(reused)),(221,44));self.assertEqual(len({x['repo'] for x in fixture[2]['records']}),173)

    def test_roster_rejects_gold_based_omission_or_reordering(self):
        for change in ['omit','reorder']:
            roster,source,manifest,new=self.roster_fixture()
            manifest=dict(manifest,records=list(manifest['records']))
            if change=='omit':manifest['records'].pop()
            else:manifest['records'][0],manifest['records'][1]=manifest['records'][1],manifest['records'][0]
            with self.assertRaises(RuntimeError):R.validate_roster(roster,source,manifest,new)

    def test_roster_rejects_relaxed_four_rules_or_history(self):
        for change in ['words','hunks','new_file','history']:
            roster,source,manifest,new=self.roster_fixture();row=source['records'][0]
            if change=='words':row['problem_words']=39
            elif change=='hunks':row['business_patch']['hunks']=4
            elif change=='new_file':row['business_patch']['added_files']=1
            else:row['history_reasons']=['protected_split_id']
            with self.assertRaises(RuntimeError):R.validate_roster(roster,source,manifest,new)

    def test_nonfinite_or_negative_accounting_rejected(self):
        for value in [float('nan'),float('inf'),-.01]:
            with self.assertRaises(RuntimeError):R.validate_ledger({'stage_cap_usd':5.,'cases':{},'attempts':{'x':{'charged_upper_usd':value}}})

    def test_ordinary_case_failure_preserved_and_next_case_runs(self):
        self.ledger();tasks=[];calls=[]
        for iid in ['first','second']:
            folder=self.run/C.COHORT/'D-SIMPLE'/iid;folder.mkdir(parents=True)
            tasks.append({'instance_id':iid,'job':iid,'result_dir':str(folder),'data_sha256':{},'snapshot_sha256':{}})
        batch={'tasks':tasks,'config':{},'shared_budget_contract':{},'worker_receipt_dir':str(self.run/'receipts')};path=self.run/'batch.json';C.write(path,batch)
        def run_one(task):
            iid=task[0];calls.append(iid);result={'status':'failed' if iid=='first' else 'complete','instance_id':iid}
            C.write(self.run/C.COHORT/'D-SIMPLE'/iid/'result.json',result);return result
        execution=types.SimpleNamespace(run_one=run_one)
        with patch.object(W,'probe',return_value={'passed':True}),patch.object(W,'verify_batch'),patch.object(B,'install',return_value=(execution,None)),patch.object(B,'stopped',return_value=False),patch.object(B,'stop') as stop:
            W.work(path,execute=True)
        self.assertEqual(calls,['first','second']);self.assertEqual(C.load(self.run/C.COHORT/'D-SIMPLE/first/result.json')['status'],'failed');stop.assert_not_called()

    def test_contract_violation_globalstops_without_model_call(self):
        self.ledger();path=self.run/'batch.json';C.write(path,{'tasks':[],'shared_budget_contract':{},'worker_receipt_dir':str(self.run/'receipts')})
        with patch.object(W,'probe',return_value={'passed':True}),patch.object(W,'verify_batch'),patch.object(B,'install',side_effect=B.BudgetIntegrityError('wrong ledger')),patch.object(B,'stop') as stop:
            with self.assertRaises(B.BudgetIntegrityError):W.work(path,execute=True)
        stop.assert_called_once()

    def test_budget_stop_is_not_cleared_or_bypassed(self):
        self.ledger();C.write(R.FREEZE,{'freeze':'current'})
        C.write(self.run/'cpu_tests.json',{'passed':True,'source_sha256':{}});C.write(self.run/'isolation_probe.json',{'passed':True,'online_freeze_sha256':C.sha(R.FREEZE)})
        (self.finance/'budget_stop.json').write_text('{"reason":"cap"}')
        with patch.object(R,'source_signature',return_value={}):
            with self.assertRaises(RuntimeError):R.paid_gates({},'smoke')
        self.assertTrue((self.finance/'budget_stop.json').exists())

    def test_stale_probe_cannot_authorize_paid_launch(self):
        C.write(self.run/'cpu_tests.json',{'passed':True,'source_sha256':{}});C.write(self.run/'isolation_probe.json',{'passed':True,'online_freeze_sha256':'old'})
        C.write(R.FREEZE,{'new':'freeze'})
        with patch.object(R,'source_signature',return_value={}):
            with self.assertRaises(RuntimeError):R.paid_gates({},'smoke')

if __name__=='__main__':unittest.main()
