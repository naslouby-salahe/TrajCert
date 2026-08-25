from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from trajcert.domain.enums import ExperimentName
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.completion import (
    CompletionExperimentName,
    CompletionRecord,
    completion_records,
)
from trajcert.infrastructure.storage import (
    AtomicWriteInput,
    FilesystemSafeNameInput,
    atomic_write_bytes,
    filesystem_safe_name,
)
from trajcert.reporting.figures import (
    PROJECT_SUMMARY_FIGURE_SOURCE,
    FigureRenderEvidence,
    FigureRenderRequest,
    render_partition_coherence_figure,
)
from trajcert.reporting.tables import (
    PROJECT_SUMMARY_TABLES,
    TableRenderEvidence,
    TableRenderRequest,
    render_parquet_table,
)

_STATISTICAL_SYNTHESIS_NAME = CompletionExperimentName("Statistical Synthesis")
_EVIDENCE_MANIFEST_RELATIVE_PATH = Path(
    "outputs/experiments/statistical-synthesis/provenance/dependencies/evidence_manifest.json"
)


@dataclass(frozen=True, slots=True)
class CompletionExportInput:
    project_root: Path
    experiment_name: CompletionExperimentName | None


@dataclass(frozen=True, slots=True)
class CompletionExport:
    path: Path
    record_count: int


def export_project_summary_tables(project_root: Path) -> tuple[TableRenderEvidence, ...]:
    _require_completed_statistical_synthesis(project_root)
    source_directory = (
        project_root / "outputs/experiments/statistical-synthesis/evaluations/aggregates"
    )
    destination_directory = project_root / "results/project_summary/tables/main"
    return tuple(
        render_parquet_table(
            TableRenderRequest(
                source_directory / f"{source_name}.parquet",
                destination_directory,
                expected_columns,
            )
        )
        for source_name, expected_columns in PROJECT_SUMMARY_TABLES
    )


def export_project_summary_figure(project_root: Path) -> FigureRenderEvidence:
    _require_completed_statistical_synthesis(project_root)
    source = project_root / (
        "outputs/experiments/statistical-synthesis/evaluations/aggregates/"
        f"{PROJECT_SUMMARY_FIGURE_SOURCE}.parquet"
    )
    return render_partition_coherence_figure(
        FigureRenderRequest(source, project_root / "results/project_summary/figures/main")
    )


def export_verified_completion_records(input_value: CompletionExportInput) -> CompletionExport:
    _require_completed_statistical_synthesis(input_value.project_root)
    records = completion_records(input_value.project_root, input_value.experiment_name)
    if not records or any(not record.valid for record in records):
        raise ValueError("report export requires verified completed evidence")
    if input_value.experiment_name is None and not _all_experiments_complete(records):
        raise ValueError("report export requires verified completed evidence")
    name = (
        "all-experiments"
        if input_value.experiment_name is None
        else filesystem_safe_name(FilesystemSafeNameInput(input_value.experiment_name)).value
    )
    destination = (
        input_value.project_root
        / "results/project_summary/reproducibility/execution"
        / f"completion-records-{name}.json"
    )
    payload = canonical_json_bytes(
        tuple(
            {
                "completed": record.completed,
                "completion_path": record.path.relative_to(input_value.project_root).as_posix(),
                "experiment_name": record.experiment_name,
            }
            for record in records
        )
    )
    atomic_write_bytes(
        AtomicWriteInput(destination, payload, lambda value: _validate_payload(value, payload))
    )
    return CompletionExport(destination, len(records))


def _require_completed_statistical_synthesis(project_root: Path) -> None:
    synthesis_records = completion_records(project_root, _STATISTICAL_SYNTHESIS_NAME)
    manifest_path = project_root / _EVIDENCE_MANIFEST_RELATIVE_PATH
    if (
        len(synthesis_records) != 1
        or not synthesis_records[0].valid
        or not _valid_evidence_manifest(manifest_path)
    ):
        raise ValueError("report export requires completed statistical synthesis evidence")


def _valid_evidence_manifest(path: Path) -> bool:
    try:
        value = cast(JSONValue, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and bool(value)


def _all_experiments_complete(records: tuple[CompletionRecord, ...]) -> bool:
    completed_names = {name for record in records for name in record.experiment_names}
    return completed_names == {experiment_name.value for experiment_name in ExperimentName}


def _validate_payload(value: bytes, expected: bytes) -> None:
    if value != expected:
        raise ValueError("completion export payload is not canonical")
