import unittest
import math
from unittest import mock

from .stats import common_visited_comparison, exact_binomial_ci, issue_risk_ci


class RiskStatsTests(unittest.TestCase):
    def test_ratio_of_sums_not_mean_ratios(self):
        result = issue_risk_ci([{'visited': 1, 'rejected': 1},
                                {'visited': 9, 'rejected': 0}], draws=100, seed=1)
        self.assertEqual(result['point'], .1)
        self.assertEqual(result['numerator'], 1)
        self.assertEqual(result['denominator'], 10)
        self.assertEqual(result['defined_draws'], 100)

    def test_zero_denominator_is_na(self):
        result = issue_risk_ci([{'visited': 0, 'rejected': 0}], draws=19)
        self.assertIsNone(result['point'])
        self.assertIsNone(result['ci95'])
        self.assertEqual(result['undefined_draws'], 19)
        self.assertFalse(result['degenerate_bootstrap'])

    def test_empty_scope_is_na_and_all_draws_undefined(self):
        result = issue_risk_ci([], draws=9)
        self.assertEqual(result['issues'], 0)
        self.assertEqual(result['defined_draws'], 0)
        self.assertEqual(result['undefined_draws'], 9)

    def test_zero_visit_issue_remains_in_resampling(self):
        result = issue_risk_ci([{'visited': 0, 'rejected': 0},
                                {'visited': 1, 'rejected': 1}], draws=200, seed=7)
        self.assertGreater(result['undefined_draws'], 0)
        self.assertGreater(result['defined_draws'], 0)
        self.assertEqual(result['defined_draws'] + result['undefined_draws'], 200)
        self.assertEqual(result['ci95'], [1., 1.])
        self.assertTrue(result['degenerate_bootstrap'])

    def test_seed_reproducible(self):
        rows = [{'visited': 1, 'rejected': 1}, {'visited': 0, 'rejected': 0},
                {'visited': 4, 'rejected': 0}]
        self.assertEqual(issue_risk_ci(rows, draws=125, seed=2),
                         issue_risk_ci(rows, draws=125, seed=2))

    def test_invalid_counts_or_settings_rejected(self):
        for row in [{'visited': True, 'rejected': 0}, {'visited': -1, 'rejected': 0},
                    {'visited': 1, 'rejected': 2}, {'visited': 1, 'rejected': .5}]:
            with self.assertRaises(ValueError):
                issue_risk_ci([row], draws=10)
        for settings in [{'draws': 0}, {'draws': True}, {'seed': True}]:
            with self.assertRaises(ValueError):
                issue_risk_ci([], **settings)

    def test_common_intersection_and_unique_any_reject(self):
        ref = {'i': {'visited': {'a', 'b', 'c'}, 'rejected': {'a', 'c'}}}
        cmp = {'i': {'visited': {'a', 'b', 'd'}, 'rejected': {'b', 'd'}}}
        result = common_visited_comparison(ref, cmp, draws=40)
        self.assertEqual(result['common_visited_identities'], 2)
        self.assertEqual(result['reference_rejected_identities'], 1)
        self.assertEqual(result['comparison_rejected_identities'], 1)
        self.assertEqual(result['reference_risk'], .5)
        self.assertEqual(result['comparison_minus_reference'], 0)
        self.assertEqual(result['difference_ci95'], [0., 0.])
        self.assertTrue(result['degenerate_bootstrap']['difference'])
        self.assertTrue(result['exploratory'])
        self.assertFalse(result['included_in_registered_nine_tests'])

    def test_same_pair_uses_same_draw_and_zero_difference(self):
        pair = {'a': {'visited': {'x'}, 'rejected': {'x'}},
                'b': {'visited': {'p', 'q', 'r'}, 'rejected': set()},
                'c': {'visited': set(), 'rejected': set()}}
        result = common_visited_comparison(pair, pair, draws=150, seed=5)
        self.assertEqual(result['comparison_minus_reference'], 0)
        self.assertEqual(result['difference_ci95'], [0., 0.])
        self.assertEqual(result['reference_ci95'], result['comparison_ci95'])

    def test_common_zero_and_undefined_draws(self):
        ref = {'a': {'visited': {'x'}, 'rejected': set()},
               'b': {'visited': set(), 'rejected': set()}}
        cmp = {'a': {'visited': {'y'}, 'rejected': set()},
               'b': {'visited': set(), 'rejected': set()}}
        result = common_visited_comparison(ref, cmp, draws=12)
        self.assertEqual(result['common_visited_identities'], 0)
        self.assertIsNone(result['comparison_minus_reference'])
        self.assertIsNone(result['difference_ci95'])
        self.assertEqual(result['undefined_draws'], 12)
        cmp['a']['visited'] = {'x'}
        result = common_visited_comparison(ref, cmp, draws=100, seed=9)
        self.assertGreater(result['undefined_draws'], 0)
        self.assertEqual(result['issues'], 2)
        self.assertEqual(result['issues_with_common_visits'], 1)

    def test_common_input_validation(self):
        good = {'i': {'visited': {'a'}, 'rejected': set()}}
        with self.assertRaises(ValueError):
            common_visited_comparison(good, {}, draws=5)
        with self.assertRaises(ValueError):
            common_visited_comparison(good, {'i': {'visited': {'a'}, 'rejected': {'b'}}}, draws=5)
        with self.assertRaises(ValueError):
            common_visited_comparison(good, {'i': {'visited': ['a'], 'rejected': set()}}, draws=5)

    def test_common_sort_order_and_seed_reproducible(self):
        a = {'b': {'visited': {'y'}, 'rejected': {'y'}},
             'a': {'visited': {'x'}, 'rejected': set()}}
        b = {'a': {'visited': {'x'}, 'rejected': {'x'}},
             'b': {'visited': {'y'}, 'rejected': set()}}
        x = common_visited_comparison(a, b, draws=81, seed=4)
        y = common_visited_comparison(dict(reversed(list(a.items()))), b, draws=81, seed=4)
        self.assertEqual(x, y)
        self.assertEqual(x['per_issue'][0]['instance_id'], 'a')

    def test_no_observed_reject_bootstrap_is_degenerate_not_zero_risk_proof(self):
        result = issue_risk_ci([{'visited': 5, 'rejected': 0}], draws=30)
        self.assertEqual(result['ci95'], [0., 0.])
        self.assertTrue(result['degenerate_bootstrap'])
        self.assertIn('not proof', result['degenerate_bootstrap_note'])

    def test_clopper_pearson_zero_n_na(self):
        self.assertIsNone(exact_binomial_ci(0, 0))

    def test_clopper_pearson_boundary_exact_formulas(self):
        for n in (1, 3, 27, 560):
            lo, hi = exact_binomial_ci(0, n)
            self.assertEqual(lo, 0.)
            self.assertAlmostEqual(hi, 1 - .025 ** (1 / n))
            lo, hi = exact_binomial_ci(n, n)
            self.assertAlmostEqual(lo, .025 ** (1 / n))
            self.assertEqual(hi, 1.)

    def test_clopper_pearson_interior_satisfies_exact_binomial_tails(self):
        for k, n in ((1, 5), (10, 70), (18, 19)):
            lo, hi = exact_binomial_ci(k, n)
            lower_tail = sum(math.comb(n, x) * lo**x * (1-lo)**(n-x)
                             for x in range(k, n+1))
            upper_tail = sum(math.comb(n, x) * hi**x * (1-hi)**(n-x)
                             for x in range(k+1))
            self.assertAlmostEqual(lower_tail, .025, places=12)
            self.assertAlmostEqual(upper_tail, .025, places=12)

    def test_clopper_pearson_known_interior_reference(self):
        # Published standard exact interval for two successes in ten trials.
        lo, hi = exact_binomial_ci(2, 10)
        self.assertAlmostEqual(lo, .02521072632683336, places=12)
        self.assertAlmostEqual(hi, .5560954623076415, places=12)

    def test_clopper_pearson_scipy_lazy_path(self):
        import sys
        beta = mock.Mock()
        beta.ppf.side_effect = [.1, .8]
        scipy = mock.Mock()
        stats = mock.Mock(beta=beta)
        with mock.patch.dict(sys.modules, {'scipy': scipy, 'scipy.stats': stats}):
            self.assertEqual(exact_binomial_ci(2, 10), [.1, .8])
        self.assertEqual(beta.ppf.call_count, 2)

    def test_clopper_pearson_invalid_parameters(self):
        for args in ((-1, 3), (4, 3), (True, 3), (0, False), (0, 3, 1.),
                     (0, 3, float('nan')), (0, 3, True)):
            with self.assertRaises(ValueError):
                exact_binomial_ci(*args)


if __name__ == '__main__':
    unittest.main()
