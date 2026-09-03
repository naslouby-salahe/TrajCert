from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from trajcert.experiments.plan import PlannedCell
from trajcert.experiments.runner import (
    SCIENTIFIC_RESULT_ARTIFACT_TYPE,
    DependencyReadiness,
    ExecutionContext,
    FailureRecord,
    FailureType,
    cell_artifact_index_path,
    cell_completion_path,
    cell_failure_path,
    cell_running_path,
    scientific_result_path,
)
from trajcert.experiments.status import (
    CellStatus,
    ExperimentStatus,
    aggregate_experiment_status,
    inspect_cell_status,
)
from trajcert.provenance import (
    ArtifactOwner,
    CodeCommit,
    EnvironmentDigest,
    ExecutionGroup,
    ProducerComponentName,
    ReusableArtifactEnvelope,
    SchemaName,
    SemanticCellIdentity,
    SemanticCoordinates,
    VariantName,
)
from trajcert.storage import (
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    ProvenanceFingerprint,
    SemanticCellKey,
    SpecificationDigest,
    atomic_write_model,
    model_digest,
)
from trajcert.types import (
    EvidenceClass,
    ExperimentName,
    FailureMessage,
    PublicExecutionState,
    ReasonCode,
)

_EXPERIMENT_NAME = ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK
_MIXED_STATUS_CELL_COUNT = 4


def _cell(executable: bool = True, required: tuple[ExperimentName, ...] = ()) -> PlannedCell:
    return PlannedCell(
        experiment_order=2,
        cell_ordinal=1,
        identity=SemanticCellIdentity(
            experiment_name=_EXPERIMENT_NAME,
            coordinates=SemanticCoordinates(gamma=1.5, variant_name=VariantName("q=0.1")),
        ),
        evidence_class=EvidenceClass.VALIDATION,
        executable=executable,
        invalid_reason=(None if executable else ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION")),
        required_experiments=required,
    )


def _envelope() -> ReusableArtifactEnvelope:
    cell = _cell()
    return ReusableArtifactEnvelope(
        artifact_key=ArtifactKey("scientific-result|legacy-cell"),
        artifact_type=SCIENTIFIC_RESULT_ARTIFACT_TYPE,
        artifact_owner=ArtifactOwner(str(cell.identity.experiment_name)),
        producer_component=ProducerComponentName("test-component"),
        semantic_cell_key=cell.identity.semantic_cell_key,
        semantic_coordinates=cell.identity.coordinates,
        experiment_name=cell.identity.experiment_name,
        classification=cell.evidence_class,
        execution_group=ExecutionGroup("execution-group"),
        scientific_specification_digest=SpecificationDigest("spec-digest"),
        scientific_dependency_digest=SpecificationDigest("dependency-digest"),
        provenance_fingerprint=ProvenanceFingerprint("provenance-digest"),
        dependency_fingerprint=DependencyFingerprint("fingerprint"),
        implementation_component_digest=DigestHex("manifest-digest"),
        environment_dependency_digest=EnvironmentDigest("env"),
        plan_digest=DigestHex("plan-digest"),
        cell_plan_digest=PlanDigest(str(model_digest(cell))),
        status=PublicExecutionState.COMPLETED,
        method_name=None,
        baseline_name=None,
        dataset_name=None,
        dataset_checksum=None,
        synthetic_law_name=cell.identity.coordinates.synthetic_law_name,
        partition_name=cell.identity.coordinates.partition_name,
        rho=None,
        beta=None,
        delta=None,
        environment_lock_digest=EnvironmentDigest("env"),
        code_commit=CodeCommit("commit"),
        seed_set_keys=(),
        parent_artifact_keys=(),
        parent_artifact_digests=(),
        input_paths=(),
        canonical_active_path=scientific_result_path(cell),
        schema_name=SchemaName("ReusableArtifactEnvelope"),
        schema_version=1,
    )


def _context(workspace_root: Path) -> ExecutionContext:
    return ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=PlanDigest("plan-digest"),
        scientific_specification_digest=SpecificationDigest("spec-digest"),
        scientific_dependency_digest=SpecificationDigest("dependency-digest"),
        provenance_fingerprint=ProvenanceFingerprint("provenance-digest"),
        dependency_fingerprint=DependencyFingerprint("fingerprint"),
        manifest_digest=DigestHex("manifest-digest"),
        required_artifact_keys=(ArtifactKey("scientific-result|legacy-cell"),),
        expected_seed_count=0,
        reusable_artifact_envelope=_envelope(),
    )


def _completed_record(cell: PlannedCell, context: ExecutionContext) -> CompletionRecord:
    return CompletionRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        cell_plan_digest=PlanDigest(str(model_digest(cell))),
        scientific_specification_digest=context.scientific_specification_digest,
        scientific_dependency_digest=context.scientific_dependency_digest,
        provenance_fingerprint=context.provenance_fingerprint,
        dependency_fingerprint=context.dependency_fingerprint,
        manifest_digest=context.manifest_digest,
        required_artifact_keys=context.required_artifact_keys,
        produced_artifact_keys=(),
        expected_artifact_count=0,
        artifact_sha256_map=(),
        completed_seed_count=context.expected_seed_count,
        expected_seed_count=context.expected_seed_count,
        metrics_complete=True,
        statistics_complete=True,
        schema_validation_pass=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
        exit_status=0,
    )


