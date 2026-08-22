from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from trajcert.data.integrity import LedgerIntegrityError
from trajcert.data.partitions import AnalysisPartition
from trajcert.domain.identity import Identifier, LocalCertificateIdentity


@dataclass(frozen=True, slots=True)
class Adjudication:
    timestamp: datetime
    harmful: bool


@dataclass(frozen=True, slots=True)
class ActionRecord:
    event_id: Identifier
    identity: LocalCertificateIdentity
    issued_at: datetime
    terminal_horizon: int
    adjudication: Adjudication | None = None

    def __post_init__(self) -> None:
        if self.terminal_horizon <= 0:
            raise LedgerIntegrityError("terminal horizon must be positive")
        if self.adjudication is not None and self.adjudication.timestamp < self.issued_at:
            raise LedgerIntegrityError("adjudication before issue")

    @property
    def maturity_timestamp(self) -> datetime:
        return self.issued_at + timedelta(days=self.terminal_horizon)


@dataclass(frozen=True, slots=True)
class MaturedCategory:
    band: int | None
    harmful: bool | None

    def __post_init__(self) -> None:
        if (self.band is None) != (self.harmful is None):
            raise LedgerIntegrityError(
                "resolved category requires both a band and correctness label"
            )
        if self.band is not None and self.band <= 0:
            raise LedgerIntegrityError("resolved category band must be positive")

    @property
    def resolved(self) -> bool:
        return self.band is not None


@dataclass(frozen=True, slots=True)
class MaturedAction:
    action: ActionRecord
    category: MaturedCategory


def mature_action(
    action: ActionRecord, partition: AnalysisPartition, now: datetime
) -> MaturedAction | None:
    if partition.terminal_horizon != action.terminal_horizon:
        raise LedgerIntegrityError("action terminal horizon disagrees with partition")
    if now < action.maturity_timestamp:
        return None
    if action.adjudication is None:
        return MaturedAction(action, MaturedCategory(None, None))
    if action.adjudication.timestamp > action.maturity_timestamp:
        raise LedgerIntegrityError("finite adjudication occurs after terminal horizon")
    age = (action.adjudication.timestamp - action.issued_at).days
    band = partition.band_for_age(age)
    if band is None:
        raise LedgerIntegrityError("finite adjudication has no partition band")
    return MaturedAction(action, MaturedCategory(band, action.adjudication.harmful))


def mature_ledger(
    actions: tuple[ActionRecord, ...], partition: AnalysisPartition, now: datetime
) -> tuple[MaturedAction, ...]:
    event_ids = tuple(action.event_id for action in actions)
    if len(set(event_ids)) != len(event_ids):
        raise LedgerIntegrityError("duplicate event_id")
    matured_actions: list[MaturedAction] = []
    for action in actions:
        matured_action = mature_action(action, partition, now)
        if matured_action is not None:
            matured_actions.append(matured_action)
    return tuple(
        sorted(
            matured_actions,
            key=lambda entry: (entry.action.maturity_timestamp, entry.action.event_id),
        )
    )
