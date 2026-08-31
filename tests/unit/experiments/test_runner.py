from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import cast

import pytest

from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.ledger import LedgerIdentity
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments import runner
from trajcert.experiments.anytime import HandCaseResult
from trajcert.experiments.inventory import InventoryValidationResult
from trajcert.experiments.mathematics import IdentityResult
from trajcert.experiments.plan import PlannedCell, build_plan, cells_for_experiment
from trajcert.provenance import (
    ExperimentNameValue,
    ProducerComponentName,
    SemanticCellIdentity,
    SemanticCoordinates,
    VariantName,
)
from trajcert.storage import (
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    ProvenanceFingerprint,
    SpecificationDigest,
    file_digest,
    read_model,
)
from trajcert.types import (
    ActionChannelId,
    ClientId,
    EpochId,
    EvidenceClass,
    PartitionName,
    PublicExecutionState,
    ReasonCode,
    ScientificState,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SMOKE_FIXTURE_COUNT = 6
_SHA256_HEX_LENGTH = 64
_INVENTORY = ExperimentNameValue("Scientific and Data Inventory")
_HAND_CASE_EXPERIMENT = ExperimentNameValue("Anytime Implementation Hand Cases")
_HAND_CASE_VARIANT = VariantName("hand-case-01")
_HAND_CASE_PARTITION = PartitionName("8-band partition")
_MISSING_CONFIGURATION_REASON = ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION")
_MANIFEST_DIGEST = DigestHex("0" * 64)
_COMPONENT_NAMES = (
    ProducerComponentName("inference/categorical.py"),
    ProducerComponentName("inference/confidence.py"),
    ProducerComponentName("inference/envelope.py"),
    ProducerComponentName("inference/projection.py"),
    ProducerComponentName("inference/certification.py"),
)


def _cell(
    *,
    executable: bool = True,
    invalid_reason: ReasonCode | None = None,
    required: tuple[ExperimentNameValue, ...] = (),
) -> PlannedCell:
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
        executable=executable,
        invalid_reason=invalid_reason,
        required_experiments=required,
    )


def _invalid_cell() -> PlannedCell:
    return _cell(executable=False, invalid_reason=_MISSING_CONFIGURATION_REASON)


def _context(workspace_root: Path, cell: PlannedCell) -> runner.ExecutionContext:
    return runner.ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=PlanDigest("plan"),
        scientific_specification_digest=SpecificationDigest("specification"),
        scientific_dependency_digest=SpecificationDigest("dependency"),
        provenance_fingerprint=ProvenanceFingerprint("provenance"),
        dependency_fingerprint=DependencyFingerprint("dependency-fingerprint"),
        manifest_digest=_MANIFEST_DIGEST,
        required_artifact_keys=(runner.scientific_result_artifact_key(cell),),
        expected_seed_count=0,
    )


def _write_artifact_executor(
    cell: PlannedCell, context: runner.ExecutionContext
) -> runner.CellExecutionResult:
    relative_path = runner.scientific_result_path(cell)
    path = context.workspace_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text("artifact-payload", encoding="utf-8")
    return runner.CellExecutionResult(
        artifact_index=CellArtifactIndex(
            artifacts=(
                ArtifactIndexEntry(
                    artifact_key=runner.scientific_result_artifact_key(cell),
                    relative_path=relative_path,
                    sha256=file_digest(path),
                ),
            )
        ),
        completed_seed_count=context.expected_seed_count,
        metrics_complete=True,
        statistics_complete=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
    )


def _missing_artifact_executor(
    cell: PlannedCell, context: runner.ExecutionContext
) -> runner.CellExecutionResult:
    return runner.CellExecutionResult(
        artifact_index=CellArtifactIndex(
            artifacts=(
                ArtifactIndexEntry(
                    artifact_key=runner.scientific_result_artifact_key(cell),
                    relative_path=runner.scientific_result_path(cell),
                    sha256=DigestHex("0" * _SHA256_HEX_LENGTH),
                ),
            )
        ),
        completed_seed_count=context.expected_seed_count,
        metrics_complete=True,
        statistics_complete=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
    )


