from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from statistics import NormalDist

from trajcert.configuration.models import ConfidenceConfiguration, NumericsConfiguration
from trajcert.inference.confidence_sequence import ProbabilityInterval
from trajcert.inference.envelope import (
    ConservativeSummaryEnvelope,
    SummaryEnvelopeInput,
    conservative_summary_envelope,
)
from trajcert.inference.projection import (
    CertifiedProjectionResult,
    ProjectionInput,
    certified_outer_projection,
)


class SequentialReferenceMethod(StrEnum):
    TRAJCERT = "TrajCert"
    TIME_UNIFORM_OBSERVABLE_LAW_PROJECTION = "Time-uniform observable-law projection"
    REPEATED_STATIC_MONITORING_NEGATIVE_CONTROL = "Repeated-static-monitoring negative control"
    IGNORABLE_DELAY_ANYTIME_REFERENCE = "Ignorable-delay anytime reference"


class ReferenceApplicability(StrEnum):
    VALID = "VALID"
    ASSUMPTION_VIOLATED = "ASSUMPTION_VIOLATED"
    NEGATIVE_CONTROL = "NEGATIVE_CONTROL"


class SequentialAblation(StrEnum):
    ENDPOINT_ONLY_PATH_INFORMATION = "Endpoint-only path information"
    SAME_ENDPOINT_DIFFERENT_TIMING = "Same Endpoint, Different Timing"
    RHO_LOG_TWO = "rho = log(2)"


@dataclass(frozen=True, slots=True)
class CategoryCountVector:
    values: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.values or any(value < 0 for value in self.values):
            raise ValueError("category counts must be nonempty and nonnegative")

    @property
    def matured_events(self) -> int:
        return sum(self.values)


@dataclass(frozen=True, slots=True)
class TimeUniformProjectionInput:
    envelope: ConservativeSummaryEnvelope
    information_budget: float
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class TimeUniformProjectionReference:
    method: SequentialReferenceMethod
    projection: CertifiedProjectionResult
    valid_for_deployment: bool


@dataclass(frozen=True, slots=True)
class StaticMonitoringInput:
    finite_band_count: int
    category_counts: CategoryCountVector
    confidence: ConfidenceConfiguration
    information_budget: float
    numerics: NumericsConfiguration


@dataclass(frozen=True, slots=True)
class StaticMonitoringReference:
    method: SequentialReferenceMethod
    category_intervals: tuple[ProbabilityInterval, ...]
    projection: CertifiedProjectionResult
    applicability: ReferenceApplicability
    valid_for_deployment: bool


@dataclass(frozen=True, slots=True)
class IgnorableDelayInput:
    resolved_harmful_count: int
    resolved_correct_count: int
    previous_interval: ProbabilityInterval | None
    independence_holds: bool
    confidence: ConfidenceConfiguration
    numerics: NumericsConfiguration
    evidence_gate_passed: bool


@dataclass(frozen=True, slots=True)
class IgnorableDelayReference:
    method: SequentialReferenceMethod
    risk_upper: float | None
    resolved_count: int
    interval: ProbabilityInterval | None
    applicability: ReferenceApplicability
    evidence_gate_passed: bool


@dataclass(frozen=True, slots=True)
class AblationDefinition:
    ablation: SequentialAblation
    information_budget: float | None


def time_uniform_observable_law_projection(
    input_value: TimeUniformProjectionInput,
) -> TimeUniformProjectionReference:
    projection = certified_outer_projection(
        ProjectionInput(
            input_value.envelope,
            input_value.information_budget,
            input_value.numerics,
        )
    )
    return TimeUniformProjectionReference(
        SequentialReferenceMethod.TIME_UNIFORM_OBSERVABLE_LAW_PROJECTION,
        projection,
        True,
    )


def trajcert_reference(projection: CertifiedProjectionResult) -> TimeUniformProjectionReference:
    return TimeUniformProjectionReference(SequentialReferenceMethod.TRAJCERT, projection, True)


def repeated_static_monitoring_negative_control(
    input_value: StaticMonitoringInput,
) -> StaticMonitoringReference:
    expected_categories = 2 * input_value.finite_band_count + 1
    if (
        input_value.finite_band_count < 1
        or len(input_value.category_counts.values) != expected_categories
    ):
        raise ValueError("static-monitoring category dimensions are invalid")
    intervals = tuple(
        _wilson_interval(
            count,
            input_value.category_counts.matured_events,
            len(input_value.category_counts.values),
            input_value.confidence.anytime_delta,
        )
        for count in input_value.category_counts.values
    )
    envelope = conservative_summary_envelope(
        SummaryEnvelopeInput(input_value.finite_band_count, intervals)
    )
    projection = certified_outer_projection(
        ProjectionInput(envelope, input_value.information_budget, input_value.numerics)
    )
    return StaticMonitoringReference(
        SequentialReferenceMethod.REPEATED_STATIC_MONITORING_NEGATIVE_CONTROL,
        intervals,
        projection,
        ReferenceApplicability.NEGATIVE_CONTROL,
        False,
    )


