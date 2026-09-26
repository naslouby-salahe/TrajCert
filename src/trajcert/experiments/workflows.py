from __future__ import annotations

import importlib
import multiprocessing
import os
import time
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from enum import StrEnum
from pathlib import Path

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH, SMOKE_CONFIG_OVERRIDES_PATH
from trajcert.data.laws import (
    LawParameters,
    build_full_law,
    configured_laws,
    prepared_synthetic_law,
)
from trajcert.data.partitions import build_partition
from trajcert.data.real_trajectories import (
    PreparedRealTrajectoryCohort,
    build_real_trajectory_eligibility,
    inventory_real_trajectory_dataset,
    validate_dataset_schema,
    verify_dataset_integrity,
)
from trajcert.data.synthetic import observable_category_probabilities
from trajcert.exceptions import InvalidScientificDataError, SerializationError
from trajcert.experiments.artifacts import (
    cell_dependency_material,
    scientific_result_artifact_key,
    scientific_specification_digest,
)
from trajcert.experiments.catalog import supports_batched_recovery
from trajcert.experiments.models import (
    CellExecutionResult,
    CellExecutor,
    CellRunOutcome,
    DependencyReadiness,
    ExecutionContext,
)
from trajcert.experiments.plan import (
    ExperimentPlan,
    PlannedCell,
    build_plan,
    cells_for_experiment,
    dependency_graph,
)
from trajcert.experiments.runner import (
    dependency_block_reason,
    execute_dispatched_cell,
    expected_seed_count,
    run_cell,
)
from trajcert.experiments.smoke import SmokeResult, run_smoke_fixtures
from trajcert.experiments.status import (
    CellStatus,
    ExperimentStatus,
    aggregate_experiment_status,
    inspect_cell_status,
)
from trajcert.experiments.synthesis import (
    make_statistical_synthesis_executor,
    synthesis_artifact_keys,
    synthesis_dependency_fingerprint,
)
from trajcert.paths import (
    OUTPUTS_ROOT,
    RESULTS_ROOT,
    ArtifactFile,
    ExperimentLeaf,
    PlanArtifactFile,
    PreprocessingLeaf,
    RealTrajectoryArtifactFile,
    experiment_leaf,
    plan_artifact_path,
    preprocessing_leaf,
    real_trajectory_preprocessing_path,
    semantic_slug,
)
from trajcert.provenance import dependency_fingerprint
from trajcert.reporting.export import (
    LOCK_PATH,
    ReportExportResult,
    export_report,
    validate_results_layout,
)
from trajcert.reporting.figures import render_figure
from trajcert.reporting.source_data import (
    figure_source_descriptors,
    read_verified_source_data,
    table_source_descriptors,
)
from trajcert.reporting.tables import render_table
from trajcert.schemas import (
    PreparedSyntheticLawArtifact,
    RealTrajectoryPreprocessingInventory,
    SyntheticPreprocessingInventory,
)
from trajcert.storage import atomic_write_model, file_digest, read_model
from trajcert.telemetry import (
    ExperimentProgress,
    PreprocessingProgress,
    attach_execution_log_file,
    configure_logging,
    detach_execution_log_file,
    observable_workflow,
)
from trajcert.types import (
    ArtifactFileName,
    Count,
    DatasetChecksumHex,
    DomainModel,
    EnvironmentDigest,
    ExperimentName,
    ExperimentSlug,
    LawName,
    PublicExecutionState,
    RawDatasetRoot,
    RealTrajectoryDatasetName,
    ReasonCode,
    SemanticCellKey,
    TimestampSeconds,
    WorkflowName,
)


class CliRuntimeModule(StrEnum):
    NUMPY = "numpy"
    PYDANTIC = "pydantic"
    PYARROW = "pyarrow"
    SCIPY = "scipy"
    FLINT = "flint"
    MPMATH = "mpmath"
    YAML = "yaml"


class CliProcessStartMethod(StrEnum):
    SPAWN = "spawn"


_PREPROCESS_PATH = (
    preprocessing_leaf(PreprocessingLeaf.VALIDATION_INTEGRITY) / ArtifactFile.SCIENTIFIC_INVENTORY
)
_REQUIRED_IMPORTS = tuple(CliRuntimeModule)


