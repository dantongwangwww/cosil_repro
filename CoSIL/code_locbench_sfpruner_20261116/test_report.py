"""Synthetic CPU tests: no model, GPU, network, history writes or sealed data."""
from contextlib import ExitStack, contextmanager
import copy
import json
from pathlib import Path
import re
import tempfile
import typing
import unittest
from unittest import mock

from code_locbench_sfpruner_20261116 import report as r
from code_sfpruner_add20_20261116.test_report import Fixture as ExecutionFixture


class Fixture:
    def __init__(self, root, *, runnable=3, allocated_count=560):
        self.root = Path(root); self.execution = ExecutionFixture(root, n=max(1, runnable))
        paths = r.locations(root); self.paths = paths
        if runnable:
            manifest = r.read(self.execution.manifest)
        else:
            manifest = {'n': 0, 'records': []}
            # No excluded task may carry leftover execution evidence.
            import shutil
            shutil.rmtree(self.root / 'paired_run')
        r.c.write(paths['manifest'], manifest)
        allocated = []
        original = []
        gold = {}; inventory = {}; statuses = []
        for number in range(560):
            if number < runnable:
                base = {key: manifest['records'][number][key] for key in ('instance_id', 'repo', 'base_commit')}
            else:
                base = {'instance_id': 'blocked-fixture-' + str(number),
                        'repo': 'fixture/repo-' + str(number // 3), 'base_commit': 'a' * 40}
            iid = base['instance_id']; seen = number < 68
            allocated.append({**base, 'source_id': 'locbench_fixture', 'source_revision': r.SOURCE_REVISION,
                'source_sha256': 'b' * 64, 'train_repo_seen': seen})
            original.append({**base, 'edit_functions': ['m.py:target']})
            complete = number != 559
            gold[iid] = {'status': 'COMPLETE_NONEMPTY' if complete else 'INCOMPLETE_BASE',
                'set_complete': complete, 'targets': ['m.py::target'], 'gold_files': ['m.py'],
                'missing_targets': [] if complete else ['m.py::target'], 'official_edit_functions': ['m.py:target']}
            inventory[iid] = {'paths': ['m.py'], 'function_identities': ['m.py::target', 'm.py::other'] if complete else []}
            statuses.append({'instance_id': iid, 'runnable': number < runnable,
                'status': 'runtime_ready' if number < runnable else 'runtime_preparation_blocked',
                'reason': None if number < runnable else 'synthetic source-download failure'})
        allocated = allocated[:allocated_count]
        selected_ids = {row['instance_id'] for row in allocated}
        gold = {iid: value for iid, value in gold.items() if iid in selected_ids}
        inventory = {iid: value for iid, value in inventory.items() if iid in selected_ids}
        statuses = statuses[:allocated_count]
        r.c.write(paths['allocation'], {'n': allocated_count, 'records': allocated})
        r.c.write(paths['gold'], gold); r.c.write(paths['inventory'], inventory)
        protocol = {'allocated': allocated_count, 'dataset': 'czlll/Loc-Bench_V1', 'revision': r.SOURCE_REVISION}
        r.c.write(paths['protocol'], protocol)
        r.c.write(paths['allocation_status'], {'schema': 1, 'status': 'PREPARATION_FINAL',
            'allocated': allocated_count, 'runnable': runnable, 'blocked': allocated_count - runnable,
            'allocation_sha256': r.c.sha(paths['allocation']),
            'runtime_manifest_sha256': r.c.sha(paths['manifest']),
            'protocol_sha256': r.c.sha(paths['protocol']), 'records': statuses})
        import pyarrow as pa
        import pyarrow.parquet as pq
        p = Path(paths['parquet']); p.parent.mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist(original), p)
        # Freeze only a local synthetic evaluator placeholder in end-to-end
        # fixtures; a separate test checks equations against pinned real source.
        official = Path(paths['official_scorer']); official.parent.mkdir(parents=True)
        official.write_text('# Synthetic evaluator bytes, never benchmark publication\n')
        self.freeze = self.root / 'report_freeze.json'

    @contextmanager
    def pinned(self):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(r, 'PROTOCOL_SHA', r.c.sha(self.paths['protocol'])))
            stack.enter_context(mock.patch.object(r, 'PARQUET_SHA', r.c.sha(self.paths['parquet'])))
            stack.enter_context(mock.patch.object(r, 'OFFICIAL_SCORER_SHA', r.c.sha(self.paths['official_scorer'])))
            # Other agents may concurrently write their own NEW modules. Test
            # freezes pin stable owned files only; production pins the package.
            stack.enter_context(mock.patch.object(r, 'source_files', lambda: [Path(r.__file__), Path(__file__),
                Path(r.e.__file__), Path(r.c.__file__), Path(r.prior.__file__), Path(r.f.__file__)]))
            yield

    def freeze_inputs(self):
        return r.freeze_inputs(self.root, self.freeze, draws=40)


