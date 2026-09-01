from __future__ import annotations

import ast
from collections.abc import Callable
from enum import StrEnum
from functools import partial
from hashlib import sha256
from pathlib import Path
from typing import Final, NewType

from pydantic import BaseModel, Field

from trajcert.config import TrajCertConfig, active_config
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.maturity import mature_ledger
from trajcert.data.partitions import TrajectoryPartition, build_partition, partition_name
from trajcert.data.summaries import ObservableSummary, summarize_full_law
from trajcert.data.synthetic import generate_balanced_prefix_ledger
from trajcert.exceptions import (
    InvalidScientificDataError,
    InvariantViolationError,
    SerializationError,
)
from trajcert.experiments.anytime import evaluate_configured_coverage_stress, run_anytime_hand_case
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
    population_sensitivity_utility,
    sequential_sensitivity_utility,
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
from trajcert.paths import ExperimentLeaf, long_path_safe, semantic_cell_path, semantic_slug
from trajcert.provenance import (
    FailureBoundaryCoordinate,
    ProducerComponentName,
    SensitivityCoordinate,
    VariantName,
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
    ProvenanceFingerprint,
    SemanticCellKey,
    SpecificationDigest,
    atomic_write_model,
    file_digest,
    model_digest,
    read_model,
    write_completion_last,
)
from trajcert.types import (
    ActionChannelId,
    CaseIndex,
    ClientId,
    Count,
    DomainModel,
    ExperimentName,
    EpochId,
    FailureBoundaryProbe,
    FailureMessage,
    LawKey,
    LawName,
    PartitionName,
    PublicExecutionState,
    ReasonCode,
    SeedCount,
    SensitivityBudget,
    ToleranceValue,
)

FailureType = NewType("FailureType", str)

_RESULT_FILENAME = "scientific_result.json"

_NON_SCIENTIFIC_MODULE_PREFIXES = (
    "trajcert.cli",
    "trajcert.reporting.export",
    "trajcert.reporting.figures",
    "trajcert.reporting.tables",
)

_MATHEMATICS_PRODUCER_ROOT: Final[Path] = Path("src/trajcert/experiments/mathematics.py")
_TIMING_PRODUCER_ROOT: Final[Path] = Path("src/trajcert/experiments/timing.py")
_SAFETY_PRODUCER_ROOT: Final[Path] = Path("src/trajcert/experiments/safety.py")

_PRODUCER_ROOTS: dict[ExperimentName, Path] = {
    ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.PATH_INFORMATION_DECOMPOSITION: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.INFORMATION_PROFILE_CONVEXITY: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.REFINEMENT_DOMINANCE_IDENTITY: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.STRICT_TIMING_GAIN_IDENTITY: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.SAFETY_BOUNDARY_IDENTITY: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.ANYTIME_PROJECTION_PROOF_CHECK: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.POPULATION_COMPLEXITY_PROOF_CHECK: _MATHEMATICS_PRODUCER_ROOT,
    ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE: Path(
        "src/trajcert/experiments/solver_validation.py"
    ),
    ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION: Path(
        "src/trajcert/experiments/comparator_reduction.py"
    ),
    ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION: Path(
        "src/trajcert/experiments/comparator_reduction.py"
    ),
    ExperimentName.PARTITION_COHERENCE: _TIMING_PRODUCER_ROOT,
    ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING: _TIMING_PRODUCER_ROOT,
    ExperimentName.STRICT_TIMING_GAIN: _TIMING_PRODUCER_ROOT,
    ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR: _SAFETY_PRODUCER_ROOT,
    ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE: _SAFETY_PRODUCER_ROOT,
    ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY: _SAFETY_PRODUCER_ROOT,
    ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES: (
        Path("src/trajcert/experiments/anytime.py")
    ),
    ExperimentName.ANYTIME_COVERAGE_STRESS: Path("src/trajcert/experiments/anytime.py"),
    ExperimentName.POPULATION_SENSITIVITY_UTILITY: (
        Path("src/trajcert/experiments/sensitivity.py")
    ),
    ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY: Path("src/trajcert/experiments/sensitivity.py"),
    ExperimentName.FAILURE_BOUNDARY_ATLAS: (
        Path("src/trajcert/experiments/failure_boundaries.py")
    ),
    ExperimentName.COMPUTATIONAL_SCALING: Path("src/trajcert/experiments/scaling.py"),
    ExperimentName.STATISTICAL_SYNTHESIS: Path("src/trajcert/experiments/synthesis.py"),
}

