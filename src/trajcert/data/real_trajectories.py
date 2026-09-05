from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path

import numpy as np
import polars as pl

from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import DataIntegrityError, InvalidScientificDataError
from trajcert.math.information import observed_timing_information
from trajcert.types import (
    AgeUnit,
    AnnotatorExpertise,
    BandCount,
    ClientId,
    Count,
    DatasetChecksumHex,
    DatasetColumnName,
    DatasetFilename,
    DatasetVersionTag,
    DomainModel,
    HitlIotDeviceType,
    InformationNats,
    Probability,
    RawDatasetRoot,
    RealTrajectoryDatasetName,
    RealTrajectoryExclusionReason,
    RealTrajectoryStratumKind,
    RealTrajectoryStratumValue,
    ToleranceValue,
)

HITL_IOT_DOI = DatasetVersionTag("10.5281/zenodo.17862334")
HITL_IOT_DATASET_FILENAME = "HITL-IoT_dataset.csv"
HITL_IOT_CHECKSUMS_FILENAME = "HITL-IoT_checksums.txt"
HITL_IOT_EXPECTED_DATASET_SHA256 = DatasetChecksumHex(
    "162121f804c2e177dddae4fb9c91e70045aaccaa6e918adde25fc7964acb0c04"
)

HITL_IOT_DEVICE_NAMES: tuple[ClientId, ...] = tuple(
    ClientId(name)
    for name in (
        "camera_21",
        "camera_22",
        "camera_26",
        "doorbell_30",
        "doorbell_31",
        "speaker_23",
        "speaker_24",
        "speaker_27",
        "thermostat_20",
        "thermostat_25",
        "tv_28",
        "tv_29",
    )
)

_RAW_COLUMNS = (
    "timestamp",
    "src_mac",
    "dst_ip",
    "src_port",
    "dst_port",
    "device_name",
    "device_type",
    "is_attack",
    "ml_prediction",
    "human_reviewed",
    "human_decision",
    "human_confidence",
    "decision_time",
    "annotator_id",
)

_FLOW_IDENTITY_COLUMNS = ("timestamp", "src_mac", "dst_ip", "src_port", "dst_port")

HITL_IOT_EXPECTED_SCHEMA: tuple[str, ...] = (
    "timestamp",
    "hour",
    "day_of_week",
    "is_weekend",
    "src_ip",
    "dst_ip",
    "src_mac",
    "dst_mac",
    "packet_size",
    "ttl",
    "is_internal_dst",
    "is_localhost",
    "protocol",
    "src_port",
    "dst_port",
    "is_well_known_port",
    "is_registered_port",
    "is_dynamic_port",
    "device_name",
    "device_type",
    "device_thermostat",
    "device_camera",
    "device_speaker",
    "duration",
    "bytes_sent",
    "bytes_received",
    "bytes_ratio",
    "bytes_per_second",
    "packet_rate",
    "is_business_hours",
    "is_night",
    "protocol_tcp",
    "protocol_udp",
    "connection_frequency",
    "baseline_deviation",
    "bytes_sent_mean_5",
    "bytes_sent_std_5",
    "bytes_sent_mean_10",
    "bytes_sent_std_10",
    "bytes_sent_mean_20",
    "bytes_sent_std_20",
    "connection_frequency_5",
    "connection_frequency_10",
    "is_attack",
    "attack_type",
    "risk_score",
    "ml_confidence",
    "ml_prediction",
    "human_reviewed",
    "human_decision",
    "human_confidence",
    "decision_time",
    "ml_human_agreement",
    "annotator_id",
)


class RealTrajectorySchemaValidation(DomainModel):
    expected_columns: tuple[DatasetColumnName, ...]
    observed_columns: tuple[DatasetColumnName, ...]
    passed: bool


