from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from math import isfinite, ldexp, log, log1p, sqrt
from sys import float_info
from typing import Self

from flint import arb, ctx
from pydantic import model_validator

from trajcert.config import active_config
from trajcert.exceptions import (
    ConfidenceSequenceViolationError,
    InvalidScientificDataError,
    NumericalError,
)
from trajcert.inference.categorical import CategoricalState
from trajcert.math.enclosure import ball_lower, ball_upper, sum_lower, sum_upper
from trajcert.types import (
    AnytimeConfidenceDelta,
    ArbEndpointValue,
    ArbitraryPrecisionBits,
    Count,
    DomainModel,
    InformationResidual,
    Probability,
    SearchPredicate,
    ToleranceValue,
)


class ClosedProbabilityInterval(DomainModel):
    lower: Probability
    upper: Probability

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if not 0.0 <= self.lower <= self.upper <= 1.0:
            raise NumericalError("confidence interval lower endpoint exceeds upper endpoint")
        return self


class CategoricalConfidenceRegion(DomainModel):
    matured_count: Count
    intervals: tuple[ClosedProbabilityInterval, ...]

    @model_validator(mode="after")
    def validate_simplex_intersection(self) -> Self:
        if not self.intervals:
            raise NumericalError("categorical confidence region cannot be empty")
        lower_sum = sum_lower(interval.lower for interval in self.intervals)
        upper_sum = sum_upper(interval.upper for interval in self.intervals)
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
    if not 0.0 < delta < 1.0:
        raise InvalidScientificDataError("anytime delta must lie strictly between zero and one")
    if not isfinite(root_tolerance) or root_tolerance <= 0.0:
        raise InvalidScientificDataError("root tolerance must be finite and positive")
    counts = tuple(state.canonical_count_vector)
    total = state.matured_count
    with ctx.workprec(active_config.get().numerics.arbitrary_precision_bits):
        threshold = (arb(len(counts)) / arb(delta)).log()
        beta_terms = tuple(_jeffreys_beta_ball(count, total) for count in counts)
        intervals = tuple(
            _invert_category_count(count, total, threshold, root_tolerance, beta_term)
            for count, beta_term in zip(counts, beta_terms, strict=True)
        )
    return CategoricalConfidenceRegion(matured_count=total, intervals=intervals)


def confidence_sequence_excludes(
    state: CategoricalState,
    anytime_delta: AnytimeConfidenceDelta,
    probabilities: tuple[Probability, ...],
) -> bool:
    delta = anytime_delta
    if not 0.0 < delta < 1.0:
        raise InvalidScientificDataError("anytime delta must lie strictly between zero and one")
    counts = state.canonical_count_vector
    if len(probabilities) != len(counts):
        raise InvalidScientificDataError("probability vector must match the categorical state")
    if any(not 0.0 <= value <= 1.0 for value in probabilities):
        raise InvalidScientificDataError("category probabilities must lie in [0, 1]")
    total = state.matured_count
    with ctx.workprec(active_config.get().numerics.arbitrary_precision_bits):
        threshold = (arb(len(counts)) / arb(delta)).log()
        return any(
            _category_excluded(count, total, probability, threshold)
            for count, probability in zip(counts, probabilities, strict=True)
        )


def _category_excluded(
    successes: Count, total: Count, probability: Probability, threshold: arb
) -> SearchPredicate:
    beta_term = _jeffreys_beta_ball(successes, total)
    bounds = _root_filter(threshold, beta_term)
    return _root_side(successes, total, probability, threshold, beta_term, bounds) is True


def _jeffreys_beta_ball(successes: Count, total: Count) -> arb:
    precision = ctx.prec
    return (
        _half_offset_lgamma(successes, precision)
        + _half_offset_lgamma(total - successes, precision)
        - _integer_lgamma(total + 1, precision)
        - 2 * _half_offset_lgamma(0, precision)
    )


@cache
def _half_offset_lgamma(count: Count, precision: ArbitraryPrecisionBits) -> arb:
    _ = precision
    return (arb(count) + arb(1) / 2).lgamma()


@cache
def _integer_lgamma(count: Count, precision: ArbitraryPrecisionBits) -> arb:
    _ = precision
    return arb(count).lgamma()


