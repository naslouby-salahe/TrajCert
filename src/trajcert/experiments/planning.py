from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

from trajcert.domain.records.execution import ExperimentPlanRow
from trajcert.infrastructure.storage import JSONValue, canonical_json_bytes

PLAN_JSON_RELATIVE_PATH = Path("outputs/artifacts/derived/plans/experiment_plan.json")
PLAN_PARQUET_RELATIVE_PATH = Path("outputs/artifacts/derived/plans/experiment_plan.parquet")


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
