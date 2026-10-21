from __future__ import annotations

from pathlib import Path

import pytest

from trajcert.config import (
    CoverageConfig,
    SequentialConfig,
    TimingInformationExpectation,
    TrajCertConfig,
    active_config,
)
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.experiments.artifacts import (
    cell_checkpoint_batch_path,
    cell_dependency_material,
    scientific_result_artifact_key,
    scientific_specification_digest,
)
from trajcert.experiments.dispatch import execute_scientific_cell
from trajcert.experiments.failure_boundaries import FailureBoundaryAxis
from trajcert.experiments.mathematics import IdentityResult
from trajcert.experiments.models import (
    CheckpointRecord,
    ExecutionContext,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.runner import (
    execute_dispatched_cell,
    expected_seed_count,
)
from trajcert.experiments.timing import PartitionCoherenceResult
from trajcert.provenance import dependency_fingerprint
from trajcert.storage import (
    file_digest,
    read_model,
)
from trajcert.types import EnvironmentDigest, ExperimentName

_RUNTIME_STREAMS = 2
_RUNTIME_EVENTS = 200
_RUNTIME_CHECKPOINT = 100
_RUNTIME_OUTER_NODE_CAP = 100
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENVIRONMENT_DIGEST = EnvironmentDigest(file_digest(_REPO_ROOT / "requirements.lock"))
_SHA256_HEX_LENGTH = 64


@pytest.mark.parametrize(
    "name", [ExperimentName.STRICT_TIMING_GAIN_IDENTITY, ExperimentName.STRICT_TIMING_GAIN]
)
@pytest.mark.parametrize("expected_valid", [True, False])
def test_strict_timing_dispatch_consumes_declared_expectation(
    name: ExperimentName, expected_valid: bool
) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    cases = list(config.study_design.strict_timing_cases)
    expectation = (
        TimingInformationExpectation.ZERO
        if expected_valid
        else TimingInformationExpectation.POSITIVE
    )
    cases[0] = cases[0].model_copy(update={"expectation": expectation})
    study = config.study_design.model_copy(update={"strict_timing_cases": tuple(cases)})
    runtime = config.model_copy(update={"study_design": study})
    cell = cells_for_experiment(build_plan(runtime), name)[0]
    result = execute_scientific_cell(cell, runtime)
    assert isinstance(result, (IdentityResult, PartitionCoherenceResult))
    assert result.passed is expected_valid


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
        if item.identity.coordinates.failure_boundary_axis_and_level is not None
        and item.identity.coordinates.failure_boundary_axis_and_level.axis
        is FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY
    )
    result = execute_scientific_cell(cell, config)
    assert result is not None


@pytest.mark.timeout(300)
def test_certification_power_batches_are_recovered_and_dispatched(tmp_path: Path) -> None:
    production = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    power = production.sequential.certification_power.model_copy(
        update={"streams": _RUNTIME_STREAMS, "batch_size": 1, "checkpoints": (200, 400)}
    )
    scenarios = tuple(
        scenario.model_copy(update={"checkpoints": (200, 400)}) for scenario in power.scenarios
    )
    power = power.model_copy(update={"scenarios": scenarios})
    runtime = production.model_copy(
        update={
            "sequential": SequentialConfig(
                coverage=production.sequential.coverage, certification_power=power
            ),
            "numerics": production.numerics.model_copy(
                update={"outer_max_nodes": _RUNTIME_OUTER_NODE_CAP}
            ),
        }
    )
    plan = build_plan(runtime)
    cell = cells_for_experiment(plan, ExperimentName.ANYTIME_CERTIFICATION_POWER)[0]
    _ = active_config.set(runtime)
    assert expected_seed_count(ExperimentName.ANYTIME_CERTIFICATION_POWER) == _RUNTIME_STREAMS
    context = _build_context(tmp_path, plan, cell)
    _ = execute_dispatched_cell(cell, context)
    batch_paths = [
        cell_checkpoint_batch_path(cell, tmp_path, index) for index in range(_RUNTIME_STREAMS)
    ]
    assert all(path.is_file() for path in batch_paths)
    before = [path.stat().st_mtime_ns for path in batch_paths]
    _ = execute_dispatched_cell(cell, context)
    assert [path.stat().st_mtime_ns for path in batch_paths] == before


def _small_runtime_config(config: TrajCertConfig) -> TrajCertConfig:
    coverage = CoverageConfig(
        streams=_RUNTIME_STREAMS,
        max_events=_RUNTIME_EVENTS,
        checkpoint_every=_RUNTIME_CHECKPOINT,
        acceptance_upper_limit=config.sequential.coverage.acceptance_upper_limit,
        clopper_pearson_confidence=config.sequential.coverage.clopper_pearson_confidence,
        batch_size=1,
    )
    numerics = config.numerics.model_copy(update={"outer_max_nodes": _RUNTIME_OUTER_NODE_CAP})
    return config.model_copy(
        update={
            "sequential": SequentialConfig(
                coverage=coverage, certification_power=config.sequential.certification_power
            ),
            "numerics": numerics,
        }
    )


def _build_context(tmp_path: Path, plan: ExperimentPlan, cell: PlannedCell) -> ExecutionContext:
    specification = scientific_specification_digest()
    dependency_material = cell_dependency_material(
        tmp_path, plan, cell, specification, _ENVIRONMENT_DIGEST
    )
    dependency = dependency_fingerprint(dependency_material)
    return ExecutionContext(
        workspace_root=tmp_path,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=specification,
        dependency_fingerprint=dependency,
        required_artifact_keys=(scientific_result_artifact_key(cell),),
        expected_seed_count=expected_seed_count(cell.identity.experiment_name),
    )


@pytest.mark.timeout(300)
def test_coverage_stress_batch_checkpoints_are_reused_on_second_execution(
    tmp_path: Path,
) -> None:
    production = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    runtime = _small_runtime_config(production)
    plan = build_plan(production)
    cell = cells_for_experiment(plan, ExperimentName.ANYTIME_COVERAGE_STRESS)[0]
    context = _build_context(tmp_path, plan, cell)
    _ = active_config.set(runtime)
    _ = execute_dispatched_cell(cell, context)
    batch_paths = [
        cell_checkpoint_batch_path(cell, tmp_path, index) for index in range(_RUNTIME_STREAMS)
    ]
    assert all(path.is_file() for path in batch_paths)
    checkpoints_before = [read_model(path, CheckpointRecord) for path in batch_paths]
    assert all(checkpoint.completed for checkpoint in checkpoints_before)
    assert [checkpoint.batch_index for checkpoint in checkpoints_before] == [0, 1]
    mtimes_before = [path.stat().st_mtime_ns for path in batch_paths]
    _ = execute_dispatched_cell(cell, context)
    mtimes_after = [path.stat().st_mtime_ns for path in batch_paths]
    assert mtimes_after == mtimes_before
