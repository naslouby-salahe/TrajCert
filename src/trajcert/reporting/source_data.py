from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import NewType, Protocol, cast

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pydantic import Field

from trajcert.analysis.metrics import MetricName, PracticalMetric
from trajcert.config import TrajCertConfig
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.sensitivity import PopulationUtilityResult
from trajcert.experiments.synthesis import TrajectoryOperationalGainSynthesis
from trajcert.schemas import (
    PublicationSourceDescriptor,
    PublicationSourceRole,
    VerifiedSourceLineage,
)
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DigestHex,
    file_digest,
    read_model,
)
from trajcert.types import (
    CompatibilityRegime,
    DomainModel,
    FiniteFloat,
    InformationNats,
    LawName,
    NonNegativeInt,
    PartitionName,
    Probability,
    RiskBudget,
    RiskValue,
    SensitivityBudget,
)

TheoremName = NewType("TheoremName", str)
ScientificConsequence = NewType("ScientificConsequence", str)
RegimeName = NewType("RegimeName", str)


class _ReadParquet(Protocol):
    def __call__(self, _source: Path) -> pa.Table: ...


class _WriteParquet(Protocol):
    def __call__(
        self,
        table: pa.Table,
        where: Path,
        *,
        compression: str,
        use_dictionary: bool,
        write_statistics: bool,
    ) -> None: ...


_READ_PARQUET = cast(_ReadParquet, pq.read_table)
_WRITE_PARQUET = cast(_WriteParquet, pq.write_table)


class AnalysisType(StrEnum):
    POPULATION = "POPULATION"
    SEQUENTIAL = "SEQUENTIAL"


class PublicationSourceName(StrEnum):
    PROTOCOL_CONSTANTS = "protocol_constants"
    SYNTHETIC_LAWS = "synthetic_laws"
    BASELINES = "baselines"
    EXPERIMENT_MATRIX = "experiment_matrix"
    THEOREM_VALIDATION = "theorem_validation_summary"
    SOLVER_ORACLE_VALIDATION = "solver_oracle_validation"
    PARTITION_TIMING = "partition_timing_results"
    COMPATIBILITY_SAFETY = "compatibility_safety"
    ANYTIME_COVERAGE = "anytime_coverage"
    RHO_UTILITY = "rho_utility"
    FAILURE_BOUNDARIES = "failure_boundaries"
    COMPUTATIONAL_SCALING = "computational_scaling"
    FIGURE_PARTITION_COHERENCE = "figure_partition_coherence"
    FIGURE_TIMING_VALUE = "figure_timing_value"
    FIGURE_INFORMATION_PROFILE = "figure_information_profile"
    FIGURE_ANYTIME_PATHS = "figure_anytime_paths"
    FIGURE_ANYTIME_COVERAGE = "figure_anytime_coverage"
    FIGURE_RHO_SENSITIVITY = "figure_rho_sensitivity"
    FIGURE_FAILURE_BOUNDARIES = "figure_failure_boundaries"
    FIGURE_COMPUTATIONAL_SCALING = "figure_computational_scaling"


class TheoremValidationSummaryRow(DomainModel):
    theorem_name: TheoremName
    case_count: NonNegativeInt
    maximum_absolute_error: FiniteFloat | None
    minimum_inequality_margin: FiniteFloat | None
    all_cases_pass: bool
    primary_artifact: ArtifactKey
    scientific_consequence: ScientificConsequence


class PartitionTimingRow(DomainModel):
    law_name: LawName
    coarse_partition: PartitionName
    fine_partition: PartitionName
    rho: SensitivityBudget
    tau_coarse: InformationNats
    tau_fine: InformationNats
    delta_tau: InformationNats
    coarse_risk_upper: RiskValue
    fine_risk_upper: RiskValue
    bound_gain: FiniteFloat
    fine_subset_coarse: bool
    theorem_condition: bool
    passed: bool = Field(serialization_alias="pass")