class RunExperimentResult(DomainModel):
    experiment_name: ExperimentName
    state: PublicExecutionState
    completed_cells: Count
    reused_cells: Count
    failed_cells: Count
    blocked_cells: Count


class DoctorResult(DomainModel):
    configuration_valid: bool
    plan_valid: bool
    dependency_lock_valid: bool
    imports_valid: bool
    workspace_writable: bool
    dataset_valid: bool
    publication_contract_valid: bool
    results_layout_valid: bool

    @property
    def passed(self) -> bool:
        return all(self.model_dump().values())


@observable_workflow(WorkflowName.DOCTOR)
def doctor(workspace_root: Path | None = None) -> DoctorResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = _load_config(workspace_root)
    _ = build_plan(config)
    finest = config.method.finest_bands
    _ = active_config.set(config)
    for parameters in configured_laws():
        _ = build_full_law(parameters, finest)
    for bands in config.grids.partitions:
        _ = build_partition(finest, bands, config.method.terminal_horizon)
    _ = verify_dataset_integrity(RawDatasetRoot(config.real_trajectory.dataset_root))
    lock_path = workspace_root / LOCK_PATH
    if not lock_path.is_file() or lock_path.stat().st_size == 0:
        raise InvalidScientificDataError("requirements.lock is missing or empty")
    for module_name in _REQUIRED_IMPORTS:
        _ = importlib.import_module(module_name)
    _assert_workspace_writable(workspace_root)
    tables = table_source_descriptors()
    figures = figure_source_descriptors()
    descriptors = (*tables, *figures)
    if (
        len(tables) != config.publication.table_count
        or len(figures) != config.publication.figure_count
        or len({item.source_path for item in descriptors})
        != config.publication.table_count + config.publication.figure_count
    ):
        raise InvalidScientificDataError(
            "publication source contract must contain "
            + f"{config.publication.table_count} tables and "
            + f"{config.publication.figure_count} figures"
        )
    validate_results_layout(workspace_root)
    return DoctorResult(
        configuration_valid=True,
        plan_valid=True,
        dependency_lock_valid=True,
        imports_valid=True,
        workspace_writable=True,
        dataset_valid=True,
        publication_contract_valid=True,
        results_layout_valid=True,
    )


@observable_workflow(WorkflowName.PREPROCESS)
def preprocess(
    dataset_name: LawName | RealTrajectoryDatasetName | None = None,
    *,
    workspace_root: Path | None = None,
    overwrite: bool = False,
) -> Path:
    workspace_root = workspace_root if workspace_root is not None else Path()
    if isinstance(dataset_name, RealTrajectoryDatasetName):
        _ = _load_config(workspace_root)
        return _preprocess_real_trajectory(workspace_root, overwrite=overwrite)
    config = _load_config(workspace_root)
    finest = config.method.finest_bands
    selected = tuple(
        parameters
        for parameters in configured_laws()
        if dataset_name is None or parameters.name == dataset_name
    )
    target = workspace_root / _PREPROCESS_PATH
    if not overwrite and _synthetic_preprocessing_is_current(target, workspace_root, selected):
        return target
    prepared: list[PreparedSyntheticLawArtifact] = []
    partitions = tuple(
        build_partition(finest, bands, config.method.terminal_horizon)
        for bands in config.grids.partitions
    )
    for parameters in selected:
        full_law = build_full_law(parameters, finest)
        _ = observable_category_probabilities(full_law)
        manifest = prepared_synthetic_law(parameters, full_law, partitions)
        relative_path = _synthetic_law_manifest_path(parameters.name)
        digest = atomic_write_model(workspace_root / relative_path, manifest)
        prepared.append(
            PreparedSyntheticLawArtifact(
                law_name=parameters.name,
                relative_path=relative_path,
                sha256=digest,
            )
        )
    _ = atomic_write_model(
        target,
        SyntheticPreprocessingInventory(
            scientific_specification_digest=scientific_specification_digest(),
            prepared_laws=tuple(prepared),
        ),
    )
    return target


def _synthetic_law_manifest_path(law_name: LawName) -> Path:
    return (
        preprocessing_leaf(PreprocessingLeaf.PREPARED_LAWS)
        / semantic_slug(law_name)
        / ArtifactFile.SCIENTIFIC_INVENTORY
    )


