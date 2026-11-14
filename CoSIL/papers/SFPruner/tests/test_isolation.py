import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specprune.runtime_helpers import BUNDLE, read
from specprune.isolation import command


class IsolationContract(unittest.TestCase):
    def test_missing_bwrap_fails_closed(self):
        with patch('specprune.isolation.shutil.which', return_value=None):
            with self.assertRaises(RuntimeError): command(['_worker','--arm','baseline'])

    def test_no_parent_data_or_user_environment_mount(self):
        if shutil.which('bwrap') is None: self.skipTest('bwrap unavailable')
        args=command(['_worker','--arm','baseline'])
        self.assertIn('--clearenv',args)
        self.assertNotIn(str(BUNDLE/'assets/evaluation'),args)
        self.assertNotIn(str(BUNDLE/'assets/training'),args)
        self.assertNotIn('--dev-bind',args)
        for flag in ('--ro-bind','--bind'):
            for i,arg in enumerate(args):
                if arg==flag:
                    self.assertNotIn(args[i+2],('/','/home','/bundle','/bundle/assets'))
        self.assertEqual(args[args.index('CUDA_VISIBLE_DEVICES')+1],'')

    def test_real_agent_factories_in_cpu_bubblewrap(self):
        if shutil.which('bwrap') is None: self.skipTest('bwrap unavailable; real runs still fail closed')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'smoke'
            env={**os.environ,'PYTHONPATH':str(BUNDLE),'CUDA_VISIBLE_DEVICES':''}
            done=subprocess.run([sys.executable,'-B','-m','specprune.runner','dry-run','--out',str(out)],
                env=env,cwd=BUNDLE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
            self.assertEqual(done.returncode,0,done.stdout)
            receipt=read(out/'dry_run_receipt.json')
            self.assertTrue(receipt['passed']);self.assertEqual(receipt['real_model_calls'],0)
            self.assertFalse(receipt['gpu_used']);self.assertTrue(receipt['not_benchmark_result'])
            for arm in ('baseline','hybrid_safe'):
                result=read(out/'pair'/arm/'result.json')
                self.assertEqual(result['status'],'complete')
                self.assertTrue(result['simulation'])
                self.assertEqual(result['predicted_functions'][0]['qualified_name'],'add')


if __name__=='__main__': unittest.main()
