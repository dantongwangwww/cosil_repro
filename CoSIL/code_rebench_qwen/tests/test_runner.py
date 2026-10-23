"""CPU-only fixtures: no transformers download, service, benchmark labels or API."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from code_rebench_qwen import common as C
from code_rebench_qwen.local_provider import LocalProvider, count_tokens, effective_messages
from code_rebench_qwen import runner as R


class Tokenizer:
    def __init__(self):
        self.kwargs = None

    def apply_chat_template(self, messages, **kwargs):
        self.kwargs = kwargs
        return [1, 2, 3]


class Response:
    def __init__(self, content='answer'):
        self.content = content

    def model_dump(self, **kwargs):
        return dict(id='local-1', model=C.SERVED_MODEL,
            choices=[dict(message=dict(content=self.content), finish_reason='stop')],
            usage=dict(prompt_tokens=3, completion_tokens=2, total_tokens=5))


class Client:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.requests = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cosil-runner-test-')
        self.root = Path(self.tmp.name)
        self.work = patch.object(C, 'WORK', self.root)
        self.work.start()

    def tearDown(self):
        self.work.stop()
        self.tmp.cleanup()

    def provider(self, responses):
        self.client = Client(responses)
        return LocalProvider(self.root/'out', tokenizer=Tokenizer(), client=self.client)

    def job(self):
        snapshot = self.root/'snapshot'
        snapshot.mkdir()
        text = 'class C:\r\n    @property\r\n    def x(self): return 1\r\n    @x.setter\r\n    def x(self, v): pass\r\n'
        (snapshot/'m.py').write_bytes(text.encode())
        defs = [dict(kind='class', qualified_name='C', start_line=1, end_line=5),
                dict(kind='function', qualified_name='C.x', start_line=2, end_line=3),
                dict(kind='function', qualified_name='C.x', start_line=4, end_line=5)]
        index = {'m.py': dict(definitions=defs, sha256=C.digest(text), raw_sha256=C.digest(text.encode()))}
        job = dict(instance_id='repo__case-1', repo='owner/repo', base_commit='a'*40,
            problem_statement='owner/repo regression', cohort='synthetic', snapshot=str(snapshot),
            paths=['m.py'], code_index=str(self.root/'index.json'),
            structure=str(self.root/'repo_structures/repo__case-1.json'))
        C.write(job['code_index'], index)
        C.write(job['structure'], dict(structure={}))
        C.write(self.root/'job.json', job)
        return job, index

    def test_template_and_wire_are_nonthinking_seeded_greedy(self):
        p = self.provider([Response()])
        messages = effective_messages([dict(role='user', content='issue')])
        p.ask(messages, 'initial_selection')
        request = self.client.requests[0]
        self.assertEqual(request['seed'], 0)
        self.assertEqual(request['temperature'], 0.)
        self.assertEqual(request['model'], 'qwen3-8b')
        self.assertEqual(request['max_tokens'], 2048)
        self.assertEqual(request['extra_body'], {'chat_template_kwargs': {'enable_thinking': False}})
        self.assertEqual(p.tokenizer.kwargs['enable_thinking'], False)
        self.assertEqual(p.resources()['prompt_tokens'], 3)
        self.assertTrue((self.root/'out/calls/0001_initial_selection/attempt_0_response.json').exists())

    def test_context_guard_before_request(self):
        p = self.provider([])
        with patch.object(p, 'count', return_value=64000):
            with self.assertRaisesRegex(RuntimeError, 'exceeds'):
                p.ask([], 'node_selection')
        self.assertEqual(self.client.requests, [])
        self.assertEqual(p.sequence, 0)

    def test_explicit_transient_attempts_reuse_identical_request(self):
        error = type('APITimeoutError', (Exception,), {})('timeout')
        p = self.provider([error, Response()])
        with patch('code_rebench_qwen.local_provider.time.sleep'):
            p.ask([], 'pruner_format_retry')
        self.assertEqual(len(self.client.requests), 2)
        self.assertEqual(self.client.requests[0], self.client.requests[1])
        self.assertEqual(p.resources()['http_attempts'], 2)
        self.assertIsNone(p.resources()['prompt_tokens'])
        self.assertEqual(p.resources()['known_prompt_tokens'], 3)
        self.assertEqual(p.resources()['usage_unknown_attempts'], 1)
        self.assertTrue(p.records[-1]['semantic_retry'])

    def test_empty_answer_is_preserved_without_semantic_retry(self):
        p = self.provider([Response('')])
        with self.assertRaisesRegex(ValueError, 'empty'):
            p.ask([], 'final_summary')
        self.assertEqual(len(self.client.requests), 1)
        self.assertEqual(p.resources()['stage_resources']['final_summary']['successful_responses'], 1)

    def test_reasoning_response_is_saved_then_stops_without_retry(self):
        class ThinkingResponse(Response):
            def model_dump(self, **kwargs):
                raw = super().model_dump(**kwargs)
                raw['choices'][0]['message']['reasoning_content'] = 'unexpected reasoning'
                return raw
        p = self.provider([ThinkingResponse()])
        with self.assertRaisesRegex(ValueError, 'Nonthinking contract violated'):
            p.ask([], 'initial_selection')
        self.assertEqual(len(self.client.requests), 1)
        receipt = C.read(self.root/'out/calls/0001_initial_selection/attempt_0_receipt.json')
        self.assertTrue(receipt['reasoning_content_present'])
        raw = C.read(self.root/'out/calls/0001_initial_selection/attempt_0_response.json')
        self.assertEqual(raw['choices'][0]['message']['reasoning_content'], 'unexpected reasoning')

    def test_missing_usage_is_unknown_with_known_tokens_separate(self):
        class MissingUsage(Response):
            def model_dump(self, **kwargs):
                raw = super().model_dump(**kwargs)
                raw.pop('usage')
                return raw
        p = self.provider([Response(), MissingUsage()])
        p.ask([], 'file_initial')
        p.ask([], 'file_reflection')
        totals = p.resources()
        self.assertEqual(totals['known_prompt_tokens'], 3)
        self.assertEqual(totals['known_completion_tokens'], 2)
        self.assertEqual(totals['usage_unknown_attempts'], 1)
        self.assertIsNone(totals['prompt_tokens'])
        self.assertIsNone(totals['completion_tokens'])
        self.assertEqual(totals['stage_resources']['file_reflection']['successful_responses'], 1)
        self.assertIsNone(totals['stage_resources']['file_reflection']['prompt_tokens'])
        self.assertEqual(totals['stage_resources']['file_initial']['prompt_tokens'], 3)

    def test_refuse_nonlocal_url(self):
        with patch.object(C, 'BASE_URL', 'https://example.com/v1'):
            with self.assertRaises(ValueError):
                LocalProvider(self.root/'out')

    def test_same_qn_all_property_spans_and_crlf_are_retained(self):
        job, index = self.job()
        call = SimpleNamespace(name='get_code_of_class_function', arguments=('m.py', 'C', 'x'))
        source = R.resolve_source(job, index, call)
        self.assertEqual(len(source['spans']), 2)
        self.assertIn('@property\r\n', source['text'])
        self.assertIn('@x.setter\r\n', source['text'])
        self.assertEqual(source['base_raw_sha256'], index['m.py']['raw_sha256'])

    def test_formfeed_does_not_shift_ast_lf_span(self):
        job, index = self.job()
        text = '# docs\fextra\ndef f():\n    pass\n'
        (Path(job['snapshot'])/'m.py').write_bytes(text.encode())
        index['m.py'] = dict(definitions=[dict(kind='function', qualified_name='f', start_line=2, end_line=3)])
        source = R.resolve_source(job, index, SimpleNamespace(name='get_code_of_file_function', arguments=('m.py', 'f')))
        self.assertEqual(source['text'], 'def f():\n    pass\n')

    def test_source_sha_mismatch_and_outside_identity_fail(self):
        job, index = self.job()
        index['m.py']['raw_sha256'] = 'bad'
        with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
            R.resolve_source(job, index, SimpleNamespace(name='get_code_of_file_function', arguments=('m.py', 'C.x')))
        with self.assertRaisesRegex(ValueError, 'inventory'):
            R.resolve_source(job, index, SimpleNamespace(name='get_code_of_file_function', arguments=('../m.py', 'f')))

    def test_catalog_keeps_nested_async_and_duplicate_identity_order(self):
        _, index = self.job()
        index['m.py']['definitions'] += [dict(kind='function', qualified_name='outer', start_line=7, end_line=10),
            dict(kind='function', qualified_name='outer.inner', start_line=8, end_line=9)]
        c = R.catalog(index, ['m.py'])[0]
        self.assertEqual([x['name'] for x in c['static_functions']], ['outer', 'outer.inner'])
        self.assertEqual([x['name'] for x in c['class_functions'][0]['functions']], ['x', 'x'])

    def test_raw_slots_keep_invalid_kind_duplicates_and_order(self):
        slots = R.raw_functions('```\nm.py\nfunction: C.x\nclass: C\nfunction: C.x\n```')
        self.assertEqual([x['qualified_name'] for x in slots], ['C.x', None, 'C.x'])

    def test_issue_mask_never_transforms_repository_or_source_path(self):
        job, _ = self.job()
        text = f"owner/repo/m.py {job['instance_id']} {job['base_commit']}"
        transformed, records = R.issue_transform(text, job)
        self.assertIn('owner/repo/m.py', transformed)
        self.assertEqual(len(records), 2)

    def test_delivery_requires_corresponding_accept_not_same_bytes(self):
        job, index = self.job()
        class Base:
            def __init__(self): pass
        agent = R.make_agent_class(Base, job, index, None, self.root, ValueError)()
        common = dict(text='same body', tool='get_code_of_file_function', arguments=['m.py', 'f'])
        agent.sources = [dict(source_id='older', step=0, **common), dict(source_id='rejected', step=1, **common)]
        agent.accepted_ids = ['older']
        agent.current_step = 1
        agent.observe_delivery([{'content':'same body'}], 'final_summary', {'request_id':'q'})
        self.assertEqual([e['source_id'] for e in agent.events], ['older'])
        agent.observe_delivery([{'content':'same body'}], 'pruner', {'request_id':'p'})
        self.assertEqual([e['source_id'] for e in agent.events if e['event']=='judge_seen'], ['rejected'])

    def test_run_case_factory_and_environment_restored_after_error(self):
        job, _ = self.job()
        class Base:
            def __init__(self, *args, **kwargs): pass
            def file_localize_with_g(self, **kwargs):
                raise RuntimeError('synthetic file failure')
        q, old = SimpleNamespace(make_model=object()), SimpleNamespace(make_model=object())
        originals = q.make_model, old.make_model
        tools = SimpleNamespace(_v3_definition_index=SimpleNamespace(cache_clear=lambda: None))
        p = self.provider([])
        before = dict(R.os.environ)
        with patch.object(R, '_load_cosil', return_value=(Base,q,old,tools,ValueError)):
            result = R.run_case(self.root/'job.json', self.root/'case', provider=p)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual((q.make_model, old.make_model), originals)
        self.assertEqual(dict(R.os.environ), before)
        self.assertTrue((self.root/'case/result.json').exists())
        self.assertGreaterEqual(result['process_cpu_seconds'], 0)
        with self.assertRaises(FileExistsError):
            R.run_case(self.root/'job.json', self.root/'case', provider=p)

    def test_original_fixed_class_preserves_both_format_repairs(self):
        try:
            base, q, old, tools, error = R._load_cosil()
        except ModuleNotFoundError as missing:
            self.skipTest('Original CoSIL dependencies unavailable: '+str(missing))
        job, _ = self.job()
        source = (Path(job['snapshot'])/'m.py').read_bytes().decode()
        C.write(job['structure'], dict(structure={'m.py': dict(text=source.splitlines(),
            functions=[], classes=[dict(name='C', start_line=1, end_line=5,
                text=source.splitlines(), methods=[dict(name='x', start_line=2, end_line=3,
                    text=source.splitlines()[1:3]), dict(name='x', start_line=4, end_line=5,
                    text=source.splitlines()[3:5])])])}))
        responses = ['bad file format', '```\nm.py\n```', '```\nm.py\n```',
            'Inspect C.x', "get_code_of_class_function('m.py', 'C', 'x')", 'uncertain',
            'True', 'exit()', '```\nm.py\nfunction: C.x\n```']
        p = self.provider([Response(s) for s in responses])
        original = q.make_model, old.make_model
        result = R.run_case(self.root/'job.json', self.root/'case', provider=p)
        self.assertEqual(result['status'], 'complete', result.get('traceback'))
        self.assertEqual((q.make_model, old.make_model), original)
        self.assertEqual(result['semantic_calls'], 9)
        stages = [r['stage'] for r in p.records]
        self.assertEqual(stages[:3], ['file_initial', 'file_format_retry', 'file_reflection'])
        self.assertIn('pruner_format_retry', stages)
        self.assertEqual(result['predicted_functions'][0]['qualified_name'], 'C.x')
        context = C.read(self.root/'case/context.json')
        self.assertEqual(len(context['blocks']), 1)
        self.assertEqual(len(context['blocks'][0]['spans']), 2)
        events = [json.loads(line) for line in (self.root/'case/events.jsonl').read_text().splitlines()]
        self.assertTrue(any(e['event']=='judge_seen' for e in events))
        self.assertTrue(any(e['event']=='agent_seen' and e['purpose']=='final_summary' for e in events))

    def test_completed_file_raw_slots_survive_function_stage_failure(self):
        self.job()
        class Base:
            def __init__(self, *args, **kwargs): pass
            def file_localize_with_g(self, **kwargs):
                self.file_outputs = [dict(stage='file_reflection',
                    response='```\noutside.py\nm.py\nm.py\n```')]
                return ['m.py'], {}, {}
            def _parse_top5_file(self, raw):
                return [line for line in raw.splitlines() if line.endswith('.py')]
            def localize_with_p(self, **kwargs):
                raise RuntimeError('synthetic later function failure')
        q, old = SimpleNamespace(make_model=object()), SimpleNamespace(make_model=object())
        tools = SimpleNamespace(_v3_definition_index=SimpleNamespace(cache_clear=lambda: None))
        p = self.provider([])
        with patch.object(R, '_load_cosil', return_value=(Base,q,old,tools,ValueError)):
            result = R.run_case(self.root/'job.json', self.root/'case', provider=p)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['predicted_files'], ['outside.py','m.py','m.py'])
        self.assertEqual(result['ranked_edit_files'], ['m.py'])
        self.assertIn('file_stage_wall_seconds', result)
        self.assertIn('function_stage_wall_seconds', result)
        self.assertEqual(C.read(self.root/'case/result.json')['predicted_files'],result['predicted_files'])


if __name__ == '__main__':
    unittest.main()
