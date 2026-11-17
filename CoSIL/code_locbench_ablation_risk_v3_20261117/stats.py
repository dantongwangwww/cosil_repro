"""Issue-resampled descriptive risk intervals; no file or model access.

Ratios are ratios of summed counts.  A resample with no visited identity is
undefined and is retained as such in the reported replicate counts.
"""
from __future__ import annotations

import math
import random

DEFAULT_SEED = 20261110
DEFAULT_DRAWS = 5000


def _integer(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, int) or value < int(positive):
        raise ValueError(name + ' must be a ' + ('positive' if positive else 'nonnegative') + ' integer')
    return value


def _settings(draws, seed):
    _integer(draws, 'draws', positive=True)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('seed must be an integer')


def _percentile(values, probability):
    """Linear interpolation at (n-1)*p, equivalent to a type-7 quantile."""
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def _interval(values):
    return [_percentile(values, .025), _percentile(values, .975)] if values else None


def _degenerate(values):
    return bool(values) and min(values) == max(values)


def _binomial_range(n, p, start, stop):
    """Stable sum of binomial probabilities over inclusive integer bounds."""
    if p == 0.:
        return float(start <= 0 <= stop)
    if p == 1.:
        return float(start <= n <= stop)
    terms = [math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1)
             + x * math.log(p) + (n - x) * math.log1p(-p)
             for x in range(start, stop + 1)]
    maximum = max(terms)
    return math.exp(maximum) * math.fsum(math.exp(value - maximum) for value in terms)


def _stdlib_binomial_interval(k, n, tail):
    # Exact binomial tail equations equivalent to beta quantiles.  This is a
    # no-install fallback, not an asymptotic or continuity approximation.
    low, high = 0., 1.
    for _ in range(80):
        mid = (low + high) / 2
        if _binomial_range(n, mid, k, n) < tail:
            low = mid
        else:
            high = mid
    lower = (low + high) / 2
    low, high = 0., 1.
    for _ in range(80):
        mid = (low + high) / 2
        if _binomial_range(n, mid, 0, k) > tail:
            low = mid
        else:
            high = mid
    return [lower, (low + high) / 2]


def exact_binomial_ci(k, n, confidence=.95):
    """Two-sided Clopper-Pearson interval; descriptive post-hoc supplement.

    A zero count does not imply zero population risk.  Here n is a number of
    tasks, not correlated repeated function-score events.  The binomial model
    does not account for dependence between issues from the same repository.
    """
    _integer(k, 'k')
    _integer(n, 'n')
    if k > n:
        raise ValueError('k cannot exceed n')
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or not 0 < confidence < 1):
        raise ValueError('confidence must be finite and strictly between zero and one')
    if not n:
        return None
    tail = (1 - confidence) / 2
    if k == 0:
        return [0., 1 - tail ** (1 / n)]
    if k == n:
        return [tail ** (1 / n), 1.]
    try:
        from scipy.stats import beta
    except ImportError:
        return _stdlib_binomial_interval(k, n, tail)
    return [float(beta.ppf(tail, k, n - k + 1)),
            float(beta.ppf(1 - tail, k + 1, n - k))]


def _indices(rng, n):
    # One sampled index sequence is shared by every count in a paired contrast.
    return [rng.randrange(n) for _ in range(n)]


def issue_risk_ci(per_issue, draws=DEFAULT_DRAWS, seed=DEFAULT_SEED):
    """Bootstrap ``sum(rejected)/sum(visited)`` by whole issue.

    Each row must contain nonnegative integer ``visited`` and ``rejected``
    counts with rejected <= visited.  Callers decide whether these are unique
    identities or events; one call must use the same unit for both counts.
    The full issue list, including zero-visit issues, is resampled unchanged.
    """
    _settings(draws, seed)
    rows = []
    for row in per_issue:
        visited = _integer(row['visited'], 'visited')
        rejected = _integer(row['rejected'], 'rejected')
        if rejected > visited:
            raise ValueError('rejected cannot exceed visited')
        rows.append((visited, rejected))
    visited = sum(row[0] for row in rows)
    rejected = sum(row[1] for row in rows)
    samples = []
    rng = random.Random(seed)
    if rows:
        for _ in range(draws):
            indices = _indices(rng, len(rows))
            denominator = sum(rows[i][0] for i in indices)
            if denominator:
                samples.append(sum(rows[i][1] for i in indices) / denominator)
    return {
        'point': rejected / visited if visited else None,
        'ci95': _interval(samples),
        'degenerate_bootstrap': _degenerate(samples),
        'degenerate_bootstrap_note': 'A degenerate interval, especially [0,0] after no observed rejection, is not proof of zero population risk.',
        'numerator': rejected,
        'denominator': visited,
        'issues': len(rows),
        'defined_draws': len(samples),
        'undefined_draws': draws - len(samples),
        'draws': draws,
        'seed': seed,
        'bootstrap_unit': 'instance_id',
        'estimator': 'ratio of summed per-issue counts',
        'rng': 'stdlib random.Random / randrange',
        'quantile_method': 'linear type-7 percentile',
        'zero_denominator': 'NA; undefined replicates excluded from interval and counted explicitly',
    }


