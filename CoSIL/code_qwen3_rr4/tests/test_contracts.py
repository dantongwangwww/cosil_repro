import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_qwen3_rr4 import config as P
from code_qwen3_rr4.report import evaluate, paired, usage
from code_qwen3_rr4.run import eligible, worker_argv
from code_qwen3_rr4.worker import agent_factory


class Routing(unittest.TestCase):
    def test_threshold_boundaries(self):
        low = .12947567721292427
        self.assertEqual(P.route(low, low), 'reject')
        self.assertEqual(P.route(math.nextafter(low, math.inf), low), 'qwen')
        self.assertEqual(P.route(.9, low), 'retain')
        self.assertEqual(P.route(math.nextafter(.9, 0.), low), 'qwen')

    def test_invalid_probabilities_fail_closed(self):
        for value in [float('nan'), float('inf'), -.01, 1.01]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                P.route(value, .1)
        for low in [.9, 1., -.1]:
            with self.assertRaises(ValueError):
                P.route(.5, low)


class Evaluation(unittest.TestCase):
    def setUp(self):
        self.gold = {'gold_functions_by_file': {'x.py': ['C.f']}}

    def test_invalid_slots_are_not_compressed(self):
        result = {'predicted_functions': [{'path': 'x.py', 'qualified_name': None}]*5 + [{'path': 'x.py', 'qualified_name': 'C.f'}]}
        self.assertFalse(evaluate(result, self.gold)['function_top5'])

    def test_qualified_name_and_path_are_strict(self):
        for path, name in [('x.py', 'f'), ('wrong.py', 'C.f')]:
            self.assertFalse(evaluate({'predicted_functions': [{'path': path, 'qualified_name': name}]}, self.gold)['function_top5'])
        self.assertTrue(evaluate({'predicted_functions': [{'path': 'x.py', 'qualified_name': 'C.f'}]}, self.gold)['function_top5'])

    def test_duplicate_predictions_do_not_inflate_recall(self):
        gold = {'gold_functions_by_file': {'x.py': ['C.f', 'C.g']}}
        got = evaluate({'predicted_functions': [{'path': 'x.py', 'qualified_name': 'C.f'}]*5}, gold)
        self.assertEqual(got['recall5'], .5)
        self.assertFalse(got['all_coverage5'])

    def test_exact_paired_discordants(self):
        got = paired([True, True, False], [True, False, True])
        self.assertEqual(got['only_baseline'], 1); self.assertEqual(got['only_hybrid'], 1)
        self.assertEqual(got['delta'], 0); self.assertEqual(got['mcnemar_exact_p'], 1)
        self.assertFalse(got['noninferiority_certified'])

    def test_zero_pairs_remain_unknown(self):
        self.assertIsNone(paired([], [])['delta'])
        with self.assertRaises(ValueError):
            paired([True], [])

    def test_file_cost_is_separate_from_function_cost(self):
        result = {'stage_resources': {'file_initial': {'known_prompt_tokens': 10, 'known_completion_tokens': 2, 'usage_unknown_attempts': 0},
                   'pruner': {'known_prompt_tokens': 20, 'known_completion_tokens': 1, 'usage_unknown_attempts': 1}}}
        self.assertEqual(usage(result, 'file_'), {'prompt': 10, 'completion': 2, 'unknown': 0})
        self.assertEqual(usage(result)['unknown'], 1)


class Isolation(unittest.TestCase):
    def test_shared_model_reuse_preserves_historical_output_guard(self):
        from code_rebench_qwen import common as C
        from code_rebench_qwen import deploy as D
        from code_qwen3_rr4.deployment import adapt
        guard = D.owned_path
        original = D.verify_model
        with patch.dict(C.__dict__, C.__dict__.copy()):
            try:
                got = adapt()
                self.assertIs(got.owned_path, guard)
                self.assertIsNot(got.verify_model, original)
            finally:
                D.verify_model = original

    def test_busy_or_underprovisioned_gpu_is_never_selected(self):
        rows = [{'index': i, 'has_compute_process': busy, 'free_mib': free, 'utilization': util}
                for i, busy, free, util in [(0, True, 24000, 0), (1, False, 10000, 0), (2, False, 24000, 90), (3, False, 24000, 0)]]
        self.assertEqual(eligible(rows), [3])

    def test_bwrap_mounts_adapter_files_without_training_sidecars(self):
        from code_rebench_qwen import common as C
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root = Path(tmp); inp = root/'inputs'; inp.mkdir(); run = root/'run'
            job = inp/'job.json'
            job.write_text(json.dumps({'instance_id': 'x__x-1', 'repo': 'x/x', 'base_commit': 'a'*40,
                'problem_statement': 'public issue', 'cohort': 'canary', 'snapshot': str(root/'snapshot'),
                'paths': ['x.py'], 'code_index': str(inp/'index.json'), 'structure': str(inp/'structure.json')}))
            with patch.object(C, 'INPUTS', inp), patch.object(C, 'RUN', run):
                args, env = worker_argv(job, run/'hybrid', 'hybrid_safe', 2, shared=root/'shared.json')
            self.assertIn(str(P.CHECKPOINT/'adapter_model.safetensors'), args)
            self.assertIn(str(P.CHECKPOINT/'adapter_config.json'), args)
            self.assertNotIn(str(P.CHECKPOINT), args)
            self.assertFalse(any('pruner_val.jsonl' in a or 'checkpoint_complete.json' in a or 'ground_truth' in a for a in args))
            self.assertEqual(env['CUDA_VISIBLE_DEVICES'], '2')
            self.assertFalse(any('API_KEY' in k or 'DEEPSEEK' in k for k in env))


