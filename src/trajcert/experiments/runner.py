from __future__ import annotations

import ast
from collections.abc import Callable
from enum import StrEnum
from functools import partial
from hashlib import sha256
from pathlib import Path
from typing import NewType

from pydantic import Field

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
from trajcert.experiments.inventory import validate_scientific_inventory
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
    evaluate_strict_timing_gain,
)
from trajcert.inference.categorical import append_matured_event, initialize_categorical_state
from trajcert.inference.confidence import CategoricalConfidenceRegion, confidence_sequence_update
from trajcert.inference.envelope import singleton_summary_envelope
from trajcert.inference.projection import project_upper_risk
from trajcert.math.bounds import sharp_risk_set
from trajcert.math.information import observed_timing_information
from trajcert.math.safety import SafetyBudgetCase, safety_budget_cases
from trajcert.paths import ExperimentLeaf, semantic_cell_path, semantic_slug
from trajcert.provenance import (
    ExperimentNameValue,
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
    SpecificationDigest,
    atomic_write_model,
    file_digest,
    model_digest,
    read_model,
    write_completion_last,
)
from trajcert.types import (
    ActionChannelId,
    ClientId,
    DomainModel,
    EpochId,
    LawKey,
    LawName,
    NonNegativeInt,
    PartitionName,
    PublicExecutionState,
    ReasonCode,
    SensitivityBudget,
)

FailureType = NewType("FailureType", str)
FailureMessage = NewType("FailureMessage", str)

_RESULT_FILENAME = "scientific_result.json"

_NON_SCIENTIFIC_MODULE_PREFIXES = (
    "trajcert.cli",
    "trajcert.operator",
    "trajcert.reporting.export",
    "trajcert.reporting.figures",
    "trajcert.reporting.tables",
)

_PRODUCER_ROOTS = {
    "Scientific and Data Inventory": Path("src/trajcert/experiments/inventory.py"),
    "Legacy Partition Incoherence Check": Path("src/trajcert/experiments/mathematics.py"),
    "Path Information Decomposition": Path("src/trajcert/experiments/mathematics.py"),
    "Information Profile Convexity": Path("src/trajcert/experiments/mathematics.py"),
    "Minimum Compatibility Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Sharp-Set Constructive Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Refinement Dominance Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Strict Timing-Gain Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Safety-Boundary Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Endpoint Special-Case Identity": Path("src/trajcert/experiments/mathematics.py"),
    "Anytime Projection Proof Check": Path("src/trajcert/experiments/mathematics.py"),
    "Population Complexity Proof Check": Path("src/trajcert/experiments/mathematics.py"),
    "Production Solver vs Independent Oracle": Path(
        "src/trajcert/experiments/solver_validation.py"
    ),
    "Callback-Model Reduction Falsification": Path(
        "src/trajcert/experiments/comparator_reduction.py"
    ),
    "Generic Information-Optimization Reduction": Path(
        "src/trajcert/experiments/comparator_reduction.py"
    ),
    "Partition Coherence": Path("src/trajcert/experiments/timing.py"),
    "Same Endpoint, Different Timing": Path("src/trajcert/experiments/timing.py"),
    "Strict Timing Gain": Path("src/trajcert/experiments/timing.py"),
    "Compatibility Floor Behavior": Path("src/trajcert/experiments/safety.py"),
    "Sharpness Against Generic Oracle": Path("src/trajcert/experiments/safety.py"),
    "Safety and Intrinsic Impossibility": Path("src/trajcert/experiments/safety.py"),
    "Anytime Implementation Hand Cases": Path("src/trajcert/experiments/anytime.py"),
    "Anytime Coverage Stress": Path("src/trajcert/experiments/anytime.py"),
    "Population Sensitivity Utility": Path("src/trajcert/experiments/sensitivity.py"),
    "Sequential Sensitivity Utility": Path("src/trajcert/experiments/sensitivity.py"),
    "Failure Boundary Atlas": Path("src/trajcert/experiments/failure_boundaries.py"),
    "Computational Scaling": Path("src/trajcert/experiments/scaling.py"),
    "Statistical Synthesis": Path("src/trajcert/experiments/synthesis_execution.py"),
}

