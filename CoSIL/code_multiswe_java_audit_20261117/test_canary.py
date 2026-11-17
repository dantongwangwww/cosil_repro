"""Synthetic engineering contracts; no dataset, Gold, provider or GPU access."""
import json
from pathlib import Path
import tempfile
import unittest

from . import canary as a


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')


class CanaryAuditTests(unittest.TestCase):
    def request(self, **changes):
        return {'model': 'qwen3-8b', 'messages': [{'role': 'user', 'content': 'synthetic'}],
                'temperature': 0., 'seed': 0, 'max_tokens': 2048,
                'chat_template_kwargs': {'enable_thinking': False}, **changes}

    def response(self, **changes):
        return {'model': 'qwen3-8b', 'choices': [{'message': {'content': 'synthetic'}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 10}, **changes}

    def basic_run(self, root):
        rows = [{'instance_id': f'org__repo-{i}', 'repo': 'org/repo', 'base_commit': 'a' * 40}
                for i in range(128)]
        save(root / 'allocation.json', {'n': 128, 'records': rows})
        source = root / 'source.py'
        source.write_text('# synthetic execution source\n')
        save(root / 'execution_freeze.json', {'commit': 'f' * 40,
            'allocation_sha256': a.sha(root / 'allocation.json'),
            'files_sha256': {str(source): a.sha(source)}})
        return rows, source

    def test_no_terminal_never_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.basic_run(root)
            result = a.review(root)
            self.assertEqual(result['status'], 'PENDING')
            self.assertFalse(result['gold_read'])
            self.assertFalse(result['accuracy_used'])
            self.assertFalse(result['gate_written'])
            self.assertEqual(result['errors'], [])

    def test_code_drift_fails_even_while_canary_pending(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, source = self.basic_run(root)
            source.write_text('# changed\n')
            result = a.review(root)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any(e['code'] == 'execution_source_sha_changed' for e in result['errors']))

    def test_chat_requires_explicit_nonthinking_real_usage_and_model(self):
        errors = []
        a.check_chat(self.request(), self.response(), errors, 'synthetic')
        self.assertEqual(errors, [])
        a.check_chat(self.request(chat_template_kwargs={}), self.response(usage=None), errors, 'synthetic')
        self.assertEqual({e['code'] for e in errors}, {'thinking_not_explicitly_disabled',
                                                      'successful_response_usage_unknown'})
        errors = []
        a.check_chat(self.request(), self.response(choices=[{'message': {'reasoning_content': 'reasoning'}}]),
                     errors, 'synthetic')
        self.assertTrue(any(e['code'] == 'thinking_response_present' for e in errors))

    def test_locagent_requires_exact_three_tools_plus_finish(self):
        request = self.request(temperature=1., top_p=.8, repetition_penalty=1.05,
            max_completion_tokens=2048, parallel_tool_calls=False,
            tools=[{'function': {'name': n}} for n in sorted(a.TOOLS)])
        errors = []
        a.check_chat(request, self.response(), errors, 'synthetic', locagent=True)
        self.assertEqual(errors, [])
        request['tools'].pop()
        a.check_chat(request, self.response(), errors, 'synthetic', locagent=True)
        self.assertEqual(errors[0]['code'], 'locagent_tool_schema_drift')

    def test_numbered_source_requires_matching_base_line(self):
        index = {'src/Foo.java': {'text': 'class Foo {\n int run() { return 1; }\n}\n'}}
        errors = []
        evidence = a.locagent_source_witness('Found code in `src/Foo.java`.\n```\n2 |  int run() { return 1; }\n```',
                                             index, errors, 'synthetic')
        self.assertEqual(evidence['source_lines'], 1)
        self.assertEqual(errors, [])
        a.locagent_source_witness('Found code in `src/Foo.java`.\n2 | fabricated source', index, errors, 'synthetic')
        self.assertEqual(errors[0]['code'], 'locagent_numbered_source_differs_from_base')

    def test_skeleton_does_not_claim_complete_source_delivery(self):
        index = {'Foo.java': {'text': 'class Foo {}'}}
        errors = []
        evidence = a.locagent_source_witness('Just show the structure\n1 | class Foo // Foo [...]',
                                             index, errors, 'synthetic')
        self.assertTrue(evidence['skeleton_only'])
        self.assertEqual(evidence['source_lines'], 0)

    def test_raw_invalid_rank_and_overload_are_not_repaired(self):
        slots = a.raw_function_slots('```\nsrc/Foo.java\nfunction: Foo.run(int)\nclass: Foo\nfunction: Foo.run\n```')
        self.assertEqual(len(slots), 3)
        self.assertIsNone(slots[1]['qualified_name'])
        self.assertEqual(slots[2]['qualified_name'], 'Foo.run')

    def test_missing_source_delivery_cannot_be_claimed_from_event_alone(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = 'int run() { return 1; }'
            path = root / 'snapshot/Foo.java'
            path.parent.mkdir()
            path.write_text(source)
            definition = {'qualified_name': 'Foo.run()', 'kind': 'function',
                          'start_byte': 0, 'end_byte': len(source)}
            index = {'Foo.java': {'raw_sha256': a.sha(path), 'definitions': [definition]}}
            returned = '[Exact base source identity: Foo.java::Foo.run()]\n' + source
            record = {'source_id': 's1', 'path': 'Foo.java', 'qualified_name': 'Foo.run()',
                      'kind': 'function', 'text': returned, 'sha256': a.text_sha(returned),
                      'raw_source_text_sha256': a.text_sha(source), 'step': 0,
                      'arguments': ['Foo.java', 'Foo', 'run()']}
            save(root / 'result.json', {'raw_output': '', 'predicted_functions': []})
            save(root / 'worker_protocol.json', {'arm': 'baseline', 'cross_language_zero_shot': True,
                                               'train_or_recalibrate': False})
            save(root / 'context.json', {'retrieved_blocks': [record], 'accepted_source_ids': ['s1']})
            (root / 'events.jsonl').write_text(json.dumps({'event': 'judge_seen', 'source_id': 's1',
                'request_id': 'does-not-exist', 'recipient': 'main_judge'}) + '\n')
            errors, observations = [], []
            a.cosil_review(root, 'cosil', {'snapshot': str(root / 'snapshot')}, index, errors, observations)
            codes = {e['code'] for e in errors}
            self.assertIn('claimed_delivery_missing_actual_http_source', codes)
            self.assertIn('accepted_source_missing_search_delivery_chain', codes)


if __name__ == '__main__':
    unittest.main()
