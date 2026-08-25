from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from trajcert.data.laws import FullLawProbabilities
from trajcert.data.partitions import (
    TrajectoryPartition,
    coarsen_mass_vector,
)
from trajcert.exceptions import (
    InvalidProbabilityError,
    InvalidScientificDataError,
)
from trajcert.types import (
    Count,
    Mass,
    Probability,
    ToleranceValue,
)


@dataclass(frozen=True, slots=True)
class ObservableSummary:
    partition: TrajectoryPartition

    harmful_by_band: tuple[Mass, ...]
    correct_by_band: tuple[Mass, ...]
    unresolved_mass: Mass

    resolved_harmful_mass: Mass
    resolved_correct_mass: Mass

    finite_band_mass: tuple[Mass, ...]
    harmful_rate_by_band: tuple[
        Probability | None,
        ...,
    ]

    @property
    def resolved_mass(self) -> Mass:
        return Mass(
            float(self.resolved_harmful_mass)
            + float(self.resolved_correct_mass)
        )

    @property
    def total_mass(self) -> Mass:
        return Mass(
            float(self.resolved_mass)
            + float(self.unresolved_mass)
        )


@dataclass(frozen=True, slots=True)
class ObservableCounts:
    harmful_by_band: tuple[Count, ...]
    correct_by_band: tuple[Count, ...]
    unresolved: Count

    @property
    def total(self) -> Count:
        return Count(
            sum(
                int(value)
                for value in self.harmful_by_band
            )
            + sum(
                int(value)
                for value in self.correct_by_band
            )
            + int(self.unresolved)
        )


def summarize_observable_masses(
    partition: TrajectoryPartition,
    harmful_by_band: tuple[Mass, ...],
    correct_by_band: tuple[Mass, ...],
    unresolved_mass: Mass,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    bands = int(partition.band_count)

    if (
        len(harmful_by_band) != bands
        or len(correct_by_band) != bands
    ):
        raise InvalidScientificDataError(
            "observable mass vectors must match "
            "the partition band count"
        )

    _validate_mass_vector(
        harmful_by_band,
        "harmful_by_band",
    )
    _validate_mass_vector(
        correct_by_band,
        "correct_by_band",
    )
    _validate_mass(
        unresolved_mass,
        "unresolved_mass",
    )

    guard = float(comparison_guard)

    if (
        not isfinite(guard)
        or guard <= 0.0
    ):
        raise InvalidScientificDataError(
            "comparison guard must be finite and positive"
        )

    harmful_total = Mass(
        sum(
            float(value)
            for value in harmful_by_band
        )
    )
    correct_total = Mass(
        sum(
            float(value)
            for value in correct_by_band
        )
    )

    total = (
        float(harmful_total)
        + float(correct_total)
        + float(unresolved_mass)
    )

    if abs(total - 1.0) > guard:
        raise InvalidProbabilityError(
            "observable masses do not sum to one "
            "within the configured comparison guard"
        )

    band_mass = tuple(
        Mass(
            float(harmful)
            + float(correct)
        )
        for harmful, correct in zip(
            harmful_by_band,
            correct_by_band,
            strict=True,
        )
    )

    harmful_rate = tuple(
        (
            None
            if float(total_band) == 0.0
            else Probability(
                float(harmful)
                / float(total_band)
            )
        )
        for harmful, total_band in zip(
            harmful_by_band,
            band_mass,
            strict=True,
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
    partition: TrajectoryPartition,
    full_law: FullLawProbabilities,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    if (
        len(full_law.harmful_resolved)
        != int(partition.band_count)
    ):
        raise InvalidScientificDataError(
            "full law resolution does not "
            "match the partition"
        )

    return summarize_observable_masses(
        partition=partition,
        harmful_by_band=full_law.harmful_resolved,
        correct_by_band=full_law.correct_resolved,
        unresolved_mass=full_law.unresolved,
        comparison_guard=comparison_guard,
    )


def summarize_counts(
    partition: TrajectoryPartition,
    counts: ObservableCounts,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    bands = int(partition.band_count)

    if (
        len(counts.harmful_by_band) != bands
        or len(counts.correct_by_band) != bands
    ):
        raise InvalidScientificDataError(
            "observable count vectors must match "
            "the partition band count"
        )

    count_values = (
        tuple(
            int(value)
            for value in (
                counts.harmful_by_band
                + counts.correct_by_band
            )
        )
        + (int(counts.unresolved),)
    )

    if any(
        value < 0
        for value in count_values
    ):
        raise InvalidScientificDataError(
            "observable counts cannot be negative"
        )

    total = int(counts.total)

    if total <= 0:
        raise InvalidScientificDataError(
            "observable counts must contain "
            "at least one event"
        )

    return summarize_observable_masses(
        partition=partition,
        harmful_by_band=tuple(
            Mass(
                int(value) / total
            )
            for value in counts.harmful_by_band
        ),
        correct_by_band=tuple(
            Mass(
                int(value) / total
            )
            for value in counts.correct_by_band
        ),
        unresolved_mass=Mass(
            int(counts.unresolved) / total
        ),
        comparison_guard=comparison_guard,
    )


def coarsen_summary(
    summary: ObservableSummary,
    coarse_partition: TrajectoryPartition,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    harmful = coarsen_mass_vector(
        summary.harmful_by_band,
        summary.partition,
        coarse_partition,
    )
    correct = coarsen_mass_vector(
        summary.correct_by_band,
        summary.partition,
        coarse_partition,
    )

    return summarize_observable_masses(
        partition=coarse_partition,
        harmful_by_band=harmful,
        correct_by_band=correct,
        unresolved_mass=summary.unresolved_mass,
        comparison_guard=comparison_guard,
    )


def _validate_mass_vector(
    values: tuple[Mass, ...],
    field_name: str,
) -> None:
    for value in values:
        _validate_mass(
            value,
            field_name,
        )


def _validate_mass(
    value: Mass,
    field_name: str,
) -> None:
    numeric = float(value)

    if (
        not isfinite(numeric)
        or numeric < 0.0
        or numeric > 1.0
    ):
        raise InvalidProbabilityError(
            f"{field_name} contains "
            "a non-probability mass"
        )