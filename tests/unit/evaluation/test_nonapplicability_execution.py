from pathlib import Path

import pytest

from trajcert.domain.enums import ExperimentName
from trajcert.evaluation.nonapplicability_execution import (
    PlannedNonapplicabilityExecutionRequest,
    execute_planned_nonapplicability,
)
from trajcert.infrastructure.completion import CompletionExperimentName, completion_records


@pytest.mark.parametrize(
    "experiment_name",
    (
        ExperimentName.REAL_TRAJECTORY_VALIDATION,
        ExperimentName.FOREIGN_INFORMATION_NEGATIVE_CONTROL,
    ),
)
def test_zero_cell_experiments_write_verified_planned_nonapplicability_evidence(
    tmp_path: Path, experiment_name: ExperimentName
) -> None:
    evidence = execute_planned_nonapplicability(
        PlannedNonapplicabilityExecutionRequest(tmp_path, experiment_name)
    )

    records = completion_records(tmp_path, CompletionExperimentName(experiment_name.value))

    assert evidence.experiment_name is experiment_name
    assert len(records) == 1
    assert records[0].completed
    assert records[0].valid


def test_nonapplicability_executor_rejects_executable_experiments(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="zero-cell"):
        execute_planned_nonapplicability(
            PlannedNonapplicabilityExecutionRequest(tmp_path, ExperimentName.FAILURE_BOUNDARY_ATLAS)
        )