def validate_dataset_schema(dataset_root: RawDatasetRoot) -> RealTrajectorySchemaValidation:
    dataset_path = Path(dataset_root) / HITL_IOT_DATASET_FILENAME
    observed = tuple(
        DatasetColumnName(name) for name in pl.scan_csv(dataset_path).collect_schema().names()
    )
    expected = tuple(DatasetColumnName(name) for name in HITL_IOT_EXPECTED_SCHEMA)
    passed = observed == expected
    if not passed:
        raise InvalidScientificDataError(
            "HITL-IoT dataset schema does not match the pinned column contract; "
            + f"expected {len(expected)} columns, observed {len(observed)}"
        )
    return RealTrajectorySchemaValidation(
        expected_columns=expected, observed_columns=observed, passed=passed
    )


class RealTrajectoryDatasetProvenance(DomainModel):
    dataset_name: RealTrajectoryDatasetName
    doi: DatasetVersionTag
    dataset_filename: DatasetFilename
    dataset_sha256: DatasetChecksumHex
    total_rows: Count


class RealTrajectoryExclusionCount(DomainModel):
    reason: RealTrajectoryExclusionReason
    count: Count


class RealTrajectoryEligibilityReport(DomainModel):
    total_dataset_rows: Count
    annotated_rows: Count
    candidate_rows: Count
    eligible_rows: Count
    excluded_rows: Count
    excluded_by_reason: tuple[RealTrajectoryExclusionCount, ...]
    device_eligible_counts: tuple[tuple[ClientId, Count], ...]
    expertise_eligible_counts: tuple[tuple[AnnotatorExpertise, Count], ...]


class HitlIotEligibleEvent(DomainModel):
    device_name: ClientId
    device_type: HitlIotDeviceType
    expertise: AnnotatorExpertise
    is_attack: bool
    ml_prediction: bool
    decision_time: AgeUnit
    human_confidence: Probability


@dataclass(frozen=True, slots=True)
class RealTrajectoryCohort:
    device_name: np.ndarray
    device_type: np.ndarray
    expertise: np.ndarray
    latent_error: np.ndarray
    decision_time: np.ndarray

    @property
    def size(self) -> Count:
        return int(self.decision_time.shape[0])


class RealTrajectoryEmpiricalOracle(DomainModel):
    theta_true: Probability
    full_information_nats: InformationNats


class PreparedRealTrajectoryCohort(DomainModel):
    events: tuple[HitlIotEligibleEvent, ...]


def verify_dataset_integrity(dataset_root: RawDatasetRoot) -> RealTrajectoryDatasetProvenance:
    root = Path(dataset_root)
    dataset_path = root / HITL_IOT_DATASET_FILENAME
    checksums_path = root / HITL_IOT_CHECKSUMS_FILENAME
    if not dataset_path.is_file():
        raise DataIntegrityError(f"HITL-IoT dataset file is missing: {dataset_path}")
    actual_digest = DatasetChecksumHex(sha256(dataset_path.read_bytes()).hexdigest())
    if actual_digest != HITL_IOT_EXPECTED_DATASET_SHA256:
        raise DataIntegrityError(
            "HITL-IoT dataset checksum mismatch against the pinned Zenodo release "
            + f"({HITL_IOT_DOI}): expected {HITL_IOT_EXPECTED_DATASET_SHA256}, got {actual_digest}"
        )
    if checksums_path.is_file():
        recorded = _parse_checksums_file(checksums_path)
        expected = recorded.get(DatasetFilename(HITL_IOT_DATASET_FILENAME))
        if expected is not None and expected != actual_digest:
            raise DataIntegrityError(
                "HITL-IoT dataset checksum does not match the dataset's own checksums manifest"
            )
    total_rows = pl.scan_csv(dataset_path).select(pl.len()).collect().item()
    return RealTrajectoryDatasetProvenance(
        dataset_name=RealTrajectoryDatasetName.HITL_IOT,
        doi=HITL_IOT_DOI,
        dataset_filename=DatasetFilename(HITL_IOT_DATASET_FILENAME),
        dataset_sha256=actual_digest,
        total_rows=total_rows,
    )


