from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trajcert.domain.enums import InternalExecutionState
from trajcert.domain.records.artifacts import ArtifactEnvelope, CanonicalJson, Digest


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

    @model_validator(mode="after")
    def validate_execution_timestamps(self) -> ActiveSemanticCellManifest:
        if (
            self.execution_start_timestamp is not None
            and self.execution_end_timestamp is not None
            and self.execution_end_timestamp < self.execution_start_timestamp
        ):
            raise ValueError("execution end cannot precede execution start")
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

    @model_validator(mode="after")
    def validate_execution_state(self) -> ExecutionStateRecord:
        if any(index < 0 for index in self.failed_seed_indices + self.completed_seed_indices):
            raise ValueError("seed indices must be nonnegative")
        if any(index < 0 for index in self.completed_batch_indices):
            raise ValueError("batch indices must be nonnegative")
        if set(self.failed_seed_indices) & set(self.completed_seed_indices):
            raise ValueError("a seed cannot be both failed and completed")
        return self
