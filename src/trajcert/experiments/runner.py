from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NewType

from trajcert.exceptions import InvariantViolationError, SerializationError
from trajcert.experiments.plan import PlannedCell
from trajcert.paths import ExperimentLeaf, semantic_cell_path
from trajcert.provenance import ExperimentNameValue
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    ProvenanceFingerprint,
    SpecificationDigest,
    atomic_write_model,
    file_digest,
    read_model,
    write_completion_last,
)
from trajcert.types import DomainModel, NonNegativeInt, PublicExecutionState, ReasonCode

FailureType = NewType("FailureType", str)
FailureMessage = NewType("FailureMessage", str)


class DependencyReadiness(DomainModel):
    experiment_name: ExperimentNameValue
    state: PublicExecutionState


class ExecutionContext(DomainModel):
    workspace_root: Path
    plan_digest: PlanDigest
    scientific_specification_digest: SpecificationDigest
    scientific_dependency_digest: SpecificationDigest
    provenance_fingerprint: ProvenanceFingerprint
    dependency_fingerprint: DependencyFingerprint
    manifest_digest: DigestHex
    required_artifact_keys: tuple[ArtifactKey, ...]
    expected_seed_count: NonNegativeInt


class CellExecutionResult(DomainModel):
    artifact_index: CellArtifactIndex
    completed_seed_count: NonNegativeInt
    metrics_complete: bool
    statistics_complete: bool
    invariant_validation_pass: bool
    dependency_validation_pass: bool
    provenance_record_complete: bool


class RunningRecord(DomainModel):
    semantic_cell_key: str
    plan_digest: PlanDigest
    dependency_fingerprint: DependencyFingerprint


class FailureRecord(DomainModel):
    semantic_cell_key: str
    plan_digest: PlanDigest
    dependency_fingerprint: DependencyFingerprint
    failure_type: FailureType
    message: FailureMessage


class CellRunOutcome(DomainModel):
    state: PublicExecutionState
    reused: bool
    completion_path: Path
    failure_path: Path
    reason: ReasonCode | None


CellExecutor = Callable[[PlannedCell, ExecutionContext], CellExecutionResult]


def run_cell(
    cell: PlannedCell,
    context: ExecutionContext,
    dependencies: tuple[DependencyReadiness, ...],
    executor: CellExecutor,
    overwrite: bool,
) -> CellRunOutcome:
    completion_path = cell_completion_path(cell, context.workspace_root)
    failure_path = cell_failure_path(cell, context.workspace_root)
    running_path = cell_running_path(cell, context.workspace_root)
    if not cell.executable:
        return CellRunOutcome(
            state=PublicExecutionState.INVALID,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=cell.invalid_reason,
        )
    dependency_reason = dependency_block_reason(cell, dependencies)
    if dependency_reason is not None:
        return CellRunOutcome(
            state=PublicExecutionState.BLOCKED,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=dependency_reason,
        )
    if completion_path.is_file() and not overwrite:
        if completion_is_compatible(cell, context, completion_path):
            return CellRunOutcome(
                state=PublicExecutionState.COMPLETED,
                reused=True,
                completion_path=completion_path,
                failure_path=failure_path,
                reason=None,
            )
    completion_path.unlink(missing_ok=True)
    failure_path.unlink(missing_ok=True)
    running_record = RunningRecord(
        semantic_cell_key=str(cell.identity.semantic_cell_key),
        plan_digest=context.plan_digest,
        dependency_fingerprint=context.dependency_fingerprint,
    )
    atomic_write_model(running_path, running_record)
    try:
        result = executor(cell, context)
        _validate_execution_result(result, context)
        _verify_artifacts(result.artifact_index, context.workspace_root)
        atomic_write_model(
            cell_artifact_index_path(cell, context.workspace_root), result.artifact_index
        )
        completion = _completion_record(cell, context, result)
        write_completion_last(completion_path.parent, completion)
        failure_path.unlink(missing_ok=True)
        return CellRunOutcome(
            state=PublicExecutionState.COMPLETED,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=None,
        )
    except Exception as exc:
        failure = FailureRecord(
            semantic_cell_key=str(cell.identity.semantic_cell_key),
            plan_digest=context.plan_digest,
            dependency_fingerprint=context.dependency_fingerprint,
            failure_type=FailureType(type(exc).__name__),
            message=FailureMessage(str(exc)),
        )
        atomic_write_model(failure_path, failure)
        completion_path.unlink(missing_ok=True)
        return CellRunOutcome(
            state=PublicExecutionState.FAILED,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=ReasonCode("TECHNICAL_EXECUTION_FAILURE"),
        )
    finally:
        running_path.unlink(missing_ok=True)


