import unittest

from code_repair50.statistics import exact_mcnemar, paired_statistics, proportion


class StatisticsTests(unittest.TestCase):
    def test_exact_mcnemar_known_values(self):
        self.assertEqual(exact_mcnemar(0, 0)["pvalue_two_sided"], 1)
        self.assertAlmostEqual(exact_mcnemar(0, 5)["pvalue_two_sided"], 0.0625)
        self.assertEqual(exact_mcnemar(2, 2)["pvalue_two_sided"], 1)

    def test_pairwise_missingness_not_failure(self):
        value = paired_statistics([
            {"instance_id": "one", "A": True, "B": True},
            {"instance_id": "two", "A": False, "B": True},
            {"instance_id": "three", "A": True, "B": False},
            {"instance_id": "four", "A": False, "B": False},
            {"instance_id": "five", "A": None, "B": True},
        ], n_bootstrap=100)
        self.assertEqual(value["paired_n"], 4)
        self.assertEqual(value["excluded_instance_ids"], ["five"])
        self.assertEqual(list(value["four_cells"].values()), [1, 1, 1, 1])
        self.assertEqual(value["B_minus_A"], 0)

    def test_bootstrap_is_paired_and_reproducible(self):
        data = [{"instance_id": str(i), "A": i % 2 == 0, "B": True} for i in range(10)]
        a = paired_statistics(data, n_bootstrap=500)
        b = paired_statistics(data, n_bootstrap=500)
        self.assertEqual(a, b)
        self.assertEqual(a["B_minus_A"], 0.5)
        self.assertGreaterEqual(a["B_minus_A_ci95"][0], 0)

    def test_empty_is_na(self):
        result = paired_statistics([], n_bootstrap=10)
        self.assertIsNone(result["B_minus_A"])
        self.assertIsNone(result["B_minus_A_ci95"])
        self.assertIsNone(result["mcnemar"])
        self.assertIsNone(proportion(0, 0)["value"])

    def test_all_identical_pairs_have_zero_paired_difference(self):
        data = [{"instance_id": str(i), "A": bool(i % 2), "B": bool(i % 2)} for i in range(8)]
        self.assertEqual(paired_statistics(data, n_bootstrap=20)["B_minus_A_ci95"], [0, 0])

    def test_duplicate_iid_or_numeric_truthiness_rejected(self):
        with self.assertRaises(ValueError):
            paired_statistics([{"instance_id": "x", "A": 1, "B": True}], n_bootstrap=10)
        with self.assertRaises(ValueError):
            paired_statistics([{"instance_id": "x", "A": True, "B": True}] * 2, n_bootstrap=10)
        for values in ((1, 0), (-1, 2), (True, 2)):
            with self.assertRaises(ValueError):
                proportion(*values)


if __name__ == "__main__":
    unittest.main()
