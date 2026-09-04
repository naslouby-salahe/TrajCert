from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from trajcert.config import active_config
from trajcert.exceptions import (
    InvalidScientificDataError,
    InvariantViolationError,
    SerializationError,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell
from trajcert.paths import (
    ArtifactFile,
    ExperimentLeaf,
    artifact_path,
    checkpoint_batch_file,
    long_path_safe,
    semantic_cell_path,
)
from trajcert.provenance import (
    ArtifactTypeName,
    DependencyMaterial,
    EnvironmentDigest,
    ParentArtifactIdentity,
    dependency_fingerprint,
)
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    PlanDigest,
    SpecificationDigest,
    file_digest,
    model_digest,
    read_model,
)
from trajcert.types import BatchIndex

if TYPE_CHECKING:
    from trajcert.experiments.models import CellExecutionResult, ExecutionContext


class ScientificArtifactKeyPrefix(StrEnum):
    SCIENTIFIC_RESULT = "scientific-result|"


SCIENTIFIC_RESULT_ARTIFACT_TYPE: Final[ArtifactTypeName] = ArtifactTypeName("scientific-result")


def completion_is_compatible(
    cell: PlannedCell, context: ExecutionContext, completion_path: Path
) -> bool:
    try:
        completion = read_model(completion_path, CompletionRecord)
        if not _completion_identity_matches(cell, context, completion):
            return False
        index_path = cell_artifact_index_path(cell, context.workspace_root)
        index = read_model(index_path, CellArtifactIndex)
        _verify_completion_artifacts(completion, index, context.workspace_root)
    except (SerializationError, InvariantViolationError):
        return False
    return True


def cell_completion_path(cell: PlannedCell, workspace_root: Path) -> Path:
    directory = semantic_cell_path(
        cell.identity.experiment_slug,
        ExperimentLeaf.CHECKPOINTS_EXECUTION,
        cell.identity.path_coordinates,
    )
    return workspace_root / artifact_path(directory, ArtifactFile.COMPLETION)


def cell_running_path(cell: PlannedCell, workspace_root: Path) -> Path:
    return cell_completion_path(cell, workspace_root).with_name(ArtifactFile.RUNNING)


def cell_artifact_index_path(cell: PlannedCell, workspace_root: Path) -> Path:
    return cell_completion_path(cell, workspace_root).with_name(ArtifactFile.ARTIFACT_INDEX)


def cell_checkpoint_batch_path(
    cell: PlannedCell, workspace_root: Path, batch_index: BatchIndex
) -> Path:
    return cell_completion_path(cell, workspace_root).with_name(checkpoint_batch_file(batch_index))


def cell_checkpoint_batch_result_path(
    cell: PlannedCell, workspace_root: Path, batch_index: BatchIndex
) -> Path:
    return cell_completion_path(cell, workspace_root).with_name(
        checkpoint_batch_file(batch_index, result=True)
    )


def cell_failure_path(cell: PlannedCell, workspace_root: Path) -> Path:
    directory = semantic_cell_path(
        cell.identity.experiment_slug,
        ExperimentLeaf.LOGS_FAILURES,
        cell.identity.path_coordinates,
    )
    return workspace_root / artifact_path(directory, ArtifactFile.FAILURE)


def cell_plan_digest(cell: PlannedCell) -> PlanDigest:
    return PlanDigest(model_digest(cell))


def _completion_identity_matches(
    cell: PlannedCell,
    context: ExecutionContext,
    completion: CompletionRecord,
) -> bool:
    checks = (
        completion.semantic_cell_key == cell.identity.semantic_cell_key,
        completion.cell_plan_digest == cell_plan_digest(cell),
        completion.scientific_specification_digest == context.scientific_specification_digest,
        completion.dependency_fingerprint == context.dependency_fingerprint,
        completion.required_artifact_keys == context.required_artifact_keys,
        completion.expected_seed_count == context.expected_seed_count,
        completion.completed_seed_count == completion.expected_seed_count,
    )
    return all(checks)


