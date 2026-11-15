"""CPU-only scoring contract tests. All tasks and predictions are synthetic."""
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from reproduction import evaluate as e


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        self.frozen, _ = e.frozen_evaluator()
        self.tasks = [dict(instance_id=f'repo-{i}', repo=f'owner/repo{i}', base_commit=str(i) * 40)
                      for i in (1, 2)]
        self.gold = {r['instance_id']: dict(status='COMPLETE_NONEMPTY', set_complete=True,
                        targets=['src/a.py::A.f'], gold_files=['src/a.py']) for r in self.tasks}
        self.inventory = {r['instance_id']: dict(paths=['src/a.py', 'src/other.py'],
                        function_identities=['src/a.py::A.f', 'src/a.py::A.g']) for r in self.tasks}
        self.write('selection/manifest.json', {'n': 2, 'records': self.tasks})
        self.write('private/gold.json', self.gold)
        self.write('private/inventory.json', self.inventory)
        self.historical = []
        for task in self.tasks:
            r = dict(task)
            for arm in ('baseline', 'hybrid_safe'):
                r[arm + '_status'] = 'complete'
                r[arm + '_file_slots'] = json.dumps(['src/a.py'])
                r[arm + '_function_slots'] = json.dumps(['src/a.py::A.f'])
                for unit, raw, inv, targets in (
                    ('file', ['src/a.py'], self.inventory[task['instance_id']]['paths'], ['src/a.py']),
                    ('function', [dict(path='src/a.py', qualified_name='A.f')],
                        self.inventory[task['instance_id']]['function_identities'], ['src/a.py::A.f'])):
                    m = self.frozen.metrics(raw, targets, inv, functions=unit == 'function')
                    for k, v in m.items():
                        if k != 'slots':
                            r[arm + '_' + unit + '_' + k] = v
                r.update({arm + '_main_tokens': 30, arm + '_known_prompt_tokens': 20,
                          arm + '_known_completion_tokens': 10, arm + '_unknown_usage_attempts': 0,
                          arm + '_http_attempts_recorded': 2, arm + '_worker_elapsed_seconds': 4,
                          arm + '_file_stage_wall_seconds': 1, arm + '_local_input_tokens': 0})
            self.historical.append(r)
        self.write_history()

    def write(self, relative, obj):
        p = self.run / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding='utf-8')

    def write_history(self):
        p = self.run / 'private/comparison_original.csv'
        with p.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(self.historical[0]))
            w.writeheader(); w.writerows(self.historical)

    def worker(self, i, **changes):
        r = dict(self.tasks[i], terminal=True, status='complete', execution_status='complete',
                 found_files=['src/a.py'], found_entities=['src/a.py:A.f'],
                 samples=[{'status': 'complete'}, {'status': 'complete'}],
                 usage=dict(prompt_tokens=20, completion_tokens=10, total_tokens=30,
                            known_prompt_tokens=20, known_completion_tokens=10,
                            known_total_tokens=30, unknown_usage_requests=0, http_attempts=2,
                            completion_requests=2, api_cost_usd=0), elapsed_seconds=3)
        r.update(changes)
        self.write('outputs/' + r['instance_id'] + '/result.json', r)
        return r

    def evaluate(self):
        return e.build_evaluation(self.run, draws=40)

    def test_invalid_and_duplicate_final_slots_are_not_compressed(self):
        self.worker(0, found_entities=['src/a.py:A', 'src/a.py:A.f', 'src/a.py:A.f'])
        row = self.evaluate()['records'][0]['locagent_function']
        self.assertEqual(row['slots'], [None, 'src/a.py::A.f', 'src/a.py::A.f'])
        self.assertEqual((row['hit1'], row['hit3'], row['precision5'], row['mrr10']), (0, 1, .2, .5))

    def test_no_gold_leaf_disambiguation_or_class_expansion(self):
        self.worker(0, found_entities=['A.f', 'src/a.py:A', 'src/a.py:f'])
        row = self.evaluate()['records'][0]['locagent_function']
        self.assertEqual(row['slots'], [None, None, None])
        self.assertEqual(row['hit5'], 0)

    def test_exact_double_colon_syntax_is_supported(self):
        self.worker(0, found_entities=['src/a.py::A.f'])
        self.assertEqual(self.evaluate()['records'][0]['locagent_function']['hit1'], 1)

    def test_pending_is_not_model_failure_or_final_comparison(self):
        s = self.evaluate()['summary']
        self.assertEqual(s['status'], 'PARTIAL')
        self.assertEqual((s['terminal_tasks'], s['pending_tasks']), (0, 2))
        self.assertEqual(s['locagent_terminal_statuses'], {})
        self.assertEqual(s['paired_comparisons']['baseline__locagent']['status'], 'PENDING_FULL_ROSTER')

    def test_terminal_partial_is_real_scored_output_not_pending(self):
        self.worker(0, status='partial', execution_status='api_error')
        self.worker(1)
        s = self.evaluate()['summary']
        self.assertEqual(s['status'], 'FINAL')
        self.assertEqual(s['locagent_terminal_statuses'], {'partial': 1, 'complete': 1})
        self.assertEqual(s['metrics']['locagent']['function']['hit1_numerator'], 2)

    def test_terminal_failed_task_stays_in_denominator(self):
        self.worker(0)
        self.worker(1, status='failed', execution_status='timeout', found_files=[], found_entities=[])
        result = self.evaluate()
        s = result['summary']
        self.assertEqual(s['status'], 'FINAL')
        self.assertEqual(s['metrics']['locagent']['function']['n'], 2)
        self.assertEqual(s['metrics']['locagent']['function']['hit5'], .5)
        p = s['paired_comparisons']['baseline__locagent']['function']['5']
        self.assertEqual((p['both_success'], p['only_a'], p['only_b'], p['both_failure']), (1, 1, 0, 0))

    def test_unknown_usage_is_not_filled_with_zero(self):
        self.worker(0, usage={'prompt_tokens': None, 'completion_tokens': None, 'total_tokens': None,
                              'known_prompt_tokens': 20, 'known_completion_tokens': 10,
                              'known_total_tokens': 30, 'unknown_usage_requests': 1})
        s = self.evaluate()['summary']['resources']['locagent']
        self.assertIsNone(s['total_tokens']['sum'])
        self.assertEqual(s['known_total_tokens']['sum'], 30)
        self.assertEqual(s['unknown_usage_requests']['sum'], 1)

    def test_unknown_usage_cannot_claim_exact_total(self):
        self.worker(0, usage={'total_tokens': 30, 'unknown_usage_requests': 1})
        with self.assertRaisesRegex(ValueError, 'Unknown HTTP usage'):
            self.evaluate()

    def test_receipt_repo_or_base_mismatch_stops_evaluation(self):
        self.worker(0, base_commit='f' * 40)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.evaluate()

    def test_gold_roster_cannot_silently_drop_or_add_tasks(self):
        g = dict(self.gold); g['leak-extra-task'] = g['repo-1']
        self.write('private/gold.json', g)
        with self.assertRaisesRegex(ValueError, 'rosters must match'):
            self.evaluate()

    def test_incomplete_gold_cannot_enter_the_cohort(self):
        self.gold['repo-1']['set_complete'] = False
        self.write('private/gold.json', self.gold)
        with self.assertRaisesRegex(ValueError, 'complete nonempty'):
            self.evaluate()

    def test_changed_historical_metric_is_detected(self):
        self.historical[0]['baseline_function_hit5'] = 0
        self.write_history()
        with self.assertRaisesRegex(ValueError, 'Historical scoring changed'):
            self.evaluate()

    def test_comparison_uses_issue_id_not_csv_order(self):
        self.historical.reverse(); self.write_history()
        result = self.evaluate()
        self.assertEqual([r['instance_id'] for r in result['records']], ['repo-1', 'repo-2'])

    def test_frozen_evaluator_byte_pin_is_enforced(self):
        p = self.run / 'different_evaluator.py'; p.write_text('')
        with self.assertRaisesRegex(ValueError, 'SHA differs'):
            e.frozen_evaluator(p)

    def test_new_report_dir_and_blank_pending_csv(self):
        out = self.run / 'reports/check'
        original = hashlib.sha256((self.run / 'private/gold.json').read_bytes()).hexdigest()
        result = e.evaluate_run(self.run, out, draws=40)
        self.assertEqual(result['summary']['status'], 'PARTIAL')
        self.assertTrue((out / 'final_report.md').is_file())
        with (out / 'per_issue.csv').open(encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]['locagent_function_hit5'], '')
        self.assertEqual(rows[0]['baseline_function_hit5'], '1')
        self.assertEqual(original, hashlib.sha256((self.run / 'private/gold.json').read_bytes()).hexdigest())
        with self.assertRaises(FileExistsError):
            e.evaluate_run(self.run, out, draws=40)

    def test_complete_receipt_without_terminal_flag_is_not_finalized(self):
        self.worker(0, terminal=False)
        self.assertEqual(self.evaluate()['summary']['terminal_tasks'], 0)

    def test_graph_representation_audit_is_metadata_not_a_prediction_repair(self):
        before = self.evaluate()['summary']['metrics']
        self.write('private/graph_coverage.json', {'records': [
            {'instance_id': 'repo-1', 'graph_ready': True, 'all_target_function_nodes_present': False,
             'missing_function_nodes': [{'identity': 'src/a.py::A.__init__',
                                        'reason': 'upstream_omits_independent_constructor_node'}]},
            {'instance_id': 'repo-2', 'graph_ready': True, 'all_target_function_nodes_present': False,
             'missing_function_nodes': [{'identity': 'src/b.py::f',
                                        'reason': 'target_not_a_function_node_in_upstream_graph'}]}]})
        self.write('public/graph_index/repo-2.receipt.json', {'syntax_skips': [
            {'path': 'src/b.py', 'message': 'invalid non-printable character U+FEFF'}]})
        result = self.evaluate()
        self.assertEqual(result['summary']['metrics'], before)
        g = result['summary']['context_audits']['graph_coverage']
        self.assertEqual((g['successful_graphs'], g['tasks_missing_target_function_nodes']), (2, 2))
        self.assertEqual(g['missing_constructor_function_nodes'], 1)
        self.assertEqual(g['bom_affected_issue_ids'], ['repo-2'])
        self.assertEqual(g['other_missing_function_nodes'], 0)

    def test_graph_audit_roster_must_match(self):
        self.write('private/graph_coverage.json', {'records': []})
        with self.assertRaisesRegex(ValueError, 'coverage roster differs'):
            self.evaluate()

    def test_previous_engineering_usage_is_separate_and_does_not_change_scores(self):
        before = self.evaluate()['summary']['metrics']
        previous = tempfile.TemporaryDirectory(prefix='locagent-previous-', dir=self.run.parent)
        self.addCleanup(previous.cleanup)
        p = Path(previous.name) / 'outputs/repo-1/result.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'instance_id': 'repo-1', 'terminal': True, 'status': 'failed',
            'samples': [{'status': 'empty_output'}, {'status': 'empty_output'}],
            'usage': {'known_prompt_tokens': 7, 'known_completion_tokens': 3, 'known_total_tokens': 10,
                      'unknown_usage_requests': 0, 'http_attempts': 2, 'completion_requests': 2, 'api_cost_usd': 0},
            'elapsed_seconds': 4}))
        self.write('protocol.json', {'protocol_version': 'native_finish_payload_v2',
                                   'previous_engineering_run': previous.name})
        result = self.evaluate()
        self.assertEqual(result['summary']['metrics'], before)
        previous_usage = result['summary']['context_audits']['previous_engineering_overhead']
        self.assertEqual((previous_usage['tasks'], previous_usage['samples'], previous_usage['known_total_tokens']), (1, 2, 10))
        self.assertFalse(previous_usage['counted_in_formal_locagent_metrics'])
        self.assertIsNone(result['summary']['resources']['locagent']['known_total_tokens']['sum'])

    def test_runner_wall_time_is_separate_from_worker_and_missing_is_unknown(self):
        self.worker(0)
        result = self.evaluate()
        self.assertIsNone(result['summary']['resources']['locagent']['runner_wall_seconds']['sum'])
        self.write('outputs/repo-1/runner_receipt.json', {'wall_seconds': 12.5, 'returncode': 0, 'timed_out': False})
        result = self.evaluate()
        resource = result['summary']['resources']['locagent']
        self.assertEqual(resource['runner_wall_seconds']['mean'], 12.5)
        self.assertEqual(resource['runner_wall_seconds']['median'], 12.5)
        self.assertEqual(resource['runner_wall_seconds']['p90'], 12.5)
        self.assertEqual(resource['elapsed_seconds']['mean'], 3)

    def test_parallel_wall_uses_launch_and_terminal_timestamps_not_task_sum(self):
        self.write('controller/canary_launcher.json', {'started': 100})
        self.write('controller/full_launcher.json', {'started': 200})
        rows = []
        for iid, timestamp in [('a', 110), ('b', 120), ('c', 130), ('d', 250)]:
            relative = f'outputs/{iid}/result.json'
            self.write(relative, {})
            os.utime(self.run / relative, (timestamp, timestamp))
            rows.append({'terminal': True, 'receipt': relative})
        wall = e.run_wall_clock(self.run, rows)
        self.assertEqual(wall['canary_first3_wall_seconds'], 30)
        self.assertEqual(wall['full_launcher_to_final_terminal_seconds'], 50)
        self.assertEqual(wall['v2_first_canary_launch_to_final_terminal_seconds'], 150)
        rows[-1]['terminal'] = False
        pending = e.run_wall_clock(self.run, rows)
        self.assertIsNone(pending['full_launcher_to_final_terminal_seconds'])
        self.assertIsNone(pending['v2_first_canary_launch_to_final_terminal_seconds'])


if __name__ == '__main__':
    unittest.main()