_SUMMARY_COORDINATE_EXPERIMENTS = frozenset(
    {
        ExperimentName.PATH_INFORMATION_DECOMPOSITION,
        ExperimentName.INFORMATION_PROFILE_CONVEXITY,
        ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY,
        ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY,
        ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY,
        ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE,
        ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR,
        ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION,
        ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION,
    }
)


class DependencyReadiness(DomainModel):
    experiment_name: ExperimentName
    state: PublicExecutionState


class ExecutionContext(DomainModel):
    workspace_root: Path
    plan_digest: PlanDigest
    scientific_specification_digest: SpecificationDigest
    scientific_dependency_digest: SpecificationDigest
    provenance_fingerprint: ProvenanceFingerprint
    dependency_fingerprint: DependencyFingerprint
    manifest_digest: DigestHex
    required_artifact_keys: tuple[ArtifactKey, ...]
    expected_seed_count: SeedCount


class CellExecutionResult(DomainModel):
    artifact_index: CellArtifactIndex
    completed_seed_count: SeedCount
    metrics_complete: bool
    statistics_complete: bool
    invariant_validation_pass: bool
    dependency_validation_pass: bool
    provenance_record_complete: bool


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


class CellRunOutcome(DomainModel):
    state: PublicExecutionState
    reused: bool
    completion_path: Path
    failure_path: Path
    reason: ReasonCode | None


class ScientificInputClass(StrEnum):
    TARGET_STREAM_EVENT_COUNT = "target-stream-event-count-artifacts"
    TARGET_EPOCH_MANIFEST = "target-epoch-manifest"
    TARGET_PARTITION_MANIFEST = "target-partition-manifest"
    CONFIG_VALUES = "config.py-values"
    LOCAL_NUMERICAL_DEPENDENCY = "local-numerical-dependencies"


class StaticComponentDependency(DomainModel):
    producer_component: ProducerComponentName
    scientific_input_classes: tuple[ScientificInputClass, ...]
    scientific_client_ids: tuple[ClientId, ...] = ()


class RuntimeLineageArtifact(DomainModel):
    artifact_key: ArtifactKey
    parent_artifact_keys: tuple[ArtifactKey, ...] = ()
    client_id: ClientId | None = None
    action_channel_id: ActionChannelId | None = None
    epoch_id: EpochId | None = None
    foreign_client_ids: tuple[ClientId, ...] = ()
    foreign_client_statistics: bool = False
    foreign_model_updates: bool = False
    cross_client_aggregate: bool = False


class LocalValidityTarget(DomainModel):
    target_identity: LedgerIdentity
    root_artifact_key: ArtifactKey
    lineage_artifacts: tuple[RuntimeLineageArtifact, ...]


class RuntimeLineageAudit(DomainModel):
    passed: bool
    violating_artifact_keys: tuple[ArtifactKey, ...]


class LocalValidityAuditResult(DomainModel):
    static_dependency_pass: bool
    runtime_lineage_pass: bool
    audited_root_count: Count
    foreign_scientific_parent_count: Count
    violating_artifact_keys: tuple[ArtifactKey, ...]
    passed: bool = Field(serialization_alias="pass")


class ScientificCellDispatchError(ValueError):
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
    except Exception as exc:
        failure = FailureRecord(
            semantic_cell_key=cell.identity.semantic_cell_key,
            plan_digest=context.plan_digest,
            dependency_fingerprint=context.dependency_fingerprint,
            failure_type=FailureType(type(exc).__name__),
            message=FailureMessage(str(exc)),
        )
        _ = atomic_write_model(failure_path, failure)
        completion_path.unlink(missing_ok=True)
        return CellRunOutcome(
            state=PublicExecutionState.FAILED,
            reused=False,
            completion_path=completion_path,
            failure_path=failure_path,
            reason=ReasonCode("TECHNICAL_EXECUTION_FAILURE"),
        )
    finally:
        running_path.unlink(missing_ok=True)


def dependency_block_reason(
    cell: PlannedCell, dependencies: tuple[DependencyReadiness, ...]
) -> ReasonCode | None:
    supplied = {item.experiment_name: item.state for item in dependencies}
    if any(name not in supplied for name in cell.required_experiments):
        return ReasonCode("MISSING_DEPENDENCY_STATUS")
    if any(
        supplied[name] is not PublicExecutionState.COMPLETED for name in cell.required_experiments
    ):
        return ReasonCode("UPSTREAM_EXPERIMENT_NOT_COMPLETED")
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
    return workspace_root / directory / "COMPLETED.json"


