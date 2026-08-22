from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trajcert.domain.enums import ArtifactValidationStatus
from trajcert.domain.records.artifacts import Digest

ARTIFACT_HANDLING_SEQUENCE = (
    "validate existing artifacts",
    "reuse compatible artifacts",
    "identify stale descendants",
    "remove stale active descendants",
    "recompute only missing or invalid roots",
    "continue execution",
)


@dataclass(frozen=True, slots=True)
class InvalidationBoundary:
    artifact_boundary: str
    must_recompute_when: str
    must_not_recompute_solely_because: str


INVALIDATION_BOUNDARIES = (
    InvalidationBoundary(
        "dataset/source preparation",
        "source checksum, eligibility semantics, generator parameters/component, event/label "
        "semantics change",
        "solver/statistics/plot/report/test changes",
    ),
    InvalidationBoundary(
        "preprocessing/partitioning",
        "prepared input, partition map, terminal horizon, preprocessing component changes",
        "rho/beta/statistics/report changes",
    ),
    InvalidationBoundary(
        "event streams",
        "law, generator, seed namespace/index, stream identity changes",
        "solver/statistics/report changes",
    ),
    InvalidationBoundary(
        "population summaries",
        "observable law, partition, profile code/numerics change",
        "beta/sequential/statistics/report changes",
    ),
    InvalidationBoundary(
        "comparator fits",
        "input, fit definition/settings/component changes",
        "downstream sensitivity value when fit-independent",
    ),
    InvalidationBoundary(
        "solver/oracle outputs",
        "parent summary, applicable sensitivity coordinate, solver/oracle implementation/"
        "tolerance changes",
        "downstream beta when bound is beta-independent",
    ),
    InvalidationBoundary(
        "categorical CS/envelopes",
        "stream/count, partition, delta, CS/envelope implementation changes",
        "rho/beta/metric/report changes",
    ),
    InvalidationBoundary(
        "outer projection",
        "envelope, rho, projection implementation/numerics changes",
        "beta/statistics/rendering changes",
    ),
    InvalidationBoundary(
        "operational states",
        "projection, beta, evidence gate, state-precedence rule changes",
        "statistical/rendering changes",
    ),
    InvalidationBoundary(
        "statistical analysis",
        "metric input or statistical contract changes",
        "upstream code changes leaving consumed metric artifact unchanged",
    ),
    InvalidationBoundary(
        "source-data tables",
        "consumed scientific/statistical artifact or source transformation changes",
        "renderer-only changes",
    ),
    InvalidationBoundary(
        "figures/tables/report",
        "source data or renderer contract changes",
        "unrelated scientific code/tests/docs",
    ),
    InvalidationBoundary(
        "runtime measurements",
        "target computation, benchmark inputs/configuration, runtime environment changes",
        "renderer/test/doc changes",
    ),
)


@dataclass(frozen=True, slots=True)
class ArtifactReuseDecision:
    status: ArtifactValidationStatus
    reusable: bool
    invalidate_descendants: bool


@dataclass(frozen=True, slots=True)
class ActiveArtifact:
    artifact_key: str
    status: ArtifactValidationStatus
    dependency_fingerprint: str
    scientific_content_digest: str


@dataclass(frozen=True, slots=True)
class ActiveCellReuseDecision:
    reusable: bool
    roots_to_recompute: tuple[str, ...]
    stale_descendants_to_remove: tuple[str, ...]


def artifact_reuse_decision(
    status: ArtifactValidationStatus,
    current_dependency_fingerprint: str,
    candidate_dependency_fingerprint: str | None,
    scientific_content_changed: bool,
) -> ArtifactReuseDecision:
    if status is not ArtifactValidationStatus.VALID:
        return ArtifactReuseDecision(status, False, status is ArtifactValidationStatus.STALE)
    if candidate_dependency_fingerprint != current_dependency_fingerprint:
        return ArtifactReuseDecision(ArtifactValidationStatus.INCOMPATIBLE, False, True)
    return ArtifactReuseDecision(status, True, scientific_content_changed)


