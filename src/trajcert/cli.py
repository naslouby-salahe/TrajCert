from __future__ import annotations

import importlib
import multiprocessing
import os
import subprocess
import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from enum import IntEnum
from pathlib import Path
from typing import cast

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH, SMOKE_CONFIG_OVERRIDES_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES, build_full_law, configured_laws
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.partitions import build_partition
from trajcert.exceptions import InvalidScientificDataError, TrajCertError
from trajcert.experiments.plan import (
    ExperimentPlan,
    PlannedCell,
    build_plan,
    cells_for_experiment,
    dependency_graph,
    experiment_names,
)
from trajcert.experiments.runner import (
    CellExecutionResult,
    CellExecutor,
    CellRunOutcome,
    DependencyReadiness,
    ExecutionContext,
    LocalValidityTarget,
    RuntimeLineageArtifact,
    ScientificInputClass,
    SmokeResult,
    StaticComponentDependency,
    cell_dependency_fingerprint,
    dependency_block_reason,
    execute_dispatched_cell,
    expected_seed_count,
    producer_component_digest,
    run_cell,
    run_smoke_fixtures,
    scientific_dependency_digest,
    scientific_result_artifact_key,
    scientific_specification_digest,
)
from trajcert.experiments.status import (
    CellStatus,
    ExperimentStatus,
    aggregate_experiment_status,
    inspect_cell_status,
)
from trajcert.experiments.synthesis import (
    SynthesisLocalValidityInput,
    make_statistical_synthesis_executor,
    synthesis_artifact_keys,
    synthesis_dependency_fingerprint,
)
from trajcert.paths import (
    OUTPUTS_ROOT,
    RESULTS_ROOT,
    ExperimentLeaf,
    PreprocessingLeaf,
    SharedArtifactCategory,
    experiment_leaf,
    preprocessing_leaf,
    semantic_slug,
    shared_artifact_path,
)
from trajcert.provenance import (
    EnvironmentDigest,
    ProducerComponentName,
    ProvenanceMaterial,
    provenance_fingerprint,
)
from trajcert.reporting.export import (
    LOCK_PATH,
    ReportExportResult,
    export_report,
    source_commit,
    validate_results_layout,
)
from trajcert.reporting.figures import render_figure
from trajcert.reporting.source_data import (
    figure_source_descriptors,
    read_verified_source_data,
    table_source_descriptors,
)
from trajcert.reporting.tables import render_table
from trajcert.storage import (
    DigestHex,
    ProvenanceFingerprint,
    SemanticCellKey,
    SpecificationDigest,
    atomic_write_model,
    file_digest,
    model_digest,
)
from trajcert.telemetry import ExperimentProgress, configure_logging
from trajcert.types import (
    ActionChannelId,
    CliCommand,
    ClientId,
    Count,
    DomainModel,
    EpochId,
    ExperimentName,
    PublicExecutionState,
    ReasonCode,
)


class CliExitCode(IntEnum):
    SUCCESS_OR_SCIENTIFIC_NOOP = 0
    USAGE_OR_UNKNOWN_NAME = 2
    ENVIRONMENT_OR_PREREQUISITE_BLOCK = 10
    TECHNICAL_EXECUTION_FAILURE = 20
    COMPLETION_OR_EVIDENCE_FAILURE = 30


class CliArguments(DomainModel):
    command: CliCommand
    experiment_name: str | None
    dataset_name: str | None
    overwrite: bool


def main() -> None:
    configure_logging()
    arguments = parse_args()
    try:
        _dispatch(arguments)
    except InvalidScientificDataError as exc:
        print(f"TrajCert: {exc}", file=sys.stderr)
        code = (
            CliExitCode.COMPLETION_OR_EVIDENCE_FAILURE
            if arguments.command is CliCommand.REPORT
            else CliExitCode.ENVIRONMENT_OR_PREREQUISITE_BLOCK
        )
        raise SystemExit(code) from exc
    except TrajCertError as exc:
        print(f"TrajCert: {exc}", file=sys.stderr)
        raise SystemExit(CliExitCode.TECHNICAL_EXECUTION_FAILURE) from exc