def _synthetic_preprocessing_is_current(
    target: Path,
    workspace_root: Path,
    selected: tuple[LawParameters, ...],
) -> bool:
    if not target.is_file():
        return False
    try:
        inventory = read_model(target, SyntheticPreprocessingInventory)
    except SerializationError:
        return False
    selected_names = tuple(parameters.name for parameters in selected)
    if (
        inventory.scientific_specification_digest != scientific_specification_digest()
        or tuple(item.law_name for item in inventory.prepared_laws) != selected_names
    ):
        return False
    return all(
        (workspace_root / item.relative_path).is_file()
        and file_digest(workspace_root / item.relative_path) == item.sha256
        for item in inventory.prepared_laws
    )


def _preprocess_real_trajectory(workspace_root: Path, *, overwrite: bool) -> Path:
    dataset_name = RealTrajectoryDatasetName.HITL_IOT
    target = workspace_root / real_trajectory_preprocessing_path(
        PreprocessingLeaf.PREPARED_REAL_TRAJECTORIES, RealTrajectoryArtifactFile.PREPARED_COHORT
    )
    config = active_config.get()
    dataset_root = RawDatasetRoot(config.real_trajectory.dataset_root)
    provenance = verify_dataset_integrity(dataset_root)
    inventory_path = workspace_root / _real_trajectory_preprocessing_inventory_path(dataset_name)
    if not overwrite and _real_trajectory_preprocessing_is_current(
        target, inventory_path, provenance.dataset_sha256
    ):
        return target
    progress = PreprocessingProgress(dataset_name)
    progress.started()
    progress.dataset_located(
        provenance.source_reference, provenance.dataset_sha256, provenance.total_rows
    )
    inventory = inventory_real_trajectory_dataset(dataset_root)
    _ = atomic_write_model(
        workspace_root
        / real_trajectory_preprocessing_path(
            PreprocessingLeaf.INVENTORIES_REAL_TRAJECTORIES,
            RealTrajectoryArtifactFile.DATASET_INVENTORY,
        ),
        inventory,
    )
    schema = validate_dataset_schema(dataset_root)
    progress.schema_validated()
    events, report = build_real_trajectory_eligibility(dataset_root)
    progress.eligibility_computed(report.candidate_rows, report.eligible_rows, report.excluded_rows)
    progress.exclusion_breakdown(
        tuple((item.reason, item.count) for item in report.excluded_by_reason)
    )
    _ = atomic_write_model(
        workspace_root
        / real_trajectory_preprocessing_path(
            PreprocessingLeaf.INVENTORIES_REAL_TRAJECTORIES,
            RealTrajectoryArtifactFile.DATASET_PROVENANCE,
        ),
        provenance,
    )
    _ = atomic_write_model(
        workspace_root
        / real_trajectory_preprocessing_path(
            PreprocessingLeaf.VALIDATION_TRAJECTORY_CONSISTENCY,
            RealTrajectoryArtifactFile.SCHEMA_VALIDATION,
        ),
        schema,
    )
    _ = atomic_write_model(
        workspace_root
        / real_trajectory_preprocessing_path(
            PreprocessingLeaf.INVENTORIES_REAL_TRAJECTORIES,
            RealTrajectoryArtifactFile.ELIGIBILITY_REPORT,
        ),
        report,
    )
    prepared_digest = atomic_write_model(target, PreparedRealTrajectoryCohort(events=events))
    _ = atomic_write_model(
        inventory_path,
        RealTrajectoryPreprocessingInventory(
            scientific_specification_digest=scientific_specification_digest(),
            dataset_sha256=provenance.dataset_sha256,
            prepared_cohort_sha256=prepared_digest,
        ),
    )
    progress.completed(target)
    return target


def _real_trajectory_preprocessing_inventory_path(
    dataset_name: RealTrajectoryDatasetName,
) -> Path:
    return (
        preprocessing_leaf(PreprocessingLeaf.METADATA_PREPARATION_RECORDS)
        / semantic_slug(dataset_name)
        / ArtifactFile.SCIENTIFIC_INVENTORY
    )


