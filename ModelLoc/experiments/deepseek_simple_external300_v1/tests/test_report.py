"""Only synthetic labels/source in temporary directories; no live benchmark."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from supplement_v1 import report
from src.code_index import file_record


SOURCE = ('class Query:\n'
          '    def from_string(self):\n'
          '        def parse(value):\n'
          '            return value\n'
          '        return parse("x")\n'
          'def other():\n'
          '    return 1\n'
          'def gold():\n'
          '    return 2\n')


class ReportTests(unittest.TestCase):
    def target_fixture(self, *, paths=None, loaded=None, blocks=None, inventory=None):
        index = {'a.py': file_record('a.py', SOURCE)}
        loaded = ['a.py'] if loaded is None else loaded
        paths = ['a.py'] if paths is None else paths
        if blocks is None:
            blocks = [{'path': 'a.py', 'start_line': 1, 'end_line': 9, 'text': SOURCE,
                       'sha256': report.digest(SOURCE), 'complete_file': True}]
        context = {'loaded_whole_files': loaded, 'blocks': blocks, 'skipped_files': [], 'ranked_edit_files': paths}
        selection = {'ranked_edit_files': paths}
        inventory = {'paths': paths} if inventory is None else inventory
        gold = {'gold_files': ['a.py'], 'gold_functions': ['a.py::gold'], 'mapping_status': 'fully_mappable',
                'changed_line_evidence': [{'function_id': 'a.py::gold', 'change': '-', 'line': 9}]}
        integrity = {'base_context_verified': True, 'blocks': [{'source_valid': True} for b in blocks]}
        proof = {'final_http_context_delivered': True}
        audit = {'raw_final_json_valid': True, 'raw_ranked_functions_list': True, 'invalid_slots_top5': []}
        return gold, index, context, inventory, selection, proof, integrity, audit

    def targets(self, fixture, slots):
        gold, index, context, inventory, selection, proof, integrity, audit = fixture
        return report.target_diagnostics('synthetic', gold, index, context, inventory, selection, proof, integrity, slots, audit)

    def test_top5_fixed_slots_property_and_exact_names(self):
        index = {'a.py': file_record('a.py', 'class A:\n @property\n def p(self): pass\n @p.setter\n def p(self,x): pass\ndef gold(): pass\n')}
        job = {'paths': ['a.py']}
        gold = {'gold_files': ['a.py'], 'gold_functions': ['a.py::gold', 'a.py::A.p']}
        raw = [{'path': 'a.py', 'qualified_name': 'A.p'}, {'path': 'a.py', 'qualified_name': 'A.p'},
               {'path': 'a.py', 'qualified_name': 'p'}, None, {'path': 'a.py', 'qualified_name': 'gold'}]
        result = report.score_result({'status': 'complete', 'predicted_functions': raw}, gold, job, index, {})
        self.assertEqual(result['normalized_function_slots'], ['a.py::A.p', 'a.py::A.p', None, None, 'a.py::gold'])
        self.assertEqual(result['function_precision_5'], .4)
        self.assertEqual(result['function_recall_5'], 1)
        self.assertEqual(result['function_mrr_10'], 1)
        self.assertEqual(result['invalid_function_slots'], 2)

    def test_rank_six_is_cutoff_without_compacting_duplicate_slots(self):
        row = self.targets(self.target_fixture(), ['a.py::other'] * 5 + ['a.py::gold'])[0]
        self.assertEqual(row['target_primary_cause'], 'rank_cutoff_at_5')
        self.assertEqual(row['gold_rank_top10'], 6)
        self.assertFalse(row['hit_at_5'])
        self.assertEqual(row['changed_base_deleted_line_coverage'], 1)

    def test_outer_instead_of_nested_is_diagnostic_only(self):
        fixture = self.target_fixture()
        fixture[0]['gold_functions'] = ['a.py::Query.from_string.parse']
        row = self.targets(fixture, ['a.py::Query.from_string'])[0]
        self.assertEqual(row['target_primary_cause'], 'ranking_omission_with_visible_source')
        self.assertIn('predicted_outer_instead_of_nested_gold', row['labels'])
        self.assertFalse(row['hit_at_5'])

    def test_grep_recovers_path_omitted_from_selection_inventory(self):
        fixture = self.target_fixture(paths=['b.py'], loaded=[], inventory={'paths': ['b.py']})
        row = self.targets(fixture, ['a.py::other'])[0]
        self.assertEqual(row['target_primary_cause'], 'ranking_omission_with_visible_source')
        self.assertIn('grep_recovered_unselected_gold_identity', row['labels'])
        self.assertIn('gold_path_not_in_displayed_inventory', row['labels'])
        self.assertFalse(row['loaded_whole_file'])

    def test_inventory_and_selection_misses_and_partial_grep_are_separate(self):
        fixture = self.target_fixture(paths=['b.py'], loaded=[], blocks=[], inventory={'paths': ['b.py']})
        self.assertEqual(self.targets(fixture, ['a.py::other'])[0]['target_primary_cause'], 'inventory_filter_and_grep_no_recovery')
        fixture[3]['paths'].append('a.py')
        self.assertEqual(self.targets(fixture, ['a.py::other'])[0]['target_primary_cause'], 'file_selection_and_grep_no_recovery')
        partial = {'path': 'a.py', 'start_line': 9, 'end_line': 9, 'text': '    return 2\n',
                   'sha256': report.digest('    return 2\n'), 'complete_file': False}
        fixture = self.target_fixture(paths=['b.py'], loaded=[], blocks=[partial])
        self.assertEqual(self.targets(fixture, ['a.py::other'])[0]['target_primary_cause'], 'grep_only_partial_gold_context')

    def test_whole_file_overflow_and_five_file_limit_are_distinct(self):
        fixture = self.target_fixture(loaded=[], blocks=[])
        fixture[2]['skipped_files'] = [{'path': 'a.py', 'reason': 'whole_file_overflow', 'reference_tokens': 90000}]
        self.assertEqual(self.targets(fixture, ['a.py::other'])[0]['target_primary_cause'], 'selected_whole_file_overflow')
        paths = [f'{i}.py' for i in range(5)] + ['a.py']
        fixture = self.target_fixture(paths=paths, loaded=paths[:5], blocks=[])
        self.assertEqual(self.targets(fixture, ['a.py::other'])[0]['target_primary_cause'], 'selected_five_file_limit')

    def test_unmappable_partial_and_mixed_causes_never_become_strict_mislabels(self):
        result = {'status': 'complete'}; integrity = {'base_context_verified': True}
        metrics = {'function_hit_5': 0, 'function_recall_5': 0}
        self.assertEqual(report.issue_primary(result, {'mapping_status': 'unmappable', 'gold_functions': []}, metrics, [], integrity), 'truth_unmappable')
        self.assertEqual(report.issue_primary(result, {'mapping_status': 'partially_mappable', 'gold_functions': ['a.py::f']}, metrics, [], integrity), 'partial_auxiliary_miss')
        targets = [{'hit_at_5': False, 'target_primary_cause': 'file_selection_and_grep_no_recovery'},
                   {'hit_at_5': False, 'target_primary_cause': 'ranking_omission_with_visible_source'}]
        self.assertEqual(report.issue_primary(result, {'mapping_status': 'fully_mappable', 'gold_functions': ['a.py::f', 'b.py::g']}, metrics, targets, integrity), 'mixed_visibility_and_ranking')

    def test_http_delivery_requires_exact_payload_and_matching_success(self):
        with tempfile.TemporaryDirectory(prefix='external300-http-unit-') as directory:
            folder = Path(directory)
            path = folder / 'calls/0007_function_localization/request.json'; path.parent.mkdir(parents=True)
            text = 'def gold():\n return 1\n'
            context = {'blocks': [{'header': 'SOURCE a.py\n', 'text': text, 'sha256': report.digest(text)}]}
            wire = {'model': 'deepseek-flash', 'thinking': {'type': 'disabled'},
                    'messages': [{'role': 'user', 'content': '<issue>x</issue>\n<context>\nSOURCE a.py\n' + text + '\n</context>'}]}
            saved = {'request': wire, 'sha256': report.digest(json.dumps(wire, sort_keys=True, ensure_ascii=False))}
            path.write_text(json.dumps(saved))
            receipt = {'stage': 'function_localization', 'sequence': 7, 'http_status': 200, 'usage': {'prompt_tokens': 3},
                       'instance_id': 'synthetic', 'method': 'D-SIMPLE', 'run_id': 'unit', 'request_sha256': saved['sha256'], 'request_id': 'unique'}
            proof = report.final_delivery(folder, context, [receipt], iid='synthetic', expected_run_id='unit')
            self.assertTrue(proof['final_http_context_delivered'])
            bad = dict(receipt, http_status=500)
            self.assertFalse(report.final_delivery(folder, context, [bad], iid='synthetic', expected_run_id='unit')['final_http_context_delivered'])
            context['blocks'][0]['text'] = 'changed'
            self.assertEqual(report.final_delivery(folder, context, [receipt], iid='synthetic', expected_run_id='unit')['delivery_error'], 'context_block_sha_mismatch')

    def test_base_sha_empty_whole_file_and_grep_origin(self):
        with tempfile.TemporaryDirectory(prefix='external300-base-unit-') as directory:
            root = Path(directory); (root / 'a.py').write_text(SOURCE); (root / 'empty.py').write_text('')
            index = {'a.py': file_record('a.py', SOURCE), 'empty.py': file_record('empty.py', '')}
            context = {'loaded_whole_files': ['empty.py'], 'blocks': [
                {'path': 'empty.py', 'start_line': 1, 'end_line': 0, 'text': '', 'sha256': report.digest(''), 'complete_file': True},
                {'path': 'a.py', 'start_line': 1, 'end_line': 9, 'text': SOURCE, 'sha256': report.digest(SOURCE), 'complete_file': True}]}
            audit = report.verify_base_context({'snapshot': str(root)}, index, context)
            self.assertTrue(audit['base_context_verified'])
            self.assertEqual(audit['blocks'][1]['origin'], 'grep_evidence')
            (root / 'a.py').write_text(SOURCE + '# drift\n')
            self.assertFalse(report.verify_base_context({'snapshot': str(root)}, index, context)['base_context_verified'])

    def test_confidence_is_deterministic_and_mean_precision_is_fixed_k(self):
        first = report.confidence([1, 0, 1], ['r1', 'r2', 'r2'], repeats=1000)
        self.assertEqual(first, report.confidence([1, 0, 1], ['r1', 'r2', 'r2'], repeats=1000))
        self.assertTrue(first['issue_bootstrap95'][0] <= 2 / 3 <= first['issue_bootstrap95'][1])
        self.assertEqual(report.confidence([], [])['issue_bootstrap95'], [None, None])

    def test_synthetic_end_to_end_cohort_join_outputs_and_historical_preservation(self):
        with tempfile.TemporaryDirectory(prefix='external300-report-unit-') as directory:
            base = Path(directory); root = base / 'new'; previous = base / 'old'; run = root / 'runs/new-unit'
            def put(path, obj):
                path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(obj))
            records = []
            for n, (origin, mapping, target, predictions) in enumerate([
                ('previous100', 'fully_mappable', 'a.py::gold', ['gold']),
                ('previous100', 'partially_mappable', 'a.py::gold', ['gold']),
                ('additional200', 'fully_mappable', 'a.py::gold', ['other'] * 5 + ['gold']),
                ('additional200', 'fully_mappable', 'a.py::Query.from_string.parse', ['Query.from_string']),
                ('additional200', 'partially_mappable', 'a.py::gold', ['other']),
                ('additional200', 'unmappable', None, ['other']),
            ]):
                iid = f'example__example-{n}'; case_root = previous if origin == 'previous100' else root
                snapshot = base / 'base-cache' / iid; snapshot.mkdir(parents=True); (snapshot / 'a.py').write_text(SOURCE)
                index = {'a.py': file_record('a.py', SOURCE)}
                jobpath = case_root / 'jobs' / iid / 'job.json'; indexpath = jobpath.parent / 'code_index.json'
                job = {'instance_id': iid, 'repo': f'example/repo{n}', 'base_commit': 'a' * 40, 'problem_statement': 'Parser returns wrong nested value.',
                       'snapshot': str(snapshot), 'code_index': str(indexpath), 'paths': ['a.py']}
                put(jobpath, job); put(indexpath, index)
                record = {'instance_id': iid, 'repo': job['repo'], 'base_commit': job['base_commit'], 'job': str(jobpath), 'origin': origin}
                records.append(record)
                put(case_root / 'evaluator_private' / iid / 'gold.json', {'mapping_status': mapping, 'gold_files': ['a.py'], 'gold_functions': [target] if target else [], 'changed_line_evidence': []})
                folder = (previous / 'runs' / report.PREVIOUS_RUN_ID / 'external/D-SIMPLE' / iid) if origin == 'previous100' else run / report.COHORT / 'D-SIMPLE' / iid
                funcs = [{'path': 'a.py', 'qualified_name': q} for q in predictions]
                raw = json.dumps({'ranked_functions': funcs})
                put(folder / 'result.json', {'status': 'complete', 'predicted_files': ['a.py'], 'predicted_functions': funcs, 'raw_output': raw, 'elapsed_seconds': 2, 'process_cpu_seconds': .1})
                block = {'path': 'a.py', 'start_line': 1, 'end_line': 9, 'text': SOURCE, 'sha256': report.digest(SOURCE), 'header': 'SOURCE a.py\n', 'complete_file': True}
                put(folder / 'context.json', {'loaded_whole_files': ['a.py'], 'ranked_edit_files': ['a.py'], 'blocks': [block], 'skipped_files': []})
                put(folder / 'file_selection.json', {'ranked_edit_files': ['a.py']})
                put(folder / 'inventory.json', {'paths': ['a.py']})
                wire = {'model': 'deepseek-flash', 'thinking': {'type': 'disabled'}, 'messages': [{'role': 'user', 'content': '<issue>x</issue>\n<context>\n' + block['header'] + SOURCE + '\n</context>'}]}
                fingerprint = report.digest(json.dumps(wire, sort_keys=True, ensure_ascii=False))
                put(folder / 'calls/0007_function_localization/request.json', {'request': wire, 'sha256': fingerprint})
                receipt = {'stage': 'function_localization', 'sequence': 7, 'http_status': 200, 'usage': {'prompt_tokens': 100, 'completion_tokens': 10},
                           'api_cost_usd_actual': .00001, 'api_cost_usd_normalized': .000042,
                           'instance_id': iid, 'method': 'D-SIMPLE', 'run_id': report.PREVIOUS_RUN_ID if origin == 'previous100' else run.name,
                           'request_sha256': fingerprint, 'request_id': 'rid-' + str(n), 'finish_reason': 'stop'}
                put(folder / 'calls/0007_function_localization/attempt_0_receipt.json', receipt)
                # A copied receipt is charged only once.
                put(folder / 'calls/0007_function_localization/attempt_0_extra_receipt.json', receipt)
            put(root / 'manifests/additional200.json', {'records': [r for r in records if r['origin'] == 'additional200']})
            put(root / 'manifests/combined300.json', {'records': list(reversed(records))})
            put(run / 'budget.json', {'stage_cap_usd': report.BUDGET_USD, 'attempts': {}})
            old_before = {str(p): p.read_bytes() for p in previous.rglob('*') if p.is_file()}
            result = report.build_report(root, previous, run, expected_counts=None, verify_previous=False)
            indexed = {s['cohort']: s for s in result['summaries']}
            self.assertEqual(indexed['previous100']['strict_hit5_count'], 1)
            self.assertEqual(indexed['additional200']['strict_n'], 2)
            self.assertEqual(indexed['combined300']['strict_n'], 3)
            self.assertEqual(indexed['combined300']['strict_hit5_count'], 1)
            self.assertEqual(indexed['additional200']['strict_hit5_misses_observed'], 2)
            self.assertAlmostEqual(result['cost_accounting']['new_usage_estimated_usd'], .00004)
            self.assertEqual(result['cost_accounting']['new_request_attempts'], 4)
            self.assertEqual(old_before, {str(p): p.read_bytes() for p in previous.rglob('*') if p.is_file()})
            required = ['per_issue.csv', 'method_summary.csv', 'failure_targets.csv', 'source_delivery_audit.csv',
                        'cost_ledger.csv', 'strict_hit5_failures.csv', 'strict_recall5_gaps.csv', 'partial_auxiliary_misses.csv',
                        'results.json', 'final_report.md', '未命中逐题归因.md']
            self.assertTrue(all((root / 'reports' / name).is_file() for name in required))
            text = (root / 'reports/未命中逐题归因.md').read_text()
            self.assertIn('Top5截断', text)
            self.assertIn('predicted_outer_instead_of_nested_gold', text)
            self.assertIn('partial辅助未命中（非严格模型失败）', text)
            first = result['cost_accounting']['new_usage_estimated_usd']
            again = report.build_report(root, previous, run, expected_counts=None, verify_previous=False)
            self.assertEqual(first, again['cost_accounting']['new_usage_estimated_usd'])
            self.assertEqual(old_before, {str(p): p.read_bytes() for p in previous.rglob('*') if p.is_file()})

    def test_report_output_cannot_escape_reports(self):
        with tempfile.TemporaryDirectory(prefix='external300-write-unit-') as directory:
            with self.assertRaises(PermissionError):
                report.report_write(Path(directory), '../outside.json', {}, json_value=True)


if __name__ == '__main__':
    unittest.main()
