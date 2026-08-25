from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from trajcert.data.summaries import ObservableSummary
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.information import information_profile, minimum_information_point
from trajcert.types import (
    InformationNats,
    ReasonCode,
    RiskBudget,
    RiskValue,
    SafetyCaseName,
    SafetyRegime,
)

_RESOLVED_HARM_BOUNDARY_OFFSET = 0.005


@dataclass(frozen=True, slots=True)
class SafetyAssessment:
    regime: SafetyRegime
    risk_budget: RiskBudget
    resolved_harmful_mass: RiskValue
    minimum_information_risk: RiskValue | None
    assumption_free_upper: RiskValue
    safety_frontier: InformationNats | None


@dataclass(frozen=True, slots=True)
class SafetyBudgetCase:
    name: SafetyCaseName
    risk_budget: RiskBudget | None
    valid: bool
    invalid_reason: ReasonCode | None


def assess_safety_geometry(summary: ObservableSummary, risk_budget: RiskBudget) -> SafetyAssessment:
    beta = _risk_budget(risk_budget)
    harmful = float(summary.resolved_harmful_mass)
    assumption_free_upper = harmful + float(summary.unresolved_mass)
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
    theta_dagger = float(minimum.latent_risk)
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


def safety_budget_cases(summary: ObservableSummary) -> tuple[SafetyBudgetCase, ...]:
    harmful = float(summary.resolved_harmful_mass)
    theta_max = harmful + float(summary.unresolved_mass)
    minimum = minimum_information_point(summary)
    if minimum is None:
        return (
            SafetyBudgetCase(
                name=SafetyCaseName("Below resolved harmful mass"),
                risk_budget=max(0.0, harmful - _RESOLVED_HARM_BOUNDARY_OFFSET),
                valid=True,
                invalid_reason=None,
            ),
            SafetyBudgetCase(
                name=SafetyCaseName("Between resolved mass and intrinsic boundary"),
                risk_budget=None,
                valid=False,
                invalid_reason=ReasonCode("DEGENERATE_SAFETY_INTERVAL"),
            ),
            SafetyBudgetCase(
                name=SafetyCaseName("At intrinsic boundary"),
                risk_budget=None,
                valid=False,
                invalid_reason=ReasonCode("NO_RESOLVED_MASS"),
            ),
            SafetyBudgetCase(
                name=SafetyCaseName("Interior safety frontier"),
                risk_budget=None,
                valid=False,
                invalid_reason=ReasonCode("NO_RESOLVED_MASS"),
            ),
            SafetyBudgetCase(
                name=SafetyCaseName("Assumption-free boundary"),
                risk_budget=theta_max,
                valid=True,
                invalid_reason=None,
            ),
        )
    theta_dagger = float(minimum.latent_risk)
    between_is_valid = harmful != theta_dagger
    return (
        SafetyBudgetCase(
            name=SafetyCaseName("Below resolved harmful mass"),
            risk_budget=max(0.0, harmful - _RESOLVED_HARM_BOUNDARY_OFFSET),
            valid=True,
            invalid_reason=None,
        ),
        SafetyBudgetCase(
            name=SafetyCaseName("Between resolved mass and intrinsic boundary"),
            risk_budget=(harmful + theta_dagger / 2.0) if between_is_valid else None,
            valid=between_is_valid,
            invalid_reason=None if between_is_valid else ReasonCode("DEGENERATE_SAFETY_INTERVAL"),
        ),
        SafetyBudgetCase(
            name=SafetyCaseName("At intrinsic boundary"),
            risk_budget=theta_dagger,
            valid=True,
            invalid_reason=None,
        ),
        SafetyBudgetCase(
            name=SafetyCaseName("Interior safety frontier"),
            risk_budget=(theta_dagger + theta_max / 2.0),
            valid=True,
            invalid_reason=None,
        ),
        SafetyBudgetCase(
            name=SafetyCaseName("Assumption-free boundary"),
            risk_budget=theta_max,
            valid=True,
            invalid_reason=None,
        ),
    )


def _risk_budget(value: RiskBudget) -> float:
    numeric = float(value)
    if not isfinite(numeric) or numeric < 0.0 or numeric > 1.0:
        raise InvalidScientificDataError("risk budget must be finite and lie in [0, 1]")
    return numeric
