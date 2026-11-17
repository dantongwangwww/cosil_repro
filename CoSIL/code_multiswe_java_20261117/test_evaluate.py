import csv
import json
from pathlib import Path
import tempfile
import unittest

from code_multiswe_java_20261117 import evaluate as e


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def inventory():
    return {'src/A.java': {'definitions': [
        {'kind': 'function', 'qualified_name': 'A.f(int)', 'canonical_id': 'src/A.java::A.f(int)'},
        {'kind': 'function', 'qualified_name': 'A.g()', 'canonical_id': 'src/A.java::A.g()'}]}}


def fixture(root, *, complete=True):
    roster = [{'instance_id': f'repo__task-{i:03d}', 'repo': f'org/repo{i}', 'base_commit': f'{i:040x}'} for i in range(128)]
    dump(root/'allocation.json', {'n': 128, 'records': roster, 'revision': 'frozen'})
    for i, row in enumerate(roster[:3]):
        iid = row['instance_id']
        dump(root/'public'/iid/'code_index.json', inventory())
        targets = ['src/A.java::A.f(int)'] if i < 2 else []
        dump(root/'evaluator_private'/iid/'gold.json', {**row, 'file_targets': ['src/A.java'],
            'function_targets': targets, 'file_evaluable': True, 'function_evaluable': bool(targets),
            'existing_target_set_complete': True, 'function_status': 'complete' if targets else 'NA'})
        for arm in e.ARMS:
            if not complete and i == 2 and arm == 'locagent':
                continue
            dump(root/'run'/iid/arm/'terminal.json', {'status': 'complete', 'elapsed_seconds': 3.0})
            result = {'status': 'complete', 'predicted_functions': [
                {'path': 'src/A.java', 'qualified_name': 'A.f(int)'}],
                'ranked_edit_files': ['src/A.java']}
            if arm == 'locagent':
                result = {'status': 'complete', 'ranked_files': ['src/A.java'],
                          'ranked_functions': ['src/A.java::A.f(int)']}
            dump(root/'run'/iid/arm/'result.json', result)
    return roster


