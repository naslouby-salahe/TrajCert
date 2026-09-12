from __future__ import annotations

import numpy as np

from trajcert.data.laws import FullLawProbabilities
from trajcert.data.partitions import TrajectoryPartition, coarsen_mass_vector
from trajcert.exceptions import InvalidProbabilityError, InvalidScientificDataError
from trajcert.types import Count, DomainModel, Mass, Probability, ToleranceValue, Vector


class ObservableSummary(DomainModel):
    partition: TrajectoryPartition
    harmful_by_band: Vector
    correct_by_band: Vector
    unresolved_mass: Mass
    resolved_harmful_mass: Mass
    resolved_correct_mass: Mass
    finite_band_mass: Vector
    harmful_rate_by_band: tuple[Probability | None, ...]

    @property
    def resolved_mass(self) -> Mass:
        return self.resolved_harmful_mass + self.resolved_correct_mass

    @property
    def total_mass(self) -> Mass:
        return self.resolved_mass + self.unresolved_mass


class ObservableCounts(DomainModel):
    harmful_by_band: tuple[Count, ...]
    correct_by_band: tuple[Count, ...]
    unresolved: Count

    @property
    def total(self) -> Count:
        return sum(self.harmful_by_band) + sum(self.correct_by_band) + self.unresolved


def summarize_observable_masses(
    partition: TrajectoryPartition,
    harmful_by_band: Vector,
    correct_by_band: Vector,
    unresolved_mass: Mass,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    bands = partition.band_count
    if len(harmful_by_band) != bands or len(correct_by_band) != bands:
        raise InvalidScientificDataError(
            "observable mass vectors must match the partition band count"
        )
    guard = comparison_guard
    harmful_total = np.sum(harmful_by_band)
    correct_total = np.sum(correct_by_band)
    total = harmful_total + correct_total + unresolved_mass
    if abs(total - 1.0) > guard:
        raise InvalidProbabilityError(
            "observable masses do not sum to one within the configured comparison guard"
        )
    band_mass = harmful_by_band + correct_by_band
    harmful_rate = tuple(
        (
            None if (total_band := harmful + correct) <= 0.0 else harmful / total_band
            for harmful, correct in zip(harmful_by_band, correct_by_band, strict=True)
        )
    )
    return ObservableSummary(
        partition=partition,
        harmful_by_band=harmful_by_band,
        correct_by_band=correct_by_band,
        unresolved_mass=unresolved_mass,
        resolved_harmful_mass=harmful_total,
        resolved_correct_mass=correct_total,
        finite_band_mass=band_mass,
        harmful_rate_by_band=harmful_rate,
    )


def summarize_full_law(
    partition: TrajectoryPartition, full_law: FullLawProbabilities, comparison_guard: ToleranceValue
) -> ObservableSummary:
    if len(full_law.harmful_resolved) != partition.band_count:
        raise InvalidScientificDataError("full law resolution does not match the partition")
    return summarize_observable_masses(
        partition=partition,
        harmful_by_band=full_law.harmful_resolved,
        correct_by_band=full_law.correct_resolved,
        unresolved_mass=full_law.unresolved,
        comparison_guard=comparison_guard,
    )


def summarize_counts(
    partition: TrajectoryPartition, counts: ObservableCounts, comparison_guard: ToleranceValue
) -> ObservableSummary:
    bands = partition.band_count
    if len(counts.harmful_by_band) != bands or len(counts.correct_by_band) != bands:
        raise InvalidScientificDataError(
            "observable count vectors must match the partition band count"
        )
    total = counts.total
    if total <= 0:
        raise InvalidScientificDataError("observable counts must contain at least one event")
    return summarize_observable_masses(
        partition=partition,
        harmful_by_band=np.array(counts.harmful_by_band, dtype=np.float64) / total,
        correct_by_band=np.array(counts.correct_by_band, dtype=np.float64) / total,
        unresolved_mass=counts.unresolved / total,
        comparison_guard=comparison_guard,
    )


def coarsen_summary(
    summary: ObservableSummary,
    coarse_partition: TrajectoryPartition,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    harmful = coarsen_mass_vector(summary.harmful_by_band, summary.partition, coarse_partition)
    correct = coarsen_mass_vector(summary.correct_by_band, summary.partition, coarse_partition)
    return summarize_observable_masses(
        partition=coarse_partition,
        harmful_by_band=harmful,
        correct_by_band=correct,
        unresolved_mass=summary.unresolved_mass,
        comparison_guard=comparison_guard,
    )
