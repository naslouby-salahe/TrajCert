from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from trajcert.analysis.vectors import validated_finite_vector
from trajcert.determinism import generator_for, permutation_namespace
from trajcert.types import (
    DomainModel,
    FavorableCount,
    ObservedStatistic,
    Probability,
    RandomizationCount,
    SemanticComparisonKey,
    Vector,
)


class SignFlipResult(DomainModel):
    observed_statistic: ObservedStatistic
    favorable_or_more_extreme_count: FavorableCount
    randomization_count: RandomizationCount
    p_value: Probability


def one_sided_sign_flip(
    differences: Vector,
    semantic_comparison_key: SemanticComparisonKey,
    randomization_count: RandomizationCount,
) -> SignFlipResult:
    values = validated_finite_vector(
        differences,
        "sign-flip inference requires a nonempty vector",
        "sign-flip inference forbids NaN and infinity",
    )
    observed = float(np.mean(values, dtype=np.float64))
    rng = generator_for(permutation_namespace(semantic_comparison_key), 0)
    favorable_or_more_extreme = 0
    for _ in range(randomization_count):
        bits: NDArray[np.int8] = rng.integers(0, 2, size=values.size, dtype=np.int8)
        multipliers: NDArray[np.float64] = bits.astype(np.float64)
        multipliers *= 2.0
        multipliers -= 1.0
        signed: NDArray[np.float64] = values * multipliers
        statistic = float(np.mean(signed, dtype=np.float64))
        favorable_or_more_extreme += (statistic >= observed)
    p_value = (1.0 + favorable_or_more_extreme) / (1.0 + randomization_count)
    return SignFlipResult(
        observed_statistic=observed,
        favorable_or_more_extreme_count=favorable_or_more_extreme,
        randomization_count=randomization_count,
        p_value=p_value,
    )
