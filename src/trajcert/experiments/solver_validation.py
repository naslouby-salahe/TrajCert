from __future__ import annotations

from trajcert.data.summaries import ObservableSummary
from trajcert.math.oracle import direct_mutual_information, solve_information_oracle
from trajcert.math.safety import assess_safety_geometry
from trajcert.math.solver import solve_hidden_mass_interval
from trajcert.types import (
    DomainModel,
    RiskBudget,
    SafetyRegime,
    SensitivityBudget,
    ToleranceValue,
)


class SolverOracleComparison(DomainModel):
    passed: bool
    state_match: bool
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
    endpoint_error: float | None = None
    if production.interval is not None and oracle.hidden_mass_interval is not None:
        endpoint_error = max(
            abs(float(production.interval.lower) - float(oracle.hidden_mass_interval.lower)),
            abs(float(production.interval.upper) - float(oracle.hidden_mass_interval.upper)),
        )
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
    if max_residual is not None:
        passed = passed and max_residual <= identity_atol
    return SolverOracleComparison(
        passed=passed,
        state_match=state_match,
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
        harmful=tuple(float(value) for value in summary.harmful_by_band),
        correct=tuple(float(value) for value in summary.correct_by_band),
        unresolved=float(summary.unresolved_mass),
        hidden_terminal_harmful=hidden,
        oracle_digits=oracle_digits,
    )
    production_value = float(safety.safety_frontier)
    error = abs(production_value - float(oracle_value))
    return SafetyFrontierOracleComparison(
        applicable=True,
        production_rho_star=production_value,
        oracle_rho_star=float(oracle_value),
        absolute_error=error,
        passed=error <= identity_atol,
    )
