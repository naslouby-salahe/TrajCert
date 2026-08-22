from trajcert.domain.enums import PublicExecutionState, ScientificState
from trajcert.experiments.lifecycle import FailureKind, failure_consequence


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
