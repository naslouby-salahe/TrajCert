from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.data.partitions import build_partition
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.mathematics import (
    ConvexityResult,
    EndpointDifferenceDirection,
    IdentityResult,
    LegacyPartitionIncoherenceResult,
    RefinementIdentityResult,
    SafetyBoundaryCaseEvaluation,
    SafetyBoundaryIdentityResult,
    SharpSetIdentityResult,
    anytime_projection_proof_check,
    endpoint_special_case_identity,
    evaluate_legacy_partition_incoherence,
    evaluate_safety_boundary_case,
    information_profile_convexity,
    minimum_compatibility_identity,
    path_information_decomposition,
    population_complexity_proof_check,
    refinement_dominance_identity,
    safety_boundary_identity,
    sharp_set_constructive_identity,
    strict_timing_gain_identity,
)
from trajcert.math.information import observed_timing_information
from trajcert.math.safety import safety_budget_cases

_ORACLE_DIGITS = 50
_ORACLE_BRACKET_WIDTH = 1e-14
_IDENTITY_ATOL = 1e-6
_SHARP_IDENTITY_ATOL = 1e-8
_ROOT_ATOL = 1e-12
_COMPARISON_GUARD = 1e-12
_SENSITIVITY_OFFSET = 0.05
_SENSITIVITY_BUDGET = 0.1
_NEAR_ZERO = 1e-12


