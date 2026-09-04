from __future__ import annotations

import importlib
import multiprocessing
import os
import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import cast

from trajcert.config import TrajCertConfig, active_config
from trajcert.constants import PRODUCTION_CONFIG_PATH, SMOKE_CONFIG_OVERRIDES_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES, build_full_law, configured_laws
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
    SmokeResult,
    cell_dependency_material,
    dependency_block_reason,
    execute_dispatched_cell,
    expected_seed_count,
    run_cell,
    run_smoke_fixtures,
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
    experiment_leaf,
    plan_artifact_path,
    preprocessing_leaf,
)
from trajcert.provenance import (
    EnvironmentDigest,
    dependency_fingerprint,
)
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
from trajcert.storage import (
    SemanticCellKey,
    atomic_write_model,
    file_digest,
)
from trajcert.telemetry import ExperimentProgress, configure_logging
from trajcert.types import (
    CliArgumentValue,
    CliCommand,
    Count,
    DomainModel,
    ExperimentName,
    LawName,
    PublicExecutionState,
    ReasonCode,
)


class CliExitCode(IntEnum):
    SUCCESS_OR_SCIENTIFIC_NOOP = 0
    USAGE_OR_UNKNOWN_NAME = 2
    ENVIRONMENT_OR_PREREQUISITE_BLOCK = 10
    TECHNICAL_EXECUTION_FAILURE = 20
    COMPLETION_OR_EVIDENCE_FAILURE = 30


class CliArgumentName(StrEnum):
    COMMAND = "command"
    EXPERIMENT_NAME = "experiment_name"
    DATASET_NAME = "dataset_name"
    OVERWRITE = "overwrite"


class CliParserToken(StrEnum):
    PROGRAM_NAME = "trajcert"
    OPTIONAL_POSITIONAL = "?"
    OVERWRITE_OPTION = "--overwrite"
    STORE_TRUE = "store_true"


class CliRuntimeModule(StrEnum):
    NUMPY = "numpy"
    PYDANTIC = "pydantic"
    PYARROW = "pyarrow"
    SCIPY = "scipy"
    FLINT = "flint"
    MPMATH = "mpmath"
    YAML = "yaml"


class CliReportAction(StrEnum):
    REUSED = "reused"
    RENDERED = "rendered"


class CliCheckState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class CliProcessStartMethod(StrEnum):
    SPAWN = "spawn"


class CliArguments(DomainModel):
    command: CliCommand
    experiment_name: ExperimentName | None
    dataset_name: LawName | None
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
    command = CliCommand(getattr(arguments, CliArgumentName.COMMAND))
    raw_name = cast(
        CliArgumentValue | None,
        getattr(arguments, CliArgumentName.EXPERIMENT_NAME, None),
    )
    raw_dataset_name = cast(
        CliArgumentValue | None,
        getattr(arguments, CliArgumentName.DATASET_NAME, None),
    )
    return CliArguments(
        command=command,
        experiment_name=_parse_experiment_name(
            parser,
            raw_name,
            required=command is CliCommand.RUN,
        ),
        dataset_name=_parse_dataset_name(parser, raw_dataset_name),
        overwrite=cast(bool, getattr(arguments, CliArgumentName.OVERWRITE, False)),
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
        action = CliReportAction.REUSED if exported.reused else CliReportAction.RENDERED
        target = exported.target.as_posix()
        print(
            f"TrajCert report: {action} {exported.rendered_artifact_count} artifacts "
            + f"from {exported.source_artifact_count} verified sources at {target}"
        )


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog=CliParserToken.PROGRAM_NAME)
    subparsers = parser.add_subparsers(dest=CliArgumentName.COMMAND, required=True)
    for command in (CliCommand.DOCTOR, CliCommand.PLAN):
        _ = subparsers.add_parser(command)
    preprocess_parser = subparsers.add_parser(CliCommand.PREPROCESS)
    _ = preprocess_parser.add_argument(
        CliArgumentName.DATASET_NAME,
        nargs=CliParserToken.OPTIONAL_POSITIONAL,
    )
    _ = preprocess_parser.add_argument(
        CliParserToken.OVERWRITE_OPTION,
        action=CliParserToken.STORE_TRUE,
    )
    smoke_parser = subparsers.add_parser(CliCommand.SMOKE)
    _ = smoke_parser.add_argument(CliParserToken.OVERWRITE_OPTION, action=CliParserToken.STORE_TRUE)
    run_parser = subparsers.add_parser(CliCommand.RUN)
    _ = run_parser.add_argument(CliArgumentName.EXPERIMENT_NAME)
    _ = run_parser.add_argument(CliParserToken.OVERWRITE_OPTION, action=CliParserToken.STORE_TRUE)
    status_parser = subparsers.add_parser(CliCommand.STATUS)
    _ = status_parser.add_argument(
        CliArgumentName.EXPERIMENT_NAME,
        nargs=CliParserToken.OPTIONAL_POSITIONAL,
    )
    report_parser = subparsers.add_parser(CliCommand.REPORT)
    _ = report_parser.add_argument(
        CliArgumentName.EXPERIMENT_NAME,
        nargs=CliParserToken.OPTIONAL_POSITIONAL,
    )
    _ = report_parser.add_argument(
        CliParserToken.OVERWRITE_OPTION, action=CliParserToken.STORE_TRUE
    )
    return parser


