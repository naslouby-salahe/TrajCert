import pytest
from pydantic import ValidationError

from trajcert.domain.enums import PublicExecutionState, ScientificState
from trajcert.domain.identity import LocalCertificateIdentity
from trajcert.domain.operational import (
    ExecutionOutcome,
    PendingAction,
    ReuseEligibility,
    ReusePolicy,
    SemanticExecutionIdentity,
)


def test_pending_action_retains_issuing_epoch_identity() -> None:
    identity = LocalCertificateIdentity(
        client_id="client-1", action_channel_id="automatic", epoch_id="epoch-01"
    )
    action = PendingAction(event_id="event-1", issuing_identity=identity)

    assert action.issuing_identity.epoch_id == "epoch-01"


def test_invalid_data_has_no_scientific_certificate() -> None:
    with pytest.raises(ValidationError, match="cannot carry scientific evidence"):
        ExecutionOutcome(
            public_execution_state=PublicExecutionState.INVALID,
            scientific_state=ScientificState.CERTIFIED,
        )

    result = ExecutionOutcome(public_execution_state=PublicExecutionState.INVALID)

    assert result.scientific_state is None


def test_semantic_execution_reuse_requires_matching_material_dependencies() -> None:
    completed = SemanticExecutionIdentity("cell-1", "dependency-a")

    identical = SemanticExecutionIdentity("cell-1", "dependency-a")
    changed_dependency = SemanticExecutionIdentity("cell-1", "dependency-b")

    assert (
        completed.reuse_eligibility(identical, policy=ReusePolicy.REUSE_VALID)
        is ReuseEligibility.REUSABLE
    )
    assert (
        completed.reuse_eligibility(changed_dependency, policy=ReusePolicy.REUSE_VALID)
        is ReuseEligibility.NOT_REUSABLE
    )
    assert (
        completed.reuse_eligibility(identical, policy=ReusePolicy.OVERWRITE)
        is ReuseEligibility.NOT_REUSABLE
    )
