from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.unit.conftest import ledger_event, ledger_identity
from trajcert.data.ledger import EventLedger, LedgerEvent, LedgerIdentity
from trajcert.exceptions import DataIntegrityError
from trajcert.types import ActionChannelId, ClientId, EpochId, EventId, OutcomeLabel


def test_event_identity_matches_ledger_identity() -> None:
    event = ledger_event("e1")
    assert event.identity == ledger_identity()
    assert event.identity == LedgerIdentity(
        client_id=event.client_id,
        action_channel_id=event.action_channel_id,
        epoch_id=event.epoch_id,
    )


def test_maturity_age_unit_is_issue_plus_horizon() -> None:
    issue = 1.5
    horizon = 8.0
    assert ledger_event("e1", issue=issue).maturity_age_unit == issue + horizon


def test_maturity_guard_rejects_negative_horizon() -> None:
    invalid = LedgerEvent.model_construct(
        event_id=EventId("e1"),
        client_id=ClientId("client"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
        issue_age_unit=2.0,
        terminal_horizon=-1.0,
        adjudication_completion_age=None,
        correctness_label=None,
    )
    with pytest.raises(DataIntegrityError, match="maturity"):
        _ = invalid.maturity_age_unit


@pytest.mark.parametrize(
    ("issue", "completion", "label", "message", "raises"),
    [
        (0.0, None, None, "", False),
        (0.0, None, OutcomeLabel.CORRECT, "terminal-unresolved", True),
        (0.0, 2.0, None, "requires a correctness label", True),
        (2.0, 0.5, OutcomeLabel.CORRECT, "cannot precede issue", True),
        (0.0, 9.0, OutcomeLabel.CORRECT, "after the stored terminal horizon", True),
        (0.0, 2.0, OutcomeLabel.CORRECT, "", False),
        (0.0, 8.0, OutcomeLabel.HARMFUL, "", False),
    ],
)
def test_adjudication_validation(
    issue: float,
    completion: float | None,
    label: OutcomeLabel | None,
    message: str,
    raises: bool,
) -> None:
    if raises:
        with pytest.raises(DataIntegrityError, match=message):
            _ = ledger_event("e1", issue=issue, completion=completion, label=label)
    else:
        event = ledger_event("e1", issue=issue, completion=completion, label=label)
        assert event.adjudication_completion_age == completion
        assert event.correctness_label == label


def test_ledger_sorts_and_deduplicates_event_ids() -> None:
    identity = ledger_identity()
    ledger = EventLedger(identity=identity, events=(ledger_event("b"), ledger_event("a")))
    assert tuple(event.event_id for event in ledger.events) == ("a", "b")
    events = (ledger_event("x"), ledger_event("x"))
    with pytest.raises(DataIntegrityError, match="duplicate"):
        _ = EventLedger(identity=identity, events=events)


def test_ledger_rejects_foreign_event_identity() -> None:
    foreign = LedgerEvent(
        event_id=EventId("e1"),
        client_id=ClientId("other"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
        issue_age_unit=0.0,
        terminal_horizon=8.0,
        adjudication_completion_age=2.0,
        correctness_label=OutcomeLabel.CORRECT,
    )
    identity = ledger_identity()
    with pytest.raises(DataIntegrityError, match="identity"):
        _ = EventLedger(identity=identity, events=(foreign,))


def test_event_ledger_construction_returns_sorted_ledger() -> None:
    identity = ledger_identity()
    ledger = EventLedger(identity=identity, events=(ledger_event("z"), ledger_event("y")))
    assert ledger.identity == identity
    assert tuple(event.event_id for event in ledger.events) == ("y", "z")


def test_ledger_identity_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _ = LedgerIdentity.model_validate(
            {
                "client_id": "c",
                "action_channel_id": "a",
                "epoch_id": "e",
                "extra": 1,
            }
        )
