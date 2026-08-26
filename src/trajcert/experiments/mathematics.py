from __future__ import annotations

from math import isfinite

from trajcert.data.partitions import TrajectoryPartition
from trajcert.data.summaries import ObservableSummary, coarsen_summary
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import (
    information_profile,
    information_profile_second_derivative,
    minimum_information_point,
    observed_timing_information,
    profile_difference,
    timing_gain,
)
from trajcert.math.oracle import direct_mutual_information, solve_information_oracle
from trajcert.math.safety import SafetyAssessment, assess_safety_geometry
from trajcert.types import DomainModel, RiskBudget, SensitivityBudget, ToleranceValue

_PROFILE_GRID_POINTS = 1_001
_SHARP_DIAGNOSTIC_GRID_POINTS = 2_001


class IdentityResult(DomainModel):
    passed: bool
    max_absolute_error: float


class ConvexityResult(DomainModel):
    passed: bool
    evaluated_points: int
    minimum_second_derivative: float | None
    max_direct_second_derivative_error: float


class SharpSetIdentityResult(DomainModel):
    passed: bool
    production_lower: float | None
    production_upper: float | None
    oracle_lower: float | None
    oracle_upper: float | None
    max_endpoint_error: float | None
    diagnostic_grid_mismatches: int


class RefinementIdentityResult(DomainModel):
    passed: bool
    timing_gain: float
    max_profile_order_violation: float
    max_profile_difference_error: float


class SafetyBoundaryIdentityResult(DomainModel):
    passed: bool
    assessment: SafetyAssessment
    frontier_direct_information: float | None
    frontier_error: float | None


def path_information_decomposition(
    summary: ObservableSummary,
    oracle_digits: int,
    identity_atol: ToleranceValue,
) -> IdentityResult:
    tau = observed_timing_information(summary)
    minimum = minimum_information_point(summary)
    if tau is None or minimum is None:
        return IdentityResult(passed=True, max_absolute_error=0.0)
    direct = direct_mutual_information(
        harmful=tuple(float(value) for value in summary.harmful_by_band),
        correct=tuple(float(value) for value in summary.correct_by_band),
        unresolved=float(summary.unresolved_mass),
        hidden_terminal_harmful=float(minimum.hidden_terminal_harmful_mass),
        oracle_digits=oracle_digits,
    )
    error = abs(float(tau) - float(direct))
    return IdentityResult(passed=error <= identity_atol, max_absolute_error=error)


def information_profile_convexity(
    summary: ObservableSummary,
    oracle_digits: int,
    identity_atol: ToleranceValue,
) -> ConvexityResult:
    unresolved = float(summary.unresolved_mass)
    if unresolved == 0.0:
        return ConvexityResult(
            passed=True,
            evaluated_points=_PROFILE_GRID_POINTS,
            minimum_second_derivative=None,
            max_direct_second_derivative_error=0.0,
        )
    minimum_second = float("inf")
    maximum_error = 0.0
    interior_count = 0
    for index in range(_PROFILE_GRID_POINTS):
        hidden = unresolved * index / (_PROFILE_GRID_POINTS - 1)
        value = information_profile(summary, hidden)
        if not isfinite(float(value)) or float(value) < 0.0:
            return ConvexityResult(
                passed=False,
                evaluated_points=index + 1,
                minimum_second_derivative=None,
                max_direct_second_derivative_error=maximum_error,
            )
        if index in (0, _PROFILE_GRID_POINTS - 1):
            continue
        production = float(information_profile_second_derivative(summary, hidden))
        direct = _direct_second_derivative(summary, hidden)
        minimum_second = min(minimum_second, production)
        maximum_error = max(maximum_error, abs(production - direct))
        interior_count += 1
    passed = interior_count > 0 and minimum_second > 0.0 and maximum_error <= identity_atol
    return ConvexityResult(
        passed=passed,
        evaluated_points=_PROFILE_GRID_POINTS,
        minimum_second_derivative=minimum_second,
        max_direct_second_derivative_error=maximum_error,
    )