_SUMMARY_COORDINATE_EXPERIMENTS = frozenset(
    {
        "Path Information Decomposition",
        "Information Profile Convexity",
        "Minimum Compatibility Identity",
        "Sharp-Set Constructive Identity",
        "Endpoint Special-Case Identity",
        "Production Solver vs Independent Oracle",
        "Compatibility Floor Behavior",
        "Callback-Model Reduction Falsification",
        "Generic Information-Optimization Reduction",
    }
)

_SMOKE_COMPATIBLE_OFFSET = 0.01
_SMOKE_REFINEMENT_OFFSET = 0.025
_SMOKE_CS_EVENTS = 25
_SMOKE_COARSE_BANDS = 4
_SMOKE_CS_BANDS = 2
_SMOKE_FIXTURE_COUNT = 6


class DependencyReadiness(DomainModel):
    experiment_name: ExperimentNameValue
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
    expected_seed_count: NonNegativeInt


class CellExecutionResult(DomainModel):
    artifact_index: CellArtifactIndex
    completed_seed_count: NonNegativeInt
    metrics_complete: bool
    statistics_complete: bool
    invariant_validation_pass: bool
    dependency_validation_pass: bool
    provenance_record_complete: bool


class RunningRecord(DomainModel):
    semantic_cell_key: str
    plan_digest: PlanDigest
    dependency_fingerprint: DependencyFingerprint


class FailureRecord(DomainModel):
    semantic_cell_key: str
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


class LocalValidityAuditResult(DomainModel):
    static_dependency_pass: bool
    runtime_lineage_pass: bool
    audited_root_count: NonNegativeInt
    foreign_scientific_parent_count: NonNegativeInt
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
    passed_fixture_count: NonNegativeInt

    @property
    def passed(self) -> bool:
        return self.passed_fixture_count == _SMOKE_FIXTURE_COUNT


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
    if completion_path.is_file() and not overwrite:
        if completion_is_compatible(cell, context, completion_path):
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
        semantic_cell_key=str(cell.identity.semantic_cell_key),
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
            semantic_cell_key=str(cell.identity.semantic_cell_key),
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
    return PlanDigest(str(model_digest(cell)))


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
        if not artifact_path.is_file():
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


def scientific_specification_digest(config: TrajCertConfig) -> SpecificationDigest:
    return SpecificationDigest(str(model_digest(config)))


def producer_component_digest(
    workspace_root: Path,
    experiment_name: ExperimentNameValue,
) -> DigestHex:
    root = _PRODUCER_ROOTS.get(str(experiment_name))
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
        digest.update(bytes.fromhex(str(file_digest(workspace_root / relative))))
    return DigestHex(digest.hexdigest())


def scientific_dependency_digest(
    scientific_specification: SpecificationDigest,
    semantic_cell_key: str,
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
        str(file_digest(cell_completion_path(parent, workspace_root)))
        for parent in parents
        if cell_completion_path(parent, workspace_root).is_file()
    )
    payload = "|".join(
        (
            str(cell.identity.semantic_cell_key),
            str(scientific_dependency),
            *parent_digests,
        )
    )
    return DependencyFingerprint(sha256(payload.encode("utf-8")).hexdigest())


def expected_seed_count(
    experiment_name: ExperimentNameValue,
    config: TrajCertConfig,
) -> NonNegativeInt:
    name = str(experiment_name)
    if name == "Anytime Coverage Stress":
        return config.sequential.coverage.streams
    if name == "Sequential Sensitivity Utility":
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
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.startswith("trajcert") and not _non_scientific_module(node.module):
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("trajcert") and not _non_scientific_module(alias.name):
                    modules.add(alias.name)
    return tuple(sorted(modules))


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


def audit_local_validity(
    target_identity: LedgerIdentity,
    static_dependencies: tuple[StaticComponentDependency, ...],
    root_artifact_key: ArtifactKey,
    lineage_artifacts: tuple[RuntimeLineageArtifact, ...],
) -> LocalValidityAuditResult:
    target = LocalValidityTarget(
        target_identity=target_identity,
        root_artifact_key=root_artifact_key,
        lineage_artifacts=lineage_artifacts,
    )
    return audit_local_validity_targets(static_dependencies, (target,))


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
        target_pass, target_violations = runtime_lineage_audit(
            target.target_identity,
            target.root_artifact_key,
            target.lineage_artifacts,
        )
        runtime_pass = runtime_pass and target_pass
        violating.update(target_violations)
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
) -> tuple[bool, tuple[ArtifactKey, ...]]:
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
    return not ordered, ordered


