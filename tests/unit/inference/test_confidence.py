from __future__ import annotations

import pytest

from trajcert.data.ledger import LedgerIdentity
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableCounts
from trajcert.exceptions import InvalidScientificDataError, NumericalError
from trajcert.inference.categorical import CategoricalState
from trajcert.inference.confidence import (
    CategoricalConfidenceRegion,
    ClosedProbabilityInterval,
    ConfidenceSequenceUpdate,
    confidence_sequence_update,
    raw_confidence_region,
)
from trajcert.types import ActionChannelId, ClientId, EpochId


def _identity() -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("client"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
    )


def _state(counts: tuple[int, ...], band_count: int = 2) -> CategoricalState:
    partition = build_partition(band_count, band_count, 8.0)
    harmful = tuple(counts[index] for index in range(0, len(counts) - 1, 2))
    correct = tuple(counts[index] for index in range(1, len(counts) - 1, 2))
    return CategoricalState(
        identity=_identity(),
        partition=partition,
        counts=ObservableCounts(
            harmful_by_band=harmful,
            correct_by_band=correct,
            unresolved=counts[-1],
        ),
    )


@pytest.mark.parametrize(
    ("lower", "upper", "raises"),
    [
        (0.2, 0.6, False),
        (0.6, 0.2, True),
    ],
)
def test_closed_probability_interval_order(lower: float, upper: float, raises: bool) -> None:
    if raises:
        with pytest.raises(NumericalError, match="lower endpoint"):
            _ = ClosedProbabilityInterval(lower=lower, upper=upper)
    else:
        interval = ClosedProbabilityInterval(lower=lower, upper=upper)
        assert interval.lower == lower
        assert interval.upper == upper


@pytest.mark.parametrize(
    "intervals",
    [
        (),
        ((ClosedProbabilityInterval(lower=0.6, upper=0.6),) * 2),
        ((ClosedProbabilityInterval(lower=0.0, upper=0.4),) * 2),
    ],
)
def test_confidence_region_rejects_invalid_simplex(
    intervals: tuple[ClosedProbabilityInterval, ...],
) -> None:
    with pytest.raises(NumericalError):
        _ = CategoricalConfidenceRegion(matured_count=4, intervals=intervals)


def test_confidence_region_accepts_nonempty_simplex_intersection() -> None:
    matured_count = 4
    interval_count = 2
    region = CategoricalConfidenceRegion(
        matured_count=matured_count,
        intervals=(
            ClosedProbabilityInterval(lower=0.2, upper=0.6),
            ClosedProbabilityInterval(lower=0.2, upper=0.6),
        ),
    )
    assert region.matured_count == matured_count
    assert len(region.intervals) == interval_count


@pytest.mark.parametrize("delta", [0.0, 1.0])
def test_raw_confidence_region_rejects_boundary_delta(delta: float) -> None:
    state = _state((1, 0, 0, 0, 0))
    with pytest.raises(InvalidScientificDataError, match="strictly between"):
        _ = raw_confidence_region(state, delta, 1e-6)


def test_raw_confidence_region_on_empty_state() -> None:
    state = _state((0, 0, 0, 0, 0))
    region = raw_confidence_region(state, 0.05, 1e-6)
    category_count = len(state.canonical_count_vector)
    assert len(region.intervals) == category_count
    assert all(interval.lower == 0.0 and interval.upper == 1.0 for interval in region.intervals)


def test_raw_confidence_region_contains_maximum_likelihood() -> None:
    state = _state((1, 0, 0, 0, 0))
    region = raw_confidence_region(state, 0.05, 1e-6)
    assert region.matured_count == state.matured_count
    category_count = len(state.canonical_count_vector)
    assert len(region.intervals) == category_count
    first = region.intervals[0]
    assert first.lower <= 1.0
    assert first.upper == 1.0


def test_confidence_sequence_update_initializes_running_from_raw() -> None:
    state = _state((1, 0, 0, 0, 0))
    update = confidence_sequence_update(state, 0.05, 1e-6, None)
    assert isinstance(update, ConfidenceSequenceUpdate)
    assert update.running == update.raw


def test_confidence_sequence_update_rejects_dimension_change() -> None:
    state = _state((1, 0, 0, 0, 0))
    previous = CategoricalConfidenceRegion(
        matured_count=1,
        intervals=(ClosedProbabilityInterval(lower=0.0, upper=1.0),) * 4,
    )
    with pytest.raises(NumericalError, match="dimension"):
        _ = confidence_sequence_update(state, 0.05, 1e-6, previous)


def test_confidence_sequence_update_narrows_running_region() -> None:
    first_state = _state((1, 0, 0, 0, 0))
    second_state = _state((2, 0, 0, 0, 0))
    first = confidence_sequence_update(first_state, 0.05, 1e-6, None)
    second = confidence_sequence_update(second_state, 0.05, 1e-6, first.running)
    for running_interval, raw_interval in zip(
        second.running.intervals, second.raw.intervals, strict=True
    ):
        assert running_interval.lower >= raw_interval.lower
        assert running_interval.upper <= raw_interval.upper
    first_interval = first.running.intervals[0]
    running_interval = second.running.intervals[0]
    assert running_interval.lower >= first_interval.lower
    assert running_interval.upper <= first_interval.upper