class BarrierTests(unittest.TestCase):
    def test_wrong_parallel_scheduling_stops_before_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, allocated_count=100)
            path = fixture.root / 'paired_run/freeze.json'; value = r.read(path)
            value['scheduling'] = {'pair_workers': 99}
            r.c.write(path, value)
            with fixture.pinned():
                fixture.freeze_inputs()
                with mock.patch.object(r, 'load_bundle') as gold:
                    with self.assertRaisesRegex(ValueError, 'scheduling/source drift'):
                        r.execute(fixture.freeze, fixture.root / 'reports')
                    gold.assert_not_called()

    def test_missing_arm_terminal_never_opens_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp)
            with fixture.pinned():
                fixture.freeze_inputs()
                (fixture.root / 'paired_run/pairs/fixture-2/hybrid_safe/terminal.json').unlink()
                with mock.patch.object(r, 'load_bundle') as gold:
                    with self.assertRaisesRegex(ValueError, 'missing arm terminal'):
                        r.execute(fixture.freeze, fixture.root / 'reports')
                    gold.assert_not_called()

    def test_missing_pair_terminal_never_opens_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp)
            with fixture.pinned():
                fixture.freeze_inputs()
                (fixture.root / 'paired_run/pairs/fixture-2/pair_terminal.json').unlink()
                with mock.patch.object(r, 'load_bundle') as gold:
                    with self.assertRaisesRegex(ValueError, 'missing pair terminal'):
                        r.execute(fixture.freeze, fixture.root / 'reports')
                    gold.assert_not_called()

    def test_unexpected_execution_cannot_be_disguised_as_preparation_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp)
            with fixture.pinned():
                fixture.freeze_inputs()
                r.c.write(fixture.root / 'paired_run/pairs/blocked-fixture-3/baseline/started.json', {'unexpected': True})
                with mock.patch.object(r, 'load_bundle') as gold:
                    with self.assertRaisesRegex(ValueError, 'unexpected execution artifacts'):
                        r.execute(fixture.freeze, fixture.root / 'reports')
                    gold.assert_not_called()

    def test_unexplained_nonrunnable_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp)
            value = r.read(fixture.paths['allocation_status']); value['records'][3]['reason'] = None
            r.c.write(fixture.paths['allocation_status'], value)
            with fixture.pinned():
                with self.assertRaisesRegex(ValueError, 'explicit preparation failure reason'):
                    fixture.freeze_inputs()

    def test_gold_assets_hash_drift_fails_before_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp)
            with fixture.pinned():
                fixture.freeze_inputs()
                Path(fixture.paths['gold']).write_text('{}\n')
                with mock.patch.object(r, 'load_bundle') as gold:
                    with self.assertRaisesRegex(ValueError, 'Frozen source/input drift'):
                        r.execute(fixture.freeze, fixture.root / 'reports')
                    gold.assert_not_called()

    def test_freeze_only_hashes_private_assets_never_parses_or_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp)
            with fixture.pinned(), mock.patch.object(r, 'load_bundle') as gold:
                value = fixture.freeze_inputs()
                self.assertTrue(value['private_assets_hashed_only_not_parsed'])
                self.assertFalse(value['gold_scored']); gold.assert_not_called()