def parse_args(argv: Sequence[str] | None = None) -> CliArguments:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    command = CliCommand(cast(str, arguments.command))
    raw_name = getattr(arguments, "experiment_name", None)
    raw_dataset_name = getattr(arguments, "dataset_name", None)
    return CliArguments(
        command=command,
        experiment_name=None if raw_name is None else cast(str, raw_name),
        dataset_name=None if raw_dataset_name is None else cast(str, raw_dataset_name),
        overwrite=cast(bool, getattr(arguments, "overwrite", False)),
    )


def _dispatch(arguments: CliArguments) -> None:
    command = arguments.command
    if command is CliCommand.DOCTOR:
        result = doctor()
        if result.passed:
            print("TrajCert doctor: PASS")
        else:
            print("TrajCert doctor: FAIL")
    elif command is CliCommand.PREPROCESS:
        name = _dataset_name(arguments)
        target = preprocess(name, overwrite=arguments.overwrite)
        print(target)
    elif command is CliCommand.PLAN:
        plan = plan_view()
        print(
            f"TrajCert plan: {plan.planned_cell_count} cells "
            + f"({plan.executable_cells} executable, {plan.invalid_cells} invalid)"
        )
    elif command is CliCommand.SMOKE:
        _print_smoke(smoke())
    elif command is CliCommand.RUN:
        name = _experiment_name(arguments, required=True)
        assert name is not None
        _print_run(run_experiment(name, overwrite=arguments.overwrite))
    elif command is CliCommand.STATUS:
        name = _experiment_name(arguments, required=False)
        if name is None:
            _print_project_status()
        else:
            _print_status(experiment_status(name))
    elif command is CliCommand.REPORT:
        name = _experiment_name(arguments, required=False)
        exported = report(
            experiment_name=name,
            overwrite=arguments.overwrite,
        )
        action = "reused" if exported.reused else "rendered"
        target = exported.target.as_posix()
        print(
            f"TrajCert report: {action} {exported.rendered_artifact_count} artifacts "
            + f"from {exported.source_artifact_count} verified sources at {target}"
        )


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="trajcert")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (CliCommand.DOCTOR, CliCommand.PLAN):
        _ = subparsers.add_parser(command)
    preprocess_parser = subparsers.add_parser(CliCommand.PREPROCESS)
    _ = preprocess_parser.add_argument("dataset_name", nargs="?")
    _ = preprocess_parser.add_argument("--overwrite", action="store_true")
    smoke_parser = subparsers.add_parser(CliCommand.SMOKE)
    _ = smoke_parser.add_argument("--overwrite", action="store_true")
    run_parser = subparsers.add_parser(CliCommand.RUN)
    _ = run_parser.add_argument("experiment_name")
    _ = run_parser.add_argument("--overwrite", action="store_true")
    status_parser = subparsers.add_parser(CliCommand.STATUS)
    _ = status_parser.add_argument("experiment_name", nargs="?")
    report_parser = subparsers.add_parser(CliCommand.REPORT)
    _ = report_parser.add_argument("experiment_name", nargs="?")
    _ = report_parser.add_argument("--overwrite", action="store_true")
    return parser


def _experiment_name(arguments: CliArguments, *, required: bool) -> str | None:
    value = arguments.experiment_name
    if value is None:
        if required:
            build_parser().error("experiment name is required")
        return None
    if not value:
        build_parser().error("experiment name must be a non-empty descriptive name")
    known = set(experiment_names())
    if value not in known:
        build_parser().error(f"unknown experiment name: {value}")
    return value


def _dataset_name(arguments: CliArguments) -> str | None:
    value = arguments.dataset_name
    if value is None:
        return None
    if not value or value not in LAW_DISPLAY_NAMES.values():
        build_parser().error(f"unknown dataset name: {value}")
    return value


def _print_run(result: RunExperimentResult) -> None:
    print(
        f"{result.experiment_name}: {result.state} "
        + f"({result.completed_cells} completed, {result.reused_cells} reused, "
        + f"{result.failed_cells} failed, {result.blocked_cells} blocked)"
    )


def _print_status(status: ExperimentStatus) -> None:
    print(
        f"{status.experiment_name}: {status.state} "
        + f"({status.completed_cells}/{status.total_cells} completed, "
        + f"{status.invalid_cells} invalid, {status.failed_cells} failed, "
        + f"{status.blocked_cells} blocked, {status.running_cells} running)"
    )


