import copy
import hashlib
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from code_qwen3_rr4_rebench100 import config as P
from code_qwen3_rr4_rebench100.report import metrics, slots, wilson
from code_rebench_qwen.reporting import normalize_functions, scores

class SamplingTests(unittest.TestCase):
    def rows(self):
        return [{'instance_id': f'o__r-{i}', 'repo': 'O/R' if i < 3 else f'o/r{i}', 'base_commit': 'a'*40,
                 'historical_hit': i % 2, 'gold_status': 'IGNORE'} for i in range(120)]
    def test_selection_is_order_independent_and_unique_repo(self):
        rows = self.rows(); selected, audit = P.select(rows)
        self.assertEqual(selected, P.select(list(reversed(rows)))[0])
        self.assertEqual(len(selected), 100)
        self.assertEqual(len({r['repo'].casefold() for r in selected}), 100)
        self.assertEqual(len(audit), 120)
    def test_changes_in_gold_and_outcome_do_not_change_ids(self):
        rows = self.rows(); other = copy.deepcopy(rows)
        for r in other: r.update(historical_hit=not r['historical_hit'], gold_status='CHANGED')
        self.assertEqual([r['instance_id'] for r in P.select(rows)[0]], [r['instance_id'] for r in P.select(other)[0]])
    def test_hash_implementation_is_fixed(self):
        rows = self.rows(); _, audit = P.select(rows)
        self.assertEqual(audit[0]['sampling_hash'], min(hashlib.sha256(f'20261110:{r["instance_id"]}'.encode()).hexdigest() for r in rows))
    def test_duplicate_ids_and_insufficient_unique_repo_are_rejected(self):
        with self.assertRaises(ValueError): P.select(self.rows() + [self.rows()[0]])
        with self.assertRaises(ValueError): P.select(self.rows()[:20])

class EvaluationTests(unittest.TestCase):
    def test_graph_uses_all_indexed_python_without_opening_nonpython_path(self):
        from code_qwen3_rr4_rebench100.render_cache import build
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root=Path(tmp); raw=b'def f():\n    return 1\n'; (root/'a.py').write_bytes(raw)
            (root/'index.json').write_text(json.dumps({'a.py':{'raw_sha256':hashlib.sha256(raw).hexdigest()}}))
            job={'snapshot':tmp,'code_index':str(root/'index.json'),'base_commit':'a'*40,
                 'paths':['.github/workflows/missing.yml','a.py']}
            with patch.object(P,'OUT',root): info=build(job,root/'cache.json')
            self.assertEqual(info['functions'],1)
    def test_invalid_raw_slot_is_not_compressed(self):
        pred = [{'path':'a.py','qualified_name':'Wrong.f'}, {'path':'a.py','qualified_name':'C.f'}]
        m = metrics(pred, ['a.py::C.f'], ['a.py::C.f'], functions=True)
        self.assertEqual(m['hit1'], 0); self.assertEqual(m['hit3'], 1)
        self.assertEqual(m['precision5'], .2)
    def test_empty_gold_is_na(self):
        self.assertIsNone(metrics([], [], [], functions=True))
    def test_na_does_not_equal_model_miss(self):
        self.assertIsNone(metrics([], [], [], functions=True))
        self.assertEqual(metrics([], ['a.py::f'], ['a.py::f'], functions=True)['hit5'], 0)
    def test_duplicate_predictions_do_not_double_recall(self):
        m = metrics([{'path':'a.py','qualified_name':'f'}]*5, ['a.py::f', 'a.py::g'], ['a.py::f', 'a.py::g'], functions=True)
        self.assertEqual(m['recall5'], .5); self.assertEqual(m['all_coverage5'], 0)
    def test_equivalent_to_existing_r2_normalizer_and_score(self):
        index = {'a.py':{'definitions':[{'qualified_name':'C.f','kind':'function'}]},
                 'tests/a.py':{'definitions':[{'qualified_name':'test_f','kind':'function'}]}}
        raw = [{'path':'./a.py','qualified_name':'C.f'}, {'path':'tests/a.py','qualified_name':'test_f'},
               {'path':'a.py','qualified_name':'Wrong.f'}, {'path':'../a.py','qualified_name':'C.f'}]
        ours = slots(raw, ['a.py::C.f','tests/a.py::test_f'], functions=True)
        self.assertEqual(ours, normalize_functions(raw,index)[0])
        m = metrics(raw, ['a.py::C.f'], ['a.py::C.f'], functions=True)
        for k in (1,3,5):
            for name,value in scores(ours,['a.py::C.f'],k).items(): self.assertEqual(m[f'{name}{k}'],value)
    def test_wilson_zero_events_not_zero_risk(self):
        lo,hi = wilson(0,100); self.assertAlmostEqual(lo,0); self.assertGreater(hi,.03)

if __name__ == '__main__': unittest.main()