class CompatibilitySafetyRow(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    rho: SensitivityBudget | None
    beta: RiskBudget | None
    tau: InformationNats | None
    theta_dagger: RiskValue | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    rho_star: InformationNats | None
    expected_regime: RegimeName
    observed_regime: RegimeName
    oracle_error: FiniteFloat | None
    passed: bool = Field(serialization_alias="pass")


class RhoUtilityRow(DomainModel):
    analysis_type: AnalysisType
    law_name: LawName
    rho: SensitivityBudget
    partition_name: PartitionName
    baseline_partition_name: PartitionName | None = None
    metric_name: MetricName
    metric_value: FiniteFloat | None = None
    compatibility_state: CompatibilityRegime | None = None
    tau: InformationNats | None = None
    risk_upper: RiskValue | None = None
    identified_width: FiniteFloat | None = None
    worst_case_upper: RiskValue | None = None
    absolute_tightening: FiniteFloat | None = None
    relative_unresolved_gain: FiniteFloat | None = None
    method_mean: FiniteFloat | None = None
    baseline_mean: FiniteFloat | None = None
    mean_paired_difference: FiniteFloat | None = None
    bootstrap_lower_95: FiniteFloat | None = None
    bootstrap_upper_95: FiniteFloat | None = None
    holm_adjusted_p: Probability | None = None
    materiality_pass: bool
    never_certified_fraction_method: Probability | None = None
    never_certified_fraction_baseline: Probability | None = None


class PartitionCoherenceFigureRow(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    partition_band_count: NonNegativeInt
    rho: SensitivityBudget
    tau: InformationNats
    risk_lower: RiskValue
    risk_upper: RiskValue


class PopulationUtilitySourceEvidence(DomainModel):
    law_name: LawName
    partition_name: PartitionName
    result: PopulationUtilityResult


@dataclass(frozen=True, slots=True)
class VerifiedSourceData:
    descriptor: PublicationSourceDescriptor
    table: pa.Table
    lineage: VerifiedSourceLineage


def population_rho_utility_rows(
    evidence: tuple[PopulationUtilitySourceEvidence, ...],
) -> tuple[RhoUtilityRow, ...]:
    return tuple(
        RhoUtilityRow(
            analysis_type=AnalysisType.POPULATION,
            law_name=item.law_name,
            rho=item.result.sensitivity_budget,
            partition_name=item.partition_name,
            metric_name=MetricName("Population latent-risk upper bound"),
            metric_value=item.result.risk_upper,
            compatibility_state=item.result.compatibility_regime,
            tau=item.result.tau,
            risk_upper=item.result.risk_upper,
            identified_width=item.result.identified_width,
            worst_case_upper=item.result.unresolved_as_harm_upper,
            absolute_tightening=item.result.absolute_tightening,
            relative_unresolved_gain=item.result.relative_unresolved_gain,
            materiality_pass=item.result.materially_nonvacuous,
        )
        for item in evidence
    )


def sequential_rho_utility_rows(
    synthesis: TrajectoryOperationalGainSynthesis,
    config: TrajCertConfig,
) -> tuple[RhoUtilityRow, ...]:
    fine_partition = partition_name(config.method.finest_bands)
    endpoint_partition = partition_name(1)
    return tuple(
        RhoUtilityRow(
            analysis_type=AnalysisType.SEQUENTIAL,
            law_name=result.law_name,
            rho=result.sensitivity_budget,
            partition_name=fine_partition,
            baseline_partition_name=endpoint_partition,
            metric_name=MetricName(result.metric_name.value),
            method_mean=result.method_mean,
            baseline_mean=result.baseline_mean,
            mean_paired_difference=result.effect.mean_paired_difference,
            bootstrap_lower_95=result.bootstrap.lower,
            bootstrap_upper_95=result.bootstrap.upper,
            holm_adjusted_p=result.holm_adjusted_p_value,
            materiality_pass=result.materiality_pass,
            never_certified_fraction_method=(
                result.never_certified_fraction_method
                if result.metric_name is PracticalMetric.TIME_TO_FIRST_CERTIFICATION
                else None
            ),
            never_certified_fraction_baseline=(
                result.never_certified_fraction_baseline
                if result.metric_name is PracticalMetric.TIME_TO_FIRST_CERTIFICATION
                else None
            ),
        )
        for result in synthesis.tests
    )


def table_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return _TABLE_SOURCES


def figure_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return _FIGURE_SOURCES


def all_publication_source_descriptors() -> tuple[PublicationSourceDescriptor, ...]:
    return (*_TABLE_SOURCES, *_FIGURE_SOURCES)


def descriptor_for(name: PublicationSourceName) -> PublicationSourceDescriptor:
    for source_name, descriptor in _NAMED_SOURCES:
        if source_name is name:
            return descriptor
    raise InvalidScientificDataError(f"unknown publication source: {name}")


def read_verified_source_data(
    workspace_root: Path,
    descriptor: PublicationSourceDescriptor,
) -> VerifiedSourceData:
    source_path = workspace_root / descriptor.source_path
    table = read_source_data(source_path)
    _validate_source_columns(table, descriptor)
    _validate_scientific_values(table, source_path)
    ordered = _deterministic_order(table, descriptor.sort_columns)
    lineage = _verify_registered_lineage(workspace_root, descriptor, source_path)
    return VerifiedSourceData(descriptor=descriptor, table=ordered, lineage=lineage)


def write_source_data(path: Path, rows: Sequence[DomainModel]) -> DigestHex:
    records = tuple(rows)
    if not records:
        raise InvalidScientificDataError("source-data Parquet requires at least one row")
    model_type = type(records[0])
    if any(type(row) is not model_type for row in records):
        raise InvalidScientificDataError("one source-data Parquet file must use one row schema")
    payload = [row.model_dump(mode="json", by_alias=True) for row in records]
    table = pa.Table.from_pylist(payload)
    _atomic_write_parquet(path, table)
    return file_digest(path)


def read_source_data(path: Path) -> pa.Table:
    try:
        table = _READ_PARQUET(path)
    except (OSError, pa.ArrowException) as exc:
        raise SerializationError(f"cannot read source-data Parquet: {path}") from exc
    if table.num_rows == 0:
        raise SerializationError(f"source-data Parquet is empty: {path}")
    return table


def _validate_source_columns(table: pa.Table, descriptor: PublicationSourceDescriptor) -> None:
    actual = tuple(table.column_names)
    required = descriptor.columns
    missing = tuple(column for column in required if column not in actual)
    if missing:
        raise InvalidScientificDataError(
            f"source-data schema missing columns for {descriptor.source_path}: {missing}"
        )
    if descriptor.source_role is PublicationSourceRole.TABLE and actual != required:
        raise InvalidScientificDataError(
            f"table source-data schema mismatch for {descriptor.source_path}"
        )


def _validate_scientific_values(table: pa.Table, source_path: Path) -> None:
    for field in table.schema:
        if not pa.types.is_floating(field.type):
            continue
        for value in table.column(field.name).to_pylist():
            if value is not None and not isfinite(float(value)):
                raise InvalidScientificDataError(
                    f"source-data float column contains NaN or infinity: {source_path}:{field.name}"
                )


def _deterministic_order(table: pa.Table, columns: tuple[str, ...]) -> pa.Table:
    if not columns or table.num_rows < 2:
        return table
    missing = tuple(column for column in columns if column not in table.column_names)
    if missing:
        raise InvalidScientificDataError(f"source sort columns are missing: {missing}")
    indices = pc.sort_indices(
        table,
        sort_keys=[(column, "ascending") for column in columns],
        null_placement="at_start",
    )
    return table.take(indices)


def _verify_registered_lineage(
    workspace_root: Path,
    descriptor: PublicationSourceDescriptor,
    source_path: Path,
) -> VerifiedSourceLineage:
    checkpoints_root = workspace_root / "outputs" / "experiments"
    if not checkpoints_root.is_dir():
        raise InvalidScientificDataError("publication sources require completed experiment evidence")
    relative_source = descriptor.source_path
    matches: list[tuple[Path, CellArtifactIndex, ArtifactKey]] = []
    for index_path in checkpoints_root.glob("*/checkpoints/execution/**/artifact_index.json"):
        index = read_model(index_path, CellArtifactIndex)
        for entry in index.artifacts:
            if entry.relative_path == relative_source:
                matches.append((index_path, index, entry.artifact_key))
    if len(matches) != 1:
        raise InvalidScientificDataError(
            f"source-data must have exactly one active registered producer: {descriptor.source_path}"
        )
    index_path, index, artifact_key = matches[0]
    completion_path = index_path.with_name("COMPLETED.json")
    completion = read_model(completion_path, CompletionRecord)
    if artifact_key not in completion.produced_artifact_keys:
        raise InvalidScientificDataError("source artifact is absent from its completion record")
    entry = next(item for item in index.artifacts if item.artifact_key == artifact_key)
    actual_digest = file_digest(source_path)
    if entry.sha256 != actual_digest:
        raise InvalidScientificDataError(f"source-data checksum mismatch: {descriptor.source_path}")
    expected = ArtifactChecksum(artifact_key=artifact_key, sha256=actual_digest)
    if expected not in completion.artifact_sha256_map:
        raise InvalidScientificDataError("source checksum is absent from completion record")
    return VerifiedSourceLineage(
        source_path=descriptor.source_path,
        source_sha256=actual_digest,
        artifact_key=artifact_key,
        completion_sha256=file_digest(completion_path),
        scientific_specification_digest=completion.scientific_specification_digest,
        dependency_fingerprint=completion.dependency_fingerprint,
        provenance_fingerprint=completion.provenance_fingerprint,
    )


def _atomic_write_parquet(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".parquet",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
        _WRITE_PARQUET(
            table,
            temporary_path,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        with temporary_path.open("rb") as stream:
            os.fsync(stream.fileno())
        _ = temporary_path.replace(path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except (OSError, pa.ArrowException) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise SerializationError(f"atomic source-data Parquet write failed: {path}") from exc


def _source(
    path: str,
    role: PublicationSourceRole,
    columns: tuple[str, ...],
    sort_columns: tuple[str, ...],
    owner: str,
) -> PublicationSourceDescriptor:
    return PublicationSourceDescriptor(
        source_path=Path(path),
        source_role=role,
        columns=columns,
        sort_columns=sort_columns,
        owner_experiment=owner,
    )


_TABLE_SOURCES = (
    _source(
        "outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/protocol_constants.parquet",
        PublicationSourceRole.TABLE,
        ("quantity", "value", "unit", "value_class", "fixed_or_swept", "scientific_role"),
        ("quantity",),
        "scientific-and-data-inventory",
    ),
    _source(
        "outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/synthetic_laws.parquet",
        PublicationSourceRole.TABLE,
        (
            "law_name",
            "theta",
            "q1",
            "q0",
            "lambda1",
            "lambda0",
            "K",
            "A",
            "G",
            "c",
            "tau_at_8_band_partition",
            "true_mutual_information_at_8_band_partition",
            "scientific_role",
        ),
        ("law_name",),
        "scientific-and-data-inventory",
    ),
    _source(
        "outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/baselines.parquet",
        PublicationSourceRole.TABLE,
        (
            "baseline_name",
            "purpose",
            "observation_access",
            "assumption",
            "numerical_contract",
            "sensitivity_grid",
            "seed_pairing",
            "metrics",
            "valid_scope",
            "forbidden_interpretation",
        ),
        ("baseline_name",),
        "scientific-and-data-inventory",
    ),
    _source(
        "outputs/experiments/scientific-and-data-inventory/evaluations/aggregates/experiment_matrix.parquet",
        PublicationSourceRole.TABLE,
        (
            "execution_group",
            "experiment_name",
            "classification",
            "purpose",
            "cell_expansion",
            "cell_count",
            "primary_metrics",
            "claim_ids",
        ),
        ("execution_group", "experiment_name"),
        "scientific-and-data-inventory",
    ),
    _source(
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/theorem_validation_summary.parquet",
        PublicationSourceRole.TABLE,
        (
            "theorem_name",
            "case_count",
            "maximum_absolute_error",
            "minimum_inequality_margin",
            "all_cases_pass",
            "primary_artifact",
            "scientific_consequence",
        ),
        ("theorem_name",),
        "statistical-synthesis",
    ),
    _source(
        "outputs/experiments/production-solver-vs-independent-oracle/evaluations/aggregates/solver_oracle_validation.parquet",
        PublicationSourceRole.TABLE,
        (
            "partition_name",
            "rho_offset_mode",
            "cell_count",
            "max_abs_u_lower_error",
            "max_abs_u_upper_error",
            "max_abs_risk_upper_error",
            "max_abs_rho_star_error",
            "rho_star_applicable_cell_count",
            "state_mismatch_count",
            "pass",
        ),
        ("partition_name", "rho_offset_mode"),
        "production-solver-vs-independent-oracle",
    ),
    _source(
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/partition_timing_results.parquet",
        PublicationSourceRole.TABLE,
        (
            "law_name",
            "coarse_partition",
            "fine_partition",
            "rho",
            "tau_coarse",
            "tau_fine",
            "delta_tau",
            "coarse_risk_upper",
            "fine_risk_upper",
            "bound_gain",
            "fine_subset_coarse",
            "theorem_condition",
            "pass",
        ),
        ("law_name", "coarse_partition", "fine_partition", "rho"),
        "statistical-synthesis",
    ),
    _source(
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/compatibility_safety.parquet",
        PublicationSourceRole.TABLE,
        (
            "law_name",
            "partition_name",
            "rho",
            "beta",
            "tau",
            "theta_dagger",
            "risk_lower",
            "risk_upper",
            "rho_star",
            "expected_regime",
            "observed_regime",
            "oracle_error",
            "pass",
        ),
        ("law_name", "partition_name", "rho", "beta"),
        "statistical-synthesis",
    ),
    _source(
        "outputs/experiments/anytime-coverage-stress/evaluations/aggregates/anytime_coverage.parquet",
        PublicationSourceRole.TABLE,
        (
            "stress_cell",
            "method_name",
            "K",
            "true_theta",
            "true_mutual_information",
            "rho",
            "beta",
            "delta",
            "independent_streams",
            "ever_violations",
            "violation_rate",
            "clopper_pearson_upper_95",
            "criterion_pass",
            "median_first_certified_n",
            "median_certified_update_fraction",
        ),
        ("stress_cell", "method_name"),
        "anytime-coverage-stress",
    ),
    _source(
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/rho_utility.parquet",
        PublicationSourceRole.TABLE,
        tuple(RhoUtilityRow.model_fields),
        ("analysis_type", "law_name", "rho", "partition_name", "metric_name"),
        "statistical-synthesis",
    ),
    _source(
        "outputs/experiments/failure-boundary-atlas/evaluations/aggregates/failure_boundaries.parquet",
        PublicationSourceRole.TABLE,
        (
            "axis",
            "level",
            "controlled_value_json",
            "rho",
            "beta",
            "tau",
            "risk_upper",
            "operational_state",
            "optimizer_gap",
            "runtime_ms",
            "scientific_interpretation",
        ),
        ("axis", "level"),
        "failure-boundary-atlas",
    ),
    _source(
        "outputs/experiments/computational-scaling/evaluations/aggregates/computational_scaling.parquet",
        PublicationSourceRole.TABLE,
        (
            "K",
            "population_median_runtime_ms",
            "population_iqr_runtime_ms",
            "outer_median_runtime_ms",
            "outer_iqr_runtime_ms",
            "peak_memory_mib",
            "median_root_iterations",
            "median_outer_nodes",
            "max_oracle_error",
        ),
        ("K",),
        "computational-scaling",
    ),
)


_FIGURE_SOURCES = (
    _source(
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/figure_partition_coherence.parquet",
        PublicationSourceRole.FIGURE,
        ("law_name", "partition_name", "partition_band_count", "rho", "tau", "risk_lower", "risk_upper"),
        ("law_name", "partition_band_count"),
        "statistical-synthesis",
    ),
    _source(
        "outputs/experiments/strict-timing-gain/evaluations/aggregates/figure_timing_value.parquet",
        PublicationSourceRole.FIGURE,
        ("semantic_timing_case", "rho_offset", "delta_tau", "bound_gain", "coarse_risk_upper", "fine_risk_upper"),
        ("rho_offset", "semantic_timing_case", "delta_tau"),
        "strict-timing-gain",
    ),
    _source(
        "outputs/experiments/safety-and-intrinsic-impossibility/evaluations/aggregates/figure_information_profile.parquet",
        PublicationSourceRole.FIGURE,
        ("u", "information_profile", "u_dagger", "tau", "rho", "u_beta", "rho_star", "feasible_lower", "feasible_upper"),
        ("u",),
        "safety-and-intrinsic-impossibility",
    ),
    _source(
        "outputs/experiments/anytime-coverage-stress/evaluations/aggregates/figure_anytime_paths.parquet",
        PublicationSourceRole.FIGURE,
        ("stream_seed_index", "n_matured", "risk_upper_anytime", "true_theta", "beta", "evidence_gate_pass", "operational_state"),
        ("stream_seed_index", "n_matured"),
        "anytime-coverage-stress",
    ),
    _source(
        "outputs/experiments/anytime-coverage-stress/evaluations/aggregates/figure_anytime_coverage.parquet",
        PublicationSourceRole.FIGURE,
        ("stress_cell", "method_name", "K", "clopper_pearson_upper_95", "delta", "acceptance_upper_limit", "criterion_pass"),
        ("stress_cell", "method_name"),
        "anytime-coverage-stress",
    ),
    _source(
        "outputs/experiments/population-sensitivity-utility/evaluations/aggregates/figure_rho_sensitivity.parquet",
        PublicationSourceRole.FIGURE,
        ("law_name", "partition_name", "rho", "risk_upper", "compatibility_state", "rho_is_log2"),
        ("law_name", "partition_name", "rho"),
        "population-sensitivity-utility",
    ),
    _source(
        "outputs/experiments/failure-boundary-atlas/evaluations/aggregates/figure_failure_boundaries.parquet",
        PublicationSourceRole.FIGURE,
        ("axis", "level", "controlled_value_json", "risk_upper", "operational_state", "optimizer_gap", "runtime_ms"),
        ("axis", "level"),
        "failure-boundary-atlas",
    ),
    _source(
        "outputs/experiments/computational-scaling/evaluations/aggregates/figure_computational_scaling.parquet",
        PublicationSourceRole.FIGURE,
        ("K", "population_median_runtime_ms", "outer_median_runtime_ms", "median_outer_nodes"),
        ("K",),
        "computational-scaling",
    ),
)


_NAMED_SOURCES = tuple(zip(PublicationSourceName, (*_TABLE_SOURCES, *_FIGURE_SOURCES), strict=True))