def cell_running_path(cell: PlannedCell, workspace_root: Path) -> Path:
    return cell_completion_path(cell, workspace_root).with_name("RUNNING.json")


def cell_artifact_index_path(cell: PlannedCell, workspace_root: Path) -> Path:
    return cell_completion_path(cell, workspace_root).with_name("artifact_index.json")


def cell_failure_path(cell: PlannedCell, workspace_root: Path) -> Path:
    directory = semantic_cell_path(
        cell.identity.experiment_slug,
        ExperimentLeaf.LOGS_FAILURES,
        cell.identity.path_coordinates,
    )
    return workspace_root / directory / "failure.json"


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
        completion.scientific_dependency_digest == context.scientific_dependency_digest,
        completion.dependency_fingerprint == context.dependency_fingerprint,
        completion.manifest_digest == context.manifest_digest,
        completion.required_artifact_keys == context.required_artifact_keys,
        completion.expected_seed_count == context.expected_seed_count,
        completion.completed_seed_count == completion.expected_seed_count,
        completion.expected_artifact_count == len(completion.produced_artifact_keys),
    )
    return all(checks)


def _validate_execution_result(result: CellExecutionResult, context: ExecutionContext) -> None:
    produced = tuple(entry.artifact_key for entry in result.artifact_index.artifacts)
    if len(produced) != len(set(produced)):
        raise InvariantViolationError("executor produced duplicate artifact keys")
    if any(key not in produced for key in context.required_artifact_keys):
        raise InvariantViolationError("executor omitted a required artifact key")
    checks = (
        (result.completed_seed_count == context.expected_seed_count, "expected seed count"),
        (result.metrics_complete, "required metrics"),
        (result.statistics_complete, "required statistics"),
        (result.invariant_validation_pass, "scientific invariant validation"),
        (result.dependency_validation_pass, "dependency validation"),
        (result.provenance_record_complete, "provenance record"),
    )
    failed = tuple(label for passed, label in checks if not passed)
    if failed:
        raise InvariantViolationError(f"executor completion contract failed: {', '.join(failed)}")


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
        scientific_dependency_digest=context.scientific_dependency_digest,
        provenance_fingerprint=context.provenance_fingerprint,
        dependency_fingerprint=context.dependency_fingerprint,
        manifest_digest=context.manifest_digest,
        required_artifact_keys=context.required_artifact_keys,
        produced_artifact_keys=produced,
        expected_artifact_count=len(produced),
        artifact_sha256_map=checksums,
        completed_seed_count=result.completed_seed_count,
        expected_seed_count=context.expected_seed_count,
        metrics_complete=True,
        statistics_complete=True,
        schema_validation_pass=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
        exit_status=0,
    )


def _checksum(entry: ArtifactIndexEntry) -> ArtifactChecksum:
    return ArtifactChecksum(artifact_key=entry.artifact_key, sha256=entry.sha256)


def scientific_specification_digest() -> SpecificationDigest:
    return SpecificationDigest(model_digest(active_config.get()))


def producer_component_digest(
    workspace_root: Path,
    experiment_name: ExperimentName,
) -> DigestHex:
    root = _PRODUCER_ROOTS.get(experiment_name)
    if root is None:
        raise InvalidScientificDataError(
            f"missing producer-component registration: {experiment_name}"
        )
    files = _first_party_import_closure(workspace_root, root)
    digest = sha256()
    for relative in files:
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(bytes.fromhex(file_digest(workspace_root / relative)))
    return DigestHex(digest.hexdigest())


def scientific_dependency_digest(
    scientific_specification: SpecificationDigest,
    semantic_cell_key: SemanticCellKey,
    component_digest: DigestHex,
) -> SpecificationDigest:
    payload = f"{scientific_specification}|{semantic_cell_key}|{component_digest}".encode()
    return SpecificationDigest(sha256(payload).hexdigest())


