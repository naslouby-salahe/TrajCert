from __future__ import annotations

import importlib
import os
import subprocess
from hashlib import sha256
from pathlib import Path

from trajcert.analysis.locality import (
    RuntimeLineageArtifact,
    ScientificInputClass,
    StaticComponentDependency,
)
from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.laws import build_full_law, configured_laws
from trajcert.data.partitions import configured_partitions
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.execution import execute_dispatched_cell, scientific_result_artifact_key
from trajcert.experiments.inventory import validate_scientific_inventory
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.registry import authoritative_registry
from trajcert.experiments.runner import (
    DependencyReadiness,
    ExecutionContext,
    cell_completion_path,
    cell_failure_path,
    cell_running_path,
    run_cell,
)
from trajcert.experiments.synthesis_execution import (
    SynthesisLocalValidityInput,
    make_statistical_synthesis_executor,
    synthesis_artifact_keys,
)
from trajcert.experiments.synthesis_inputs import synthesis_dependency_fingerprint
from trajcert.paths import ARTIFACTS_ROOT, RESULTS_ROOT
from trajcert.provenance import (
    CodeCommit,
    ContainerImageDigest,
    EnvironmentDigest,
    ExperimentNameValue,
    ProducerComponentName,
    ProvenanceMaterial,
    provenance_fingerprint,
)
from trajcert.reporting.export import ReportExportResult, export_report, validate_results_layout
from trajcert.reporting.source_data import figure_source_descriptors, table_source_descriptors
from trajcert.storage import (
    ArtifactKey,
    DependencyFingerprint,
    DigestHex,
    ProvenanceFingerprint,
    SpecificationDigest,
    atomic_write_model,
    file_digest,
    model_digest,
)
from trajcert.types import (
    ActionChannelId,
    ClientId,
    DomainModel,
    EpochId,
    PublicExecutionState,
)

_LOCK_PATH = Path("uv.lock")
_PLAN_PATH = ARTIFACTS_ROOT / "derived/plans/plan.json"
_PREPROCESS_PATH = Path("outputs/preprocessing/validation/scientific_inventory.json")
_SYNTHESIS_NAME = ExperimentNameValue("Statistical Synthesis")
_REQUIRED_IMPORTS = ("numpy", "pydantic", "pyarrow", "scipy", "flint", "mpmath", "yaml")


class OperatorCellStatus(DomainModel):
    semantic_cell_key: str
    state: PublicExecutionState


class OperatorExperimentStatus(DomainModel):
    experiment_name: ExperimentNameValue
    state: PublicExecutionState
    total_cells: int
    completed_cells: int
    failed_cells: int
    running_cells: int
    ready_cells: int


class RunExperimentResult(DomainModel):
    experiment_name: ExperimentNameValue
    state: PublicExecutionState
    completed_cells: int
    reused_cells: int
    failed_cells: int
    blocked_cells: int


class DoctorResult(DomainModel):
    configuration_valid: bool
    plan_valid: bool
    dependency_lock_valid: bool
    imports_valid: bool
    workspace_writable: bool
    publication_contract_valid: bool
    results_layout_valid: bool

    @property
    def passed(self) -> bool:
        return all(self.model_dump().values())


def doctor(workspace_root: Path = Path(".")) -> DoctorResult:
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    if plan.registry_total != sum(item.declared_cells for item in authoritative_registry()):
        raise InvalidScientificDataError("expanded plan does not match the authoritative registry")
    partitions = configured_partitions(config)
    for law in configured_laws(config):
        _ = build_full_law(law, partitions[0].band_count)
    lock_path = workspace_root / _LOCK_PATH
    if not lock_path.is_file() or lock_path.stat().st_size == 0:
        raise InvalidScientificDataError("uv.lock is missing or empty")
    for module_name in _REQUIRED_IMPORTS:
        _ = importlib.import_module(module_name)
    _assert_workspace_writable(workspace_root)
    descriptors = (*table_source_descriptors(), *figure_source_descriptors())
    if len(descriptors) != 20 or len({item.source_path for item in descriptors}) != 20:
        raise InvalidScientificDataError("publication source contract must contain 12 tables and 8 figures")
    validate_results_layout(workspace_root)
    return DoctorResult(
        configuration_valid=True,
        plan_valid=True,
        dependency_lock_valid=True,
        imports_valid=True,
        workspace_writable=True,
        publication_contract_valid=True,
        results_layout_valid=True,
    )


def preprocess(workspace_root: Path = Path(".")) -> Path:
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    result = validate_scientific_inventory(config)
    if not result.valid:
        raise InvalidScientificDataError("scientific preprocessing/inventory validation failed")
    target = workspace_root / _PREPROCESS_PATH
    _ = atomic_write_model(target, result)
    return target


def persist_plan(workspace_root: Path = Path(".")) -> Path:
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    target = workspace_root / _PLAN_PATH
    _ = atomic_write_model(target, plan)
    return target