def _print_project_status() -> None:
    statuses = tuple(experiment_status(item) for item in experiment_names())
    completed = sum(item.state is PublicExecutionState.COMPLETED for item in statuses)
    failed = sum(item.state is PublicExecutionState.FAILED for item in statuses)
    blocked = sum(item.state is PublicExecutionState.BLOCKED for item in statuses)
    running = sum(item.state is PublicExecutionState.RUNNING for item in statuses)
    print(
        f"TrajCert status: {completed}/{len(statuses)} experiments completed, "
        + f"{failed} failed, {blocked} blocked, {running} running"
    )


def _print_smoke(result: SmokeResult) -> None:
    state = "PASS" if result.passed else "FAIL"
    print(f"TrajCert smoke: {state} ({result.passed_fixture_count}/6 fixtures passed)")


_PREPROCESS_PATH = (
    preprocessing_leaf(PreprocessingLeaf.VALIDATION_INTEGRITY) / "scientific_inventory.json"
)
_SYNTHESIS_NAME = ExperimentName.STATISTICAL_SYNTHESIS
_REQUIRED_IMPORTS = ("numpy", "pydantic", "pyarrow", "scipy", "flint", "mpmath", "yaml")
_LOCAL_BOUND_EXPERIMENTS = (
    ExperimentName.ANYTIME_COVERAGE_STRESS,
    ExperimentName.SEQUENTIAL_SENSITIVITY_UTILITY,
)


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
    source_control_valid: bool
    workspace_writable: bool
    publication_contract_valid: bool
    results_layout_valid: bool

    @property
    def passed(self) -> bool:
        return all(self.model_dump().values())


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
    lock_path = workspace_root / LOCK_PATH
    if not lock_path.is_file() or lock_path.stat().st_size == 0:
        raise InvalidScientificDataError("uv.lock is missing or empty")
    for module_name in _REQUIRED_IMPORTS:
        _ = importlib.import_module(module_name)
    _ = source_commit(workspace_root)
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
            "publication source contract must contain 8 tables and 8 figures"
        )
    validate_results_layout(workspace_root)
    return DoctorResult(
        configuration_valid=True,
        plan_valid=True,
        dependency_lock_valid=True,
        imports_valid=True,
        source_control_valid=True,
        workspace_writable=True,
        publication_contract_valid=True,
        results_layout_valid=True,
    )


def preprocess(
    dataset_name: str | None = None,
    *,
    workspace_root: Path | None = None,
    overwrite: bool = False,
) -> Path:
    workspace_root = workspace_root if workspace_root is not None else Path()
    target = workspace_root / _PREPROCESS_PATH
    if not overwrite and target.is_file():
        return target
    _ = dataset_name
    _ = atomic_write_model(target, _load_config(workspace_root))
    return target


def plan_view(workspace_root: Path | None = None) -> ExperimentPlan:
    workspace_root = workspace_root if workspace_root is not None else Path()
    plan = build_plan(_load_config(workspace_root))
    _persist_plan_artifacts(workspace_root, plan)
    return plan


def _persist_plan_artifacts(workspace_root: Path, plan: ExperimentPlan) -> None:
    plans_root = workspace_root / shared_artifact_path(SharedArtifactCategory.DERIVED_PLANS)
    _ = atomic_write_model(plans_root / "experiment_plan.json", plan)
    _ = atomic_write_model(plans_root / "dependency_graph.json", dependency_graph(plan))


def smoke(workspace_root: Path | None = None) -> SmokeResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = TrajCertConfig.from_yaml_with_overrides(
        workspace_root / PRODUCTION_CONFIG_PATH, workspace_root / SMOKE_CONFIG_OVERRIDES_PATH
    )
    _ = active_config.set(config)
    return run_smoke_fixtures(config)


