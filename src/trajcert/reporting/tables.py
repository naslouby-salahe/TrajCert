from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Protocol, cast

import pyarrow.parquet as pyarrow_parquet

from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import AtomicWriteInput, atomic_write_bytes

PROJECT_SUMMARY_TABLES = (
    (
        "theorem_validation_summary",
        (
            "theorem_name",
            "case_count",
            "maximum_absolute_error",
            "minimum_inequality_margin",
            "all_cases_pass",
            "primary_artifact",
            "scientific_consequence",
        ),
    ),
    (
        "partition_timing_results",
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
    ),
    (
        "compatibility_safety",
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
    ),
    (
        "rho_utility",
        (
            "analysis_type",
            "law_name",
            "rho",
            "partition_name",
            "baseline_partition_name",
            "metric_name",
            "metric_value",
            "compatibility_state",
            "tau",
            "risk_upper",
            "identified_width",
            "worst_case_upper",
            "absolute_tightening",
            "relative_unresolved_gain",
            "materiality_pass",
            "method_mean",
            "baseline_mean",
            "mean_paired_difference",
            "bootstrap_lower_95",
            "bootstrap_upper_95",
            "holm_adjusted_p",
            "never_certified_fraction_method",
            "never_certified_fraction_baseline",
        ),
    ),
    (
        "claim_registry",
        (
            "claim_name",
            "claim",
            "required_experiments",
            "primary_metric",
            "minimum_support_condition",
            "final_state",
            "supporting_table",
            "supporting_figure",
            "scope",
            "forbidden_extrapolation",
        ),
    ),
)


class _ArrowSchema(Protocol):
    @property
    def names(self) -> list[str]: ...


class _ArrowTable(Protocol):
    @property
    def schema(self) -> _ArrowSchema: ...

    def to_pylist(self) -> list[Mapping[str, JSONValue]]: ...


class _ParquetModule(Protocol):
    def read_table(self, source: Path) -> _ArrowTable: ...


PARQUET = cast(_ParquetModule, pyarrow_parquet)


@dataclass(frozen=True, slots=True)
class TableRenderRequest:
    source_path: Path
    destination_directory: Path
    expected_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TableRenderEvidence:
    csv_path: Path
    tex_path: Path
    row_count: int


def render_parquet_table(request: TableRenderRequest) -> TableRenderEvidence:
    if not request.source_path.is_file():
        raise ValueError("table rendering requires an authoritative Parquet source")
    table = PARQUET.read_table(request.source_path)
    columns = tuple(table.schema.names)
    if columns != request.expected_columns:
        raise ValueError("authoritative table schema does not match its report contract")
    rows = table.to_pylist()
    if any(frozenset(row) != frozenset(columns) for row in rows):
        raise ValueError("authoritative table rows do not match the Parquet schema")
    csv_path = request.destination_directory / f"{request.source_path.stem}.csv"
    tex_path = request.destination_directory / f"{request.source_path.stem}.tex"
    atomic_write_bytes(
        AtomicWriteInput(csv_path, _csv_bytes(columns, rows), _validate_tabular_bytes)
    )
    atomic_write_bytes(
        AtomicWriteInput(tex_path, _tex_bytes(columns, rows), _validate_tabular_bytes)
    )
    return TableRenderEvidence(csv_path, tex_path, len(rows))


def _csv_bytes(columns: tuple[str, ...], rows: list[Mapping[str, JSONValue]]) -> bytes:
    destination = StringIO(newline="")
    writer = csv.writer(destination, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(tuple(_display(row[column]) for column in columns) for row in rows)
    return destination.getvalue().encode("utf-8")


def _tex_bytes(columns: tuple[str, ...], rows: list[Mapping[str, JSONValue]]) -> bytes:
    alignment = "l" * len(columns)
    header = " & ".join(_tex_escape(column) for column in columns)
    body = "\n".join(
        " & ".join(_tex_escape(_display(row[column])) for column in columns) + r" \\"
        for row in rows
    )
    value = "\n".join(
        (
            r"\begin{tabular}{" + alignment + "}",
            r"\hline",
            header + r" \\",
            r"\hline",
            body,
            r"\hline",
            r"\end{tabular}",
            "",
        )
    )
    return value.encode("utf-8")


def _display(value: JSONValue) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (bool, int, float)):
        return str(value).lower()
    return canonical_json_bytes(value).decode("utf-8")


def _tex_escape(value: str) -> str:
    return (
        value.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
        .replace("#", r"\#")
    )


def _validate_tabular_bytes(value: bytes) -> None:
    if not value:
        raise ValueError("rendered table must not be empty")
