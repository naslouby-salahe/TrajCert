from __future__ import annotations

from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.experiments.plan import build_plan, cells_for_experiment
from trajcert.types import ExperimentName

_PRODUCTION_CELL_TOTAL = 1_426


def test_recovered_plan_has_no_configuration_gap_cells() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    assert plan.planned_cell_count == _PRODUCTION_CELL_TOTAL
    assert plan.executable_cells == plan.planned_cell_count
    assert plan.invalid_cells == 0


def test_sequential_utility_family_is_fully_planned() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cells = cells_for_experiment(plan, ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY)
    expected_count = len(config.study_design.utility_and_coherence_laws) * len(
        config.sequential.utility.rho
    )
    assert len(cells) == expected_count
    assert all(cell.executable for cell in cells)
    assert {cell.identity.coordinates.rho for cell in cells} == set(config.sequential.utility.rho)


def test_coverage_stress_cells_match_authoritative_configuration() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cells = cells_for_experiment(plan, ExperimentName.ANYTIME_COVERAGE_STRESS)
    assert len(cells) == len(config.study_design.coverage_stress_cases)
    for cell, case in zip(cells, config.study_design.coverage_stress_cases, strict=True):
        variant = cell.identity.coordinates.variant_name
        assert variant is not None and variant.name == case.name
        assert cell.identity.coordinates.synthetic_law_name == LAW_DISPLAY_NAMES[case.law]
        assert cell.identity.coordinates.partition_name == partition_name(case.band_count)