def run_experiment(
    experiment_name: str,
    *,
    workspace_root: Path | None = None,
    overwrite: bool = False,
    max_workers: int | None = None,
) -> RunExperimentResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    if _dirty_tree(workspace_root):
        raise InvalidScientificDataError("authoritative run requires a clean Git working tree")
    config = _load_config(workspace_root)
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
    status_cache: dict[ExperimentName, ExperimentStatus] = {}
    dependencies = _dependency_readiness(plan, workspace_root, cells[0], status_cache)
    progress = ExperimentProgress(name, len(cells))
    if name == _SYNTHESIS_NAME or max_workers == 1:
        completed, reused, failed, blocked = _run_cells_sequentially(
            cells, plan, workspace_root, dependencies, _executor(name, plan), overwrite, progress
        )
    else:
        completed, reused, failed, blocked = _run_cells_in_parallel(
            cells, plan, workspace_root, dependencies, overwrite, progress, max_workers
        )
    state = _run_state(len(cells), completed, failed, blocked)
    progress.experiment_finished(state, completed, reused, failed, blocked)
    if name == _SYNTHESIS_NAME and state is PublicExecutionState.COMPLETED:
        _render_synthesis_publication_artifacts(workspace_root)
    return RunExperimentResult(
        experiment_name=name,
        state=state,
        completed_cells=completed,
        reused_cells=reused,
        failed_cells=failed,
        blocked_cells=blocked,
    )


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
    max_workers: int | None,
) -> tuple[Count, Count, Count, Count]:
    completed = reused = failed = blocked = 0
    available_workers = max_workers if max_workers is not None else (os.cpu_count() or 1)
    worker_count = min(len(cells), available_workers)
    spawn_context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=worker_count, mp_context=spawn_context) as pool:
        futures: dict[Future[CellRunOutcome], tuple[SemanticCellKey, float]] = {}
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


def experiment_status(
    experiment_name: str,
    *,
    workspace_root: Path | None = None,
) -> ExperimentStatus:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = _load_config(workspace_root)
    plan = build_plan(config)
    name = _known_experiment_name(experiment_name)
    return _experiment_status(name, plan, workspace_root, {})


def report(
    *,
    workspace_root: Path | None = None,
    experiment_name: str | None = None,
    overwrite: bool = False,
) -> ReportExportResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    validated_name = None if experiment_name is None else _known_experiment_name(experiment_name)
    return export_report(workspace_root, experiment_name=validated_name, overwrite=overwrite)


def _load_config(workspace_root: Path) -> TrajCertConfig:
    config = TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)
    _ = active_config.set(config)
    return config


def _known_experiment_name(value: str) -> ExperimentName:
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
            reason=ReasonCode("CURRENT_EXECUTION_CONTEXT_UNAVAILABLE"),
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
    if name == _SYNTHESIS_NAME:
        return make_statistical_synthesis_executor(plan, _locality_input(plan))

    def execute(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
        return execute_dispatched_cell(cell, context)

    return execute


def _execution_context(
    cell: PlannedCell,
    plan: ExperimentPlan,
    workspace_root: Path,
) -> ExecutionContext:
    specification = scientific_specification_digest()
    component_digest = producer_component_digest(workspace_root, cell.identity.experiment_name)
    dependency_specification = scientific_dependency_digest(
        specification,
        cell.identity.semantic_cell_key,
        component_digest,
    )
    environment_digest = _environment_digest(workspace_root)
    if cell.identity.experiment_name == _SYNTHESIS_NAME:
        upstream = tuple(item for item in plan.cells if item.identity != cell.identity)
        dependency = synthesis_dependency_fingerprint(upstream, workspace_root)
        required = synthesis_artifact_keys(cell)
    else:
        dependency = cell_dependency_fingerprint(
            workspace_root,
            plan,
            cell,
            dependency_specification,
            component_digest,
            environment_digest,
        )
        required = (scientific_result_artifact_key(cell),)
    return ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=specification,
        scientific_dependency_digest=dependency_specification,
        provenance_fingerprint=_provenance(plan, workspace_root, environment_digest),
        dependency_fingerprint=dependency,
        manifest_digest=model_digest(cell),
        required_artifact_keys=required,
        expected_seed_count=expected_seed_count(cell.identity.experiment_name),
    )


def _environment_digest(workspace_root: Path) -> EnvironmentDigest:
    lock = workspace_root / LOCK_PATH
    if not lock.is_file():
        raise InvalidScientificDataError("uv.lock is required for execution provenance")
    return EnvironmentDigest(file_digest(lock))


