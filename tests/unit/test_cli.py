from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pyarrow as pa
import pytest
from pydantic import ValidationError

from tests.unit.conftest import write_artifact_executor
from trajcert import cli
from trajcert.cli import CliArguments, CliExitCode, DoctorResult, RunExperimentResult
from trajcert.config import TrajCertConfig
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.exceptions import (
    ConfigurationError,
    InvalidScientificDataError,
    SerializationError,
)
from trajcert.experiments import runner
from trajcert.experiments.plan import (
    DependencyGraphRecord,
    ExperimentPlan,
    PlannedCell,
    build_plan,
    cells_for_experiment,
    experiment_names,
)
from trajcert.experiments.runner import SmokeResult
from trajcert.experiments.status import ExperimentStatus
from trajcert.paths import PreprocessingLeaf, preprocessing_leaf
from trajcert.provenance import (
    SemanticCellIdentity,
    SemanticCoordinates,
    VariantName,
)
from trajcert.reporting.export import ReportExportResult
from trajcert.reporting.source_data import (
    VerifiedSourceData,
    figure_source_descriptors,
    table_source_descriptors,
)
from trajcert.schemas import PublicationSourceDescriptor, VerifiedSourceLineage
from trajcert.storage import (
    ArtifactKey,
    DependencyFingerprint,
    DigestHex,
    PlanDigest,
    ProvenanceFingerprint,
    SpecificationDigest,
    read_model,
)
from trajcert.types import (
    CliCommand,
    EvidenceClass,
    ExperimentName,
    PublicExecutionState,
    ReasonCode,
)

_FIXTURE_COUNT = 6
_SHA256_HEX_LENGTH = 64
_HAND_CASE_CELL_COUNT = 4
_REPO_SRC = Path(__file__).resolve().parents[2] / "src"
_RENDERED_ARTIFACT_COUNT = 3
_SOURCE_ARTIFACT_COUNT = 2
_HAND_CASE_OUTCOMES = (
    (PublicExecutionState.COMPLETED, False),
    (PublicExecutionState.COMPLETED, True),
    (PublicExecutionState.FAILED, False),
    (PublicExecutionState.BLOCKED, False),
)


def _configured_workspace(tmp_path: Path) -> Path:
    target = tmp_path / "configs" / "trajcert.yaml"
    target.parent.mkdir(parents=True)
    _ = shutil.copy2(PRODUCTION_CONFIG_PATH, target)
    return tmp_path


def _single_cell_plan() -> ExperimentPlan:
    cell = PlannedCell(
        experiment_order=1,
        cell_ordinal=1,
        identity=SemanticCellIdentity(
            experiment_name=ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,
            coordinates=SemanticCoordinates(variant_name=VariantName("q=0.1, Gamma=1.5")),
        ),
        evidence_class=EvidenceClass.VALIDATION,
        executable=True,
        invalid_reason=None,
        required_experiments=(),
    )
    return ExperimentPlan(
        cells=(cell,),
        planned_cell_count=1,
        executable_cells=1,
        invalid_cells=0,
        nonapplicable_experiments=(),
        plan_digest=PlanDigest("abc"),
    )


def _fake_run_experiment(experiment_name: str, *, overwrite: bool) -> RunExperimentResult:
    _ = overwrite
    return RunExperimentResult(
        experiment_name=ExperimentName(experiment_name),
        state=PublicExecutionState.COMPLETED,
        completed_cells=1,
        reused_cells=0,
        failed_cells=0,
        blocked_cells=0,
    )


def _fake_experiment_status(experiment_name: str) -> ExperimentStatus:
    return ExperimentStatus(
        experiment_name=ExperimentName(experiment_name),
        state=PublicExecutionState.COMPLETED,
        total_cells=1,
        completed_cells=1,
        invalid_cells=0,
        failed_cells=0,
        blocked_cells=0,
        running_cells=0,
        ready_cells=0,
    )


def _fake_smoke_fail() -> SmokeResult:
    return SmokeResult(
        compatible_population_pass=True,
        incompatible_population_pass=True,
        endpoint_special_case_pass=True,
        refinement_pass=True,
        deterministic_confidence_sequence_pass=True,
        singleton_projection_pass=False,
        passed_fixture_count=5,
    )


def _fake_preprocess_target(dataset_name: str | None = None, *, overwrite: bool = False) -> Path:
    del dataset_name, overwrite
    return preprocessing_leaf(PreprocessingLeaf.VALIDATION_INTEGRITY) / "scientific_inventory.json"


def _fake_doctor_fail() -> DoctorResult:
    return DoctorResult(
        configuration_valid=False,
        plan_valid=True,
        dependency_lock_valid=True,
        imports_valid=True,
        source_control_valid=True,
        workspace_writable=True,
        publication_contract_valid=True,
        results_layout_valid=True,
    )