class FullRosterTests(unittest.TestCase):
    def test_pilot100_scope_and_fixed_denominator_are_independent_of_parent560(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, allocated_count=100); out = fixture.root / 'reports'
            with fixture.pinned():
                fixture.freeze_inputs(); summary = r.execute(fixture.freeze, out)
            self.assertEqual(summary['allocated'], 100)
            self.assertEqual(summary['main_group'], 'all100')
            self.assertEqual(summary['groups']['all100']['function_denominator'], 100)
            self.assertNotIn('all560', summary['groups'])
            self.assertEqual(summary['preparation_blocked'], 97)
            self.assertEqual(r.read(out / 'official_compatible.json')['n'], 100)
            self.assertEqual(len(r.read(out / 'predictions.json')['records']), 100)
            self.assertIn('100题', next(out.glob('*总览.md')).read_text())

    def test_fixed560_with_na_source_blocks_and_model_failure_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp); out = fixture.root / 'reports'
            with fixture.pinned():
                fixture.freeze_inputs(); summary = r.execute(fixture.freeze, out)
                self.assertEqual(summary['allocated'], 560); self.assertEqual(summary['runnable'], 3)
                self.assertEqual(summary['preparation_blocked'], 557)
                main = summary['groups']['all560']
                self.assertEqual(main['function_denominator'], 559)
                self.assertEqual(main['file_denominator'], 560)
                self.assertEqual(main['metrics']['baseline']['function']['hit1_numerator'], 1)
                self.assertEqual(main['metrics']['hybrid_safe']['function']['hit1_numerator'], 0)
                self.assertEqual(main['metrics']['hybrid_safe']['function']['hit3_numerator'], 1)
                self.assertEqual(main['statuses']['baseline']['PREPARATION_BLOCKED'], 557)
                self.assertEqual(main['statuses']['baseline']['ERROR_fixture'], 1)
                self.assertEqual(main['statuses']['hybrid_safe']['DEPENDENCY_BLOCKED'], 1)
                self.assertEqual(summary['train_repo_overlap_tasks'], 68)
                self.assertEqual(summary['groups']['train_repo_seen']['allocated'], 68)
                self.assertEqual(summary['groups']['train_repo_unseen']['allocated'], 492)
                rows = r.read(out / 'all560_evaluation.json')['records']
                self.assertEqual(len(rows), 560)
                self.assertEqual(rows[-1]['baseline_function'], None)
                self.assertEqual(rows[3]['baseline_function']['hit5'], 0)
                self.assertEqual(main['metrics']['hybrid_safe']['function']['precision3'], (1 / 3) / 559)
                self.assertTrue((out / 'all560_逐题定位与资源.csv').is_file())
                self.assertEqual(len(r.read(out / 'predictions.json')['records']), 560)
                self.assertEqual(r.read(out / 'terminal_gate.json')['terminal_pairs'], 3)
                with self.assertRaises(FileExistsError):
                    r.execute(fixture.freeze, out)

    def test_zero_runnable_produces_explicit_allocation_not_gpu_or_gold_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(tmp, runnable=0)
            with fixture.pinned():
                fixture.freeze_inputs(); summary = r.execute(fixture.freeze, fixture.root / 'reports')
            self.assertEqual(summary['allocated'], 560); self.assertEqual(summary['runnable'], 0)
            self.assertEqual(summary['groups']['all560']['file_denominator'], 560)
            self.assertEqual(summary['groups']['all560']['metrics']['baseline']['function']['hit5_numerator'], 0)

    def test_canonical_does_not_repair_path_name_or_initializer(self):
        self.assertEqual(r.canonical('pkg/pkg.py:Outer.inner'), 'pkg/pkg.py::Outer.inner')
        self.assertEqual(r.canonical('pkg/mod.py:Class.__init__'), 'pkg/mod.py::Class.__init__')
        for label in ('../m.py:f', '/m.py:f', 'm.py::f', 'm.py:<locals>.f', 'm.py:f()'):
            with self.assertRaises(ValueError):
                r.canonical(label)

    def test_unknown_usage_never_becomes_zero(self):
        self.assertIsNone(r.prior.usage({})['main_tokens'])
        self.assertIsNone(r.prior.usage({'main_tokens': 12, 'unknown_usage_attempts': 1})['main_tokens'])
        self.assertEqual(r.prior.usage(r.empty_resource())['main_tokens'], 0)


