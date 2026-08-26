from __future__ import annotations

import sys
from pathlib import Path

import pytest

from trajcert import cli
from trajcert.cli import DoctorResult
from trajcert.exceptions import InvalidScientificDataError
from trajcert.reporting.export import ReportExportResult
from trajcert.types import CliCommand


def test_cli_exposes_exact_public_command_set() -> None:
    parser = cli._parser()
    action = next(item for item in parser._actions if getattr(item, "choices", None))
    assert set(action.choices) == {command.value for command in CliCommand}


def test_run_accepts_only_experiment_family_and_overwrite() -> None:
    arguments = cli._parser().parse_args(["run", "Population Sensitivity Utility", "--overwrite"])
    assert arguments.command == "run"
    assert arguments.experiment_name == "Population Sensitivity Utility"
    assert arguments.overwrite is True


@pytest.mark.parametrize(
    "forbidden",
    ("--seed", "--rho", "--beta", "--delta", "--partition", "--method", "--config"),
)
def test_run_rejects_public_scientific_knobs(forbidden: str) -> None:
    with pytest.raises(SystemExit) as raised:
        cli._parser().parse_args(["run", "Population Sensitivity Utility", forbidden, "1"])
    assert raised.value.code == cli.CliExitCode.USAGE_OR_UNKNOWN_NAME


def test_status_and_report_accept_optional_experiment_scope() -> None:
    parser = cli._parser()
    bare_status = parser.parse_args(["status"])
    scoped_status = parser.parse_args(["status", "Population Sensitivity Utility"])
    bare_report = parser.parse_args(["report"])
    scoped_report = parser.parse_args(["report", "Population Sensitivity Utility", "--overwrite"])
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
    monkeypatch.setattr(
        cli,
        "report",
        lambda *, experiment_name, overwrite: ReportExportResult(
            rendered_artifact_count=2,
            source_artifact_count=1,
            target=Path("results/experiments/population-sensitivity-utility"),
            reused=not overwrite and experiment_name is not None,
        ),
    )
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
            source_control_valid=True,
            workspace_writable=True,
            publication_contract_valid=True,
            results_layout_valid=True,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["trajcert", "doctor"])
    cli.main()
    assert capsys.readouterr().out == "TrajCert doctor: PASS\n"