def _fake_report_rendered(*, experiment_name: str | None, overwrite: bool) -> ReportExportResult:
    _ = experiment_name
    _ = overwrite
    return ReportExportResult(
        rendered_artifact_count=_RENDERED_ARTIFACT_COUNT,
        source_artifact_count=_SOURCE_ARTIFACT_COUNT,
        target=Path("results/experiments/population-sensitivity-utility"),
        reused=False,
    )


def _raise_configuration_error() -> ExperimentPlan:
    raise ConfigurationError("synthetic technical failure")


def _raise_invalid_scientific_data() -> ExperimentPlan:
    raise InvalidScientificDataError("synthetic evidence failure")


def _passing_doctor() -> DoctorResult:
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


def _reused_report(*, experiment_name: str | None, overwrite: bool) -> ReportExportResult:
    _ = (experiment_name, overwrite)
    return ReportExportResult(
        rendered_artifact_count=_RENDERED_ARTIFACT_COUNT,
        source_artifact_count=_SOURCE_ARTIFACT_COUNT,
        target=Path("results/experiments/population-sensitivity-utility"),
        reused=True,
    )


def _git_workspace(tmp_path: Path) -> Path:
    workspace = _configured_workspace(tmp_path)
    _ = (workspace / "uv.lock").write_text("locked\n", encoding="utf-8")
    _ = subprocess.run(("git", "init", "-q"), cwd=workspace, check=True)
    _ = subprocess.run(("git", "add", "-A"), cwd=workspace, check=True)
    _ = subprocess.run(
        (
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "init",
        ),
        cwd=workspace,
        check=True,
    )
    return workspace


def _tmp_context(cell: PlannedCell, workspace_root: Path) -> runner.ExecutionContext:
    return runner.ExecutionContext(
        workspace_root=workspace_root,
        plan_digest=PlanDigest("plan"),
        scientific_specification_digest=SpecificationDigest("specification"),
        scientific_dependency_digest=SpecificationDigest("dependency"),
        provenance_fingerprint=ProvenanceFingerprint("provenance"),
        dependency_fingerprint=DependencyFingerprint("dependency-fingerprint"),
        manifest_digest=DigestHex("0" * _SHA256_HEX_LENGTH),
        required_artifact_keys=(runner.scientific_result_artifact_key(cell),),
        expected_seed_count=0,
    )


def _hand_case_cells() -> tuple[PlannedCell, ...]:
    return tuple(
        PlannedCell(
            experiment_order=1,
            cell_ordinal=index,
            identity=SemanticCellIdentity(
                experiment_name=ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES,
                coordinates=SemanticCoordinates(variant_name=VariantName(f"hand-case-0{index}")),
            ),
            evidence_class=EvidenceClass.VALIDATION,
            executable=True,
            invalid_reason=None,
            required_experiments=(),
        )
        for index in range(1, _HAND_CASE_CELL_COUNT + 1)
    )


def _invalid_cell() -> PlannedCell:
    return PlannedCell(
        experiment_order=1,
        cell_ordinal=1,
        identity=SemanticCellIdentity(
            experiment_name=ExperimentName.LEGACY_PARTITION_INCOHERENCE_CHECK,
            coordinates=SemanticCoordinates(variant_name=VariantName("q=0.1, Gamma=1.5")),
        ),
        evidence_class=EvidenceClass.VALIDATION,
        executable=False,
        invalid_reason=ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION"),
        required_experiments=(),
    )


def _cell_outcome(state: PublicExecutionState, *, reused: bool) -> runner.CellRunOutcome:
    return runner.CellRunOutcome(
        state=state,
        reused=reused,
        completion_path=Path("completion"),
        failure_path=Path("failure"),
        reason=None,
    )


def _cycle_outcome(cell: PlannedCell) -> runner.CellRunOutcome:
    ordinal = int(cell.cell_ordinal)
    state, reused = _HAND_CASE_OUTCOMES[min(ordinal, len(_HAND_CASE_OUTCOMES)) - 1]
    return _cell_outcome(state, reused=reused)


def _fake_run_cell_cycling(
    cell: PlannedCell,
    context: runner.ExecutionContext,
    dependencies: tuple[runner.DependencyReadiness, ...],
    executor: runner.CellExecutor,
    overwrite: bool,
) -> runner.CellRunOutcome:
    _ = (context, dependencies, executor, overwrite)
    return _cycle_outcome(cell)


def _fake_git_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    _ = (args, kwargs)
    return subprocess.CompletedProcess(("git", "rev-parse", "HEAD"), 0, stdout="short")


def _no_cells(_plan: ExperimentPlan, _name: ExperimentName) -> tuple[PlannedCell, ...]:
    return ()


def _hand_cells(_plan: ExperimentPlan, _name: ExperimentName) -> tuple[PlannedCell, ...]:
    return _hand_case_cells()


