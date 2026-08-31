from __future__ import annotations

from enum import StrEnum
from math import isfinite

import numpy as np

from trajcert.comparators.legacy import LegacyApplicability, legacy_bandwise_odds_ratio
from trajcert.config import active_config
from trajcert.data.partitions import TrajectoryPartition, build_partition
from trajcert.data.summaries import ObservableSummary, coarsen_summary, summarize_observable_masses
from trajcert.exceptions import InvalidScientificDataError
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
from trajcert.math.safety import (
    SafetyAssessment,
    SafetyBudgetCase,
    assess_safety_geometry,
)
from trajcert.types import (
    Count,
    DomainModel,
    FiniteFloat,
    HiddenMassInterval,
    InformationCurvature,
    InformationNats,
    Mass,
    NonNegativeFloat,
    PositiveInt,
    Probability,
    RiskBudget,
    RiskInterval,
    RiskValue,
    SensitivityBudget,
    ToleranceValue,
)


class IdentityResult(DomainModel):
    passed: bool # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    max_absolute_error: NonNegativeFloat # TODO: Consider using a proper alias type or whatever already exists with actually fits this


class ConvexityResult(DomainModel):
    passed: bool # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    evaluated_points: Count
    minimum_second_derivative: InformationCurvature | None
    max_direct_second_derivative_error: NonNegativeFloat


class SharpSetIdentityResult(DomainModel):
    passed: bool # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    production_lower: RiskValue | None
    production_upper: RiskValue | None
    oracle_lower: RiskValue | None
    oracle_upper: RiskValue | None
    max_endpoint_error: NonNegativeFloat | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    diagnostic_grid_mismatches: Count


class RefinementIdentityResult(DomainModel):
    passed: bool # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    timing_gain: InformationNats
    max_profile_order_violation: NonNegativeFloat # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    max_profile_difference_error: NonNegativeFloat # TODO: Consider using a proper alias type or whatever already exists with actually fits this


class SafetyBoundaryIdentityResult(DomainModel):
    passed: bool # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    assessment: SafetyAssessment
    frontier_direct_information: InformationNats | None
    frontier_error: NonNegativeFloat | None # TODO: Consider using a proper alias type or whatever already exists with actually fits this


class SafetyBoundaryCaseEvaluation(DomainModel):
    case: SafetyBudgetCase
    identity: SafetyBoundaryIdentityResult | None
    passed: bool # TODO: Consider using a proper alias type or whatever already exists with actually fits this


def path_information_decomposition(
    summary: ObservableSummary,
    oracle_digits: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
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
    oracle_digits: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    identity_atol: ToleranceValue,
) -> ConvexityResult:
    del oracle_digits
    grid_points = active_config.get().numerics.profile_grid_points
    unresolved = float(summary.unresolved_mass)
    if unresolved == 0.0:
        return ConvexityResult(
            passed=True,
            evaluated_points=grid_points,
            minimum_second_derivative=None,
            max_direct_second_derivative_error=0.0,
        )
    minimum_second = float("inf")
    maximum_error = 0.0
    interior_count = 0
    for index in range(grid_points):
        hidden = unresolved * index / (grid_points - 1)
        value = information_profile(summary, hidden)
        if not isfinite(float(value)) or float(value) < 0.0:
            return ConvexityResult(
                passed=False,
                evaluated_points=index + 1,
                minimum_second_derivative=None,
                max_direct_second_derivative_error=maximum_error,
            )
        if index in (0, grid_points - 1):
            continue
        production = float(information_profile_second_derivative(summary, hidden))
        direct = _direct_second_derivative(summary, hidden)
        minimum_second = min(minimum_second, production)
        maximum_error = max(maximum_error, abs(production - direct))
        interior_count += 1
    passed = interior_count > 0 and minimum_second > 0.0 and maximum_error <= identity_atol
    return ConvexityResult(
        passed=passed,
        evaluated_points=grid_points,
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
    oracle_digits: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    oracle_bracket_width: ToleranceValue,
) -> SharpSetIdentityResult:
    production = sharp_risk_set(summary, sensitivity_budget, root_atol, identity_atol)
    oracle = solve_information_oracle(
        summary, sensitivity_budget, oracle_digits, oracle_bracket_width
    )
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
    production_lower = production.latent_risk.lower
    production_upper = float(production.latent_risk.upper)
    oracle_lower = float(oracle.latent_risk_interval.lower)
    oracle_upper = float(oracle.latent_risk_interval.upper)
    endpoint_error = max(
        abs(production_lower - oracle_lower),
        abs(production_upper - oracle_upper),
    )
    mismatches = _sharp_grid_mismatches(
        summary, sensitivity_budget, production_lower, production_upper
    )
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
    grid_points = active_config.get().numerics.profile_grid_points
    for index in range(grid_points):
        hidden = unresolved * index / (grid_points - 1)
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
    oracle_digits: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
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
    hidden = risk_budget - summary.resolved_harmful_mass
    direct = direct_mutual_information(
        harmful=tuple(float(value) for value in summary.harmful_by_band),
        correct=tuple(float(value) for value in summary.correct_by_band),
        unresolved=summary.unresolved_mass,
        hidden_terminal_harmful=hidden,
        oracle_digits=oracle_digits,
    )
    error = abs(assessment.safety_frontier - direct)
    return SafetyBoundaryIdentityResult(
        passed=error <= identity_atol,
        assessment=assessment,
        frontier_direct_information=float(direct),
        frontier_error=error,
    )


