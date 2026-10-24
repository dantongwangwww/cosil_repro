"""CPU-only, dependency-free paired statistics for the repair diagnostic.

Missing/undetermined outcomes are excluded pairwise and explicitly reported;
they are never converted into model test failures. Delivery rates with a fixed
roster denominator are a separate system-level estimand.
"""
from __future__ import annotations

import math
import random
from statistics import NormalDist


SEED = 20261024
BOOTSTRAP_REPLICATES = 20000


def proportion(successes: int, total: int) -> dict:
    if type(successes) is not int or type(total) is not int or not 0 <= successes <= total:
        raise ValueError("A proportion needs integer 0 <= successes <= total")
    if not total:
        return {"numerator": 0, "denominator": 0, "value": None, "ci95": None,
                "ci_method": "Wilson score interval"}
    value = successes / total
    z = NormalDist().inv_cdf(0.975)
    divisor = 1 + z * z / total
    center = (value + z * z / (2 * total)) / divisor
    margin = z * math.sqrt(value * (1 - value) / total + z * z / (4 * total * total)) / divisor
    return {"numerator": successes, "denominator": total, "value": value,
            "ci95": [max(0.0, center - margin), min(1.0, center + margin)],
            "ci_method": "Wilson score interval"}


def exact_mcnemar(only_a: int, only_b: int) -> dict:
    if any(type(value) is not int or value < 0 for value in (only_a, only_b)):
        raise ValueError("McNemar discordant counts must be nonnegative integers")
    count = only_a + only_b
    if not count:
        pvalue = 1.0
    else:
        tail = sum(math.comb(count, number) for number in range(min(only_a, only_b) + 1))
        pvalue = min(1.0, 2 * tail / (2 ** count))
    return {"only_A": only_a, "only_B": only_b, "discordant_n": count,
            "pvalue_two_sided": pvalue, "method": "exact conditional two-sided binomial McNemar"}


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def paired_statistics(pairs: list[dict], *, bootstrap_seed: int = SEED,
                      n_bootstrap: int = BOOTSTRAP_REPLICATES) -> dict:
    """Accept [{instance_id, A: bool|None, B: bool|None}], preserving IID joins.

    Pairing, subset eligibility, and formal-harness provenance must already be
    established by the reporting adapter. None remains an excluded unknown.
    """
    if type(bootstrap_seed) is not int or type(n_bootstrap) is not int or n_bootstrap < 1:
        raise ValueError("Positive bootstrap replicate count and integer seed required")
    seen, observed, excluded = set(), [], []
    for pair in pairs:
        instance_id = pair.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id or instance_id in seen:
            raise ValueError("Unique nonempty instance_id required for paired statistics")
        seen.add(instance_id)
        a, b = pair.get("A"), pair.get("B")
        if any(value is not None and type(value) is not bool for value in (a, b)):
            raise ValueError("Paired outcomes must be booleans or None, never numeric truthiness")
        if a is None or b is None:
            excluded.append(instance_id)
        else:
            observed.append((instance_id, a, b))
    both = sum(a and b for _, a, b in observed)
    only_a = sum(a and not b for _, a, b in observed)
    only_b = sum(not a and b for _, a, b in observed)
    neither = sum(not a and not b for _, a, b in observed)
    n = len(observed)
    difference, interval = None, None
    if n:
        deltas = [int(b) - int(a) for _, a, b in observed]
        difference = sum(deltas) / n
        generator = random.Random(bootstrap_seed)
        draws = sorted(sum(generator.choices(deltas, k=n)) / n for _ in range(n_bootstrap))
        interval = [_percentile(draws, 0.025), _percentile(draws, 0.975)]
    return {
        "input_n": len(pairs), "paired_n": n,
        "included_instance_ids": [instance_id for instance_id, _, _ in observed],
        "excluded_instance_ids": excluded,
        "four_cells": {"both_success": both, "only_A_success": only_a,
                       "only_B_success": only_b, "both_failure": neither},
        "A_success_rate": proportion(both + only_a, n),
        "B_success_rate": proportion(both + only_b, n),
        "B_minus_A": difference, "B_minus_A_ci95": interval,
        "ci_method": "paired task-level percentile bootstrap; linear quantiles",
        "bootstrap_seed": bootstrap_seed, "bootstrap_replicates": n_bootstrap,
        "mcnemar": exact_mcnemar(only_a, only_b) if n else None,
    }
