"""Statistical and denominator checks; fixtures are not experimental results."""
import copy
import math
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a
import report_results as report


def val_row(case, issue, label, logit, group=None):
    return {'case_id': case, 'instance_id': issue, 'function_id': case + '.py::f',
            'label': label, 'logit_difference': logit, 'split': 'val',
            'distribution_group': group or ('gold_AB' if label else 'E_negative'),
            'label_sources': ['A'] if label else ['e_log']}


class MetricTests(unittest.TestCase):
    def test_auc_ties_and_undefined_one_label(self):
        self.assertEqual(a.auc([True, False], [1., 1.]), .5)
        self.assertEqual(a.auc([True, False, False], [2., 0., 1.]), 1.)
        self.assertEqual(a.auc([True, False], [-1., 1.]), 0.)
        self.assertIsNone(a.auc([True, True], [0., 1.]))

    def test_stable_nll_and_calibration_bin_endpoints(self):
        rows = [val_row('a', 'i', True, 1000.), val_row('b', 'i', False, 1000.)]
        result = a.calibration_metrics(rows, 1.)
        self.assertEqual(result['nll'], 500.)
        self.assertEqual(result['brier'], .5)
        self.assertEqual(result['ece10'], .5)
        self.assertEqual(result['bins'][9]['n'], 2)
        self.assertTrue(all(math.isfinite(result[k]) for k in ('nll', 'brier', 'ece10')))

    def test_probability_half_is_positive_and_route_boundaries_are_closed(self):
        rows = [val_row('a', 'i', True, 0.), val_row('b', 'i', False, -.1)]
        self.assertEqual(a.discrimination(rows)['accuracy'], 1.)
        self.assertEqual(a.route(.2, .2, .9), 'reject')
        self.assertEqual(a.route(.9, .2, .9), 'retain')
        self.assertEqual(a.route(math.nextafter(.2, math.inf), .2, .9), 'qwen')

    def test_static_graph_line_suffix_maps_to_r2_exact_identity(self):
        self.assertEqual(a.target_identity('a.py::C.f@123'), 'a.py::C.f')
        self.assertEqual(a.target_identity('a.py::C.f'), 'a.py::C.f')
        self.assertEqual(a.target_identity('a.py::C.f@invalid'), 'a.py::C.f@invalid')

    def test_strict_low_preserves_minimum_gold_and_empty_rejection_is_na(self):
        rows = [val_row('a', 'i', True, 0.), val_row('b', 'j', False, -2.)]
        cfg = a.derive_calibration(rows)
        self.assertEqual(cfg['low'], math.nextafter(.5, -math.inf))
        report = a.validation_routing(rows, cfg)
        self.assertEqual(report['gold_AB']['counts']['reject'], 0)
        only_gold = a.validation_routing(rows[:1], cfg)
        self.assertIsNone(only_gold['rejection_precision'])


class BootstrapTests(unittest.TestCase):
    def test_pairs_are_joined_by_case_not_order_and_clusters_repeat_whole(self):
        full = [val_row('a', 'first', True, 1.), val_row('b', 'first', False, -1.),
                val_row('c', 'second', True, 2.), val_row('d', 'second', False, -2.)]
        reverse = [{**r, 'logit_difference': -r['logit_difference']} for r in reversed(full)]
        result = a.paired_cluster_bootstrap({'full': full, 'no_lora': reverse,
                                           'no_neighbors': list(reversed(full))}, draws=40)
        self.assertEqual(result['clusters'], 2)
        for metric in ('accuracy', 'auc'):
            self.assertEqual(result['comparisons']['no_lora'][metric]['delta'], -1.)
            self.assertEqual(result['comparisons']['no_lora'][metric]['ci95'], [-1., -1.])
            self.assertEqual(result['comparisons']['no_neighbors'][metric]['ci95'], [0., 0.])

    def test_one_class_bootstrap_samples_are_counted_not_fabricated(self):
        rows = [val_row('a', 'pos', True, 1.), val_row('b', 'neg', False, -1.)]
        mapping = {v: copy.deepcopy(rows) for v in a.VARIANTS}
        result = a.paired_cluster_bootstrap(mapping, draws=100)
        counts = result['comparisons']['no_lora']
        self.assertGreater(counts['auc']['undefined_draws'], 0)
        self.assertEqual(counts['auc']['valid_draws'] + counts['auc']['undefined_draws'], 100)
        self.assertEqual(counts['accuracy']['valid_draws'], 100)
        mapping['no_lora'].pop()
        with self.assertRaisesRegex(ValueError, 'paired case'):
            a.paired_cluster_bootstrap(mapping, draws=10)


