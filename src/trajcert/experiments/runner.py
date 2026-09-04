from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from functools import partial
from pathlib import Path
from typing import Final, NewType

from pydantic import BaseModel

from trajcert.config import CoverageStressCaseConfig, TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition, partition_name
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.data.synthetic import generate_balanced_prefix_ledger
from trajcert.exceptions import (
    InvalidScientificDataError,
    InvariantViolationError,
    SerializationError,
)
from trajcert.experiments.anytime import (
    CoverageBatchResult,
    combine_coverage_stress_batches,
    coverage_evidence_from_base,
    coverage_stress_batch,
    evaluate_configured_coverage_stress,
    resolve_coverage_stress_case,
    run_anytime_hand_case,
)
from trajcert.experiments.catalog import (
    ExecutionHandler,
    SeedPolicy,
    execution_handler_for,
    seed_policy_for,
    supports_batched_recovery,
)
from trajcert.experiments.comparator_reduction import evaluate_comparator_reduction
from trajcert.experiments.failure_boundaries import (
    FailureBoundaryAxis,
    evaluate_failure_boundary,
    evaluate_optimizer_node_budget,
    evaluate_terminal_selection_asymmetry,
)
from trajcert.experiments.mathematics import (
    anytime_projection_proof_check,
    endpoint_special_case_identity,
    evaluate_legacy_partition_incoherence,
    evaluate_safety_boundary_case,
    information_profile_convexity,
    minimum_compatibility_identity,
    path_information_decomposition,
    population_complexity_proof_check,
    refinement_dominance_identity,
    sharp_set_constructive_identity,
    strict_timing_gain_identity,
)
from trajcert.experiments.plan import ExperimentPlan, PlannedCell
from trajcert.experiments.safety import (
    SafetyCaseEvaluation,
    compatibility_floor_behavior,
    safety_and_intrinsic_impossibility,
    sharpness_against_generic_oracle,
)
from trajcert.experiments.scaling import benchmark_scaling_cell
from trajcert.experiments.sensitivity import (
    SequentialUtilityBatchResult,
    combine_sequential_sensitivity_utility_batches,
    population_sensitivity_utility,
    sequential_sensitivity_utility,
    sequential_sensitivity_utility_batch,
)
from trajcert.experiments.solver_validation import compare_production_solver_to_oracle
from trajcert.experiments.timing import (
    evaluate_partition_coherence,
    evaluate_same_endpoint_different_timing,
)
from trajcert.inference.categorical import append_matured_event, initialize_categorical_state
from trajcert.inference.confidence import CategoricalConfidenceRegion, confidence_sequence_update
from trajcert.inference.envelope import singleton_summary_envelope
from trajcert.inference.projection import project_upper_risk
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import observed_timing_information
from trajcert.math.safety import SafetyBudgetCase, safety_budget_cases
from trajcert.paths import (
    ArtifactFile,
    ExperimentLeaf,
    artifact_path,
    checkpoint_batch_file,
    long_path_safe,
    semantic_cell_path,
    semantic_slug,
)
from trajcert.provenance import (
    ArtifactTypeName,
    CoordinateGrammar,
    DependencyMaterial,
    EnvironmentDigest,
    FailureBoundaryCoordinate,
    ParentArtifactIdentity,
    SensitivityCoordinate,
    VariantName,
    dependency_fingerprint,
)
from trajcert.storage import (
    ArtifactChecksum,
    ArtifactIndexEntry,
    ArtifactKey,
    CellArtifactIndex,
    CompletionRecord,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    SemanticCellKey,
    SpecificationDigest,
    atomic_write_model,
    file_digest,
    model_digest,
    read_model,
    write_completion_last,
)
from trajcert.telemetry import set_current_cell_key
from trajcert.types import (
    BatchIndex,
    BatchSize,
    CaseIndex,
    Count,
    DomainModel,
    ExperimentName,
    FailureBoundaryProbe,
    FailureMessage,
    LawKey,
    LawName,
    PartitionName,
    PublicExecutionState,
    ReasonCode,
    SeedCount,
    SeedIndex,
    SensitivityBudget,
    StreamCount,
)

FailureType = NewType("FailureType", str)


class ScientificArtifactKeyPrefix(StrEnum):
    SCIENTIFIC_RESULT = "scientific-result|"


SCIENTIFIC_RESULT_ARTIFACT_TYPE: Final[ArtifactTypeName] = ArtifactTypeName("scientific-result")


class DependencyReadiness(DomainModel):
    experiment_name: ExperimentName
    state: PublicExecutionState


class ExecutionContext(DomainModel):
    workspace_root: Path
    plan_digest: PlanDigest
    scientific_specification_digest: SpecificationDigest
    dependency_fingerprint: DependencyFingerprint
    required_artifact_keys: tuple[ArtifactKey, ...]
    expected_seed_count: SeedCount


class CellExecutionResult(DomainModel):
    artifact_index: CellArtifactIndex
    completed_seed_count: SeedCount


class RunningRecord(DomainModel):
    semantic_cell_key: SemanticCellKey
    plan_digest: PlanDigest
    dependency_fingerprint: DependencyFingerprint


class FailureRecord(DomainModel):
    semantic_cell_key: SemanticCellKey
    plan_digest: PlanDigest
    dependency_fingerprint: DependencyFingerprint
    failure_type: FailureType
    message: FailureMessage
    execution_state: PublicExecutionState


class CellRunOutcome(DomainModel):
    state: PublicExecutionState
    reused: bool
    completion_path: Path
    failure_path: Path
    reason: ReasonCode | None