def cell_dependency_fingerprint(
    workspace_root: Path,
    plan: ExperimentPlan,
    cell: PlannedCell,
    scientific_dependency: SpecificationDigest,
) -> DependencyFingerprint:
    required = set(cell.required_experiments)
    parents = tuple(item for item in plan.cells if item.identity.experiment_name in required)
    parent_digests = tuple(
        file_digest(cell_completion_path(parent, workspace_root))
        for parent in parents
        if cell_completion_path(parent, workspace_root).is_file()
    )
    payload = "|".join(
        (
            cell.identity.semantic_cell_key,
            scientific_dependency,
            *parent_digests,
        )
    )
    return DependencyFingerprint(sha256(payload.encode("utf-8")).hexdigest())


def expected_seed_count(experiment_name: ExperimentName) -> SeedCount:
    config = active_config.get()
    name = experiment_name
    if name == ExperimentName.ANYTIME_COVERAGE_STRESS:
        return config.sequential.coverage.streams
    if name == ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY:
        return config.sequential.utility.streams
    return 0


def _first_party_import_closure(workspace_root: Path, root: Path) -> tuple[Path, ...]:
    pending = [root]
    visited: set[Path] = set()
    while pending:
        relative = pending.pop()
        if relative in visited:
            continue
        full_path = workspace_root / relative
        if not full_path.is_file():
            raise InvalidScientificDataError(f"registered producer source is missing: {relative}")
        visited.add(relative)
        try:
            tree = ast.parse(full_path.read_text(encoding="utf-8"), filename=str(relative))
        except (OSError, SyntaxError, UnicodeError) as exc:
            raise InvalidScientificDataError(f"cannot inspect producer source: {relative}") from exc
        for module_name in _first_party_imports(tree):
            dependency = _module_path(workspace_root, module_name)
            if dependency is not None and dependency not in visited:
                pending.append(dependency)
    return tuple(sorted(visited, key=lambda path: path.as_posix()))


def _first_party_imports(tree: ast.AST) -> tuple[str, ...]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.update(_first_party_import_from(node))
        elif isinstance(node, ast.Import):
            modules.update(_first_party_import(node))
    return tuple(sorted(modules))


def _first_party_import_from(node: ast.ImportFrom) -> tuple[str, ...]:
    return tuple(
        module for module in (node.module,) if module is not None and _is_first_party_module(module)
    )


def _first_party_import(node: ast.Import) -> tuple[str, ...]:
    return tuple(alias.name for alias in node.names if _is_first_party_module(alias.name))


def _is_first_party_module(module_name: str) -> bool:
    return module_name.startswith("trajcert") and not _non_scientific_module(module_name)


def _non_scientific_module(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in _NON_SCIENTIFIC_MODULE_PREFIXES
    )


def _module_path(workspace_root: Path, module_name: str) -> Path | None:
    parts = module_name.split(".")
    if not parts or parts[0] != "trajcert":
        return None
    module_path = Path("src") / Path(*parts)
    file_candidate = module_path.with_suffix(".py")
    package_candidate = module_path / "__init__.py"
    if (workspace_root / file_candidate).is_file():
        return file_candidate
    if (workspace_root / package_candidate).is_file():
        return package_candidate
    return None


def audit_local_validity_targets(
    static_dependencies: tuple[StaticComponentDependency, ...],
    targets: tuple[LocalValidityTarget, ...],
) -> LocalValidityAuditResult:
    if not targets:
        raise InvalidScientificDataError("local-validity audit requires at least one bound root")
    static_pass = all(
        static_dependency_audit(target.target_identity, static_dependencies) for target in targets
    )
    runtime_pass = True
    violating: set[ArtifactKey] = set()
    for target in targets:
        audit = runtime_lineage_audit(
            target.target_identity,
            target.root_artifact_key,
            target.lineage_artifacts,
        )
        runtime_pass = runtime_pass and audit.passed
        violating.update(audit.violating_artifact_keys)
    ordered = tuple(sorted(violating, key=str))
    return LocalValidityAuditResult(
        static_dependency_pass=static_pass,
        runtime_lineage_pass=runtime_pass,
        audited_root_count=len(targets),
        foreign_scientific_parent_count=len(ordered),
        violating_artifact_keys=ordered,
        passed=static_pass and runtime_pass,
    )


def static_dependency_audit(
    target_identity: LedgerIdentity,
    dependencies: tuple[StaticComponentDependency, ...],
) -> bool:
    expected_components = {
        ProducerComponentName("inference/categorical.py"),
        ProducerComponentName("inference/confidence.py"),
        ProducerComponentName("inference/envelope.py"),
        ProducerComponentName("inference/projection.py"),
        ProducerComponentName("inference/certification.py"),
    }
    supplied_components = tuple(item.producer_component for item in dependencies)
    if len(supplied_components) != len(set(supplied_components)):
        return False
    if set(supplied_components) != expected_components:
        return False
    if any(not dependency.scientific_input_classes for dependency in dependencies):
        return False
    return all(
        client_id == target_identity.client_id
        for dependency in dependencies
        for client_id in dependency.scientific_client_ids
    )


