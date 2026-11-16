"""Synthetic subprocesses only: concurrent scheduling, isolation and no replay."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from . import parallel_controller as p
from .queue import Queue


class Backend(p.c.FrozenBackend):
    simulation = True

    def __init__(self, calls, fail_iid=None):
        self.calls, self.fail_iid = str(calls), fail_iid

    def protocol(self):
        return {'fixture': 'synthetic CPU only', 'fail_iid': self.fail_iid}

    def check_services(self, *args):
        return {'simulation': True, 'model_service_used': False}

    def command(self, arm, staged, snapshot, armout, runtime):
        code = '''import json,sys,time
from pathlib import Path
job=json.loads(Path(sys.argv[1]).read_text());arm=sys.argv[2];shared_ok=None
if arm=='hybrid_safe':
 shared=json.loads((Path(sys.argv[1]).parent/'shared.json').read_text())
 shared_ok=shared['instance_id']==job['instance_id'] and shared['base_commit']==job['base_commit'] and shared['raw_file_responses']==[job['instance_id']]
 if not shared_ok:raise RuntimeError('cross-issue source sharing')
with Path(sys.argv[4]).open('a') as f:f.write(json.dumps({'iid':job['instance_id'],'arm':arm,'shared_ok':shared_ok})+'\\n')
time.sleep(.05)
fail=arm=='baseline' and job['instance_id']==sys.argv[5]
result={k:job[k] for k in ('instance_id','repo','base_commit')}
result.update(arm=arm,status='failed' if fail else 'complete',simulation=True)
if not fail:result.update(ranked_edit_files=['m.py'],file_rank_after_reflection=['m.py'],raw_file_responses=[job['instance_id']])
Path(sys.argv[3]).write_text(json.dumps(result))
'''
        return [sys.executable, '-B', '-c', code, str(staged/'job.json'), arm,
                str(armout/'result.json'), self.calls, self.fail_iid or 'none']


class TrackingController(p.ParallelController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._count_lock = threading.Lock(); self.active = 0; self.peak = 0

    def run_pair(self, *args):
        with self._count_lock:
            self.active += 1; self.peak = max(self.peak, self.active)
        try:
            return super().run_pair(*args)
        finally:
            with self._count_lock:
                self.active -= 1


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);inputs=self.root/'inputs';inputs.mkdir()
        records=[]
        for n in range(5):
            iid='fixture__repo-'+str(n);task=inputs/iid;repo=task/'snapshot';repo.mkdir(parents=True)
            (repo/'m.py').write_text('def f():\n    return 1\n')
            p.c.write(task/'index.json',{'m.py':{'raw_sha256':p.c.sha(repo/'m.py')}})
            p.c.write(task/'structure.json',{});p.c.write(task/'render_cache.json',{})
            job={'instance_id':iid,'repo':'fixture/repo','base_commit':'a'*40,'problem_statement':'Synthetic fixture only.',
                 'cohort':'fixture','snapshot':'snapshot','paths':['m.py'],'code_index':'index.json','structure':'structure.json'}
            p.c.write(task/'job.json',job)
            records.append({'instance_id':iid,'repo':'fixture/repo','base_commit':'a'*40,
                            'job':iid+'/job.json','job_sha256':p.c.sha(task/'job.json')})
        self.manifest=inputs/'manifest.json';p.c.write(self.manifest,{'n':5,'records':records})
        self.out=self.root/'out';self.calls=self.root/'calls.jsonl'

    def controller(self, fail=None):
        return TrackingController(self.manifest,self.out,backend=Backend(self.calls,fail),heartbeat_seconds=.01)

    def read_calls(self):
        return [json.loads(x) for x in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_two_workers_same_base_distinct_issues_in_order_and_no_cross_sharing(self):
        ctrl=self.controller();ctrl.prepare();ctrl.run(None,None)
        self.assertEqual(ctrl.peak,2)
        calls=self.read_calls();self.assertEqual(len(calls),10)
        for record in ctrl.records:
            one=[x for x in calls if x['iid']==record['instance_id']]
            self.assertEqual([x['arm'] for x in one],['baseline','hybrid_safe'])
            self.assertTrue(one[1]['shared_ok'])
        self.assertEqual(p.c.read(self.out/'progress.json')['terminal_pairs'],5)
        self.assertTrue(p.c.read(self.out/'freeze.json')['simulation'])

    def test_completed_resume_does_not_replay_calls(self):
        ctrl=self.controller();ctrl.prepare();ctrl.run(None,None)
        before=self.calls.read_bytes()
        self.controller()._run(None,None)
        self.assertEqual(self.calls.read_bytes(),before)

    def test_started_without_result_is_interrupted_and_not_replayed(self):
        ctrl=self.controller();ctrl.prepare();record=ctrl.records[0]
        p.c.write(ctrl.pair(record)/'baseline/started.json',{'protocol_sha256':ctrl.protocol_sha},immutable=True)
        ctrl.run(None,None)
        self.assertFalse(any(x['iid']==record['instance_id'] for x in self.read_calls()))
        self.assertEqual(ctrl.arm_state(record,'baseline')['status'],'interrupted')
        self.assertEqual(ctrl.arm_state(record,'hybrid_safe')['status'],'dependency_blocked')

    def test_failed_baseline_blocks_only_its_own_hybrid(self):
        iid='fixture__repo-0';ctrl=self.controller(iid);ctrl.prepare();ctrl.run(None,None)
        calls=self.read_calls();self.assertEqual(len(calls),9)
        self.assertEqual([x['arm'] for x in calls if x['iid']==iid],['baseline'])
        term=p.c.read(self.out/'pairs'/iid/'hybrid_safe/terminal.json')
        self.assertEqual(term['status'],'dependency_blocked');self.assertTrue(term['keep_in_denominator'])

    def test_protocol_binds_scheduler_and_original_arm_source(self):
        ctrl=self.controller()
        self.assertEqual(ctrl.protocol['scheduling']['pair_workers'],2)
        self.assertEqual(ctrl.protocol['scheduling']['adapter_sha256'],p.c.sha(p.__file__))
        self.assertEqual(ctrl.protocol['controller_sha256'],p.c.sha(p.c.__file__))
        queue=Queue(self.manifest,self.out,self.root/'queue',self.root/'model',self.root/'judge',self.root/'adapter',judge_gpu=1)
        self.assertEqual(queue.plan['main_command'][queue.plan['main_command'].index('--max-num-seqs')+1],'1')
        self.assertIn('parallel_controller',queue.controller_command('/tmp/fake.sock')[3])
        queue.verify_plan_now()
        with patch('code_locbench_sfpruner_20261116.queue.scheduling_protocol',return_value={'changed':True}):
            with self.assertRaisesRegex(ValueError,'adapter changed'):
                queue.verify_plan_now()


if __name__ == '__main__':
    unittest.main()
