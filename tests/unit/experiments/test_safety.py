from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.data.summaries import ObservableSummary
from trajcert.experiments.safety import (
    CompatibilitySweepStatus,
    compatibility_floor_behavior,
    safety_and_intrinsic_impossibility,
    sharpness_against_generic_oracle,
)
from trajcert.experiments.solver_validation import compare_safety_frontier_to_oracle
from trajcert.math.information import observed_timing_information
from trajcert.types import CompatibilityRegime, SafetyRegime

_ORACLE_DIGITS = 20
_ORACLE_BRACKET_WIDTH = 1e-14
_RESOLVED_HARM_BOUNDARY_OFFSET = 0.005
_ROOT_ATOL = 1e-8
_IDENTITY_ATOL = 1e-8
_COMPATIBILITY_OFFSET = 0.005
_SHARPNESS_OFFSET = 0.05
_EXPECTED_TAU = 0.01834500701737518
_FRONTIER_AT_BOUNDARY = 0.018345007017375153
_INTERIOR_FRONTIER_PRODUCTION = 0.02475744123686413
_INTERIOR_FRONTIER_ORACLE = 0.024757441236864186
_FRONTIER_AT_0_67_PRODUCTION = 0.01857446105876006
_FRONTIER_AT_0_67_ORACLE = 0.018574461058760046
_EXPECTED_CASE_COUNT = 5
_COMPATIBILITY_SWEEP_POINT_COUNT = 3
_SHARPNESS_RESIDUAL = 0.011998449410437997


def _benchmark_summary() -> ObservableSummary:
    return summary([0.2, 0.3, 0.1], [0.1, 0.1, 0.1], 0.1)


def test_compatibility_floor_marks_below_zero_budget_not_applicable() -> None:
    uniform = summary([0.2, 0.2], [0.2, 0.2], 0.2)
    result = compatibility_floor_behavior(
        uniform, _ROOT_ATOL, _IDENTITY_ATOL, _ORACLE_DIGITS, _ORACLE_BRACKET_WIDTH
    )
    assert result.tau == 0.0
    assert result.passed
    below, at, above = result.points
    assert below.label == "below"
    assert below.rho is None
    assert below.status == CompatibilitySweepStatus.NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET
    assert below.comparison is None
    assert at.status == CompatibilitySweepStatus.APPLICABLE
    assert at.rho == 0.0
    assert above.status == CompatibilitySweepStatus.APPLICABLE
    assert above.rho == pytest.approx(_COMPATIBILITY_OFFSET)


def test_compatibility_floor_below_tau_uses_model_incompatible_solver() -> None:
    result = compatibility_floor_behavior(
        _benchmark_summary(), _ROOT_ATOL, _IDENTITY_ATOL, _ORACLE_DIGITS, _ORACLE_BRACKET_WIDTH
    )
    assert result.tau == pytest.approx(_EXPECTED_TAU)
    below, at, above = result.points
    assert below.rho == pytest.approx(result.tau - _COMPATIBILITY_OFFSET)
    assert below.comparison is not None
    assert below.comparison.passed
    assert below.comparison.compatibility_regime == CompatibilityRegime.MODEL_INCOMPATIBLE
    assert at.comparison is not None
    assert at.comparison.compatibility_regime == CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON
    assert above.comparison is not None
    assert above.comparison.compatibility_regime == CompatibilityRegime.COMPATIBLE_INTERVAL


def test_compatibility_floor_fails_when_above_tau_solver_mismatches() -> None:
    result = compatibility_floor_behavior(
        _benchmark_summary(), _ROOT_ATOL, _IDENTITY_ATOL, _ORACLE_DIGITS, _ORACLE_BRACKET_WIDTH
    )
    assert not result.passed
    assert len(result.points) == _COMPATIBILITY_SWEEP_POINT_COUNT
    assert all(point.status == CompatibilitySweepStatus.APPLICABLE for point in result.points)


def test_safety_frontier_interior_matches_oracle() -> None:
    frontier = compare_safety_frontier_to_oracle(
        _benchmark_summary(), 0.67, _ORACLE_DIGITS, _IDENTITY_ATOL
    )
    assert frontier.applicable
    assert frontier.production_rho_star == pytest.approx(_FRONTIER_AT_0_67_PRODUCTION)
    assert frontier.oracle_rho_star == pytest.approx(_FRONTIER_AT_0_67_ORACLE)
    assert frontier.absolute_error is not None
    assert frontier.absolute_error <= _IDENTITY_ATOL
    assert frontier.passed


