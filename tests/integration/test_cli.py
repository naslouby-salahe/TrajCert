from __future__ import annotations

import sys
from pathlib import Path

import pytest

from trajcert import cli
from trajcert.exceptions import InvalidScientificDataError
from trajcert.experiments.workflows import DoctorResult
from trajcert.reporting.export import ReportExportResult
from trajcert.types import CliCommand, ExperimentName, PublicExecutionState


def test_cli_exposes_exact_public_command_set() -> None:
    for command in CliCommand:
        argv = [command.value]
        if command is CliCommand.RUN:
            argv.append("Population Sensitivity Utility")
        assert cli.parse_args(argv).command is command
    with pytest.raises(SystemExit):
        _ = cli.parse_args(["unknown-command"])


def test_run_accepts_only_experiment_family_and_overwrite() -> None:
    arguments = cli.parse_args(["run", "Population Sensitivity Utility", "--overwrite"])
    assert arguments.command is CliCommand.RUN
    assert arguments.experiment_name == "Population Sensitivity Utility"
    assert arguments.overwrite is True


@pytest.mark.parametrize(
    "forbidden",
    ("--seed", "--rho", "--beta", "--delta", "--partition", "--method", "--config"),
)
def test_run_rejects_public_scientific_knobs(forbidden: str) -> None:
    with pytest.raises(SystemExit) as raised:
        _ = cli.parse_args(["run", "Population Sensitivity Utility", forbidden, "1"])
    assert raised.value.code == cli.CliExitCode.USAGE_OR_UNKNOWN_NAME


def test_status_and_report_accept_optional_experiment_scope() -> None:
    bare_status = cli.parse_args(["status"])
    scoped_status = cli.parse_args(["status", "Population Sensitivity Utility"])
    bare_report = cli.parse_args(["report"])
    scoped_report = cli.parse_args(["report", "Population Sensitivity Utility", "--overwrite"])
    assert bare_status.experiment_name is None
    assert scoped_status.experiment_name == "Population Sensitivity Utility"
    assert bare_report.experiment_name is None
    assert scoped_report.experiment_name == "Population Sensitivity Utility"
    assert scoped_report.overwrite is True


