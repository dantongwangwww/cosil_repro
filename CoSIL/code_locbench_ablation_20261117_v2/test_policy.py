"""Pure CPU synthetic policy/input tests; no benchmark labels or model loads."""
import copy
import hashlib
import math
import unittest
from unittest.mock import patch

from . import policy as p

p.activate_bundle()
from specprune.input_format import INPUT_VERSION, body


class Tokenizer:
    def encode(self, text, **kwargs):
        return list(text)

    def apply_chat_template(self, messages, **kwargs):
        return str(messages)


def row():
    issue, function = 'already fitted issue', 'def already_fitted():\n    return 1'
    neighbors = '[Direct static call context; incomplete, not causal labels]\nf -> g | m.py:1 | g()'
    text = body(issue, function, neighbors)
    return dict(issue=issue, function=function, neighbors=neighbors, model_input=text,
                input_version=INPUT_VERSION, input_sha256=hashlib.sha256(text.encode()).hexdigest(),
                token_budget_trimmed=True, neighbors_selected=1, function_id='m.py::f',
                source_sha256='a' * 64)


class PolicyTests(unittest.TestCase):
    def test_only_normal_gray_changes_and_half_is_retain(self):
        for variant in p.ARMS:
            for score, original in ((0., 'reject'), (.129, 'reject'), (.2, 'qwen'),
                                    (.5, 'qwen'), (.89, 'qwen'), (.9, 'retain'), (1., 'retain')):
                actual = p.route(variant, score, .13, .9)
                self.assertEqual(actual['route_original'], original)
                self.assertEqual(actual['p_yes'], score)
                expected = ('retain' if score >= .5 else 'reject') if (
                    variant == 'ablation_no_defer' and original == 'qwen') else original
                self.assertEqual(actual['route_effective'], expected)
        self.assertEqual(p.route('ablation_no_defer', .5, .13, .9)['route_effective'], 'retain')

    def test_nonfinite_invalid_scores_and_variants_fail_never_reject(self):
        for value in (float('nan'), float('inf'), -float('inf'), -.1, 1.1, True, None, '.5'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.route(p.ARMS[2], value, .13, .9)
        with self.assertRaises(ValueError): p.route('unknown', .5, .13, .9)
        with self.assertRaises(ValueError): p.route(p.ARMS[0], .5, .9, .13)

    def test_neighbors_fully_empty_postfit_no_backfill_no_input_mutation(self):
        original = row(); before = copy.deepcopy(original)
        with patch('specprune.input_format.fit_input', side_effect=AssertionError('must not refit')):
            result = p.without_neighbors(original, {'fake': (Tokenizer(), 'reranker')})
        self.assertEqual(original, before)
        self.assertEqual(result['issue'], original['issue'])
        self.assertEqual(result['function'], original['function'])
        self.assertEqual(result['neighbors'], '')
        self.assertNotIn('Direct static', result['model_input'])
        self.assertIn('<direct_call_context>\n\n</direct_call_context>', result['model_input'])
        self.assertEqual(result['neighbors_selected'], 0)
        self.assertTrue(result['token_budget_trimmed'])
        self.assertEqual(result['original_input_sha256'], original['input_sha256'])
        self.assertEqual(result['input_sha256'], hashlib.sha256(result['model_input'].encode()).hexdigest())
        self.assertEqual(result['token_counts']['fake']['body'], len(result['model_input']))

    def test_bad_original_semantics_or_hash_refused(self):
        for key in ('model_input', 'input_sha256'):
            value = row(); value[key] += 'bad'
            with self.assertRaises(ValueError): p.without_neighbors(value, {})


if __name__ == '__main__':
    unittest.main()
