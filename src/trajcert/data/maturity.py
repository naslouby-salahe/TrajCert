from __future__ import annotations

from bisect import bisect_left
from enum import StrEnum
from typing import Self

from pydantic import model_validator

from trajcert.data.ledger import EventLedger, LedgerEvent, LedgerIdentity
from trajcert.data.partitions import TrajectoryPartition
from trajcert.exceptions import DataIntegrityError
from trajcert.types import AgeUnit, BandIndex, DomainModel, EventId, OutcomeLabel


class MaturedCategoryKind(StrEnum):
    RESOLVED = "RESOLVED"
    TERMINAL_UNRESOLVED = "TERMINAL_UNRESOLVED"


class MaturedCategory(DomainModel):
    kind: MaturedCategoryKind
    band_index: BandIndex | None
    correctness_label: OutcomeLabel | None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.kind is MaturedCategoryKind.TERMINAL_UNRESOLVED:
            if self.band_index is not None or self.correctness_label is not None:
                raise DataIntegrityError(
                    "terminal-unresolved category cannot contain band or correctness values"
                )
            return self
        if self.band_index is None or self.correctness_label is None:
            raise DataIntegrityError("resolved category requires band and correctness values")
        return self


class MaturedEvent(DomainModel):
    event_id: EventId
    identity: LedgerIdentity
    maturity_age_unit: AgeUnit
    category: MaturedCategory


def mature_event(event: LedgerEvent, partition: TrajectoryPartition) -> MaturedEvent:
    if event.terminal_horizon != partition.terminal_horizon:
        raise DataIntegrityError("event terminal horizon is inconsistent with the partition")
    completion = event.adjudication_completion_age
    if completion is None:
        category = MaturedCategory(
            kind=MaturedCategoryKind.TERMINAL_UNRESOLVED,
            band_index=None,
            correctness_label=None,
        )
    else:
        elapsed = completion - event.issue_age_unit
        position = bisect_left(partition.boundaries, elapsed)
        if position >= partition.band_count:
            raise DataIntegrityError("finite adjudication is inconsistent with the partition")
        category = MaturedCategory(
            kind=MaturedCategoryKind.RESOLVED,
            band_index=position + 1,
            correctness_label=event.correctness_label,
        )
    return MaturedEvent(
        event_id=event.event_id,
        identity=event.identity,
        maturity_age_unit=event.maturity_age_unit,
        category=category,
    )


def mature_ledger(ledger: EventLedger, partition: TrajectoryPartition) -> tuple[MaturedEvent, ...]:
    matured = (mature_event(event, partition) for event in ledger.events)
    return tuple(
        sorted(
            matured,
            key=lambda event: (event.maturity_age_unit, event.event_id),
        )
    )
