from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.data.summaries import ObservableSummary
from trajcert.math import solver
from trajcert.math.solver import solve_hidden_mass_interval
from trajcert.types import CompatibilityRegime, RootBranch, RootStatus


@pytest.mark.parametrize(
    ("observed", "rho", "regime", "interval"),
    [
        (summary([0.0], [0.0], 1.0), 0.0, CompatibilityRegime.NO_RESOLVED_MASS, (0.0, 1.0)),
        (summary([0.2], [0.8], 0.0), 0.0, CompatibilityRegime.NO_UNRESOLVED_MASS, (0.0, 0.0)),
        (summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.0, CompatibilityRegime.MODEL_INCOMPATIBLE, None),
        (summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.6, CompatibilityRegime.COMPATIBLE_INTERVAL, None),
    ],
)
def test_solver_handles_all_non_singleton_branches(
    observed: ObservableSummary,
    rho: float,
    regime: CompatibilityRegime,
    interval: tuple[float, float] | None,
) -> None:
    result = solve_hidden_mass_interval(observed, rho, 1e-8, 1e-7)
    assert result.compatibility.regime is regime
    if interval is not None:
        assert result.interval is not None
        assert (result.interval.lower, result.interval.upper) == pytest.approx(interval)
    elif regime is CompatibilityRegime.MODEL_INCOMPATIBLE:
        assert result.interval is None
    else:
        assert result.interval is not None
        assert result.lower_root is not None
        assert result.upper_root is not None
        assert result.lower_root.status in (RootStatus.BISECTION, RootStatus.EXACT_BOUNDARY)


def test_solver_bisects_interior_roots_and_rejects_invalid_tolerances() -> None:
    observed = summary([0.2, 0.0], [0.0, 0.4], 0.4)
    result = solve_hidden_mass_interval(observed, 0.45, 1e-8, 1e-7)
    assert result.lower_root is not None
    assert result.upper_root is not None
    assert result.lower_root.status is RootStatus.BISECTION
    assert result.upper_root.status is RootStatus.BISECTION
    with pytest.raises(Exception, match="root_atol"):
        _ = solve_hidden_mass_interval(observed, 0.45, 0.0, 1e-7)


_TIGHT_ROOT_ATOL = 1e-10
_LOOSE_IDENTITY_ATOL = 1e-3


def test_solver_bisection_narrows_to_root_atol_not_identity_atol() -> None:
    observed = summary([0.2, 0.0], [0.0, 0.4], 0.4)
    result = solve_hidden_mass_interval(observed, 0.45, _TIGHT_ROOT_ATOL, _LOOSE_IDENTITY_ATOL)
    assert result.lower_root is not None
    assert result.upper_root is not None
    for root in (result.lower_root, result.upper_root):
        assert root.status is RootStatus.BISECTION
        assert root.width <= _TIGHT_ROOT_ATOL


@pytest.mark.parametrize(("width", "tolerance", "expected"), [(0.0, 0.1, 0), (0.1, 0.1, 2)])
def test_solver_boundary_helper_values(width: float, tolerance: float, expected: int) -> None:
    assert solver.compute_iteration_cap(width, tolerance) == expected
    solver.validate_final_signs(RootBranch.LOWER, 0.0, -1.0)
    with pytest.raises(Exception, match="sign-valid"):
        solver.validate_initial_signs(RootBranch.LOWER, 0.0, -1.0)
    with pytest.raises(Exception, match="sign-valid"):
        solver.validate_initial_signs(RootBranch.UPPER, 1.0, 0.0)
