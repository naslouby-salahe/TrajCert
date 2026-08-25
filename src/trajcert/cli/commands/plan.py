from __future__ import annotations

from pathlib import Path
from typing import NewType

from trajcert.configuration.loading import load_configuration
from trajcert.experiments.planning import materialized_plan_rows

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PlanExitCode = NewType("PlanExitCode", int)


def execute() -> PlanExitCode:
    configuration = load_configuration(PROJECT_ROOT / "configs/trajcert.yaml")
    materialized_plan_rows(configuration)
    return PlanExitCode(0)
