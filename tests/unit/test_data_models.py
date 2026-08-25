from __future__ import annotations

# pytest's comparison helpers are intentionally dynamically typed.
# pyright: reportUnknownMemberType=false
from typing import cast

import numpy as np
import pytest
from pydantic import ValidationError

from trajcert.data.laws import (
    FullLawProbabilities,
    LawParameters,
    build_full_law,
    resolved_band_weights,
)
from trajcert.data.partitions import (
    TrajectoryPartition,
    build_partition,
    coarsen_mass_vector,
    partition_name,
)
from trajcert.data.summaries import (
    ObservableCounts,
    ObservableSummary,
    coarsen_summary,
    summarize_counts,
    summarize_full_law,
    summarize_observable_masses,
)
from trajcert.exceptions import (
    InvalidPartitionError,
    InvalidProbabilityError,
    InvalidScientificDataError,
)
from trajcert.types import HiddenMassInterval, LawKey, LawName, PartitionName, RiskInterval


@pytest.fixture
def fine_partition() -> TrajectoryPartition:
    return build_partition(4, 4, 8.0)


@pytest.fixture
def observable_summary(fine_partition: TrajectoryPartition) -> ObservableSummary:
    return summarize_observable_masses(
        fine_partition,
        np.array([0.10, 0.05, 0.0, 0.05]),
        np.array([0.20, 0.10, 0.10, 0.10]),
        0.30,
        1e-12,
    )


@pytest.mark.parametrize(
    ("finest", "bands", "horizon", "boundaries", "mapping"),
    [
        (4, 4, 8.0, (2.0, 4.0, 6.0, 8.0), (1, 2, 3, 4)),
        (4, 2, 8.0, (4.0, 8.0), (1, 1, 2, 2)),
        (8, 1, 6.0, (6.0,), (1,) * 8),
    ],
)
def test_build_partition_constructs_deterministic_coarsenings(
    finest: int, bands: int, horizon: float, boundaries: tuple[float, ...], mapping: tuple[int, ...]
) -> None:
    partition = build_partition(finest, bands, horizon)

    assert partition.boundaries == boundaries
    assert partition.coarsening_map_from_finest == mapping
    observed_mapping = tuple(
        partition.coarse_band_for_finest(index) for index in range(1, finest + 1)
    )
    assert observed_mapping == mapping


@pytest.mark.parametrize(
    ("finest", "bands", "horizon"),
    [(0, 1, 1.0), (4, 0, 1.0), (4, 3, 1.0), (2, 4, 1.0), (4, 2, 0.0)],
)
def test_build_partition_rejects_invalid_shapes(finest: int, bands: int, horizon: float) -> None:
    with pytest.raises(InvalidPartitionError):
        build_partition(finest, bands, horizon)


@pytest.mark.parametrize(
    ("bands", "expected"), [(1, "Endpoint-only partition"), (3, "3-band partition")]
)
def test_partition_name(bands: int, expected: str) -> None:
    assert partition_name(bands) == expected


def test_partition_model_rejects_inconsistent_mapping() -> None:
    with pytest.raises(InvalidPartitionError, match="inconsistent"):
        TrajectoryPartition(
            name=cast(PartitionName, "bad"),
            finest_band_count=4,
            band_count=2,
            terminal_horizon=8.0,
            boundaries=(4.0, 8.0),
            coarsening_map_from_finest=(1, 2, 1, 2),
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"finest_band_count": 4, "band_count": 3},
        {"boundaries": (8.0,)},
        {"coarsening_map_from_finest": (1, 1)},
        {"boundaries": (8.0, 4.0)},
        {"boundaries": (3.0, 7.0)},
        {"coarsening_map_from_finest": (1, 1, 3, 3)},
    ],
)
def test_partition_model_rejects_every_structural_invariant(payload: dict[str, object]) -> None:
    valid: dict[str, object] = {
        "name": "two bands",
        "finest_band_count": 4,
        "band_count": 2,
        "terminal_horizon": 8.0,
        "boundaries": (4.0, 8.0),
        "coarsening_map_from_finest": (1, 1, 2, 2),
    }
    valid.update(payload)
    with pytest.raises(InvalidPartitionError):
        TrajectoryPartition.model_validate(valid)


@pytest.mark.parametrize(
    ("values", "fine_bands", "coarse_bands", "expected"),
    [
        ([0.1, 0.2, 0.3, 0.4], 4, 2, [0.3, 0.7]),
        ([0.1, 0.2, 0.3, 0.4], 4, 4, [0.1, 0.2, 0.3, 0.4]),
    ],
)
def test_coarsen_mass_vector(
    values: list[float], fine_bands: int, coarse_bands: int, expected: list[float]
) -> None:
    fine = build_partition(4, fine_bands, 8.0)
    coarse = build_partition(4, coarse_bands, 8.0)
    assert np.allclose(coarsen_mass_vector(np.array(values), fine, coarse), expected)