def _single_invalid_cell(_plan: ExperimentPlan, _name: ExperimentName) -> tuple[PlannedCell, ...]:
    return (_invalid_cell(),)


def _single_hand_case_cell(plan: ExperimentPlan, _name: ExperimentName) -> tuple[PlannedCell, ...]:
    return (cells_for_experiment(plan, ExperimentName.ANYTIME_IMPLEMENTATION_HAND_CASES)[0],)


def _no_dependencies(
    _plan: ExperimentPlan,
    _root: Path,
    _cell: PlannedCell,
    _cache: dict[ExperimentName, ExperimentStatus],
) -> tuple[runner.DependencyReadiness, ...]:
    return ()


def _completed_upstream_dependencies(
    _plan: ExperimentPlan,
    _root: Path,
    cell: PlannedCell,
    _cache: dict[ExperimentName, ExperimentStatus],
) -> tuple[runner.DependencyReadiness, ...]:
    return tuple(
        runner.DependencyReadiness(experiment_name=name, state=PublicExecutionState.COMPLETED)
        for name in cell.required_experiments
    )


def _ready_upstream_dependencies(
    _plan: ExperimentPlan,
    _root: Path,
    cell: PlannedCell,
    _cache: dict[ExperimentName, ExperimentStatus],
) -> tuple[runner.DependencyReadiness, ...]:
    return tuple(
        runner.DependencyReadiness(experiment_name=name, state=PublicExecutionState.READY)
        for name in cell.required_experiments
    )


def _context_for(
    cell: PlannedCell,
    _plan: ExperimentPlan,
    root: Path,
) -> runner.ExecutionContext:
    return _tmp_context(cell, root)


def _raise_context(
    _cell: PlannedCell,
    _plan: ExperimentPlan,
    _root: Path,
) -> runner.ExecutionContext:
    raise InvalidScientificDataError("context unavailable")


def _synthesis_fingerprint(
    _upstream: tuple[PlannedCell, ...], _root: Path
) -> DependencyFingerprint:
    return DependencyFingerprint("synthesis-fingerprint")


def _completed_run_cell(
    _cell: PlannedCell,
    _context: runner.ExecutionContext,
    _dependencies: tuple[runner.DependencyReadiness, ...],
    _executor: runner.CellExecutor,
    _overwrite: bool,
) -> runner.CellRunOutcome:
    return _cell_outcome(PublicExecutionState.COMPLETED, reused=False)


def _noop_publication_render(_workspace_root: Path) -> None:
    pass


def _failed_run_cell(
    _cell: PlannedCell,
    _context: runner.ExecutionContext,
    _dependencies: tuple[runner.DependencyReadiness, ...],
    _executor: runner.CellExecutor,
    _overwrite: bool,
) -> runner.CellRunOutcome:
    return _cell_outcome(PublicExecutionState.FAILED, reused=False)


def _outcome_sequence_run_cell(
    states: tuple[PublicExecutionState, ...],
) -> Callable[
    [
        PlannedCell,
        runner.ExecutionContext,
        tuple[runner.DependencyReadiness, ...],
        runner.CellExecutor,
        bool,
    ],
    runner.CellRunOutcome,
]:
    def _run_cell(
        _cell: PlannedCell,
        _context: runner.ExecutionContext,
        _dependencies: tuple[runner.DependencyReadiness, ...],
        _executor: runner.CellExecutor,
        _overwrite: bool,
    ) -> runner.CellRunOutcome:
        return _cell_outcome(states[int(_cell.cell_ordinal) - 1], reused=False)

    return _run_cell


def _real_cell_count(experiment_name: str) -> int:
    config = TrajCertConfig.from_yaml(PRODUCTION_CONFIG_PATH)
    plan = build_plan(config)
    return len(cells_for_experiment(plan, ExperimentName(experiment_name)))


@pytest.mark.parametrize(
    ("member", "expected"),
    (
        (CliExitCode.SUCCESS_OR_SCIENTIFIC_NOOP, 0),
        (CliExitCode.USAGE_OR_UNKNOWN_NAME, 2),
        (CliExitCode.ENVIRONMENT_OR_PREREQUISITE_BLOCK, 10),
        (CliExitCode.TECHNICAL_EXECUTION_FAILURE, 20),
        (CliExitCode.COMPLETION_OR_EVIDENCE_FAILURE, 30),
    ),
)
def test_cli_exit_codes_are_stable_integers(member: CliExitCode, expected: int) -> None:
    assert member == expected


def _arguments_with_command(command: object) -> CliArguments:
    return CliArguments(
        command=cast(CliCommand, command),
        experiment_name=None,
        dataset_name=None,
        overwrite=False,
    )


def test_cli_arguments_rejects_unknown_command() -> None:
    with pytest.raises(ValidationError):
        _ = _arguments_with_command("bogus")


