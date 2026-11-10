"""Check audit intervals against boundary laws and defining tail equations."""
import math
import unittest

from code_qwen3_rr4.offline_audit import binomial_interval


class ExactIntervalTests(unittest.TestCase):
    def test_zero_events_has_positive_upper_bound(self):
        low, high = binomial_interval(0, 20)
        self.assertEqual(low, 0)
        self.assertAlmostEqual(high, 1 - 0.0125 ** (1 / 20), places=13)

    def test_all_events_has_less_than_one_lower_bound(self):
        low, high = binomial_interval(20, 20)
        self.assertAlmostEqual(low, 0.0125 ** (1 / 20), places=13)
        self.assertEqual(high, 1)

    def test_complement_symmetry(self):
        for n in (17, 20):
            for k in range(n + 1):
                low, high = binomial_interval(k, n)
                other_low, other_high = binomial_interval(n - k, n)
                self.assertAlmostEqual(low, 1 - other_high, places=12)
                self.assertAlmostEqual(high, 1 - other_low, places=12)

    def test_nonboundary_tails(self):
        for k in (1, 7, 19):
            low, high = binomial_interval(k, 20)
            tail_low = sum(math.comb(20, i) * low ** i * (1 - low) ** (20 - i)
                           for i in range(k, 21))
            tail_high = sum(math.comb(20, i) * high ** i * (1 - high) ** (20 - i)
                            for i in range(k + 1))
            self.assertAlmostEqual(tail_low, 0.0125, places=12)
            self.assertAlmostEqual(tail_high, 0.0125, places=12)

    def test_invalid_inputs_rejected(self):
        for args in ((0, 0), (-1, 20), (21, 20), (1, 20, 0), (1, 20, 1)):
            with self.assertRaises(ValueError):
                binomial_interval(*args)


if __name__ == '__main__':
    unittest.main()
