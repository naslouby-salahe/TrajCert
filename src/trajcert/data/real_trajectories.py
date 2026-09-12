from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path

import numpy as np
import polars as pl

from trajcert.config import RealTrajectoryDatasetConfig, active_config
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


def _dataset_contract() -> RealTrajectoryDatasetConfig:
    return active_config.get().real_trajectory.dataset


def hitl_iot_device_names() -> tuple[ClientId, ...]:
    return _dataset_contract().device_names



class RealTrajectorySchemaValidation(DomainModel):
    expected_columns: tuple[DatasetColumnName, ...]
    observed_columns: tuple[DatasetColumnName, ...]
    passed: bool


def validate_dataset_schema(dataset_root: RawDatasetRoot) -> RealTrajectorySchemaValidation:
    dataset = _dataset_contract()
    dataset_path = Path(dataset_root) / dataset.data_filename
    observed = tuple(
        DatasetColumnName(name) for name in pl.scan_csv(dataset_path).collect_schema().names()
    )
    expected = dataset.expected_schema
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
    dataset = _dataset_contract()
    root = Path(dataset_root)
    dataset_path = root / dataset.data_filename
    checksums_path = root / dataset.checksums_filename
    if not dataset_path.is_file():
        raise DataIntegrityError(f"HITL-IoT dataset file is missing: {dataset_path}")
    actual_digest = DatasetChecksumHex(sha256(dataset_path.read_bytes()).hexdigest())
    if actual_digest != dataset.sha256:
        raise DataIntegrityError(
            "HITL-IoT dataset checksum mismatch against the pinned Zenodo release "
            + f"({dataset.doi}): expected {dataset.sha256}, got {actual_digest}"
        )
    if checksums_path.is_file():
        recorded = _parse_checksums_file(checksums_path)
        expected = recorded.get(dataset.data_filename)
        if expected is not None and expected != actual_digest:
            raise DataIntegrityError(
                "HITL-IoT dataset checksum does not match the dataset's own checksums manifest"
            )
    total_rows = pl.scan_csv(dataset_path).select(pl.len()).collect().item()
    return RealTrajectoryDatasetProvenance(
        dataset_name=dataset.name,
        doi=dataset.doi,
        dataset_filename=dataset.data_filename,
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
    dataset = _dataset_contract()
    root = Path(dataset_root)
    dataset_path = root / dataset.data_filename
    frame = pl.read_csv(dataset_path, columns=list(dataset.raw_columns))
    columns = dataset.columns
    total_rows = frame.height
    annotated = frame.filter(pl.col(columns.human_reviewed))
    candidate_rows = annotated.height

    duplicate_mask = annotated.select(list(dataset.flow_identity_columns)).is_duplicated()
    checks: tuple[tuple[RealTrajectoryExclusionReason, pl.Series], ...] = (
        (
            RealTrajectoryExclusionReason.MISSING_GROUND_TRUTH,
            annotated[columns.is_attack].is_null(),
        ),
        (
            RealTrajectoryExclusionReason.MISSING_AUTOMATIC_PREDICTION,
            annotated[columns.ml_prediction].is_null(),
        ),
        (
            RealTrajectoryExclusionReason.INVALID_DEVICE_IDENTITY,
            annotated[columns.device_name].is_null()
            | (annotated[columns.device_name].str.len_chars() == 0),
        ),
        (
            RealTrajectoryExclusionReason.INVALID_DECISION_LATENCY,
            annotated[columns.decision_time].is_null() | (annotated[columns.decision_time] <= 0.0),  # TODO: should be constant
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
        (ClientId(row[columns.device_name]), row["len"])
        for row in eligible.group_by(columns.device_name).len().sort(columns.device_name).to_dicts()
    )
    expertise_counts = tuple(
        (AnnotatorExpertise(row[columns.annotator_id]), row["len"])
        for row in eligible.group_by(columns.annotator_id)
        .len()
        .sort(columns.annotator_id)
        .to_dicts()
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
            device_name=ClientId(row[columns.device_name]),
            device_type=HitlIotDeviceType(row[columns.device_type]),
            expertise=AnnotatorExpertise(row[columns.annotator_id]),
            is_attack=row[columns.is_attack],
            ml_prediction=row[columns.ml_prediction],
            decision_time=row[columns.decision_time],
            human_confidence=row[columns.human_confidence],
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
    else:
        mask = cohort.expertise == stratum_value
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
    if horizon_seconds <= 0.0 or not isfinite(horizon_seconds):  # TODO: should be constant
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
    full_horizon = float(cohort.decision_time.max()) * (1.0 + comparison_guard)  # TODO: should be constant
    fully_resolved_summary = finest_observable_summary(
        cohort, full_horizon, finest_bands, comparison_guard
    )
    full_information = observed_timing_information(fully_resolved_summary) or 0.0  # TODO: should be constant
    return RealTrajectoryEmpiricalOracle(
        theta_true=theta_true, full_information_nats=full_information
    )


def resolved_count(cohort: RealTrajectoryCohort, horizon_seconds: AgeUnit) -> Count:
    return int((cohort.decision_time <= horizon_seconds).sum())
