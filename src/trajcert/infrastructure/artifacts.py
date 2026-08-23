from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

import pyarrow as pyarrow

from trajcert.domain.records.artifacts import ArtifactEnvelope
from trajcert.domain.serialization import JSONValue, canonical_json_bytes
from trajcert.infrastructure.storage import semantic_coordinate_segment


class ArrowDataType(Protocol):
    bit_width: int

    def __str__(self) -> str: ...


class ArrowField(Protocol):
    nullable: bool
    type: ArrowDataType


class ArrowSchema(Protocol):
    names: list[str]

    def field(self, name: str) -> ArrowField: ...


class ArrowTable(Protocol):
    schema: ArrowSchema


class ArrowTableFactory(Protocol):
    def from_pylist(
        self,
        rows: tuple[Mapping[str, ArtifactValue], ...],
        schema: ArrowSchema,
    ) -> ArrowTable: ...


class ArrowModule(Protocol):
    Table: ArrowTableFactory

    def bool_(self) -> ArrowDataType: ...

    def field(self, name: str, field_type: ArrowDataType, nullable: bool = True) -> ArrowField:
        raise NotImplementedError((name, field_type, nullable))

    def float64(self) -> ArrowDataType: ...

    def int64(self) -> ArrowDataType: ...

    def list_(self, value_type: ArrowDataType) -> ArrowDataType:
        raise NotImplementedError(value_type)

    def schema(self, fields: tuple[ArrowField, ...]) -> ArrowSchema:
        raise NotImplementedError(fields)

    def string(self) -> ArrowDataType: ...

    def timestamp(self, unit: str, tz: str) -> ArrowDataType:
        raise NotImplementedError((unit, tz))

    def uint64(self) -> ArrowDataType: ...


type ArtifactValue = str | float | int | list[str] | None
ARROW = cast(ArrowModule, pyarrow)


def semantic_cell_key(experiment_name: str, coordinates: Mapping[str, JSONValue]) -> str:
    if not experiment_name.strip():
        raise ValueError("experiment name must not be empty")
    return f"{experiment_name}:{canonical_json_bytes(coordinates).decode('utf-8')}"


def canonical_active_path(workspace_root: Path, semantic_cell_key: str) -> Path:
    if not semantic_cell_key.strip():
        raise ValueError("semantic cell key must not be empty")
    cell_digest = hashlib.sha256(semantic_cell_key.encode("utf-8")).hexdigest()
    return workspace_root / "artifacts" / "active" / cell_digest


def descriptive_artifact_key(
    artifact_type: str,
    coordinates: Mapping[str, float | str],
) -> str:
    if not artifact_type.strip():
        raise ValueError("artifact type must not be empty")
    segments = [artifact_type]
    for name in sorted(coordinates):
        segments.append(semantic_coordinate_segment(name, coordinates[name]))
    return "-".join(segments)


def canonical_physical_types() -> Mapping[str, ArrowDataType]:
    return {
        "string": ARROW.string(),
        "boolean": ARROW.bool_(),
        "integer": ARROW.int64(),
        "large_identifier": ARROW.uint64(),
        "scientific_real": ARROW.float64(),
        "timestamp": ARROW.timestamp("us", tz="UTC"),
        "string_list": ARROW.list_(ARROW.string()),
        "canonical_json": ARROW.string(),
        "sha256_digest": ARROW.string(),
    }


def artifact_envelope_arrow_schema() -> ArrowSchema:
    physical_types = canonical_physical_types()
    string = physical_types["string"]
    digest = physical_types["sha256_digest"]
    return ARROW.schema(
        (
            ARROW.field("artifact_key", string, nullable=False),
            ARROW.field("artifact_type", string, nullable=False),
            ARROW.field("artifact_owner", string, nullable=False),
            ARROW.field("producer_component", string, nullable=False),
            ARROW.field("semantic_cell_key", string),
            ARROW.field("semantic_coordinates", physical_types["canonical_json"]),
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
            ARROW.field("rho", physical_types["scientific_real"]),
            ARROW.field("beta", physical_types["scientific_real"]),
            ARROW.field("delta", physical_types["scientific_real"]),
            ARROW.field("environment_lock_digest", digest),
            ARROW.field("code_commit", digest),
            ARROW.field("seed_set_keys", physical_types["string_list"], nullable=False),
            ARROW.field("parent_artifact_keys", physical_types["string_list"], nullable=False),
            ARROW.field("parent_artifact_digests", physical_types["string_list"], nullable=False),
            ARROW.field("input_paths", physical_types["string_list"], nullable=False),
            ARROW.field("canonical_active_path", string),
            ARROW.field("schema_name", string, nullable=False),
            ARROW.field("schema_version", physical_types["integer"], nullable=False),
        )
    )


def artifact_envelope_table(envelope: ArtifactEnvelope) -> ArrowTable:
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
