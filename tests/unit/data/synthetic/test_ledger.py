from datetime import UTC, datetime, timedelta

import pytest

from trajcert.data.synthetic.generator import SyntheticEvent
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw
from trajcert.data.synthetic.ledger import synthetic_ledger_records


def test_synthetic_ledger_uses_canonical_ids_and_terminal_null_semantics() -> None:
    law = SyntheticTrajectoryLaw("Test law", 0.5, 0.2, 0.1, 0.0, 0.0, 2, 10.0)
    records = synthetic_ledger_records(
        law,
        3,
        (SyntheticEvent(0, True, 1, True), SyntheticEvent(1, False, None, True)),
        datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert records[0].event_id == "test-law::S000003::E000000"
    assert records[0].identity.epoch_id == "test-law::static-epoch"
    assert records[0].adjudication is not None
    assert records[1].adjudication is None
    assert records[1].maturity_timestamp == records[1].issued_at + timedelta(days=10)


def test_synthetic_ledger_rejects_noncanonical_duplicate_event_indices() -> None:
    law = SyntheticTrajectoryLaw("Test law", 0.5, 0.2, 0.1, 0.0, 0.0, 2, 10.0)

    with pytest.raises(ValueError, match="contiguous canonical"):
        synthetic_ledger_records(
            law,
            0,
            (SyntheticEvent(0, True, 1, True), SyntheticEvent(0, False, 1, True)),
            datetime(2026, 1, 1, tzinfo=UTC),
        )