class AgentIntegration(unittest.TestCase):
    def parent(self):
        class Parent:
            def __init__(self):
                self.events = []; self.sources = []; self.accepted_ids = []; self.problem_statement = 'issue'
            def _record_event(self, name, **fields):
                self.events.append({'event': name, **fields})
            def _prune(self, *args):
                return 'MAIN'
            def file_localize_with_g(self, *args, **kwargs):
                return ['original.py'], '', ''
        return Parent

    def make(self, arm, shared=None):
        return agent_factory(lambda *a: self.parent(), arm, {'low': .1, 'high': .9}, shared)(None,
            {'instance_id': 'x__x-1', 'base_commit': 'a'*40}, {}, None, None, ValueError)()

    def test_baseline_uses_original_pruner(self):
        agent = self.make('baseline')
        self.assertEqual(agent._prune(None, None, '', '', 0), 'MAIN')

    def test_raw_event_arm_and_source_delivery_are_preserved(self):
        agent = self.make('hybrid_safe')
        agent.sources = [{'step': 1, 'tool': 'read', 'arguments': ['x.py'], 'source_id': 's0'}]
        agent._record_event('tool_call', step=1)
        agent._record_event('context_accept', step=1, tool='read', arguments=['x.py'])
        self.assertEqual(agent.current_step, 1)
        self.assertEqual(agent.accepted_ids, ['s0'])
        self.assertEqual(agent.events[-1]['arm'], 'hybrid_safe')
        self.assertEqual(agent.events[-1]['annotation'], 'off')

    def test_classes_always_use_main_model(self):
        from types import SimpleNamespace
        agent = self.make('hybrid_safe')
        call = SimpleNamespace(name='get_code_of_class')
        self.assertEqual(agent._prune(None, call, '', '', 0), 'MAIN')
        self.assertEqual(agent.events[0]['event'], 'pruner_class_fallback')

    def test_shared_file_stage_is_exact_and_has_no_new_model_call(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            shared = Path(tmp)/'shared.json'
            shared.write_text(json.dumps({'instance_id': 'x__x-1', 'base_commit': 'a'*40,
                'files': ['public.py'], 'raw_file_responses': [{'stage': 'file_initial', 'response': 'public.py'}]}))
            agent = self.make('hybrid_safe', shared)
            self.assertEqual(agent.file_localize_with_g()[0], ['public.py'])
            self.assertEqual(agent.events[0]['new_file_model_calls'], 0)
            data = json.loads(shared.read_text()); data['base_commit'] = 'b'*40; shared.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                agent.file_localize_with_g()

    def test_local_routes_and_unknown_binding_fallback(self):
        from types import SimpleNamespace
        call = SimpleNamespace(name='get_code_of_file_function', arguments=['x.py', 'f'])
        row = {'function_id': 'x.py::f@1', 'input_sha256': 'i', 'source_sha256': 's', 'input_version': 'v6',
               'model_input': 'public', 'token_budget_trimmed': False, 'neighbors_selected': 0}
        for p, expected in [(0.01, 'False'), (.5, 'MAIN'), (.99, 'True')]:
            agent = self.make('hybrid_safe')
            agent._judge = SimpleNamespace(renderer=SimpleNamespace(render=lambda *a: row), score=lambda row: {'p_yes': p, 'input_tokens': 7})
            self.assertEqual(agent._prune(None, call, 'f', 'def f(): pass', 0), expected)
        agent = self.make('hybrid_safe')
        def ambiguous(*args):
            raise ValueError('ambiguous overload')
        agent._judge = SimpleNamespace(renderer=SimpleNamespace(render=ambiguous))
        self.assertEqual(agent._prune(None, call, '', '', 0), 'MAIN')
        self.assertEqual(agent.events[0]['event'], 'judge_binding_fallback')


if __name__ == '__main__':
    unittest.main()
