from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, cast

import pyarrow as pyarrow

from trajcert.domain.records.artifacts import ArtifactEnvelope
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import (
    SemanticCoordinateSegmentInput,
    semantic_coordinate_segment,
)


class _ArrowDataType(Protocol):
    bit_width: int

    def __str__(self) -> str: ...


class _ArrowField(Protocol):
    nullable: bool
    type: _ArrowDataType


class _ArrowSchema(Protocol):
    names: list[str]

    def field(self, name: str) -> _ArrowField: ...


class _ArrowTable(Protocol):
    schema: _ArrowSchema


class _ArrowTableFactory(Protocol):
    def from_pylist(
        self,
        rows: tuple[Mapping[str, ArtifactValue], ...],
        schema: _ArrowSchema,
    ) -> _ArrowTable: ...


class _ArrowModule(Protocol):
    Table: _ArrowTableFactory

    def bool_(self) -> _ArrowDataType: ...

    def field(self, name: str, field_type: _ArrowDataType, nullable: bool = True) -> _ArrowField:
        raise NotImplementedError((name, field_type, nullable))

    def float64(self) -> _ArrowDataType: ...

    def int64(self) -> _ArrowDataType: ...

    def list_(self, value_type: _ArrowDataType) -> _ArrowDataType:
        raise NotImplementedError(value_type)

    def schema(self, fields: tuple[_ArrowField, ...]) -> _ArrowSchema:
        raise NotImplementedError(fields)

    def string(self) -> _ArrowDataType: ...

    def timestamp(self, unit: str, tz: str) -> _ArrowDataType:
        raise NotImplementedError((unit, tz))

    def uint64(self) -> _ArrowDataType: ...


type ArtifactValue = str | float | int | list[str] | None
ARROW = cast(_ArrowModule, pyarrow)


@dataclass(frozen=True, slots=True)
class SemanticCellKeyInput:
    experiment_name: str
    coordinates: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class SemanticCellKey:
    value: str


@dataclass(frozen=True, slots=True)
class CanonicalActivePathInput:
    workspace_root: Path
    semantic_cell_key: SemanticCellKey


@dataclass(frozen=True, slots=True)
class CanonicalActivePath:
    value: Path


@dataclass(frozen=True, slots=True)
class DescriptiveArtifactKeyInput:
    artifact_type: str
    coordinates: Mapping[str, float | str]


@dataclass(frozen=True, slots=True)
class DescriptiveArtifactKey:
    value: str


def semantic_cell_key(request: SemanticCellKeyInput) -> SemanticCellKey:
    if not request.experiment_name.strip():
        raise ValueError("experiment name must not be empty")
    return SemanticCellKey(
        f"{request.experiment_name}:{canonical_json_bytes(request.coordinates).decode('utf-8')}"
    )


def canonical_active_path(request: CanonicalActivePathInput) -> CanonicalActivePath:
    if not request.semantic_cell_key.value.strip():
        raise ValueError("semantic cell key must not be empty")
    cell_digest = hashlib.sha256(request.semantic_cell_key.value.encode("utf-8")).hexdigest()
    return CanonicalActivePath(request.workspace_root / "artifacts" / "active" / cell_digest)


def descriptive_artifact_key(request: DescriptiveArtifactKeyInput) -> DescriptiveArtifactKey:
    if not request.artifact_type.strip():
        raise ValueError("artifact type must not be empty")
    segments = [request.artifact_type]
    for name in sorted(request.coordinates):
        segments.append(
            semantic_coordinate_segment(
                SemanticCoordinateSegmentInput(name, request.coordinates[name])
            ).value
        )
    return DescriptiveArtifactKey("-".join(segments))


class ArtifactPhysicalType(StrEnum):
    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    LARGE_IDENTIFIER = "large_identifier"
    SCIENTIFIC_REAL = "scientific_real"
    TIMESTAMP = "timestamp"
    STRING_LIST = "string_list"
    CANONICAL_JSON = "canonical_json"
    SHA256_DIGEST = "sha256_digest"


def canonical_physical_types() -> Mapping[ArtifactPhysicalType, _ArrowDataType]:
    return {
        ArtifactPhysicalType.STRING: ARROW.string(),
        ArtifactPhysicalType.BOOLEAN: ARROW.bool_(),
        ArtifactPhysicalType.INTEGER: ARROW.int64(),
        ArtifactPhysicalType.LARGE_IDENTIFIER: ARROW.uint64(),
        ArtifactPhysicalType.SCIENTIFIC_REAL: ARROW.float64(),
        ArtifactPhysicalType.TIMESTAMP: ARROW.timestamp("us", tz="UTC"),
        ArtifactPhysicalType.STRING_LIST: ARROW.list_(ARROW.string()),
        ArtifactPhysicalType.CANONICAL_JSON: ARROW.string(),
        ArtifactPhysicalType.SHA256_DIGEST: ARROW.string(),
    }


