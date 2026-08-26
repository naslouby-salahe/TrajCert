from __future__ import annotations

from pathlib import Path

from trajcert.analysis.metrics import MetricName
from trajcert.config import (
    CoverageConfig,
    SequentialConfig,
    SequentialUtilityConfig,
    TrajCertConfig,
)
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.data.partitions import partition_name
from trajcert.experiments.dispatch import execute_phase_one_cell
from trajcert.experiments.plan import build_plan, cells_for_experiment
from trajcert.provenance import ExperimentNameValue
from trajcert.reporting.source_data import (
    AnalysisType,
    RhoUtilityRow,
    read_source_data,
    write_source_data,
)
from trajcert.types import LawName

_RUNTIME_STREAMS = 2
_RUNTIME_EVENTS = 200
_RUNTIME_CHECKPOINT = 100


def test_recovered_plan_has_no_configuration_gap_cells() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    assert plan.registry_total == 1_423
    assert plan.executable_cells == plan.registry_total
    assert plan.invalid_cells == 0


def test_recovered_scientific_families_dispatch() -> None:
    production = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    runtime = _small_runtime_config(production)
    plan = build_plan(production)
    names = (
        "Legacy Partition Incoherence Check",
        "Strict Timing-Gain Identity",
        "Partition Coherence",
        "Same Endpoint, Different Timing",
        "Strict Timing Gain",
        "Sharpness Against Generic Oracle",
        "Safety and Intrinsic Impossibility",
        "Population Sensitivity Utility",
        "Sequential Sensitivity Utility",
    )
    for name in names:
        cell = cells_for_experiment(plan, ExperimentNameValue(name))[0]
        result = execute_phase_one_cell(cell, runtime)
        assert result is not None


def test_coverage_stress_cells_match_authoritative_configuration() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cells = cells_for_experiment(plan, ExperimentNameValue("Anytime Coverage Stress"))
    assert len(cells) == len(config.study_design.coverage_stress_cases)
    for cell, case in zip(cells, config.study_design.coverage_stress_cases, strict=True):
        assert cell.identity.coordinates.variant_name == case.name
        assert cell.identity.coordinates.synthetic_law_name == LAW_DISPLAY_NAMES[case.law]
        assert cell.identity.coordinates.partition_name == partition_name(case.band_count)


def test_terminal_selection_failure_boundary_dispatches() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cells = cells_for_experiment(plan, ExperimentNameValue("Failure Boundary Atlas"))
    cell = next(
        item
        for item in cells
        if "terminal-selection-asymmetry="
        in str(item.identity.coordinates.failure_boundary_axis_and_level)
    )
    result = execute_phase_one_cell(cell, config)
    assert result is not None


def test_source_data_parquet_roundtrip_preserves_aliases(tmp_path: Path) -> None:
    path = tmp_path / "rho-utility.parquet"
    row = RhoUtilityRow(
        analysis_type=AnalysisType.POPULATION,
        law_name=LawName("law"),
        rho=0.05,
        partition_name="8-band partition",
        metric_name=MetricName("risk upper"),
        metric_value=0.1,
        materiality_pass=True,
    )
    digest = write_source_data(path, (row,))
    table = read_source_data(path)
    assert len(str(digest)) == 64
    assert table.num_rows == 1
    assert "materiality_pass" in table.column_names


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
