from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest

from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.runner import (
    CellExecutionResult,
    DependencyReadiness,
    ExecutionContext,
    FailureRecord,
    cell_artifact_index_path,
    cell_completion_path,
    cell_dependency_fingerprint,
    cell_failure_path,
    cell_running_path,
    completion_is_compatible,
    execute_dispatched_cell,
    expected_seed_count,
    producer_component_digest,
    run_cell,
    scientific_dependency_digest,
    scientific_result_artifact_key,
    scientific_result_path,
    scientific_specification_digest,
)
from trajcert.provenance import ExperimentNameValue
from trajcert.storage import (
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    ProvenanceFingerprint,
    file_digest,
    model_digest,
    read_model,
)
from trajcert.types import PublicExecutionState, ReasonCode

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHA256_HEX_LENGTH = 64
_INVENTORY_NAME = ExperimentNameValue("Scientific and Data Inventory")
_LEGACY_INCOHERENCE_NAME = ExperimentNameValue("Legacy Partition Incoherence Check")
_EXECUTOR_INVOCATIONS_AFTER_OVERWRITE = 2


@pytest.fixture(scope="module")
def config() -> TrajCertConfig:
    return TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)


@pytest.fixture(scope="module")
def plan(config: TrajCertConfig) -> ExperimentPlan:
    return build_plan(config)


@pytest.fixture
def inventory_cell(plan: ExperimentPlan) -> PlannedCell:
    return cells_for_experiment(plan, _INVENTORY_NAME)[0]


@pytest.fixture
def legacy_cell(plan: ExperimentPlan) -> PlannedCell:
    return cells_for_experiment(plan, _LEGACY_INCOHERENCE_NAME)[0]


def _build_context(
    tmp_path: Path,
    config: TrajCertConfig,
    plan: ExperimentPlan,
    cell: PlannedCell,
) -> ExecutionContext:
    specification = scientific_specification_digest(config)
    component_digest = producer_component_digest(_REPO_ROOT, cell.identity.experiment_name)
    dependency_specification = scientific_dependency_digest(
        specification,
        str(cell.identity.semantic_cell_key),
        component_digest,
    )
    dependency = cell_dependency_fingerprint(tmp_path, plan, cell, dependency_specification)
    return ExecutionContext(
        workspace_root=tmp_path,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=specification,
        scientific_dependency_digest=dependency_specification,
        provenance_fingerprint=ProvenanceFingerprint("0" * _SHA256_HEX_LENGTH),
        dependency_fingerprint=dependency,
        manifest_digest=DigestHex(str(model_digest(cell))),
        required_artifact_keys=(scientific_result_artifact_key(cell),),
        expected_seed_count=expected_seed_count(cell.identity.experiment_name, config),
    )


