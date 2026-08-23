from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Annotated, Literal, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from trajcert.domain.enums import EvidenceClass, PublicExecutionState
from trajcert.domain.serialization import JSONValue, canonical_json_text

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GitCommit = Annotated[str, Field(pattern=r"^[0-9a-f]{40}([0-9a-f]{24})?$")]
DescriptiveKey = Annotated[str, Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._=-]*$")]
SCHEMA_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_canonical_json_text(value: str) -> str:
    return canonical_json_text(value)


CanonicalJson = Annotated[str, Field(min_length=2), AfterValidator(_validate_canonical_json_text)]


class ArtifactEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    artifact_key: DescriptiveKey
    artifact_type: str = Field(min_length=1)
    artifact_owner: str = Field(min_length=1)
    producer_component: str = Field(min_length=1)
    semantic_cell_key: str | None = None
    semantic_coordinates: CanonicalJson | None = None
    experiment_name: str | None = Field(default=None, min_length=1)
    classification: EvidenceClass | None = None
    execution_group: str | None = Field(default=None, min_length=1)
    scientific_specification_digest: Digest
    scientific_dependency_digest: Digest
    provenance_fingerprint: Digest
    dependency_fingerprint: Digest
    implementation_component_digest: Digest
    environment_dependency_digest: Digest
    plan_digest: Digest | None = None
    cell_plan_digest: Digest | None = None
    status: PublicExecutionState
    method_name: str | None = None
    baseline_name: str | None = None
    dataset_name: str | None = None
    dataset_checksum: Digest | None = None
    synthetic_law_name: str | None = None
    partition_name: str | None = None
    rho: float | None = None
    beta: float | None = None
    delta: float | None = None
    environment_lock_digest: Digest | None = None
    code_commit: GitCommit | None = None
    seed_set_keys: tuple[str, ...] = ()
    parent_artifact_keys: tuple[str, ...] = ()
    parent_artifact_digests: tuple[Digest, ...] = ()
    input_paths: tuple[str, ...] = ()
    canonical_active_path: str | None = None
    schema_name: str = Field(min_length=1)
    schema_version: Literal[1] = 1

    @field_validator("schema_name")
    @classmethod
    def validate_schema_name(cls, value: str) -> str:
        if not SCHEMA_NAME_PATTERN.fullmatch(value):
            raise ValueError("schema name must be lower snake case")
        return value

    @field_validator("rho", "beta", "delta")
    @classmethod
    def validate_finite_scientific_value(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("claim-bearing scientific values must be finite")
        return value

    @field_validator("semantic_coordinates")
    @classmethod
    def validate_canonical_json_text(cls, value: str | None) -> str | None:
        if value is not None and (value[0] != "{" or value[-1] != "}"):
            raise ValueError("semantic coordinates must be canonical JSON object text")
        return value

    @model_validator(mode="after")
    def validate_semantic_cell_fields(self) -> ArtifactEnvelope:
        semantic_values = (
            self.semantic_cell_key,
            self.semantic_coordinates,
            self.experiment_name,
        )
        if not any(value is not None for value in semantic_values):
            return self
        if any(value is None for value in semantic_values):
            raise ValueError(
                "semantic cell artifacts require key, coordinates, and experiment name together"
            )
        assert self.semantic_cell_key is not None
        assert self.semantic_coordinates is not None
        assert self.experiment_name is not None
        parsed_coordinates = json.loads(self.semantic_coordinates)
        if not isinstance(parsed_coordinates, dict):
            raise ValueError("semantic coordinates must be a canonical JSON object")
        coordinates = cast(Mapping[str, JSONValue], parsed_coordinates)
        expected_key = f"{self.experiment_name}:{self.semantic_coordinates}"
        if self.semantic_cell_key != expected_key:
            raise ValueError("semantic cell key must match experiment name and coordinates")
        coordinate_fields = (
            ("method", "method_name"),
            ("baseline", "baseline_name"),
            ("dataset", "dataset_name"),
            ("law", "synthetic_law_name"),
            ("partition", "partition_name"),
            ("rho", "rho"),
            ("beta", "beta"),
            ("delta", "delta"),
        )
        for coordinate_name, field_name in coordinate_fields:
            coordinate_value = coordinates.get(coordinate_name)
            field_value = getattr(self, field_name)
            if coordinate_value is not None and field_value is None:
                raise ValueError(f"{field_name} is required when {coordinate_name} is a coordinate")
            if coordinate_value is not None and field_value != coordinate_value:
                raise ValueError(f"{field_name} must match semantic coordinate {coordinate_name}")
        return self
