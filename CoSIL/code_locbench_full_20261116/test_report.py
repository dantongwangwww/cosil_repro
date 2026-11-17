"""Synthetic tests of scope, finality, lossless metrics and resource accounting."""
from __future__ import annotations

from copy import deepcopy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import report as r


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def sample_record(i, *, a=True, b=False, status='complete', eligible=True):
    iid = 'synthetic__repo-' + str(i).zfill(4)
    target = 'src/file.py::target'
    gold = {'status': 'COMPLETE_NONEMPTY' if eligible else 'PARTIAL', 'set_complete': eligible,
            'targets': [target], 'gold_files': ['src/file.py']}
    inventory = {'function_identities': [target, 'src/file.py::other'], 'paths': ['src/file.py', 'src/other.py']}
    def pred(hit):
        return {'status': status, 'predicted_functions': [{'path': 'src/file.py', 'qualified_name': 'target' if hit else 'other'}],
                'predicted_files': ['src/file.py'] if hit else ['src/other.py']}
    predictions = {'instance_id': iid, 'repo': 'synthetic/repo', 'base_commit': 'base' + str(i),
                   'arms': {'baseline': pred(a), 'hybrid_safe': pred(b)}}
    if status == 'NOT_RUN':
        for value in predictions['arms'].values():
            value.update(predicted_functions=[], predicted_files=[])
    row = r.e.evaluate([predictions], {iid: gold}, {iid: inventory}, draws=40)['records'][0]
    return row