def test_partition_public_guards_reject_invalid_indices_and_coarsenings() -> None:
    fine = build_partition(4, 4, 8.0)
    coarse = build_partition(4, 2, 8.0)
    unrelated = build_partition(6, 2, 8.0)
    with pytest.raises(InvalidPartitionError):
        fine.coarse_band_for_finest(0)
    with pytest.raises(InvalidPartitionError):
        partition_name(0)
    with pytest.raises(InvalidPartitionError):
        coarsen_mass_vector(np.array([0.1]), fine, coarse)
    with pytest.raises(InvalidPartitionError):
        coarsen_mass_vector(np.array([0.1, 0.2, 0.3, 0.4]), fine, unrelated)


def test_summary_helpers_reject_mismatched_inputs() -> None:
    partition = build_partition(2, 2, 1.0)
    with pytest.raises(InvalidScientificDataError, match="vectors"):
        summarize_observable_masses(partition, np.array([0.2]), np.array([0.8]), 0.0, 1e-12)
    law = FullLawProbabilities(
        harmful_resolved=np.array([0.2]),
        correct_resolved=np.array([0.8]),
        terminal_harmful=0.0,
        terminal_correct=0.0,
    )
    with pytest.raises(InvalidScientificDataError, match="resolution"):
        summarize_full_law(partition, law, 1e-12)
    with pytest.raises(InvalidScientificDataError, match="count vectors"):
        summarize_counts(
            partition,
            ObservableCounts(harmful_by_band=(1,), correct_by_band=(1,), unresolved=0),
            1e-12,
        )


@pytest.mark.parametrize("slope", [-2.0, 0.0, 2.0])
def test_resolved_band_weights_are_normalized_and_follow_slope(slope: float) -> None:
    weights = resolved_band_weights(4, slope)
    assert weights.dtype == np.float64
    assert weights.sum() == pytest.approx(1.0)
    if slope == 0.0:
        assert np.allclose(weights, np.repeat(0.25, 4))
    else:
        assert bool(weights[-1] > weights[0]) is (slope > 0.0)


def test_full_law_and_summary_preserve_probability_mass() -> None:
    parameters = LawParameters(
        key=LawKey.NO_PATH_DEPENDENCE,
        name=LawName("law"),
        theta=0.2,
        q1=0.25,
        q0=0.5,
        lambda1=0.0,
        lambda0=0.0,
    )
    law = build_full_law(parameters, 2)
    summary = summarize_full_law(build_partition(2, 2, 1.0), law, 1e-12)

    assert law.unresolved == pytest.approx(0.45)
    assert law.total == pytest.approx(1.0)
    assert summary.total_mass == pytest.approx(1.0)
    assert summary.harmful_rate_by_band == (pytest.approx(3 / 11), pytest.approx(3 / 11))


@pytest.mark.parametrize(
    ("harmful", "correct", "unresolved", "exception"),
    [([0.2], [0.2], 0.2, InvalidProbabilityError), ([0.2], [0.8], 0.0, None)],
)
def test_summarize_observable_masses_validates_mass(
    harmful: list[float],
    correct: list[float],
    unresolved: float,
    exception: type[Exception] | None,
) -> None:
    partition = build_partition(1, 1, 1.0)
    if exception:
        with pytest.raises(exception):
            summarize_observable_masses(
                partition, np.array(harmful), np.array(correct), unresolved, 1e-12
            )
    else:
        summary = summarize_observable_masses(
            partition, np.array(harmful), np.array(correct), unresolved, 1e-12
        )
        assert summary.harmful_rate_by_band == (pytest.approx(0.2),)


@pytest.mark.parametrize(
    ("counts", "expected_total", "raises"),
    [
        (ObservableCounts(harmful_by_band=(1, 0), correct_by_band=(1, 2), unresolved=2), 6, False),
        (ObservableCounts(harmful_by_band=(0, 0), correct_by_band=(0, 0), unresolved=0), 0, True),
    ],
)
def test_summarize_counts_and_counts_total(
    counts: ObservableCounts, expected_total: int, raises: bool
) -> None:
    partition = build_partition(2, 2, 1.0)
    assert counts.total == expected_total
    if raises:
        with pytest.raises(InvalidScientificDataError, match="at least one"):
            summarize_counts(partition, counts, 1e-12)
    else:
        assert summarize_counts(partition, counts, 1e-12).total_mass == pytest.approx(1.0)


def test_coarsen_summary_and_intervals(observable_summary: ObservableSummary) -> None:
    coarse = build_partition(4, 2, 8.0)
    result = coarsen_summary(observable_summary, coarse, 1e-12)
    assert np.allclose(result.harmful_by_band, [0.15, 0.05])
    assert result.total_mass == pytest.approx(1.0)
    assert HiddenMassInterval(lower=0.1, upper=0.3).width == pytest.approx(0.2)
    assert RiskInterval(lower=0.2, upper=0.6).width == pytest.approx(0.4)


@pytest.mark.parametrize(
    "payload",
    [{"lower": 0.2, "upper": 0.8, "extra": 1}, {"lower": -0.1, "upper": 0.8}],
)
def test_domain_models_forbid_extra_and_invalid_probability(payload: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        HiddenMassInterval.model_validate(payload)
