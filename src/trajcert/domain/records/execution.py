from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trajcert.domain.enums import InternalExecutionState
from trajcert.domain.records.artifacts import ArtifactEnvelope, CanonicalJson, Digest, GitCommit


def _validate_utc_timestamp(value: datetime | None) -> datetime | None:
    if value is not None:
        offset = value.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("timestamps must be UTC")
    return value


class ExperimentPlanRow(ArtifactEnvelope):
    executable: bool
    invalid_reason: str | None = None
    gamma: float | None = None
    sensitivity_parameter_json: CanonicalJson
    seed_namespace: str | None = None
    seed_index_start: int | None = Field(default=None, ge=0)
    seed_index_stop_exclusive: int | None = Field(default=None, ge=0)
    expected_stream_count: int = Field(ge=0)
    expected_artifact_schema: str = Field(min_length=1)
    expected_output_path: str = Field(min_length=1)
    upstream_artifact_types: tuple[str, ...] = ()
    dependency_coordinates: CanonicalJson

    @model_validator(mode="after")
    def validate_plan_cell(self) -> ExperimentPlanRow:
        if self.executable and self.invalid_reason is not None:
            raise ValueError("executable plan rows cannot have an invalid reason")
        if not self.executable and self.invalid_reason is None:
            raise ValueError("nonexecutable plan rows require an invalid reason")
        if (self.seed_index_start is None) != (self.seed_index_stop_exclusive is None):
            raise ValueError("seed range endpoints must be provided together")
        if (
            self.seed_index_start is not None
            and self.seed_index_stop_exclusive is not None
            and self.seed_index_stop_exclusive < self.seed_index_start
        ):
            raise ValueError("seed range stop must not precede its start")
        if self.gamma is not None and not math.isfinite(self.gamma):
            raise ValueError("gamma must be finite")
        return self


class ActiveSemanticCellManifest(ArtifactEnvelope):
    resolved_scientific_parameters: CanonicalJson
    expected_artifacts: tuple[str, ...]
    required_artifact_keys: tuple[str, ...]
    produced_artifact_keys: tuple[str, ...] = ()
    execution_start_timestamp: datetime | None = None
    execution_end_timestamp: datetime | None = None
    host_runtime_fingerprint: Digest | None = None
    checkpoint_recovery_history: CanonicalJson

    @field_validator("execution_start_timestamp", "execution_end_timestamp")
    @classmethod
    def _validate_utc_execution_timestamp(cls, value: datetime | None) -> datetime | None:
        return _validate_utc_timestamp(value)

    @model_validator(mode="after")
    def validate_execution_timestamps(self) -> ActiveSemanticCellManifest:
        if self.execution_end_timestamp is not None and self.execution_start_timestamp is None:
            raise ValueError("execution end requires an execution start")
        if (
            self.execution_start_timestamp is not None
            and self.execution_end_timestamp is not None
            and self.execution_end_timestamp < self.execution_start_timestamp
        ):
            raise ValueError("execution end cannot precede execution start")
        if not set(self.produced_artifact_keys).issubset(self.required_artifact_keys):
            raise ValueError("produced artifacts must be required artifacts")
        return self


class ExecutionStateRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    state: InternalExecutionState
    semantic_cell_key: str = Field(min_length=1)
    state_sequence_number: int = Field(ge=0)
    last_transition_timestamp: datetime
    reason_code: str | None = None
    reason_text: str | None = None
    failed_seed_indices: tuple[int, ...] = ()
    completed_seed_indices: tuple[int, ...] = ()
    completed_batch_indices: tuple[int, ...] = ()
    checkpoint_recovery_eligible: bool
    stale_artifact_keys: tuple[str, ...] = ()
    blocking_artifact_keys: tuple[str, ...] = ()

    @field_validator("last_transition_timestamp")
    @classmethod
    def _validate_utc_transition_timestamp(cls, value: datetime) -> datetime:
        validated = _validate_utc_timestamp(value)
        assert validated is not None
        return validated

    @model_validator(mode="after")
    def validate_execution_state(self) -> ExecutionStateRecord:
        if any(index < 0 for index in self.failed_seed_indices + self.completed_seed_indices):
            raise ValueError("seed indices must be nonnegative")
        if any(index < 0 for index in self.completed_batch_indices):
            raise ValueError("batch indices must be nonnegative")
        if len(set(self.failed_seed_indices)) != len(self.failed_seed_indices):
            raise ValueError("failed seed indices must be unique")
        if len(set(self.completed_seed_indices)) != len(self.completed_seed_indices):
            raise ValueError("completed seed indices must be unique")
        if len(set(self.completed_batch_indices)) != len(self.completed_batch_indices):
            raise ValueError("completed batch indices must be unique")
        if set(self.failed_seed_indices) & set(self.completed_seed_indices):
            raise ValueError("a seed cannot be both failed and completed")
        has_reason = self.reason_code is not None or self.reason_text is not None
        if (self.reason_code is None) != (self.reason_text is None):
            raise ValueError("execution reasons require both a code and text")
        if self.state in {InternalExecutionState.FAILED, InternalExecutionState.INVALID}:
            if not has_reason:
                raise ValueError("failed and invalid states require a reason")
        elif has_reason:
            raise ValueError("nonterminal execution states cannot retain a reason")
        if self.state is InternalExecutionState.PLANNED and (
            self.failed_seed_indices
            or self.completed_seed_indices
            or self.completed_batch_indices
            or self.checkpoint_recovery_eligible
        ):
            raise ValueError("planned execution states cannot contain execution progress")
        if self.state is InternalExecutionState.COMPLETED and (
            self.failed_seed_indices or self.checkpoint_recovery_eligible
        ):
            raise ValueError("completed execution states cannot retain failures or recovery")
        return self


class ExperimentAggregateRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    experiment_name: str = Field(min_length=1)
    overall_state: InternalExecutionState
    expected_semantic_cells: int = Field(ge=0)
    completed_semantic_cells: int = Field(ge=0)
    failed_semantic_cells: int = Field(ge=0)
    invalid_semantic_cells: int = Field(ge=0)
    stale_semantic_cells: int = Field(ge=0)
    blocking_dependencies: tuple[str, ...] = ()
    active_provenance_digest: Digest | None = None
    last_execution_outcome: str | None = None
    results_export_state: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_semantic_cell_counts(self) -> ExperimentAggregateRecord:
        completed_or_terminal = (
            self.completed_semantic_cells
            + self.failed_semantic_cells
            + self.invalid_semantic_cells
            + self.stale_semantic_cells
        )
        if completed_or_terminal > self.expected_semantic_cells:
            raise ValueError("semantic cell counts cannot exceed the expected total")
        if self.overall_state is InternalExecutionState.COMPLETED:
            if self.completed_semantic_cells != self.expected_semantic_cells:
                raise ValueError("completed experiments require all semantic cells to complete")
            if (
                self.failed_semantic_cells
                or self.invalid_semantic_cells
                or self.stale_semantic_cells
            ):
                raise ValueError("completed experiments cannot retain terminal failure states")
        return self


class ProvenanceFingerprintInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    scientific_specification_digest: Digest
    code_commit: GitCommit
    dirty_tree_flag: bool
    environment_lock_digest: Digest
    container_image_digest: str = Field(min_length=1)
    dataset_preprocessing_checksums: tuple[Digest, ...]
    partition_checksum: Digest
    seed_manifest_checksums: tuple[Digest, ...]
    plan_digest: Digest


class DependencyFingerprintInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    artifact_type: str = Field(min_length=1)
    semantic_coordinates: CanonicalJson
    scientific_dependency_digest: Digest
    implementation_component_digest: Digest
    environment_dependency_digest: Digest
    seed_manifest_digest: Digest | None = None
    parent_artifact_keys: tuple[str, ...] = ()
    parent_scientific_content_digests: tuple[Digest, ...] = ()
    producer_immutable_inputs: CanonicalJson

    @model_validator(mode="after")
    def validate_parent_lineage(self) -> DependencyFingerprintInput:
        if len(self.parent_artifact_keys) != len(self.parent_scientific_content_digests):
            raise ValueError("parent artifact keys and scientific content digests must align")
        if len(set(self.parent_artifact_keys)) != len(self.parent_artifact_keys):
            raise ValueError("parent artifact keys must be unique")
        return self