def test_cli_arguments_carries_parsed_values() -> None:
    arguments = CliArguments(
        command=CliCommand.RUN,
        experiment_name="Population Sensitivity Utility",
        dataset_name=None,
        overwrite=True,
    )
    assert arguments.command is CliCommand.RUN
    assert arguments.experiment_name == "Population Sensitivity Utility"
    assert arguments.overwrite is True


def test_build_parser_uses_trajcert_program_name() -> None:
    assert cli.build_parser().prog == "trajcert"


def test_parse_args_run_requires_experiment_name() -> None:
    with pytest.raises(SystemExit) as raised:
        _ = cli.parse_args(["run"])
    assert raised.value.code == CliExitCode.USAGE_OR_UNKNOWN_NAME


def test_doctor_result_passes_only_when_all_checks_pass() -> None:
    passing = DoctorResult(
        configuration_valid=True,
        plan_valid=True,
        dependency_lock_valid=True,
        imports_valid=True,
        source_control_valid=True,
        workspace_writable=True,
        publication_contract_valid=True,
        results_layout_valid=True,
    )
    assert passing.passed is True


def test_doctor_result_fails_when_any_check_fails() -> None:
    failing = DoctorResult(
        configuration_valid=True,
        plan_valid=True,
        dependency_lock_valid=False,
        imports_valid=True,
        source_control_valid=True,
        workspace_writable=True,
        publication_contract_valid=True,
        results_layout_valid=True,
    )
    assert failing.passed is False


def test_doctor_rejects_workspace_without_configuration(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        _ = cli.doctor(workspace_root=tmp_path)


def test_doctor_rejects_missing_dependency_lock(tmp_path: Path) -> None:
    workspace = _configured_workspace(tmp_path)
    with pytest.raises(InvalidScientificDataError, match=r"uv\.lock is missing or empty"):
        _ = cli.doctor(workspace_root=workspace)


def test_preprocess_writes_configuration_artifact(tmp_path: Path) -> None:
    workspace = _configured_workspace(tmp_path)
    target = cli.preprocess(workspace_root=workspace)
    expected = (
        workspace
        / preprocessing_leaf(PreprocessingLeaf.VALIDATION_INTEGRITY)
        / "scientific_inventory.json"
    )
    assert target == expected
    assert target.is_file()
    stored = TrajCertConfig.model_validate_json(target.read_text(encoding="utf-8"))
    assert stored == TrajCertConfig.from_yaml(workspace / PRODUCTION_CONFIG_PATH)


def test_preprocess_reuses_existing_artifact_without_overwrite(tmp_path: Path) -> None:
    workspace = _configured_workspace(tmp_path)
    first = cli.preprocess(workspace_root=workspace)
    written_at = first.stat().st_mtime_ns
    second = cli.preprocess(workspace_root=workspace)
    assert second == first
    assert second.stat().st_mtime_ns == written_at


def test_preprocess_overwrite_forces_recompute(tmp_path: Path) -> None:
    workspace = _configured_workspace(tmp_path)
    first = cli.preprocess(workspace_root=workspace)
    _ = first.write_bytes(b"stale")
    second = cli.preprocess(workspace_root=workspace, overwrite=True)
    assert second == first
    stored = TrajCertConfig.model_validate_json(second.read_text(encoding="utf-8"))
    assert stored == TrajCertConfig.from_yaml(workspace / PRODUCTION_CONFIG_PATH)


def test_plan_view_matches_cell_count() -> None:
    plan = cli.plan_view()
    assert plan.planned_cell_count == len(plan.cells)
    assert plan.executable_cells + plan.invalid_cells == plan.planned_cell_count


def test_plan_view_persists_shared_plan_artifacts(tmp_path: Path) -> None:
    workspace = _configured_workspace(tmp_path)
    plan = cli.plan_view(workspace_root=workspace)
    plans_root = workspace / "outputs" / "artifacts" / "derived" / "plans"
    stored_plan = read_model(plans_root / "experiment_plan.json", ExperimentPlan)
    assert stored_plan == plan
    stored_graph = read_model(plans_root / "dependency_graph.json", DependencyGraphRecord)
    assert len(stored_graph.edges) == len(experiment_names())
    synthesis_edge = next(
        edge
        for edge in stored_graph.edges
        if edge.experiment_name == ExperimentName.STATISTICAL_SYNTHESIS
    )
    assert len(synthesis_edge.required_experiments) > 0


def test_smoke_passes_all_fixtures() -> None:
    result = cli.smoke()
    assert result.passed is True
    assert result.passed_fixture_count == _FIXTURE_COUNT


def test_experiment_status_rejects_unknown_family() -> None:
    with pytest.raises(InvalidScientificDataError, match="unknown experiment family"):
        _ = cli.experiment_status("Unknown Experiment")


def test_experiment_status_zero_declared_cells_is_invalid() -> None:
    status = cli.experiment_status("Real-Trajectory Validation")
    assert status.state is PublicExecutionState.INVALID
    assert status.total_cells == 0


def test_report_rejects_unknown_experiment_name() -> None:
    with pytest.raises(InvalidScientificDataError, match="unknown experiment family"):
        _ = cli.report(experiment_name="Unknown Experiment")


def test_main_run_prints_execution_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "run_experiment", _fake_run_experiment)
    monkeypatch.setattr(sys, "argv", ["trajcert", "run", "Legacy Partition Incoherence Check"])
    cli.main()
    result = _fake_run_experiment("Legacy Partition Incoherence Check", overwrite=False)
    expected = (
        f"{result.experiment_name}: {result.state.value} "
        f"({result.completed_cells} completed, {result.reused_cells} reused, "
        f"{result.failed_cells} failed, {result.blocked_cells} blocked)\n"
    )
    assert capsys.readouterr().out == expected


