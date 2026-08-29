from __future__ import annotations

from math import log

import pytest
from pydantic import ValidationError

from tests.unit.conftest import summary
from trajcert.data.partitions import build_partition
from trajcert.exceptions import InvalidScientificDataError
from trajcert.math.oracle import (
    OracleMassInterval,
    ProjectionOracleInput,
    direct_mutual_information,
    feasible_projection_lower_oracle,
    solve_information_oracle,
)
from trajcert.types import CompatibilityRegime


def _interval(lower: float, upper: float) -> OracleMassInterval:
    return OracleMassInterval(lower=lower, upper=upper)


def _oracle_input(correct_upper: float = 0.0) -> ProjectionOracleInput:
    return ProjectionOracleInput(
        partition=build_partition(1, 1, 8.0),
        harmful_by_band=(_interval(0.4, 0.6),),
        correct_by_band=(_interval(0.0, correct_upper),),
        unresolved=_interval(0.4, 0.6),
    )


_GRID_POINTS = 5
_REFINEMENT_CANDIDATES = 2
_REFINEMENT_STEPS = 3
_GRID_POINTS_CHECKED = _GRID_POINTS * _GRID_POINTS
_ORACLE_BRACKET_WIDTH = 1e-14


def test_oracle_mass_interval_rejects_reversed_order() -> None:
    with pytest.raises(ValidationError, match="oracle mass interval is reversed"):
        _ = OracleMassInterval(lower=0.6, upper=0.4)
    lower = 0.4
    upper = 0.6
    interval = OracleMassInterval(lower=lower, upper=upper)
    assert interval.lower == lower
    assert interval.upper == upper


def test_projection_oracle_input_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValidationError, match="partition dimension"):
        _ = ProjectionOracleInput(
            partition=build_partition(1, 1, 8.0),
            harmful_by_band=(_interval(0.4, 0.6), _interval(0.0, 0.1)),
            correct_by_band=(_interval(0.0, 0.0),),
            unresolved=_interval(0.4, 0.6),
        )


def test_projection_oracle_input_rejects_empty_simplex() -> None:
    with pytest.raises(ValidationError, match="empty simplex"):
        _ = ProjectionOracleInput(
            partition=build_partition(1, 1, 8.0),
            harmful_by_band=(_interval(0.9, 1.0),),
            correct_by_band=(_interval(0.0, 0.0),),
            unresolved=_interval(0.4, 0.6),
        )


def test_solve_information_oracle_rejects_nonpositive_digits() -> None:
    observable = summary([0.5], [0.0], 0.5)
    with pytest.raises(InvalidScientificDataError, match="oracle precision"):
        _ = solve_information_oracle(observable, 0.0, 0, _ORACLE_BRACKET_WIDTH)


def test_solve_information_oracle_reports_model_incompatible_regime() -> None:
    observable = summary([0.5], [0.0], 0.5)
    result = solve_information_oracle(observable, 0.0, 50, _ORACLE_BRACKET_WIDTH)
    assert result.regime is CompatibilityRegime.MODEL_INCOMPATIBLE
    assert result.minimum_hidden_mass == pytest.approx(0.5, abs=1e-9)
    assert result.hidden_mass_interval is None
    assert result.latent_risk_interval is None


def test_solve_information_oracle_reports_minimum_information_singleton() -> None:
    observable = summary([0.5], [0.2], 0.3)
    result = solve_information_oracle(observable, 0.0, 50, _ORACLE_BRACKET_WIDTH)
    assert result.regime is CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON
    assert result.minimum_hidden_mass == pytest.approx(3 / 14, abs=1e-9)
    assert result.hidden_mass_interval is not None
    assert result.latent_risk_interval is not None


def test_feasible_projection_lower_oracle_rejects_nonpositive_digits() -> None:
    with pytest.raises(InvalidScientificDataError, match="oracle precision"):
        _ = feasible_projection_lower_oracle(
            _oracle_input(), 0.05, 0, 1e-12, _GRID_POINTS, _REFINEMENT_CANDIDATES, _REFINEMENT_STEPS
        )


def test_feasible_projection_lower_oracle_at_entropy_singularity() -> None:
    result = feasible_projection_lower_oracle(
        _oracle_input(), 0.05, 50, 1e-12, _GRID_POINTS, _REFINEMENT_CANDIDATES, _REFINEMENT_STEPS
    )
    assert result.best_feasible_risk == pytest.approx(1.0)
    assert result.best_resolved_harmful == pytest.approx(0.4)
    assert result.best_resolved_correct == pytest.approx(0.0)
    assert result.best_hidden_terminal_harmful == pytest.approx(0.6)
    assert result.grid_points_per_axis == _GRID_POINTS
    assert result.aggregate_points_checked == _GRID_POINTS_CHECKED
    assert result.feasible_points == _GRID_POINTS_CHECKED
    assert result.locally_refined_candidates == _REFINEMENT_CANDIDATES


def test_feasible_projection_lower_oracle_filters_infeasible_grid_points() -> None:
    result = feasible_projection_lower_oracle(
        _oracle_input(correct_upper=0.2),
        0.05,
        50,
        1e-12,
        _GRID_POINTS,
        _REFINEMENT_CANDIDATES,
        _REFINEMENT_STEPS,
    )
    assert result.best_feasible_risk is not None
    assert 0.0 <= result.best_feasible_risk <= 1.0
    assert result.aggregate_points_checked == _GRID_POINTS_CHECKED
    assert 0 < result.feasible_points < result.aggregate_points_checked
    assert result.locally_refined_candidates == _REFINEMENT_CANDIDATES


def test_direct_mutual_information_values() -> None:
    assert direct_mutual_information((0.5,), (0.0,), 0.5, 0.0, 50) == pytest.approx(log(2.0))
    assert direct_mutual_information((0.5,), (0.0,), 0.5, 0.25, 50) == pytest.approx(
        0.2157615543388357
    )
