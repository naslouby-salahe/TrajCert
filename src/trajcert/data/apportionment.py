from __future__ import annotations

import math

from trajcert.data.partitions import ObservableLaw

type SyntheticCategory = tuple[int, bool] | None


def canonical_synthetic_category_order(resolved_band_count: int) -> tuple[SyntheticCategory, ...]:
    if resolved_band_count < 1:
        raise ValueError("synthetic category order requires a positive resolved-band count")
    return (
        *(
            category
            for band in range(1, resolved_band_count + 1)
            for category in ((band, True), (band, False))
        ),
        None,
    )


def synthetic_category_probabilities(observable_law: ObservableLaw) -> tuple[float, ...]:
    return (
        *(
            probability
            for harmful, correct in zip(
                observable_law.harmful_masses,
                observable_law.correct_masses,
                strict=True,
            )
            for probability in (harmful, correct)
        ),
        observable_law.unresolved_mass,
    )


def synthetic_hamilton_apportionment(total: int, observable_law: ObservableLaw) -> tuple[int, ...]:
    return hamilton_apportionment(total, synthetic_category_probabilities(observable_law))


def hamilton_apportionment(total: int, probabilities: tuple[float, ...]) -> tuple[int, ...]:
    if total < 0:
        raise ValueError("apportionment total must be nonnegative")
    if not probabilities or any(not math.isfinite(value) or value < 0 for value in probabilities):
        raise ValueError("apportionment probabilities must be finite nonnegative values")
    if math.fsum(probabilities) != 1.0:
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