def _experiment_name(arguments: CliArguments, *, required: bool) -> ExperimentName | None:
    value = arguments.experiment_name
    if value is None:
        if required:
            build_parser().error("experiment name is required")
        return None
    return value


def _dataset_name(arguments: CliArguments) -> LawName | None:
    return arguments.dataset_name


def _parse_experiment_name(
    parser: ArgumentParser,
    value: CliArgumentValue | None,
    *,
    required: bool,
) -> ExperimentName | None:
    if value is None:
        if required:
            parser.error("experiment name is required")
        return None
    if not value:
        parser.error("experiment name must be a non-empty descriptive name")
    try:
        return ExperimentName(value)
    except ValueError:
        parser.error(f"unknown experiment name: {value}")


def _parse_dataset_name(parser: ArgumentParser, value: CliArgumentValue | None) -> LawName | None:
    if value is None:
        return None
    if LawName(value) not in LAW_DISPLAY_NAMES.values():
        parser.error(f"unknown dataset name: {value}")
    return LawName(value)


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
    state = CliCheckState.PASS if result.passed else CliCheckState.FAIL
    print(f"TrajCert smoke: {state} ({result.passed_fixture_count}/6 fixtures passed)")


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
        workspace_writable=True,
        publication_contract_valid=True,
        results_layout_valid=True,
    )


def preprocess(
    dataset_name: LawName | None = None,
    *,
    workspace_root: Path | None = None,
    overwrite: bool = False,
) -> Path:
    workspace_root = workspace_root if workspace_root is not None else Path()
    target = workspace_root / _PREPROCESS_PATH
    if not overwrite and target.is_file():
        return target
    config = _load_config(workspace_root)
    finest = config.method.finest_bands
    selected = tuple(
        parameters
        for parameters in configured_laws()
        if dataset_name is None or parameters.name == dataset_name
    )
    for parameters in selected:
        _ = build_full_law(parameters, finest)
    _ = atomic_write_model(target, config)
    return target


def plan_view(workspace_root: Path | None = None) -> ExperimentPlan:
    workspace_root = workspace_root if workspace_root is not None else Path()
    plan = build_plan(_load_config(workspace_root))
    _persist_plan_artifacts(workspace_root, plan)
    return plan


def _persist_plan_artifacts(workspace_root: Path, plan: ExperimentPlan) -> None:
    _ = atomic_write_model(
        workspace_root / plan_artifact_path(PlanArtifactFile.EXPERIMENT_PLAN), plan
    )
    _ = atomic_write_model(
        workspace_root / plan_artifact_path(PlanArtifactFile.DEPENDENCY_GRAPH),
        dependency_graph(plan),
    )


def smoke(workspace_root: Path | None = None) -> SmokeResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = TrajCertConfig.from_yaml_with_overrides(
        workspace_root / PRODUCTION_CONFIG_PATH, workspace_root / SMOKE_CONFIG_OVERRIDES_PATH
    )
    _ = active_config.set(config)
    return run_smoke_fixtures(config)


def run_experiment(
    experiment_name: ExperimentName,
    *,
    workspace_root: Path | None = None,
    overwrite: bool = False,
    max_workers: int | None = None,
) -> RunExperimentResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
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
    if name is ExperimentName.STATISTICAL_SYNTHESIS or max_workers == 1:
        completed, reused, failed, blocked = _run_cells_sequentially(
            cells, plan, workspace_root, dependencies, _executor(name, plan), overwrite, progress
        )
    else:
        completed, reused, failed, blocked = _run_cells_in_parallel(
            cells, plan, workspace_root, dependencies, overwrite, progress, max_workers
        )
    state = _run_state(len(cells), completed, failed, blocked)
    progress.experiment_finished(state, completed, reused, failed, blocked)
    if name is ExperimentName.STATISTICAL_SYNTHESIS and state is PublicExecutionState.COMPLETED:
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
    spawn_context = multiprocessing.get_context(CliProcessStartMethod.SPAWN)
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
    experiment_name: ExperimentName,
    *,
    workspace_root: Path | None = None,
) -> ExperimentStatus:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = _load_config(workspace_root)
    plan = build_plan(config)
    return _experiment_status(_known_experiment_name(experiment_name), plan, workspace_root, {})


def report(
    *,
    workspace_root: Path | None = None,
    experiment_name: ExperimentName | None = None,
    overwrite: bool = False,
) -> ReportExportResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    validated_name = None if experiment_name is None else _known_experiment_name(experiment_name)
    return export_report(workspace_root, experiment_name=validated_name, overwrite=overwrite)


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
        raise InvalidScientificDataError("uv.lock is required for execution provenance")
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
