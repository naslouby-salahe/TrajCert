import pytest

from trajcert.domain.identity import LocalCertificateIdentity
from trajcert.domain.manifests import EpochManifest


def manifest(*, action_policy: str = "policy-a", epoch_id: str = "epoch-01") -> EpochManifest:
    return EpochManifest(
        identity=LocalCertificateIdentity(
            client_id="client-1", action_channel_id="automatic", epoch_id=epoch_id
        ),
        detector_model_identity="detector-a",
        action_policy=action_policy,
        adjudication_regime="adjudication-a",
        event_logging_semantics="logging-a",
        terminal_horizon_age_units=8,
        finest_trajectory_representation="eight-bands",
    )


def test_material_change_closes_epoch_without_reassigning_identity() -> None:
    closed = manifest().close_for_material_change(manifest(action_policy="policy-b"))

    assert closed.closed_manifest.identity == closed.replacement_manifest.identity
    assert closed.closed_manifest.action_policy == "policy-a"
    assert closed.replacement_manifest.action_policy == "policy-b"


def test_epoch_cannot_close_without_material_change_or_identity_change() -> None:
    with pytest.raises(ValueError, match="material change"):
        manifest().close_for_material_change(manifest())

    with pytest.raises(ValueError, match="identity"):
        manifest().close_for_material_change(manifest(epoch_id="epoch-02"))
