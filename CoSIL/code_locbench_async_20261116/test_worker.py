"""CPU-only synthetic tests of asynchronous finality, recovery and ordering."""
import copy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import worker as w


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.plan={'pilot':str(self.root/'pilot'),'batches':[]}
        for i,n in enumerate([100,100,100,100,60],1):
            work=self.root/f'batch{i:02d}';work.mkdir()
            self.plan['batches'].append({'index':i,'name':work.name,'work':str(work),'n':n})

    def tearDown(self):self.tmp.cleanup()

    def fixture_gate(self):
        spec=self.plan['batches'][0];work=Path(spec['work'])
        manifest={'n':1,'records':[{'instance_id':'fixture__repo-1'}]}
        counts={'selected':1,'terminal_arms':2,'terminal_pairs':1,'all_terminal':True}
        w.c.write(work/'runtime/runnable_manifest.json',manifest)
        w.c.write(work/'allocation.json',{'n':100});w.c.write(work/'controller/report_freeze.json',{})
        terminal={}
        for suffix in ['baseline/terminal.json','hybrid_safe/terminal.json','pair_terminal.json']:
            p=work/'paired_run/pairs/fixture__repo-1'/suffix;w.c.write(p,{})
            terminal[str(p.resolve())]=w.c.sha(p)
        owner=work/'service_queue/sessions/fixture/main/ownership.json'
        w.c.write(owner,{'identity':{'pid':1234}})
        value={'status':'GPU_BATCH_COMPLETE','batch':spec['name'],'n':100,'allocated':100,
            'runnable':1,'counts':counts,'inference_protocol_changed':False,
            'service_release':{'all_observed_service_processes_exited':True},
            'terminal_sha256':terminal,'manifest_sha256':w.c.sha(work/'runtime/runnable_manifest.json'),
            'allocation_sha256':w.c.sha(work/'allocation.json'),
            'report_freeze_sha256':w.c.sha(work/'controller/report_freeze.json')}
        w.c.write(work/'controller/gpu_completion.json',value)
        return spec,work,value,counts

    def test_gate_checks_all_terminals_before_gold_evaluator(self):
        spec,work,gate,counts=self.fixture_gate()
        with patch.object(w,'verify_execution'),patch.object(w.old_supervisor,'terminal_counts',return_value=counts),\
             patch.object(w.c,'same_process',return_value=False),patch.object(w.sq,'identity',return_value=None),\
             patch.object(w.report.original,'terminal_barrier',return_value=('PASS',)) as barrier:
            self.assertEqual(w.gpu_gate(self.root,spec)[0],gate);barrier.assert_called_once()
            gate['terminal_sha256'].pop(next(iter(gate['terminal_sha256'])))
            w.c.write(work/'controller/gpu_completion.json',gate)
            barrier.reset_mock()
            with self.assertRaisesRegex(ValueError,'omits or adds'):
                w.gpu_gate(self.root,spec)
            barrier.assert_not_called()

    def test_nonterminal_or_live_service_cannot_open_gold(self):
        for error in ['nonterminal','live','false_release']:
            spec,work,gate,counts=self.fixture_gate()
            if error=='nonterminal':counts=dict(counts,all_terminal=False)
            if error=='false_release':
                gate['service_release']['all_observed_service_processes_exited']=False
                w.c.write(work/'controller/gpu_completion.json',gate)
            with patch.object(w,'verify_execution'),patch.object(w.old_supervisor,'terminal_counts',return_value=counts),\
                 patch.object(w.c,'same_process',return_value=error=='live'),patch.object(w.sq,'identity',return_value=None),\
                 patch.object(w.report.original,'terminal_barrier') as barrier:
                with self.assertRaises(ValueError):w.gpu_gate(self.root,spec)
                barrier.assert_not_called()

    def run_process_fixture(self, *, complete=False, partial=False):
        spec,work,gate,counts=self.fixture_gate();prior=[Path(self.plan['pilot'])/'reports/final']
        dest=work/'reports/final';cumulative=self.root/'reports/cumulative200';calls=[]
        if complete:
            for d in [dest,cumulative]:w.c.write(d/'output_sha256.json',{'fixture':True})
        if partial:
            w.c.write(dest/'partial.json',{'keep':'old bytes'})
            w.c.write(cumulative/'partial.json',{'keep':'old cumulative'})
        def batch(path):
            calls.append('batch');w.c.write(dest/'output_sha256.json',{'fixture':True})
        def combine(directories,out):
            calls.append('combine');self.assertEqual(directories,prior+[dest])
            w.c.write(out/'output_sha256.json',{'fixture':True})
        with patch.object(w,'verify_execution'),patch.object(w,'gpu_gate',return_value=(gate,None)),\
             patch.object(w.report,'report_batch',side_effect=batch),patch.object(w.report,'report_gate'),\
             patch.object(w.report,'combine',side_effect=combine),patch.object(w,'cumulative_gate'):
            done=w.process_batch(self.root,self.plan,spec,prior)
        return spec,work,done,calls

    def test_complete_reports_are_verified_and_never_recomputed(self):
        _,work,done,calls=self.run_process_fixture(complete=True)
        self.assertFalse(calls);self.assertEqual(done['status'],'REPORT_COMPLETE')
        self.assertEqual(done['cumulative_allocated'],200)
        self.assertTrue((work/'completion.json').exists())
        self.assertFalse((self.root/'controller/status.json').exists())

    def test_partial_reports_are_preserved_before_cpu_only_recompute(self):
        _,work,done,calls=self.run_process_fixture(partial=True)
        self.assertEqual(calls,['batch','combine'])
        preserved=list((work/'reports').glob('final.preserved_interrupted_*'))
        kept=[d for d in preserved if d.is_dir()]
        self.assertEqual(len(kept),1)
        self.assertEqual(w.c.read(kept[0]/'partial.json'),{'keep':'old bytes'})
        self.assertTrue(done['models_called_by_reporter'] is False)

    def test_skipping_a_prefix_is_rejected_before_private_reads(self):
        with patch.object(w,'verify_execution') as verify:
            with self.assertRaisesRegex(ValueError,'skip or reorder'):
                w.process_batch(self.root,self.plan,self.plan['batches'][1],[])
            verify.assert_not_called()

    def test_sequential_worker_recovers_IO_without_model_calls(self):
        events=[];attempts={};first=self.plan['batches'][0]
        for s in self.plan['batches']:w.c.write(Path(s['work'])/'controller/gpu_completion.json',{})
        def process(root,plan,spec,completed):
            attempts[spec['index']]=attempts.get(spec['index'],0)+1
            if spec['index']==1 and attempts[1]==1:raise OSError('synthetic transient IO')
            events.append((spec['index'],len(completed)));return {'batch':spec['name']}
        with patch.object(w,'verify_execution'),patch.object(w.prepare,'validate_plan',return_value=self.plan),\
             patch.object(w,'process_batch',side_effect=process),patch.object(w.time,'sleep'):
            value=w.run(self.root,poll_seconds=2)
        self.assertEqual(events,[(i,i) for i in range(1,6)])
        self.assertEqual(attempts[1],2);self.assertEqual(value['allocated'],560)
        self.assertEqual(value['status'],w.REPORTS_COMPLETE)
        self.assertEqual(w.REPORTS_COMPLETE,'ALL_REPORTS_COMPLETE')
        self.assertTrue((self.root/'reports/async_completion.json').exists())

    def test_integrity_failure_stops_without_later_batch_or_retry(self):
        for s in self.plan['batches']:w.c.write(Path(s['work'])/'controller/gpu_completion.json',{})
        with patch.object(w,'verify_execution'),patch.object(w.prepare,'validate_plan',return_value=self.plan),\
             patch.object(w,'process_batch',side_effect=ValueError('terminal/source drift')) as process:
            with self.assertRaises(ValueError):w.run(self.root,poll_seconds=2)
            self.assertEqual(process.call_count,1)
        self.assertEqual(w.c.read(self.root/'reports/async_status.json')['phase'],'FATAL_INTEGRITY_ERROR')
        self.assertFalse((self.root/'reports/async_completion.json').exists())

    def test_IO_retries_are_bounded_and_never_skip_to_later_batch(self):
        for s in self.plan['batches']:w.c.write(Path(s['work'])/'controller/gpu_completion.json',{})
        with patch.object(w,'verify_execution'),patch.object(w.prepare,'validate_plan',return_value=self.plan),\
             patch.object(w.time,'sleep'),\
             patch.object(w,'process_batch',side_effect=OSError('synthetic disk error')) as process:
            with self.assertRaises(OSError):w.run(self.root,poll_seconds=2)
            self.assertEqual(process.call_count,w.CPU_ATTEMPTS)
            self.assertTrue(all(call.args[2]['index']==1 for call in process.call_args_list))
        status=w.c.read(self.root/'reports/async_status.json')
        self.assertEqual(status['phase'],'REPORT_IO_ERROR')
        self.assertEqual(status['cpu_attempt'],w.CPU_ATTEMPTS)

    def test_missing_execution_authority_is_an_integrity_failure(self):
        with self.assertRaisesRegex(ValueError,'Missing async execution authority'):
            w.verify_execution(self.root)

    def test_source_freeze_drift_refused_before_plan_or_score(self):
        source=self.root/'frozen.py';source.write_text('original')
        old=self.root/'controller/execution_freeze.json';w.c.write(old,{'files_sha256':{str(source):w.c.sha(source)}})
        w.c.write(self.root/'plan.json',{})
        pub=self.root/'audits/async_execution_publication/publication_receipt.json';w.c.write(pub,{'commit':'fixture'})
        files={str(source):w.c.sha(source),str(Path(w.__file__).resolve()):w.c.sha(w.__file__),
               str(Path(w.report.__file__).resolve()):w.c.sha(w.report.__file__)}
        freeze={'status':'ASYNC_EXECUTION_FROZEN','commit':'fixture','plan_sha256':w.c.sha(self.root/'plan.json'),
            'old_execution_freeze_sha256':w.c.sha(old),'files_sha256':files,
            'async_publication_sha256':w.c.sha(pub),'pilot_preserved_sha256':{}}
        w.c.write(self.root/'controller/async_execution_freeze.json',freeze)
        with patch.object(w.prepare,'validate_plan'):
            w.verify_execution(self.root)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError,'Frozen async source'):
                w.verify_execution(self.root)


if __name__=='__main__':unittest.main()
