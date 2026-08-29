from __future__ import annotations

import importlib
import os
import subprocess
import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from enum import IntEnum
from pathlib import Path
from typing import cast

from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH, SMOKE_CONFIG_OVERRIDES_PATH
from trajcert.data.laws import LAW_DISPLAY_NAMES, LawParameters, build_full_law
from trajcert.data.ledger import LedgerIdentity
from trajcert.data.partitions import build_partition
from trajcert.exceptions import InvalidScientificDataError, TrajCertError
from trajcert.experiments.inventory import validate_scientific_inventory
from trajcert.experiments.plan import ExperimentPlan, PlannedCell, build_plan, cells_for_experiment
from trajcert.experiments.registry import authoritative_registry
from trajcert.experiments.runner import (
    CellExecutionResult,
    CellExecutor,
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
from trajcert.paths import RESULTS_ROOT, semantic_slug
from trajcert.provenance import (
    CodeCommit,
    EnvironmentDigest,
    ExperimentNameValue,
    ProducerComponentName,
    ProvenanceMaterial,
    provenance_fingerprint,
)
from trajcert.reporting.export import ReportExportResult, export_report, validate_results_layout
from trajcert.reporting.source_data import figure_source_descriptors, table_source_descriptors
from trajcert.storage import (
    DigestHex,
    ProvenanceFingerprint,
    SpecificationDigest,
    atomic_write_model,
    file_digest,
    model_digest,
)
from trajcert.types import (
    ActionChannelId,
    CliCommand,
    ClientId,
    DomainModel,
    EpochId,
    NonNegativeInt,
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
    overwrite: bool


def main() -> None:
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
    return CliArguments(
        command=command,
        experiment_name=None if raw_name is None else cast(str, raw_name),
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
        print(preprocess())
    elif command is CliCommand.PLAN:
        plan = plan_view()
        print(
            f"TrajCert plan: {plan.registry_total} cells "
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
    for command in (CliCommand.DOCTOR, CliCommand.PREPROCESS, CliCommand.PLAN, CliCommand.SMOKE):
        _ = subparsers.add_parser(command.value)
    run_parser = subparsers.add_parser(CliCommand.RUN.value)
    _ = run_parser.add_argument("experiment_name")
    _ = run_parser.add_argument("--overwrite", action="store_true")
    status_parser = subparsers.add_parser(CliCommand.STATUS.value)
    _ = status_parser.add_argument("experiment_name", nargs="?")
    report_parser = subparsers.add_parser(CliCommand.REPORT.value)
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
    known = {str(item.experiment_name) for item in authoritative_registry()}
    if value not in known:
        build_parser().error(f"unknown experiment name: {value}")
    return value


def _print_run(result: RunExperimentResult) -> None:
    print(
        f"{result.experiment_name}: {result.state.value} "
        + f"({result.completed_cells} completed, {result.reused_cells} reused, "
        + f"{result.failed_cells} failed, {result.blocked_cells} blocked)"
    )


def _print_status(status: ExperimentStatus) -> None:
    print(
        f"{status.experiment_name}: {status.state.value} "
        + f"({status.completed_cells}/{status.total_cells} completed, "
        + f"{status.invalid_cells} invalid, {status.failed_cells} failed, "
        + f"{status.blocked_cells} blocked, {status.running_cells} running)"
    )


def _print_project_status() -> None:
    statuses = tuple(
        experiment_status(str(item.experiment_name)) for item in authoritative_registry()
    )
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


_LOCK_PATH = Path("uv.lock")
_PREPROCESS_PATH = Path("outputs/preprocessing/validation/scientific_inventory.json")
_SYNTHESIS_NAME = ExperimentNameValue("Statistical Synthesis")
_REQUIRED_IMPORTS = ("numpy", "pydantic", "pyarrow", "scipy", "flint", "mpmath", "yaml")
_PUBLICATION_TABLE_COUNT = 12
_PUBLICATION_FIGURE_COUNT = 8
_PUBLICATION_SOURCE_COUNT = _PUBLICATION_TABLE_COUNT + _PUBLICATION_FIGURE_COUNT
_GIT_SHA1_LENGTH = 40
_LOCAL_BOUND_EXPERIMENTS = (
    ExperimentNameValue("Anytime Coverage Stress"),
    ExperimentNameValue("Sequential Sensitivity Utility"),
)


class RunExperimentResult(DomainModel):
    experiment_name: ExperimentNameValue
    state: PublicExecutionState
    completed_cells: NonNegativeInt
    reused_cells: NonNegativeInt
    failed_cells: NonNegativeInt
    blocked_cells: NonNegativeInt


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
    plan = build_plan(config)
    expected_cells = sum(item.declared_cells for item in authoritative_registry())
    if plan.registry_total != expected_cells:
        raise InvalidScientificDataError("expanded plan does not match the authoritative registry")
    finest = config.method.finest_bands
    for key, law in config.ordered_laws:
        parameters = LawParameters(
            key=key,
            name=LAW_DISPLAY_NAMES[key],
            theta=law.theta,
            q1=law.q1,
            q0=law.q0,
            lambda1=law.lambda1,
            lambda0=law.lambda0,
        )
        _ = build_full_law(parameters, finest)
    for bands in config.grids.partitions:
        _ = build_partition(finest, bands, config.method.terminal_horizon)
    lock_path = workspace_root / _LOCK_PATH
    if not lock_path.is_file() or lock_path.stat().st_size == 0:
        raise InvalidScientificDataError("uv.lock is missing or empty")
    for module_name in _REQUIRED_IMPORTS:
        _ = importlib.import_module(module_name)
    _ = _source_commit(workspace_root)
    _assert_workspace_writable(workspace_root)
    descriptors = (*table_source_descriptors(), *figure_source_descriptors())
    if (
        len(descriptors) != _PUBLICATION_SOURCE_COUNT
        or len({item.source_path for item in descriptors}) != _PUBLICATION_SOURCE_COUNT
    ):
        raise InvalidScientificDataError(
            "publication source contract must contain 12 tables and 8 figures"
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


def preprocess(workspace_root: Path | None = None) -> Path:
    workspace_root = workspace_root if workspace_root is not None else Path()
    result = validate_scientific_inventory(_load_config(workspace_root))
    if not result.valid:
        raise InvalidScientificDataError("scientific preprocessing/inventory validation failed")
    target = workspace_root / _PREPROCESS_PATH
    _ = atomic_write_model(target, result)
    return target


def plan_view(workspace_root: Path | None = None) -> ExperimentPlan:
    workspace_root = workspace_root if workspace_root is not None else Path()
    return build_plan(_load_config(workspace_root))


def smoke(workspace_root: Path | None = None) -> SmokeResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = TrajCertConfig.from_yaml_with_overrides(
        workspace_root / PRODUCTION_CONFIG_PATH, workspace_root / SMOKE_CONFIG_OVERRIDES_PATH
    )
    return run_smoke_fixtures(config)


def run_experiment(
    experiment_name: str,
    *,
    workspace_root: Path | None = None,
    overwrite: bool = False,
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
    status_cache: dict[ExperimentNameValue, ExperimentStatus] = {}
    dependencies = _dependency_readiness(plan, config, workspace_root, cells[0], status_cache)
    executor = _executor(name, plan, config)
    completed = reused = failed = blocked = 0
    for cell in cells:
        context = _execution_context(cell, plan, config, workspace_root)
        outcome = run_cell(cell, context, dependencies, executor, overwrite)
        if outcome.state is PublicExecutionState.COMPLETED:
            completed += 1
            reused += int(outcome.reused)
        elif outcome.state is PublicExecutionState.FAILED:
            failed += 1
        elif outcome.state is PublicExecutionState.BLOCKED:
            blocked += 1
    return RunExperimentResult(
        experiment_name=name,
        state=_run_state(len(cells), completed, failed, blocked),
        completed_cells=completed,
        reused_cells=reused,
        failed_cells=failed,
        blocked_cells=blocked,
    )


def experiment_status(
    experiment_name: str,
    *,
    workspace_root: Path | None = None,
) -> ExperimentStatus:
    workspace_root = workspace_root if workspace_root is not None else Path()
    config = _load_config(workspace_root)
    plan = build_plan(config)
    name = _known_experiment_name(experiment_name)
    return _experiment_status(name, plan, config, workspace_root, {})


def report(
    *,
    workspace_root: Path | None = None,
    experiment_name: str | None = None,
    overwrite: bool = False,
) -> ReportExportResult:
    workspace_root = workspace_root if workspace_root is not None else Path()
    if experiment_name is not None:
        _ = _known_experiment_name(experiment_name)
    return export_report(workspace_root, experiment_name=experiment_name, overwrite=overwrite)


def _load_config(workspace_root: Path) -> TrajCertConfig:
    return TrajCertConfig.from_yaml(workspace_root / PRODUCTION_CONFIG_PATH)


def _known_experiment_name(value: str) -> ExperimentNameValue:
    names = tuple(item.experiment_name for item in authoritative_registry())
    requested = ExperimentNameValue(value)
    if requested not in names:
        raise InvalidScientificDataError(f"unknown experiment family: {value}")
    return requested


def _experiment_status(
    name: ExperimentNameValue,
    plan: ExperimentPlan,
    config: TrajCertConfig,
    workspace_root: Path,
    cache: dict[ExperimentNameValue, ExperimentStatus],
) -> ExperimentStatus:
    cached = cache.get(name)
    if cached is not None:
        return cached
    cells = cells_for_experiment(plan, name)
    statuses = tuple(
        _current_cell_status(cell, plan, config, workspace_root, cache) for cell in cells
    )
    declared_cells = next(
        item.declared_cells for item in authoritative_registry() if item.experiment_name == name
    )
    result = aggregate_experiment_status(name, statuses, declared_cells)
    cache[name] = result
    return result


def _current_cell_status(
    cell: PlannedCell,
    plan: ExperimentPlan,
    config: TrajCertConfig,
    workspace_root: Path,
    cache: dict[ExperimentNameValue, ExperimentStatus],
) -> CellStatus:
    key = str(cell.identity.semantic_cell_key)
    if not cell.executable:
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.INVALID,
            reason=cell.invalid_reason,
        )
    dependencies = _dependency_readiness(plan, config, workspace_root, cell, cache)
    reason = dependency_block_reason(cell, dependencies)
    if reason is not None:
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.BLOCKED,
            reason=reason,
        )
    try:
        context = _execution_context(cell, plan, config, workspace_root)
    except InvalidScientificDataError:
        return CellStatus(
            semantic_cell_key=key,
            state=PublicExecutionState.BLOCKED,
            reason=ReasonCode("CURRENT_EXECUTION_CONTEXT_UNAVAILABLE"),
        )
    return inspect_cell_status(cell, context, dependencies)


def _dependency_readiness(
    plan: ExperimentPlan,
    config: TrajCertConfig,
    workspace_root: Path,
    cell: PlannedCell,
    cache: dict[ExperimentNameValue, ExperimentStatus],
) -> tuple[DependencyReadiness, ...]:
    return tuple(
        DependencyReadiness(
            experiment_name=name,
            state=_experiment_status(name, plan, config, workspace_root, cache).state,
        )
        for name in cell.required_experiments
    )


def _executor(
    name: ExperimentNameValue,
    plan: ExperimentPlan,
    config: TrajCertConfig,
) -> CellExecutor:
    if name == _SYNTHESIS_NAME:
        return make_statistical_synthesis_executor(plan, config, _locality_input(plan))

    def execute(cell: PlannedCell, context: ExecutionContext) -> CellExecutionResult:
        return execute_dispatched_cell(cell, context, config)

    return execute


def _execution_context(
    cell: PlannedCell,
    plan: ExperimentPlan,
    config: TrajCertConfig,
    workspace_root: Path,
) -> ExecutionContext:
    specification = scientific_specification_digest(config)
    component_digest = producer_component_digest(workspace_root, cell.identity.experiment_name)
    dependency_specification = scientific_dependency_digest(
        specification,
        str(cell.identity.semantic_cell_key),
        component_digest,
    )
    if cell.identity.experiment_name == _SYNTHESIS_NAME:
        upstream = tuple(item for item in plan.cells if item.identity != cell.identity)
        dependency = synthesis_dependency_fingerprint(upstream, workspace_root)
        required = synthesis_artifact_keys()
    else:
        dependency = cell_dependency_fingerprint(
            workspace_root,
            plan,
            cell,
            dependency_specification,
        )
        required = (scientific_result_artifact_key(cell),)
    return ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=plan.plan_digest,
        scientific_specification_digest=specification,
        scientific_dependency_digest=dependency_specification,
        provenance_fingerprint=_provenance(plan, config, workspace_root),
        dependency_fingerprint=dependency,
        manifest_digest=DigestHex(str(model_digest(cell))),
        required_artifact_keys=required,
        expected_seed_count=expected_seed_count(cell.identity.experiment_name, config),
    )


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
        dirty_tree_flag=False,
        environment_lock_digest=EnvironmentDigest(str(file_digest(lock))),
        container_image_digest=None,
        dataset_preprocessing_digests=(),
        partition_digest=None,
        seed_manifest_digests=(),
        plan_digest=DigestHex(str(plan.plan_digest)),
    )
    return provenance_fingerprint(material)


def _source_commit(workspace_root: Path) -> str:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=workspace_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InvalidScientificDataError("cannot resolve source commit") from exc
    commit = result.stdout.strip()
    if len(commit) != _GIT_SHA1_LENGTH:
        raise InvalidScientificDataError("source commit must be a full Git SHA-1")
    return commit


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
        definition.declared_cells
        for definition in authoritative_registry()
        if definition.experiment_name in _LOCAL_BOUND_EXPERIMENTS
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
        epoch_id=EpochId(f"{semantic_slug(str(law_name))}::static-epoch"),
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
    for relative in (Path("outputs"), RESULTS_ROOT):
        directory = workspace_root / relative
        if directory.exists() and (not directory.is_dir() or not os.access(directory, os.W_OK)):
            raise InvalidScientificDataError(f"workspace path is not writable: {directory}")


def _run_state(total: int, completed: int, failed: int, blocked: int) -> PublicExecutionState:
    if failed:
        return PublicExecutionState.FAILED
    if blocked:
        return PublicExecutionState.BLOCKED
    if completed == total:
        return PublicExecutionState.COMPLETED
    return PublicExecutionState.READY