def test_main_status_prints_scoped_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "experiment_status", _fake_experiment_status)
    monkeypatch.setattr(sys, "argv", ["trajcert", "status", "Real-Trajectory Validation"])
    cli.main()
    status = _fake_experiment_status("Real-Trajectory Validation")
    expected = (
        f"{status.experiment_name}: {status.state.value} "
        f"({status.completed_cells}/{status.total_cells} completed, "
        f"{status.invalid_cells} invalid, {status.failed_cells} failed, "
        f"{status.blocked_cells} blocked, {status.running_cells} running)\n"
    )
    assert capsys.readouterr().out == expected


def test_main_status_prints_project_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "experiment_status", _fake_experiment_status)
    monkeypatch.setattr(sys, "argv", ["trajcert", "status"])
    cli.main()
    registry_count = len(experiment_names())
    expected = (
        f"TrajCert status: {registry_count}/{registry_count} experiments completed, "
        "0 failed, 0 blocked, 0 running\n"
    )
    assert capsys.readouterr().out == expected


def test_main_smoke_prints_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "smoke", _fake_smoke_fail)
    monkeypatch.setattr(sys, "argv", ["trajcert", "smoke"])
    cli.main()
    result = _fake_smoke_fail()
    state = "PASS" if result.passed else "FAIL"
    expected = (
        f"TrajCert smoke: {state} "
        f"({result.passed_fixture_count}/{_FIXTURE_COUNT} fixtures passed)\n"
    )
    assert capsys.readouterr().out == expected


def test_main_preprocess_prints_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "preprocess", _fake_preprocess_target)
    monkeypatch.setattr(sys, "argv", ["trajcert", "preprocess"])
    cli.main()
    assert capsys.readouterr().out == f"{_fake_preprocess_target()}\n"


def test_main_plan_prints_cell_counts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "plan_view", _single_cell_plan)
    monkeypatch.setattr(sys, "argv", ["trajcert", "plan"])
    cli.main()
    plan = _single_cell_plan()
    expected = (
        f"TrajCert plan: {plan.planned_cell_count} cells "
        f"({plan.executable_cells} executable, {plan.invalid_cells} invalid)\n"
    )
    assert capsys.readouterr().out == expected


def test_main_doctor_prints_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "doctor", _fake_doctor_fail)
    monkeypatch.setattr(sys, "argv", ["trajcert", "doctor"])
    cli.main()
    assert capsys.readouterr().out == "TrajCert doctor: FAIL\n"


def test_main_report_prints_rendered_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "report", _fake_report_rendered)
    monkeypatch.setattr(sys, "argv", ["trajcert", "report"])
    cli.main()
    exported = _fake_report_rendered(experiment_name=None, overwrite=False)
    expected = (
        f"TrajCert report: rendered {exported.rendered_artifact_count} artifacts "
        f"from {exported.source_artifact_count} verified sources at {exported.target.as_posix()}\n"
    )
    assert capsys.readouterr().out == expected


def test_main_status_empty_name_exits_with_usage_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["trajcert", "status", ""])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == CliExitCode.USAGE_OR_UNKNOWN_NAME


