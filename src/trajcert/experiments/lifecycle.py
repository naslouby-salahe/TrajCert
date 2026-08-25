from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trajcert.domain.enums import PublicExecutionState, ScientificState


class FailureKind(StrEnum):
    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
    STALE_DEPENDENCY_INCOMPATIBLE = "STALE_DEPENDENCY_INCOMPATIBLE"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"
    SCIENTIFIC_FALSIFICATION = "SCIENTIFIC_FALSIFICATION"
    SCIENTIFIC_NULL_BOUNDARY = "SCIENTIFIC_NULL_BOUNDARY"
    PLANNED_NONAPPLICABILITY = "PLANNED_NONAPPLICABILITY"


@dataclass(frozen=True, slots=True)
class FailureConsequence:
    execution_state: PublicExecutionState
    scientific_state: ScientificState | None
    claim_state: str | None
    recovery_required: bool
    blocks_downstream_evidence: bool


@dataclass(frozen=True, slots=True)
class FailureAssessment:
    consequence: FailureConsequence
    internal_result_code: str | None


@dataclass(frozen=True, slots=True)
class FailureAssessmentInput:
    data_validation_failure: bool
    technical_failure: bool
    scientific_falsification: bool
    scientific_null_boundary: bool
    planned_nonapplicability: bool
    insufficient_evidence: bool


def assess_failure_precedence(
    failure_input: FailureAssessmentInput,
) -> FailureAssessment:
    if failure_input.data_validation_failure:
        return FailureAssessment(failure_consequence(FailureKind.DATA_VALIDATION_FAILURE), None)
    if failure_input.technical_failure:
        return FailureAssessment(
            failure_consequence(FailureKind.TECHNICAL_FAILURE), "TECHNICAL_FAIL"
        )
    if failure_input.planned_nonapplicability:
        return FailureAssessment(failure_consequence(FailureKind.PLANNED_NONAPPLICABILITY), None)
    if failure_input.scientific_falsification:
        return FailureAssessment(failure_consequence(FailureKind.SCIENTIFIC_FALSIFICATION), None)
    if failure_input.scientific_null_boundary or failure_input.insufficient_evidence:
        return FailureAssessment(failure_consequence(FailureKind.SCIENTIFIC_NULL_BOUNDARY), None)
    raise ValueError("failure assessment requires a classified outcome")


FAILURE_CONSEQUENCES = {
    FailureKind.TECHNICAL_FAILURE: FailureConsequence(
        PublicExecutionState.FAILED, None, None, True, True
    ),
    FailureKind.STALE_DEPENDENCY_INCOMPATIBLE: FailureConsequence(
        PublicExecutionState.BLOCKED, None, None, True, True
    ),
    FailureKind.DATA_VALIDATION_FAILURE: FailureConsequence(
        PublicExecutionState.INVALID, None, None, False, True
    ),
    FailureKind.SCIENTIFIC_FALSIFICATION: FailureConsequence(
        PublicExecutionState.COMPLETED, ScientificState.UNCERTIFIED, "NOT_SUPPORTED", False, False
    ),
    FailureKind.SCIENTIFIC_NULL_BOUNDARY: FailureConsequence(
        PublicExecutionState.COMPLETED, ScientificState.UNCERTIFIED, None, False, False
    ),
    FailureKind.PLANNED_NONAPPLICABILITY: FailureConsequence(
        PublicExecutionState.NOT_STARTED, None, None, False, False
    ),
}


def failure_consequence(kind: FailureKind) -> FailureConsequence:
    return FAILURE_CONSEQUENCES[kind]
