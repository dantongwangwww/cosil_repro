"""Transport-only continuation fixtures; no GPU or real model invocation."""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from code_sfpruner300_20261114 import controller_continuation as h
from code_sfpruner300_20261114 import test_controller as fixtures


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sfpruner-continuation-cpu-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.out=self.root/'run';self.out.mkdir();self.model=self.root/'model';self.model.mkdir()
        self.token_bytes=b'{"fixture":"tokenizer only; not a model"}'
        model_token=self.model/'tokenizer.json';model_token.write_bytes(self.token_bytes)
        self.pin={'model_id':'Qwen/Qwen3-8B','revision':'b968826d9c46dd6066d109eabc6255188de91218',
                  'files_sha256':{'tokenizer.json':h.c.sha(model_token),'model.safetensors':'0'*64}}
        self.seed_out(self.out)

    def environment(self,out,socket='/tmp/simulation-old/score.sock'):
        return {'verified_model_directory':str(self.model.resolve()),'model':self.pin['model_id'],
            'revision':self.pin['revision'],'verified_files':len(self.pin['files_sha256']),
            'tokenizer_directory':str(out.absolute()/'_main_tokenizer'),'judge_socket':socket,
            'alias_is_not_weight_identity_proof':True,'service_launch_receipt_still_required_for_publication':True}

    def seed_out(self,out,*,write_freeze=True):
        tokenizer=out/'_main_tokenizer';tokenizer.mkdir(exist_ok=True);(tokenizer/'tokenizer.json').write_bytes(self.token_bytes)
        if write_freeze:h.c.write(out/'freeze.json',{'controller_sha256':h.c.sha(h.c.__file__)},immutable=True)
        h.c.write(out/'runtime_environment.json',self.environment(out),immutable=True)

    def test_only_socket_redirects_and_original_bytes_are_preserved(self):
        target=self.out/'runtime_environment.json';before=target.read_bytes();new=self.environment(self.out,'/tmp/simulation-new/score.sock')
        original_write=h.c.write
        with h.redirect_runtime_receipt(self.out,self.model,pin=self.pin):h.c.write(target,new,immutable=True)
        self.assertIs(h.c.write,original_write);self.assertEqual(target.read_bytes(),before)
        files=list((self.out/'runtime_continuations').glob('*.json'));self.assertEqual(len(files),1)
        receipt=h.c.read(files[0]);self.assertEqual(receipt['changed_fields'],['judge_socket'])
        self.assertEqual(receipt['original_sha256'],h.byte_sha(before));self.assertEqual(receipt['new_runtime_sha256'],h.byte_sha(h.serialized(new)))
        self.assertEqual(receipt['runtime_environment'],new)
        self.assertEqual(files[0].stem,h.c.digest({'old':receipt['original_sha256'],'new':receipt['new_runtime_sha256'],'helper':receipt['helper_sha256']}))
        with h.redirect_runtime_receipt(self.out,self.model,pin=self.pin):h.c.write(target,new,immutable=True)
        self.assertEqual(len(list((self.out/'runtime_continuations').glob('*.json'))),1)

    def test_other_environment_changes_are_rejected_without_touching_original(self):
        target=self.out/'runtime_environment.json';before=target.read_bytes()
        for field,value in [('revision','wrong'),('verified_files',1),('model','other'),
            ('tokenizer_directory','/tmp/other'),('verified_model_directory','/tmp/other'),
            ('alias_is_not_weight_identity_proof',False),('unexpected','private')]:
            with self.subTest(field=field):
                incoming=self.environment(self.out,'/tmp/new/score.sock');incoming[field]=value
                with self.assertRaises(ValueError):
                    with h.redirect_runtime_receipt(self.out,self.model,pin=self.pin):h.c.write(target,incoming,immutable=True)
                self.assertEqual(target.read_bytes(),before)

    def test_tokenizer_and_controller_pin_are_checked_before_interception(self):
        original=h.c.write;token=self.out/'_main_tokenizer/tokenizer.json';token.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'tokenizer bytes'):
            with h.redirect_runtime_receipt(self.out,self.model,pin=self.pin):pass
        self.assertIs(h.c.write,original);token.write_bytes(self.token_bytes)
        (self.out/'freeze.json').write_text(json.dumps({'controller_sha256':'bad'}))
        with self.assertRaisesRegex(ValueError,'controller SHA'):
            with h.redirect_runtime_receipt(self.out,self.model,pin=self.pin):pass
        self.assertIs(h.c.write,original)

    def test_other_writes_and_exceptions_follow_original_logic_and_wrapper_restores(self):
        original=h.c.write;other=self.out/'other.json';marker=RuntimeError('original caller exception')
        with self.assertRaises(RuntimeError) as caught:
            with h.redirect_runtime_receipt(self.out,self.model,pin=self.pin):
                h.c.write(other,{'fixture':True},immutable=True)
                raise marker
        self.assertIs(caught.exception,marker);self.assertIs(h.c.write,original)
        self.assertEqual(h.c.read(other),{'fixture':True})
        with self.assertRaises(ValueError):
            with h.redirect_runtime_receipt(self.out,self.model,pin=self.pin):h.c.write(other,{'changed':True},immutable=True)
        self.assertIs(h.c.write,original)

    def test_interception_requires_the_exact_immutable_write(self):
        original=h.c.write;calls=[]
        def spy(path,value,*,immutable=False):
            calls.append((Path(path),immutable));return original(path,value,immutable=immutable)
        with patch.object(h.c,'write',spy):
            with h.redirect_runtime_receipt(self.out,self.model,pin=self.pin):
                h.c.write(self.out/'another.json',{'fixture':1},immutable=False)
                # An unchanged mutable call is deliberately forwarded, rather
                # than broadly patched; the frozen core never uses this mode.
                h.c.write(self.out/'runtime_environment.json',self.environment(self.out),immutable=False)
        self.assertIn((self.out/'another.json',False),calls)
        self.assertIn((self.out/'runtime_environment.json',False),calls)
        self.assertFalse((self.out/'runtime_continuations').exists())

    def test_main_new_run_keeps_original_entry_and_args(self):
        argv=['shim','--run','--manifest','fixture.json','--out',str(self.root/'new'),
              '--main-model-dir',str(self.model),'--judge-socket','/tmp/new.sock']
        with patch.object(sys,'argv',argv),patch.object(h.c,'main',return_value='original') as main,patch.object(h,'redirect_runtime_receipt') as redirect:
            self.assertEqual(h.main(),'original');main.assert_called_once();redirect.assert_not_called()
            self.assertEqual(sys.argv,argv)

    def test_main_existing_run_uses_only_the_runtime_redirect_scope(self):
        argv=['shim','--run','--manifest','fixture.json','--out',str(self.out),
              '--main-model-dir',str(self.model),'--judge-socket','/tmp/new.sock']
        with patch.object(sys,'argv',argv),patch.object(h.c,'main',return_value='original') as main,patch.object(h,'redirect_runtime_receipt',return_value=nullcontext()) as redirect:
            self.assertEqual(h.main(),'original');main.assert_called_once()
            redirect.assert_called_once_with(self.out,self.model);self.assertEqual(sys.argv,argv)

    def test_original_controller_never_replays_the_started_baseline(self):
        fixture=fixtures.ControllerTests('test_real_staging_fake_execution_and_resume_never_duplicate_calls');fixture.setUp();self.addCleanup(fixture.temporary.cleanup)
        new=self.environment(fixture.out,'/tmp/simulation-new/score.sock')
        class NeverRunBackend(fixtures.FakeBackend):
            def check_services(self,*args):return new
            def command(self,*args):raise AssertionError('A previously started arm was replayed')
        backend=NeverRunBackend(fixture.count)
        ctrl=h.c.Controller(fixture.manifest,fixture.out,backend=backend,heartbeat_seconds=.01);ctrl.prepare()
        self.seed_out(fixture.out,write_freeze=False)
        baseline=ctrl.pair(ctrl.records[0])/'baseline';baseline.mkdir()
        h.c.write(baseline/'started.json',{'protocol_sha256':ctrl.protocol_sha},immutable=True)
        started_sha=h.c.sha(baseline/'started.json');old_sha=h.c.sha(fixture.out/'runtime_environment.json')
        with h.redirect_runtime_receipt(fixture.out,self.model,pin=self.pin):ctrl.run(self.model,'/tmp/simulation-new/score.sock')
        self.assertEqual(h.c.read(baseline/'terminal.json')['status'],'interrupted')
        self.assertEqual(h.c.read(baseline.parent/'hybrid_safe/terminal.json')['status'],'dependency_blocked')
        self.assertFalse(fixture.count.exists());self.assertEqual(h.c.sha(baseline/'started.json'),started_sha)
        self.assertEqual(h.c.sha(fixture.out/'runtime_environment.json'),old_sha)
        # A terminal run returns before services/environment writes, and cannot
        # create additional attempts or ask a model a second time.
        ctrl.run(None,None)
        self.assertEqual(h.c.sha(baseline/'started.json'),started_sha)
        self.assertEqual(h.c.read(fixture.out/'progress.json')['terminal_pairs'],1)


if __name__=='__main__':unittest.main()