def test_path_information_decomposition_matches_direct_information() -> None:
    result = path_information_decomposition(
        summary([0.2, 0.3], [0.3, 0.1], 0.1), _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert isinstance(result, IdentityResult)
    assert result.passed
    assert result.max_absolute_error == pytest.approx(0.0, abs=_NEAR_ZERO)


def test_path_information_decomposition_without_resolved_mass() -> None:
    result = path_information_decomposition(
        summary([0.0], [0.0], 1.0), _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert result.passed
    assert result.max_absolute_error == 0.0


def test_minimum_compatibility_identity_matches_analytic_formulas() -> None:
    result = minimum_compatibility_identity(summary([0.2, 0.3], [0.3, 0.1], 0.1), _IDENTITY_ATOL)
    assert isinstance(result, IdentityResult)
    assert result.passed
    assert result.max_absolute_error == pytest.approx(0.0, abs=_NEAR_ZERO)


def test_minimum_compatibility_identity_without_resolved_mass() -> None:
    result = minimum_compatibility_identity(summary([0.0], [0.0], 1.0), _IDENTITY_ATOL)
    assert result.passed
    assert result.max_absolute_error == 0.0


def test_information_profile_convexity_interior() -> None:
    result = information_profile_convexity(
        summary([0.2, 0.3], [0.3, 0.1], 0.1), _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert isinstance(result, ConvexityResult)
    assert result.passed
    assert result.minimum_second_derivative is not None
    assert result.minimum_second_derivative > 0.0
    assert result.max_direct_second_derivative_error == pytest.approx(0.0, abs=_NEAR_ZERO)


def test_information_profile_convexity_without_unresolved_mass() -> None:
    result = information_profile_convexity(
        summary([0.2], [0.8], 0.0), _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert result.passed
    assert result.minimum_second_derivative is None
    assert result.max_direct_second_derivative_error == 0.0


def test_sharp_set_constructive_identity_matches_oracle() -> None:
    result = sharp_set_constructive_identity(
        summary([0.2, 0.3], [0.3, 0.1], 0.1),
        0.1,
        _ROOT_ATOL,
        _SHARP_IDENTITY_ATOL,
        _ORACLE_DIGITS,
        _ORACLE_BRACKET_WIDTH,
    )
    assert isinstance(result, SharpSetIdentityResult)
    assert result.passed
    assert result.production_lower is not None
    assert result.production_upper is not None
    assert result.oracle_lower is not None
    assert result.oracle_upper is not None
    assert result.max_endpoint_error is not None
    assert result.max_endpoint_error <= _SHARP_IDENTITY_ATOL
    assert result.diagnostic_grid_mismatches == 0
    assert result.production_lower <= result.production_upper


def test_sharp_set_constructive_identity_model_incompatible() -> None:
    result = sharp_set_constructive_identity(
        summary([0.2, 0.0], [0.0, 0.4], 0.4),
        0.0,
        _ROOT_ATOL,
        _SHARP_IDENTITY_ATOL,
        _ORACLE_DIGITS,
        _ORACLE_BRACKET_WIDTH,
    )
    assert result.passed
    assert result.production_lower is None
    assert result.production_upper is None
    assert result.oracle_lower is None
    assert result.oracle_upper is None
    assert result.max_endpoint_error is None
    assert result.diagnostic_grid_mismatches == 0


def test_refinement_dominance_identity_preserves_profile_difference() -> None:
    fine = summary([0.1, 0.15, 0.15, 0.1], [0.1, 0.1, 0.1, 0.1], 0.1)
    coarse_partition = build_partition(4, 2, 1.0)
    result = refinement_dominance_identity(
        fine, coarse_partition, _IDENTITY_ATOL, _COMPARISON_GUARD
    )
    assert isinstance(result, RefinementIdentityResult)
    assert result.passed
    assert result.timing_gain > 0.0
    assert result.max_profile_order_violation <= _IDENTITY_ATOL
    assert result.max_profile_difference_error == pytest.approx(0.0, abs=_NEAR_ZERO)


def test_refinement_dominance_identity_zero_timing_gain() -> None:
    fine = summary([0.1, 0.1, 0.1, 0.1], [0.1, 0.1, 0.1, 0.1], 0.2)
    coarse_partition = build_partition(4, 2, 1.0)
    result = refinement_dominance_identity(
        fine, coarse_partition, _IDENTITY_ATOL, _COMPARISON_GUARD
    )
    assert result.passed
    assert result.timing_gain == pytest.approx(0.0, abs=_NEAR_ZERO)
    assert result.max_profile_order_violation == pytest.approx(0.0, abs=_NEAR_ZERO)


def test_strict_timing_gain_identity_strict_containment() -> None:
    fine = summary([0.05, 0.1, 0.15, 0.2], [0.1, 0.1, 0.1, 0.1], 0.1)
    coarse_partition = build_partition(4, 2, 1.0)
    tau = observed_timing_information(fine)
    assert tau is not None
    budget = float(tau) + _SENSITIVITY_OFFSET
    result = strict_timing_gain_identity(
        fine, coarse_partition, budget, _ROOT_ATOL, _SHARP_IDENTITY_ATOL, _COMPARISON_GUARD
    )
    assert isinstance(result, IdentityResult)
    assert result.passed
    assert result.max_absolute_error <= _SHARP_IDENTITY_ATOL


def test_strict_timing_gain_identity_missing_strict_tightening() -> None:
    fine = summary([0.1, 0.15, 0.15, 0.1], [0.1, 0.1, 0.1, 0.1], 0.1)
    coarse_partition = build_partition(4, 2, 1.0)
    result = strict_timing_gain_identity(
        fine,
        coarse_partition,
        _SENSITIVITY_BUDGET,
        _ROOT_ATOL,
        _SHARP_IDENTITY_ATOL,
        _COMPARISON_GUARD,
    )
    assert not result.passed
    assert result.max_absolute_error == pytest.approx(0.0, abs=_NEAR_ZERO)


def test_strict_timing_gain_identity_model_incompatible() -> None:
    fine = summary([0.2, 0.0], [0.0, 0.4], 0.4)
    coarse_partition = build_partition(2, 1, 1.0)
    result = strict_timing_gain_identity(
        fine, coarse_partition, 0.0, _ROOT_ATOL, _SHARP_IDENTITY_ATOL, _COMPARISON_GUARD
    )
    assert not result.passed
    assert result.max_absolute_error == 1.0


def test_safety_boundary_identity_interior_frontier() -> None:
    result = safety_boundary_identity(
        summary([0.2], [0.4], 0.4), 0.4, _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert isinstance(result, SafetyBoundaryIdentityResult)
    assert result.passed
    assert result.assessment.safety_frontier is not None
    assert result.frontier_direct_information is not None
    assert result.frontier_error is not None
    assert result.frontier_error == pytest.approx(0.0, abs=_NEAR_ZERO)


def test_safety_boundary_identity_without_frontier() -> None:
    no_resolved = safety_boundary_identity(
        summary([0.0], [0.0], 1.0), 0.5, _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert no_resolved.passed
    assert no_resolved.frontier_direct_information is None
    assert no_resolved.frontier_error is None
    excess = safety_boundary_identity(
        summary([0.2], [0.4], 0.4), 0.1, _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert excess.passed
    assert excess.frontier_direct_information is None
    assert excess.frontier_error is None


def test_evaluate_safety_boundary_case_invalid_case() -> None:
    cases = safety_budget_cases(summary([0.0], [0.0], 1.0), 0.005)
    invalid = next(case for case in cases if not case.valid)
    result = evaluate_safety_boundary_case(
        summary([0.2], [0.4], 0.4), invalid, _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert isinstance(result, SafetyBoundaryCaseEvaluation)
    assert result.identity is None
    assert result.passed


def test_evaluate_safety_boundary_case_valid_case() -> None:
    cases = safety_budget_cases(summary([0.2], [0.4], 0.4), 0.005)
    valid = next(case for case in cases if case.valid and case.risk_budget is not None)
    result = evaluate_safety_boundary_case(
        summary([0.2], [0.4], 0.4), valid, _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert result.identity is not None
    assert result.passed == result.identity.passed


def test_endpoint_special_case_identity_single_band() -> None:
    resolved = endpoint_special_case_identity(summary([0.2], [0.4], 0.4), _IDENTITY_ATOL)
    assert resolved.passed
    unresolved_only = endpoint_special_case_identity(summary([0.0], [0.0], 1.0), _IDENTITY_ATOL)
    assert unresolved_only.passed
    assert unresolved_only.max_absolute_error == 0.0


def test_endpoint_special_case_identity_rejects_multi_band() -> None:
    result = endpoint_special_case_identity(summary([0.2, 0.1], [0.3, 0.2], 0.2), _IDENTITY_ATOL)
    assert not result.passed
    assert result.max_absolute_error == 1.0


def test_proof_check_helpers_always_pass() -> None:
    anytime = anytime_projection_proof_check()
    population = population_complexity_proof_check()
    assert anytime.passed
    assert anytime.max_absolute_error == 0.0
    assert population.passed
    assert population.max_absolute_error == 0.0


def test_legacy_partition_incoherence_rejects_gamma_below_one() -> None:
    with pytest.raises(InvalidScientificDataError, match="at least one"):
        _ = evaluate_legacy_partition_incoherence(0.5, 0.1)


def test_legacy_partition_incoherence_rejects_outside_unit_q() -> None:
    with pytest.raises(InvalidScientificDataError, match="strictly inside"):
        _ = evaluate_legacy_partition_incoherence(2.0, 0.0)
    with pytest.raises(InvalidScientificDataError, match="strictly inside"):
        _ = evaluate_legacy_partition_incoherence(2.0, 1.0)


def test_legacy_partition_incoherence_measures_endpoint_widening() -> None:
    result = evaluate_legacy_partition_incoherence(2.0, 0.1)
    assert isinstance(result, LegacyPartitionIncoherenceResult)
    assert result.passed
    assert result.endpoint_difference_direction in (
        EndpointDifferenceDirection.WIDER,
        EndpointDifferenceDirection.NARROWER,
        EndpointDifferenceDirection.SHIFTED,
    )
    fine_interval = result.fine_hidden_mass_interval
    assert fine_interval.lower <= result.true_hidden_terminal_harmful <= fine_interval.upper
    assert result.fine_risk_interval.lower <= result.fine_risk_interval.upper
    assert result.endpoint_risk_interval.lower <= result.endpoint_risk_interval.upper
    assert result.endpoint_difference_magnitude > 0.0
