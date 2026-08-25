from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import pyarrow as pyarrow
import pyarrow.parquet as pyarrow_parquet

from trajcert.configuration.models import TrajCertConfiguration
from trajcert.domain.enums import PublicExecutionState
from trajcert.domain.records.artifacts import Digest
from trajcert.domain.records.execution import ExperimentPlanRow
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.experiments.registry import (
    CURRENT_EXPERIMENT_REGISTRY,
    PlannedExperimentCell,
    expand_experiment_registry,
)
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes

PLAN_JSON_RELATIVE_PATH = Path("outputs/artifacts/derived/plans/experiment_plan.json")
PLAN_PARQUET_RELATIVE_PATH = Path("outputs/artifacts/derived/plans/experiment_plan.parquet")


class _ArrowBuffer(Protocol):
    def to_pybytes(self) -> bytes: ...


class _ArrowBufferOutputStream(Protocol):
    def getvalue(self) -> _ArrowBuffer: ...


class _ArrowTable(Protocol):
    column_names: list[str]


class _ArrowTableFactory(Protocol):
    def from_pylist(self, rows: list[Mapping[str, JSONValue]]) -> _ArrowTable: ...


class _ArrowModule(Protocol):
    Table: _ArrowTableFactory
    BufferOutputStream: Callable[[], _ArrowBufferOutputStream]


class _ParquetModule(Protocol):
    def write_table(
        self,
        table: _ArrowTable,
        where: _ArrowBufferOutputStream,
        *,
        compression: str,
        use_dictionary: bool,
        write_statistics: bool,
    ) -> None:
        raise NotImplementedError((table, where, compression, use_dictionary, write_statistics))


ARROW = cast(_ArrowModule, pyarrow)
PARQUET = cast(_ParquetModule, pyarrow_parquet)


@dataclass(frozen=True)
class PlanArtifactWriteResult:
    json_digest: Digest
    parquet_digest: Digest


def expand_authoritative_plan(
    configuration: TrajCertConfiguration,
) -> tuple[PlannedExperimentCell, ...]:
    return expand_experiment_registry(CURRENT_EXPERIMENT_REGISTRY, configuration)


def materialized_plan_rows(
    configuration: TrajCertConfiguration,
) -> tuple[ExperimentPlanRow, ...]:
    configuration_digest = _digest(configuration.model_dump(mode="json"))
    registry_digest = _digest(
        tuple(
            {
                "cells": experiment.expected_semantic_cell_count,
                "class": experiment.evidence_class.value,
                "execution_group": experiment.execution_group,
                "expansion": experiment.expansion,
                "experiment": experiment.name.value,
            }
            for experiment in CURRENT_EXPERIMENT_REGISTRY
        )
    )
    rows = tuple(
        _materialize_plan_row(cell, configuration, configuration_digest, registry_digest)
        for cell in expand_authoritative_plan(configuration)
    )
    expected_cell_count = sum(
        experiment.expected_semantic_cell_count for experiment in CURRENT_EXPERIMENT_REGISTRY
    )
    if len(rows) != expected_cell_count:
        raise ValueError("materialized plan row count must match the authoritative registry")
    if len({row.semantic_cell_key for row in rows}) != len(rows):
        raise ValueError("materialized plan rows must have unique semantic cell keys")
    if len({row.artifact_key for row in rows}) != len(rows):
        raise ValueError("materialized plan rows must have unique artifact keys")
    return ordered_plan_rows(rows)


def materialize_authoritative_plan(
    project_root: Path,
    configuration: TrajCertConfiguration,
) -> tuple[ExperimentPlanRow, ...]:
    rows = materialized_plan_rows(configuration)
    write_plan_artifacts(project_root, rows)
    return rows


def ordered_plan_rows(rows: tuple[ExperimentPlanRow, ...]) -> tuple[ExperimentPlanRow, ...]:
    return tuple(sorted(rows, key=_plan_sort_key))


