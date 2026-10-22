"""Synthetic CPU verification; no benchmark gold, providers, API or repo tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from filtered265 import report as R


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def aggregate_row(iid, *, status='complete', hit=1, origin=R.NEW_ORIGIN, family=None,
                  executed=True, http=True, state='COMPLETE_NONEMPTY', unknown=False):
    family = family or R.status_family(status, executed=executed)
    row = {'instance_id': iid, 'repo': 'same/repo', 'origin': origin,
           'is_new_inference': origin == R.NEW_ORIGIN, 'status': status, 'status_family': family,
           'execution_attempted': executed, 'http_attempted': http, 'repository_observed_in_old100': origin == R.REUSE_ORIGIN,
           'function_evaluation_status': state, 'function_eligibility_unknown': state in ('INCOMPLETE', 'evaluation_unavailable'),
           'file_eligibility_unknown': state == 'evaluation_unavailable', 'function_scorable': state == 'COMPLETE_NONEMPTY',
           'file_scorable': state != 'evaluation_unavailable', 'gold_function_count': int(state == 'COMPLETE_NONEMPTY'),
           'input_tokens': None if unknown else 10, 'output_tokens': None if unknown else 2,
           'usage_cost_usd': None if unknown else .1, 'known_usage_cost_usd': 0 if unknown else .1,
           'peak_no_cache_cost_usd': None if unknown else .2, 'elapsed_seconds': 3., 'process_cpu_seconds': .2,
           'billing_unknown_attempts': int(unknown), 'cost_unknown_attempts': int(unknown)}
    for prefix in ('file', 'function'):
        for k in R.KS:
            metrics = R.score(['x'] if hit else [], ['x'], k)
            for key, val in metrics.items():
                row[f'{prefix}_{key}_{k}'] = None if family == 'NOT_RUN' or not row[prefix + '_scorable'] else val
        row[prefix + '_mrr_10'] = None if family == 'NOT_RUN' or not row[prefix + '_scorable'] else hit
    return row


class ReportTests(unittest.TestCase):
    def test_strict_slots_fixed_k_and_shared_identity(self):
        index = {'a.py': {'definitions': [{'kind': 'function', 'qualified_name': 'C.x'},
                                        {'kind': 'function', 'qualified_name': 'C.x'}]}}
        slots, invalid = R.H.normalize_functions([{'path': 'a.py', 'qualified_name': 'C.x'},
                                                  {'path': 'a.py', 'qualified_name': 'x'},
                                                  {'path': 'a.py', 'qualified_name': 'C.x'}], index)
        self.assertEqual(slots, ['a.py::C.x', None, 'a.py::C.x'])
        self.assertEqual(invalid, 1)
        self.assertEqual(R.score(slots, ['a.py::C.x', 'a.py::y'], 3),
                         {'hit': 1, 'precision': 1/3, 'recall': .5, 'f1': .4, 'all_coverage': 0})
        self.assertEqual(R.score([], ['x'], 5)['precision'], 0)
        self.assertIsNone(R.score(['x'], [], 5)['hit'])

    def test_valid_empty_output_has_visibility_cause(self):
        target = {'target_primary_cause': 'invalid_final_output', 'final_delivered_any_definition_full': True}
        out = R.fix_valid_empty_causes([target], [], {'raw_final_json_valid': True, 'raw_ranked_functions_list': True})
        self.assertEqual(out[0]['target_primary_cause'], 'valid_empty_prediction_with_visible_source')

    def test_allocation_and_execution_keep_failures_and_separate_notrun(self):
        rows = [aggregate_row('a'), aggregate_row('b', status='failed', hit=0),
                aggregate_row('c', status='budget_exceeded', hit=0),
                aggregate_row('d', status='NOT_RUN', hit=0, executed=False, http=False)]
        a = R.summarize(rows, 'a', ci_repeats=40)
        e = R.summarize(rows, 'e', population='executed', ci_repeats=40)
        self.assertEqual((a['function_denominator'], e['function_denominator']), (4, 3))
        self.assertEqual(a['function_hit_5'], .25)
        self.assertEqual(e['function_hit_5'], 1/3)
        self.assertEqual(a['function_hit_5_allocation_uncertainty_bounds'], [.25, .5])
        self.assertEqual((a['not_run_n'], a['budget_stopped_n'], a['model_or_output_failure_n']), (1, 1, 1))
        self.assertEqual(a['resource_population_n'], 3)
        self.assertEqual(a['score_semantics'], 'allocation_completion_credit_lower_bound')
        self.assertIsNone(rows[-1]['function_hit_5'])

    def test_unavailable_incomplete_and_empty_never_blend(self):
        rows = [aggregate_row('a'), aggregate_row('b', state='COMPLETE_EMPTY'),
                aggregate_row('c', state='INCOMPLETE'), aggregate_row('d', state='evaluation_unavailable')]
        summary = R.summarize(rows, 'a', ci_repeats=30)
        self.assertEqual(summary['function_denominator'], 1)
        self.assertEqual(summary['function_empty_n'], 1)
        self.assertEqual(summary['incomplete_n'], 1)
        self.assertEqual(summary['evaluation_unavailable_n'], 1)
        self.assertEqual(summary['allocation_function_eligibility_unknown_n'], 2)

    def test_orphan_http_and_local_start_are_not_notrun(self):
        self.assertEqual(R.classify_missing_result({'status': 'NOT_RUN'}, [{}])['status'], 'attempted_without_terminal_result')
        self.assertEqual(R.classify_missing_result({'status': 'NOT_RUN'}, [], started=True)['status'], 'execution_started_without_terminal_result')
        self.assertEqual(R.classify_missing_result({'status': 'NOT_RUN'}, [])['status'], 'NOT_RUN')

    def test_unknown_usage_and_cost_are_not_zero(self):
        attempt = {'billing_unknown': True, 'input_tokens': 0, 'output_tokens': 0,
                   'api_cost_usd_usage_estimate': None, 'api_cost_usd_peak_no_cache': None}
        totals = R.resource_totals([attempt])
        self.assertIsNone(totals['input_tokens']); self.assertIsNone(totals['usage_cost_usd'])
        self.assertEqual((totals['known_usage_cost_usd'], totals['cost_unknown_attempts']), (0, 1))
        self.assertEqual(R.resource_totals([])['usage_cost_usd'], 0)
        unknown = aggregate_row('a', unknown=True)
        summary = R.summarize([unknown], 'new', ci_repeats=20)
        self.assertIsNone(summary['new_api_usage_cost_usd'])
        self.assertEqual(summary['known_usage_cost_usd'], 0)

    def test_cluster_bootstrap_repeated_repos_reproducible(self):
        a = R.ci([0, 0, 1, 1], ['a', 'a', 'b', 'b'], repeats=1000)
        self.assertEqual(a, R.ci([0, 0, 1, 1], ['a', 'a', 'b', 'b'], repeats=1000))
        self.assertEqual(a['repo_cluster_bootstrap95'], [0., 1.])

    def test_manifest_rejects_duplicates_and_unexpected_origin(self):
        with self.assertRaises(ValueError):
            R.validate_manifest({'n': 2, 'records': [{'instance_id': 'x', 'origin': R.NEW_ORIGIN}]*2})
        with self.assertRaises(ValueError):
            R.validate_manifest({'n': 1, 'records': [{'instance_id': 'x', 'origin': 'old215'}]})

    def test_output_rejects_escape(self):
        with self.assertRaises(PermissionError):
            R.output('../../escaped.md', 'bad')

    def test_shared_budget_preserves_prior_lite_and_unknown_reservations(self):
        base = {'stage_cap_usd': 5., 'attempts': {'prior': {'key': 'D-SIMPLE|old', 'status': 'usage_received', 'charged_upper_usd': 3.24130776}}, 'cases': {}}
        budget = copy.deepcopy(base)
        budget['attempts']['new'] = {'key': 'D-SIMPLE|newcase', 'status': 'usage_received', 'charged_upper_usd': .2, 'usage': {'prompt_tokens': 2}}
        new = {'request_id': 'new', 'instance_id': 'newcase', 'origin': R.NEW_ORIGIN, 'usage': {'prompt_tokens': 2},
               'api_cost_usd_usage_estimate': .1}
        old = {'request_id': 'reuse', 'instance_id': 'oldcase', 'origin': R.REUSE_ORIGIN, 'usage': {},
               'api_cost_usd_usage_estimate': .03}
        summary = R.financial_summary([new, old], budget, base)
        self.assertAlmostEqual(summary['shared_charged_upper_usd'], 3.44130776)
        self.assertEqual(summary['baseline_charged_upper_usd'], 3.24130776)
        self.assertEqual(summary['new_usage_cost_usd'], .1)
        self.assertEqual(summary['historical_reuse_usage_cost_usd'], .03)
        budget['attempts']['reserved'] = {'key': 'D-SIMPLE|inflight', 'status': 'reserved', 'charged_upper_usd': .2}
        summary = R.financial_summary([new, old], budget, base)
        self.assertIsNone(summary['new_usage_cost_usd'])
        self.assertEqual(summary['known_new_usage_cost_usd'], .1)
        self.assertEqual(summary['unlinked_current_ledger_request_ids'], ['reserved'])
        bad = copy.deepcopy(budget); bad['attempts']['prior']['charged_upper_usd'] = 0
        with self.assertRaises(RuntimeError): R.financial_summary([new], bad, base)

    def test_contradictory_duplicate_receipts_rejected(self):
        a = {'request_id': 'x', 'instance_id': 'a', 'usage': {}}
        self.assertEqual(len(R.deduplicate_receipts([a, dict(a)])), 1)
        with self.assertRaises(RuntimeError): R.deduplicate_receipts([a, dict(a, instance_id='b')])


class CollectTests(unittest.TestCase):
    def fixture(self, base, iid='case-1', *, result=True, receipt=True, gold=True):
        snapshot = base / iid / 'snapshot'; snapshot.mkdir(parents=True)
        text = 'def f():\n    return 1\n'; (snapshot / 'a.py').write_text(text)
        defs = [{'kind': 'function', 'qualified_name': 'f', 'start_line': 1, 'end_line': 2, 'def_line': 1}]
        index = {'a.py': {'sha256': R.H.digest(text), 'definitions': defs}}
        indexpath = base / iid / 'index.json'; write(indexpath, index)
        job = {'instance_id': iid, 'repo': 'example/repo', 'base_commit': 'a'*40, 'paths': ['a.py'],
               'snapshot': str(snapshot), 'code_index': str(indexpath)}
        jobpath = base / iid / 'job.json'; write(jobpath, job)
        folder = base / iid / 'result'; folder.mkdir()
        block = {'path': 'a.py', 'start_line': 1, 'end_line': 2, 'complete_file': True,
                 'header': '--- SOURCE 1: a.py ---\n', 'text': text, 'sha256': R.H.digest(text)}
        write(folder/'context.json', {'blocks': [block], 'loaded_whole_files': ['a.py'], 'skipped_files': []})
        write(folder/'inventory.json', {'paths': ['a.py']})
        write(folder/'file_selection.json', {'ranked_edit_files': ['a.py']})
        qraw = [{'path': 'a.py', 'qualified_name': 'f', 'evidence_start_line': 1, 'evidence_end_line': 2}]
        raw = {**{k:job[k] for k in ('instance_id', 'repo', 'base_commit')}, 'status': 'complete', 'method': 'D-SIMPLE',
               'run_id': 'synthetic', 'predicted_files': ['a.py'], 'predicted_functions': qraw,
               'raw_output': json.dumps({'ranked_functions': qraw}), 'elapsed_seconds': 1.}
        if result: write(folder/'result.json', raw)
        if gold:
            write(base/'evaluator_private/eval_v2/filtered265'/iid/'gold_v2.json',
                  {**{k:job[k] for k in ('instance_id', 'repo', 'base_commit')}, 'status': 'COMPLETE_NONEMPTY',
                   'existing_function_targets': ['a.py::f'], 'gold_files': ['a.py'], 'code_index_v2_path': str(indexpath),
                   'changed_line_evidence': [], 'scope_exempt_changes': [], 'errors': []})
        if receipt:
            call = folder/'calls/0001_function_localization'
            request = {'messages': [{'role': 'user', 'content': '\n<context>\n'+block['header']+text+'\n</context>'}]}
            fingerprint = R.H.digest(json.dumps(request, sort_keys=True, ensure_ascii=False))
            write(call/'request.json', {'sha256': fingerprint, 'request': request})
            usage = {'prompt_tokens': 10, 'completion_tokens': 1, 'total_tokens': 11, 'prompt_cache_hit_tokens': 0}
            r = {'request_id': iid+'-req', 'instance_id': iid, 'method': 'D-SIMPLE', 'run_id': 'synthetic',
                 'stage': 'function_localization', 'sequence': 1, 'attempt': 0, 'request_sha256': fingerprint,
                 'usage': usage, 'http_status': 200, 'finish_reason': 'stop', 'thinking_mode': 'disabled',
                 'api_cost_usd_actual': .01, 'api_cost_usd_normalized': .02}
            write(call/'attempt_0_receipt.json', r)
        return {'instance_id': iid, 'repo': job['repo'], 'base_commit': job['base_commit'],
                'job': str(jobpath), 'result_dir': str(folder), 'origin': R.NEW_ORIGIN}

    def test_real_collect_proves_actual_context_and_does_not_use_hash_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); record = self.fixture(base)
            with patch.object(R.C, 'ROOT', base), patch.object(R.C, 'PREVIOUS', base/'old'):
                rows, targets, _ = R.collect({'n': 1, 'records': [record]}, budget={})
                self.assertEqual(rows[0]['function_hit_5'], 1)
                self.assertTrue(targets[0]['final_delivered_any_definition_full'])
                request = Path(record['result_dir'])/'calls/0001_function_localization/request.json'
                saved = json.loads(request.read_text());saved['request']['messages'][0]['content'] = 'different'
                saved['sha256'] = R.H.digest(json.dumps(saved['request'], sort_keys=True, ensure_ascii=False)); write(request, saved)
                rows, targets, _ = R.collect({'n': 1, 'records': [record]}, budget={})
                self.assertFalse(rows[0]['final_http_context_delivered'])
                self.assertFalse(targets[0]['final_delivered_any_definition_full'])

    def test_missing_gold_and_missing_terminal_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); a = self.fixture(base, 'missing-gold', gold=False)
            b = self.fixture(base, 'orphan', result=False)
            c = self.fixture(base, 'notrun', result=False, receipt=False)
            with patch.object(R.C, 'ROOT', base), patch.object(R.C, 'PREVIOUS', base/'old'):
                rows, _, _ = R.collect({'n': 3, 'records': [a,b,c]}, budget={})
            self.assertEqual(rows[0]['function_evaluation_status'], 'evaluation_unavailable')
            self.assertFalse(rows[0]['function_scorable'])
            self.assertEqual(rows[1]['status'], 'attempted_without_terminal_result')
            self.assertEqual(rows[1]['function_hit_5'], 0)
            self.assertEqual(rows[2]['status'], 'NOT_RUN')
            self.assertIsNone(rows[2]['function_hit_5'])

    def test_end_to_end_checkpoint_keeps_full_allocation_and_writes_only_new_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory);a=self.fixture(base, 'complete');b=self.fixture(base,'pending', result=False, receipt=False)
            manifest=base/'manifests/filtered265.json';write(manifest,{'n':2,'records':[a,b]})
            prior={'stage_cap_usd':5.,'attempts':{'prior':{'key':'D-SIMPLE|old','status':'usage_received','charged_upper_usd':3.24130776}},'cases':{}}
            budget=copy.deepcopy(prior);budget['attempts']['complete-req']={'key':'D-SIMPLE|complete','status':'usage_received','charged_upper_usd':.02,'usage':{'prompt_tokens':10,'completion_tokens':1,'total_tokens':11,'prompt_cache_hit_tokens':0}}
            finance=base/'finance/budget.json';write(finance,budget);run=base/'runs/synthetic';write(run/'financial_baseline.json',prior)
            before=Path(a['result_dir'])/'result.json';initial=before.read_bytes()
            with patch.object(R.C,'ROOT',base),patch.object(R.C,'PREVIOUS',base/'old'),patch.object(R.C,'RUN',run),patch.object(R.C,'SHARED_BUDGET',finance):
                with self.assertRaises(RuntimeError):R.run_report(manifest,expected_counts=None,ci_repeats=20)
                result=R.run_report(manifest,expected_counts=None,allow_incomplete=True,ci_repeats=20)
            self.assertEqual(result['allocation']['n'],2)
            self.assertEqual(len(result['summaries']),7)
            self.assertEqual(result['summaries'][0]['function_hit_5'],.5)
            self.assertEqual(result['summaries'][1]['function_hit_5'],1)
            self.assertEqual(before.read_bytes(),initial)
            self.assertEqual(json.loads(finance.read_text()),budget)
            for name in ['per_issue.csv','method_summary.csv','gold_source_evidence.csv','cost_ledger.csv','evaluation_summary.json','总览.md','未命中分析.md']:
                self.assertTrue((base/'reports/filtered265'/name).is_file())


class EvidenceBoundaryTests(unittest.TestCase):
    def test_same_leaf_mismatch_records_original_rank_without_repair(self):
        raw = [{'path':'a.py','qualified_name':'Wrong.f'}, {'path':'b.py','qualified_name':'Right.f'},
               {'path':'a.py','qualified_name':'Right.g'}]
        slots = [None, 'b.py::Right.f', 'a.py::Right.g']; original = copy.deepcopy(slots)
        targets = [{'gold_identity':'a.py::Right.f'}]
        out = R.enrich_target_evidence(targets, {}, {'blocks':[]}, {'blocks':[]},
                                       {'final_http_context_delivered':False}, raw, slots)
        self.assertEqual([e['rank'] for e in out[0]['same_leaf_different_identity_top10']], [1,2])
        self.assertEqual(slots, original)
        self.assertIsNone(out[0]['same_leaf_different_identity_top10'][0]['normalized_slot'])

    def test_shared_qn_other_span_is_not_modified_body_delivery(self):
        target = {'gold_identity':'a.py::C.x', 'final_delivered_any_definition_full':True}
        changed = {'base_function_id':'a.py::C.x','matched_base_span':{'qualified_name':'C.x','start_line':10,'end_line':12}}
        ctx = {'blocks':[{'path':'a.py','start_line':1,'end_line':3}]}; integrity = {'blocks':[{'source_valid':True}]}
        out = R.enrich_target_evidence([target], {'changed_line_evidence':[changed]}, ctx, integrity,
                                       {'final_http_context_delivered':True}, [], [])
        self.assertTrue(out[0]['modified_base_span_evidence_complete'])
        self.assertFalse(out[0]['actual_modified_implementation_verified'])
        ctx['blocks'][0].update(start_line=1,end_line=12)
        out = R.enrich_target_evidence([target], {'changed_line_evidence':[changed]}, ctx, integrity,
                                       {'final_http_context_delivered':True}, [], [])
        self.assertTrue(out[0]['actual_modified_implementation_verified'])
        out = R.enrich_target_evidence([target], {'changed_line_evidence':[changed]}, ctx, integrity,
                                       {'final_http_context_delivered':False}, [], [])
        self.assertFalse(out[0]['actual_modified_implementation_verified'])

    def test_strict_miss_recall_gap_and_engineering_populations_separate(self):
        self.assertEqual(R.diagnostic_population(aggregate_row('miss',hit=0)), 'completed_strict_hit5_miss')
        gap=aggregate_row('gap');gap['function_recall_5']=.5
        self.assertEqual(R.diagnostic_population(gap), 'hit5_with_recall_gap')
        self.assertEqual(R.diagnostic_population(aggregate_row('budget',status='budget_exceeded',hit=0)), 'engineering_budget_or_output_failure')
        self.assertEqual(R.diagnostic_population(aggregate_row('notrun',status='NOT_RUN',executed=False,http=False)), 'not_run')


if __name__ == '__main__':
    unittest.main()
