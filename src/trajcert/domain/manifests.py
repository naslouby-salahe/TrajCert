from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trajcert.domain.enums import ArtifactValidationStatus, DatasetKind
from trajcert.domain.identity import Identifier, LocalCertificateIdentity
from trajcert.domain.records.artifacts import CanonicalJson, Digest
from trajcert.domain.serialization import JSONValue

UNSIGNED_DECIMAL_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    dataset_name: str = Field(min_length=1)
    dataset_kind: DatasetKind
    generator_name: str | None = None
    generator_code_digest: Digest | None = None
    source_version: str = Field(min_length=1)
    source_checksum: Digest
    license_or_permission: str | None = None
    official_documentation_reference: str | None = None
    primary_publication_reference: str | None = None
    event_semantics: str = Field(min_length=1)
    label_semantics: str = Field(min_length=1)
    time_semantics: str = Field(min_length=1)
    terminal_horizon: int = Field(gt=0)
    finest_partition_name: str = Field(min_length=1)
    number_of_categories: int = Field(gt=0)
    documented_expected_structure: CanonicalJson
    observed_raw_structure: CanonicalJson
    field_mapping_json: CanonicalJson
    population_parameters: CanonicalJson | None = None
    known_full_law: bool
    known_theta: float | None = None
    known_observable_probabilities: CanonicalJson | None = None
    known_terminal_harmful_mass: float | None = None
    known_information: float | None = None
    preprocessing_digest: Digest
    eligibility_status: str = Field(min_length=1)
    ineligibility_reason: str | None = None

    @field_validator("known_theta", "known_terminal_harmful_mass", "known_information")
    @classmethod
    def validate_finite_known_value(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("known scientific values must be finite")
        return value

    @model_validator(mode="after")
    def validate_dataset_kind_contract(self) -> DatasetManifest:
        if self.dataset_kind is DatasetKind.SYNTHETIC and not self.known_full_law:
            raise ValueError("synthetic datasets require a known full law")
        return self


class PartitionManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    partition_name: str = Field(min_length=1)
    finest_partition_name: str = Field(min_length=1)
    terminal_horizon: int = Field(gt=0)
    K: int = Field(gt=0)
    boundaries: tuple[float, ...]
    coarsening_map_from_finest: CanonicalJson
    parent_partition_name: str | None = None
    is_endpoint_only: bool
    is_precommitted: bool
    checksum: Digest

    @model_validator(mode="after")
    def validate_boundaries(self) -> PartitionManifest:
        if len(self.boundaries) != self.K:
            raise ValueError("partition boundaries must have one entry per finite band")
        if any(not math.isfinite(boundary) for boundary in self.boundaries):
            raise ValueError("partition boundaries must be finite")
        if tuple(sorted(self.boundaries)) != self.boundaries:
            raise ValueError("partition boundaries must be sorted")
        return self


class SeedManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    seed_set_key: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    index_start: int = Field(ge=0)
    index_stop_exclusive: int = Field(ge=0)
    derivation_algorithm: str = Field(min_length=1)
    seeds_sha256: Digest
    seed_count: int = Field(ge=0)
    seeds: tuple[str, ...]

    @model_validator(mode="after")
    def validate_seed_set(self) -> SeedManifest:
        if self.index_stop_exclusive < self.index_start:
            raise ValueError("seed range stop must not precede its start")
        if self.seed_count != len(self.seeds):
            raise ValueError("seed count must match the stored seed list")
        if self.seed_count != self.index_stop_exclusive - self.index_start:
            raise ValueError("seed count must match the declared index range")
        if any(UNSIGNED_DECIMAL_PATTERN.fullmatch(seed) is None for seed in self.seeds):
            raise ValueError("seeds must be unsigned decimal strings")
        return self


class ReusableArtifactManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    artifact_key: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    artifact_owner: str = Field(min_length=1)
    producer_component: str = Field(min_length=1)
    dependency_fingerprint: Digest
    implementation_component_digest: Digest
    environment_dependency_digest: Digest
    scientific_dependency_digest: Digest
    semantic_coordinates: CanonicalJson
    parent_artifact_keys: tuple[str, ...] = ()
    parent_artifact_digests: tuple[Digest, ...] = ()
    scientific_content_digest: Digest
    payload_paths: tuple[str, ...]
    payload_sha256_map: CanonicalJson
    schema_name: str = Field(min_length=1)
    schema_version: Literal[1] = 1
    status: ArtifactValidationStatus
    created_timestamp: datetime
    validated_timestamp: datetime | None = None
    declared_downstream_consumers: tuple[str, ...] = ()

    @field_validator("created_timestamp", "validated_timestamp")
    @classmethod
    def validate_utc_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            offset = value.utcoffset()
            if offset is None or offset.total_seconds() != 0:
                raise ValueError("artifact timestamps must be UTC")
        return value

    @model_validator(mode="after")
    def validate_artifact_lineage(self) -> ReusableArtifactManifest:
        if len(self.parent_artifact_keys) != len(self.parent_artifact_digests):
            raise ValueError("parent artifact keys and digests must align")
        if self.status is ArtifactValidationStatus.VALID and self.validated_timestamp is None:
            raise ValueError("valid reusable artifacts require a validation timestamp")
        parsed_checksums = json.loads(self.payload_sha256_map)
        if not isinstance(parsed_checksums, dict):
            raise ValueError("payload checksum map must be a canonical JSON object")
        payload_checksums = cast(dict[str, JSONValue], parsed_checksums)
        if set(payload_checksums) != set(self.payload_paths):
            raise ValueError("payload checksum map must exactly match payload paths")
        if not all(
            isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest)
            for digest in payload_checksums.values()
        ):
            raise ValueError("payload checksum map values must be SHA-256 digests")
        return self


class EpochManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    identity: LocalCertificateIdentity
    detector_model_identity: Identifier
    action_policy: Identifier
    adjudication_regime: Identifier
    event_logging_semantics: Identifier
    terminal_horizon_age_units: int = Field(gt=0)
    finest_trajectory_representation: Identifier

    def materially_differs_from(self, other: EpochManifest) -> bool:
        return self != other

    def close_for_material_change(self, replacement: EpochManifest) -> ClosedEpoch:
        if self.identity != replacement.identity:
            raise ValueError("epoch replacement must preserve local certificate identity")
        if not self.materially_differs_from(replacement):
            raise ValueError("an epoch closes only for a material change")
        return ClosedEpoch(closed_manifest=self, replacement_manifest=replacement)


@dataclass(frozen=True, slots=True)
class ClosedEpoch:
    closed_manifest: EpochManifest
    replacement_manifest: EpochManifest