def _write_raw(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(payload, encoding="utf-8")


def test_inspect_cell_status_reports_invalid_cell() -> None:
    cell = _cell(executable=False)
    result = inspect_cell_status(cell, _context(Path("/nonexistent")), ())
    assert result.state is PublicExecutionState.INVALID
    assert result.reason == ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION")


def test_inspect_cell_status_ready_without_artifacts(tmp_path: Path) -> None:
    cell = _cell()
    result = inspect_cell_status(cell, _context(tmp_path), ())
    assert result.state is PublicExecutionState.READY
    assert result.reason is None


def test_inspect_cell_status_blocked_missing_dependency_status() -> None:
    cell = _cell(required=(ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,))
    result = inspect_cell_status(cell, _context(Path("/nonexistent")), ())
    assert result.state is PublicExecutionState.BLOCKED
    assert result.reason == ReasonCode("MISSING_DEPENDENCY_STATUS")


def test_inspect_cell_status_blocked_uncompleted_dependency() -> None:
    cell = _cell(required=(ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,))
    dependencies = (
        DependencyReadiness(
            experiment_name=ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,
            state=PublicExecutionState.READY,
        ),
    )
    result = inspect_cell_status(cell, _context(Path("/nonexistent")), dependencies)
    assert result.state is PublicExecutionState.BLOCKED
    assert result.reason == ReasonCode("UPSTREAM_EXPERIMENT_NOT_COMPLETED")


def test_inspect_cell_status_completed_with_compatible_completion(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path)
    _ = atomic_write_model(cell_completion_path(cell, tmp_path), _completed_record(cell, context))
    _ = atomic_write_model(
        cell_artifact_index_path(cell, tmp_path), CellArtifactIndex(artifacts=())
    )
    result = inspect_cell_status(cell, context, ())
    assert result.state is PublicExecutionState.COMPLETED
    assert result.reason is None


def test_inspect_cell_status_blocked_by_stale_completion(tmp_path: Path) -> None:
    cell = _cell()
    _write_raw(cell_completion_path(cell, tmp_path), "{not valid completion json")
    result = inspect_cell_status(cell, _context(tmp_path), ())
    assert result.state is PublicExecutionState.BLOCKED
    assert result.reason == ReasonCode("STALE_OR_INCOMPATIBLE_COMPLETION")


def test_inspect_cell_status_running_when_running_file_present(tmp_path: Path) -> None:
    cell = _cell()
    _write_raw(cell_running_path(cell, tmp_path), "running marker")
    result = inspect_cell_status(cell, _context(tmp_path), ())
    assert result.state is PublicExecutionState.RUNNING
    assert result.reason is None


def test_inspect_cell_status_failed_with_matching_failure(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path)
    record = FailureRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        plan_digest=context.plan_digest,
        dependency_fingerprint=context.dependency_fingerprint,
        failure_type=FailureType("RuntimeError"),
        message=FailureMessage("boom"),
        execution_state=PublicExecutionState.FAILED,
    )
    _ = atomic_write_model(cell_failure_path(cell, tmp_path), record)
    result = inspect_cell_status(cell, context, ())
    assert result.state is PublicExecutionState.FAILED
    assert result.reason == ReasonCode("TECHNICAL_EXECUTION_FAILURE")


def test_inspect_cell_status_invalid_with_data_validation_failure(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path)
    record = FailureRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        plan_digest=context.plan_digest,
        dependency_fingerprint=context.dependency_fingerprint,
        failure_type=FailureType("InvalidProbabilityError"),
        message=FailureMessage("bad probability"),
        execution_state=PublicExecutionState.INVALID,
    )
    _ = atomic_write_model(cell_failure_path(cell, tmp_path), record)
    result = inspect_cell_status(cell, context, ())
    assert result.state is PublicExecutionState.INVALID
    assert result.reason == ReasonCode("DATA_VALIDATION_FAILURE")


def test_inspect_cell_status_failed_with_invalid_failure_record(tmp_path: Path) -> None:
    cell = _cell()
    _write_raw(cell_failure_path(cell, tmp_path), "{invalid failure json")
    result = inspect_cell_status(cell, _context(tmp_path), ())
    assert result.state is PublicExecutionState.FAILED
    assert result.reason == ReasonCode("INVALID_FAILURE_RECORD")


