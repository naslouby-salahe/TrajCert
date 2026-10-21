from __future__ import annotations

import pytest

from tests.unit.conftest import ledger_event, ledger_identity
from trajcert.data.ledger import EventLedger
from trajcert.data.maturity import (
    MaturedCategory,
    MaturedCategoryKind,
    mature_event,
    mature_ledger,
)
from trajcert.data.partitions import build_partition
from trajcert.exceptions import DataIntegrityError
from trajcert.types import EventId, OutcomeLabel


@pytest.mark.parametrize(
    ("payload", "valid"),
    [
        ({"kind": "RESOLVED", "band_index": 1, "correctness_label": 0}, True),
        (
            {"kind": "TERMINAL_UNRESOLVED", "band_index": None, "correctness_label": None},
            True,
        ),
        (
            {"kind": "TERMINAL_UNRESOLVED", "band_index": 1, "correctness_label": None},
            False,
        ),
        ({"kind": "RESOLVED", "band_index": None, "correctness_label": 0}, False),
        ({"kind": "RESOLVED", "band_index": 1, "correctness_label": None}, False),
    ],
)
def test_matured_category_shape(payload: dict[str, object], valid: bool) -> None:
    if valid:
        category = MaturedCategory.model_validate(payload)
        assert category.kind in (
            MaturedCategoryKind.RESOLVED,
            MaturedCategoryKind.TERMINAL_UNRESOLVED,
        )
    else:
        with pytest.raises(DataIntegrityError):
            _ = MaturedCategory.model_validate(payload)


def test_mature_event_marks_terminal_unresolved() -> None:
    partition = build_partition(4, 4, 8.0)
    event = ledger_event("e1", completion=None, label=None)
    matured = mature_event(event, partition)
    assert matured.category.kind is MaturedCategoryKind.TERMINAL_UNRESOLVED
    assert matured.category.band_index is None
    assert matured.category.correctness_label is None
    assert matured.maturity_age_unit == partition.terminal_horizon
    assert matured.event_id == EventId("e1")
    assert matured.identity == ledger_identity()


def test_mature_event_resolves_band_and_label() -> None:
    partition = build_partition(4, 4, 8.0)
    elapsed = 5.0
    event = ledger_event("e1", issue=0.0, completion=elapsed, label=OutcomeLabel.HARMFUL)
    matured = mature_event(event, partition)
    expected_band = 1 + sum(1 for boundary in partition.boundaries if boundary <= elapsed)
    assert matured.category.kind is MaturedCategoryKind.RESOLVED
    assert matured.category.band_index == expected_band
    assert matured.category.correctness_label is OutcomeLabel.HARMFUL


def test_mature_event_rejects_horizon_mismatch() -> None:
    partition = build_partition(4, 4, 8.0)
    event = ledger_event("e1", horizon=6.0)
    with pytest.raises(DataIntegrityError, match="horizon"):
        _ = mature_event(event, partition)


def test_mature_event_rejects_out_of_band_completion() -> None:
    partition = build_partition(4, 4, 8.0)
    issue = 8.005
    completion = issue + 8.0
    event = ledger_event("e1", issue=issue, completion=completion, label=OutcomeLabel.CORRECT)
    with pytest.raises(DataIntegrityError, match="inconsistent with the partition"):
        _ = mature_event(event, partition)


def test_mature_ledger_sorts_by_maturity_then_id() -> None:
    partition = build_partition(4, 4, 8.0)
    late = ledger_event("late", issue=2.0, completion=3.0)
    early = ledger_event("early", issue=0.0, completion=1.0)
    ledger = EventLedger(identity=ledger_identity(), events=(late, early))
    matured = mature_ledger(ledger, partition)
    assert tuple(event.event_id for event in matured) == ("early", "late")
