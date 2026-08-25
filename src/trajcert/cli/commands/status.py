from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NewType

from trajcert.domain.enums import ExperimentName
from trajcert.infrastructure.completion import (
    CompletionExperimentName,
    CompletionRecord,
    completion_records,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
StatusExitCode = NewType("StatusExitCode", int)


@dataclass(frozen=True, slots=True)
class StatusCommandInput:
    experiment_name: ExperimentName | None


@dataclass(frozen=True, slots=True)
class StatusInspection:
    records: tuple[CompletionRecord, ...]


def execute(input_value: StatusCommandInput) -> StatusExitCode:
    inspect(input_value)
    return StatusExitCode(0)


def inspect(input_value: StatusCommandInput) -> StatusInspection:
    selected = (
        None
        if input_value.experiment_name is None
        else CompletionExperimentName(input_value.experiment_name.value)
    )
    return StatusInspection(completion_records(PROJECT_ROOT, selected))
