from trajcert.domain.enums import PublicExecutionState, ScientificState
from trajcert.experiments.lifecycle import (
    FailureKind,
    assess_failure_precedence,
    failure_consequence,
)


def test_failure_consequences_keep_technical_and_scientific_outcomes_distinct() -> None:
    technical = failure_consequence(FailureKind.TECHNICAL_FAILURE)
    falsification = failure_consequence(FailureKind.SCIENTIFIC_FALSIFICATION)
    null_boundary = failure_consequence(FailureKind.SCIENTIFIC_NULL_BOUNDARY)

    assert technical.execution_state is PublicExecutionState.FAILED
    assert technical.scientific_state is None
    assert technical.recovery_required
    assert falsification.execution_state is PublicExecutionState.COMPLETED
    assert falsification.claim_state == "NOT_SUPPORTED"
    assert null_boundary.scientific_state is ScientificState.UNCERTIFIED


def test_failure_precedence_prevents_technical_or_invalid_outcomes_being_scientific_evidence() -> (
    None
):
    invalid = assess_failure_precedence(True, True, True, False, False, False)
    technical = assess_failure_precedence(False, True, True, False, False, False)
    insufficient = assess_failure_precedence(False, False, False, False, False, True)

    assert invalid.consequence.execution_state is PublicExecutionState.INVALID
    assert invalid.consequence.scientific_state is None
    assert technical.consequence.execution_state is PublicExecutionState.FAILED
    assert technical.internal_result_code == "TECHNICAL_FAIL"
    assert insufficient.consequence.execution_state is PublicExecutionState.COMPLETED
    assert insufficient.consequence.scientific_state is ScientificState.UNCERTIFIED
