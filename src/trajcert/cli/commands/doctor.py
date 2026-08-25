from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import NewType

from trajcert.configuration.loading import load_configuration
from trajcert.infrastructure.completion import CompletionRecord, completion_records

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DoctorExitCode = NewType("DoctorExitCode", int)


@dataclass(frozen=True, slots=True)
class DoctorInspection:
    completion_records: tuple[CompletionRecord, ...]
    missing_runtime_dependencies: tuple[str, ...]


def execute() -> DoctorExitCode:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    inspection = inspect()
    return DoctorExitCode(
        configuration.cli.exit_codes.success_or_scientific_noop
        if not inspection.missing_runtime_dependencies
        else configuration.cli.exit_codes.environment_or_prerequisite_block
    )


def inspect() -> DoctorInspection:
    dependencies = ("mpmath", "numpy", "pydantic", "pyarrow", "scipy", "yaml")
    missing = tuple(dependency for dependency in dependencies if find_spec(dependency) is None)
    return DoctorInspection(completion_records(PROJECT_ROOT), missing)
