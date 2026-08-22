from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from trajcert.configuration.models import ConfidenceConfiguration, NumericsConfiguration


class ConfidenceSequenceState(StrEnum):
    VALID = "VALID"
    TECHNICAL_FAIL = "TECHNICAL_FAIL"


@dataclass(frozen=True, slots=True)
class ProbabilityBracket:
    lower: float
    upper: float


@dataclass(frozen=True, slots=True)
class ProbabilityInterval:
    lower: float
    upper: float
    lower_bracket: ProbabilityBracket | None
    upper_bracket: ProbabilityBracket | None


@dataclass(frozen=True, slots=True)
class CategoryCounts:
    values: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.values or any(value < 0 for value in self.values):
            raise ValueError("category counts must be nonempty and nonnegative")

    @property
    def matured_events(self) -> int:
        return sum(self.values)


@dataclass(frozen=True, slots=True)
class ConfidenceSequenceInput:
    counts: CategoryCounts
    confidence: ConfidenceConfiguration
    numerics: NumericsConfiguration
    previous_running_intervals: tuple[ProbabilityInterval, ...] | None


@dataclass(frozen=True, slots=True)
class ConfidenceSequenceResult:
    state: ConfidenceSequenceState
    raw_intervals: tuple[ProbabilityInterval, ...]
    running_intervals: tuple[ProbabilityInterval, ...]
    simplex_feasible: bool
    threshold: float


def categorical_confidence_sequence(
    input_value: ConfidenceSequenceInput,
) -> ConfidenceSequenceResult:
    category_count = len(input_value.counts.values)
    expected_category_count = 2 * ((category_count - 1) // 2) + 1
    if category_count != expected_category_count:
        raise ValueError("categorical confidence sequence requires 2K+1 categories")
    if (
        input_value.previous_running_intervals is not None
        and len(input_value.previous_running_intervals) != category_count
    ):
        raise ValueError("running interval dimension must match category counts")
    threshold = math.log(category_count / input_value.confidence.anytime_delta)
    raw_intervals = tuple(
        _raw_interval(count, input_value.counts.matured_events, threshold, input_value.numerics)
        for count in input_value.counts.values
    )
    running_intervals = tuple(
        _running_interval(raw, previous)
        for raw, previous in zip(
            raw_intervals,
            input_value.previous_running_intervals
            if input_value.previous_running_intervals is not None
            else (None,) * category_count,
            strict=True,
        )
    )
    simplex_feasible = _simplex_feasible(running_intervals)
    state = (
        ConfidenceSequenceState.VALID
        if simplex_feasible
        else ConfidenceSequenceState.TECHNICAL_FAIL
    )
    return ConfidenceSequenceResult(
        state, raw_intervals, running_intervals, simplex_feasible, threshold
    )


def category_log_mixture(count: int, matured_events: int, probability: float) -> float:
    if count < 0 or matured_events < count or probability < 0 or probability > 1:
        raise ValueError("invalid categorical mixture inputs")
    beta_difference = (
        math.lgamma(count + 0.5)
        + math.lgamma(matured_events - count + 0.5)
        - math.lgamma(matured_events + 1)
        - (2 * math.lgamma(0.5) - math.lgamma(1))
    )
    if probability == 0:
        return beta_difference if count == 0 else math.inf
    if probability == 1:
        return beta_difference if count == matured_events else math.inf
    return (
        beta_difference
        - count * math.log(probability)
        - (matured_events - count) * math.log1p(-probability)
    )


def _raw_interval(
    count: int, matured_events: int, threshold: float, numerics: NumericsConfiguration
) -> ProbabilityInterval:
    empirical = count / matured_events if matured_events else 0.5

    def objective(probability: float) -> float:
        return category_log_mixture(count, matured_events, probability) - threshold

    lower_bracket = None if objective(0) <= 0 else _bisect(objective, 0, empirical, numerics)
    upper_bracket = None if objective(1) <= 0 else _bisect(objective, empirical, 1, numerics)
    lower = 0 if lower_bracket is None else lower_bracket.lower
    upper = 1 if upper_bracket is None else upper_bracket.upper
    if lower > upper:
        raise ValueError("raw categorical confidence interval is empty")
    return ProbabilityInterval(lower, upper, lower_bracket, upper_bracket)


def _bisect(
    objective: _ProbabilityObjective, lower: float, upper: float, numerics: NumericsConfiguration
) -> ProbabilityBracket:
    left = lower
    right = upper
    left_value = objective(left)
    right_value = objective(right)
    if left_value * right_value > 0:
        raise ValueError("categorical confidence root bracket is not sign-valid")
    while right - left > numerics.anytime_category_root_tolerance:
        midpoint = (left + right) / 2
        midpoint_value = objective(midpoint)
        if midpoint_value == 0:
            return ProbabilityBracket(midpoint, midpoint)
        if left_value * midpoint_value <= 0:
            right = midpoint
        else:
            left = midpoint
            left_value = midpoint_value
    return ProbabilityBracket(left, right)


def _running_interval(
    raw: ProbabilityInterval, previous: ProbabilityInterval | None
) -> ProbabilityInterval:
    if previous is None:
        return raw
    lower = max(previous.lower, raw.lower)
    upper = min(previous.upper, raw.upper)
    if lower > upper:
        return ProbabilityInterval(lower, upper, raw.lower_bracket, raw.upper_bracket)
    return ProbabilityInterval(lower, upper, raw.lower_bracket, raw.upper_bracket)


def _simplex_feasible(intervals: tuple[ProbabilityInterval, ...]) -> bool:
    return (
        sum(interval.lower for interval in intervals)
        <= 1
        <= sum(interval.upper for interval in intervals)
    )


type _ProbabilityObjective = Callable[[float], float]