def test_inspect_cell_status_ready_when_failure_digest_mismatches(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path)
    stale = context.model_copy(update={"plan_digest": PlanDigest("different-plan")})
    record = FailureRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        plan_digest=stale.plan_digest,
        dependency_fingerprint=context.dependency_fingerprint,
        failure_type=FailureType("RuntimeError"),
        message=FailureMessage("boom"),
        execution_state=PublicExecutionState.FAILED,
    )
    _ = atomic_write_model(cell_failure_path(cell, tmp_path), record)
    result = inspect_cell_status(cell, context, ())
    assert result.state is PublicExecutionState.READY
    assert result.reason is None


def test_aggregate_experiment_status_rejects_mismatched_count() -> None:
    statuses = (_cell_status(PublicExecutionState.READY),)
    with pytest.raises(ValueError, match="cell-status count does not match"):
        _ = aggregate_experiment_status(_EXPERIMENT_NAME, statuses, declared_cells=2)


def test_aggregate_experiment_status_invalid_when_zero_declared_cells() -> None:
    result = aggregate_experiment_status(_EXPERIMENT_NAME, (), declared_cells=0)
    assert result.state is PublicExecutionState.INVALID
    assert result.total_cells == 0


def test_aggregate_experiment_status_invalid_when_all_invalid() -> None:
    statuses = (_cell_status(PublicExecutionState.INVALID),)
    result = aggregate_experiment_status(_EXPERIMENT_NAME, statuses, declared_cells=1)
    assert result.state is PublicExecutionState.INVALID
    assert result.invalid_cells == 1


def test_aggregate_experiment_status_failed_takes_precedence() -> None:
    statuses = (
        _cell_status(PublicExecutionState.FAILED),
        _cell_status(PublicExecutionState.RUNNING),
    )
    result = aggregate_experiment_status(_EXPERIMENT_NAME, statuses, declared_cells=2)
    assert result.state is PublicExecutionState.FAILED


def test_aggregate_experiment_status_running_when_any_running() -> None:
    statuses = (
        _cell_status(PublicExecutionState.RUNNING),
        _cell_status(PublicExecutionState.READY),
    )
    result = aggregate_experiment_status(_EXPERIMENT_NAME, statuses, declared_cells=2)
    assert result.state is PublicExecutionState.RUNNING


def test_aggregate_experiment_status_blocked_when_any_blocked() -> None:
    statuses = (
        _cell_status(PublicExecutionState.BLOCKED),
        _cell_status(PublicExecutionState.READY),
    )
    result = aggregate_experiment_status(_EXPERIMENT_NAME, statuses, declared_cells=2)
    assert result.state is PublicExecutionState.BLOCKED


def test_aggregate_experiment_status_completed_when_all_terminal() -> None:
    statuses = (
        _cell_status(PublicExecutionState.COMPLETED),
        _cell_status(PublicExecutionState.INVALID),
    )
    result = aggregate_experiment_status(_EXPERIMENT_NAME, statuses, declared_cells=2)
    assert result.state is PublicExecutionState.COMPLETED
    assert result.completed_cells == 1
    assert result.invalid_cells == 1


def test_aggregate_experiment_status_ready_when_any_ready() -> None:
    statuses = (
        _cell_status(PublicExecutionState.READY),
        _cell_status(PublicExecutionState.NOT_STARTED),
    )
    result = aggregate_experiment_status(_EXPERIMENT_NAME, statuses, declared_cells=2)
    assert result.state is PublicExecutionState.READY


def test_aggregate_experiment_status_not_started_without_ready_cells() -> None:
    statuses = (_cell_status(PublicExecutionState.NOT_STARTED),)
    result = aggregate_experiment_status(_EXPERIMENT_NAME, statuses, declared_cells=1)
    assert result.state is PublicExecutionState.NOT_STARTED
    assert result.ready_cells == 0


def _cell_status(state: PublicExecutionState) -> CellStatus:
    return CellStatus(
        semantic_cell_key=SemanticCellKey("key"),
        state=state,
        reason=None,
    )


def test_aggregate_experiment_status_round_trips_counts() -> None:
    statuses = (
        _cell_status(PublicExecutionState.COMPLETED),
        _cell_status(PublicExecutionState.FAILED),
        _cell_status(PublicExecutionState.BLOCKED),
        _cell_status(PublicExecutionState.READY),
    )
    result = aggregate_experiment_status(
        _EXPERIMENT_NAME, statuses, declared_cells=_MIXED_STATUS_CELL_COUNT
    )
    assert isinstance(result, ExperimentStatus)
    assert result.experiment_name == _EXPERIMENT_NAME
    assert result.total_cells == _MIXED_STATUS_CELL_COUNT
    assert result.completed_cells == 1
    assert result.failed_cells == 1
    assert result.blocked_cells == 1
    assert result.ready_cells == 1


def test_experiment_status_validates_nonnegative_cell_counts() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        _ = ExperimentStatus(
            experiment_name=_EXPERIMENT_NAME,
            state=PublicExecutionState.READY,
            total_cells=-1,
            completed_cells=0,
            invalid_cells=0,
            failed_cells=0,
            blocked_cells=0,
            running_cells=0,
            ready_cells=0,
        )
