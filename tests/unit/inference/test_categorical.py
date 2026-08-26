from __future__ import annotations

import pytest

from trajcert.data.ledger import LedgerIdentity
from trajcert.data.maturity import MaturedCategory, MaturedCategoryKind, MaturedEvent
from trajcert.data.partitions import build_partition
from trajcert.exceptions import DataIntegrityError, InvalidScientificDataError
from trajcert.inference.categorical import (
    CategoricalState,
    accumulate_matured_events,
    append_matured_event,
    initialize_categorical_state,
)
from trajcert.types import ActionChannelId, ClientId, EpochId, EventId, OutcomeLabel


def _identity() -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("client"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
    )


def _state(band_count: int = 2) -> CategoricalState:
    partition = build_partition(band_count, band_count, 8.0)
    return initialize_categorical_state(_identity(), partition)


def _matured(
    kind: MaturedCategoryKind,
    band_index: int | None,
    label: OutcomeLabel | None,
) -> MaturedEvent:
    return MaturedEvent(
        event_id=EventId("e1"),
        identity=_identity(),
        maturity_age_unit=1.0,
        category=MaturedCategory(
            kind=kind,
            band_index=band_index,
            correctness_label=label,
        ),
    )


def test_initialize_categorical_state() -> None:
    state = _state()
    assert state.matured_count == 0
    assert state.resolved_count == 0
    assert state.unresolved_count == 0
    assert state.canonical_count_vector == (0, 0, 0, 0, 0)


def test_append_matured_event_accumulates_bands() -> None:
    state = _state()
    state = append_matured_event(
        state, _matured(MaturedCategoryKind.RESOLVED, 1, OutcomeLabel.HARMFUL)
    )
    state = append_matured_event(
        state, _matured(MaturedCategoryKind.RESOLVED, 2, OutcomeLabel.CORRECT)
    )
    state = append_matured_event(
        state, _matured(MaturedCategoryKind.TERMINAL_UNRESOLVED, None, None)
    )

    resolved_harmful = 1
    resolved_correct = 1
    unresolved = 1
    expected_counts = (resolved_harmful, 0, 0, resolved_correct, unresolved)
    assert state.matured_count == sum(expected_counts)
    assert state.resolved_count == resolved_harmful + resolved_correct
    assert state.unresolved_count == unresolved
    assert state.canonical_count_vector == expected_counts


def test_append_matured_event_rejects_foreign_identity() -> None:
    state = _state()
    foreign = MaturedEvent(
        event_id=EventId("e1"),
        identity=LedgerIdentity(
            client_id=ClientId("other"),
            action_channel_id=ActionChannelId("channel"),
            epoch_id=EpochId("epoch"),
        ),
        maturity_age_unit=1.0,
        category=MaturedCategory(
            kind=MaturedCategoryKind.TERMINAL_UNRESOLVED,
            band_index=None,
            correctness_label=None,
        ),
    )
    with pytest.raises(DataIntegrityError, match="foreign"):
        _ = append_matured_event(state, foreign)


def test_append_matured_event_rejects_out_of_range_band() -> None:
    state = _state(band_count=2)
    out_of_range = MaturedCategory.model_construct(
        kind=MaturedCategoryKind.RESOLVED,
        band_index=3,
        correctness_label=OutcomeLabel.CORRECT,
    )
    event = MaturedEvent(
        event_id=EventId("e1"),
        identity=_identity(),
        maturity_age_unit=1.0,
        category=out_of_range,
    )
    with pytest.raises(DataIntegrityError, match="inconsistent with the partition"):
        _ = append_matured_event(state, event)


def test_append_matured_event_rejects_unknown_label() -> None:
    state = _state()
    unknown = MaturedCategory.model_construct(
        kind=MaturedCategoryKind.RESOLVED,
        band_index=1,
        correctness_label=2,
    )
    event = MaturedEvent(
        event_id=EventId("e1"),
        identity=_identity(),
        maturity_age_unit=1.0,
        category=unknown,
    )
    with pytest.raises(InvalidScientificDataError, match="binary correctness label"):
        _ = append_matured_event(state, event)


def test_accumulate_matured_events_sums_over_sequence() -> None:
    partition = build_partition(2, 2, 8.0)
    events = (
        _matured(MaturedCategoryKind.RESOLVED, 1, OutcomeLabel.HARMFUL),
        _matured(MaturedCategoryKind.TERMINAL_UNRESOLVED, None, None),
    )
    state = accumulate_matured_events(_identity(), partition, events)
    assert state.canonical_count_vector == (1, 0, 0, 0, 1)
