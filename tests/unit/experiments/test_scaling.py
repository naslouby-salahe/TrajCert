from __future__ import annotations

import pytest
from pydantic import ValidationError

from trajcert.config import BenchmarkConfig, TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.experiments.scaling import (
    ComputationalScalingResult,
    ScalingMeasurement,
    ScalingTarget,
    ScalingTargetSummary,
    benchmark_scaling_cell,
)

_NODE_BUDGET = 500
_SAMPLE_RUNTIME_SECONDS = 0.1
_SAMPLE_IQR_SECONDS = 0.01
_SAMPLE_MEAN_SECONDS = 0.1
_SAMPLE_SD_SECONDS = 0.001
_POPULATION_PEAK_MIB = 10.0
_OUTER_PEAK_MIB = 20.0


def _small_benchmark_config() -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    benchmark = BenchmarkConfig(
        warmup_repetitions=0,
        measured_repetitions=1,
        outer_sample_size=config.benchmark.outer_sample_size,
        minimum_samples_for_standard_deviation=(
            config.benchmark.minimum_samples_for_standard_deviation
        ),
        scaling_information_margin=config.benchmark.scaling_information_margin,
    )
    numerics = config.numerics.model_copy(update={"outer_max_nodes": _NODE_BUDGET})
    return config.model_copy(update={"benchmark": benchmark, "numerics": numerics})


def _population_summary() -> ScalingTargetSummary:
    return ScalingTargetSummary(
        target=ScalingTarget.POPULATION_SOLVER,
        median_runtime_seconds=_SAMPLE_RUNTIME_SECONDS,
        iqr_runtime_seconds=_SAMPLE_IQR_SECONDS,
        mean_runtime_seconds=_SAMPLE_MEAN_SECONDS,
        sample_sd_runtime_seconds=_SAMPLE_SD_SECONDS,
        peak_rss_mib=_POPULATION_PEAK_MIB,
        median_root_iterations=3.0,
        median_outer_nodes=None,
    )


def _outer_summary() -> ScalingTargetSummary:
    return ScalingTargetSummary(
        target=ScalingTarget.OUTER_PROJECTION,
        median_runtime_seconds=_SAMPLE_RUNTIME_SECONDS,
        iqr_runtime_seconds=_SAMPLE_IQR_SECONDS,
        mean_runtime_seconds=_SAMPLE_MEAN_SECONDS,
        sample_sd_runtime_seconds=_SAMPLE_SD_SECONDS,
        peak_rss_mib=_OUTER_PEAK_MIB,
        median_root_iterations=None,
        median_outer_nodes=5.0,
    )


def test_benchmark_scaling_cell_rejects_nonpositive_band_count() -> None:
    config = _small_benchmark_config()
    _ = active_config.set(config)
    with pytest.raises(ValueError, match="positive"):
        _ = benchmark_scaling_cell(0)
    with pytest.raises(ValueError, match="positive"):
        _ = benchmark_scaling_cell(-2)


def test_benchmark_scaling_cell_small_run() -> None:
    config = _small_benchmark_config()
    _ = active_config.set(config)
    result = benchmark_scaling_cell(1)
    assert result.band_count == 1
    assert result.population.target is ScalingTarget.POPULATION_SOLVER
    assert result.outer_projection.target is ScalingTarget.OUTER_PROJECTION
    assert result.population.median_root_iterations is not None
    assert result.outer_projection.median_outer_nodes is not None
    assert 1 <= result.outer_projection.median_outer_nodes <= _NODE_BUDGET
    assert result.population.median_runtime_seconds >= 0.0
    assert result.outer_projection.median_runtime_seconds >= 0.0
    assert result.population.sample_sd_runtime_seconds == 0.0
    assert result.outer_projection.sample_sd_runtime_seconds == 0.0
    assert result.peak_memory_mib >= result.population.peak_rss_mib
    assert result.peak_memory_mib >= result.outer_projection.peak_rss_mib


def test_scaling_target_enum_values() -> None:
    assert ScalingTarget.POPULATION_SOLVER.value == "population-solver"
    assert ScalingTarget.OUTER_PROJECTION.value == "outer-projection"


def test_scaling_measurement_rejects_nonfinite_peak_memory() -> None:
    with pytest.raises(ValidationError):
        _ = ScalingMeasurement(
            target=ScalingTarget.POPULATION_SOLVER,
            runtime_ns=5,
            peak_rss_mib=float("nan"),
            root_iterations=None,
            outer_nodes=None,
        )


def test_scaling_measurement_rejects_unknown_target() -> None:
    with pytest.raises(ValidationError):
        _ = ScalingMeasurement.model_validate(
            {
                "target": "bogus",
                "runtime_ns": 5,
                "peak_rss_mib": 1.0,
                "root_iterations": None,
                "outer_nodes": None,
            }
        )


def test_computational_scaling_result_aggregates_peak_memory() -> None:
    population = _population_summary()
    outer = _outer_summary()
    result = ComputationalScalingResult(
        band_count=2,
        population=population,
        outer_projection=outer,
        peak_memory_mib=max(population.peak_rss_mib, outer.peak_rss_mib),
    )
    assert result.peak_memory_mib == pytest.approx(_OUTER_PEAK_MIB)
    assert result.population.median_root_iterations == pytest.approx(3.0)
    assert result.outer_projection.median_outer_nodes == pytest.approx(5.0)
