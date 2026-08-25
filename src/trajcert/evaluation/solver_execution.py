from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import pyarrow as pyarrow
import pyarrow.parquet as pyarrow_parquet

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.data.partitions import CoarseningGroups
from trajcert.data.synthetic.laws import SyntheticTrajectoryLaw, synthetic_law_catalog
from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.evaluation.oracle_validation import (
    OracleValidationState,
    PopulationSolverOracleValidationInput,
    PopulationSolverOracleValidationResult,
    validate_population_solver_against_oracle,
)
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes
from trajcert.math.information_profile import InformationProfile

SOLVER_ORACLE_AGGREGATE_RELATIVE_PATH = Path(
    "outputs/experiments/production-solver-vs-independent-oracle/"
    "evaluations/aggregates/solver_oracle_validation.parquet"
)
SOLVER_ORACLE_SOURCE_RELATIVE_PATH = Path(
    "outputs/experiments/production-solver-vs-independent-oracle/"
    "evaluations/source_data/solver_oracle_cells.json"
)
SOLVER_ORACLE_COMPLETION_RELATIVE_PATH = Path(
    "outputs/experiments/production-solver-vs-independent-oracle/"
    "evaluations/completion/solver_oracle_validation.json"
)


class _ArrowBuffer(Protocol):
    def to_pybytes(self) -> bytes: ...


class _ArrowBufferOutputStream(Protocol):
    def getvalue(self) -> _ArrowBuffer: ...


class _ArrowTable(Protocol): ...


class _ArrowTableFactory(Protocol):
    def from_pylist(self, rows: list[Mapping[str, JSONValue]]) -> _ArrowTable: ...


class _ArrowModule(Protocol):
    Table: _ArrowTableFactory
    BufferOutputStream: type[_ArrowBufferOutputStream]


class _ParquetModule(Protocol):
    def write_table(
        self,
        table: _ArrowTable,
        where: _ArrowBufferOutputStream,
        *,
        compression: str,
        use_dictionary: bool,
        write_statistics: bool,
    ) -> None: ...


ARROW = cast(_ArrowModule, pyarrow)
PARQUET = cast(_ParquetModule, pyarrow_parquet)


@dataclass(frozen=True, slots=True)
class SolverOracleExecutionRequest:
    project_root: Path
    configuration: TrajCertConfiguration


@dataclass(frozen=True, slots=True)
class SolverOracleCellEvidence:
    law_name: str
    partition_name: str
    rho_offset: float
    rho: float
    validation: PopulationSolverOracleValidationResult
    provenance_digest: str


@dataclass(frozen=True, slots=True)
class SolverOracleAggregateEvidence:
    partition_name: str
    rho_offset: float
    cell_count: int
    maximum_lower_hidden_mass_error: float
    maximum_upper_hidden_mass_error: float
    maximum_risk_upper_error: float
    state_mismatch_count: int
    passed: bool


@dataclass(frozen=True, slots=True)
class SolverOracleExecutionEvidence:
    cells: tuple[SolverOracleCellEvidence, ...]
    aggregates: tuple[SolverOracleAggregateEvidence, ...]
    source_digest: str
    aggregate_digest: str


def execute_solver_oracle_validation(
    request: SolverOracleExecutionRequest,
) -> SolverOracleExecutionEvidence:
    configuration = request.configuration
    laws = _authoritative_laws(configuration)
    cells = tuple(
        _execute_cell(law, partition.name, partition.groups, offset, configuration)
        for law in laws
        for partition in configuration.partitions.primary
        for offset in configuration.sensitivity.theorem_rho_offsets.oracle_validation
    )
    expected_count = (
        len(laws)
        * len(configuration.partitions.primary)
        * len(configuration.sensitivity.theorem_rho_offsets.oracle_validation)
    )
    if len(cells) != expected_count:
        raise ValueError("solver/oracle execution did not cover the authoritative cell grid")
    aggregates = _aggregate(cells)
    if not all(cell.validation.state is OracleValidationState.PASS for cell in cells):
        raise ValueError("solver/oracle validation evidence contains a failed cell")
    source_payload = canonical_json_bytes([_cell_payload(cell) for cell in cells])
    aggregate_payload = _canonical_aggregate_parquet(aggregates)
    source_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SOLVER_ORACLE_SOURCE_RELATIVE_PATH,
            source_payload,
            _validate_source_payload,
        )
    ).sha256_digest
    aggregate_digest = atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SOLVER_ORACLE_AGGREGATE_RELATIVE_PATH,
            aggregate_payload,
            _validate_parquet_payload,
        )
    ).sha256_digest
    completion_payload = canonical_json_bytes(
        {
            "aggregate_digest": aggregate_digest,
            "cell_count": len(cells),
            "completed": True,
            "experiment_name": ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE.value,
            "source_digest": source_digest,
        }
    )
    atomic_write_bytes(
        AtomicWriteInput(
            request.project_root / SOLVER_ORACLE_COMPLETION_RELATIVE_PATH,
            completion_payload,
            _validate_completion_payload,
        )
    )
    return SolverOracleExecutionEvidence(cells, aggregates, source_digest, aggregate_digest)


def _authoritative_laws(
    configuration: TrajCertConfiguration,
) -> tuple[SyntheticTrajectoryLaw, ...]:
    configured_names = tuple(law.name for law in configuration.synthetic_data.laws)
    catalog = synthetic_law_catalog(configuration.synthetic_data, configuration.method)
    laws = tuple(law for law in catalog if law.name in configured_names)
    if tuple(law.name for law in laws) != configured_names:
        raise ValueError(
            "solver/oracle validation requires every configured synthetic law exactly once"
        )
    return laws


