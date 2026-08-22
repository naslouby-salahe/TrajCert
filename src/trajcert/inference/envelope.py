from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from trajcert.inference.confidence_sequence import ProbabilityInterval


class SummaryEnvelopeState(StrEnum):
    VALID = "VALID"
    TECHNICAL_FAIL = "TECHNICAL_FAIL"


@dataclass(frozen=True, slots=True)
class SummaryEnvelopeInput:
    finite_band_count: int
    category_intervals: tuple[ProbabilityInterval, ...]


@dataclass(frozen=True, slots=True)
class ConservativeSummaryEnvelope:
    state: SummaryEnvelopeState
    harmful_lower: float
    harmful_upper: float
    correct_lower: float
    correct_upper: float
    terminal_lower: float
    terminal_upper: float
    timing_entropy_lower: float
    timing_entropy_upper: float


def conservative_summary_envelope(input_value: SummaryEnvelopeInput) -> ConservativeSummaryEnvelope:
    if input_value.finite_band_count < 1:
        raise ValueError("summary envelope requires at least one finite band")
    expected_categories = 2 * input_value.finite_band_count + 1
    if len(input_value.category_intervals) != expected_categories:
        raise ValueError("summary envelope category dimensions are invalid")
    harmful_intervals = input_value.category_intervals[0:-1:2]
    correct_intervals = input_value.category_intervals[1:-1:2]
    terminal_interval = input_value.category_intervals[-1]
    harmful_lower = sum(interval.lower for interval in harmful_intervals)
    harmful_upper = sum(interval.upper for interval in harmful_intervals)
    correct_lower = sum(interval.lower for interval in correct_intervals)
    correct_upper = sum(interval.upper for interval in correct_intervals)
    terminal_lower = max(terminal_interval.lower, 1 - harmful_upper - correct_upper)
    terminal_upper = min(terminal_interval.upper, 1 - harmful_lower - correct_lower)
    entropy_lower = sum(
        _binary_entropy(harmful.lower, correct.lower)
        for harmful, correct in zip(harmful_intervals, correct_intervals, strict=True)
    )
    entropy_upper = sum(
        _binary_entropy(harmful.upper, correct.upper)
        for harmful, correct in zip(harmful_intervals, correct_intervals, strict=True)
    )
    state = (
        SummaryEnvelopeState.VALID
        if terminal_lower <= terminal_upper and entropy_lower <= entropy_upper
        else SummaryEnvelopeState.TECHNICAL_FAIL
    )
    return ConservativeSummaryEnvelope(
        state,
        harmful_lower,
        harmful_upper,
        correct_lower,
        correct_upper,
        terminal_lower,
        terminal_upper,
        entropy_lower,
        entropy_upper,
    )


def _binary_entropy(harmful_mass: float, correct_mass: float) -> float:
    total_mass = harmful_mass + correct_mass
    if total_mass == 0:
        return 0
    harmful_term = 0 if harmful_mass == 0 else -harmful_mass * math.log(harmful_mass / total_mass)
    correct_term = 0 if correct_mass == 0 else -correct_mass * math.log(correct_mass / total_mass)
    return harmful_term + correct_term
