from __future__ import annotations

from math import sqrt

from scipy.stats import norm

from trajcert.inference.categorical import CategoricalState
from trajcert.inference.confidence import CategoricalConfidenceRegion, ClosedProbabilityInterval
from trajcert.inference.envelope import summary_envelope_from_confidence
from trajcert.inference.projection import ProjectionResult, project_upper_risk
from trajcert.types import (
    AnytimeConfidenceDelta,
    ArbitraryPrecisionBits,
    Count,
    FiniteFloat,
    OuterMaxNodes,
    SensitivityBudget,
    ToleranceValue,
)


def repeated_static_region(
    state: CategoricalState,
    anytime_delta: AnytimeConfidenceDelta,
) -> CategoricalConfidenceRegion:
    total = state.matured_count
    dimension = len(state.canonical_count_vector)
    if total == 0:
        intervals = tuple(ClosedProbabilityInterval(lower=0.0, upper=1.0) for _ in range(dimension))
        return CategoricalConfidenceRegion(matured_count=0, intervals=intervals)
    delta = anytime_delta
    z = float(norm.ppf(1.0 - delta / (2.0 * dimension)))
    intervals = tuple(
        _wilson_interval(count, total, z) for count in state.canonical_count_vector
    )
    return CategoricalConfidenceRegion(matured_count=state.matured_count, intervals=intervals)


def repeated_static_projection(
    state: CategoricalState,
    anytime_delta: AnytimeConfidenceDelta,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
    arbitrary_precision_bits: ArbitraryPrecisionBits,
    outer_gap: ToleranceValue,
    outer_max_nodes: OuterMaxNodes,
) -> ProjectionResult:
    region = repeated_static_region(state, anytime_delta)
    envelope = summary_envelope_from_confidence(state.partition, region)
    return project_upper_risk(
        envelope=envelope,
        sensitivity_budget=sensitivity_budget,
        root_atol=root_atol,
        identity_atol=identity_atol,
        comparison_guard=comparison_guard,
        arbitrary_precision_bits=arbitrary_precision_bits,
        outer_gap=outer_gap,
        outer_max_nodes=outer_max_nodes,
    )


def _wilson_interval(successes: Count, total: Count, z: FiniteFloat) -> ClosedProbabilityInterval:
    proportion = successes / total
    z_squared = z * z
    denominator = 1.0 + z_squared / total
    center = (proportion + z_squared / (2.0 * total)) / denominator
    half = (
        z
        / denominator
        * sqrt(proportion * (1.0 - proportion) / total + z_squared / (4.0 * total * total))
    )
    return ClosedProbabilityInterval(
        lower=max(0.0, center - half),
        upper=min(1.0, center + half),
    )