def test_main_translates_trajcert_error_to_technical_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "plan_view", _raise_configuration_error)
    monkeypatch.setattr(sys, "argv", ["trajcert", "plan"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == CliExitCode.TECHNICAL_EXECUTION_FAILURE
    assert "TrajCert: synthetic technical failure" in capsys.readouterr().err


def test_main_translates_invalid_scientific_data_to_prerequisite_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "plan_view", _raise_invalid_scientific_data)
    monkeypatch.setattr(sys, "argv", ["trajcert", "plan"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == CliExitCode.ENVIRONMENT_OR_PREREQUISITE_BLOCK
    assert "TrajCert: synthetic evidence failure" in capsys.readouterr().err


def test_main_doctor_prints_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "doctor", _passing_doctor)
    monkeypatch.setattr(sys, "argv", ["trajcert", "doctor"])
    cli.main()
    assert capsys.readouterr().out == "TrajCert doctor: PASS\n"


def test_main_report_prints_reused_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "report", _reused_report)
    monkeypatch.setattr(sys, "argv", ["trajcert", "report"])
    cli.main()
    expected = (
        "TrajCert report: reused 3 artifacts from 2 verified sources "
        "at results/experiments/population-sensitivity-utility\n"
    )
    assert capsys.readouterr().out == expected


def test_doctor_passes_complete_git_workspace(tmp_path: Path) -> None:
    workspace = _git_workspace(tmp_path)
    result = cli.doctor(workspace_root=workspace)
    assert result.passed is True


def test_experiment_name_rejects_unknown_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["trajcert", "status", "Not a Registry Experiment"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == CliExitCode.USAGE_OR_UNKNOWN_NAME


def test_run_experiment_reports_invalid_when_no_cells(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _configured_workspace(tmp_path)
    monkeypatch.setattr(cli, "cells_for_experiment", _no_cells)
    result = cli.run_experiment("Anytime Implementation Hand Cases", workspace_root=workspace)
    assert result.state is PublicExecutionState.INVALID
    assert result.completed_cells == 0


def test_run_experiment_aggregates_cell_outcomes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _configured_workspace(tmp_path)
    monkeypatch.setattr(cli, "cells_for_experiment", _hand_cells)
    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "_execution_context", _context_for)
    monkeypatch.setattr(cli, "run_cell", _fake_run_cell_cycling)
    result = cli.run_experiment(
        "Anytime Implementation Hand Cases", workspace_root=workspace, max_workers=1
    )
    outcome_states = tuple(state for state, _reused in _HAND_CASE_OUTCOMES)
    assert result.state is PublicExecutionState.FAILED
    assert result.completed_cells == outcome_states.count(PublicExecutionState.COMPLETED)
    assert result.reused_cells == sum(1 for _state, reused in _HAND_CASE_OUTCOMES if reused)
    assert result.failed_cells == outcome_states.count(PublicExecutionState.FAILED)
    assert result.blocked_cells == outcome_states.count(PublicExecutionState.BLOCKED)


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    (
        (
            (PublicExecutionState.COMPLETED,) * _HAND_CASE_CELL_COUNT,
            PublicExecutionState.COMPLETED,
        ),
        (
            (PublicExecutionState.COMPLETED,) * (_HAND_CASE_CELL_COUNT - 1)
            + (PublicExecutionState.BLOCKED,),
            PublicExecutionState.BLOCKED,
        ),
        (
            (PublicExecutionState.COMPLETED,) * (_HAND_CASE_CELL_COUNT - 1)
            + (PublicExecutionState.FAILED,),
            PublicExecutionState.FAILED,
        ),
        (
            (PublicExecutionState.COMPLETED,) * (_HAND_CASE_CELL_COUNT - 1)
            + (PublicExecutionState.READY,),
            PublicExecutionState.READY,
        ),
    ),
)
def test_run_experiment_maps_aggregated_run_states(
    outcomes: tuple[PublicExecutionState, ...],
    expected: PublicExecutionState,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = _configured_workspace(tmp_path)
    monkeypatch.setattr(cli, "cells_for_experiment", _hand_cells)
    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "_execution_context", _context_for)
    monkeypatch.setattr(cli, "run_cell", _outcome_sequence_run_cell(outcomes))
    result = cli.run_experiment(
        "Anytime Implementation Hand Cases", workspace_root=workspace, max_workers=1
    )
    assert result.state is expected


def test_run_experiment_resolves_real_execution_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "run_cell", _completed_run_cell)
    result = cli.run_experiment(
        "Anytime Implementation Hand Cases", workspace_root=Path(), max_workers=1
    )
    assert result.state is PublicExecutionState.COMPLETED
    assert result.completed_cells == _real_cell_count("Anytime Implementation Hand Cases")


def test_run_experiment_synthesis_resolves_real_locality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "synthesis_dependency_fingerprint", _synthesis_fingerprint)
    monkeypatch.setattr(cli, "run_cell", _completed_run_cell)
    monkeypatch.setattr(cli, "_render_synthesis_publication_artifacts", _noop_publication_render)
    result = cli.run_experiment("Statistical Synthesis", workspace_root=Path())
    assert result.state is PublicExecutionState.COMPLETED
    assert result.completed_cells == _real_cell_count("Statistical Synthesis")


def test_run_experiment_synthesis_completion_triggers_publication_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def _record_render(workspace_root: Path) -> None:
        calls.append(workspace_root)

    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "synthesis_dependency_fingerprint", _synthesis_fingerprint)
    monkeypatch.setattr(cli, "run_cell", _completed_run_cell)
    monkeypatch.setattr(cli, "_render_synthesis_publication_artifacts", _record_render)
    result = cli.run_experiment("Statistical Synthesis", workspace_root=Path())
    assert result.state is PublicExecutionState.COMPLETED
    assert calls == [Path()]


