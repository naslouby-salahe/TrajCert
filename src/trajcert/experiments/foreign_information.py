from __future__ import annotations

import time
from enum import StrEnum
from typing import Final

from trajcert.data.laws import LawParameters, build_full_law, configured_laws, resolved_band_weights
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError, InvariantViolationError
from trajcert.math.information import observed_timing_information
from trajcert.math.safety import assess_safety_geometry, safety_budget_cases
from trajcert.math.solver import solve_hidden_mass_interval
from trajcert.types import (
    CompatibilityRegime,
    DomainModel,
    HiddenMassInterval,
    InformationNats,
    LawCount,
    LawName,
    Mass,
    NumericStatus,
    Ordinal,
    Probability,
    RiskBudget,
    RiskValue,
    RuntimeSeconds,
    SafetyCaseName,
    SafetyRegime,
    SensitivityBudget,
    SlopeValue,
    ToleranceValue,
)


class ForeignInformationConditionLabel(StrEnum):
    TRUE_LOCAL = "true_local"
    FOREIGN_PATH = "foreign_path"
    NAIVE_POOLED = "naive_pooled"


_SAFETY_REGIME_SEVERITY: dict[SafetyRegime, Ordinal] = {
    SafetyRegime.NO_RESOLVED_MASS: 1,
    SafetyRegime.RESOLVED_HARM_EXCEEDS_BUDGET: 2,
    SafetyRegime.INTRINSICALLY_UNCERTIFIABLE: 3,
    SafetyRegime.INTERIOR_SAFETY_FRONTIER: 4,
    SafetyRegime.ASSUMPTION_FREE_SAFE: 5,
}


class ForeignEffect(StrEnum):
    NO_CHANGE = "NO_CHANGE"
    BENIGN_TIGHTENING = "BENIGN_TIGHTENING"
    CONSERVATIVE_WIDENING = "CONSERVATIVE_WIDENING"
    ERRONEOUS_BOUND = "ERRONEOUS_BOUND"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"


class ForeignInformationCondition(DomainModel):
    resolved_harmful_mass: Mass
    resolved_correct_mass: Mass
    unresolved_mass: Mass
    observed_timing_information: InformationNats | None
    compatibility_regime: CompatibilityRegime
    numeric_status: NumericStatus
    hidden_mass_interval: HiddenMassInterval | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    safety_regime: SafetyRegime
    safety_frontier: InformationNats | None
    certified: bool
    contains_true_risk: bool | None
    underestimates_true_risk: bool | None
    false_certification: bool
    runtime_seconds: RuntimeSeconds


class ForeignHeterogeneityPoint(DomainModel):
    heterogeneity: Probability
    foreign_path: ForeignInformationCondition
    naive_pooled: ForeignInformationCondition
    foreign_path_effect: ForeignEffect
    naive_pooled_effect: ForeignEffect


class ForeignInformationNegativeControlResult(DomainModel):
    local_law_name: LawName
    foreign_law_name: LawName
    sensitivity_budget: SensitivityBudget
    risk_budget: RiskBudget
    true_local: ForeignInformationCondition
    foreign_path: ForeignInformationCondition
    naive_pooled: ForeignInformationCondition
    foreign_spurious_improvement: bool
    naive_pooled_spurious_improvement: bool
    true_risk: Probability
    foreign_path_effect: ForeignEffect
    naive_pooled_effect: ForeignEffect
    heterogeneity: tuple[ForeignHeterogeneityPoint, ...]


_MINIMUM_LAWS_FOR_FOREIGN_INFORMATION: Final[LawCount] = 2


class ForeignNumerics(DomainModel):
    root_atol: ToleranceValue
    identity_atol: ToleranceValue
    comparison_guard: ToleranceValue


def foreign_law_for(local_law_name: LawName) -> LawParameters:
    laws = configured_laws()
    if len(laws) < _MINIMUM_LAWS_FOR_FOREIGN_INFORMATION:
        raise InvalidScientificDataError(
            "Foreign-Information Negative Control requires at least two configured laws"
        )
    names = [law.name for law in laws]
    if local_law_name not in names:
        raise InvalidScientificDataError(f"unknown synthetic law: {local_law_name}")
    index = names.index(local_law_name)
    return laws[(index + 1) % len(laws)]