def validate_execution_result(
    result: CellExecutionResult,
    context: ExecutionContext,
) -> None:
    produced = tuple(entry.artifact_key for entry in result.artifact_index.artifacts)
    if len(produced) != len(set(produced)):
        raise InvariantViolationError("executor produced duplicate artifact keys")
    if any(key not in produced for key in context.required_artifact_keys):
        raise InvariantViolationError("executor omitted a required artifact key")
    if result.completed_seed_count != context.expected_seed_count:
        raise InvariantViolationError("executor returned an incomplete seed count")


def verify_artifacts(index: CellArtifactIndex, workspace_root: Path) -> None:
    root = workspace_root.resolve()
    for entry in index.artifacts:
        artifact_path_resolved = (workspace_root / entry.relative_path).resolve()
        if not artifact_path_resolved.is_relative_to(root):
            raise InvariantViolationError("artifact path escapes the workspace root")
        if not long_path_safe(artifact_path_resolved).is_file():
            raise InvariantViolationError(
                f"required produced artifact is missing: {entry.artifact_key}"
            )
        if file_digest(artifact_path_resolved) != entry.sha256:
            raise InvariantViolationError(
                f"produced artifact checksum mismatch: {entry.artifact_key}"
            )


def _verify_completion_artifacts(
    completion: CompletionRecord,
    index: CellArtifactIndex,
    workspace_root: Path,
) -> None:
    indexed = tuple(entry.artifact_key for entry in index.artifacts)
    if indexed != completion.produced_artifact_keys:
        raise SerializationError("persisted artifact index does not match completion record")
    expected_checksums = tuple(
        ArtifactChecksum(artifact_key=entry.artifact_key, sha256=entry.sha256)
        for entry in sorted(index.artifacts, key=lambda item: item.artifact_key)
    )
    if expected_checksums != completion.artifact_sha256_map:
        raise SerializationError("persisted artifact checksums do not match completion record")
    verify_artifacts(index, workspace_root)


def completion_record(
    cell: PlannedCell,
    context: ExecutionContext,
    result: CellExecutionResult,
) -> CompletionRecord:
    produced = tuple(entry.artifact_key for entry in result.artifact_index.artifacts)
    checksums = tuple(
        _checksum(entry)
        for entry in sorted(result.artifact_index.artifacts, key=lambda item: item.artifact_key)
    )
    return CompletionRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        cell_plan_digest=cell_plan_digest(cell),
        scientific_specification_digest=context.scientific_specification_digest,
        dependency_fingerprint=context.dependency_fingerprint,
        required_artifact_keys=context.required_artifact_keys,
        produced_artifact_keys=produced,
        artifact_sha256_map=checksums,
        completed_seed_count=result.completed_seed_count,
        expected_seed_count=context.expected_seed_count,
    )


def _checksum(entry: ArtifactIndexEntry) -> ArtifactChecksum:
    return ArtifactChecksum(artifact_key=entry.artifact_key, sha256=entry.sha256)


def scientific_specification_digest() -> SpecificationDigest:
    return SpecificationDigest(model_digest(active_config.get()))


def cell_dependency_material(
    workspace_root: Path,
    plan: ExperimentPlan,
    cell: PlannedCell,
    scientific_specification: SpecificationDigest,
    environment_dependency_digest: EnvironmentDigest,
) -> DependencyMaterial:
    required = set(cell.required_experiments)
    parents = tuple(item for item in plan.cells if item.identity.experiment_name in required)
    parent_identities = tuple(
        identity
        for parent in parents
        if (identity := _parent_artifact_identity(parent, workspace_root)) is not None
    )
    return DependencyMaterial(
        artifact_type=SCIENTIFIC_RESULT_ARTIFACT_TYPE,
        semantic_cell=cell.identity,
        scientific_specification_digest=scientific_specification,
        environment_dependency_digest=environment_dependency_digest,
        parents=parent_identities,
    )


