from __future__ import annotations

from typing import Self

from pydantic import field_validator, model_validator

from trajcert.exceptions import DataIntegrityError
from trajcert.types import (
    ActionChannelId,
    ClientId,
    DomainModel,
    EpochId,
    EventId,
    NonNegativeFloat,
    OutcomeLabel,
    TerminalHorizon,
)


class LedgerIdentity(DomainModel):
    client_id: ClientId
    action_channel_id: ActionChannelId
    epoch_id: EpochId


class LedgerEvent(DomainModel):
    event_id: EventId
    client_id: ClientId
    action_channel_id: ActionChannelId
    epoch_id: EpochId
    issue_age_unit: NonNegativeFloat # TODO: Consider using a proper alias type for adjudication completion age or whatever already exists with actually fits this
    terminal_horizon: TerminalHorizon
    adjudication_completion_age: NonNegativeFloat | None # TODO: Consider using a proper alias type for adjudication completion age or whatever already exists with actually fits this
    correctness_label: OutcomeLabel | None

    @model_validator(mode="after")
    def validate_adjudication(self) -> Self:
        completion = self.adjudication_completion_age
        label = self.correctness_label
        if completion is None:
            if label is not None:
                raise DataIntegrityError(
                    "terminal-unresolved event cannot carry a correctness label"
                )
            return self
        if label is None:
            raise DataIntegrityError("finite adjudication requires a correctness label")
        if completion < self.issue_age_unit:
            raise DataIntegrityError("adjudication cannot precede issue")
        if completion > self.maturity_age_unit:
            raise DataIntegrityError(
                "finite adjudication cannot occur after the stored terminal horizon"
            )
        return self

    @property
    def identity(self) -> LedgerIdentity:
        return LedgerIdentity(
            client_id=self.client_id,
            action_channel_id=self.action_channel_id,
            epoch_id=self.epoch_id,
        )

    @property
    def maturity_age_unit(self) -> NonNegativeFloat: # TODO: Consider using a proper alias type for maturity age unit or whatever already exists with actually fits this
        maturity = self.issue_age_unit + self.terminal_horizon
        if maturity < self.issue_age_unit:
            raise DataIntegrityError("maturity cannot precede issue")
        return maturity


class EventLedger(DomainModel):
    identity: LedgerIdentity
    events: tuple[LedgerEvent, ...]

    @field_validator("events")
    @classmethod
    def validate_events(cls, events: tuple[LedgerEvent, ...]) -> tuple[LedgerEvent, ...]:
        identifiers = tuple(event.event_id for event in events)
        if len(identifiers) != len(set(identifiers)):
            raise DataIntegrityError("ledger contains duplicate event_id values")
        return tuple(sorted(events, key=lambda event: str(event.event_id)))

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if any(event.identity != self.identity for event in self.events):
            raise DataIntegrityError(
                "every ledger event must belong to the ledger client/channel/epoch identity"
            )
        return self


def build_ledger(identity: LedgerIdentity, events: tuple[LedgerEvent, ...]) -> EventLedger:
    return EventLedger(identity=identity, events=events)
