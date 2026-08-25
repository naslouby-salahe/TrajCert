from __future__ import annotations

import math
from typing import NewType

from trajcert.data.partitions import ObservableLaw
from trajcert.domain.seeds import ResolvedBandCount

type SyntheticCategory = tuple[int, bool] | None
ApportionmentTotal = NewType("ApportionmentTotal", int)
SyntheticCategoryProbabilities = NewType("SyntheticCategoryProbabilities", tuple[float, ...])
ApportionedCategoryCounts = NewType("ApportionedCategoryCounts", tuple[int, ...])


def canonical_synthetic_category_order(
    resolved_band_count: ResolvedBandCount,
) -> tuple[SyntheticCategory, ...]:
    return (
        *(
            category
            for band in range(1, resolved_band_count.value + 1)
            for category in ((band, True), (band, False))
        ),
        None,
    )


def synthetic_category_probabilities(
    observable_law: ObservableLaw,
) -> SyntheticCategoryProbabilities:
    return SyntheticCategoryProbabilities(
        (
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
    )


def synthetic_hamilton_apportionment(
    total: ApportionmentTotal,
    observable_law: ObservableLaw,
) -> ApportionedCategoryCounts:
    return hamilton_apportionment(total, synthetic_category_probabilities(observable_law))


def hamilton_apportionment(
    total: ApportionmentTotal,
    probabilities: SyntheticCategoryProbabilities,
) -> ApportionedCategoryCounts:
    if total < 0:
        raise ValueError("apportionment total must be nonnegative")
    if not probabilities or any(not math.isfinite(value) or value < 0 for value in probabilities):
        raise ValueError("apportionment probabilities must be finite nonnegative values")
    probability_total = math.fsum(probabilities)
    if not math.isclose(
        probability_total,
        1.0,
        rel_tol=0.0,
        abs_tol=math.ulp(1.0) * len(probabilities),
    ):
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
    return ApportionedCategoryCounts(tuple(counts))
