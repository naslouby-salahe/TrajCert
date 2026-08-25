from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NewType

from trajcert.configuration.loading import load_configuration
from trajcert.domain.enums import ExperimentName
from trajcert.infrastructure.completion import CompletionExperimentName
from trajcert.reporting.export import (
    CompletionExportInput,
    export_project_summary_figure,
    export_project_summary_tables,
    export_verified_completion_records,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
OverwriteRequested = NewType("OverwriteRequested", bool)
ReportExitCode = NewType("ReportExitCode", int)


@dataclass(frozen=True, slots=True)
class ReportCommandInput:
    experiment_name: ExperimentName | None
    overwrite: OverwriteRequested


def execute(input_value: ReportCommandInput) -> ReportExitCode:
    selected = (
        None
        if input_value.experiment_name is None
        else CompletionExperimentName(input_value.experiment_name.value)
    )
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    try:
        export_verified_completion_records(CompletionExportInput(PROJECT_ROOT, selected))
        if input_value.experiment_name is None:
            export_project_summary_tables(PROJECT_ROOT)
            export_project_summary_figure(PROJECT_ROOT)
    except ValueError:
        return ReportExitCode(configuration.cli.exit_codes.completion_or_evidence_failure)
    return ReportExitCode(configuration.cli.exit_codes.success_or_scientific_noop)