def _parse_checksums_file(path: Path) -> dict[DatasetFilename, DatasetChecksumHex]:
    mapping: dict[DatasetFilename, DatasetChecksumHex] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        digest, _, filename = stripped.partition("  ")
        if not filename:
            continue
        mapping[DatasetFilename(filename.strip())] = DatasetChecksumHex(digest.strip())
    return mapping


def build_real_trajectory_eligibility(
    dataset_root: RawDatasetRoot,
) -> tuple[tuple[HitlIotEligibleEvent, ...], RealTrajectoryEligibilityReport]:
    root = Path(dataset_root)
    dataset_path = root / HITL_IOT_DATASET_FILENAME
    frame = pl.read_csv(dataset_path, columns=list(_RAW_COLUMNS))
    total_rows = frame.height
    annotated = frame.filter(pl.col("human_reviewed"))
    candidate_rows = annotated.height

    duplicate_mask = annotated.select(list(_FLOW_IDENTITY_COLUMNS)).is_duplicated()
    checks: tuple[tuple[RealTrajectoryExclusionReason, pl.Series], ...] = (
        (RealTrajectoryExclusionReason.MISSING_GROUND_TRUTH, annotated["is_attack"].is_null()),
        (
            RealTrajectoryExclusionReason.MISSING_AUTOMATIC_PREDICTION,
            annotated["ml_prediction"].is_null(),
        ),
        (
            RealTrajectoryExclusionReason.INVALID_DEVICE_IDENTITY,
            annotated["device_name"].is_null() | (annotated["device_name"].str.len_chars() == 0),
        ),
        (
            RealTrajectoryExclusionReason.INVALID_DECISION_LATENCY,
            annotated["decision_time"].is_null() | (annotated["decision_time"] <= 0.0),
        ),
        (RealTrajectoryExclusionReason.DUPLICATE_ANNOTATION, duplicate_mask),
    )
    exclusion_counts: list[RealTrajectoryExclusionCount] = [
        RealTrajectoryExclusionCount(
            reason=RealTrajectoryExclusionReason.NOT_HUMAN_ANNOTATED,
            count=total_rows - candidate_rows,
        )
    ]
    excluded_so_far = pl.Series(np.zeros(candidate_rows, dtype=bool))
    for reason, mask in checks:
        newly_excluded = mask & ~excluded_so_far
        exclusion_counts.append(
            RealTrajectoryExclusionCount(reason=reason, count=int(newly_excluded.sum()))
        )
        excluded_so_far = excluded_so_far | mask
    eligible = annotated.filter(~excluded_so_far)
    eligible_rows = eligible.height

    device_counts = tuple(
        (ClientId(row["device_name"]), int(row["len"]))
        for row in eligible.group_by("device_name").len().sort("device_name").to_dicts()
    )
    expertise_counts = tuple(
        (AnnotatorExpertise(row["annotator_id"]), int(row["len"]))
        for row in eligible.group_by("annotator_id").len().sort("annotator_id").to_dicts()
    )
    report = RealTrajectoryEligibilityReport(
        total_dataset_rows=total_rows,
        annotated_rows=candidate_rows,
        candidate_rows=candidate_rows,
        eligible_rows=eligible_rows,
        excluded_rows=candidate_rows - eligible_rows,
        excluded_by_reason=tuple(exclusion_counts),
        device_eligible_counts=device_counts,
        expertise_eligible_counts=expertise_counts,
    )
    events = tuple(
        HitlIotEligibleEvent(
            device_name=ClientId(row["device_name"]),
            device_type=HitlIotDeviceType(row["device_type"]),
            expertise=AnnotatorExpertise(row["annotator_id"]),
            is_attack=bool(row["is_attack"]),
            ml_prediction=bool(row["ml_prediction"]),
            decision_time=float(row["decision_time"]),
            human_confidence=float(row["human_confidence"]),
        )
        for row in eligible.to_dicts()
    )
    return events, report


