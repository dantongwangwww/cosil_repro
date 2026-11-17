"""Synthetic counterexamples only; no benchmark Gold or model access."""
from pathlib import Path
import ast
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

import audit_prefix as a
import metric_reference as m


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def history_fixture(self,future=False):
        rows=[];bound={}
        for i in range(2):
            work=self.root/f'batch{i}'
            row=dict(instance_id=f'i{i}',repo='toy/repo',base_commit='base',original_work=str(work))
            rows.append(row);selected=[row]
            if future and i==1:selected.append(dict(row,instance_id='future'))
            paths={k:work/v for k,v in {'allocation':'allocation.json','manifest':'manifest.json','allocation_status':'status.json','gold':'private_gold.json','inventory':'private_inventory.json'}.items()}
            hashes={str(paths['allocation']):put(paths['allocation'],{'records':selected}),
                    str(paths['manifest']):put(paths['manifest'],{'records':[]}),
                    str(paths['allocation_status']):put(paths['allocation_status'],{'status':'PREPARATION_FINAL'})}
            for key in ('gold','inventory'):
                hashes[str(paths[key])]=put(paths[key],{r['instance_id']:{'synthetic':True} for r in selected})
            freeze={**{k:str(v) for k,v in paths.items()},'source_sha256':hashes}
            path=work/'controller/report_freeze.json';bound[str(path)]=put(path,freeze)
        return rows,bound

    def test_multiple_old_batches_load_exact_selected_scope(self):
        rows,bound=self.history_fixture();meta,gold,inv=a.histories(rows,a.Evidence(),bound)
        self.assertEqual(set(gold),{'i0','i1'});self.assertEqual(set(inv),set(gold));self.assertEqual(len(meta),2)

    def test_later_old_batch_future_guard_before_any_private_read(self):
        rows,bound=self.history_fixture(future=True);ev=a.Evidence();original=ev.read
        def guarded(path,expected=None):
            if Path(path).name.startswith('private_'):raise AssertionError('Private file opened before all allocations validated')
            return original(path,expected)
        with patch.object(ev,'read',side_effect=guarded):
            with self.assertRaisesRegex(ValueError,'future'):a.histories(rows,ev,bound)

    def test_pending_report_rejected_before_any_private_or_metric_file(self):
        put(self.root/'reports/checkpoints/200.json',{'status':'PENDING','allocated':200})
        ev=a.Evidence()
        with self.assertRaisesRegex(ValueError,'REPORT_COMPLETE'):a.public_gate(self.root,200,ev)
        self.assertEqual(list(ev.hashes),[str(self.root/'reports/checkpoints/200.json')])

    def test_full_authority_option_forbidden_before_final560(self):
        with patch.object(a,'public_gate',side_effect=AssertionError('must reject before any roster/read')):
            with self.assertRaisesRegex(ValueError,'final560'):a.audit(self.root,200,self.root/'audits/out.json',final_authority_rehash=True)

    def test_output_outside_audits_refused(self):
        with patch.object(a,'public_gate',side_effect=AssertionError('must reject before any read')):
            with self.assertRaisesRegex(ValueError,'audits'):a.audit(self.root,100,self.root/'reports/out.json')


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.arm='ablation_no_neighbors'

    def rpc(self,role,**extra):
        value=dict(request_id='request',operation='score',experimental_arm=self.arm,internal_arm='hybrid_safe',input_sha256='input')
        value.update(extra);put(self.root/'judge_rpc'/f'request_{role}.json',value)

    def test_explicit_preparation_block_zero_and_no_call(self):
        result=a.account(self.root,{},self.arm,a.Evidence(),no_dispatch=True)
        self.assertEqual(result['physical_main_tokens'],0);self.assertEqual(result['judge_rpc_attempts'],0)
        self.assertEqual(result['new_file_agent_http_calls'],0)

    def test_preparation_block_cannot_hide_http_attempt(self):
        put(self.root/'calls/0001_pruner/attempt_0_start.json',{'stage':'pruner','request_sha256':'request'})
        with self.assertRaisesRegex(ValueError,'no-call'):a.account(self.root,{},self.arm,a.Evidence(),no_dispatch=True)

    def test_no_ledger_or_result_is_unknown_not_zero(self):
        result=a.account(self.root,{},self.arm,a.Evidence())
        self.assertIsNone(result['physical_main_tokens']);self.assertIsNone(result['unknown_usage_attempts'])
        self.assertIsNone(result['new_file_agent_http_calls'])

    def test_http_start_without_receipt_is_unknown(self):
        put(self.root/'calls/0001_pruner/attempt_0_start.json',{'stage':'pruner','request_sha256':'request'})
        result=a.account(self.root,{},self.arm,a.Evidence())
        self.assertEqual(result['http_attempts_recorded'],1);self.assertEqual(result['unknown_usage_attempts'],1)
        self.assertIsNone(result['physical_main_tokens']);self.assertEqual(result['known_prompt_tokens'],0)

    def test_real_rpc_error_is_unknown_forward_and_usage(self):
        self.rpc('start');self.rpc('receipt',status='error',forward_status='unknown',usage_status='unknown')
        result=a.account(self.root,{},self.arm,a.Evidence())
        self.assertEqual(result['judge_rpc_error_attempts'],1);self.assertEqual(result['judge_forward_known_sum'],0)
        self.assertEqual(result['judge_forward_unknown_attempts'],1);self.assertEqual(result['judge_usage_unknown_attempts'],1)
        self.assertIsNone(result['local_scoring_forwards_recorded']);self.assertIsNone(result['local_input_tokens'])

    def test_unmatched_success_receipt_keeps_known_lower_bound_but_total_unknown(self):
        self.rpc('receipt',status='success',forward_status='confirmed_score_success',usage_status='known',input_tokens=9,generated_output_tokens=0,adapter_active=True)
        result=a.account(self.root,{},self.arm,a.Evidence())
        self.assertEqual(result['judge_forward_known_sum'],1);self.assertEqual(result['judge_input_tokens_known_sum'],9)
        self.assertEqual(result['judge_rpc_unclosed_attempts'],1);self.assertIsNone(result['local_scoring_forwards_recorded'])

    def test_nonbenchmark_probe_is_not_a_benchmark_score(self):
        self.rpc('start',operation='probe');self.rpc('receipt',operation='probe',status='success')
        result=a.account(self.root,{},self.arm,a.Evidence())
        self.assertEqual(result['judge_rpc_attempts'],0);self.assertEqual(result['local_scoring_forwards_recorded'],0)

    def test_new_file_model_call_is_refused(self):
        put(self.root/'calls/file/attempt_0_start.json',{'stage':'file_0','request_sha256':'request'})
        with self.assertRaisesRegex(ValueError,'file-stage'):a.account(self.root,{},self.arm,a.Evidence())

    def test_dependency_no_call_main_zero_but_unknown_shared_usage(self):
        result=a.account(self.root,{},'hybrid_safe',a.Evidence(),explicit_no_call=True)
        self.assertEqual(result['physical_main_tokens'],0);self.assertIsNone(result['file_main_usage'])

    def test_shared_usage_unknown_does_not_become_normalized_zero(self):
        resource=a.account(self.root,{},'baseline',a.Evidence(),explicit_no_call=True)
        usage={arm:[dict(resource)] for arm in a.ARMS};value=a.resources(usage)
        self.assertIsNone(value['ablation_no_defer']['shared_file_stage_tokens_known'])
        self.assertIsNone(value['ablation_no_defer']['main_tokens_including_shared_file_stage'])

    def test_preparation_status_is_separate_from_model_attempt_failure(self):
        row=dict(instance_id='i',repo='toy/repo',base_commit='base')
        status,result,used,no_call=a.raw_arm(self.root,row,self.arm,a.Evidence(),blocked=True)
        self.assertEqual(status,'PREPARATION_BLOCKED');self.assertEqual(result,{});self.assertFalse(used);self.assertTrue(no_call)

    def test_invalid_failed_result_retains_artifact_failure_status(self):
        row=dict(instance_id='i',repo='toy/repo',base_commit='base');path=self.root/'result.json';path.write_bytes(b'broken JSON')
        put(self.root/'terminal.json',dict(row,arm=self.arm,status='worker_failed',result_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        status,result,used,_=a.raw_arm(self.root,row,self.arm,a.Evidence())
        self.assertEqual(status,'ARTIFACT_INVALID');self.assertFalse(used);self.assertEqual(result,{})


class MetricTests(unittest.TestCase):
    def test_all_pure_metric_algorithms_match_original_first100_ast(self):
        old=Path(__file__).resolve().parents[1]/'checkpoint100/independent_check.py'
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),a.BASELINE_HELPER_SHA)
        original={x.name:ast.dump(x,include_attributes=False) for x in ast.parse(old.read_text()).body if isinstance(x,ast.FunctionDef)}
        current={x.name:ast.dump(x,include_attributes=False) for x in ast.parse(Path(m.__file__).read_text()).body if isinstance(x,ast.FunctionDef)}
        for name,value in current.items():self.assertEqual(value,original[name],name)

    def test_failed_empty_prediction_keeps_scorable_denominator(self):
        failed=m.score([],{'m.py::f'});summary=m.aggregate([failed],20261110,40)
        self.assertEqual(summary['n'],1);self.assertEqual(summary['hit5_numerator'],0)
        self.assertEqual(summary['precision5'],0);self.assertEqual(summary['recall5'],0)

    def test_duplicates_and_invalid_slots_not_compressed(self):
        ranked=m.slots([{'path':'m.py','qualified_name':'f'},{'path':'m.py','qualified_name':'f'},{'path':'missing.py','qualified_name':'f'}],{'m.py::f'},True)
        self.assertEqual(ranked,['m.py::f','m.py::f',None]);self.assertEqual(m.score(ranked,{'m.py::f'})['precision5'],.2)


if __name__=='__main__':unittest.main()