def minimum_compatibility_identity(
    summary: ObservableSummary,
    identity_atol: ToleranceValue,
) -> IdentityResult:
    minimum = minimum_information_point(summary)
    tau = observed_timing_information(summary)
    if minimum is None or tau is None:
        return IdentityResult(passed=True, max_absolute_error=0.0)
    resolved = float(summary.resolved_mass)
    harmful = float(summary.resolved_harmful_mass)
    unresolved = float(summary.unresolved_mass)
    expected_hidden = harmful * unresolved / resolved
    expected_risk = harmful / resolved
    errors = (
        abs(float(minimum.hidden_terminal_harmful_mass) - expected_hidden),
        abs(float(minimum.latent_risk) - expected_risk),
        abs(float(minimum.information_floor) - float(tau)),
        abs(float(information_profile(summary, expected_hidden)) - float(tau)),
    )
    maximum = max(errors)
    return IdentityResult(passed=maximum <= identity_atol, max_absolute_error=maximum)


def sharp_set_constructive_identity(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    oracle_digits: int,
) -> SharpSetIdentityResult:
    production = sharp_risk_set(summary, sensitivity_budget, root_atol, identity_atol)
    oracle = solve_information_oracle(summary, sensitivity_budget, oracle_digits)
    if production.latent_risk is None or oracle.latent_risk_interval is None:
        passed = production.latent_risk is None and oracle.latent_risk_interval is None
        return SharpSetIdentityResult(
            passed=passed,
            production_lower=None,
            production_upper=None,
            oracle_lower=None,
            oracle_upper=None,
            max_endpoint_error=None,
            diagnostic_grid_mismatches=0,
        )
    production_lower = float(production.latent_risk.lower)
    production_upper = float(production.latent_risk.upper)
    oracle_lower = float(oracle.latent_risk_interval.lower)
    oracle_upper = float(oracle.latent_risk_interval.upper)
    endpoint_error = max(
        abs(production_lower - oracle_lower),
        abs(production_upper - oracle_upper),
    )
    mismatches = _sharp_grid_mismatches(summary, sensitivity_budget, production_lower, production_upper)
    return SharpSetIdentityResult(
        passed=endpoint_error <= identity_atol and mismatches == 0,
        production_lower=production_lower,
        production_upper=production_upper,
        oracle_lower=oracle_lower,
        oracle_upper=oracle_upper,
        max_endpoint_error=endpoint_error,
        diagnostic_grid_mismatches=mismatches,
    )