class RuntimeTests(unittest.TestCase):
    def fixture(self):
        rows = [
            {'case_id': 'a', 'instance_id': 'i1', 'function_id': 'a.py::f', 'logit_difference': -2.},
            {'case_id': 'b', 'instance_id': 'i1', 'function_id': 'a.py::f', 'logit_difference': 3.},
            {'case_id': 'c', 'instance_id': 'i1', 'function_id': 'a.py::other', 'logit_difference': -3.},
            {'case_id': 'd', 'instance_id': 'i2', 'function_id': 'b.py::f', 'logit_difference': -3.}]
        events = [{k: row[k] for k in ('case_id', 'instance_id', 'function_id')} for row in rows]
        events.append(dict(events[0]))
        gold = {
            'i1': {'status': 'COMPLETE_NONEMPTY', 'set_complete': True, 'targets': ['a.py::f']},
            'i2': {'status': 'INCOMPLETE', 'set_complete': False, 'targets': ['b.py::f']},
            'i3': {'status': 'COMPLETE_NONEMPTY', 'set_complete': True, 'targets': ['c.py::f']}}
        inv = {iid: {'function_identities': g['targets']} for iid, g in gold.items()}
        return rows, events, {'temperature': 1., 'low': .2, 'high': .9}, gold, inv

    def test_events_unique_functions_and_eligible_gold_are_distinct(self):
        result = a.runtime_routing(*self.fixture())
        self.assertEqual(result['events']['target']['n'], 3)
        self.assertEqual(result['events']['target']['counts']['reject'], 2)
        self.assertEqual(result['unique_inputs']['target']['n'], 2)
        function = result['unique_functions']['target']
        self.assertEqual(function['n'], 1)
        self.assertEqual(function['counts'], {'reject': 1, 'qwen': 0, 'retain': 1})
        self.assertEqual(function['multiple_route_units'], 1)
        self.assertEqual(result['cohort']['function_eligible_issues'], 2)
        self.assertEqual(result['cohort']['eligible_issues_without_target_visit'], 1)
        self.assertEqual(result['cohort']['visited_ineligible_issues'], 1)
        self.assertTrue(result['nongold_is_not_negative'])

    def test_unscored_event_or_gold_identity_drift_is_rejected(self):
        rows, events, cfg, gold, inv = self.fixture()
        bad = [{**events[0], 'case_id': 'missing'}]
        with self.assertRaisesRegex(ValueError, 'scored case'):
            a.runtime_routing(rows, bad, cfg, gold, inv)
        inv['i1']['function_identities'] = []
        with self.assertRaisesRegex(ValueError, 'absent from inventory'):
            a.runtime_routing(rows, events, cfg, gold, inv)


class ReportTests(unittest.TestCase):
    def test_export_whitelist_and_history_has_no_new_latency(self):
        cfg = {'temperature': 1., 'low': .2, 'high': .9}
        summary = {'variants': {v: {'calibration': cfg,
                    'same_frozen_threshold_diagnostic': {'calibration': cfg}} for v in a.VARIANTS}}
        row = {'case_id': 'case', 'instance_id': 'i', 'function_id': 'a.py::f@1',
               'source_input_sha256': 's', 'input_sha256': 's', 'source': 'history',
               'logit_difference': -2., 'p_yes': a.sigmoid(-2), 'input_tokens': 12,
               'latency_seconds': 99., 'issue': 'must never export', 'function': 'private code'}
        joined = {v: {'val': [], 'runtime': [row]} for v in a.VARIANTS}
        gold = {'i': {'status': 'INCOMPLETE', 'set_complete': False, 'targets': ['a.py::f']}}
        result = report.sample_rows(joined, summary, gold)
        self.assertEqual(len(result), 3)
        self.assertFalse(result[0]['runtime_known_r2_target'])
        self.assertEqual(result[0]['runtime_label_interpretation'], 'NA_incomplete_or_empty_R2')
        self.assertEqual(result[0]['new_forward_latency_seconds'], '')
        self.assertNotIn('issue', result[0])
        self.assertNotIn('function', result[0])
        self.assertEqual(result[0]['r2_function_identity'], 'a.py::f')

    def test_resource_accounting_separates_probes_and_completed_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); session = root / 'sessions' / 'one'; session.mkdir(parents=True)
            def save(path, value): path.write_text(json.dumps(value))
            save(root / 'run_contract.json', {'inputs_manifest_sha256': 'manifest'})
            save(session / 'started.json', {})
            save(session / 'complete.json', {'status': 'complete', 'new_completed': 1, 'elapsed_seconds': 4.})
            save(session / 'loaded.json', {'seconds': 1.})
            (session / 'probes.jsonl').write_text(json.dumps({'status': 'complete', 'passed': True,
                'input_tokens': 20, 'latency_seconds': .5, 'logit_difference': 2., 'expected_logit_difference': 2.}) + '\n')
            score = {'status': 'complete', 'source': 'new', 'request_id': 'id', 'variant': 'no_lora',
                     'input_tokens': 10, 'generated_output_tokens': 0, 'latency_seconds': .2, 'split': 'val'}
            path = root / 'scores.jsonl'; path.write_text(json.dumps(score) + '\n')
            summary = {'provenance': {'manifest': {'sha256': 'manifest'}}, 'variants': {
                v: {'calibration': {'cpu_wall_seconds': .01}} for v in a.VARIANTS}, 'analysis_cpu_wall_seconds': 1.}
            result = report.resource_report([path], summary)
            self.assertEqual(result['totals']['new_component_input_tokens'], 10)
            self.assertEqual(result['totals']['probe_input_tokens'], 20)
            self.assertEqual(result['totals']['new_component_requests'], 1)
            self.assertEqual(result['totals']['probe_completed_forwards'], 1)
            self.assertAlmostEqual(result['totals']['validation_calibration_cpu_seconds'], .03)


if __name__ == '__main__':
    unittest.main()
