from __future__ import annotations

import numpy as np

from trajcert.data.summaries import ObservableSummary
from trajcert.math.information import observed_timing_information
from trajcert.math.oracle import direct_mutual_information, solve_information_oracle
from trajcert.math.safety import assess_safety_geometry
from trajcert.math.solver import solve_hidden_mass_interval
from trajcert.types import (
    CompatibilityRegime,
    DomainModel,
    InformationNats,
    RiskBudget,
    RiskValue,
    RootStatus,
    SafetyRegime,
    SensitivityBudget,
    ToleranceValue,
    Vector,
)


class SolverOracleComparison(DomainModel):
    sensitivity_budget: SensitivityBudget
    compatibility_regime: CompatibilityRegime
    oracle_regime: CompatibilityRegime
    tau: InformationNats | None
    theta_dagger: RiskValue | None
    risk_lower: RiskValue | None
    risk_upper: RiskValue | None
    passed: bool
    state_match: bool
    abs_u_lower_error: float | None
    abs_u_upper_error: float | None
    abs_risk_upper_error: float | None
    max_endpoint_error: float | None
    max_root_bracket_width: float | None
    max_root_residual: float | None


class SafetyFrontierOracleComparison(DomainModel):
    applicable: bool
    production_rho_star: float | None
    oracle_rho_star: float | None
    absolute_error: float | None
    passed: bool


def compare_production_solver_to_oracle(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    oracle_digits: int,
) -> SolverOracleComparison:
    production = solve_hidden_mass_interval(
        summary,
        sensitivity_budget,
        root_atol,
        identity_atol,
    )
    oracle = solve_information_oracle(summary, sensitivity_budget, oracle_digits)
    state_match = production.compatibility.regime == oracle.regime
    lower_error: float | None = None
    upper_error: float | None = None
    risk_upper_error: float | None = None
    endpoint_error: float | None = None
    if production.interval is not None and oracle.hidden_mass_interval is not None:
        lower_error = abs(
            float(production.interval.lower) - float(oracle.hidden_mass_interval.lower)
        )
        upper_error = abs(
            float(production.interval.upper) - float(oracle.hidden_mass_interval.upper)
        )
        risk_upper_error = upper_error
        endpoint_error = max(lower_error, upper_error)
    elif production.interval is not None or oracle.hidden_mass_interval is not None:
        state_match = False
    brackets = tuple(
        bracket for bracket in (production.lower_root, production.upper_root) if bracket is not None
    )
    max_width = max((float(bracket.width) for bracket in brackets), default=None)
    max_residual = max((float(bracket.residual) for bracket in brackets), default=None)
    passed = state_match
    if endpoint_error is not None:
        passed = passed and endpoint_error <= identity_atol
    if max_width is not None:
        passed = passed and max_width <= root_atol
    if any(
        float(bracket.residual) > identity_atol
        for bracket in brackets
        if bracket.status is not RootStatus.EXACT_BOUNDARY
    ):
        passed = False
    risk_lower: RiskValue | None = None
    risk_upper: RiskValue | None = None
    if production.interval is not None:
        resolved_harmful = float(summary.resolved_harmful_mass)
        risk_lower = resolved_harmful + float(production.interval.lower)
        risk_upper = resolved_harmful + float(production.interval.upper)
    minimum = production.compatibility.minimum_information_point
    tau_value = observed_timing_information(summary)
    return SolverOracleComparison(
        sensitivity_budget=sensitivity_budget,
        compatibility_regime=production.compatibility.regime,
        oracle_regime=oracle.regime,
        tau=None if tau_value is None else float(tau_value),
        theta_dagger=None if minimum is None else float(minimum.latent_risk),
        risk_lower=risk_lower,
        risk_upper=risk_upper,
        passed=passed,
        state_match=state_match,
        abs_u_lower_error=lower_error,
        abs_u_upper_error=upper_error,
        abs_risk_upper_error=risk_upper_error,
        max_endpoint_error=endpoint_error,
        max_root_bracket_width=max_width,
        max_root_residual=max_residual,
    )


def compare_safety_frontier_to_oracle(
    summary: ObservableSummary,
    risk_budget: RiskBudget,
    oracle_digits: int,
    identity_atol: ToleranceValue,
) -> SafetyFrontierOracleComparison:
    safety = assess_safety_geometry(summary, risk_budget)
    if safety.regime is not SafetyRegime.INTERIOR_SAFETY_FRONTIER:
        return SafetyFrontierOracleComparison(
            applicable=False,
            production_rho_star=None,
            oracle_rho_star=None,
            absolute_error=None,
            passed=True,
        )
    if safety.safety_frontier is None:
        return SafetyFrontierOracleComparison(
            applicable=True,
            production_rho_star=None,
            oracle_rho_star=None,
            absolute_error=None,
            passed=False,
        )
    hidden = float(risk_budget) - float(summary.resolved_harmful_mass)
    oracle_value = direct_mutual_information(
        harmful=_float_tuple(summary.harmful_by_band),
        correct=_float_tuple(summary.correct_by_band),
        unresolved=float(summary.unresolved_mass),
        hidden_terminal_harmful=hidden,
        oracle_digits=oracle_digits,
    )
    production_value = float(safety.safety_frontier)
    oracle_rho_star = float(oracle_value)
    error = abs(production_value - oracle_rho_star)
    return SafetyFrontierOracleComparison(
        applicable=True,
        production_rho_star=production_value,
        oracle_rho_star=oracle_rho_star,
        absolute_error=error,
        passed=error <= identity_atol,
    )


def _float_tuple(values: Vector) -> tuple[float, ...]:
    array = np.asarray(values, dtype=np.float64)
    return tuple(array.item(index) for index in range(array.size))
