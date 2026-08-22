from __future__ import annotations

import argparse
from collections.abc import Sequence

SUCCESS_OR_SCIENTIFIC_NOOP = 0
USAGE_OR_UNKNOWN_NAME = 2
ENVIRONMENT_OR_PREREQUISITE_BLOCK = 10
TECHNICAL_EXECUTION_FAILURE = 20
COMPLETION_OR_EVIDENCE_FAILURE = 30


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
        parser.parse_args(arguments)
    except SystemExit as error:
        return SUCCESS_OR_SCIENTIFIC_NOOP if error.code == 0 else USAGE_OR_UNKNOWN_NAME
    return SUCCESS_OR_SCIENTIFIC_NOOP
