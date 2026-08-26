from __future__ import annotations

import sys

import pytest

from trajcert import cli
from trajcert.operator import DoctorResult
from trajcert.types import CliCommand


def test_cli_exposes_exact_public_command_set() -> None:
    parser = cli._parser()
    choices = parser._subparsers._group_actions[0].choices
    assert tuple(choices) == tuple(command.value for command in CliCommand)
    assert set(choices) == {
        "doctor",
        "preprocess",
        "plan",
        "smoke",
        "run",
        "status",
        "report",
    }


def test_run_accepts_only_experiment_family_and_overwrite() -> None:
    arguments = cli._parser().parse_args(
        ["run", "Population Sensitivity Utility", "--overwrite"]
    )
    assert arguments.command == "run"
    assert arguments.experiment_name == "Population Sensitivity Utility"
    assert arguments.overwrite is True


@pytest.mark.parametrize(
    "forbidden",
    ("--seed", "--rho", "--beta", "--partition", "--method", "--config"),
)
def test_run_rejects_public_scientific_knobs(forbidden: str) -> None:
    with pytest.raises(SystemExit):
        cli._parser().parse_args(["run", "Population Sensitivity Utility", forbidden, "1"])


def test_report_rejects_experiment_selection() -> None:
    with pytest.raises(SystemExit):
        cli._parser().parse_args(["report", "Population Sensitivity Utility"])


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