def _raise_executor(
    cell: PlannedCell, context: runner.ExecutionContext
) -> runner.CellExecutionResult:
    del cell, context
    raise RuntimeError("executor exploded")


def _target_identity() -> LedgerIdentity:
    return LedgerIdentity(
        client_id=ClientId("client"),
        action_channel_id=ActionChannelId("channel"),
        epoch_id=EpochId("epoch"),
    )


def _clean_lineage_artifact(key: str) -> runner.RuntimeLineageArtifact:
    identity = _target_identity()
    return runner.RuntimeLineageArtifact(
        artifact_key=ArtifactKey(key),
        client_id=identity.client_id,
        action_channel_id=identity.action_channel_id,
        epoch_id=identity.epoch_id,
    )


def _static_dependency(
    component: ProducerComponentName,
    client_id: ClientId,
    *,
    input_classes: tuple[runner.ScientificInputClass, ...] = (
        runner.ScientificInputClass.CONFIG_VALUES,
    ),
) -> runner.StaticComponentDependency:
    return runner.StaticComponentDependency(
        producer_component=component,
        scientific_input_classes=input_classes,
        scientific_client_ids=(client_id,),
    )


def _static_dependencies(client_id: ClientId) -> tuple[runner.StaticComponentDependency, ...]:
    return tuple(_static_dependency(component, client_id) for component in _COMPONENT_NAMES)


def test_run_cell_rejects_planned_invalid_cell(tmp_path: Path) -> None:
    cell = _invalid_cell()
    outcome = runner.run_cell(cell, _context(tmp_path, cell), (), _write_artifact_executor, False)
    assert outcome.state is PublicExecutionState.INVALID
    assert outcome.reused is False
    assert outcome.reason == cell.invalid_reason


def test_run_cell_blocks_on_missing_dependency_status(tmp_path: Path) -> None:
    cell = _cell(required=(_INVENTORY,))
    outcome = runner.run_cell(cell, _context(tmp_path, cell), (), _write_artifact_executor, False)
    assert outcome.state is PublicExecutionState.BLOCKED
    assert outcome.reason == ReasonCode("MISSING_DEPENDENCY_STATUS")


def test_run_cell_blocks_on_uncompleted_dependency(tmp_path: Path) -> None:
    cell = _cell(required=(_INVENTORY,))
    dependencies = (
        runner.DependencyReadiness(experiment_name=_INVENTORY, state=PublicExecutionState.READY),
    )
    outcome = runner.run_cell(
        cell, _context(tmp_path, cell), dependencies, _write_artifact_executor, False
    )
    assert outcome.state is PublicExecutionState.BLOCKED
    assert outcome.reason == ReasonCode("UPSTREAM_EXPERIMENT_NOT_COMPLETED")


