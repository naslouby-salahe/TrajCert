from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trajcert.domain.enums import ScientificState
from trajcert.domain.records.artifacts import CanonicalJson, Digest
from trajcert.domain.serialization import JSONValue

DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FailureRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    failure_record_key: str = Field(min_length=1)
    semantic_cell_key: str = Field(min_length=1)
    dependency_fingerprint: Digest
    provenance_fingerprint: Digest
    failure_class: str = Field(min_length=1)
    execution_group: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    exception_type: str | None = None
    seed_index: int | None = Field(default=None, ge=0)
    input_artifact_keys: tuple[str, ...] = ()
    input_artifact_digests: tuple[Digest, ...] = ()
    last_valid_checkpoint: str | None = None
    retry_allowed: bool
    downstream_blocking: bool

    @field_validator("failure_class")
    @classmethod
    def reject_scientific_outcomes(cls, value: str) -> str:
        if value in {state.value for state in ScientificState}:
            raise ValueError("scientific outcomes must not enter failure records")
        return value

    @model_validator(mode="after")
    def validate_input_lineage(self) -> FailureRecord:
        if len(self.input_artifact_keys) != len(self.input_artifact_digests):
            raise ValueError("failure input artifact keys and digests must align")
        return self


class CompletionMarker(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    semantic_cell_key: str = Field(min_length=1)
    cell_plan_digest: Digest
    scientific_specification_digest: Digest
    scientific_dependency_digest: Digest
    provenance_fingerprint: Digest
    dependency_fingerprint: Digest
    manifest_digest: Digest
    required_artifact_keys: tuple[str, ...]
    produced_artifact_keys: tuple[str, ...]
    expected_artifact_count: int = Field(ge=0)
    artifact_sha256_map: CanonicalJson
    completed_seed_count: int = Field(ge=0)
    expected_seed_count: int = Field(ge=0)
    metrics_complete: bool
    statistics_complete: bool
    schema_validation_pass: bool
    invariant_validation_pass: bool
    dependency_validation_pass: bool
    provenance_record_complete: bool
    exit_status: int

    @model_validator(mode="after")
    def validate_completion_evidence(self) -> CompletionMarker:
        if len(set(self.required_artifact_keys)) != len(self.required_artifact_keys):
            raise ValueError("required artifact keys must be unique")
        if len(set(self.produced_artifact_keys)) != len(self.produced_artifact_keys):
            raise ValueError("produced artifact keys must be unique")
        if len(self.produced_artifact_keys) != self.expected_artifact_count:
            raise ValueError("produced artifact count must equal the expected artifact count")
        if set(self.produced_artifact_keys) != set(self.required_artifact_keys):
            raise ValueError("produced artifact keys must exactly match required artifact keys")
        parsed_artifact_digests = json.loads(self.artifact_sha256_map)
        if not isinstance(parsed_artifact_digests, dict):
            raise ValueError("artifact checksum map must be a canonical JSON object")
        artifact_digests = cast(Mapping[str, JSONValue], parsed_artifact_digests)
        if set(artifact_digests) != set(self.produced_artifact_keys):
            raise ValueError("artifact checksum map must exactly match produced artifact keys")
        if not all(
            isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest)
            for digest in artifact_digests.values()
        ):
            raise ValueError("artifact checksum map values must be SHA-256 digests")
        if self.completed_seed_count != self.expected_seed_count:
            raise ValueError("completed seed count must equal expected seed count")
        if not all(
            (
                self.metrics_complete,
                self.statistics_complete,
                self.schema_validation_pass,
                self.invariant_validation_pass,
                self.dependency_validation_pass,
                self.provenance_record_complete,
            )
        ):
            raise ValueError("completion markers require every validation gate to pass")
        if self.exit_status != 0:
            raise ValueError("completion markers require a successful exit status")
        return self


class ClaimRegistryRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    claim_name: str = Field(min_length=1)
    exact_claim: str = Field(min_length=1)
    research_question: str = Field(min_length=1)
    hypotheses_or_theorems: tuple[str, ...] = ()
    supporting_experiments: tuple[str, ...]
    primary_metric: str = Field(min_length=1)
    secondary_metrics: tuple[str, ...] = ()
    statistical_comparison: str | None = None
    effect_size_rule: str | None = None
    minimum_support_condition: str = Field(min_length=1)
    failure_condition: str = Field(min_length=1)
    valid_scope: str = Field(min_length=1)
    forbidden_extrapolation: str = Field(min_length=1)
    supporting_tables: tuple[str, ...] = ()
    supporting_figures: tuple[str, ...] = ()
    final_state: str = Field(min_length=1)
    final_state_reason: str = Field(min_length=1)
    evidence_artifact_digests: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def validate_claim_evidence(self) -> ClaimRegistryRecord:
        if self.final_state == "SUPPORTED" and not self.evidence_artifact_digests:
            raise ValueError("supported claims require evidence artifact digests")
        return self