class CheckpointRecord(DomainModel):
    semantic_cell_key: SemanticCellKey
    artifact_key: ArtifactKey
    dependency_fingerprint: DependencyFingerprint
    cell_plan_digest: PlanDigest
    batch_index: BatchIndex
    seed_index_start: SeedIndex
    seed_index_stop_exclusive: SeedIndex
    input_artifact_keys: tuple[ArtifactKey, ...]
    input_artifact_digests: tuple[DigestHex, ...]
    result_file_sha256: DigestHex
    completed: bool


class ScientificCellDispatchError(InvariantViolationError):
    pass


class SmokeResult(DomainModel):
    compatible_population_pass: bool
    incompatible_population_pass: bool
    endpoint_special_case_pass: bool
    refinement_pass: bool
    deterministic_confidence_sequence_pass: bool
    singleton_projection_pass: bool
    passed_fixture_count: Count

    @property
    def passed(self) -> bool:
        return self.passed_fixture_count == active_config.get().smoke.fixture_count


CellExecutor = Callable[[PlannedCell, ExecutionContext], CellExecutionResult]


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
        _validate_execution_result(result, context)
        _verify_artifacts(result.artifact_index, context.workspace_root)
        _ = atomic_write_model(
            cell_artifact_index_path(cell, context.workspace_root), result.artifact_index
        )
        completion = _completion_record(cell, context, result)
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


def completion_is_compatible(
    cell: PlannedCell, context: ExecutionContext, completion_path: Path
) -> bool:
    try:
        completion = read_model(completion_path, CompletionRecord)
        if not _completion_identity_matches(cell, context, completion):
            return False
        index_path = cell_artifact_index_path(cell, context.workspace_root)
        index = read_model(index_path, CellArtifactIndex)
        _verify_completion_artifacts(completion, index, context.workspace_root)
    except (SerializationError, InvariantViolationError):
        return False
    return True


def cell_completion_path(cell: PlannedCell, workspace_root: Path) -> Path:
    directory = semantic_cell_path(
        cell.identity.experiment_slug,
        ExperimentLeaf.CHECKPOINTS_EXECUTION,
        cell.identity.path_coordinates,
    )
    return workspace_root / artifact_path(directory, ArtifactFile.COMPLETION)


def cell_running_path(cell: PlannedCell, workspace_root: Path) -> Path:
    return cell_completion_path(cell, workspace_root).with_name(ArtifactFile.RUNNING)


def cell_artifact_index_path(cell: PlannedCell, workspace_root: Path) -> Path:
    return cell_completion_path(cell, workspace_root).with_name(ArtifactFile.ARTIFACT_INDEX)


def cell_checkpoint_batch_path(
    cell: PlannedCell, workspace_root: Path, batch_index: BatchIndex
) -> Path:
    return cell_completion_path(cell, workspace_root).with_name(checkpoint_batch_file(batch_index))


def cell_checkpoint_batch_result_path(
    cell: PlannedCell, workspace_root: Path, batch_index: BatchIndex
) -> Path:
    return cell_completion_path(cell, workspace_root).with_name(
        checkpoint_batch_file(batch_index, result=True)
    )


def cell_failure_path(cell: PlannedCell, workspace_root: Path) -> Path:
    directory = semantic_cell_path(
        cell.identity.experiment_slug,
        ExperimentLeaf.LOGS_FAILURES,
        cell.identity.path_coordinates,
    )
    return workspace_root / artifact_path(directory, ArtifactFile.FAILURE)


def _cell_plan_digest(cell: PlannedCell) -> PlanDigest:
    return PlanDigest(model_digest(cell))


def _completion_identity_matches(
    cell: PlannedCell,
    context: ExecutionContext,
    completion: CompletionRecord,
) -> bool:
    checks = (
        completion.semantic_cell_key == cell.identity.semantic_cell_key,
        completion.cell_plan_digest == _cell_plan_digest(cell),
        completion.scientific_specification_digest == context.scientific_specification_digest,
        completion.dependency_fingerprint == context.dependency_fingerprint,
        completion.required_artifact_keys == context.required_artifact_keys,
        completion.expected_seed_count == context.expected_seed_count,
        completion.completed_seed_count == completion.expected_seed_count,
    )
    return all(checks)


def _validate_execution_result(
    result: CellExecutionResult,
    context: ExecutionContext,
) -> None:
    produced = tuple(entry.artifact_key for entry in result.artifact_index.artifacts)
    if len(produced) != len(set(produced)):
        raise InvariantViolationError("executor produced duplicate artifact keys")
    if any(key not in produced for key in context.required_artifact_keys):
        raise InvariantViolationError("executor omitted a required artifact key")
    if result.completed_seed_count != context.expected_seed_count:
        raise InvariantViolationError("executor returned an incomplete seed count")


def _verify_artifacts(index: CellArtifactIndex, workspace_root: Path) -> None:
    root = workspace_root.resolve()
    for entry in index.artifacts:
        artifact_path = (workspace_root / entry.relative_path).resolve()
        if not artifact_path.is_relative_to(root):
            raise InvariantViolationError("artifact path escapes the workspace root")
        if not long_path_safe(artifact_path).is_file():
            raise InvariantViolationError(
                f"required produced artifact is missing: {entry.artifact_key}"
            )
        if file_digest(artifact_path) != entry.sha256:
            raise InvariantViolationError(
                f"produced artifact checksum mismatch: {entry.artifact_key}"
            )


def _verify_completion_artifacts(
    completion: CompletionRecord,
    index: CellArtifactIndex,
    workspace_root: Path,
) -> None:
    indexed = tuple(entry.artifact_key for entry in index.artifacts)
    if indexed != completion.produced_artifact_keys:
        raise SerializationError("persisted artifact index does not match completion record")
    expected_checksums = tuple(
        ArtifactChecksum(artifact_key=entry.artifact_key, sha256=entry.sha256)
        for entry in sorted(index.artifacts, key=lambda item: item.artifact_key)
    )
    if expected_checksums != completion.artifact_sha256_map:
        raise SerializationError("persisted artifact checksums do not match completion record")
    _verify_artifacts(index, workspace_root)