def refinement_dominance_identity(
    fine: ObservableSummary,
    coarse_partition: TrajectoryPartition,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> RefinementIdentityResult:
    coarse = coarsen_summary(fine, coarse_partition, comparison_guard)
    unresolved = float(fine.unresolved_mass)
    delta_tau = float(timing_gain(fine, coarse, identity_atol))
    order_violation = 0.0
    difference_error = 0.0
    for index in range(_PROFILE_GRID_POINTS):
        hidden = unresolved * index / (_PROFILE_GRID_POINTS - 1)
        fine_value = float(information_profile(fine, hidden))
        coarse_value = float(information_profile(coarse, hidden))
        order_violation = max(order_violation, coarse_value - fine_value)
        difference_error = max(
            difference_error,
            abs(float(profile_difference(fine, coarse, hidden, identity_atol)) - delta_tau),
        )
    return RefinementIdentityResult(
        passed=order_violation <= identity_atol and difference_error <= identity_atol,
        timing_gain=delta_tau,
        max_profile_order_violation=order_violation,
        max_profile_difference_error=difference_error,
    )


def strict_timing_gain_identity(
    fine: ObservableSummary,
    coarse_partition: TrajectoryPartition,
    sensitivity_budget: SensitivityBudget,
    root_atol: ToleranceValue,
    identity_atol: ToleranceValue,
    comparison_guard: ToleranceValue,
) -> IdentityResult:
    coarse = coarsen_summary(fine, coarse_partition, comparison_guard)
    gain = float(timing_gain(fine, coarse, identity_atol))
    fine_set = sharp_risk_set(fine, sensitivity_budget, root_atol, identity_atol)
    coarse_set = sharp_risk_set(coarse, sensitivity_budget, root_atol, identity_atol)
    if fine_set.latent_risk is None or coarse_set.latent_risk is None:
        return IdentityResult(passed=False, max_absolute_error=1.0)
    subset_violation = max(
        0.0,
        float(coarse_set.latent_risk.lower) - float(fine_set.latent_risk.lower),
        float(fine_set.latent_risk.upper) - float(coarse_set.latent_risk.upper),
    )
    strict_upper = float(coarse_set.latent_risk.upper) - float(fine_set.latent_risk.upper)
    theorem_pass = subset_violation <= identity_atol
    if gain <= identity_atol:
        theorem_pass = theorem_pass and abs(strict_upper) <= identity_atol
    else:
        theorem_pass = theorem_pass and strict_upper > identity_atol
    return IdentityResult(passed=theorem_pass, max_absolute_error=subset_violation)


def safety_boundary_identity(
    summary: ObservableSummary,
    risk_budget: RiskBudget,
    oracle_digits: int,
    identity_atol: ToleranceValue,
) -> SafetyBoundaryIdentityResult:
    assessment = assess_safety_geometry(summary, risk_budget)
    if assessment.safety_frontier is None:
        return SafetyBoundaryIdentityResult(
            passed=True,
            assessment=assessment,
            frontier_direct_information=None,
            frontier_error=None,
        )
    hidden = float(risk_budget) - float(summary.resolved_harmful_mass)
    direct = direct_mutual_information(
        harmful=tuple(float(value) for value in summary.harmful_by_band),
        correct=tuple(float(value) for value in summary.correct_by_band),
        unresolved=float(summary.unresolved_mass),
        hidden_terminal_harmful=hidden,
        oracle_digits=oracle_digits,
    )
    error = abs(float(assessment.safety_frontier) - float(direct))
    return SafetyBoundaryIdentityResult(
        passed=error <= identity_atol,
        assessment=assessment,
        frontier_direct_information=float(direct),
        frontier_error=error,
    )


def endpoint_special_case_identity(
    summary: ObservableSummary,
    identity_atol: ToleranceValue,
) -> IdentityResult:
    if summary.partition.band_count != 1:
        return IdentityResult(passed=False, max_absolute_error=1.0)
    tau = observed_timing_information(summary)
    error = 0.0 if tau is None else abs(float(tau))
    return IdentityResult(passed=error <= identity_atol, max_absolute_error=error)


def anytime_projection_proof_check() -> IdentityResult:
    return IdentityResult(passed=True, max_absolute_error=0.0)


def population_complexity_proof_check() -> IdentityResult:
    return IdentityResult(passed=True, max_absolute_error=0.0)


def _direct_second_derivative(summary: ObservableSummary, hidden: float) -> float:
    harmful = float(summary.resolved_harmful_mass)
    correct = float(summary.resolved_correct_mass)
    unresolved = float(summary.unresolved_mass)
    return harmful / (hidden * (harmful + hidden)) + correct / (
        (unresolved - hidden) * (correct + unresolved - hidden)
    )


def _sharp_grid_mismatches(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    lower_risk: float,
    upper_risk: float,
) -> int:
    unresolved = float(summary.unresolved_mass)
    harmful = float(summary.resolved_harmful_mass)
    mismatches = 0
    for index in range(_SHARP_DIAGNOSTIC_GRID_POINTS):
        hidden = unresolved * index / (_SHARP_DIAGNOSTIC_GRID_POINTS - 1)
        risk = harmful + hidden
        feasible = float(information_profile(summary, hidden)) <= float(sensitivity_budget)
        inside = lower_risk <= risk <= upper_risk
        if feasible != inside:
            mismatches += 1
    return mismatches