def _execute_cell(
    law: SyntheticTrajectoryLaw,
    partition_name: str,
    groups: tuple[tuple[int, ...], ...],
    rho_offset: float,
    configuration: TrajCertConfiguration,
) -> SolverOracleCellEvidence:
    observable_law = law.observable_law().coarsened(CoarseningGroups(groups))
    minimum_information = InformationProfile(observable_law).compatibility_floor()
    if minimum_information.minimum_information_budget is None:
        raise ValueError("solver/oracle validation requires a resolved observable law")
    rho = minimum_information.minimum_information_budget + rho_offset
    validation = validate_population_solver_against_oracle(
        PopulationSolverOracleValidationInput(observable_law, rho, configuration.numerics)
    )
    provenance_digest = hashlib.sha256(
        canonical_json_bytes(
            {
                "law": law.name,
                "partition": partition_name,
                "rho_offset": rho_offset,
                "rho": rho,
                "configuration": configuration.model_dump(mode="json"),
            }
        )
    ).hexdigest()
    return SolverOracleCellEvidence(
        law.name,
        partition_name,
        rho_offset,
        rho,
        validation,
        provenance_digest,
    )


def _aggregate(
    cells: tuple[SolverOracleCellEvidence, ...],
) -> tuple[SolverOracleAggregateEvidence, ...]:
    coordinates = tuple(sorted({(cell.partition_name, cell.rho_offset) for cell in cells}))
    return tuple(
        _aggregate_coordinate(
            tuple(cell for cell in cells if (cell.partition_name, cell.rho_offset) == coordinate),
            coordinate,
        )
        for coordinate in coordinates
    )


def _aggregate_coordinate(
    cells: tuple[SolverOracleCellEvidence, ...],
    coordinate: tuple[str, float],
) -> SolverOracleAggregateEvidence:
    if not cells:
        raise ValueError("solver/oracle aggregate coordinate must contain cells")
    lower_errors = _present_errors(
        tuple(cell.validation.lower_hidden_mass_absolute_error for cell in cells)
    )
    upper_errors = _present_errors(
        tuple(cell.validation.upper_hidden_mass_absolute_error for cell in cells)
    )
    upper_risk_errors = _present_errors(
        tuple(cell.validation.endpoint_absolute_error for cell in cells)
    )
    return SolverOracleAggregateEvidence(
        coordinate[0],
        coordinate[1],
        len(cells),
        max(lower_errors, default=0.0),
        max(upper_errors, default=0.0),
        max(upper_risk_errors, default=0.0),
        sum(cell.validation.state_mismatch_count for cell in cells),
        all(cell.validation.state is OracleValidationState.PASS for cell in cells),
    )


def _cell_payload(cell: SolverOracleCellEvidence) -> Mapping[str, JSONValue]:
    validation = cell.validation
    return {
        "law_name": cell.law_name,
        "partition_name": cell.partition_name,
        "rho_offset": cell.rho_offset,
        "rho": cell.rho,
        "production_state": validation.production.state.value,
        "oracle_state": validation.oracle.state.value,
        "state_mismatch_count": validation.state_mismatch_count,
        "lower_hidden_mass_absolute_error": validation.lower_hidden_mass_absolute_error,
        "upper_hidden_mass_absolute_error": validation.upper_hidden_mass_absolute_error,
        "endpoint_absolute_error": validation.endpoint_absolute_error,
        "maximum_root_bracket_width": validation.maximum_root_bracket_width,
        "maximum_returned_root_residual": validation.maximum_returned_root_residual,
        "state": validation.state.value,
        "provenance_digest": cell.provenance_digest,
    }


def _present_errors(values: tuple[float | None, ...]) -> tuple[float, ...]:
    return tuple(value for value in values if value is not None)


def _canonical_aggregate_parquet(
    aggregates: tuple[SolverOracleAggregateEvidence, ...],
) -> bytes:
    rows: list[Mapping[str, JSONValue]] = [
        {
            "partition_name": aggregate.partition_name,
            "rho_offset_mode": aggregate.rho_offset,
            "cell_count": aggregate.cell_count,
            "max_abs_u_lower_error": aggregate.maximum_lower_hidden_mass_error,
            "max_abs_u_upper_error": aggregate.maximum_upper_hidden_mass_error,
            "max_abs_risk_upper_error": aggregate.maximum_risk_upper_error,
            "state_mismatch_count": aggregate.state_mismatch_count,
            "pass": aggregate.passed,
        }
        for aggregate in aggregates
    ]
    destination = ARROW.BufferOutputStream()
    PARQUET.write_table(
        ARROW.Table.from_pylist(rows),
        destination,
        compression="zstd",
        use_dictionary=False,
        write_statistics=False,
    )
    return destination.getvalue().to_pybytes()


def _validate_source_payload(payload: bytes) -> None:
    if not payload.startswith(b"[") or not payload.endswith(b"]"):
        raise ValueError("solver/oracle source payload must be a canonical JSON array")


def _validate_parquet_payload(payload: bytes) -> None:
    if not payload.startswith(b"PAR1") or not payload.endswith(b"PAR1"):
        raise ValueError("solver/oracle aggregate payload must be Parquet")


def _validate_completion_payload(payload: bytes) -> None:
    if not payload.startswith(b'{"aggregate_digest":') or not payload.endswith(b"}"):
        raise ValueError("solver/oracle completion payload must be canonical JSON")
