from dataclasses import replace

from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import InternalExecutionState, PublicExecutionState, ScientificState
from trajcert.inference.states import (
    InferenceValidity,
    StateGateInput,
    classify_scientific_state,
)


def state_input() -> StateGateInput:
    configuration = load_configuration()
    return StateGateInput(
        InferenceValidity.VALID,
        configuration.minimum_evidence.matured_events,
        configuration.minimum_evidence.resolved_events,
        True,
        0.01,
        0.01,
        False,
        0.01,
        0.05,
        0.05,
        configuration.minimum_evidence,
        configuration.numerics,
    )


def test_validity_precedes_evidence_and_scientific_states() -> None:
    valid = state_input()

    invalid = classify_scientific_state(replace(valid, validity=InferenceValidity.INVALID))
    technical_failure = classify_scientific_state(
        replace(valid, validity=InferenceValidity.TECHNICAL_FAIL)
    )
    insufficient = classify_scientific_state(replace(valid, matured_events=0))

    assert invalid.public_execution_state is PublicExecutionState.INVALID
    assert invalid.internal_execution_state is InternalExecutionState.INVALID
    assert invalid.scientific_state is None
    assert technical_failure.public_execution_state is PublicExecutionState.FAILED
    assert technical_failure.internal_execution_state is InternalExecutionState.FAILED
    assert technical_failure.scientific_state is None
    assert insufficient.scientific_state is ScientificState.INSUFFICIENT_EVIDENCE


def test_substantive_state_precedence_and_strict_comparison_guard() -> None:
    valid = state_input()
    guard = valid.numerics.scientific_comparison_guard

    compatible_boundary = classify_scientific_state(
        replace(valid, compatibility_lower_bound=valid.deployment_information_budget + guard)
    )
    incompatible = classify_scientific_state(
        replace(valid, compatibility_lower_bound=valid.deployment_information_budget + 2 * guard)
    )
    impossible = classify_scientific_state(
        replace(
            valid,
            compatibility_lower_bound=0.01,
            intrinsic_risk_lower_bound=valid.deployment_risk_budget + 2 * guard,
        )
    )
    certified = classify_scientific_state(
        replace(valid, proven_upper_risk=valid.deployment_risk_budget)
    )

    assert compatible_boundary.scientific_state is ScientificState.CERTIFIED
    assert incompatible.scientific_state is ScientificState.MODEL_INCOMPATIBLE
    assert impossible.scientific_state is ScientificState.INTRINSICALLY_UNCERTIFIABLE
    assert certified.scientific_state is ScientificState.CERTIFIED
