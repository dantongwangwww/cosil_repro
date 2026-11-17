"""Hermetic fixtures only; never open a LocBench Gold/model/result asset."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import analysis as a


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False))
    return a.digest(path.read_bytes())


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = '@deco\ndef f():\n    return 1\n\nclass C:\n    def __init__(self):\n        pass\n\ndef outer():\n    def inner():\n        return 2\n    return inner()\n'
        (self.root/'m.py').write_text(self.source)
        self.functions = {}
        self.definitions = []
        for qn, start, definition, end in [('f',1,2,3),('C.__init__',6,6,7),('outer',9,9,12),('outer.inner',10,10,11)]:
            raw_id = f'm.py::{qn}@{definition}'
            body = ''.join(self.source.splitlines(keepends=True)[definition-1:end])
            self.functions[raw_id] = dict(id=raw_id,file='m.py',qualified_name=qn,start_line=definition,
                def_line=definition,end_line=end,source_sha256=a.digest(body.encode()),source_characters=len(body))
            self.definitions.append(dict(kind='function',qualified_name=qn,start_line=start,def_line=definition,end_line=end))
        self.index = {'m.py':dict(definitions=self.definitions,raw_sha256=a.digest(self.source.encode()),parse_error=None)}
        self.cache = dict(base_commit='base',functions=self.functions)

    def mapper(self):
        return a.Mapper(self.cache,self.index,self.root,'base',a.Evidence())

    def event(self, fid='m.py::f@2', **updates):
        value=dict(event='local_judge',instance_id='iid',arm='hybrid_safe',function_id=fid,
            source_sha256=self.functions.get(fid,{}).get('source_sha256'),p_yes=.4,route='qwen')
        value.update(updates);return value

    def test_decorator_uses_definition_not_start(self):
        result=self.mapper().resolve(self.event())
        self.assertEqual(result['canonical_function_id'],'m.py::f')
        self.assertEqual((result['base_index_start_line'],result['def_line']),(1,2))
        self.assertTrue(result['decorator_start_differs'])

    def test_init_and_nested_names_preserved(self):
        for fid in ('m.py::C.__init__@6','m.py::outer.inner@10'):
            self.assertEqual(self.mapper().resolve(self.event(fid))['canonical_function_id'],fid.rsplit('@',1)[0])

    def test_mapping_has_no_gold_parameter(self):
        event=self.event();before=self.mapper().resolve(event)
        unused_gold={'m.py::f'}; unused_gold.clear();unused_gold.add('other.py::g')
        self.assertEqual(before,self.mapper().resolve(event))

    def test_duplicate_cache_qname_is_unknown(self):
        self.cache['functions']['m.py::f@20']={**self.functions['m.py::f@2'],'id':'m.py::f@20','def_line':20}
        self.assertIsNone(self.mapper().resolve(self.event())['canonical_function_id'])

    def test_duplicate_base_definition_is_unknown(self):
        self.definitions.append(dict(self.definitions[0]))
        self.assertIn('ambiguous',self.mapper().resolve(self.event())['mapping_reason'])

    def test_source_sha_conflict_is_unknown(self):
        result=self.mapper().resolve(self.event(source_sha256='0'*64))
        self.assertEqual(result['mapping_status'],'unknown')
        self.assertIsNone(result['canonical_function_id'])

    def test_actual_base_bytes_mismatch_is_unknown(self):
        (self.root/'m.py').write_text('def f(): pass\n')
        self.assertEqual(self.mapper().resolve(self.event())['mapping_reason'],'base_file_raw_sha_mismatch')

    def test_absent_exact_id_not_guessed_by_suffix(self):
        self.assertEqual(self.mapper().resolve(self.event('m.py::f@1'))['mapping_status'],'unknown')

    def test_wrong_base_commit_refused(self):
        with self.assertRaises(ValueError):a.Mapper(self.cache,self.index,self.root,'other',a.Evidence())

    def test_index_endline_conflict_unknown(self):
        self.definitions[0]['end_line']=2
        self.assertEqual(self.mapper().resolve(self.event())['mapping_reason'],'base_definition_range_mismatch')

    def test_path_escape_unknown(self):
        fn=self.functions['m.py::f@2'];fn['file']='../m.py'
        self.assertEqual(self.mapper().resolve(self.event())['mapping_status'],'unknown')

    def test_original_false_zero_schema_and_unknown_not_false(self):
        raw=self.event(); mapper=self.mapper()
        self.assertNotIn(raw['function_id'],{'m.py::f'})
        events=a.local_event_rows([raw,self.event('absent')],mapper,'iid','hybrid_safe','events')
        technical={('iid',arm):{} for arm in a.LOCAL};available={('iid',arm):'recorded' for arm in a.LOCAL}
        value,reject=a.aggregate(['iid'],{'iid':{'m.py::f'}},events,technical,available,draws=40)
        full=value['conditions']['hybrid_safe']
        self.assertIs(events[0]['is_gold'],True)
        self.assertIsNone(events[1]['is_gold'])
        self.assertEqual(full['known_lower_bounds']['gold_score_visits'],1)
        self.assertIsNone(full['gold_score_visits'])
        self.assertFalse(full['attribution_complete'])
        self.assertIsNone(value['conditions']['baseline']['gold_score_visits'])

    def test_common_visited_unknown_repeated_rejection_is_na(self):
        mapper=self.mapper();known=self.event(p_yes=.95,route='retain')
        unknown=self.event(p_yes=.1,route='reject',source_sha256='0'*64)
        events=a.local_event_rows([known],mapper,'iid','hybrid_safe','full_events')
        cmp_events=a.local_event_rows([dict(known,experimental_arm='ablation_no_lora'),dict(unknown,experimental_arm='ablation_no_lora')],mapper,'iid','ablation_no_lora','cmp_events')
        technical={('iid',arm):{} for arm in a.LOCAL};available={('iid',arm):'recorded' for arm in a.LOCAL}
        value,_=a.aggregate(['iid'],{'iid':{'m.py::f'}},events+cmp_events,technical,available,draws=40)
        pair=value['common_visited_exploratory']['ablation_no_lora']
        self.assertIsNone(value['conditions']['ablation_no_lora']['unique_identity_conditional_risk'])
        for field in ('reference_risk','comparison_risk','comparison_minus_reference','reference_ci95','comparison_ci95','difference_ci95'):
            self.assertIsNone(pair[field])
        self.assertEqual(pair['verified_lower_bound_counts_only']['common_visited_identities'],1)
        self.assertEqual(pair['verified_lower_bound_counts_only']['comparison_rejected_identities'],0)
        self.assertEqual(pair['unknown_reasons_by_condition']['ablation_no_lora']['unknown_attribution_events'],1)

    def test_known_zero_bootstrap_not_zero_risk_claim(self):
        technical={('iid',arm):{} for arm in a.LOCAL};available={('iid',arm):'recorded' for arm in a.LOCAL}
        events=a.local_event_rows([self.event()],self.mapper(),'iid','hybrid_safe','events')
        value,_=a.aggregate(['iid'],{'iid':{'m.py::f'}},events,technical,available,draws=40)
        risk=value['conditions']['hybrid_safe']
        self.assertTrue(risk['unique_identity_conditional_risk']['degenerate_bootstrap'])
        self.assertGreater(risk['task_any_gold_reject_conditional_risk']['clopper_pearson_ci95'][1],0)

    def test_no_defer_gray_only_and_routes_not_mutated(self):
        raw=self.event(route='reject',route_original='qwen',route_effective='reject')
        before=copy.deepcopy(raw);result=a.route_fields(raw,'ablation_no_defer')
        self.assertTrue(result['route_valid']);self.assertEqual(raw,before)
        self.assertTrue(a.route_fields(self.event(p_yes=.5,route='retain'),'ablation_no_defer')['route_valid'])
        self.assertFalse(a.route_fields(self.event(route='retain'),'hybrid_safe')['route_valid'])

    def test_technical_union_not_fake_zero_or_double_count(self):
        common=dict(step=1,tool='tool',arguments=['f'])
        events=[dict(event='judge_binding_fallback',**common),dict(event='prune',technical_fallback=True,**common),dict(event='pruner_class_fallback')]
        counts=a.technical_counts(events)
        self.assertEqual(counts['technical_fallback_events'],1)
        self.assertEqual(counts['class_fallback_events'],1)


class BarrierTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.row=dict(instance_id='iid',base_commit='base',no_model_dispatch=True,upstream_status='source_preparation_blocked')
        self.execution=dict(protocol_sha256='a'*64,manifest_sha256='m'*64,authority_sha256='u'*64,
            files_sha256={str(a.CONTROLLER_SOURCE.resolve()):a.digest(a.CONTROLLER_SOURCE.read_bytes())})
        payload=dict(allocated=560,arms=list(a.VARIANTS),user_protocol_sha256=self.execution['protocol_sha256'],
            manifest_sha256=self.execution['manifest_sha256'],preparation_authority_sha256=self.execution['authority_sha256'],
            controller_sha256=self.execution['files_sha256'][str(a.CONTROLLER_SOURCE.resolve())])
        self.protocol=a.canonical_digest(payload)
        put(self.root/'run/freeze.json',dict(payload,protocol_sha256=self.protocol))
        states={}
        for arm in a.VARIANTS:
            term=dict(instance_id='iid',base_commit='base',arm=arm,protocol_sha256=self.protocol,status='source_preparation_blocked',simulation=False,keep_in_denominator=True,model_called=False,upstream_status='source_preparation_blocked')
            put(self.root/'run/pairs/iid'/arm/'terminal.json',term);states[arm]=term
        put(self.root/'run/pairs/iid/group_terminal.json',dict(instance_id='iid',base_commit='base',protocol_sha256=self.protocol,arms=states,simulation=False,keep_in_denominator=True))
        put(self.root/'controller/checkpoints/1.json',dict(status='PREFIX_ALL_ARMS_TERMINAL',n=1,protocol_sha256=self.protocol))

    def test_terminal_failure_is_honest_and_no_gold_read(self):
        evidence=a.Evidence();a.terminal_barrier(self.root,[self.row],evidence,self.execution)
        self.assertNotEqual(self.execution['protocol_sha256'],self.protocol)
        self.assertTrue(all('gold' not in p.lower() for p in evidence.hashes))

    def test_unclosed_group_refused_before_private_reader(self):
        (self.root/'run/pairs/iid/group_terminal.json').unlink()
        with patch.object(a,'load_postterminal',side_effect=AssertionError('private reader invoked')) as private:
            with self.assertRaises(FileNotFoundError):a.terminal_barrier(self.root,[self.row],a.Evidence(),self.execution)
            private.assert_not_called()

    def test_no_call_cannot_hide_started(self):
        put(self.root/'run/pairs/iid/ablation_no_lora/started.json',{})
        with self.assertRaises(ValueError):a.terminal_barrier(self.root,[self.row],a.Evidence(),self.execution)

    def test_wrong_base_refused(self):
        self.row['base_commit']='different'
        with self.assertRaises(ValueError):a.terminal_barrier(self.root,[self.row],a.Evidence(),self.execution)

    def test_wrong_execution_to_user_protocol_link_refused(self):
        freeze=json.loads((self.root/'run/freeze.json').read_text());freeze['user_protocol_sha256']='wrong'
        freeze['protocol_sha256']=a.canonical_digest({k:v for k,v in freeze.items() if k!='protocol_sha256'})
        put(self.root/'run/freeze.json',freeze)
        with self.assertRaisesRegex(ValueError,'chain'):a.terminal_barrier(self.root,[self.row],a.Evidence(),self.execution)

    def test_manifest_or_authority_chain_mismatch_refused(self):
        for field in ('manifest_sha256','preparation_authority_sha256'):
            with self.subTest(field=field):
                path=self.root/'run/freeze.json';before=json.loads(path.read_text());changed=dict(before);changed[field]='0'*64
                changed['protocol_sha256']=a.canonical_digest({k:v for k,v in changed.items() if k!='protocol_sha256'});put(path,changed)
                with self.assertRaisesRegex(ValueError,'chain'):a.terminal_barrier(self.root,[self.row],a.Evidence(),self.execution)
                put(path,before)

    def test_forged_derived_digest_refused(self):
        freeze=json.loads((self.root/'run/freeze.json').read_text());freeze['pair_workers']=999
        put(self.root/'run/freeze.json',freeze)
        with self.assertRaisesRegex(ValueError,'digest'):a.terminal_barrier(self.root,[self.row],a.Evidence(),self.execution)

    def test_controller_binding_refused(self):
        wrong=copy.deepcopy(self.execution);wrong['files_sha256'][str(a.CONTROLLER_SOURCE.resolve())]='0'*64
        with self.assertRaises(ValueError):a.terminal_barrier(self.root,[self.row],a.Evidence(),wrong)

    def test_wrong_terminal_protocol_chain_refused(self):
        path=self.root/'run/pairs/iid/ablation_no_lora/terminal.json';term=json.loads(path.read_text());term['protocol_sha256']=self.execution['protocol_sha256'];put(path,term)
        with self.assertRaises(ValueError):a.terminal_barrier(self.root,[self.row],a.Evidence(),self.execution)

    def test_evidence_change_and_hash_mismatch_refused(self):
        path=self.root/'file';path.write_bytes(b'first');ev=a.Evidence();ev.raw(path)
        path.write_bytes(b'other changed size')
        with self.assertRaises(ValueError):ev.unchanged()
        with self.assertRaises(ValueError):a.Evidence().raw(path,'0'*64)


class LayoutTests(unittest.TestCase):
    """Exercise actual sealed_scope/load_postterminal/run file layouts."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'riskroot';self.old=Path(self.tmp.name)/'old'
        self.graph=Path(self.tmp.name)/'graph.py';self.graph.write_text('# frozen graph producer\n')
        self.graph_patch=patch.object(a,'GRAPH_SOURCE',self.graph);self.graph_patch.start();self.addCleanup(self.graph_patch.stop)
        self.protocol='b'*64;self.ids=['iid'+str(i) for i in range(560)]
        self.public=Path(self.tmp.name)/'public';self.snapshot=Path(self.tmp.name)/'task/snapshot'
        self.snapshot.mkdir(parents=True);self.source='@deco\ndef f():\n    return 1\n';(self.snapshot/'m.py').write_text(self.source)
        body=''.join(self.source.splitlines(keepends=True)[1:3]);self.body_sha=a.digest(body.encode())
        index={'m.py':dict(definitions=[dict(kind='function',qualified_name='f',start_line=1,def_line=2,end_line=3)],raw_sha256=a.digest(self.source.encode()),parse_error=None)}
        index_sha=put(self.public/'code_index.json',index)
        cache=dict(base_commit='base',index_sha256=index_sha,graph_code_sha256=a.digest(self.graph.read_bytes()),functions={'m.py::f@2':dict(id='m.py::f@2',file='m.py',qualified_name='f',start_line=2,def_line=2,end_line=3,source_sha256=self.body_sha,source_characters=len(body))})
        cache_sha=put(self.public/'render_cache.json',cache)
        job_path=self.snapshot.parent/'job.json';job_sha=put(job_path,dict(instance_id='iid0',base_commit='base',snapshot='snapshot'))
        self.rows=[]
        for i,iid in enumerate(self.ids):
            ready=i==0
            self.rows.append(dict(instance_id=iid,repo='repo',base_commit='base',rank=i+1,original_work=str(self.old),source_job_path=str(job_path) if ready else None,
                source_snapshot=str(self.snapshot) if ready else None,public_input_path=str(self.public) if ready else None,
                public_files_sha256={'code_index.json':index_sha,'render_cache.json':cache_sha} if ready else {},upstream_files_sha256={str(job_path):job_sha} if ready else {},
                upstream_status='ready' if ready else 'source_preparation_blocked',no_model_dispatch=not ready))
        manifest=dict(n=560,records=self.rows,arms=list(a.VARIANTS));manifest_sha=put(self.root/'manifest.json',manifest)
        proto_sha=put(self.root/'protocol.json',dict(allocated=560,root=str(self.root),experiment_id='locbench_qwen3_sfpruner_ablation_20261117'))
        auth_sha=put(self.root/'authority.json',{})
        controller_sha=a.digest(a.CONTROLLER_SOURCE.read_bytes())
        put(self.root/'controller/execution_freeze.json',dict(status='EXECUTION_FROZEN_READY',protocol_sha256=proto_sha,manifest_sha256=manifest_sha,authority_sha256=auth_sha,files_sha256={str(a.CONTROLLER_SOURCE.resolve()):controller_sha}))
        payload=dict(allocated=560,arms=list(a.VARIANTS),user_protocol_sha256=proto_sha,manifest_sha256=manifest_sha,
            preparation_authority_sha256=auth_sha,controller_sha256=controller_sha)
        self.protocol=a.canonical_digest(payload)
        run_freeze_sha=put(self.root/'run/freeze.json',dict(payload,protocol_sha256=self.protocol))
        bound={str(self.root/'run/freeze.json'):run_freeze_sha};self.old_run=self.old/'paired_run'
        for row in self.rows[:100]:
            states={};iid=row['instance_id']
            for arm in a.VARIANTS:
                directory=self.root/'run/pairs'/iid/arm
                term=dict(instance_id=iid,base_commit='base',arm=arm,protocol_sha256=self.protocol,simulation=False,keep_in_denominator=True)
                if row['no_model_dispatch']:
                    term.update(status='source_preparation_blocked',upstream_status='source_preparation_blocked',model_called=False)
                else:
                    put(directory/'started.json',dict(instance_id=iid,base_commit='base',arm=arm,protocol_sha256=self.protocol))
                    result_sha=put(directory/'result.json',dict(status='complete'))
                    term.update(status='complete',internal_arm='hybrid_safe',result_sha256=result_sha)
                    event=dict(event='local_judge',instance_id=iid,arm='hybrid_safe',experimental_arm=arm,function_id='m.py::f@2',source_sha256=self.body_sha,p_yes=.4,route='reject' if arm=='ablation_no_defer' else 'qwen')
                    path=directory/'events.jsonl';path.write_text(json.dumps(event)+'\n');bound[str(path)]=a.digest(path.read_bytes())
                put(directory/'terminal.json',term);states[arm]=term
            put(self.root/'run/pairs'/iid/'group_terminal.json',dict(instance_id=iid,base_commit='base',protocol_sha256=self.protocol,simulation=False,keep_in_denominator=True,arms=states))
        old_term=self.old_run/'pairs/iid0/hybrid_safe/terminal.json'
        bound[str(old_term)]=put(old_term,dict(instance_id='iid0',base_commit='base',arm='hybrid_safe',status='complete'))
        old_event=old_term.parent/'events.jsonl';old_event.write_text(json.dumps(dict(event='local_judge',instance_id='iid0',arm='hybrid_safe',function_id='m.py::f@2',source_sha256=self.body_sha,p_yes=.4,route='qwen'))+'\n');bound[str(old_event)]=a.digest(old_event.read_bytes())
        self.old_allocation=self.old/'allocation.json';old_alloc_sha=put(self.old_allocation,dict(records=self.rows[:100]))
        gold_path=self.old/'private_gold.json';bound[str(gold_path)]=put(gold_path,{iid:dict(status='COMPLETE_NONEMPTY',set_complete=True,targets=['m.py::f']) for iid in self.ids[:100]})
        old_freeze=self.old/'controller/report_freeze.json';bound[str(old_freeze)]=put(old_freeze,dict(allocation=str(self.old_allocation),gold=str(gold_path),run_root=str(self.old_run),source_sha256={str(self.old_allocation):old_alloc_sha}))
        put(self.root/'controller/checkpoints/100.json',dict(status='PREFIX_ALL_ARMS_TERMINAL',n=100,protocol_sha256=self.protocol))
        self.report=self.root/'reports/cumulative100';self.report.mkdir(parents=True)
        put(self.report/'allocation.json',dict(n=100,records=self.rows[:100]))
        put(self.report/'summary.json',dict(allocated=100,terminal_barrier_before_gold=True,models_called_by_evaluator=0))
        put(self.report/'input_sha256.json',bound)
        put(self.report/'route_risk.json',dict(hybrid_safe=dict(gold_score_visits=0)))
        headers=['instance_id']+[arm+'_function_hit'+str(k) for arm in a.LOCAL for k in (1,3,5)]
        with (self.report/'逐题定位与资源.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            import csv
            writer=csv.DictWriter(stream,headers);writer.writeheader()
            for iid in self.ids[:100]:writer.writerow(dict(instance_id=iid))
        self.seal()
        plan_sha=put(self.root/'audits/final_secondary_analysis_plan.json',dict(supplementary_gold_risk_CI=dict(seed=20261110,draws=5000)))
        put(self.root/'audits/final_secondary_analysis_addendum_cp_taskrisk.json',dict(base_plan_sha256=plan_sha,status='POST_FIRST100_DESCRIPTIVE_INTERVAL_ADDENDUM_NOT_PRIMARY_TEST_CHANGE'))
        self.out=self.root/'reports/risk_revision_v3/cumulative100'

    def seal(self):
        output={p.name:a.digest(p.read_bytes()) for p in self.report.iterdir() if p.is_file() and p.name!='output_sha256.json'}
        sealed_sha=put(self.report/'output_sha256.json',output)
        put(self.root/'reports/checkpoints/100.json',dict(status='REPORT_COMPLETE',allocated=100,directory=str(self.report),models_called=0,output_manifest_sha256=sealed_sha))

    def test_real_layout_roundtrip_and_false_zero_regression(self):
        value=a.run(self.root,100,self.out)
        self.assertEqual(value['conditions']['hybrid_safe']['gold_score_visits'],1)
        self.assertEqual(value['conditions']['ablation_no_defer']['gold_direct_reject_events'],1)
        self.assertEqual(value['allocated'],100)
        self.assertFalse(value['primary_metrics_changed'])
        self.assertEqual(json.loads((self.report/'route_risk.json').read_text())['hybrid_safe']['gold_score_visits'],0)
        self.assertTrue((self.out/'Gold直剪逐题.csv').is_file())

    def test_not_report_complete_refuses_private_read(self):
        put(self.root/'reports/checkpoints/100.json',dict(status='PENDING'))
        with patch.object(a,'load_postterminal',side_effect=AssertionError('Gold opened')) as reader:
            with self.assertRaises(ValueError):a.run(self.root,100,self.out)
            reader.assert_not_called()

    def test_sealed_output_tampering_refused(self):
        put(self.report/'route_risk.json',{'altered':True})
        with self.assertRaises(ValueError):a.run(self.root,100,self.out)

    def test_existing_output_refused(self):
        out=self.out;out.mkdir(parents=True)
        with self.assertRaises(FileExistsError):a.run(self.root,100,out)

    def test_write_guard_keeps_sealed_report_immutable(self):
        with self.assertRaises(ValueError):a.run(self.root,100,self.report/'new_analysis')

    def test_interval_addendum_must_bind_original_plan(self):
        put(self.root/'audits/final_secondary_analysis_addendum_cp_taskrisk.json',dict(base_plan_sha256='0'*64,status='POST_FIRST100_DESCRIPTIVE_INTERVAL_ADDENDUM_NOT_PRIMARY_TEST_CHANGE'))
        with self.assertRaises(ValueError):a.run(self.root,100,self.out)

    def test_future_gold_guard_before_open(self):
        values=json.loads(self.old_allocation.read_text());values['records'].append(self.rows[100]);new_sha=put(self.old_allocation,values)
        old_freeze=self.old/'controller/report_freeze.json';freeze=json.loads(old_freeze.read_text());freeze['source_sha256'][str(self.old_allocation)]=new_sha;put(old_freeze,freeze)
        bound=json.loads((self.report/'input_sha256.json').read_text());bound[str(old_freeze)]=a.digest(old_freeze.read_bytes());put(self.report/'input_sha256.json',bound);self.seal()
        evidence=a.Evidence();scope=a.sealed_scope(self.root,100,evidence)
        original=evidence.json
        def guarded(path,expected=None):
            if Path(path).name=='private_gold.json':raise AssertionError('future Gold opened')
            return original(path,expected)
        with patch.object(evidence,'json',side_effect=guarded):
            with self.assertRaisesRegex(ValueError,'future'):a.load_postterminal(scope,evidence)


if __name__=='__main__':unittest.main()
