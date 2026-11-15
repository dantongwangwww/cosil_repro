"""CPU supervisor fixtures; no GPU, model invocation, or real study reports."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from code_sfpruner300_20261114 import controller as c
from code_sfpruner300_20261114 import pipeline as p


def identity():
    return dict(pid=9999999,uid=os.getuid(),state='S',pgid=9999999,sid=9999999,
                start_ticks=17,cmdline_sha256='fixture')


def args(root):
    return argparse.Namespace(work=root,pipeline_dir=root/'pipeline',manifest=root/'runtime/manifest.json',
        run_dir=root/'paired',queue_dir=root/'queue',reports=root/'reports',python=sys.executable,
        poll_seconds=1,stale_seconds=600,builder_private=root/'builder',
        builder_identity=root/'builder/identity.json',archive_cache=root/'cache')


class PreparationTests(unittest.TestCase):
    def test_large_archive_activity_and_stale_alive_are_not_builder_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);progress=root/'progress.json';progress.write_text(json.dumps(dict(selected=208,complete=1,blocked={})))
            cache=root/'cache';cache.mkdir();part=cache/'large.tar.gz.part';part.write_bytes(b'partial')
            os.utime(progress,(100,100));os.utime(part,(990,990));who=identity()
            observation=p.observe_builder(progress,root/'manifest.json',who,cache,now=1000,observer=lambda _:dict(who))
            self.assertEqual(observation['phase'],'WAITING_PREPARATION')
            self.assertEqual(observation['source_activity_age_seconds'],10)
            os.utime(part,(100,100))
            observation=p.observe_builder(progress,root/'manifest.json',who,cache,now=1000,observer=lambda _:dict(who))
            self.assertEqual(observation['phase'],'STALE_PREPARATION_BUILDER_ALIVE')
            self.assertTrue(observation['builder_alive']);self.assertFalse(observation['ready'])

    def test_dead_or_reused_builder_and_explicit_block_stop_without_signals(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);progress=root/'progress.json';progress.write_text(json.dumps(dict(selected=208,complete=1,blocked={})))
            with self.assertRaisesRegex(p.PipelineStop,'Recorded builder'):
                p.observe_builder(progress,root/'manifest.json',identity(),root/'cache',observer=lambda _:None)
            changed=identity();changed['start_ticks']+=1
            with self.assertRaises(p.PipelineStop):
                p.observe_builder(progress,root/'manifest.json',identity(),root/'cache',observer=lambda _:changed)
            progress.write_text(json.dumps(dict(selected=208,complete=1,blocked={'bad':{'error':'fixture'}})))
            with self.assertRaisesRegex(p.PipelineStop,'explicit blocked'):
                p.observe_builder(progress,root/'manifest.json',identity(),root/'cache',observer=lambda _:identity())

    def test_manifest_requires_complete_progress(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);progress=root/'builder/progress.json';progress.parent.mkdir();manifest=root/'manifest.json';manifest.write_text(json.dumps(dict(n=208,records=[{}]*208)))
            progress.write_text(json.dumps(dict(selected=208,complete=207,blocked={})))
            with self.assertRaises(p.PipelineStop):p.observe_builder(progress,manifest,identity(),root/'cache')
            progress.write_text(json.dumps(dict(selected=208,complete=208,blocked={})))
            self.assertTrue(p.observe_builder(progress,manifest,identity(),root/'cache')['ready'])

    def test_recovered_manifest_uses_verified_ledger_instead_of_historical_block(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);progress=root/'runtime_build/progress.json';progress.parent.mkdir()
            progress.write_text(json.dumps(dict(selected=208,complete=207,blocked={'old':'preserved fixture'})))
            manifest=root/'manifest.json';manifest.write_text(json.dumps(dict(n=208,records=[{}]*208)))
            recovery=root/'runtime_recovery';recovery.mkdir();ledger=recovery/'ledger.json';ledger.write_text('{"simulation":true}')
            proof=dict(status='READY',n=208,manifest_sha256=c.sha(manifest),recovery_ledger_path=str(ledger),recovery_ledger_sha256=c.sha(ledger))
            (progress.parent/'finalization_receipt.json').write_text(json.dumps(proof))
            observation=p.observe_builder(progress,manifest,identity(),root/'cache',observer=lambda _:None)
            self.assertTrue(observation['ready']);self.assertTrue(observation['recovery_proof'])
            ledger.write_text('changed ledger fixture')
            with self.assertRaisesRegex(p.PipelineStop,'ledger SHA'):p.observe_builder(progress,manifest,identity(),root/'cache')


class GateTests(unittest.TestCase):
    def test_r2_targets_use_exact_existing_function_identities(self):
        index={'pkg/f.py':{'definitions':[dict(kind='function',qualified_name='C.run'),dict(kind='class',qualified_name='C')]}}
        self.assertEqual(p.verify_target_inventory(['pkg/f.py::C.run'],index),1)
        with self.assertRaises(p.PipelineStop):p.verify_target_inventory(['other/f.py::C.run'],index)
        with self.assertRaises(p.PipelineStop):p.verify_target_inventory(['pkg/f.py::C'],index)

    def test_historical_source_drift_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'old.json';file.write_text('immutable fixture')
            frozen={'files_sha256':{str(file):c.sha(file)}};p.verify_anchor(frozen)
            file.write_text('changed fixture')
            with self.assertRaises(p.PipelineStop):p.verify_anchor(frozen)


class StageTests(unittest.TestCase):
    def test_real_cpu_child_has_owned_session_and_completed_stage_is_not_relaunched(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);called=[]
            def spawn(*a,**kw):called.append(a[0]);return subprocess.Popen(*a,**kw)
            pipeline=p.Pipeline(args(root),popen=spawn,sleeper=lambda _:time.sleep(.01))
            pipeline.out.mkdir();command=[sys.executable,'-c','import time;time.sleep(.2);print("simulation-only fixture")']
            first=pipeline.stage('cpu_fixture',command)
            self.assertEqual(first['returncode'],0)
            ownership=c.read(root/'pipeline/stages/cpu_fixture/ownership.json')
            self.assertEqual(ownership['identity']['pid'],ownership['identity']['pgid'])
            self.assertEqual(ownership['identity']['pid'],ownership['identity']['sid'])
            self.assertEqual(ownership['identity']['uid'],os.getuid())
            self.assertEqual(ownership['command'],command)
            self.assertEqual(first,pipeline.stage('cpu_fixture',command));self.assertEqual(len(called),1)

    def test_failed_started_stage_is_preserved_and_never_automatically_retried(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);calls=[]
            def spawn(*a,**kw):calls.append(a[0]);return subprocess.Popen(*a,**kw)
            pipeline=p.Pipeline(args(root),popen=spawn,sleeper=lambda _:time.sleep(.01));pipeline.out.mkdir()
            command=[sys.executable,'-c','import time,sys;time.sleep(.2);sys.exit(3)']
            with self.assertRaises(p.PipelineStop):pipeline.stage('failed_fixture',command)
            with self.assertRaisesRegex(p.PipelineStop,'already launched'):pipeline.stage('failed_fixture',command)
            self.assertEqual(len(calls),1)
            self.assertEqual(c.read(root/'pipeline/stages/failed_fixture/failed.json')['returncode'],3)

    def test_cleanup_will_not_signal_a_reused_process(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);saved=identity();saved.update(argv=['fixture'],cwd=str(c.ROOT))
            observed=dict(saved,start_ticks=18)
            pipeline=p.Pipeline(args(root),observer=lambda _:observed)
            pipeline.children=[('fixture',None,dict(identity=saved,command=['fixture'],cwd=str(c.ROOT)))]
            result=pipeline.cleanup()['fixture']
            self.assertFalse(result['signal_sent']);self.assertTrue(result['ownership_mismatch'])

    def test_normal_exit_between_poll_and_proc_observation_is_not_identity_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);command=['simulation-only-fixture'];saved=identity();saved.update(argv=command,cwd=str(c.ROOT))
            class Process:
                pid=saved['pid'];returncode=None
                def poll(self):
                    if self.returncode is None:self.returncode=0;return None
                    return 0
            observations=iter([dict(saved),None])
            pipeline=p.Pipeline(args(root),popen=lambda *a,**k:Process(),observer=lambda _:next(observations),sleeper=lambda _:None)
            pipeline.out.mkdir()
            self.assertEqual(pipeline.stage('simulated_exit_race',command)['returncode'],0)


if __name__=='__main__':unittest.main()