def execute_scientific_cell(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    if not cell.executable:
        raise ScientificCellDispatchError("planned-invalid cell cannot be scientifically executed")
    _ = active_config.set(config)
    name = str(cell.identity.experiment_name)
    if name == "Anytime Projection Proof Check":
        return anytime_projection_proof_check()
    if name == "Population Complexity Proof Check":
        return population_complexity_proof_check()
    handler = _DISPATCH_TABLE.get(name)
    if handler is None:
        raise ScientificCellDispatchError(
            f"experiment lacks a registered dispatch handler or authoritative "
            f"scientific coordinates: {name}"
        )
    return handler(cell, config)


def _dispatch_scientific_and_data_inventory(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    del cell
    return validate_scientific_inventory(config)


def _dispatch_legacy_partition_incoherence(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    gamma = cell.identity.coordinates.gamma
    variant = cell.identity.coordinates.variant_name
    if gamma is None or variant is None or not str(variant).startswith("q="):
        raise ScientificCellDispatchError("legacy incoherence cell is missing Gamma or q")
    return evaluate_legacy_partition_incoherence(
        gamma=float(gamma),
        q=float(str(variant).removeprefix("q=")),
        config=config,
    )


def _dispatch_refinement_dominance_identity(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    fine, coarse = _refinement_inputs(cell, config)
    return refinement_dominance_identity(
        fine=fine,
        coarse_partition=coarse,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_strict_timing_gain_identity(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    fine, coarse = _refinement_inputs(cell, config)
    return strict_timing_gain_identity(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_partition_coherence(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    fine, coarse = _refinement_inputs(cell, config)
    return evaluate_partition_coherence(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_same_endpoint_different_timing(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    partition = _partition_from_coordinates(cell, config)
    rho = _direct_rho(cell)
    no_timing = _population_summary(
        _law_from_name(LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_NO_TIMING], config),
        partition,
        config,
    )
    with_timing = _population_summary(
        _law_from_name(LAW_DISPLAY_NAMES[LawKey.SAME_ENDPOINT_WITH_TIMING], config),
        partition,
        config,
    )
    return evaluate_same_endpoint_different_timing(
        no_timing=no_timing,
        with_timing=with_timing,
        sensitivity_budget=rho,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
    )


def _dispatch_strict_timing_gain(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    fine, coarse = _refinement_inputs(cell, config)
    return evaluate_strict_timing_gain(
        fine=fine,
        coarse_partition=coarse,
        sensitivity_budget=_rho_from_offset(fine, cell.identity.coordinates.sensitivity_coordinate),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )


def _dispatch_safety_boundary_identity(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    summary = _law_level_finest_summary(cell, config)
    return _execute_summary_cell("Safety-Boundary Identity", cell, summary, config)


def _dispatch_sharpness_against_generic_oracle(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    return sharpness_against_generic_oracle(
        summary=_summary_from_coordinates(cell, config),
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        oracle_digits=config.numerics.oracle_digits,
    )


def _dispatch_population_sensitivity_utility(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    return population_sensitivity_utility(
        summary=_summary_from_coordinates(cell, config),
        sensitivity_budget=_direct_rho(cell),
        config=config,
    )


def _dispatch_sequential_sensitivity_utility(
    cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name, config)
    finest = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    return sequential_sensitivity_utility(
        parameters=law,
        fine_partition=finest,
        config=config,
        sensitivity_budget=_direct_rho(cell),
    )


def _dispatch_anytime_hand_case(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    partition = _partition_from_coordinates(cell, config)
    case_index = _variant_index(cell.identity.coordinates.variant_name, "hand-case-")
    return run_anytime_hand_case(case_index, partition, config)


def _dispatch_computational_scaling(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    bands = cell.identity.coordinates.scaling_band_count
    if bands is None:
        raise ScientificCellDispatchError("scaling cell is missing K")
    return benchmark_scaling_cell(int(bands), config)


def _dispatch_summary_coordinate_experiment(
    name: str, cell: PlannedCell, config: TrajCertConfig
) -> DomainModel:
    return _execute_summary_cell(name, cell, _summary_from_coordinates(cell, config), config)


_DISPATCH_TABLE: dict[str, Callable[[PlannedCell, TrajCertConfig], DomainModel]] = {
    "Scientific and Data Inventory": _dispatch_scientific_and_data_inventory,
    "Legacy Partition Incoherence Check": _dispatch_legacy_partition_incoherence,
    "Refinement Dominance Identity": _dispatch_refinement_dominance_identity,
    "Strict Timing-Gain Identity": _dispatch_strict_timing_gain_identity,
    "Partition Coherence": _dispatch_partition_coherence,
    "Same Endpoint, Different Timing": _dispatch_same_endpoint_different_timing,
    "Strict Timing Gain": _dispatch_strict_timing_gain,
    "Safety-Boundary Identity": _dispatch_safety_boundary_identity,
    "Sharpness Against Generic Oracle": _dispatch_sharpness_against_generic_oracle,
    "Safety and Intrinsic Impossibility": lambda cell, config: _safety_intrinsic_case(cell, config),
    "Anytime Coverage Stress": lambda cell, config: _coverage_stress_case(cell, config),
    "Population Sensitivity Utility": _dispatch_population_sensitivity_utility,
    "Sequential Sensitivity Utility": _dispatch_sequential_sensitivity_utility,
    "Anytime Implementation Hand Cases": _dispatch_anytime_hand_case,
    "Failure Boundary Atlas": lambda cell, config: _execute_failure_boundary(cell, config),
    "Computational Scaling": _dispatch_computational_scaling,
    **{
        name: partial(_dispatch_summary_coordinate_experiment, name)
        for name in _SUMMARY_COORDINATE_EXPERIMENTS
    },
}


def _summary_path_information_decomposition(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return path_information_decomposition(
        summary,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_information_profile_convexity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return information_profile_convexity(
        summary,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_minimum_compatibility_identity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return minimum_compatibility_identity(summary, config.numerics.identity_atol)


def _summary_sharp_set_constructive_identity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    return sharp_set_constructive_identity(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
    )


def _summary_endpoint_special_case_identity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return endpoint_special_case_identity(summary, config.numerics.identity_atol)


def _summary_production_solver_vs_independent_oracle(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    rho = _rho_from_offset(summary, cell.identity.coordinates.sensitivity_coordinate)
    return compare_production_solver_to_oracle(
        summary,
        rho,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
    )


def _summary_compatibility_floor_behavior(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return compatibility_floor_behavior(
        summary,
        config.numerics.root_atol,
        config.numerics.identity_atol,
        config.numerics.oracle_digits,
    )


def _summary_safety_boundary_identity(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    case = _safety_case(summary, cell.identity.coordinates.variant_name)
    return evaluate_safety_boundary_case(
        summary,
        case,
        config.numerics.oracle_digits,
        config.numerics.identity_atol,
    )


def _summary_comparator_reduction(
    cell: PlannedCell, summary: ObservableSummary, config: TrajCertConfig
) -> DomainModel:
    del cell
    return evaluate_comparator_reduction(summary, config)


_SUMMARY_DISPATCH_TABLE: dict[
    str, Callable[[PlannedCell, ObservableSummary, TrajCertConfig], DomainModel]
] = {
    "Path Information Decomposition": _summary_path_information_decomposition,
    "Information Profile Convexity": _summary_information_profile_convexity,
    "Minimum Compatibility Identity": _summary_minimum_compatibility_identity,
    "Sharp-Set Constructive Identity": _summary_sharp_set_constructive_identity,
    "Endpoint Special-Case Identity": _summary_endpoint_special_case_identity,
    "Production Solver vs Independent Oracle": _summary_production_solver_vs_independent_oracle,
    "Compatibility Floor Behavior": _summary_compatibility_floor_behavior,
    "Safety-Boundary Identity": _summary_safety_boundary_identity,
    "Callback-Model Reduction Falsification": _summary_comparator_reduction,
    "Generic Information-Optimization Reduction": _summary_comparator_reduction,
}


def _execute_summary_cell(
    name: str,
    cell: PlannedCell,
    summary: ObservableSummary,
    config: TrajCertConfig,
) -> DomainModel:
    handler = _SUMMARY_DISPATCH_TABLE.get(name)
    if handler is None:
        raise ScientificCellDispatchError(f"no summary executor for {name}")
    return handler(cell, summary, config)


def _summary_from_coordinates(cell: PlannedCell, config: TrajCertConfig) -> ObservableSummary:
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name, config)
    partition = _partition_from_coordinates(cell, config)
    return _population_summary(law, partition, config)


def _law_level_finest_summary(cell: PlannedCell, config: TrajCertConfig) -> ObservableSummary:
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name, config)
    partition = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    return _population_summary(law, partition, config)


def _refinement_inputs(
    cell: PlannedCell,
    config: TrajCertConfig,
) -> tuple[ObservableSummary, TrajectoryPartition]:
    comparison = cell.identity.coordinates.comparison_pair_name
    if comparison is None:
        raise ScientificCellDispatchError("refinement cell is missing its comparison pair")
    fine_text, separator, coarse_text = str(comparison).partition(" -> ")
    if not separator:
        raise ScientificCellDispatchError("invalid comparison-pair encoding")
    fine = _partition_named(PartitionName(fine_text), config)
    coarse = _partition_named(PartitionName(coarse_text), config)
    law = _law_from_name(cell.identity.coordinates.synthetic_law_name, config)
    return _population_summary(law, fine, config), coarse


def _population_summary(
    law: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
) -> ObservableSummary:
    return summarize_full_law(
        partition,
        build_full_law(law, partition.band_count),
        config.numerics.comparison_guard,
    )


def _law_from_name(law_name: LawName | None, config: TrajCertConfig) -> LawParameters:
    if law_name is None:
        raise ScientificCellDispatchError("scientific cell is missing its synthetic law")
    for key, law in config.ordered_laws:
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


def _partition_from_coordinates(cell: PlannedCell, config: TrajCertConfig) -> TrajectoryPartition:
    requested = cell.identity.coordinates.partition_name
    if requested is None:
        raise ScientificCellDispatchError("scientific cell is missing its partition")
    return _partition_named(requested, config)


def _partition_named(name: PartitionName, config: TrajCertConfig) -> TrajectoryPartition:
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
    if coordinate is None or not str(coordinate).startswith(prefix):
        raise ScientificCellDispatchError("rho-offset cell is missing its sensitivity coordinate")
    offset = float(str(coordinate)[len(prefix) :])
    return float(observed_timing_information(summary) or 0.0) + offset


def _direct_rho(cell: PlannedCell) -> SensitivityBudget:
    rho = cell.identity.coordinates.rho
    if rho is None:
        raise ScientificCellDispatchError("scientific cell is missing its rho coordinate")
    return rho


def _variant_index(variant: VariantName | None, prefix: str) -> int:
    if variant is None or not str(variant).startswith(prefix):
        raise ScientificCellDispatchError("cell is missing its expected variant index")
    return int(str(variant)[len(prefix) :])


def _safety_case(summary: ObservableSummary, variant: VariantName | None) -> SafetyBudgetCase:
    if variant is None:
        raise ScientificCellDispatchError("safety cell is missing its case variant")
    for case in safety_budget_cases(summary):
        if str(semantic_slug(str(case.name))) == str(variant):
            return case
    raise ScientificCellDispatchError(f"unknown safety case: {variant}")


def _safety_intrinsic_case(cell: PlannedCell, config: TrajCertConfig) -> SafetyCaseEvaluation:
    summary = _law_level_finest_summary(cell, config)
    result = safety_and_intrinsic_impossibility(
        summary=summary,
        oracle_digits=config.numerics.oracle_digits,
        identity_atol=config.numerics.identity_atol,
    )
    variant = cell.identity.coordinates.variant_name
    if variant is None:
        raise ScientificCellDispatchError("safety/impossibility cell is missing its case variant")
    for evaluation in result.cases:
        if str(semantic_slug(str(evaluation.case.name))) == str(variant):
            return evaluation
    raise ScientificCellDispatchError(f"unknown safety/impossibility case: {variant}")


def _coverage_stress_case(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    variant = cell.identity.coordinates.variant_name
    if variant is None:
        raise ScientificCellDispatchError(
            "coverage-stress cell is missing its configured case name"
        )
    for case in config.study_design.coverage_stress_cases:
        if case.name != str(variant):
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


def _execute_failure_boundary(cell: PlannedCell, config: TrajCertConfig) -> DomainModel:
    coordinate = cell.identity.coordinates.failure_boundary_axis_and_level
    if coordinate is None:
        raise ScientificCellDispatchError("failure-boundary cell is missing axis/level")
    axis_text, separator, value_text = str(coordinate).partition("=")
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
            config=config,
        )
    if axis is FailureBoundaryAxis.OPTIMIZER_NODE_BUDGET:
        return evaluate_optimizer_node_budget(int(value_text), config)
    parsed_axis, level = _failure_coordinate(coordinate)
    return evaluate_failure_boundary(parsed_axis, level, config)


def _failure_coordinate(
    coordinate: FailureBoundaryCoordinate,
) -> tuple[FailureBoundaryAxis, float | int]:
    axis_text, separator, value_text = str(coordinate).partition("=")
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


def execute_dispatched_cell(
    cell: PlannedCell,
    context: ExecutionContext,
    config: TrajCertConfig,
) -> CellExecutionResult:
    if str(cell.identity.experiment_name) == "Statistical Synthesis":
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
        execute_scientific_cell(cell, config),
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
    principal = _parameters(config, LawKey.TIMING_TERMINAL_HARMFUL_LATE)
    timing = _parameters(config, LawKey.TIMING_HARMFUL_LATE)
    fine = build_partition(
        config.method.finest_bands,
        config.method.finest_bands,
        config.method.terminal_horizon,
    )
    coarse = build_partition(
        config.method.finest_bands,
        _SMOKE_COARSE_BANDS,
        config.method.terminal_horizon,
    )
    endpoint = build_partition(
        config.method.finest_bands,
        1,
        config.method.terminal_horizon,
    )
    principal_fine = _summary(principal, fine, config)
    timing_fine = _summary(timing, fine, config)

    principal_tau = float(observed_timing_information(principal_fine) or 0.0)
    compatible = sharp_risk_set(
        principal_fine,
        principal_tau + _SMOKE_COMPATIBLE_OFFSET,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    compatible_pass = compatible.latent_risk is not None

    timing_tau = float(observed_timing_information(timing_fine) or 0.0)
    incompatible = sharp_risk_set(
        timing_fine,
        timing_tau / 2.0,
        config.numerics.root_atol,
        config.numerics.identity_atol,
    )
    incompatible_pass = timing_tau > 0.0 and incompatible.latent_risk is None

    endpoint_summary = _summary(principal, endpoint, config)
    endpoint_tau = float(observed_timing_information(endpoint_summary) or 0.0)
    endpoint_pass = abs(endpoint_tau) <= config.numerics.identity_atol

    refinement = evaluate_partition_coherence(
        fine=principal_fine,
        coarse_partition=coarse,
        sensitivity_budget=principal_tau + _SMOKE_REFINEMENT_OFFSET,
        root_atol=config.numerics.root_atol,
        identity_atol=config.numerics.identity_atol,
        comparison_guard=config.numerics.comparison_guard,
    )
    refinement_pass = refinement.passed

    confidence_pass = _confidence_smoke(principal, config)
    projection_pass = _projection_smoke(principal, config)
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


def _confidence_smoke(parameters: LawParameters, config: TrajCertConfig) -> bool:
    partition = build_partition(
        config.method.finest_bands,
        _SMOKE_CS_BANDS,
        config.method.terminal_horizon,
    )
    ledger = generate_balanced_prefix_ledger(
        parameters,
        partition,
        0,
        _SMOKE_CS_EVENTS,
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
    return running is not None and int(running.matured_count) == _SMOKE_CS_EVENTS


def _projection_smoke(parameters: LawParameters, config: TrajCertConfig) -> bool:
    partition = build_partition(
        config.method.finest_bands,
        _SMOKE_CS_BANDS,
        config.method.terminal_horizon,
    )
    summary = _summary(parameters, partition, config)
    tau = float(observed_timing_information(summary) or 0.0)
    rho = tau + _SMOKE_COMPATIBLE_OFFSET
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
    error = abs(float(projection.proven_upper) - float(population.latent_risk.upper))
    return error <= config.numerics.identity_atol


def _parameters(config: TrajCertConfig, key: LawKey) -> LawParameters:
    law = config.laws[key]
    return LawParameters(
        key=key,
        name=LAW_DISPLAY_NAMES[key],
        theta=law.theta,
        q1=law.q1,
        q0=law.q0,
        lambda1=law.lambda1,
        lambda0=law.lambda0,
    )


def _summary(
    parameters: LawParameters,
    partition: TrajectoryPartition,
    config: TrajCertConfig,
) -> ObservableSummary:
    return summarize_full_law(
        partition,
        build_full_law(parameters, partition.band_count),
        config.numerics.comparison_guard,
    )
