"""Synthetic artifact/process tests: no model, GPU, network or real signals."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from . import common as c, freeze, reporter, supervise


def fixture(root, *, group=True):
    row = {'instance_id': 'synthetic__repo-1', 'base_commit': 'a' * 40, 'rank': 1}
    c.write(root / 'manifest.json', {'n': 1, 'records': [row]})
    c.write(root / 'run/freeze.json', {'protocol_sha256': 'p' * 64})
    c.write(root / 'run/progress.json', {'phase': 'running'})
    c.write(root / 'controller/checkpoints/1.json',
            {'status': 'PREFIX_ALL_ARMS_TERMINAL', 'n': 1, 'protocol_sha256': 'p' * 64})
    arms = {}
    for arm in c.ARMS:
        term = {'instance_id': row['instance_id'], 'base_commit': row['base_commit'],
                'protocol_sha256': 'p' * 64, 'arm': arm, 'status': 'complete'}
        c.write(root / 'run/pairs' / row['instance_id'] / arm / 'terminal.json', term)
        arms[arm] = term
    if group:
        c.write(root / 'run/pairs' / row['instance_id'] / 'group_terminal.json',
                {'instance_id': row['instance_id'], 'base_commit': row['base_commit'],
                 'protocol_sha256': 'p' * 64, 'arms': arms})
    return row


def report_output(root, n, out):
    out.mkdir(parents=True)
    c.write(out / 'summary.json', {'status': 'FINAL_ABLATION_CHECKPOINT', 'allocated': n,
            'models_called_by_evaluator': 0, 'terminal_barrier_before_gold': True})
    c.write(out / 'input_sha256.json', {str(root / 'manifest.json'): c.sha(root / 'manifest.json')})
    c.write(out / 'output_sha256.json', {p.name: c.sha(p) for p in out.iterdir() if p.is_file()})


def service_session(root, name, roles, *, negative=False):
    from .services import role_cuda_observations
    session=root/'controller/service_queue/sessions'/name;items=[];records=[]
    for role,pid in roles:
        directory=session/role;receipt={'identity':{'pid':pid,'start_ticks':pid+100,'uid':os.getuid()}}
        c.write(directory/'ownership.json',receipt);items.append((role,None,receipt,directory))
        if not negative:
            records.append({'claimed_owned':True,'owned_role':role,'expected_gpu':True,
                'gpu_index':2 if role=='main' else 1,'pid':pid+10000,
                'leader_pid':pid,'leader_start_ticks':pid+100,
                'current_basic':{'pid':pid+10000,'start_ticks':pid+200}})
    records += [{'claimed_owned':False,'gpu_index':0,'pid':900001},
                {'claimed_owned':False,'gpu_index':1,'pid':900002}]
    snapshot={'status':'OBSERVED','errors':[],'gpu_inventory':{'g0':0,'g1':1,'g2':2,'g3':3},
              'records':records,'observation_phase':'after_shutdown' if negative else 'before_controller'}
    snapshot['role_observations']=role_cuda_observations(snapshot,items)
    c.write(session/('cuda_ownership_negative.json' if negative else 'cuda_ownership.json'),snapshot)
    return session


class ReporterIntegrity(unittest.TestCase):
    def test_three_terminals_without_group_do_not_score(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); fixture(root, group=False); score = Mock()
            self.assertIsNone(reporter.checkpoint(root, 1, report_run=score))
            score.assert_not_called()

    def test_missing_condition_does_not_close_group(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); row = fixture(root)
            (root/'run/pairs'/row['instance_id']/c.ARMS[0]/'terminal.json').unlink()
            self.assertFalse(reporter.prefix_closed(root, 1))

    def test_group_drift_is_fatal_before_score(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); row = fixture(root)
            path = root/'run/pairs'/row['instance_id']/'group_terminal.json'
            value = c.read(path); value['arms'][c.ARMS[0]]['status'] = 'interrupted'; c.write(path, value)
            score = Mock()
            with patch.object(c, 'CHECKPOINTS', (1,)), patch.object(c, 'require_execution_freeze'):
                with self.assertRaises(ValueError):
                    reporter.run(root, report_run=score, sleeper=lambda _: None)
            score.assert_not_called()
            self.assertEqual(c.read(root/'controller/report_fatal.json')['status'], 'REPORT_FATAL')

    def test_complete_report_recovery_checks_output_and_input_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); fixture(root); out = root/'reports/cumulative1'
            report_output(root, 1, out)
            score = Mock()
            self.assertEqual(reporter.checkpoint(root, 1, report_run=score)['allocated'], 1)
            score.assert_not_called()
            (out/'summary.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'SHA'):
                reporter.checkpoint(root, 1, report_run=score)

    def test_report_IO_retries_have_lifetime_cap_and_keep_all_partial_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); fixture(root); calls = []
            def bad(root, n, out):
                calls.append(out); out.mkdir(); (out/'partial.txt').write_text('keep')
                raise OSError('synthetic temporary disk failure')
            with patch.object(c, 'require_execution_freeze'):
                with self.assertRaisesRegex(RuntimeError, 'I/O allowance'):
                    reporter.checkpoint(root, 1, report_run=bad, sleeper=lambda _: None)
                with self.assertRaisesRegex(RuntimeError, 'lifetime'):
                    reporter.checkpoint(root, 1, report_run=bad, sleeper=lambda _: None)
            self.assertEqual(len(calls), 3)
            self.assertTrue(all((p/'partial.txt').read_text() == 'keep' for p in calls))


class FakeProcess:
    def __init__(self, states, pid=987654, callback=None):
        self.states = list(states); self.pid = pid; self.callback = callback
    def poll(self):
        value = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if value is not None and self.callback:
            callback, self.callback = self.callback, None; callback()
        return value


class SupervisorFlow(unittest.TestCase):
    def test_real_CUDA_identity_must_exit_foreign_record_is_never_claimed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=root/'controller/service_queue/sessions/synthetic'
            for role,pid in [('main',10),('judge',11)]:
                c.write(session/role/'ownership.json',{'identity':{'pid':pid,'start_ticks':1}})
            c.write(session/'cuda_ownership.json',{'records':[
                {'claimed_owned':True,'owned_role':'main','expected_gpu':True,'leader_pid':10,'leader_start_ticks':1,'current_basic':{'pid':12,'start_ticks':2}},
                {'claimed_owned':True,'owned_role':'judge','expected_gpu':True,'leader_pid':11,'leader_start_ticks':1,'current_basic':{'pid':13,'start_ticks':3}},
                {'claimed_owned':False,'pid':999999}]})
            seen=[]
            def observe(saved):
                seen.append(saved['pid']);return {'leader_exited':saved['pid']!=12}
            with patch('code_locbench_ablation_20261117_v2.services.leader_exit_observation',side_effect=observe):
                self.assertFalse(supervise.service_release(root)['all_owned_services_and_CUDA_children_exited'])
            self.assertNotIn(999999,seen)
            with patch('code_locbench_ablation_20261117_v2.services.leader_exit_observation',return_value={'leader_exited':True}):
                self.assertTrue(supervise.service_release(root)['all_owned_services_and_CUDA_children_exited'])

    def test_service_leader_exit_without_CUDA_witness_does_not_certify_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);c.write(root/'controller/service_queue/sessions/s/main/ownership.json',
                                    {'identity':{'pid':10,'start_ticks':1}})
            with patch('code_locbench_ablation_20261117_v2.services.leader_exit_observation',return_value={'leader_exited':True}):
                self.assertFalse(supervise.service_release(root)['all_owned_services_and_CUDA_children_exited'])

    def test_precontroller_main_failure_then_healthy_session_can_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fixture(root);(root/'controller/checkpoints/1.json').unlink()
            launches=[];reporter_process=FakeProcess([None])
            def finish():
                c.write(root/'controller/checkpoints/1.json',{'status':'PREFIX_ALL_ARMS_TERMINAL','n':1,'protocol_sha256':'p'*64})
                output=root/'reports/cumulative1';report_output(root,1,output)
                c.write(root/'reports/completion.json',{'status':reporter.COMPLETE,'allocated':1,
                    'reports':[reporter.validate_report(output,1)]})
            def starter(command,**kwargs):
                role='reporter' if command[3].endswith('reporter') else 'services';launches.append(role)
                if role=='reporter':return reporter_process,{'identity':{'pid':101,'start_ticks':1}}
                number=launches.count('services')
                if number==1:
                    service_session(root,'failed_main',[('main',201)],negative=True)
                    return FakeProcess([1]),{'identity':{'pid':202,'start_ticks':1}}
                service_session(root,'healthy',[('main',301),('judge',302)])
                return FakeProcess([0],callback=finish),{'identity':{'pid':303,'start_ticks':1}}
            seen=[]
            def observe(saved):seen.append(saved['pid']);return {'leader_exited':True}
            with patch.object(c,'CHECKPOINTS',(1,)),patch('code_locbench_ablation_20261117_v2.services.leader_exit_observation',side_effect=observe),patch.object(supervise.recovery,'stop_saved') as stop:
                value=supervise.run(root,starter=starter,guard=lambda _: {},sleeper=lambda _:None)
            self.assertEqual(value['phase'],'COMPLETE_REPORT_READY')
            self.assertEqual(launches,['reporter','services','services'])
            self.assertNotIn(900001,seen);self.assertNotIn(900002,seen);stop.assert_not_called()
            requirements=value['service_release']['session_requirements']
            failed=next(r for r in requirements if r['session'].endswith('failed_main'))
            self.assertEqual(failed['started_roles'],['main'])
            self.assertEqual(failed['post_shutdown_no_CUDA_observed_roles'],['main'])

    def test_later_negative_snapshot_never_overrides_live_historical_CUDA_pid(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);service_session(root,'s',[('main',201)])
            service_session(root,'s',[('main',201)],negative=True)
            with patch('code_locbench_ablation_20261117_v2.services.leader_exit_observation',side_effect=lambda saved:{'leader_exited':saved['pid']!=10201}):
                self.assertFalse(supervise.service_release(root)['all_owned_services_and_CUDA_children_exited'])

    def test_pre_shutdown_negative_snapshot_alone_is_not_release_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=service_session(root,'s',[('main',201)],negative=True)
            path=session/'cuda_ownership_negative.json';value=c.read(path);value['observation_phase']='before_shutdown';c.write(path,value)
            with patch('code_locbench_ablation_20261117_v2.services.leader_exit_observation',return_value={'leader_exited':True}):
                self.assertFalse(supervise.service_release(root)['all_owned_services_and_CUDA_children_exited'])

    def test_GPU_starts_without_waiting_for_CPU_report_and_finishes_only_after_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); fixture(root)
            # The real supervisor sees a closed prefix only after the fake queue finishes.
            (root/'controller/checkpoints/1.json').unlink()
            launches, ticks, releases = [], [], []
            def finish_queue():
                c.write(root/'controller/checkpoints/1.json',
                    {'status':'PREFIX_ALL_ARMS_TERMINAL','n':1,'protocol_sha256':'p'*64})
            queue = FakeProcess([None, 0], callback=finish_queue)
            cpu = FakeProcess([None])
            def starter(command, **kwargs):
                role = 'reporter' if command[3].endswith('reporter') else 'services'
                launches.append(role)
                if role == 'reporter': self.assertEqual(kwargs['env']['CUDA_VISIBLE_DEVICES'], '')
                return (cpu if role == 'reporter' else queue), {'identity': {'pid': 987654, 'start_ticks': 1}}
            def sleep(_):
                ticks.append(1)
                if len(ticks) == 2:
                    out=root/'reports/cumulative1'; report_output(root,1,out)
                    value=reporter.validate_report(out,1)
                    c.write(root/'reports/completion.json',{'status':reporter.COMPLETE,'allocated':1,'reports':[value]})
            def release(_):
                releases.append(1)
                return {'all_owned_services_and_CUDA_children_exited': len(releases)>1}
            with patch.object(c,'CHECKPOINTS',(1,)), patch.object(supervise.recovery,'stop_saved') as signal:
                result=supervise.run(root,starter=starter,release=release,guard=lambda _: {},sleeper=sleep)
            self.assertEqual(launches,['reporter','services'])
            self.assertGreaterEqual(len(releases),2)
            self.assertEqual(result['phase'],'COMPLETE_REPORT_READY')
            signal.assert_not_called()

    def test_source_guard_failure_prevents_any_service_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fixture(root);starter=Mock()
            def bad(_):raise ValueError('source changed')
            with self.assertRaises(ValueError):
                supervise.run(root,starter=starter,guard=bad)
            starter.assert_not_called()

    def test_source_drift_sets_stop_marker_and_never_relaunches_started_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fixture(root);guard_calls=[];launches=[]
            (root/'controller/checkpoints/1.json').unlink()
            def guard(_):
                guard_calls.append(1)
                if len(guard_calls)>1:raise ValueError('new source drift')
            cpu=FakeProcess([None]);queue=FakeProcess([0])
            def starter(command,**kwargs):
                role='reporter' if command[3].endswith('reporter') else 'services';launches.append(role)
                return (cpu if role=='reporter' else queue),{'identity':{'pid':987654,'start_ticks':1}}
            with patch.object(supervise.recovery,'stop_saved',return_value={'signal_sent':False}):
                with self.assertRaisesRegex(RuntimeError,'source drift'):
                    supervise.run(root,starter=starter,guard=guard,
                        release=lambda _:{'all_owned_services_and_CUDA_children_exited':True},sleeper=lambda _:None)
            self.assertTrue((root/'controller/stop_dispatch.json').is_file())
            self.assertEqual(launches,['reporter','services'])

    def test_started_semantic_arm_is_never_redispatched(self):
        from .controller import Controller
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);marker=root/'started.json';marker.write_text('original')
            obj=Controller.__new__(Controller);obj.verify_group=Mock();obj.arm_state=Mock(return_value={'status':'interrupted'});obj.backend=Mock()
            obj.execute_arm({'instance_id':'synthetic__case-1'},c.ARMS[0],{})
            obj.backend.command.assert_not_called();self.assertEqual(marker.read_text(),'original')


class CumulativeRestartBudget(unittest.TestCase):
    def test_SIGTERM_is_translated_to_cleanup_path_instead_of_abrupt_exit(self):
        handlers=[]
        def install(sig, handler):
            handlers.append((sig,handler)); return 'previous-handler'
        def interrupted_run(*args, **kwargs):
            handlers[0][1](supervise.signal.SIGTERM,None)
        with patch.object(supervise.signal,'signal',side_effect=install), \
                patch.object(supervise,'run',side_effect=interrupted_run), \
                patch('sys.argv',['supervise','--root','/synthetic/root']):
            with self.assertRaises(SystemExit) as error:supervise.main()
        self.assertEqual(error.exception.code,143)
        self.assertEqual(handlers[-1],(supervise.signal.SIGTERM,'previous-handler'))

    def test_controlled_stop_cleans_both_saved_owned_children(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fixture(root)
            (root/'controller/checkpoints/1.json').unlink()
            queue=FakeProcess([None]);cpu=FakeProcess([None])
            def starter(command,**kwargs):
                return (cpu if command[3].endswith('reporter') else queue),{
                    'identity':{'pid':987654,'start_ticks':1}}
            def stop(_):raise SystemExit(143)
            with patch.object(c,'CHECKPOINTS',(1,)), \
                    patch.object(supervise.recovery,'stop_saved',return_value={'leader_exited':True}) as cleanup:
                with self.assertRaises(SystemExit):
                    supervise.run(root,starter=starter,release=lambda _: {
                        'all_owned_services_and_CUDA_children_exited':True},
                        guard=lambda _: {},sleeper=stop)
            self.assertEqual(cleanup.call_count,2)
            d=c.read(root/'controller/status.json')
            self.assertEqual(set(d['owned_shutdown']),{'services','reporter'})
            self.assertFalse(d['completion_claimed'])

    def test_prior_engineering_session_counts_toward_same_three_launch_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            c.write(root/'protocol.json',{'engineering_amendment':{'prior_service_sessions':[
                {'session_directory':'/immutable/failed_v1_session'}]}})
            self.assertEqual(supervise.cumulative_session_count(root),1)
            for n in range(2): (root/'controller/service_queue/sessions'/str(n)).mkdir(parents=True)
            self.assertEqual(supervise.cumulative_session_count(root),3)
            c.write(root/'protocol.json',{'engineering_amendment':{}})
            with self.assertRaisesRegex(ValueError,'reset'):supervise.cumulative_session_count(root)


class FreezeEvidence(unittest.TestCase):
    def test_valid_source_and_three_input_bindings_freeze_then_controller_prepare(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'experiment';parent=Path(folder)/'history';root.mkdir()
            new=root/'synthetic_source.py';new.write_text('new source')
            old=parent/'source.py';old.parent.mkdir();old.write_text('old source')
            protocol={'experiment_id':'locbench_qwen3_sfpruner_ablation_20261117',
                'root':str(root),'parent':str(parent),'n':560,'allocated':560,'arms':list(c.ARMS)}
            c.write(root/'protocol.json',protocol)
            c.write(root/'manifest.json',{'n':560,'records':[{'rank':i} for i in range(560)],
                    'availability':{'ready':557,'source_preparation_blocked':2,'upstream_file_stage_unavailable':1}})
            c.write(root/'authority.json',{'status':'FROZEN_BEFORE_NEW_MODEL_CALLS','models_called':False,
                    'manifest_sha256':c.sha(root/'manifest.json'),'protocol_sha256':c.sha(root/'protocol.json'),
                    'files_sha256':{str(root/'manifest.json'):c.sha(root/'manifest.json')}})
            c.write(parent/'continuation460/controller/async_execution_freeze.json',{'files_sha256':{str(old):c.sha(old)}})
            sources={str(new):c.sha(new)};pub=root/'publication.json';test=root/'tests.json';gate=root/'gate.json'
            c.write(pub,{'commit':'a'*40,'source_sha256':{**sources,str(old):c.sha(old)}})
            c.write(test,{'status':'ALL_TESTS_PASS','tests':1,'source_sha256':sources})
            c.write(gate,{'status':'INDEPENDENT_CPU_PASS','source_sha256':sources,
                **{name+'_sha256':c.sha(root/(name+'.json')) for name in ['protocol','manifest','authority']}})
            with (patch.object(c,'package_sources',return_value=sources),
                  patch.object(freeze,'PROTOCOL_SHA',c.sha(root/'protocol.json')),
                  patch('code_locbench_ablation_20261117_v2.controller.Controller') as controller):
                value=freeze.freeze(root,pub,test,gate)
                self.assertEqual(value['status'],'EXECUTION_FROZEN_READY')
                controller.return_value.prepare.assert_called_once_with()
                gate.write_text('{}')
                with self.assertRaises(ValueError):freeze.freeze(root,pub,test,gate)

    def test_audit_without_complete_source_coverage_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audit.json';c.write(path,{'status':'CPU_TESTS_PASS','source_sha256':{}})
            with self.assertRaisesRegex(ValueError,'omits'):
                freeze.check_audit(path,{'source.py':'a'*64})

    def test_independent_gate_must_bind_all_three_prepared_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audit.json';c.write(path,{'status':'INDEPENDENT_CPU_PASS','source_sha256':{'source.py':'a'*64}})
            with self.assertRaisesRegex(ValueError,'does not bind'):
                freeze.check_audit(path,{'source.py':'a'*64},{'/tmp/protocol.json':'b'*64})

    def test_failed_or_pending_receipts_are_not_passes(self):
        for status in ['FAILED_PASS','PASS_PENDING','CPU_BLOCKED_PASS','BYPASS_INVALID','NOT_PASS']:
            self.assertFalse(freeze.successful({'status':status}))


if __name__=='__main__':
    unittest.main()
