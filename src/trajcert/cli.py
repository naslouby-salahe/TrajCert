from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from enum import IntEnum

from trajcert.exceptions import InvalidScientificDataError, TrajCertError
from trajcert.experiments.registry import authoritative_registry
from trajcert.experiments.runner import SmokeResult
from trajcert.experiments.status import ExperimentStatus
from trajcert.operator import (
    RunExperimentResult,
    doctor,
    experiment_status,
    plan_view,
    preprocess,
    report,
    run_experiment,
    smoke,
)
from trajcert.types import CliCommand, PublicExecutionState


class CliExitCode(IntEnum):
    SUCCESS_OR_SCIENTIFIC_NOOP = 0
    USAGE_OR_UNKNOWN_NAME = 2
    ENVIRONMENT_OR_PREREQUISITE_BLOCK = 10
    TECHNICAL_EXECUTION_FAILURE = 20
    COMPLETION_OR_EVIDENCE_FAILURE = 30


def main() -> None:
    parser = _parser()
    arguments = parser.parse_args()
    command = CliCommand(arguments.command)
    try:
        _dispatch(parser, arguments, command)
    except InvalidScientificDataError as exc:
        print(f"TrajCert: {exc}", file=sys.stderr)
        code = (
            CliExitCode.COMPLETION_OR_EVIDENCE_FAILURE
            if command is CliCommand.REPORT
            else CliExitCode.ENVIRONMENT_OR_PREREQUISITE_BLOCK
        )
        raise SystemExit(code) from exc
    except TrajCertError as exc:
        print(f"TrajCert: {exc}", file=sys.stderr)
        raise SystemExit(CliExitCode.TECHNICAL_EXECUTION_FAILURE) from exc


def _dispatch(parser: ArgumentParser, arguments: Namespace, command: CliCommand) -> None:
    if command is CliCommand.DOCTOR:
        result = doctor()
        print(f"TrajCert doctor: {'PASS' if result.passed else 'FAIL'}")
    elif command is CliCommand.PREPROCESS:
        print(preprocess())
    elif command is CliCommand.PLAN:
        plan = plan_view()
        print(
            f"TrajCert plan: {plan.registry_total} cells "
            f"({plan.executable_cells} executable, {plan.invalid_cells} invalid)"
        )
    elif command is CliCommand.SMOKE:
        _print_smoke(smoke())
    elif command is CliCommand.RUN:
        name = _experiment_name(parser, arguments, required=True)
        assert name is not None
        _print_run(run_experiment(name, overwrite=bool(arguments.overwrite)))
    elif command is CliCommand.STATUS:
        name = _experiment_name(parser, arguments, required=False)
        if name is None:
            _print_project_status()
        else:
            _print_status(experiment_status(name))
    elif command is CliCommand.REPORT:
        name = _experiment_name(parser, arguments, required=False)
        exported = report(
            experiment_name=name,
            overwrite=bool(arguments.overwrite),
        )
        action = "reused" if exported.reused else "rendered"
        print(
            f"TrajCert report: {action} {exported.rendered_artifact_count} artifacts "
            f"from {exported.source_artifact_count} verified sources at {exported.target}"
        )


def _parser() -> ArgumentParser:
    parser = ArgumentParser(prog="trajcert")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (CliCommand.DOCTOR, CliCommand.PREPROCESS, CliCommand.PLAN, CliCommand.SMOKE):
        _ = subparsers.add_parser(command.value)
    run_parser = subparsers.add_parser(CliCommand.RUN.value)
    run_parser.add_argument("experiment_name")
    run_parser.add_argument("--overwrite", action="store_true")
    status_parser = subparsers.add_parser(CliCommand.STATUS.value)
    status_parser.add_argument("experiment_name", nargs="?")
    report_parser = subparsers.add_parser(CliCommand.REPORT.value)
    report_parser.add_argument("experiment_name", nargs="?")
    report_parser.add_argument("--overwrite", action="store_true")
    return parser


def _experiment_name(
    parser: ArgumentParser,
    arguments: Namespace,
    *,
    required: bool,
) -> str | None:
    value = getattr(arguments, "experiment_name", None)
    if value is None:
        if required:
            parser.error("experiment name is required")
        return None
    if not isinstance(value, str) or not value:
        parser.error("experiment name must be a non-empty descriptive name")
    known = {str(item.experiment_name) for item in authoritative_registry()}
    if value not in known:
        parser.error(f"unknown experiment name: {value}")
    return value


def _print_run(result: RunExperimentResult) -> None:
    print(
        f"{result.experiment_name}: {result.state.value} "
        f"({result.completed_cells} completed, {result.reused_cells} reused, "
        f"{result.failed_cells} failed, {result.blocked_cells} blocked)"
    )


def _print_status(status: ExperimentStatus) -> None:
    print(
        f"{status.experiment_name}: {status.state.value} "
        f"({status.completed_cells}/{status.total_cells} completed, "
        f"{status.invalid_cells} invalid, {status.failed_cells} failed, "
        f"{status.blocked_cells} blocked, {status.running_cells} running)"
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
        f"{failed} failed, {blocked} blocked, {running} running"
    )


def _print_smoke(result: SmokeResult) -> None:
    state = "PASS" if result.passed else "FAIL"
    print(f"TrajCert smoke: {state} ({result.passed_fixture_count}/6 fixtures passed)")