def evaluate_foreign_information_negative_control(
    local_summary: ObservableSummary,
    local_law: LawParameters,
    foreign_law: LawParameters,
    sensitivity_budget: SensitivityBudget,
    numerics: ForeignNumerics,
    heterogeneity_levels: tuple[Probability, ...],
) -> ForeignInformationNegativeControlResult:
    risk_budget = _fixed_risk_budget(local_summary)
    true_local = _evaluate_condition(
        local_summary, sensitivity_budget, risk_budget, local_law.theta, numerics
    )
    foreign_path, naive_pooled = _foreign_conditions(
        local_summary, foreign_law, sensitivity_budget, risk_budget, local_law.theta, numerics
    )
    return ForeignInformationNegativeControlResult(
        local_law_name=local_law.name,
        foreign_law_name=foreign_law.name,
        sensitivity_budget=sensitivity_budget,
        risk_budget=risk_budget,
        true_local=true_local,
        foreign_path=foreign_path,
        naive_pooled=naive_pooled,
        foreign_spurious_improvement=_is_spurious_improvement(
            true_local, foreign_path, numerics.identity_atol
        ),
        naive_pooled_spurious_improvement=_is_spurious_improvement(
            true_local, naive_pooled, numerics.identity_atol
        ),
        true_risk=local_law.theta,
        foreign_path_effect=_effect(true_local, foreign_path, numerics.identity_atol),
        naive_pooled_effect=_effect(true_local, naive_pooled, numerics.identity_atol),
        heterogeneity=tuple(
            _heterogeneity_point(
                local_summary,
                true_local,
                _blend_law(local_law, foreign_law, level),
                (level, sensitivity_budget, risk_budget, local_law.theta),
                numerics,
            )
            for level in heterogeneity_levels
        ),
    )


def _foreign_conditions(
    local_summary: ObservableSummary,
    foreign_law: LawParameters,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    true_risk: Probability,
    numerics: ForeignNumerics,
) -> tuple[ForeignInformationCondition, ForeignInformationCondition]:
    foreign_path = _evaluate_condition(
        _foreign_path_summary(local_summary, foreign_law, numerics.comparison_guard),
        sensitivity_budget,
        risk_budget,
        true_risk,
        numerics,
    )
    naive_pooled = _evaluate_condition(
        _naive_pooled_summary(local_summary, foreign_law, numerics.comparison_guard),
        sensitivity_budget,
        risk_budget,
        true_risk,
        numerics,
    )
    return foreign_path, naive_pooled


def _heterogeneity_point(
    local_summary: ObservableSummary,
    true_local: ForeignInformationCondition,
    blended: LawParameters,
    context: tuple[Probability, SensitivityBudget, RiskBudget, Probability],
    numerics: ForeignNumerics,
) -> ForeignHeterogeneityPoint:
    level, sensitivity_budget, risk_budget, true_risk = context
    foreign_path, naive_pooled = _foreign_conditions(
        local_summary, blended, sensitivity_budget, risk_budget, true_risk, numerics
    )
    return ForeignHeterogeneityPoint(
        heterogeneity=level,
        foreign_path=foreign_path,
        naive_pooled=naive_pooled,
        foreign_path_effect=_effect(true_local, foreign_path, numerics.identity_atol),
        naive_pooled_effect=_effect(true_local, naive_pooled, numerics.identity_atol),
    )


def _blend_law(local: LawParameters, foreign: LawParameters, level: Probability) -> LawParameters:
    return foreign.model_copy(
        update={
            "theta": _blend_probability(local.theta, foreign.theta, level),
            "q1": _blend_probability(local.q1, foreign.q1, level),
            "q0": _blend_probability(local.q0, foreign.q0, level),
            "lambda1": _blend_slope(local.lambda1, foreign.lambda1, level),
            "lambda0": _blend_slope(local.lambda0, foreign.lambda0, level),
        }
    )


def _blend_probability(left: Probability, right: Probability, level: Probability) -> Probability:
    return left + level * (right - left)


def _blend_slope(left: SlopeValue, right: SlopeValue, level: Probability) -> SlopeValue:
    return left + level * (right - left)