def test_run_experiment_synthesis_failure_skips_publication_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def _record_render(workspace_root: Path) -> None:
        calls.append(workspace_root)

    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "synthesis_dependency_fingerprint", _synthesis_fingerprint)
    monkeypatch.setattr(cli, "run_cell", _failed_run_cell)
    monkeypatch.setattr(cli, "_render_synthesis_publication_artifacts", _record_render)
    result = cli.run_experiment("Statistical Synthesis", workspace_root=Path())
    assert result.state is PublicExecutionState.FAILED
    assert calls == []


def test_run_experiment_non_synthesis_completion_skips_publication_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def _record_render(workspace_root: Path) -> None:
        calls.append(workspace_root)

    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "_execution_context", _context_for)
    monkeypatch.setattr(cli, "run_cell", _completed_run_cell)
    monkeypatch.setattr(cli, "_render_synthesis_publication_artifacts", _record_render)
    result = cli.run_experiment(
        "Anytime Implementation Hand Cases", workspace_root=Path(), max_workers=1
    )
    assert result.state is PublicExecutionState.COMPLETED
    assert calls == []


def test_render_synthesis_publication_artifacts_writes_under_owner_experiment_leaves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _configured_workspace(tmp_path)
    recorded_table_destinations: list[Path] = []
    recorded_figure_destinations: list[Path] = []

    def _fake_read_verified(
        _root: Path, descriptor: PublicationSourceDescriptor
    ) -> VerifiedSourceData:
        return VerifiedSourceData(
            descriptor=descriptor,
            table=pa.Table.from_pydict({"quantity": [1], "value": [0.5]}),
            lineage=VerifiedSourceLineage(
                source_path=descriptor.source_path,
                source_sha256=DigestHex("0" * _SHA256_HEX_LENGTH),
                artifact_key=ArtifactKey("artifact"),
                completion_sha256=DigestHex("0" * _SHA256_HEX_LENGTH),
                scientific_specification_digest=SpecificationDigest("specification"),
                dependency_fingerprint=DependencyFingerprint("dependency"),
                provenance_fingerprint=ProvenanceFingerprint("provenance"),
            ),
        )

    def _fake_render_table(source: VerifiedSourceData, destination_directory: Path) -> None:
        recorded_table_destinations.append(destination_directory)
        destination_directory.mkdir(parents=True, exist_ok=True)
        _ = (destination_directory / f"{source.descriptor.source_path.stem}.csv").write_text(
            "x", encoding="utf-8"
        )

    def _fake_render_figure(source: VerifiedSourceData, destination_directory: Path) -> None:
        recorded_figure_destinations.append(destination_directory)
        destination_directory.mkdir(parents=True, exist_ok=True)
        _ = (destination_directory / f"{source.descriptor.source_path.stem}.svg").write_text(
            "x", encoding="utf-8"
        )

    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "_execution_context", _context_for)
    monkeypatch.setattr(cli, "synthesis_dependency_fingerprint", _synthesis_fingerprint)
    monkeypatch.setattr(cli, "run_cell", _completed_run_cell)
    monkeypatch.setattr(cli, "read_verified_source_data", _fake_read_verified)
    monkeypatch.setattr(cli, "render_table", _fake_render_table)
    monkeypatch.setattr(cli, "render_figure", _fake_render_figure)

    result = cli.run_experiment("Statistical Synthesis", workspace_root=workspace)
    assert result.state is PublicExecutionState.COMPLETED

    tables = table_source_descriptors()
    figures = figure_source_descriptors()
    assert len(recorded_table_destinations) == len(tables)
    assert len(recorded_figure_destinations) == len(figures)
    for descriptor, destination in zip(tables, recorded_table_destinations, strict=True):
        expected = workspace / "outputs" / "experiments" / descriptor.owner_experiment
        assert destination == expected / "tables" / "main"
        assert (destination / f"{descriptor.source_path.stem}.csv").is_file()
    for descriptor, destination in zip(figures, recorded_figure_destinations, strict=True):
        expected = workspace / "outputs" / "experiments" / descriptor.owner_experiment
        assert destination == expected / "figures" / "main"
        assert (destination / f"{descriptor.source_path.stem}.svg").is_file()


def test_run_experiment_requires_clean_working_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _git_workspace(tmp_path)
    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "_execution_context", _context_for)
    monkeypatch.setattr(cli, "run_cell", _completed_run_cell)
    result = cli.run_experiment(
        "Anytime Implementation Hand Cases", workspace_root=workspace, max_workers=1
    )
    assert result.state is PublicExecutionState.COMPLETED
    assert result.completed_cells == _real_cell_count("Anytime Implementation Hand Cases")


def test_experiment_status_resolves_real_workspace() -> None:
    status = cli.experiment_status("Legacy Partition Incoherence Check", workspace_root=Path())
    assert status.total_cells == _real_cell_count("Legacy Partition Incoherence Check")


