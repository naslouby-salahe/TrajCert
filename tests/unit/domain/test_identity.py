import pytest
from pydantic import ValidationError

from trajcert.domain.identity import LocalCertificateIdentity


def test_local_certificate_identity_is_immutable_and_exact() -> None:
    identity = LocalCertificateIdentity(
        client_id="client-1", action_channel_id="automatic", epoch_id="epoch-01"
    )

    assert identity.model_dump() == {
        "client_id": "client-1",
        "action_channel_id": "automatic",
        "epoch_id": "epoch-01",
    }

    with pytest.raises(ValidationError):
        LocalCertificateIdentity(client_id="", action_channel_id="automatic", epoch_id="epoch-01")

    with pytest.raises(ValidationError):
        LocalCertificateIdentity.model_validate(
            {
                "client_id": "client-1",
                "action_channel_id": "automatic",
                "epoch_id": "epoch-01",
                "foreign_client_id": "client-2",
            }
        )
