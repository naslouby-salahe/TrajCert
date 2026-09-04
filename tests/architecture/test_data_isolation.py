from __future__ import annotations

import pytest

from trajcert.data.ledger import LedgerIdentity
from trajcert.data.maturity import (
    MaturedCategory,
    MaturedCategoryKind,
    MaturedEvent,
)
from trajcert.data.partitions import build_partition
from trajcert.exceptions import DataIntegrityError
from trajcert.inference.categorical import (
    CategoricalState,
    append_matured_event,
    initialize_categorical_state,
)
from trajcert.types import ActionChannelId, ClientId, EpochId, EventId, OutcomeLabel


def _identity(client: str) -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId(client),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
    )


def _state(identity: LedgerIdentity) -> CategoricalState:
    partition = build_partition(2, 2, 8.0)
    return initialize_categorical_state(identity, partition)


def _matured_event(identity: LedgerIdentity) -> MaturedEvent:
    return MaturedEvent(
        event_id=EventId("event-1"),
        identity=identity,
        maturity_age_unit=8.0,
        category=MaturedCategory(
            kind=MaturedCategoryKind.RESOLVED,
            band_index=1,
            correctness_label=OutcomeLabel.CORRECT,
        ),
    )


def test_inference_stream_rejects_foreign_client_identity() -> None:
    state = _state(_identity("target-client"))
    foreign = _matured_event(_identity("foreign-client"))
    with pytest.raises(DataIntegrityError, match="foreign"):
        _ = append_matured_event(state, foreign)


def test_inference_stream_preserves_single_ledger_identity() -> None:
    identity = _identity("target-client")
    state = _state(identity)
    updated = append_matured_event(state, _matured_event(identity))
    assert updated.identity == identity
    assert updated.matured_count == 1
