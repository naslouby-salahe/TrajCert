from __future__ import annotations

import traceback

from trajcert.config import active_config
from trajcert.exceptions import (
    InvalidScientificDataError,
)
from trajcert.experiments.artifacts import (
    cell_artifact_index_path,
    cell_completion_path,
    cell_failure_path,
    cell_running_path,
    completion_is_compatible,
    completion_record,
    scientific_result_artifact_key,
    scientific_result_path,
    validate_execution_result,
    verify_artifacts,
)
from trajcert.experiments.catalog import (
    SeedPolicy,
    seed_policy_for,
    supports_batched_recovery,
)
from trajcert.experiments.checkpointing import dispatch_with_batched_recovery
from trajcert.experiments.dispatch import (
    dispatch_real_trajectory_validation,
    execute_scientific_cell,
)
from trajcert.experiments.models import (
    CellExecutionResult,
    CellExecutor,
    CellRunOutcome,
    DependencyReadiness,
    ExecutionContext,
    FailureRecord,
    FailureTraceback,
    FailureType,
    RunningRecord,
)
from trajcert.experiments.plan import PlannedCell
from trajcert.storage import (
    ArtifactIndexEntry,
    CellArtifactIndex,
    atomic_write_model,
    write_completion_last,
)
from trajcert.telemetry import set_current_cell_key
from trajcert.types import (
    ExperimentName,
    FailureMessage,
    PublicExecutionState,
    ReasonCode,
    SeedCount,
)


def _failure_traceback(exc: BaseException) -> FailureTraceback:
    formatted = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return FailureTraceback(formatted)


def run_cell(
    cell: PlannedCell,
    context: ExecutionContext,
    dependencies: tuple[DependencyReadiness, ...],
    executor: CellExecutor,
    overwrite: bool,
) -> CellRunOutcome:
    completion_path = cell_completion_path(cell, context.workspace_root)
    failure_path = cell_failure_path(cell, context.workspace_root)
    running_path = cell_running_path(cell, context.workspace_root)
    if not cell.executable:
        return CellRunOutcome(
            state=PublicExecutionState.INVALID,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=cell.invalid_reason,
        )
    dependency_reason = dependency_block_reason(cell, dependencies)
    if dependency_reason is not None:
        return CellRunOutcome(
            state=PublicExecutionState.BLOCKED,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=dependency_reason,
        )
    if (
        completion_path.is_file()
        and not overwrite
        and completion_is_compatible(cell, context, completion_path)
    ):
        return CellRunOutcome(
            state=PublicExecutionState.COMPLETED,
            reused=True,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=None,
        )
    completion_path.unlink(missing_ok=True)
    failure_path.unlink(missing_ok=True)
    running_record = RunningRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        plan_digest=context.plan_digest,
        dependency_fingerprint=context.dependency_fingerprint,
    )
    _ = atomic_write_model(running_path, running_record)
    set_current_cell_key(cell.identity.semantic_cell_key)
    try:
        result = executor(cell, context)
        validate_execution_result(result, context)
        verify_artifacts(result.artifact_index, context.workspace_root)
        _ = atomic_write_model(
            cell_artifact_index_path(cell, context.workspace_root), result.artifact_index
        )
        completion = completion_record(cell, context, result)
        _ = write_completion_last(completion_path.parent, completion)
        failure_path.unlink(missing_ok=True)
        return CellRunOutcome(
            state=PublicExecutionState.COMPLETED,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=None,
        )
    except InvalidScientificDataError as exc:
        failure = FailureRecord(
            semantic_cell_key=cell.identity.semantic_cell_key,
            plan_digest=context.plan_digest,
            dependency_fingerprint=context.dependency_fingerprint,
            failure_type=FailureType(type(exc).__name__),
            message=FailureMessage(str(exc)),
            traceback=_failure_traceback(exc),
            execution_state=PublicExecutionState.INVALID,
        )
        _ = atomic_write_model(failure_path, failure)
        completion_path.unlink(missing_ok=True)
        return CellRunOutcome(
            state=PublicExecutionState.INVALID,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=ReasonCode.DATA_VALIDATION_FAILURE,
        )
    except Exception as exc:
        failure = FailureRecord(
            semantic_cell_key=cell.identity.semantic_cell_key,
            plan_digest=context.plan_digest,
            dependency_fingerprint=context.dependency_fingerprint,
            failure_type=FailureType(type(exc).__name__),
            message=FailureMessage(str(exc)),
            traceback=_failure_traceback(exc),
            execution_state=PublicExecutionState.FAILED,
        )
        _ = atomic_write_model(failure_path, failure)
        completion_path.unlink(missing_ok=True)
        return CellRunOutcome(
            state=PublicExecutionState.FAILED,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=ReasonCode.TECHNICAL_EXECUTION_FAILURE,
        )
    finally:
        set_current_cell_key(None)
        running_path.unlink(missing_ok=True)


def dependency_block_reason(
    cell: PlannedCell, dependencies: tuple[DependencyReadiness, ...]
) -> ReasonCode | None:
    supplied = {item.experiment_name: item.state for item in dependencies}
    if any(name not in supplied for name in cell.required_experiments):
        return ReasonCode.MISSING_DEPENDENCY_STATUS
    if any(
        supplied[name] is not PublicExecutionState.COMPLETED for name in cell.required_experiments
    ):
        return ReasonCode.UPSTREAM_EXPERIMENT_NOT_COMPLETED
    return None


def expected_seed_count(experiment_name: ExperimentName) -> SeedCount:
    config = active_config.get()
    policy = seed_policy_for(experiment_name)
    if policy is SeedPolicy.COVERAGE_STREAMS:
        return config.sequential.coverage.streams
    if policy is SeedPolicy.UTILITY_STREAMS:
        return config.sequential.utility.streams
    if policy is SeedPolicy.NONE:
        return 0
    raise RuntimeError(f"unhandled seed policy: {policy}")


def execute_dispatched_cell(
    cell: PlannedCell,
    context: ExecutionContext,
) -> CellExecutionResult:
    if cell.identity.experiment_name == ExperimentName.STATISTICAL_SYNTHESIS:
        raise InvalidScientificDataError(
            "Statistical Synthesis requires the dedicated cross-experiment executor"
        )
    artifact_key = scientific_result_artifact_key(cell)
    if context.required_artifact_keys != (artifact_key,):
        raise InvalidScientificDataError(
            "dispatched cell execution requires exactly its scientific-result artifact"
        )
    relative_path = scientific_result_path(cell)
    if cell.identity.experiment_name is ExperimentName.REAL_TRAJECTORY_VALIDATION:
        result = dispatch_real_trajectory_validation(cell, context.workspace_root)
    elif supports_batched_recovery(cell.identity.experiment_name):
        result = dispatch_with_batched_recovery(cell, context, artifact_key)
    else:
        result = execute_scientific_cell(cell, active_config.get())
    digest = atomic_write_model(
        context.workspace_root / relative_path,
        result,
    )
    return CellExecutionResult(
        artifact_index=CellArtifactIndex(
            artifacts=(
                ArtifactIndexEntry(
                    artifact_key=artifact_key,
                    relative_path=relative_path,
                    sha256=digest,
                ),
            )
        ),
        completed_seed_count=context.expected_seed_count,
    )