def _counting_dispatch_executor(
    config: TrajCertConfig,
    calls: list[int],
) -> Callable[[PlannedCell, ExecutionContext], CellExecutionResult]:
    def executor(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
        calls.append(1)
        return execute_dispatched_cell(cell, context, config)

    return executor


def _raising_executor(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
    del cell, context
    raise AssertionError("executor must not be invoked")


def test_run_cell_first_execution_persists_all_artifacts(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, inventory_cell)
    executor = partial(execute_dispatched_cell, config=config)
    outcome = run_cell(inventory_cell, context, (), executor, False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False
    assert outcome.reason is None
    assert cell_completion_path(inventory_cell, tmp_path).is_file()
    assert cell_artifact_index_path(inventory_cell, tmp_path).is_file()
    assert (tmp_path / scientific_result_path(inventory_cell)).is_file()


def test_run_cell_second_call_reuses_without_invoking_executor(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, inventory_cell)
    calls: list[int] = []
    executor = _counting_dispatch_executor(config, calls)
    first = run_cell(inventory_cell, context, (), executor, False)
    assert first.state is PublicExecutionState.COMPLETED
    assert len(calls) == 1
    second = run_cell(inventory_cell, context, (), executor, False)
    assert second.state is PublicExecutionState.COMPLETED
    assert second.reused is True
    assert len(calls) == 1


def test_run_cell_overwrite_forces_recompute(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, inventory_cell)
    calls: list[int] = []
    executor = _counting_dispatch_executor(config, calls)
    _ = run_cell(inventory_cell, context, (), executor, False)
    assert len(calls) == 1
    outcome = run_cell(inventory_cell, context, (), executor, True)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False
    assert len(calls) == _EXECUTOR_INVOCATIONS_AFTER_OVERWRITE


def test_run_cell_recomputes_when_context_field_changes(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, inventory_cell)
    executor = partial(execute_dispatched_cell, config=config)
    _ = run_cell(inventory_cell, context, (), executor, False)
    changed_context = context.model_copy(
        update={"dependency_fingerprint": DependencyFingerprint("f" * _SHA256_HEX_LENGTH)}
    )
    completion_path = cell_completion_path(inventory_cell, tmp_path)
    assert completion_is_compatible(inventory_cell, changed_context, completion_path) is False
    outcome = run_cell(inventory_cell, changed_context, (), executor, False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False
    updated = read_model(completion_path, CompletionRecord)
    assert updated.dependency_fingerprint == changed_context.dependency_fingerprint


def test_run_cell_rebuilds_after_artifact_index_corruption(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, inventory_cell)
    executor = partial(execute_dispatched_cell, config=config)
    _ = run_cell(inventory_cell, context, (), executor, False)
    artifact_path = tmp_path / scientific_result_path(inventory_cell)
    artifact_path.unlink()
    completion_path = cell_completion_path(inventory_cell, tmp_path)
    assert completion_is_compatible(inventory_cell, context, completion_path) is False
    outcome = run_cell(inventory_cell, context, (), executor, False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False
    assert artifact_path.is_file()


def test_run_cell_rebuilds_after_completion_record_corruption(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, inventory_cell)
    executor = partial(execute_dispatched_cell, config=config)
    _ = run_cell(inventory_cell, context, (), executor, False)
    completion_path = cell_completion_path(inventory_cell, tmp_path)
    _ = completion_path.write_text("not valid json {{{", encoding="utf-8")
    assert completion_is_compatible(inventory_cell, context, completion_path) is False
    outcome = run_cell(inventory_cell, context, (), executor, False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False
    restored = read_model(completion_path, CompletionRecord)
    assert restored.semantic_cell_key == inventory_cell.identity.semantic_cell_key


def test_run_cell_blocked_on_missing_dependency_status(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, legacy_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, legacy_cell)
    outcome = run_cell(legacy_cell, context, (), _raising_executor, False)
    assert outcome.state is PublicExecutionState.BLOCKED
    assert outcome.reused is False
    assert outcome.reason == ReasonCode("MISSING_DEPENDENCY_STATUS")
    assert not cell_completion_path(legacy_cell, tmp_path).exists()
    assert not cell_running_path(legacy_cell, tmp_path).exists()
    assert not cell_failure_path(legacy_cell, tmp_path).exists()


def test_run_cell_blocked_on_upstream_not_completed(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, legacy_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, legacy_cell)
    dependencies = (
        DependencyReadiness(experiment_name=_INVENTORY_NAME, state=PublicExecutionState.FAILED),
    )
    outcome = run_cell(legacy_cell, context, dependencies, _raising_executor, False)
    assert outcome.state is PublicExecutionState.BLOCKED
    assert outcome.reused is False
    assert outcome.reason == ReasonCode("UPSTREAM_EXPERIMENT_NOT_COMPLETED")
    assert not cell_completion_path(legacy_cell, tmp_path).exists()


def test_run_cell_invalid_cell_short_circuits(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    invalid_reason = ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION")
    invalid_cell = inventory_cell.model_copy(
        update={"executable": False, "invalid_reason": invalid_reason}
    )
    context = _build_context(tmp_path, config, plan, inventory_cell)
    outcome = run_cell(invalid_cell, context, (), _raising_executor, False)
    assert outcome.state is PublicExecutionState.INVALID
    assert outcome.reused is False
    assert outcome.reason == invalid_reason
    assert not cell_completion_path(invalid_cell, tmp_path).exists()
    assert not cell_running_path(invalid_cell, tmp_path).exists()
    assert not cell_failure_path(invalid_cell, tmp_path).exists()


def test_run_cell_failure_and_recovery(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, inventory_cell)

    def raise_boom(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
        del cell, context
        raise RuntimeError("boom")

    failed = run_cell(inventory_cell, context, (), raise_boom, False)
    assert failed.state is PublicExecutionState.FAILED
    assert failed.reused is False
    assert failed.reason == ReasonCode("TECHNICAL_EXECUTION_FAILURE")
    failure_path = cell_failure_path(inventory_cell, tmp_path)
    assert failure_path.is_file()
    failure = read_model(failure_path, FailureRecord)
    assert failure.failure_type == "RuntimeError"
    assert failure.message == "boom"
    completion_path = cell_completion_path(inventory_cell, tmp_path)
    assert not completion_path.exists()

    executor = partial(execute_dispatched_cell, config=config)
    recovered = run_cell(inventory_cell, context, (), executor, False)
    assert recovered.state is PublicExecutionState.COMPLETED
    assert recovered.reused is False
    assert completion_path.is_file()


def test_cell_dependency_fingerprint_reflects_upstream_completion(
    tmp_path: Path,
    config: TrajCertConfig,
    plan: ExperimentPlan,
    legacy_cell: PlannedCell,
    inventory_cell: PlannedCell,
) -> None:
    specification = scientific_specification_digest(config)
    component_digest = producer_component_digest(_REPO_ROOT, legacy_cell.identity.experiment_name)
    dependency_specification = scientific_dependency_digest(
        specification,
        str(legacy_cell.identity.semantic_cell_key),
        component_digest,
    )
    before = cell_dependency_fingerprint(tmp_path, plan, legacy_cell, dependency_specification)

    inventory_context = _build_context(tmp_path, config, plan, inventory_cell)
    executor = partial(execute_dispatched_cell, config=config)
    outcome = run_cell(inventory_cell, inventory_context, (), executor, False)
    assert outcome.state is PublicExecutionState.COMPLETED

    after = cell_dependency_fingerprint(tmp_path, plan, legacy_cell, dependency_specification)
    assert before != after


def test_completion_is_compatible_true_immediately_after_a_valid_run(
    tmp_path: Path, config: TrajCertConfig, plan: ExperimentPlan, inventory_cell: PlannedCell
) -> None:
    context = _build_context(tmp_path, config, plan, inventory_cell)
    executor = partial(execute_dispatched_cell, config=config)
    _ = run_cell(inventory_cell, context, (), executor, False)
    completion_path = cell_completion_path(inventory_cell, tmp_path)
    assert completion_is_compatible(inventory_cell, context, completion_path) is True
    index = read_model(cell_artifact_index_path(inventory_cell, tmp_path), CellArtifactIndex)
    assert len(index.artifacts) == 1
    entry = index.artifacts[0]
    assert file_digest(tmp_path / entry.relative_path) == entry.sha256