def test_safety_frontier_not_applicable_outside_interior_regime() -> None:
    for risk_budget in (0.55, 0.75):
        frontier = compare_safety_frontier_to_oracle(
            _benchmark_summary(), risk_budget, _ORACLE_DIGITS, _IDENTITY_ATOL
        )
        assert not frontier.applicable
        assert frontier.production_rho_star is None
        assert frontier.oracle_rho_star is None
        assert frontier.absolute_error is None
        assert frontier.passed


def test_sharpness_against_generic_oracle_uses_tau_offset_budget() -> None:
    comparison = sharpness_against_generic_oracle(
        _benchmark_summary(), _ROOT_ATOL, _IDENTITY_ATOL, _ORACLE_DIGITS, _ORACLE_BRACKET_WIDTH
    )
    benchmark = _benchmark_summary()
    expected_budget = float(observed_timing_information(benchmark) or 0.0) + _SHARPNESS_OFFSET
    assert float(comparison.sensitivity_budget) == pytest.approx(expected_budget)
    assert comparison.compatibility_regime == CompatibilityRegime.COMPATIBLE_INTERVAL
    assert comparison.oracle_regime == CompatibilityRegime.COMPATIBLE_INTERVAL
    assert comparison.state_match


def test_sharpness_against_generic_oracle_passes_with_exact_boundary_roots() -> None:
    comparison = sharpness_against_generic_oracle(
        _benchmark_summary(), _ROOT_ATOL, _IDENTITY_ATOL, _ORACLE_DIGITS, _ORACLE_BRACKET_WIDTH
    )
    assert comparison.passed
    assert comparison.max_root_residual == pytest.approx(_SHARPNESS_RESIDUAL)


def test_safety_intrinsic_impossibility_covers_all_regimes() -> None:
    result = safety_and_intrinsic_impossibility(
        _benchmark_summary(), _ORACLE_DIGITS, _IDENTITY_ATOL, _RESOLVED_HARM_BOUNDARY_OFFSET
    )
    assert result.passed
    assert len(result.cases) == _EXPECTED_CASE_COUNT
    regimes = tuple(item.assessment.regime for item in result.cases if item.assessment is not None)
    assert regimes == (
        SafetyRegime.RESOLVED_HARM_EXCEEDS_BUDGET,
        SafetyRegime.INTRINSICALLY_UNCERTIFIABLE,
        SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        SafetyRegime.INTERIOR_SAFETY_FRONTIER,
        SafetyRegime.ASSUMPTION_FREE_SAFE,
    )
    assert tuple(item.expected_regime for item in result.cases) == regimes
    assert all(item.passed for item in result.cases)


def test_safety_intrinsic_frontier_applies_only_to_interior_cases() -> None:
    result = safety_and_intrinsic_impossibility(
        _benchmark_summary(), _ORACLE_DIGITS, _IDENTITY_ATOL, _RESOLVED_HARM_BOUNDARY_OFFSET
    )
    applicable = tuple(
        item.frontier_oracle.applicable for item in result.cases if item.frontier_oracle is not None
    )
    assert applicable == (False, False, True, True, False)
    boundary = next(item for item in result.cases if item.case.name == "At intrinsic boundary")
    interior = next(item for item in result.cases if item.case.name == "Interior safety frontier")
    assert boundary.frontier_oracle is not None
    assert boundary.frontier_oracle.production_rho_star == pytest.approx(_FRONTIER_AT_BOUNDARY)
    assert interior.frontier_oracle is not None
    assert interior.frontier_oracle.production_rho_star == pytest.approx(
        _INTERIOR_FRONTIER_PRODUCTION
    )
    assert interior.frontier_oracle.oracle_rho_star == pytest.approx(_INTERIOR_FRONTIER_ORACLE)
    assert interior.frontier_oracle.passed


def test_safety_intrinsic_reports_tau_for_benchmark_summary() -> None:
    result = safety_and_intrinsic_impossibility(
        _benchmark_summary(), _ORACLE_DIGITS, _IDENTITY_ATOL, _RESOLVED_HARM_BOUNDARY_OFFSET
    )
    assert all(item.tau == pytest.approx(_EXPECTED_TAU) for item in result.cases)