def plan_digest(rows: tuple[ExperimentPlanRow, ...]) -> Digest:
    return hashlib.sha256(canonical_plan_json(rows)).hexdigest()


def canonical_plan_json(rows: tuple[ExperimentPlanRow, ...]) -> bytes:
    ordered_rows = ordered_plan_rows(rows)
    serialized_rows = [cast(JSONValue, row.model_dump(mode="json")) for row in ordered_rows]
    return canonical_json_bytes(serialized_rows)


def cell_plan_digest(row: ExperimentPlanRow) -> Digest:
    serialized_row = cast(JSONValue, row.model_dump(mode="json"))
    return hashlib.sha256(canonical_json_bytes(serialized_row)).hexdigest()


def canonical_plan_parquet(rows: tuple[ExperimentPlanRow, ...]) -> bytes:
    ordered_rows = ordered_plan_rows(rows)
    serialized_rows = [
        cast(Mapping[str, JSONValue], row.model_dump(mode="json")) for row in ordered_rows
    ]
    destination = ARROW.BufferOutputStream()
    PARQUET.write_table(
        ARROW.Table.from_pylist(serialized_rows),
        destination,
        compression="zstd",
        use_dictionary=False,
        write_statistics=False,
    )
    return destination.getvalue().to_pybytes()


def write_plan_artifacts(
    project_root: Path,
    rows: tuple[ExperimentPlanRow, ...],
) -> PlanArtifactWriteResult:
    canonical_json = canonical_plan_json(rows)
    canonical_parquet = canonical_plan_parquet(rows)
    json_result = atomic_write_bytes(
        AtomicWriteInput(
            project_root / PLAN_JSON_RELATIVE_PATH,
            canonical_json,
            lambda payload: _validate_plan_json(payload, rows),
        )
    )
    parquet_result = atomic_write_bytes(
        AtomicWriteInput(
            project_root / PLAN_PARQUET_RELATIVE_PATH,
            canonical_parquet,
            _validate_plan_parquet,
        )
    )
    return PlanArtifactWriteResult(json_result.sha256_digest, parquet_result.sha256_digest)


def _validate_plan_json(payload: bytes, rows: tuple[ExperimentPlanRow, ...]) -> None:
    if payload != canonical_plan_json(rows):
        raise ValueError("plan JSON payload is not canonical")


def _validate_plan_parquet(payload: bytes) -> None:
    if not payload.startswith(b"PAR1") or not payload.endswith(b"PAR1"):
        raise ValueError("plan Parquet payload has an invalid signature")


def _plan_sort_key(
    row: ExperimentPlanRow,
) -> tuple[
    tuple[int, str],
    tuple[int, str],
    tuple[int, str],
    tuple[int, str],
    tuple[int, str],
    tuple[int, float],
    tuple[int, float],
    tuple[int, int],
    tuple[int, str],
]:
    return (
        _nullable_string(row.execution_group),
        _nullable_string(row.experiment_name),
        _nullable_string(row.synthetic_law_name),
        _nullable_string(row.partition_name),
        _nullable_string(row.method_name),
        _nullable_float(row.rho),
        _nullable_float(row.beta),
        _nullable_integer(row.seed_index_start),
        _nullable_string(row.semantic_cell_key),
    )


def _nullable_string(value: str | None) -> tuple[int, str]:
    return (0, "") if value is None else (1, value)


def _nullable_float(value: float | None) -> tuple[int, float]:
    return (0, 0.0) if value is None else (1, value)


def _nullable_integer(value: int | None) -> tuple[int, int]:
    return (0, 0) if value is None else (1, value)