def runtime_lineage_audit(
    target_identity: LedgerIdentity,
    root_artifact_key: ArtifactKey,
    artifacts: tuple[RuntimeLineageArtifact, ...],
) -> RuntimeLineageAudit:
    by_key = {artifact.artifact_key: artifact for artifact in artifacts}
    if len(by_key) != len(artifacts):
        raise InvalidScientificDataError("runtime lineage contains duplicate artifact keys")
    violating: set[ArtifactKey] = set()
    visited: set[ArtifactKey] = set()
    visiting: set[ArtifactKey] = set()

    def visit(artifact_key: ArtifactKey) -> None:
        if artifact_key in visited:
            return
        if artifact_key in visiting:
            raise InvalidScientificDataError("runtime lineage parent graph contains a cycle")
        artifact = by_key.get(artifact_key)
        if artifact is None:
            violating.add(artifact_key)
            return
        visiting.add(artifact_key)
        identity_fields = (artifact.client_id, artifact.action_channel_id, artifact.epoch_id)
        target_fields = (
            target_identity.client_id,
            target_identity.action_channel_id,
            target_identity.epoch_id,
        )
        if any(value is not None for value in identity_fields) and identity_fields != target_fields:
            violating.add(artifact.artifact_key)
        if (
            artifact.foreign_client_ids
            or artifact.foreign_client_statistics
            or artifact.foreign_model_updates
            or artifact.cross_client_aggregate
        ):
            violating.add(artifact.artifact_key)
        for parent_key in artifact.parent_artifact_keys:
            visit(parent_key)
        visiting.remove(artifact_key)
        visited.add(artifact_key)

    visit(root_artifact_key)
    ordered = tuple(sorted(violating, key=str))
    return RuntimeLineageAudit(passed=not ordered, violating_artifact_keys=ordered)


