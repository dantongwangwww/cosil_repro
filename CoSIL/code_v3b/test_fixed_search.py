"""Offline regression checks: no model service or benchmark run is started."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v3b.tool_dispatch import DispatchError, parse_tool_call, parse_verdict
from code_v3b.gen_annotations_300 import prepare_function_source
from code_v3b import FL_tools_注入版 as node_tools
from code_v3b import fixed_search


class DispatchTests(unittest.TestCase):
    def test_prefix_fences_and_trailing_explanation(self):
        text = "**Call 1:**\n```python\nget_code_of_file_function('a.py', 'foo')\n```\nThis retrieves code."
        call = parse_tool_call(text)
        self.assertEqual((call.name, call.arguments), ('get_code_of_file_function', ('a.py', 'foo')))

    def test_first_call_is_not_greedy(self):
        call = parse_tool_call("get_code_of_file_function('a.py', 'foo')\nget_code_of_file_function('b.py', 'bar')")
        self.assertEqual(call.arguments, ('a.py', 'foo'))

    def test_keywords_and_parentheses_inside_strings(self):
        call = parse_tool_call("get_code_of_file_function(func_name='foo(x,y)', file_name='a.py')")
        self.assertEqual(call.arguments, ('a.py', 'foo(x,y)'))

    def test_known_static_alias(self):
        self.assertEqual(parse_tool_call("get_code_of_static_function('a.py', 'foo')").name,
                         'get_code_of_file_function')

    def test_exit_has_a_distinct_meaning(self):
        self.assertEqual(parse_tool_call('```python\nexit()\n```').name, 'exit')

    def test_invalid_arguments_are_not_executed(self):
        with self.assertRaises(DispatchError):
            parse_tool_call("get_code_of_file_function(__import__('os').getcwd(), 'foo')")
        with self.assertRaises(DispatchError):
            parse_tool_call("get_code_of_file_function(file_name='a.py', unknown='foo')")

    def test_verdicts_and_ambiguity(self):
        for text in ['True', 'Verdict: True', '```True```', '```\nTrue\n```']:
            self.assertEqual(parse_verdict(text), 'True')
        self.assertEqual(parse_verdict('Decision: false'), 'False')
        self.assertEqual(parse_verdict('No verdict'), '')
        self.assertEqual(parse_verdict('True\nFalse'), '')


class NodeTests(unittest.TestCase):
    def setUp(self):
        self.definitions = ([], [
            {'file': 'a.py', 'name': 'C', 'methods': [{'name': 'a_method'}]},
            {'file': 'b.py', 'name': 'C', 'methods': [{'name': 'b_method'}]}],
            [{'file': 'a.py', 'name': 'foo'}, {'file': 'a.py', 'name': 'bar'}])
        self.annotations = {('a.py', 'foo'): '功能甲', ('a.py', 'bar'): '功能乙',
                            ('a.py', 'C.a_method'): '方法甲'}
        self.shuffled = {('a.py', 'foo'): '功能乙', ('a.py', 'bar'): '功能甲',
                         ('a.py', 'C.a_method'): '方法甲'}

    def test_description_is_a_field_and_name_is_constant(self):
        with patch.object(node_tools, '_v3_definition_index', return_value=self.definitions), \
             patch.object(node_tools, '_v3_annotations', return_value=(self.annotations, self.shuffled)):
            results = {}
            for arm in ('off', 'on', 'shuffled'):
                with patch.dict(os.environ, {'NODE_ANNOTATION': arm}):
                    results[arm] = node_tools.get_function_node_catalog(['a.py'], 'fixture')[0]
            self.assertEqual([n['name'] for n in results['off']['static_functions']], ['foo', 'bar'])
            self.assertNotIn('description', results['off']['static_functions'][0])
            self.assertEqual(results['on']['static_functions'][0], {'name': 'foo', 'description': '功能甲'})
            self.assertEqual(results['shuffled']['static_functions'][0]['description'], '功能乙')
            self.assertEqual(results['on']['class_functions'][0]['functions'][0]['name'], 'a_method')
            self.assertNotIn('b_method', json.dumps(results['on']))

    def test_long_docstring_does_not_hide_body(self):
        source = 'def double(x):\n    """' + '文档说明' * 400 + '"""\n    return x * 2'
        prepared = prepare_function_source(source)
        self.assertIn('return x * 2', prepared)
        self.assertLess(len(prepared), 100)


class FakeModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def codegen(self, messages, num_samples=1):
        self.calls.append(copy.deepcopy(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return [{'response': response, 'usage': {'prompt_tokens': 20, 'completion_tokens': 5}}]


class SearchTests(unittest.TestCase):
    def run_search(self, verdict, arm='off', planner_note=''):
        body = 'def foo(x):\n    # UNIQUE_IMPLEMENTATION_BODY\n    return x * 2'
        responses = ['I will inspect foo.',
            planner_note + "**Call 1:**\n```python\nget_code_of_file_function(file_name='a.py', func_name='foo')\n```",
            verdict, 'exit()', '```\na.py\nfunction: foo\n```']
        model = FakeModel(responses)
        with tempfile.TemporaryDirectory(prefix='cosil-fixed-test-') as directory:
            nodes = [{'name': 'foo'}]
            if arm != 'off':
                nodes[0]['description'] = 'Qwen_FUNCTION_DESCRIPTION' if arm == 'on' else 'WRONG_DESCRIPTION'
            with patch.dict(os.environ, {'NODE_ANNOTATION': arm, 'V3B_LOG_DIR': directory}), \
                 patch.object(fixed_search, 'get_function_node_catalog', return_value=[
                    {'file': 'a.py', 'classes': [], 'static_functions': nodes, 'class_functions': []}]), \
                 patch.object(fixed_search, 'get_code_of_file_function', return_value=body), \
                 patch.object(fixed_search.AFL, '_count_tokens', return_value=100), \
                 patch('code_v3b.qwen_model.make_model', return_value=model):
                import logging
                agent = fixed_search.AFL('fixture', {}, 'double produces the wrong value',
                                        'llama3', 'openai', logging.getLogger('offline-test'))
                locations, _, _ = agent.localize_with_p(file=['a.py'])
                events = [json.loads(line) for line in (Path(directory) / f'{arm}_fixture.jsonl').read_text().splitlines()]
        return model, locations, events

    def test_actual_pruning_entry_uses_fixed_dispatch(self):
        model, locations, events = self.run_search('Verdict: True')
        self.assertEqual(locations['a.py'], ['function: foo'])
        self.assertEqual([e['event'] for e in events].count('tool_result'), 1)
        self.assertTrue(any(e['event'] == 'context_accept' for e in events))
        self.assertIn('UNIQUE_IMPLEMENTATION_BODY', str(model.calls[-1]))
        self.assertTrue(any(e['event'] == 'explicit_exit' for e in events))

    def test_rejected_code_is_excluded_from_search_context(self):
        model, _, events = self.run_search('False')
        self.assertIn('UNIQUE_IMPLEMENTATION_BODY', str(model.calls[2]))  # pruner sees source
        self.assertNotIn('UNIQUE_IMPLEMENTATION_BODY', str(model.calls[-1]))  # main search does not
        self.assertTrue(any(e['event'] == 'context_reject' for e in events))

    def test_arm_metadata_reaches_searcher_but_not_pruner(self):
        for arm in ('off', 'on', 'shuffled'):
            model, _, events = self.run_search('True', arm=arm, planner_note='PLANNER_ONLY_REASON\n')
            initial = str(model.calls[0])
            self.assertEqual('"description"' in initial, arm != 'off')
            pruner = str(model.calls[2])
            self.assertNotIn('Qwen_FUNCTION_DESCRIPTION', pruner)
            self.assertNotIn('WRONG_DESCRIPTION', pruner)
            self.assertNotIn('PLANNER_ONLY_REASON', pruner)
            call = next(e for e in events if e['event'] == 'tool_call')
            self.assertEqual(call['arguments'], ['a.py', 'foo'])

    def test_empty_service_reply_is_a_failure(self):
        model = FakeModel([''])
        with tempfile.TemporaryDirectory(prefix='cosil-empty-test-') as directory, \
             patch.dict(os.environ, {'V3B_LOG_DIR': directory}), \
             patch.object(fixed_search.AFL, '_count_tokens', return_value=10):
            import logging
            agent = fixed_search.AFL('fixture', {}, 'issue', 'llama3', 'openai', logging.getLogger('offline-test'))
            with self.assertRaises(RuntimeError):
                agent._query(model, [{'role': 'user', 'content': 'query'}], 'node_selection')

    def test_api_failure_cannot_reuse_a_stale_response(self):
        model = FakeModel([RuntimeError('simulated transport failure')])
        with tempfile.TemporaryDirectory(prefix='cosil-api-test-') as directory, \
             patch.dict(os.environ, {'V3B_LOG_DIR': directory}), \
             patch.object(fixed_search.AFL, '_count_tokens', return_value=10):
            import logging
            agent = fixed_search.AFL('fixture', {}, 'issue', 'llama3', 'openai', logging.getLogger('offline-test'))
            with self.assertRaises(RuntimeError):
                agent._query(model, [{'role': 'user', 'content': 'query'}], 'node_selection')
            self.assertEqual(len(model.calls), 1)

    def test_context_budget_is_enforced_before_query(self):
        model = FakeModel([])
        with tempfile.TemporaryDirectory(prefix='cosil-budget-test-') as directory, \
             patch.dict(os.environ, {'V3B_LOG_DIR': directory}), \
             patch.object(fixed_search.AFL, '_count_tokens', return_value=65000):
            import logging
            agent = fixed_search.AFL('fixture', {}, 'issue', 'llama3', 'openai', logging.getLogger('offline-test'))
            with self.assertRaises(fixed_search.ContextBudgetError):
                agent._query(model, [{'role': 'user', 'content': 'query'}], 'node_selection')
            self.assertEqual(model.calls, [])

    def test_token_counter_counts_ids_not_encoding_dictionary_keys(self):
        class Tokenizer:
            def apply_chat_template(self, *args, **kwargs):
                return {'input_ids': list(range(50)), 'attention_mask': [1] * 50}
        import logging
        with patch.object(fixed_search, 'qwen_tokenizer', return_value=Tokenizer()):
            agent = fixed_search.AFL('fixture', {}, 'issue', 'llama3', 'openai', logging.getLogger('offline-test'))
            self.assertEqual(agent._count_tokens([{'role': 'user', 'content': 'test'}]), 50)


if __name__ == '__main__':
    unittest.main()