@dataclass(frozen=True, slots=True)
class _RootFilter:
    offset_low: ArbEndpointValue
    offset_high: ArbEndpointValue


def _root_filter(threshold: arb, beta_term: arb) -> _RootFilter:
    offset = beta_term - threshold
    return _RootFilter(offset_low=ball_lower(offset), offset_high=ball_upper(offset))


def _float_side(
    successes: Count, total: Count, probability: Probability, bounds: _RootFilter
) -> SearchPredicate | None:
    if not 0.0 < probability < 1.0:
        return None
    failures = total - successes
    likelihood = successes * log(probability) + failures * log1p(-probability)
    slack = (
        ldexp(float_info.epsilon, 10)
        * (abs(bounds.offset_low) + abs(bounds.offset_high) - likelihood)
        + bounds.offset_high
        - bounds.offset_low
    )
    if bounds.offset_low - likelihood > slack:
        return True
    if bounds.offset_high - likelihood < -slack:
        return False
    return None


def _root_side(
    successes: Count,
    total: Count,
    probability: Probability,
    threshold: arb,
    beta_term: arb,
    bounds: _RootFilter,
) -> SearchPredicate | None:
    side = _float_side(successes, total, probability, bounds)
    if side is not None:
        return side
    value = _root_ball(successes, total, probability, threshold, beta_term)
    if value > 0:
        return True
    if value <= 0:
        return False
    return None


@dataclass(frozen=True, slots=True)
class _RootBracket:
    below: Probability
    above: Probability
    positive_below: SearchPredicate


def _root_estimate(
    successes: Count,
    total: Count,
    negative_end: Probability,
    positive_end: Probability,
    bounds: _RootFilter,
) -> Probability:
    offset = (bounds.offset_low + bounds.offset_high) / 2.0
    failures = total - successes
    estimate = _quadratic_estimate(total, negative_end, positive_end, offset)
    resolution = ldexp(abs(positive_end - negative_end), -44)
    for _ in range(64):
        value = offset - successes * log(estimate) - failures * log1p(-estimate)
        if value > 0.0:
            positive_end = estimate
        else:
            negative_end = estimate
        slope = failures / (1.0 - estimate) - successes / estimate
        step = estimate - value / slope if slope != 0.0 else estimate
        inside = min(negative_end, positive_end) < step < max(negative_end, positive_end)
        candidate = step if inside else (negative_end + positive_end) / 2.0
        if abs(candidate - estimate) <= resolution:
            return candidate
        estimate = candidate
    return estimate


def _quadratic_estimate(
    total: Count, negative_end: Probability, positive_end: Probability, offset: InformationResidual
) -> Probability:
    midpoint = (negative_end + positive_end) / 2.0
    center = negative_end
    if not 0.0 < center < 1.0:
        return midpoint
    entropy = -center * log(center) - (1.0 - center) * log1p(-center)
    divergence = max(0.0, -offset / total - entropy)
    spread = sqrt(2.0 * divergence * center * (1.0 - center))
    guess = center + spread if positive_end > negative_end else center - spread
    inside = min(negative_end, positive_end) < guess < max(negative_end, positive_end)
    return guess if inside else midpoint


def _advance_outside_bracket(
    lower: Probability,
    upper: Probability,
    root_tolerance: ToleranceValue,
    bracket: _RootBracket | None,
) -> tuple[Probability, Probability]:
    if bracket is None:
        return lower, upper
    while upper - lower > root_tolerance:
        midpoint = (lower + upper) / 2.0
        if midpoint in (lower, upper) or bracket.below < midpoint < bracket.above:
            break
        if midpoint <= bracket.below:
            lower = midpoint
        else:
            upper = midpoint
    return lower, upper


def _verified_bracket(
    successes: Count,
    total: Count,
    estimate: Probability,
    positive_below: SearchPredicate,
    bounds: _RootFilter,
) -> _RootBracket | None:
    width = ldexp(estimate, -40)
    for _ in range(8):
        below = estimate - width
        above = estimate + width
        below_side = _float_side(successes, total, below, bounds)
        above_side = _float_side(successes, total, above, bounds)
        if below_side is positive_below and above_side is (not positive_below):
            return _RootBracket(below=below, above=above, positive_below=positive_below)
        width *= 16.0
    return None