def cell_dependency_fingerprint(
    workspace_root: Path,
    plan: ExperimentPlan,
    cell: PlannedCell,
    scientific_specification: SpecificationDigest,
    environment_dependency_digest: EnvironmentDigest,
) -> DependencyFingerprint:
    material = cell_dependency_material(
        workspace_root,
        plan,
        cell,
        scientific_specification,
        environment_dependency_digest,
    )
    return dependency_fingerprint(material)


def _parent_artifact_identity(
    parent: PlannedCell, workspace_root: Path
) -> ParentArtifactIdentity | None:
    index_path = cell_artifact_index_path(parent, workspace_root)
    if not index_path.is_file():
        return None
    index = read_model(index_path, CellArtifactIndex)
    artifact_key = scientific_result_artifact_key(parent)
    entry = next((item for item in index.artifacts if item.artifact_key == artifact_key), None)
    if entry is None:
        return None
    return ParentArtifactIdentity(artifact_key=artifact_key, scientific_content_digest=entry.sha256)


def scientific_result_artifact_key(cell: PlannedCell) -> ArtifactKey:
    return ArtifactKey(
        f"{ScientificArtifactKeyPrefix.SCIENTIFIC_RESULT}{cell.identity.semantic_cell_key}"
    )


def scientific_result_path(cell: PlannedCell) -> Path:
    return (
        semantic_cell_path(
            cell.identity.experiment_slug,
            ExperimentLeaf.EVALUATION_RECORDS,
            cell.identity.path_coordinates,
        )
        / ArtifactFile.SCIENTIFIC_RESULT
    )


def read_verified_scientific_result[ModelT: BaseModel](
    cell: PlannedCell,
    workspace_root: Path,
    model_type: type[ModelT],
) -> ModelT:
    completion, index = verified_upstream_completion_and_index(cell, workspace_root)
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


def verified_upstream_completion_and_index(
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
    _validate_upstream_completion(completion, cell, expected_key, index)
    entry = index.artifacts[0]
    _validate_upstream_artifact_entry(entry, cell, workspace_root, expected_key)
    expected_checksum = ArtifactChecksum(
        artifact_key=entry.artifact_key,
        sha256=entry.sha256,
    )
    if completion.artifact_sha256_map != (expected_checksum,):
        raise InvalidScientificDataError("upstream completion checksum map is stale")
    return completion, index


def _validate_upstream_completion(
    completion: CompletionRecord,
    cell: PlannedCell,
    expected_key: ArtifactKey,
    index: CellArtifactIndex,
) -> None:
    if completion.semantic_cell_key != cell.identity.semantic_cell_key:
        raise InvalidScientificDataError("upstream completion semantic identity is stale")
    expected_plan_digest = PlanDigest(model_digest(cell))
    if completion.cell_plan_digest != expected_plan_digest:
        raise InvalidScientificDataError("upstream completion cell-plan digest is stale")
    if completion.produced_artifact_keys != (expected_key,):
        raise InvalidScientificDataError(
            "upstream completion must expose exactly one persisted scientific result"
        )
    if len(index.artifacts) != 1:
        raise InvalidScientificDataError(
            "upstream scientific cell must have exactly one authoritative result artifact"
        )
    if completion.completed_seed_count != completion.expected_seed_count:
        raise InvalidScientificDataError("upstream completion has an incomplete seed count")


def _validate_upstream_artifact_entry(
    entry: ArtifactIndexEntry,
    cell: PlannedCell,
    workspace_root: Path,
    expected_key: ArtifactKey,
) -> None:
    if entry.artifact_key != expected_key:
        raise InvalidScientificDataError("upstream artifact index contains the wrong result key")
    if entry.relative_path != scientific_result_path(cell):
        raise InvalidScientificDataError("upstream artifact index contains a stale result path")
    result_path = (workspace_root / entry.relative_path).resolve()
    root = workspace_root.resolve()
    if not result_path.is_relative_to(root) or not long_path_safe(result_path).is_file():
        raise InvalidScientificDataError("upstream scientific-result artifact is missing")
    if file_digest(result_path) != entry.sha256:
        raise InvalidScientificDataError("upstream scientific-result checksum mismatch")
