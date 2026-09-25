from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from math import isfinite
from pathlib import Path

import numpy as np
import polars as pl
from numpy.typing import NDArray

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
    DatasetComparisonStatus,
    DatasetFieldMappingStatus,
    DatasetFilename,
    DatasetSourceReference,
    DatasetTimestamp,
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
    source_reference: DatasetSourceReference
    dataset_filename: DatasetFilename
    dataset_sha256: DatasetChecksumHex
    total_rows: Count


class RealTrajectoryDatasetStructure(DomainModel):
    dataset_filename: DatasetFilename
    file_count: Count
    row_count: Count
    ground_truth_attack_rows: Count
    human_reviewed_rows: Count
    entity_ids: tuple[ClientId, ...]
    raw_schema: tuple[DatasetColumnName, ...]
    flow_identity_columns: tuple[DatasetColumnName, ...]
    decision_time_column: DatasetColumnName


class RealTrajectoryDatasetInventory(DomainModel):
    expected_source_release: DatasetVersionTag | None
    source_documentation_reference: DatasetSourceReference
    primary_publication_reference: DatasetVersionTag | None
    documented_expected_value: RealTrajectoryDatasetStructure
    observed_raw_dataset_value: RealTrajectoryDatasetStructure
    reviewed_attack_rows: Count
    reviewed_attack_model_error_rows: Count
    reviewed_attack_model_error_rate: Probability | None
    unreviewed_attack_rows: Count
    unreviewed_attack_model_error_rows: Count
    unreviewed_attack_model_error_rate: Probability | None
    observed_timestamp_start: DatasetTimestamp
    observed_timestamp_end: DatasetTimestamp
    discrepancy_status: DatasetComparisonStatus
    field_mapping_status: DatasetFieldMappingStatus


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
    device_name: NDArray[np.str_]
    device_type: NDArray[np.str_]
    expertise: NDArray[np.str_]
    latent_error: NDArray[np.bool_]
    decision_time: NDArray[np.float64]

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
            "HITL-IoT dataset checksum mismatch against the configured external file identity "
            + f"for {dataset.source_reference}: expected {dataset.sha256}, got {actual_digest}"
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
        source_reference=dataset.source_reference,
        dataset_filename=dataset.data_filename,
        dataset_sha256=actual_digest,
        total_rows=total_rows,
    )


