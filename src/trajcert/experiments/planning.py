from __future__ import annotations

import hashlib
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from trajcert.domain.records.execution import ExperimentPlanRow
from trajcert.infrastructure.storage import JSONValue, atomic_write_bytes, canonical_json_bytes

PLAN_JSON_RELATIVE_PATH = Path("outputs/artifacts/derived/plans/experiment_plan.json")
PLAN_PARQUET_RELATIVE_PATH = Path("outputs/artifacts/derived/plans/experiment_plan.parquet")


class ArrowBuffer(Protocol):
    def to_pybytes(self) -> bytes: ...


class ArrowBufferOutputStream(Protocol):
    def getvalue(self) -> ArrowBuffer: ...


class ArrowTable(Protocol):
    column_names: list[str]


class ArrowTableFactory(Protocol):
    def from_pylist(self, rows: list[dict[str, JSONValue]]) -> ArrowTable: ...


class ArrowModule(Protocol):
    Table: ArrowTableFactory
    BufferOutputStream: Callable[[], ArrowBufferOutputStream]


class ParquetModule(Protocol):
    def write_table(
        self,
        table: ArrowTable,
        where: ArrowBufferOutputStream,
        *,
        compression: str,
        use_dictionary: bool,
        write_statistics: bool,
    ) -> None: ...


ARROW = cast(ArrowModule, importlib.import_module("pyarrow"))
PARQUET = cast(ParquetModule, importlib.import_module("pyarrow.parquet"))


def ordered_plan_rows(rows: tuple[ExperimentPlanRow, ...]) -> tuple[ExperimentPlanRow, ...]:
    return tuple(sorted(rows, key=_plan_sort_key))


def plan_digest(rows: tuple[ExperimentPlanRow, ...]) -> str:
    return hashlib.sha256(canonical_plan_json(rows)).hexdigest()


def canonical_plan_json(rows: tuple[ExperimentPlanRow, ...]) -> bytes:
    ordered_rows = ordered_plan_rows(rows)
    serialized_rows = [cast(JSONValue, row.model_dump(mode="json")) for row in ordered_rows]
    return canonical_json_bytes(serialized_rows)


def cell_plan_digest(row: ExperimentPlanRow) -> str:
    serialized_row = cast(JSONValue, row.model_dump(mode="json"))
    return hashlib.sha256(canonical_json_bytes(serialized_row)).hexdigest()


def canonical_plan_parquet(rows: tuple[ExperimentPlanRow, ...]) -> bytes:
    ordered_rows = ordered_plan_rows(rows)
    serialized_rows = [
        cast(dict[str, JSONValue], row.model_dump(mode="json")) for row in ordered_rows
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
) -> tuple[str, str]:
    canonical_json = canonical_plan_json(rows)
    canonical_parquet = canonical_plan_parquet(rows)
    json_digest = atomic_write_bytes(
        project_root / PLAN_JSON_RELATIVE_PATH,
        canonical_json,
        lambda payload: _validate_plan_json(payload, rows),
    )
    parquet_digest = atomic_write_bytes(
        project_root / PLAN_PARQUET_RELATIVE_PATH,
        canonical_parquet,
        _validate_plan_parquet,
    )
    return json_digest, parquet_digest


def _validate_plan_json(payload: bytes, rows: tuple[ExperimentPlanRow, ...]) -> None:
    if payload != canonical_plan_json(rows):
        raise ValueError("plan JSON payload is not canonical")


def _validate_plan_parquet(payload: bytes) -> None:
    if not payload.startswith(b"PAR1") or not payload.endswith(b"PAR1"):
        raise ValueError("plan Parquet payload has an invalid signature")


def _plan_sort_key(
    row: ExperimentPlanRow,
) -> tuple[
    str,
    str,
    tuple[int, str],
    tuple[int, str],
    tuple[int, str],
    tuple[int, float],
    tuple[int, float],
    tuple[int, int],
    tuple[int, str],
]:
    return (
        row.execution_group or "",
        row.experiment_name or "",
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
