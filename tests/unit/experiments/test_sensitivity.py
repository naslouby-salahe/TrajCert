from __future__ import annotations

import pytest

from tests.unit.conftest import summary
from trajcert.config import (
    MinimumEvidenceConfig,
    SequentialConfig,
    SequentialUtilityConfig,
    TrajCertConfig,
    active_config,
)
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters
from trajcert.data.partitions import build_partition
from trajcert.experiments.sensitivity import (
    PopulationUtilityResult,
    SequentialStreamUtility,
    SequentialUtilityResult,
    population_sensitivity_utility,
    sequential_sensitivity_utility,
)
from trajcert.types import CompatibilityRegime, LawKey

_STREAMS = 1
_MAX_EVENTS = 60
_CHECKPOINT_EVERY = 15
_SENSITIVITY_BUDGET = 0.1
_MIN_MATURED = 20
_MIN_RESOLVED = 5
_NODE_BUDGET = 500
_NEAR_ZERO = 1e-9


def _small_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    utility = SequentialUtilityConfig(
        streams=_STREAMS,
        max_events=_MAX_EVENTS,
        checkpoint_every=_CHECKPOINT_EVERY,
        rho=config.sequential.utility.rho,
    )
    sequential = SequentialConfig(coverage=config.sequential.coverage, utility=utility)
    minimum_evidence = MinimumEvidenceConfig(
        matured_events=_MIN_MATURED, resolved_events=_MIN_RESOLVED
    )
    numerics = config.numerics.model_copy(update={"outer_max_nodes": _NODE_BUDGET})
    return config.model_copy(
        update={
            "sequential": sequential,
            "minimum_evidence": minimum_evidence,
            "numerics": numerics,
        }
    )


def _law_parameters(config: TrajCertConfig) -> LawParameters:
    law = config.laws[LawKey.TIMING_TERMINAL_HARMFUL_LATE]
    return LawParameters(
        key=LawKey.TIMING_TERMINAL_HARMFUL_LATE,
        name=LAW_DISPLAY_NAMES[LawKey.TIMING_TERMINAL_HARMFUL_LATE],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def test_population_utility_model_incompatible() -> None:
    config = active_config.get()
    result = population_sensitivity_utility(summary([0.2, 0.0], [0.0, 0.4], 0.4), 0.0, config)
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
    config = active_config.get()
    result = population_sensitivity_utility(summary([0.2], [0.4], 0.4), 0.0, config)
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
    config = active_config.get()
    result = population_sensitivity_utility(summary([0.2], [0.4], 0.4), _SENSITIVITY_BUDGET, config)
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
    config = active_config.get()
    result = population_sensitivity_utility(summary([0.2], [0.8], 0.0), 0.0, config)
    assert result.compatibility_regime is CompatibilityRegime.NO_UNRESOLVED_MASS
    assert result.relative_unresolved_gain is None
    assert result.absolute_tightening is not None
    assert result.absolute_tightening == pytest.approx(0.0, abs=_NEAR_ZERO)
    assert not result.materially_nonvacuous


def test_sequential_utility_rejects_mismatched_fine_partition() -> None:
    config = _small_config()
    parameters = _law_parameters(config)
    wrong = build_partition(4, 4, config.method.terminal_horizon)
    with pytest.raises(ValueError, match="finest partition"):
        _ = sequential_sensitivity_utility(parameters, wrong, config, _SENSITIVITY_BUDGET)


def test_sequential_sensitivity_utility_small_run() -> None:
    config = _small_config()
    parameters = _law_parameters(config)
    fine_partition = build_partition(
        config.method.finest_bands, config.method.finest_bands, config.method.terminal_horizon
    )
    result = sequential_sensitivity_utility(parameters, fine_partition, config, _SENSITIVITY_BUDGET)
    assert isinstance(result, SequentialUtilityResult)
    assert result.sensitivity_budget == pytest.approx(_SENSITIVITY_BUDGET)
    assert len(result.streams) == _STREAMS
    stream = result.streams[0]
    assert isinstance(stream, SequentialStreamUtility)
    assert stream.stream_index == 0
    assert 0.0 <= stream.fine_certified_update_fraction <= 1.0
    assert 0.0 <= stream.endpoint_certified_update_fraction <= 1.0
    assert stream.fine_time_to_first_certification is None or (
        stream.fine_time_to_first_certification >= 1
    )
    assert stream.endpoint_time_to_first_certification is None or (
        stream.endpoint_time_to_first_certification >= 1
    )
    assert result.mean_certified_update_fraction_gain == pytest.approx(
        stream.certified_update_fraction_gain
    )
    assert result.mean_bound_gain == pytest.approx(stream.mean_bound_gain)
