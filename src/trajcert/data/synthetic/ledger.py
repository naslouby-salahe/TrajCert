from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from trajcert.data.ledger import ActionRecord, Adjudication, MaturedCategory
from trajcert.data.synthetic.generator import SyntheticEvent
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw
from trajcert.domain.enums import DatasetEligibilityStatus, DatasetKind
from trajcert.domain.identity import LocalCertificateIdentity
from trajcert.domain.manifests import DatasetManifest
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import atomic_write_bytes

SYNTHETIC_CLIENT_ID = "synthetic-client"
SYNTHETIC_ACTION_CHANNEL_ID = "automatic-action"
SYNTHETIC_LEDGER_ROOT_RELATIVE_PATH = Path("outputs/preprocessing/prepared/synthetic_ledgers")


@dataclass(frozen=True, slots=True)
class PreparedSyntheticLedger:
    law_slug: str
    stream_index: int
    records: tuple[ActionRecord, ...]
    dataset_manifest: DatasetManifest
    ledger_checksum: str


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
    if any(
        event.resolution_band is not None and event.resolution_band > law.resolved_band_count
        for event in events
    ):
        raise ValueError("synthetic event resolution band exceeds the law band count")
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


def prepare_synthetic_ledger(
    law: SyntheticTrajectoryLaw,
    stream_index: int,
    events: tuple[SyntheticEvent, ...],
    epoch_start: datetime,
    scientific_comparison_guard: float,
) -> PreparedSyntheticLedger:
    if scientific_comparison_guard < 0:
        raise ValueError("scientific comparison guard must be nonnegative")
    observable_law = law.observable_law()
    probabilities = (
        *observable_law.harmful_masses,
        *observable_law.correct_masses,
        observable_law.unresolved_mass,
    )
    if any(not 0 <= probability <= 1 for probability in probabilities):
        raise ValueError("synthetic probabilities must lie in [0, 1]")
    if abs(sum(probabilities) - 1) > scientific_comparison_guard:
        raise ValueError("synthetic probabilities must sum to one within comparison guard")
    records = tuple(
        sorted(
            synthetic_ledger_records(law, stream_index, events, epoch_start),
            key=lambda record: record.event_id,
        )
    )
    payload = canonical_json_bytes(_ledger_payload(records))
    checksum = sha256(payload).hexdigest()
    law_payload = canonical_json_bytes(_law_payload(law))
    source_checksum = sha256(law_payload).hexdigest()
    manifest = DatasetManifest(
        dataset_name=law.name,
        dataset_kind=DatasetKind.SYNTHETIC,
        generator_name="trajcert.data.synthetic.generator",
        generator_code_digest=source_checksum,
        source_version="synthetic-law-v1",
        source_checksum=source_checksum,
        event_semantics="IID sampled (L,J) trajectory events",
        label_semantics="L is revealed only for finite J",
        time_semantics="issue and maturity ages are fixed synthetic age units",
        terminal_horizon=_integral_age_unit(law.terminal_horizon),
        finest_partition_name=f"{law.resolved_band_count}-band partition",
        number_of_categories=2 * law.resolved_band_count + 1,
        documented_expected_structure=law_payload.decode("utf-8"),
        observed_raw_structure=canonical_json_bytes(
            {"event_count": len(records), "stream_index": stream_index}
        ).decode("utf-8"),
        field_mapping_json=canonical_json_bytes(
            {
                "correctness_label": "sampled L when finite J",
                "resolution_band": "sampled finite J band",
                "terminal": "unresolved J=infinity",
            }
        ).decode("utf-8"),
        population_parameters=law_payload.decode("utf-8"),
        known_full_law=True,
        known_theta=law.theta,
        known_observable_probabilities=canonical_json_bytes(
            {"probabilities": probabilities}
        ).decode("utf-8"),
        preprocessing_digest=checksum,
        eligibility_status=DatasetEligibilityStatus.ELIGIBLE,
    )
    return PreparedSyntheticLedger(
        synthetic_law_slug(law.name), stream_index, records, manifest, checksum
    )


def prepared_synthetic_ledger_relative_path(prepared: PreparedSyntheticLedger) -> Path:
    return (
        SYNTHETIC_LEDGER_ROOT_RELATIVE_PATH
        / f"law={prepared.law_slug}"
        / f"stream={prepared.stream_index:06d}.json"
    )


def write_prepared_synthetic_ledger(
    project_root: Path,
    prepared: PreparedSyntheticLedger,
) -> str:
    payload = canonical_json_bytes(_ledger_payload(prepared.records))
    digest = atomic_write_bytes(
        project_root / prepared_synthetic_ledger_relative_path(prepared),
        payload,
        lambda candidate: _validate_prepared_synthetic_ledger(candidate, prepared),
    )
    if digest != prepared.ledger_checksum:
        raise ValueError("prepared synthetic ledger checksum does not match its canonical payload")
    return digest


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


def _law_payload(law: SyntheticTrajectoryLaw) -> dict[str, float | int | str]:
    return {
        "K": law.resolved_band_count,
        "lambda0": law.lambda0,
        "lambda1": law.lambda1,
        "name": law.name,
        "q0": law.q0,
        "q1": law.q1,
        "terminal_horizon": law.terminal_horizon,
        "theta": law.theta,
    }


def _ledger_payload(records: tuple[ActionRecord, ...]) -> tuple[dict[str, JSONValue], ...]:
    return tuple(
        {
            "action_channel_id": record.identity.action_channel_id,
            "adjudication_completion_age": (
                None
                if record.adjudication is None
                else (record.adjudication.timestamp - record.issued_at).days
            ),
            "client_id": record.identity.client_id,
            "correctness_label": None
            if record.adjudication is None
            else record.adjudication.harmful,
            "epoch_id": record.identity.epoch_id,
            "event_id": record.event_id,
            "issue_age_unit": record.issued_at.isoformat(),
            "maturity_age_unit": record.maturity_timestamp.isoformat(),
        }
        for record in records
    )


def _validate_prepared_synthetic_ledger(
    payload: bytes,
    prepared: PreparedSyntheticLedger,
) -> None:
    if payload != canonical_json_bytes(_ledger_payload(prepared.records)):
        raise ValueError("prepared synthetic ledger payload is not canonical")


__all__ = [
    "SYNTHETIC_ACTION_CHANNEL_ID",
    "SYNTHETIC_CLIENT_ID",
    "SYNTHETIC_LEDGER_ROOT_RELATIVE_PATH",
    "ActionRecord",
    "MaturedCategory",
    "PreparedSyntheticLedger",
    "prepare_synthetic_ledger",
    "prepared_synthetic_ledger_relative_path",
    "synthetic_law_slug",
    "synthetic_ledger_records",
    "write_prepared_synthetic_ledger",
]
