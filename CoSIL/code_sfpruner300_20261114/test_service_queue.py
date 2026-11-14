"""No GPU/model services: deterministic resource gate and ownership tests."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import service_queue as q


def row(index,*,process=False,free=24106,used=470,util=0):
    return {'index':index,'uuid':'gpu-'+str(index),'free_mib':free,
            'used_mib':used,'total_mib':24576,'utilization':util,
            'has_compute_process':process}


class GateTests(unittest.TestCase):
    def test_zero_utilization_does_not_make_another_users_process_idle(self):
        occupied=[row(0,process=True,free=13600,used=10976),
                  row(1,process=True,free=8000,used=16576),
                  row(2,process=True,free=8700,used=15876),row(3,process=True,free=8700,used=15876)]
        self.assertEqual(q.eligible(occupied),())
        gate=q.IdleGate()
        self.assertFalse(gate.observe(occupied,0)['ready'])
        self.assertFalse(gate.observe(occupied,3600)['ready'])

    def test_same_two_cards_must_remain_idle_for_full_90_seconds(self):
        cards=[row(2,used=0,free=24576),row(3,used=0,free=24576)]
        gate=q.IdleGate()
        self.assertFalse(gate.observe(cards,10)['ready'])
        self.assertFalse(gate.observe(cards,99.99)['ready'])
        self.assertTrue(gate.observe(cards,100)['ready'])
        self.assertFalse(gate.observe([row(2,process=True),cards[1]],101)['ready'])
        self.assertFalse(gate.observe(cards,190)['ready'])
        self.assertTrue(gate.observe(cards,280)['ready'])

    def test_chosen_card_change_resets_timer_and_prelaunch_rechecks(self):
        gate=q.IdleGate();cards=[row(2,used=0),row(3,used=0)]
        gate.observe(cards,0)
        changed=[row(1,used=0),row(2,used=0)]
        self.assertFalse(gate.observe(changed,90)['ready'])
        q.final_gpu_check(changed,(1,2))
        for broken in ([row(1,used=257),row(2,used=0)],
                       [row(1,used=0,process=True),row(2,used=0)],
                       [row(1,used=0,free=22000),row(2,used=0)]):
            with self.assertRaises(RuntimeError):q.final_gpu_check(broken,(1,2))

    def test_original_vllm_command_profile_is_exactly_preserved(self):
        from code_rebench_qwen import deploy as original
        expected=original.command()
        expected[0]=sys.executable
        expected[expected.index('--gpu-memory-utilization')+1]='0.59'
        expected[expected.index('--max-num-seqs')+1]='1'
        self.assertEqual(q.main_command(original.C.MODEL_DIR),expected)
        command=q.main_command('/model')
        overrides=json.loads(command[command.index('--hf-overrides')+1])
        self.assertEqual(overrides,original.HF_OVERRIDES)

    def test_inventory_uses_measured_free_memory_and_any_compute_pid(self):
        with patch.object(q.subprocess,'check_output',side_effect=[
                '2, gpu-2, 24576, 0, 24106, 0\n3, gpu-3, 24576, 0, 24106, 0\n',
                'gpu-3, 1234\n']):
            inventory=q.gpu_inventory()
        self.assertEqual(inventory[0]['free_mib'],24106)
        self.assertFalse(inventory[0]['has_compute_process'])
        self.assertTrue(inventory[1]['has_compute_process'])
        self.assertEqual(q.eligible(inventory),(2,))


class OwnershipTests(unittest.TestCase):
    def owner(self):
        command=[sys.executable,'-m','fake_service']
        saved={'pid':1234,'uid':q.os.getuid(),'state':'S','pgid':1234,'sid':1234,
               'start_ticks':99,'cmdline_sha256':'x','argv':command,'cwd':str(q.c.ROOT)}
        return {'identity':saved,'command':command,'cwd':str(q.c.ROOT)}

    def test_unknown_pid_reuse_argv_cwd_and_uid_never_signalled(self):
        receipt=self.owner();signals=[];saved=receipt['identity']
        variations=[None,{**saved,'start_ticks':100},{**saved,'uid':saved['uid']+1},
                    {**saved,'argv':['foreign']},{**saved,'cwd':'/other'},{**saved,'pgid':111}]
        for observed in variations:
            result=q.stop_owned(receipt,observe=lambda pid:observed,send=lambda *args:signals.append(args),wait_seconds=0)
            self.assertFalse(result['signal_sent'])
        self.assertEqual(signals,[])

    def test_only_witnessed_self_owned_independent_session_gets_sigterm(self):
        receipt=self.owner();observations=iter([receipt['identity'],None]);signals=[]
        result=q.stop_owned(receipt,observe=lambda pid:next(observations),
                            send=lambda *args:signals.append(args),sleeper=lambda _:None)
        self.assertEqual(signals,[(1234,q.c.signal.SIGTERM)])
        self.assertTrue(result['leader_exited'])
        self.assertFalse(result['forced_kill'])

    def test_natural_exit_between_ownership_check_and_signal_is_not_an_error(self):
        receipt=self.owner()
        def vanished(*args):raise ProcessLookupError('already exited')
        result=q.stop_owned(receipt,observe=lambda pid:receipt['identity'],send=vanished)
        self.assertTrue(result['leader_exited'])
        self.assertFalse(result['signal_sent'])


class QueueTests(unittest.TestCase):
    def make(self,root):
        return q.Queue(root/'not-ready/manifest.json',root/'run',root/'queue',
                       root/'model',root/'judge',root/'adapter')

    def test_observe_once_with_missing_data_never_launches_services(self):
        with tempfile.TemporaryDirectory() as d:
            queue=self.make(Path(d))
            with patch.object(q,'gpu_inventory',return_value=[row(2,used=0),row(3,used=0)]),\
                 patch.object(queue,'spawn',side_effect=AssertionError('must not spawn')):
                result=queue.observe_once()
            self.assertEqual(result['phase'],'WAITING_INPUTS')
            self.assertFalse(result['services_started'])
            self.assertEqual(result['eligible_gpus'],[2,3])
            self.assertTrue((queue.out/'plan.json').exists())

    def test_observe_driver_error_is_durable_not_fake_gpu_availability(self):
        with tempfile.TemporaryDirectory() as d:
            queue=self.make(Path(d))
            with patch.object(q,'gpu_inventory',side_effect=RuntimeError('no driver in sandbox')):
                result=queue.observe_once()
            self.assertEqual(result['gpus'],[])
            self.assertIn('no driver',result['gpu_query_error'])
            self.assertFalse(result['services_started'])

    def test_old_controller_cleanup_uses_saved_socket_not_unset_current_socket(self):
        with tempfile.TemporaryDirectory() as d:
            queue=self.make(Path(d));queue.out.mkdir()
            transport=Path('/tmp')/('sfpq_'+q.c.digest(str(queue.out))[:12])/'judge_fixture'
            command=queue.controller_command(transport/'score.sock')
            receipt=OwnershipTests().owner();receipt.update(role='controller',command=command,
                plan_sha256=q.c.digest(queue.plan),cwd=str(q.c.ROOT))
            path=queue.out/'sessions/old/controller/ownership.json'
            q.c.write(path,receipt,immutable=True)
            calls=[]
            with patch.object(q,'stop_owned',side_effect=lambda value:calls.append(value) or {'signal_sent':False,'leader_exited':True}):
                queue.cleanup_prior()
            self.assertEqual(len(calls),1)

    def test_private_transport_and_credential_environment_are_constrained(self):
        with tempfile.TemporaryDirectory() as d:
            queue=self.make(Path(d))
            with self.assertRaises(RuntimeError):queue.validate_transport(Path('/tmp/other/judge_fake'))
            with patch.dict(q.os.environ,{'DEEPSEEK_API_KEY':'must-not-leak','OPENAI_API_KEY':'must-not-leak'}):
                env,short=q.service_environment(queue.out,(2,3))
            self.assertNotIn('DEEPSEEK_API_KEY',env);self.assertNotIn('OPENAI_API_KEY',env)
            self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'2,3')
            self.assertEqual(env['HF_HUB_OFFLINE'],'1')

    def test_local_scripts_do_not_shadow_standard_queue_for_pyarrow_or_requests(self):
        program='import queue,pyarrow,requests; assert hasattr(queue,"Empty") and hasattr(queue,"LifoQueue"); print(queue.__file__)'
        result=subprocess.run([sys.executable,'-B','-c',program],cwd=Path(__file__).parent,
                              text=True,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('code_sfpruner300_20261114/queue.py',result.stdout)

    def exercise_infra_failure(self,root,controller_started):
        queue=self.make(root);queue.run_dir.mkdir()
        q.c.write(queue.run_dir/'progress.json',{'phase':'prepared','selected':1,'terminal_pairs':0})
        called=[]
        def fail(*args):
            called.append(True)
            if controller_started:queue.processes=[('controller',None,None,None)]
            raise RuntimeError('synthetic startup or execution failure')
        observed={'chosen':(2,3),'idle_seconds':90,'ready':True}
        with patch.object(queue,'ready',return_value=object()),\
             patch.object(queue,'cleanup_prior',return_value=None),\
             patch.object(q,'gpu_inventory',return_value=[row(2,used=0),row(3,used=0)]),\
             patch.object(q.IdleGate,'observe',return_value=observed),\
             patch.object(queue,'execute',side_effect=fail),\
             patch.object(queue,'shutdown',return_value={'main':{'leader_exited':True}}),\
             patch.object(q.time,'sleep',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'synthetic'):
                queue.wait()
        failures=[q.c.read(p) for p in queue.out.glob('sessions/*/failure.json')]
        return called,failures,q.c.read(queue.out/'status.json')

    def test_only_prebenchmark_infrastructure_has_two_fixed_attempts(self):
        with tempfile.TemporaryDirectory() as d:
            calls,failures,status=self.exercise_infra_failure(Path(d),False)
        self.assertEqual(len(calls),2);self.assertEqual(len(failures),2)
        self.assertTrue(all(not x['controller_launched'] and not x['semantic_retry'] for x in failures))
        self.assertEqual(status['phase'],'FAILED')

    def test_any_controller_launch_prevents_automatic_execution_retry(self):
        with tempfile.TemporaryDirectory() as d:
            calls,failures,status=self.exercise_infra_failure(Path(d),True)
        self.assertEqual(len(calls),1);self.assertEqual(len(failures),1)
        self.assertTrue(failures[0]['controller_launched'])
        self.assertFalse(failures[0]['semantic_retry'])

    def test_one_cleanup_error_does_not_skip_other_owned_services(self):
        with tempfile.TemporaryDirectory() as d:
            queue=self.make(Path(d));queue.out.mkdir()
            class Finished:
                def poll(self):return 0
            directories=[queue.out/'main',queue.out/'judge']
            for directory in directories:directory.mkdir()
            queue.processes=[('main',Finished(),{'role':'main'},directories[0]),
                             ('judge',Finished(),{'role':'judge'},directories[1])]
            def stop(receipt):
                if receipt['role']=='judge':raise PermissionError('simulated ownership read failure')
                return {'signal_sent':False,'leader_exited':True}
            with patch.object(q,'stop_owned',side_effect=stop):result=queue.shutdown()
        self.assertTrue(result['main']['leader_exited'])
        self.assertIn('shutdown_error',result['judge'])

    def test_execution_code_drift_fails_before_any_service_launch(self):
        with tempfile.TemporaryDirectory() as d:
            queue=self.make(Path(d));original=q.c.sha
            def changed(path):
                return 'wrong' if Path(path)==Path(q.c.__file__) else original(path)
            with patch.object(q.c,'sha',side_effect=changed),\
                 patch.object(queue,'spawn',side_effect=AssertionError('must not launch')):
                with self.assertRaisesRegex(ValueError,'code/config changed'):
                    queue.ready()


if __name__=='__main__':unittest.main()