def evaluate_safety_boundary_case(
    summary: ObservableSummary,
    case: SafetyBudgetCase,
    oracle_digits: PositiveInt, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    identity_atol: ToleranceValue,
) -> SafetyBoundaryCaseEvaluation:
    if not case.valid or case.risk_budget is None:
        return SafetyBoundaryCaseEvaluation(case=case, identity=None, passed=True)
    identity = safety_boundary_identity(
        summary=summary,
        risk_budget=case.risk_budget,
        oracle_digits=oracle_digits,
        identity_atol=identity_atol,
    )
    return SafetyBoundaryCaseEvaluation(
        case=case,
        identity=identity,
        passed=identity.passed,
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


def _direct_second_derivative(summary: ObservableSummary, hidden: Mass) -> InformationCurvature:
    harmful = float(summary.resolved_harmful_mass)
    correct = float(summary.resolved_correct_mass)
    unresolved = float(summary.unresolved_mass)
    return harmful / (hidden * (harmful + hidden)) + correct / (
        (unresolved - hidden) * (correct + unresolved - hidden)
    )


def _sharp_grid_mismatches(
    summary: ObservableSummary,
    sensitivity_budget: SensitivityBudget,
    lower_risk: RiskValue,
    upper_risk: RiskValue,
) -> Count:
    unresolved = float(summary.unresolved_mass)
    harmful = float(summary.resolved_harmful_mass)
    mismatches = 0
    grid_points = active_config.get().numerics.sharp_diagnostic_grid_points
    for index in range(grid_points):
        hidden = unresolved * index / (grid_points - 1)
        risk = harmful + hidden
        feasible = information_profile(summary, hidden) <= sensitivity_budget
        inside = lower_risk <= risk <= upper_risk
        if feasible != inside:
            mismatches += 1
    return mismatches


class EndpointDifferenceDirection(StrEnum):
    WIDER = "WIDER"
    NARROWER = "NARROWER"
    SHIFTED = "SHIFTED"


class LegacyPartitionIncoherenceResult(DomainModel):
    gamma: FiniteFloat # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    q: FiniteFloat # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    true_hidden_terminal_harmful: FiniteFloat # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    fine_hidden_mass_interval: HiddenMassInterval
    endpoint_hidden_mass_interval: HiddenMassInterval
    fine_risk_interval: RiskInterval
    endpoint_risk_interval: RiskInterval
    endpoint_difference_direction: EndpointDifferenceDirection
    endpoint_difference_magnitude: FiniteFloat # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    passed: bool # TODO: Consider using a proper alias type or whatever already exists with actually fits this


def evaluate_legacy_partition_incoherence(
    gamma: FiniteFloat, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
    q: FiniteFloat, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
) -> LegacyPartitionIncoherenceResult:
    config = active_config.get()
    if gamma < 1.0:
        raise InvalidScientificDataError("legacy incoherence Gamma must be at least one")
    if not 0.0 < q < 1.0:
        raise InvalidScientificDataError("legacy incoherence q must lie strictly inside (0, 1)")
    p_correct, p_harmful = (
        config.study_design.legacy_partition_incoherence.latent_outcome_probabilities
    )
    harmful_hazards = (_tilted_probability(q, gamma), _tilted_probability(q, 1.0 / gamma))
    correct_hazards = (q, q)
    harmful_by_band, harmful_unresolved = _response_masses(float(p_harmful), harmful_hazards)
    correct_by_band, correct_unresolved = _response_masses(float(p_correct), correct_hazards)
    unresolved = harmful_unresolved + correct_unresolved
    fine_partition = build_partition(
        finest_band_count=2, # TODO: these are magic numbers that should be from conf
        band_count=2, # TODO: these are magic numbers that should be from conf
        terminal_horizon=config.method.terminal_horizon,
    )
    fine = summarize_observable_masses(
        partition=fine_partition,
        harmful_by_band=np.asarray(harmful_by_band, dtype=np.float64),
        correct_by_band=np.asarray(correct_by_band, dtype=np.float64),
        unresolved_mass=unresolved,
        comparison_guard=config.numerics.comparison_guard,
    )
    endpoint_partition = build_partition(
        finest_band_count=2, # TODO: these are magic numbers that should be from conf
        band_count=1, # TODO: these are magic numbers that should be from conf
        terminal_horizon=config.method.terminal_horizon,
    )
    endpoint = coarsen_summary(fine, endpoint_partition, config.numerics.comparison_guard)
    fine_result = legacy_bandwise_odds_ratio(fine, gamma)
    endpoint_result = legacy_bandwise_odds_ratio(endpoint, gamma)
    if (
        fine_result.applicability is not LegacyApplicability.APPLICABLE
        or endpoint_result.applicability is not LegacyApplicability.APPLICABLE
        or fine_result.hidden_mass_interval is None
        or endpoint_result.hidden_mass_interval is None
        or fine_result.latent_risk_interval is None
        or endpoint_result.latent_risk_interval is None
    ):
        raise InvalidScientificDataError(
            "authoritative legacy incoherence case unexpectedly became model-incompatible"
        )
    true_hidden = harmful_unresolved
    fine_risk = fine_result.latent_risk_interval
    endpoint_risk = endpoint_result.latent_risk_interval
    difference = max(
        abs(endpoint_risk.lower - fine_risk.lower),
        abs(endpoint_risk.upper - fine_risk.upper),
    )
    fine_width = fine_risk.upper - fine_risk.lower
    endpoint_width = endpoint_risk.upper - endpoint_risk.lower
    atol = config.numerics.identity_atol
    if endpoint_width > fine_width + atol:
        direction = EndpointDifferenceDirection.WIDER
    elif endpoint_width + atol < fine_width:
        direction = EndpointDifferenceDirection.NARROWER
    else:
        direction = EndpointDifferenceDirection.SHIFTED
    hidden_interval = fine_result.hidden_mass_interval
    true_hidden_feasible = (
        float(hidden_interval.lower) - atol <= true_hidden <= float(hidden_interval.upper) + atol
    )
    return LegacyPartitionIncoherenceResult(
        gamma=gamma,
        q=q,
        true_hidden_terminal_harmful=true_hidden,
        fine_hidden_mass_interval=hidden_interval,
        endpoint_hidden_mass_interval=endpoint_result.hidden_mass_interval,
        fine_risk_interval=fine_risk,
        endpoint_risk_interval=endpoint_risk,
        endpoint_difference_direction=direction,
        endpoint_difference_magnitude=difference,
        passed=true_hidden_feasible and difference > atol,
    )


def _tilted_probability(q: FiniteFloat, # TODO: Consider using a proper alias type or whatever already exists with actually fits this
                        gamma: FiniteFloat # TODO: Consider using a proper alias type or whatever already exists with actually fits this
                        ) -> Probability:
    return gamma * q / (1.0 - q + gamma * q)


def _response_masses(
    prior: Probability,
    hazards: tuple[Probability, Probability],
) -> tuple[tuple[Mass, Mass], Mass]: # TODO:  This output should be better
    first, second = hazards
    first_mass = prior * first
    second_mass = prior * (1.0 - first) * second
    unresolved = prior * (1.0 - first) * (1.0 - second)
    return (first_mass, second_mass), unresolved
