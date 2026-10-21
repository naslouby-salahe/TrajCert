from __future__ import annotations

from trajcert.config import active_config
from trajcert.data.laws import LawParameters
from trajcert.data.summaries import ObservableSummary
from trajcert.experiments.feasibility import (
    PowerFeasibilityClass,
    population_feasibility,
    population_summary_at,
)
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import observed_timing_information
from trajcert.math.oracle import solve_information_oracle
from trajcert.math.safety import assess_safety_geometry
from trajcert.types import (
    AbsoluteError,
    BandCount,
    CompatibilityRegime,
    DomainModel,
    InformationNats,
    LawName,
    Probability,
    RiskBudget,
    RiskValue,
    ScientificState,
    SensitivityBudget,
)

_STATE_BY_CLASS: dict[PowerFeasibilityClass, ScientificState] = {
    PowerFeasibilityClass.STRICTLY_CERTIFIABLE: ScientificState.CERTIFIED,
    PowerFeasibilityClass.BOUNDARY_CERTIFIABLE: ScientificState.CERTIFIED,
    PowerFeasibilityClass.COMPATIBLE_NOT_CERTIFIABLE: ScientificState.UNCERTIFIED,
    PowerFeasibilityClass.MODEL_INCOMPATIBLE: ScientificState.MODEL_INCOMPATIBLE,
    PowerFeasibilityClass.INTRINSICALLY_UNCERTIFIABLE: ScientificState.INTRINSICALLY_UNCERTIFIABLE,
}


class BudgetDecision(DomainModel):
    risk_budget: RiskBudget
    state: ScientificState
    safety_frontier: InformationNats | None


class PartitionDecisionProfile(DomainModel):
    band_count: BandCount
    tau: InformationNats | None
    compatibility_regime: CompatibilityRegime
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    oracle_risk_upper: RiskValue | None
    oracle_abs_error: AbsoluteError | None
    decisions: tuple[BudgetDecision, ...]


class TrajectoryDecisionResult(DomainModel):
    law_name: LawName
    sensitivity_budget: SensitivityBudget
    true_theta: Probability
    profiles: tuple[PartitionDecisionProfile, ...]


def evaluate_trajectory_decision(
    parameters: LawParameters,
    sensitivity_budget: SensitivityBudget,
    band_counts: tuple[BandCount, ...],
    risk_budgets: tuple[RiskBudget, ...],
) -> TrajectoryDecisionResult:
    return TrajectoryDecisionResult(
        law_name=parameters.name,
        sensitivity_budget=sensitivity_budget,
        true_theta=parameters.theta,
        profiles=tuple(
            _profile(parameters, bands, sensitivity_budget, risk_budgets) for bands in band_counts
        ),
    )


def _profile(
    parameters: LawParameters,
    band_count: BandCount,
    sensitivity_budget: SensitivityBudget,
    risk_budgets: tuple[RiskBudget, ...],
) -> PartitionDecisionProfile:
    config = active_config.get()
    summary, _ = population_summary_at(parameters, band_count)
    solved = sharp_risk_set(
        summary,
        sensitivity_budget,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    oracle = solve_information_oracle(
        summary,
        sensitivity_budget,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.comparison_guard,
    )
    oracle_upper = (
        None if oracle.latent_risk_interval is None else oracle.latent_risk_interval.upper
    )
    risk = solved.latent_risk
    return PartitionDecisionProfile(
        band_count=band_count,
        tau=observed_timing_information(summary),
        compatibility_regime=solved.solve_result.compatibility.regime,
        risk_lower=None if risk is None else risk.lower,
        risk_upper=None if risk is None else risk.upper,
        oracle_risk_upper=oracle_upper,
        oracle_abs_error=(
            None if risk is None or oracle_upper is None else abs(risk.upper - oracle_upper)
        ),
        decisions=tuple(
            _decision(parameters, summary, band_count, sensitivity_budget, beta)
            for beta in risk_budgets
        ),
    )


def _decision(
    parameters: LawParameters,
    summary: ObservableSummary,
    band_count: BandCount,
    sensitivity_budget: SensitivityBudget,
    risk_budget: RiskBudget,
) -> BudgetDecision:
    feasibility = population_feasibility(parameters, band_count, sensitivity_budget, risk_budget)
    return BudgetDecision(
        risk_budget=risk_budget,
        state=_STATE_BY_CLASS[feasibility.classification],
        safety_frontier=assess_safety_geometry(summary, risk_budget).safety_frontier,
    )