def _materialize_plan_row(
    cell: PlannedExperimentCell,
    configuration: TrajCertConfiguration,
    configuration_digest: str,
    registry_digest: str,
) -> ExperimentPlanRow:
    coordinates = cast(Mapping[str, JSONValue], json.loads(cell.semantic_coordinates))
    expected_stream_count, seed_index_start, seed_index_stop_exclusive = _seed_range(
        cell.experiment.name.value,
        configuration,
    )
    law = _string_coordinate(coordinates, "law")
    partition = _string_coordinate(coordinates, "partition")
    row_digest = _digest(
        {
            "configuration_digest": configuration_digest,
            "registry_digest": registry_digest,
            "semantic_cell_key": cell.semantic_cell_key,
        }
    )
    artifact_key = _plan_artifact_key(cell.experiment.name.value, coordinates)
    expected_output_path = (
        f"{configuration.artifacts.execution_workspace_root}/artifacts/active/"
        f"experiment_cells/{artifact_key}.json"
    )
    return ExperimentPlanRow(
        artifact_key=artifact_key,
        artifact_type="experiment_plan_row",
        artifact_owner="authoritative_experiment_registry",
        producer_component="trajcert.experiments.planning",
        semantic_cell_key=cell.semantic_cell_key,
        semantic_coordinates=cell.semantic_coordinates,
        experiment_name=cell.experiment.name.value,
        classification=cell.experiment.evidence_class,
        execution_group=cell.experiment.execution_group,
        scientific_specification_digest=configuration_digest,
        scientific_dependency_digest=registry_digest,
        provenance_fingerprint=row_digest,
        dependency_fingerprint=row_digest,
        implementation_component_digest=registry_digest,
        environment_dependency_digest=configuration_digest,
        status=PublicExecutionState.NOT_STARTED,
        synthetic_law_name=law,
        partition_name=partition,
        rho=_float_coordinate(coordinates, "rho"),
        beta=_float_coordinate(coordinates, "beta"),
        executable=True,
        sensitivity_parameter_json=cell.semantic_coordinates,
        seed_namespace=_seed_namespace(law, configuration, expected_stream_count),
        seed_index_start=seed_index_start,
        seed_index_stop_exclusive=seed_index_stop_exclusive,
        expected_stream_count=expected_stream_count,
        expected_artifact_schema="experiment_result",
        expected_output_path=expected_output_path,
        dependency_coordinates=cell.semantic_coordinates,
        schema_name="experiment_plan_row",
    )


def _seed_range(
    experiment_name: str,
    configuration: TrajCertConfiguration,
) -> tuple[int, int | None, int | None]:
    if experiment_name == "Anytime Coverage Stress":
        indices = configuration.sequential_inference.coverage_validation.seed_indices
        return indices.stop_exclusive - indices.start, indices.start, indices.stop_exclusive
    if experiment_name == "Sequential Sensitivity Utility":
        indices = configuration.sequential_inference.sequential_utility.seed_indices
        return indices.stop_exclusive - indices.start, indices.start, indices.stop_exclusive
    return 0, None, None


def _seed_namespace(
    law: str | None,
    configuration: TrajCertConfiguration,
    expected_stream_count: int,
) -> str | None:
    if law is None or expected_stream_count == 0:
        return None
    finest_partition = configuration.partitions.primary[0]
    return f"Event stream|law={law}|K={len(finest_partition.groups)}"


def _string_coordinate(coordinates: Mapping[str, JSONValue], name: str) -> str | None:
    value = coordinates.get(name)
    return value if isinstance(value, str) else None


def _float_coordinate(coordinates: Mapping[str, JSONValue], name: str) -> float | None:
    value = coordinates.get(name)
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, int | float) else None


def _plan_artifact_key(experiment_name: str, coordinates: Mapping[str, JSONValue]) -> str:
    coordinate_segments = "-".join(
        f"{_key_segment(name)}-{_key_segment(_coordinate_token(value))}"
        for name, value in coordinates.items()
    )
    return f"experiment-plan-row-{_key_segment(experiment_name)}-{coordinate_segments}"


def _coordinate_token(value: JSONValue) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _key_segment(value: str) -> str:
    rendered = "".join(
        character.lower()
        if character.isascii() and character.isalnum()
        else "-minus-"
        if character == "-"
        else "-"
        for character in value
    )
    return rendered.strip("-")


def _digest(value: JSONValue) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
