from __future__ import annotations

from trajcert.config import (
    CoverageConfig,
    SequentialConfig,
    SequentialUtilityConfig,
    TrajCertConfig,
)
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.experiments.plan import build_plan, cells_for_experiment
from trajcert.experiments.runner import execute_scientific_cell
from trajcert.types import ExperimentName

_RUNTIME_STREAMS = 2
_RUNTIME_EVENTS = 200
_RUNTIME_CHECKPOINT = 100


def test_recovered_scientific_families_dispatch() -> None:
    production = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    runtime = _small_runtime_config(production)
    plan = build_plan(production)
    names = (
        ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,
        ExperimentName.STRICT_TIMING_GAIN_IDENTITY,
        ExperimentName.PARTITION_COHERENCE,
        ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING,
        ExperimentName.STRICT_TIMING_GAIN,
        ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE,
        ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY,
        ExperimentName.POPULATION_SENSITIVITY_UTILITY,
    )
    for name in names:
        cell = cells_for_experiment(plan, name)[0]
        result = execute_scientific_cell(cell, runtime)
        assert result is not None


def test_terminal_selection_failure_boundary_dispatches() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cells = cells_for_experiment(plan, ExperimentName.FAILURE_BOUNDARY_ATLAS)
    cell = next(
        item
        for item in cells
        if "terminal-selection-asymmetry="
        in str(item.identity.coordinates.failure_boundary_axis_and_level)
    )
    result = execute_scientific_cell(cell, config)
    assert result is not None


def _small_runtime_config(config: TrajCertConfig) -> TrajCertConfig:
    coverage = CoverageConfig(
        streams=_RUNTIME_STREAMS,
        max_events=_RUNTIME_EVENTS,
        checkpoint_every=_RUNTIME_CHECKPOINT,
        acceptance_upper_limit=config.sequential.coverage.acceptance_upper_limit,
    )
    utility = SequentialUtilityConfig(
        streams=_RUNTIME_STREAMS,
        max_events=_RUNTIME_EVENTS,
        checkpoint_every=_RUNTIME_CHECKPOINT,
        rho=config.sequential.utility.rho,
    )
    return config.model_copy(
        update={"sequential": SequentialConfig(coverage=coverage, utility=utility)}
    )