def _real_trajectory_preprocessing_is_current(
    target: Path,
    inventory_path: Path,
    dataset_sha256: DatasetChecksumHex,
) -> bool:
    if not target.is_file() or not inventory_path.is_file():
        return False
    try:
        inventory = read_model(inventory_path, RealTrajectoryPreprocessingInventory)
        _ = read_model(target, PreparedRealTrajectoryCohort)
    except SerializationError:
        return False
    return (
        inventory.scientific_specification_digest == scientific_specification_digest()
        and inventory.dataset_sha256 == dataset_sha256
        and inventory.prepared_cohort_sha256 == file_digest(target)
    )


@observable_workflow(WorkflowName.PLAN)
def plan_view(workspace_root: Path | None = None) -> ExperimentPlan:
    workspace_root = workspace_root if workspace_root is not None else Path()
    return build_plan(_load_config(workspace_root))


def _persist_plan_artifacts(workspace_root: Path, plan: ExperimentPlan) -> None:
    _ = atomic_write_model(
        workspace_root / plan_artifact_path(PlanArtifactFile.EXPERIMENT_PLAN), plan
    )
    _ = atomic_write_model(
        workspace_root / plan_artifact_path(PlanArtifactFile.DEPENDENCY_GRAPH),
        dependency_graph(plan),
    )


@observable_workflow(WorkflowName.SMOKE)
def smoke(workspace_root: Path | None = None) -> SmokeResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = TrajCertConfig.from_yaml_with_overrides(
        workspace_root / PRODUCTION_CONFIG_PATH, workspace_root / SMOKE_CONFIG_OVERRIDES_PATH
    )
    _ = active_config.set(config)
    return run_smoke_fixtures(config)


@observable_workflow(WorkflowName.RUN_EXPERIMENT)
def run_experiment(
    experiment_name: ExperimentName,
    *,
    workspace_root: Path | None = None,
    overwrite: bool = False,
    max_workers: Count | None = None,
) -> RunExperimentResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = _load_config(workspace_root)
    plan = build_plan(config)
    _persist_plan_artifacts(workspace_root, plan)
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
    status_cache: dict[ExperimentName, ExperimentStatus] = {}
    dependencies = _dependency_readiness(plan, workspace_root, cells[0], status_cache)
    progress = ExperimentProgress(name, len(cells))
    log_handler = attach_execution_log_file(workspace_root / _execution_log_path(name))
    try:
        if (
            name is ExperimentName.STATISTICAL_SYNTHESIS
            or max_workers == 1
            or supports_batched_recovery(name)
        ):
            completed, reused, failed, blocked = _run_cells_sequentially(
                cells,
                plan,
                workspace_root,
                dependencies,
                _executor(name, plan),
                overwrite,
                progress,
            )
        else:
            completed, reused, failed, blocked = _run_cells_in_parallel(
                cells, plan, workspace_root, dependencies, overwrite, progress, max_workers
            )
        state = _run_state(len(cells), completed, failed, blocked)
        progress.experiment_finished(state, completed, reused, failed, blocked)
        if name is ExperimentName.STATISTICAL_SYNTHESIS and state is PublicExecutionState.COMPLETED:
            _render_synthesis_publication_artifacts(workspace_root)
    finally:
        detach_execution_log_file(log_handler)
    return RunExperimentResult(
        experiment_name=name,
        state=state,
        completed_cells=completed,
        reused_cells=reused,
        failed_cells=failed,
        blocked_cells=blocked,
    )


def _execution_log_path(name: ExperimentName) -> Path:
    slug = ExperimentSlug(semantic_slug(name))
    filename = ArtifactFileName(f"{time.strftime('%Y%m%dT%H%M%S')}.log")
    return experiment_leaf(slug, ExperimentLeaf.LOGS_EXECUTION) / filename


def _render_synthesis_publication_artifacts(workspace_root: Path) -> None:
    for descriptor in table_source_descriptors():
        verified = read_verified_source_data(workspace_root, descriptor)
        destination = workspace_root / experiment_leaf(
            descriptor.owner_experiment, ExperimentLeaf.TABLES_MAIN
        )
        _ = render_table(verified, destination)
    for descriptor in figure_source_descriptors():
        verified = read_verified_source_data(workspace_root, descriptor)
        destination = workspace_root / experiment_leaf(
            descriptor.owner_experiment, ExperimentLeaf.FIGURES_MAIN
        )
        _ = render_figure(verified, destination)


