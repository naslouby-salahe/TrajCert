from __future__ import annotations

from math import inf, log, log1p
from typing import Self

from pydantic import model_validator
from scipy.special import betaln

from trajcert.exceptions import InvalidScientificDataError, NumericalError
from trajcert.inference.categorical import CategoricalState
from trajcert.types import (
    AnytimeConfidenceDelta,
    Count,
    DomainModel,
    LogMixtureRatio,
    Probability,
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
    counts = state.canonical_count_vector
    category_count = len(counts)
    threshold = log(category_count / delta)
    intervals = tuple(
        _invert_category_count(count, state.matured_count, threshold, root_tolerance)
        for count in counts
    )
    return CategoricalConfidenceRegion(matured_count=state.matured_count, intervals=intervals)


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
        ClosedProbabilityInterval(
            lower=max(previous.lower, current.lower),
            upper=min(previous.upper, current.upper),
        )
        for previous, current in zip(previous_running.intervals, raw.intervals, strict=True)
    )
    running = CategoricalConfidenceRegion(matured_count=state.matured_count, intervals=intervals)
    return ConfidenceSequenceUpdate(raw=raw, running=running)


def _invert_category_count(
    successes: Count,
    matured_count: Count,
    threshold: Threshold,
    root_tolerance: ToleranceValue,
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
        lower = _lower_root(success_count, total, maximum_likelihood, threshold, root_tolerance)
    upper = 1.0
    if success_count < total:
        upper = _upper_root(success_count, total, maximum_likelihood, threshold, root_tolerance)
    return ClosedProbabilityInterval(lower=lower, upper=upper)


def _lower_root(
    successes: Count,
    total: Count,
    maximum_likelihood: Probability,
    threshold: Threshold,
    root_tolerance: ToleranceValue,
) -> Probability:
    lower = 0.0
    upper = maximum_likelihood
    if _root_function(successes, total, lower, threshold) <= 0.0:
        return 0.0
    if _root_function(successes, total, upper, threshold) > 0.0:
        raise NumericalError("lower confidence root is not sign-bracketed")
    while upper - lower > root_tolerance:
        midpoint = (lower + upper) / 2.0
        if _root_function(successes, total, midpoint, threshold) > 0.0:
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
) -> Probability:
    lower = maximum_likelihood
    upper = 1.0
    if _root_function(successes, total, upper, threshold) <= 0.0:
        return 1.0
    if _root_function(successes, total, lower, threshold) > 0.0:
        raise NumericalError("upper confidence root is not sign-bracketed")
    while upper - lower > root_tolerance:
        midpoint = (lower + upper) / 2.0
        if _root_function(successes, total, midpoint, threshold) <= 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return upper


def _root_function(
    successes: Count, total: Count, probability: Probability, threshold: Threshold
) -> LogMixtureRatio:
    return _log_mixture_likelihood_ratio(successes, total, probability) - threshold


def _log_mixture_likelihood_ratio(
    successes: Count, total: Count, probability: Probability
) -> LogMixtureRatio:
    failures = total - successes
    beta_term = betaln(successes + 0.5, failures + 0.5) - betaln(0.5, 0.5)
    if probability == 0.0:
        return beta_term if successes == 0 else inf
    if probability == 1.0:
        return beta_term if failures == 0 else inf
    return beta_term - successes * log(probability) - failures * log1p(-probability)