def smoke(workspace_root: Path = Path(".")) -> RunExperimentResult:
    return run_experiment("Scientific and Data Inventory", workspace_root=workspace_root)


def run_experiment(
    experiment_name: str,
    *,
    workspace_root: Path = Path("."),
    overwrite: bool = False,
) -> RunExperimentResult:
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    name = _known_experiment_name(experiment_name)
    cells = cells_for_experiment(plan, name)
    if not cells:
        return RunExperimentResult(
            experiment_name=name,
            state=PublicExecutionState.INVALID,
            completed_cells=0,
            reused_cells=0,
            failed_cells=0,
            blocked_cells=0,
        )
    dependencies = _dependency_readiness(plan, workspace_root, cells[0])
    completed = reused = failed = blocked = 0
    for cell in cells:
        context = _execution_context(cell, plan, config, workspace_root)
        if name == _SYNTHESIS_NAME:
            executor = make_statistical_synthesis_executor(
                plan,
                config,
                _locality_input(),
            )
        else:
            executor = lambda selected, selected_context: execute_dispatched_cell(
                selected, selected_context, config
            )
        outcome = run_cell(cell, context, dependencies, executor, overwrite)
        if outcome.state is PublicExecutionState.COMPLETED:
            completed += 1
            reused += int(outcome.reused)
        elif outcome.state is PublicExecutionState.FAILED:
            failed += 1
        elif outcome.state is PublicExecutionState.BLOCKED:
            blocked += 1
    state = _run_state(len(cells), completed, failed, blocked)
    return RunExperimentResult(
        experiment_name=name,
        state=state,
        completed_cells=completed,
        reused_cells=reused,
        failed_cells=failed,
        blocked_cells=blocked,
    )


def experiment_status(
    experiment_name: str,
    *,
    workspace_root: Path = Path("."),
) -> OperatorExperimentStatus:
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    name = _known_experiment_name(experiment_name)
    cells = cells_for_experiment(plan, name)
    statuses = tuple(_persisted_cell_status(cell, workspace_root) for cell in cells)
    completed = sum(item.state is PublicExecutionState.COMPLETED for item in statuses)
    failed = sum(item.state is PublicExecutionState.FAILED for item in statuses)
    running = sum(item.state is PublicExecutionState.RUNNING for item in statuses)
    ready = sum(item.state is PublicExecutionState.READY for item in statuses)
    if not cells:
        state = PublicExecutionState.INVALID
    elif failed:
        state = PublicExecutionState.FAILED
    elif running:
        state = PublicExecutionState.RUNNING
    elif completed == len(cells):
        state = PublicExecutionState.COMPLETED
    else:
        state = PublicExecutionState.READY
    return OperatorExperimentStatus(
        experiment_name=name,
        state=state,
        total_cells=len(cells),
        completed_cells=completed,
        failed_cells=failed,
        running_cells=running,
        ready_cells=ready,
    )


def report(
    *,
    workspace_root: Path = Path("."),
    experiment_name: str | None = None,
    overwrite: bool = False,
) -> ReportExportResult:
    if experiment_name is not None:
        _ = _known_experiment_name(experiment_name)
    return export_report(
        workspace_root,
        experiment_name=experiment_name,
        overwrite=overwrite,
    )


def _known_experiment_name(value: str) -> ExperimentNameValue:
    names = tuple(item.experiment_name for item in authoritative_registry())
    requested = ExperimentNameValue(value)
    if requested not in names:
        raise InvalidScientificDataError(f"unknown experiment family: {value}")
    return requested


def _persisted_cell_status(cell: PlannedCell, workspace_root: Path) -> OperatorCellStatus:
    key = str(cell.identity.semantic_cell_key)
    if not cell.executable:
        return OperatorCellStatus(semantic_cell_key=key, state=PublicExecutionState.INVALID)
    if cell_running_path(cell, workspace_root).is_file():
        return OperatorCellStatus(semantic_cell_key=key, state=PublicExecutionState.RUNNING)
    if cell_failure_path(cell, workspace_root).is_file():
        return OperatorCellStatus(semantic_cell_key=key, state=PublicExecutionState.FAILED)
    if cell_completion_path(cell, workspace_root).is_file():
        return OperatorCellStatus(semantic_cell_key=key, state=PublicExecutionState.COMPLETED)
    return OperatorCellStatus(semantic_cell_key=key, state=PublicExecutionState.READY)


def _dependency_readiness(
    plan: ExperimentPlan,
    workspace_root: Path,
    cell: PlannedCell,
) -> tuple[DependencyReadiness, ...]:
    return tuple(
        DependencyReadiness(
            experiment_name=name,
            state=experiment_status(str(name), workspace_root=workspace_root).state,
        )
        for name in cell.required_experiments
    )


