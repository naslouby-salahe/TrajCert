from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from trajcert.domain.records.execution import DependencyFingerprintInput, ProvenanceFingerprintInput
from trajcert.domain.serialization import JSONValue, canonical_json_bytes


@dataclass(frozen=True, slots=True)
class ProvenanceEnvelope:
    git_commit: str
    dirty_tree_flag: bool
    dependency_lock_sha256: str
    container_image_digest: str
    python_implementation_version: str
    os_kernel: str
    cpu_model: str
    package_versions: tuple[str, ...]
    arithmetic_threading_environment: tuple[str, ...]
    input_checksums: tuple[str, ...]
    semantic_coordinates: str
    scientific_specification_digest: str
    scientific_dependency_digest: str
    implementation_component_digest: str
    environment_dependency_digest: str
    dependency_fingerprint: str
    partition_law_dataset_checksums: tuple[str, ...]
    seed_manifest_checksums: tuple[str, ...]
    execution_start_timestamp: datetime
    execution_end_timestamp: datetime | None


def canonical_provenance_envelope_payload(value: ProvenanceEnvelope) -> bytes:
    return canonical_json_bytes(
        {
            "arithmetic_threading_environment": value.arithmetic_threading_environment,
            "container_image_digest": value.container_image_digest,
            "cpu_model": value.cpu_model,
            "dependency_fingerprint": value.dependency_fingerprint,
            "dependency_lock_sha256": value.dependency_lock_sha256,
            "dirty_tree_flag": value.dirty_tree_flag,
            "environment_dependency_digest": value.environment_dependency_digest,
            "execution_end_timestamp": None
            if value.execution_end_timestamp is None
            else value.execution_end_timestamp.isoformat(),
            "execution_start_timestamp": value.execution_start_timestamp.isoformat(),
            "git_commit": value.git_commit,
            "implementation_component_digest": value.implementation_component_digest,
            "input_checksums": value.input_checksums,
            "os_kernel": value.os_kernel,
            "package_versions": value.package_versions,
            "partition_law_dataset_checksums": value.partition_law_dataset_checksums,
            "python_implementation_version": value.python_implementation_version,
            "scientific_dependency_digest": value.scientific_dependency_digest,
            "scientific_specification_digest": value.scientific_specification_digest,
            "seed_manifest_checksums": value.seed_manifest_checksums,
            "semantic_coordinates": value.semantic_coordinates,
        }
    )


def canonical_provenance_payload(value: ProvenanceFingerprintInput) -> bytes:
    payload: Mapping[str, JSONValue] = {
        "code_commit": value.code_commit,
        "container_image_digest": value.container_image_digest,
        "dataset_preprocessing_checksums": tuple(
            str(checksum) for checksum in value.dataset_preprocessing_checksums
        ),
        "dirty_tree_flag": value.dirty_tree_flag,
        "environment_lock_digest": value.environment_lock_digest,
        "partition_checksum": value.partition_checksum,
        "plan_digest": value.plan_digest,
        "scientific_specification_digest": value.scientific_specification_digest,
        "seed_manifest_checksums": tuple(
            str(checksum) for checksum in value.seed_manifest_checksums
        ),
    }
    return canonical_json_bytes(payload)


def canonical_dependency_payload(value: DependencyFingerprintInput) -> bytes:
    payload: Mapping[str, JSONValue] = {
        "artifact_type": value.artifact_type,
        "environment_dependency_digest": value.environment_dependency_digest,
        "implementation_component_digest": value.implementation_component_digest,
        "parent_artifact_keys": tuple(value.parent_artifact_keys),
        "parent_scientific_content_digests": tuple(
            str(digest) for digest in value.parent_scientific_content_digests
        ),
        "producer_immutable_inputs": value.producer_immutable_inputs,
        "scientific_dependency_digest": value.scientific_dependency_digest,
        "seed_manifest_digest": value.seed_manifest_digest,
        "semantic_coordinates": value.semantic_coordinates,
    }
    return canonical_json_bytes(payload)