def _completion_record(
    cell: PlannedCell,
    context: ExecutionContext,
    result: CellExecutionResult,
) -> CompletionRecord:
    produced = tuple(entry.artifact_key for entry in result.artifact_index.artifacts)
    checksums = tuple(
        _checksum(entry)
        for entry in sorted(result.artifact_index.artifacts, key=lambda item: item.artifact_key)
    )
    return CompletionRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        cell_plan_digest=_cell_plan_digest(cell),
        scientific_specification_digest=context.scientific_specification_digest,
        dependency_fingerprint=context.dependency_fingerprint,
        required_artifact_keys=context.required_artifact_keys,
        produced_artifact_keys=produced,
        artifact_sha256_map=checksums,
        completed_seed_count=result.completed_seed_count,
        expected_seed_count=context.expected_seed_count,
    )


def _checksum(entry: ArtifactIndexEntry) -> ArtifactChecksum:
    return ArtifactChecksum(artifact_key=entry.artifact_key, sha256=entry.sha256)


def scientific_specification_digest() -> SpecificationDigest:
    return SpecificationDigest(model_digest(active_config.get()))


def cell_dependency_material(
    workspace_root: Path,
    plan: ExperimentPlan,
    cell: PlannedCell,
    scientific_specification: SpecificationDigest,
    environment_dependency_digest: EnvironmentDigest,
) -> DependencyMaterial:
    required = set(cell.required_experiments)
    parents = tuple(item for item in plan.cells if item.identity.experiment_name in required)
    parent_identities = tuple(
        identity
        for parent in parents
        if (identity := _parent_artifact_identity(parent, workspace_root)) is not None
    )
    return DependencyMaterial(
        artifact_type=SCIENTIFIC_RESULT_ARTIFACT_TYPE,
        semantic_cell=cell.identity,
        scientific_specification_digest=scientific_specification,
        environment_dependency_digest=environment_dependency_digest,
        parents=parent_identities,
    )


def cell_dependency_fingerprint(
    workspace_root: Path,
    plan: ExperimentPlan,
    cell: PlannedCell,
    scientific_specification: SpecificationDigest,
    environment_dependency_digest: EnvironmentDigest,
) -> DependencyFingerprint:
    material = cell_dependency_material(
        workspace_root,
        plan,
        cell,
        scientific_specification,
        environment_dependency_digest,
    )
    return dependency_fingerprint(material)


def _parent_artifact_identity(
    parent: PlannedCell, workspace_root: Path
) -> ParentArtifactIdentity | None:
    index_path = cell_artifact_index_path(parent, workspace_root)
    if not index_path.is_file():
        return None
    index = read_model(index_path, CellArtifactIndex)
    artifact_key = scientific_result_artifact_key(parent)
    entry = next((item for item in index.artifacts if item.artifact_key == artifact_key), None)
    if entry is None:
        return None
    return ParentArtifactIdentity(artifact_key=artifact_key, scientific_content_digest=entry.sha256)


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