def _bracketed_side(
    successes: Count,
    total: Count,
    probability: Probability,
    threshold: arb,
    beta_term: arb,
    bounds: _RootFilter,
    bracket: _RootBracket | None,
) -> SearchPredicate | None:
    if bracket is not None:
        if probability <= bracket.below:
            return bracket.positive_below
        if probability >= bracket.above:
            return not bracket.positive_below
    return _root_side(successes, total, probability, threshold, beta_term, bounds)


def _root_ball(
    successes: Count, total: Count, probability: Probability, threshold: arb, beta_term: arb
) -> arb:
    failures = total - successes
    if probability <= 0.0:
        return beta_term - threshold if successes == 0 else arb.pos_inf()
    if probability >= 1.0:
        return beta_term - threshold if failures == 0 else arb.pos_inf()
    x = arb(probability)
    return beta_term - successes * x.log() - failures * (1 - x).log() - threshold


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
    threshold: arb,
    root_tolerance: ToleranceValue,
    beta_term: arb,
) -> ClosedProbabilityInterval:
    success_count = successes
    total = matured_count
    if success_count < 0 or success_count > total:
        raise InvalidScientificDataError("categorical success count is outside [0, n]")
    if total == 0:
        return ClosedProbabilityInterval(lower=0.0, upper=1.0)
    maximum_likelihood = success_count / total
    bounds = _root_filter(threshold, beta_term)
    lower = 0.0
    if success_count > 0:
        lower = _lower_root(
            success_count, total, maximum_likelihood, threshold, root_tolerance, beta_term, bounds
        )
    upper = 1.0
    if success_count < total:
        upper = _upper_root(
            success_count, total, maximum_likelihood, threshold, root_tolerance, beta_term, bounds
        )
    return ClosedProbabilityInterval(lower=lower, upper=upper)


def _lower_root(
    successes: Count,
    total: Count,
    maximum_likelihood: Probability,
    threshold: arb,
    root_tolerance: ToleranceValue,
    beta_term: arb,
    bounds: _RootFilter,
) -> Probability:
    lower = 0.0
    upper = maximum_likelihood
    if _root_ball(successes, total, lower, threshold, beta_term) <= 0.0:
        return 0.0
    inner_is_certified = _root_side(successes, total, upper, threshold, beta_term, bounds) is False
    if not inner_is_certified:
        return 0.0
    estimate = _root_estimate(successes, total, upper, lower, bounds)
    bracket = _verified_bracket(successes, total, estimate, True, bounds)
    lower, upper = _advance_outside_bracket(lower, upper, root_tolerance, bracket)
    while upper - lower > root_tolerance:
        midpoint = (lower + upper) / 2.0
        if midpoint in (lower, upper):
            break
        side = _bracketed_side(successes, total, midpoint, threshold, beta_term, bounds, bracket)
        if side is None:
            break
        if side:
            lower = midpoint
        else:
            upper = midpoint
    return lower


def _upper_root(
    successes: Count,
    total: Count,
    maximum_likelihood: Probability,
    threshold: arb,
    root_tolerance: ToleranceValue,
    beta_term: arb,
    bounds: _RootFilter,
) -> Probability:
    lower = maximum_likelihood
    upper = 1.0
    if _root_ball(successes, total, upper, threshold, beta_term) <= 0.0:
        return 1.0
    inner_is_certified = _root_side(successes, total, lower, threshold, beta_term, bounds) is False
    if not inner_is_certified:
        return 1.0
    estimate = _root_estimate(successes, total, lower, upper, bounds)
    bracket = _verified_bracket(successes, total, estimate, False, bounds)
    lower, upper = _advance_outside_bracket(lower, upper, root_tolerance, bracket)
    while upper - lower > root_tolerance:
        midpoint = (lower + upper) / 2.0
        if midpoint in (lower, upper):
            break
        side = _bracketed_side(successes, total, midpoint, threshold, beta_term, bounds, bracket)
        if side is None:
            break
        if side:
            upper = midpoint
        else:
            lower = midpoint
    return upper
