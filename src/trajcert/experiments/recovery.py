from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trajcert.domain.enums import ArtifactValidationStatus
from trajcert.domain.records.artifacts import DescriptiveKey, Digest
from trajcert.domain.seeds import SeedIndex, SeedIndexRange

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
class ArtifactReuseDecisionInput:
    status: ArtifactValidationStatus
    current_dependency_fingerprint: Digest
    candidate_dependency_fingerprint: Digest | None
    scientific_content_changed: bool


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


@dataclass(frozen=True, slots=True)
class ActiveCellReuseDecisionInput:
    required_artifacts: tuple[ActiveArtifact, ...]
    expected_dependency_fingerprints: Mapping[str, Digest]
    completion_marker: ActiveArtifact | None
    overwrite_roots: tuple[str, ...]
    replacement_content_digests: Mapping[str, Digest] | None


@dataclass(frozen=True, slots=True)
class StochasticSeedAccountingInput:
    seed_index_start: int
    seed_index_stop_exclusive: int
    completed_seed_indices: tuple[int, ...]
    failed_seed_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class StochasticSeedAccounting:
    expected_seed_indices: tuple[int, ...]
    completed_seed_indices: tuple[int, ...]
    failed_seed_indices: tuple[int, ...]
    missing_seed_indices: tuple[int, ...]
    complete: bool


def stochastic_seed_accounting(
    input_value: StochasticSeedAccountingInput,
) -> StochasticSeedAccounting:
    expected = tuple(range(input_value.seed_index_start, input_value.seed_index_stop_exclusive))
    completed = tuple(sorted(input_value.completed_seed_indices))
    failed = tuple(sorted(input_value.failed_seed_indices))
    if len(set(completed)) != len(completed) or len(set(failed)) != len(failed):
        raise ValueError("stochastic seed accounting requires unique seed indices")
    if set(completed) & set(failed):
        raise ValueError("failed seeds cannot be treated as completed observations")
    if not set(completed).union(failed).issubset(expected):
        raise ValueError("stochastic seed accounting contains undeclared seed indices")
    missing = tuple(index for index in expected if index not in set(completed).union(failed))
    return StochasticSeedAccounting(
        expected, completed, failed, missing, not failed and not missing
    )


def artifact_reuse_decision(input_value: ArtifactReuseDecisionInput) -> ArtifactReuseDecision:
    status = input_value.status
    if status is not ArtifactValidationStatus.VALID:
        return ArtifactReuseDecision(status, False, status is ArtifactValidationStatus.STALE)
    if input_value.candidate_dependency_fingerprint != input_value.current_dependency_fingerprint:
        return ArtifactReuseDecision(ArtifactValidationStatus.INCOMPATIBLE, False, True)
    return ArtifactReuseDecision(status, True, input_value.scientific_content_changed)


def active_cell_reuse_decision(
    input_value: ActiveCellReuseDecisionInput,
) -> ActiveCellReuseDecision:
    replacement_digests: Mapping[str, Digest] = (
        {}
        if input_value.replacement_content_digests is None
        else input_value.replacement_content_digests
    )
    roots = set(input_value.overwrite_roots)
    stale_descendants: set[str] = set()
    for artifact in input_value.required_artifacts:
        expected_fingerprint = input_value.expected_dependency_fingerprints.get(
            artifact.artifact_key
        )
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
        input_value.completion_marker is not None
        and input_value.completion_marker.status is ArtifactValidationStatus.VALID
        and input_value.completion_marker.dependency_fingerprint
        == input_value.expected_dependency_fingerprints.get(
            input_value.completion_marker.artifact_key
        )
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


@dataclass(frozen=True, slots=True)
class CheckpointSelectionInput:
    request: CheckpointRecoveryRequest
    checkpoints: tuple[CheckpointRecord, ...]
    result_payloads: Mapping[DescriptiveKey, bytes]


def nearest_valid_checkpoint(
    input_value: CheckpointSelectionInput,
) -> CheckpointRecord | None:
    candidates = tuple(
        checkpoint
        for checkpoint in input_value.checkpoints
        if _checkpoint_is_valid(input_value.request, checkpoint, input_value.result_payloads)
    )
    if not candidates:
        return None
    return max(candidates, key=lambda checkpoint: checkpoint.batch_index)


def _checkpoint_is_valid(
    request: CheckpointRecoveryRequest,
    checkpoint: CheckpointRecord,
    result_payloads: Mapping[str, bytes],
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


@dataclass(frozen=True, slots=True)
class MissingSeedRangesInput:
    declared_range: SeedIndexRange
    completed_seed_indices: tuple[SeedIndex, ...]


@dataclass(frozen=True, slots=True)
class CheckpointBatchSize:
    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("checkpoint batch size must be positive")


@dataclass(frozen=True, slots=True)
class CheckpointBatchCountInput:
    declared_range: SeedIndexRange
    batch_size: CheckpointBatchSize


@dataclass(frozen=True, slots=True)
class CheckpointBatchCount:
    value: int


def missing_seed_ranges(input_value: MissingSeedRangesInput) -> tuple[SeedIndexRange, ...]:
    completed = {index.value for index in input_value.completed_seed_indices}
    if any(
        index < input_value.declared_range.start.value
        or index >= input_value.declared_range.stop_exclusive.value
        for index in completed
    ):
        raise ValueError("completed seed index is outside the declared range")
    missing = tuple(
        index
        for index in range(
            input_value.declared_range.start.value,
            input_value.declared_range.stop_exclusive.value,
        )
        if index not in completed
    )
    if not missing:
        return ()
    ranges: list[SeedIndexRange] = []
    range_start = missing[0]
    previous = missing[0]
    for index in missing[1:]:
        if index != previous + 1:
            ranges.append(SeedIndexRange(SeedIndex(range_start), SeedIndex(previous + 1)))
            range_start = index
        previous = index
    ranges.append(SeedIndexRange(SeedIndex(range_start), SeedIndex(previous + 1)))
    return tuple(ranges)


def checkpoint_batch_count(input_value: CheckpointBatchCountInput) -> CheckpointBatchCount:
    seed_count = (
        input_value.declared_range.stop_exclusive.value - input_value.declared_range.start.value
    )
    if seed_count < 1:
        raise ValueError("declared seed interval is invalid")
    return CheckpointBatchCount(
        (seed_count + input_value.batch_size.value - 1) // input_value.batch_size.value
    )
