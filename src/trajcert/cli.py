from __future__ import annotations

import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from enum import IntEnum, StrEnum
from typing import Literal, cast, overload

from trajcert.data.laws import LAW_DISPLAY_NAMES
from trajcert.exceptions import InvalidScientificDataError, TrajCertError
from trajcert.experiments.plan import (
    experiment_names,
)
from trajcert.experiments.smoke import SmokeResult
from trajcert.experiments.status import (
    ExperimentStatus,
)
from trajcert.experiments.workflows import (
    RunExperimentResult,
    doctor,
    experiment_status,
    plan_view,
    preprocess,
    report,
    run_experiment,
    smoke,
)
from trajcert.telemetry import configure_logging
from trajcert.types import (
    CliArgumentValue,
    CliCommand,
    DomainModel,
    ExperimentName,
    LawName,
    PublicExecutionState,
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


class CliReportAction(StrEnum):
    REUSED = "reused"
    RENDERED = "rendered"


class CliCheckState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


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


@overload
def _experiment_name(arguments: CliArguments, *, required: Literal[True]) -> ExperimentName: ...


@overload
def _experiment_name(
    arguments: CliArguments, *, required: Literal[False]
) -> ExperimentName | None: ...


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
