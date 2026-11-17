import hashlib
import io
import json
import signal
import tempfile
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from code_v3b.tool_dispatch import DispatchError, ToolCall
from code_qwen3_rr4_rebench100.identity import Identities
from code_qwen3_rr4_rebench100.rpc import receive, request, validate_row
from code_qwen3_rr4_rebench100.service import Server
from code_qwen3_rr4_rebench100.deployment import stop_owned
from code_qwen3_rr4_rebench100 import config as P


def definition(name, owner=None, kind='function', line=1):
    return {'qualified_name': name, 'class_owner': owner, 'kind': kind, 'start_line': line}


def row():
    from code_v6.input_format import body, INPUT_VERSION
    values = {'issue': 'Public issue', 'function': 'def f():\n    return 1\n', 'neighbors': '[No neighbors]'}
    text = body(values['issue'], values['function'], values['neighbors'])
    return {**values, 'input_version': INPUT_VERSION, 'model_input': text,
            'input_sha256': hashlib.sha256(text.encode()).hexdigest()}


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.ids = Identities({'lib/pkg/a.py': {'definitions': [definition('f'), definition('Base.g', 'Base'), definition('C', kind='class')]},
                               'pkg/b.py': {'definitions': [definition('h')]},
                               'other.py': {'definitions': [definition('Other.__eq__', 'Other')]}})

    def test_unique_layout_prefix_is_resolved(self):
        self.assertEqual(self.ids.path('pkg/a.py'), 'lib/pkg/a.py')
        self.assertEqual(self.ids.path('./lib/pkg/a.py'), 'lib/pkg/a.py')
        self.assertEqual(self.ids.path('lib\\pkg\\a.py'), 'lib/pkg/a.py')

    def test_ambiguous_prefix_rejected(self):
        ids = Identities({'lib/pkg/a.py': {'definitions': []}, 'src/pkg/a.py': {'definitions': []}})
        with self.assertRaises(DispatchError):
            ids.path('pkg/a.py')

    def test_no_basename_or_fuzzy_guess(self):
        for value in ['a.py', 'pkg/aa.py', '../pkg/a.py', '/lib/pkg/a.py', 'C:\\pkg\\a.py']:
            with self.subTest(value=value), self.assertRaises(DispatchError):
                self.ids.path(value)

    def test_wrong_owner_is_help_not_automatic_execution(self):
        call = ToolCall('get_code_of_class_function', ('lib/pkg/a.py', 'Wrong', 'f'), 'get_code_of_class_function')
        self.assertEqual(self.ids.call(call), call)
        help_text = self.ids.guidance(call)
        self.assertIn("get_code_of_file_function('lib/pkg/a.py', 'f')", help_text)
        self.assertIn('Nothing was executed', help_text)

    def test_inherited_method_suggests_real_owner(self):
        call = ToolCall('get_code_of_class_function', ('lib/pkg/a.py', 'Sub', 'g'), 'get_code_of_class_function')
        self.assertIn("'Base', 'g'", self.ids.guidance(call))

    def test_missing_new_method_does_not_suggest_other_classes_dunder(self):
        call = ToolCall('get_code_of_class_function', ('lib/pkg/a.py', 'C', '__eq__'), 'get_code_of_class_function')
        help_text = self.ids.guidance(call)
        self.assertIn("get_code_of_class('lib/pkg/a.py', 'C')", help_text)
        self.assertNotIn('Other', help_text)

    def test_imported_module_symbol_has_inventory_help(self):
        call = ToolCall('get_code_of_file_function', ('lib/pkg/a.py', 'h'), 'get_code_of_file_function')
        self.assertIn("get_code_of_file_function('pkg/b.py', 'h')", self.ids.guidance(call))

    def test_exact_identity_needs_no_help(self):
        call = ToolCall('get_code_of_class_function', ('lib/pkg/a.py', 'Base', 'g'), 'get_code_of_class_function')
        self.assertIsNone(self.ids.guidance(call))


