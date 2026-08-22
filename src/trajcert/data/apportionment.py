from __future__ import annotations

import math


def hamilton_apportionment(total: int, probabilities: tuple[float, ...]) -> tuple[int, ...]:
    if total < 0:
        raise ValueError("apportionment total must be nonnegative")
    if not probabilities or any(not math.isfinite(value) or value < 0 for value in probabilities):
        raise ValueError("apportionment probabilities must be finite nonnegative values")
    if not math.isclose(sum(probabilities), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("apportionment probabilities must sum to one")
    quotas = tuple(total * probability for probability in probabilities)
    floors = tuple(math.floor(quota) for quota in quotas)
    remaining = total - sum(floors)
    ranked = sorted(
        range(len(probabilities)),
        key=lambda index: (-(quotas[index] - floors[index]), index),
    )
    counts = list(floors)
    for index in ranked[:remaining]:
        counts[index] += 1
    return tuple(counts)
