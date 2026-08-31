from __future__ import annotations

from trajcert.exceptions import InvalidScientificDataError
from trajcert.inference.categorical import CategoricalState
from trajcert.inference.projection import ProjectionResult
from trajcert.types import (
    Count,
    DomainModel,
    NumericStatus,
    PositiveInt,
    RiskBudget,
    ScientificState,
    SensitivityBudget,
    ToleranceValue,
)


class CertificationAssessment(DomainModel):
    numeric_status: NumericStatus
    scientific_state: ScientificState | None
    matured_count: Count
    resolved_count: Count
    sensitivity_budget: SensitivityBudget
    risk_budget: RiskBudget
    projection_upper: RiskBudget | None
    compatibility_lower_bound: SensitivityBudget | None
    intrinsic_risk_lower_bound: RiskBudget | None


def classify_certification(
    state: CategoricalState,
    projection: ProjectionResult | None,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    minimum_matured_events: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    minimum_resolved_events: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    comparison_guard: ToleranceValue,
) -> CertificationAssessment:
    rho = sensitivity_budget
    beta = risk_budget
    guard = comparison_guard
    if rho < 0.0 or beta < 0.0 or beta > 1.0 or guard <= 0.0:
        raise InvalidScientificDataError("invalid certification budget or comparison guard")
    matured = state.matured_count
    resolved = state.resolved_count
    if projection is None:
        return CertificationAssessment(
            numeric_status=NumericStatus.TECHNICAL_FAIL,
            scientific_state=None,
            matured_count=matured,
            resolved_count=resolved,
            sensitivity_budget=rho,
            risk_budget=beta,
            projection_upper=None,
            compatibility_lower_bound=None,
            intrinsic_risk_lower_bound=None,
        )
    compatibility_lower = projection.compatibility_lower_bound
    intrinsic_lower = projection.intrinsic_risk_lower_bound
    upper = projection.proven_upper
    if matured < minimum_matured_events or resolved < minimum_resolved_events:
        scientific_state = ScientificState.INSUFFICIENT_EVIDENCE
    elif compatibility_lower > rho + guard:
        scientific_state = ScientificState.MODEL_INCOMPATIBLE
    elif intrinsic_lower is not None and intrinsic_lower > beta + guard:
        scientific_state = ScientificState.INTRINSICALLY_UNCERTIFIABLE
    elif upper <= beta:
        scientific_state = ScientificState.CERTIFIED
    else:
        scientific_state = ScientificState.UNCERTIFIED
    return CertificationAssessment(
        numeric_status=NumericStatus.FINITE,
        scientific_state=scientific_state,
        matured_count=matured,
        resolved_count=resolved,
        sensitivity_budget=rho,
        risk_budget=beta,
        projection_upper=upper,
        compatibility_lower_bound=compatibility_lower,
        intrinsic_risk_lower_bound=intrinsic_lower,
    )
