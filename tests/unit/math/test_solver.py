from __future__ import annotations

import random

import pytest

from tests.unit.conftest import summary
from trajcert.data.summaries import ObservableSummary
from trajcert.math import solver
from trajcert.math.information import (
    information_profile_residual,
    information_profile_with_resolved_entropy,
    resolved_timing_entropy,
)
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


def _random_summary(rng: random.Random) -> ObservableSummary:
    bands = rng.choice((1, 2, 4, 8))
    weights = [rng.random() for _ in range(2 * bands + 1)]
    scale = sum(weights)
    masses = [weight / scale for weight in weights]
    harmful, correct = masses[:bands], masses[bands : 2 * bands]
    unresolved = 1.0 - sum(harmful) - sum(correct)
    return summary(harmful, correct, max(0.0, unresolved))


def _oracle_root(
    observed: ObservableSummary,
    rho: float,
    entropy: float,
    bounds: tuple[float, float],
    descending: bool,
) -> tuple[float, float]:
    lower, upper = bounds
    while upper - lower > _ORACLE_ATOL:
        midpoint = (lower + upper) / 2.0
        residual = information_profile_with_resolved_entropy(observed, midpoint, entropy) - rho
        if residual == 0.0:
            return midpoint, midpoint
        if (residual > 0.0) is descending:
            lower = midpoint
        else:
            upper = midpoint
    return lower, upper


_ORACLE_ATOL = 1e-12
_ORACLE_CASES = 60


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_solver_roots_match_plain_bisection_bitwise(seed: int) -> None:
    rng = random.Random(seed)
    checked = 0
    while checked < _ORACLE_CASES:
        observed = _random_summary(rng)
        rho = rng.uniform(0.0, 0.3)
        result = solve_hidden_mass_interval(observed, rho, _ORACLE_ATOL, 1e-7)
        lower_root, upper_root = result.lower_root, result.upper_root
        if lower_root is None or upper_root is None:
            continue
        minimum = result.compatibility.minimum_information_point
        assert minimum is not None
        entropy = resolved_timing_entropy(observed)
        u_dagger = minimum.hidden_terminal_harmful_mass
        if lower_root.status is RootStatus.BISECTION:
            expected = _oracle_root(observed, rho, entropy, (0.0, u_dagger), descending=True)
            assert (lower_root.lower.hex(), lower_root.upper.hex()) == tuple(
                value.hex() for value in expected
            )
        if upper_root.status is RootStatus.BISECTION:
            bounds = (u_dagger, observed.unresolved_mass)
            expected = _oracle_root(observed, rho, entropy, bounds, descending=False)
            assert (upper_root.lower.hex(), upper_root.upper.hex()) == tuple(
                value.hex() for value in expected
            )
        checked += 1


@pytest.mark.parametrize("seed", [5, 6])
def test_information_profile_residual_matches_profile_minus_budget(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(400):
        observed = _random_summary(rng)
        entropy = resolved_timing_entropy(observed)
        hidden = rng.uniform(0.0, observed.unresolved_mass)
        rho = rng.uniform(0.0, 1.0)
        expected = information_profile_with_resolved_entropy(observed, hidden, entropy) - rho
        observed_value = information_profile_residual(observed, hidden, entropy, rho)
        assert observed_value.hex() == expected.hex()
