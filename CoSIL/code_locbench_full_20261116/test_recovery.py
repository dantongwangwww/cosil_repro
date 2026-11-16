"""Synthetic ownership and immutable output recovery tests; no model/GPU work."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import recovery as r


def receipt():
    command=['fixture','--cpu-only'];cwd='/fixture'
    saved={'pid':12345,'pgid':12345,'sid':12345,'uid':os.getuid(),'state':'S',
        'start_ticks':100,'cmdline_sha256':'a'*64,'argv':command,'cwd':cwd}
    return {'identity':saved,'command':command,'cwd':cwd}


class IdentityTests(unittest.TestCase):
    def test_adopted_unknown_exit_never_becomes_success(self):
        saved=receipt(); observations=[saved['identity'],None]
        ref=r.ProcessRef(receipt=saved,adopted=True,observe=lambda pid:observations.pop(0))
        self.assertIsNone(ref.poll());self.assertEqual(ref.wait(timeout=1),r.UNKNOWN_EXIT)
        self.assertEqual(ref.returncode,-255);self.assertTrue(ref.adopted)

    def test_adopted_reused_PID_is_unknown_and_stop_refuses_signal(self):
        saved=receipt();other=copy.deepcopy(saved['identity']);other['start_ticks']+=1
        ref=r.ProcessRef(receipt=saved,adopted=True,observe=lambda pid:other)
        self.assertEqual(ref.poll(),r.UNKNOWN_EXIT);sent=[]
        result=r.stop_saved(saved,observe=lambda pid:other,send=lambda *args:sent.append(args))
        self.assertTrue(result['ownership_mismatch']);self.assertFalse(sent)

    def test_argv_and_cwd_mismatch_never_signalled(self):
        for field,value in [('argv',['other']),('cwd','/other')]:
            saved=receipt();other=dict(saved['identity']);other[field]=value;sent=[]
            result=r.stop_saved(saved,observe=lambda pid:other,send=lambda *args:sent.append(args))
            self.assertTrue(result['ownership_mismatch']);self.assertFalse(sent)

    def test_owned_stop_delegates_the_full_identity(self):
        saved=receipt();observations=iter([saved['identity'],None]);sent=[]
        result=r.stop_saved(saved,observe=lambda pid:next(observations),
            send=lambda *args:sent.append(args),sleeper=lambda _:None,wait_seconds=1)
        self.assertTrue(result['leader_exited']);self.assertEqual(len(sent),1)
        self.assertEqual(sent[0][0],saved['identity']['pgid'])

    def test_start_refuses_unknown_live_PID_without_new_process(self):
        saved=receipt()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);saved['cwd']=str(root);saved['identity']['cwd']=str(root)
            p=root/'ownership.json';r.c.write(p,saved);other=dict(saved['identity'],start_ticks=999)
            with patch.object(r.sq,'identity',return_value=other),patch.object(r.subprocess,'Popen') as launch:
                with self.assertRaisesRegex(RuntimeError,'Unknown/reused'):
                    r.start_or_adopt(saved['command'],root,{},p,root/'run')
                launch.assert_not_called()

    def test_real_cpu_child_adoption_unique_restart_logs_and_unknown_reaping(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);command=[sys.executable,'-c',
                'import time; print("synthetic CPU child",flush=True); time.sleep(.8)']
            pointer=root/'ownership.json';env={**os.environ,'CUDA_VISIBLE_DEVICES':''}
            ref,saved=r.start_or_adopt(command,root,env,pointer,root/'cpu')
            try:
                self.assertFalse(ref.adopted);self.assertIsNone(ref.poll())
                adopted,again=r.start_or_adopt(command,root,env,pointer,root/'cpu')
                self.assertTrue(adopted.adopted);self.assertEqual(ref.pid,adopted.pid)
                self.assertEqual(ref.wait(timeout=5),0)
            finally:
                if ref.poll() is None:ref.wait(timeout=5)
            self.assertEqual(adopted.wait(timeout=1),r.UNKNOWN_EXIT)
            first=Path(saved['log']).read_bytes()
            restarted,later=r.start_or_adopt(command,root,env,pointer,root/'cpu')
            try:self.assertEqual(restarted.wait(timeout=5),0)
            finally:
                if restarted.poll() is None:r.stop_saved(later)
            self.assertNotEqual(saved['log'],later['log'])
            self.assertEqual(Path(saved['log']).read_bytes(),first)
            self.assertTrue(Path(saved['history_receipt']).exists())
            self.assertEqual(json.loads(pointer.read_text())['identity']['pid'],restarted.pid)

    def test_adopted_timeout_does_not_terminate(self):
        saved=receipt();ref=r.ProcessRef(receipt=saved,adopted=True,observe=lambda pid:saved['identity'])
        with self.assertRaises(subprocess.TimeoutExpired):ref.wait(timeout=.01)


class OutputTests(unittest.TestCase):
    def test_partial_output_renamed_with_identical_bytes_and_SHA(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'final';(out/'nested').mkdir(parents=True)
            (out/'nested/raw.txt').write_bytes(b'partial\x00exact\n');before=r.c.sha(out/'nested/raw.txt')
            proof=r.preserve_partial_output(out)
            self.assertFalse(out.exists());self.assertFalse(proof['deleted'])
            kept=Path(proof['preserved_path'])/'nested/raw.txt'
            self.assertEqual(r.c.sha(kept),before);self.assertTrue(proof['original_bytes_preserved'])
            self.assertTrue(Path(proof['receipt_path']).exists())

    def test_complete_manifest_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'final';out.mkdir();r.c.write(out/'output_sha256.json',{'complete':True})
            before=(out/'output_sha256.json').read_bytes();proof=r.preserve_partial_output(out)
            self.assertEqual(proof['status'],'COMPLETE_MANIFEST_PRESENT');self.assertFalse(proof['preserved'])
            self.assertEqual((out/'output_sha256.json').read_bytes(),before)

    def test_absent_does_not_create_output_and_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'missing';self.assertEqual(r.preserve_partial_output(out)['status'],'ABSENT')
            self.assertFalse(out.exists());target=root/'target';target.mkdir();link=root/'linked';link.symlink_to(target)
            with self.assertRaisesRegex(ValueError,'Symlink'):r.preserve_partial_output(link)


if __name__=='__main__':unittest.main()
