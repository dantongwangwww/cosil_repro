"""Selection is an IID-only fixed hash prefix, never a performance filter."""
import copy
import hashlib
import unittest

from . import pilot


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'instance_id': 'owner__repo-' + str(i), 'repo': 'same/repo',
                      'Gold': i % 2, 'previous_hit': i % 3} for i in range(120)]

    def test_exact_hash_prefix_no_repo_cap_or_replacement(self):
        expected = sorted(self.rows, key=lambda r: (hashlib.sha256(
            ('20261116:' + r['instance_id']).encode()).hexdigest(), r['instance_id']))[:100]
        self.assertEqual(pilot.select(self.rows), expected)
        self.assertEqual(len({r['repo'] for r in expected}), 1)

    def test_membership_unaffected_by_source_order(self):
        self.assertEqual(pilot.select(self.rows), pilot.select(list(reversed(self.rows))))

    def test_gold_and_previous_hit_cannot_change_membership(self):
        modified = copy.deepcopy(self.rows)
        for r in modified:
            r['Gold'] = not r['Gold']; r['previous_hit'] = 99
        self.assertEqual([r['instance_id'] for r in pilot.select(self.rows)],
                         [r['instance_id'] for r in pilot.select(modified)])

    def test_duplicate_or_insufficient_pool_is_not_filled(self):
        for rows in (self.rows[:99], self.rows + [self.rows[0]]):
            with self.assertRaises(ValueError):
                pilot.select(rows)

    def test_projection_preserves_frozen_order_and_refuses_missing(self):
        ids = [self.rows[3]['instance_id'], self.rows[1]['instance_id']]
        self.assertEqual(pilot.project_records(self.rows, ids), [self.rows[3], self.rows[1]])
        with self.assertRaises(ValueError):
            pilot.project_records(self.rows, ['missing'])


if __name__ == '__main__':
    unittest.main()
