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

from trajcert.analysis.metrics import MetricName
from trajcert.exceptions import InvalidScientificDataError, SerializationError
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
        os.replace(temporary_path, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except (OSError, pa.ArrowException) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise SerializationError(f"atomic source-data Parquet write failed: {path}") from exc