def cohort_from_events(events: tuple[HitlIotEligibleEvent, ...]) -> RealTrajectoryCohort:
    if not events:
        raise InvalidScientificDataError("real-trajectory cohort requires at least one event")
    return RealTrajectoryCohort(
        device_name=np.array([event.device_name for event in events], dtype=object),
        device_type=np.array([event.device_type for event in events], dtype=object),
        expertise=np.array([event.expertise for event in events], dtype=object),
        latent_error=np.array(
            [event.ml_prediction != event.is_attack for event in events], dtype=bool
        ),
        decision_time=np.array([event.decision_time for event in events], dtype=np.float64),
    )


def cohort_for_stratum(
    cohort: RealTrajectoryCohort,
    stratum_kind: RealTrajectoryStratumKind,
    stratum_value: RealTrajectoryStratumValue | None,
) -> RealTrajectoryCohort:
    if stratum_kind is RealTrajectoryStratumKind.POOLED:
        return cohort
    if stratum_value is None:
        raise InvalidScientificDataError("non-pooled stratum requires a stratum value")
    if stratum_kind is RealTrajectoryStratumKind.DEVICE:
        mask = cohort.device_name == stratum_value
    elif stratum_kind is RealTrajectoryStratumKind.EXPERTISE:
        mask = cohort.expertise == stratum_value
    else:
        raise InvalidScientificDataError(f"unknown real-trajectory stratum kind: {stratum_kind}")
    if not bool(mask.any()):
        raise InvalidScientificDataError(f"stratum has no eligible events: {stratum_value}")
    return RealTrajectoryCohort(
        device_name=cohort.device_name[mask],
        device_type=cohort.device_type[mask],
        expertise=cohort.expertise[mask],
        latent_error=cohort.latent_error[mask],
        decision_time=cohort.decision_time[mask],
    )


def finest_observable_summary(
    cohort: RealTrajectoryCohort,
    horizon_seconds: AgeUnit,
    finest_bands: BandCount,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    if horizon_seconds <= 0.0 or not isfinite(horizon_seconds):
        raise InvalidScientificDataError("real-trajectory horizon must be finite and positive")
    total = cohort.size
    resolved = cohort.decision_time <= horizon_seconds
    band_width = horizon_seconds / finest_bands
    band_index = np.minimum(
        np.floor(cohort.decision_time / band_width).astype(np.int64), finest_bands - 1
    )
    harmful_by_band = np.zeros(finest_bands, dtype=np.float64)
    correct_by_band = np.zeros(finest_bands, dtype=np.float64)
    resolved_harmful = resolved & cohort.latent_error
    resolved_correct = resolved & ~cohort.latent_error
    harmful_counts = np.bincount(band_index[resolved_harmful], minlength=finest_bands)
    correct_counts = np.bincount(band_index[resolved_correct], minlength=finest_bands)
    harmful_by_band[:] = harmful_counts[:finest_bands] / total
    correct_by_band[:] = correct_counts[:finest_bands] / total
    unresolved_mass = float((~resolved).sum()) / total
    partition = build_partition(finest_bands, finest_bands, horizon_seconds)
    return summarize_observable_masses(
        partition=partition,
        harmful_by_band=harmful_by_band,
        correct_by_band=correct_by_band,
        unresolved_mass=unresolved_mass,
        comparison_guard=comparison_guard,
    )


def empirical_oracle(
    cohort: RealTrajectoryCohort,
    finest_bands: BandCount,
    comparison_guard: ToleranceValue,
) -> RealTrajectoryEmpiricalOracle:
    theta_true = float(cohort.latent_error.mean())
    full_horizon = float(cohort.decision_time.max()) * (1.0 + comparison_guard)
    fully_resolved_summary = finest_observable_summary(
        cohort, full_horizon, finest_bands, comparison_guard
    )
    full_information = observed_timing_information(fully_resolved_summary) or 0.0
    return RealTrajectoryEmpiricalOracle(
        theta_true=theta_true, full_information_nats=full_information
    )


def resolved_count(cohort: RealTrajectoryCohort, horizon_seconds: AgeUnit) -> Count:
    return int((cohort.decision_time <= horizon_seconds).sum())
