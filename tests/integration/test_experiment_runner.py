from __future__ import annotations

from pathlib import Path

from trajcert.config import (
    CoverageConfig,
    SequentialConfig,
    SequentialUtilityConfig,
    TrajCertConfig,
    active_config,
)
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.runner import (
    CheckpointRecord,
    ExecutionContext,
    cell_checkpoint_batch_path,
    cell_dependency_material,
    execute_dispatched_cell,
    execute_scientific_cell,
    expected_seed_count,
    scientific_result_artifact_key,
    scientific_specification_digest,
)
from trajcert.provenance import (
    EnvironmentDigest,
    dependency_fingerprint,
)
from trajcert.storage import (
    file_digest,
    read_model,
)
from trajcert.types import ExperimentName

_RUNTIME_STREAMS = 2
_RUNTIME_EVENTS = 200
_RUNTIME_CHECKPOINT = 100
_RUNTIME_OUTER_NODE_CAP = 100
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENVIRONMENT_DIGEST = EnvironmentDigest(file_digest(_REPO_ROOT / "uv.lock"))
_SHA256_HEX_LENGTH = 64


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
        clopper_pearson_confidence=config.sequential.coverage.clopper_pearson_confidence,
        batch_size=1,
    )
    utility = SequentialUtilityConfig(
        streams=_RUNTIME_STREAMS,
        max_events=_RUNTIME_EVENTS,
        checkpoint_every=_RUNTIME_CHECKPOINT,
        rho=config.sequential.utility.rho,
        batch_size=1,
    )
    numerics = config.numerics.model_copy(update={"outer_max_nodes": _RUNTIME_OUTER_NODE_CAP})
    return config.model_copy(
        update={
            "sequential": SequentialConfig(coverage=coverage, utility=utility),
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


def test_sequential_utility_batch_checkpoints_are_reused_on_second_execution(
    tmp_path: Path,
) -> None:
    production = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    runtime = _small_runtime_config(production)
    plan = build_plan(production)
    cell = cells_for_experiment(plan, ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY)[0]
    context = _build_context(tmp_path, plan, cell)
    _ = active_config.set(runtime)
    _ = execute_dispatched_cell(cell, context)
    batch_paths = [
        cell_checkpoint_batch_path(cell, tmp_path, index) for index in range(_RUNTIME_STREAMS)
    ]
    assert all(path.is_file() for path in batch_paths)
    checkpoints_before = [read_model(path, CheckpointRecord) for path in batch_paths]
    assert all(checkpoint.completed for checkpoint in checkpoints_before)
    mtimes_before = [path.stat().st_mtime_ns for path in batch_paths]
    _ = execute_dispatched_cell(cell, context)
    mtimes_after = [path.stat().st_mtime_ns for path in batch_paths]
    assert mtimes_after == mtimes_before
