"""Outcome-free CPU tests for the frozen extension selection contract."""
from collections import Counter
import random
import unittest

from . import prepare as p


def row(iid, repo='owner/repo', source=p.pc.FULL_ID, base='a' * 40):
    return dict(instance_id=iid, repo=repo, base_commit=base, source_id=source,
                issue_sha256='b' * 64, patch_sha256='c' * 64)


def eligible(_):
    return dict(status='QUALIFIED', complete=True, nonempty=True,
                R2_status='COMPLETE_NONEMPTY', base_files_sha256={'file.py': 'd' * 64})


class PrefixTests(unittest.TestCase):
    def test_prior308_exclusion_and_cap_include_all_original308(self):
        prior = [row(f'prior{i}', f'owner/repo{i}') for i in range(308)]
        candidates = [row('prior0', 'different/repo')] + [row(f'new{i}', 'OWNER/REPO0') for i in range(5)]
        candidates += [row(f'other{i}', f'fresh/repo{i}') for i in range(3)]
        result = p.ordered_prefix(candidates, prior, eligible, target=5)
        self.assertEqual(result['status'], 'READY')
        self.assertNotIn('prior0', result['selected_prefix_ids'])
        self.assertEqual(sum(r['repo'].casefold() == 'owner/repo0' for r in result['records']), 2)
        self.assertEqual(result['repo_counts_including_original308']['owner/repo0'], 3)

    def test_new_repository_cap_three_and_permutation_invariance(self):
        candidates = [row(f'new{i}', f'owner/repo{i % 7}') for i in range(45)]
        one = p.ordered_prefix(candidates, [], eligible, target=20)
        random.Random(771).shuffle(candidates)
        two = p.ordered_prefix(candidates, [], eligible, target=20)
        self.assertEqual(one, two)
        self.assertTrue(all(n <= 3 for n in Counter(r['repo'].casefold() for r in one['records']).values()))

    def test_missing_qualification_blocks_without_replacement(self):
        candidates = [row(f'i{i}', f'owner/r{i}') for i in range(6)]
        order = sorted(candidates, key=lambda r: p.pc.order_key(r, p.SEED))
        seen = []
        def qualifier(record):
            seen.append(record['instance_id'])
            return None if len(seen) == 2 else eligible(record)
        result = p.ordered_prefix(candidates, [], qualifier, target=3)
        self.assertEqual(result['status'], 'BLOCKED_QUALIFICATION')
        self.assertEqual(seen, [r['instance_id'] for r in order[:2]])
        self.assertFalse(result['selection_frozen']); self.assertEqual(result['records'], [])
        self.assertEqual(len(result['selected_prefix_ids']), 1)

    def test_network_block_preserves_prefix(self):
        candidates = [row(f'i{i}', f'owner/r{i}') for i in range(6)]
        seen = []
        def qualifier(record):
            seen.append(record['instance_id'])
            if len(seen) == 2: raise p.q.NetworkBlocked('temporary transport failure')
            return eligible(record)
        result = p.ordered_prefix(candidates, [], qualifier, target=3)
        self.assertEqual(result['status'], 'BLOCKED_NETWORK')
        self.assertEqual(len(seen), 2); self.assertEqual(result['records'], [])

    def test_insufficient_qualified_is_not_ready(self):
        result = p.ordered_prefix([row('i')], [], eligible, target=2)
        self.assertEqual(result['status'], 'INSUFFICIENT_QUALIFIED_TASKS')
        self.assertEqual(result['records'], []); self.assertFalse(result['selection_frozen'])

    def test_only_definitive_unavailable_advances(self):
        candidates = [row(f'i{i}', f'o/r{i}') for i in range(4)]
        first = sorted(candidates, key=lambda r: p.pc.order_key(r, p.SEED))[0]['instance_id']
        def qualifier(record):
            return dict(status='SOURCE_UNAVAILABLE', qualification_source='definite_HTTP_404_or_410') if record['instance_id'] == first else eligible(record)
        self.assertEqual(p.ordered_prefix(candidates, [], qualifier, target=3)['status'], 'READY')
        def uncertain(record):
            return dict(status='SOURCE_UNAVAILABLE', qualification_source='timeout')
        self.assertEqual(p.ordered_prefix(candidates, [], uncertain, target=3)['status'], 'BLOCKED_QUALIFICATION')

    def test_reference_priority_conflicts_not_full_fallback(self):
        full = row('same', base='a' * 40)
        reference = row('same', source=p.pc.REFERENCE_ID, base='b' * 40)
        for candidates in ([full, reference], [reference, full]):
            selected, conflicts = p.source_priority(candidates)
            self.assertEqual(selected, [reference]); self.assertFalse(conflicts[0]['fields_equal'])
            seen = []
            def no_targets(record):
                seen.append(record['source_id'])
                return dict(status='INELIGIBLE', complete=True, nonempty=False, R2_status='COMPLETE_EMPTY')
            outcome = p.ordered_prefix(candidates, [], no_targets, target=1)
            self.assertEqual(seen, [p.pc.REFERENCE_ID])
            self.assertEqual(outcome['status'], 'INSUFFICIENT_QUALIFIED_TASKS')

    def test_same_source_conflicting_duplicate_blocks(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting duplicate'):
            p.source_priority([row('i'), row('i', base='f' * 40)])

    def test_nonboolean_or_inconsistent_qualification_blocks(self):
        for bad in [dict(status='QUALIFIED', complete=1, nonempty=True),
                    dict(status='INELIGIBLE', complete=True, nonempty=True),
                    dict(status='QUALIFIED', complete=True, nonempty=True, R2_status='WRONG')]:
            result = p.ordered_prefix([row('i')], [], lambda _: bad, target=1)
            self.assertEqual(result['status'], 'BLOCKED_QUALIFICATION')


if __name__ == '__main__':
    unittest.main()
