"""Synthetic-only independent-audit tests; no live run or Gold is opened."""
from collections import Counter
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import metrics_audit as a


def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')


def provenance(root, rows):
    paths = [root / 'allocation.json']
    for row in rows:
        iid = row['instance_id']
        paths.extend(root / 'run' / iid / arm / filename for arm in a.ARMS
                     for filename in ('terminal.json', 'result.json'))
        paths.extend([root / 'public' / iid / 'code_index.json', root / 'evaluator_private' / iid / 'gold.json'])
    return {str(path): a.digest(path) for path in paths}


INDEX = {'src/A.java': {'definitions': [
    {'kind': 'function', 'qualified_name': 'A.run(int)', 'canonical_id': 'src/A.java::A.run(int)'},
    {'kind': 'function', 'qualified_name': 'A.other()', 'canonical_id': 'src/A.java::A.other()'}]}}


class MetricsAuditTests(unittest.TestCase):
    def test_invalid_and_duplicate_slots_do_not_promote_later_hit(self):
        slots, _ = a.canonical_slots([
            {'path': 'src/A.java', 'qualified_name': 'A.run'},
            {'path': 'src/A.java', 'qualified_name': 'A.other()'},
            {'path': 'src/A.java', 'qualified_name': 'A.other()'},
            {'path': 'src/A.java', 'qualified_name': 'A.run(int)'}], INDEX, 'function')
        value = a.measure(slots, {'src/A.java::A.run(int)'})
        self.assertFalse(value['hit1'])
        self.assertFalse(value['hit3'])
        self.assertTrue(value['hit5'])
        self.assertEqual(value['prediction_slots5'], 4)
        self.assertEqual(value['precision5'], .25)
        self.assertEqual(value['recall5'], 1.)
        self.assertAlmostEqual(value['f1_5'], .4)
        self.assertEqual(value['mrr10'], .25)
        self.assertEqual(slots[2]['reason'], 'duplicate_rank_slot')

    def test_no_signature_or_path_repair_and_canonical_disagreement(self):
        slots, _ = a.canonical_slots(['src/A.java::A.run( int )', 'A.java::A.run(int)',
            {'path': 'src/A.java', 'qualified_name': 'A.run(int)', 'canonical_id': 'src/A.java::A.other()'}], INDEX, 'function')
        self.assertFalse(any(x['valid'] for x in slots))
        self.assertEqual(slots[2]['reason'], 'canonical_id_disagrees_with_fields')

    def test_missing_predictions_zero_and_multiple_targets_recall(self):
        empty = a.measure([], {'src/A.java::A.run(int)'})
        self.assertEqual(empty['precision5'], 0.)
        self.assertEqual(empty['recall5'], 0.)
        slots, _ = a.canonical_slots(['src/A.java::A.run(int)'], INDEX, 'function')
        result = a.measure(slots, {'src/A.java::A.run(int)', 'src/A.java::A.other()'})
        self.assertEqual(result['precision5'], 1.)
        self.assertEqual(result['recall5'], .5)
        self.assertFalse(result['allcoverage5'])
        self.assertAlmostEqual(result['f1_5'], 2 / 3)

    def test_wilson_and_bootstrap_known_cases(self):
        self.assertAlmostEqual(a.wilson(0, 100)[1], .03699349820698568)
        self.assertAlmostEqual(a.wilson(100, 100)[0], .9630065017930143)
        self.assertEqual(a.bootstrap([.25] * 117), [.25, .25])
        self.assertEqual(a.bootstrap([0., 1.]), [0., 1.])
        self.assertEqual(a.bootstrap([0., 1., .5]), a.bootstrap([0., 1., .5]))

    def test_gold_reader_is_closed_before_fence(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'gold.json'
            put(path, {'synthetic': True})
            reader = a.Reader()
            with self.assertRaisesRegex(RuntimeError, 'forbidden'):
                reader.json(path, 'gold')
            self.assertFalse(reader.gold_opened)
            self.assertEqual(reader.artifacts, {})

    def skeleton(self, root):
        rows = [{'instance_id': 'synthetic__repo-' + str(i), 'repo': 'synthetic/repo', 'base_commit': 'a' * 40}
                for i in range(128)]
        put(root / 'allocation.json', {'n': 128, 'records': rows})
        source = root / 'source.py'
        source.write_text('# synthetic execution only\n')
        freeze = {'commit': 'b' * 40, 'files_sha256': {str(source): a.digest(source)}}
        put(root / 'execution_freeze.json', freeze)
        put(root / 'audits/analysis_execution_freeze.json', freeze)
        return rows

    def test_incomplete_run_returns_pending_without_any_gold_or_index_read(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.skeleton(root)
            # Poison future content: the audit must not even parse these files.
            p = root / 'evaluator_private/synthetic__repo-0/gold.json'
            p.parent.mkdir(parents=True)
            p.write_text('NOT JSON AND MUST NOT BE OPENED')
            result = a.audit(root, root / 'reports/final128')
            self.assertEqual(result['status'], 'PENDING')
            self.assertFalse(result['gold_opened'])
            self.assertFalse(any(x['category'] in ('gold', 'public_index') for x in result['read_artifacts'].values()))

    def test_source_drift_fails_without_gold(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.skeleton(root)
            (root / 'source.py').write_text('# changed\n')
            result = a.audit(root, root / 'reports/final128')
            self.assertEqual(result['status'], 'FAIL')
            self.assertFalse(result['gold_opened'])
            self.assertTrue(any(e['kind'] == 'bound_sha_mismatch' for e in result['errors']))

    def test_misconfigured_source_freeze_cannot_hash_private_gold_early(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.skeleton(root)
            private = root / 'evaluator_private/synthetic__repo-0/gold.json'
            private.parent.mkdir(parents=True)
            private.write_text('PRIVATE MUST NOT BE HASHED BEFORE FULL FENCE')
            frozen = json.loads((root / 'execution_freeze.json').read_text())
            frozen['files_sha256'][str(private)] = '0' * 64
            put(root / 'execution_freeze.json', frozen)
            original_digest = a.digest
            def guarded(path):
                if Path(path).resolve() == private.resolve():
                    raise AssertionError('Attempted forbidden early private hash')
                return original_digest(path)
            with patch.object(a, 'digest', guarded):
                result = a.audit(root, root / 'reports/final128')
            self.assertEqual(result['status'], 'FAIL')
            self.assertFalse(result['gold_opened'])
            self.assertTrue(any(e['kind'] == 'private_data_binding_forbidden_before_fence' for e in result['errors']))

    def complete_fixture(self, root):
        """All expected numbers below are literal constants, not evaluator calls."""
        rows = self.skeleton(root)
        evaldir = root / 'reports/final128'
        reports, bindings = [], {}
        rawfiles = ['src/A.java', 'missing.java', 'src/A.java']
        rawmethods = ['src/A.java::A.run(int)', 'src/A.java::A.run',
                      'src/A.java::A.run(int)', 'src/A.java::A.other()']
        file_slots = [
            {'rank': 1, 'raw': rawfiles[0], 'canonical_id': rawfiles[0], 'valid': True, 'reason': None},
            {'rank': 2, 'raw': rawfiles[1], 'canonical_id': rawfiles[1], 'valid': False, 'reason': 'file_not_in_base_java_inventory'},
            {'rank': 3, 'raw': rawfiles[2], 'canonical_id': rawfiles[2], 'valid': False, 'reason': 'duplicate_rank_slot'}]
        method_slots = [
            {'rank': 1, 'raw': rawmethods[0], 'canonical_id': rawmethods[0], 'valid': True, 'reason': None},
            {'rank': 2, 'raw': rawmethods[1], 'canonical_id': rawmethods[1], 'valid': False, 'reason': 'ambiguous_or_nonexistent_method_identity'},
            {'rank': 3, 'raw': rawmethods[2], 'canonical_id': rawmethods[2], 'valid': False, 'reason': 'duplicate_rank_slot'},
            {'rank': 4, 'raw': rawmethods[3], 'canonical_id': rawmethods[3], 'valid': True, 'reason': None}]
        for i, row in enumerate(rows):
            iid = row['instance_id']
            indexpath = root / 'public' / iid / 'code_index.json'
            put(indexpath, INDEX)
            gold = {**row, 'file_evaluable': i < 125, 'function_evaluable': i < 117,
                'existing_target_set_complete': i < 117, 'base_index_sha256': a.digest(indexpath),
                'file_targets': ['src/A.java'] if i < 125 else [],
                'function_targets': ['src/A.java::A.run(int)'] if i < 117 else [],
                'function_status': 'complete' if i < 117 else 'NA', 'limitations': []}
            gp = root / 'evaluator_private' / iid / 'gold.json'
            put(gp, gold)
            bindings[str(gp)] = a.digest(gp)
            record = {**row, 'selected_for_evaluation': True, 'gold_status': gold['function_status'],
                'gold_error': None, 'file_evaluable': gold['file_evaluable'], 'function_evaluable': gold['function_evaluable'],
                'gold_files': gold['file_targets'], 'gold_functions': gold['function_targets'], 'gold_limitations': [], 'arms': {}}
            terminals = {}
            for arm in a.ARMS:
                d = root / 'run' / iid / arm
                result = {**row, 'status': 'complete', 'predicted_functions': rawmethods}
                filefield = 'ranked_files' if arm == 'locagent' else 'ranked_edit_files'
                result[filefield] = rawfiles
                put(d / 'result.json', result)
                terminal = {'instance_id': iid, 'arm': arm, 'status': 'complete', 'keep_in_denominator': True,
                            'result_sha256': a.digest(d / 'result.json')}
                put(d / 'terminal.json', terminal)
                terminals[arm] = terminal
                values = {}
                for unit, enabled, p, f1, nslots in [('file', i < 125, 1 / 3, .5, 3), ('function', i < 117, .25, .4, 4)]:
                    values[unit] = {'hit1': True, 'hit3': True, 'hit5': True, 'tp5': 1,
                        'prediction_slots5': nslots, 'target_count': 1, 'precision5': p, 'recall5': 1.,
                        'f1_5': f1, 'allcoverage5': True, 'mrr10': 1.} if enabled else None
                record['arms'][arm] = {'status': 'complete', 'result_status': 'complete',
                    'ranking': {'file': file_slots, 'function': method_slots, 'file_field': filefield,
                                'function_field': 'predicted_functions', 'field_errors': []}, 'metrics': values}
            put(root / 'run' / iid / 'group_terminal.json', {'instance_id': iid, 'status': 'group_terminal', 'arms': terminals})
            reports.append(record)
        put(root / 'run/completion.json', {'status': 'COMPLETE', 'allocated': 128, 'groups': 128})
        put(root / 'audits/evaluator_qualification_frozen.json', {'allocated': 128, 'file_evaluable': 125,
            'function_evaluable': 117, 'gold_files_sha256': bindings})
        summary = {'allocated': 128, 'selected': 128, 'status': 'EVALUATED', 'gold_opened': True,
            'incomplete_arms': [], 'file_denominator': 125, 'function_denominator': 117,
            'arm_status_counts': {arm: {'complete': 128} for arm in a.ARMS},
            'gold_status_counts': {'complete': 117, 'NA': 11}, 'metrics': {}}
        summary['provenance_sha256'] = provenance(root, rows)
        for arm in a.ARMS:
            summary['metrics'][arm] = {}
            for unit, n, p, f1 in [('file', 125, 1 / 3, .5), ('function', 117, .25, .4)]:
                # For all n successes, Wilson's lower bound is n/(n+z^2).
                table = {'denominator': n}
                for k in a.BINARY:
                    table[k] = {'numerator': n, 'denominator': n, 'value': 1.,
                                'ci95': [n / (n + 3.8414588206941254), 1.], 'ci_method': 'Wilson_score'}
                for k, value in [('precision5', p), ('recall5', 1.), ('f1_5', f1), ('mrr10', 1.)]:
                    table[k] = {'numerator_sum': n * value, 'denominator': n, 'value': value,
                        'ci95': [value, value], 'ci_method': 'task_percentile_bootstrap', 'draws': 2000, 'seed': 20261117}
                summary['metrics'][arm][unit] = table
        put(evaldir / 'summary.json', summary)
        put(evaldir / 'per_issue.json', reports)
        flattened = []
        for row in reports:
            flat = {k: row[k] for k in ('instance_id', 'repo', 'base_commit', 'selected_for_evaluation',
                'gold_status', 'gold_error', 'file_evaluable', 'function_evaluable')}
            for k in ('gold_files', 'gold_functions'):
                flat[k] = json.dumps(row[k])
            for arm in a.ARMS:
                flat[arm + '_status'] = flat[arm + '_result_status'] = 'complete'
                for unit in a.UNITS:
                    flat[f'{arm}_{unit}_original_slots'] = json.dumps(row['arms'][arm]['ranking'][unit])
                    for key in a.METRICS:
                        flat[f'{arm}_{unit}_{key}'] = row['arms'][arm]['metrics'][unit][key] if row['arms'][arm]['metrics'][unit] else None
            flattened.append(flat)
        with (evaldir / 'per_issue.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(flattened[0]))
            writer.writeheader()
            writer.writerows(flattened)
        put(root / 'analysis_supervisor/completion.json', {'status': 'ANALYSIS_READY_FOR_INDEPENDENT_REVIEW',
            'new_model_calls': 0, 'outputs_sha256': {str(evaldir / 'summary.json'): a.digest(evaldir / 'summary.json')}})
        return evaldir

    def test_full128_known_metrics_json_csv_and_ci_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evaldir = self.complete_fixture(root)
            result = a.audit(root, evaldir)
            self.assertEqual(result['status'], 'PASS', result['errors'][:3])
            self.assertTrue(result['gold_opened'])
            self.assertEqual(result['denominators'], {'allocated': 128, 'file': 125, 'function': 117})
            self.assertEqual(result['invalid_slots']['cosil']['function'], 256)
            self.assertEqual(result['duplicate_slots']['cosil']['function'], 128)
            self.assertEqual(result['paired_comparisons']['cosil_vs_sfpruner']['function']['hit1']['n'], 117)

    def test_report_corruption_is_detected_without_changing_predictions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evaldir = self.complete_fixture(root)
            report = json.loads((evaldir / 'per_issue.json').read_text())
            report[0]['arms']['cosil']['metrics']['function']['hit1'] = False
            put(evaldir / 'per_issue.json', report)
            result = a.audit(root, evaldir)
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(any(e['kind'] == 'reported_value_mismatch' for e in result['errors']))

    def test_missing_analysis_completion_never_opens_gold(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evaldir = self.complete_fixture(root)
            (root / 'analysis_supervisor/completion.json').unlink()
            result = a.audit(root, evaldir)
            self.assertEqual(result['status'], 'PENDING')
            self.assertFalse(result['gold_opened'])

    def test_failed_task_remains_in125_and117_denominators(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evaldir = self.complete_fixture(root)
            iid = 'synthetic__repo-0'
            directory = root / 'run' / iid / 'cosil'
            original = json.loads((directory / 'result.json').read_text())
            result = {k: original[k] for k in ('instance_id', 'repo', 'base_commit')}
            result['status'] = 'failed'
            put(directory / 'result.json', result)
            terminal = json.loads((directory / 'terminal.json').read_text())
            terminal.update(status='worker_failed', result_sha256=a.digest(directory / 'result.json'))
            put(directory / 'terminal.json', terminal)
            groupfile = root / 'run' / iid / 'group_terminal.json'
            group = json.loads(groupfile.read_text())
            group['arms']['cosil'] = terminal
            put(groupfile, group)
            audited = a.audit(root, evaldir)
            self.assertEqual(audited['status'], 'FAIL')  # Saved report intentionally still says success.
            self.assertEqual(audited['denominators']['file'], 125)
            self.assertEqual(audited['denominators']['function'], 117)
            self.assertEqual(audited['metrics']['cosil']['function']['hit1']['numerator'], 116)
            self.assertEqual(audited['metrics']['cosil']['function']['hit1']['denominator'], 117)
            self.assertEqual(audited['records'][0]['arms']['cosil']['status'], 'worker_failed')

    def test_group_terminal_drift_is_caught_before_gold(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evaldir = self.complete_fixture(root)
            terminal = root / 'run/synthetic__repo-0/group_terminal.json'
            data = json.loads(terminal.read_text())
            data['arms']['cosil']['result_sha256'] = '0' * 64
            put(terminal, data)
            result = a.audit(root, evaldir)
            self.assertEqual(result['status'], 'FAIL')
            self.assertFalse(result['gold_opened'])
            self.assertTrue(any(x['kind'] == 'group_arm_terminal_disagrees' for x in result['errors']))

    def test_bound_derived_view_requires_its_own_analysis_closure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evaldir = self.complete_fixture(root)
            view = root / 'evaluation_views/signature_format_v2'
            view.mkdir(parents=True)
            allocation = json.loads((root / 'allocation.json').read_text())
            put(view / 'allocation.json', allocation)
            (view / 'public').symlink_to(root / 'public', target_is_directory=True)
            (view / 'evaluator_private').symlink_to(root / 'evaluator_private', target_is_directory=True)
            frozen = json.loads((root / 'execution_freeze.json').read_text())
            put(root / 'audits/signature_view_execution_freeze.json', frozen)
            manifest_records = []
            for row in allocation['records']:
                iid = row['instance_id']
                terminals = {}
                for arm in a.ARMS:
                    origin, target = root / 'run' / iid / arm, view / 'run' / iid / arm
                    original = json.loads((origin / 'result.json').read_text())
                    derived = {**original, 'offline_identity_view': {
                        'version': 'java_signature_format_v2', 'original_result': str(origin / 'result.json'),
                        'original_result_sha256': a.digest(origin / 'result.json'),
                        'base_index_sha256': a.digest(root / 'public' / iid / 'code_index.json'),
                        'new_model_calls': 0, 'Gold_read_for_normalization': False}}
                    put(target / 'result.json', derived)
                    put(target / 'normalization_provenance.json', {'new_model_calls': 0, 'Gold_read': False})
                    terminal = json.loads((origin / 'terminal.json').read_text())
                    terminal.update(offline_view_only=True, result_sha256=a.digest(target / 'result.json'))
                    put(target / 'terminal.json', terminal)
                    terminals[arm] = terminal
                    manifest_records.append({'instance_id': iid, 'arm': arm,
                        'original_result_sha256': a.digest(origin / 'result.json'),
                        'derived_result_sha256': a.digest(target / 'result.json'),
                        'provenance_sha256': a.digest(target / 'normalization_provenance.json')})
                put(view / 'run' / iid / 'group_terminal.json', {'instance_id': iid, 'status': 'group_terminal',
                                                              'arms': terminals, 'offline_view_only': True})
            put(view / 'run/completion.json', {'status': 'COMPLETE', 'allocated': 128, 'groups': 128, 'offline_view_only': True})
            manifest = {'status': 'COMPLETE', 'allocated': 128, 'new_model_calls': 0,
                'normalization_uses_Gold': False, 'original_root': str(root),
                'source_allocation_sha256': a.digest(root / 'allocation.json'), 'records': manifest_records}
            put(view / 'view_manifest.json', manifest)
            derived_eval = root / 'reports/signature_v2_evaluation'
            derived_eval.mkdir()
            for filename in ('per_issue.json', 'per_issue.csv'):
                (derived_eval / filename).write_bytes((evaldir / filename).read_bytes())
            summary = json.loads((evaldir / 'summary.json').read_text())
            summary['provenance_sha256'] = provenance(view, allocation['records'])
            put(derived_eval / 'summary.json', summary)
            missing = a.audit(root, derived_eval, view)
            self.assertEqual(missing['status'], 'PENDING')
            self.assertFalse(missing['gold_opened'])
            put(root / 'signature_view_supervisor/completion.json', {
                'status': 'NORMALIZED_REPORTS_READY_FOR_INDEPENDENT_REVIEW', 'new_model_calls': 0,
                'outputs_sha256': {str(derived_eval / 'summary.json'): a.digest(derived_eval / 'summary.json')},
                'view_manifest_sha256': a.digest(view / 'view_manifest.json'),
                'original_analysis_completion_sha256': a.digest(root / 'analysis_supervisor/completion.json')})
            done = a.audit(root, derived_eval, view)
            self.assertEqual(done['status'], 'PASS', done['errors'][:3])
            # Keep the group internally consistent, but change a derived outcome
            # field. The audit must compare with the original terminal as well.
            tp = view / 'run/synthetic__repo-0/cosil/terminal.json'
            terminal = json.loads(tp.read_text())
            terminal['elapsed_seconds'] = 123.0
            put(tp, terminal)
            gp = tp.parent.parent / 'group_terminal.json'
            group = json.loads(gp.read_text())
            group['arms']['cosil'] = terminal
            put(gp, group)
            changed = a.audit(root, derived_eval, view)
            self.assertEqual(changed['status'], 'FAIL')
            self.assertTrue(any(e['kind'] == 'derived_view_changed_terminal_outcome_or_timing' for e in changed['errors']))


if __name__ == '__main__':
    unittest.main()
