from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from trajcert.determinism import generator_for, permutation_namespace
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    DomainModel,
    FiniteFloat,
    NonNegativeInt,
    PositiveInt,
    Probability,
    SemanticComparisonKey,
    Vector,
)


class SignFlipResult(DomainModel):
    observed_statistic: FiniteFloat
    favorable_or_more_extreme_count: NonNegativeInt
    randomization_count: PositiveInt
    p_value: Probability


def one_sided_sign_flip(
    differences: Vector,
    semantic_comparison_key: SemanticComparisonKey,
    randomization_count: PositiveInt,
) -> SignFlipResult:
    values = _validated_vector(differences)
    observed = float(np.mean(values, dtype=np.float64))
    rng = generator_for(permutation_namespace(semantic_comparison_key), 0)
    favorable_or_more_extreme = 0
    for _ in range(int(randomization_count)):
        signs: NDArray[np.int8] = rng.integers(0, 2, size=values.size, dtype=np.int8)
        signed: NDArray[np.float64] = np.where(signs == 0, -values, values)
        statistic = float(np.mean(signed, dtype=np.float64))
        favorable_or_more_extreme += int(statistic >= observed)
    p_value = (1.0 + favorable_or_more_extreme) / (1.0 + int(randomization_count))
    return SignFlipResult(
        observed_statistic=observed,
        favorable_or_more_extreme_count=favorable_or_more_extreme,
        randomization_count=randomization_count,
        p_value=p_value,
    )


def _validated_vector(values: Vector) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise InvalidScientificDataError("sign-flip inference requires a nonempty vector")
    if not np.all(np.isfinite(array)):
        raise InvalidScientificDataError("sign-flip inference forbids NaN and infinity")
    return array