def test_run_cell_executes_and_writes_completion_record(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    outcome = runner.run_cell(cell, context, (), _write_artifact_executor, False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False
    assert outcome.reason is None
    completion = read_model(runner.cell_completion_path(cell, tmp_path), CompletionRecord)
    assert completion.semantic_cell_key == cell.identity.semantic_cell_key
    assert completion.expected_artifact_count == 1
    assert completion.expected_seed_count == 0
    assert not runner.cell_running_path(cell, tmp_path).exists()


def test_run_cell_reuses_compatible_completion(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    _ = runner.run_cell(cell, context, (), _write_artifact_executor, False)
    outcome = runner.run_cell(cell, context, (), _write_artifact_executor, False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is True
    assert outcome.reason is None


def test_run_cell_overwrite_reruns_execution(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    _ = runner.run_cell(cell, context, (), _write_artifact_executor, False)
    outcome = runner.run_cell(cell, context, (), _write_artifact_executor, True)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False


def test_run_cell_records_executor_failure(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    outcome = runner.run_cell(cell, context, (), _raise_executor, False)
    assert outcome.state is PublicExecutionState.FAILED
    assert outcome.reason == ReasonCode("TECHNICAL_EXECUTION_FAILURE")
    failure = read_model(runner.cell_failure_path(cell, tmp_path), runner.FailureRecord)
    assert failure.message == "executor exploded"
    assert not runner.cell_completion_path(cell, tmp_path).exists()
    assert not runner.cell_running_path(cell, tmp_path).exists()


def test_run_cell_records_missing_artifact_failure(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    outcome = runner.run_cell(cell, context, (), _missing_artifact_executor, False)
    assert outcome.state is PublicExecutionState.FAILED
    assert outcome.reason == ReasonCode("TECHNICAL_EXECUTION_FAILURE")
    failure = read_model(runner.cell_failure_path(cell, tmp_path), runner.FailureRecord)
    assert failure.failure_type == "InvariantViolationError"
    assert "required produced artifact is missing" in failure.message
    assert not runner.cell_completion_path(cell, tmp_path).exists()


def test_dependency_block_reason_requires_all_statuses() -> None:
    cell = _cell(required=(_INVENTORY,))
    assert runner.dependency_block_reason(cell, ()) == ReasonCode("MISSING_DEPENDENCY_STATUS")


def test_dependency_block_reason_requires_completion() -> None:
    cell = _cell(required=(_INVENTORY,))
    completed = (
        runner.DependencyReadiness(
            experiment_name=_INVENTORY, state=PublicExecutionState.COMPLETED
        ),
    )
    ready = (
        runner.DependencyReadiness(experiment_name=_INVENTORY, state=PublicExecutionState.READY),
    )
    assert runner.dependency_block_reason(cell, completed) is None
    assert runner.dependency_block_reason(cell, ready) == ReasonCode(
        "UPSTREAM_EXPERIMENT_NOT_COMPLETED"
    )


def test_completion_is_compatible_true_after_valid_run(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    _ = runner.run_cell(cell, context, (), _write_artifact_executor, False)
    completion_path = runner.cell_completion_path(cell, tmp_path)
    assert runner.completion_is_compatible(cell, context, completion_path) is True


def test_completion_is_compatible_false_after_artifact_tamper(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    _ = runner.run_cell(cell, context, (), _write_artifact_executor, False)
    artifact_path = tmp_path / runner.scientific_result_path(cell)
    _ = artifact_path.write_text("tampered", encoding="utf-8")
    completion_path = runner.cell_completion_path(cell, tmp_path)
    assert runner.completion_is_compatible(cell, context, completion_path) is False


def test_completion_is_compatible_false_on_context_mismatch(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    _ = runner.run_cell(cell, context, (), _write_artifact_executor, False)
    mismatched = context.model_copy(update={"manifest_digest": DigestHex("1" * _SHA256_HEX_LENGTH)})
    completion_path = runner.cell_completion_path(cell, tmp_path)
    assert runner.completion_is_compatible(cell, mismatched, completion_path) is False


def test_completion_is_compatible_false_when_index_missing(tmp_path: Path) -> None:
    cell = _cell()
    context = _context(tmp_path, cell)
    _ = runner.run_cell(cell, context, (), _write_artifact_executor, False)
    runner.cell_artifact_index_path(cell, tmp_path).unlink()
    completion_path = runner.cell_completion_path(cell, tmp_path)
    assert runner.completion_is_compatible(cell, context, completion_path) is False


def test_cell_path_helpers_follow_semantic_layout(tmp_path: Path) -> None:
    cell = _cell()
    completion = runner.cell_completion_path(cell, tmp_path)
    running = runner.cell_running_path(cell, tmp_path)
    index = runner.cell_artifact_index_path(cell, tmp_path)
    failure = runner.cell_failure_path(cell, tmp_path)
    assert completion.parent == running.parent == index.parent
    assert completion.name == "COMPLETED.json"
    assert running.name == "RUNNING.json"
    assert index.name == "artifact_index.json"
    assert failure.name == "failure.json"
    assert failure.parent != completion.parent
    assert "checkpoints/execution" in completion.as_posix()
    assert "logs/failures" in failure.as_posix()


def test_producer_component_digest_is_deterministic() -> None:
    first = runner.producer_component_digest(_REPO_ROOT, _INVENTORY)
    second = runner.producer_component_digest(_REPO_ROOT, _INVENTORY)
    assert first == second
    assert len(first) == _SHA256_HEX_LENGTH


def test_producer_component_digest_rejects_unregistered_experiment(tmp_path: Path) -> None:
    with pytest.raises(InvalidScientificDataError, match="missing producer-component registration"):
        _ = runner.producer_component_digest(
            tmp_path, ExperimentNameValue("Unregistered Experiment")
        )


def test_scientific_dependency_digest_is_deterministic() -> None:
    component = DigestHex("a" * _SHA256_HEX_LENGTH)
    first = runner.scientific_dependency_digest(SpecificationDigest("spec"), "cell", component)
    second = runner.scientific_dependency_digest(SpecificationDigest("spec"), "cell", component)
    assert first == second
    assert first != runner.scientific_dependency_digest(
        SpecificationDigest("other"), "cell", component
    )


def test_cell_dependency_fingerprint_is_deterministic_without_parents(tmp_path: Path) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cell = cells_for_experiment(plan, _HAND_CASE_EXPERIMENT)[0]
    scientific_dependency = SpecificationDigest("dependency")
    first = runner.cell_dependency_fingerprint(tmp_path, plan, cell, scientific_dependency)
    second = runner.cell_dependency_fingerprint(tmp_path, plan, cell, scientific_dependency)
    assert first == second


def test_expected_seed_count_reflects_stream_configuration() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    assert (
        runner.expected_seed_count(ExperimentNameValue("Anytime Coverage Stress"), config)
        == config.sequential.coverage.streams
    )
    assert (
        runner.expected_seed_count(ExperimentNameValue("Sequential Sensitivity Utility"), config)
        == config.sequential.utility.streams
    )
    assert runner.expected_seed_count(_HAND_CASE_EXPERIMENT, config) == 0


def test_scientific_result_artifact_key_and_path_are_consistent() -> None:
    cell = _cell()
    key = runner.scientific_result_artifact_key(cell)
    path = runner.scientific_result_path(cell)
    assert key == ArtifactKey(f"scientific-result|{cell.identity.semantic_cell_key}")
    assert path.name == "scientific_result.json"
    assert "evaluations/records" in path.as_posix()


def test_static_dependency_audit_passes_exact_component_set() -> None:
    identity = _target_identity()
    assert (
        runner.static_dependency_audit(identity, _static_dependencies(identity.client_id)) is True
    )


def test_static_dependency_audit_rejects_duplicate_components() -> None:
    identity = _target_identity()
    duplicate = _static_dependencies(identity.client_id)[0]
    dependencies = (*_static_dependencies(identity.client_id), duplicate)
    assert runner.static_dependency_audit(identity, dependencies) is False


def test_static_dependency_audit_rejects_missing_components() -> None:
    identity = _target_identity()
    dependencies = _static_dependencies(identity.client_id)[1:]
    assert runner.static_dependency_audit(identity, dependencies) is False


def test_static_dependency_audit_rejects_empty_input_classes() -> None:
    identity = _target_identity()
    dependencies = tuple(
        _static_dependency(component, identity.client_id, input_classes=())
        for component in _COMPONENT_NAMES
    )
    assert runner.static_dependency_audit(identity, dependencies) is False


def test_static_dependency_audit_rejects_foreign_client() -> None:
    identity = _target_identity()
    foreign = _static_dependency(_COMPONENT_NAMES[0], ClientId("other"))
    dependencies = (*_static_dependencies(identity.client_id)[1:], foreign)
    assert runner.static_dependency_audit(identity, dependencies) is False


def test_runtime_lineage_audit_passes_clean_lineage() -> None:
    identity = _target_identity()
    passed, violations = runner.runtime_lineage_audit(
        identity, ArtifactKey("root"), (_clean_lineage_artifact("root"),)
    )
    assert passed is True
    assert violations == ()


def test_runtime_lineage_audit_flags_foreign_client_statistics() -> None:
    identity = _target_identity()
    artifact = runner.RuntimeLineageArtifact(
        artifact_key=ArtifactKey("root"),
        foreign_client_statistics=True,
    )
    passed, violations = runner.runtime_lineage_audit(identity, ArtifactKey("root"), (artifact,))
    assert passed is False
    assert violations == (ArtifactKey("root"),)


def test_runtime_lineage_audit_flags_missing_parent() -> None:
    identity = _target_identity()
    artifact = runner.RuntimeLineageArtifact(
        artifact_key=ArtifactKey("root"),
        parent_artifact_keys=(ArtifactKey("missing"),),
    )
    passed, violations = runner.runtime_lineage_audit(identity, ArtifactKey("root"), (artifact,))
    assert passed is False
    assert violations == (ArtifactKey("missing"),)


def test_runtime_lineage_audit_rejects_duplicate_keys() -> None:
    identity = _target_identity()
    artifact = _clean_lineage_artifact("root")
    with pytest.raises(InvalidScientificDataError, match="duplicate artifact keys"):
        _ = runner.runtime_lineage_audit(identity, ArtifactKey("root"), (artifact, artifact))


def test_runtime_lineage_audit_rejects_cycle() -> None:
    identity = _target_identity()
    first = runner.RuntimeLineageArtifact(
        artifact_key=ArtifactKey("a"), parent_artifact_keys=(ArtifactKey("b"),)
    )
    second = runner.RuntimeLineageArtifact(
        artifact_key=ArtifactKey("b"), parent_artifact_keys=(ArtifactKey("a"),)
    )
    with pytest.raises(InvalidScientificDataError, match="cycle"):
        _ = runner.runtime_lineage_audit(identity, ArtifactKey("a"), (first, second))


def test_audit_local_validity_targets_requires_targets() -> None:
    with pytest.raises(InvalidScientificDataError, match="at least one bound root"):
        _ = runner.audit_local_validity_targets((), ())


def test_audit_local_validity_passes_clean_target() -> None:
    identity = _target_identity()
    root = ArtifactKey("root")
    lineage = (
        runner.RuntimeLineageArtifact(
            artifact_key=root,
            parent_artifact_keys=(ArtifactKey("leaf"),),
            client_id=identity.client_id,
            action_channel_id=identity.action_channel_id,
            epoch_id=identity.epoch_id,
        ),
        runner.RuntimeLineageArtifact(
            artifact_key=ArtifactKey("leaf"),
            client_id=identity.client_id,
            action_channel_id=identity.action_channel_id,
            epoch_id=identity.epoch_id,
        ),
    )
    result = runner.audit_local_validity_targets(
        _static_dependencies(identity.client_id),
        (
            runner.LocalValidityTarget(
                target_identity=identity, root_artifact_key=root, lineage_artifacts=lineage
            ),
        ),
    )
    assert result.passed is True
    assert result.static_dependency_pass is True
    assert result.runtime_lineage_pass is True
    assert result.audited_root_count == 1
    assert result.foreign_scientific_parent_count == 0
    assert result.violating_artifact_keys == ()


def test_audit_local_validity_reports_runtime_violations() -> None:
    identity = _target_identity()
    root = ArtifactKey("root")
    lineage = (
        runner.RuntimeLineageArtifact(
            artifact_key=root,
            parent_artifact_keys=(ArtifactKey("leaf"),),
            client_id=identity.client_id,
            action_channel_id=identity.action_channel_id,
            epoch_id=identity.epoch_id,
        ),
        runner.RuntimeLineageArtifact(
            artifact_key=ArtifactKey("leaf"),
            foreign_model_updates=True,
        ),
    )
    result = runner.audit_local_validity_targets(
        _static_dependencies(identity.client_id),
        (
            runner.LocalValidityTarget(
                target_identity=identity, root_artifact_key=root, lineage_artifacts=lineage
            ),
        ),
    )
    assert result.passed is False
    assert result.static_dependency_pass is True
    assert result.runtime_lineage_pass is False
    assert result.violating_artifact_keys == (ArtifactKey("leaf"),)


def test_execute_scientific_cell_dispatches_proof_checks() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    projection = cells_for_experiment(plan, ExperimentNameValue("Anytime Projection Proof Check"))[
        0
    ]
    complexity = cells_for_experiment(
        plan, ExperimentNameValue("Population Complexity Proof Check")
    )[0]
    projection_result = cast(IdentityResult, runner.execute_scientific_cell(projection, config))
    complexity_result = cast(IdentityResult, runner.execute_scientific_cell(complexity, config))
    assert projection_result.passed is True
    assert complexity_result.passed is True


def test_execute_scientific_cell_dispatches_inventory() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    inventory = cells_for_experiment(plan, _INVENTORY)[0]
    result = cast(InventoryValidationResult, runner.execute_scientific_cell(inventory, config))
    assert result.valid is True
    assert result.configured_law_count == len(tuple(config.ordered_laws))


def test_execute_scientific_cell_rejects_planned_invalid_cell() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    with pytest.raises(runner.ScientificCellDispatchError, match="planned-invalid"):
        _ = runner.execute_scientific_cell(_invalid_cell(), config)


def test_execute_scientific_cell_rejects_unregistered_experiment() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    cell = PlannedCell(
        experiment_order=1,
        cell_ordinal=1,
        identity=SemanticCellIdentity(
            experiment_name=ExperimentNameValue("Unregistered Experiment"),
            coordinates=SemanticCoordinates(),
        ),
        evidence_class=EvidenceClass.VALIDATION,
        executable=True,
        invalid_reason=None,
        required_experiments=(),
    )
    with pytest.raises(runner.ScientificCellDispatchError, match="registered dispatch handler"):
        _ = runner.execute_scientific_cell(cell, config)


def test_execute_dispatched_cell_rejects_statistical_synthesis(tmp_path: Path) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    cell = cells_for_experiment(plan, ExperimentNameValue("Statistical Synthesis"))[0]
    with pytest.raises(InvalidScientificDataError, match="dedicated cross-experiment executor"):
        _ = runner.execute_dispatched_cell(cell, _context(tmp_path, cell), config)


def test_execute_dispatched_cell_requires_exact_result_artifact(tmp_path: Path) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    cell = _cell()
    context = _context(tmp_path, cell).model_copy(
        update={"required_artifact_keys": (ArtifactKey("scientific-result|other"),)}
    )
    with pytest.raises(InvalidScientificDataError, match="exactly its scientific-result artifact"):
        _ = runner.execute_dispatched_cell(cell, context, config)


def test_dispatched_cell_round_trip_through_run_cell(tmp_path: Path) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    cell = _cell()
    context = _context(tmp_path, cell)
    executor = partial(runner.execute_dispatched_cell, config=config)
    outcome = runner.run_cell(cell, context, (), executor, False)
    assert outcome.state is PublicExecutionState.COMPLETED
    assert outcome.reused is False
    completion, index = runner.verified_upstream_completion_and_index(cell, tmp_path)
    assert completion.produced_artifact_keys == (runner.scientific_result_artifact_key(cell),)
    assert len(index.artifacts) == 1
    readback = runner.read_verified_scientific_result(cell, tmp_path, HandCaseResult)
    assert readback.passed is True
    assert readback.expected_state is ScientificState.INSUFFICIENT_EVIDENCE


def test_verified_upstream_completion_rejects_planned_invalid_cell(tmp_path: Path) -> None:
    with pytest.raises(InvalidScientificDataError, match="planned-invalid"):
        _ = runner.verified_upstream_completion_and_index(_invalid_cell(), tmp_path)


def test_verified_upstream_completion_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(SerializationError):
        _ = runner.verified_upstream_completion_and_index(_cell(), tmp_path)


def test_verified_upstream_completion_rejects_stale_artifact_checksum(tmp_path: Path) -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    cell = _cell()
    context = _context(tmp_path, cell)
    executor = partial(runner.execute_dispatched_cell, config=config)
    _ = runner.run_cell(cell, context, (), executor, False)
    artifact_path = tmp_path / runner.scientific_result_path(cell)
    _ = artifact_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="checksum mismatch"):
        _ = runner.verified_upstream_completion_and_index(cell, tmp_path)


def test_run_smoke_fixtures_passes_all_production_fixtures() -> None:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    result = runner.run_smoke_fixtures(config)
    assert result.passed is True
    assert result.passed_fixture_count == _SMOKE_FIXTURE_COUNT
