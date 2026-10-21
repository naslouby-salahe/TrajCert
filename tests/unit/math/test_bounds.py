from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.math.bounds import (
    complete_case_arrival_only,
    sharp_risk_set,
    unresolved_as_harm_upper,
)
from trajcert.math.information import observed_timing_information
from trajcert.types import CompatibilityRegime

_ROOT_ATOL = 1e-10
_IDENTITY_ATOL = 1e-9


def test_sharp_risk_set_empty_below_tau() -> None:
    observed = summary([0.2, 0.0], [0.0, 0.4], 0.4)
    result = sharp_risk_set(observed, 0.0, _ROOT_ATOL, _IDENTITY_ATOL)
    assert result.solve_result.compatibility.regime is CompatibilityRegime.MODEL_INCOMPATIBLE
    assert result.hidden_mass is None
    assert result.latent_risk is None
    assert result.identified_width is None


def test_sharp_risk_set_singleton_at_tau() -> None:
    observed = summary([0.2], [0.4], 0.4)
    tau = observed_timing_information(observed)
    assert tau is not None
    result = sharp_risk_set(observed, tau, _ROOT_ATOL, _IDENTITY_ATOL)
    assert (
        result.solve_result.compatibility.regime
        is CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON
    )
    assert result.hidden_mass is not None
    assert result.hidden_mass.lower == pytest.approx(result.hidden_mass.upper)
    assert result.identified_width == pytest.approx(0.0, abs=1e-9)


def test_sharp_risk_set_interval_above_tau_is_nested_and_matches_bounds() -> None:
    observed = summary([0.2], [0.4], 0.4)
    result = sharp_risk_set(observed, 0.5, _ROOT_ATOL, _IDENTITY_ATOL)
    assert result.solve_result.compatibility.regime is CompatibilityRegime.COMPATIBLE_INTERVAL
    assert result.latent_risk is not None
    harmful = observed.resolved_harmful_mass
    assert result.latent_risk.lower >= harmful
    assert result.latent_risk.upper <= harmful + observed.unresolved_mass
    assert result.identified_width is not None
    assert result.identified_width > 0.0


def test_unresolved_as_harm_upper_matches_worst_case_formula() -> None:
    observed = summary([0.2], [0.4], 0.4)
    assert unresolved_as_harm_upper(observed) == pytest.approx(0.6)


def test_complete_case_arrival_only_matches_resolved_ratio() -> None:
    observed = summary([0.2], [0.4], 0.4)
    assert complete_case_arrival_only(observed) == pytest.approx(1.0 / 3.0)


def test_complete_case_arrival_only_undefined_without_resolved_mass() -> None:
    observed = summary([0.0], [0.0], 1.0)
    assert complete_case_arrival_only(observed) is None
