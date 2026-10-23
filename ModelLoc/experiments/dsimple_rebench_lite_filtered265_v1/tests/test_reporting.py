"""Synthetic report-only CPU tests: no real benchmark labels, API or repo tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from paper_retest93 import reporting as R


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def row(iid, hit=1, *, origin='new221', status='complete', filehit=None, recall=None):
    filehit = hit if filehit is None else filehit
    out = {'instance_id': iid, 'repo': 'same/repo', 'origin': origin, 'is_new_inference': origin == 'new221',
           'status': status, 'status_family': R.B.status_family(status, executed=status != 'NOT_RUN'),
           'execution_attempted': status != 'NOT_RUN', 'http_attempted': status != 'NOT_RUN',
           'repository_observed_in_old100': origin == 'old100_reuse44', 'function_scorable': True, 'file_scorable': True,
           'function_evaluation_status': 'COMPLETE_NONEMPTY', 'function_eligibility_unknown': False,
           'file_eligibility_unknown': False, 'gold_function_count': 1, 'gold_functions': ['a.py::f'],
           'gold_files': ['a.py'], 'raw_predicted_files': ['a.py'] if filehit else [],
           'normalized_file_slots': ['a.py'] if filehit else [], 'raw_predicted_functions': [],
           'normalized_function_slots': ['a.py::f'] if hit else [], 'failure_category': 'ranking_omission_with_visible_source',
           'result_path': '/old/' + iid + '/result.json', 'context_path': '/old/' + iid + '/context.json',
           'gold_v2_path': '/gold/' + iid + '.json', 'base_context_verified': True,
           'final_http_context_delivered': True, 'source_delivery_proof': {}, 'source_integrity_errors': [],
           'input_tokens': 10, 'output_tokens': 2, 'usage_cost_usd': .1, 'known_usage_cost_usd': .1,
           'request_attempts': 1,
           'peak_no_cache_cost_usd': .2, 'elapsed_seconds': 2., 'process_cpu_seconds': .1,
           'billing_unknown_attempts': 0, 'cost_unknown_attempts': 0}
    for prefix, value in [('function', hit), ('file', filehit)]:
        for k in R.B.KS:
            for key, metric in R.B.score(['x'] if value else [], ['x'], k).items():
                out[prefix + '_' + key + '_' + str(k)] = metric if status != 'NOT_RUN' else None
        out[prefix + '_mrr_10'] = value if status != 'NOT_RUN' else None
    if recall is not None:
        out['function_recall_5'] = recall
    return out


def source_fixture(base, iid='case', *, prefix=None, extension='.py'):
    snapshot = base / iid / 'snapshot'; snapshot.mkdir(parents=True)
    text = 'def f():\n    return 123\n' if extension == '.py' else 'const value = 123;\n'
    path = 'a' + extension; (snapshot / path).write_text(text)
    index = {path: {'sha256': R.B.H.digest(text), 'definitions': [
        {'kind': 'function', 'qualified_name': 'f', 'start_line': 1, 'end_line': 2, 'def_line': 1}]}} if extension == '.py' else {}
    retained = text if prefix is None else text[:prefix]
    end = len(retained.splitlines()); last = R.full_line_prefix(text, retained, 1)
    block = {'path': path, 'start_line': 1, 'end_line': end, 'text': retained,
             'header': '--- SOURCE 1: ' + path + ' ---\n', 'sha256': R.B.H.digest(retained),
             'origin': 'selected_file', 'complete_file': prefix is None,
             'truncation': {'last_complete_line': last, 'original_body_tokens': 100,
                            'retained_body_tokens': 100 if prefix is None else 50}}
    job = {'instance_id': iid, 'repo': 'example/repo', 'base_commit': 'a' * 40, 'snapshot': str(snapshot),
           'paths': [path], 'problem_statement': 'A real issue description about return values.'}
    context = {'blocks': [block], 'ranked_edit_files': [path], 'loaded_whole_files': [path] if prefix is None else [],
               'skipped_files': []}
    raw = block['header'] + retained
    context.update(model_context_text=R.masked(raw, job), model_context_sha256=R.B.H.digest(R.masked(raw, job)))
    qualification = {'snapshot_sha256': {str(snapshot / path): R.B.H.digest(text)}}
    return job, index, context, qualification


def invalid_row(iid, path, qn):
    value = row(iid, 0)
    value.update(raw_predicted_functions=[{'path': path, 'qualified_name': qn}], normalized_function_slots=[None],
                 output_audit={'raw_final_json_valid': True, 'raw_ranked_functions_list': True},
                 failure_category='invalid_final_output', protocol_group='paper_params_retest93')
    return value


class ReportingTests(unittest.TestCase):
    def test_metadata_alias_recovery_is_diagnostic_only_not_a_score_repair(self):
        canonical = 'src/instructlab/sdg/blocks/llmblock.py'; qn = 'LLMMessagesBlock.__init__'
        value = invalid_row('instructlab__sdg-461', 'src/[BENCHMARK_METADATA]/blocks/llmblock.py', qn)
        original = copy.deepcopy(value)
        job = {'instance_id': value['instance_id'], 'base_commit': 'a'*40, 'repo': 'instructlab/sdg', 'paths': [canonical]}
        index = {canonical: {'definitions': [{'kind': 'function', 'qualified_name': qn}]}}
        context = {'model_context_text': '--- src/[BENCHMARK_METADATA]/blocks/llmblock.py ---', 'blocks': []}
        diagnostic = R.classify_output_identity(value, job, index, context)
        self.assertEqual(diagnostic['output_identity_subtypes'], ['metadata_alias_identity_boundary'])
        self.assertTrue(diagnostic['diagnostic_unmask_unique_base_identity'])
        self.assertFalse(diagnostic['source_sha_proves_canonical_paths_recoverable'])
        self.assertEqual(value, original)
        self.assertEqual(value['normalized_function_slots'], [None])
        self.assertEqual(value['function_hit_5'], 0)

    def test_existing_test_identity_is_scope_exclusion_not_malformed_json(self):
        path = 'stonesoup/types/tests/test_angle.py'
        value = invalid_row('stone', path, 'pytest_generate_tests')
        diagnostic = R.classify_output_identity(value, {'paths': [path]}, {}, {'blocks': []})
        self.assertEqual(diagnostic['output_identity_subtypes'], ['existing_test_scope_identity'])
        self.assertTrue(diagnostic['identity_diagnostic_json_valid'])
        self.assertTrue(diagnostic['output_identity_diagnostics'][0]['path_exists_in_clean_job'])

    def test_wrong_class_records_visible_method_but_missing_class_header(self):
        path = 'factory.py'; value = invalid_row('berri', path, 'Wrong.f')
        index = {path: {'definitions': [
            {'kind': 'class', 'qualified_name': 'Right', 'start_line': 1, 'def_line': 1, 'end_line': 4},
            {'kind': 'function', 'qualified_name': 'Right.f', 'start_line': 3, 'end_line': 4}]}}
        context = {'blocks': [{'path': path, 'start_line': 3, 'end_line': 4}]}
        diagnostic = R.classify_output_identity(value, {'paths': [path]}, index, context)
        self.assertEqual(diagnostic['output_identity_subtypes'], ['wrong_class_qualified_name'])
        evidence = diagnostic['output_identity_diagnostics'][0]['same_leaf_base_evidence'][0]
        self.assertTrue(evidence['function_full_in_final_context'])
        self.assertFalse(evidence['class_header_in_final_context'])
        self.assertEqual(value['function_hit_5'], 0)

    def test_invalid_subtype_breakdown_does_not_double_count_issue_union(self):
        values = [invalid_row('alias', 'src/[BENCHMARK_METADATA]/a.py', 'f'),
                  invalid_row('test', 'tests/test_a.py', 'f'), invalid_row('class', 'a.py', 'Wrong.f')]
        subtypes = ['metadata_alias_identity_boundary', 'existing_test_scope_identity', 'wrong_class_qualified_name']
        for value, subtype in zip(values, subtypes):
            value['output_identity_subtypes'] = [subtype]
            value['identity_diagnostic_json_valid'] = True
        text, categories, index = R.failure_report(values, [], {})
        self.assertEqual(categories, [{'category': 'invalid_final_output', 'count': 3}])
        self.assertEqual(len(index), 3)
        self.assertIn('并集为3题', text)
        self.assertIn('不额外加入上述总数', text)
        for subtype in subtypes:
            self.assertIn(subtype, text)

    def test_upstream_file_draw_path_alias_is_an_input_identity_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); canonical = 'lib/spack/spack/util/git.py'
            aliased = 'lib/[BENCHMARK_METADATA]/util/git.py'
            job = {'instance_id': 'spack__spack-51723', 'repo': 'spack/spack', 'base_commit': 'a'*40, 'paths': [canonical]}
            save(folder/'calls/0001_file_draw_0/request.json', {'request': {'messages': [{'content': aliased}]}})
            value = row(job['instance_id'], 0)
            result = R.path_alias_and_planner_audit(value, job, folder, {}, {'draws': [[aliased]], 'ranked_edit_files': []})
            self.assertTrue(result['metadata_path_alias_boundary'])
            self.assertTrue(result['metadata_alias_inventory_delivery_verified'])
            self.assertTrue(result['diagnostic_draw_aliases_uniquely_reversible'])
            self.assertEqual(result['canonical_selected_file_count'], 0)
            self.assertFalse(result['source_sha_proves_canonical_paths_recoverable'])
            self.assertEqual(value['function_hit_5'], 0)

    def test_owner_header_context_gap_can_involve_a_valid_other_owner_prediction(self):
        path = 'dataset.py'; value = row('nimare', 0)
        target = {'gold_identity': path+'::convert._analysis_to_dict', 'final_delivered_any_definition_full': True,
                  'same_leaf_different_identity_top10': [{'same_path': True, 'raw_qualified_name': 'Dataset._analysis_to_dict',
                                                       'normalized_slot': path+'::Dataset._analysis_to_dict'}]}
        index = {path: {'definitions': [{'kind': 'function', 'qualified_name': 'convert', 'start_line': 1, 'end_line': 8}]}}
        context = {'blocks': [{'path': path, 'start_line': 3, 'end_line': 5}]}
        result = R.owner_context_audit(value, [target], index, context)
        self.assertTrue(result['owner_identity_context_gap'])
        self.assertFalse(result['owner_identity_context_diagnostics'][0]['owner_header_in_final_context'])
        self.assertEqual(value['function_hit_5'], 0)

    def test_planner_syntax_and_schema_are_separate_diagnostics(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d); path = folder/'calls/0006_query_planning/result.json'
            job = {'instance_id': 'case', 'repo': 'a/b', 'base_commit': 'a'*40, 'paths': []}
            context = {'planner_errors': ['malformed_planner_json'], 'queries': []}
            save(path, {'content': '{"queries": [}'})
            result = R.path_alias_and_planner_audit(row('case'), job, folder, context, {})
            self.assertEqual(result['planner_error_subtype'], 'json_syntax_invalid')
            self.assertFalse(result['planner_json_syntax_valid'])
            save(path, {'content': '{"not_queries": []}'})
            result = R.path_alias_and_planner_audit(row('case'), job, folder, context, {})
            self.assertEqual(result['planner_error_subtype'], 'queries_field_missing')
            self.assertTrue(result['planner_json_syntax_valid'])

    def test_real_collect_keeps_scoring_but_verifies_masked_half_line_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); job, index, context, qualification = source_fixture(base, prefix=17)
            job['paths'].append('a.js')
            indexpath = base/'index.json'; save(indexpath, index)
            job['code_index'] = str(indexpath)
            jobpath = base/'job.json'; save(jobpath, job)
            folder = base/'result'; folder.mkdir()
            save(folder/'context.json', context)
            save(folder/'file_selection.json', {'ranked_edit_files': ['a.py']})
            save(folder/'inventory.json', {'paths': ['a.py', 'a.js']})
            prediction = [{'path': 'a.py', 'qualified_name': 'f'}]
            raw = {'instance_id': 'case', 'repo': job['repo'], 'base_commit': job['base_commit'], 'status': 'complete',
                   'method': 'D-SIMPLE', 'run_id': 'new', 'predicted_files': ['a.js', 'a.py'],
                   'predicted_functions': prediction, 'raw_output': json.dumps({'ranked_functions': prediction})}
            save(folder/'result.json', raw)
            req = {'messages': [{'role': 'user', 'content': '\n<context>\n'+context['model_context_text']+'\n</context>'}]}
            fp = R.B.H.digest(json.dumps(req, sort_keys=True, ensure_ascii=False))
            call = folder/'calls/0007_function_localization'
            save(call/'request.json', {'sha256': fp, 'request': req})
            usage = {'prompt_tokens': 10, 'completion_tokens': 1}
            receipt = {'request_id': 'new', 'instance_id': 'case', 'method': 'D-SIMPLE', 'run_id': 'new',
                       'stage': 'function_localization', 'sequence': 7, 'attempt': 0, 'request_sha256': fp,
                       'usage': usage, 'http_status': 200, 'finish_reason': 'stop', 'api_cost_usd_actual': .01}
            save(call/'attempt_0_receipt.json', receipt)
            save(base/'evaluator_private/eval_v2/filtered265/case/gold_v2.json',
                 {'instance_id': 'case', 'repo': job['repo'], 'base_commit': job['base_commit'],
                  'status': 'COMPLETE_NONEMPTY', 'existing_function_targets': ['a.py::f'], 'gold_files': ['a.py'],
                  'code_index_v2_path': str(indexpath), 'scope_exempt_changes': [], 'errors': [],
                  'changed_line_evidence': [{'change': '-', 'old_line': 2, 'base_function_id': 'a.py::f',
                    'matched_base_span': index['a.py']['definitions'][0]}]})
            preparation = base/'prep.json'; save(preparation, qualification)
            rec = {'instance_id': 'case', 'repo': job['repo'], 'base_commit': job['base_commit'], 'origin': 'paper_retest93',
                   'job': str(jobpath), 'result_dir': str(folder), 'preparation_receipt': str(preparation)}
            with patch.object(R.B.C, 'ROOT', base), patch.object(R.B.C, 'PREVIOUS', base/'old'):
                rows, targets, _ = R.collect_new({'n': 1, 'records': [rec]}, {})
            self.assertEqual(rows[0]['function_hit_5'], 1)
            self.assertEqual(rows[0]['normalized_file_slots'], [None, 'a.py'])
            self.assertEqual(rows[0]['file_prediction_scope_notes'][0]['scope_status'], 'existing_path_outside_business_python_evaluation_scope')
            self.assertTrue(rows[0]['base_context_verified'])
            self.assertTrue(rows[0]['final_http_context_delivered'])
            self.assertFalse(targets[0]['final_delivered_any_definition_full'])
            self.assertTrue(targets[0]['final_delivered_any_definition_partial'])
            self.assertFalse(targets[0]['actual_modified_implementation_verified'])

    def test_merge_unconditionally_keeps_worse_new_result(self):
        old = [row('correct'), row('retest', 1)]
        original = copy.deepcopy(old)
        new = [row('retest', 0)]
        merged = R.merge_rows(old, new, {'retest'})
        self.assertEqual(merged[1]['function_hit_5'], 0)
        self.assertEqual(merged[0]['protocol_group'], 'old_correct_reuse172')
        self.assertEqual(merged[1]['protocol_group'], 'paper_params_retest93')
        self.assertEqual(old, original)
        with self.assertRaises(RuntimeError):
            R.merge_rows(old, new, {'retest', 'missing'})

    def test_scope_union_does_not_confuse_recall_gap_with_miss(self):
        rows = [row('fn', 0, filehit=1), row('file', 1, filehit=0), row('both', 0),
                row('gap', 1, recall=.5), row('pending', 0, status='NOT_RUN')]
        wrong, pending = R.scope_sets(rows)
        self.assertEqual(wrong, {'fn', 'file', 'both'})
        self.assertEqual(pending, {'pending'})
        self.assertEqual(R.failure_kind(rows[3]), 'hit5_with_recall_gap')

    def test_half_last_line_never_proves_full_function(self):
        with tempfile.TemporaryDirectory() as d:
            job, index, context, qualification = source_fixture(Path(d), prefix=17)
            result = R.verify_prefix_context(job, index, context, qualification)
            self.assertTrue(result['base_context_verified'])
            self.assertEqual(context['blocks'][0]['end_line'], 1)
            self.assertFalse(R.B.H.intervals_cover(context['blocks'], 1, 2))
            context['blocks'][0]['text'] += 'wrong'
            self.assertFalse(R.verify_prefix_context(job, index, context, qualification)['base_context_verified'])

    def test_non_python_source_requires_materialized_raw_sha_not_ast(self):
        with tempfile.TemporaryDirectory() as d:
            job, index, context, qualification = source_fixture(Path(d), extension='.js')
            self.assertTrue(R.verify_prefix_context(job, index, copy.deepcopy(context), qualification)['base_context_verified'])
            self.assertFalse(R.verify_prefix_context(job, index, copy.deepcopy(context))['base_context_verified'])
            qualification['snapshot_sha256'][str(Path(job['snapshot'])/'a.js')] = 'bad'
            self.assertFalse(R.verify_prefix_context(job, index, copy.deepcopy(context), qualification)['base_context_verified'])

    def test_masked_final_context_must_match_actual_successful_request(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); job, _, context, _ = source_fixture(base)
            context['blocks'][0]['header'] += job['repo'] + ' ' + job['base_commit'] + '\n'
            raw = context['blocks'][0]['header'] + context['blocks'][0]['text']
            rendered = R.masked(raw, job)
            context.update(model_context_text=rendered, model_context_sha256=R.B.H.digest(rendered))
            call = base / 'out/calls/0007_function_localization'
            req = {'messages': [{'role': 'user', 'content': '\n<context>\n' + rendered + '\n</context>'}]}
            fingerprint = R.B.H.digest(json.dumps(req, sort_keys=True, ensure_ascii=False))
            save(call/'request.json', {'sha256': fingerprint, 'request': req})
            receipt = {'request_id': 'r', 'stage': 'function_localization', 'sequence': 7, 'http_status': 200,
                       'usage': {'prompt_tokens': 1}, 'instance_id': job['instance_id'], 'method': 'D-SIMPLE',
                       'run_id': 'new', 'request_sha256': fingerprint, 'finish_reason': 'stop'}
            proof = R.final_delivery(base/'out', context, [receipt], iid=job['instance_id'], expected_run_id='new', job=job)
            self.assertTrue(proof['final_http_context_delivered'])
            context['model_context_text'] += 'tampered'
            self.assertFalse(R.final_delivery(base/'out', context, [receipt], iid=job['instance_id'], expected_run_id='new', job=job)['final_http_context_delivered'])

    def test_finance_allows_more_than_old_cap_but_preserves_baseline(self):
        prior = {'key': 'D-SIMPLE|old', 'charged_upper_usd': 4.9, 'status': 'usage_received'}
        baseline = {'stage_cap_usd': 5., 'attempts': {'old': prior}}
        ledger = copy.deepcopy(baseline)
        ledger['attempts']['new'] = {'key': 'D-SIMPLE|case', 'charged_upper_usd': .4, 'usage': {'prompt_tokens': 2}}
        a = {'request_id': 'new', 'instance_id': 'case', 'usage': {'prompt_tokens': 2}, 'api_cost_usd_usage_estimate': .2}
        result = R.finance_summary([a, dict(a)], ledger, baseline)
        self.assertEqual(result['new_unique_http_attempts'], 1)
        self.assertEqual(result['usage_cost_usd'], .2)
        self.assertEqual(result['duplicate_request_ids_removed'], 1)
        ledger['attempts']['old']['charged_upper_usd'] = 0
        with self.assertRaises(RuntimeError):
            R.finance_summary([a], ledger, baseline)

    def test_failure_report_categories_first_every_iid_and_no_gap_as_miss(self):
        rows = R.merge_rows([row('miss', 0), row('file', 1, filehit=0), row('gap', 1, recall=.5)], [], set())
        text, categories, index = R.failure_report(rows, [], {r['instance_id']: {'problem_statement': 'Issue evidence'} for r in rows})
        self.assertEqual(sum(c['count'] for c in categories), 3)
        self.assertLess(text.index('| 主分类'), text.index('### file'))
        self.assertEqual({r['instance_id'] for r in index}, {'miss', 'file', 'gap'})
        self.assertIn('retained_old_hit5_recall_gap', {r['primary_category'] for r in index})
        for iid in ('miss', 'file', 'gap'):
            self.assertIn('### ' + iid, text)

    def test_strict_slots_and_p5_are_unchanged(self):
        index = {'a.py': {'definitions': [{'kind': 'function', 'qualified_name': 'C.f'},
                                        {'kind': 'function', 'qualified_name': 'C.f'}]}}
        slots, invalid = R.B.H.normalize_functions([{'path': 'a.py', 'qualified_name': 'f'},
            {'path': 'a.py', 'qualified_name': 'C.f'}, {'path': 'a.py', 'qualified_name': 'C.f'}], index)
        self.assertEqual(slots, [None, 'a.py::C.f', 'a.py::C.f'])
        self.assertEqual(invalid, 1)
        self.assertEqual(R.B.score(slots, ['a.py::C.f'], 5)['precision'], .2)

    def test_paired_function_na_preserved(self):
        a, b = row('case'), row('case', 0)
        a['function_hit_5'] = b['function_hit_5'] = None
        a['function_scorable'] = b['function_scorable'] = False
        paired = R.paired_table([a], [b], {'case'})[0]
        self.assertIsNone(paired['delta_function_hit_5'])
        self.assertEqual(paired['delta_file_hit_5'], -1)

    def test_paired_wins_are_metric_specific(self):
        old, new = row('case', 1, recall=.5), row('case', 1, recall=1.)
        stats = {r['metric']: r for r in R.paired_summary(R.paired_table([old], [new], {'case'}), repeats=20)}
        self.assertEqual(stats['function_hit_5']['tie_n'], 1)
        self.assertEqual(stats['function_hit_5']['new_better_n'], 0)
        self.assertEqual(stats['function_recall_5']['new_better_n'], 1)
        self.assertEqual(stats['function_recall_5']['new_minus_old'], .5)

    def test_output_escape_rejected(self):
        with self.assertRaises(PermissionError):
            R.output('../../old/report.md', 'bad')

    def test_report_workflow_writes_separate_outputs_preserves_history_and_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); run = base/'runs/new'; manifestpath = base/'manifests/new.json'
            oldrows = [row('keep'), row('wrong', 0), row('pending', 0, status='NOT_RUN')]
            newrows = [row('wrong'), row('pending')]
            original_records = []
            for prior in oldrows:
                iid = prior['instance_id']; jobpath = base/'jobs'/iid/'job.json'
                save(jobpath, {'problem_statement': 'Synthetic issue facts'})
                original_records.append({'instance_id': iid, 'repo': prior['repo'], 'base_commit': 'a'*40,
                                         'origin': 'new221', 'job': str(jobpath), 'result_dir': str(base/'old'/iid)})
            original = {'n': 3, 'records': original_records}
            selected_records = []
            for new in newrows:
                rec = dict(next(r for r in original_records if r['instance_id'] == new['instance_id']))
                rec.update(origin='paper_retest93', result_dir=str(run/R.C.COHORT/'D-SIMPLE'/rec['instance_id']))
                new['result_path'] = str(Path(rec['result_dir'])/'result.json')
                selected_records.append(rec)
            save(base/'manifests/filtered265.json', original)
            save(manifestpath, {'n': 2, 'records': selected_records})
            baseline = {'attempts': {'prior': {'key': 'D-SIMPLE|prior', 'charged_upper_usd': 4.9}}}
            ledger = copy.deepcopy(baseline); attempts = []
            for new in newrows:
                iid = new['instance_id']; usage = {'prompt_tokens': 10, 'completion_tokens': 2}
                ledger['attempts'][iid] = {'key': 'D-SIMPLE|'+iid, 'usage': usage, 'charged_upper_usd': .1}
                attempts.append({'request_id': iid, 'instance_id': iid, 'usage': usage,
                                 'api_cost_usd_usage_estimate': .1})
            ledgerpath = base/'finance/budget.json'; save(ledgerpath, ledger)
            save(run/'financial_baseline.json', baseline)
            sentinel = base/'reports/filtered265/original.md';sentinel.parent.mkdir(parents=True);sentinel.write_text('preserved')
            before = {p: p.read_bytes() for p in (ledgerpath, sentinel, base/'manifests/filtered265.json')}
            with patch.object(R.C, 'ROOT', base), patch.object(R.C, 'RUN', run), patch.object(R.C, 'MANIFEST', manifestpath), \
                 patch.object(R.C, 'SHARED_BUDGET', ledgerpath), patch.object(R.B, 'collect', return_value=(oldrows, [], [])), \
                 patch.object(R, 'collect_new', return_value=(newrows, [], attempts)):
                result = R.run_report(expected_counts=None, ci_repeats=20)
            self.assertEqual(result['allocation']['merged'], 3)
            self.assertEqual(result['allocation']['old_correct_reused'], 1)
            self.assertEqual(result['finance']['new_unique_http_attempts'], 2)
            self.assertFalse(result['best_of_old_new'])
            for path, raw in before.items():
                self.assertEqual(path.read_bytes(), raw)
            for name in ('merged265_per_issue.csv', 'new93_per_issue.csv', 'paired28.csv', 'paired28_summary.csv',
                         '本轮93题_逐题资源.csv', '合并265题_总览.md', '定位失败分析报告.md', 'evaluation_summary.json'):
                self.assertTrue((base/'reports/paper_retest93'/name).is_file(), name)


if __name__ == '__main__':
    unittest.main()
