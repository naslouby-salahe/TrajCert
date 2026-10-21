from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.data.summaries import ObservableSummary
from trajcert.experiments.solver_validation import (
    SolverOracleComparison,
    compare_production_solver_to_oracle,
    compare_safety_frontier_to_oracle,
)
from trajcert.math.information import observed_timing_information
from trajcert.types import CompatibilityRegime

_ORACLE_DIGITS = 20
_ORACLE_BRACKET_WIDTH = 1e-14
_ROOT_ATOL = 1e-8
_IDENTITY_ATOL = 1e-8
_COMPARISON_GUARD = 1e-12
_TAU = 0.01834500701737518
_THETA_DAGGER = 0.6666666666666666
_RISK_LOWER_AT_0_05 = 0.62550843556722
_RISK_UPPER_AT_0_05 = 0.6985523780186971
_LOWER_ERROR_AT_0_05 = 7.633403874274247e-10
_UPPER_ERROR_AT_0_05 = 1.4440910967028486e-09
_ENDPOINT_ERROR_AT_TAU = 6.1267518836061186e-12
_RESIDUAL_AT_0_07 = 0.01365344239306282


def _benchmark_summary() -> ObservableSummary:
    return summary([0.2, 0.3, 0.1], [0.1, 0.1, 0.1], 0.1)


def _compare(
    benchmark: ObservableSummary, sensitivity_budget: float, oracle_digits: int = _ORACLE_DIGITS
) -> SolverOracleComparison:
    return compare_production_solver_to_oracle(
        benchmark,
        sensitivity_budget,
        _ROOT_ATOL,
        _IDENTITY_ATOL,
        oracle_digits,
        _ORACLE_BRACKET_WIDTH,
        _COMPARISON_GUARD,
    )


def test_compare_solver_above_tau_reports_compatible_interval() -> None:
    comparison = _compare(_benchmark_summary(), 0.05)
    assert comparison.sensitivity_budget == pytest.approx(0.05)
    assert comparison.compatibility_regime == CompatibilityRegime.COMPATIBLE_INTERVAL
    assert comparison.oracle_regime == CompatibilityRegime.COMPATIBLE_INTERVAL
    assert comparison.state_match
    assert comparison.passed
    assert comparison.tau == pytest.approx(_TAU)
    assert comparison.theta_dagger == pytest.approx(_THETA_DAGGER)
    assert comparison.risk_lower == pytest.approx(_RISK_LOWER_AT_0_05)
    assert comparison.risk_upper == pytest.approx(_RISK_UPPER_AT_0_05)


def test_compare_solver_above_tau_endpoint_errors_within_tolerance() -> None:
    comparison = _compare(_benchmark_summary(), 0.05)
    assert comparison.abs_u_lower_error == pytest.approx(_LOWER_ERROR_AT_0_05)
    assert comparison.abs_u_upper_error == pytest.approx(_UPPER_ERROR_AT_0_05)
    assert comparison.max_endpoint_error == pytest.approx(_UPPER_ERROR_AT_0_05)
    assert comparison.abs_u_lower_error is not None
    assert comparison.abs_u_lower_error <= _IDENTITY_ATOL
    assert comparison.abs_u_upper_error is not None
    assert comparison.abs_u_upper_error <= _IDENTITY_ATOL
    assert comparison.max_root_bracket_width is not None
    assert comparison.max_root_bracket_width <= _ROOT_ATOL
    assert comparison.max_root_residual is not None
    assert comparison.max_root_residual <= _IDENTITY_ATOL


def test_compare_solver_below_tau_reports_model_incompatible() -> None:
    comparison = _compare(_benchmark_summary(), 0.01)
    assert comparison.compatibility_regime == CompatibilityRegime.MODEL_INCOMPATIBLE
    assert comparison.oracle_regime == CompatibilityRegime.MODEL_INCOMPATIBLE
    assert comparison.state_match
    assert comparison.passed
    assert comparison.risk_lower is None
    assert comparison.risk_upper is None
    assert comparison.abs_u_lower_error is None
    assert comparison.max_endpoint_error is None
    assert comparison.max_root_residual is None
    assert comparison.theta_dagger == pytest.approx(_THETA_DAGGER)


def test_compare_solver_at_tau_reports_singleton() -> None:
    comparison = _compare(_benchmark_summary(), _TAU)
    assert comparison.compatibility_regime == CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON
    assert comparison.oracle_regime == CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON
    assert comparison.passed
    assert comparison.risk_lower == pytest.approx(_THETA_DAGGER)
    assert comparison.risk_upper == pytest.approx(_THETA_DAGGER)
    assert comparison.max_endpoint_error == pytest.approx(_ENDPOINT_ERROR_AT_TAU)


def test_compare_solver_high_rho_exact_boundary_roots_pass() -> None:
    comparison = _compare(_benchmark_summary(), 0.07)
    assert comparison.compatibility_regime == CompatibilityRegime.COMPATIBLE_INTERVAL
    assert comparison.oracle_regime == CompatibilityRegime.COMPATIBLE_INTERVAL
    assert comparison.state_match
    assert comparison.passed
    assert comparison.max_endpoint_error is not None
    assert comparison.max_endpoint_error <= _IDENTITY_ATOL
    assert comparison.max_root_residual == pytest.approx(_RESIDUAL_AT_0_07)


def test_compare_solver_tau_derived_from_summary() -> None:
    benchmark = _benchmark_summary()
    comparison = _compare(benchmark, 0.05)
    expected_tau = float(observed_timing_information(benchmark) or 0.0)
    assert comparison.tau == pytest.approx(expected_tau)


def test_compare_safety_frontier_interior_agrees_with_oracle() -> None:
    frontier = compare_safety_frontier_to_oracle(
        _benchmark_summary(), 0.67, _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert frontier.applicable
    assert frontier.production_rho_star == pytest.approx(0.01857446105876006)
    assert frontier.oracle_rho_star == pytest.approx(0.018574461058760046)
    assert frontier.absolute_error is not None
    assert frontier.absolute_error <= _IDENTITY_ATOL
    assert frontier.passed


def test_compare_safety_frontier_inapplicable_passes_without_oracle() -> None:
    frontier = compare_safety_frontier_to_oracle(
        _benchmark_summary(), 0.55, _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert not frontier.applicable
    assert frontier.production_rho_star is None
    assert frontier.oracle_rho_star is None
    assert frontier.absolute_error is None
    assert frontier.passed