class ProtocolTests(unittest.TestCase):
    def test_semantic_and_sha_drift_rejected(self):
        value = row(); self.assertEqual(validate_row(value), value)
        for field in ['function', 'model_input', 'input_sha256']:
            bad = {**value, field: value[field] + 'changed'}
            with self.assertRaises(ValueError):
                validate_row(bad)

    def test_private_fields_rejected(self):
        for key in ['label', 'gold', 'test_patch', 'checkpoint_metrics']:
            with self.assertRaises(ValueError):
                validate_row({**row(), key: True})

    def test_truncated_and_oversized_frames_rejected(self):
        with self.assertRaises(ValueError):
            receive(io.BytesIO(b'{}'))
        with self.assertRaises(ValueError):
            receive(io.BytesIO(b'x' * (1024 * 1024 + 2)))

    def test_one_scorer_handles_multiple_tasks(self):
        class Fake:
            load_seconds = .1
            count = 0
            def score(self, value):
                self.count += 1
                return {'p_yes': .95, 'input_tokens': 20, 'latency_seconds': .01}
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            path = Path(tmp) / 's.sock'; scorer = Fake()
            with Server(path, scorer, tmp) as server:
                def loop():
                    while not server.stopping:
                        server.handle_request()
                thread = threading.Thread(target=loop); thread.start()
                try:
                    first = request('score', row(), socket_path=path)
                    second = request('score', row(), socket_path=path)
                    self.assertEqual(first['score_sequence'], 1)
                    self.assertEqual(second['score_sequence'], 2)
                    self.assertEqual(scorer.count, 2)
                    self.assertEqual(request('health', socket_path=path)['model_load_count'], 1)
                finally:
                    request('shutdown', socket_path=path); thread.join(timeout=2)
                self.assertFalse(thread.is_alive())


