from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.plan import PlannedCell
from trajcert.experiments.runner import (
    cell_artifact_index_path,
    cell_completion_path,
    scientific_result_artifact_key,
    scientific_result_path,
)
from trajcert.storage import (
    ArtifactChecksum,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    file_digest,
    model_digest,
    models_digest,
    read_model,
)
from trajcert.types import DomainModel


class SynthesisDependencyReference(DomainModel):
    semantic_cell_key: str
    completion_digest: DigestHex
    scientific_result_digest: DigestHex


def read_verified_scientific_result[ModelT: BaseModel](
    cell: PlannedCell,
    workspace_root: Path,
    model_type: type[ModelT],
) -> ModelT:
    completion, index = _verified_completion_and_index(cell, workspace_root)
    entry = index.artifacts[0]
    expected_path = scientific_result_path(cell)
    if entry.relative_path != expected_path:
        raise InvalidScientificDataError(
            "persisted scientific-result path does not match the planned semantic cell"
        )
    result_path = workspace_root / entry.relative_path
    if file_digest(result_path) != entry.sha256:
        raise InvalidScientificDataError("persisted scientific-result checksum is stale")
    expected_checksum = ArtifactChecksum(
        artifact_key=entry.artifact_key,
        sha256=entry.sha256,
    )
    if completion.artifact_sha256_map != (expected_checksum,):
        raise InvalidScientificDataError(
            "completion checksum map does not match the persisted scientific result"
        )
    return read_model(result_path, model_type)


def synthesis_dependency_fingerprint(
    upstream_cells: tuple[PlannedCell, ...],
    workspace_root: Path,
) -> DependencyFingerprint:
    if not upstream_cells:
        raise InvalidScientificDataError("Statistical Synthesis requires upstream cells")
    references = tuple(
        _dependency_reference(cell, workspace_root)
        for cell in sorted(upstream_cells, key=_cell_order)
    )
    return DependencyFingerprint(str(models_digest(references)))


def verify_synthesis_dependency_fingerprint(
    upstream_cells: tuple[PlannedCell, ...],
    workspace_root: Path,
    expected: DependencyFingerprint,
) -> None:
    observed = synthesis_dependency_fingerprint(upstream_cells, workspace_root)
    if observed != expected:
        raise InvalidScientificDataError(
            "Statistical Synthesis dependency fingerprint does not match persisted upstream evidence"
        )


def _dependency_reference(
    cell: PlannedCell,
    workspace_root: Path,
) -> SynthesisDependencyReference:
    completion, index = _verified_completion_and_index(cell, workspace_root)
    return SynthesisDependencyReference(
        semantic_cell_key=str(cell.identity.semantic_cell_key),
        completion_digest=model_digest(completion),
        scientific_result_digest=index.artifacts[0].sha256,
    )


def _verified_completion_and_index(
    cell: PlannedCell,
    workspace_root: Path,
) -> tuple[CompletionRecord, CellArtifactIndex]:
    if not cell.executable:
        raise InvalidScientificDataError(
            "Statistical Synthesis cannot consume a planned-invalid upstream cell"
        )
    completion = read_model(cell_completion_path(cell, workspace_root), CompletionRecord)
    index = read_model(cell_artifact_index_path(cell, workspace_root), CellArtifactIndex)
    expected_key = scientific_result_artifact_key(cell)
    if completion.semantic_cell_key != cell.identity.semantic_cell_key:
        raise InvalidScientificDataError("upstream completion semantic identity is stale")
    expected_plan_digest = PlanDigest(str(model_digest(cell)))
    if completion.cell_plan_digest != expected_plan_digest:
        raise InvalidScientificDataError("upstream completion cell-plan digest is stale")
    if completion.produced_artifact_keys != (expected_key,):
        raise InvalidScientificDataError(
            "upstream completion must expose exactly one persisted scientific result"
        )
    if completion.expected_artifact_count != 1 or len(index.artifacts) != 1:
        raise InvalidScientificDataError(
            "upstream scientific cell must have exactly one authoritative result artifact"
        )
    if completion.completed_seed_count != completion.expected_seed_count:
        raise InvalidScientificDataError("upstream completion has an incomplete seed count")
    entry = index.artifacts[0]
    if entry.artifact_key != expected_key:
        raise InvalidScientificDataError("upstream artifact index contains the wrong result key")
    if entry.relative_path != scientific_result_path(cell):
        raise InvalidScientificDataError("upstream artifact index contains a stale result path")
    result_path = (workspace_root / entry.relative_path).resolve()
    root = workspace_root.resolve()
    if not result_path.is_relative_to(root) or not result_path.is_file():
        raise InvalidScientificDataError("upstream scientific-result artifact is missing")
    if file_digest(result_path) != entry.sha256:
        raise InvalidScientificDataError("upstream scientific-result checksum mismatch")
    expected_checksum = ArtifactChecksum(
        artifact_key=entry.artifact_key,
        sha256=entry.sha256,
    )
    if completion.artifact_sha256_map != (expected_checksum,):
        raise InvalidScientificDataError("upstream completion checksum map is stale")
    return completion, index


def _cell_order(cell: PlannedCell) -> tuple[int, int, str]:
    return (
        int(cell.experiment_order),
        int(cell.cell_ordinal),
        str(cell.identity.semantic_cell_key),
    )
