from __future__ import annotations

from math import exp, inf, log, log1p
from typing import Self

from pydantic import model_validator
from scipy.special import betaln, gammaln

from trajcert.config import active_config
from trajcert.exceptions import (
    ConfidenceSequenceViolationError,
    InvalidScientificDataError,
    NumericalError,
)
from trajcert.inference.categorical import CategoricalState
from trajcert.math.entropy import xlogx
from trajcert.types import (
    AnytimeConfidenceDelta,
    Count,
    DomainModel,
    LogMixtureRatio,
    Probability,
    SequenceConstruction,
    Threshold,
    ToleranceValue,
)


class ClosedProbabilityInterval(DomainModel):
    lower: Probability
    upper: Probability

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.lower > self.upper:
            raise NumericalError("confidence interval lower endpoint exceeds upper endpoint")
        return self


class CategoricalConfidenceRegion(DomainModel):
    matured_count: Count
    intervals: tuple[ClosedProbabilityInterval, ...]

    @model_validator(mode="after")
    def validate_simplex_intersection(self) -> Self:
        if not self.intervals:
            raise NumericalError("categorical confidence region cannot be empty")
        lower_sum = sum(interval.lower for interval in self.intervals)
        upper_sum = sum(interval.upper for interval in self.intervals)
        if lower_sum > 1.0 or upper_sum < 1.0:
            raise NumericalError("categorical confidence rectangle has empty simplex intersection")
        return self


class ConfidenceSequenceUpdate(DomainModel):
    raw: CategoricalConfidenceRegion
    running: CategoricalConfidenceRegion


def raw_confidence_region(
    state: CategoricalState,
    anytime_delta: AnytimeConfidenceDelta,
    root_tolerance: ToleranceValue,
) -> CategoricalConfidenceRegion:
    delta = anytime_delta
    if delta <= 0.0 or delta >= 1.0:
        raise InvalidScientificDataError("anytime delta must lie strictly between zero and one")
    counts = tuple(state.canonical_count_vector)
    total = state.matured_count
    threshold, beta_terms = _sequence_constants(counts, total, delta)
    intervals = tuple(
        _invert_category_count(count, total, threshold, root_tolerance, beta_term)
        for count, beta_term in zip(counts, beta_terms, strict=True)
    )
    return CategoricalConfidenceRegion(matured_count=total, intervals=intervals)


def _sequence_constants(
    counts: tuple[Count, ...], total: Count, delta: AnytimeConfidenceDelta
) -> tuple[Threshold, tuple[LogMixtureRatio, ...]]:
    construction = active_config.get().confidence.sequence.construction
    if construction is SequenceConstruction.DIRICHLET_JOINT:
        return _joint_sequence_constants(counts, total, delta)
    return (
        log(len(counts) / delta),
        tuple(_mixture_beta_term(count, total) for count in counts),
    )


def _joint_sequence_constants(
    counts: tuple[Count, ...], total: Count, delta: AnytimeConfidenceDelta
) -> tuple[Threshold, tuple[LogMixtureRatio, ...]]:
    shape = active_config.get().confidence.sequence.joint_shape
    concentration = shape * len(counts)
    log_evidence = gammaln(concentration) - gammaln(total + concentration)
    log_evidence += sum(gammaln(count + shape) - gammaln(shape) for count in counts)
    terms: list[LogMixtureRatio] = []
    for index, count in enumerate(counts):
        remainder = total - count
        rest = sum(xlogx(other) for position, other in enumerate(counts) if position != index)
        tail = 0.0 if remainder == 0 else remainder * log(remainder)
        terms.append(log_evidence - rest + tail)
    return -log(delta), tuple(terms)


def confidence_sequence_update(
    state: CategoricalState,
    anytime_delta: AnytimeConfidenceDelta,
    root_tolerance: ToleranceValue,
    previous_running: CategoricalConfidenceRegion | None,
) -> ConfidenceSequenceUpdate:
    raw = raw_confidence_region(state, anytime_delta, root_tolerance)
    if previous_running is None:
        return ConfidenceSequenceUpdate(raw=raw, running=raw)
    if len(previous_running.intervals) != len(raw.intervals):
        raise NumericalError("running confidence region category dimension changed")
    intervals = tuple(
        _intersect_running(previous, current)
        for previous, current in zip(previous_running.intervals, raw.intervals, strict=True)
    )
    running = CategoricalConfidenceRegion(matured_count=state.matured_count, intervals=intervals)
    return ConfidenceSequenceUpdate(raw=raw, running=running)