def _provenance(
    plan: ExperimentPlan,
    workspace_root: Path,
    environment_digest: EnvironmentDigest,
) -> ProvenanceFingerprint:
    material = ProvenanceMaterial(
        scientific_specification_digest=SpecificationDigest(model_digest(active_config.get())),
        code_commit=source_commit(workspace_root),
        dirty_tree_flag=False,
        environment_lock_digest=environment_digest,
        container_image_digest=None,
        dataset_preprocessing_digests=(),
        partition_digest=None,
        seed_manifest_digests=(),
        plan_digest=DigestHex(plan.plan_digest),
    )
    return provenance_fingerprint(material)


def _dirty_tree(workspace_root: Path) -> bool:
    try:
        result = subprocess.run(
            ("git", "status", "--porcelain=v1", "--untracked-files=all"),
            cwd=workspace_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InvalidScientificDataError("cannot inspect source working tree") from exc
    return bool(result.stdout.strip())


def _locality_input(plan: ExperimentPlan) -> SynthesisLocalValidityInput:
    client_id = ClientId("synthetic-client")
    static_dependencies = _local_static_dependencies(client_id)
    bound_cells = tuple(
        cell
        for experiment_name in _LOCAL_BOUND_EXPERIMENTS
        for cell in cells_for_experiment(plan, experiment_name)
        if cell.executable
    )
    expected_roots = sum(
        len(cells_for_experiment(plan, experiment_name))
        for experiment_name in _LOCAL_BOUND_EXPERIMENTS
    )
    if len(bound_cells) != expected_roots:
        raise InvalidScientificDataError(
            "local-validity audit does not cover every declared coverage/utility bound root"
        )
    targets = tuple(_local_validity_target(cell, client_id) for cell in bound_cells)
    return SynthesisLocalValidityInput(
        static_dependencies=static_dependencies,
        targets=targets,
    )


def _local_static_dependencies(
    client_id: ClientId,
) -> tuple[StaticComponentDependency, ...]:
    contracts = (
        (
            "inference/categorical.py",
            (
                ScientificInputClass.TARGET_STREAM_EVENT_COUNT,
                ScientificInputClass.TARGET_EPOCH_MANIFEST,
                ScientificInputClass.TARGET_PARTITION_MANIFEST,
            ),
        ),
        (
            "inference/confidence.py",
            (
                ScientificInputClass.TARGET_STREAM_EVENT_COUNT,
                ScientificInputClass.CONFIG_VALUES,
                ScientificInputClass.LOCAL_NUMERICAL_DEPENDENCY,
            ),
        ),
        (
            "inference/envelope.py",
            (ScientificInputClass.LOCAL_NUMERICAL_DEPENDENCY,),
        ),
        (
            "inference/projection.py",
            (
                ScientificInputClass.CONFIG_VALUES,
                ScientificInputClass.LOCAL_NUMERICAL_DEPENDENCY,
            ),
        ),
        (
            "inference/certification.py",
            (
                ScientificInputClass.CONFIG_VALUES,
                ScientificInputClass.LOCAL_NUMERICAL_DEPENDENCY,
            ),
        ),
    )
    return tuple(
        StaticComponentDependency(
            producer_component=ProducerComponentName(component),
            scientific_input_classes=input_classes,
            scientific_client_ids=(client_id,),
        )
        for component, input_classes in contracts
    )


def _local_validity_target(
    cell: PlannedCell,
    client_id: ClientId,
) -> LocalValidityTarget:
    law_name = cell.identity.coordinates.synthetic_law_name
    if law_name is None:
        raise InvalidScientificDataError(
            f"local bound cell lacks a synthetic law identity: {cell.identity.semantic_cell_key}"
        )
    identity = LedgerIdentity(
        client_id=client_id,
        action_channel_id=ActionChannelId("automatic-action"),
        epoch_id=EpochId(f"{semantic_slug(law_name)}::static-epoch"),
    )
    root_key = scientific_result_artifact_key(cell)
    root = RuntimeLineageArtifact(
        artifact_key=root_key,
        client_id=identity.client_id,
        action_channel_id=identity.action_channel_id,
        epoch_id=identity.epoch_id,
    )
    return LocalValidityTarget(
        target_identity=identity,
        root_artifact_key=root_key,
        lineage_artifacts=(root,),
    )


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
