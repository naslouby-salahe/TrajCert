from __future__ import annotations

import argparse
from collections.abc import Sequence

from trajcert.cli.commands import doctor, plan, preprocess, report, run, smoke, status

SUCCESS_OR_SCIENTIFIC_NOOP = 0
USAGE_OR_UNKNOWN_NAME = 2
ENVIRONMENT_OR_PREREQUISITE_BLOCK = 10
TECHNICAL_EXECUTION_FAILURE = 20
COMPLETION_OR_EVIDENCE_FAILURE = 30


class CliApplicationError(Exception):
    exit_code: int

    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code


class EnvironmentOrPrerequisiteBlockError(CliApplicationError):
    def __init__(self) -> None:
        super().__init__(ENVIRONMENT_OR_PREREQUISITE_BLOCK)


class TechnicalExecutionFailureError(CliApplicationError):
    def __init__(self) -> None:
        super().__init__(TECHNICAL_EXECUTION_FAILURE)


class CompletionOrEvidenceFailureError(CliApplicationError):
    def __init__(self) -> None:
        super().__init__(COMPLETION_OR_EVIDENCE_FAILURE)


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


def main(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        parsed = parser.parse_args(arguments)
    except SystemExit as error:
        return SUCCESS_OR_SCIENTIFIC_NOOP if error.code == 0 else USAGE_OR_UNKNOWN_NAME
    try:
        return _dispatch(parsed)
    except CliApplicationError as error:
        return error.exit_code


def _dispatch(parsed: argparse.Namespace) -> int:
    if parsed.command == "doctor":
        return doctor.execute()
    if parsed.command == "preprocess":
        return preprocess.execute(parsed.dataset_name, parsed.overwrite)
    if parsed.command == "plan":
        return plan.execute()
    if parsed.command == "smoke":
        return smoke.execute(parsed.overwrite)
    if parsed.command == "run":
        return run.execute(parsed.experiment_name, parsed.overwrite)
    if parsed.command == "status":
        return status.execute(parsed.experiment_name)
    if parsed.command == "report":
        return report.execute(parsed.experiment_name, parsed.overwrite)
    raise AssertionError("argparse accepted an undeclared command")