def _intersect_running(
    previous: ClosedProbabilityInterval, current: ClosedProbabilityInterval
) -> ClosedProbabilityInterval:
    lower = max(previous.lower, current.lower)
    upper = min(previous.upper, current.upper)
    if lower > upper:
        raise ConfidenceSequenceViolationError(
            "running confidence region intersection is empty at this prefix"
        )
    return ClosedProbabilityInterval(lower=lower, upper=upper)


def _invert_category_count(
    successes: Count,
    matured_count: Count,
    threshold: Threshold,
    root_tolerance: ToleranceValue,
    beta_term: LogMixtureRatio,
) -> ClosedProbabilityInterval:
    success_count = successes
    total = matured_count
    if success_count < 0 or success_count > total:
        raise InvalidScientificDataError("categorical success count is outside [0, n]")
    if total == 0:
        return ClosedProbabilityInterval(lower=0.0, upper=1.0)
    maximum_likelihood = success_count / total
    lower = 0.0
    if success_count > 0:
        lower = _lower_root(
            success_count, total, maximum_likelihood, threshold, root_tolerance, beta_term
        )
    upper = 1.0
    if success_count < total:
        upper = _upper_root(
            success_count, total, maximum_likelihood, threshold, root_tolerance, beta_term
        )
    return ClosedProbabilityInterval(lower=lower, upper=upper)


def _lower_root(
    successes: Count,
    total: Count,
    maximum_likelihood: Probability,
    threshold: Threshold,
    root_tolerance: ToleranceValue,
    beta_term: LogMixtureRatio,
) -> Probability:
    lower = 0.0
    upper = maximum_likelihood
    if _root_function(successes, total, lower, threshold, beta_term) <= 0.0:
        return 0.0
    if _root_function(successes, total, upper, threshold, beta_term) > 0.0:
        raise NumericalError("lower confidence root is not sign-bracketed")
    while upper - lower > root_tolerance:
        midpoint = (lower + upper) / 2.0
        if _root_function(successes, total, midpoint, threshold, beta_term) > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return lower


def _upper_root(
    successes: Count,
    total: Count,
    maximum_likelihood: Probability,
    threshold: Threshold,
    root_tolerance: ToleranceValue,
    beta_term: LogMixtureRatio,
) -> Probability:
    lower = maximum_likelihood
    upper = 1.0
    if _root_function(successes, total, upper, threshold, beta_term) <= 0.0:
        return 1.0
    if _root_function(successes, total, lower, threshold, beta_term) > 0.0:
        raise NumericalError("upper confidence root is not sign-bracketed")
    while upper - lower > root_tolerance:
        midpoint = (lower + upper) / 2.0
        if _root_function(successes, total, midpoint, threshold, beta_term) <= 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return upper


def _mixture_beta_term(successes: Count, total: Count) -> LogMixtureRatio:
    failures = total - successes
    sequence = active_config.get().confidence.sequence
    terms = tuple(
        log(weight) + betaln(successes + shape, failures + spread) - betaln(shape, spread)
        for (shape, spread), weight in zip(sequence.components, sequence.weights, strict=True)
    )
    peak = max(terms)
    return peak + log(sum(exp(term - peak) for term in terms))


def _root_function(
    successes: Count,
    total: Count,
    probability: Probability,
    threshold: Threshold,
    beta_term: LogMixtureRatio,
) -> LogMixtureRatio:
    return _log_mixture_likelihood_ratio(successes, total, probability, beta_term) - threshold


def _log_mixture_likelihood_ratio(
    successes: Count, total: Count, probability: Probability, beta_term: LogMixtureRatio
) -> LogMixtureRatio:
    failures = total - successes
    if probability <= 0.0:
        return beta_term if successes == 0 else inf
    if probability >= 1.0:
        return beta_term if failures == 0 else inf
    return beta_term - successes * log(probability) - failures * log1p(-probability)