def _run_cells_sequentially(
    cells: tuple[PlannedCell, ...],
    plan: ExperimentPlan,
    workspace_root: Path,
    dependencies: tuple[DependencyReadiness, ...],
    executor: CellExecutor,
    overwrite: bool,
    progress: ExperimentProgress,
) -> tuple[Count, Count, Count, Count]:
    completed = reused = failed = blocked = 0
    for cell in cells:
        context = _execution_context(cell, plan, workspace_root)
        semantic_cell_key = cell.identity.semantic_cell_key
        started_at = progress.cell_started(semantic_cell_key)
        outcome = run_cell(cell, context, dependencies, executor, overwrite)
        progress.cell_finished(semantic_cell_key, outcome.state, outcome.reused, started_at)
        completed, reused, failed, blocked = _tally_outcome(
            outcome, completed, reused, failed, blocked
        )
    return completed, reused, failed, blocked


def _run_cells_in_parallel(
    cells: tuple[PlannedCell, ...],
    plan: ExperimentPlan,
    workspace_root: Path,
    dependencies: tuple[DependencyReadiness, ...],
    overwrite: bool,
    progress: ExperimentProgress,
    max_workers: Count | None,
) -> tuple[Count, Count, Count, Count]:
    completed = reused = failed = blocked = 0
    available_workers = max_workers if max_workers is not None else (os.cpu_count() or 1)
    worker_count = min(len(cells), available_workers)
    spawn_context = multiprocessing.get_context(CliProcessStartMethod.SPAWN)
    with ProcessPoolExecutor(max_workers=worker_count, mp_context=spawn_context) as pool:
        futures: dict[Future[CellRunOutcome], tuple[SemanticCellKey, TimestampSeconds]] = {}
        for cell in cells:
            context = _execution_context(cell, plan, workspace_root)
            semantic_cell_key = cell.identity.semantic_cell_key
            started_at = progress.cell_started(semantic_cell_key)
            future = pool.submit(
                _run_cell_worker, cell, context, dependencies, overwrite, workspace_root
            )
            futures[future] = (semantic_cell_key, started_at)
        for future in as_completed(futures):
            semantic_cell_key, started_at = futures[future]
            outcome = future.result()
            progress.cell_finished(semantic_cell_key, outcome.state, outcome.reused, started_at)
            completed, reused, failed, blocked = _tally_outcome(
                outcome, completed, reused, failed, blocked
            )
    return completed, reused, failed, blocked


def _run_cell_worker(
    cell: PlannedCell,
    context: ExecutionContext,
    dependencies: tuple[DependencyReadiness, ...],
    overwrite: bool,
    workspace_root: Path,
) -> CellRunOutcome:
    _ = _load_config(workspace_root)
    configure_logging()
    return run_cell(cell, context, dependencies, execute_dispatched_cell, overwrite)


def _tally_outcome(
    outcome: CellRunOutcome,
    completed: Count,
    reused: Count,
    failed: Count,
    blocked: Count,
) -> tuple[Count, Count, Count, Count]:
    if outcome.state is PublicExecutionState.COMPLETED:
        completed += 1
        reused += outcome.reused
    elif outcome.state is PublicExecutionState.FAILED:
        failed += 1
    elif outcome.state is PublicExecutionState.BLOCKED:
        blocked += 1
    return completed, reused, failed, blocked


@observable_workflow(WorkflowName.EXPERIMENT_STATUS)
def experiment_status(
    experiment_name: ExperimentName,
    *,
    workspace_root: Path | None = None,
) -> ExperimentStatus:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = _load_config(workspace_root)
    plan = build_plan(config)
    return _experiment_status(_known_experiment_name(experiment_name), plan, workspace_root, {})


@observable_workflow(WorkflowName.REPORT)
def report(
    *,
    workspace_root: Path | None = None,
    experiment_name: ExperimentName | None = None,
    overwrite: bool = False,
) -> ReportExportResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    _ = _load_config(workspace_root)
    validated_name = None if experiment_name is None else _known_experiment_name(experiment_name)
    try:
        return export_report(workspace_root, experiment_name=validated_name, overwrite=overwrite)
    except SerializationError as error:
        raise InvalidScientificDataError(
            "report evidence is missing, unreadable, or incomplete"
        ) from error


def _load_config(workspace_root: Path) -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    _ = active_config.set(config)
    return config


def _known_experiment_name(value: ExperimentName) -> ExperimentName:
    try:
        return ExperimentName(value)
    except ValueError as error:
        raise InvalidScientificDataError(f"unknown experiment family: {value}") from error


