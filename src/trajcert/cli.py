from __future__ import annotations

from argparse import ArgumentParser, Namespace

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
from trajcert.types import CliCommand


def main() -> None:
    parser = _parser()
    arguments = parser.parse_args()
    command = CliCommand(arguments.command)
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
        _print_run(smoke())
    elif command is CliCommand.RUN:
        _print_run(
            run_experiment(
                _experiment_name(arguments),
                overwrite=bool(arguments.overwrite),
            )
        )
    elif command is CliCommand.STATUS:
        status = experiment_status(_experiment_name(arguments))
        print(
            f"{status.experiment_name}: {status.state.value} "
            f"({status.completed_cells}/{status.total_cells} completed, "
            f"{status.failed_cells} failed, {status.running_cells} running)"
        )
    elif command is CliCommand.REPORT:
        exported = report(overwrite=bool(arguments.overwrite))
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
    status_parser.add_argument("experiment_name")
    report_parser = subparsers.add_parser(CliCommand.REPORT.value)
    report_parser.add_argument("--overwrite", action="store_true")
    return parser


def _experiment_name(arguments: Namespace) -> str:
    value = getattr(arguments, "experiment_name", None)
    if not isinstance(value, str) or not value:
        raise ValueError("experiment name is required")
    return value


def _print_run(result: RunExperimentResult) -> None:
    print(
        f"{result.experiment_name}: {result.state.value} "
        f"({result.completed_cells} completed, {result.reused_cells} reused, "
        f"{result.failed_cells} failed, {result.blocked_cells} blocked)"
    )
