from __future__ import annotations

from trajcert.analysis.locality import (
    RuntimeLineageArtifact,
    ScientificInputClass,
    StaticComponentDependency,
    audit_local_validity,
)
from trajcert.data.ledger import LedgerIdentity
from trajcert.provenance import ProducerComponentName
from trajcert.storage import ArtifactKey
from trajcert.types import ActionChannelId, ClientId, EpochId


def test_local_bound_lineage_accepts_only_target_identity() -> None:
    identity = _identity()
    dependencies = _static_dependencies(identity.client_id)
    source = RuntimeLineageArtifact(
        artifact_key=ArtifactKey("target-stream"),
        client_id=identity.client_id,
        action_channel_id=identity.action_channel_id,
        epoch_id=identity.epoch_id,
    )
    root = RuntimeLineageArtifact(
        artifact_key=ArtifactKey("local-bound"),
        parent_artifact_keys=(source.artifact_key,),
        client_id=identity.client_id,
        action_channel_id=identity.action_channel_id,
        epoch_id=identity.epoch_id,
    )
    result = audit_local_validity(identity, dependencies, root.artifact_key, (source, root))
    assert result.passed
    assert result.foreign_scientific_parent_count == 0


def test_local_bound_lineage_rejects_foreign_scientific_parent() -> None:
    identity = _identity()
    dependencies = _static_dependencies(identity.client_id)
    foreign = RuntimeLineageArtifact(
        artifact_key=ArtifactKey("foreign-parent"),
        client_id=ClientId("foreign-client"),
        action_channel_id=identity.action_channel_id,
        epoch_id=identity.epoch_id,
        foreign_client_statistics=True,
    )
    root = RuntimeLineageArtifact(
        artifact_key=ArtifactKey("local-bound"),
        parent_artifact_keys=(foreign.artifact_key,),
        client_id=identity.client_id,
        action_channel_id=identity.action_channel_id,
        epoch_id=identity.epoch_id,
    )
    result = audit_local_validity(identity, dependencies, root.artifact_key, (foreign, root))
    assert not result.passed
    assert result.violating_artifact_keys == (foreign.artifact_key,)


def test_static_dependency_audit_rejects_foreign_client_input() -> None:
    identity = _identity()
    dependencies = list(_static_dependencies(identity.client_id))
    dependencies[0] = dependencies[0].model_copy(
        update={"scientific_client_ids": (ClientId("foreign-client"),)}
    )
    root = RuntimeLineageArtifact(artifact_key=ArtifactKey("local-bound"))
    result = audit_local_validity(identity, tuple(dependencies), root.artifact_key, (root,))
    assert not result.static_dependency_pass
    assert not result.passed


def _identity() -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("target-client"),
        action_channel_id=ActionChannelId("automatic-action"),
        epoch_id=EpochId("static-epoch"),
    )


def _static_dependencies(client_id: ClientId) -> tuple[StaticComponentDependency, ...]:
    components = (
        "inference/categorical.py",
        "inference/confidence.py",
        "inference/envelope.py",
        "inference/projection.py",
        "inference/certification.py",
    )
    return tuple(
        StaticComponentDependency(
            producer_component=ProducerComponentName(component),
            scientific_input_classes=(ScientificInputClass.LOCAL_NUMERICAL_DEPENDENCY,),
            scientific_client_ids=(client_id,),
        )
        for component in components
    )
