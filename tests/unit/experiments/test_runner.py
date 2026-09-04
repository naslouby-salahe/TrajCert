from __future__ import annotations

from pathlib import Path

from tests.unit.conftest import write_artifact_executor
from trajcert.experiments import runner
from trajcert.experiments.artifacts import (
    cell_completion_path,
    cell_failure_path,
    completion_is_compatible,
    scientific_result_artifact_key,
)
from trajcert.experiments.models import (
    CellExecutionResult,
    DependencyReadiness,
    ExecutionContext,
)
from trajcert.experiments.plan import PlannedCell
from trajcert.provenance import SemanticCellIdentity, SemanticCoordinates, VariantCoordinate
from trajcert.storage import (
    CompletionRecord,
    DependencyFingerprint,
    PlanDigest,
    SpecificationDigest,
    read_model,
)
from trajcert.types import (
    EvidenceClass,
    ExperimentName,
    PartitionName,
    PublicExecutionState,
    ReasonCode,
)

_HAND_CASE_EXPERIMENT = ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES
_HAND_CASE_VARIANT = VariantCoordinate(hand_case_index=1)
_HAND_CASE_PARTITION = PartitionName("8-band partition")
_MISSING_CONFIGURATION_REASON = ReasonCode.MISSING_AUTHORITATIVE_CONFIGURATION
_DEPENDENCY = DependencyFingerprint("dependency-fingerprint")
_PLAN_DIGEST = PlanDigest("plan")
_SPECIFICATION = SpecificationDigest("specification")


def _cell(*, required: tuple[ExperimentName, ...] = ()) -> PlannedCell:
    return PlannedCell(
        experiment_order=1,
        cell_ordinal=1,
        identity=SemanticCellIdentity(
            experiment_name=_HAND_CASE_EXPERIMENT,
            coordinates=SemanticCoordinates(
                variant_name=_HAND_CASE_VARIANT,
                partition_name=_HAND_CASE_PARTITION,
            ),
        ),
        evidence_class=EvidenceClass.VALIDATION,
        executable=True,
        invalid_reason=None,
        required_experiments=required,
    )


def _invalid_cell() -> PlannedCell:
    return PlannedCell(
        experiment_order=1,
        cell_ordinal=1,
        identity=SemanticCellIdentity(
            experiment_name=_HAND_CASE_EXPERIMENT,
            coordinates=SemanticCoordinates(
                variant_name=_HAND_CASE_VARIANT,
                partition_name=_HAND_CASE_PARTITION,
            ),
        ),
        evidence_class=EvidenceClass.VALIDATION,
        executable=False,
        invalid_reason=_MISSING_CONFIGURATION_REASON,
        required_experiments=(),
    )


def _context(workspace_root: Path, cell: PlannedCell) -> ExecutionContext:
    return ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=_PLAN_DIGEST,
        scientific_specification_digest=_SPECIFICATION,
        dependency_fingerprint=_DEPENDENCY,
        required_artifact_keys=(scientific_result_artifact_key(cell),),
        expected_seed_count=0,
    )


def _cell_context(workspace_root: Path) -> tuple[PlannedCell, ExecutionContext]:
    cell = _cell()
    return cell, _context(workspace_root, cell)


def _failing_executor(_cell: PlannedCell, _context: ExecutionContext) -> CellExecutionResult:
    raise RuntimeError("synthetic technical failure")


def test_run_cell_executes_and_writes_completion(tmp_path: Path) -> None:
    cell, context = _cell_context(tmp_path)
    outcome = runner.run_cell(cell, context, (), write_artifact_executor, overwrite=False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False
    completion = read_model(cell_completion_path(cell, tmp_path), CompletionRecord)
    assert completion.semantic_cell_key == cell.identity.semantic_cell_key
    assert completion.produced_artifact_keys == (scientific_result_artifact_key(cell),)
    assert completion.expected_seed_count == context.expected_seed_count
    assert completion.completed_seed_count == context.expected_seed_count
    assert len(completion.artifact_sha256_map) == 1


def test_run_cell_reuses_compatible_completion(tmp_path: Path) -> None:
    cell, context = _cell_context(tmp_path)
    _ = runner.run_cell(cell, context, (), write_artifact_executor, overwrite=False)
    outcome = runner.run_cell(cell, context, (), write_artifact_executor, overwrite=False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is True


def test_run_cell_overwrite_recomputes(tmp_path: Path) -> None:
    cell, context = _cell_context(tmp_path)
    _ = runner.run_cell(cell, context, (), write_artifact_executor, overwrite=False)
    outcome = runner.run_cell(cell, context, (), write_artifact_executor, overwrite=True)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False


def test_run_cell_reports_invalid_cell(tmp_path: Path) -> None:
    cell = _invalid_cell()
    context = _context(tmp_path, cell)
    outcome = runner.run_cell(cell, context, (), write_artifact_executor, overwrite=False)
    assert outcome.state is PublicExecutionState.INVALID
    assert outcome.reason == _MISSING_CONFIGURATION_REASON
    assert not cell_completion_path(cell, tmp_path).exists()


def test_run_cell_blocks_on_unready_dependency(tmp_path: Path) -> None:
    required = (ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,)
    cell = _cell(required=required)
    context = _context(tmp_path, cell)
    dependencies = (
        DependencyReadiness(experiment_name=required[0], state=PublicExecutionState.BLOCKED),
    )
    outcome = runner.run_cell(cell, context, dependencies, write_artifact_executor, overwrite=False)
    assert outcome.state is PublicExecutionState.BLOCKED
    assert outcome.reason == ReasonCode.UPSTREAM_EXPERIMENT_NOT_COMPLETED
    assert not cell_completion_path(cell, tmp_path).exists()


def test_run_cell_writes_failure_record_not_completion(tmp_path: Path) -> None:
    cell, context = _cell_context(tmp_path)
    outcome = runner.run_cell(cell, context, (), _failing_executor, overwrite=False)
    assert outcome.state is PublicExecutionState.FAILED
    assert outcome.reason == ReasonCode.TECHNICAL_EXECUTION_FAILURE
    assert not cell_completion_path(cell, tmp_path).exists()
    assert cell_failure_path(cell, tmp_path).exists()


def test_completion_is_incompatible_when_specification_changes(tmp_path: Path) -> None:
    cell, context = _cell_context(tmp_path)
    _ = runner.run_cell(cell, context, (), write_artifact_executor, overwrite=False)
    changed = context.model_copy(
        update={"scientific_specification_digest": SpecificationDigest("other")}
    )
    assert completion_is_compatible(cell, changed, cell_completion_path(cell, tmp_path)) is False