class EvaluateTests(unittest.TestCase):
    def test_invalid_duplicate_and_bare_name_slots_are_not_compressed(self):
        result = {'ranked_functions': [
            'src/A.java::A.f', 'bad', 'src/A.java::A.f(int)',
            'src/A.java::A.f(int)', 'src/A.java::A.g()']}
        slots = e.ranking_slots(result, inventory(), 'locagent')['function']
        self.assertEqual([s['rank'] for s in slots], [1, 2, 3, 4, 5])
        self.assertEqual([s['valid'] for s in slots], [False, False, True, False, True])
        score = e.score_slots(slots, {'src/A.java::A.f(int)', 'src/A.java::A.g()'})
        self.assertFalse(score['hit1'])
        self.assertTrue(score['hit3'])
        self.assertEqual(score['precision5'], .4)
        self.assertEqual(score['recall5'], 1.)
        self.assertEqual(score['mrr10'], 1/3)

    def test_inconsistent_canonical_fields_invalid(self):
        result = {'ranked_functions': [{'path': 'src/A.java', 'qualified_name': 'A.f(int)',
                                       'canonical_id': 'src/A.java::A.g()'}, 'src/A.java::A.f(int)']}
        ranking = e.ranking_slots(result, inventory(), 'locagent')['function']
        s = ranking[0]
        self.assertFalse(s['valid'])
        self.assertEqual(s['reason'], 'canonical_id_disagrees_with_fields')
        self.assertTrue(ranking[1]['valid'])

    def test_ambiguous_inventory_is_not_expanded(self):
        i = inventory(); i['src/A.java']['definitions'].append(i['src/A.java']['definitions'][0])
        s = e.ranking_slots({'ranked_functions': ['src/A.java::A.f(int)']}, i, 'locagent')['function'][0]
        self.assertFalse(s['valid'])

    def test_missing_terminal_never_opens_gold(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); rows = fixture(root, complete=False)
            for row in rows[:3]:
                (root/'evaluator_private'/row['instance_id']/'gold.json').write_text('THIS IS NOT JSON')
            value = e.evaluate_run(root, prefix3=True, draws=50)
            self.assertFalse(value['summary']['gold_opened'])
            self.assertIsNone(value['summary']['metrics'])
            self.assertEqual(value['summary']['status'], 'WAITING_TERMINAL_NO_GOLD_OPENED')
            self.assertFalse(any('evaluator_private' in p for p in value['summary']['provenance_sha256']))

    def test_prefix3_keeps_all128_rows_and_NA_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); fixture(root)
            value = e.evaluate_run(root, prefix3=True, draws=50)
            s = value['summary']
            self.assertEqual(len(value['records']), 128)
            self.assertEqual(s['selected'], 3)
            self.assertEqual(s['file_denominator'], 3)
            self.assertEqual(s['function_denominator'], 2)
            self.assertEqual(s['metrics']['cosil']['function']['hit1']['numerator'], 2)
            self.assertEqual(value['records'][3]['gold_status'], 'NOT_SELECTED_PREFIX3')

    def test_failed_model_remains_in_function_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); rows = fixture(root)
            path = root/'run'/rows[0]['instance_id']/'sfpruner'
            dump(path/'terminal.json', {'status': 'worker_failed'})
            (path/'result.json').unlink()
            value = e.evaluate_run(root, prefix3=True, draws=50)
            m = value['summary']['metrics']['sfpruner']['function']['hit5']
            self.assertEqual((m['numerator'], m['denominator']), (1, 2))

    def test_missing_gold_is_error_not_empty_or_model_miss(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); rows = fixture(root)
            (root/'evaluator_private'/rows[0]['instance_id']/'gold.json').unlink()
            value = e.evaluate_run(root, prefix3=True, draws=50)
            self.assertEqual(value['summary']['status'], 'INCOMPLETE_GOLD')
            self.assertIsNone(value['records'][0]['function_evaluable'])
            self.assertIsNone(value['records'][0]['gold_functions'])
            self.assertEqual(value['summary']['function_denominator'], 1)

    def test_unknown_usage_is_not_zero_and_receipt_is_authoritative(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dump(root/'calls/001_file_initial/attempt_0_receipt.json', {'usage': {'prompt_tokens': 11, 'completion_tokens': 2}})
            dump(root/'calls/001_file_initial/attempt_1_start.json', {'stage': 'file_initial'})
            result = e.resource_record(root, {'known_prompt_tokens': 999, 'known_completion_tokens': 999,
                                              'usage_unknown_attempts': 0}, {})
            self.assertEqual(result['known_prompt_tokens'], 11)
            self.assertEqual(result['unknown_usage_attempts'], 1)
            self.assertIsNone(result['physical_main_tokens'])
            missing = e.resource_record(root/'absent', {'usage': None}, {})
            self.assertIsNone(missing['physical_main_tokens'])
            self.assertIsNone(missing['api_cost_usd'])

    def test_shared_file_physical_and_fair_attribution_differ(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); rows = fixture(root)
            iid = rows[0]['instance_id']
            dump(root/'run'/iid/'shared.json', {'files': ['src/A.java']})
            for arm, own in [('cosil', 120), ('sfpruner', 20)]:
                p = root/'run'/iid/arm/'result.json'; r = json.loads(p.read_text())
                r.update(known_prompt_tokens=own, known_completion_tokens=0, usage_unknown_attempts=0)
                if arm == 'cosil':
                    r['stage_resources'] = {'file_initial': {'known_prompt_tokens': 100,
                        'known_completion_tokens': 0, 'usage_unknown_attempts': 0}}
                dump(p, r)
            value = e.evaluate_run(root, prefix3=True, draws=50)
            a = value['records'][0]['arms']
            self.assertEqual(a['cosil']['resource']['physical_main_tokens'], 120)
            self.assertEqual(a['sfpruner']['resource']['physical_main_tokens'], 20)
            self.assertEqual(a['sfpruner']['resource']['fair_attributed_main_tokens'], 120)

    def test_wilson_bootstrap_and_immutable_report(self):
        self.assertTrue(0 < e.wilson(0, 10)[1] < 1)
        self.assertEqual(e.bootstrap_mean([0., 1.], draws=50), e.bootstrap_mean([0., 1.], draws=50))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'; fixture(root)
            value = e.evaluate_run(root, prefix3=True, draws=50)
            out = Path(d)/'reports'; e.write_report(value, out)
            with (out/'per_issue.csv').open(encoding='utf-8-sig', newline='') as f:
                self.assertEqual(len(list(csv.DictReader(f))), 128)
            self.assertIn('金丝雀工程链路', (out/'总览.md').read_text())
            with self.assertRaises(FileExistsError):
                e.write_report(value, out)


if __name__ == '__main__':
    unittest.main()