def execute_scientific_cell(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    if not cell.executable:
        raise ScientificCellDispatchError("planned-invalid cell cannot be scientifically executed")
    _ = active_config.set(config)
    name = cell.identity.experiment_name
    if name == "Anytime Projection Proof Check":
        return anytime_projection_proof_check()
    if name == "Population Complexity Proof Check":
        return population_complexity_proof_check()
    handler = _DISPATCH_TABLE.get(name)
    if handler is None:
        raise ScientificCellDispatchError(
            "experiment lacks a registered dispatch handler or authoritative "
            + f"scientific coordinates: {name}"
        )
    return handler(cell)


def _dispatch_legacy_partition_incoherence(cell: PlannedCell) -> DomainModel:
    gamma = cell.identity.coordinates.gamma
    variant = cell.identity.coordinates.variant_name
    if gamma is None or variant is None or not variant.startswith("q="):
        raise ScientificCellDispatchError("legacy incoherence cell is missing Gamma or q")
    return evaluate_legacy_partition_incoherence(
        gamma=gamma,
        q=float(variant.removeprefix("q=")),
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


def _dispatch_safety_boundary_identity(cell: PlannedCell) -> DomainModel:
    summary = _law_level_finest_summary(cell)
    return _execute_summary_cell(ExperimentName.SAFETY_BOUNDARY_IDENTITY, cell, summary)


def _dispatch_sharpness_against_generic_oracle(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
    return sharpness_against_generic_oracle(
        summary=_summary_from_coordinates(cell),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        oracle_digits=config.numerics.oracle_digits,
        oracle_bracket_width=config.numerics.oracle_bracket_width,
        sharpness_diagnostic_offset=config.numerics.sharpness_diagnostic_offset,
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
    return run_anytime_hand_case(case_index, partition, active_config.get())


def _dispatch_computational_scaling(cell: PlannedCell) -> DomainModel:
    bands = cell.identity.coordinates.scaling_band_count
    if bands is None:
        raise ScientificCellDispatchError("scaling cell is missing K")
    return benchmark_scaling_cell(bands)


def _dispatch_summary_coordinate_experiment(
    name: ExperimentName, cell: PlannedCell
) -> DomainModel:
    return _execute_summary_cell(name, cell, _summary_from_coordinates(cell))


_DISPATCH_TABLE: dict[ExperimentName, Callable[[PlannedCell], DomainModel]] = {
    ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK: (
        _dispatch_legacy_partition_incoherence
    ),
    ExperimentName.REFINEMENT_DOMINANCE_IDENTITY: _dispatch_refinement_dominance_identity,
    ExperimentName.STRICT_TIMING_GAIN_IDENTITY: _dispatch_strict_timing_gain_identity,
    ExperimentName.PARTITION_COHERENCE: _dispatch_partition_coherence,
    ExperimentName.SAME_ENDPOINT_DIFFERENT_TIMING: (
        _dispatch_same_endpoint_different_timing
    ),
    ExperimentName.STRICT_TIMING_GAIN: _dispatch_strict_timing_gain,
    ExperimentName.SAFETY_BOUNDARY_IDENTITY: _dispatch_safety_boundary_identity,
    ExperimentName.SHARPNESS_AGAINST_GENERIC_ORACLE: (
        _dispatch_sharpness_against_generic_oracle
    ),
    ExperimentName.SAFETY_AND_INTRINSIC_IMPOSSIBILITY: _safety_intrinsic_case,
    ExperimentName.ANYTIME_COVERAGE_STRESS: _coverage_stress_case,
    ExperimentName.POPULATION_SENSITIVITY_UTILITY: _dispatch_population_sensitivity_utility,
    ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY: _dispatch_sequential_sensitivity_utility,
    ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES: _dispatch_anytime_hand_case,
    ExperimentName.FAILURE_BOUNDARY_ATLAS: _execute_failure_boundary,
    ExperimentName.COMPUTATIONAL_SCALING: _dispatch_computational_scaling,
    **{
        name: partial(_dispatch_summary_coordinate_experiment, name)
        for name in _SUMMARY_COORDINATE_EXPERIMENTS
    },
}


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
    return compare_production_solver_to_oracle(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
    )


def _summary_compatibility_floor_behavior(
    cell: PlannedCell, summary: ObservableSummary
) -> DomainModel:
    del cell
    config = active_config.get()
    return compatibility_floor_behavior(
        summary,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
        config.numerics.oracle_bracket_width,
        config.numerics.compatibility_floor_offset,
    )


def _summary_safety_boundary_identity(cell: PlannedCell, summary: ObservableSummary) -> DomainModel:
    config = active_config.get()
    case = _safety_case(
        summary,
        cell.identity.coordinates.variant_name,
        config.numerics.resolved_harm_boundary_offset,
    )
    return evaluate_safety_boundary_case(
        summary,
        case,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_comparator_reduction(cell: PlannedCell, summary: ObservableSummary) -> DomainModel:
    del cell
    return evaluate_comparator_reduction(summary)


_SUMMARY_DISPATCH_TABLE: dict[
    ExperimentName, Callable[[PlannedCell, ObservableSummary], DomainModel]
] = {
    ExperimentName.PATH_INFORMATION_DECOMPOSITION: _summary_path_information_decomposition,
    ExperimentName.INFORMATION_PROFILE_CONVEXITY: _summary_information_profile_convexity,
    ExperimentName.MINIMUM_COMPATIBILITY_IDENTITY: _summary_minimum_compatibility_identity,
    ExperimentName.SHARP_SET_CONSTRUCTIVE_IDENTITY: _summary_sharp_set_constructive_identity,
    ExperimentName.ENDPOINT_SPECIAL_CASE_IDENTITY: _summary_endpoint_special_case_identity,
    ExperimentName.PRODUCTION_SOLVER_VS_INDEPENDENT_ORACLE: (
        _summary_production_solver_vs_independent_oracle
    ),
    ExperimentName.COMPATIBILITY_FLOOR_BEHAVIOR: _summary_compatibility_floor_behavior,
    ExperimentName.SAFETY_BOUNDARY_IDENTITY: _summary_safety_boundary_identity,
    ExperimentName.CALLBACK_MODEL_REDUCTION_FALSIFICATION: _summary_comparator_reduction,
    ExperimentName.GENERIC_INFORMATION_OPTIMIZATION_REDUCTION: _summary_comparator_reduction,
}


def _execute_summary_cell(
    name: ExperimentName,
    cell: PlannedCell,
    summary: ObservableSummary,
) -> DomainModel:
    handler = _SUMMARY_DISPATCH_TABLE.get(name)
    if handler is None:
        raise ScientificCellDispatchError(f"no summary executor for {name}")
    return handler(cell, summary)


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
    fine_text, separator, coarse_text = comparison.partition(" -> ")
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
    prefix = "rho-offset="
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
    prefix = "hand-case-"
    if variant is None or not variant.startswith(prefix):
        raise ScientificCellDispatchError("cell is missing its expected variant index")
    return int(variant[len(prefix) :])


def _safety_case(
    summary: ObservableSummary,
    variant: VariantName | None,
    resolved_harm_boundary_offset: ToleranceValue,
) -> SafetyBudgetCase:
    if variant is None:
        raise ScientificCellDispatchError("safety cell is missing its case variant")
    for case in safety_budget_cases(summary, resolved_harm_boundary_offset):
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
        resolved_harm_boundary_offset=config.numerics.resolved_harm_boundary_offset,
    )
    variant = cell.identity.coordinates.variant_name
    if variant is None:
        raise ScientificCellDispatchError("safety/impossibility cell is missing its case variant")
    for evaluation in result.cases:
        if semantic_slug(evaluation.case.name) == variant:
            return evaluation
    raise ScientificCellDispatchError(f"unknown safety/impossibility case: {variant}")


def _coverage_stress_case(cell: PlannedCell) -> DomainModel:
    config = active_config.get()
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
        return evaluate_configured_coverage_stress(case, config)
    raise ScientificCellDispatchError(f"unknown configured coverage-stress case: {variant}")


def _execute_failure_boundary(cell: PlannedCell) -> DomainModel:
    coordinate = cell.identity.coordinates.failure_boundary_axis_and_level
    if coordinate is None:
        raise ScientificCellDispatchError("failure-boundary cell is missing axis/level")
    axis_text, separator, value_text = coordinate.partition("=")
    if not separator:
        raise ScientificCellDispatchError("invalid failure-boundary coordinate")
    axis = FailureBoundaryAxis(axis_text)
    if axis is FailureBoundaryAxis.TERMINAL_SELECTION_ASYMMETRY:
        q1_text, separator, q0_text = value_text.partition(",q0:")
        if not separator or not q1_text.startswith("q1:"):
            raise ScientificCellDispatchError("invalid terminal-selection-asymmetry coordinate")
        return evaluate_terminal_selection_asymmetry(
            q1=float(q1_text.removeprefix("q1:")),
            q0=float(q0_text),
        )
    if axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET:
        return evaluate_optimizer_node_budget(int(value_text))
    parsed_axis, level = _failure_coordinate(coordinate)
    return evaluate_failure_boundary(parsed_axis, level)


def _failure_coordinate(
    coordinate: FailureBoundaryCoordinate,
) -> tuple[FailureBoundaryAxis, FailureBoundaryProbe]:
    axis_text, separator, value_text = coordinate.partition("=")
    if not separator:
        raise ScientificCellDispatchError("invalid failure-boundary coordinate")
    axis = FailureBoundaryAxis(axis_text)
    if axis is FailureBoundaryAxis.RISK_OFFSET:
        if value_text.startswith("negative-"):
            return axis, -float(value_text.removeprefix("negative-"))
        if value_text.startswith("nonnegative-"):
            return axis, float(value_text.removeprefix("nonnegative-"))
    if axis in {FailureBoundaryAxis.PATH_RESOLUTION, FailureBoundaryAxis.MATURED_SAMPLE_SIZE}:
        return axis, int(value_text)
    return axis, float(value_text)


def scientific_result_artifact_key(cell: PlannedCell) -> ArtifactKey:
    return ArtifactKey(f"scientific-result|{cell.identity.semantic_cell_key}")


def scientific_result_path(cell: PlannedCell) -> Path:
    return (
        semantic_cell_path(
            cell.identity.experiment_slug,
            ExperimentLeaf.EVALUATION_RECORDS,
            cell.identity.path_coordinates,
        )
        / _RESULT_FILENAME
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
    if completion.expected_artifact_count != 1 or len(index.artifacts) != 1:
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
    digest = atomic_write_model(
        context.workspace_root / relative_path,
        execute_scientific_cell(cell, active_config.get()),
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
        metrics_complete=True,
        statistics_complete=True,
        invariant_validation_pass=True,
        dependency_validation_pass=True,
        provenance_record_complete=True,
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