def dependency_block_reason(
    cell: PlannedCell, dependencies: tuple[DependencyReadiness, ...]
) -> ReasonCode | None:
    supplied = {item.experiment_name: item.state for item in dependencies}
    if any(name not in supplied for name in cell.required_experiments):
        return ReasonCode("MISSING_DEPENDENCY_STATUS")
    if any(
        supplied[name] is not PublicExecutionState.COMPLETED for name in cell.required_experiments
    ):
        return ReasonCode("UPSTREAM_EXPERIMENT_NOT_COMPLETED")
    return None


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
    return workspace_root / directory / "COMPLETED.json"


def cell_running_path(cell: PlannedCell, workspace_root: Path) -> Path:
    return cell_completion_path(cell, workspace_root).with_name("RUNNING.json")


def cell_artifact_index_path(cell: PlannedCell, workspace_root: Path) -> Path:
    return cell_completion_path(cell, workspace_root).with_name("artifact_index.json")


def cell_failure_path(cell: PlannedCell, workspace_root: Path) -> Path:
    directory = semantic_cell_path(
        cell.identity.experiment_slug,
        ExperimentLeaf.LOGS_FAILURES,
        cell.identity.path_coordinates,
    )
    return workspace_root / directory / "failure.json"


def _completion_identity_matches(
    cell: PlannedCell,
    context: ExecutionContext,
    completion: CompletionRecord,
) -> bool:
    checks = (
        completion.semantic_cell_key == cell.identity.semantic_cell_key,
        completion.cell_plan_digest == context.plan_digest,
        completion.scientific_specification_digest == context.scientific_specification_digest,
        completion.scientific_dependency_digest == context.scientific_dependency_digest,
        completion.provenance_fingerprint == context.provenance_fingerprint,
        completion.dependency_fingerprint == context.dependency_fingerprint,
        completion.manifest_digest == context.manifest_digest,
        completion.required_artifact_keys == context.required_artifact_keys,
        completion.expected_seed_count == context.expected_seed_count,
        completion.completed_seed_count == completion.expected_seed_count,
        completion.expected_artifact_count == len(completion.produced_artifact_keys),
    )
    return all(checks)


def _validate_execution_result(result: CellExecutionResult, context: ExecutionContext) -> None:
    produced = tuple(entry.artifact_key for entry in result.artifact_index.artifacts)
    if len(produced) != len(set(produced)):
        raise InvariantViolationError("executor produced duplicate artifact keys")
    if any(key not in produced for key in context.required_artifact_keys):
        raise InvariantViolationError("executor omitted a required artifact key")
    checks = (
        (result.completed_seed_count == context.expected_seed_count, "expected seed count"),
        (result.metrics_complete, "required metrics"),
        (result.statistics_complete, "required statistics"),
        (result.invariant_validation_pass, "scientific invariant validation"),
        (result.dependency_validation_pass, "dependency validation"),
        (result.provenance_record_complete, "provenance record"),
    )
    failed = tuple(label for passed, label in checks if not passed)
    if failed:
        raise InvariantViolationError(f"executor completion contract failed: {', '.join(failed)}")


def _verify_artifacts(index: CellArtifactIndex, workspace_root: Path) -> None:
    root = workspace_root.resolve()
    for entry in index.artifacts:
        artifact_path = (workspace_root / entry.relative_path).resolve()
        if not artifact_path.is_relative_to(root):
            raise InvariantViolationError("artifact path escapes the workspace root")
        if not artifact_path.is_file():
            raise InvariantViolationError(
                f"required produced artifact is missing: {entry.artifact_key}"
            )
        if file_digest(artifact_path) != entry.sha256:
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
    _verify_artifacts(index, workspace_root)


def _completion_record(
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
        cell_plan_digest=context.plan_digest,
        scientific_specification_digest=context.scientific_specification_digest,
        scientific_dependency_digest=context.scientific_dependency_digest,
        provenance_fingerprint=context.provenance_fingerprint,
        dependency_fingerprint=context.dependency_fingerprint,
        manifest_digest=context.manifest_digest,
        required_artifact_keys=context.required_artifact_keys,
        produced_artifact_keys=produced,
        expected_artifact_count=len(produced),
        artifact_sha256_map=checksums,
        completed_seed_count=result.completed_seed_count,
        expected_seed_count=context.expected_seed_count,
        metrics_complete=True,
        statistics_complete=True,
        schema_validation_pass=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
        exit_status=0,
    )


def _checksum(entry: ArtifactIndexEntry) -> ArtifactChecksum:
    return ArtifactChecksum(artifact_key=entry.artifact_key, sha256=entry.sha256)
