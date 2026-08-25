from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NewType

from trajcert.cli.commands import doctor, plan, preprocess, report, run, smoke, status
from trajcert.configuration.loading import load_configuration
from trajcert.configuration.models import CliConfiguration
from trajcert.domain.enums import ExperimentName

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CliToken = NewType("CliToken", str)
CliExitCode = NewType("CliExitCode", int)


@dataclass(frozen=True, slots=True)
class CliInvocation:
    tokens: tuple[CliToken, ...]


class CliExitCategory(StrEnum):
    SUCCESS_OR_SCIENTIFIC_NOOP = "success_or_scientific_noop"
    USAGE_OR_UNKNOWN_NAME = "usage_or_unknown_name"
    ENVIRONMENT_OR_PREREQUISITE_BLOCK = "environment_or_prerequisite_block"
    TECHNICAL_EXECUTION_FAILURE = "technical_execution_failure"
    COMPLETION_OR_EVIDENCE_FAILURE = "completion_or_evidence_failure"


class CliApplicationError(Exception):
    exit_category: CliExitCategory

    def __init__(self, exit_category: CliExitCategory) -> None:
        self.exit_category = exit_category


class EnvironmentOrPrerequisiteBlockError(CliApplicationError):
    def __init__(self) -> None:
        super().__init__(CliExitCategory.ENVIRONMENT_OR_PREREQUISITE_BLOCK)


class TechnicalExecutionFailureError(CliApplicationError):
    def __init__(self) -> None:
        super().__init__(CliExitCategory.TECHNICAL_EXECUTION_FAILURE)


class CompletionOrEvidenceFailureError(CliApplicationError):
    def __init__(self) -> None:
        super().__init__(CliExitCategory.COMPLETION_OR_EVIDENCE_FAILURE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trajcert")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor")
    preprocess = subcommands.add_parser("preprocess")
    preprocess.add_argument("dataset_name", nargs="?")
    preprocess.add_argument("--overwrite", action="store_true")
    subcommands.add_parser("plan")
    smoke = subcommands.add_parser("smoke")
    smoke.add_argument("--overwrite", action="store_true")
    run = subcommands.add_parser("run")
    run.add_argument("experiment_name")
    run.add_argument("--overwrite", action="store_true")
    status = subcommands.add_parser("status")
    status.add_argument("experiment_name", nargs="?")
    report = subcommands.add_parser("report")
    report.add_argument("experiment_name", nargs="?")
    report.add_argument("--overwrite", action="store_true")
    return parser


def main(invocation: CliInvocation | None = None) -> CliExitCode:
    parser = build_parser()
    try:
        parsed = parser.parse_args(_parser_arguments(invocation))
    except SystemExit as error:
        category = (
            CliExitCategory.SUCCESS_OR_SCIENTIFIC_NOOP
            if error.code == 0
            else CliExitCategory.USAGE_OR_UNKNOWN_NAME
        )
        return _exit_code(category)
    try:
        return CliExitCode(_dispatch(parsed))
    except CliApplicationError as error:
        return _exit_code(error.exit_category)


def exit_code_for(category: CliExitCategory) -> CliExitCode:
    return _exit_code(category)


def _parser_arguments(invocation: CliInvocation | None) -> Sequence[str] | None:
    if invocation is None:
        return None
    return invocation.tokens


def _exit_code(category: CliExitCategory) -> CliExitCode:
    exit_codes = _cli_configuration().exit_codes
    return CliExitCode(getattr(exit_codes, category.value))


def _cli_configuration() -> CliConfiguration:
    return load_configuration(PROJECT_ROOT / "configs/trajcert.yaml").cli


def _dispatch(parsed: argparse.Namespace) -> int:
    if parsed.command == "doctor":
        return doctor.execute()
    if parsed.command == "preprocess":
        dataset_name = (
            None if parsed.dataset_name is None else preprocess.DatasetName(parsed.dataset_name)
        )
        return preprocess.execute(
            preprocess.PreprocessCommandInput(
                dataset_name,
                preprocess.OverwriteRequested(parsed.overwrite),
            )
        )
    if parsed.command == "plan":
        return plan.execute()
    if parsed.command == "smoke":
        return smoke.execute(smoke.SmokeCommandInput(smoke.OverwriteRequested(parsed.overwrite)))
    if parsed.command == "run":
        return run.execute(
            run.RunCommandInput(
                ExperimentName(parsed.experiment_name),
                run.OverwriteRequested(parsed.overwrite),
            )
        )
    if parsed.command == "status":
        selected_experiment = (
            None if parsed.experiment_name is None else ExperimentName(parsed.experiment_name)
        )
        return status.execute(status.StatusCommandInput(selected_experiment))
    if parsed.command == "report":
        selected_experiment = (
            None if parsed.experiment_name is None else ExperimentName(parsed.experiment_name)
        )
        return report.execute(
            report.ReportCommandInput(
                selected_experiment,
                report.OverwriteRequested(parsed.overwrite),
            )
        )
    raise AssertionError("argparse accepted an undeclared command")
