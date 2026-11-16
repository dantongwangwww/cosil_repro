"""CPU synthetic contract tests. No benchmark Gold, models or services are used."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

from . import report as r


def put(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def bundle(n=2):
    rows = []; gold = {}; inv = {}; details = {}
    for k in range(n):
        iid = 'synthetic-' + str(k); targets = ['pkg/a.py::f'] if k == 0 else ['pkg/a.py::f' + str(i) for i in range(5)]
        prediction = {'path': 'pkg/a.py', 'qualified_name': 'f' if k == 0 else 'f0'}
        arms = {arm: {'status': 'complete', 'predicted_files': ['pkg/a.py'], 'predicted_functions': [prediction]} for arm in r.ARMS}
        rows.append({'instance_id': iid, 'repo': 'x/y', 'base_commit': 'a' * 40, 'arms': arms})
        gold[iid] = {'status': 'COMPLETE_NONEMPTY', 'set_complete': True, 'targets': targets, 'gold_files': ['pkg/a.py']}
        inv[iid] = {'paths': ['pkg/a.py'], 'function_identities': targets}
        for arm in r.ARMS:
            details[(iid, arm)] = {'resource': r.blocked_resource(), 'local_events': []}
    return {'records': rows, 'gold': gold, 'inventory': inv, 'details': details}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name) / 'new'; self.root.mkdir()
        self.row = {'instance_id': 'synthetic-0', 'repo': 'x/y', 'base_commit': 'a' * 40,
            'rank': 1, 'upstream_status': 'ready', 'no_model_dispatch': False,
            'public_input_path': str(self.root / 'inputs/synthetic-0'), 'original_work': str(self.root / 'old')}
        public = Path(self.row['public_input_path'])
        job = {**{k: self.row[k] for k in r.IDENTITY}, 'problem_statement': 'a public synthetic issue',
            'cohort': 'synthetic', 'snapshot': '/snapshot', 'paths': ['pkg/a.py'],
            'code_index': '/input/code_index.json', 'structure': '/input/repo_structures/synthetic-0.json'}
        for name, value in [('job.json', job), ('code_index.json', {}), ('render_cache.json', {}),
                ('public_receipt.json', {'gold_or_patch_read': False}),
                ('repo_structures/synthetic-0.json', {}),
                ('shared.json', {'instance_id': self.row['instance_id'], 'base_commit': self.row['base_commit'],
                                 'files': ['pkg/a.py'], 'raw_file_responses': ['pkg/a.py']})]:
            put(public / name, value)
        source_job = self.root / 'old_job.json'; put(source_job, job)
        self.row['source_job_path'] = str(source_job)
        origin = self.root / 'old_upstream.json'; put(origin, {'public_file_evidence': True})
        self.row['upstream_files_sha256'] = {str(origin): r.sha(origin)}
        self.refresh()
        self.protocol = 'b' * 64
        put(self.root / 'run/freeze.json', {'protocol_sha256': self.protocol, 'arms': r.VARIANTS, 'simulation': False})
        self.terminals()

    def tearDown(self):
        self.tmp.cleanup()

    def refresh(self):
        public = Path(self.row['public_input_path'])
        self.row['public_files_sha256'] = {p.relative_to(public).as_posix(): r.sha(p) for p in public.rglob('*') if p.is_file()}
        put(self.root / 'protocol.json', {'synthetic': True})
        put(self.root / 'manifest.json', {'schema': 1, 'n': 1, 'allocated': 1, 'arms': r.VARIANTS, 'records': [self.row]})
        put(self.root / 'authority.json', {'parent': str(self.root / 'old'),
            'manifest_sha256': r.sha(self.root / 'manifest.json'), 'protocol_sha256': r.sha(self.root / 'protocol.json'),
            'files_sha256': {str(self.root / 'protocol.json'): r.sha(self.root / 'protocol.json')}})

    def terminals(self, *, no_dispatch=False):
        terms = {}
        for arm in r.VARIANTS:
            directory = self.root / 'run/pairs/synthetic-0' / arm
            term = {'instance_id': self.row['instance_id'], 'base_commit': self.row['base_commit'], 'arm': arm,
                'internal_arm': 'hybrid_safe', 'status': 'complete', 'protocol_sha256': self.protocol,
                'keep_in_denominator': True, 'simulation': False}
            if no_dispatch:
                term.update(status='dependency_blocked', model_called=False, upstream_status=self.row['upstream_status'])
            else:
                put(directory / 'started.json', {'protocol_sha256': self.protocol, 'arm': arm})
                put(directory / 'result.json', {**{k: self.row[k] for k in r.IDENTITY}, 'arm': 'hybrid_safe',
                    'internal_arm': 'hybrid_safe', 'experimental_arm': arm, 'status': 'complete',
                    'predicted_files': ['pkg/a.py'], 'predicted_functions': [{'path': 'pkg/a.py', 'qualified_name': 'f'}]})
                term['result_sha256'] = r.sha(directory / 'result.json')
            put(directory / 'terminal.json', term); terms[arm] = term
        put(self.root / 'run/pairs/synthetic-0/group_terminal.json', {'instance_id': self.row['instance_id'],
            'base_commit': self.row['base_commit'], 'simulation': False, 'protocol_sha256': self.protocol, 'arms': terms, 'keep_in_denominator': True})
        return terms

    def test_public_poison_job_is_rejected_even_after_hash_update(self):
        path = Path(self.row['public_input_path']) / 'job.json'; value = r.read(path); value['patch'] = 'private poison'; put(path, value); self.refresh()
        with self.assertRaisesRegex(ValueError, 'nine clean'): r.public_manifest(self.root, 1, expected_n=1)

    def test_issue_text_cannot_be_changed_even_with_rehashed_staging(self):
        path=Path(self.row['public_input_path'])/'job.json';value=r.read(path)
        value['problem_statement']='poisoned answer text';put(path,value);self.refresh()
        with self.assertRaisesRegex(ValueError,'original public issue'):
            r.public_manifest(self.root,1,expected_n=1)

    def test_shared_poison_and_same_iid_wrong_base_are_rejected(self):
        path = Path(self.row['public_input_path']) / 'shared.json'; value = r.read(path)
        for field, data in [('gold_functions', ['private']), ('base_commit', 'c' * 40)]:
            changed = dict(value); changed[field] = data; put(path, changed); self.refresh()
            with self.assertRaisesRegex(ValueError, 'Shared file'): r.public_manifest(self.root, 1, expected_n=1)

    def test_extra_private_public_file_is_rejected(self):
        put(Path(self.row['public_input_path']) / 'gold.json', {'secret': 1}); self.refresh()
        with self.assertRaisesRegex(ValueError, 'inventory'): r.public_manifest(self.root, 1, expected_n=1)

    def test_all_three_terminal_barrier_and_real_roles(self):
        r.public_manifest(self.root, 1, expected_n=1)
        gate, terms = r.terminal_barrier(self.root, [self.row])
        self.assertEqual(gate['terminal_arms'], 3); self.assertFalse(gate['gold_opened'])
        pred, detail = r.new_arm(self.root, self.row, r.VARIANTS[0], terms[(self.row['instance_id'], r.VARIANTS[0])], {})
        self.assertEqual(pred['status'], 'complete'); self.assertTrue(detail['terminal_verified'])

    def test_missing_arm_never_opens_private_bundle(self):
        (self.root / 'run/pairs/synthetic-0' / r.VARIANTS[0] / 'terminal.json').unlink()
        with mock.patch.object(r, 'load_bundle') as private:
            with self.assertRaises(OSError): r.run(self.root, 1, self.root / 'out', draws=40, expected_n=1)
        private.assert_not_called()

    def test_result_hash_drift_rejected_before_gold(self):
        put(self.root / 'run/pairs/synthetic-0' / r.VARIANTS[0] / 'result.json', {'new': 'answer'})
        with mock.patch.object(r, 'load_bundle') as private:
            with self.assertRaisesRegex(ValueError, 'SHA mismatch'): r.run(self.root, 1, self.root / 'out', draws=40, expected_n=1)
        private.assert_not_called()

    def test_same_iid_terminal_wrong_base_rejected(self):
        p = self.root / 'run/pairs/synthetic-0' / r.VARIANTS[0] / 'terminal.json'; v = r.read(p); v['base_commit'] = 'd' * 40; put(p, v)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'): r.terminal_barrier(self.root, [self.row])

    def test_fake_complete_without_start_rejected(self):
        (self.root / 'run/pairs/synthetic-0' / r.VARIANTS[0] / 'started.json').unlink()
        with self.assertRaisesRegex(ValueError, 'never started'): r.terminal_barrier(self.root, [self.row])

    def test_raw_internal_or_external_identity_not_silently_rewritten(self):
        arm = r.VARIANTS[0]; p = self.root / 'run/pairs/synthetic-0' / arm / 'result.json'; v = r.read(p); v['experimental_arm'] = r.VARIANTS[1]; put(p, v)
        term = {'status': 'complete'}
        with self.assertRaisesRegex(ValueError, 'condition identity'): r.new_arm(self.root, self.row, arm, term, {})

    def test_no_dispatch_has_zero_actual_calls_and_remains_evaluable(self):
        for p in (self.root / 'run/pairs/synthetic-0').rglob('*'):
            if p.is_file():p.unlink()
        self.row.update(upstream_status='source_preparation_blocked', no_model_dispatch=True)
        terms = self.terminals(no_dispatch=True); self.refresh()
        gate, actual = r.terminal_barrier(self.root, [self.row]); self.assertEqual(gate['terminal_arms'], 3)
        pred, detail = r.new_arm(self.root, self.row, r.VARIANTS[0], actual[(self.row['instance_id'], r.VARIANTS[0])], {})
        self.assertEqual(pred['status'], 'PREPARATION_BLOCKED'); self.assertEqual(detail['resource']['http_attempts_recorded'], 0)
        b = bundle(1)
        for arm in r.VARIANTS:b['records'][0]['arms'][arm] = pred
        evaluation = r.evaluate(b, draws=40)
        self.assertEqual(evaluation['summary']['allocated'], 1)
        self.assertEqual(evaluation['summary']['metrics'][r.VARIANTS[0]]['function']['n'], 1)
        self.assertEqual(evaluation['summary']['metrics'][r.VARIANTS[0]]['function']['hit5_numerator'], 0)

    def test_no_dispatch_cannot_hide_started_worker(self):
        self.row.update(upstream_status='upstream_file_stage_unavailable', no_model_dispatch=True)
        self.terminals(no_dispatch=True)
        with self.assertRaisesRegex(ValueError, 'actually executed'):r.terminal_barrier(self.root, [self.row])

    def test_group_requires_exact_base_and_nonsimulation(self):
        path = self.root/'run/pairs/synthetic-0/group_terminal.json'; value=r.read(path)
        for key,data in [('base_commit','f'*40),('simulation',True)]:
            changed=dict(value);changed[key]=data;put(path,changed)
            with self.assertRaisesRegex(ValueError,'group'):
                r.terminal_barrier(self.root,[self.row])

    def test_new_file_model_call_is_a_protocol_violation(self):
        arm=r.VARIANTS[0];directory=self.root/'run/pairs/synthetic-0'/arm
        put(directory/'calls/0001_file_initial/attempt_0_receipt.json',{'stage':'file_initial','usage':{'prompt_tokens':1,'completion_tokens':1}})
        term=r.read(directory/'terminal.json')
        with self.assertRaisesRegex(ValueError,'file model'):
            r.new_arm(self.root,self.row,arm,term,{})

    def test_unknown_http_phase_is_not_fabricated_as_zero(self):
        value=r.http_phases(self.root/'no_calls',{}, {})
        self.assertIsNone(value['file_stage_http_attempts'])

    def test_new_arm_error_receipt_is_unknown_even_without_success_event(self):
        arm=r.VARIANTS[0];directory=self.root/'run/pairs/synthetic-0'/arm
        result=r.read(directory/'result.json');result['status']='failed';put(directory/'result.json',result)
        term=r.read(directory/'terminal.json');term.update(status='worker_failed',result_sha256=r.sha(directory/'result.json'))
        identity={'request_id':'failed','experimental_arm':arm,'internal_arm':'hybrid_safe','input_sha256':'d'*64,'operation':'score'}
        put(directory/'judge_rpc/failed_start.json',dict(identity,status='started'))
        put(directory/'judge_rpc/failed_receipt.json',dict(identity,status='error',forward_status='unknown',usage_status='unknown',input_tokens=None,generated_output_tokens=None,error_type='FloatingPointError'))
        pred,detail=r.new_arm(self.root,self.row,arm,term,{})
        self.assertEqual(pred['status'],'failed');self.assertIsNone(detail['resource']['local_input_tokens'])
        self.assertIsNone(detail['resource']['local_physical_scoring_forwards'])
        self.assertEqual(detail['resource']['judge_forward_known_sum'],0)
        self.assertEqual(detail['resource']['judge_forward_unknown_attempts'],1)

    def test_closed_synthetic_end_to_end_writes_chinese_and_csv_without_models(self):
        b = bundle(1);b['records'][0].update({k:self.row[k] for k in r.IDENTITY});old_id='synthetic-0'
        with mock.patch.object(r, 'load_bundle', return_value=b) as private:
            value = r.run(self.root, 1, self.root / 'out', draws=40, expected_n=1)
        private.assert_called_once();self.assertEqual(value['function_denominator'],1)
        manifest = r.read(self.root / 'out/output_sha256.json')
        self.assertIn('消融实验_总览.md',manifest);self.assertIn('逐题定位与资源.csv',manifest)
        self.assertTrue(r.read(self.root/'out/terminal_gate.json')['passed'])
        with self.assertRaises(FileExistsError):r.run(self.root,1,self.root/'out',draws=40,expected_n=1)


class Metrics(unittest.TestCase):
    def test_macro_f1_is_not_harmonic_of_macro_precision_recall(self):
        evaluated = r.evaluate(bundle(), draws=40); m = evaluated['summary']['metrics']['hybrid_safe']['function']
        self.assertAlmostEqual(m['f15'], (1/3+.2)/2)
        harmonic = 2*m['precision5']*m['recall5']/(m['precision5']+m['recall5'])
        self.assertNotAlmostEqual(m['f15'], harmonic)

    def test_all_three_reference_comparisons_and_holm_nine_tests(self):
        evaluated = r.evaluate(bundle(), draws=40); comparisons = evaluated['paired_against_full_sf']
        self.assertEqual(len(comparisons),9)
        self.assertTrue(all(v['reference']=='hybrid_safe' for v in comparisons.values()))
        self.assertEqual(r.holm({'a':.01,'b':.03,'c':.04}),{'a':.03,'b':.06,'c':.06})

    def test_rejected_gold_uses_visits_not_unvisited_gold_as_retained(self):
        b=bundle();iid=b['records'][0]['instance_id']
        b['details'][(iid,r.VARIANTS[2])]['local_events']=[{'function_id':'pkg/a.py::f','p_yes':.4,
            'low':.1,'high':.9,'route':'reject','route_original':'qwen','route_effective':'reject'}]
        value=r.route_risk(b)[r.VARIANTS[2]]
        self.assertEqual(value['gold_visited_unique_identities'],1);self.assertEqual(value['gold_direct_rejected_unique_identities'],1)
        self.assertEqual(value['gold_direct_reject_fraction_given_visit'],1)
        self.assertEqual(value['gray_direct_override_events'],1);self.assertTrue(value['unvisited_gold_is_not_counted_as_retained'])

    def test_unknown_usage_remains_unknown_and_history_cost_not_recharged(self):
        b=bundle();b['details'][('synthetic-0',r.VARIANTS[0])]['resource']['main_tokens']=None
        resources=r.resource_summary(b)
        self.assertIsNone(resources[r.VARIANTS[0]]['new_physical_main_tokens'])
        self.assertEqual(resources['hybrid_safe']['new_physical_main_tokens'],0)
        self.assertEqual(resources['hybrid_safe']['new_physical_api_usd'],0)

if __name__=='__main__': unittest.main()


class JudgePhysicalJournal(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.directory=Path(self.tmp.name);self.arm=r.VARIANTS[0]
    def tearDown(self):self.tmp.cleanup()
    def journal(self, request, *, operation='score', outcome='success', tokens=31, closed=True):
        identity={'request_id':request,'experimental_arm':self.arm,'internal_arm':'hybrid_safe',
                  'input_sha256':'d'*64,'operation':operation}
        put(self.directory/'judge_rpc'/(request+'_start.json'),dict(identity,status='started'))
        if closed:
            put(self.directory/'judge_rpc'/(request+'_receipt.json'),dict(identity,status=outcome,
                forward_status='confirmed_score_success' if outcome=='success' else 'unknown',
                usage_status='known' if outcome=='success' else 'unknown',
                input_tokens=tokens if outcome=='success' else None,
                generated_output_tokens=0 if outcome=='success' else None,
                adapter_active=False,score_sequence=1,elapsed_seconds=.1))
    def test_actual_forward_without_local_judge_event_is_counted(self):
        self.journal('a');provenance={};value=r.judge_journal(self.directory,self.arm,provenance)
        self.assertEqual(value['local_physical_scoring_forwards'],1)
        self.assertEqual(value['local_input_tokens'],31)
        self.assertEqual(value['local_successful_score_events'],0)
        self.assertIsNone(value['local_forward_seconds'])
        self.assertEqual(len(provenance),2)
    def test_forward_then_nonfinite_or_disconnect_does_not_become_zero(self):
        self.journal('a');self.journal('b',outcome='error')
        value=r.judge_journal(self.directory,self.arm,{})
        self.assertEqual(value['judge_forward_known_sum'],1)
        self.assertEqual(value['judge_input_tokens_known_sum'],31)
        self.assertEqual(value['judge_forward_unknown_attempts'],1)
        self.assertEqual(value['judge_usage_unknown_attempts'],1)
        self.assertIsNone(value['local_physical_scoring_forwards']);self.assertIsNone(value['local_input_tokens'])
    def test_unmatched_start_is_unknown_and_probe_is_separate(self):
        self.journal('pending',closed=False);self.journal('probe',operation='probe',tokens=7)
        value=r.judge_journal(self.directory,self.arm,{})
        self.assertEqual(value['judge_rpc_attempts'],1)
        self.assertEqual(value['judge_forward_known_sum'],0)
        self.assertIsNone(value['local_physical_scoring_forwards'])
        self.assertEqual(value['judge_nonbenchmark_operations']['known_input_tokens_sum'],7)
        self.assertEqual(value['judge_input_tokens_known_sum'],0)
    def test_cross_arm_or_input_journal_rejected(self):
        self.journal('a');path=self.directory/'judge_rpc/a_receipt.json';v=r.read(path);v['input_sha256']='e'*64;put(path,v)
        with self.assertRaisesRegex(ValueError,'identity mismatch'):r.judge_journal(self.directory,self.arm,{})
    def test_technical_fallback_union_uses_real_prune_flag(self):
        b=bundle(1);key=('synthetic-0',self.arm)
        b['details'][key].update(all_events_available=True,all_events=[
            {'event':'judge_binding_fallback','step':2,'tool':'get_code_of_function','arguments':['a.py','f']},
            {'event':'prune','technical_fallback':True,'step':2,'tool':'get_code_of_function','arguments':['a.py','f']},
            {'event':'prune','technical_fallback':True,'step':3,'tool':'get_code_of_function','arguments':['a.py','g']}])
        values=r.route_risk(b)[self.arm]
        self.assertEqual(values['technical_fallback_events'],2)
        self.assertEqual(values['technical_fallback_prune_events'],2)


class RealBundleLayout(unittest.TestCase):
    """Exercise load_bundle itself over real synthetic historical/new files."""
    def test_real_layout_old_controls_new_results_and_all_no_call_categories(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'new';old=Path(temp)/'old';protocol='b'*64
            records=[];allocated=[];runnable=[];gold={};inventory={};statuses={};terms={}
            specs=[('ready',False),('source_preparation_blocked',True),('upstream_file_stage_unavailable',True)]
            for number,(upstream,blocked) in enumerate(specs):
                iid='layout-'+str(number);base={'instance_id':iid,'repo':'x/y','base_commit':'a'*40}
                row=dict(base,rank=number+1,original_work=str(old),upstream_status=upstream,no_model_dispatch=blocked)
                records.append(row);allocated.append(base)
                gold[iid]={'status':'COMPLETE_NONEMPTY','set_complete':True,'targets':['pkg/a.py::f'],'gold_files':['pkg/a.py'],**base}
                inventory[iid]={'paths':['pkg/a.py'],'function_identities':['pkg/a.py::f']}
                if upstream!='source_preparation_blocked':
                    snap=old/'runtime/tasks'/iid/'snapshot';snap.mkdir(parents=True);(snap/'pkg').mkdir();(snap/'pkg/a.py').write_text('def f():\n return 1\n')
                    job={**base,'problem_statement':'Synthetic public issue','cohort':'fixture','snapshot':'snapshot','paths':['pkg/a.py'],'code_index':'code_index.json','structure':'structure.json'}
                    jp=snap.parent/'job.json';put(jp,job);put(snap.parent/'code_index.json',{'pkg/a.py':{'raw_sha256':r.sha(snap/'pkg/a.py'),'definitions':[{'kind':'function','qualified_name':'f'}]}});put(snap.parent/'structure.json',{})
                    runnable.append(dict(base,job='tasks/'+iid+'/job.json'))
                    for arm in ('baseline','hybrid_safe'):
                        d=old/'paired_run/pairs'/iid/arm
                        result={**base,'arm':arm,'status':'complete','predicted_files':['pkg/a.py'],'predicted_functions':[{'path':'pkg/a.py','qualified_name':'f'}]}
                        put(d/'result.json',result);put(d/'terminal.json',dict(base,arm=arm,status='complete',protocol_sha256=protocol,simulation=False,keep_in_denominator=True,result_sha256=r.sha(d/'result.json')))
                statuses[iid]={'status':'PREPARATION_BLOCKED' if upstream=='source_preparation_blocked' else 'RUNTIME_READY'}
                for arm in r.VARIANTS:
                    d=root/'run/pairs'/iid/arm
                    term=dict(base,arm=arm,internal_arm='hybrid_safe',protocol_sha256=protocol,simulation=False,keep_in_denominator=True)
                    if blocked:term.update(status=upstream,upstream_status=upstream,model_called=False)
                    else:
                        put(d/'started.json',{'protocol_sha256':protocol,'arm':arm})
                        put(d/'result.json',dict(base,arm='hybrid_safe',experimental_arm=arm,status='complete',predicted_files=['pkg/a.py'],predicted_functions=[{'path':'pkg/a.py','qualified_name':'f'}]))
                        term.update(status='complete',result_sha256=r.sha(d/'result.json'))
                        identity={'request_id':'rpc','experimental_arm':arm,'internal_arm':'hybrid_safe','operation':'score','input_sha256':'d'*64}
                        put(d/'judge_rpc/rpc_start.json',dict(identity,status='started'))
                        put(d/'judge_rpc/rpc_receipt.json',dict(identity,status='success',forward_status='confirmed_score_success',usage_status='known',input_tokens=31,generated_output_tokens=0,score_sequence=1,adapter_active=arm!='ablation_no_lora'))
                    put(d/'terminal.json',term);terms[(iid,arm)]=term
            put(old/'gold.json',gold);put(old/'inventory.json',inventory)
            put(old/'paired_run/freeze.json',{'protocol_sha256':protocol})
            frozen={'gold':str(old/'gold.json'),'inventory':str(old/'inventory.json'),'run_root':str(old/'paired_run'),'source_sha256':{str(old/'gold.json'):r.sha(old/'gold.json'),str(old/'inventory.json'):r.sha(old/'inventory.json')}}
            put(old/'controller/report_freeze.json',frozen)
            # The old whole-benchmark provenance barrier has its own production
            # tests; only its returned synthetic public identities are stubbed.
            with mock.patch.object(r.old,'terminal_barrier',return_value=({},allocated,runnable,statuses)):
                actual=r.load_bundle(root,records,terms,{})
            evaluated=r.evaluate(actual,draws=40)
            self.assertEqual(evaluated['summary']['allocated'],3)
            for arm in r.VARIANTS:
                self.assertEqual(evaluated['summary']['metrics'][arm]['function']['n'],3)
                self.assertEqual(evaluated['summary']['metrics'][arm]['function']['hit5_numerator'],1)
                self.assertEqual(actual['details'][('layout-0',arm)]['resource']['local_input_tokens'],31)
                self.assertEqual(actual['details'][('layout-0',arm)]['resource']['local_successful_score_events'],0)
                self.assertEqual(actual['records'][1]['arms'][arm]['status'],'PREPARATION_BLOCKED')
                self.assertEqual(actual['records'][2]['arms'][arm]['status'],'UPSTREAM_FILE_STAGE_UNAVAILABLE')

if __name__ == '__main__':
    unittest.main()
