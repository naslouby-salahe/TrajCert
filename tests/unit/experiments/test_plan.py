from __future__ import annotations

import pytest
from pydantic import ValidationError

from trajcert.config import GridsConfig, TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.experiments.plan import (
    ExperimentPlan,
    PlannedCell,
    build_plan,
    cells_for_experiment,
)
from trajcert.provenance import (
    ExperimentNameValue,
    SemanticCellIdentity,
    SemanticCoordinates,
    VariantName,
)
from trajcert.storage import PlanDigest
from trajcert.types import EvidenceClass, ReasonCode

_EXPECTED_REGISTRY_TOTAL = 1423
_EXPECTED_SCALING_CELL_COUNT = 2
_PLAN_DIGEST = PlanDigest("digest")


def _production_config() -> TrajCertConfig:
    return TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)


def _cell(executable: bool, invalid_reason: ReasonCode | None) -> PlannedCell:
    return PlannedCell(
        experiment_order=1,
        cell_ordinal=1,
        identity=SemanticCellIdentity(
            experiment_name=ExperimentNameValue("Legacy Partition Incoherence Check"),
            coordinates=SemanticCoordinates(variant_name=VariantName("protocol-inventory-gate")),
        ),
        evidence_class=EvidenceClass.VALIDATION,
        executable=executable,
        invalid_reason=invalid_reason,
        required_experiments=(),
    )


def test_planned_cell_rejects_executable_with_invalid_reason() -> None:
    invalid_reason = ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION")
    with pytest.raises(ValidationError, match="cannot carry an invalid reason"):
        _ = _cell(executable=True, invalid_reason=invalid_reason)


def test_planned_cell_rejects_nonexecutable_without_reason() -> None:
    with pytest.raises(ValidationError, match="requires an invalid reason"):
        _ = _cell(executable=False, invalid_reason=None)


def test_planned_cell_accepts_valid_contracts() -> None:
    assert _cell(executable=True, invalid_reason=None).executable
    assert not _cell(
        executable=False, invalid_reason=ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION")
    ).executable


def test_build_plan_production_reproduces_cell_total() -> None:
    plan = build_plan(_production_config())
    assert plan.planned_cell_count == _EXPECTED_REGISTRY_TOTAL - 1
    assert plan.executable_cells == _EXPECTED_REGISTRY_TOTAL - 1
    assert plan.invalid_cells == 0


def test_build_plan_is_deterministic() -> None:
    config = _production_config()
    first = build_plan(config)
    second = build_plan(config)
    assert first == second
    assert first.plan_digest == second.plan_digest


def test_build_plan_marks_nonapplicable_experiments() -> None:
    plan = build_plan(_production_config())
    names = tuple(item.identity.semantic_cell_key for item in plan.cells)
    assert len(names) == len(set(names))
    assert plan.nonapplicable_experiments == (
        ExperimentNameValue("Real-Trajectory Validation"),
        ExperimentNameValue("Foreign-Information Negative Control"),
    )


def test_cells_for_experiment_filters_by_name() -> None:
    config = _production_config()
    plan = build_plan(config)
    cells = cells_for_experiment(plan, ExperimentNameValue("Sequential Sensitivity Utility"))
    expected_count = len(config.study_design.utility_and_coherence_laws) * len(
        config.sequential.utility.rho
    )
    assert len(cells) == expected_count
    assert all(cell.executable for cell in cells)


def test_cells_for_experiment_unknown_name_is_empty() -> None:
    plan = build_plan(_production_config())
    assert cells_for_experiment(plan, ExperimentNameValue("Unknown Experiment")) == ()


def test_build_plan_adapts_to_configured_scaling_bands() -> None:
    config = _production_config()
    grids = GridsConfig(
        partitions=config.grids.partitions,
        scaling_bands=(16, 32),
        rho=config.grids.rho,
        same_endpoint_rho=config.grids.same_endpoint_rho,
        beta=config.grids.beta,
    )
    plan = build_plan(config.model_copy(update={"grids": grids}))
    assert (
        len(cells_for_experiment(plan, ExperimentNameValue("Computational Scaling")))
        == _EXPECTED_SCALING_CELL_COUNT
    )


def test_experiment_plan_rejects_cell_count_mismatch() -> None:
    with pytest.raises(ValidationError, match="cell count must equal"):
        _ = ExperimentPlan(
            cells=(),
            planned_cell_count=1,
            executable_cells=0,
            invalid_cells=0,
            nonapplicable_experiments=(),
            plan_digest=_PLAN_DIGEST,
        )


def test_experiment_plan_rejects_uncounted_executable_cells() -> None:
    cell = _cell(executable=True, invalid_reason=None)
    with pytest.raises(ValidationError, match="do not cover the plan"):
        _ = ExperimentPlan(
            cells=(cell,),
            planned_cell_count=1,
            executable_cells=0,
            invalid_cells=0,
            nonapplicable_experiments=(),
            plan_digest=_PLAN_DIGEST,
        )


def test_experiment_plan_rejects_duplicate_cell_keys() -> None:
    cell = _cell(executable=True, invalid_reason=None)
    with pytest.raises(ValidationError, match="must be unique"):
        _ = ExperimentPlan(
            cells=(cell, cell),
            planned_cell_count=2,
            executable_cells=2,
            invalid_cells=0,
            nonapplicable_experiments=(),
            plan_digest=_PLAN_DIGEST,
        )