def _identity_sets(value):
    visited, rejected = value['visited'], value['rejected']
    if not isinstance(visited, (set, frozenset)) or not isinstance(rejected, (set, frozenset)):
        raise ValueError('visited and rejected must be identity sets')
    if any(not isinstance(identity, str) or not identity for identity in visited | rejected):
        raise ValueError('identities must be nonempty strings')
    if not rejected <= visited:
        raise ValueError('rejected identity must have been visited')
    return visited, rejected


def common_visited_comparison(reference, comparison, draws=DEFAULT_DRAWS, seed=DEFAULT_SEED):
    """Exploratory paired rejection contrast on actual common visited Gold IDs.

    Both dictionaries must contain exactly the same issue IDs, including
    zero-visit tasks.  For each issue, one identity is counted once, even when
    scored repeatedly.  "Rejected" means any direct-reject event.  The same
    whole-issue draw drives reference, comparison and their difference.
    """
    _settings(draws, seed)
    if set(reference) != set(comparison):
        raise ValueError('paired comparisons require identical issue scopes')
    if any(not isinstance(iid, str) or not iid for iid in reference):
        raise ValueError('issue IDs must be nonempty strings')
    rows = []
    per_issue = []
    for iid in sorted(reference):
        ref_visited, ref_rejected = _identity_sets(reference[iid])
        cmp_visited, cmp_rejected = _identity_sets(comparison[iid])
        common = ref_visited & cmp_visited
        ref_count = len(common & ref_rejected)
        cmp_count = len(common & cmp_rejected)
        rows.append((len(common), ref_count, cmp_count))
        per_issue.append({'instance_id': iid, 'common_visited': len(common),
                          'reference_rejected': ref_count, 'comparison_rejected': cmp_count})
    total = sum(row[0] for row in rows)
    ref_total = sum(row[1] for row in rows)
    cmp_total = sum(row[2] for row in rows)
    ref_samples, cmp_samples, diff_samples = [], [], []
    rng = random.Random(seed)
    if rows:
        for _ in range(draws):
            indices = _indices(rng, len(rows))
            denominator = sum(rows[i][0] for i in indices)
            if denominator:
                ref = sum(rows[i][1] for i in indices) / denominator
                cmp = sum(rows[i][2] for i in indices) / denominator
                ref_samples.append(ref)
                cmp_samples.append(cmp)
                diff_samples.append(cmp - ref)
    return {
        'scope': 'intersection of actually locally scored Gold identities within each issue',
        'exploratory': True,
        'included_in_registered_nine_tests': False,
        'issues': len(rows),
        'issues_with_common_visits': sum(row[0] > 0 for row in rows),
        'common_visited_identities': total,
        'reference_rejected_identities': ref_total,
        'comparison_rejected_identities': cmp_total,
        'reference_risk': ref_total / total if total else None,
        'comparison_risk': cmp_total / total if total else None,
        'comparison_minus_reference': (cmp_total - ref_total) / total if total else None,
        'reference_ci95': _interval(ref_samples),
        'comparison_ci95': _interval(cmp_samples),
        'difference_ci95': _interval(diff_samples),
        'degenerate_bootstrap': {'reference': _degenerate(ref_samples),
                                 'comparison': _degenerate(cmp_samples),
                                 'difference': _degenerate(diff_samples)},
        'degenerate_bootstrap_note': 'A degenerate bootstrap interval cannot reveal unobserved failures and is not proof of zero risk or equivalence.',
        'defined_draws': len(diff_samples),
        'undefined_draws': draws - len(diff_samples),
        'draws': draws,
        'seed': seed,
        'bootstrap_unit': 'instance_id; same draw for both conditions',
        'rng': 'stdlib random.Random / randrange',
        'quantile_method': 'linear type-7 percentile',
        'zero_denominator': 'NA; undefined replicates excluded from interval and counted explicitly',
        'per_issue': per_issue,
    }
