from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.experiments.sensitivity import (
    PopulationUtilityResult,
    population_sensitivity_utility,
)
from trajcert.types import CompatibilityRegime

_SENSITIVITY_BUDGET = 0.1
_NEAR_ZERO = 1e-9


def test_population_utility_model_incompatible() -> None:
    result = population_sensitivity_utility(summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.0)
    assert isinstance(result, PopulationUtilityResult)
    assert result.compatibility_regime is CompatibilityRegime.MODEL_INCOMPATIBLE
    assert result.tau is not None
    assert result.risk_lower is None
    assert result.risk_upper is None
    assert result.identified_width is None
    assert result.absolute_tightening is None
    assert result.relative_unresolved_gain is None
    assert not result.materially_nonvacuous
    assert result.unresolved_as_harm_upper == pytest.approx(0.6, abs=_NEAR_ZERO)


def test_population_utility_minimum_information_singleton() -> None:
    result = population_sensitivity_utility(summary([0.2], [0.4], 0.4), 0.0)
    assert result.compatibility_regime is CompatibilityRegime.MINIMUM_INFORMATION_SINGLETON
    assert result.risk_lower is not None
    assert result.risk_upper is not None
    assert result.risk_lower == pytest.approx(1 / 3, abs=_NEAR_ZERO)
    assert result.risk_upper == pytest.approx(1 / 3, abs=_NEAR_ZERO)
    assert result.identified_width is not None
    assert result.identified_width == pytest.approx(0.0, abs=_NEAR_ZERO)
    assert result.absolute_tightening is not None
    assert result.absolute_tightening == pytest.approx(0.6 - 1 / 3, abs=_NEAR_ZERO)
    assert result.relative_unresolved_gain is not None
    assert result.relative_unresolved_gain == pytest.approx((0.6 - 1 / 3) / 0.4, abs=_NEAR_ZERO)
    assert result.materially_nonvacuous


def test_population_utility_compatible_interval() -> None:
    result = population_sensitivity_utility(summary([0.2], [0.4], 0.4), _SENSITIVITY_BUDGET)
    assert result.compatibility_regime is CompatibilityRegime.COMPATIBLE_INTERVAL
    assert result.risk_lower is not None
    assert result.risk_upper is not None
    assert result.risk_lower <= result.risk_upper
    assert result.identified_width is not None
    assert result.identified_width > 0.0
    assert result.absolute_tightening is not None
    assert result.absolute_tightening > 0.0
    assert result.relative_unresolved_gain is not None
    assert result.relative_unresolved_gain > 0.0
    assert result.materially_nonvacuous


def test_population_utility_without_unresolved_mass_has_no_relative_gain() -> None:
    result = population_sensitivity_utility(summary([0.2], [0.8], 0.0), 0.0)
    assert result.compatibility_regime is CompatibilityRegime.NO_UNRESOLVED_MASS
    assert result.relative_unresolved_gain is None
    assert result.absolute_tightening is not None
    assert result.absolute_tightening == pytest.approx(0.0, abs=_NEAR_ZERO)
    assert not result.materially_nonvacuous
