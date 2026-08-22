import math

import pytest
from pydantic import ValidationError

from trajcert.domain.identity import LocalCertificateIdentity, ScientificCellIdentity


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


def test_scientific_cell_identity_contains_only_declared_semantic_coordinates() -> None:
    identity = ScientificCellIdentity(
        experiment_name="population-sensitivity-utility",
        dataset_id_or_synthetic_law_name="timing-terminal",
        partition_name="8-band",
        rho=0.05,
        Gamma=0.2,
        K=8,
        other_explicit_sensitivity_or_ablation_coordinates='{"axis":"rho"}',
    )

    assert identity.model_dump(by_alias=True)["Gamma"] == 0.2
    with pytest.raises(ValidationError, match="finite"):
        ScientificCellIdentity.model_validate(identity.model_dump() | {"rho": math.nan})