def active_cell_reuse_decision(
    required_artifacts: tuple[ActiveArtifact, ...],
    expected_dependency_fingerprints: dict[str, str],
    completion_marker: ActiveArtifact | None,
    overwrite_roots: tuple[str, ...] = (),
    replacement_content_digests: dict[str, str] | None = None,
) -> ActiveCellReuseDecision:
    replacement_digests = {} if replacement_content_digests is None else replacement_content_digests
    roots = set(overwrite_roots)
    stale_descendants: set[str] = set()
    for artifact in required_artifacts:
        expected_fingerprint = expected_dependency_fingerprints.get(artifact.artifact_key)
        if artifact.status is not ArtifactValidationStatus.VALID or (
            expected_fingerprint != artifact.dependency_fingerprint
        ):
            roots.add(artifact.artifact_key)
        replacement_digest = replacement_digests.get(artifact.artifact_key)
        if (
            replacement_digest is not None
            and replacement_digest != artifact.scientific_content_digest
        ):
            stale_descendants.add(artifact.artifact_key)
    complete = (
        completion_marker is not None
        and completion_marker.status is ArtifactValidationStatus.VALID
        and completion_marker.dependency_fingerprint
        == expected_dependency_fingerprints.get(completion_marker.artifact_key)
    )
    return ActiveCellReuseDecision(
        complete and not roots and not stale_descendants,
        tuple(sorted(roots)),
        tuple(sorted(stale_descendants)),
    )


class CheckpointRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    semantic_cell_key: str = Field(min_length=1)
    artifact_key: str = Field(min_length=1)
    dependency_fingerprint: Digest
    provenance_fingerprint: Digest
    cell_plan_digest: Digest
    batch_index: int = Field(ge=0)
    seed_index_start: int = Field(ge=0)
    seed_index_stop_exclusive: int = Field(ge=0)
    input_artifact_keys: tuple[str, ...]
    input_artifact_digests: tuple[Digest, ...]
    result_file_sha256: Digest
    completed: bool

    @model_validator(mode="after")
    def validate_checkpoint_lineage(self) -> CheckpointRecord:
        if self.seed_index_stop_exclusive < self.seed_index_start:
            raise ValueError("checkpoint seed range must not be reversed")
        if len(self.input_artifact_keys) != len(self.input_artifact_digests):
            raise ValueError("checkpoint input artifact keys and digests must align")
        return self


class CheckpointRecoveryRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    semantic_cell_key: str = Field(min_length=1)
    dependency_fingerprint: Digest
    cell_plan_digest: Digest
    input_artifact_digests: tuple[Digest, ...]


def nearest_valid_checkpoint(
    request: CheckpointRecoveryRequest,
    checkpoints: tuple[CheckpointRecord, ...],
    result_payloads: dict[str, bytes],
) -> CheckpointRecord | None:
    candidates = tuple(
        checkpoint
        for checkpoint in checkpoints
        if _checkpoint_is_valid(request, checkpoint, result_payloads)
    )
    if not candidates:
        return None
    return max(candidates, key=lambda checkpoint: checkpoint.batch_index)


def _checkpoint_is_valid(
    request: CheckpointRecoveryRequest,
    checkpoint: CheckpointRecord,
    result_payloads: dict[str, bytes],
) -> bool:
    payload = result_payloads.get(checkpoint.artifact_key)
    return (
        checkpoint.completed
        and checkpoint.semantic_cell_key == request.semantic_cell_key
        and checkpoint.dependency_fingerprint == request.dependency_fingerprint
        and checkpoint.cell_plan_digest == request.cell_plan_digest
        and checkpoint.input_artifact_digests == request.input_artifact_digests
        and payload is not None
        and hashlib.sha256(payload).hexdigest() == checkpoint.result_file_sha256
    )


def missing_seed_ranges(
    seed_index_start: int,
    seed_index_stop_exclusive: int,
    completed_seed_indices: tuple[int, ...],
) -> tuple[tuple[int, int], ...]:
    if seed_index_start < 0 or seed_index_stop_exclusive < seed_index_start:
        raise ValueError("declared seed range is invalid")
    completed = set(completed_seed_indices)
    if any(index < seed_index_start or index >= seed_index_stop_exclusive for index in completed):
        raise ValueError("completed seed index is outside the declared range")
    missing = tuple(
        index
        for index in range(seed_index_start, seed_index_stop_exclusive)
        if index not in completed
    )
    if not missing:
        return ()
    ranges: list[tuple[int, int]] = []
    range_start = missing[0]
    previous = missing[0]
    for index in missing[1:]:
        if index != previous + 1:
            ranges.append((range_start, previous + 1))
            range_start = index
        previous = index
    ranges.append((range_start, previous + 1))
    return tuple(ranges)
