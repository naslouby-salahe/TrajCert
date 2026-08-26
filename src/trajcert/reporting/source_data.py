from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import NewType

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field

from trajcert.analysis.metrics import MetricName, PracticalMetric
from trajcert.config import TrajCertConfig
from trajcert.data.partitions import partition_name
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.sensitivity import PopulationUtilityResult
from trajcert.experiments.synthesis import TrajectoryOperationalGainSynthesis
from trajcert.storage import ArtifactKey, DigestHex, file_digest
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


class AnalysisType(StrEnum):
    POPULATION = "POPULATION"
    SEQUENTIAL = "SEQUENTIAL"


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
    rho: SensitivityBudget
    beta: RiskBudget
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
        table = pq.read_table(path)
    except (OSError, pa.ArrowException) as exc:
        raise SerializationError(f"cannot read source-data Parquet: {path}") from exc
    if table.num_rows == 0:
        raise SerializationError(f"source-data Parquet is empty: {path}")
    return table


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
        pq.write_table(
            table,
            temporary_path,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        with temporary_path.open("rb") as stream:
            os.fsync(stream.fileno())
        temporary_path.replace(path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except (OSError, pa.ArrowException) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise SerializationError(f"atomic source-data Parquet write failed: {path}") from exc
