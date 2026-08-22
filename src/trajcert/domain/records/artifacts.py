from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from trajcert.domain.enums import EvidenceClass, PublicExecutionState

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GitCommit = Annotated[str, Field(pattern=r"^[0-9a-f]{40}([0-9a-f]{24})?$")]
DescriptiveKey = Annotated[str, Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._=-]*$")]
SCHEMA_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _reject_duplicate_json_keys(pairs: list[tuple[str, str]]) -> Mapping[str, str]:
    value = dict[str, str]()
    for key, item in pairs:
        if key in value:
            raise ValueError("canonical JSON forbids duplicate object keys")
        value[key] = item
    return value


def _reject_nonfinite_json_constant(value: str) -> str:
    raise ValueError(f"canonical JSON forbids nonfinite value {value}")


def _validate_canonical_json_text(value: str) -> str:
    try:
        json.loads(
            value,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonfinite_json_constant,
        )
    except json.JSONDecodeError as error:
        raise ValueError("canonical JSON text must be valid JSON") from error
    return value


CanonicalJson = Annotated[str, Field(min_length=2), AfterValidator(_validate_canonical_json_text)]


class ArtifactEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    artifact_key: DescriptiveKey
    artifact_type: str = Field(min_length=1)
    artifact_owner: str = Field(min_length=1)
    producer_component: str = Field(min_length=1)
    semantic_cell_key: str | None = None
    semantic_coordinates: CanonicalJson | None = None
    experiment_name: str | None = None
    classification: EvidenceClass | None = None
    execution_group: str | None = None
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
        if value is not None and (value[0] not in "[{" or value[-1] not in "]}"):
            raise ValueError("semantic coordinates must be canonical JSON object or array text")
        return value
