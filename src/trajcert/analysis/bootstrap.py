from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from trajcert.analysis.vectors import validated_finite_vector
from trajcert.determinism import bootstrap_namespace, generator_for
from trajcert.exceptions import InvalidScientificDataError
from trajcert.types import (
    ConfidenceLevel,
    DomainModel,
    FailureMessage,
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
    values = validated_finite_vector(
        differences,
        FailureMessage("paired statistics require a nonempty one-dimensional vector"),
        FailureMessage("paired statistics forbid NaN and infinity"),
    )
    namespace = bootstrap_namespace(semantic_comparison_key)
    rng = generator_for(namespace, 0)
    pair_count = values.size
    bootstrap_means = np.empty(resample_count, dtype=np.float64)
    for index in range(resample_count):
        sampled: NDArray[np.int64] = rng.integers(0, pair_count, size=pair_count)
        bootstrap_means[index] = np.mean(values[sampled], dtype=np.float64)
    bootstrap_means.sort()
    alpha = 1.0 - confidence_level
    return PercentileBootstrapInterval(
        estimate=float(np.mean(values, dtype=np.float64)),
        lower=linear_quantile(bootstrap_means, alpha / 2.0),
        upper=linear_quantile(bootstrap_means, 1.0 - alpha / 2.0),
        confidence_level=confidence_level,
        resample_count=resample_count,
    )


def linear_quantile(sorted_values: Vector, probability: Probability) -> PairedDifferenceValue:
    values = validated_finite_vector(
        sorted_values,
        FailureMessage("paired statistics require a nonempty one-dimensional vector"),
        FailureMessage("paired statistics forbid NaN and infinity"),
    )
    if np.any(values[:-1] > values[1:]):
        raise InvalidScientificDataError("linear quantile requires sorted values")
    return float(np.quantile(values, probability, method="linear"))
