from __future__ import annotations

from math import ceil, floor

import numpy as np
from numpy.typing import NDArray

from trajcert.determinism import bootstrap_namespace, generator_for
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    ConfidenceLevel,
    DomainModel,
    PairedDifferenceValue,
    Probability,
    ResampleCount,
    SemanticComparisonKey,
    Vector,
)


class PercentileBootstrapInterval(DomainModel):
    estimate: PairedDifferenceValue
    lower: PairedDifferenceValue
    upper: PairedDifferenceValue
    confidence_level: ConfidenceLevel
    resample_count: ResampleCount


def paired_percentile_bootstrap(
    differences: Vector,
    semantic_comparison_key: SemanticComparisonKey,
    resample_count: ResampleCount,
    confidence_level: ConfidenceLevel,
) -> PercentileBootstrapInterval:
    values = _validated_vector(differences)
    namespace = bootstrap_namespace(semantic_comparison_key)
    rng = generator_for(namespace, 0)
    pair_count = values.size
    bootstrap_means = np.empty(int(resample_count), dtype=np.float64)
    for index in range(int(resample_count)):
        sampled: NDArray[np.int64] = rng.integers(0, pair_count, size=pair_count)
        bootstrap_means[index] = float(np.mean(values[sampled], dtype=np.float64))
    bootstrap_means.sort()
    alpha = 1.0 - float(confidence_level)
    return PercentileBootstrapInterval(
        estimate=float(np.mean(values, dtype=np.float64)),
        lower=linear_quantile(bootstrap_means, alpha / 2.0),
        upper=linear_quantile(bootstrap_means, 1.0 - alpha / 2.0),
        confidence_level=confidence_level,
        resample_count=resample_count,
    )


def linear_quantile(sorted_values: Vector, probability: Probability) -> PairedDifferenceValue:
    values = _validated_vector(sorted_values)
    if np.any(values[:-1] > values[1:]):
        raise InvalidScientificDataError("linear quantile requires sorted values")
    position = (values.size - 1) * float(probability)
    lower_index = floor(position)
    upper_index = ceil(position)
    lower_value = values.item(lower_index)
    if lower_index == upper_index:
        return lower_value
    upper_value = values.item(upper_index)
    weight = position - lower_index
    return lower_value + weight * (upper_value - lower_value)


def _validated_vector(values: Vector) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise InvalidScientificDataError(
            "paired statistics require a nonempty one-dimensional vector"
        )
    if not np.all(np.isfinite(array)):
        raise InvalidScientificDataError("paired statistics forbid NaN and infinity")
    return array
