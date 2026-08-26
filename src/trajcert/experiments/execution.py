from __future__ import annotations

from pathlib import Path

from trajcert.config import TrajCertConfig
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.dispatch import execute_phase_one_cell
from trajcert.experiments.plan import PlannedCell
from trajcert.experiments.runner import CellExecutionResult, ExecutionContext
from trajcert.paths import ExperimentLeaf, semantic_cell_path
from trajcert.storage import (
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    atomic_write_model,
)

_RESULT_FILENAME = "scientific_result.json"


def scientific_result_artifact_key(cell: PlannedCell) -> ArtifactKey:
    return ArtifactKey(f"scientific-result|{cell.identity.semantic_cell_key}")


def scientific_result_path(cell: PlannedCell) -> Path:
    return (
        semantic_cell_path(
            cell.identity.experiment_slug,
            ExperimentLeaf.EVALUATION_RECORDS,
            cell.identity.path_coordinates,
        )
        / _RESULT_FILENAME
    )


def execute_dispatched_cell(
    cell: PlannedCell,
    context: ExecutionContext,
    config: TrajCertConfig,
) -> CellExecutionResult:
    if str(cell.identity.experiment_name) == "Statistical Synthesis":
        raise InvalidScientificDataError(
            "Statistical Synthesis requires the dedicated cross-experiment executor"
        )
    artifact_key = scientific_result_artifact_key(cell)
    if context.required_artifact_keys != (artifact_key,):
        raise InvalidScientificDataError(
            "dispatched cell execution requires exactly its scientific-result artifact"
        )
    relative_path = scientific_result_path(cell)
    digest = atomic_write_model(
        context.workspace_root / relative_path,
        execute_phase_one_cell(cell, config),
    )
    return CellExecutionResult(
        artifact_index=CellArtifactIndex(
            artifacts=(
                ArtifactIndexEntry(
                    artifact_key=artifact_key,
                    relative_path=relative_path,
                    sha256=digest,
                ),
            )
        ),
        completed_seed_count=context.expected_seed_count,
        metrics_complete=True,
        statistics_complete=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
    )