def _experiment_status(
    name: ExperimentName,
    plan: ExperimentPlan,
    workspace_root: Path,
    cache: dict[ExperimentName, ExperimentStatus],
) -> ExperimentStatus:
    cached = cache.get(name)
    if cached is not None:
        return cached
    cells = cells_for_experiment(plan, name)
    statuses = tuple(_current_cell_status(cell, plan, workspace_root, cache) for cell in cells)
    declared_cells = len(cells)
    result = aggregate_experiment_status(name, statuses, declared_cells)
    cache[name] = result
    return result


def _current_cell_status(
    cell: PlannedCell,
    plan: ExperimentPlan,
    workspace_root: Path,
    cache: dict[ExperimentName, ExperimentStatus],
) -> CellStatus:
    key = cell.identity.semantic_cell_key
    if not cell.executable:
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.INVALID,
            reason=cell.invalid_reason,
        )
    dependencies = _dependency_readiness(plan, workspace_root, cell, cache)
    reason = dependency_block_reason(cell, dependencies)
    if reason is not None:
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.BLOCKED,
            reason=reason,
        )
    try:
        context = _execution_context(cell, plan, workspace_root)
    except InvalidScientificDataError:
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.BLOCKED,
            reason=ReasonCode.CURRENT_EXECUTION_CONTEXT_UNAVAILABLE,
        )
    return inspect_cell_status(cell, context, dependencies)


def _dependency_readiness(
    plan: ExperimentPlan,
    workspace_root: Path,
    cell: PlannedCell,
    cache: dict[ExperimentName, ExperimentStatus],
) -> tuple[DependencyReadiness, ...]:
    return tuple(
        DependencyReadiness(
            experiment_name=name,
            state=_experiment_status(name, plan, workspace_root, cache).state,
        )
        for name in cell.required_experiments
    )


def _executor(name: ExperimentName, plan: ExperimentPlan) -> CellExecutor:
    if name is ExperimentName.STATISTICAL_SYNTHESIS:
        return make_statistical_synthesis_executor(plan)

    def execute(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
        return execute_dispatched_cell(cell, context)

    return execute


def _execution_context(
    cell: PlannedCell,
    plan: ExperimentPlan,
    workspace_root: Path,
) -> ExecutionContext:
    specification = scientific_specification_digest()
    environment_digest = _environment_digest(workspace_root)
    if cell.identity.experiment_name is ExperimentName.STATISTICAL_SYNTHESIS:
        upstream = tuple(item for item in plan.cells if item.identity != cell.identity)
        dependency = synthesis_dependency_fingerprint(upstream, workspace_root)
        required = synthesis_artifact_keys(cell)
    else:
        dependency_material = cell_dependency_material(
            workspace_root,
            plan,
            cell,
            specification,
            environment_digest,
        )
        dependency = dependency_fingerprint(dependency_material)
        required = (scientific_result_artifact_key(cell),)
    return ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=specification,
        dependency_fingerprint=dependency,
        required_artifact_keys=required,
        expected_seed_count=expected_seed_count(cell.identity.experiment_name),
    )


def _environment_digest(workspace_root: Path) -> EnvironmentDigest:
    lock = workspace_root / LOCK_PATH
    if not lock.is_file():
        raise InvalidScientificDataError("requirements.lock is required for execution provenance")
    return EnvironmentDigest(file_digest(lock))


def _assert_workspace_writable(workspace_root: Path) -> None:
    if not workspace_root.is_dir() or not os.access(workspace_root, os.W_OK):
        raise InvalidScientificDataError(f"workspace is not writable: {workspace_root}")
    for relative in (OUTPUTS_ROOT, RESULTS_ROOT):
        directory = workspace_root / relative
        if directory.exists() and (not directory.is_dir() or not os.access(directory, os.W_OK)):
            raise InvalidScientificDataError(f"workspace path is not writable: {directory}")


def _run_state(
    total: Count, completed: Count, failed: Count, blocked: Count
) -> PublicExecutionState:
    if failed:
        return PublicExecutionState.FAILED
    if blocked:
        return PublicExecutionState.BLOCKED
    if completed == total:
        return PublicExecutionState.COMPLETED
    return PublicExecutionState.READY
