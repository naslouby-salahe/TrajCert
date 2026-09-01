from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.information import information_profile, minimum_information_point
from trajcert.types import (
    DomainModel,
    InformationNats,
    ReasonCode,
    RiskBudget,
    RiskValue,
    SafetyCaseName,
    SafetyRegime,
    ToleranceValue,
)


@dataclass(frozen=True, slots=True)
class SafetyAssessment:
    regime: SafetyRegime
    risk_budget: RiskBudget
    resolved_harmful_mass: RiskValue
    minimum_information_risk: RiskValue | None
    assumption_free_upper: RiskValue
    safety_frontier: InformationNats | None


class SafetyBudgetCase(DomainModel):
    name: SafetyCaseName
    risk_budget: RiskBudget | None
    valid: bool
    invalid_reason: ReasonCode | None


def assess_safety_geometry(summary: ObservableSummary, risk_budget: RiskBudget) -> SafetyAssessment:
    beta = _risk_budget(risk_budget)
    harmful = summary.resolved_harmful_mass
    assumption_free_upper = harmful + summary.unresolved_mass
    minimum = minimum_information_point(summary)
    if minimum is None:
        return SafetyAssessment(
            regime=SafetyRegime.NO_RESOLVED_MASS,
            risk_budget=beta,
            resolved_harmful_mass=harmful,
            minimum_information_risk=None,
            assumption_free_upper=assumption_free_upper,
            safety_frontier=None,
        )
    theta_dagger = minimum.latent_risk
    if beta < harmful:
        regime = SafetyRegime.RESOLVED_HARM_EXCEEDS_BUDGET
        frontier = None
    elif beta < theta_dagger:
        regime = SafetyRegime.INTRINSICALLY_UNCERTIFIABLE
        frontier = None
    elif beta < assumption_free_upper:
        regime = SafetyRegime.INTERIOR_SAFETY_FRONTIER
        frontier = information_profile(summary, beta - harmful)
    else:
        regime = SafetyRegime.ASSUMPTION_FREE_SAFE
        frontier = None
    return SafetyAssessment(
        regime=regime,
        risk_budget=beta,
        resolved_harmful_mass=harmful,
        minimum_information_risk=minimum.latent_risk,
        assumption_free_upper=assumption_free_upper,
        safety_frontier=frontier,
    )


def safety_budget_cases(
    summary: ObservableSummary, resolved_harm_boundary_offset: ToleranceValue
) -> tuple[SafetyBudgetCase, ...]:
    harmful = summary.resolved_harmful_mass
    theta_max = harmful + summary.unresolved_mass
    minimum = minimum_information_point(summary)
    if minimum is None:
        return (
            SafetyBudgetCase(
                name=SafetyCaseName.BELOW_RESOLVED_HARMFUL_MASS,
                risk_budget=max(0.0, harmful - resolved_harm_boundary_offset),
                valid=True,
                invalid_reason=None,
            ),
            SafetyBudgetCase(
                name=SafetyCaseName.BETWEEN_RESOLVED_MASS_AND_INTRINSIC_BOUNDARY,
                risk_budget=None,
                valid=False,
                invalid_reason=ReasonCode("DEGENERATE_SAFETY_INTERVAL"),
            ),
            SafetyBudgetCase(
                name=SafetyCaseName.AT_INTRINSIC_BOUNDARY,
                risk_budget=None,
                valid=False,
                invalid_reason=ReasonCode("NO_RESOLVED_MASS"),
            ),
            SafetyBudgetCase(
                name=SafetyCaseName.INTERIOR_SAFETY_FRONTIER,
                risk_budget=None,
                valid=False,
                invalid_reason=ReasonCode("NO_RESOLVED_MASS"),
            ),
            SafetyBudgetCase(
                name=SafetyCaseName.ASSUMPTION_FREE_BOUNDARY,
                risk_budget=theta_max,
                valid=True,
                invalid_reason=None,
            ),
        )
    theta_dagger = minimum.latent_risk
    between_is_valid = harmful != theta_dagger
    return (
        SafetyBudgetCase(
            name=SafetyCaseName.BELOW_RESOLVED_HARMFUL_MASS,
            risk_budget=max(0.0, harmful - resolved_harm_boundary_offset),
            valid=True,
            invalid_reason=None,
        ),
        SafetyBudgetCase(
            name=SafetyCaseName.BETWEEN_RESOLVED_MASS_AND_INTRINSIC_BOUNDARY,
            risk_budget=((harmful + theta_dagger) / 2.0) if between_is_valid else None,
            valid=between_is_valid,
            invalid_reason=None if between_is_valid else ReasonCode("DEGENERATE_SAFETY_INTERVAL"),
        ),
        SafetyBudgetCase(
            name=SafetyCaseName.AT_INTRINSIC_BOUNDARY,
            risk_budget=theta_dagger,
            valid=True,
            invalid_reason=None,
        ),
        SafetyBudgetCase(
            name=SafetyCaseName.INTERIOR_SAFETY_FRONTIER,
            risk_budget=(theta_dagger + theta_max) / 2.0,
            valid=True,
            invalid_reason=None,
        ),
        SafetyBudgetCase(
            name=SafetyCaseName.ASSUMPTION_FREE_BOUNDARY,
            risk_budget=theta_max,
            valid=True,
            invalid_reason=None,
        ),
    )


def _risk_budget(value: RiskBudget) -> RiskBudget:
    if not isfinite(value) or value < 0.0 or value > 1.0:
        raise InvalidScientificDataError("risk budget must be finite and lie in [0, 1]")
    return value
