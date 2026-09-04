from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NewType

from trajcert.experiments.plan import PlannedCell
from trajcert.storage import (
    ArtifactKey,
    CellArtifactIndex,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    SemanticCellKey,
    SpecificationDigest,
)
from trajcert.types import (
    BatchIndex,
    DomainModel,
    ExperimentName,
    FailureMessage,
    PublicExecutionState,
    ReasonCode,
    SeedCount,
    SeedIndex,
)

FailureType = NewType("FailureType", str)
FailureTraceback = NewType("FailureTraceback", str)


class DependencyReadiness(DomainModel):
    experiment_name: ExperimentName
    state: PublicExecutionState


class ExecutionContext(DomainModel):
    workspace_root: Path
    plan_digest: PlanDigest
    scientific_specification_digest: SpecificationDigest
    dependency_fingerprint: DependencyFingerprint
    required_artifact_keys: tuple[ArtifactKey, ...]
    expected_seed_count: SeedCount


class CellExecutionResult(DomainModel):
    artifact_index: CellArtifactIndex
    completed_seed_count: SeedCount


class RunningRecord(DomainModel):
    semantic_cell_key: SemanticCellKey
    plan_digest: PlanDigest
    dependency_fingerprint: DependencyFingerprint


class FailureRecord(DomainModel):
    semantic_cell_key: SemanticCellKey
    plan_digest: PlanDigest
    dependency_fingerprint: DependencyFingerprint
    failure_type: FailureType
    message: FailureMessage
    traceback: FailureTraceback
    execution_state: PublicExecutionState


class CellRunOutcome(DomainModel):
    state: PublicExecutionState
    reused: bool
    completion_path: Path
    failure_path: Path
    reason: ReasonCode | None


class CheckpointRecord(DomainModel):
    semantic_cell_key: SemanticCellKey
    artifact_key: ArtifactKey
    dependency_fingerprint: DependencyFingerprint
    cell_plan_digest: PlanDigest
    batch_index: BatchIndex
    seed_index_start: SeedIndex
    seed_index_stop_exclusive: SeedIndex
    input_artifact_keys: tuple[ArtifactKey, ...]
    input_artifact_digests: tuple[DigestHex, ...]
    result_file_sha256: DigestHex
    completed: bool


CellExecutor = Callable[[PlannedCell, ExecutionContext], CellExecutionResult]
