from datetime import UTC, datetime

import pytest

from trajcert.data.integrity import LedgerIntegrityError
from trajcert.data.ledger import ActionRecord, Adjudication, mature_ledger
from trajcert.data.partitions import AnalysisPartition
from trajcert.domain.identity import LocalCertificateIdentity


def action(event_id: str, *, adjudication: Adjudication | None = None) -> ActionRecord:
    return ActionRecord(
        event_id=event_id,
        identity=LocalCertificateIdentity(
            client_id="client-1", action_channel_id="automatic", epoch_id="epoch-1"
        ),
        issued_at=datetime(2026, 1, 1, tzinfo=UTC),
        terminal_horizon=8,
        adjudication=adjudication,
    )


def test_maturation_is_fixed_horizon_and_lexically_ordered() -> None:
    now = datetime(2026, 1, 9, tzinfo=UTC)
    records = (action("event-b"), action("event-a"))

    matured = mature_ledger(records, AnalysisPartition((8,)), now)

    assert [entry.action.event_id for entry in matured] == ["event-a", "event-b"]
    assert all(not entry.category.resolved for entry in matured)


def test_ledger_rejects_duplicate_and_late_finite_adjudication() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    partition = AnalysisPartition((8,))
    with pytest.raises(LedgerIntegrityError, match="duplicate"):
        mature_ledger((action("event-a"), action("event-a")), partition, now)

    late = Adjudication(datetime(2026, 1, 10, tzinfo=UTC), harmful=True)
    with pytest.raises(LedgerIntegrityError, match="after terminal"):
        mature_ledger((action("event-a", adjudication=late),), partition, now)


def test_ledger_rejects_adjudication_before_issue() -> None:
    before_issue = Adjudication(datetime(2025, 12, 31, tzinfo=UTC), harmful=False)
    with pytest.raises(LedgerIntegrityError, match="before issue"):
        action("event-a", adjudication=before_issue)