def test_experiment_status_reports_invalid_cell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _configured_workspace(tmp_path)
    monkeypatch.setattr(cli, "cells_for_experiment", _single_invalid_cell)
    status = cli.experiment_status("Legacy Partition Incoherence Check", workspace_root=workspace)
    assert status.state is PublicExecutionState.INVALID


def test_experiment_status_reports_blocked_upstream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _configured_workspace(tmp_path)
    monkeypatch.setattr(cli, "_dependency_readiness", _ready_upstream_dependencies)
    status = cli.experiment_status(
        "Production Solver vs Independent Oracle", workspace_root=workspace
    )
    assert status.state is PublicExecutionState.BLOCKED


def test_experiment_status_reports_ready_cell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _configured_workspace(tmp_path)
    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "_execution_context", _context_for)
    status = cli.experiment_status("Legacy Partition Incoherence Check", workspace_root=workspace)
    assert status.state is PublicExecutionState.READY


def test_experiment_status_blocks_when_context_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _configured_workspace(tmp_path)
    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "_execution_context", _raise_context)
    status = cli.experiment_status("Legacy Partition Incoherence Check", workspace_root=workspace)
    assert status.state is PublicExecutionState.BLOCKED


def test_executor_dispatches_ordinary_cell_through_run_cell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _dispatched_cell(
        cell: PlannedCell,
        context: runner.ExecutionContext,
    ) -> runner.CellExecutionResult:
        return write_artifact_executor(cell, context)

    workspace = _configured_workspace(tmp_path)
    monkeypatch.setattr(cli, "cells_for_experiment", _single_hand_case_cell)
    monkeypatch.setattr(cli, "_dependency_readiness", _completed_upstream_dependencies)
    monkeypatch.setattr(cli, "_execution_context", _context_for)
    monkeypatch.setattr(cli, "execute_dispatched_cell", _dispatched_cell)
    result = cli.run_experiment(
        "Anytime Implementation Hand Cases", workspace_root=workspace, max_workers=1
    )
    assert result.state is PublicExecutionState.COMPLETED
    assert result.completed_cells == 1


def test_report_requires_completed_synthesis(tmp_path: Path) -> None:
    workspace = _configured_workspace(tmp_path)
    with pytest.raises(SerializationError, match="cannot read artifact"):
        _ = cli.report(workspace_root=workspace)


def test_main_report_failure_maps_to_completion_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise_report(
        *,
        workspace_root: Path | None = None,
        experiment_name: str | None = None,
        overwrite: bool = False,
    ) -> ReportExportResult:
        _ = (workspace_root, experiment_name, overwrite)
        raise InvalidScientificDataError("synthesis evidence incomplete")

    monkeypatch.setattr(cli, "report", _raise_report)
    monkeypatch.setattr(sys, "argv", ["trajcert", "report"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == CliExitCode.COMPLETION_OR_EVIDENCE_FAILURE
    assert "synthesis evidence incomplete" in capsys.readouterr().err


def test_doctor_rejects_non_git_workspace(tmp_path: Path) -> None:
    workspace = _configured_workspace(tmp_path)
    _ = (workspace / "uv.lock").write_text("locked\n", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="cannot resolve source commit"):
        _ = cli.doctor(workspace_root=workspace)


def test_doctor_rejects_short_source_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_git_run)
    with pytest.raises(InvalidScientificDataError, match="full Git SHA-1"):
        _ = cli.doctor(workspace_root=Path())


def test_doctor_rejects_file_outputs_path(tmp_path: Path) -> None:
    workspace = _git_workspace(tmp_path)
    _ = (workspace / "outputs").write_text("x", encoding="utf-8")
    with pytest.raises(InvalidScientificDataError, match="workspace path is not writable"):
        _ = cli.doctor(workspace_root=workspace)


def _truncated_table_sources() -> tuple[PublicationSourceDescriptor, ...]:
    return table_source_descriptors()[:1]


def test_doctor_rejects_incomplete_publication_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _git_workspace(tmp_path)
    monkeypatch.setattr(cli, "table_source_descriptors", _truncated_table_sources)
    with pytest.raises(InvalidScientificDataError, match="publication source contract"):
        _ = cli.doctor(workspace_root=workspace)


def test_run_experiment_rejects_missing_uv_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _configured_workspace(tmp_path)
    try:
        _ = (workspace / "src").symlink_to(_REPO_SRC, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable in this environment: {exc}")
    monkeypatch.setattr(cli, "_dependency_readiness", _no_dependencies)
    monkeypatch.setattr(cli, "run_cell", _completed_run_cell)
    with pytest.raises(InvalidScientificDataError, match=r"uv\.lock is required"):
        _ = cli.run_experiment("Anytime Implementation Hand Cases", workspace_root=workspace)