def _execution_context(
    cell: PlannedCell,
    plan: ExperimentPlan,
    config: TrajCertConfig,
    workspace_root: Path,
) -> ExecutionContext:
    configuration_digest = SpecificationDigest(str(model_digest(config)))
    scientific_dependency_digest = SpecificationDigest(
        _digest_text(f"{configuration_digest}|{cell.identity.semantic_cell_key}")
    )
    if cell.identity.experiment_name == _SYNTHESIS_NAME:
        upstream = tuple(item for item in plan.cells if item.identity != cell.identity)
        dependency = synthesis_dependency_fingerprint(upstream, workspace_root)
        required = synthesis_artifact_keys()
    else:
        parent_digests = tuple(
            str(file_digest(cell_completion_path(parent, workspace_root)))
            for parent in _parent_cells(plan, cell)
            if cell_completion_path(parent, workspace_root).is_file()
        )
        dependency = DependencyFingerprint(
            _digest_text(
                "|".join(
                    (
                        str(cell.identity.semantic_cell_key),
                        str(scientific_dependency_digest),
                        _scientific_code_digest(workspace_root),
                        *parent_digests,
                    )
                )
            )
        )
        required = (scientific_result_artifact_key(cell),)
    provenance = _provenance(plan, config, workspace_root)
    return ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=configuration_digest,
        scientific_dependency_digest=scientific_dependency_digest,
        provenance_fingerprint=provenance,
        dependency_fingerprint=dependency,
        manifest_digest=DigestHex(str(model_digest(cell))),
        required_artifact_keys=required,
        expected_seed_count=0,
    )


def _parent_cells(plan: ExperimentPlan, cell: PlannedCell) -> tuple[PlannedCell, ...]:
    required = set(cell.required_experiments)
    return tuple(item for item in plan.cells if item.identity.experiment_name in required)


def _provenance(
    plan: ExperimentPlan,
    config: TrajCertConfig,
    workspace_root: Path,
) -> ProvenanceFingerprint:
    lock = workspace_root / _LOCK_PATH
    if not lock.is_file():
        raise InvalidScientificDataError("uv.lock is required for execution provenance")
    material = ProvenanceMaterial(
        scientific_specification_digest=SpecificationDigest(str(model_digest(config))),
        code_commit=CodeCommit(_source_commit(workspace_root)),
        dirty_tree_flag=_dirty_tree(workspace_root),
        environment_lock_digest=EnvironmentDigest(str(file_digest(lock))),
        container_image_digest=None,
        dataset_preprocessing_digests=(),
        partition_digest=None,
        seed_manifest_digests=(),
        plan_digest=DigestHex(str(plan.plan_digest)),
    )
    return provenance_fingerprint(material)


def _scientific_code_digest(workspace_root: Path) -> str:
    root = workspace_root / "src/trajcert"
    digest = sha256()
    files = tuple(
        path
        for path in root.rglob("*.py")
        if "reporting" not in path.parts and path.name not in {"cli.py", "operator.py"}
    )
    for path in sorted(files):
        relative = path.relative_to(workspace_root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(bytes.fromhex(str(file_digest(path))))
    return digest.hexdigest()


def _source_commit(workspace_root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=workspace_root,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if len(commit) != 40:
        raise InvalidScientificDataError("source commit must be a full Git SHA-1")
    return commit


def _dirty_tree(workspace_root: Path) -> bool:
    result = subprocess.run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=workspace_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _locality_input() -> SynthesisLocalValidityInput:
    identity = LedgerIdentity(
        client_id=ClientId("target-client"),
        action_channel_id=ActionChannelId("target-action-channel"),
        epoch_id=EpochId("target-epoch"),
    )
    components = (
        "inference/categorical.py",
        "inference/confidence.py",
        "inference/envelope.py",
        "inference/projection.py",
        "inference/certification.py",
    )
    dependencies = tuple(
        StaticComponentDependency(
            producer_component=ProducerComponentName(component),
            scientific_input_classes=(ScientificInputClass.LOCAL_NUMERICAL_DEPENDENCY,),
            scientific_client_ids=(),
        )
        for component in components
    )
    root_key = ArtifactKey("local-bound-root")
    lineage = (
        RuntimeLineageArtifact(
            artifact_key=root_key,
            client_id=identity.client_id,
            action_channel_id=identity.action_channel_id,
            epoch_id=identity.epoch_id,
        ),
    )
    return SynthesisLocalValidityInput(
        target_identity=identity,
        static_dependencies=dependencies,
        root_artifact_key=root_key,
        lineage_artifacts=lineage,
    )


def _assert_workspace_writable(workspace_root: Path) -> None:
    for relative in (Path("outputs"), RESULTS_ROOT):
        directory = workspace_root / relative
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".trajcert-write-probe"
        try:
            probe.write_bytes(b"")
        except OSError as exc:
            raise InvalidScientificDataError(f"workspace is not writable: {directory}") from exc
        finally:
            probe.unlink(missing_ok=True)


def _run_state(total: int, completed: int, failed: int, blocked: int) -> PublicExecutionState:
    if failed:
        return PublicExecutionState.FAILED
    if blocked:
        return PublicExecutionState.BLOCKED
    if completed == total:
        return PublicExecutionState.COMPLETED
    return PublicExecutionState.READY


def _digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
