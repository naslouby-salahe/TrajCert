from __future__ import annotations

# pytest's comparison helpers are intentionally dynamically typed.
# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from pathlib import Path

import numpy as np
import pytest

from trajcert.config import TrajCertConfig
from trajcert.data.partitions import build_partition
from trajcert.data.summaries import ObservableSummary, summarize_observable_masses
from trajcert.exceptions import InvalidProbabilityError, InvalidScientificDataError
from trajcert.math.bounds import SharpRiskSet, sharp_risk_set, unresolved_as_harm_upper
from trajcert.math.compatibility import assess_compatibility
from trajcert.math.entropy import (
    binary_entropy,
    binary_entropy_from_masses,
    weighted_binary_entropy,
    xlogx,
)
from trajcert.math.information import (
    information_profile,
    information_profile_derivative,
    information_profile_second_derivative,
    latent_risk,
    minimum_information_point,
    observed_timing_information,
    profile_difference,
    resolved_timing_entropy,
    timing_gain,
)
from trajcert.math.safety import assess_safety_geometry, safety_budget_cases
from trajcert.math.solver import solve_hidden_mass_interval
from trajcert.types import CompatibilityRegime, RootStatus, SafetyRegime


@pytest.fixture(autouse=True)
def active_test_config() -> None:
    TrajCertConfig.from_yaml(Path("configs/trajcert.yaml"))


def summary(harmful: list[float], correct: list[float], unresolved: float) -> ObservableSummary:
    partition = build_partition(len(harmful), len(harmful), 1.0)
    return summarize_observable_masses(
        partition, np.array(harmful), np.array(correct), unresolved, 1e-12
    )


@pytest.mark.parametrize(
    ("function", "value", "expected"),
    [
        (xlogx, 0.5, 0.5 * np.log(0.5)),
        (binary_entropy, 0.5, np.log(2.0)),
        (binary_entropy_from_masses, (0.25, 0.25), 0.5 * np.log(2.0)),
        (weighted_binary_entropy, (0.5, 0.5), 0.5 * np.log(2.0)),
    ],
)
def test_entropy_primitives(function, value, expected: float) -> None:
    actual = function(*value) if isinstance(value, tuple) else function(value)
    assert actual == pytest.approx(expected)


@pytest.mark.parametrize("mass", [0.0, np.array([0.0, 0.0])])
def test_weighted_entropy_allows_undefined_rate_for_zero_mass(mass) -> None:
    assert np.allclose(weighted_binary_entropy(mass, None), 0.0)


def test_weighted_entropy_requires_rate_for_positive_mass() -> None:
    with pytest.raises(InvalidProbabilityError):
        weighted_binary_entropy(0.1, None)


def test_information_profile_geometry_and_derivatives() -> None:
    observed = summary([0.2, 0.0], [0.0, 0.4], 0.4)
    minimum = minimum_information_point(observed)
    assert minimum is not None
    assert resolved_timing_entropy(observed) == pytest.approx(0.0)
    timing_information = observed_timing_information(observed)
    assert timing_information is not None
    assert timing_information > 0.0
    assert latent_risk(observed, 0.1) == pytest.approx(0.3)
    assert information_profile(observed, minimum.hidden_terminal_harmful_mass) == pytest.approx(
        minimum.information_floor
    )
    assert information_profile_derivative(
        observed, minimum.hidden_terminal_harmful_mass
    ) == pytest.approx(0.0)
    assert (
        information_profile_second_derivative(observed, minimum.hidden_terminal_harmful_mass) > 0.0
    )


@pytest.mark.parametrize("hidden", [-0.1, 0.5])
def test_information_profile_rejects_hidden_mass_outside_unresolved_domain(hidden: float) -> None:
    with pytest.raises(InvalidScientificDataError):
        information_profile(summary([0.2], [0.4], 0.4), hidden)


def test_information_handles_degenerate_and_coarsened_summaries() -> None:
    no_resolved = summary([0.0], [0.0], 1.0)
    assert observed_timing_information(no_resolved) is None
    assert minimum_information_point(no_resolved) is None
    fine = summary([0.1, 0.1], [0.2, 0.2], 0.4)
    coarse = summary([0.2], [0.4], 0.4)
    assert timing_gain(fine, coarse, 1e-12) >= 0.0
    assert profile_difference(fine, coarse, 0.1, 1e-12) >= 0.0


@pytest.mark.parametrize(
    ("observed", "rho", "regime"),
    [
        (summary([0.0], [0.0], 1.0), 0.0, CompatibilityRegime.NO_RESOLVED_MASS),
        (summary([0.2], [0.8], 0.0), 0.0, CompatibilityRegime.NO_UNRESOLVED_MASS),
        (summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.0, CompatibilityRegime.MODEL_INCOMPATIBLE),
        (
            summary([0.2, 0.0], [0.0, 0.4], 0.4),
            None,
            CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON,
        ),
        (summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.6, CompatibilityRegime.COMPATIBLE_INTERVAL),
    ],
)
def test_compatibility_regimes(
    observed: ObservableSummary, rho: float | None, regime: CompatibilityRegime
) -> None:
    if rho is None:
        rho = observed_timing_information(observed)
        assert rho is not None
    assert assess_compatibility(observed, rho).regime is regime


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
        assert result.lower_root is not None and result.upper_root is not None
        assert result.lower_root.status in (RootStatus.BISECTION, RootStatus.EXACT_BOUNDARY)


@pytest.mark.parametrize(
    ("budget", "expected"),
    [
        (0.1, SafetyRegime.RESOLVED_HARM_EXCEEDS_BUDGET),
        (0.25, SafetyRegime.INTRINSICALLY_UNCERTIFIABLE),
        (0.4, SafetyRegime.INTERIOR_SAFETY_FRONTIER),
        (0.7, SafetyRegime.ASSUMPTION_FREE_SAFE),
    ],
)
def test_safety_geometry_regimes(budget: float, expected: SafetyRegime) -> None:
    assessment = assess_safety_geometry(summary([0.2], [0.4], 0.4), budget)
    assert assessment.regime is expected
    assert (assessment.safety_frontier is not None) is (
        expected is SafetyRegime.INTERIOR_SAFETY_FRONTIER
    )


def test_safety_degenerate_case_and_bounds() -> None:
    observed = summary([0.0], [0.0], 1.0)
    assert assess_safety_geometry(observed, 0.5).regime is SafetyRegime.NO_RESOLVED_MASS
    cases = safety_budget_cases(observed)
    assert [case.valid for case in cases] == [True, False, False, False, True]
    assert unresolved_as_harm_upper(summary([0.2], [0.4], 0.4)) == pytest.approx(0.6)
    sharp = sharp_risk_set(summary([0.2], [0.4], 0.4), 0.0, 1e-8, 1e-7)
    assert isinstance(sharp, SharpRiskSet)
    assert sharp.identified_width == pytest.approx(0.0)
