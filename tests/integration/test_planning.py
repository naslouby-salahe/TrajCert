from __future__ import annotations

from math import ceil

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.experiments.checkpointing import batch_seed_ranges
from trajcert.experiments.plan import build_plan, cells_for_experiment
from trajcert.experiments.runner import expected_seed_count
from trajcert.types import ExperimentName

_PRODUCTION_CELL_TOTAL = 2_013


def test_recovered_plan_has_no_configuration_gap_cells() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    assert plan.planned_cell_count == _PRODUCTION_CELL_TOTAL
    assert plan.executable_cells == plan.planned_cell_count
    assert plan.invalid_cells == 0


def test_removed_sequential_utility_experiment_is_not_planned() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    planned_names = {cell.identity.experiment_name.value for cell in plan.cells}
    assert "Sequential Sensitivity Utility" not in planned_names
    assert "Sequential Sensitivity Utility" not in {name.value for name in ExperimentName}
    assert not hasattr(config.sequential, "utility")
    assert not hasattr(config.materiality, "sequential")


def test_coverage_stream_count_drives_execution_seed_batches() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    token = active_config.set(config)
    try:
        count = expected_seed_count(ExperimentName.ANYTIME_COVERAGE_STRESS)
        batches = batch_seed_ranges(count, config.sequential.coverage.batch_size)
    finally:
        active_config.reset(token)

    assert count == config.sequential.coverage.streams
    assert len(batches) == ceil(count / config.sequential.coverage.batch_size)
    assert batches[0].start == 0
    assert batches[-1].stop == count
    assert all(left.stop == right.start for left, right in zip(batches, batches[1:]))


def test_coverage_stress_cells_match_authoritative_configuration() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cells = cells_for_experiment(plan, ExperimentName.ANYTIME_COVERAGE_STRESS)
    assert len(cells) == len(config.study_design.coverage_stress_cases)
    for cell, case in zip(cells, config.study_design.coverage_stress_cases, strict=True):
        variant = cell.identity.coordinates.variant_name
        assert variant is not None
        assert variant.name == case.name
        assert cell.identity.coordinates.synthetic_law_name == LAW_DISPLAY_NAMES[case.law]
        assert cell.identity.coordinates.partition_name == partition_name(case.band_count)
