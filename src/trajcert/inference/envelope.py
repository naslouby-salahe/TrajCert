from __future__ import annotations

from typing import Self

import numpy as np
from flint import arb
from pydantic import model_validator

from trajcert.data.partitions import TrajectoryPartition
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import NumericalError
from trajcert.inference.confidence import CategoricalConfidenceRegion, ClosedProbabilityInterval
from trajcert.math.enclosure import ball_lower, ball_upper, mass_entropy_ball, sum_lower, sum_upper
from trajcert.types import (
    CategoryIndex,
    DomainModel,
    Mass,
    ToleranceValue,
    mass_tuple,
)


class ScalarEnvelope(DomainModel):
    lower: Mass
    upper: Mass

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if not 0.0 <= self.lower <= self.upper <= 1.0:
            raise NumericalError("envelope lower endpoint exceeds upper endpoint")
        return self

    @property
    def is_singleton(self) -> bool:
        return self.lower == self.upper


class ObservableSummaryEnvelope(DomainModel):
    partition: TrajectoryPartition
    harmful_by_band: tuple[ScalarEnvelope, ...]
    correct_by_band: tuple[ScalarEnvelope, ...]
    unresolved: ScalarEnvelope
    resolved_harmful: ScalarEnvelope
    resolved_correct: ScalarEnvelope
    resolved_entropy: ScalarEnvelope

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        bands = self.partition.band_count
        if len(self.harmful_by_band) != bands or len(self.correct_by_band) != bands:
            raise NumericalError("summary-envelope vectors must match the partition")
        return self

    @property
    def is_singleton(self) -> bool:
        intervals = self.harmful_by_band + self.correct_by_band + (self.unresolved,)
        return all(interval.is_singleton for interval in intervals)

    def exact_summary(self, comparison_guard: ToleranceValue) -> ObservableSummary:
        if not self.is_singleton:
            raise NumericalError("non-singleton envelope has no exact observable summary")
        harmful = np.asarray(
            tuple(interval.lower for interval in self.harmful_by_band), dtype=np.float64
        )
        correct = np.asarray(
            tuple(interval.lower for interval in self.correct_by_band), dtype=np.float64
        )
        return summarize_observable_masses(
            partition=self.partition,
            harmful_by_band=harmful,
            correct_by_band=correct,
            unresolved_mass=self.unresolved.lower,
            comparison_guard=comparison_guard,
        )


def summary_envelope_from_confidence(
    partition: TrajectoryPartition,
    confidence: CategoricalConfidenceRegion,
) -> ObservableSummaryEnvelope:
    expected_categories = 2 * partition.band_count + 1
    if len(confidence.intervals) != expected_categories:
        raise NumericalError("confidence-region dimension is inconsistent with the partition")
    harmful = tuple(confidence.intervals[index] for index in range(0, expected_categories - 1, 2))
    correct = tuple(confidence.intervals[index] for index in range(1, expected_categories - 1, 2))
    unresolved = _subset_interval(confidence.intervals, (expected_categories - 1,))
    harmful_indices = tuple(range(0, expected_categories - 1, 2))
    correct_indices = tuple(range(1, expected_categories - 1, 2))
    resolved_harmful = _subset_interval(confidence.intervals, harmful_indices)
    resolved_correct = _subset_interval(confidence.intervals, correct_indices)
    resolved_entropy = _resolved_entropy_envelope(harmful, correct)
    return ObservableSummaryEnvelope(
        partition=partition,
        harmful_by_band=tuple(_scalar(interval) for interval in harmful),
        correct_by_band=tuple(_scalar(interval) for interval in correct),
        unresolved=_scalar(unresolved),
        resolved_harmful=_scalar(resolved_harmful),
        resolved_correct=_scalar(resolved_correct),
        resolved_entropy=resolved_entropy,
    )


def singleton_summary_envelope(summary: ObservableSummary) -> ObservableSummaryEnvelope:
    harmful_masses = mass_tuple(summary.harmful_by_band)
    correct_masses = mass_tuple(summary.correct_by_band)
    harmful = tuple(ScalarEnvelope(lower=value, upper=value) for value in harmful_masses)
    correct = tuple(ScalarEnvelope(lower=value, upper=value) for value in correct_masses)
    entropy = _resolved_entropy_envelope(
        tuple(ClosedProbabilityInterval(lower=x, upper=x) for x in harmful_masses),
        tuple(ClosedProbabilityInterval(lower=x, upper=x) for x in correct_masses),
    )
    return ObservableSummaryEnvelope(
        partition=summary.partition,
        harmful_by_band=harmful,
        correct_by_band=correct,
        unresolved=ScalarEnvelope(lower=summary.unresolved_mass, upper=summary.unresolved_mass),
        resolved_harmful=ScalarEnvelope(
            lower=sum_lower(harmful_masses),
            upper=sum_upper(harmful_masses),
        ),
        resolved_correct=ScalarEnvelope(
            lower=sum_lower(correct_masses),
            upper=sum_upper(correct_masses),
        ),
        resolved_entropy=entropy,
    )


def _subset_interval(
    intervals: tuple[ClosedProbabilityInterval, ...],
    selected: tuple[CategoryIndex, ...],
) -> ClosedProbabilityInterval:
    selected_set = frozenset(selected)
    direct_lower = sum_lower(intervals[index].lower for index in selected)
    direct_upper = sum_upper(intervals[index].upper for index in selected)
    complement_lower = sum_lower(
        interval.lower for index, interval in enumerate(intervals) if index not in selected_set
    )
    complement_upper = sum_upper(
        interval.upper for index, interval in enumerate(intervals) if index not in selected_set
    )
    lower = max(direct_lower, sum_lower((1.0, -complement_upper)), 0.0)
    upper = min(direct_upper, sum_upper((1.0, -complement_lower)), 1.0)
    if lower > upper:
        raise NumericalError("confidence rectangle yields an empty aggregate interval")
    return ClosedProbabilityInterval(lower=lower, upper=upper)


def _resolved_entropy_envelope(
    harmful: tuple[ClosedProbabilityInterval, ...],
    correct: tuple[ClosedProbabilityInterval, ...],
) -> ScalarEnvelope:
    lower_ball = sum(
        (
            mass_entropy_ball(arb(left.lower), arb(right.lower))
            for left, right in zip(harmful, correct, strict=True)
        ),
        arb(0),
    )
    upper_ball = sum(
        (
            mass_entropy_ball(arb(left.upper), arb(right.upper))
            for left, right in zip(harmful, correct, strict=True)
        ),
        arb(0),
    )
    mass_upper = min(
        1.0, sum_upper(x.upper for pair in zip(harmful, correct, strict=True) for x in pair)
    )
    upper = min(ball_upper(upper_ball), ball_upper(arb(mass_upper) * arb(2).log()))
    return ScalarEnvelope(lower=max(0.0, ball_lower(lower_ball)), upper=upper)


def _scalar(interval: ClosedProbabilityInterval) -> ScalarEnvelope:
    return ScalarEnvelope(lower=interval.lower, upper=interval.upper)