def ignorable_delay_anytime_reference(input_value: IgnorableDelayInput) -> IgnorableDelayReference:
    if input_value.resolved_harmful_count < 0 or input_value.resolved_correct_count < 0:
        raise ValueError("resolved outcome counts must be nonnegative")
    resolved_count = input_value.resolved_harmful_count + input_value.resolved_correct_count
    if not input_value.independence_holds:
        return IgnorableDelayReference(
            SequentialReferenceMethod.IGNORABLE_DELAY_ANYTIME_REFERENCE,
            None,
            resolved_count,
            None,
            ReferenceApplicability.ASSUMPTION_VIOLATED,
            input_value.evidence_gate_passed,
        )
    interval = (
        input_value.previous_interval
        if resolved_count == 0
        else _jeffreys_interval(
            input_value.resolved_harmful_count,
            resolved_count,
            input_value.confidence.anytime_delta,
            input_value.numerics,
        )
    )
    return IgnorableDelayReference(
        SequentialReferenceMethod.IGNORABLE_DELAY_ANYTIME_REFERENCE,
        None if interval is None else interval.upper,
        resolved_count,
        interval,
        ReferenceApplicability.VALID,
        input_value.evidence_gate_passed,
    )


def declared_ablations() -> tuple[AblationDefinition, ...]:
    return (
        AblationDefinition(SequentialAblation.ENDPOINT_ONLY_PATH_INFORMATION, None),
        AblationDefinition(SequentialAblation.SAME_ENDPOINT_DIFFERENT_TIMING, None),
        AblationDefinition(SequentialAblation.RHO_LOG_TWO, math.log(2)),
    )


def _wilson_interval(count: int, total: int, dimensions: int, delta: float) -> ProbabilityInterval:
    if total <= 0 or dimensions <= 0 or not 0 < delta < 1:
        raise ValueError("Wilson inputs are invalid")
    estimate = count / total
    z = NormalDist().inv_cdf(1 - delta / (2 * dimensions))
    denominator = 1 + z**2 / total
    center = (estimate + z**2 / (2 * total)) / denominator
    half = z / denominator * math.sqrt(estimate * (1 - estimate) / total + z**2 / (4 * total**2))
    return ProbabilityInterval(max(0, center - half), min(1, center + half), None, None)


def _jeffreys_interval(
    harmful_count: int,
    resolved_count: int,
    delta: float,
    numerics: NumericsConfiguration,
) -> ProbabilityInterval:
    estimate = harmful_count / resolved_count
    threshold = math.log(1 / delta)

    def objective(probability: float) -> float:
        return _binary_log_mixture(harmful_count, resolved_count, probability) - threshold

    lower = 0 if objective(0) <= 0 else _lower_root(objective, 0, estimate, numerics)
    upper = 1 if objective(1) <= 0 else _upper_root(objective, estimate, 1, numerics)
    return ProbabilityInterval(lower, upper, None, None)


def _binary_log_mixture(harmful_count: int, resolved_count: int, probability: float) -> float:
    beta_difference = (
        math.lgamma(harmful_count + 0.5)
        + math.lgamma(resolved_count - harmful_count + 0.5)
        - math.lgamma(resolved_count + 1)
        - (2 * math.lgamma(0.5) - math.lgamma(1))
    )
    if probability == 0:
        return beta_difference if harmful_count == 0 else math.inf
    if probability == 1:
        return beta_difference if harmful_count == resolved_count else math.inf
    return (
        beta_difference
        - harmful_count * math.log(probability)
        - (resolved_count - harmful_count) * math.log1p(-probability)
    )


def _lower_root(
    objective: Callable[[float], float], lower: float, upper: float, numerics: NumericsConfiguration
) -> float:
    left = lower
    right = upper
    while right - left > numerics.anytime_category_root_tolerance:
        midpoint = (left + right) / 2
        if objective(midpoint) <= 0:
            right = midpoint
        else:
            left = midpoint
    return right


def _upper_root(
    objective: Callable[[float], float], lower: float, upper: float, numerics: NumericsConfiguration
) -> float:
    left = lower
    right = upper
    while right - left > numerics.anytime_category_root_tolerance:
        midpoint = (left + right) / 2
        if objective(midpoint) <= 0:
            left = midpoint
        else:
            right = midpoint
    return left