def inventory_real_trajectory_dataset(
    dataset_root: RawDatasetRoot,
) -> RealTrajectoryDatasetInventory:
    dataset = _dataset_contract()
    dataset_path = Path(dataset_root) / dataset.data_filename
    observed_columns = tuple(
        DatasetColumnName(name) for name in pl.scan_csv(dataset_path).collect_schema().names()
    )
    observed_entity_ids = tuple(
        ClientId(device_name)
        for (device_name,) in pl.read_csv(dataset_path, columns=[dataset.columns.device_name])
        .unique()
        .sort(dataset.columns.device_name)
        .iter_rows()
    )
    observed_counts = (
        pl.scan_csv(dataset_path)
        .select(
            pl.col(dataset.columns.is_attack).sum().alias("ground_truth_attack_rows"),
            pl.col(dataset.columns.human_reviewed).sum().alias("human_reviewed_rows"),
            (pl.col(dataset.columns.human_reviewed) & pl.col(dataset.columns.is_attack))
            .sum()
            .alias("reviewed_attack_rows"),
            (
                pl.col(dataset.columns.human_reviewed)
                & pl.col(dataset.columns.is_attack)
                & (pl.col(dataset.columns.ml_prediction) != pl.col(dataset.columns.is_attack))
            )
            .sum()
            .alias("reviewed_attack_model_error_rows"),
            (~pl.col(dataset.columns.human_reviewed) & pl.col(dataset.columns.is_attack))
            .sum()
            .alias("unreviewed_attack_rows"),
            (
                ~pl.col(dataset.columns.human_reviewed)
                & pl.col(dataset.columns.is_attack)
                & (pl.col(dataset.columns.ml_prediction) != pl.col(dataset.columns.is_attack))
            )
            .sum()
            .alias("unreviewed_attack_model_error_rows"),
        )
        .collect()
        .row(0, named=True)
    )
    timestamp_range = (
        pl.scan_csv(dataset_path)
        .select(
            pl.col("timestamp").min().alias("start"),
            pl.col("timestamp").max().alias("end"),
        )
        .collect()
        .row(0, named=True)
    )
    observed_structure = RealTrajectoryDatasetStructure(
        dataset_filename=DatasetFilename(dataset_path.name),
        file_count=len((dataset_path,)),
        row_count=pl.scan_csv(dataset_path).select(pl.len()).collect().item(),
        ground_truth_attack_rows=int(observed_counts["ground_truth_attack_rows"]),
        human_reviewed_rows=int(observed_counts["human_reviewed_rows"]),
        entity_ids=observed_entity_ids,
        raw_schema=observed_columns,
        flow_identity_columns=tuple(
            column for column in dataset.flow_identity_columns if column in observed_columns
        ),
        decision_time_column=dataset.columns.decision_time,
    )
    documented_structure = RealTrajectoryDatasetStructure(
        dataset_filename=dataset.data_filename,
        file_count=len((dataset.data_filename,)),
        row_count=dataset.documented_total_rows,
        ground_truth_attack_rows=dataset.documented_ground_truth_attack_rows,
        human_reviewed_rows=dataset.documented_human_reviewed_rows,
        entity_ids=dataset.device_names,
        raw_schema=dataset.expected_schema,
        flow_identity_columns=dataset.flow_identity_columns,
        decision_time_column=dataset.columns.decision_time,
    )
    matched = documented_structure == observed_structure
    reviewed_attack_rows = int(observed_counts["reviewed_attack_rows"])
    reviewed_attack_errors = int(observed_counts["reviewed_attack_model_error_rows"])
    unreviewed_attack_rows = int(observed_counts["unreviewed_attack_rows"])
    unreviewed_attack_errors = int(observed_counts["unreviewed_attack_model_error_rows"])
    return RealTrajectoryDatasetInventory(
        expected_source_release=None,
        source_documentation_reference=dataset.source_reference,
        primary_publication_reference=None,
        documented_expected_value=documented_structure,
        observed_raw_dataset_value=observed_structure,
        reviewed_attack_rows=reviewed_attack_rows,
        reviewed_attack_model_error_rows=reviewed_attack_errors,
        reviewed_attack_model_error_rate=(
            reviewed_attack_errors / reviewed_attack_rows if reviewed_attack_rows > 0 else None
        ),
        unreviewed_attack_rows=unreviewed_attack_rows,
        unreviewed_attack_model_error_rows=unreviewed_attack_errors,
        unreviewed_attack_model_error_rate=(
            unreviewed_attack_errors / unreviewed_attack_rows
            if unreviewed_attack_rows > 0
            else None
        ),
        observed_timestamp_start=DatasetTimestamp(
            datetime.fromisoformat(str(timestamp_range["start"]))
        ),
        observed_timestamp_end=DatasetTimestamp(
            datetime.fromisoformat(str(timestamp_range["end"]))
        ),
        discrepancy_status=(
            DatasetComparisonStatus.MATCHED
            if matched
            else DatasetComparisonStatus.OBSERVED_DEVIATION
        ),
        field_mapping_status=(
            DatasetFieldMappingStatus.IDENTICAL
            if set(dataset.raw_columns).issubset(observed_columns)
            else DatasetFieldMappingStatus.REQUIRES_REVIEW
        ),
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
            annotated[columns.decision_time].is_null() | (annotated[columns.decision_time] <= 0.0),
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
        (ClientId(device_name), count)
        for device_name, count in eligible.group_by(columns.device_name)
        .len()
        .sort(columns.device_name)
        .iter_rows()
    )
    expertise_counts = tuple(
        (AnnotatorExpertise(annotator_id), count)
        for annotator_id, count in eligible.group_by(columns.annotator_id)
        .len()
        .sort(columns.annotator_id)
        .iter_rows()
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
    event_rows = eligible.select(
        (
            columns.device_name,
            columns.device_type,
            columns.annotator_id,
            columns.is_attack,
            columns.ml_prediction,
            columns.decision_time,
            columns.human_confidence,
        )
    ).iter_rows()
    events = tuple(
        HitlIotEligibleEvent(
            device_name=ClientId(device_name),
            device_type=HitlIotDeviceType(device_type),
            expertise=AnnotatorExpertise(annotator_id),
            is_attack=is_attack,
            ml_prediction=ml_prediction,
            decision_time=decision_time,
            human_confidence=human_confidence,
        )
        for (
            device_name,
            device_type,
            annotator_id,
            is_attack,
            ml_prediction,
            decision_time,
            human_confidence,
        ) in event_rows
    )
    return events, report


def cohort_from_events(events: tuple[HitlIotEligibleEvent, ...]) -> RealTrajectoryCohort:
    if not events:
        raise InvalidScientificDataError("real-trajectory cohort requires at least one event")
    return RealTrajectoryCohort(
        device_name=np.array([event.device_name for event in events], dtype=np.str_),
        device_type=np.array([event.device_type for event in events], dtype=np.str_),
        expertise=np.array([event.expertise for event in events], dtype=np.str_),
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
