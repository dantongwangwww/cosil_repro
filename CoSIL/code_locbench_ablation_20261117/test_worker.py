"""Real frozen agent factory with synthetic renderer/client; no model calls."""
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import worker as w
from .policy import ARMS, activate_bundle
from .test_policy import Tokenizer, row

activate_bundle()
from specprune.runtime_helpers import activate_vendor
activate_vendor()
from specprune import runner, runtime_renderer, provider
from code_qwen3_rr4_rebench100 import worker as old


class Base:
    def __init__(self):
        self.problem_statement = 'Synthetic issue'; self.events = []
        self.accepted_ids = []; self.sources = []; self.main_prune_calls = 0

    def _prune(self, model, call, content, code, step):
        self.main_prune_calls += 1
        self._record_event('prune', step=step, tool=call.name, decision='True')
        return 'True'


class Renderer:
    fail = False
    def __init__(self, *args): self.tokenizers = {'fake': (Tokenizer(), 'reranker')}
    def render(self, *args):
        if self.fail: raise ValueError('synthetic identity binding error')
        return row()


class Client:
    probability = .5
    error = None
    def score(self, value):
        if self.error: raise self.error
        return {'p_yes': self.probability, 'input_tokens': 40, 'generated_output_tokens': 0,
                'latency_seconds': .01, 'temperature': 2.9846201034621833}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        Renderer.fail = False; Client.error = None; Client.probability = .5
        self.call = SimpleNamespace(name='get_code_of_file_function', arguments=('m.py', 'f'))
        self.deployment = dict(low=.12947567721292427, high=.9, temperature=2.9846201034621833)

    def agent(self, variant):
        stack = w.hooks(variant); stack.__enter__(); self.addCleanup(stack.__exit__, None, None, None)
        old.Renderer, old.Client = Renderer, Client
        original = lambda base, *args: base
        agent_type = old.agent_factory(original, 'hybrid_safe', self.deployment, None, None, 'synthetic')(
            Base, {'instance_id': 'synthetic__repo-1'}, {}, None, None, RuntimeError)
        return agent_type()

    def test_original_gray_qwen_only_overridden_for_no_defer_and_probability_not_forged(self):
        agent = self.agent(ARMS[2])
        self.assertEqual(agent._prune(None, self.call, 'candidate', 'code', 1), 'True')
        self.assertEqual(agent.main_prune_calls, 0)
        event = next(x for x in agent.events if x['event'] == 'local_judge')
        self.assertEqual((event['route_original'], event['route_effective']), ('qwen', 'retain'))
        self.assertEqual(event['p_yes'], .5)
        self.assertEqual(event['arm'], 'hybrid_safe')
        self.assertEqual(event['experimental_arm'], ARMS[2])
        self.assertTrue(event['gray_override'])

    def test_no_defer_below_half_rejects_without_qwen(self):
        Client.probability = .49999; agent = self.agent(ARMS[2])
        self.assertEqual(agent._prune(None, self.call, '', '', 1), 'False')
        self.assertEqual(agent.main_prune_calls, 0)

    def test_other_variants_keep_gray_qwen_and_all_events_have_variant(self):
        for variant in ARMS[:2]:
            with self.subTest(variant=variant):
                with w.hooks(variant):
                    old.Renderer, old.Client = Renderer, Client
                    original = lambda base, *args: base
                    agent = old.agent_factory(original, 'hybrid_safe', self.deployment, None, None, 'x')(
                        Base, {'instance_id': 'synthetic__repo-1'}, {}, None, None, RuntimeError)()
                    self.assertEqual(agent._prune(None, self.call, '', '', 1), 'True')
                    self.assertEqual(agent.main_prune_calls, 1)
                    self.assertTrue(all(e['experimental_arm'] == variant for e in agent.events))

    def test_class_and_binding_fallback_preserved_even_no_defer(self):
        agent = self.agent(ARMS[2])
        class_call = SimpleNamespace(name='get_code_of_class', arguments=('m.py', 'C'))
        self.assertEqual(agent._prune(None, class_call, '', '', 1), 'True')
        self.assertEqual(agent.main_prune_calls, 1)
        self.assertEqual(agent.events[-1]['policy_decision_source'], 'qwen_class_fallback')
        Renderer.fail = True
        self.assertEqual(agent._prune(None, self.call, '', '', 2), 'True')
        self.assertEqual(agent.main_prune_calls, 2)
        self.assertEqual(agent.events[-1]['policy_decision_source'], 'qwen_binding_fallback')
        self.assertTrue(agent.events[-1]['technical_fallback'])

    def test_rpc_and_nonfinite_failure_never_qwen_or_silent_reject(self):
        agent = self.agent(ARMS[2]); Client.error = RuntimeError('synthetic RPC failure')
        with self.assertRaisesRegex(RuntimeError, 'RPC'): agent._prune(None, self.call, '', '', 1)
        self.assertEqual(agent.main_prune_calls, 0)
        Client.error = None; Client.probability = float('nan')
        with self.assertRaises(ValueError): agent._prune(None, self.call, '', '', 2)
        self.assertEqual(agent.main_prune_calls, 0)

    def test_real_renderer_hook_removes_every_neighbor_after_fitting(self):
        with patch.object(runtime_renderer, 'Renderer', Renderer):
            with w.hooks(ARMS[1]):
                result = runtime_renderer.Renderer().render('', None, '')
                self.assertEqual(result['neighbors'], '')
                self.assertEqual(result['issue'], row()['issue'])
                self.assertEqual(result['function'], row()['function'])
                self.assertTrue(result['token_budget_trimmed'])

    def test_hooks_restore_all_bindings_after_exception(self):
        before = (runner.SocketClient, runtime_renderer.Renderer, old.agent_factory, old.P.route)
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            with w.hooks(ARMS[0]): raise RuntimeError('synthetic')
        self.assertEqual(before, (runner.SocketClient, runtime_renderer.Renderer, old.agent_factory, old.P.route))

    def test_provider_first_result_identity_without_changing_http_api(self):
        fake = SimpleNamespace(resources=lambda: {'semantic_calls': 7})
        with patch.object(provider, 'real_provider', return_value=fake):
            with w.hooks(ARMS[0]):
                resources = provider.real_provider('/unused').resources()
        self.assertEqual(resources['experimental_arm'], ARMS[0])
        self.assertEqual(resources['internal_arm'], 'hybrid_safe')
        self.assertEqual(resources['semantic_calls'], 7)

    def test_client_outer_variant_does_not_enter_six_field_model_row(self):
        captured = []
        answer = dict(ok=True, result=dict(p_yes=.5, route='qwen', experimental_arm=ARMS[0],
                      internal_arm='hybrid_safe', adapter_active=False))
        class Socket:
            def __init__(self, *args): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def settimeout(self, value): self.timeout = value
            def connect(self, value): pass
            def sendall(self, data): captured.append(json.loads(data))
            def makefile(self, *args): return io.BytesIO((json.dumps(answer)+'\n').encode())
        with patch.object(w.socket, 'socket', Socket):
            result = w.SocketClient(ARMS[0]).score(row())
        self.assertEqual(set(captured[0]), {'operation', 'variant', 'row'})
        self.assertEqual(set(captured[0]['row']), set(runner.RPC_FIELDS))
        self.assertNotIn('experimental_arm', captured[0]['row'])
        self.assertEqual(result['p_yes'], .5)
        self.assertNotIn('route', result)

    def test_client_rpc_error_preserved(self):
        client = w.SocketClient(ARMS[0])
        with patch.object(client, 'request', side_effect=RuntimeError('synthetic resident error')):
            with self.assertRaises(RuntimeError): client.score(row())

    def test_run_delegates_original_internal_worker_inside_hooks(self):
        original_factory = old.agent_factory
        def entry(args):
            self.assertEqual(args.arm, 'hybrid_safe')
            self.assertFalse(args.simulate)
            self.assertIsNot(old.agent_factory, original_factory)
            self.assertEqual(runner.SocketClient().variant, ARMS[2])
            return 'synthetic-delegate-result'
        with patch.object(runner, 'worker', side_effect=entry):
            self.assertEqual(w.run(ARMS[2]), 'synthetic-delegate-result')
        self.assertIs(old.agent_factory, original_factory)

    def test_rpc_journal_success_survives_missing_agent_event_and_never_changes_wire_request(self):
        with tempfile.TemporaryDirectory() as directory:
            client = w.SocketClient(ARMS[0], audit_dir=directory)
            response = {'p_yes': .5, 'route': 'qwen', 'input_tokens': 345,
                        'generated_output_tokens': 0, 'score_sequence': 19, 'model_load_count': 1,
                        'adapter_active': False}
            with patch.object(client, 'request', return_value=response) as request:
                result = client.score(row())  # No Agent/local_judge event is written.
            request.assert_called_once_with('score', row())
            starts, receipts = list(Path(directory).glob('*_start.json')), list(Path(directory).glob('*_receipt.json'))
            self.assertEqual((len(starts), len(receipts)), (1, 1))
            receipt = json.loads(receipts[0].read_text())
            self.assertEqual(receipt['status'], 'success')
            self.assertEqual(receipt['usage_status'], 'known')
            self.assertEqual(receipt['input_tokens'], 345)
            self.assertEqual(receipt['generated_output_tokens'], 0)
            self.assertEqual(receipt['score_sequence'], 19)
            self.assertEqual(receipt['request_id'], result['judge_rpc_request_id'])
            self.assertEqual(receipt['experimental_arm'], ARMS[0])
            self.assertEqual(receipt['input_sha256'], row()['input_sha256'])

    def test_forward_then_nonfinite_or_response_disconnect_journals_unknown_and_reraises(self):
        for error in (FloatingPointError('forward then nonfinite'), ConnectionResetError('response lost')):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                client = w.SocketClient(ARMS[2], audit_dir=directory)
                with patch.object(client, 'request', side_effect=error):
                    with self.assertRaises(type(error)): client.score(row())
                receipt = json.loads(next(Path(directory).glob('*_receipt.json')).read_text())
                self.assertEqual(receipt['status'], 'error')
                self.assertEqual(receipt['usage_status'], 'unknown')
                self.assertEqual(receipt['forward_status'], 'unknown')
                self.assertIsNone(receipt['input_tokens'])
                self.assertIsNone(receipt['generated_output_tokens'])
                self.assertEqual(receipt['error_type'], type(error).__name__)

    def test_rpc_journal_start_precedes_forward_and_exception_receipt_failure_preserves_error(self):
        with tempfile.TemporaryDirectory() as directory:
            client = w.SocketClient(ARMS[1], audit_dir=directory)
            original_journal = client._journal
            def journal(request_id, suffix, value):
                if suffix == 'receipt': raise OSError('synthetic journal storage failure')
                return original_journal(request_id, suffix, value)
            def forward(*args):
                self.assertEqual(len(list(Path(directory).glob('*_start.json'))), 1)
                raise FloatingPointError('original scoring error')
            with patch.object(client, '_journal', side_effect=journal), \
                    patch.object(client, 'request', side_effect=forward), patch.object(w.sys, 'stderr'):
                with self.assertRaisesRegex(FloatingPointError, 'original scoring error'): client.score(row())
            start = json.loads(next(Path(directory).glob('*_start.json')).read_text())
            self.assertEqual(start['usage_status'], 'unknown')
            self.assertEqual(list(Path(directory).glob('*_receipt.json')), [])

    def test_real_worker_bound_client_requires_audit_but_synthetic_probe_does_not(self):
        with w.hooks(ARMS[0]):
            client = runner.SocketClient()
            self.assertEqual(client.audit_dir, Path('/output/judge_rpc'))
        self.assertIsNone(w.SocketClient(ARMS[0]).audit_dir)

    def test_original_run_case_keeps_rpc_forward_failure_as_failed_with_unknown_journal(self):
        from code_rebench_qwen import runner as original_runner
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'snapshot'; source.mkdir()
            (source/'m.py').write_text('def f():\n    return 1\n')
            index, structure, jobpath = root/'index.json', root/'structures'/'case.json', root/'job.json'
            structure.parent.mkdir()
            index.write_text('{}'); structure.write_text(json.dumps({'structure': {}}))
            job = dict(instance_id='synthetic__repo-1', repo='synthetic/repo', base_commit='a'*40,
                problem_statement='Synthetic issue only.', cohort='fixture', snapshot=str(source),
                paths=['m.py'], code_index=str(index), structure=str(structure))
            jobpath.write_text(json.dumps(job))
            output = root/'out'
            client = w.SocketClient(ARMS[2], audit_dir=output/'judge_rpc')
            class Agent:
                def __init__(self, *args, **kwargs):
                    self.file_outputs = [{'response': 'm.py'}]
                    self.sources = []; self.accepted_ids = []; self.last_messages = []
                def file_localize_with_g(self, **kwargs): return ['m.py'], '', ''
                def _record_event(self, *args, **kwargs): pass
                def _parse_top5_file(self, *args): return ['m.py']
                def localize_with_p(self, **kwargs): return client.score(row())
            provider = SimpleNamespace(resources=lambda: {'experimental_arm': ARMS[2], 'internal_arm': 'hybrid_safe'})
            qmodel, oldmodel = SimpleNamespace(make_model=lambda: None), SimpleNamespace(make_model=lambda: None)
            tools = SimpleNamespace(_v3_definition_index=SimpleNamespace(cache_clear=lambda: None))
            with patch.object(original_runner, '_load_cosil', return_value=(Base, qmodel, oldmodel, tools, RuntimeError)), \
                    patch.object(original_runner, 'make_agent_class', return_value=Agent), \
                    patch.object(original_runner.C, 'WORK', root), patch.object(original_runner.C, 'REPORTS', root), \
                    patch.object(client, 'request', side_effect=RuntimeError('Resident judge failed after forward')):
                result = original_runner.run_case(jobpath, output, provider=provider)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['error_type'], 'RuntimeError')
            self.assertEqual(result['experimental_arm'], ARMS[2])
            receipt = json.loads(next((output/'judge_rpc').glob('*_receipt.json')).read_text())
            self.assertEqual(receipt['usage_status'], 'unknown')
            self.assertIsNone(receipt['input_tokens'])


if __name__ == '__main__':
    unittest.main()