class OfficialCompatibilityTests(unittest.TestCase):
    def bundle(self, labels, raw):
        return {'records': [{'instance_id': 'fixture', 'arms': {arm: {'predicted_functions': copy.deepcopy(raw)} for arm in r.ARMS}}],
                'official': {'fixture': {'edit_functions': labels}}}

    def test_gold_three_first_one_hit_official_recall_third_acc_one(self):
        bundle = self.bundle(['m.py:f', 'm.py:g', 'm.py:h'], [{'path': 'm.py', 'qualified_name': 'f'}])
        result, _ = r.official_compatible(bundle)
        metrics = result['metrics']['baseline']['function']
        self.assertEqual(metrics['Recall@1'], 1 / 3)
        self.assertEqual(metrics['Acc@1'], 1); self.assertEqual(metrics['Acc@3'], 0)

    def test_constructor_folding_and_duplicate_multiplicity_preserved(self):
        bundle = self.bundle(['m.py:C.__init__'], [{'path': 'm.py', 'qualified_name': 'C.__init__'}] * 3)
        result, export = r.official_compatible(bundle)
        self.assertEqual(export['baseline'][0]['docs'], ['m.py/C.__init__'] * 3)
        metric = result['metrics']['baseline']['function']
        self.assertEqual(metric['Recall@3'], 3); self.assertEqual(metric['P@3'], 1)
        self.assertEqual(metric['Acc@3'], 0)
        strict = r.e.metrics(bundle['records'][0]['arms']['baseline']['predicted_functions'],
            ['m.py::C.__init__'], ['m.py::C.__init__'], functions=True)
        self.assertEqual(strict['recall3'], 1); self.assertEqual(strict['precision3'], 1 / 3)

    def test_invalid_docs_slot_preserved_and_no_basename_repair(self):
        raw = [None, {'path': 'wrong.py', 'qualified_name': 'C.f'}, {'path': 'm.py', 'qualified_name': 'C.f'}]
        result, docs = r.official_compatible(self.bundle(['m.py:C.f'], raw))
        self.assertEqual(len(docs['baseline'][0]['docs']), 3)
        self.assertEqual(result['metrics']['baseline']['function']['P@1'], 0)
        self.assertEqual(result['metrics']['baseline']['function']['Recall@3'], 1)

    def test_malformed_raw_identity_is_nonmatching_sentinel_not_report_crash(self):
        raw = [{'path': 'm.py', 'qualified_name': 'other.py/f'},
               {'path': 'bad\nm.py', 'qualified_name': 'f'},
               {'path': 'm.py', 'qualified_name': 'f\x00'}]
        result, docs = r.official_compatible(self.bundle(['m.py:f'], raw))
        self.assertEqual(len(docs['baseline'][0]['docs']), 3)
        self.assertTrue(all(value.startswith('__INVALID_RANK_SLOT__/') for value in docs['baseline'][0]['docs']))
        self.assertEqual(result['metrics']['baseline']['function']['Recall@5'], 0)

    def test_equations_match_pinned_official_CPU_functions(self):
        path = r.ROOT / 'results/locbench_qwen3_sfpruner_20261116/dataset_download/official_evaluation/evaluation/eval_metric.py'
        if not path.exists():
            self.skipTest('Run documented official source download to check pinned reference')
        self.assertEqual(r.c.sha(path), r.OFFICIAL_SCORER_SHA)
        import torch
        source = path.read_text(); namespace = {'Tensor': torch.Tensor, 'Optional': typing.Optional, 'torch': torch}
        for name in ('div_no_nan', 'recall_at_k', 'acc_at_k', 'precision_at_k'):
            match = re.search(r'^def ' + name + r'\(.*?(?=^def |\Z)', source, re.M | re.S)
            # Only the pinned pure tensor metric functions are compiled. Do not
            # import the full evaluator or load any dataset/network/model.
            exec(compile(match.group(0), str(path) + ':' + name, 'exec'), namespace)
        pred = torch.tensor([[1, 0, 0, 0, 0, 0, 0, 0, 0, 0]], device='cpu')
        target = torch.tensor([[1, 1, 1, 0, 0, 0, 0, 0, 0, 0]], device='cpu')
        values, _ = r.official_compatible(self.bundle(['m.py:f', 'm.py:g', 'm.py:h'], [{'path': 'm.py', 'qualified_name': 'f'}]))
        for k in r.OFFICIAL_K:
            for label, function in (('Acc', 'acc_at_k'), ('Recall', 'recall_at_k'), ('P', 'precision_at_k')):
                self.assertAlmostEqual(values['metrics']['baseline']['function'][label + '@' + str(k)],
                    namespace[function](pred, target, k=k).item(), places=6)


if __name__ == '__main__':
    unittest.main()
