from __future__ import annotations

import time
from enum import StrEnum

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
    LawName,
    Mass,
    NumericStatus,
    RiskBudget,
    RiskValue,
    RuntimeSeconds,
    SafetyCaseName,
    SafetyRegime,
    SensitivityBudget,
    ToleranceValue,
)


class ForeignInformationConditionLabel(StrEnum):
    TRUE_LOCAL = "true_local"
    FOREIGN_PATH = "foreign_path"
    NAIVE_POOLED = "naive_pooled"


_SAFETY_REGIME_RANK: dict[SafetyRegime, int] = {
    SafetyRegime.NO_RESOLVED_MASS: -1,
    SafetyRegime.RESOLVED_HARM_EXCEEDS_BUDGET: 0,
    SafetyRegime.INTRINSICALLY_UNCERTIFIABLE: 1,
    SafetyRegime.INTERIOR_SAFETY_FRONTIER: 2,
    SafetyRegime.ASSUMPTION_FREE_SAFE: 3,
}


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
    runtime_seconds: RuntimeSeconds


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


_MINIMUM_LAWS_FOR_FOREIGN_INFORMATION = 2


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
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> ForeignInformationNegativeControlResult:
    foreign_path_summary = _foreign_path_summary(local_summary, foreign_law, comparison_guard)
    naive_pooled_summary = _naive_pooled_summary(local_summary, foreign_law, comparison_guard)
    risk_budget = _fixed_risk_budget(local_summary)
    true_local = _evaluate_condition(
        local_summary, sensitivity_budget, risk_budget, root_atol, identity_atol
    )
    foreign_path = _evaluate_condition(
        foreign_path_summary, sensitivity_budget, risk_budget, root_atol, identity_atol
    )
    naive_pooled = _evaluate_condition(
        naive_pooled_summary, sensitivity_budget, risk_budget, root_atol, identity_atol
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
            true_local, foreign_path, identity_atol
        ),
        naive_pooled_spurious_improvement=_is_spurious_improvement(
            true_local, naive_pooled, identity_atol
        ),
    )


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
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
) -> ForeignInformationCondition:
    started = time.perf_counter()
    solve = solve_hidden_mass_interval(summary, sensitivity_budget, root_atol, identity_atol)
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
        runtime_seconds=elapsed,
    )


def _is_spurious_improvement(
    true_local: ForeignInformationCondition,
    other: ForeignInformationCondition,
    identity_atol: ToleranceValue,
) -> bool:
    if _SAFETY_REGIME_RANK[other.safety_regime] > _SAFETY_REGIME_RANK[true_local.safety_regime]:
        return True
    if true_local.hidden_mass_interval is not None and other.hidden_mass_interval is not None:
        true_width = true_local.hidden_mass_interval.width
        other_width = other.hidden_mass_interval.width
        return other_width < true_width - identity_atol
    return False
