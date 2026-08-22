from __future__ import annotations

import re
from datetime import datetime, timedelta

from trajcert.data.ledger import ActionRecord, Adjudication, MaturedCategory
from trajcert.data.synthetic.generator import SyntheticEvent
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw
from trajcert.domain.identity import LocalCertificateIdentity

SYNTHETIC_CLIENT_ID = "synthetic-client"
SYNTHETIC_ACTION_CHANNEL_ID = "automatic-action"


def synthetic_law_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError("synthetic law name must produce a nonempty slug")
    return slug


def synthetic_ledger_records(
    law: SyntheticTrajectoryLaw,
    stream_index: int,
    events: tuple[SyntheticEvent, ...],
    epoch_start: datetime,
) -> tuple[ActionRecord, ...]:
    if stream_index < 0:
        raise ValueError("synthetic stream index must be nonnegative")
    if any(event.action_index != index for index, event in enumerate(events)):
        raise ValueError("synthetic events must have contiguous canonical action indices")
    horizon = _integral_age_unit(law.terminal_horizon)
    law_slug = synthetic_law_slug(law.name)
    identity = LocalCertificateIdentity(
        client_id=SYNTHETIC_CLIENT_ID,
        action_channel_id=SYNTHETIC_ACTION_CHANNEL_ID,
        epoch_id=f"{law_slug}::static-epoch",
    )
    return tuple(
        _synthetic_action_record(law, event, stream_index, epoch_start, horizon, law_slug, identity)
        for event in events
    )


def _synthetic_action_record(
    law: SyntheticTrajectoryLaw,
    event: SyntheticEvent,
    stream_index: int,
    epoch_start: datetime,
    horizon: int,
    law_slug: str,
    identity: LocalCertificateIdentity,
) -> ActionRecord:
    issued_at = epoch_start + timedelta(days=event.action_index)
    adjudication = None
    if event.resolution_band is not None:
        completion_age = _integral_age_unit(law.band_horizons()[event.resolution_band - 1])
        adjudication = Adjudication(issued_at + timedelta(days=completion_age), event.label)
    return ActionRecord(
        event_id=f"{law_slug}::S{stream_index:06d}::E{event.action_index:06d}",
        identity=identity,
        issued_at=issued_at,
        terminal_horizon=horizon,
        adjudication=adjudication,
    )


def _integral_age_unit(value: float) -> int:
    if not value.is_integer():
        raise ValueError("synthetic ledger requires integral age-unit horizons")
    return int(value)


__all__ = [
    "SYNTHETIC_ACTION_CHANNEL_ID",
    "SYNTHETIC_CLIENT_ID",
    "ActionRecord",
    "MaturedCategory",
    "synthetic_law_slug",
    "synthetic_ledger_records",
]