class ShutdownTests(unittest.TestCase):
    def saved(self):
        return {'pid': 42, 'uid': 1011, 'state': 'R', 'process_group': 42, 'session_id': 42,
                'start_ticks': 99, 'argv': ['owned'], 'cwd': '/owned'}

    def setup_service(self, root, identity, assert_identity):
        (root / 'ownership.json').write_text(json.dumps({'identity': self.saved()}))
        return SimpleNamespace(SERVICE=root, identity=identity, assert_identity=assert_identity)

    def test_exit_cleanup_does_not_require_mutable_argv(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root = Path(tmp)
            D = self.setup_service(root, lambda pid: self.saved(), lambda a, b: None)
            alive = {k: v for k, v in self.saved().items() if k not in ['argv', 'cwd']}
            with patch.object(P, 'OUT', root), patch('os.killpg') as kill, patch('time.sleep'), \
                 patch('code_qwen3_rr4_rebench100.deployment.stable_identity', side_effect=[alive, FileNotFoundError()]):
                receipt = stop_owned(D)
                self.assertTrue(receipt['leader_exited'])
                kill.assert_called_once_with(42, signal.SIGTERM)

    def test_pid_reuse_never_gets_a_second_signal(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root = Path(tmp); D = self.setup_service(root, lambda pid: self.saved(), lambda a, b: None)
            reused = {**self.saved(), 'start_ticks': 100, 'uid': 5000}
            with patch.object(P, 'OUT', root), patch('os.killpg') as kill, \
                 patch('code_qwen3_rr4_rebench100.deployment.stable_identity', return_value=reused):
                self.assertTrue(stop_owned(D)['leader_exited']); self.assertEqual(kill.call_count, 1)

    def test_wrong_pre_signal_owner_is_never_terminated(self):
        def reject(a, b):
            raise RuntimeError('Wrong owner')
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root = Path(tmp); D = self.setup_service(root, lambda pid: self.saved(), reject)
            with patch.object(P, 'OUT', root), patch('os.killpg') as kill:
                with self.assertRaises(RuntimeError):
                    stop_owned(D)
                kill.assert_not_called()


class IsolationTests(unittest.TestCase):
    def test_hidden_paths_check_reads_no_contents(self):
        from code_qwen3_rr4_rebench100.privacy import assert_hidden
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            self.assertEqual(assert_hidden([Path(tmp) / 'not-mounted']), 1)

    def test_visible_private_checkpoint_is_rejected(self):
        from code_qwen3_rr4_rebench100.privacy import assert_hidden
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            path = Path(tmp) / 'private.json'; path.write_text('secret-evaluation-data')
            with self.assertRaises(PermissionError), patch.object(Path, 'read_text', side_effect=AssertionError('No content reads')):
                assert_hidden([path])

    def test_cpu_worker_cannot_access_gpu_or_private_adapter_metrics(self):
        from code_qwen3_rr4_rebench100.run import argv
        from code_rebench_qwen import common as C
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root = Path(tmp); inp = root / 'inputs'; inp.mkdir()
            job = inp / 'job.json'
            job.write_text(json.dumps({'instance_id': 'a__a-1', 'repo': 'a/a', 'base_commit': 'b' * 40,
                'problem_statement': 'issue', 'cohort': 'c', 'snapshot': str(root / 'source'),
                'paths': ['a.py'], 'code_index': str(inp / 'index.json'), 'structure': str(inp / 'structure.json')}))
            record = {'job': str(job), 'cache': str(inp / 'cache.json'), 'cache_sha256': 'hash'}
            with patch.object(C, 'INPUTS', inp), patch.object(C, 'RUN', root / 'run'):
                args, env = argv(record, root / 'run/hybrid', 'hybrid_safe', root / 'shared.json')
            self.assertEqual(env['CUDA_VISIBLE_DEVICES'], '')
            self.assertNotIn('--dev-bind', args)
            self.assertNotIn(str(P.CHECKPOINT), args)
            self.assertNotIn(str(P.OUT / 'evaluation_private.json'), args)
            self.assertNotIn(str(P.OUT / 'score_smoke_private.json'), args)


class IntegrationTests(unittest.TestCase):
    def make_agent(self, arm):
        from code_qwen3_rr4_rebench100.worker import agent_factory
        class Base:
            def _prune(self, *args):return 'MAIN'
        class Parent(Base):
            def __init__(self):
                self.events=[];self.sources=[];self.accepted_ids=[];self.problem_statement='Public issue'
            def _parse_top5_file(self, content):return ['pkg/a.py','lib/pkg/a.py','a.py']
            def _execute(self, call):return 'EXECUTED'
        index={'lib/pkg/a.py':{'definitions':[definition('f')]}}
        return agent_factory(lambda *args: Parent,arm,{'low':.1,'high':.9},None,'cache','sha')(
            Base,{'instance_id':'a__a-1','base_commit':'a'*40},index,None,None,DispatchError)()

    def test_actual_agent_normalizes_menu_and_tool_path_without_guessing_basename(self):
        from code_v3b import fixed_search
        with patch.object(fixed_search,'parse_tool_call',fixed_search.parse_tool_call):
            agent=self.make_agent('baseline')
            self.assertEqual(agent._parse_top5_file('unused'),['lib/pkg/a.py'])
            call=fixed_search.parse_tool_call("get_code_of_file_function('pkg/a.py', 'f')")
            self.assertEqual(call.arguments,('lib/pkg/a.py','f'))
            self.assertTrue(any(e['event']=='file_identity_error' for e in agent.events))

    def test_actual_agent_requires_model_to_choose_corrected_owner(self):
        from code_v3b import fixed_search
        with patch.object(fixed_search,'parse_tool_call',fixed_search.parse_tool_call):
            agent=self.make_agent('baseline');agent.current_step=0
            bad=ToolCall('get_code_of_class_function',('lib/pkg/a.py','Wrong','f'),'get_code_of_class_function')
            with self.assertRaises(DispatchError):agent._execute(bad)
            good=ToolCall('get_code_of_file_function',('lib/pkg/a.py','f'),'get_code_of_file_function')
            self.assertEqual(agent._execute(good),'EXECUTED')
            self.assertTrue(any(e['event']=='tool_identity_help' for e in agent.events))

    def test_actual_agent_retains_or_delegates_using_resident_score(self):
        from code_v3b import fixed_search
        call=ToolCall('get_code_of_file_function',('lib/pkg/a.py','f'),'get_code_of_file_function')
        rendered={**row(),'function_id':'lib/pkg/a.py::f@1','source_sha256':'s',
                  'token_budget_trimmed':False,'neighbors_selected':0}
        with patch.object(fixed_search,'parse_tool_call',fixed_search.parse_tool_call):
            for probability,expected in [(.95,'True'),(.5,'MAIN'),(.01,'False')]:
                agent=self.make_agent('hybrid_safe')
                agent.renderer=SimpleNamespace(render=lambda *args:rendered)
                with patch('code_qwen3_rr4_rebench100.worker.Client') as client:
                    client.return_value.score.return_value={'p_yes':probability,'input_tokens':10}
                    self.assertEqual(agent._prune(None,call,'tool','code',0),expected)

    def test_lazy_source_change_is_detected(self):
        from code_qwen3_rr4_rebench100.render_cache import Sources
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root = Path(tmp); file = root / 'a.py'; raw = b'def f():\n    return 1\n'; file.write_bytes(raw)
            index = {'a.py': {'raw_sha256': hashlib.sha256(raw).hexdigest()}}
            source = Sources({'snapshot': tmp}, index)
            self.assertEqual(source['a.py'], raw.decode())
            file.write_text('modified')
            with self.assertRaises(ValueError):
                Sources({'snapshot': tmp}, index)['a.py']

    def test_final_prediction_paths_and_owners_are_never_fixed(self):
        from code_rebench_qwen.runner import raw_functions
        raw = '```\npkg/a.py\nfunction: Wrong.f\n```'
        self.assertEqual(raw_functions(raw)[0]['path'], 'pkg/a.py')
        self.assertEqual(raw_functions(raw)[0]['qualified_name'], 'Wrong.f')

    def test_cache_wrong_provenance_is_rejected_before_tokenizer_loading(self):
        from code_qwen3_rr4_rebench100.render_cache import Renderer
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            file = Path(tmp) / 'cache.json'; file.write_text('{}')
            with self.assertRaises(ValueError), patch('code_qwen3_rr4_rebench100.render_cache.tokenizers') as tokenizer:
                Renderer({'base_commit': 'a'}, file, 'wrong-sha')
            tokenizer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
