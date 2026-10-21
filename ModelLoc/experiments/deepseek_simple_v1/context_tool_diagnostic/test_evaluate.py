"""Synthetic CPU-only tests. Never open the real evaluator_private directory."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from context_tool_diagnostic import evaluate


class EvaluationTests(unittest.TestCase):
    def test_fixed_slots_and_shared_property_identity(self):
        index = {'a.py': {'definitions': [
            {'kind': 'function', 'qualified_name': 'A.p'},
            {'kind': 'function', 'qualified_name': 'A.p'},
            {'kind': 'function', 'qualified_name': 'correct'}]}}
        raw = [{'path': 'a.py', 'qualified_name': 'A.p'},
               {'path': 'a.py', 'qualified_name': 'A.p'}, None,
               {'path': '../a.py', 'qualified_name': 'correct'},
               {'path': 'a.py', 'qualified_name': 'correct'}]
        row = evaluate.metric_values(raw, index, ['a.py::correct', 'a.py::A.p'])
        self.assertEqual(row['normalized_function_slots'], ['a.py::A.p', 'a.py::A.p', None, None, 'a.py::correct'])
        self.assertEqual(row['hit_1'], 1)
        self.assertEqual(row['recall_5'], 1)
        self.assertEqual(row['precision_5'], .4)
        self.assertEqual(row['all_coverage_5'], 1)
        self.assertEqual(row['duplicate_function_count'], 1)
        self.assertIsNone(evaluate.metric_values([], index, [], 'complete')['hit_5'])
        self.assertIsNone(evaluate.metric_values([], index, ['a.py::correct'], 'NOT_RUN')['hit_5'])
        self.assertEqual(evaluate.metric_values([], index, ['a.py::correct'], 'context_overflow')['hit_5'], 0)

    def test_exact_mcnemar_and_paired_deterministic_bootstraps(self):
        pairs = []
        for repo, a, b in [('repo-a', 1, 0), ('repo-a', 1, 0), ('repo-a', 1, 0), ('repo-b', 0, 1)]:
            pairs.append(({'repo': repo, 'hit_5': a}, {'repo': repo, 'hit_5': b}))
        first = evaluate.paired_statistics(pairs, 'hit_5', bootstraps=1000)
        second = evaluate.paired_statistics(pairs, 'hit_5', bootstraps=1000)
        self.assertEqual(first, second)
        self.assertEqual(first['mean_difference'], .5)
        self.assertEqual(first['a_win_b_lose'], 3)
        self.assertEqual(first['a_lose_b_win'], 1)
        self.assertEqual(first['McNemar_exact_two_sided'], .625)
        self.assertEqual(first['repo_cluster_bootstrap95'], [-1., 1.])
        self.assertEqual(evaluate.exact_mcnemar(4, 0), .125)
        self.assertEqual(evaluate.exact_mcnemar(0, 0), 1)
        self.assertEqual(evaluate.paired_statistics([], 'hit_5')['paired_strict_n'], 0)

    def test_recall_wins_follow_recall_when_hit5_is_identical(self):
        pairs = [
            ({'repo': 'r1', 'hit_5': 1, 'recall_5': 1.}, {'repo': 'r1', 'hit_5': 1, 'recall_5': .5}),
            ({'repo': 'r2', 'hit_5': 1, 'recall_5': .25}, {'repo': 'r2', 'hit_5': 1, 'recall_5': .75}),
            ({'repo': 'r2', 'hit_5': 0, 'recall_5': 0.}, {'repo': 'r2', 'hit_5': 0, 'recall_5': 0.}),
        ]
        recall = evaluate.paired_statistics(pairs, 'recall_5', bootstraps=1000)
        self.assertEqual((recall['a_win_b_lose'], recall['a_lose_b_win'], recall['ties']), (1, 1, 1))
        self.assertIsNone(recall['both_correct'])
        self.assertIsNone(recall['both_wrong'])
        self.assertIsNone(recall['McNemar_exact_two_sided'])
        self.assertEqual(recall['hit5_four_cells'], {'a_win_b_lose': 0, 'a_lose_b_win': 0, 'both_correct': 2, 'both_wrong': 1})
        hit = evaluate.paired_statistics(pairs, 'hit_5', bootstraps=1000)
        self.assertEqual((hit['a_win_b_lose'], hit['a_lose_b_win'], hit['ties']), (0, 0, 3))
        self.assertEqual(hit['both_correct'], 2)
        self.assertEqual(hit['both_wrong'], 1)
        self.assertEqual(hit['McNemar_exact_two_sided'], 1.)

    def test_pending_pairs_do_not_make_inference_and_completed_filter(self):
        base = {'instance_id': 'i', 'repo': 'r', 'gold_mapping_status': 'fully_mappable',
                'entered_search': False, **{m: 1 for m in evaluate.METRICS}}
        rows = [dict(base, method='A-FULL', status='NOT_RUN'), dict(base, method='A-SIGNATURE', status='complete')]
        pairs = evaluate.paired_table(rows, 'A-FULL', 'A-SIGNATURE')
        self.assertTrue(all(x['mean_difference'] is None for x in pairs))
        self.assertTrue(all(x['comparison_status'] == 'INCOMPLETE_NOT_RUN_PRESENT' for x in pairs))
        self.assertEqual(evaluate.paired_table(rows, 'A-FULL', 'A-SIGNATURE', 'completed')[0]['allocated_strict_pairs'], 0)

    def test_coverage_and_grep_do_not_mutate_candidates(self):
        frozen = {'candidates': [{'identity': 'a.py::present'}], 'manifest': {
            'loaded_whole_files': ['a.py'], 'candidate_sha256': 'fixed',
            'excluded_grep_evidence': [{'path': 'b.py', 'start_line': 10, 'end_line': 20}]}}
        index = {'b.py': {'definitions': [{'kind': 'function', 'qualified_name': 'missing', 'start_line': 12, 'end_line': 18}]}}
        before = copy.deepcopy(frozen)
        row = evaluate.coverage_audit(frozen, ['a.py::present', 'b.py::missing'], index)
        self.assertEqual(row['candidate_gold_recall'], .5)
        self.assertEqual(row['full_file_gold_recall'], .5)
        self.assertEqual(row['gold_only_in_excluded_grep'], ['b.py::missing'])
        self.assertEqual(frozen, before)

    def test_source_return_judge_and_effective_later_agent_are_distinct(self):
        events = [
            {'event': 'raw_model_tool_output', 'step': 0, 'raw_model_tool_output': '{}'},
            {'event': 'parsed_tool_call', 'step': 0, 'tool': 'get_code_of_file_function', 'arguments': ['a.py', 'f']},
            {'event': 'target_resolution', 'step': 0, 'target_resolution': {'target_exists': True}},
            {'event': 'source_returned', 'navigation_round': 0, 'source_id': 's1', 'source_sha256': 'source', 'exact_base_span_available': True},
            {'event': 'tool_io_audit', 'navigation_round': 0, 'executed': True, 'success': True},
            {'event': 'judge_seen', 'navigation_round': 0, 'source_id': 's1', 'recipient': 'small_judge', 'full_source_in_request': False},
        ]
        first = evaluate.structured_calls(Path('/tmp/synthetic-unused'), 'D-COSIL-STRUCTURED', 'i', events)[0]
        self.assertTrue(first['source_returned'])
        self.assertFalse(first['judge_seen_full_source'])
        self.assertFalse(first['agent_seen_full_source'])
        events.append({'event': 'context_accept', 'step': 0, 'tool': 'get_code_of_file_function', 'arguments': ['a.py', 'f']})
        events.append({'event': 'http_request_effective', 'navigation_round': 1, 'purpose': 'node_selection', 'request_id': 'req-next'})
        events.append({'event': 'agent_seen', 'navigation_round': 1, 'source_id': 's1', 'full_source_in_request': True, 'purpose': 'node_selection', 'request_id': 'req-next'})
        second = evaluate.structured_calls(Path('/tmp/synthetic-unused'), 'D-COSIL-STRUCTURED', 'i', events)[0]
        self.assertTrue(second['agent_seen_full_source'])
        self.assertFalse(second['judge_seen_full_source'])
        counts = evaluate.mechanism_counts([second], events, {'entered_search': True})
        self.assertEqual(counts['returned_but_agent_unseen_count'], 0)
        self.assertEqual(counts['first_source_return_round'], 1)

    def test_rejected_repeat_is_byte_visible_without_same_action_delivery(self):
        events = []
        for step, source_id in ((0, 'old-accepted'), (1, 'new-rejected')):
            events.extend([
                {'event': 'raw_model_tool_output', 'step': step, 'raw_model_tool_output': '{}'},
                {'event': 'parsed_tool_call', 'step': step, 'tool': 'get_code_of_file_function', 'arguments': ['a.py', 'f']},
                {'event': 'source_returned', 'navigation_round': step, 'source_id': source_id, 'source_sha256': 'SAME_BYTES', 'exact_base_span_available': True},
                {'event': 'tool_io_audit', 'navigation_round': step, 'executed': True, 'success': True},
                {'event': 'context_accept' if step == 0 else 'context_reject', 'step': step, 'tool': 'get_code_of_file_function', 'arguments': ['a.py', 'f']},
            ])
        # An unrelated later class pruner request includes both old function byte strings.
        events.append({'event': 'http_request_effective', 'navigation_round': 2, 'purpose': 'pruner', 'request_id': 'later-class'})
        for source_id in ('old-accepted', 'new-rejected'):
            events.append({'event': 'judge_seen', 'navigation_round': 2, 'source_id': source_id, 'recipient': 'main_judge', 'purpose': 'pruner', 'request_id': 'later-class', 'full_source_in_request': True})
        events.append({'event': 'http_request_effective', 'navigation_round': 3, 'purpose': 'final_summary', 'request_id': 'final'})
        for source_id in ('old-accepted', 'new-rejected'):
            events.append({'event': 'agent_seen', 'navigation_round': 3, 'source_id': source_id, 'purpose': 'final_summary', 'request_id': 'final', 'full_source_in_request': True})
        calls = evaluate.structured_calls(Path('/tmp/synthetic-unused'), 'Q-PRUNER-STRUCTURED', 'i', events)
        self.assertTrue(calls[0]['agent_seen_full_source'])
        self.assertTrue(calls[0]['agent_byte_visible_full_source'])
        self.assertFalse(calls[1]['agent_seen_full_source'])
        self.assertTrue(calls[1]['agent_byte_visible_full_source'])
        self.assertTrue(calls[1]['actual_reject'])
        self.assertFalse(calls[1]['context_accept_same_action'])
        self.assertTrue(all(c['main_judge_byte_visible_full_source'] for c in calls))
        self.assertFalse(any(c['main_judge_seen_full_source'] for c in calls))
        self.assertEqual(evaluate.mechanism_counts(calls, events, {})['returned_but_agent_unseen_count'], 1)

    def test_csv_blank_tool_names_do_not_become_target_proposals(self):
        calls = [{'canonical_tool': '', 'historical_parsed': False},
                 {'canonical_tool': None, 'syntax_contract_valid': False},
                 {'canonical_tool': 'exit', 'historical_parsed': True},
                 {'canonical_tool': 'get_code_of_file_function', 'historical_parsed': True, 'target_exists': True}]
        counts = evaluate.mechanism_counts(calls, [], {})
        self.assertEqual(counts['actions'], 4)
        self.assertEqual(counts['target_proposals'], 1)
        self.assertEqual(counts['target_exists'], 1)

    def test_recorded_source_sha_can_match_one_of_multiple_property_spans(self):
        import hashlib
        with tempfile.TemporaryDirectory(prefix='cosil-multispan-source-test-') as directory:
            root = Path(directory); snapshot = root / 'base'; snapshot.mkdir()
            source = 'class A:\n    @property\n    def p(self):\n        return 1\n    @p.setter\n    def p(self, x):\n        self.x = x\n'
            (snapshot / 'a.py').write_text(source)
            body = ''.join(source.splitlines(keepends=True)[4:7])
            digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
            artifact = {'path': 'a.py', 'text': body, 'sha256': digest(body), 'tool': 'get_code_of_class_function', 'arguments': ['a.py', 'A', 'p']}
            (root / 'sources').mkdir(); (root / 'sources/s1.json').write_text(json.dumps(artifact))
            event = {'source_id': 's1', 'source_sha256': digest(body), 'exact_base_span_available': False}
            index = {'a.py': {'sha256': digest(source), 'definitions': [
                {'kind': 'function', 'qualified_name': 'A.p', 'start_line': 2, 'end_line': 4},
                {'kind': 'function', 'qualified_name': 'A.p', 'start_line': 5, 'end_line': 7}]}}
            valid, reason = evaluate._verify_returned_source(event, root, {'snapshot': str(snapshot)}, index)
            self.assertTrue(valid)
            self.assertEqual(reason, 'recorded_sha_matches_one_of_base_identity_spans')
            artifact['text'] += '# drift'; (root / 'sources/s1.json').write_text(json.dumps(artifact))
            self.assertFalse(evaluate._verify_returned_source(event, root, {'snapshot': str(snapshot)}, index)[0])

    def test_local_judge_tokens_and_synchronized_wall_are_separate_from_http(self):
        usage = evaluate.local_judge_usage([
            {'event': 'small_judge', 'input_tokens': 100, 'generated_output_tokens': 0, 'forward_seconds': .1},
            {'event': 'small_judge', 'input_tokens': 200, 'generated_output_tokens': 1, 'forward_seconds': .2},
            {'event': 'http_request_effective', 'input_tokens': 1000},
        ])
        self.assertEqual(usage['small_judge_input_tokens'], 300)
        self.assertEqual(usage['small_judge_output_tokens'], 1)
        self.assertAlmostEqual(usage['small_judge_forward_sync_wall_seconds'], .3)

    def test_gold_identity_reject_requires_return_sha_actual_reject_and_separates_delivery(self):
        row = {'actual_reject': True, 'source_returned': True, 'judge_seen_full_source': True,
               'source_sha_valid': True, 'arguments': ['a.py', 'f'], 'canonical_tool': 'get_code_of_file_function'}
        self.assertEqual(len(evaluate.direct_prune([row], ['a.py::f'], {})), 1)
        for key in ('actual_reject', 'source_returned', 'source_sha_valid'):
            wrong = dict(row, **{key: False})
            self.assertEqual(evaluate.direct_prune([wrong], ['a.py::f'], {}), [])
        self.assertEqual(evaluate.direct_prune([row], ['a.py::other'], {}), [])
        partial = evaluate.direct_prune([dict(row, judge_seen_full_source=False, small_judge_route='reject')], ['a.py::f'], {})
        self.assertFalse(partial[0]['full_judge_source_delivered'])
        self.assertEqual(partial[0]['reject_route'], 'small_router_reject')
        gray = evaluate.direct_prune([dict(row, small_judge_route='qwen')], ['a.py::f'], {})
        self.assertEqual(gray[0]['reject_route'], 'gray_to_main_reject')

    def test_end_to_end_synthetic_only_outputs_and_cost_dedup(self):
        with tempfile.TemporaryDirectory(prefix='cosil-offline-eval-test-') as directory:
            root = Path(directory); run, old = root / 'new', root / 'old'
            def put(path, obj):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(obj))
            recs = []
            definitions = [{'kind': 'function', 'qualified_name': 'f', 'start_line': 1, 'end_line': 2}]
            index = {'a.py': {'definitions': definitions}}
            statuses = [('fully_mappable', ['a.py::f']), ('fully_mappable', ['a.py::f']),
                        ('partially_mappable', ['a.py::f']), ('unmappable', [])]
            for n, (mapping, targets) in enumerate(statuses):
                iid = f'example__example-{n}'
                jobfile = root / 'jobs' / iid / 'job.json'
                idxfile = jobfile.parent / 'code_index.json'
                job = {'instance_id': iid, 'repo': 'example/example', 'base_commit': '0' * 40, 'code_index': str(idxfile)}
                put(jobfile, job); put(idxfile, index)
                recs.append({'instance_id': iid, 'repo': job['repo'], 'base_commit': job['base_commit'], 'job': str(jobfile)})
                put(root / 'evaluator_private' / iid / 'gold.json', {'mapping_status': mapping, 'gold_functions': targets})
                put(run / 'frozen' / iid / 'frozen_context.json', {'candidates': [{'identity': 'a.py::f'}], 'manifest': {
                    'loaded_whole_files': ['a.py'], 'candidate_sha256': 'same', 'excluded_grep_evidence': []}})
                for method in (*evaluate.HISTORICAL, *evaluate.ARMS):
                    folder = (old if method in evaluate.HISTORICAL else run) / 'lite_pilot' / method / iid
                    overflow = method == 'A-FULL' and n == 1
                    put(folder / 'result.json', {'status': 'context_overflow' if overflow else 'complete',
                        'predicted_functions': [] if overflow else [{'path': 'a.py', 'qualified_name': 'f'}], 'elapsed_seconds': n + 1})
                    if method in evaluate.ARMS and not overflow:
                        put(folder / 'calls/0001_final/attempt_0_receipt.json', {
                            'request_id': method + iid, 'instance_id': iid, 'usage': {'prompt_tokens': 100, 'completion_tokens': 10},
                            'api_cost_usd_actual': .00001, 'api_cost_usd_normalized': .000042,
                            'http_status': 200, 'finish_reason': 'stop', 'start_utc': '2026-10-21T10:00:00+00:00'})
            put(run / 'run_manifest.json', {'records': recs, 'b2_ids': [recs[0]['instance_id']]})
            put(run / 'budget.json', {'stage_cap_usd': 3, 'attempts': {}})
            put(run / 'cpu_tests.json', {'passed': True, 'output': 'Ran 56 tests in 1.0s\nOK'})
            history_before = {str(p): p.read_bytes() for p in old.rglob('*') if p.is_file()}
            private_before = {str(p): p.read_bytes() for p in (root / 'evaluator_private').rglob('*') if p.is_file()}
            result = evaluate.build_report(run, old, root)
            self.assertEqual(result['historical_reproduction']['D-SIMPLE']['strict_hit5'], 2)
            self.assertEqual(result['new_request_count'], 7)
            self.assertAlmostEqual(result['new_cost_known_actual_usd'], .00007)
            self.assertEqual(history_before, {str(p): p.read_bytes() for p in old.rglob('*') if p.is_file()})
            self.assertEqual(private_before, {str(p): p.read_bytes() for p in (root / 'evaluator_private').rglob('*') if p.is_file()})
            required = ['ablation_pairwise.csv', 'tool_failure_taxonomy.csv', 'tool_protocol_per_call.csv',
                        'per_issue.csv', 'method_summary.csv', 'paired_comparisons.csv', 'cost_ledger.csv',
                        'final_diagnostic_report.md', 'README_如何复现.md',
                        'b2_matched_method_summary.csv', 'b2_mechanism_pairwise.csv']
            self.assertTrue(all((run / 'reports' / name).is_file() for name in required))
            report_text = (run / 'reports/final_diagnostic_report.md').read_text()
            self.assertIn('差值(pp)', report_text)
            self.assertIn('双方成功3同题对', report_text)
            self.assertIn('严格格式合约是离线按完整响应检查', report_text)
            self.assertIn('费用推算而非逐笔账单', report_text)
            self.assertIn('每题累计同步forward wall', report_text)
            self.assertIn('CPU测试56项全部通过', report_text)
            self.assertIn('provider json_mode=False', report_text)
            self.assertIn('没有本次完全相同的显式候选函数清单', report_text)
            pairs = evaluate.load_csv(run / 'reports/ablation_pairwise.csv')
            self.assertEqual(pairs[1]['pair_state_hit5'], 'SIGNATURE_win')
            structured = [x for x in result['summary'] if x['method'] == 'D-COSIL-STRUCTURED' and x['population'] == 'all_allocated'][0]
            self.assertEqual(structured['allocated_n'], 1)
            self.assertEqual(structured['observed_n'], 0)
            self.assertIsNone(structured['hit_5'])
            # Rebuilding report is safe and new cost is counted once again, not accumulated.
            second = evaluate.build_report(run, old, root)
            self.assertEqual(second['new_request_count'], 7)
            self.assertAlmostEqual(second['new_cost_known_actual_usd'], .00007)
            with self.assertRaisesRegex(RuntimeError, 'reproduction failed'):
                evaluate.build_report(run, old, root, expected_reference={'D-SIMPLE': 38})

    def test_navigation_suffix_excludes_file_init_and_measures_same_interval(self):
        def call(stage, tokens, cost, start, end):
            return {'stage': stage, 'prompt_tokens': tokens, 'completion_tokens': 2,
                    'api_cost_usd_actual': cost, 'api_cost_usd_normalized_peak_no_cache': cost * 2,
                    'start_utc': f'2026-10-21T10:00:{start:02d}+00:00',
                    'end_utc': f'2026-10-21T10:00:{end:02d}+00:00', 'billing_unknown': False}
        ledger = [call('file_selection', 10000, 1, 0, 2), call('initial_selection', 1000, .5, 3, 5),
                  call('node_selection', 100, .01, 10, 12), call('pruner', 200, .02, 13, 14),
                  call('final_summary', 300, .03, 15, 17)]
        result = evaluate.navigation_usage(ledger, {'small_judge_input_tokens': 400}, paid=True)
        self.assertEqual(result['navigation_http_input_tokens'], 600)
        self.assertEqual(result['navigation_total_model_input_tokens'], 1000)
        self.assertEqual(result['navigation_http_output_tokens'], 6)
        self.assertAlmostEqual(result['navigation_api_cost_usd_actual_known'], .06)
        self.assertEqual(result['navigation_request_count'], 3)
        self.assertEqual(result['navigation_measured_interval_seconds'], 7)
        self.assertEqual(result['navigation_interval_end_kind'], 'final_summary_end')
        failed = evaluate.navigation_usage(ledger[:-1], {}, paid=False)
        self.assertEqual(failed['navigation_measured_interval_seconds'], 4)
        self.assertEqual(failed['navigation_interval_end_kind'], 'last_observed_navigation_attempt_end')
        self.assertIsNone(failed['navigation_api_cost_usd_actual_known'])

    def test_b2_mechanism_summary_matches_only_frozen_twenty_ids(self):
        ids = {f'issue-{i}' for i in range(20)}
        rows = []
        for variant in evaluate.STRUCTURED:
            for method in (variant.removesuffix('-STRUCTURED'), variant):
                for n in range(25):
                    rows.append({'method': method, 'instance_id': f'issue-{n}', 'repo': 'r',
                                 'status': 'complete', 'entered_search': True, 'elapsed_seconds': 100,
                                 'time_scope': 'whole_pipeline' if method != variant else 'resumed',
                                 'navigation_http_input_tokens': 100 if method != variant else 80})
        def summary(items, population):
            return {'method': items[0]['method'], 'time_scope': items[0]['time_scope'],
                    'population': population, 'allocated_n': len(items), 'observed_n': len(items),
                    'input_tokens': 99999, 'input_tokens_mean': 99999, 'elapsed_seconds_mean': 100}
        with patch.object(evaluate, 'summarize', summary):
            summaries, paired = evaluate.b2_matched_tables(rows, ids)
        self.assertEqual(len(summaries), 18)
        self.assertTrue(all(r['allocated_n'] == r['cohort_n'] == 20 for r in summaries))
        self.assertTrue(all('input_tokens' not in r and 'elapsed_seconds_mean' not in r for r in summaries))
        self.assertEqual(len(paired), 60)
        self.assertEqual({r['instance_id'] for r in paired}, ids)
        self.assertTrue(all(r['navigation_http_input_tokens_new_minus_old'] == -20 for r in paired))
        self.assertFalse(any(r['pipeline_elapsed_comparable'] for r in paired))

    def test_report_entry_point_refuses_labels_before_a_complete(self):
        with tempfile.TemporaryDirectory(prefix='cosil-report-guard-test-') as directory:
            run = Path(directory)
            (run / 'run_manifest.json').write_text(json.dumps({'records': [{'instance_id': 'synthetic'}]}))
            with patch.object(evaluate, 'RUN', run), patch.object(evaluate, 'build_report') as build:
                with self.assertRaisesRegex(RuntimeError, 'Finish all allocated A'):
                    evaluate.main()
                build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