def _foreign_path_summary(
    local: ObservableSummary,
    foreign_law: LawParameters,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    bands = local.partition.band_count
    harmful_shape = resolved_band_weights(bands, foreign_law.lambda1)
    correct_shape = resolved_band_weights(bands, foreign_law.lambda0)
    return summarize_observable_masses(
        partition=local.partition,
        harmful_by_band=local.resolved_harmful_mass * harmful_shape,
        correct_by_band=local.resolved_correct_mass * correct_shape,
        unresolved_mass=local.unresolved_mass,
        comparison_guard=comparison_guard,
    )


def _naive_pooled_summary(
    local: ObservableSummary,
    foreign_law: LawParameters,
    comparison_guard: ToleranceValue,
) -> ObservableSummary:
    bands = local.partition.band_count
    foreign_full = build_full_law(foreign_law, bands)
    return summarize_observable_masses(
        partition=local.partition,
        harmful_by_band=0.5 * (local.harmful_by_band + foreign_full.harmful_resolved),
        correct_by_band=0.5 * (local.correct_by_band + foreign_full.correct_resolved),
        unresolved_mass=0.5 * (local.unresolved_mass + foreign_full.unresolved),
        comparison_guard=comparison_guard,
    )


def _fixed_risk_budget(summary: ObservableSummary) -> RiskBudget:
    cases = {case.name: case for case in safety_budget_cases(summary)}
    interior = cases[SafetyCaseName.INTERIOR_SAFETY_FRONTIER]
    if interior.valid and interior.risk_budget is not None:
        return interior.risk_budget
    fallback = cases[SafetyCaseName.ASSUMPTION_FREE_BOUNDARY]
    if fallback.risk_budget is None:
        raise InvariantViolationError("assumption-free safety case must always be valid")
    return fallback.risk_budget


def _evaluate_condition(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
    true_risk: Probability,
    numerics: ForeignNumerics,
) -> ForeignInformationCondition:
    started = time.perf_counter()
    solve = solve_hidden_mass_interval(
        summary, sensitivity_budget, numerics.root_atol, numerics.identity_atol
    )
    safety = assess_safety_geometry(summary, risk_budget)
    elapsed = time.perf_counter() - started
    numeric_status = (
        NumericStatus.NOT_APPLICABLE
        if solve.compatibility.regime is CompatibilityRegime.MODEL_INCOMPATIBLE
        else NumericStatus.FINITE
    )
    risk_lower: RiskValue | None = None
    risk_upper: RiskValue | None = None
    if solve.interval is not None:
        risk_lower = summary.resolved_harmful_mass + solve.interval.lower
        risk_upper = summary.resolved_harmful_mass + solve.interval.upper
    atol = numerics.identity_atol
    certified = risk_upper is not None and risk_upper <= risk_budget
    return ForeignInformationCondition(
        resolved_harmful_mass=summary.resolved_harmful_mass,
        resolved_correct_mass=summary.resolved_correct_mass,
        unresolved_mass=summary.unresolved_mass,
        observed_timing_information=observed_timing_information(summary),
        compatibility_regime=solve.compatibility.regime,
        numeric_status=numeric_status,
        hidden_mass_interval=solve.interval,
        risk_lower=risk_lower,
        risk_upper=risk_upper,
        safety_regime=safety.regime,
        safety_frontier=safety.safety_frontier,
        certified=certified,
        contains_true_risk=(
            None
            if risk_lower is None or risk_upper is None
            else risk_lower - atol <= true_risk <= risk_upper + atol
        ),
        underestimates_true_risk=None if risk_upper is None else risk_upper < true_risk - atol,
        false_certification=certified and true_risk > risk_budget + atol,
        runtime_seconds=elapsed,
    )


def _introduces_error(
    true_local: ForeignInformationCondition, other: ForeignInformationCondition
) -> bool:
    return (
        (other.contains_true_risk is False and true_local.contains_true_risk is not False)
        or (
            other.underestimates_true_risk is True
            and true_local.underestimates_true_risk is not True
        )
        or (other.false_certification and not true_local.false_certification)
    )


def _effect(
    true_local: ForeignInformationCondition,
    other: ForeignInformationCondition,
    identity_atol: ToleranceValue,
) -> ForeignEffect:
    if other.hidden_mass_interval is None:
        return ForeignEffect.MODEL_INCOMPATIBLE
    if _introduces_error(true_local, other):
        return ForeignEffect.ERRONEOUS_BOUND
    if true_local.hidden_mass_interval is None:
        return ForeignEffect.NO_CHANGE
    difference = other.hidden_mass_interval.width - true_local.hidden_mass_interval.width
    if difference < -identity_atol:
        return ForeignEffect.BENIGN_TIGHTENING
    if difference > identity_atol:
        return ForeignEffect.CONSERVATIVE_WIDENING
    return ForeignEffect.NO_CHANGE


def _is_spurious_improvement(
    true_local: ForeignInformationCondition,
    other: ForeignInformationCondition,
    identity_atol: ToleranceValue,
) -> bool:
    if (
        _SAFETY_REGIME_SEVERITY[other.safety_regime]
        > _SAFETY_REGIME_SEVERITY[true_local.safety_regime]
    ):
        return True
    if true_local.hidden_mass_interval is not None and other.hidden_mass_interval is not None:
        true_width = true_local.hidden_mass_interval.width
        other_width = other.hidden_mass_interval.width
        return other_width < true_width - identity_atol
    return False
