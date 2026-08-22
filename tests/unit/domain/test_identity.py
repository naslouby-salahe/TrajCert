import math

import pytest
from pydantic import ValidationError

from trajcert.domain.enums import (
    EXECUTION_DEPENDENCY_CHAIN,
    EXECUTION_PHASE_CONTRACTS,
    ExecutionPhase,
    ReusableArtifactLayer,
)
from trajcert.domain.identity import (
    LocalCertificateIdentity,
    ScientificCellIdentity,
)


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
    assert identity.semantic_coordinates() == {
        "experiment_name": "population-sensitivity-utility",
        "dataset_id_or_synthetic_law_name": "timing-terminal",
        "partition_name": "8-band",
        "rho": 0.05,
        "Gamma": 0.2,
        "K": 8,
        "other_explicit_sensitivity_or_ablation_coordinates": '{"axis":"rho"}',
    }
    with pytest.raises(ValidationError, match="finite"):
        ScientificCellIdentity.model_validate(identity.model_dump() | {"rho": math.nan})
    with pytest.raises(ValidationError):
        ScientificCellIdentity.model_validate(identity.model_dump() | {"attempt_number": 1})


def test_execution_contract_and_reusable_layers_match_the_roadmap() -> None:
    assert EXECUTION_DEPENDENCY_CHAIN == (
        ExecutionPhase.INPUTS,
        ExecutionPhase.PREPROCESSING,
        ExecutionPhase.TRAINING,
        ExecutionPhase.SCORING,
        ExecutionPhase.CALIBRATION_THRESHOLDING,
        ExecutionPhase.EVALUATION,
        ExecutionPhase.ANALYSIS,
        ExecutionPhase.REPORTING,
    )
    contracts = {contract.phase: contract for contract in EXECUTION_PHASE_CONTRACTS}
    assert contracts[ExecutionPhase.TRAINING].trajcert_meaning == "not applicable"
    assert contracts[ExecutionPhase.TRAINING].reusable_authoritative_artifacts == ("none",)
    assert contracts[ExecutionPhase.CALIBRATION_THRESHOLDING].trajcert_meaning == (
        "no learned calibration; rho, beta, delta, materiality thresholds, and multiplicity "
        "rules are prespecified"
    )
    assert tuple(ReusableArtifactLayer) == (
        ReusableArtifactLayer.PREPARED_LAW_AND_PARTITION,
        ReusableArtifactLayer.STOCHASTIC_EVENT_STREAM,
        ReusableArtifactLayer.DETERMINISTIC_COARSENING_AND_COUNT_PREFIX,
        ReusableArtifactLayer.POPULATION_SUFFICIENT_SUMMARY,
        ReusableArtifactLayer.POPULATION_SOLVER_AND_ORACLE,
        ReusableArtifactLayer.COMPARATOR_FIT_AND_REFERENCE,
        ReusableArtifactLayer.SEQUENTIAL_CONFIDENCE,
        ReusableArtifactLayer.SEQUENTIAL_PROJECTION,
        ReusableArtifactLayer.EVALUATION_AND_STATISTICAL,
        ReusableArtifactLayer.SOURCE_DATA_AND_DISPLAY,
    )