def execute_scientific_cell(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    if not cell.executable:
        raise ScientificCellDispatchError("planned-invalid cell cannot be scientifically executed")
    _ = active_config.set(config)
    handler_name = execution_handler_for(cell.identity.experiment_name)
    if handler_name is None:
        raise ScientificCellDispatchError(
            "experiment lacks a registered dispatch handler or authoritative scientific coordinates"
        )
    handler = _EXECUTION_DISPATCH.get(handler_name)
    if handler is None:
        raise ScientificCellDispatchError(
            "experiment lacks a registered dispatch handler or authoritative "
            + f"scientific coordinates: {cell.identity.experiment_name}"
        )
    return handler(cell)


def _dispatch_legacy_partition_incoherence(cell: PlannedCell) -> DomainModel:
    gamma = cell.identity.coordinates.gamma
    variant = cell.identity.coordinates.variant_name
    if (
        gamma is None
        or variant is None
        or not variant.startswith(CoordinateGrammar.LEGACY_Q_PREFIX)
    ):
        raise ScientificCellDispatchError("legacy incoherence cell is missing Gamma or q")
    return evaluate_legacy_partition_incoherence(
        gamma=gamma,
        q=float(variant.removeprefix(CoordinateGrammar.LEGACY_Q_PREFIX)),
    )


def _dispatch_refinement_dominance_identity(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    fine, coarse = _refinement_inputs(cell)
    return refinement_dominance_identity(
        fine=fine,
        coarse_partition=coarse,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_strict_timing_gain_identity(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    fine, coarse = _refinement_inputs(cell)
    return strict_timing_gain_identity(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_partition_coherence(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    fine, coarse = _refinement_inputs(cell)
    return evaluate_partition_coherence(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_same_endpoint_different_timing(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    partition = _partition_from_coordinates(cell)
    rho = _direct_rho(cell)
    no_timing = _population_summary(
        _law_from_name(LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_NO_TIMING]),
        partition,
    )
    with_timing = _population_summary(
        _law_from_name(LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING]),
        partition,
    )
    return evaluate_same_endpoint_different_timing(
        no_timing=no_timing,
        with_timing=with_timing,
        sensitivity_budget=rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )


def _dispatch_strict_timing_gain(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    fine, coarse = _refinement_inputs(cell)
    return evaluate_partition_coherence(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_sharpness_against_generic_oracle(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = _partition_from_coordinates(cell)
    return sharpness_against_generic_oracle(
        summary=_summary_from_coordinates(cell),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        oracle_digits=config.numerics.oracle_digits,
        oracle_bracket_width=config.numerics.oracle_bracket_width,
        sharpness_diagnostic_offset=config.numerics.sharpness_diagnostic_offset,
        comparison_guard=config.numerics.comparison_guard,
        population_law=law,
        population_band_count=partition.band_count,
    )


def _dispatch_population_sensitivity_utility(cell: PlannedCell) -> DomainModel:
    return population_sensitivity_utility(
        summary=_summary_from_coordinates(cell),
        sensitivity_budget=_direct_rho(cell),
    )


def _dispatch_sequential_sensitivity_utility(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name)
    finest = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    return sequential_sensitivity_utility(
        parameters=law,
        fine_partition=finest,
        sensitivity_budget=_direct_rho(cell),
    )


def _dispatch_anytime_hand_case(cell: PlannedCell) -> DomainModel:
    partition = _partition_from_coordinates(cell)
    case_index = _variant_index(cell.identity.coordinates.variant_name)
    return run_anytime_hand_case(case_index, partition)


def _dispatch_computational_scaling(cell: PlannedCell) -> DomainModel:
    bands = cell.identity.coordinates.scaling_band_count
    if bands is None:
        raise ScientificCellDispatchError("scaling cell is missing K")
    return benchmark_scaling_cell(bands)


def _summary_path_information_decomposition(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    config = active_config.get()
    return path_information_decomposition(
        summary,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_information_profile_convexity(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    config = active_config.get()
    return information_profile_convexity(
        summary,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_minimum_compatibility_identity(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    return minimum_compatibility_identity(summary, active_config.get().numerics.identity_atol)


def _summary_sharp_set_constructive_identity(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    config = active_config.get()
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    return sharp_set_constructive_identity(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.comparison_guard,
    )


def _summary_endpoint_special_case_identity(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    return endpoint_special_case_identity(summary, active_config.get().numerics.identity_atol)


def _summary_production_solver_vs_independent_oracle(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    config = active_config.get()
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = _partition_from_coordinates(cell)
    return compare_production_solver_to_oracle(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.comparison_guard,
        population_law=law,
        population_band_count=partition.band_count,
    )


def _summary_compatibility_floor_behavior(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    config = active_config.get()
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = _partition_from_coordinates(cell)
    return compatibility_floor_behavior(
        summary,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.compatibility_floor_offset,
        config.numerics.comparison_guard,
        population_law=law,
        population_band_count=partition.band_count,
    )


def _summary_safety_boundary_identity(cell: PlannedCell, summary: ObservableSummary) -> DomainModel:
    config = active_config.get()
    case = _safety_case(summary, cell.identity.coordinates.variant_name)
    return evaluate_safety_boundary_case(
        summary,
        case,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_comparator_reduction(cell: PlannedCell, summary: ObservableSummary) -> DomainModel:
    del cell
    return evaluate_comparator_reduction(summary)


def _dispatch_summary_handler(
    handler: Callable[[PlannedCell, ObservableSummary], DomainModel],
    summary_factory: Callable[[PlannedCell], ObservableSummary],
    cell: PlannedCell,
) -> DomainModel:
    return handler(cell, summary_factory(cell))


def _dispatch_cell_independent(
    handler: Callable[[], DomainModel], cell: PlannedCell
) -> DomainModel:
    del cell
    return handler()


def _summary_from_coordinates(cell: PlannedCell) -> ObservableSummary:
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = _partition_from_coordinates(cell)
    return _population_summary(law, partition)


def _law_level_finest_summary(cell: PlannedCell) -> ObservableSummary:
    config = active_config.get()
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name)
    partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    return _population_summary(law, partition)


def _refinement_inputs(
    cell: PlannedCell,
) -> tuple[ObservableSummary, TrajectoryPartition]:
    comparison = cell.identity.coordinates.comparison_pair_name
    if comparison is None:
        raise ScientificCellDispatchError("refinement cell is missing its comparison pair")
    fine_text, separator, coarse_text = comparison.partition(CoordinateGrammar.COMPARISON_PAIR)
    if not separator:
        raise ScientificCellDispatchError("invalid comparison-pair encoding")
    fine = _partition_named(PartitionName(fine_text))
    coarse = _partition_named(PartitionName(coarse_text))
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name)
    return _population_summary(law, fine), coarse


def _population_summary(
    law: LawParameters,
    partition: TrajectoryPartition,
) -> ObservableSummary:
    return summarize_full_law(
        partition,
        build_full_law(law, partition.band_count),
        active_config.get().numerics.comparison_guard,
    )


def _law_from_name(law_name: LawName | None) -> LawParameters:
    if law_name is None:
        raise ScientificCellDispatchError("scientific cell is missing its synthetic law")
    for key, law in active_config.get().ordered_laws:
        if LAW_DISPLAY_NAMES[key] == law_name:
            return LawParameters(
                key=key,
                name=law_name,
                theta=law.theta,
                q1=law.q1,
                q0=law.q0,
                lambda1=law.lambda1,
                lambda0=law.lambda0,
            )
    raise ScientificCellDispatchError(f"unknown synthetic law: {law_name}")


def _partition_from_coordinates(cell: PlannedCell) -> TrajectoryPartition:
    requested = cell.identity.coordinates.partition_name
    if requested is None:
        raise ScientificCellDispatchError("scientific cell is missing its partition")
    return _partition_named(requested)


def _partition_named(name: PartitionName) -> TrajectoryPartition:
    config = active_config.get()
    for bands in (*config.grids.partitions, *config.grids.scaling_bands):
        if partition_name(bands) == name:
            return build_partition(
                max(config.method.finest_bands, bands),
                bands,
                config.method.terminal_horizon,
            )
    raise ScientificCellDispatchError(f"unknown configured partition: {name}")


def _rho_from_offset(
    summary: ObservableSummary,
    coordinate: SensitivityCoordinate | None,
) -> SensitivityBudget:
    prefix = CoordinateGrammar.RHO_OFFSET_PREFIX
    if coordinate is None or not coordinate.startswith(prefix):
        raise ScientificCellDispatchError("rho-offset cell is missing its sensitivity coordinate")
    offset = float(coordinate[len(prefix) :])
    return (observed_timing_information(summary) or 0.0) + offset


def _direct_rho(cell: PlannedCell) -> SensitivityBudget:
    rho = cell.identity.coordinates.rho
    if rho is None:
        raise ScientificCellDispatchError("scientific cell is missing its rho coordinate")
    return rho


def _variant_index(variant: VariantName | None) -> CaseIndex:
    prefix = CoordinateGrammar.HAND_CASE_PREFIX
    if variant is None or not variant.startswith(prefix):
        raise ScientificCellDispatchError("cell is missing its expected variant index")
    return int(variant[len(prefix) :])


def _safety_case(
    summary: ObservableSummary,
    variant: VariantName | None,
) -> SafetyBudgetCase:
    if variant is None:
        raise ScientificCellDispatchError("safety cell is missing its case variant")
    for case in safety_budget_cases(summary):
        if semantic_slug(case.name) == variant:
            return case
    raise ScientificCellDispatchError(f"unknown safety case: {variant}")


def _safety_intrinsic_case(cell: PlannedCell) -> SafetyCaseEvaluation:
    config = active_config.get()
    summary = _law_level_finest_summary(cell)
    result = safety_and_intrinsic_impossibility(
        summary=summary,
        oracle_digits=config.numerics.oracle_digits,
        identity_atol=config.numerics.identity_atol,
    )
    variant = cell.identity.coordinates.variant_name
    if variant is None:
        raise ScientificCellDispatchError("safety/impossibility cell is missing its case variant")
    for evaluation in result.cases:
        if semantic_slug(evaluation.case.name) == variant:
            return evaluation
    raise ScientificCellDispatchError(f"unknown safety/impossibility case: {variant}")


def _coverage_stress_case_config(
    cell: PlannedCell, config: TrajCertConfig
) -> CoverageStressCaseConfig:
    variant = cell.identity.coordinates.variant_name
    if variant is None:
        raise ScientificCellDispatchError(
            "coverage-stress cell is missing its configured case name"
        )
    for case in config.study_design.coverage_stress_cases:
        if case.name != variant:
            continue
        expected_law = LAW_DISPLAY_NAMES[case.law]
        expected_partition = partition_name(case.band_count)
        if cell.identity.coordinates.synthetic_law_name != expected_law:
            raise ScientificCellDispatchError(
                "coverage-stress law coordinate does not match configuration"
            )
        if cell.identity.coordinates.partition_name != expected_partition:
            raise ScientificCellDispatchError(
                "coverage-stress partition coordinate does not match configuration"
            )
        return case
    raise ScientificCellDispatchError(f"unknown configured coverage-stress case: {variant}")


def _coverage_stress_case(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    case = _coverage_stress_case_config(cell, config)
    return evaluate_configured_coverage_stress(case)


def _execute_failure_boundary(cell: PlannedCell) -> DomainModel:
    coordinate = cell.identity.coordinates.failure_boundary_axis_and_level
    if coordinate is None:
        raise ScientificCellDispatchError("failure-boundary cell is missing axis/level")
    axis_text, separator, value_text = coordinate.partition(CoordinateGrammar.ASSIGNMENT)
    if not separator:
        raise ScientificCellDispatchError("invalid failure-boundary coordinate")
    axis = FailureBoundaryAxis(axis_text)
    if axis is FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY:
        q1_text, separator, q0_text = value_text.partition(CoordinateGrammar.TERMINAL_Q0_SEPARATOR)
        if not separator or not q1_text.startswith(CoordinateGrammar.TERMINAL_Q1_PREFIX):
            raise ScientificCellDispatchError("invalid terminal-selection-asymmetry coordinate")
        return evaluate_terminal_selection_asymmetry(
            q1=float(q1_text.removeprefix(CoordinateGrammar.TERMINAL_Q1_PREFIX)),
            q0=float(q0_text),
        )
    if axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET:
        return evaluate_optimizer_node_budget(int(value_text))
    parsed_axis, level = _failure_coordinate(coordinate)
    return evaluate_failure_boundary(parsed_axis, level)


_EXECUTION_DISPATCH: dict[ExecutionHandler, Callable[[PlannedCell], DomainModel]] = {
    ExecutionHandler.LEGACY_PARTITION_INCOHERENCE: _dispatch_legacy_partition_incoherence,
    ExecutionHandler.REFINEMENT_DOMINANCE: _dispatch_refinement_dominance_identity,
    ExecutionHandler.STRICT_TIMING_IDENTITY: _dispatch_strict_timing_gain_identity,
    ExecutionHandler.PARTITION_COHERENCE: _dispatch_partition_coherence,
    ExecutionHandler.SAME_ENDPOINT_TIMING: _dispatch_same_endpoint_different_timing,
    ExecutionHandler.STRICT_TIMING_GAIN: _dispatch_strict_timing_gain,
    ExecutionHandler.SAFETY_BOUNDARY: partial(
        _dispatch_summary_handler, _summary_safety_boundary_identity, _law_level_finest_summary
    ),
    ExecutionHandler.SHARPNESS: _dispatch_sharpness_against_generic_oracle,
    ExecutionHandler.SAFETY_INTRINSIC: _safety_intrinsic_case,
    ExecutionHandler.COVERAGE_STRESS: _coverage_stress_case,
    ExecutionHandler.POPULATION_UTILITY: _dispatch_population_sensitivity_utility,
    ExecutionHandler.SEQUENTIAL_UTILITY: _dispatch_sequential_sensitivity_utility,
    ExecutionHandler.ANYTIME_HAND_CASE: _dispatch_anytime_hand_case,
    ExecutionHandler.FAILURE_BOUNDARY: _execute_failure_boundary,
    ExecutionHandler.COMPUTATIONAL_SCALING: _dispatch_computational_scaling,
    ExecutionHandler.SUMMARY_PATH_INFORMATION: partial(
        _dispatch_summary_handler,
        _summary_path_information_decomposition,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_INFORMATION_PROFILE: partial(
        _dispatch_summary_handler, _summary_information_profile_convexity, _summary_from_coordinates
    ),
    ExecutionHandler.SUMMARY_MINIMUM_COMPATIBILITY: partial(
        _dispatch_summary_handler,
        _summary_minimum_compatibility_identity,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_SHARP_SET: partial(
        _dispatch_summary_handler,
        _summary_sharp_set_constructive_identity,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_ENDPOINT: partial(
        _dispatch_summary_handler,
        _summary_endpoint_special_case_identity,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_SOLVER_ORACLE: partial(
        _dispatch_summary_handler,
        _summary_production_solver_vs_independent_oracle,
        _summary_from_coordinates,
    ),
    ExecutionHandler.SUMMARY_COMPATIBILITY_FLOOR: partial(
        _dispatch_summary_handler, _summary_compatibility_floor_behavior, _summary_from_coordinates
    ),
    ExecutionHandler.SUMMARY_COMPARATOR_REDUCTION: partial(
        _dispatch_summary_handler, _summary_comparator_reduction, _summary_from_coordinates
    ),
    ExecutionHandler.ANYTIME_PROJECTION_PROOF: partial(
        _dispatch_cell_independent, anytime_projection_proof_check
    ),
    ExecutionHandler.POPULATION_COMPLEXITY_PROOF: partial(
        _dispatch_cell_independent, population_complexity_proof_check
    ),
}
if set(_EXECUTION_DISPATCH) != set(ExecutionHandler) - {ExecutionHandler.SYNTHESIS}:
    raise RuntimeError("runner dispatch must define every direct execution handler exactly once")


def _failure_coordinate(
    coordinate: FailureBoundaryCoordinate,
) -> tuple[FailureBoundaryAxis, FailureBoundaryProbe]:
    axis_text, separator, value_text = coordinate.partition(CoordinateGrammar.ASSIGNMENT)
    if not separator:
        raise ScientificCellDispatchError("invalid failure-boundary coordinate")
    axis = FailureBoundaryAxis(axis_text)
    if axis is FailureBoundaryAxis.RISK_OFFSET:
        if value_text.startswith(CoordinateGrammar.NEGATIVE_PREFIX):
            return axis, -float(value_text.removeprefix(CoordinateGrammar.NEGATIVE_PREFIX))
        if value_text.startswith(CoordinateGrammar.NONNEGATIVE_PREFIX):
            return axis, float(value_text.removeprefix(CoordinateGrammar.NONNEGATIVE_PREFIX))
    if axis in {FailureBoundaryAxis.PATH_RESOLUTION, FailureBoundaryAxis.MATURED_SAMPLE_SIZE}:
        return axis, int(value_text)
    return axis, float(value_text)


def scientific_result_artifact_key(cell: PlannedCell) -> ArtifactKey:
    return ArtifactKey(
        f"{ScientificArtifactKeyPrefix.SCIENTIFIC_RESULT}{cell.identity.semantic_cell_key}"
    )


def scientific_result_path(cell: PlannedCell) -> Path:
    return (
        semantic_cell_path(
            cell.identity.experiment_slug,
            ExperimentLeaf.EVALUATION_RECORDS,
            cell.identity.path_coordinates,
        )
        / ArtifactFile.SCIENTIFIC_RESULT
    )


def read_verified_scientific_result[ModelT: BaseModel](
    cell: PlannedCell,
    workspace_root: Path,
    model_type: type[ModelT],
) -> ModelT:
    completion, index = verified_upstream_completion_and_index(cell, workspace_root)
    entry = index.artifacts[0]
    expected_path = scientific_result_path(cell)
    if entry.relative_path != expected_path:
        raise InvalidScientificDataError(
            "persisted scientific-result path does not match the planned semantic cell"
        )
    result_path = workspace_root / entry.relative_path
    if file_digest(result_path) != entry.sha256:
        raise InvalidScientificDataError("persisted scientific-result checksum is stale")
    expected_checksum = ArtifactChecksum(
        artifact_key=entry.artifact_key,
        sha256=entry.sha256,
    )
    if completion.artifact_sha256_map != (expected_checksum,):
        raise InvalidScientificDataError(
            "completion checksum map does not match the persisted scientific result"
        )
    return read_model(result_path, model_type)


def verified_upstream_completion_and_index(
    cell: PlannedCell,
    workspace_root: Path,
) -> tuple[CompletionRecord, CellArtifactIndex]:
    if not cell.executable:
        raise InvalidScientificDataError(
            "Statistical Synthesis cannot consume a planned-invalid upstream cell"
        )
    completion = read_model(cell_completion_path(cell, workspace_root), CompletionRecord)
    index = read_model(cell_artifact_index_path(cell, workspace_root), CellArtifactIndex)
    expected_key = scientific_result_artifact_key(cell)
    _validate_upstream_completion(completion, cell, expected_key, index)
    entry = index.artifacts[0]
    _validate_upstream_artifact_entry(entry, cell, workspace_root, expected_key)
    expected_checksum = ArtifactChecksum(
        artifact_key=entry.artifact_key,
        sha256=entry.sha256,
    )
    if completion.artifact_sha256_map != (expected_checksum,):
        raise InvalidScientificDataError("upstream completion checksum map is stale")
    return completion, index


def _validate_upstream_completion(
    completion: CompletionRecord,
    cell: PlannedCell,
    expected_key: ArtifactKey,
    index: CellArtifactIndex,
) -> None:
    if completion.semantic_cell_key != cell.identity.semantic_cell_key:
        raise InvalidScientificDataError("upstream completion semantic identity is stale")
    expected_plan_digest = PlanDigest(model_digest(cell))
    if completion.cell_plan_digest != expected_plan_digest:
        raise InvalidScientificDataError("upstream completion cell-plan digest is stale")
    if completion.produced_artifact_keys != (expected_key,):
        raise InvalidScientificDataError(
            "upstream completion must expose exactly one persisted scientific result"
        )
    if len(index.artifacts) != 1:
        raise InvalidScientificDataError(
            "upstream scientific cell must have exactly one authoritative result artifact"
        )
    if completion.completed_seed_count != completion.expected_seed_count:
        raise InvalidScientificDataError("upstream completion has an incomplete seed count")


def _validate_upstream_artifact_entry(
    entry: ArtifactIndexEntry,
    cell: PlannedCell,
    workspace_root: Path,
    expected_key: ArtifactKey,
) -> None:
    if entry.artifact_key != expected_key:
        raise InvalidScientificDataError("upstream artifact index contains the wrong result key")
    if entry.relative_path != scientific_result_path(cell):
        raise InvalidScientificDataError("upstream artifact index contains a stale result path")
    result_path = (workspace_root / entry.relative_path).resolve()
    root = workspace_root.resolve()
    if not result_path.is_relative_to(root) or not long_path_safe(result_path).is_file():
        raise InvalidScientificDataError("upstream scientific-result artifact is missing")
    if file_digest(result_path) != entry.sha256:
        raise InvalidScientificDataError("upstream scientific-result checksum mismatch")


def _batch_seed_ranges(total: StreamCount, batch_size: BatchSize) -> tuple[range, ...]:
    ranges: list[range] = []
    start = 0
    while start < total:
        stop = min(start + batch_size, total)
        ranges.append(range(start, stop))
        start = stop
    return tuple(ranges)


def _checkpoint_batch_valid(
    checkpoint: CheckpointRecord,
    cell: PlannedCell,
    context: ExecutionContext,
    artifact_key: ArtifactKey,
    batch_index: BatchIndex,
    seed_index_start: SeedIndex,
    seed_index_stop_exclusive: SeedIndex,
    result_path: Path,
) -> bool:
    if not checkpoint.completed:
        return False
    if (
        checkpoint.semantic_cell_key != cell.identity.semantic_cell_key
        or checkpoint.artifact_key != artifact_key
        or checkpoint.dependency_fingerprint != context.dependency_fingerprint
        or checkpoint.cell_plan_digest != _cell_plan_digest(cell)
        or checkpoint.batch_index != batch_index
        or checkpoint.seed_index_start != seed_index_start
        or checkpoint.seed_index_stop_exclusive != seed_index_stop_exclusive
    ):
        return False
    return file_digest(result_path) == checkpoint.result_file_sha256


def _recover_batch[PayloadT: DomainModel](
    cell: PlannedCell,
    context: ExecutionContext,
    artifact_key: ArtifactKey,
    batch_index: BatchIndex,
    seed_index_start: SeedIndex,
    seed_index_stop_exclusive: SeedIndex,
    payload_type: type[PayloadT],
    compute: Callable[[], PayloadT],
) -> PayloadT:
    workspace_root = context.workspace_root
    checkpoint_path = cell_checkpoint_batch_path(cell, workspace_root, batch_index)
    result_path = cell_checkpoint_batch_result_path(cell, workspace_root, batch_index)
    if checkpoint_path.is_file() and result_path.is_file():
        try:
            checkpoint = read_model(checkpoint_path, CheckpointRecord)
            if _checkpoint_batch_valid(
                checkpoint,
                cell,
                context,
                artifact_key,
                batch_index,
                seed_index_start,
                seed_index_stop_exclusive,
                result_path,
            ):
                return read_model(result_path, payload_type)
        except SerializationError:
            pass
    payload = compute()
    digest = atomic_write_model(result_path, payload)
    checkpoint = CheckpointRecord(
        semantic_cell_key=cell.identity.semantic_cell_key,
        artifact_key=artifact_key,
        dependency_fingerprint=context.dependency_fingerprint,
        cell_plan_digest=_cell_plan_digest(cell),
        batch_index=batch_index,
        seed_index_start=seed_index_start,
        seed_index_stop_exclusive=seed_index_stop_exclusive,
        input_artifact_keys=(),
        input_artifact_digests=(),
        result_file_sha256=digest,
        completed=True,
    )
    _ = atomic_write_model(checkpoint_path, checkpoint)
    return payload


def _coverage_stress_cell_with_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    config = active_config.get()
    case = _coverage_stress_case_config(cell, config)
    parameters, partition, rho, _ = resolve_coverage_stress_case(case)
    stream_count = config.sequential.coverage.streams
    batch_size = config.sequential.coverage.batch_size
    batches: list[CoverageBatchResult] = []
    for batch_index, seed_range in enumerate(_batch_seed_ranges(stream_count, batch_size)):
        batches.append(
            _recover_batch(
                cell,
                context,
                artifact_key,
                batch_index,
                seed_range.start,
                seed_range.stop,
                CoverageBatchResult,
                lambda seed_range=seed_range, batch_index=batch_index: coverage_stress_batch(
                    parameters, partition, rho, seed_range, batch_index
                ),
            )
        )
    base = combine_coverage_stress_batches(parameters, tuple(batches))
    return coverage_evidence_from_base(case, base)


def _sequential_utility_cell_with_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    config = active_config.get()
    parameters = _law_from_name(cell.identity.coordinates.synthetic_law_name)
    fine_partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    sensitivity_budget = _direct_rho(cell)
    stream_count = config.sequential.utility.streams
    batch_size = config.sequential.utility.batch_size
    batches: list[SequentialUtilityBatchResult] = []
    for batch_index, seed_range in enumerate(_batch_seed_ranges(stream_count, batch_size)):
        batches.append(
            _recover_batch(
                cell,
                context,
                artifact_key,
                batch_index,
                seed_range.start,
                seed_range.stop,
                SequentialUtilityBatchResult,
                lambda seed_range=seed_range,
                batch_index=batch_index: sequential_sensitivity_utility_batch(
                    parameters, fine_partition, sensitivity_budget, seed_range, batch_index
                ),
            )
        )
    return combine_sequential_sensitivity_utility_batches(sensitivity_budget, tuple(batches))


def _dispatch_with_batched_recovery(
    cell: PlannedCell, context: ExecutionContext, artifact_key: ArtifactKey
) -> DomainModel:
    policy = seed_policy_for(cell.identity.experiment_name)
    if policy is SeedPolicy.COVERAGE_STREAMS:
        return _coverage_stress_cell_with_recovery(cell, context, artifact_key)
    if policy is SeedPolicy.UTILITY_STREAMS:
        return _sequential_utility_cell_with_recovery(cell, context, artifact_key)
    raise ScientificCellDispatchError("experiment does not support batched recovery")


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
    result = (
        _dispatch_with_batched_recovery(cell, context, artifact_key)
        if supports_batched_recovery(cell.identity.experiment_name)
        else execute_scientific_cell(cell, active_config.get())
    )
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


def run_smoke_fixtures(config: TrajCertConfig) -> SmokeResult:
    _ = active_config.set(config)
    principal = _parameters(LawKey.TIMING_TERMINAL_HARMFUL_LATE)
    timing = _parameters(LawKey.TIMING_HARMFUL_LATE)
    fine = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    coarse = build_partition(
        config.method.finest_bands,
        config.smoke.coarse_bands,
        config.method.terminal_horizon,
    )
    endpoint = build_partition(
        config.method.finest_bands,
        1,
        config.method.terminal_horizon,
    )
    principal_fine = _population_summary(principal, fine)
    timing_fine = _population_summary(timing, fine)

    principal_tau = observed_timing_information(principal_fine) or 0.0
    compatible = sharp_risk_set(
        principal_fine,
        principal_tau + config.smoke.compatible_offset,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    compatible_pass = compatible.latent_risk is not None

    timing_tau = observed_timing_information(timing_fine) or 0.0
    incompatible = sharp_risk_set(
        timing_fine,
        timing_tau / 2.0,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    incompatible_pass = timing_tau > 0.0 and incompatible.latent_risk is None

    endpoint_summary = _population_summary(principal, endpoint)
    endpoint_tau = observed_timing_information(endpoint_summary) or 0.0
    endpoint_pass = abs(endpoint_tau) <= config.numerics.identity_atol

    refinement = evaluate_partition_coherence(
        fine=principal_fine,
        coarse_partition=coarse,
        sensitivity_budget=principal_tau + config.smoke.refinement_offset,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )
    refinement_pass = refinement.passed

    confidence_pass = _confidence_smoke(principal)
    projection_pass = _projection_smoke(principal)
    checks = (
        compatible_pass,
        incompatible_pass,
        endpoint_pass,
        refinement_pass,
        confidence_pass,
        projection_pass,
    )
    return SmokeResult(
        compatible_population_pass=compatible_pass,
        incompatible_population_pass=incompatible_pass,
        endpoint_special_case_pass=endpoint_pass,
        refinement_pass=refinement_pass,
        deterministic_confidence_sequence_pass=confidence_pass,
        singleton_projection_pass=projection_pass,
        passed_fixture_count=sum(checks),
    )


def _confidence_smoke(parameters: LawParameters) -> bool:
    config = active_config.get()
    partition = build_partition(
        config.method.finest_bands,
        config.smoke.coverage_stress_bands,
        config.method.terminal_horizon,
    )
    ledger = generate_balanced_prefix_ledger(
        parameters,
        partition,
        0,
        config.smoke.coverage_stress_events,
    )
    state = initialize_categorical_state(ledger.identity, partition)
    running: CategoricalConfidenceRegion | None = None
    for event in mature_ledger(ledger, partition):
        state = append_matured_event(state, event)
        update = confidence_sequence_update(
            state,
            config.confidence.anytime_delta,
            config.numerics.anytime_root_atol,
            running,
        )
        running = update.running
    return running is not None and running.matured_count == config.smoke.coverage_stress_events


def _projection_smoke(parameters: LawParameters) -> bool:
    config = active_config.get()
    partition = build_partition(
        config.method.finest_bands,
        config.smoke.coverage_stress_bands,
        config.method.terminal_horizon,
    )
    summary = _population_summary(parameters, partition)
    tau = observed_timing_information(summary) or 0.0
    rho = tau + config.smoke.compatible_offset
    population = sharp_risk_set(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    if population.latent_risk is None:
        return False
    projection = project_upper_risk(
        singleton_summary_envelope(summary),
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.comparison_guard,
        config.numerics.arbitrary_precision_bits,
        config.numerics.outer_gap,
        config.numerics.outer_max_nodes,
    )
    error = abs(projection.proven_upper - population.latent_risk.upper)
    return error <= config.numerics.identity_atol


def _parameters(key: LawKey) -> LawParameters:
    law = active_config.get().laws[key]
    return LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )
