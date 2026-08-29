from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.config import GridsConfig, TrajCertConfig, active_config
from trajcert.constants import BINARY_MAX_INFORMATION_NATS, PRODUCTION_CONFIG_PATH
from trajcert.data.summaries import ObservableSummary
from trajcert.experiments.comparator_reduction import (
    ComparatorReductionResult,
    evaluate_comparator_reduction,
)

_ORACLE_DIGITS = 20
_FINEST_BAND_COUNT = 8
_UNIFORM_BAND_MASS = 0.0625
_EXPECTED_LEGACY_GAMMA_COUNT = 6
_GENERIC_GRID_POINT_COUNT = 3
_MIXED_HARMFUL = (0.2, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05)


def _production_config() -> TrajCertConfig:
    return TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)


def _reduced_config(config: TrajCertConfig, rho: tuple[float, ...]) -> TrajCertConfig:
    numerics = config.numerics.model_copy(update={"oracle_digits": _ORACLE_DIGITS})
    grids = GridsConfig(
        partitions=config.grids.partitions,
        scaling_bands=config.grids.scaling_bands,
        rho=rho,
        same_endpoint_rho=config.grids.same_endpoint_rho,
        beta=config.grids.beta,
    )
    return config.model_copy(update={"numerics": numerics, "grids": grids})


def _uniform_summary() -> ObservableSummary:
    return summary(
        [_UNIFORM_BAND_MASS] * _FINEST_BAND_COUNT,
        [_UNIFORM_BAND_MASS] * _FINEST_BAND_COUNT,
        0.0,
    )


def _mixed_summary() -> ObservableSummary:
    return summary(list(_MIXED_HARMFUL), [0.05] * _FINEST_BAND_COUNT, 0.0)


def _evaluate(rho: tuple[float, ...]) -> ComparatorReductionResult:
    _ = active_config.set(_reduced_config(_production_config(), rho))
    return evaluate_comparator_reduction(_uniform_summary())


def test_comparator_reduction_requires_configured_finest_partition() -> None:
    coarse = summary([0.125] * 4, [0.125] * 4, 0.0)
    _ = active_config.set(_reduced_config(_production_config(), (0.0, 0.1)))
    with pytest.raises(ValueError, match="finest partition"):
        _ = evaluate_comparator_reduction(coarse)


def test_comparator_reduction_appends_binary_maximum_information() -> None:
    result = _evaluate((0.0, 0.1))
    rhos = tuple(float(point.rho) for point in result.generic_information)
    assert len(rhos) == _GENERIC_GRID_POINT_COUNT
    assert rhos[:2] == (0.0, 0.1)
    assert rhos[2] == pytest.approx(BINARY_MAX_INFORMATION_NATS)


def test_comparator_reduction_keeps_grid_when_log_two_already_present() -> None:
    result = _evaluate((0.0, 0.1, BINARY_MAX_INFORMATION_NATS))
    rhos = tuple(float(point.rho) for point in result.generic_information)
    assert len(rhos) == _GENERIC_GRID_POINT_COUNT
    assert rhos == (0.0, 0.1, BINARY_MAX_INFORMATION_NATS)


def test_comparator_reduction_uniform_summary_accepts_all_reductions() -> None:
    result = _evaluate((0.0, 0.1))
    assert result.alho_common_slope.status == "APPLICABLE"
    assert result.alho_common_slope.accepted_hidden_roots == (0.0,)
    assert result.alho_common_slope.informative_bands == _FINEST_BAND_COUNT
    assert result.stable_resistance.status == "APPLICABLE"
    assert result.stable_resistance.accepted_hidden_roots == (0.0,)
    assert result.pattern_mixture.status == "APPLICABLE"
    assert all(item.applicability == "APPLICABLE" for item in result.legacy)


def test_comparator_reduction_mixed_summary_reports_incompatibility() -> None:
    _ = active_config.set(_reduced_config(_production_config(), (0.0, 0.1)))
    result = evaluate_comparator_reduction(_mixed_summary())
    assert result.alho_common_slope.status == "MODEL_INCOMPATIBLE"
    assert result.alho_common_slope.accepted_hidden_roots == ()
    assert result.stable_resistance.status == "MODEL_INCOMPATIBLE"
    assert result.legacy[0].applicability == "MODEL_INCOMPATIBLE"
    assert result.legacy[-1].applicability == "APPLICABLE"
    assert result.legacy[0].informative_bands == 1


def test_comparator_reduction_legacy_gamma_count_matches_config() -> None:
    config = _production_config()
    result = _evaluate((0.0, 0.1))
    assert len(result.legacy) == _EXPECTED_LEGACY_GAMMA_COUNT
    assert tuple(item.gamma for item in result.legacy) == tuple(config.comparators.legacy_gamma)


def test_comparator_reduction_generic_points_carry_budgets() -> None:
    result = _evaluate((0.0, 0.1))
    assert tuple(float(point.rho) for point in result.generic_information) == (
        0.0,
        0.1,
        BINARY_MAX_INFORMATION_NATS,
    )
    assert result.generic_information[0].oracle.regime == "MINIMUM_INFORMATION_SINGLETON"
    assert result.generic_information[1].oracle.regime == "NO_UNRESOLVED_MASS"
    assert result.generic_information[2].oracle.regime == "NO_UNRESOLVED_MASS"
    assert result.generic_information[0].oracle.minimum_information == 0.0
