from __future__ import annotations

from argparse import ArgumentParser

from trajcert.config import load_config
from trajcert.constants import PRODUCTION_CONFIG_PATH
from trajcert.data.laws import build_full_law, configured_laws
from trajcert.data.partitions import configured_partitions
from trajcert.types import CliCommand


def main() -> None:
    parser = ArgumentParser(prog="trajcert")
    parser.add_argument(
        "command",
        choices=tuple(command.value for command in CliCommand),
    )
    arguments = parser.parse_args()
    command = CliCommand(arguments.command)

    if command is CliCommand.DOCTOR:
        _doctor()


def _doctor() -> None:
    configuration = load_config(PRODUCTION_CONFIG_PATH)
    partitions = configured_partitions(configuration)
    laws = configured_laws(configuration)

    for law in laws:
        build_full_law(law, partitions[0].band_count)

    print("TrajCert doctor: configuration and core scientific inputs are valid")
