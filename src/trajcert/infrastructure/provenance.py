from __future__ import annotations

from trajcert.domain.records.execution import DependencyFingerprintInput, ProvenanceFingerprintInput
from trajcert.domain.serialization import JSONValue, canonical_json_bytes


def canonical_provenance_payload(value: ProvenanceFingerprintInput) -> bytes:
    payload: dict[str, JSONValue] = {
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
    payload: dict[str, JSONValue] = {
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