def test_unknown_experiment_exits_with_usage_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["trajcert", "run", "Unknown Experiment"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == cli.CliExitCode.USAGE_OR_UNKNOWN_NAME


def test_cli_command_logs_successful_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[tuple[CliCommand, PublicExecutionState | None]] = []

    def started(command: CliCommand) -> None:
        logged.append((command, None))

    def finished(command: CliCommand, state: PublicExecutionState) -> None:
        logged.append((command, state))

    result = DoctorResult(
        configuration_valid=True,
        plan_valid=True,
        dependency_lock_valid=True,
        imports_valid=True,
        workspace_writable=True,
        dataset_valid=True,
        publication_contract_valid=True,
        results_layout_valid=True,
    )
    monkeypatch.setattr(cli, "log_cli_command_started", started)
    monkeypatch.setattr(cli, "log_cli_command_finished", finished)
    monkeypatch.setattr(cli, "doctor", lambda: result)
    monkeypatch.setattr(sys, "argv", ["trajcert", "doctor"])

    cli.main()

    assert logged == [
        (CliCommand.DOCTOR, None),
        (CliCommand.DOCTOR, PublicExecutionState.COMPLETED),
    ]


def test_cli_command_logs_failure_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[tuple[CliCommand, PublicExecutionState | None]] = []

    def started(command: CliCommand) -> None:
        logged.append((command, None))

    def finished(command: CliCommand, state: PublicExecutionState) -> None:
        logged.append((command, state))

    def fail_report(
        *, experiment_name: ExperimentName | None, overwrite: bool
    ) -> ReportExportResult:
        _ = experiment_name
        _ = overwrite
        raise InvalidScientificDataError("synthesis evidence is incomplete")

    monkeypatch.setattr(cli, "log_cli_command_started", started)
    monkeypatch.setattr(cli, "log_cli_command_finished", finished)
    monkeypatch.setattr(cli, "report", fail_report)
    monkeypatch.setattr(sys, "argv", ["trajcert", "report"])

    with pytest.raises(SystemExit) as raised:
        cli.main()

    assert raised.value.code == cli.CliExitCode.COMPLETION_OR_EVIDENCE_FAILURE
    assert logged == [
        (CliCommand.REPORT, None),
        (CliCommand.REPORT, PublicExecutionState.FAILED),
    ]


def test_cli_command_logs_unhandled_failure_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[tuple[CliCommand, PublicExecutionState | None]] = []

    def started(command: CliCommand) -> None:
        logged.append((command, None))

    def finished(command: CliCommand, state: PublicExecutionState) -> None:
        logged.append((command, state))

    def fail_doctor() -> DoctorResult:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(cli, "log_cli_command_started", started)
    monkeypatch.setattr(cli, "log_cli_command_finished", finished)
    monkeypatch.setattr(cli, "doctor", fail_doctor)
    monkeypatch.setattr(sys, "argv", ["trajcert", "doctor"])

    with pytest.raises(RuntimeError, match="unexpected failure"):
        cli.main()

    assert logged == [
        (CliCommand.DOCTOR, None),
        (CliCommand.DOCTOR, PublicExecutionState.FAILED),
    ]


def test_report_evidence_failure_exits_with_completion_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_report(*, experiment_name: str | None, overwrite: bool) -> ReportExportResult:
        _ = experiment_name
        _ = overwrite
        raise InvalidScientificDataError("synthesis evidence is incomplete")

    monkeypatch.setattr(cli, "report", fail_report)
    monkeypatch.setattr(sys, "argv", ["trajcert", "report"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == cli.CliExitCode.COMPLETION_OR_EVIDENCE_FAILURE


def test_report_prints_scoped_export_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def scoped_report(*, experiment_name: str | None, overwrite: bool) -> ReportExportResult:
        return ReportExportResult(
            rendered_artifact_count=2,
            source_artifact_count=1,
            target=Path("results/experiments/population-sensitivity-utility"),
            reused=not overwrite and experiment_name is not None,
        )

    monkeypatch.setattr(cli, "report", scoped_report)
    monkeypatch.setattr(
        sys,
        "argv",
        ["trajcert", "report", "Population Sensitivity Utility"],
    )
    cli.main()
    output = capsys.readouterr().out
    assert "reused 2 artifacts from 1 verified sources" in output


def test_doctor_prints_compact_pass(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli,
        "doctor",
        lambda: DoctorResult(
            configuration_valid=True,
            plan_valid=True,
            dependency_lock_valid=True,
            imports_valid=True,
            workspace_writable=True,
            dataset_valid=True,
            publication_contract_valid=True,
            results_layout_valid=True,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["trajcert", "doctor"])
    cli.main()
    output = capsys.readouterr().out
    assert cli.CliCheckState.PASS in output
    assert f"{cli.CliDoctorField.WORKSPACE}=" in output
    assert f"{cli.CliDoctorField.ENVIRONMENT}={cli.CliDoctorValue.VALID}" in output
    assert f"{cli.CliDoctorField.DATASET}={cli.CliDoctorValue.VALID}" in output
    assert f"{cli.CliDoctorField.EXPERIMENT}={cli.CliDoctorValue.VALID}" in output
    assert f"{cli.CliDoctorField.ARTIFACT_DAG}={cli.CliDoctorValue.VALID}" in output
    assert f"{cli.CliDoctorField.NEXT_ACTION}={cli.CliDoctorValue.PREPROCESS}" in output


def test_cli_doctor_validates_inputs_and_reports_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["trajcert", "doctor"])
    cli.main()
    output = capsys.readouterr().out
    assert cli.CliCheckState.PASS in output
    assert f"{cli.CliDoctorField.WORKSPACE}=" in output
    assert f"{cli.CliDoctorField.ENVIRONMENT}={cli.CliDoctorValue.VALID}" in output
    assert f"{cli.CliDoctorField.DATASET}={cli.CliDoctorValue.VALID}" in output
    assert f"{cli.CliDoctorField.EXPERIMENT}={cli.CliDoctorValue.VALID}" in output
    assert f"{cli.CliDoctorField.ARTIFACT_DAG}={cli.CliDoctorValue.VALID}" in output
    assert f"{cli.CliDoctorField.NEXT_ACTION}={cli.CliDoctorValue.PREPROCESS}" in output
