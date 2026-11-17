"""CPU tests: exact Java source identity, original search wiring and no gold input."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import socketserver
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import cosil_adapter as a


class TinyTokenizer:
    def encode(self, text, **kwargs):
        return list(range(max(1, len(text) // 4)))

    def apply_chat_template(self, messages, **kwargs):
        text = json.dumps(messages)
        return text if kwargs.get('tokenize') is False else self.encode(text)


class FakeProvider:
    def __init__(self):
        self.records = []
        self.step = 0

    def count(self, messages):
        return max(1, len(json.dumps(messages)) // 4)

    def ask(self, messages, purpose, **kwargs):
        if purpose.startswith('file'):
            text = '```\nsrc/pkg/Thing.java\n```'
        elif purpose in ('pruner', 'pruner_format_retry'):
            text = 'True'
        elif purpose == 'node_selection':
            self.step += 1
            text = ("get_code_of_class_function('src/pkg/Thing.java', 'Thing', 'run(int)')"
                    if self.step == 1 else 'exit()')
        else:
            text = '```\nsrc/pkg/Thing.java\nfunction: Thing.run(int)\n```'
        self.records.append({'purpose': purpose, 'messages': copy.deepcopy(messages)})
        return {'content': text, 'usage': {'prompt_tokens': self.count(messages), 'completion_tokens': 8},
                'receipt': {'request_id': 'synthetic-' + str(len(self.records)),
                            'request_sha256': a.digest(json.dumps(messages))}}

    def resources(self):
        return {'simulation': True, 'not_benchmark_result': True, 'semantic_calls': len(self.records)}

    def close(self):
        pass


class JavaAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='multiswe_java_adapter_cpu_')
        self.root = Path(self.temp.name)
        self.path = 'src/pkg/Thing.java'
        self.source = ('package pkg;\nimport java.util.List;\nclass Thing {\n'
                       '  int run(int x) { return target(x); }\n'
                       '  int run(String x) { return x.length(); }\n'
                       '  int target(int x) { return x + 1; }\n}\n')
        raw = self.source.encode()
        target = self.root / 'snapshot' / self.path
        target.parent.mkdir(parents=True)
        target.write_bytes(raw)
        defs = []
        for name, signature, body, line in [
            ('run', 'run(int)', 'int run(int x) { return target(x); }', 4),
            ('run', 'run(String)', 'int run(String x) { return x.length(); }', 5),
            ('target', 'target(int)', 'int target(int x) { return x + 1; }', 6)]:
            start = raw.index(body.encode())
            qn = 'Thing.' + signature
            defs.append({'kind': 'function', 'declaration_kind': 'method', 'name': name,
                'qualified_name': qn, 'signature': signature, 'canonical_id': self.path + '::' + qn,
                'parent_qualified_name': 'Thing', 'start_line': line, 'end_line': line, 'def_line': line,
                'start_byte': start, 'end_byte': start + len(body.encode()), 'code': body,
                'raw_sha256': a.digest(body)})
        cls_start, cls_end = raw.index(b'class Thing'), raw.rindex(b'}') + 1
        cls = {'name': 'Thing', 'qualified_name': 'Thing', 'parent_qualified_name': None,
               'start_line': 3, 'end_line': 7, 'def_line': 3, 'start_byte': cls_start,
               'end_byte': cls_end, 'code': raw[cls_start:cls_end].decode()}
        self.index = {self.path: {'raw_sha256': a.digest(raw), 'text': self.source, 'classes': [cls],
                                 'definitions': defs, 'imports': ['import java.util.List;'], 'calls': []}}
        self.index_path = self.root / 'code_index.json'
        a.write(self.index_path, self.index)
        self.job = {'instance_id': 'owner__repo-1', 'repo': 'owner/repo', 'base_commit': 'a' * 40,
                    'problem_statement': 'run returns an incorrect value', 'snapshot': str(self.root / 'snapshot'),
                    'code_index': str(self.index_path), 'structure': str(self.root / 'unused_structure.json')}
        self.job_path = self.root / 'job.json'
        a.write(self.job_path, self.job)
        self.cache = self.root / 'render_cache.json'
        self.edges = {'base_commit': self.job['base_commit'], 'index_sha256': a.digest(self.index_path.read_bytes()),
            'edges': [{'caller': defs[0]['canonical_id'], 'callee': defs[2]['canonical_id'],
                       'path': self.path, 'line': 4, 'column': 26, 'expression': 'target(x)',
                       'resolution': 'exact_local_single_candidate'}],
            'unresolved': [{'caller': defs[1]['canonical_id'], 'reason': 'external_receiver'}]}
        a.write(self.cache, self.edges)

    def tearDown(self):
        self.temp.cleanup()

    def call(self, name='get_code_of_class_function', args=None):
        return SimpleNamespace(name=name, arguments=args or (self.path, 'Thing', 'run(int)'))

    def test_overloads_have_separate_catalog_and_exact_source(self):
        a.validate_index(self.index)
        names = a.java_catalog(self.index, [self.path])[0]['class_functions'][0]['functions']
        self.assertEqual([x['name'] for x in names], ['run(int)', 'run(String)', 'target(int)'])
        source = a.resolve_java_source(self.job, self.index, self.call())
        self.assertIn('return target(x)', source['text'])
        self.assertNotIn('x.length', source['text'])
        with self.assertRaises(ValueError):
            a.resolve_java_source(self.job, self.index, self.call(args=(self.path, 'Thing', 'run')))

    def test_structure_and_predictions_preserve_java_and_invalid_rank(self):
        tree = a.structure_from_index(self.index)
        self.assertIn('Thing.java', a.show_java_structure(tree))
        output = '```\nsrc/pkg/Thing.java\nfunction: Thing.run(int)\nclass: Thing\nfunction: nonexistent()\n```'
        self.assertEqual(a.java_file_output(output), [self.path])
        ranks = a.java_function_output(output)
        self.assertEqual(len(ranks), 3)
        self.assertIsNone(ranks[1]['qualified_name'])
        self.assertEqual(ranks[2]['qualified_name'], 'nonexistent()')

    def test_sha_and_byte_range_verification(self):
        target = self.root / 'snapshot' / self.path
        target.write_text(self.source.replace('x + 1', 'x + 2'))
        with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
            a.resolve_java_source(self.job, self.index, self.call())

    def test_renderer_uses_only_resolved_edges_with_v6_contract(self):
        a.activate_bundle()
        renderer = a.JavaRenderer(self.job, self.cache, a.digest(self.cache.read_bytes()),
            tokenizers={'tiny': (TinyTokenizer(), 'reranker')})
        source = a.resolve_java_source(self.job, self.index, self.call())
        row = renderer.render(self.job['problem_statement'], self.call(), source['text'])
        self.assertEqual(row['function_id'], self.path + '::Thing.run(int)')
        self.assertEqual(row['neighbors_selected'], 1)
        self.assertIn('Thing.target(int)', row['neighbors'])
        self.assertIn('incomplete, not causal labels', row['neighbors'])
        self.assertEqual(row['input_sha256'], a.digest(row['model_input']))
        with self.assertRaisesRegex(ValueError, 'differs from frozen'):
            renderer.render(self.job['problem_statement'], self.call(), 'different code')

    def test_public_job_rejects_gold_and_builds_original_leaf_schema(self):
        staged, job, index = a.normalize_job(self.job_path, self.root / 'good')
        self.assertEqual(set(job), a.PUBLIC_REQUIRED | a.PUBLIC_OPTIONAL)
        self.assertEqual(job['paths'], [self.path])
        self.assertTrue(staged.exists())
        self.assertIn('Thing.java', a.show_java_structure(a.read(job['structure'])['structure']))
        bad = self.root / 'bad.json'
        a.write(bad, {**self.job, 'patch': 'SECRET'})
        with self.assertRaisesRegex(ValueError, 'public issue/base'):
            a.normalize_job(bad, self.root / 'bad')

    def test_scoring_endpoint_must_be_unix(self):
        with self.assertRaises(ValueError):
            a.JudgeClient('https://external.example/score', self.root / 'rpc')

    def test_original_baseline_factory_reads_java_and_restores_bindings(self):
        bundle = a.activate_bundle()
        from code_rebench_qwen import runner as original
        from code_v3b import fixed_search
        from code_v3b.AFL_插桩版 import AFL
        saved = (original.resolve_source, original.raw_functions, original.make_agent_class,
                 fixed_search.parse_tool_call, AFL._parse_top5_file)
        config = self.root / 'config.json'
        a.write(config, {'main_model_dir': str(self.root), 'render_cache': str(self.cache)})
        fake = FakeProvider()
        result = a.run(SimpleNamespace(job=self.job_path, out=self.root / 'baseline', arm='baseline',
            config=config, main_api_base='http://127.0.0.1:7343/v1', judge_endpoint='unix:/unused'), provider=fake)
        self.assertEqual(result['status'], 'complete', result.get('traceback'))
        self.assertEqual(result['predicted_files'], [self.path])
        self.assertEqual(result['predicted_functions'][0]['qualified_name'], 'Thing.run(int)')
        events = [json.loads(x) for x in (self.root / 'baseline/events.jsonl').read_text().splitlines()]
        self.assertTrue(any(x['event'] == 'source_returned' for x in events))
        self.assertTrue(any(x['event'] == 'agent_seen' for x in events))
        self.assertTrue(any(x['purpose'] == 'pruner' for x in fake.records))
        self.assertTrue(all('Python software' not in json.dumps(x['messages']) for x in fake.records))
        self.assertEqual(saved, (original.resolve_source, original.raw_functions, original.make_agent_class,
                                fixed_search.parse_tool_call, AFL._parse_top5_file))

    def test_original_hybrid_factory_scores_java_once_and_reuses_file_stage(self):
        bundle = a.activate_bundle()
        from specprune import runtime_renderer
        shared = self.root / 'shared.json'
        a.write(shared, {'instance_id': self.job['instance_id'], 'base_commit': self.job['base_commit'],
                         'files': [self.path], 'raw_file_responses': []})
        # Match the real allowlist CLI: config is the frozen scorer deployment,
        # not an engineering config; shared is a separate public CLI argument.
        config = bundle / 'configs/deployment.json'
        requests = []
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                body = json.loads(self.rfile.readline())
                requests.append(body)
                answer = {'ok': True, 'result': {'p_yes': .99, 'temperature': 2.9846201034621833,
                    'logit_difference': 13.7, 'input_tokens': 123, 'generated_output_tokens': 0,
                    'latency_seconds': .01, 'score_sequence': len(requests), 'model_load_count': 1}}
                self.wfile.write((json.dumps(answer) + '\n').encode())
        server = socketserver.UnixStreamServer(str(self.root / 'judge.sock'), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        fake = FakeProvider()
        try:
            with patch.object(runtime_renderer, 'tokenizers', lambda: {'tiny': (TinyTokenizer(), 'reranker')}):
                result = a.run(SimpleNamespace(job=self.job_path, out=self.root / 'hybrid', arm='hybrid_safe',
                    config=config, main_api_base='http://127.0.0.1:7343/v1',
                    shared=shared, judge_endpoint='unix:' + str(self.root / 'judge.sock')), provider=fake)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(result['status'], 'complete', result.get('traceback'))
        self.assertEqual(len(requests), 1)
        self.assertEqual(set(requests[0]), {'operation', 'row'})
        self.assertEqual(set(requests[0]['row']), set(a.RPC_FIELDS))
        self.assertFalse(any(x['purpose'].startswith('file') for x in fake.records))
        self.assertFalse(any(x['purpose'] == 'pruner' for x in fake.records))
        self.assertTrue(all("for static functions, don't add class name" not in json.dumps(x['messages'])
                            for x in fake.records))
        events = [json.loads(x) for x in (self.root / 'hybrid/events.jsonl').read_text().splitlines()]
        judges = [x for x in events if x['event'] == 'local_judge']
        self.assertEqual(len(judges), 1)
        self.assertEqual(judges[0]['function_id'], self.path + '::Thing.run(int)')
        self.assertEqual(judges[0]['route'], 'retain')
        self.assertTrue(any(x['event'] == 'agent_seen' for x in events))

    def test_actual_index_parser_renderer_interface_including_constructor(self):
        try:
            from .java_index import parse_java, direct_edges
        except ImportError:
            self.skipTest('Shared Java index is not yet available')
        try:
            entry = parse_java('Foo.java', b'class Foo { Foo() {} int run(int x) { return x; } }')
        except ModuleNotFoundError as error:
            self.skipTest('Java parser environment unavailable: ' + str(error))
        index = {'Foo.java': entry}
        a.validate_index(index)
        self.assertEqual(len(a.java_catalog(index, ['Foo.java'])[0]['class_functions'][0]['functions']), 2)
        edges = direct_edges(index)
        self.assertIn('edges', edges)
        self.assertIn('unresolved', edges)


if __name__ == '__main__':
    unittest.main()