def artifact_envelope_arrow_schema() -> _ArrowSchema:
    physical_types = canonical_physical_types()
    string = physical_types[ArtifactPhysicalType.STRING]
    digest = physical_types[ArtifactPhysicalType.SHA256_DIGEST]
    return ARROW.schema(
        (
            ARROW.field("artifact_key", string, nullable=False),
            ARROW.field("artifact_type", string, nullable=False),
            ARROW.field("artifact_owner", string, nullable=False),
            ARROW.field("producer_component", string, nullable=False),
            ARROW.field("semantic_cell_key", string),
            ARROW.field(
                "semantic_coordinates", physical_types[ArtifactPhysicalType.CANONICAL_JSON]
            ),
            ARROW.field("experiment_name", string),
            ARROW.field("classification", string),
            ARROW.field("execution_group", string),
            ARROW.field("scientific_specification_digest", digest, nullable=False),
            ARROW.field("scientific_dependency_digest", digest, nullable=False),
            ARROW.field("provenance_fingerprint", digest, nullable=False),
            ARROW.field("dependency_fingerprint", digest, nullable=False),
            ARROW.field("implementation_component_digest", digest, nullable=False),
            ARROW.field("environment_dependency_digest", digest, nullable=False),
            ARROW.field("plan_digest", digest),
            ARROW.field("cell_plan_digest", digest),
            ARROW.field("status", string, nullable=False),
            ARROW.field("method_name", string),
            ARROW.field("baseline_name", string),
            ARROW.field("dataset_name", string),
            ARROW.field("dataset_checksum", digest),
            ARROW.field("synthetic_law_name", string),
            ARROW.field("partition_name", string),
            ARROW.field("rho", physical_types[ArtifactPhysicalType.SCIENTIFIC_REAL]),
            ARROW.field("beta", physical_types[ArtifactPhysicalType.SCIENTIFIC_REAL]),
            ARROW.field("delta", physical_types[ArtifactPhysicalType.SCIENTIFIC_REAL]),
            ARROW.field("environment_lock_digest", digest),
            ARROW.field("code_commit", digest),
            ARROW.field(
                "seed_set_keys", physical_types[ArtifactPhysicalType.STRING_LIST], nullable=False
            ),
            ARROW.field(
                "parent_artifact_keys",
                physical_types[ArtifactPhysicalType.STRING_LIST],
                nullable=False,
            ),
            ARROW.field(
                "parent_artifact_digests",
                physical_types[ArtifactPhysicalType.STRING_LIST],
                nullable=False,
            ),
            ARROW.field(
                "input_paths", physical_types[ArtifactPhysicalType.STRING_LIST], nullable=False
            ),
            ARROW.field("canonical_active_path", string),
            ARROW.field("schema_name", string, nullable=False),
            ARROW.field(
                "schema_version", physical_types[ArtifactPhysicalType.INTEGER], nullable=False
            ),
        )
    )


def artifact_envelope_table(envelope: ArtifactEnvelope) -> _ArrowTable:
    return ARROW.Table.from_pylist(
        (
            {
                "artifact_key": envelope.artifact_key,
                "artifact_type": envelope.artifact_type,
                "artifact_owner": envelope.artifact_owner,
                "producer_component": envelope.producer_component,
                "semantic_cell_key": envelope.semantic_cell_key,
                "semantic_coordinates": envelope.semantic_coordinates,
                "experiment_name": envelope.experiment_name,
                "classification": None
                if envelope.classification is None
                else envelope.classification.value,
                "execution_group": envelope.execution_group,
                "scientific_specification_digest": envelope.scientific_specification_digest,
                "scientific_dependency_digest": envelope.scientific_dependency_digest,
                "provenance_fingerprint": envelope.provenance_fingerprint,
                "dependency_fingerprint": envelope.dependency_fingerprint,
                "implementation_component_digest": envelope.implementation_component_digest,
                "environment_dependency_digest": envelope.environment_dependency_digest,
                "plan_digest": envelope.plan_digest,
                "cell_plan_digest": envelope.cell_plan_digest,
                "status": envelope.status.value,
                "method_name": envelope.method_name,
                "baseline_name": envelope.baseline_name,
                "dataset_name": envelope.dataset_name,
                "dataset_checksum": envelope.dataset_checksum,
                "synthetic_law_name": envelope.synthetic_law_name,
                "partition_name": envelope.partition_name,
                "rho": envelope.rho,
                "beta": envelope.beta,
                "delta": envelope.delta,
                "environment_lock_digest": envelope.environment_lock_digest,
                "code_commit": envelope.code_commit,
                "seed_set_keys": list(envelope.seed_set_keys),
                "parent_artifact_keys": list(envelope.parent_artifact_keys),
                "parent_artifact_digests": list(envelope.parent_artifact_digests),
                "input_paths": list(envelope.input_paths),
                "canonical_active_path": envelope.canonical_active_path,
                "schema_name": envelope.schema_name,
                "schema_version": envelope.schema_version,
            },
        ),
        schema=artifact_envelope_arrow_schema(),
    )
