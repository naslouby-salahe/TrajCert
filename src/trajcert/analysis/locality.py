from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from trajcert.data.ledger import LedgerIdentity
from trajcert.exceptions import InvalidScientificDataError
from trajcert.provenance import ProducerComponentName
from trajcert.storage import ArtifactKey
from trajcert.types import (
    ActionChannelId,
    ClientId,
    DomainModel,
    EpochId,
    NonNegativeInt,
)


class ScientificInputClass(StrEnum):
    TARGET_STREAM_EVENT_COUNT = "target-stream-event-count-artifacts"
    TARGET_EPOCH_MANIFEST = "target-epoch-manifest"
    TARGET_PARTITION_MANIFEST = "target-partition-manifest"
    CONFIG_VALUES = "config.py-values"
    LOCAL_NUMERICAL_DEPENDENCY = "local-numerical-dependencies"


class StaticComponentDependency(DomainModel):
    producer_component: ProducerComponentName
    scientific_input_classes: tuple[ScientificInputClass, ...]
    scientific_client_ids: tuple[ClientId, ...] = ()


class RuntimeLineageArtifact(DomainModel):
    artifact_key: ArtifactKey
    parent_artifact_keys: tuple[ArtifactKey, ...] = ()
    client_id: ClientId | None = None
    action_channel_id: ActionChannelId | None = None
    epoch_id: EpochId | None = None
    foreign_client_ids: tuple[ClientId, ...] = ()
    foreign_client_statistics: bool = False
    foreign_model_updates: bool = False
    cross_client_aggregate: bool = False


class LocalValidityAuditResult(DomainModel):
    static_dependency_pass: bool
    runtime_lineage_pass: bool
    foreign_scientific_parent_count: NonNegativeInt
    violating_artifact_keys: tuple[ArtifactKey, ...]
    passed: bool = Field(serialization_alias="pass")


def audit_local_validity(
    target_identity: LedgerIdentity,
    static_dependencies: tuple[StaticComponentDependency, ...],
    root_artifact_key: ArtifactKey,
    lineage_artifacts: tuple[RuntimeLineageArtifact, ...],
) -> LocalValidityAuditResult:
    static_pass = static_dependency_audit(target_identity, static_dependencies)
    runtime_pass, violating = runtime_lineage_audit(
        target_identity, root_artifact_key, lineage_artifacts
    )
    return LocalValidityAuditResult(
        static_dependency_pass=static_pass,
        runtime_lineage_pass=runtime_pass,
        foreign_scientific_parent_count=len(violating),
        violating_artifact_keys=violating,
        passed=static_pass and runtime_pass,
    )


def static_dependency_audit(
    target_identity: LedgerIdentity,
    dependencies: tuple[StaticComponentDependency, ...],
) -> bool:
    expected_components = {
        ProducerComponentName("inference/categorical.py"),
        ProducerComponentName("inference/confidence.py"),
        ProducerComponentName("inference/envelope.py"),
        ProducerComponentName("inference/projection.py"),
        ProducerComponentName("inference/certification.py"),
    }
    supplied_components = tuple(item.producer_component for item in dependencies)
    if len(supplied_components) != len(set(supplied_components)):
        return False
    if set(supplied_components) != expected_components:
        return False
    return all(
        client_id == target_identity.client_id
        for dependency in dependencies
        for client_id in dependency.scientific_client_ids
    )


def runtime_lineage_audit(
    target_identity: LedgerIdentity,
    root_artifact_key: ArtifactKey,
    artifacts: tuple[RuntimeLineageArtifact, ...],
) -> tuple[bool, tuple[ArtifactKey, ...]]:
    by_key = {artifact.artifact_key: artifact for artifact in artifacts}
    if len(by_key) != len(artifacts):
        raise InvalidScientificDataError("runtime lineage contains duplicate artifact keys")
    violating: set[ArtifactKey] = set()
    visited: set[ArtifactKey] = set()
    visiting: set[ArtifactKey] = set()

    def visit(artifact_key: ArtifactKey) -> None:
        if artifact_key in visited:
            return
        if artifact_key in visiting:
            raise InvalidScientificDataError("runtime lineage parent graph contains a cycle")
        artifact = by_key.get(artifact_key)
        if artifact is None:
            violating.add(artifact_key)
            return
        visiting.add(artifact_key)
        identity_fields = (artifact.client_id, artifact.action_channel_id, artifact.epoch_id)
        target_fields = (
            target_identity.client_id,
            target_identity.action_channel_id,
            target_identity.epoch_id,
        )
        if any(value is not None for value in identity_fields) and identity_fields != target_fields:
            violating.add(artifact.artifact_key)
        if (
            artifact.foreign_client_ids
            or artifact.foreign_client_statistics
            or artifact.foreign_model_updates
            or artifact.cross_client_aggregate
        ):
            violating.add(artifact.artifact_key)
        for parent_key in artifact.parent_artifact_keys:
            visit(parent_key)
        visiting.remove(artifact_key)
        visited.add(artifact_key)

    visit(root_artifact_key)
    ordered = tuple(sorted(violating, key=str))
    return not ordered, ordered
