from __future__ import annotations

from pathlib import Path

from trajcert.exceptions import SerializationError
from trajcert.experiments.plan import PlannedCell
from trajcert.experiments.runner import (
    DependencyReadiness,
    ExecutionContext,
    FailureRecord,
    cell_completion_path,
    cell_failure_path,
    cell_running_path,
    completion_is_compatible,
    dependency_block_reason,
)
from trajcert.storage import SemanticCellKey, read_model
from trajcert.types import Count, DomainModel, ExperimentName, PublicExecutionState, ReasonCode


class CellStatus(DomainModel):
    semantic_cell_key: SemanticCellKey
    state: PublicExecutionState
    reason: ReasonCode | None


class ExperimentStatus(DomainModel):
    experiment_name: ExperimentName
    state: PublicExecutionState
    total_cells: Count
    completed_cells: Count
    invalid_cells: Count
    failed_cells: Count
    blocked_cells: Count
    running_cells: Count
    ready_cells: Count


class StateCounts(DomainModel):
    completed_cells: Count
    invalid_cells: Count
    failed_cells: Count
    blocked_cells: Count
    running_cells: Count
    ready_cells: Count


def inspect_cell_status(
    cell: PlannedCell,
    context: ExecutionContext,
    dependencies: tuple[DependencyReadiness, ...],
) -> CellStatus:
    key = cell.identity.semantic_cell_key
    if not cell.executable:
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.INVALID,
            reason=cell.invalid_reason,
        )
    dependency_reason = dependency_block_reason(cell, dependencies)
    if dependency_reason is not None:
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.BLOCKED,
            reason=dependency_reason,
        )
    completion_path = cell_completion_path(cell, context.workspace_root)
    if completion_path.is_file():
        return _completion_status(key, cell, context, completion_path)
    if cell_running_path(cell, context.workspace_root).is_file():
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.RUNNING,
            reason=None,
        )
    failure_path = cell_failure_path(cell, context.workspace_root)
    if failure_path.is_file():
        failure_status = _matching_failure_status(key, context, failure_path)
        if failure_status is not None:
            return failure_status
    return CellStatus(
        semantic_cell_key=key,
        state=PublicExecutionState.READY,
        reason=None,
    )


def _completion_status(
    key: SemanticCellKey,
    cell: PlannedCell,
    context: ExecutionContext,
    completion_path: Path,
) -> CellStatus:
    if completion_is_compatible(cell, context, completion_path):
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.COMPLETED,
            reason=None,
        )
    return CellStatus(
        semantic_cell_key=key,
        state=PublicExecutionState.BLOCKED,
        reason=ReasonCode.STALE_OR_INCOMPATIBLE_COMPLETION,
    )


def aggregate_experiment_status(
    experiment_name: ExperimentName,
    statuses: tuple[CellStatus, ...],
    declared_cells: Count,
) -> ExperimentStatus:
    if len(statuses) != declared_cells:
        raise ValueError("cell-status count does not match the declared experiment cell count")
    counts = _state_counts(statuses)
    state = _aggregate_state(counts, declared_cells)
    return ExperimentStatus(
        experiment_name=experiment_name,
        state=state,
        total_cells=declared_cells,
        completed_cells=counts.completed_cells,
        invalid_cells=counts.invalid_cells,
        failed_cells=counts.failed_cells,
        blocked_cells=counts.blocked_cells,
        running_cells=counts.running_cells,
        ready_cells=counts.ready_cells,
    )


def _matching_failure_status(
    semantic_cell_key: SemanticCellKey,
    context: ExecutionContext,
    failure_path: Path,
) -> CellStatus | None:
    try:
        failure = read_model(failure_path, FailureRecord)
    except SerializationError:
        return CellStatus(
            semantic_cell_key=semantic_cell_key,
            state=PublicExecutionState.FAILED,
            reason=ReasonCode.INVALID_FAILURE_RECORD,
        )
    if (
        failure.semantic_cell_key != semantic_cell_key
        or failure.plan_digest != context.plan_digest
        or failure.dependency_fingerprint != context.dependency_fingerprint
    ):
        return None
    reason = (
        ReasonCode.DATA_VALIDATION_FAILURE
        if failure.execution_state is PublicExecutionState.INVALID
        else ReasonCode.TECHNICAL_EXECUTION_FAILURE
    )
    return CellStatus(
        semantic_cell_key=semantic_cell_key,
        state=failure.execution_state,
        reason=reason,
    )


def _aggregate_state(counts: StateCounts, declared_cells: Count) -> PublicExecutionState:
    if declared_cells in (0, counts.invalid_cells):
        return PublicExecutionState.INVALID
    if counts.failed_cells > 0:
        return PublicExecutionState.FAILED
    if counts.running_cells > 0:
        return PublicExecutionState.RUNNING
    if counts.blocked_cells > 0:
        return PublicExecutionState.BLOCKED
    if counts.completed_cells + counts.invalid_cells == declared_cells:
        return PublicExecutionState.COMPLETED
    return (
        PublicExecutionState.READY if counts.ready_cells > 0 else PublicExecutionState.NOT_STARTED
    )


def _state_counts(statuses: tuple[CellStatus, ...]) -> StateCounts:
    return StateCounts(
        completed_cells=sum(item.state is PublicExecutionState.COMPLETED for item in statuses),
        invalid_cells=sum(item.state is PublicExecutionState.INVALID for item in statuses),
        failed_cells=sum(item.state is PublicExecutionState.FAILED for item in statuses),
        blocked_cells=sum(item.state is PublicExecutionState.BLOCKED for item in statuses),
        running_cells=sum(item.state is PublicExecutionState.RUNNING for item in statuses),
        ready_cells=sum(item.state is PublicExecutionState.READY for item in statuses),
    )