def resource(main, *, file_tokens=0, unknown=0):
    return {'main_tokens': main if not unknown else None, 'known_prompt_tokens': main,
        'known_completion_tokens': 0, 'unknown_usage_attempts': unknown,
        'worker_elapsed_seconds': 1., 'file_main_usage': {'prompt': file_tokens, 'completion': 0, 'unknown': 0},
        'local_input_tokens': 2, 'local_decisions': 1, 'local_forward_seconds': .01,
        'routes': {'qwen': 1}, 'usage_source': 'synthetic_receipts'}


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.order = [{'instance_id': 'synthetic__repo-' + str(i).zfill(4),
                       'repo': 'synthetic/repo', 'base_commit': 'base' + str(i)} for i in range(560)]
        self.frozen_execution = r.c.FrozenBackend().protocol()

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, start=0, n=100, *, a=True, b=False):
        directory = self.root / ('batch' + str(start)) / 'reports/final'
        directory.mkdir(parents=True)
        work = directory.parents[1]
        allocations = [{**row, 'train_repo_seen': False} for row in self.order[start:start+n]]
        rows = [sample_record(i, a=a, b=b) for i in range(start, start+n)]
        evaluated = r.summarize(rows, draws=40)
        controller = {'schema': 1, 'simulation': False, 'controller_sha256': r.c.sha(r.c.__file__),
            'execution': self.frozen_execution, 'arms': list(r.ARMS), 'replay_policy': 'never replay',
            'arm_timeout_seconds': 3600, 'scheduling': {'pair_workers': 2, 'main_max_num_seqs': 1},
            'protocol_sha256': 'synthetic-protocol-' + str(start)}
        controller_path = work / 'paired_run/freeze.json'; write(controller_path, controller)
        terminal_paths = {}
        for row in allocations:
            for suffix in ('baseline/terminal.json', 'hybrid_safe/terminal.json', 'pair_terminal.json'):
                path = work / 'paired_run/pairs' / row['instance_id'] / suffix
                write(path, {'instance_id': row['instance_id'], 'state': 'complete'})
                terminal_paths[str(path)] = r.sha(path)
        gate = {'passed': True, 'issues': n, 'terminal_pairs': n, 'terminal_arms': 2*n,
            'gold_opened_during_gate': False, 'terminal_sha256': terminal_paths,
            'protocol_sha256': controller['protocol_sha256']}
        frozen = {'status': 'FROZEN_BEFORE_SCORING', 'allocated': n, 'runnable': n,
            'protocol_sha256': 'cohort-' + str(start), 'run_root': str(work / 'paired_run'),
            'parquet': str(work / 'unused.parquet'),
            'source_sha256': {str(controller_path): r.sha(controller_path)}}
        write(directory / 'report_freeze.json', frozen)
        summary = {'status': 'FINAL', 'allocated': n, 'runnable': n,
            'dataset': 'czlll/Loc-Bench_V1', 'revision': r.original.SOURCE_REVISION,
            'official_scorer_sha256': r.original.OFFICIAL_SCORER_SHA,
            'evaluator_sha256': r.c.sha(r.e.__file__), 'gold_read_after_all_runnable_terminal': True,
            'test_unsealed': False, 'new_model_calls_by_evaluator': 0,
            'protocol_sha256': frozen['protocol_sha256'], 'report_freeze_sha256': r.sha(directory / 'report_freeze.json'),
            'main_group': 'all' + str(n), 'groups': {'all' + str(n): evaluated['summary']}}
        write(directory / 'summary.json', summary); write(directory / 'terminal_gate.json', gate)
        write(directory / 'allocation.json', {'n': n, 'records': allocations})
        write(directory / ('all' + str(n) + '_evaluation.json'), evaluated)
        flat = []
        for row in rows:
            item = {k: row[k] for k in ('instance_id', 'repo', 'base_commit', 'gold_status')}
            item.update({k: json.dumps(row[k]) for k in ('gold_files', 'gold_functions')})
            for arm in r.ARMS:
                item[arm + '_status'] = row[arm + '_status']
                item[arm + '_resource'] = json.dumps(resource(100 if arm == 'baseline' else 50, file_tokens=10 if arm == 'baseline' else 0))
                for unit in ('file', 'function'):
                    for metric in r.METRICS:
                        item[arm + '_' + unit + '_' + metric] = row[arm + '_' + unit][metric]
            flat.append(item)
        with (directory / ('all' + str(n) + '_逐题定位与资源.csv')).open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, list(flat[0])); writer.writeheader(); writer.writerows(flat)
        official = {'n': n, 'k_values': [1, 3, 5, 10], 'source_sha256': r.original.OFFICIAL_SCORER_SHA,
            'view': 'synthetic official', 'metrics': {}, 'records': [dict(instance_id=row['instance_id'],
                **{arm: {unit: {'Acc@1': int(a if arm == 'baseline' else b), 'P@5': .2 if (a if arm == 'baseline' else b) else 0}
                          for unit in ('file', 'function')} for arm in r.ARMS}) for row in rows]}
        write(directory / 'official_compatible.json', official)
        self.rehash(directory)
        return directory

    def rehash(self, directory):
        write(directory / 'output_sha256.json', {p.name: r.sha(p) for p in directory.iterdir()
              if p.is_file() and p.name != 'output_sha256.json'})

    def combine(self, directories, out='combined'):
        with patch.object(r, 'official_order', return_value=self.order):
            return r.combine(directories, self.root / out, draws=40)

    def test_fixed_prefix_merge_preserves_every_issue_and_recomputes_pairing(self):
        first = self.fixture(a=True, b=False)
        second = self.fixture(100, a=False, b=True)
        result = self.combine([first, second])
        metric = result['groups']['all200']['metrics']
        self.assertEqual(result['allocated'], 200)
        self.assertEqual(metric['baseline']['function']['hit5_numerator'], 100)
        self.assertEqual(metric['hybrid_safe']['function']['hit5_numerator'], 100)
        ev = r.read(self.root / 'combined/evaluation.json')
        self.assertEqual(ev['paired_function']['hit5']['only_a'], 100)
        self.assertEqual(ev['paired_function']['hit5']['only_b'], 100)
        self.assertEqual(ev['paired_function']['hit5']['exact_mcnemar_p'], 1.)
        with (self.root / 'combined/逐题定位与资源.csv').open(encoding='utf-8-sig') as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 200)

    def test_duplicate_report_rejected(self):
        first = self.fixture()
        with self.assertRaisesRegex(ValueError, 'unique fixed checkpoint'):
            self.combine([first, first])

    def test_skipped_first_batch_rejected(self):
        second = self.fixture(100)
        with self.assertRaisesRegex(ValueError, 'skipped, replaced or reordered'):
            self.combine([second])

    def test_reports_reordered_rejected(self):
        a, b = self.fixture(), self.fixture(100)
        with self.assertRaisesRegex(ValueError, 'skipped, replaced or reordered'):
            self.combine([b, a])

    def test_nonfinal_gate_rejected_before_gold_bearing_evaluation_parse(self):
        first = self.fixture()
        value = r.read(first / 'terminal_gate.json'); value['terminal_arms'] = 199
        write(first / 'terminal_gate.json', value); self.rehash(first)
        original_read = r.read
        def guarded(path):
            self.assertFalse(str(path).endswith('_evaluation.json'))
            return original_read(path)
        with patch.object(r, 'read', side_effect=guarded):
            with self.assertRaisesRegex(ValueError, 'terminals must precede'):
                self.combine([first])

    def test_terminal_file_drift_rejected(self):
        first = self.fixture(); gate = r.read(first / 'terminal_gate.json')
        Path(next(iter(gate['terminal_sha256']))).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'terminal receipt drift'):
            self.combine([first])

    def test_output_hash_drift_rejected(self):
        first = self.fixture()
        with (first / 'all100_evaluation.json').open('a') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'output hash/shape drift'):
            self.combine([first])

    def test_manifest_cannot_omit_score_file(self):
        first = self.fixture(); manifest = r.read(first / 'output_sha256.json')
        del manifest['all100_evaluation.json']; write(first / 'output_sha256.json', manifest)
        with self.assertRaisesRegex(ValueError, 'manifest is incomplete'):
            self.combine([first])

    def test_method_drift_cannot_be_hidden_by_different_cohort_protocol_sha(self):
        first = self.fixture(); second = self.fixture(100)
        frozen = r.read(second / 'report_freeze.json')
        path = Path(frozen['run_root']) / 'freeze.json'; controller = r.read(path)
        controller['scheduling']['pair_workers'] = 3; write(path, controller)
        frozen['source_sha256'][str(path)] = r.sha(path); write(second / 'report_freeze.json', frozen)
        summary = r.read(second / 'summary.json'); summary['report_freeze_sha256'] = r.sha(second / 'report_freeze.json')
        write(second / 'summary.json', summary); self.rehash(second)
        with self.assertRaisesRegex(ValueError, 'different model, prompt, renderer or scheduling'):
            self.combine([first, second])

    def test_existing_output_never_overwritten(self):
        first = self.fixture(); self.combine([first])
        marker = r.sha(self.root / 'combined/summary.json')
        with self.assertRaises(FileExistsError):
            self.combine([first])
        self.assertEqual(marker, r.sha(self.root / 'combined/summary.json'))

    def test_macro_f1_is_mean_of_issue_f1_not_harmonic_of_macro_pr(self):
        rows = [sample_record(0), sample_record(1)]
        rows[0]['gold_functions'] = ['src/file.py::target', 'src/file.py::other']
        value = rows[0]['baseline_function']
        for k in (1, 3, 5):
            value.update({m + str(k): x for m, x in r.e.scores(value['slots'], rows[0]['gold_functions'], k).items()})
        result = r.summarize(rows, draws=40)['summary']['metrics']['baseline']['function']
        expected = sum(row['baseline_function']['f15'] for row in rows) / 2
        self.assertAlmostEqual(result['f15'], expected)
        harmonic = 2*result['precision5']*result['recall5']/(result['precision5']+result['recall5'])
        # Different target cardinality is the reason macro F1 must be computed per issue.
        self.assertNotAlmostEqual(result['f15'], harmonic)

    def test_failure_and_not_run_remain_in_eligible_denominator(self):
        rows = [sample_record(0), sample_record(1, status='NOT_RUN')]
        s = r.summarize(rows, draws=40)['summary']
        self.assertEqual(s['allocated'], 2)
        self.assertEqual(s['function_denominator'], 2)
        self.assertEqual(s['metrics']['baseline']['function']['hit1'], .5)
        self.assertEqual(s['statuses']['baseline']['NOT_RUN'], 1)

    def test_na_is_separate_not_silently_removed_from_allocation(self):
        rows = [sample_record(0), sample_record(1, eligible=False)]
        s = r.summarize(rows, draws=40)['summary']
        self.assertEqual(s['allocated'], 2)
        self.assertEqual(s['function_denominator'], 1)
        self.assertEqual(s['file_denominator'], 2)

    def test_resource_shared_stage_is_added_for_fair_comparison(self):
        rows = [{'instance_id': 'a', 'baseline_resource': json.dumps(resource(100, file_tokens=10)),
                 'hybrid_safe_resource': json.dumps(resource(50))}]
        value = r.resources(rows)
        self.assertEqual(value['sfpruner_main_tokens_including_shared_file_stage'], 60)
        self.assertAlmostEqual(value['fair_main_token_relative_reduction'], .4)
        self.assertEqual(value['actual_both_arms_main_tokens'], 150)

    def test_unknown_usage_is_not_zero_or_a_fake_saving(self):
        rows = [{'instance_id': 'a', 'baseline_resource': json.dumps(resource(100, file_tokens=10)),
                 'hybrid_safe_resource': json.dumps(resource(50, unknown=1))}]
        value = r.resources(rows)
        self.assertIsNone(value['sfpruner_main_tokens_including_shared_file_stage'])
        self.assertIsNone(value['fair_main_token_relative_reduction'])

    def test_report_batch_requires_preexisting_freeze_and_uses_original_execute(self):
        work = self.root / 'single'; work.mkdir()
        with self.assertRaisesRegex(ValueError, 'before inference'):
            r.report_batch(work)
        write(work / 'controller/report_freeze.json', {'frozen': True})
        with patch.object(r.original, 'execute', return_value={'status': 'FINAL'}) as execute:
            self.assertEqual(r.report_batch(work), {'status': 'FINAL'})
            execute.assert_called_once_with(work / 'controller/report_freeze.json', work / 'reports/final')


if __name__ == '__main__':
    unittest.main()
