import ast
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

os.environ['TIKTOKEN_CACHE_DIR'] = str(Path(__file__).resolve().parents[2] / 'resources/offline_tiktoken')
from paper_retest93 import pipeline as P


class Provider:
    def __init__(self, draws=None, queries=None, function=None):
        self.draws = draws or [[] for _ in range(5)]
        self.queries = queries or []
        self.function = function or []
        self.calls = []

    def ask(self, messages, stage, **kwargs):
        self.calls.append((messages, stage, kwargs))
        if stage.startswith('file_draw_'):
            value = self.draws[int(stage[-1])]
            return {'content': value if isinstance(value, str) else json.dumps({'ranked_files': value})}
        if stage == 'query_planning':
            return {'content': json.dumps({'queries': self.queries})}
        return {'content': json.dumps({'ranked_functions': self.function})}


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network = patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden'))
        cls.network.start()
        P.encoder()

    @classmethod
    def tearDownClass(cls):
        cls.network.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def job(self, sources, *, missing=()):
        base = self.root / 'snapshot';base.mkdir()
        index = {}
        for name, text in sources.items():
            file = base / name;file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(text if isinstance(text, bytes) else text.encode())
            if name.endswith('.py'):
                try:
                    source = P.decode(file.read_bytes(), name)
                    tree = ast.parse(source)
                except (ValueError, UnicodeError, SyntaxError):
                    index[name] = {'definitions': []};continue
                definitions = []
                def visit(node, prefix=''):
                    for child in ast.iter_child_nodes(node):
                        if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                            qn = prefix + child.name
                            definitions.append({'kind': 'class' if isinstance(child, ast.ClassDef) else 'function',
                                'qualified_name': qn, 'start_line': child.lineno, 'end_line': child.end_lineno})
                            visit(child, qn + '.')
                        else:
                            visit(child, prefix)
                visit(tree);index[name] = {'definitions': definitions}
        ip = self.root / 'index.json';ip.write_text(json.dumps(index))
        return {'instance_id': 'example__project-123', 'repo': 'example/project',
            'base_commit': 'f0123456789abcdef0123456789abcdef01234567',
            'problem_statement': 'Fix the example behavior.', 'cohort': 'synthetic',
            'snapshot': str(base), 'paths': sorted(set(sources) | set(missing)),
            'code_index': str(ip), 'structure': str(self.root / 'structure.json')}

    def out(self):
        return self.root / 'out'

    def context(self):
        return json.loads((self.out() / 'context.json').read_text())

    def test_actual_stage_contract_no_file_rank10_or_loaded5_limit(self):
        sources = {f'a{i:02}.py': f'def f{i}():\n    return {i}\n' for i in range(12)}
        job = self.job(sources);ranked = list(sources)
        provider = Provider([ranked] * 5)
        result = P.run(job, provider, self.out())
        self.assertEqual(result['predicted_files'], ranked)
        self.assertEqual(self.context()['loaded_whole_files'], ranked)
        self.assertEqual([c[1] for c in provider.calls],
                         [f'file_draw_{i}' for i in range(5)] + ['query_planning', 'function_localization'])
        self.assertEqual([c[2]['max_tokens'] for c in provider.calls], [6144] * 5 + [4096, 4096])
        self.assertTrue(all(c[2]['temperature'] is None and c[2]['json_mode'] is True for c in provider.calls))

    def test_malformed_construction_uses_fallback_L0(self):
        job = self.job({'a.py': 'a=1\n', 'b.py': 'b=2\n'})
        role = P.roles(job['instance_id']);draws = [['a.py'] for _ in range(5)]
        draws[role['L0']] = ['b.py'];draws[role['L1']] = 'not JSON'
        result = P.run(job, Provider(draws), self.out())
        selection = json.loads((self.out() / 'file_selection.json').read_text())
        self.assertTrue(selection['fallback']);self.assertEqual(result['predicted_files'], ['b.py'])
        self.assertIn(role['L1'], selection['parse_error_draws'])

    def test_intersection_reciprocal_ranks_and_alphabetical_ties(self):
        draws = [['b.py'], ['b.py', 'a.py'], ['a.py', 'b.py'], [], []]
        selected, fallback = P.select_files(draws, {'L0': 0, 'L1': 1, 'L2': 2}, {'a.py', 'b.py'})
        self.assertEqual(selected, ['a.py', 'b.py']);self.assertFalse(fallback)

    def test_reciprocal_rank_keeps_original_invalid_and_excluded_slots(self):
        draws = [[], ['missing.py', 'a.py', 'b.py'], ['b.py', 'a.py'], [], []]
        selected, fallback = P.select_files(draws, {'L0': 0, 'L1': 1, 'L2': 2}, {'a.py', 'b.py'})
        self.assertEqual(selected, ['b.py', 'a.py']);self.assertFalse(fallback)

    def test_inventory_bytes_third_half_cap_and_display_order(self):
        paths = ['z.py', 'b.py', 'a.py', 'x.py']
        shown, stats = P.inventory(paths, 'z')
        self.assertEqual(stats['inventory_cap_tokens'], sum(len((p+'\n').encode())/3 for p in paths)/2)
        self.assertLessEqual(stats['inventory_estimated_tokens'], stats['inventory_cap_tokens'])
        self.assertEqual(shown, sorted(shown));self.assertIn('z.py', shown)

    def test_60000_token_source_prefix_is_raw_and_has_correct_partial_line(self):
        original = '# ' + 'x ' * 60100 + '\nlast = 1\n'
        self.assertGreater(len(P.tokens(original)), 60000)
        prefix, info = P.token_prefix(original, 60000)
        self.assertTrue(original.startswith(prefix));self.assertLessEqual(len(P.tokens(prefix)), 60000)
        self.assertTrue(info['is_truncated']);self.assertTrue(info['partial_last_line'])
        self.assertEqual(info['end_line'], 1);self.assertEqual(info['last_complete_line'], 0)
        self.assertEqual(info['retained_characters'], len(prefix));self.assertEqual(info['prefix_sha256'], P.digest(prefix))

    def test_unicode_boundary_retains_verbatim_prefix_without_replacement(self):
        text = '😀汉字 café\n' * 10
        for cap in range(1, 20):
            prefix, info = P.token_prefix(text, cap)
            self.assertTrue(text.startswith(prefix));self.assertNotIn('\ufffd', prefix)
            self.assertLessEqual(len(P.tokens(prefix)), cap)
            self.assertEqual(info['retained_utf8_bytes'], len(prefix.encode()))

    def test_evidence_12k_is_per_span_not_aggregate(self):
        sources = {'main.py': 'def main():\n    pass\n'}
        for letter in ('a', 'b'):
            sources[letter+'.py'] = f"def evidence_{letter}():\n    value = 'needle_{letter} " + 'x ' * 9000 + "'\n    return value\n"
        job = self.job(sources)
        provider = Provider([['main.py']] * 5, [{'kind': 'definition', 'patterns': ['needle_a', 'needle_b']}])
        P.run(job, provider, self.out());context = self.context()
        evidence = [b for b in context['blocks'] if b['origin'] == 'evidence']
        self.assertEqual(len(evidence), 2);self.assertGreater(context['evidence_tokens'], 12000)
        self.assertTrue(all(b['truncation']['retained_body_tokens'] <= 12000 for b in evidence))

    def test_each_evidence_span_is_truncated_to12k_and_not_whole_file(self):
        sources = {'main.py': 'x=1\n', 'e.py': "def e():\n    x = 'needle " + 'x ' * 13000 + "'\n    return x\n"}
        job = self.job(sources)
        P.run(job, Provider([['main.py']]*5, [{'kind':'definition','patterns':['needle']}]), self.out())
        block = [b for b in self.context()['blocks'] if b['origin']=='evidence'][0]
        self.assertEqual(block['truncation']['body_token_limit'], 12000)
        self.assertTrue(block['truncation']['is_truncated']);self.assertFalse(block['complete_file'])

    def test_E_is_fixed_before_budget_and_does_not_replace_overflow_with_later_file(self):
        sources = {'main.py': '# ' + 'x ' * 60100 + '\n'}
        for letter in ('a', 'b'):
            sources[letter+'.py'] = f"def evidence_{letter}():\n    value = 'needle " + 'x ' * 11000 + "'\n    return value\n"
        sources['c.py'] = 'needle = 1\n'
        job = self.job(sources)
        P.run(job, Provider([['main.py']]*5,[{'kind':'literal','patterns':['needle']}]), self.out())
        context = self.context()
        self.assertEqual(context['collected_evidence_files'], ['a.py', 'b.py'])
        self.assertNotIn('c.py', context['context_files'])
        self.assertEqual([s['path'] for s in context['skipped_files'] if s['reason']=='context_80k_overflow'], ['b.py'])
        self.assertLessEqual(context['reference_tokens'], 80000)
        self.assertEqual(context['reference_tokens'], len(P.tokens(context['model_context_text'])))

    def test_multiple_patterns_share_two_file_limit_and_total8_limit(self):
        job = self.job({f'{i}.txt': f'pattern{i}\n' for i in range(10)})
        base = P.BaseText(job)
        q = {'kind': 'related_tests', 'patterns': [f'pattern{i}' for i in range(8)]}
        evidence, queries = P.collect_evidence([q]*4, [], base, {})
        self.assertEqual(len(evidence), 8);self.assertTrue(all(len(q['new_files'])==2 for q in queries))
        self.assertEqual(len({e['path'] for e in evidence}), 8)

    def test_class_is_enclosing_definition_and_test_files_can_be_evidence(self):
        sources = {'main.py': 'x=1\n', 'tests/test_a.py': 'class Example:\n    marker = "needle"\n    def method(self):\n        return 1\n'}
        job = self.job(sources);base = P.BaseText(job);index=json.loads(Path(job['code_index']).read_text())
        evidence, _ = P.collect_evidence([{'kind':'related_tests','patterns':['needle']}], ['main.py'], base, index)
        self.assertEqual(evidence[0]['definition']['kind'], 'class')
        self.assertEqual(evidence[0]['start_line'], 1);self.assertEqual(evidence[0]['end_line'], 4)
        selected, _ = P.select_files([['tests/test_a.py','main.py']]*5,P.roles(job['instance_id']),set(job['paths']))
        self.assertEqual(selected,['main.py'])

    def test_nonpython_code_can_be_selected_and_other_text_searched(self):
        job=self.job({'main.js':'const answer = 1;\n', 'notes.md':'needle in supporting text\n'})
        P.run(job,Provider([['main.js']]*5,[{'kind':'literal','patterns':['needle']}]),self.out())
        context=self.context();self.assertIn('main.js',context['loaded_whole_files'])
        self.assertIn('notes.md',context['context_files']);self.assertEqual(context['blocks'][1]['origin'],'evidence')

    def test_binary_or_unmaterialized_inventory_path_is_recorded_not_read(self):
        job=self.job({'main.py':'x=1\n'},missing=['other.py'])
        P.run(job,Provider([['other.py','main.py']]*5),self.out())
        self.assertEqual(self.context()['skipped_files'][0]['reason'],'source_not_materialized_or_decodable')
        self.assertEqual(self.context()['loaded_whole_files'],['main.py'])

    def test_exact_full_metadata_is_masked_in_every_request_with_raw_context_preserved(self):
        repo='example/project';iid='example__project-123';sha='f0123456789abcdef0123456789abcdef01234567'
        source=f'def f():\n    return "{repo} {iid} {sha} project"\n'
        job=self.job({'main.py':source});job['problem_statement']+=' '+repo+' '+iid+' '+sha
        provider=Provider([['main.py']]*5);P.run(job,provider,self.out());context=self.context()
        for messages,_,_ in provider.calls:
            visible=messages[0]['content']
            for literal in (repo,iid,sha):self.assertNotIn(literal,visible)
        self.assertIn(repo,context['blocks'][0]['text']);self.assertIn('project',context['model_context_text'])
        raw='\n\n'.join(b['header']+b['text'] for b in context['blocks'])
        self.assertEqual(P.metadata_mask(raw,job)[0],context['model_context_text'])
        self.assertEqual(context['model_context_sha256'],P.digest(context['model_context_text']))
        self.assertEqual(context['raw_context_sha256'],P.digest(raw));self.assertEqual(len(context['metadata_mask_records']),3)
        self.assertFalse((self.out()/'gold.json').exists())

    def test_extra_gold_or_patch_field_rejected_before_provider(self):
        job=self.job({'main.py':'x=1\n'});job['patch']='DO_NOT_READ_OR_SEND'
        provider=Provider()
        with self.assertRaises(ValueError):P.run(job,provider,self.out())
        self.assertFalse(provider.calls)

    def test_query_schema_caps_original_queries_and_patterns_without_extra_calls(self):
        response={'content':json.dumps({'queries':[{'kind':'callers','patterns':[str(i) for i in range(9)]}]*5})}
        queries,errors=P.parse_queries(response)
        self.assertEqual(len(queries),4);self.assertTrue(all(len(q['patterns'])==8 for q in queries))
        self.assertIn('queries_after_four_ignored',errors)
        queries,errors=P.parse_queries({'content':'{"queries":[{"kind":"literal","patterns":["", "x\\ny", "good"]}]}'})
        self.assertEqual(queries[0]['patterns'],['good'])

    def test_decoding_python_encoding_nonpython_boms_and_nul(self):
        self.assertIn('é',P.decode(b'# coding: latin-1\nx="\xe9"\n','a.py'))
        self.assertEqual(P.decode('x=1'.encode('utf-16'),'a.js'),'x=1')
        self.assertEqual(P.decode(b'\xef\xbb\xbfx=1','a.js'),'x=1')
        with self.assertRaises(ValueError):P.decode(b'a\x00b','a.js')

    def test_changed_durable_trace_is_rejected(self):
        p=self.root/'trace.json';P.write_json(p,{'x':1});P.write_json(p,{'x':1})
        with self.assertRaises(RuntimeError):P.write_json(p,{'x':2})


if __name__ == '__main__':
    unittest.main()
